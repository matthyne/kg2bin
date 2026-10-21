# kg2bin v2 — Python tool

`kg2bin` builds and reads channel ROMs for Kyodo KG107/109 (VHF) and
Sawtron 999 (UHF) radios. It is the recommended tool. The original Node.js
version is in [`../kg2bin-v1/`](../kg2bin-v1/).

## Install

Needs Python 3.10+ and no other packages. From the repo root:

```bash
pipx install --editable .     # puts the `kg2bin` command on your PATH
```

Or run it without installing, from the repo root: `python3 -m kg2bin …`

(The package is named `kg2bin`. The `kg2bin` folder in the repo root is a
symlink to this one.)

## Use

```bash
kg2bin template mychannels.csv                # starter channel list
kg2bin write mychannels.csv --radio saw999    # -> mychannels.bin
kg2bin read mychannels.bin                    # show channels (radio auto-detected)
kg2bin read old.bin --csv old.csv             # ROM -> editable CSV
```

`--radio`: `kg107` / `kg109` (VHF) or `saw999` (UHF). Alternatively give the
PLL reference with `--xtl <kHz>`: 1500 or 6000.

Useful `write` options:

| Option | Does |
|--------|------|
| `-o FILE` | Output name (default: CSV name with `.bin`) |
| `--force` | Replace an existing `.bin`. Without it `write` refuses to overwrite |
| `--size 2048` | Single-bank 2 KB image (default 8192) |
| `--round` | Snap off-grid frequencies to the nearest channel instead of erroring |
| `-v` | List every channel written |

`kg2bin <command> --help` shows everything. Errors name the CSV line, and
nothing is written until the whole file is valid.

## Files

- `cli.py` — the commands
- `rom.py` — ROM format encode/decode and CSV handling (see
  [`../docs/ROM-FORMAT.md`](../docs/ROM-FORMAT.md))

Tests: `python3 -m unittest -v` from the repo root.
