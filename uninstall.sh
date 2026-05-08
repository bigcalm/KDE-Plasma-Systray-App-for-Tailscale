#!/usr/bin/env bash
set -euo pipefail

BIN_PATH="${HOME}/.local/bin/tailscale-exit-node-tray"
DESKTOP_PATH="${HOME}/.local/share/applications/tailscale-exit-node-tray.desktop"
ICON_PATH="${HOME}/.local/share/icons/hicolor/scalable/apps/tailscale-exit-node-tray.svg"

pkill -f "tailscale_exit_node_tray.py|tailscale-exit-node-tray" || true

rm -f "$BIN_PATH"
rm -f "$DESKTOP_PATH"
rm -f "$ICON_PATH"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

printf 'Removed %s\n' "$BIN_PATH"
printf 'Removed %s\n' "$DESKTOP_PATH"
printf 'Removed %s\n' "$ICON_PATH"
printf 'If you created a sudoers file for this app, remove /etc/sudoers.d/%s-tailscale-exit-node-tray separately.\n' "$(id -un)"
