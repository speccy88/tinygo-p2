#!/usr/bin/env python3
"""Independent Phase2 patch-applicator acceptance probes.

Uses real three patch bodies and preimage file bytes captured read-only from the
workspace's pinned source copies. Temporary synthetic Git histories test the
applicator, NOT upstream revision authenticity or a clean toolchain build.
Only disposable temporary repositories are mutated; never the working SDK.
Run: P2_PATCH_APPLIER=/absolute/path/apply_phase2_patches.py python3 this_file.py
Fixture JSON must be beside this file. Include both files with any report.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FIXTURES = json.loads((HERE / 'patch-review-fixtures.json').read_text())
APPLIER = Path(os.environ['P2_PATCH_APPLIER']).resolve()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(
        ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
         *args], cwd=root, stderr=subprocess.STDOUT, text=True).strip()


class RealPatchAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p2-parent-patch-review-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.entries = []
        assert len(FIXTURES) == 3
        for source in FIXTURES:
            repo = self.root / source['name']
            repo.mkdir()
            for rel, text in source['files'].items():
                path = repo / rel
                assert path.resolve().is_relative_to(repo.resolve())
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            git(repo, 'init', '-q')
            git(repo, 'add', '.')
            git(repo, '-c', 'user.name=Parent Review', '-c',
                'user.email=review@example.invalid', 'commit', '-qm', 'fixture')
            patch = self.root / (source['name'] + '.patch')
            patch.write_text(source['patch'])
            git(repo, 'apply', '--check', str(patch))
            git(repo, 'apply', str(patch))
            identities = []
            for rel, text in source['files'].items():
                identities.append({'path': rel,
                                   'before_sha256': digest(text.encode()),
                                   'after_sha256': digest((repo / rel).read_bytes())})
                (repo / rel).write_text(text)
            self.entries.append({'name': source['name'], 'checkout': str(repo),
                                 'patch': str(patch),
                                 'before_head': git(repo, 'rev-parse', 'HEAD'),
                                 'patch_sha256': digest(patch.read_bytes()),
                                 'files': identities})
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps({'schema': 1, 'patches': self.entries}))

    def invoke(self):
        return subprocess.run([sys.executable, str(APPLIER), '--manifest',
                               str(self.manifest)], cwd=self.root,
                              text=True, capture_output=True, timeout=20)

    def test_real_three_patches_fresh_and_idempotent(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual([p['status'] for p in json.loads(first.stdout)['patches']],
                         ['fresh'] * 3)
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual([p['status'] for p in json.loads(second.stdout)['patches']],
                         ['already'] * 3)

    def test_patch_bytes_must_match_declared_identity(self):
        entry = self.entries[0]
        patch = Path(entry['patch'])
        # A valid extra hunk must not be trusted merely because git can apply it.
        patch.write_text(patch.read_text() + '\ndiff --git a/UNEXPECTED b/UNEXPECTED\n'
                         'new file mode 100644\n--- /dev/null\n+++ b/UNEXPECTED\n'
                         '@@ -0,0 +1 @@\n+must never be written\n')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0,
                            'Accepted changed patch bytes and undeclared extra file')
        self.assertFalse((Path(entry['checkout']) / 'UNEXPECTED').exists())
        for item in self.entries:
            self.assertEqual(git(Path(item['checkout']), 'diff', 'HEAD'), '')

    def test_preimage_drift_outside_hunk_is_rejected_atomically(self):
        entry = self.entries[2]
        rel = entry['files'][0]['path']
        path = Path(entry['checkout']) / rel
        changed = b'// Intentional unrelated preimage drift.\n' + path.read_bytes()
        path.write_bytes(changed)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0,
                            'Accepted a nonmatching intended-file preimage')
        self.assertEqual(path.read_bytes(), changed)
        for item in self.entries[:2]:
            self.assertEqual(git(Path(item['checkout']), 'diff', 'HEAD'), '')

    def test_wrong_revision_is_rejected_before_any_write(self):
        self.entries[2]['before_head'] = '0' * 40
        self.manifest.write_text(json.dumps({'schema': 1, 'patches': self.entries}))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        for item in self.entries:
            self.assertEqual(git(Path(item['checkout']), 'diff', 'HEAD'), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
