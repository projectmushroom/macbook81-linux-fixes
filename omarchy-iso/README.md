# Baking the fixes into the Omarchy install ISO

Omarchy 4.x already detects the MacBook8,1 and applies the fragile
initramfs-ordering keyboard fix (`install/hardware/apple/fix-spi-keyboard.sh`).
These patches make the fix deterministic and add the suspend/resume hook, by
teaching the ISO's install orchestrator a new phase.

## What the patches do

`orchestrator-main.patch` and `orchestrator-phases_impl.patch` apply to
`/usr/share/omarchy-iso/orchestrator/` inside the ISO's `airootfs.sfs`. They add
an **"Applying MacBook8,1 fixes"** phase, gated on
`/sys/class/dmi/id/product_name == "MacBook8,1"` (a no-op everywhere else),
which runs after `run_system_finalizer` (the stock hardware scripts) and before
`finalize_limine_boot` — so the kernel-cmdline drop-in lands in the final
Limine config build naturally.

The phase copies a payload from `/usr/local/share/macbook81/` in the live
environment into the install target:

- `etc/limine-entry-tool.d/20-macbook.conf` (pci-stub + backlight cmdline)
- `etc/modprobe.d/macbook-spi.conf`
- `usr/lib/systemd/system-sleep/95-macbook-spi-resume`
- `etc/pacman.d/hooks/99-macbook-spi-check.hook` + `usr/local/bin/macbook-spi-check`
- `etc/systemd/system/facetime-cam-d3.service` (+ enable symlinks)

Populate that payload dir from [`../fixes/`](../fixes/) when building.

## Repacking the official ISO

No root needed except to write the USB stick. Tools: `squashfs-tools`,
`libisoburn` (xorriso).

1. Extract `arch/x86_64/airootfs.sfs` from the ISO (`bsdtar` reads ISO9660),
   then `unsquashfs -d airootfs airootfs.sfs`.
2. Apply the two patches under
   `airootfs/usr/share/omarchy-iso/orchestrator/`, delete that directory's
   `__pycache__`, and create `airootfs/usr/local/share/macbook81/` with the
   payload files.
3. Add `pci-stub.ids=8086:9ce0` to the kernel lines of the ISO's
   `boot/grub/grub.cfg`, `boot/grub/loopback.cfg`, and
   `boot/syslinux/archiso_sys-linux.cfg` — this makes the internal keyboard
   work in the live installer itself.
4. Rebuild: `mksquashfs airootfs airootfs-new.sfs -comp zstd
   -Xcompression-level 12 -b 1M -noappend`, update
   `arch/x86_64/airootfs.sha512` to match.
5. Reassemble, replaying the original boot structure:

   ```
   xorriso -indev omarchy-X.iso -outdev omarchy-X-macbook81.iso \
     -boot_image any replay \
     -map airootfs-new.sfs /arch/x86_64/airootfs.sfs \
     -map airootfs.sha512.new /arch/x86_64/airootfs.sha512 \
     -map grub.cfg /boot/grub/grub.cfg \
     -map loopback.cfg /boot/grub/loopback.cfg \
     -map archiso_sys-linux.cfg /boot/syslinux/archiso_sys-linux.cfg
   ```

If rebuilding the squashfs as a non-root user: capture ownership first
(`unsquashfs -lln`), generate a mksquashfs pseudo-file from it (`"path" m mode
uid gid` per entry, escape literal backslashes in filenames), pass `-pf` plus
`-root-mode 555 -root-uid 0 -root-gid 0`, and watch for owner-unreadable files
(e.g. `usr/lib/dbus-daemon-launch-helper`, mode `---s--x---`) — `chmod u+r`
them after extraction or they end up empty in the rebuilt image.

Patches are against Omarchy 4.0.0; the orchestrator is small and moves slowly,
so they should apply (possibly with offsets) to nearby versions.
