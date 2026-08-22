# Diagnostics

Small root-only tools (python3, `/dev/mem`) used to root-cause the SPI keyboard
failure. Ordered roughly by usefulness:

| Tool | What it answers |
|---|---|
| `sspdump.py` | Dump the SSP (SPI controller) registers at BAR0 of `0000:00:15.4`. Is the controller clocked? What's in SSCR0/SSCR1/SSSR? |
| `spipio.py` | Drive the SSP by hand in polled PIO — proves the SPI bus and controller work independent of interrupts and drivers. |
| `intx.py` | Does the controller actually assert INTx (PCI status bit 3) when poked? Separates "device never raises" from "raised but not delivered". |
| `ioapic.py` | Read IO-APIC redirection entries — is the pin unmasked, right trigger mode, right vector? |
| `irte.py` | Read the VT-d interrupt-remapping table entries for the pins in question. |
| `rcba.py` / `rcba2.py` | PCH RCBA interrupt-route registers (D2xIR): which PIRQ each device pin routes to. `rcba2.py` dumps raw without assuming an offset map — use it first; guessed maps produce bogus mismatches. |
| `lpssfix.py` | Restore the LPSS private registers (clock gate, function reset, CS ctrl) after S3 — the standalone version of the sleep hook. |

Notes:

- `IO_STRICT_DEVMEM` (default on most distros) blocks `/dev/mem` access to a
  region **while a driver is bound**. Unbind the driver first
  (`echo 0000:00:15.4 > /sys/bus/pci/drivers/pxa2xx_spi_pci/unbind`).
- A hard-won lesson baked into these tools: before concluding an interrupt is
  undeliverable, check whether the driver ever *enabled* it. In DMA mode
  `spi-pxa2xx` never enables the SSP's own interrupt, so "IRQ 21 stays at 0"
  proves nothing about delivery.
- Do not unbind `dw_dmac_pci` while `spi-pxa2xx` holds DMA channels — the
  channel teardown NULL-derefs and wedges the SPI bus until reboot. Unbind the
  SPI driver first, or test across a reboot.
