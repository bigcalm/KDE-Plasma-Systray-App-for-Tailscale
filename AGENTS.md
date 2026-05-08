# AGENTS.md

## Project summary

This repository contains a small KDE Plasma 6 tray app for managing Tailscale exit nodes.

Main entry points:

- `tailscale_exit_node_tray.py` - PyQt6 tray application
- `install.sh` - installs the launcher, executable, and icon for the current user
- `uninstall.sh` - removes the installed files for the current user
- `generate-sudoers.sh` - generates a restrictive sudoers file for the current user and current exit-node list

## Stack

- Python 3
- PyQt6
- Tailscale CLI
- KDE Plasma 6

## Behavioural constraints

- The tray menu is intentionally right-click only.
- Do not reintroduce left-click popup handling unless Wayland behaviour is revalidated. Plasma/Wayland rejected the popup path with `Failed to create grabbing popup`.
- The app is single-instance only via `QLockFile`.
- The app should not require `sudo` for status reads or exit-node listing.
- The app only uses `sudo` for `tailscale set --exit-node=...`.
- User-facing error messages should stay friendly and action-oriented.

## Desktop integration constraints

- Keep the desktop file icon as an absolute path in the installed `.desktop` file.
- This was needed because Plasma application-menu caching showed stale icons when resolving by icon name.
- The shipped desktop file can keep `Icon=tailscale-exit-node-tray`, but `install.sh` should continue rewriting it to the installed absolute SVG path.

## Sudoers constraints

- Keep `generate-sudoers.sh` restrictive.
- Do not broaden it to allow `/usr/bin/tailscale *` or `/usr/bin/tailscale set *`.
- Do not add `requiretty` or similar sudo defaults; that was not portable on this system.
- The generated sudoers output should remain suitable for manual review before copying into `/etc/sudoers.d/`.

## Editing guidance

- Prefer small changes.
- Preserve the current PyQt6 single-file structure unless there is a clear need to split it.
- Avoid adding dependencies.
- Keep icons and launcher assets simple and locally installable.
- If changing user-visible behaviour, update `README.md` in the same change.

## Verification

Useful checks:

```bash
python3 -m py_compile tailscale_exit_node_tray.py
bash -n install.sh
bash -n uninstall.sh
bash -n generate-sudoers.sh
```

Useful install cycle:

```bash
./install.sh
./uninstall.sh
```

Useful runtime checks:

```bash
python3 ./tailscale_exit_node_tray.py
tailscale status --json
tailscale exit-node list
```

## Files commonly updated together

- `tailscale_exit_node_tray.py` and `README.md`
- `tailscale-exit-node-tray.desktop`, `install.sh`, and `uninstall.sh`
- `generate-sudoers.sh` and `README.md`

## Generated files

These should remain untracked by git:

- `__pycache__/`
- `*.pyc`, `*.pyo`, `*.pyd`
- `tailscale-exit-node-tray.sudoers`
