#!/usr/bin/env python3
"""Does the GSPI controller actually ASSERT its INTx line?

Enables the port with RX/TX FIFO interrupts unmasked, forces the FIFO past its
threshold, and watches PCI config STATUS bit 3 (Interrupt Status), which is set
by the device itself whenever its INTx is asserted -- independent of whether the
PCH/IO-APIC ever delivers it.
"""
import mmap, struct, time

BAR, SIZE = 0xc181a000, 0x1000
SSCR0, SSCR1, SSSR, SSDR = 0x00, 0x04, 0x08, 0x10
CFG = "/sys/bus/pci/devices/0000:00:15.4/config"

fd = open("/dev/mem", "r+b")
m = mmap.mmap(fd.fileno(), SIZE, mmap.MAP_SHARED,
              mmap.PROT_READ | mmap.PROT_WRITE, offset=BAR)
def r(o):    return struct.unpack("<I", m[o:o+4])[0]
def w(o, v): m[o:o+4] = struct.pack("<I", v & 0xffffffff)

def intx():
    with open(CFG, "rb") as c:
        c.seek(0x06)
        status = struct.unpack("<H", c.read(2))[0]
    return (status >> 3) & 1, status

def cmd():
    with open(CFG, "rb") as c:
        c.seek(0x04)
        return struct.unpack("<H", c.read(2))[0]

a, s = intx()
print(f"COMMAND=0x{cmd():04x} (INTx disable bit={(cmd()>>10)&1})")
print(f"baseline: STATUS=0x{s:04x}  INTx asserted={a}")

# Clear stale RX + sticky bits
w(SSCR0, r(SSCR0) & ~(1 << 7))
while (r(SSSR) >> 3) & 1:
    r(SSDR)
w(SSSR, r(SSSR) | (1 << 7) | (1 << 21) | (1 << 23))

# Unmask FIFO interrupts: RIE(bit0), TIE(bit1); also TINTE (bit19) rx-timeout
sscr1 = r(SSCR1) | (1 << 0) | (1 << 1) | (1 << 19)
w(SSCR1, sscr1)
w(SSCR0, r(SSCR0) | (1 << 7))
print(f"armed:    SSCR0=0x{r(SSCR0):08x} SSCR1=0x{r(SSCR1):08x}")

a, s = intx()
print(f"after arm (TX FIFO empty => TFS should assert): STATUS=0x{s:04x} INTx={a}")

seen = a
for b in range(16):
    w(SSDR, 0xa5)
for i in range(300):
    a, s = intx()
    if a:
        seen = 1
        print(f"  INTx ASSERTED at poll {i}: STATUS=0x{s:04x} SSSR=0x{r(SSSR):08x}")
        break
    time.sleep(0.001)

a, s = intx()
print(f"final:    STATUS=0x{s:04x} INTx={a} SSSR=0x{r(SSSR):08x}")

# Disarm
w(SSCR0, r(SSCR0) & ~(1 << 7))
w(SSCR1, sscr1 & ~((1 << 0) | (1 << 1) | (1 << 19)))
m.close()

print("\nVERDICT:", "DEVICE ASSERTS INTx -> generation OK, PCH/IO-APIC routing drops it"
      if seen else "DEVICE NEVER ASSERTS INTx -> interrupt generation itself is blocked")
