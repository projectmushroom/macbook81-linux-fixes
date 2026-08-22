#!/bin/bash
# Apply the MacBook8,1 fixes on an installed Arch-family system.
# Run as root from the repo root: sudo ./apply.sh
# Idempotent. Optional extras (TLP config, camera-off service) are printed at
# the end rather than installed.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }
product=$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)
if [[ $product != "MacBook8,1" ]]; then
  echo "This machine reports '$product', not MacBook8,1." >&2
  echo "The fixes are model-specific; refusing. (Edit this check if you know better.)" >&2
  exit 1
fi

here=$(cd "$(dirname "$0")" && pwd)
PARAM="pci-stub.ids=8086:9ce0"

install -Dm644 "$here/fixes/modprobe.d/macbook-spi.conf" /etc/modprobe.d/macbook-spi.conf
install -Dm755 "$here/fixes/system-sleep/95-macbook-spi-resume" /usr/lib/systemd/system-sleep/95-macbook-spi-resume

# Kernel cmdline: handle limine-entry-tool setups directly, otherwise instruct.
if [[ -d /etc/limine-entry-tool.d ]]; then
  install -Dm644 "$here/fixes/limine/20-macbook.conf" /etc/limine-entry-tool.d/20-macbook.conf
  if command -v limine-update >/dev/null; then
    limine-update
  else
    echo "NOTE: installed the limine drop-in but 'limine-update' was not found;" >&2
    echo "      regenerate your limine config manually." >&2
  fi
  # The pacman guard only makes sense where the limine drop-in mechanism exists.
  install -Dm644 "$here/fixes/pacman-hooks/99-macbook-spi-check.hook" /etc/pacman.d/hooks/99-macbook-spi-check.hook
  install -Dm755 "$here/fixes/pacman-hooks/macbook-spi-check" /usr/local/bin/macbook-spi-check
elif [[ -f /etc/default/grub ]]; then
  if grep -q "$PARAM" /etc/default/grub; then
    echo "GRUB already carries $PARAM"
  else
    echo "ACTION NEEDED: add '$PARAM' to GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub,"
    echo "then run: grub-mkconfig -o /boot/grub/grub.cfg"
  fi
else
  echo "ACTION NEEDED: add '$PARAM' to your kernel command line (bootloader not recognized)."
fi

echo
echo "Core fixes installed. Reboot, then verify:"
echo "  grep pci-stub /proc/cmdline"
echo "  grep -i 'Name=.*Apple SPI' /proc/bus/input/devices   # want: Apple SPI Touchpad"
echo
echo "Optional extras (see README):"
echo "  fixes/tlp/00-macbook81.conf          -> /etc/tlp.d/  (install tlp first)"
echo "  fixes/systemd/facetime-cam-d3.service -> /etc/systemd/system/ + systemctl enable"
