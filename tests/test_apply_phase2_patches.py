#!/usr/bin/env python3
import hashlib
import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PHASE2 = Path(os.environ.get('PHASE2_ROOT', Path(__file__).resolve().parents[1])).resolve()
APPLIER = PHASE2 / 'src/apply_phase2_patches.py'

if not APPLIER.is_file():
    raise RuntimeError(f'extracted Phase 2 applier is unavailable: {APPLIER}')


def run(*args, cwd):
    return subprocess.run([sys.executable, str(APPLIER), *map(str, args)], cwd=cwd,
                          text=True, capture_output=True)


class ApplyPatchesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name, text in {'llvm': 'old llvm\n', 'p2llvm': 'old p2\n', 'go-llvm': 'old go\n'}.items():
            d = self.root / name; d.mkdir()
            (d / 'file.txt').write_text(text)
            subprocess.run(['git', 'init', '-q'], cwd=d, check=True)
            subprocess.run(['git', 'add', '.'], cwd=d, check=True)
            subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'base'], cwd=d, check=True)
        patches = self.root / 'patches'; patches.mkdir()
        entries = []
        for name, before, after in [('llvm', 'old llvm\n', 'new llvm\n'), ('p2llvm', 'old p2\n', 'new p2\n'), ('go-llvm', 'old go\n', 'new go\n')]:
            d = self.root / name
            (d / 'file.txt').write_text(after)
            patch = subprocess.check_output(['git', 'diff', '--binary'], cwd=d)
            (d / 'file.txt').write_text(before)
            p = patches / f'{name}.patch'; p.write_bytes(patch)
            entries.append({
                'name': name, 'checkout': str(d), 'patch': str(p),
                'before_head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=d, text=True).strip(),
                'patch_sha256': hashlib.sha256(patch).hexdigest(),
                'files': [{'path': 'file.txt',
                           'before_sha256': hashlib.sha256(before.encode()).hexdigest(),
                           'after_sha256': hashlib.sha256(after.encode()).hexdigest()}],
            })
        self.manifest = self.root / 'manifest.json'; self.manifest.write_text(json.dumps({'patches': entries}))

    def tearDown(self): self.tmp.cleanup()

    def test_fresh_then_already_is_idempotent(self):
        first = run('--manifest', self.manifest, cwd=self.root); self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual([x['status'] for x in json.loads(first.stdout)['patches']], ['fresh'] * 3)
        second = run('--manifest', self.manifest, cwd=self.root); self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual([x['status'] for x in json.loads(second.stdout)['patches']], ['already'] * 3)

    def test_unexpected_content_rejected_without_partial_apply(self):
        (self.root/'p2llvm/file.txt').write_text('tampered\n')
        result = run('--manifest', self.manifest, cwd=self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root/'llvm/file.txt').read_text(), 'old llvm\n')
        self.assertIn('unexpected-content', result.stderr)

if __name__ == '__main__': unittest.main()
