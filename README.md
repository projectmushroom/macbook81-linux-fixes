# MacBook8,1 (12" Retina MacBook, Early 2015) Linux fixes

Working, root-caused fixes for the bugs that make Linux on this machine
miserable: the **dead internal keyboard/trackpad** (applespi `-110` timeouts),
the **keyboard dying after suspend/resume**, and notes for the now-working
**internal speakers**. Plus a few optional extras.

The keyboard/trackpad fixes use stock in-tree drivers — no DKMS module and
nothing to rebuild on kernel updates. The separate speaker solution does use
DKMS. Tested on Arch-family distros (CachyOS, Omarchy) with kernels 6.x–7.x;
the keyboard analysis and boot parameter apply to any distro.

## TL;DR

Add this to your kernel command line:

```
pci-stub.ids=8086:9ce0
```

Install [`fixes/system-sleep/95-macbook-spi-resume`](fixes/system-sleep/95-macbook-spi-resume)
into `/usr/lib/systemd/system-sleep/` (mode 0755).

That's the keyboard fixed at boot and after suspend. Details below.

For built-in sound on Arch/Omarchy, see [`audio/README.md`](audio/README.md).

## Bug 1: keyboard/trackpad dead, applespi times out with -110

**Symptom:** `applespi` probes, the SPI controller looks healthy, but every
transfer fails with `-110` (timeout). An "Apple SPI Keyboard" input node may
exist but nothing works, and "Apple SPI Touchpad" never appears. IRQ 21 never
increments. Seen on many distros; e.g. basecamp/omarchy#1954 (closed, unfixed).

**Root cause:** on this machine the LPSS DMA controller at PCI `0000:00:15.0`
(`8086:9ce0`) never delivers its interrupt — IRQ 20 stays at 0 counts forever;
this appears to be a hardware/firmware quirk of the Broadwell-Y LPSS island as
Apple wired it. `spi-pxa2xx` prefers DMA whenever a DMA channel is available,
and on the DMA path it deliberately does **not** enable the SSP's own interrupt
(completion is supposed to come from the DMA engine). With the DMA IRQ dead,
completion never arrives → every transfer times out.

The SPI controller's *own* interrupt (IRQ 21) works fine. Deny the SPI driver a
DMA channel and it falls back to PIO (`"no DMA channels available, using
PIO"`), enables its own IRQ, and everything works.

**Why some distros "just work":** kernels with `CONFIG_DW_DMAC_PCI=m`
(Debian/Ubuntu, Arch `linux`) often win the probe race by accident — if
`spi-pxa2xx` probes before the DMA module loads, it lands on PIO. Kernels with
`CONFIG_DW_DMAC_PCI=y` (e.g. CachyOS) always have DMA available at probe time
and always pick the dead path. This is also why "put applespi in the initramfs"
sometimes appears to help: it's an ordering fix, and it's fragile.

**The deterministic fix:** `pci-stub.ids=8086:9ce0` on the kernel cmdline.
`pci-stub` (built into essentially every kernel) claims the DMA controller
before any dw_dmac driver can bind it. The device has no other consumer, so
nothing is lost. A modprobe blacklist **cannot** do this when the driver is
built in — that's why so many attempts at this fix fail.

- Limine (limine-entry-tool): [`fixes/limine/20-macbook.conf`](fixes/limine/20-macbook.conf)
  → `/etc/limine-entry-tool.d/`
- GRUB: append to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, then
  regenerate (`grub-mkconfig -o /boot/grub/grub.cfg`)
- systemd-boot: append to the `options` line of your loader entry

Belt-and-braces: [`fixes/modprobe.d/macbook-spi.conf`](fixes/modprobe.d/macbook-spi.conf)
blacklists the loadable `dw_dmac`/`dw_dmac_pci` variants too.

**Verify:** `grep pci-stub /proc/cmdline`, then check
`grep -i 'Name=.*Apple SPI' /proc/bus/input/devices` — success is an
**"Apple SPI Touchpad"** node. (The keyboard node is created unconditionally at
probe; the touchpad node only appears once a real packet arrives, so it's the
true health check.)

Arch users: [`fixes/pacman-hooks/`](fixes/pacman-hooks/) has a warn-only pacman
hook that checks the parameter survived kernel/bootloader updates.

## Bug 2: keyboard dead after lid close / suspend (S3)

**Symptom:** identical `-110` spam after resume from S3 ("deep") suspend, even
with bug 1 fixed. This is Ubuntu bug #2143682. Distinguishing signature: after
resume the device doesn't even assert INTx, and SSCR0 writes read back as 0 —
the controller is unclocked/held in reset, not misrouted.

**Root cause:** S3 wipes the LPSS island's private registers (at BAR0+0x800 of
the SPI controller `0000:00:15.4`): clock gate (`+0x00`), function reset
(`+0x04`), CS control (`+0x18`). Apple's firmware doesn't restore them (macOS
does it itself). On non-Mac platforms `acpi_lpss.c` restores this context
(`LPSS_SAVE_CTX`), but Macs enumerate these devices via PCI, so that path never
runs — and the PCI driver's resume path doesn't touch the private registers
either. Cold boot works only because the firmware leaves them enabled.

**The fix:** [`fixes/system-sleep/95-macbook-spi-resume`](fixes/system-sleep/95-macbook-spi-resume),
a systemd sleep hook. On resume it unbinds `pxa2xx_spi_pci` (which releases the
MMIO region so `/dev/mem` can map it despite `IO_STRICT_DEVMEM`), restores the
three private registers, and rebinds — the probe path redoes the rest and
applespi comes back, no reboot needed. Needs python3 at resume time.

Install to **`/usr/lib/systemd/system-sleep/`** — on current systemd,
`/etc/systemd/system-sleep/` is *not* read. Two "corrupted packet (crc
mismatch)" lines right after rebind are harmless leftovers.

## Optional extras

- **Backlight:** add `acpi_backlight=native` to the cmdline for the fine-grained
  `intel_backlight` instead of coarse `acpi_video0` (already included in the
  Limine drop-in).
- **Power draw:** [`fixes/tlp/00-macbook81.conf`](fixes/tlp/00-macbook81.conf)
  for TLP roughly halved idle draw (~12 W → ~6.5 W). Gotcha inside: the stubbed
  DMA device must be excluded from runtime PM by **address**
  (`RUNTIME_PM_DENYLIST="00:15.0"`) — TLP's driver-name denylist does not cover
  `pci-stub` devices.
- **FaceTime camera off:** [`fixes/systemd/facetime-cam-d3.service`](fixes/systemd/facetime-cam-d3.service)
  forces the (unsupported-on-Linux anyway) camera into D3hot to save power.
  Skip if you hold out hope for a camera driver.
- **WiFi (BCM4350):** works out of the box with `brcmfmac`. On WPA2/WPA3
  transition-mode networks you may need
  `options brcmfmac feature_disable=0x82000` (software WPA handshake). A
  missing `clm_blob` limits available channels; extracting it from macOS is
  possible but usually not worth it.
- **Bluetooth:** UART-attached Broadcom; needs an out-of-tree driver + firmware
  extracted from macOS. Not covered here.

## Diagnostics

[`diagnostics/`](diagnostics/) has the small `/dev/mem`-poking tools used to
find all this: SSP register dump, polled-PIO SPI exerciser, INTx/IO-APIC/RCBA
interrupt-routing inspectors, and the LPSS private-register fixer the sleep
hook grew from. See [diagnostics/README.md](diagnostics/README.md).

If the pci-stub route is ever insufficient, a patched `spi-pxa2xx-core` with
`poll_mode`/`poll_timeout_ms` parameters (busy-polling the SSP interrupt
handler) is a proven fallback — build the in-tree driver out of tree with your
kernel's toolchain. Not shipped here because the stub fix makes it redundant.

## Baking the fixes into an Omarchy install ISO

[`omarchy-iso/`](omarchy-iso/) has patches for the Omarchy 4.x install
orchestrator adding a DMI-gated "Applying MacBook8,1 fixes" phase (a no-op on
any other machine), plus notes on repacking the official ISO — including adding
the boot parameter to the live environment so the internal keyboard works
*during* installation. See [omarchy-iso/README.md](omarchy-iso/README.md).

## Applying

`sudo ./apply.sh` installs the core fixes on an Arch-family system (detects
your bootloader config; prints instructions when it can't apply the cmdline
change itself). Or just copy the files per the sections above — every fix is a
single file plus one kernel parameter.
