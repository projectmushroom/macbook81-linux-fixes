#!/usr/bin/env bash
# Read-only MacBook8,1 health check. Run as the logged-in desktop user.
set -u

failures=0
warnings=0

pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; failures=$((failures + 1)); }
info() { printf 'INFO  %s\n' "$*"; }

count_kernel() {
  journalctl -b -k --no-pager 2>/dev/null | grep -Eic "$1" || true
}

product=$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)
if [[ $product != MacBook8,1 ]]; then
  fail "DMI reports '${product:-unknown}', not MacBook8,1"
else
  pass "DMI model is MacBook8,1"
fi

if grep -qw 'pci-stub.ids=8086:9ce0' /proc/cmdline; then
  pass "LPSS DMA controller is disabled on the kernel command line"
else
  fail "missing pci-stub.ids=8086:9ce0 on the kernel command line"
fi

dma_driver=$(basename "$(readlink /sys/bus/pci/devices/0000:00:15.0/driver 2>/dev/null)" 2>/dev/null || true)
if [[ $dma_driver == pci-stub ]]; then
  pass "LPSS DMA controller is bound to pci-stub"
else
  fail "LPSS DMA controller is bound to '${dma_driver:-nothing}', not pci-stub"
fi

if grep -q 'Name="Apple SPI Touchpad"' /proc/bus/input/devices 2>/dev/null; then
  pass "Apple SPI touchpad is responding"
else
  fail "Apple SPI touchpad input node is absent"
fi

sleep_hook=/usr/lib/systemd/system-sleep/95-macbook-spi-resume
if [[ -x $sleep_hook ]]; then
  pass "SPI resume hook is installed"
else
  fail "SPI resume hook is missing or not executable"
fi

suspend_in=$(count_kernel 'PM: suspend entry')
suspend_out=$(count_kernel 'PM: suspend exit')
if [[ $suspend_in -eq $suspend_out ]]; then
  pass "suspend/resume pairs match ($suspend_in/$suspend_out)"
else
  warn "suspend/resume pairs differ ($suspend_in entries, $suspend_out exits)"
fi

spi_timeouts=$(count_kernel 'applespi.*SPI transfer timed out')
spi_recoveries=$(count_kernel 'applespi.*modeswitch done')
if [[ $spi_timeouts -gt 0 ]]; then
  info "$spi_timeouts Apple SPI timeouts and $spi_recoveries successful mode switches this boot"
  info "timeouts during the resume hook's unbind/rebind window are expected"
fi

if command -v modinfo >/dev/null && [[ $(modinfo -n snd-hda-intel 2>/dev/null) == */updates/dkms/* ]]; then
  pass "patched DKMS HDA driver is active"
else
  warn "patched DKMS HDA driver is not active"
fi

single_cmd=$(cat /sys/module/snd_hda_intel/parameters/single_cmd 2>/dev/null || true)
power_save=$(cat /sys/module/snd_hda_intel/parameters/power_save 2>/dev/null || true)
if [[ $single_cmd == 1 && $power_save == 0 ]]; then
  pass "MacBook audio module parameters are active"
else
  warn "audio parameters are single_cmd=${single_cmd:-?}, power_save=${power_save:-?}; expected 1 and 0"
fi

if command -v wpctl >/dev/null && wpctl status 2>/dev/null | grep -q 'MacBook Speaker'; then
  pass "MacBook speaker PipeWire node is present"
else
  warn "MacBook speaker PipeWire node is absent"
fi

audio_responses=$(count_kernel 'snd_hda_intel.*spurious response')
[[ $audio_responses -eq 0 ]] || info "$audio_responses HDA spurious-response messages this boot; expected with the current speaker patch unless audio malfunctions"

if systemctl -q is-active rtkit-daemon.service 2>/dev/null; then
  pass "RealtimeKit is active for PipeWire"
else
  warn "RealtimeKit is not active; on Arch install it with: sudo pacman -S rtkit"
fi

wifi_driver=$(basename "$(readlink /sys/class/net/wlp1s0/device/driver 2>/dev/null)" 2>/dev/null || true)
if [[ $wifi_driver == brcmfmac ]]; then
  pass "Broadcom Wi-Fi uses brcmfmac"
else
  warn "Wi-Fi driver is '${wifi_driver:-unknown}', not brcmfmac"
fi

clm_missing=$(count_kernel 'brcmfmac.*no clm_blob available')
[[ $clm_missing -eq 0 ]] || warn "Broadcom CLM blob is absent; Wi-Fi may expose fewer regulatory channels"

if [[ -e /sys/bus/pci/devices/0000:02:00.0/driver ]]; then
  pass "FaceTime HD camera has a kernel driver"
else
  info "FaceTime HD camera has no kernel driver (normal unless an out-of-tree driver is installed)"
fi

battery_capacity=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || true)
battery_health=$(awk -F= '
  /POWER_SUPPLY_(ENERGY|CHARGE)_FULL_DESIGN=/ { design=$2 }
  /POWER_SUPPLY_(ENERGY|CHARGE)_FULL=/ { full=$2 }
  END { if (design > 0) printf "%.0f", 100 * full / design }
' /sys/class/power_supply/BAT0/uevent 2>/dev/null)
[[ -z $battery_capacity ]] || info "battery charge is ${battery_capacity}%"
[[ -z $battery_health ]] || info "battery health is approximately ${battery_health}% of design capacity"

failed_system=$(systemctl --failed --no-legend --plain 2>/dev/null | grep -c . || true)
failed_user=$(systemctl --user --failed --no-legend --plain 2>/dev/null | grep -c . || true)
if [[ $failed_system -eq 0 && $failed_user -eq 0 ]]; then
  pass "no failed system or user services"
else
  warn "$failed_system system and $failed_user user services are failed"
fi

storage_errors=$(count_kernel 'I/O error|EXT4-fs.*error|BTRFS.*error|nvme.*(error|timeout|reset)')
if [[ $storage_errors -eq 0 ]]; then
  pass "no storage or filesystem errors in this boot"
else
  fail "$storage_errors storage/filesystem errors in this boot"
fi

printf '\nSummary: %d failure(s), %d warning(s).\n' "$failures" "$warnings"
[[ $failures -eq 0 ]]
