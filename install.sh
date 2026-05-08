#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

install -d "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
install -m 0755 "$SCRIPT_DIR/tailscale_exit_node_tray.py" "$BIN_DIR/tailscale-exit-node-tray"
install -m 0644 "$SCRIPT_DIR/tailscale-exit-node-tray.desktop" "$APP_DIR/tailscale-exit-node-tray.desktop"
install -m 0644 "$SCRIPT_DIR/tailscale-exit-node-tray.svg" "$ICON_DIR/tailscale-exit-node-tray.svg"

sed -i "s|^Exec=.*$|Exec=${BIN_DIR}/tailscale-exit-node-tray|" "$APP_DIR/tailscale-exit-node-tray.desktop"
sed -i "s|^Icon=.*$|Icon=${ICON_DIR}/tailscale-exit-node-tray.svg|" "$APP_DIR/tailscale-exit-node-tray.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

printf 'Installed launcher to %s\n' "$APP_DIR/tailscale-exit-node-tray.desktop"
printf 'Installed executable to %s\n' "$BIN_DIR/tailscale-exit-node-tray"
printf 'Installed icon to %s\n' "$ICON_DIR/tailscale-exit-node-tray.svg"
