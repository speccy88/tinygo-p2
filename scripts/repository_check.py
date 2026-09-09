#!/usr/bin/env python3
"""Offline publication checks; never opens hardware or mutates the SDK baseline.

Requires Python 3.11+ and the established pinned Linux SDK. Generated outputs and
full logs are written outside Git. Historical large fixtures come only from the
exact sealed release archive; project source comes only from this repository.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

CANONICAL = '132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8'
SEALED = 'f1da3d3a31090ecad29d17691d21fab095321584c7ce83cce9b8d07064130f80'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    data = json.loads((root / 'provenance/source-inventory.json').read_text())
    for row in data['files']:
        path = root / row['path']
        if not path.is_file() or path.is_symlink() or sha(path) != row['sha256']:
            raise ValueError('source identity mismatch: ' + row['path'])
    return len(data['files'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--baseline-root', type=Path)
    parser.add_argument('--log-dir', type=Path)
    parser.add_argument('--inventory-only', action='store_true')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    count = inventory(root)
    if args.inventory_only:
        print(json.dumps({'passed': True, 'source_files': count}))
        return 0
    if not all((args.archive, args.baseline_root, args.log_dir)):
        parser.error('--archive, --baseline-root and --log-dir are required for tests')
    if os.getuid() != 10000 or os.getgid() != 10000:
        raise SystemExit('run as 10000:10000 in the established propeller2 container')
    archive = args.archive.resolve()
    baseline = args.baseline_root.resolve()
    logs = args.log_dir.resolve()
    logs.mkdir(parents=True, exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix='p2-repository-check-'))
    work, sealed, replay, sdk = [scratch / n for n in ('source', 'sealed', 'phase1-replay', 'sdk-inputs')]
    receipt = {'passed': False, 'source_root': str(root), 'source_files': count,
               'started_at': time.time(), 'scratch': str(scratch), 'commands': [],
               'scope': 'offline source tests and clean CLI/application rebuild; no new HIL',
               'archive': str(archive), 'archive_sha256': sha(archive)}
    try:
        if receipt['archive_sha256'] != SEALED:
            raise ValueError('wrong sealed Phase 2 archive')
        spec = importlib.util.spec_from_file_location('archived_verifier', root / 'scripts/verify_extracted_archive.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        sealed.mkdir()
        receipt['sealed_inventory'] = verifier.extract(archive, sealed, manifest=True)
        # Copy repository source, not archived source. Excluded historical fixtures
        # are restored only into this disposable copy, never into the Git index.
        shutil.copytree(root, work, ignore=shutil.ignore_patterns('.git', '__pycache__', '.work'))
        for rel in ('artifacts',):
            for source in (sealed / rel).rglob('*'):
                if source.is_file() and not (work / source.relative_to(sealed)).exists():
                    dest = work / source.relative_to(sealed)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
        inventory(work)
        replay.mkdir()
        verifier.extract(work / 'baseline/tinygo-p2-final-handoff-20260908.tar.gz', replay)
        # Confirm Phase 1 tests actually use the same browsable imported code.
        data = json.loads((work / 'provenance/source-inventory.json').read_text())
        for row in data['files']:
            if row['archive'] == 'phase1' and sha(replay / row['member']) != row['sha256']:
                raise ValueError('Phase 1 replay source differs from repository')
        for rel in ('scripts', 'src/p2goapp', 'artifacts', 'hil'):
            shutil.copytree(work / rel, replay / '.work/phase2' / rel)
        # Static installed SDK trees are read as inputs only. Module caches are
        # copied, so Go's locks/download bookkeeping cannot touch the original.
        (sdk / '.work/phase2/src').mkdir(parents=True)
        for rel in ('.work/toolchains', '.work/build', '.work/phase2/src/llvm'):
            (sdk / rel).symlink_to(baseline / rel, target_is_directory=True)
        shutil.copytree(baseline / '.work/phase2/cache/go-mod', sdk / '.work/phase2/cache/go-mod')
        # The controlled binding ZIP belongs to the Phase 1 module-download cache,
        # not necessarily the Phase 2 warm module tree. Copy only that pinned input.
        ziprel = Path('cache/download/tinygo.org/x/go-llvm/@v/v0.0.0-20220420140351-512c94c1e71f.zip')
        targetzip = sdk / '.work/phase2/cache/go-mod' / ziprel
        if not targetzip.is_file():
            sourcezip = baseline / '.work/cache/go-mod' / ziprel
            targetzip.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sourcezip, targetzip)
        (sdk / '.work/cache').mkdir()
        (sdk / '.work/cache/go-mod').symlink_to(sdk / '.work/phase2/cache/go-mod', target_is_directory=True)
        go = sdk / '.work/toolchains/go1.18.10/bin/go'
        env = dict(os.environ, PHASE2_ROOT=str(work), P2_BASELINE_ROOT=str(sdk),
                   BASELINE_ROOT=str(sdk), P2_ROOT=str(work), OUT_ELF=str(scratch / 'fresh-final.elf'),
                   GOROOT=str(go.parent.parent), PATH=str(go.parent) + ':' + os.environ['PATH'],
                   GOWORK='off', GOPROXY='off', GOSUMDB='off', GOFLAGS='-mod=readonly',
                   GOCACHE=str(scratch / 'test-go-cache'), PYTHONDONTWRITEBYTECODE='1')
        receipt['environment'] = {k: env[k] for k in ('PHASE2_ROOT', 'P2_BASELINE_ROOT', 'BASELINE_ROOT', 'P2_ROOT', 'OUT_ELF', 'GOROOT', 'PATH', 'GOWORK', 'GOPROXY', 'GOSUMDB', 'GOFLAGS', 'GOCACHE')}

        def run(name, argv, cwd=work, overrides=None, expected=None):
            path = logs / (name + '.log')
            with path.open('w') as stream:
                result = subprocess.run(list(map(str, argv)), cwd=cwd, env=dict(env, **(overrides or {})),
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=540)
            text = path.read_text(errors='replace')
            row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
                   'returncode': result.returncode, 'log': str(path), 'log_sha256': sha(path)}
            if expected is not None:
                counts = re.findall(r'Ran (\d+) tests?', text)
                row.update(expected_tests=expected, tests=int(counts[-1]) if counts else 0)
            receipt['commands'].append(row)
            print(json.dumps(row), flush=True)
            if result.returncode or (expected is not None and row['tests'] != expected):
                raise RuntimeError(name + ' failed; see ' + str(path))

        # Portable controlled restore is exercised before the regular tests/build.
        upstream = sdk / '.work/cache/go-mod/cache/download/tinygo.org/x/go-llvm/@v/v0.0.0-20220420140351-512c94c1e71f.zip'
        run('controlled-binding-restore', ['python3', work / 'binding/restore_go_llvm.py',
            '--bundle', work / 'binding/go-llvm-fc868cbb.bundle', '--upstream-zip', upstream,
            '--upstream-manifest', work / 'binding/upstream-go-llvm-v0.0.0-20220420140351-512c94c1e71f-zip-manifest.json',
            '--binding-manifest', work / 'patch-manifest.json', '--compat-patch', work / 'patches/01-go-llvm-llvm14dev.patch',
            '--destination', scratch / 'cold-restored-binding'])
        for name, rel, total in [('restore-guard', 'tests/test_restore_go_llvm.py', 4),
                                 ('patch-guard', 'tests/test_apply_phase2_patches.py', 2),
                                 ('review-utilities', 'scripts/test_phase2_review_utilities.py', 5)]:
            run(name, ['python3', rel], expected=total)
        final = replay / '.work/phase2/artifacts/gate2f-final-cli-20260908T131540.392502595Z/p2goapp-final.elf'
        records = sorted((replay / '.work/phase2/hil').glob('gate2f-final-[123]-*'))
        if len(records) != 3 or len({sha(p / 'vectors.json') for p in records}) != 3:
            raise ValueError('missing or nondistinct recorded physical evidence')
        penv = {'P2_ROOT': str(replay), 'P2_ELF': str(final), 'P2_RECORD': str(records[0])}
        for name in ('test_verify_gate2e_record', 'test_verify_gate2f_controls'):
            run(name, ['python3', work / ('parent-cache/' + name + '.py')], overrides=penv, expected=5)
        for i, record in enumerate(records, 1):
            run('record-replay-' + str(i), ['python3', work / 'parent-cache/verify_gate2e_record.py',
                '--root', replay, '--record', record, '--elf', final])
        run('phase1-host-regression', ['python3', 'scripts/host_check.py'], cwd=replay, expected=39)
        run('go-app-tests', [go, 'test', '-count=1', './...'], cwd=work / 'src/p2goapp')
        if not args.skip_build:
            run('fresh-cli-and-app', ['sh', 'scripts/reproduce_from_extraction.sh'])
            receipt['elf_sha256'] = sha(scratch / 'fresh-final.elf')
            receipt['cli_sha256'] = sha(work / 'src/tinygo/build/tinygo')
            receipt['cli_version'] = subprocess.check_output([str(work / 'src/tinygo/build/tinygo'), 'version'], text=True,
                env=dict(env, LD_LIBRARY_PATH=str(sdk / '.work/build/llvm/lib'))).strip()
            if receipt['elf_sha256'] != CANONICAL:
                raise ValueError('rebuilt ELF is not the hardware-proven image')
            if not all(v in receipt['cli_version'] for v in ('0.23.0', '1.18.10', '14.0.0git')):
                raise ValueError('wrong pinned toolchain version')
        inventory(root)
        inventory(work)
        if sha(archive) != SEALED:
            raise ValueError('sealed archive changed')
        receipt['passed'] = True
    except Exception as exc:
        receipt['error'] = str(exc)
    receipt['finished_at'] = time.time()
    (logs / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('sealed_inventory', 'commands', 'environment')}, indent=2))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
