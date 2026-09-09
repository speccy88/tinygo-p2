#!/usr/bin/env python3
"""Behavioral acceptance for the controlled go-llvm cold-restorer."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PHASE2 = Path(os.environ.get("PHASE2_ROOT", Path(__file__).resolve().parents[1])).resolve()
BASELINE_ROOT = Path(os.environ["P2_BASELINE_ROOT"]).resolve()
RESTORE = PHASE2 / "binding/restore_go_llvm.py"
BUNDLE = PHASE2 / "binding/go-llvm-fc868cbb.bundle"
UPSTREAM_MANIFEST = PHASE2 / "binding/upstream-go-llvm-v0.0.0-20220420140351-512c94c1e71f-zip-manifest.json"
PATCH = PHASE2 / "patches/01-go-llvm-llvm14dev.patch"
BINDING_MANIFEST = PHASE2 / "patch-manifest.json"
MODULE_VERSION = "v0.0.0-20220420140351-512c94c1e71f"


def locate_zip():
    candidates = [
        BASELINE_ROOT / ".work/cache/go-mod/cache/download/tinygo.org/x/go-llvm/@v" / f"{MODULE_VERSION}.zip",
        BASELINE_ROOT / ".work/phase2/cache/go-mod/cache/download/tinygo.org/x/go-llvm/@v" / f"{MODULE_VERSION}.zip",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("pinned upstream go-llvm ZIP is unavailable")


class RestoreGoLLVMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zip = locate_zip()

    def run_restore(self, destination, patch=PATCH, upstream_zip=None):
        return subprocess.run([
            "python3", str(RESTORE), "--bundle", str(BUNDLE),
            "--upstream-zip", str(upstream_zip or self.zip),
            "--upstream-manifest", str(UPSTREAM_MANIFEST),
            "--binding-manifest", str(BINDING_MANIFEST),
            "--compat-patch", str(patch), "--destination", str(destination),
        ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_real_cold_restore(self):
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "controlled"
            result = self.run_restore(dst)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "PASS")
            self.assertTrue((dst / "backports.cpp").is_file())

    def test_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "existing"
            dst.mkdir()
            result = self.run_restore(dst)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("destination must be absent", result.stderr)

    def test_modified_patch_rejected_before_destination_materialization(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            altered = td / "altered.patch"
            altered.write_bytes(PATCH.read_bytes() + b"\n# unauthorized change\n")
            dst = td / "controlled"
            result = self.run_restore(dst, patch=altered)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("compatibility patch digest does not match", result.stderr)
            self.assertFalse(dst.exists(), "invalid patch must not materialize destination")

    def test_wrong_zip_rejected_before_destination_materialization(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            wrong_zip = td / "wrong.zip"
            shutil.copyfile(self.zip, wrong_zip)
            with wrong_zip.open("r+b") as handle:
                handle.seek(0)
                first = handle.read(1)
                handle.seek(0)
                handle.write(bytes([first[0] ^ 1]))
            dst = td / "controlled"
            result = self.run_restore(dst, upstream_zip=wrong_zip)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pinned module ZIP full-tree comparison failed", result.stderr)
            self.assertFalse(dst.exists(), "wrong ZIP must not materialize destination")


if __name__ == "__main__":
    unittest.main(verbosity=2)
