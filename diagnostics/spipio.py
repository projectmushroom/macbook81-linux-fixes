#!/usr/bin/env python3
"""Manually clock bytes out of the MacBook8,1 GSPI port in polled PIO mode.

Purpose: determine whether the SSP hardware can shift data at all when nothing
depends on IRQ 21. If BSY asserts and the TX FIFO drains, the bus is alive and
the ONLY defect is interrupt delivery.
"""
import mmap, struct, time

BAR, SIZE = 0xc181a000, 0x1000
SSCR0, SSCR1, SSSR, SSDR = 0x00, 0x04, 0x08, 0x10

fd = open("/dev/mem", "r+b")
m = mmap.mmap(fd.fileno(), SIZE, mmap.MAP_SHARED,
              mmap.PROT_READ | mmap.PROT_WRITE, offset=BAR)

def r(o):    return struct.unpack("<I", m[o:o+4])[0]
def w(o, v): m[o:o+4] = struct.pack("<I", v & 0xffffffff)

def show(tag):
    s = r(SSSR)
    print(f"  {tag:22s} SSSR=0x{s:08x}  BSY={(s>>4)&1} TNF={(s>>2)&1} "
          f"RNE={(s>>3)&1} TFL={(s>>8)&0xf} RFL={(s>>12)&0xf}")

print(f"initial SSCR0=0x{r(SSCR0):08x} SSCR1=0x{r(SSCR1):08x}")
show("before")

# Drain any stale RX, clear sticky status bits (ROR/TUR/BCE are write-1-to-clear)
while (r(SSSR) >> 3) & 1:
    r(SSDR)
w(SSSR, r(SSSR) | (1 << 7) | (1 << 21) | (1 << 23))

# Enable the port: keep existing config, set SSE (bit 7)
w(SSCR0, r(SSCR0) | (1 << 7))
time.sleep(0.01)
print(f"after SSE:   SSCR0=0x{r(SSCR0):08x}")
show("port enabled")

# Push 8 bytes into the TX FIFO
for b in (0xa5, 0x5a, 0x00, 0xff, 0xde, 0xad, 0xbe, 0xef):
    w(SSDR, b)
show("8 bytes queued")

# Poll for the shift engine to move them
moved = False
for i in range(200):
    s = r(SSSR)
    if (s >> 4) & 1:
        moved = True
    if (s >> 3) & 1:
        moved = True
        break
    time.sleep(0.001)

show("after 200ms poll")

rx = []
while (r(SSSR) >> 3) & 1 and len(rx) < 16:
    rx.append(r(SSDR) & 0xff)

print(f"\n  bytes received: {[hex(b) for b in rx] if rx else 'NONE'}")
print(f"  shift activity seen: {moved}")

# Turn the port back off so the driver re-inits cleanly
w(SSCR0, r(SSCR0) & ~(1 << 7))
m.close()

print("\nVERDICT:", "SSP SHIFTS DATA -> bus alive, IRQ delivery is the sole defect"
      if moved else "SSP INERT -> clock/pin/firmware problem, not just the IRQ")
