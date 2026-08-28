# Linux fixes for MacBook8,1

Practical fixes for the 12-inch Retina MacBook (Early 2015), tested on Arch,
CachyOS, and Omarchy with Linux 6.x–7.x.

The core fix keeps the internal keyboard and trackpad working at boot and
after suspend. This repository also documents working internal speakers and a
few optional power and hardware tweaks.

## Current status

This is the state of the machine used to develop and verify the fixes, last
checked on Omarchy 4.0.1 with Linux 7.1.9:

| Hardware | Status | Notes |
|---|---|---|
| Keyboard and trackpad | Working | Stock `applespi`, forced into reliable PIO mode |
| Suspend and resume | Working | Resume hook restores the Apple SPI controller |
| Internal speakers | Working | Patched DKMS driver, PipeWire, and RealtimeKit |
| Wi-Fi | Working | `brcmfmac`; a missing CLM blob may limit available channels |
| Bluetooth | Not configured | Requires an out-of-tree driver and Apple firmware |
| FaceTime HD camera | Not configured | No in-tree driver; it can be powered down to save energy |

The reference machine has completed repeated S3 suspend/resume cycles with the
keyboard, trackpad, speakers, and Wi-Fi recovering successfully.

## Quick install

On an installed Arch-family system:

```bash
git clone https://github.com/projectmushroom/macbook81-linux-fixes.git
cd macbook81-linux-fixes
sudo ./apply.sh
sudo reboot
```

The installer is model-gated to `MacBook8,1`, is safe to run more than once,
and installs only the core keyboard/trackpad fixes. It handles Limine directly
and prints manual instructions for other bootloaders.

Python 3 is required by the resume hook.

After reboot, run the read-only health check as your normal desktop user:

```bash
./diagnostics/health-check.sh
```

A healthy core setup reports:

- `pci-stub.ids=8086:9ce0` on the kernel command line
- the LPSS DMA controller bound to `pci-stub`
- an `Apple SPI Touchpad` input node
- the SPI resume hook installed
- matching suspend-entry and suspend-exit counts
- no failed services or storage errors

## Internal speakers

Speakers require the separate patched driver from
[`thomas-shirley/macbook8.1-speaker-driver`](https://github.com/thomas-shirley/macbook8.1-speaker-driver).
Follow [audio/README.md](audio/README.md) for the Arch/Omarchy installation,
PipeWire setup, RealtimeKit dependency, verification, and resume recovery.

## What the core fix does

### Reliable keyboard and trackpad at boot

The LPSS DMA controller at `0000:00:15.0` does not deliver completion
interrupts reliably on this model. The SPI driver then times out and the Apple
input devices remain unusable.

The deterministic workaround is:

```text
pci-stub.ids=8086:9ce0
```

This reserves the unused DMA controller and makes `spi-pxa2xx` use its working
PIO path. The repository also includes a defensive module blacklist and a
warn-only Arch pacman hook that checks the boot parameter after updates.

### Recovery after suspend

S3 suspend clears private clock, reset, and chip-select registers in the Apple
SPI controller. Apple's firmware does not restore them for Linux.

[`fixes/system-sleep/95-macbook-spi-resume`](fixes/system-sleep/95-macbook-spi-resume)
restores those registers and rebinds the SPI driver after wake. Install it to
`/usr/lib/systemd/system-sleep/`; current systemd does not use
`/etc/systemd/system-sleep/` for these hooks.

## Manual bootloader setup

The installer handles Limine automatically. For another bootloader, add
`pci-stub.ids=8086:9ce0` yourself:

- **GRUB:** append it to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`,
  then run `grub-mkconfig -o /boot/grub/grub.cfg`.
- **systemd-boot:** append it to the `options` line of the relevant loader
  entry.
- **Limine:** use [`fixes/limine/20-macbook.conf`](fixes/limine/20-macbook.conf)
  with `limine-entry-tool`, then run `limine-update`.

Reboot after changing the kernel command line.

## Expected log messages

The resume hooks deliberately detach and re-probe hardware. A short burst of
the following messages around wake is expected when the devices subsequently
return:

- `applespi` transfer timeouts (`-110`)
- one or two Apple SPI CRC mismatches
- HDA `spurious response` messages with the patched speaker driver
- a fresh `brcmfmac` firmware load

Judge recovery by device state rather than raw log counts. The health-check
script does this automatically. Investigate when the touchpad node or speaker
node is missing, Wi-Fi does not reconnect, or suspend entries and exits do not
match.

## Optional extras

- **Backlight:** add `acpi_backlight=native` for fine-grained
  `intel_backlight` control. It is included in the Limine drop-in.
- **Power:** [`fixes/tlp/00-macbook81.conf`](fixes/tlp/00-macbook81.conf)
  contains the tested TLP settings. Keep `00:15.0` on the runtime-PM denylist.
- **Camera power:**
  [`fixes/systemd/facetime-cam-d3.service`](fixes/systemd/facetime-cam-d3.service)
  puts the unsupported camera into D3hot. Skip it if you intend to install an
  out-of-tree camera driver.
- **Wi-Fi transition mode:** if WPA2/WPA3 transition networks fail, try
  `options brcmfmac feature_disable=0x82000`. Do not add it when Wi-Fi already
  works normally.

## Remove the core fixes

For a Limine installation made by `apply.sh`:

```bash
sudo rm /etc/modprobe.d/macbook-spi.conf
sudo rm /usr/lib/systemd/system-sleep/95-macbook-spi-resume
sudo rm /etc/limine-entry-tool.d/20-macbook.conf
sudo rm /etc/pacman.d/hooks/99-macbook-spi-check.hook
sudo rm /usr/local/bin/macbook-spi-check
sudo limine-update
sudo reboot
```

For GRUB or systemd-boot, remove `pci-stub.ids=8086:9ce0` from the kernel
command line, regenerate the bootloader configuration if required, remove the
resume hook and module blacklist, and reboot.

Removing these fixes may leave the internal keyboard and trackpad unusable, so
have an external USB input device available first.

## Repository layout

- [`fixes/`](fixes/) — installable SPI, suspend, bootloader, TLP, and camera files
- [`audio/`](audio/) — working internal-speaker installation notes
- [`diagnostics/`](diagnostics/) — health check and low-level investigation tools
- [`omarchy-iso/`](omarchy-iso/) — notes and patches for an Omarchy installer ISO

The low-level root-cause analysis and `/dev/mem` tools live in
[diagnostics/README.md](diagnostics/README.md), keeping this page focused on
installation and everyday use.
