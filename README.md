# kg2bin

Tools to create and read the channel ROM (EPROM) contents for
**Kyodo KG107 / KG109** (VHF) and **Sawtron 999** (UHF) radios.

- Write a channel list (CSV) into a `.bin` ready to burn to the EPROM
- Read a `.bin` (e.g. dumped from a radio) back into a channel list or CSV

There are two implementations:

- **`kg2bin`** — Python 3 command-line tool for Linux (recommended)
- `writerom.js` / `readrom.js` — the original Node.js tools

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

Output is byte-for-byte identical to `writerom.js` for every valid input
except where the Node tool is wrong (see known limitations below):

- Exact arithmetic — no channels land one step low through float error.
- Off-grid frequencies are an **error** (naming the nearest valid channels)
  instead of being silently truncated; `--round` opts in to snapping.
- Bad rows (unsupported spacing, bank not 0–3, channel not 1–99, duplicate
  bank/channel, unparseable numbers, missing columns) stop with an error that
  names the CSV line, instead of being skipped. Placeholder rows with a blank
  or `0` RX frequency are still skipped quietly.
- `--radio` is required for `write` (no silent default reference), and
  `write` won't overwrite an existing file without `--force`.
- `read` decodes TX with its own R value, flags corrupt records (e.g.
  `master_saw999.bin` bank 2 ch 76) and leaves them out of CSV exports.
- Options always work — no leading `2` needed.

### Tests

```bash
python3 -m unittest -v
```

The tests check the Python tool against the original: rebuilding every
committed ROM byte for byte, matching `readrom.js` output saved in
`tests/fixtures/node/`, and a bin → CSV → bin round trip of every ROM.

## Repository contents

| Path | What it is |
|------|------------|
| `kg2bin/` | Python tool (`rom.py` = format encode/decode + CSV, `cli.py` = commands) |
| `tests/` | Python tests; `tests/fixtures/node/` = saved `readrom.js` output |
| `pyproject.toml` | Python packaging (`kg2bin` console script) |
| `writerom.js` | Original Node CSV → ROM encoder |
| `readrom.js` | Original Node ROM → frequency list decoder |
| `data/uhfcb-80ch.csv` | Australian UHF CB: bank 0 = 80-channel 12.5 kHz plan, bank 1 = old 40-channel 25 kHz plan (Sawtron, xtl 6000) |
| `data/vhfmarine.csv` | VHF marine channels, 5 kHz step (KG107, xtl 1500) |
| `data/vhf2m.csv` | Currently identical to `vhfmarine.csv` |
| `roms/uhfcb-80ch.bin` | Built from `data/uhfcb-80ch.csv` with xtl 6000 |
| `roms/vhf-marine.bin` | Built from `data/vhfmarine.csv` with xtl 1500 |
| `roms/rom.bin` | Default output path — currently the same as `vhf-marine.bin` |
| `master-roms/master_saw999.bin` | Factory/master Sawtron 999 dump — 4 banks of 25 kHz UHF channels (see the known anomaly in the format doc) |
| `master-roms/VHF_Master.bin` | Master VHF dump — 2 KB, 7 channels around 168–171 MHz |
| `package-lock.json` | Dependency lock (there is no `package.json`; `node_modules` isn't committed) |

## Original Node.js tools

### Setup

```bash
npm install csv-parser@2.3.0 minimist@1.2.0
```

(Those are the versions in `package-lock.json`; this was verified to rebuild
the committed ROMs byte for byte on Node 22.)

### Usage

> **Important quirk:** both scripts only read the `--` options if the **first
> argument is a number greater than 1**. Without it, the options are silently
> ignored and the hard-coded defaults are used (`./data/data.csv`,
> `./roms/rom.bin`, xtl 1500). Put a `2` first:

```bash
# Build a ROM
node writerom.js 2 --csv=data/uhfcb-80ch.csv --rom=roms/uhfcb-80ch.bin --xtl=6000
node writerom.js 2 --csv=data/vhfmarine.csv  --rom=roms/vhf-marine.bin  --xtl=1500

# Read a ROM back
node readrom.js 2 --rom=roms/uhfcb-80ch.bin --xtl=6000
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
- An invalid `spacing`: Node skips the row (printed as `Skipped`); `kg2bin`
  stops with an error naming the line.

## Known limitations of the Node tools

(All fixed in the Python tool.)

Found while documenting. They don't affect the bundled CSVs (those rebuild the
committed ROMs exactly).

1. **Arguments ignored** unless the first argument is a number > 1 (see above).
   With no arguments, `writerom.js` crashes looking for `./data/data.csv`.
2. **Off-grid frequencies are silently truncated** to the channel grid below
   — e.g. 476.430 MHz at 12.5 kHz becomes 476.425 MHz with no warning.
3. **Floating-point error can put a channel one step low.** Frequencies are
   multiplied as floats and then truncated, so e.g. `512.045 * 1000` =
   `512044.99999…` → 512.040 MHz. In a sweep of ~63,000 on-grid frequencies
   (136–174 and 400–520 MHz, every step size, both reference values) 532 were
   encoded one step low, all between 512.04 and 519.93 MHz; none in the UHF
   CB or VHF marine ranges.
4. `readrom.js` decodes TX using the **RX** R value, prints the input file as
   "Output File", shows slot 128 as `1-0`, and only treats a slot as empty if
   byte 0 is `0xFF`.
5. Values ≥ 0x1000 for N or R would be silently mangled (no range check).

## License

GPL-3.0 — see [LICENSE](LICENSE).
