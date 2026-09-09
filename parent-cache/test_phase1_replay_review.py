#!/usr/bin/env python3
"""Review copied Phase1 replay utility using immutable real archived evidence.

These are OFFLINE validator tests, never fresh hardware evidence. Each negative
case alters only a disposable test copy. Set P2_REPLAY_UTILITY and
P2_PHASE1_ARCHIVE to their absolute paths. Python standard library only.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

UTILITY = Path(os.environ['P2_REPLAY_UTILITY']).resolve()
ARCHIVE = Path(os.environ['P2_PHASE1_ARCHIVE']).resolve()


class ReplayAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='p2-replay-source-')
        cls.base = Path(cls.tmp.name)
        with tarfile.open(ARCHIVE) as archive:
            for member in archive:
                parts = Path(member.name).parts
                if not member.isfile() or '.work' not in parts:
                    continue
                pos = parts.index('.work')
                if parts[pos:pos + 2] != ('.work', 'hil'):
                    continue
                target = cls.base.joinpath(*parts[pos:])
                if not target.resolve().is_relative_to(cls.base):
                    raise ValueError('Unsafe archive path')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
        if not list((cls.base / '.work/hil').glob('*/transport.json')):
            raise ValueError('No archived hardware records found')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p2-replay-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'fixture'
        shutil.copytree(self.base, self.root)

    def invoke(self):
        return subprocess.run([sys.executable, str(UTILITY), str(self.root),
                               '--require-full'], text=True, capture_output=True,
                              timeout=20)

    def go_run(self):
        for path in (self.root / '.work/hil').glob('*/transport.json'):
            data = json.loads(path.read_text())
            if data['status'] == 'PASS' and data['expected_mode'] == 'G':
                return path.parent
        raise AssertionError('No genuine archived passing Go record')

    def test_immutable_real_archive_passes(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['go_passes'], 7)
        self.assertGreaterEqual(data['c_passes'], 1)
        self.assertTrue(all(data['checks'].values()))

    def test_missing_image_loader_profile_identities_are_rejected(self):
        changed = 0
        for path in (self.root / '.work/hil').glob('*/hardware.json'):
            data = json.loads(path.read_text())
            for key in ('elf_sha256', 'loader_sha256', 'profile_sha256'):
                data.pop(key, None)
            path.write_text(json.dumps(data))
            changed += 1
        self.assertGreater(changed, 0)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0,
                            'Missing identities incorrectly satisfy shared-image checks')

    def test_corrupted_raw_arithmetic_is_rejected(self):
        path = self.go_run() / 'terminal.raw'
        lines = path.read_bytes().splitlines(keepends=True)
        for i, line in enumerate(lines):
            fields = line.split()
            if len(fields) == 5 and fields[:2] == [b'R', b'G']:
                fields[3] = f'{int(fields[3], 16) ^ 1:08x}'.encode()
                lines[i] = b' '.join(fields) + b'\r\n'
                break
        else:
            self.fail('No real Go raw response found')
        path.write_bytes(b''.join(lines))
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_forbidden_loader_flag_is_rejected(self):
        path = self.go_run() / 'command.json'
        command = json.loads(path.read_text())
        command.insert(-1, '-9')
        path.write_text(json.dumps(command))
        self.assertNotEqual(self.invoke().returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
