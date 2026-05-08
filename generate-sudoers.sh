#!/usr/bin/env bash
set -euo pipefail

tailscale_bin="$(command -v tailscale)"
if [[ -z "$tailscale_bin" ]]; then
    printf 'tailscale command not found in PATH\n' >&2
    exit 1
fi

target_user="${SUDO_USER:-$(id -un)}"
sudoers_name="${target_user}-tailscale-exit-node-tray"

mapfile -t exit_targets < <(
    "$tailscale_bin" exit-node list | awk '/^[[:space:]]*[0-9a-fA-F:.]+[[:space:]]+/ { print $1 "\n" $2 }' | sort -u
)

printf '# Install as: /etc/sudoers.d/%s\n' "$sudoers_name"
printf '# Validate with: sudo visudo -cf /etc/sudoers.d/%s\n' "$sudoers_name"
printf '%s ALL=(root) NOPASSWD: \\\n' "$target_user"
printf '    %s set --exit-node=' "$tailscale_bin"

for target in "${exit_targets[@]}"; do
    printf ', \\\n'
    printf '    %s set --exit-node=%s' "$tailscale_bin" "$target"
done

printf '\n'
