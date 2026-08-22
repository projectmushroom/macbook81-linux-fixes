#!/usr/bin/env python3
"""Dump the RCBA interrupt-route block raw, without assuming an offset->device map.

The offset map differs between PCH generations, so instead of trusting a guessed
table we dump the whole window and let the caller cross-check it against the
routings that lspci/ACPI report for devices whose INTx demonstrably works.
"""
import mmap, struct

with open("/sys/bus/pci/devices/0000:00:1f.0/config", "rb") as c:
    c.seek(0xF0)
    rcba = struct.unpack("<I", c.read(4))[0] & ~0x3FFF

fd = open("/dev/mem", "rb")
m = mmap.mmap(fd.fileno(), 0x4000, mmap.MAP_SHARED, mmap.PROT_READ, offset=rcba)
def r16(o): return struct.unpack("<H", m[o:o+2])[0]

PIRQ = "ABCDEFGH"
print(f"RCBA base 0x{rcba:08x}\n")
print(f"{'offset':8s} {'raw':7s}  INTA        INTB        INTC        INTD")
for off in range(0x3140, 0x3180, 2):
    v = r16(off)
    f = [(v >> (4 * i)) & 0x7 for i in range(4)]
    pins = "  ".join(f"PIRQ{PIRQ[x]}/IRQ{16+x}" for x in f)
    print(f"0x{off:04x}   0x{v:04x}   {pins}")
m.close()
