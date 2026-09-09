#!/usr/bin/env python3
import hashlib,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT/'.work/phase2/scripts')); sys.path.insert(0,str(ROOT/'scripts'))
from gate2f_hil import oracle,parse,getline
from hil import Terminal,ProtocolError
LOADER=ROOT/'.work/bin/loadp2'; PROFILE=ROOT/'firmware/p2-edge-tcxo.json'; PORT='/dev/ttyUSB0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if len(sys.argv)!=2:raise SystemExit('usage: gate2f_mutation_hil.py ELF')
 elf=Path(sys.argv[1]); out=ROOT/'.work/phase2/hil'/('gate2f-mutation-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'));out.mkdir(parents=True)
 cmd=[str(LOADER),'-p',PORT,'-b','115200','-l','115200','-ZERO','-v','-t',str(elf)];(out/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
 r={'status':'FAIL','elf_sha256':sha(elf),'loader_sha256':sha(LOADER),'profile_sha256':sha(PROFILE)};t=None
 try:
  t=Terminal(cmd,out/'terminal.raw'); expected=[b'P2 PHASE2 IMPORT INIT',b'P2 PHASE2 INIT',b'READY P2E 1'];boot=[];deadline=time.monotonic()+60
  for want in expected:
   while True:
    x=getline(t,deadline)
    if x==want:break
    if x in expected:raise ProtocolError('boot order '+repr(x))
   boot.append(x.decode())
  v={'id':0x51a0f00d,'a':0x12345678,'b':0x87654321,'n':7};st={'sum':0,'count':0,'fold':0,'seed':0x91e10da5};normal=oracle(v['a'],v['b'],v['n'],st);predicted=normal^1;want=[v['id'],predicted,st['sum'],st['count']]
  t.send(f"C {v['id']:08x} {v['a']:08x} {v['b']:08x} {v['n']:08x}\r".encode());got=parse(getline(t,time.monotonic()+3));r.update({'boot':boot,'vector':v,'normal_expected':[v['id'],normal,st['sum'],st['count']],'predicted_mutated':want,'observed':got,'normal_validation_failed':got != [v['id'],normal,st['sum'],st['count']]})
  if got!=want or not r['normal_validation_failed']:raise ProtocolError('mutation prediction failed '+repr(r))
  r['status']='PASS';return 0
 except BaseException as e:r['error']=type(e).__name__+': '+str(e);return 1
 finally:
  if t:t.close()
  (out/'hardware.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__':raise SystemExit(main())
