#!/usr/bin/env python3
"""Capture and verify real P2 LLD-linked object provenance.

This deliberately asks the pinned linker to re-link the exact parsed command:
P2 R_P2_20/R_P2_AUG20/R_P2_32 relocation encoding is performed by that same
pinned LLD, rather than masking instruction words as a leaf-function checker
would.  The resulting ELF must be byte-identical to the supplied final ELF.
"""
import argparse, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALLOWED_RELOCS = {"R_P2_20", "R_P2_AUG20", "R_P2_32"}

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd, cwd=None): return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def link_command(log):
    # -x emits one complete ld.lld command; retain only the final one.
    lines = [line.strip() for line in Path(log).read_text(errors="replace").splitlines()
             if re.search(r"(?:^|/)ld\.lld(?:\s|$)", line)]
    if not lines: raise ValueError("no ld.lld command in build log")
    argv = shlex.split(lines[-1])
    if not argv or not argv[0].endswith("ld.lld"): raise ValueError("unparseable ld.lld command")
    return argv

def inputs(argv):
    # LLD's input objects are positional; options such as -L and -T take values.
    take = {"-L", "-T", "-o", "--sysroot", "--plugin-opt"}; out=[]; skip=False
    for arg in argv[1:]:
        if skip: skip=False; continue
        if arg in take: skip=True; continue
        if arg.startswith("-"): continue
        if arg.endswith((".o", ".a")): out.append(Path(arg))
    if not out: raise ValueError("no positional .o/.a link inputs")
    return out

def linker_scripts(argv):
    out=[]
    for i,arg in enumerate(argv[:-1]):
        if arg == '-T': out.append(Path(argv[i+1]))
    return out

def checked_copy(artifact, entry):
    # Exact recorded path only: never fall back to a matching basename.
    p=artifact/entry['portable_path']
    if not p.is_file(): raise ValueError('retained portable input missing: '+str(p))
    if p.stat().st_size != entry['bytes'] or digest(p) != entry['sha256']:
        raise ValueError('retained portable input identity mismatch: '+str(p))
    return p

def portable_replay(argv, artifact):
    meta=artifact/'metadata.corrected.json'
    if not meta.is_file(): raise ValueError('verify requires metadata.corrected.json with retained inputs')
    record=json.loads(meta.read_text())
    recorded_argv=record.get('parsed_link_command')
    # The caller supplies the pinned LLD path; it may differ after extraction.
    # Every recorded build argument after argv[0] must remain exact.
    if not isinstance(recorded_argv,list) or recorded_argv[1:] != argv[1:]:
        raise ValueError('build log link command differs from the recorded command')
    objmap={x['link_path']:x for x in record.get('linked_inputs',[])}
    scriptmap={x['link_path']:x for x in record.get('linker_scripts',[])}
    replay=list(argv)
    for i,arg in enumerate(replay):
        if arg in objmap: replay[i]=str(checked_copy(artifact,objmap[arg]))
    for i,arg in enumerate(replay):
        if arg == '-T' and i+1 < len(replay):
            original=replay[i+1]
            if original not in scriptmap: raise ValueError('recorded linker script is not retained: '+original)
            replay[i+1]=str(checked_copy(artifact,scriptmap[original]))
    # Every positional object and -T script must have an exact retained mapping.
    if any(str(p) not in objmap for p in inputs(argv)): raise ValueError('incomplete retained object mapping')
    if any(str(p) not in scriptmap for p in linker_scripts(argv)): raise ValueError('incomplete retained linker-script mapping')
    return replay, record

def relocations(readobj, obj):
    p=run([str(readobj),"--relocations",str(obj)])
    if p.returncode: raise ValueError("readobj failed for %s: %s"%(obj,p.stderr))
    got=set(re.findall(r"\bR_P2_[A-Z0-9_]+\b",p.stdout)); bad=sorted(got-ALLOWED_RELOCS)
    if bad: raise ValueError("unsupported P2 relocations in %s: %s"%(obj, bad))
    return sorted(got)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--build-log",required=True); ap.add_argument("--elf",required=True)
 ap.add_argument("--artifact-dir",required=True); ap.add_argument("--readobj",required=True); ap.add_argument("--lld",required=True); ap.add_argument("--mode",choices=("capture","verify"),default="capture")
 ns=ap.parse_args(); artifact=Path(ns.artifact_dir); elf=Path(ns.elf); argv=link_command(ns.build_log); argv[0]=str(Path(ns.lld).absolute()); objs=inputs(argv); scripts=linker_scripts(argv)
 if ns.mode == 'capture':
  missing=[str(p) for p in objs+scripts if not p.exists()]
  if missing: raise SystemExit("real linked inputs missing: "+", ".join(missing))
  replay=list(argv); record=None
 else:
  try: replay,record=portable_replay(argv,artifact)
  except ValueError as e: raise SystemExit(str(e))
  # Relocation inspection is performed on exactly the retained files replayed.
  objs=[Path(replay[argv.index(str(obj))]) for obj in objs]
 relocs={str(p): relocations(ns.readobj,p) for p in objs}
 outarg=argv.index("-o")+1 if "-o" in argv else None
 if outarg is None: raise SystemExit("link command has no -o")
 with tempfile.TemporaryDirectory(prefix="p2-provenance-") as td:
  rebuilt=Path(td)/"relinked.elf"; replay=list(replay); replay[outarg]=str(rebuilt)
  p=run(replay)
  if p.returncode: raise SystemExit("pinned LLD replay failed: "+p.stderr)
  if digest(rebuilt)!=digest(elf): raise SystemExit("relinked ELF differs from supplied ELF")
 copied=[]
 if ns.mode=="capture":
  target=artifact/"linked-inputs"; target.mkdir(parents=True,exist_ok=True)
  for n,obj in enumerate(objs):
   name=f"{n:02d}-{obj.name}"; dst=target/name; shutil.copyfile(obj,dst)
   copied.append({"link_path":str(obj),"portable_path":str(Path("linked-inputs")/name),"sha256":digest(obj),"bytes":obj.stat().st_size})
  copied_scripts=[]
  for n,script in enumerate(scripts):
   name=f"linker-script-{n:02d}-{script.name}"; dst=target/name; shutil.copyfile(script,dst)
   copied_scripts.append({"link_path":str(script),"portable_path":str(Path("linked-inputs")/name),"sha256":digest(script),"bytes":script.stat().st_size})
  # Corrected metadata never alters the historical metadata.json.
  record={"schema":"p2-link-provenance-v2","build_log":str(Path(ns.build_log)),"parsed_link_command":argv,"elf":str(elf),"elf_sha256":digest(elf),"relocation_types":relocs,"linked_inputs":copied,"linker_scripts":copied_scripts,"pinned_lld_replay":"byte-identical","limitations":"Static provenance only: it proves the retained inputs relink byte-identically with pinned LLD; it does not prove source-to-object compiler reproducibility."}
  (artifact/"metadata.corrected.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"status":"PASS","objects":[str(x) for x in objs],"relocations":relocs,"elf_sha256":digest(elf),"replay":"byte-identical"},sort_keys=True))
if __name__ == "__main__": main()
