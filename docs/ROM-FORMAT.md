# Kyodo KG107/109 & Sawtron 999 channel ROM format

This describes the binary format that `writerom.js` produces and `readrom.js`
decodes. Everything here was derived from the source and verified against the
ROM images in this repo (the original tools regenerate `roms/*.bin` byte for
byte from `data/*.csv`).

## The radio side (what the numbers mean)

The radios use a dual-modulus PLL synthesiser. For every channel the ROM holds
three divider values for receive and three for transmit:

| Value | Width | Meaning |
|-------|-------|---------|
| **A** | 2 nibbles (0x00–0x3F used) | swallow counter — remainder of D / 64 |
| **N** | 3 nibbles (0x000–0xFFF) | main counter — quotient of D / 64 |
| **R** | 3 nibbles (0x000–0xFFF) | reference divider = `xtl / step` |

where

```
D       = N * 64 + A                 (64 = prescaler modulus, fixed)
step    = xtl / R                    (channel step / spacing, kHz)
TX freq = D * step                   (kHz)
RX freq = D * step + 21600           (kHz — RX synth runs 21.6 MHz below the
                                      receive frequency, i.e. the 1st IF)
```

`xtl` is the PLL reference frequency in kHz. It is **not stored in the ROM** —
it's a property of the radio, so you must know it to encode or decode:

| Radio | `xtl` (kHz) | Typical use in this repo |
|-------|-------------|--------------------------|
| Kyodo KG107/109 (VHF) | 1500 | `data/vhfmarine.csv` → `roms/vhf-marine.bin` |
| Sawtron 999 (UHF) | 6000 | `data/uhfcb-80ch.csv` → `roms/uhfcb-80ch.bin` |

Valid channel steps (as enforced by `writerom.js`): **5, 10, 12.5, 25, 30 kHz**.
For both reference frequencies every one of those gives an integer R
(e.g. 6000 / 12.5 = 480 = 0x1E0, 1500 / 5 = 300 = 0x12C).

## Memory layout

```
ROM size      8192 bytes (0x2000), unused bytes = 0xFF
4 banks       × 128 channel slots × 16 bytes
              (only channels 1–99 of each bank are addressable by the radio)
address       = bank * 2048 + (channel - 1) * 16
```

| Bank | Byte range |
|------|------------|
| 0 | 0x0000–0x07FF |
| 1 | 0x0800–0x0FFF |
| 2 | 0x1000–0x17FF |
| 3 | 0x1800–0x1FFF |

`master-roms/VHF_Master.bin` is only 2048 bytes — a single bank — so the VHF
radio's EPROM may be smaller than 8 KB. `writerom.js` always writes 8192 bytes;
bank 0 is the first 2048 bytes either way.

## Channel record (16 bytes)

```
offset  0  1 | 2  3  4 | 5  6  7 | 8  9 | 10 11 12 | 13 14 15
        A    |    N    |    R    | A    |    N     |    R
        ------ RX (8 bytes) ------ ------ TX (8 bytes) -------
```

Each byte holds **one hex nibble** (high nibble always 0), **least-significant
nibble first**. Example — value 0x12C stored as 3 nibbles is `0C 02 01`.

Worked example, first record of `roms/uhfcb-80ch.bin` (Sawtron, xtl 6000):

```
02 02 08 03 02 00 0E 01   02 02 03 05 02 00 0E 01
RX: A=0x22=34  N=0x238=568  R=0x1E0=480 → step 12.5 kHz
    D = 568*64+34 = 36386 → 36386*12.5 + 21600 = 476425 kHz = 476.4250 MHz
TX: A=0x22=34  N=0x253=595  R=0x1E0=480
    D = 595*64+34 = 38114 → 38114*12.5        = 476425 kHz = 476.4250 MHz
```

### Empty / partial records

- A slot whose first byte is `0xFF` is an empty channel.
- A record with RX filled and TX bytes all `0xFF` is a **receive-only**
  channel (`readrom.js` prints `--Empty--` for TX; it tests byte 9).

## CSV input format (`writerom.js`)

Columns are matched **by header name**, so order doesn't matter (the two VHF
CSVs list `tx_freq` before `rx_freq`). Extra columns such as `desc` are ignored.

| Column | Example | Notes |
|--------|---------|-------|
| `bank` | `0` | 0–3 |
| `channel` | `23` | 1–99 |
| `rx_freq` | `476.4250` | MHz. Blank or `0` → whole row skipped |
| `tx_freq` | `477.1750` | MHz. Blank or `0` → receive-only (TX = 0xFF) |
| `spacing` | `12.5` | kHz, one of 5 / 10 / 12.5 / 25 / 30, else row skipped |

## Known anomaly in `master-roms/master_saw999.bin`

Bank 2, channel 76 (offset 0x14B0) decodes to nonsense on the RX half
(`RX 807.2000 / TX 7684.8000 / 400 kHz` in `readrom.js`, which uses the RX
R value for both halves):

```
0C 02 0E 01 00 0F 00 00 | 0C 00 0C 02 01 00 0F 00
```

The TX half is fine on its own (R = 0x0F0 = 240 → 25 kHz, 480.3000 MHz, which
fits between its neighbours 2-75 = 480.2750 and 2-77 = 480.3250). The RX half
looks like it is missing a byte compared with its neighbours, but the cause is
unknown — treat that channel as suspect if this master is ever reused.
