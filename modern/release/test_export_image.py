import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

MODERN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODERN / "hil"))
from test_p2ram import elf

spec = importlib.util.spec_from_file_location("export_image", MODERN / "export-image.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Export(unittest.TestCase):
    def test_zero_fill_gaps_not_bss_and_align_for_boot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "app.elf"
            target = Path(folder) / "_BOOT_P2.BIX"
            source.write_bytes(elf([(0x100, 0, b"boot", 8), (0x110, 16, b"abc", 1000)]))
            result = module.export(source, target)
            self.assertEqual(result, b"boot" + bytes(12) + b"abc\0")
            self.assertEqual(target.read_bytes(), result)

    def test_reject_renamed_raw_input(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "app.elf"
            source.write_bytes(b"not an elf")
            with self.assertRaisesRegex(ValueError, "native P2 ELF"):
                module.export(source, Path(folder) / "app.binary")

    def test_reject_rom_sd_reserved_region(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "app.elf"
            source.write_bytes(elf([(0x100, 0, b"boot", 4), (0x110, 496 * 1024, b"tail", 4)]))
            with self.assertRaisesRegex(ValueError, "496 KiB"):
                module.export(source, Path(folder) / "app.binary")


if __name__ == "__main__":
    unittest.main()
