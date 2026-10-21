"""Tests for the Node tools in kg2bin-v1/. Skipped unless node and the npm
deps are available (kg2bin-v1/node_modules, or NODE_PATH pointing at them).

Setup: cd kg2bin-v1 && npm install csv-parser@2.3.0 minimist@1.2.0
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "kg2bin-v1"
NODE = ROOT / "tests" / "fixtures" / "node"


def node_ready():
    if not shutil.which("node"):
        return False
    r = subprocess.run(["node", "-e", "require('csv-parser'); require('minimist')"],
                       cwd=V1, capture_output=True)
    return r.returncode == 0


def node(script, *args):
    return subprocess.run(["node", str(V1 / script), *args], cwd=ROOT,
                          capture_output=True, text=True)


def write(csv_text, xtl, tmp):
    csv_path, rom_path = Path(tmp) / "in.csv", Path(tmp) / "out.bin"
    csv_path.write_text(csv_text)
    r = node("writerom.js", f"--csv={csv_path}", f"--rom={rom_path}", f"--xtl={xtl}")
    return r, rom_path


@unittest.skipUnless(node_ready(), "node + kg2bin-v1 npm deps not installed")
class NodeTools(unittest.TestCase):
    def test_writerom_reproduces_committed_roms(self):
        with tempfile.TemporaryDirectory() as tmp:
            for csv_path, rom_path, xtl in [
                    ("data/uhfcb-80ch.csv", "roms/uhfcb-80ch.bin", 6000),
                    ("data/vhfmarine.csv", "roms/vhf-marine.bin", 1500)]:
                for lead in ([], ["2"]):   # old-style leading "2" still works
                    with self.subTest(csv_path, lead=lead):
                        out = Path(tmp) / "out.bin"
                        r = node("writerom.js", *lead, f"--csv={csv_path}",
                                 f"--rom={out}", f"--xtl={xtl}")
                        self.assertEqual(r.returncode, 0, r.stdout)
                        self.assertEqual(out.read_bytes(),
                                         (ROOT / rom_path).read_bytes())

    def test_float_trap_frequency_is_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, rom = write("bank,channel,rx_freq,tx_freq,spacing\n"
                           "0,1,512.045,512.045,5\n", 1500, tmp)
            self.assertEqual(r.returncode, 0, r.stdout)
            out = node("readrom.js", f"--rom={rom}", "--xtl=1500").stdout
            self.assertIn("0-1 | RX: 512.0450 | TX: 512.0450", out)

    def test_off_grid_is_an_error_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, rom = write("bank,channel,rx_freq,tx_freq,spacing\n"
                           "0,1,476.430,476.430,12.5\n", 6000, tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("line 2", r.stdout)
            self.assertIn("not on the 12.5 kHz channel grid", r.stdout)
            self.assertFalse(rom.exists())

    def test_readrom_matches_original_output(self):
        data = re.compile(r"^\d+-\d+ \|")
        for rom, xtl, fixture in [
                ("roms/uhfcb-80ch.bin", 6000, "readrom_uhfcb-80ch.txt"),
                ("roms/vhf-marine.bin", 1500, "readrom_vhf-marine.txt"),
                ("master-roms/master_saw999.bin", 6000, "readrom_master_saw999.txt"),
                ("master-roms/VHF_Master.bin", 1500, "readrom_VHF_Master.txt")]:
            with self.subTest(rom):
                got = [l for l in node("readrom.js", f"--rom={rom}",
                                       f"--xtl={xtl}").stdout.splitlines()
                       if data.match(l)]
                want = [l for l in (NODE / fixture).read_text().splitlines()
                        if data.match(l)]
                # the one corrupt record is now flagged instead of decoded
                want = [("2-76 | CORRUPT: RX step 400 kHz is not valid for a "
                         "6000 kHz reference (offset 0x14b0)")
                        if l.startswith("2-76 |") and "saw999" in rom else l
                        for l in want]
                self.assertEqual(got, want)

    def test_slot_128_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, rom = write("bank,channel,rx_freq,tx_freq,spacing\n"
                           "0,128,476.425,,12.5\n", 6000, tmp)
            self.assertEqual(r.returncode, 0, r.stdout)
            out = node("readrom.js", f"--rom={rom}", "--xtl=6000").stdout
            self.assertIn("0-128 | RX: 476.4250", out)


if __name__ == "__main__":
    unittest.main()
