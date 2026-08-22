# Built-in speakers on Arch Linux/Omarchy

The internal speakers now work after a cold boot and reboot on this
MacBook8,1. This was verified on Omarchy/Arch with kernel `7.1.8-arch1-3` on
2026-08-22.

The driver implementation lives in
[`thomas-shirley/macbook8.1-speaker-driver`](https://github.com/thomas-shirley/macbook8.1-speaker-driver).
It patches three HDA modules and adds the PipeWire/WirePlumber routing needed
for the CS4208 codec and the MacBook's TDM class-D speaker path. Do not confuse
this with a simple mixer or PipeWire-only fix.

## Arch/Omarchy installation notes

Install the build dependencies and headers matching the running kernel:

```bash
sudo pacman -S --needed base-devel dkms wget linux-headers
test -e /lib/modules/$(uname -r)/build
```

For a nonstandard kernel, install its matching header package instead, such as
`linux-lts-headers`.

Clone and install the speaker driver:

```bash
git clone https://github.com/thomas-shirley/macbook8.1-speaker-driver.git
cd macbook8.1-speaker-driver
sudo bash install.sh
sudo reboot
```

The installer must regenerate the Arch/Omarchy boot image after DKMS installs
the modules. On Omarchy, use `limine-mkinitcpio`; on another Arch setup, use
`mkinitcpio -P`. The local working checkout adds this fallback because the
upstream installer at commit `fe54ad1` only invokes `update-initramfs`:

```bash
if command -v limine-mkinitcpio >/dev/null; then
    sudo limine-mkinitcpio
else
    sudo mkinitcpio -P
fi
```

This step matters: without a refreshed boot image, the machine can boot the
stock or stale HDA modules and ignore the module soft dependency, leaving a
detected audio card with silent speakers.

## What the working setup installs

- Three patched DKMS modules: `snd-hda-intel`,
  `snd-hda-codec-cs420x`, and `snd-hda-codec-generic`.
- `/etc/modprobe.d/mb81-singlecmd.conf`, setting `single_cmd=1` and
  `power_save=0` and loading the CS420x codec before `snd-hda-intel`.
- A PipeWire EQ sink and a WirePlumber raw-PCM speaker node.
- The per-user `mb81-jack-switch.service` for headphone/speaker switching.
- The system `mb81-resume-recover.service` to re-heal the codec after resume.

The installed files on the verified machine match the corresponding files in
the speaker-driver checkout.

## Verify after reboot

```bash
# All three paths should end in updates/dkms/*.ko.zst
modinfo -n snd-hda-intel snd-hda-codec-cs420x snd-hda-codec-generic

# Expected: 1 and 0
cat /sys/module/snd_hda_intel/parameters/single_cmd
cat /sys/module/snd_hda_intel/parameters/power_save

# Expected: enabled for both
systemctl --user is-enabled mb81-jack-switch.service
systemctl is-enabled mb81-resume-recover.service

# Should show MacBook Speaker (Raw), the EQ sink, and DSP output
wpctl status | grep -i speaker
```

On the verified boot, all three modules loaded from
`/lib/modules/7.1.8-arch1-3/updates/dkms/`, the parameters were `1` and `0`,
both services were enabled, and the raw and EQ speaker nodes were active.

## Suspend/resume

S3 resume can re-latch the codec clock and return to silence. The installed
`mb81-resume-recover.service` unloads the HDA stack, replays the EFI codec
state, reattaches the patched driver, and restarts the user audio path. Manual
fallback:

```bash
sudo /usr/local/bin/mb81-resume-recover
```

A plain reboot remains the clean fallback if recovery fails.
