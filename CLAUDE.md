# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this is

Tools to encode/decode channel EPROMs for Kyodo KG107/109 (VHF, PLL ref
`xtl`=1500 kHz) and Sawtron 999 (UHF, `xtl`=6000 kHz) radios. Original tools
are Node.js (`writerom.js`, `readrom.js`); a Python port for Linux is planned.

**The ROM format spec is `docs/ROM-FORMAT.md` — read it before touching any
encode/decode logic.** Short version: 8192 bytes, 4 banks × 128 slots × 16
bytes, addr = bank·2048 + (ch−1)·16; each record is RX A(2) N(3) R(3) then TX
A(2) N(3) R(3), one nibble per byte, LS nibble first; D = N·64 + A,
step = xtl/R, TX = D·step, RX = D·step + 21600 kHz. Unused = 0xFF.

## Ground truth / regression oracle

- `roms/uhfcb-80ch.bin` = `writerom.js` on `data/uhfcb-80ch.csv`, xtl 6000.
- `roms/vhf-marine.bin` (= `roms/rom.bin`) = `data/vhfmarine.csv`, xtl 1500.
- Any reimplementation must reproduce these byte for byte.
- `master-roms/` are dumps from real radios; `master_saw999.bin` bank 2 ch 76
  has a corrupt RX half (documented in the format doc) — exclude it from
  round-trip tests.

## Running the Node tools

```bash
npm install csv-parser@2.3.0 minimist@1.2.0   # no package.json in repo
node writerom.js 2 --csv=data/uhfcb-80ch.csv --rom=/tmp/x.bin --xtl=6000
node readrom.js 2 --rom=roms/uhfcb-80ch.bin --xtl=6000
```

The leading `2` is required — without a numeric first arg >1 all flags are
ignored. `writerom.js` writes asynchronously; wait for "Saved" before reading.

## Known Node bugs (don't replicate in ports)

Float truncation (512.045 MHz → one step low; observed only 512–520 MHz in a
sweep), silent truncation of off-grid frequencies, no N/R ≤ 0xFFF range
check, `readrom.js` decodes TX with the RX R value. Full list in README.md.

## Data files

CSV columns are matched by header name (`bank,channel,rx_freq,tx_freq,spacing`;
`desc` ignored). VHF CSVs have tx before rx. `data/vhf2m.csv` is currently a
copy of `vhfmarine.csv`.
