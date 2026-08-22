#!/usr/bin/env python3
"""Read the VT-d interrupt remapping table entries for the dead vs working pins.

IO-APIC pin 18 (i801_smbus, works) uses IRTE index 17.
IO-APIC pin 21 (GSPI, dead)        uses IRTE index 23.
If IRTE[23] is not present/malformed, interrupt remapping is silently dropping it.
Also dumps the IOMMU fault-recording registers, which would log such a drop.
"""
import mmap, struct

DRHD = 0xfed91000   # the DRHD that has IOAPIC id 2 under it

fd = open("/dev/mem", "rb")
m = mmap.mmap(fd.fileno(), 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=DRHD)
def r32(o): return struct.unpack("<I", m[o:o+4])[0]
def r64(o): return struct.unpack("<Q", m[o:o+8])[0]

cap, ecap, gsts = r64(0x08), r64(0x10), r32(0x1c)
irta = r64(0xb8)
print(f"VER  = 0x{r32(0x00):08x}")
print(f"CAP  = 0x{cap:016x}")
print(f"ECAP = 0x{ecap:016x}")
print(f"GSTS = 0x{gsts:08x}  IRES(irq remap enabled, bit25)={(gsts>>25)&1} "
      f"IRTPS(bit24)={(gsts>>24)&1}  CFIS(compat fmt allowed, bit23)={(gsts>>23)&1}")
irt_base = irta & ~0xfff
size = 2 ** ((irta & 0xf) + 1)
print(f"IRTA = 0x{irta:016x} -> table @ 0x{irt_base:012x}, {size} entries, EIME={(irta>>11)&1}")

# Fault status / recording
fsts = r32(0x34)
fro = ((cap >> 24) & 0x3ff) * 16
print(f"\nFSTS = 0x{fsts:08x}  PPF(pending fault,bit1)={(fsts>>1)&1} "
      f"PFO(overflow,bit0)={fsts & 1}  fault-record offset=0x{fro:x}")
nfr = ((cap >> 40) & 0xff) + 1
for i in range(min(nfr, 4)):
    lo = r64(fro + 16 * i)
    hi = r64(fro + 16 * i + 8)
    if hi >> 63:
        reason = (hi >> 32) & 0xff
        typ = (hi >> 62) & 1
        sid = hi & 0xffff
        print(f"  FAULT[{i}]: addr/index=0x{lo:016x} reason=0x{reason:02x} "
              f"type={'read' if typ else 'write'} source={sid>>8:02x}:{(sid>>3)&0x1f:02x}.{sid&7}")
    else:
        print(f"  FAULT[{i}]: none")
m.close()

# Now the IRT itself
t = mmap.mmap(fd.fileno(), 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=irt_base)
def e(idx):
    lo = struct.unpack("<Q", t[idx*16:idx*16+8])[0]
    hi = struct.unpack("<Q", t[idx*16+8:idx*16+16])[0]
    return lo, hi

print(f"\n{'idx':4s} {'low':18s} {'high':18s} {'P':2s} {'TM':6s} {'DLM':4s} "
      f"{'vec':4s} {'dest':6s} {'SVT':4s} {'SID':6s}")
for idx in (17, 23, 16, 18, 19, 20, 21, 22):
    lo, hi = e(idx)
    p    = lo & 1
    tm   = "level" if (lo >> 4) & 1 else "edge"
    dlm  = (lo >> 5) & 0x7
    vec  = (lo >> 16) & 0xff
    dest = (lo >> 32) & 0xffffffff
    svt  = (hi >> 18) & 0x3
    sid  = hi & 0xffff
    tag = {17: "<- pin18 smbus OK", 23: "<- pin21 GSPI DEAD"}.get(idx, "")
    print(f"{idx:<4d} 0x{lo:016x} 0x{hi:016x} {p:<2d} {tm:6s} {dlm:<4d} "
          f"0x{vec:02x} 0x{dest:04x} {svt:<4d} 0x{sid:04x} {tag}")
t.close()
