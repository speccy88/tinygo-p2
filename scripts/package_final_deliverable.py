#!/usr/bin/env python3
"""Construct the deliberately bounded final Phase 2 archive staging tree."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

project = Path(sys.argv[1]).resolve()
stage = Path(sys.argv[2]).resolve()
cache = Path(sys.argv[3]).resolve()
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir(parents=True)
phase2 = project / '.work/phase2'

def ignore(directory, names):
    blocked = {'.git', '__pycache__', 'llvm', 'cache'}
    # Do not package resource-header symlinks whose historical absolute targets
    # are outside an arbitrary extraction. The reproduction recipe uses the
    # installed baseline headers instead.
    return [name for name in names if name in blocked or name.endswith('.pyc') or (Path(directory) / name).is_symlink()]

def copy(source, target):
    if source.is_dir():
        shutil.copytree(source, target, ignore=ignore, symlinks=False)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

# Archive root is directly usable as P2 after extraction.
for name in ('artifacts', 'baseline', 'binding', 'hil', 'logs', 'out', 'patches',
             'reports', 'scripts', 'snapshots', 'tests', 'utilities'):
    copy(phase2 / name, stage / name)
copy(phase2 / 'patch-manifest.json', stage / 'patch-manifest.json')
for name in ('apply_phase2_patches.py', 'go-llvm', 'p2goapp', 'p2llvm', 'p2panic', 'tinygo'):
    copy(phase2 / 'src' / name, stage / 'src' / name)
# Preserve the real transport utility, not a stub or an absolute import path.
copy(project / 'scripts/hil.py', stage / 'scripts/hil.py')
# Context, parent fixtures/results, and immutable project-facing descriptions.
copy(cache, stage / 'parent-cache')
for name in ('README.md', 'AGENTS.md', 'CODEX_PROMPT.md', 'MANIFEST.sha256', 'sources.lock.json'):
    source = project / name
    if source.exists(): copy(source, stage / 'project' / name)

# Keep the archive explainable without shipping a recursive previous archive or SDK/cache.
(stage / 'ARCHIVE_SCOPE.md').write_text('''# Archive scope\n\nThis root is the extracted `P2` directory used by `reports/PHASE2_REPORT.md`.\nIt intentionally excludes `.work/phase2/src/llvm`, Go/SDK/build caches, all Git internals, recursive prior archives, and unrelated project files. The compact immutable Phase 1 archive is retained at `baseline/tinygo-p2-final-handoff-20260908.tar.gz`; its baseline hash is retained beside it. The bundled TinyGo CLI is dynamically dependent on the separately installed pinned Go/LLVM baseline described in the report.\n''')

# Reject common credential forms in textual package inputs before manifesting.
import re
hits=[]
patterns = {
    'private-key': re.compile(r'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----'),
    'github-token': re.compile(r'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}'),
    'aws-access-key': re.compile(r'AKIA[0-9A-Z]{16}'),
}
for p in stage.rglob('*'):
    if not p.is_file() or p.stat().st_size > 2_000_000: continue
    try: text=p.read_text(errors='ignore')
    except OSError: continue
    for label, pattern in patterns.items():
        if pattern.search(text): hits.append(f'{p.relative_to(stage)}:{label}')
if hits:
    raise SystemExit('possible secret marker(s): ' + ', '.join(hits))

entries=[]
for p in sorted(x for x in stage.rglob('*') if x.is_file()):
    rel=p.relative_to(stage).as_posix()
    entries.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")
(stage / 'MANIFEST.sha256').write_text('\n'.join(entries)+'\n')
print(json.dumps({'stage': str(stage), 'files': len(entries), 'bytes': sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())}, sort_keys=True))
