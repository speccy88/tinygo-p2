#!/usr/bin/env python3
import hashlib, importlib.util, json, os, shlex, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
PHASE2=Path(os.environ.get('PHASE2_ROOT',Path(__file__).resolve().parents[1])).resolve()
BASELINE=Path(os.environ['P2_BASELINE_ROOT']).resolve()
ROOT=BASELINE
SCRIPTS=PHASE2/'scripts'
FINAL=PHASE2/'artifacts/gate2f-loader-trace-20260908T140446.301348854Z'
# This portable capture retains its own exact linker script and object copies.
# Do not regress to the earlier final-cli directory, which references a historical
# /work linker-script path and intentionally cannot be replayed stand-alone.
def load(name):
 # Helpers imported by the hardware script live with the extracted script, not
 # beneath the installed baseline's project-level scripts directory.
 sys.path.insert(0, str(SCRIPTS))
 s=importlib.util.spec_from_file_location(name,SCRIPTS/name);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class PanicAcceptanceTests(unittest.TestCase):
 def test_filename_word_is_not_panic(self):
  m=load('gate2f_panic_hil.py'); r=m.validate_raw(b'Loading p2panic.elf\r\nP2 GO BOUNDS ARMED\r\nP2 GO BOUNDS TRIGGER\r\n')
  self.assertFalse(r['go_panic_marker'])
  # A standalone offline import must work even without hil.py or a project root.
  with tempfile.TemporaryDirectory() as td:
   script=Path(td)/'panic.py'; shutil.copyfile(SCRIPTS/'gate2f_panic_hil.py',script)
   code="import runpy,sys; m=runpy.run_path(sys.argv[1]); assert not m['validate_raw'](b'Loading p2panic.elf')['go_panic_marker']"
   p=subprocess.run([sys.executable,'-I','-c',code,str(script)],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
 def test_order_and_exact_diagnostic_required(self):
  m=load('gate2f_panic_hil.py')
  self.assertFalse(m.validate_raw(b'P2 GO BOUNDS TRIGGER\npanic: runtime error: index out of range\nP2 GO BOUNDS ARMED\n')['trigger_marker'])
  self.assertTrue(m.validate_raw(b'P2 GO BOUNDS ARMED\r\nP2 GO BOUNDS TRIGGER\r\npanic: runtime error: index out of range\r\n')['go_panic_marker'])
class RestoreTrapTests(unittest.TestCase):
 def test_forced_failure_restores_isolated_source(self):
  script=SCRIPTS/'gate2f_mutation_build.sh'; src=PHASE2/'src/p2goapp'
  with tempfile.TemporaryDirectory() as td:
   app=Path(td)/'app'; shutil.copytree(src,app); before=(app/'core.go').read_bytes(); art=Path(td)/'art'
   p=subprocess.run(['sh',str(script)],env={**os.environ,'ROOT':str(ROOT),'APP':str(app),'ARTIFACT_ROOT':str(art),'TINYGO':'/bin/false'},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   self.assertNotEqual(p.returncode,0); self.assertEqual(before,(app/'core.go').read_bytes())
   records=list(art.glob('gate2f-mutation-*/source-restored.sha256')); self.assertEqual(len(records),1)
   self.assertEqual(records[0].read_text().split()[0],hashlib.sha256(before).hexdigest())
class ProvenanceTests(unittest.TestCase):
 def build_log(self, artifact, path):
  # The Git publication intentionally omits the historical absolute build log.
  # Reconstruct the exact retained linker invocation from corrected metadata so
  # these tests remain portable after extraction or a remote clone.
  record=json.loads((artifact/'metadata.corrected.json').read_text())
  argv=record['parsed_link_command']
  path.write_text(' '.join(shlex.quote(x) for x in argv)+'\n')
  return path
 def base(self, artifact, log):
  tool=SCRIPTS/'capture_link_provenance.py'
  return ['python3',str(tool),'--build-log',str(log),'--elf',str(artifact/'p2goapp-loader-trace.elf'),'--artifact-dir',str(artifact),'--readobj',str(ROOT/'.work/build/llvm/bin/llvm-readobj'),'--lld',str(ROOT/'.work/build/llvm/bin/ld.lld')]
 def test_real_relink_and_nonreloc_mutation_rejected(self):
  a=FINAL
  with tempfile.TemporaryDirectory() as td:
   td=Path(td); log=self.build_log(a,td/'build.log'); base=self.base(a,log)
   self.assertEqual(subprocess.run(base+['--mode','verify'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).returncode,0)
   altered=td/'main.o'; shutil.copyfile(a/'linked-inputs/00-main.o',altered); b=bytearray(altered.read_bytes()); b[0x100]^=1; altered.write_bytes(b)
   mutated_log=td/'mutated-build.log'; mutated_log.write_text(log.read_text().replace('/tmp/tinygo1578978653/main.o',str(altered)))
   bad=base.copy(); bad[bad.index('--build-log')+1]=str(mutated_log)
   self.assertNotEqual(subprocess.run(bad+['--mode','verify'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).returncode,0)
 def test_wrong_relocation_target_rejected_by_pinned_lld(self):
  a=FINAL
  with tempfile.TemporaryDirectory() as td:
   td=Path(td); log=self.build_log(a,td/'build.log'); base=self.base(a,log)
   wrong=td/'main.o'; data=(a/'linked-inputs/00-main.o').read_bytes(); self.assertEqual(data.count(b'raw_p2_uart_getc'),1); wrong.write_bytes(data.replace(b'raw_p2_uart_getc',b'bad_p2_uart_getc'))
   wrong_log=td/'wrong-build.log'; wrong_log.write_text(log.read_text().replace('/tmp/tinygo1578978653/main.o',str(wrong)))
   bad=base.copy(); bad[bad.index('--build-log')+1]=str(wrong_log)
   self.assertNotEqual(subprocess.run(bad+['--mode','verify'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).returncode,0)
if __name__=='__main__': unittest.main(verbosity=2)
