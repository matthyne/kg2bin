"""Encode/decode Kyodo KG107/109 and Sawtron 999 channel ROMs.

Format reference: docs/ROM-FORMAT.md. All arithmetic is exact (Fraction),
so frequencies never land a channel step low through float rounding.
"""

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction

PRESCALE = 64          # dual-modulus prescaler
RX_OFFSET = 21600      # kHz, RX synth runs this far below the receive freq
BANKS = 4
SLOTS_PER_BANK = 128
MAX_CHANNEL = 99       # highest channel the radio can select in a bank
RECORD = 16
ROM_SIZE = BANKS * SLOTS_PER_BANK * RECORD   # 8192
BANK_SIZE = SLOTS_PER_BANK * RECORD          # 2048
EMPTY = 0xFF

# PLL reference frequency (kHz) per radio model; not stored in the ROM.
RADIOS = {
    "kg107": 1500,
    "kg109": 1500,
    "saw999": 6000,
}
STEPS = (Fraction(5), Fraction(10), Fraction(25, 2), Fraction(25), Fraction(30))


class RomError(ValueError):
    pass


@dataclass
class Channel:
    bank: int
    channel: int
    rx: Fraction            # kHz
    tx: Fraction | None     # kHz, None = receive only
    step: Fraction          # kHz
    desc: str = ""


# ---------- helpers ----------

def parse_mhz(text):
    """'476.4250' -> Fraction kHz; blank or zero -> None."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        value = Fraction(Decimal(text)) * 1000
    except (InvalidOperation, ValueError):
        raise RomError(f"not a frequency: {text!r}")
    return value if value > 0 else None


def parse_step(text):
    text = (text or "").strip()
    try:
        step = Fraction(Decimal(text))
    except (InvalidOperation, ValueError):
        raise RomError(f"not a channel spacing: {text!r}")
    if step not in STEPS:
        raise RomError(f"spacing {text} kHz not supported "
                       f"(use {', '.join(fmt_num(s) for s in STEPS)})")
    return step


def fmt_num(value):
    """Exact, minimal decimal form of a Fraction (12.5, 25, 476.4250...)."""
    d = Decimal(value.numerator) / Decimal(value.denominator)
    s = format(d.normalize(), "f")
    return s


def fmt_mhz(khz):
    mhz = Decimal(khz.numerator) / Decimal(khz.denominator) / 1000
    s = format(mhz, "f")
    whole, _, frac = s.partition(".")
    return f"{whole}.{frac.rstrip('0').ljust(4, '0')}"


def to_nibbles(value, count):
    return bytes((value >> (4 * i)) & 0xF for i in range(count))


def from_nibbles(data):
    return sum(b << (4 * i) for i, b in enumerate(data))


def slot_address(bank, channel):
    return bank * BANK_SIZE + (channel - 1) * RECORD


# ---------- encoding ----------

def encode_half(freq, step, xtl, offset, allow_round=False):
    """Return 8 bytes A(2) N(3) R(3) for one RX or TX frequency (kHz)."""
    r = Fraction(xtl) / step
    if r.denominator != 1:
        raise RomError(f"{fmt_num(step)} kHz spacing is not possible with a "
                       f"{xtl} kHz reference")
    d = (freq - offset) / step
    if d.denominator != 1:
        if not allow_round:
            lo = (d.numerator // d.denominator) * step + offset
            raise RomError(f"{fmt_mhz(freq)} MHz is not on the "
                           f"{fmt_num(step)} kHz channel grid (nearest: "
                           f"{fmt_mhz(lo)} or {fmt_mhz(lo + step)}); "
                           f"use --round to snap to the nearest channel")
        d = Fraction(int(d + Fraction(1, 2)))
    d = int(d)
    n, a = divmod(d, PRESCALE)
    r = int(r)
    if d < 0 or n > 0xFFF or r > 0xFFF:
        raise RomError(f"{fmt_mhz(freq)} MHz is out of range for this radio")
    return to_nibbles(a, 2) + to_nibbles(n, 3) + to_nibbles(r, 3)


def encode_channel(ch, xtl, allow_round=False):
    rx = encode_half(ch.rx, ch.step, xtl, RX_OFFSET, allow_round)
    tx = (encode_half(ch.tx, ch.step, xtl, 0, allow_round)
          if ch.tx is not None else bytes([EMPTY] * 8))
    return rx + tx


def build_rom(channels, xtl, size=ROM_SIZE, allow_round=False):
    rom = bytearray([EMPTY] * size)
    for ch in channels:
        addr = slot_address(ch.bank, ch.channel)
        if addr + RECORD > size:
            raise RomError(f"bank {ch.bank} does not fit in a {size}-byte ROM")
        try:
            rom[addr:addr + RECORD] = encode_channel(ch, xtl, allow_round)
        except RomError as e:
            raise RomError(f"bank {ch.bank} ch {ch.channel}: {e}") from None
    return bytes(rom)


# ---------- decoding ----------

@dataclass
class Slot:
    bank: int
    channel: int
    address: int
    rx: Fraction | None = None
    tx: Fraction | None = None
    step: Fraction | None = None
    problem: str = ""


def decode_half(data, xtl, offset):
    """Return (freq_khz, step_khz) or raise RomError for a bad record."""
    if any(b > 0xF for b in data):
        raise RomError("bytes are not nibbles (>0x0F)")
    a = from_nibbles(data[0:2])
    n = from_nibbles(data[2:5])
    r = from_nibbles(data[5:8])
    if r == 0:
        raise RomError("reference divider R is 0")
    step = Fraction(xtl, r)
    return (n * PRESCALE + a) * step + offset, step


def detect_xtl(rom):
    """Work out the PLL reference from the R values in the ROM.

    Each supported (reference, spacing) pair gives a distinct R, so a single
    good record identifies the radio. Returns None if nothing matches.
    """
    lookup = {}
    for xtl in set(RADIOS.values()):
        for step in STEPS:
            lookup[int(Fraction(xtl) / step)] = xtl
    votes = {}
    for addr in range(0, len(rom) - RECORD + 1, RECORD):
        rec = rom[addr:addr + RECORD]
        if rec[0] == EMPTY or any(b > 0xF for b in rec[:8]):
            continue
        xtl = lookup.get(from_nibbles(rec[5:8]))
        if xtl:
            votes[xtl] = votes.get(xtl, 0) + 1
    if not votes:
        return None
    return max(votes, key=votes.get)


def read_rom(rom, xtl):
    """Yield a Slot for every non-empty record."""
    for addr in range(0, len(rom) - RECORD + 1, RECORD):
        rec = rom[addr:addr + RECORD]
        if all(b == EMPTY for b in rec):
            continue
        bank, slot = divmod(addr // RECORD, SLOTS_PER_BANK)
        s = Slot(bank=bank, channel=slot + 1, address=addr)
        try:
            if rec[0] == EMPTY:
                raise RomError("RX half is empty but TX is set")
            s.rx, s.step = decode_half(rec[:8], xtl, RX_OFFSET)
            if s.step not in STEPS:
                raise RomError(f"RX step {fmt_num(s.step)} kHz is not valid "
                               f"for a {xtl} kHz reference")
            if not all(b == EMPTY for b in rec[8:]):
                s.tx, tx_step = decode_half(rec[8:], xtl, 0)
                if tx_step != s.step:
                    raise RomError(f"RX/TX steps differ ({fmt_num(s.step)} "
                                   f"vs {fmt_num(tx_step)} kHz)")
            if s.channel > MAX_CHANNEL:
                s.problem = f"slot {s.channel} is beyond channel {MAX_CHANNEL}"
        except RomError as e:
            s.rx = s.tx = s.step = None
            s.problem = f"corrupt record: {e}"
        yield s


# ---------- CSV ----------

CSV_FIELDS = ["bank", "channel", "rx_freq", "tx_freq", "desc", "spacing"]


def read_csv(path):
    """Parse a channel CSV. Raises RomError naming the line on bad input."""
    channels = []
    seen = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = {"bank", "channel", "rx_freq", "tx_freq", "spacing"} - set(
            h.strip() for h in reader.fieldnames or [])
        if missing:
            raise RomError(f"{path}: missing column(s): "
                           f"{', '.join(sorted(missing))}")
        for row in reader:
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            line = reader.line_num
            if not any(row.values()):
                continue
            try:
                rx = parse_mhz(row["rx_freq"])
                tx = parse_mhz(row["tx_freq"])
                if rx is None:
                    if tx is not None:
                        raise RomError("TX without RX is not supported")
                    continue        # placeholder row, e.g. "0,89,0,0,,"
                try:
                    bank, channel = int(row["bank"]), int(row["channel"])
                except ValueError:
                    raise RomError("bank and channel must be whole numbers")
                if not 0 <= bank < BANKS:
                    raise RomError(f"bank {bank} out of range 0-{BANKS - 1}")
                if not 1 <= channel <= MAX_CHANNEL:
                    raise RomError(f"channel {channel} out of range "
                                   f"1-{MAX_CHANNEL}")
                if (bank, channel) in seen:
                    raise RomError(f"bank {bank} ch {channel} already "
                                   f"defined on line {seen[(bank, channel)]}")
                seen[(bank, channel)] = line
                step = parse_step(row["spacing"])
            except RomError as e:
                raise RomError(f"{path} line {line}: {e}") from None
            channels.append(Channel(bank, channel, rx, tx, step,
                                    row.get("desc", "")))
    return channels


def write_csv(slots, f):
    w = csv.writer(f, lineterminator="\n")
    w.writerow(CSV_FIELDS)
    for s in slots:
        w.writerow([s.bank, s.channel, fmt_mhz(s.rx),
                    fmt_mhz(s.tx) if s.tx is not None else "",
                    "", fmt_num(s.step)])
