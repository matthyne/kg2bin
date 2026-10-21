# kg2bin v1 — Node.js tools

The original tools, bug-fixed in October 2026:

- `writerom.js` — CSV channel list → `.bin` ROM
- `readrom.js` — `.bin` ROM → channel list on screen

For most jobs the Python tool in [`../kg2bin-v2/`](../kg2bin-v2/) is easier.
Both tools produce identical ROMs.

## Install

Needs Node.js (tested on Node 22).

```bash
cd kg2bin-v1
npm install csv-parser@2.3.0 minimist@1.2.0
```

## Use

Run from the repo root:

```bash
# Build a ROM
node kg2bin-v1/writerom.js --csv=data/uhfcb-80ch.csv --rom=roms/uhfcb-80ch.bin --xtl=6000

# Read a ROM
node kg2bin-v1/readrom.js --rom=roms/uhfcb-80ch.bin --xtl=6000
```

| Option | Meaning | Default |
|--------|---------|---------|
| `--csv` | Channel list to read (writerom only) | `data/data.csv` |
| `--rom` | ROM file to write / read | `roms/rom.bin` |
| `--xtl` | Radio's PLL reference in kHz: **1500** = Kyodo KG107/109, **6000** = Sawtron 999 | `1500` |

Defaults point at the repo's `data/` and `roms/` folders wherever you run
from. The old style with a leading `2` (`node writerom.js 2 --csv=…`) still
works.

- `writerom.js` lists every channel it writes. If any row has a problem, such
  as an off-grid frequency or a bad number, it prints `ERROR` lines with the
  CSV line number. It then writes **nothing** and exits with status 1.
- `readrom.js` prints `bank-channel | RX MHz | TX MHz | step`. Records that
  can't be valid show as `CORRUPT`.

CSV columns: `bank,channel,rx_freq,tx_freq,desc,spacing`. See the main
[README](../README.md#csv-format) and the
[ROM format](../docs/ROM-FORMAT.md) for details.
