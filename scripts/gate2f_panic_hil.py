#!/usr/bin/env python3
"""RAM-only controlled bounds panic check; exact diagnostic required."""
import hashlib,json,re,sys,time
from datetime import datetime,timezone
from pathlib import Path
PANIC_LINE=re.compile(rb'(?m)^panic: runtime error: index out of range(?: \[[^\r\n]*\])?\r?$')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate_raw(raw):
 lines=[x.strip() for x in re.split(rb'[\r\n]+',raw) if x.strip()]
 try: armed=lines.index(b'P2 GO BOUNDS ARMED'); trigger=lines.index(b'P2 GO BOUNDS TRIGGER')
 except ValueError: return {"armed":False,"trigger_marker":False,"go_panic_marker":False,"forbidden_continuation":b'FORBIDDEN CONTINUATION' in raw}
 return {"armed":True,"trigger_marker":trigger>armed,"go_panic_marker":bool(PANIC_LINE.search(raw)),"forbidden_continuation":b'FORBIDDEN CONTINUATION' in raw}
def main():
 # Offline validation must not depend on the original project layout or HIL.
 # The archive includes hil.py beside this script; retain the historical live
 # project fallback without importing it when validate_raw() is used alone.
 ROOT=Path(__file__).resolve().parents[3]
 sys.path[:0]=[str(Path(__file__).resolve().parent),str(ROOT/'scripts')]
 from hil import Terminal,ProtocolError
 LOADER=ROOT/'.work/bin/loadp2';PROFILE=ROOT/'firmware/p2-edge-tcxo.json'
 elf=Path(sys.argv[1]);out=ROOT/'.work/phase2/hil'/('gate2f-panic-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'));out.mkdir(parents=True);cmd=[str(LOADER),'-p','/dev/ttyUSB0','-b','115200','-l','115200','-ZERO','-v','-t',str(elf)];(out/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');r={'status':'FAIL','elf_sha256':sha(elf),'loader_sha256':sha(LOADER),'profile_sha256':sha(PROFILE),'observation_seconds':4};t=None
 try:
  t=Terminal(cmd,out/'terminal.raw'); deadline=time.monotonic()+60
  while t.line(deadline).strip()!=b'P2 GO BOUNDS ARMED': pass
  t.send(b'X'); end=time.monotonic()+r['observation_seconds']
  # A normal quiet halt is expected. EOF/loader failure before the bounded
  # observation deadline is an error, never evidence of a panic.
  while time.monotonic()<end:
   try: t.line(end)
   except ProtocolError as e:
    if time.monotonic() < end-0.02: raise ProtocolError('premature terminal failure: '+str(e))
    break
  t.close();t=None;raw=(out/'terminal.raw').read_bytes();r.update(validate_raw(raw));r.update({'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw)})
  if not (r['armed'] and r['trigger_marker'] and r['go_panic_marker']) or r['forbidden_continuation']: raise ProtocolError('panic acceptance markers absent '+repr(r))
  r['status']='PASS';return 0
 except BaseException as e:r['error']=type(e).__name__+': '+str(e);return 1
 finally:
  if t:t.close()
  (out/'hardware.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__':raise SystemExit(main())
