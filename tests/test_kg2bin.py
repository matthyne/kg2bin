"""Tests for kg2bin. Run from the repo root: python3 -m unittest -v

The original Node tools (kg2bin-v1/) are the oracle: roms/*.bin were
produced by writerom.js, and tests/fixtures/node/readrom_*.txt are
readrom.js output.
"""

import io
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
from pathlib import Path

from kg2bin.cli import main
from kg2bin.rom import (Channel, RomError, build_rom, detect_xtl, encode_half,
                        fmt_mhz, read_csv, read_rom, RX_OFFSET)

ROOT = Path(__file__).resolve().parent.parent
NODE = ROOT / "tests" / "fixtures" / "node"

BUILDS = [  # csv, committed rom, xtl
    ("data/uhfcb-80ch.csv", "roms/uhfcb-80ch.bin", 6000),
    ("data/vhfmarine.csv", "roms/vhf-marine.bin", 1500),
    ("data/vhf2m.csv", "roms/rom.bin", 1500),
]
DUMPS = [  # rom, node readrom output, xtl
    ("roms/uhfcb-80ch.bin", "readrom_uhfcb-80ch.txt", 6000),
    ("roms/vhf-marine.bin", "readrom_vhf-marine.txt", 1500),
    ("master-roms/master_saw999.bin", "readrom_master_saw999.txt", 6000),
    ("master-roms/VHF_Master.bin", "readrom_VHF_Master.txt", 1500),
]
CORRUPT = {("master-roms/master_saw999.bin", 0x14B0)}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class MatchesNodeTools(unittest.TestCase):
    def test_write_reproduces_committed_roms(self):
        for csv_path, rom_path, xtl in BUILDS:
            with self.subTest(csv_path):
                rom = build_rom(read_csv(ROOT / csv_path), xtl)
                self.assertEqual(rom, (ROOT / rom_path).read_bytes())

    def test_read_matches_readrom_js(self):
        line = re.compile(r"^(\d+)-(\d+) \| RX: ([\d.]+) \| TX: (\S+)")
        for rom_path, txt, xtl in DUMPS:
            with self.subTest(rom_path):
                expected = {}
                for m in map(line.match, (NODE / txt).read_text().splitlines()):
                    if m:
                        b, c, rx, tx = m.groups()
                        tx = None if tx.startswith("--") else tx
                        expected[(int(b), int(c))] = (rx, tx)
                rom = (ROOT / rom_path).read_bytes()
                got = {}
                for s in read_rom(rom, xtl):
                    if (rom_path, s.address) in CORRUPT:
                        self.assertTrue(s.problem)
                        expected.pop((s.bank, s.channel))
                        continue
                    got[(s.bank, s.channel)] = (
                        fmt_mhz(s.rx), fmt_mhz(s.tx) if s.tx else None)
                self.assertEqual(got, expected)


class RoundTrip(unittest.TestCase):
    def test_bin_to_csv_to_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rom_path, _, xtl in DUMPS:
                with self.subTest(rom_path):
                    original = (ROOT / rom_path).read_bytes()
                    csv_path = Path(tmp) / "out.csv"
                    bin_path = Path(tmp) / "out.bin"
                    code, _, _ = run("read", str(ROOT / rom_path),
                                     "--csv", str(csv_path))
                    self.assertEqual(code, 0)
                    code, _, _ = run("write", str(csv_path), "--xtl", str(xtl),
                                     "--size", str(len(original)),
                                     "-o", str(bin_path), "--force")
                    self.assertEqual(code, 0)
                    rebuilt = bytearray(bin_path.read_bytes())
                    expected = bytearray(original)
                    for path, addr in CORRUPT:
                        if path == rom_path:
                            expected[addr:addr + 16] = rebuilt[addr:addr + 16]
                    self.assertEqual(rebuilt, expected)


class Encoding(unittest.TestCase):
    def test_float_trap_frequency_is_exact(self):
        # writerom.js encodes 512.045 MHz one 5 kHz step low (float noise)
        freq = Fraction(512045)
        data = encode_half(freq, Fraction(5), 1500, 0)
        a = data[0] | data[1] << 4
        n = data[2] | data[3] << 4 | data[4] << 8
        self.assertEqual((n * 64 + a) * 5, 512045)

    def test_off_grid_is_rejected_unless_rounding(self):
        ch = Channel(0, 1, Fraction(476430), Fraction(476430), Fraction(25, 2))
        with self.assertRaisesRegex(RomError, "not on the 12.5 kHz"):
            build_rom([ch], 6000)
        rom = build_rom([ch], 6000, allow_round=True)
        s = next(read_rom(rom, 6000))
        self.assertEqual(fmt_mhz(s.rx), "476.4250")

    def test_receive_only(self):
        ch = Channel(1, 5, Fraction(476425), None, Fraction(25, 2))
        rom = build_rom([ch], 6000)
        self.assertEqual(rom[2048 + 64 + 8:2048 + 64 + 16], b"\xff" * 8)
        s = next(read_rom(rom, 6000))
        self.assertEqual((s.bank, s.channel, s.tx), (1, 5, None))

    def test_bank_must_fit_rom_size(self):
        ch = Channel(1, 1, Fraction(156050), None, Fraction(5))
        with self.assertRaisesRegex(RomError, "does not fit"):
            build_rom([ch], 1500, size=2048)

    def test_rx_below_offset_is_out_of_range(self):
        ch = Channel(0, 1, Fraction(RX_OFFSET - 5), None, Fraction(5))
        with self.assertRaisesRegex(RomError, "out of range"):
            build_rom([ch], 1500)


class CsvParsing(unittest.TestCase):
    def parse(self, body):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("bank,channel,rx_freq,tx_freq,desc,spacing\n" + body)
        try:
            return read_csv(f.name)
        finally:
            Path(f.name).unlink()

    def test_placeholder_and_blank_rows_skipped(self):
        chans = self.parse("0,1,476.425,,x,12.5\n0,2,0,0,,\n\n,,,,,\n")
        self.assertEqual([(c.bank, c.channel) for c in chans], [(0, 1)])

    def test_errors_name_the_line(self):
        cases = {
            "0,1,476.425,476.425,,6.25\n": "line 2: spacing 6.25",
            "0,100,476.425,,,12.5\n": "line 2: channel 100",
            "4,1,476.425,,,12.5\n": "line 2: bank 4",
            "0,1,476.425,,,12.5\n0,1,476.45,,,12.5\n": "line 3: .*line 2",
            "0,1,abc,,,12.5\n": "line 2: not a frequency",
        }
        for body, pattern in cases.items():
            with self.subTest(body):
                with self.assertRaisesRegex(RomError, pattern):
                    self.parse(body)

    def test_missing_column(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("bank,channel,rx_freq\n0,1,476.425\n")
        try:
            with self.assertRaisesRegex(RomError, "missing column.*spacing"):
                read_csv(f.name)
        finally:
            Path(f.name).unlink()


class Cli(unittest.TestCase):
    def test_detect_radio(self):
        self.assertEqual(detect_xtl((ROOT / "roms/uhfcb-80ch.bin").read_bytes()), 6000)
        self.assertEqual(detect_xtl((ROOT / "roms/vhf-marine.bin").read_bytes()), 1500)
        self.assertIsNone(detect_xtl(b"\xff" * 2048))

    def test_write_requires_radio(self):
        code, _, err = run("write", str(ROOT / "data/uhfcb-80ch.csv"),
                           "-o", "/dev/null")
        self.assertEqual(code, 1)
        self.assertIn("--radio", err)

    def test_template_then_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "c.csv"
            self.assertEqual(run("template", str(csv_path))[0], 0)
            self.assertEqual(run("template", str(csv_path))[0], 1)  # no clobber
            code, out, _ = run("write", str(csv_path), "--radio", "saw999",
                               "-o", str(Path(tmp) / "c.bin"))
            self.assertEqual(code, 0, out)
            code, out, _ = run("read", str(Path(tmp) / "c.bin"))
            self.assertIn("477.1750", out)
            self.assertIn("RX only", out)

    def test_write_does_not_clobber_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, bin_path = Path(tmp) / "c.csv", Path(tmp) / "c.bin"
            run("template", str(csv_path))
            bin_path.write_bytes(b"original dump")
            args = ["write", str(csv_path), "--radio", "saw999",
                    "-o", str(bin_path)]
            code, _, err = run(*args)
            self.assertEqual(code, 1)
            self.assertIn("--force", err)
            self.assertEqual(bin_path.read_bytes(), b"original dump")
            self.assertEqual(run(*args, "--force")[0], 0)
            self.assertEqual(len(bin_path.read_bytes()), 8192)


if __name__ == "__main__":
    unittest.main()
