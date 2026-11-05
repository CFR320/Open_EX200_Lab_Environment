#!/usr/bin/env bash
set -euo pipefail

grub_defaults=/etc/default/grub
if [[ ! -f "$grub_defaults" ]]; then
  echo "GRUB defaults file not found: $grub_defaults" >&2
  exit 1
fi

sed -i -E '/^[[:space:]]*GRUB_TIMEOUT(_STYLE)?=/d' "$grub_defaults"
printf '%s\n' 'GRUB_TIMEOUT=60' 'GRUB_TIMEOUT_STYLE=menu' >> "$grub_defaults"
grub2-editenv /boot/grub2/grubenv unset menu_auto_hide
grub2-mkconfig -o /boot/grub2/grub.cfg
