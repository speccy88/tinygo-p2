"""Host/synthetic tests only. None of these establish P2 hardware execution."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from artifactcheck import CheckError, check_elf, check_ir
from hil import ProtocolError, exchange, make_vectors, oracle, verify_response
import project

IR='''; SYNTHETIC checker fixture, NOT TinyGo output.
target triple = "p2"
target datalayout = "e-p:32:32"
define i32 @p2_add(i32 %a, i32 %b) #0 {
 %x = add i32 %a, %b
 ret i32 %x
}
define i32 @p2_mix(i32 %a, i32 %b) #0 {
 %x = xor i32 %a, %b
 ret i32 %x
}
attributes #0 = { "no-jump-tables"="true" }
'''

def synthetic_elf(machine=300, exports=True, undefined=False, elf_type=1, oversized=False):
    # This fixture checks ELF parsing only; its text bytes are NOT P2 code.
    names=b'\0p2_add\0p2_mix\0'
    syms=bytes(16)
    if exports:
        syms+=struct.pack('<IIIBBH',1,0,4,0x12,0,0 if undefined else 1)
        syms+=struct.pack('<IIIBBH',8,4,4,0x12,0,1)
    code=b'NOT-CODE'
    offset=52+(32 if elf_type==2 else 0)
    codeoff=offset; offset+=len(code)
    stroff=offset; offset+=len(names)
    symoff=offset; offset+=len(syms)
    shoff=(offset+3)&~3
    sections=[(0,0,0,0,0,0,0,0,0,0),
              (0,1,6,0,codeoff,len(code),0,0,4,0),
              (0,3,0,0,stroff,len(names),0,0,1,0),
              (0,2,0,0,symoff,len(syms),2,1,4,16)]
    ident=b'\x7fELF\x01\x01\x01'+bytes(9)
    hdr=struct.pack('<16sHHIIIIIHHHHHH',ident,elf_type,machine,1,0,52 if elf_type==2 else 0,
                    shoff,0,52,32 if elf_type==2 else 0,1 if elf_type==2 else 0,40,4,0)
    body=code+names+syms+bytes(shoff-offset)+b''.join(struct.pack('<10I',*s) for s in sections)
    if elf_type==2:
        length=52+32+len(body)
        ph=struct.pack('<8I',1,0,0,0,length,0x7c001 if oversized else length,5,4)
        return hdr+ph+body
    return hdr+body

class ProtocolChecks(unittest.TestCase):
    def test_wrap(self): self.assertEqual(oracle(0xffffffff,1)[0],0)
    def test_zero(self): self.assertEqual(oracle(0,0),(0,0))
    def test_argument_order(self): self.assertNotEqual(oracle(7,3)[1],oracle(3,7)[1])
    def test_vectors(self):
        v=make_vectors(128)
        self.assertEqual(len(v),138)
        self.assertEqual(len({x['id'] for x in v}),138)
    def test_count_guard(self):
        with self.assertRaises(ValueError): make_vectors(-1)
    def test_response_accepts(self):
        v={'id':42,'sum':3,'mix':99}
        self.assertEqual(verify_response(b'R G 0000002a 00000003 00000063','G',v)['sum'],3)
    def test_wrong_mode(self):
        with self.assertRaises(ProtocolError): verify_response(b'R C 0000002a 00000003 00000063','G',{'id':42,'sum':3,'mix':99})
    def test_wrong_nonce(self):
        with self.assertRaises(ProtocolError): verify_response(b'R G 0000002b 00000003 00000063','G',{'id':42,'sum':3,'mix':99})
    def test_wrong_result(self):
        with self.assertRaises(ProtocolError): verify_response(b'R G 0000002a 00000004 00000063','G',{'id':42,'sum':3,'mix':99})
    def test_malformed(self):
        with self.assertRaises(ProtocolError): verify_response(b'PASS','G',{})

class IRChecks(unittest.TestCase):
    def test_fixture(self): self.assertEqual(check_ir(IR)['target'],'p2')
    def test_add_only_fixture(self):
        addition = re.sub(r'define i32 @p2_mix[^}]+}\n', '', IR)
        self.assertEqual(check_ir(addition,('p2_add',))['exports'],['p2_add'])
    def test_add_only_is_not_full_support(self):
        addition = re.sub(r'define i32 @p2_mix[^}]+}\n', '', IR)
        with self.assertRaises(CheckError): check_ir(addition)
    def test_arm_retarget_guard(self):
        with self.assertRaises(CheckError): check_ir(IR.replace('"p2"','"arm-none-eabi"'))
    def test_missing_export(self):
        with self.assertRaises(CheckError): check_ir(IR.replace('@p2_add','@other'))
    def test_hidden_parameter(self):
        with self.assertRaises(CheckError): check_ir(IR.replace('i32 %a, i32 %b','i32 %a, i32 %b, i8* %context'))
    def test_runtime_call(self):
        with self.assertRaises(CheckError): check_ir(IR+'declare void @runtime.alloc()\n')
    def test_fastcc(self):
        with self.assertRaises(CheckError): check_ir(IR.replace('define i32','define fastcc i32'))
    def test_no_jumptable_guard(self):
        with self.assertRaises(CheckError): check_ir(IR.replace('no-jump-tables','other'))

class ELFChecks(unittest.TestCase):
    def check(self, data, typ=1, exports=True):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'SYNTHETIC-NOT-CODE.o'; p.write_bytes(data)
            return check_elf(p,typ,exports)
    def test_valid_structure_only(self): self.assertEqual(self.check(synthetic_elf())['machine'],300)
    def test_wrong_arch(self):
        with self.assertRaises(CheckError): self.check(synthetic_elf(machine=62))
    def test_missing_exports(self):
        with self.assertRaises(CheckError): self.check(synthetic_elf(exports=False))
    def test_undefined(self):
        with self.assertRaises(CheckError): self.check(synthetic_elf(undefined=True))
    def test_truncated(self):
        with self.assertRaises(CheckError): self.check(synthetic_elf()[:60])
    def test_wrong_type(self):
        with self.assertRaises(CheckError): self.check(synthetic_elf(),2)
    def test_executable_structure(self): self.assertEqual(self.check(synthetic_elf(elf_type=2),2)['elf_type'],2)
    def test_hub_boundary(self):
        with self.assertRaises(CheckError): self.check(synthetic_elf(elf_type=2,oversized=True),2)

class WorkflowGuards(unittest.TestCase):
    def test_sha_pins(self):
        for name in ['tinygo','p2llvm','llvm','loadp2']:
            self.assertRegex(project.LOCK[name]['revision'],r'^[0-9a-f]{40}$')
    def test_ram_requires_opt_in(self):
        with self.assertRaises(project.BuildError): project.hil(argparse.Namespace(allow_ram_reset=False))
    def test_missing_probe_not_success(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(project,'OUT',Path(d)):
            with self.assertRaises(project.BuildError): project.validate_probe()
    def test_job_limit(self):
        with mock.patch.dict(os.environ,{'P2_JOBS':'32'}):
            with self.assertRaises(project.BuildError): project.jobs()
    def test_port_ambiguity(self):
        with mock.patch.object(project,'list_ports',return_value=['/dev/cu.usbserial1','/dev/cu.usbserial2']):
            with self.assertRaises(project.BuildError):
                project.hil(argparse.Namespace(allow_ram_reset=True,port='auto'))
    def test_run_log_stem_keeps_fractional_timestamp_and_returncode(self):
        class SuccessProc:
            def __init__(self, *args, **kwargs): self.stdout=io.StringIO('ok\n')
            def wait(self, timeout=None): return 0
        with tempfile.TemporaryDirectory() as d:
            work=Path(d)
            with mock.patch.object(project,'WORK',work), mock.patch.object(project,'stamp',return_value='20260908T100000.100001Z'), mock.patch.object(project.subprocess,'Popen',SuccessProc):
                project.run(['first'],name='first')
                project.run(['second'],name='second')
            first=work/'logs/20260908T100000.100001Z-first'
            second=work/'logs/20260908T100000.100001Z-second'
            self.assertEqual((first.with_name(first.name+'.log')).read_text(),'ok\n')
            self.assertEqual((second.with_name(second.name+'.log')).read_text(),'ok\n')
            self.assertEqual(json.loads(first.with_name(first.name+'.json').read_text())['returncode'],0)
            self.assertEqual(json.loads(second.with_name(second.name+'.json').read_text())['command'],['second'])
    def test_hil_failure_persists_artifact_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'root'; work=Path(d)/'work'; out=work/'out'; firmware=out/'firmware'
            (root/'firmware').mkdir(parents=True); firmware.mkdir(parents=True); (work/'bin').mkdir(parents=True)
            profile=root/'firmware/p2-edge-tcxo.json'; profile.write_text('{}')
            harness=root/'firmware/protocol.c'; harness.write_text('/* harness */')
            image=firmware/'c.elf'; image.write_bytes(b'ELF-for-mocked-check')
            loader=work/'bin/loadp2'; loader.write_bytes(b'loader')
            manifest={'mode':'c','elf':{'sha256':project.sha256(image)},'harness_sha256':project.sha256(harness),'profile_sha256':project.sha256(profile)}
            (firmware/'c.json').write_text(json.dumps(manifest))
            def fail_exchange(command, mode, vectors, directory):
                directory.mkdir(parents=True)
                (directory/'transport.json').write_text(json.dumps({'status':'FAIL','passed':0,'total':len(vectors),'error':'ProtocolError: expected failure'}))
                raise RuntimeError('expected failure')
            args=argparse.Namespace(allow_ram_reset=True,port='/dev/ttyUSB0',mode='c',random=0)
            with mock.patch.object(project,'ROOT',root), mock.patch.object(project,'WORK',work), mock.patch.object(project,'OUT',out), mock.patch.object(project,'list_ports',return_value=['/dev/ttyUSB0']), mock.patch.object(project,'check_elf',return_value={}), mock.patch.object(project,'exchange',side_effect=fail_exchange), mock.patch.object(project.shutil,'which',return_value=None), mock.patch.object(project,'stamp',return_value='failure'):
                with self.assertRaisesRegex(RuntimeError,'expected failure'): project.hil(args)
            report=json.loads((work/'hil/failure-c/hardware.json').read_text())
            self.assertEqual(report['status'],'FAIL'); self.assertEqual(report['mode'],'c')
            self.assertEqual(report['elf_sha256'],project.sha256(image)); self.assertEqual(report['loader_sha256'],project.sha256(loader))
            self.assertEqual(json.loads((work/'reports/baseline-hardware.json').read_text())['status'],'FAIL')

class CIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.base=Path(cls.temp.name)
        cls.cc=shutil.which('clang') or shutil.which('cc')
        if not cls.cc: raise unittest.SkipTest('host C compiler unavailable')
        cls.binary=cls.base/'host-C-baseline'
        subprocess.run([cls.cc,'-std=c11','-Wall','-Wextra','-Werror','-DHOST_TEST','-DBASELINE',
                        str(ROOT/'firmware/protocol.c'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_host_c_through_pty_138_challenges(self):
        result=exchange([str(self.binary)],'C',make_vectors(128),self.base/'pty-success',boot_timeout=3,response_timeout=1)
        self.assertEqual(result['status'],'PASS'); self.assertEqual(result['passed'],138)
        self.assertEqual(result['scope'],'transport-only')
    def test_c_cannot_pass_as_go(self):
        with self.assertRaises(ProtocolError):
            exchange([str(self.binary)],'G',make_vectors(0),self.base/'wrong-mode',boot_timeout=3,response_timeout=1)
        report=json.loads((self.base/'wrong-mode/transport.json').read_text())
        self.assertEqual(report['status'],'FAIL')
    def test_bad_input_and_overflow(self):
        output=subprocess.run([str(self.binary)],input=b'bad\r'+b'x'*100+b'\r?\r',capture_output=True,check=True).stdout
        self.assertIn(b'ERR INPUT',output); self.assertIn(b'ERR OVERFLOW',output)
        self.assertEqual(output.count(b'READY C 1'),2)
    def test_missing_go_object_fails_link(self):
        p=subprocess.run([self.cc,'-DHOST_TEST',str(ROOT/'firmware/protocol.c'),'-o',str(self.base/'must-not-link')],capture_output=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn(b'p2_add',p.stderr); self.assertIn(b'p2_mix',p.stderr)

    def test_p2_stdio_flag_access_is_excluded_from_host_build(self):
        source=(ROOT/'firmware/protocol.c').read_text()
        guarded=re.compile(r'#ifndef HOST_TEST\s+stdin->_flag &= ~_IOCOOKED;\s+#endif',re.S)
        self.assertRegex(source, guarded)

if __name__=='__main__': unittest.main(verbosity=2)
