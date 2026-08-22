#!/usr/bin/env python3
"""Read IO-APIC redirection table entries for the dead vs working pins."""
import mmap, struct

BASE = 0xFEC00000
fd = open("/dev/mem", "r+b")
try:
    m = mmap.mmap(fd.fileno(), 0x1000, mmap.MAP_SHARED,
                  mmap.PROT_READ | mmap.PROT_WRITE, offset=BASE)
except Exception as e:
    raise SystemExit(f"mmap IOAPIC failed: {e}")

def ioread(reg):
    m[0x00:0x04] = struct.pack("<I", reg)
    return struct.unpack("<I", m[0x10:0x14])[0]

print(f"IOAPIC ID  = 0x{ioread(0):08x}")
ver = ioread(1)
print(f"IOAPIC VER = 0x{ver:08x}  (max redir entry = {(ver >> 16) & 0xff})")

print(f"\n{'pin':4s} {'low':10s} {'high':10s} {'vec':4s} {'mask':5s} {'trig':6s} "
      f"{'pol':9s} {'dest':5s} {'remap':6s}")
for pin in (9, 18, 20, 21, 22, 23):
    lo = ioread(0x10 + 2 * pin)
    hi = ioread(0x11 + 2 * pin)
    vec   = lo & 0xff
    mask  = (lo >> 16) & 1
    trig  = "level" if (lo >> 15) & 1 else "edge"
    pol   = "act-low" if (lo >> 13) & 1 else "act-high"
    remap = (lo >> 11) & 1          # in IR mode bit 48 of the 64-bit entry
    dest  = (hi >> 24) & 0xff
    tag = {9: "acpi(OK)", 18: "smbus(OK)", 20: "lpss-dma(DEAD)",
           21: "gspi(DEAD)"}.get(pin, "")
    print(f"{pin:<4d} 0x{lo:08x} 0x{hi:08x} 0x{vec:02x}  {mask:<5d} {trig:6s} "
          f"{pol:9s} 0x{dest:02x}  {remap:<6d} {tag}")
m.close()
