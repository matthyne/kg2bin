# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this is

Tools to encode/decode channel EPROMs for Kyodo KG107/109 (VHF, PLL ref
`xtl`=1500 kHz) and Sawtron 999 (UHF, `xtl`=6000 kHz) radios.

- `kg2bin-v2/` — Python 3.10+ CLI, stdlib only. The primary tool. The
  package is still imported as `kg2bin`: `kg2bin` is a git-tracked symlink to
  `kg2bin-v2/` (for `python3 -m kg2bin` from the checkout and the tests), and
  pyproject maps it with `package-dir = { kg2bin = "kg2bin-v2" }` so installs
  don't depend on the symlink. Edit files under `kg2bin-v2/`.
- `kg2bin-v1/README.md`, `kg2bin-v2/README.md` — short per-tool install/usage
  guides; keep them in sync with the main README when options change.
  - `rom.py` — format constants, exact (Fraction) encode/decode, radio
    auto-detect, CSV read/write. `RomError` for every user-facing failure.
  - `cli.py` — argparse subcommands `write`, `read`, `template`; console
    script `kg2bin` (pyproject.toml), also `python3 -m kg2bin`.
- `kg2bin-v1/` — original Node tools (`writerom.js`, `readrom.js`,
  `package-lock.json`), kept as the reference. They share the top-level
  `data/`, `roms/`, `master-roms/` with the Python tool; their built-in
  default paths are `__dirname/../data|roms`. Bug-fixed in Oct 2026 (exact
  integer-Hz maths, off-grid = error and no ROM written, args work without
  the leading `2`, readrom flags corrupt records). Original code: `923339c`.

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
- `tests/test_v1_node.py` runs the Node tools; skipped unless `node` and
  the npm deps resolve from `kg2bin-v1/` (node_modules or NODE_PATH).
- A one-off sweep of ~63k on-grid frequencies showed fixed Node == Python on
  every channel (the original Node got 532 channels at 512–520 MHz one step
  low via float error).

## Differences between the Python and Node tools

Both: exact maths, off-grid freq is an error, TX decoded with its own R,
corrupt records flagged, identical ROM bytes. Python only: `--round`; bad
spacing / bank / channel / duplicate rows are errors (Node skips bad
spacing, doesn't check the rest); `--radio`/`--xtl` required for `write`;
`write` refuses to overwrite without `--force` (protects radio dumps, since
CSV export is lossy); radio auto-detect; CSV export. Keep these when
changing code; README lists them for users.

## Running the Node tools (for comparison)

```bash
# from repo root; deps resolve from kg2bin-v1/node_modules (or NODE_PATH)
(cd kg2bin-v1 && npm install csv-parser@2.3.0 minimist@1.2.0)  # no package.json
node kg2bin-v1/writerom.js --csv=data/uhfcb-80ch.csv --rom=/tmp/x.bin --xtl=6000
node kg2bin-v1/readrom.js --rom=roms/uhfcb-80ch.bin --xtl=6000
```

A leading `2` (old style) is accepted but no longer needed. `writerom.js`
writes asynchronously; wait for "Saved" before reading. It exits 1 and
writes nothing if any row has an ERROR.
`node_modules/` is gitignored; or point NODE_PATH at a scratch install.

## Data files

CSV columns are matched by header name (`bank,channel,rx_freq,tx_freq,
desc,spacing`; `desc` not stored in ROM). VHF CSVs have tx before rx.
`data/vhf2m.csv` is currently a copy of `vhfmarine.csv`.
