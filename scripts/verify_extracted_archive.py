#!/usr/bin/env python3
"""Offline archive/test/rebuild runner; uses only an installed pinned SDK.

Run inside the established propeller2 container as 10000:10000. Historical
parent validators get a disposable project-shaped copy of archived inputs,
not a fallback to the installed application's sources. Never opens serial.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import time

CANONICAL = '132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def extract(archive, root, manifest=False):
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        names = set()
        for member in members:
            p = PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or not (member.isfile() or member.isdir()):
                raise ValueError('unsafe archive member: ' + member.name)
            if str(p) in names:
                raise ValueError('duplicate archive path: ' + member.name)
            names.add(str(p))
        tf.extractall(root, filter='data')
    files = sorted(str(PurePosixPath(m.name)) for m in members if m.isfile())
    expected = {}
    if manifest:
        for line in (root / 'MANIFEST.sha256').read_text().splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
            if not match or match[2] in expected:
                raise ValueError('malformed/duplicate manifest line')
            digest, name = match.groups()
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or str(p) != name:
                raise ValueError('unsafe manifest path')
            expected[name] = digest
        if list(expected) not in (sorted(expected), [str(p) for p in sorted(map(PurePosixPath, expected))]):
            raise ValueError('unsorted manifest')
        if set(expected) != set(files) - {'MANIFEST.sha256'}:
            raise ValueError('incomplete manifest')
        for name, digest in expected.items():
            if sha(root / name) != digest:
                raise ValueError('hash mismatch: ' + name)
    return {'members': len(members), 'regular_files': len(files),
            'manifest_files': len(expected), 'paths': files,
            'uncompressed_bytes': sum(m.size for m in members)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--baseline-root', type=Path, required=True)
    parser.add_argument('--log-dir', type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() != 10000 or os.getgid() != 10000:
        raise SystemExit('must run as 10000:10000 in the established container')
    archive, base, logs = args.archive.resolve(), args.baseline_root.resolve(), args.log_dir.resolve()
    logs.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='p2-archive-check-'))
    replay = Path(tempfile.mkdtemp(prefix='p2-archived-parent-'))
    receipt = {'passed': False, 'started_at': time.time(), 'archive': str(archive),
               'archive_sha256': sha(archive), 'archive_bytes': archive.stat().st_size,
               'extraction': str(root), 'parent_replay': str(replay), 'commands': [],
               'scope': 'offline tests and real CLI/application rebuild; no hardware execution'}
    try:
        receipt['inventory'] = extract(archive, root, manifest=True)
        phase1 = root / 'baseline/tinygo-p2-final-handoff-20260908.tar.gz'
        receipt['phase1_archive_sha256'] = sha(phase1)
        extract(phase1, replay)
        # The unmodified historical verifiers require a project-shaped root.
        for rel in ('scripts', 'src/p2goapp', 'artifacts', 'hil'):
            shutil.copytree(root / rel, replay / '.work/phase2' / rel)
        go = base / '.work/toolchains/go1.18.10/bin/go'
        env = dict(os.environ, PHASE2_ROOT=str(root), P2_BASELINE_ROOT=str(base),
                   BASELINE_ROOT=str(base), P2_ROOT=str(root), OUT_ELF=str(root / 'fresh-final.elf'),
                   GOROOT=str(go.parent.parent), PATH=str(go.parent) + ':' + os.environ['PATH'],
                   GOWORK='off', GOPROXY='off', GOSUMDB='off', GOFLAGS='-mod=readonly',
                   GOCACHE=str(root / 'test-go-cache'), PYTHONDONTWRITEBYTECODE='1')
        def run(name, argv, cwd=root, overrides=None, count=None):
            log = logs / (name + '.log')
            command_env = dict(env, **(overrides or {}))
            with log.open('w') as out:
                result = subprocess.run(argv, cwd=cwd, env=command_env, stdout=out,
                                        stderr=subprocess.STDOUT, timeout=540)
            text = log.read_text(errors='replace')
            row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
                   'returncode': result.returncode, 'log': str(log), 'log_sha256': sha(log)}
            if count is not None:
                counts = re.findall(r'Ran (\d+) tests?', text)
                row['tests'] = int(counts[-1]) if counts else 0
                row['expected_tests'] = count
            receipt['commands'].append(row)
            print(json.dumps(row), flush=True)
            if result.returncode or (count is not None and row['tests'] != count):
                print(text[-8000:], flush=True)
                return False
            return True
        receipt['environment'] = {k: env[k] for k in ('PHASE2_ROOT', 'P2_BASELINE_ROOT', 'BASELINE_ROOT',
            'P2_ROOT', 'OUT_ELF', 'GOROOT', 'PATH', 'GOWORK', 'GOPROXY', 'GOSUMDB', 'GOFLAGS', 'GOCACHE')}
        passed = []
        passed.append(run('restore-guard', ['python3', 'tests/test_restore_go_llvm.py'], count=4))
        passed.append(run('patch-guard', ['python3', 'tests/test_apply_phase2_patches.py'], count=2))
        passed.append(run('review-utilities', ['python3', 'scripts/test_phase2_review_utilities.py'], count=5))
        final = replay / '.work/phase2/artifacts/gate2f-final-cli-20260908T131540.392502595Z/p2goapp-final.elf'
        records = sorted((replay / '.work/phase2/hil').glob('gate2f-final-[123]-*'))
        if len(records) != 3 or len({sha(p / 'vectors.json') for p in records}) != 3:
            raise ValueError('missing or nondistinct final physical records')
        parent_env = {'P2_ROOT': str(replay), 'P2_ELF': str(final), 'P2_RECORD': str(records[0])}
        for name in ('test_verify_gate2e_record.py', 'test_verify_gate2f_controls.py'):
            passed.append(run(name.removesuffix('.py'), ['python3', str(root / 'parent-cache' / name)],
                              overrides=parent_env, count=5))
        for index, record in enumerate(records, 1):
            passed.append(run('physical-record-replay-' + str(index),
                              ['python3', str(root / 'parent-cache/verify_gate2e_record.py'),
                               '--root', str(replay), '--record', str(record), '--elf', str(final)]))
        passed.append(run('phase1-host-regression', ['python3', 'scripts/host_check.py'], cwd=replay, count=39))
        passed.append(run('go-app-tests', [str(go), 'test', '-count=1', './...'], cwd=root / 'src/p2goapp'))
        passed.append(run('fresh-cli-and-app', ['sh', 'scripts/reproduce_from_extraction.sh']))
        if not all(passed):
            raise RuntimeError('one or more extracted acceptance commands failed')
        cli = root / 'src/tinygo/build/tinygo'
        version = subprocess.check_output([str(cli), 'version'], text=True,
            env=dict(env, LD_LIBRARY_PATH=str(base / '.work/build/llvm/lib'))).strip()
        receipt.update(cli_version=version, cli_sha256=sha(cli),
                       elf_sha256=sha(root / 'fresh-final.elf'), elf_path=str(root / 'fresh-final.elf'))
        if not all(s in version for s in ('0.23.0', '1.18.10', '14.0.0git')):
            raise ValueError('wrong CLI/toolchain identity: ' + version)
        if receipt['elf_sha256'] != CANONICAL:
            raise ValueError('rebuilt ELF differs from preserved canonical hardware image')
        if sha(archive) != receipt['archive_sha256']:
            raise ValueError('archive changed during verification')
        receipt['passed'] = True
    except Exception as exc:
        receipt['error'] = str(exc)
    receipt['finished_at'] = time.time()
    path = logs / 'receipt.json'
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('inventory', 'environment', 'commands')}, sort_keys=True))
    print('receipt=' + str(path), flush=True)
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
