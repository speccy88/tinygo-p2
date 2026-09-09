#!/usr/bin/env python3
"""Compute P2 HUB allocation from ELF PT_LOAD memory ranges, not .text alone."""
import argparse,json,re,subprocess
from pathlib import Path
def main():
 a=argparse.ArgumentParser();a.add_argument('--elf',required=True);a.add_argument('--readelf',default='readelf');a.add_argument('--out',required=True);n=a.parse_args()
 q=subprocess.run([n.readelf,'-W','-l',n.elf],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 loads=[]
 for line in q.stdout.splitlines():
  m=re.match(r'\s*LOAD\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)',line,re.I)
  if m:
   off,vaddr,paddr,filesz,memsz=(int(x,16) for x in m.groups());loads.append({'offset':off,'vaddr':vaddr,'paddr':paddr,'file_bytes':filesz,'memory_bytes':memsz,'end':vaddr+memsz})
 if not loads: raise SystemExit('no LOAD segments parsed')
 hub_limit=0x80000; actual=max(x['end'] for x in loads); filebacked=sum(x['file_bytes'] for x in loads)
 r={'schema':'p2-hub-accounting-v1','elf':n.elf,'load_segments':loads,'file_backed_load_bytes':filebacked,'maximum_loaded_or_reserved_hub_address':actual,'hub_address_limit':hub_limit,'remaining_unallocated_hub_bytes':hub_limit-actual,'bootstrap_layout':{'cog_reserved_bytes':'0x000-0x200','lut_reserved_bytes':'0x200-0xa00','hub_text_start':'0xa00'},'interpretation':'PT_LOAD MemSiz includes .bss/.heap/.stack reservations; maximum is the end-exclusive highest address, not ELF file size or .text.'}
 r['status']='PASS' if actual<=hub_limit else 'FAIL';Path(n.out).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
