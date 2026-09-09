#!/usr/bin/env python3
"""Validator tests use temporary copies of real recorded evidence, not HIL."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from verify_gate2e_record import verify

class Gate2EReplayTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(os.environ['P2_ROOT'])
        self.elf=Path(os.environ['P2_ELF'])
        self.tmp=tempfile.TemporaryDirectory(prefix='gate2e-replay-test-')
        self.record=Path(self.tmp.name)/'record'
        shutil.copytree(os.environ['P2_RECORD'],self.record)
    def tearDown(self): self.tmp.cleanup()
    def test_real_record(self): self.assertEqual(verify(self.root,self.record,self.elf)['raw_validated'],138)
    def test_duplicate_id(self):
        p=self.record/'vectors.json'; d=json.loads(p.read_text()); d[1]['id']=d[0]['id']; p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'duplicate IDs'): verify(self.root,self.record,self.elf)
    def test_corrupt_raw(self):
        p=self.record/'terminal.raw'; lines=p.read_text().splitlines()
        for i,line in enumerate(lines):
            if line.startswith('R E '):
                words=line.split(); words[3]=f'{int(words[3],16)^1:08x}'; lines[i]=' '.join(words); break
        else: self.fail('no real reply')
        p.write_text('\n'.join(lines)+'\n')
        with self.assertRaisesRegex(ValueError,'raw arithmetic'): verify(self.root,self.record,self.elf)
    def test_wrong_image(self):
        p=self.record/'hardware.json'; d=json.loads(p.read_text()); d['elf_sha256']='0'*64; p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'elf_sha256 mismatch'): verify(self.root,self.record,self.elf)
    def test_duplicate_boot(self):
        p=self.record/'terminal.raw'; p.write_bytes(p.read_bytes()+b'\r\nP2 PHASE2 IMPORT INIT\r\n')
        with self.assertRaisesRegex(ValueError,'boot order/count'): verify(self.root,self.record,self.elf)

if __name__=='__main__': unittest.main(verbosity=2)
