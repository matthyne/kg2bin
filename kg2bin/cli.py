"""kg2bin command line: build and read Kyodo/Sawtron channel ROMs."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .rom import (RADIOS, ROM_SIZE, BANK_SIZE, RomError, build_rom, detect_xtl,
                  fmt_mhz, fmt_num, read_csv, read_rom, write_csv)

RADIO_HELP = "kg107 / kg109 (VHF, 1500 kHz ref) or saw999 (UHF, 6000 kHz ref)"
RADIO_NAMES = {1500: "Kyodo KG107/109", 6000: "Sawtron 999"}

TEMPLATE = """\
bank,channel,rx_freq,tx_freq,desc,spacing
0,1,476.4250,476.4250,Simplex example,12.5
0,2,476.4250,477.1750,Repeater example (TX +750 kHz),12.5
0,3,476.4500,,Receive only example,12.5
"""


def radio_xtl(args, required):
    if args.xtl:
        return args.xtl
    if args.radio:
        return RADIOS[args.radio]
    if required:
        raise RomError("say which radio the ROM is for: --radio kg107 or "
                       "--radio saw999 (or --xtl <kHz>)")
    return None


def describe_xtl(xtl):
    name = RADIO_NAMES.get(xtl)
    return f"{xtl} kHz reference ({name})" if name else f"{xtl} kHz reference"


def cmd_write(args):
    xtl = radio_xtl(args, required=True)
    src = Path(args.csv)
    out = Path(args.output) if args.output else Path(src.stem + ".bin")
    if out.resolve() == src.resolve():
        raise RomError("output file would overwrite the CSV")
    channels = read_csv(src)
    if not channels:
        raise RomError(f"{src}: no channels found")
    rom = build_rom(channels, xtl, size=args.size, allow_round=args.round)
    out.write_bytes(rom)

    banks = {}
    for ch in channels:
        banks[ch.bank] = banks.get(ch.bank, 0) + 1
        if args.verbose:
            tx = fmt_mhz(ch.tx) if ch.tx is not None else "RX only"
            print(f"  bank {ch.bank} ch {ch.channel:2}  RX {fmt_mhz(ch.rx)}  "
                  f"TX {tx:9}  {fmt_num(ch.step)} kHz  {ch.desc}")
    per_bank = ", ".join(f"bank {b}: {n}" for b, n in sorted(banks.items()))
    print(f"Wrote {out} ({len(rom)} bytes) for {describe_xtl(xtl)}")
    print(f"{len(channels)} channels ({per_bank})")
    return 0


def cmd_read(args):
    path = Path(args.rom)
    rom = path.read_bytes()
    if len(rom) % BANK_SIZE:
        print(f"warning: {path} is {len(rom)} bytes, not a multiple of "
              f"{BANK_SIZE}", file=sys.stderr)
    xtl = radio_xtl(args, required=False)
    how = ""
    if xtl is None:
        xtl = detect_xtl(rom)
        if xtl is None:
            raise RomError("can't tell which radio this ROM is for; "
                           "pass --radio or --xtl")
        how = ", auto-detected"
    slots = list(read_rom(rom, xtl))
    good = [s for s in slots if not s.problem]
    bad = [s for s in slots if s.problem]

    if args.csv:
        if args.csv == "-":
            write_csv(good, sys.stdout)
        else:
            with open(args.csv, "w", newline="") as f:
                write_csv(good, f)
            print(f"Wrote {len(good)} channels to {args.csv}", file=sys.stderr)
    else:
        print(f"{path} ({len(rom)} bytes), {describe_xtl(xtl)}{how}")
        print()
        print("Bank  Ch   RX MHz     TX MHz     Step kHz")
        last_bank = None
        for s in slots:
            if last_bank is not None and s.bank != last_bank:
                print()
            last_bank = s.bank
            if s.problem and s.rx is None:
                print(f"{s.bank:>4}  {s.channel:>2}   ?? {s.problem}")
                continue
            tx = fmt_mhz(s.tx) if s.tx is not None else "RX only"
            flag = f"   !! {s.problem}" if s.problem else ""
            print(f"{s.bank:>4}  {s.channel:>2}   {fmt_mhz(s.rx):9}  "
                  f"{tx:9}  {fmt_num(s.step):>8}{flag}")
        print()
        print(f"{len(good)} channels" +
              (f", {len(bad)} with problems (marked ??/!!)" if bad else ""))

    if args.csv:
        for s in bad:
            print(f"warning: bank {s.bank} ch {s.channel} (offset "
                  f"0x{s.address:04X}): {s.problem} - left out of CSV",
                  file=sys.stderr)
    return 0


def cmd_template(args):
    if args.file == "-":
        sys.stdout.write(TEMPLATE)
        return 0
    out = Path(args.file)
    if out.exists() and not args.force:
        raise RomError(f"{out} already exists (use --force to overwrite)")
    out.write_text(TEMPLATE)
    print(f"Wrote {out} - edit it, then: kg2bin write {out} --radio saw999")
    return 0


def add_radio_args(p):
    g = p.add_mutually_exclusive_group()
    g.add_argument("-r", "--radio", choices=sorted(RADIOS), help=RADIO_HELP)
    g.add_argument("--xtl", type=int, metavar="KHZ",
                   help="PLL reference in kHz, instead of --radio")


def build_parser():
    p = argparse.ArgumentParser(
        prog="kg2bin",
        description="Build and read channel ROMs for Kyodo KG107/109 and "
                    "Sawtron 999 radios.",
        epilog="examples:\n"
               "  kg2bin template mychannels.csv\n"
               "  kg2bin write mychannels.csv --radio saw999\n"
               "  kg2bin read mychannels.bin\n"
               "  kg2bin read old.bin --csv old.csv     (edit, then write)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", metavar="command")

    w = sub.add_parser("write", help="build a .bin ROM from a channel CSV")
    w.add_argument("csv", help="channel list (bank,channel,rx_freq,tx_freq,"
                               "desc,spacing)")
    w.add_argument("-o", "--output", help="ROM file to write "
                                          "(default: <csv name>.bin)")
    add_radio_args(w)
    w.add_argument("--size", type=int, default=ROM_SIZE,
                   choices=[BANK_SIZE, 2 * BANK_SIZE, ROM_SIZE],
                   help=f"ROM size in bytes (default {ROM_SIZE})")
    w.add_argument("--round", action="store_true",
                   help="snap off-grid frequencies to the nearest channel "
                        "instead of stopping with an error")
    w.add_argument("-v", "--verbose", action="store_true",
                   help="list every channel written")
    w.set_defaults(func=cmd_write)

    r = sub.add_parser("read", help="show the channels in a .bin ROM")
    r.add_argument("rom", help="ROM file (.bin)")
    add_radio_args(r)
    r.add_argument("--csv", metavar="FILE",
                   help="save as a CSV that 'write' accepts ('-' for stdout)")
    r.set_defaults(func=cmd_read)

    t = sub.add_parser("template", help="create a starter channel CSV")
    t.add_argument("file", nargs="?", default="channels.csv",
                   help="where to write it (default channels.csv, '-' for stdout)")
    t.add_argument("--force", action="store_true", help="overwrite if it exists")
    t.set_defaults(func=cmd_template)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (RomError, OSError) as e:
        print(f"kg2bin: error: {e}", file=sys.stderr)
        return 1
