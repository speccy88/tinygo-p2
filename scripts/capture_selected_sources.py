#!/usr/bin/env python3
"""Record Go's actual dependency selection and every selected source hash."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--go',required=True);p.add_argument('--dir',required=True);p.add_argument('--out',required=True);p.add_argument('--tags',default='p2,baremetal,scheduler.none,gc.none');a=p.parse_args();a.go=str(Path(a.go).resolve()); a.dir=str(Path(a.dir).resolve())
 env={**os.environ,'GOOS':'linux','GOARCH':'arm','CGO_ENABLED':'0'}
 q=subprocess.run([a.go,'list','-deps','-json','-tags='+a.tags,'.'],cwd=a.dir,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if q.returncode: raise SystemExit(q.stderr)
 dec=json.JSONDecoder(); i=0; packages=[]; foreign=[]
 while i<len(q.stdout):
  while i<len(q.stdout) and q.stdout[i].isspace(): i+=1
  if i>=len(q.stdout): break
  x,n=dec.raw_decode(q.stdout,i);i=n; directory=Path(x['Dir']); names=[]
  for field in ('GoFiles','CgoFiles','CFiles','SFiles','HFiles','SysoFiles'):
   for name in x.get(field,[]):
    fp=directory/name
    if not fp.exists(): raise SystemExit('selected source missing: '+str(fp))
    entry={'field':field,'path':str(fp),'sha256':h(fp),'bytes':fp.stat().st_size};names.append(entry)
    if field=='SFiles' and any(z in fp.name.lower() for z in ('arm','aarch','thumb')): foreign.append(entry)
  packages.append({'import_path':x.get('ImportPath'),'dir':str(directory),'root':x.get('Root'),'files':names})
 r={'schema':'p2-selected-go-sources-v1','go_command':[a.go,'list','-deps','-json','-tags='+a.tags,'.'],'env':{'GOOS':'linux','GOARCH':'arm','CGO_ENABLED':'0'},'packages':packages,'selected_file_count':sum(len(x['files']) for x in packages),'foreign_isa_assembly_selected':foreign,'limitations':'This records Go package selection for the P2 target surrogate (GOARCH=arm). It does not prove TinyGo internal loader selection beyond its matching build tags; ELF/object provenance is recorded separately.'}
 Path(a.out).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'packages':len(packages),'files':r['selected_file_count'],'foreign_asm':len(foreign),'status':'PASS' if not foreign else 'FAIL'}))
if __name__=='__main__':main()
