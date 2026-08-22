#!/usr/bin/env python3
"""Recover the MacBook8,1 GSPI controller after S3 resume.

The LPSS island at 00:15.x loses its private-register context in S3
(this is why acpi_lpss.c has LPSS_SAVE_CTX for these devices when ACPI-
enumerated). On this Mac the SPI function is PCI-enumerated via
pxa2xx_spi_pci, whose system-resume handler does NOT restore the
private block at BAR0+0x800 — in particular the clock-gate bit at
priv+0x00 comes back gated, so the SSP is dead: no register writes
stick, no interrupts, every applespi transfer times out with -110.

Usage:  lpssfix.py          dump only
        lpssfix.py fix      dump, then ungate clock + restore CS ctrl, dump again
"""
import mmap, struct, sys

BAR = 0xc181a000
SIZE = 0x1000
PRIV = 0x800

CLK_EN = 0x1            # priv+0x00 bit0: clock gate (acpi_lpss LPSS_CLK_GATE, bit 0)
CS_SW_MODE_HIGH = 0x3   # priv+0x18: LPSS_CS_CONTROL_SW_MODE | LPSS_CS_CONTROL_CS_HIGH

fix = len(sys.argv) > 1 and sys.argv[1] == "fix"

fd = open("/dev/mem", "r+b" if fix else "rb")
prot = mmap.PROT_READ | (mmap.PROT_WRITE if fix else 0)
m = mmap.mmap(fd.fileno(), SIZE, mmap.MAP_SHARED, prot, offset=BAR)

def r32(off):
    return struct.unpack("<I", m[off:off+4])[0]

def w32(off, val):
    m[off:off+4] = struct.pack("<I", val)

def dump(tag):
    print(f"-- {tag} --")
    for off in range(0, 0x24, 4):
        print(f"  priv+0x{off:02x} = 0x{r32(PRIV+off):08x}")
    print(f"  SSCR0 = 0x{r32(0):08x}  SSCR1 = 0x{r32(4):08x}  SSSR = 0x{r32(8):08x}")

dump("before")
if fix:
    w32(PRIV + 0x00, r32(PRIV + 0x00) | CLK_EN)
    w32(PRIV + 0x18, r32(PRIV + 0x18) | CS_SW_MODE_HIGH)
    dump("after")
m.close()
