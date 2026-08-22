#!/usr/bin/env python3
"""Read the PCH Root Complex device interrupt-route registers (read-only).

ACPI claims 00:15.4 INTD -> GSI 21. On Intel PCH, PIRQ[A..H] map to IO-APIC pins
16..23, so GSI 21 == PIRQF (index 5). The DxxIR register says what the firmware
actually programmed. A mismatch means the interrupt is physically steered to a
different pin than the one Linux unmasks and waits on.
"""
import mmap, struct

LPC_CFG = "/sys/bus/pci/devices/0000:00:1f.0/config"

with open(LPC_CFG, "rb") as c:
    c.seek(0xF0)
    rcba_reg = struct.unpack("<I", c.read(4))[0]

rcba = rcba_reg & ~0x3FFF
en = rcba_reg & 1
print(f"LPC RCBA register = 0x{rcba_reg:08x} -> base 0x{rcba:08x}, enabled={en}")
if not en:
    raise SystemExit("RCBA not enabled; cannot continue")

PAGE = 0x4000
fd = open("/dev/mem", "rb")
try:
    m = mmap.mmap(fd.fileno(), PAGE, mmap.MAP_SHARED, mmap.PROT_READ, offset=rcba)
except Exception as e:
    raise SystemExit(f"mmap of RCBA failed: {e}")

def r16(o): return struct.unpack("<H", m[o:o+2])[0]

PIRQ = "ABCDEFGH"
# Lynx Point / Wildcat Point-LP RCBA interrupt route registers
REGS = [(0x3140, "D31IR"), (0x3142, "D29IR"), (0x3144, "D28IR"), (0x3146, "D27IR"),
        (0x3148, "D26IR"), (0x314C, "D22IR"), (0x3150, "D20IR"), (0x3152, "D21IR"),
        (0x3154, "D23IR"), (0x3156, "D19IR"), (0x315C, "D25IR")]

print(f"\n{'reg':7s} {'off':7s} {'value':8s}  INTA  INTB  INTC  INTD")
for off, name in REGS:
    v = r16(off)
    fields = [(v >> (4 * i)) & 0x7 for i in range(4)]  # A,B,C,D
    pins = [f"PIRQ{PIRQ[f]}(IRQ{16+f})" for f in fields]
    print(f"{name:7s} 0x{off:04x}  0x{v:04x}    " + "  ".join(pins))

d21 = r16(0x3152)
intd = (d21 >> 12) & 0x7
print(f"\n== decode D21IR (LPSS, device 0x15) ==")
print(f"  raw = 0x{d21:04x}")
print(f"  INTD -> PIRQ{PIRQ[intd]} -> IO-APIC pin {16 + intd} (GSI {16 + intd})")
print(f"  ACPI _PRT claims                     -> GSI 21")
print("  MATCH" if 16 + intd == 21 else f"  *** MISMATCH: hardware steers it to GSI {16+intd}, "
      f"Linux listens on GSI 21 ***")
m.close()
