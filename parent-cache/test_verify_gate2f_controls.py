#!/usr/bin/env python3
"""Fault-injection tests alter temporary copies of real control evidence only."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from verify_gate2f_controls import verify

class ControlsTests(unittest.TestCase):
    def setUp(self):
        self.real=Path(os.environ['P2_ROOT']);self.tmp=tempfile.TemporaryDirectory(prefix='p2-control-fixture-');self.root=Path(self.tmp.name)
        paths=['scripts','.work/bin/loadp2','firmware/p2-edge-tcxo.json','.work/phase2/scripts/gate2e_hil.py','.work/phase2/src/p2goapp/core.go']
        self.mut='.work/phase2/artifacts/gate2f-mutation-20260908T131809.889528543Z'
        self.restore='.work/phase2/artifacts/gate2f-restored-20260908T131856.889558316Z'
        self.mr='.work/phase2/hil/gate2f-mutation-20260908T131831.929435Z'
        self.pr='.work/phase2/hil/gate2f-panic-20260908T132003.741335Z'
        paths += [self.mut,self.restore,self.mr,self.pr,'.work/phase2/artifacts/gate2f-panic-20260908T131933.458767181Z','.work/phase2/artifacts/gate2f-final-cli-20260908T131540.392502595Z/p2goapp-final.elf']
        for rel in paths:
            src=self.real/rel;dst=self.root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            if src.is_dir(): shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__'))
            else: shutil.copy2(src,dst)
    def tearDown(self): self.tmp.cleanup()
    def test_real_controls(self): self.assertEqual(verify(self.root)['status'],'PASS')
    def test_wrong_mutation(self):
        p=self.root/self.mut/'core-mutated.go';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'exact single'):verify(self.root)
    def test_unrestored_source(self):
        p=self.root/'.work/phase2/src/p2goapp/core.go';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'not restored'):verify(self.root)
    def test_filename_panic_is_not_diagnostic(self):
        p=self.root/self.pr/'terminal.raw';data=p.read_bytes();self.assertIn(b'p2panic.elf',data)
        p.write_bytes(data.replace(b'panic: runtime error: index out of range',b'no target diagnostic'))
        with self.assertRaisesRegex(ValueError,'actual panic diagnostic'):verify(self.root)
    def test_normal_result_cannot_pass_mutation(self):
        hw=json.loads((self.root/self.mr/'hardware.json').read_text())
        p=self.root/self.mr/'terminal.raw';lines=p.read_text().splitlines()
        for i,line in enumerate(lines):
            if line.startswith('R E '): lines[i]='R E '+' '.join(f'{v:08x}' for v in hw['normal_expected'])
        p.write_text('\n'.join(lines)+'\n')
        with self.assertRaisesRegex(ValueError,'predicted XOR1'):verify(self.root)

if __name__=='__main__':unittest.main(verbosity=2)
