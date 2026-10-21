# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this is

Tools to encode/decode channel EPROMs for Kyodo KG107/109 (VHF, PLL ref
`xtl`=1500 kHz) and Sawtron 999 (UHF, `xtl`=6000 kHz) radios.

- `kg2bin/` — Python 3.10+ CLI, stdlib only. The primary tool.
  - `rom.py` — format constants, exact (Fraction) encode/decode, radio
    auto-detect, CSV read/write. `RomError` for every user-facing failure.
  - `cli.py` — argparse subcommands `write`, `read`, `template`; console
    script `kg2bin` (pyproject.toml), also `python3 -m kg2bin`.
- `writerom.js` / `readrom.js` — original Node tools, kept as the reference.

**The ROM format spec is `docs/ROM-FORMAT.md` — read it before touching any
encode/decode logic.** Short version: 8192 bytes, 4 banks × 128 slots × 16
bytes, addr = bank·2048 + (ch−1)·16; each record is RX A(2) N(3) R(3) then TX
A(2) N(3) R(3), one nibble per byte, LS nibble first; D = N·64 + A,
step = xtl/R, TX = D·step, RX = D·step + 21600 kHz. Unused = 0xFF.

## Tests

```bash
python3 -m unittest -v      # from repo root
```

- Ground truth: `roms/uhfcb-80ch.bin` = writerom.js on `data/uhfcb-80ch.csv`
  xtl 6000; `roms/vhf-marine.bin` (= `roms/rom.bin`) = `data/vhfmarine.csv`
  xtl 1500. Python must reproduce these byte for byte.
- `tests/fixtures/node/readrom_*.txt` = saved readrom.js output; the read
  tests parse these.
- Round trip bin→csv→bin over every committed ROM.
- `master-roms/master_saw999.bin` bank 2 ch 76 (offset 0x14B0) has a corrupt
  RX half — `CORRUPT` in the tests excludes it; `read` flags it.
- A one-off sweep of ~63k on-grid frequencies showed Python == Node except
  the 532 channels (512–520 MHz) that Node gets one step low via float error.

## Intentional differences from the Node tools

Exact maths; off-grid freq is an error unless `--round`; bad CSV rows are
errors with line numbers (Node silently skips); `--radio`/`--xtl` required
for `write`; TX decoded with its own R; corrupt records flagged and left out
of CSV exports. Keep these when changing code; README lists them for users.

## Running the Node tools (for comparison)

```bash
npm install csv-parser@2.3.0 minimist@1.2.0   # no package.json in repo
node writerom.js 2 --csv=data/uhfcb-80ch.csv --rom=/tmp/x.bin --xtl=6000
node readrom.js 2 --rom=roms/uhfcb-80ch.bin --xtl=6000
```

The leading `2` is required — without a numeric first arg >1 all flags are
ignored. `writerom.js` writes asynchronously; wait for "Saved" before reading.
Do this in a scratch copy so `node_modules/` doesn't land in the repo.

## Data files

CSV columns are matched by header name (`bank,channel,rx_freq,tx_freq,
desc,spacing`; `desc` not stored in ROM). VHF CSVs have tx before rx.
`data/vhf2m.csv` is currently a copy of `vhfmarine.csv`.
