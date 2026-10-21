# kg2bin

Tools to create and read the channel ROM (EPROM) contents for
**Kyodo KG107 / KG109** (VHF) and **Sawtron 999** (UHF) radios.

- `writerom.js` — turn a CSV channel list into an 8 KB `.bin` ready to burn
- `readrom.js`  — decode a `.bin` (e.g. one read from a radio) back into a
  list of RX/TX frequencies

The binary format is documented in [docs/ROM-FORMAT.md](docs/ROM-FORMAT.md).

> A Python rewrite for Linux is in progress — see the Python section below
> once it lands.

## Repository contents

| Path | What it is |
|------|------------|
| `writerom.js` | CSV → ROM encoder |
| `readrom.js` | ROM → frequency list decoder |
| `data/uhfcb-80ch.csv` | Australian UHF CB: bank 0 = 80-channel 12.5 kHz plan, bank 1 = old 40-channel 25 kHz plan (Sawtron, xtl 6000) |
| `data/vhfmarine.csv` | VHF marine channels, 5 kHz step (KG107, xtl 1500) |
| `data/vhf2m.csv` | Currently identical to `vhfmarine.csv` |
| `roms/uhfcb-80ch.bin` | Built from `data/uhfcb-80ch.csv` with xtl 6000 |
| `roms/vhf-marine.bin` | Built from `data/vhfmarine.csv` with xtl 1500 |
| `roms/rom.bin` | Default output path — currently the same as `vhf-marine.bin` |
| `master-roms/master_saw999.bin` | Factory/master Sawtron 999 dump — 4 banks of 25 kHz UHF channels (see the known anomaly in the format doc) |
| `master-roms/VHF_Master.bin` | Master VHF dump — 2 KB, 7 channels around 168–171 MHz |
| `package-lock.json` | Dependency lock (there is no `package.json`; `node_modules` isn't committed) |

## Setup (Node.js)

```bash
npm install csv-parser@2.3.0 minimist@1.2.0
```

(Those are the versions in `package-lock.json`; this was verified to rebuild
the committed ROMs byte for byte on Node 22.)

## Usage

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

### CSV format

```csv
bank,channel,rx_freq,tx_freq,desc,spacing
0,1,476.4250,476.4250,Repeater Channel,12.5
0,81,476.4250,477.1750,Rep 1,12.5
```

- Matched by header name, so column order doesn't matter; `desc` is ignored.
- `bank` 0–3, `channel` 1–99, frequencies in MHz, `spacing` in kHz
  (5, 10, 12.5, 25 or 30).
- Blank/`0` `rx_freq` or an invalid `spacing` → row skipped (printed as
  `Skipped`). Blank/`0` `tx_freq` → receive-only channel.

## Known limitations of the Node tools

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
