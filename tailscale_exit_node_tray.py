#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QLockFile, QStandardPaths, QTimer, Qt
from PyQt6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


STATUS_NOT_CONNECTED = "not_connected"
STATUS_CONNECTED = "connected"
STATUS_EXIT_NODE = "exit_node"
COMMAND_TIMEOUT_SECONDS = 10
REFRESH_INTERVAL_MS = 15_000
TAILSCALE_COMMAND = shutil.which("tailscale") or "tailscale"
SUDO_COMMAND = shutil.which("sudo") or "sudo"


@dataclass(frozen=True)
class ExitNode:
    ip: str
    hostname: str
    country: str
    city: str
    status: str

    @property
    def label(self) -> str:
        location = ", ".join(part for part in (self.country, self.city) if part and part != "-")
        if not location:
            return self.hostname
        return f"{self.hostname} ({location})"

    @property
    def command_target(self) -> str:
        return self.hostname or self.ip


@dataclass(frozen=True)
class AppState:
    tray_state: str
    backend_state: str
    current_exit_node: str | None
    exit_nodes: list[ExitNode]
    error_message: str | None = None


class CommandError(RuntimeError):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class TailscaleExitNodeTray:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Tailscale Exit Node Tray")
        self.app.setQuitOnLastWindowClosed(False)

        self.menu = QMenu()

        self.tray = QSystemTrayIcon()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_tray_activated)

        self.icons = {
            STATUS_NOT_CONNECTED: self.build_icon(QColor("#6b7280")),
            STATUS_CONNECTED: self.build_icon(QColor("#2563eb")),
            STATUS_EXIT_NODE: self.build_icon(QColor("#16a34a")),
        }

        self.timer = QTimer()
        self.timer.setInterval(REFRESH_INTERVAL_MS)
        self.timer.timeout.connect(self.refresh_state)

    def run(self) -> int:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise SystemExit("No system tray is available in this session.")

        self.refresh_state()
        self.tray.show()
        self.timer.start()
        return self.app.exec()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.refresh_state()

    def refresh_state(self) -> None:
        state = self.load_state()
        self.tray.setIcon(self.icons[state.tray_state])
        self.tray.setToolTip(self.build_tooltip(state))
        self.rebuild_menu(state)

    def load_state(self) -> AppState:
        try:
            status_data = self.run_command([TAILSCALE_COMMAND, "status", "--json"])
            exit_node_output = self.run_command(
                [TAILSCALE_COMMAND, "exit-node", "list"],
                expect_json=False,
            )
        except CommandError as error:
            return AppState(
                tray_state=STATUS_NOT_CONNECTED,
                backend_state="error",
                current_exit_node=None,
                exit_nodes=[],
                error_message=error.user_message,
            )

        backend_state = str(status_data.get("BackendState") or "unknown")
        auth_url = status_data.get("AuthURL") or ""
        self_data = status_data.get("Self") or {}
        connected_to_tailnet = backend_state == "Running" and not auth_url and bool(self_data)

        current_exit_node = None
        if connected_to_tailnet:
            current_exit_node = self.find_current_exit_node(status_data)

        tray_state = STATUS_NOT_CONNECTED
        if connected_to_tailnet:
            tray_state = STATUS_EXIT_NODE if current_exit_node else STATUS_CONNECTED

        return AppState(
            tray_state=tray_state,
            backend_state=backend_state,
            current_exit_node=current_exit_node,
            exit_nodes=self.parse_exit_node_list(exit_node_output),
        )

    def rebuild_menu(self, state: AppState) -> None:
        self.menu.clear()

        title = QAction(self.build_tooltip(state), self.menu)
        title.setEnabled(False)
        self.menu.addAction(title)
        self.menu.addSeparator()

        if state.error_message:
            error_action = QAction(state.error_message, self.menu)
            error_action.setEnabled(False)
            self.menu.addAction(error_action)
            help_action = QAction("See README for setup help", self.menu)
            help_action.setEnabled(False)
            self.menu.addAction(help_action)
        elif state.tray_state == STATUS_NOT_CONNECTED:
            disconnected_action = QAction("Not connected to a tailnet", self.menu)
            disconnected_action.setEnabled(False)
            self.menu.addAction(disconnected_action)
        else:
            clear_action = QAction("No exit node", self.menu)
            clear_action.setCheckable(True)
            clear_action.setChecked(state.current_exit_node is None)
            clear_action.triggered.connect(lambda checked=False: self.set_exit_node(""))
            self.menu.addAction(clear_action)

            if state.exit_nodes:
                for node in state.exit_nodes:
                    action = QAction(node.label, self.menu)
                    action.setCheckable(True)
                    action.setChecked(self.node_matches_current(node, state.current_exit_node))
                    action.triggered.connect(
                        lambda checked=False, target=node.command_target: self.set_exit_node(target)
                    )
                    self.menu.addAction(action)
            else:
                unavailable_action = QAction("No exit nodes available", self.menu)
                unavailable_action.setEnabled(False)
                self.menu.addAction(unavailable_action)

        self.menu.addSeparator()

        refresh_action = QAction("Refresh", self.menu)
        refresh_action.triggered.connect(self.refresh_state)
        self.menu.addAction(refresh_action)

        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def set_exit_node(self, target: str) -> None:
        try:
            self.run_command(
                [SUDO_COMMAND, TAILSCALE_COMMAND, "set", f"--exit-node={target}"],
                expect_json=False,
            )
        except CommandError as error:
            self.tray.showMessage(
                "Tailscale Exit Node Tray",
                error.user_message,
                QSystemTrayIcon.MessageIcon.Critical,
                8000,
            )
            return

        self.refresh_state()
        if target:
            message = f"Using exit node {target}."
        else:
            message = "Exit node disabled."
        self.tray.showMessage(
            "Tailscale Exit Node Tray",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def run_command(self, command: list[str], expect_json: bool = True):
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as error:
            command_name = Path(error.filename or command[0]).name
            if command_name == "tailscale":
                raise CommandError("Tailscale is not installed or is not in PATH.") from error
            if command_name == "sudo":
                raise CommandError("sudo is not installed or is not in PATH.") from error
            raise CommandError(f"Required command not found: {command_name}") from error
        except subprocess.TimeoutExpired as error:
            raise CommandError("Tailscale did not respond in time. Try again in a moment.") from error
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or error.stdout or "command failed").strip()
            raise CommandError(self.describe_command_failure(command, stderr)) from error

        output = completed.stdout.strip()
        if expect_json:
            try:
                return json.loads(output)
            except json.JSONDecodeError as error:
                raise CommandError("Tailscale returned an unexpected response.") from error
        return output

    def describe_command_failure(self, command: list[str], stderr: str) -> str:
        lowered = stderr.lower()
        command_text = " ".join(command)

        if "failed to connect to local tailscaled" in lowered:
            return "Tailscale is installed, but the local tailscaled service is not available."
        if "not connected to any control plane" in lowered or "logged out" in lowered:
            return "Tailscale is not currently connected to a tailnet."
        if (
            "sudoers" in lowered
            or "a password is required" in lowered
            or "not allowed to execute" in lowered
            or "a terminal is required to authenticate" in lowered
        ):
            return "sudo is not configured for this app yet. Generate and install the sudoers file from the README."
        if "permission denied" in lowered and command and command[0] == SUDO_COMMAND:
            return "This action was blocked by sudo. Check the generated sudoers file and try again."
        if command[:2] == [TAILSCALE_COMMAND, "exit-node"]:
            return "Could not load the exit-node list from Tailscale."
        if command[:2] == [TAILSCALE_COMMAND, "status"]:
            return "Could not read Tailscale status."
        if command[:3] == [SUDO_COMMAND, TAILSCALE_COMMAND, "set"]:
            return "Could not change the Tailscale exit node."
        if stderr:
            return f"Command failed: {stderr}"
        return f"Command failed: {command_text}"

    def parse_exit_node_list(self, output: str) -> list[ExitNode]:
        nodes: list[ExitNode] = []
        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("IP"):
                continue

            parts = re.split(r"\s{2,}", stripped)
            if len(parts) < 5:
                continue

            ip, hostname, country, city, status = parts[:5]
            nodes.append(
                ExitNode(
                    ip=ip,
                    hostname=hostname,
                    country=country,
                    city=city,
                    status=status,
                )
            )
        return nodes

    def find_current_exit_node(self, status_data: dict) -> str | None:
        peers = status_data.get("Peer") or {}
        for peer in peers.values():
            if not peer.get("ExitNode"):
                continue

            dns_name = str(peer.get("DNSName") or "").strip()
            if dns_name:
                return dns_name.rstrip(".")

            host_name = str(peer.get("HostName") or "").strip()
            if host_name:
                return host_name

            ips = peer.get("TailscaleIPs") or []
            if ips:
                return str(ips[0])
        return None

    def node_matches_current(self, node: ExitNode, current_exit_node: str | None) -> bool:
        if not current_exit_node:
            return False

        node_keys = {
            node.hostname.rstrip("."),
            node.hostname.split(".", 1)[0],
            node.ip,
        }
        return current_exit_node.rstrip(".") in node_keys

    def build_tooltip(self, state: AppState) -> str:
        if state.error_message:
            return f"Tailscale error: {state.error_message}"
        if state.tray_state == STATUS_NOT_CONNECTED:
            return "Tailscale: not connected to a tailnet"
        if state.current_exit_node:
            return f"Tailscale: using exit node {state.current_exit_node}"
        return "Tailscale: connected, no exit node"

    def build_icon(self, color: QColor) -> QIcon:
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ring_pen = QPen(QColor("#1f2937"))
        ring_pen.setWidth(2)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(3, 3, 16, 16)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(7, 7, 8, 8)

        painter.end()
        return QIcon(pixmap)


def main() -> int:
    runtime_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    if not runtime_dir:
        runtime_dir = str(Path.home())

    lock_file = QLockFile(str(Path(runtime_dir) / "tailscale-exit-node-tray.lock"))
    lock_file.setStaleLockTime(0)
    if not lock_file.tryLock(0):
        return 0

    desktop_files = [
        Path.home() / ".local/share/applications/tailscale-exit-node-tray.desktop",
        Path("/usr/share/applications/tailscale-exit-node-tray.desktop"),
    ]
    if any(path.exists() for path in desktop_files):
        QGuiApplication.setDesktopFileName("tailscale-exit-node-tray")

    tray = TailscaleExitNodeTray()
    tray.lock_file = lock_file
    return tray.run()


if __name__ == "__main__":
    raise SystemExit(main())
