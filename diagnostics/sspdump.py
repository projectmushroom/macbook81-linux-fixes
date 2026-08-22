#!/usr/bin/env python3
"""Dump the PXA2xx/LPSS SSP registers of the MacBook8,1 GSPI controller at BAR0."""
import mmap, struct, sys

BAR = 0xc181a000
SIZE = 0x1000

try:
    fd = open("/dev/mem", "rb")
except Exception as e:
    sys.exit(f"open /dev/mem failed: {e}")

try:
    m = mmap.mmap(fd.fileno(), SIZE, mmap.MAP_SHARED, mmap.PROT_READ, offset=BAR)
except Exception as e:
    sys.exit(f"mmap failed (likely CONFIG_IO_STRICT_DEVMEM, driver holds the region): {e}")

def r32(off):
    return struct.unpack("<I", m[off:off+4])[0]

SSP = {0x00: "SSCR0", 0x04: "SSCR1", 0x08: "SSSR", 0x0c: "SSITR",
       0x28: "SSTO",  0x2c: "SSPSP", 0x30: "SSTSA", 0x34: "SSRSA",
       0x38: "SSTSS", 0x40: "SSACD"}
print("== SSP core registers ==")
for off, name in sorted(SSP.items()):
    print(f"  0x{off:03x} {name:6s} = 0x{r32(off):08x}")

print("\n== LPSS private registers (LPT window @ 0x800) ==")
PRIV = {0x800: "PRIV+0x00", 0x804: "RESETS?", 0x808: "GENERAL", 0x80c: "SSP_REG",
        0x810: "PRIV+0x10", 0x814: "PRIV+0x14", 0x818: "CS_CTRL", 0x81c: "PRIV+0x1c"}
for off, name in sorted(PRIV.items()):
    print(f"  0x{off:03x} {name:10s} = 0x{r32(off):08x}")

sscr0, sscr1, sssr = r32(0x00), r32(0x04), r32(0x08)
print("\n== decode ==")
print(f"  SSCR0.SSE (port enabled)   = {(sscr0 >> 7) & 1}")
print(f"  SSCR0.DSS (data size-1)    = {sscr0 & 0xf} -> {(sscr0 & 0xf) + 1} bits")
print(f"  SSCR0.SCR (clock divisor)  = {(sscr0 >> 8) & 0xfff}")
print(f"  SSCR1.TIE (tx fifo irq en) = {(sscr1 >> 1) & 1}")
print(f"  SSCR1.RIE (rx fifo irq en) = {(sscr1 >> 0) & 1}")
print(f"  SSCR1.TSRE/RSRE (dma en)   = tx:{(sscr1 >> 21) & 1} rx:{(sscr1 >> 20) & 1}")
print(f"  SSSR.BSY (busy)            = {(sssr >> 4) & 1}")
print(f"  SSSR.TNF (tx not full)     = {(sssr >> 2) & 1}")
print(f"  SSSR.RNE (rx not empty)    = {(sssr >> 3) & 1}")
print(f"  SSSR.TFL (tx fifo level)   = {(sssr >> 8) & 0xf}")
print(f"  SSSR.RFL (rx fifo level)   = {(sssr >> 12) & 0xf}")
m.close()
