#!/usr/bin/env python3
"""Fresh RAM-only final Go-app challenge run with exact oracle validation."""
import argparse, hashlib, json, secrets, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from hil import ProtocolError, Terminal
MASK=0xffffffff
PHASE2=ROOT/'.work/phase2'; LOADER=ROOT/'.work/bin/loadp2'; PROFILE=ROOT/'firmware/p2-edge-tcxo.json'; PORT='/dev/ttyUSB0'
EDGES=[(0,0,0),(0xffffffff,1,15),(0x80000000,0x7fffffff,16),(0x7fffffff,0xffffffff,3),(19,0xdeadbeef,31),(0xffffffff,0xffffffff,0xffffffff),(0x13,0,1),(0xffffffed,4,2),(0x12345678,0x87654321,7),(0xaaaaaaaa,0x55555555,8)]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rol5(x): return ((x<<5)|(x>>27))&MASK
def oracle(a,b,limit,st):
 words=(0x13579bdf,0x2468ace0,0xf00dcafe,0x10203040); local=(a+words[(a^b)&3])&MASK; fold=st['fold']^st['seed']
 for i in range(4): fold=(((fold<<3)|(fold>>29))^words[(local+i)&3])&MASK
 signed_a=a if a<0x80000000 else a-0x100000000
 if signed_a < -19: local^=(-19)&MASK
 elif a > ((-19)&MASK): local=(local+b)&MASK
 else: local^=0xa5a5a5a5
 for i in range((limit&15)+1): local=rol5(local)^fold^i; local&=MASK; fold=(fold+words[(i+st['count'])&3])&MASK
 st['sum']=(st['sum']+local)&MASK; st['count']=(st['count']+1)&MASK; st['fold']=fold^local; st['seed']=(st['seed']+local+b+limit)&MASK
 return local^st['sum']^st['fold']
def request(v): return f"C {v['id']:08x} {v['a']:08x} {v['b']:08x} {v['n']:08x}\r".encode()
def parse(line):
 p=line.strip().split()
 if len(p)!=6 or p[:2]!=[b'R',b'E'] or any(len(x)!=8 or any(c not in b'0123456789abcdefABCDEF' for c in x) for x in p[2:]): raise ProtocolError('malformed canonical reply: '+repr(line))
 return [int(x,16) for x in p[2:]]
def getline(t,deadline):
 while True:
  x=t.line(deadline).strip()
  if x:return x
def unique_id(seen):
 while True:
  x=secrets.randbits(32)
  if x not in seen: seen.add(x); return x
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--elf',required=True); ap.add_argument('--label',required=True); a=ap.parse_args(); elf=Path(a.elf).resolve()
 if not elf.is_file(): raise SystemExit('missing ELF: '+str(elf))
 if not Path(PORT).exists() or list(Path('/dev').glob('ttyUSB*'))!=[Path(PORT)]: raise SystemExit('requires sole '+PORT)
 if shutil.which('lsof') and subprocess.run(['lsof','-t',PORT],capture_output=True,text=True).stdout.strip(): raise SystemExit('serial port already held')
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'); out=PHASE2/'hil'/('gate2f-'+a.label+'-'+stamp); out.mkdir(parents=True)
 command=[str(LOADER),'-p',PORT,'-b','115200','-l','115200','-ZERO','-v','-t',str(elf)]
 seen=set(); vectors=[{'id':unique_id(seen),'a':x,'b':y,'n':z} for x,y,z in EDGES]
 vectors += [{'id':unique_id(seen),'a':secrets.randbits(32),'b':secrets.randbits(32),'n':secrets.randbits(32)} for _ in range(128)]
 if len(vectors)!=138 or len(seen)!=138: raise SystemExit('unique-ID generator invariant failed')
 (out/'command.json').write_text(json.dumps(command,indent=2)+'\n'); (out/'vectors.json').write_text(json.dumps(vectors,indent=2)+'\n')
 result={'status':'FAIL','scope':'physical-P2-via-USB-serial','mode':'gate2f-fresh-RAM-only','label':a.label,'elf':str(elf),'elf_sha256':sha(elf),'loader_sha256':sha(LOADER),'profile_sha256':sha(PROFILE),'total':len(vectors),'unique_ids':len(seen),'passed':0,'malformed_passed':0}
 t=None
 try:
  t=Terminal(command,out/'terminal.raw'); expected=[b'P2 PHASE2 IMPORT INIT',b'P2 PHASE2 INIT',b'READY P2E 1']; boot=[]
  deadline=time.monotonic()+60
  for want in expected:
   while True:
    got=getline(t,deadline)
    if got==want: break
    if got in expected: raise ProtocolError('boot ordering mismatch: wanted '+repr(want)+' got '+repr(got))
   boot.append(got.decode())
  result['boot']=boot
  for bad in (b'?',b'C 00000000 00000000',b'C zzzzzzzz 00000000 00000000 00000000',b'X'*65):
   t.send(bad+b'\r'); got=getline(t,time.monotonic()+3)
   if got!=b'ERR INPUT': raise ProtocolError('malformed input response: '+repr(got))
   result['malformed_passed']+=1
  st={'sum':0,'count':0,'fold':0,'seed':0x91e10da5}
  with (out/'responses.jsonl').open('w') as f:
   for v in vectors:
    expected_reply=[v['id'],oracle(v['a'],v['b'],v['n'],st),st['sum'],st['count']]; t.send(request(v)); got=parse(getline(t,time.monotonic()+3)); r={'id':v['id'],'expected':expected_reply,'observed':got}; f.write(json.dumps(r,sort_keys=True)+'\n'); f.flush()
    if got!=expected_reply: raise ProtocolError('challenge mismatch: '+repr(r))
    result['passed']+=1
  result['status']='PASS'; return 0
 except BaseException as e: result['error']=type(e).__name__+': '+str(e); return 1
 finally:
  if t:t.close()
  (out/'hardware.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': raise SystemExit(main())
