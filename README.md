# kg2bin

Tools to create and read the channel ROM (EPROM) contents for
**Kyodo KG107 / KG109** (VHF) and **Sawtron 999** (UHF) radios.

- Write a channel list (CSV) into a `.bin` ready to burn to the EPROM
- Read a `.bin` (e.g. dumped from a radio) back into a channel list or CSV

There are two implementations:

- [`kg2bin-v2/`](kg2bin-v2/) — **`kg2bin`**, the Python 3 command-line tool for Linux (recommended)
- [`kg2bin-v1/`](kg2bin-v1/) — the original Node.js tools (`writerom.js` / `readrom.js`)

The binary format is documented in [docs/ROM-FORMAT.md](docs/ROM-FORMAT.md).

## Python tool (`kg2bin`)

Needs Python 3.10+ and nothing else (standard library only).

### Install

```bash
git clone git@github.com:matthyne/kg2bin.git
cd kg2bin
pipx install --editable .        # puts `kg2bin` on your PATH
```

Or run it straight from the checkout without installing:
`python3 -m kg2bin ...`

### Everyday use

```bash
# 1. Start a channel list (or copy one from data/)
kg2bin template mychannels.csv

# 2. Edit it, then build the ROM -- say which radio it's for
kg2bin write mychannels.csv --radio saw999        # -> mychannels.bin
kg2bin write data/vhfmarine.csv --radio kg107 -o roms/vhf-marine.bin

# 3. Check what's in a ROM (the radio type is auto-detected)
kg2bin read mychannels.bin

# Modify an existing ROM: dump it to CSV, edit, write it back
kg2bin read master-roms/master_saw999.bin --csv saw999.csv
kg2bin write saw999.csv --radio saw999           # -> saw999.bin
kg2bin write saw999.csv --radio saw999 --force   # rebuild after more edits
```

`write` never replaces an existing `.bin` unless you add `--force` (or pick
another name with `-o`). That protects original radio dumps, because the
CSV export can't hold everything in a ROM: descriptions, corrupt records and
slots above channel 99 aren't kept.

`--radio` choices: `kg107` / `kg109` (VHF, 1500 kHz PLL reference) and
`saw999` (UHF, 6000 kHz reference). `--xtl <kHz>` sets the reference
directly instead. The reference isn't stored in the ROM, so `write` always
needs one; `read` works it out from the ROM's divider values (it's
unambiguous for all supported spacings), or you can pass `--radio`.

Sample `kg2bin read` output:

```
roms/uhfcb-80ch.bin (8192 bytes), 6000 kHz reference (Sawtron 999), auto-detected

Bank  Ch   RX MHz     TX MHz     Step kHz
   0   1   476.4250   476.4250       12.5
   0  81   476.4250   477.1750       12.5
```

Other options: `write --size 2048|4096|8192` (default 8192; a single-bank
2 KB image like `VHF_Master.bin` needs 2048), `write --round` (snap off-grid
frequencies to the nearest channel), `write --force` (replace an
existing output file), `write -v` (list every channel),
`read --csv -` (CSV to stdout). `kg2bin <command> --help` for the full list.

### How it differs from the Node tools

Both tools use the same exact maths and produce byte-for-byte identical
ROMs for every valid input (checked over ~63,000 frequencies). `kg2bin` is
stricter and does more:

- Bad rows — unsupported spacing, bank not 0–3, channel not 1–99, duplicate
  bank/channel, missing columns — stop with an error that names the CSV line.
  (`writerom.js` skips unsupported-spacing rows and doesn't check the rest.)
  Placeholder rows with a blank or `0` RX frequency are skipped by both.
- `--round` can snap off-grid frequencies to the nearest channel
  (`writerom.js` always treats them as an error).
- `--radio` is required for `write` (no silent default reference), and
  `write` won't overwrite an existing file without `--force`.
- `read` auto-detects the radio and can export a ROM back to an editable CSV.

### Tests

```bash
python3 -m unittest -v
```

The tests check the Python tool against the original: rebuilding every
committed ROM byte for byte, matching `readrom.js` output saved in
`tests/fixtures/node/`, and a bin → CSV → bin round trip of every ROM.

`tests/test_v1_node.py` also tests the Node tools in `kg2bin-v1/`. It runs
when `node` and the npm dependencies are installed (see the setup below), and
skips otherwise.

## Repository contents

| Path | What it is |
|------|------------|
| `kg2bin-v2/` | Python tool (`rom.py` = format encode/decode + CSV, `cli.py` = commands) |
| `kg2bin` | Symlink to `kg2bin-v2/`, so `python3 -m kg2bin` and `import kg2bin` work (Python names can't contain `-`) |
| `tests/` | Python tests; `tests/fixtures/node/` = saved `readrom.js` output |
| `pyproject.toml` | Python packaging (`kg2bin` console script) |
| `kg2bin-v1/writerom.js` | Original Node CSV → ROM encoder |
| `kg2bin-v1/readrom.js` | Original Node ROM → frequency list decoder |
| `kg2bin-v1/package-lock.json` | Node dependency lock (there is no `package.json`; `node_modules` isn't committed) |
| `data/uhfcb-80ch.csv` | Australian UHF CB: bank 0 = 80-channel 12.5 kHz plan, bank 1 = old 40-channel 25 kHz plan (Sawtron, xtl 6000) |
| `data/vhfmarine.csv` | VHF marine channels, 5 kHz step (KG107, xtl 1500) |
| `data/vhf2m.csv` | Currently identical to `vhfmarine.csv` |
| `roms/uhfcb-80ch.bin` | Built from `data/uhfcb-80ch.csv` with xtl 6000 |
| `roms/vhf-marine.bin` | Built from `data/vhfmarine.csv` with xtl 1500 |
| `roms/rom.bin` | Default output path — currently the same as `vhf-marine.bin` |
| `master-roms/master_saw999.bin` | Factory/master Sawtron 999 dump — 4 banks of 25 kHz UHF channels (see the known anomaly in the format doc) |
| `master-roms/VHF_Master.bin` | Master VHF dump — 2 KB, 7 channels around 168–171 MHz |

## Original Node.js tools (`kg2bin-v1/`)

The original programs live in [`kg2bin-v1/`](kg2bin-v1/). They share the
top-level `data/`, `roms/` and `master-roms/` folders with the Python tool.

### Setup

```bash
cd kg2bin-v1
npm install csv-parser@2.3.0 minimist@1.2.0
```

(Those are the versions in `kg2bin-v1/package-lock.json`; this was verified
to rebuild the committed ROMs byte for byte on Node 22.)

### Usage

Options left out fall back to the built-in defaults (`data/data.csv`,
`roms/rom.bin`, xtl 1500). The old style with a leading `2`
(`node kg2bin-v1/writerom.js 2 --csv=…`) still works.

Run from the repo root (`--csv`/`--rom` paths are relative to where you run
the command; the built-in defaults always point at the repo's `data/` and
`roms/` folders, wherever you run from):

```bash
# Build a ROM
node kg2bin-v1/writerom.js --csv=data/uhfcb-80ch.csv --rom=roms/uhfcb-80ch.bin --xtl=6000
node kg2bin-v1/writerom.js --csv=data/vhfmarine.csv  --rom=roms/vhf-marine.bin  --xtl=1500

# Read a ROM back
node kg2bin-v1/readrom.js --rom=roms/uhfcb-80ch.bin --xtl=6000
```

`--xtl` is the radio's PLL reference in kHz: **1500 for the KG107/109, 6000
for the Sawtron 999**. It isn't stored in the ROM, so reading with the wrong
value gives wrong frequencies.

Sample `readrom.js` output:

```
0-1 | RX: 476.4250 | TX: 476.4250 | Spacing 12.5 kHz (0x1)
0-81 | RX: 476.4250 | TX: 477.1750 | Spacing 12.5 kHz (0x51)
```

Format: `bank-channel | RX MHz | TX MHz | step | (slot number in hex)`.
A record that can't be valid is shown as
`2-76 | CORRUPT: <reason> (offset 0x…)` and counted in a warning at the end.

If `writerom.js` finds a problem in the CSV (off-grid frequency, unreadable
number, frequency out of range) it lists every `ERROR` with its CSV line
number, does **not** write the ROM, and exits with status 1.

## CSV format

```csv
bank,channel,rx_freq,tx_freq,desc,spacing
0,1,476.4250,476.4250,Repeater Channel,12.5
0,81,476.4250,477.1750,Rep 1,12.5
```

Used by both tools (`kg2bin template` writes a starter file).

- Matched by header name, so column order doesn't matter; `desc` is a free
  note (not stored in the ROM, so `kg2bin read --csv` leaves it blank).
- `bank` 0–3, `channel` 1–99, frequencies in MHz, `spacing` in kHz
  (5, 10, 12.5, 25 or 30).
- Blank/`0` `rx_freq` → placeholder row, skipped. Blank/`0` `tx_freq` →
  receive-only channel.
- An invalid `spacing`: `writerom.js` skips the row (printed as `Skipped`);
  `kg2bin` stops with an error naming the line.

## Bugs fixed in the Node tools (October 2026)

Found while documenting and fixed in `kg2bin-v1/`. None of them affected the
bundled CSVs: the fixed tools still rebuild the committed ROMs byte for byte.
The original 2019 code is in git history (commit `923339c`).

1. **Arguments were ignored** unless the first argument was a number > 1.
   With no arguments `writerom.js` crashed with a stack trace; it now prints
   a clear "CSV file not found" error.
2. **Off-grid frequencies were silently truncated** to the channel grid below
   (476.430 MHz at 12.5 kHz became 476.425 MHz). Now an error naming the
   nearest valid channels.
3. **Floating-point error could put a channel one step low** (`512.045 * 1000`
   = `512044.99999…` → 512.040 MHz). In a sweep of ~63,000 on-grid
   frequencies, 532 were wrong, all between 512.04 and 519.93 MHz. All maths
   is now done in whole Hz, and the sweep matches the Python tool exactly.
4. `readrom.js` decoded TX with the **RX** R value, labelled its input file
   "Output File", showed slot 128 as `1-0`, and decoded corrupt records as
   nonsense frequencies. Each half now uses its own R, the label is
   "ROM File", slot 128 shows as `0-128`, and corrupt records are flagged.
5. Values ≥ 0x1000 for N or R were silently mangled; now a range error.

## License

GPL-3.0 — see [LICENSE](LICENSE).
