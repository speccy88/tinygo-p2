#!/usr/bin/env python3
"""Isolated unchanged Phase-1 scalar regression using Phase-2 outputs only.

Uses the Phase-2 pinned TinyGo/go-llvm/LLVM copies, but the unchanged Phase-1
scalar source, overlay, C transport, profile, and local Go 1.18.10. It never
writes Phase-1 .work output, report, cache, or HIL directories.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PHASE2 = Path(__file__).resolve().parents[1]
ROOT = PHASE2.parents[1]
SRC = PHASE2 / 'src'
# Reuse the already-validated workspace-local P2 LLVM build; only scalar
# source/cache/output paths are Phase2-owned. This is not a global SDK/cache.
LLVM = ROOT / '.work' / 'build' / 'llvm'
OUT = PHASE2 / 'out' / 'gate2a-scalar-regression'
GO = ROOT / '.work/toolchains/go1.18.10/bin/go'
LOADER = ROOT / '.work/bin/loadp2'
PROFILE = ROOT / 'firmware/p2-edge-tcxo.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, *, cwd, env):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, env=env, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--physical', action='store_true', help='run exactly 8 RAM-only Go scalar challenges')
    args = ap.parse_args()
    tinygo, llvmsrc = SRC / 'tinygo', SRC / 'llvm'
    probe, firmware = OUT / 'probe', OUT / 'firmware'
    probe.mkdir(parents=True, exist_ok=True)
    firmware.mkdir(parents=True, exist_ok=True)
    for required in (GO, LLVM / 'bin/llvm-config', LLVM / 'bin/clang', LLVM / 'bin/ld.lld', LOADER):
        if not required.is_file():
            raise SystemExit('missing prerequisite: ' + str(required))
    if subprocess.check_output([str(GO), 'version'], text=True).split()[2] != 'go1.18.10':
        raise SystemExit('wrong Go compatibility SDK')
    llvm_config = LLVM / 'bin/llvm-config'
    if not subprocess.check_output([str(llvm_config), '--version'], text=True).startswith('14.'):
        raise SystemExit('wrong workspace-local LLVM')
    overlay = ROOT / 'overlays/tinygo/compiler/zz_p2probe_test.go'
    target_overlay = tinygo / 'compiler/zz_p2probe_test.go'
    if target_overlay.exists() and target_overlay.read_bytes() != overlay.read_bytes():
        raise SystemExit('Phase2 scalar hook differs from preserved Phase1 hook')
    if not target_overlay.exists():
        shutil.copy2(overlay, target_overlay)
    env = dict(os.environ, CGO_ENABLED='1', GOWORK='off', GOFLAGS='',
               GOROOT=str(GO.parent.parent), PATH=str(GO.parent) + os.pathsep + os.environ.get('PATH', ''),
               GOCACHE=str(PHASE2 / 'cache/gate2a-scalar-go-build'),
               # Reuse the pinned workspace module cache read-only; network is
               # disabled in the hardware container and no global cache is used.
               GOMODCACHE=str(ROOT / '.work/cache/go-mod'), CC='clang', CXX='clang++',
               CGO_CPPFLAGS=subprocess.check_output([str(llvm_config), '--cppflags'], text=True).strip() + ' -I' + str(llvmsrc / 'clang/include'),
               CGO_CFLAGS='-Wno-deprecated-declarations', CGO_CXXFLAGS='-std=c++14',
               CGO_LDFLAGS=subprocess.check_output([str(llvm_config), '--link-shared', '--ldflags', '--libs', 'all', '--system-libs'], text=True).replace('\n', ' ').strip() + ' -L' + str(LLVM / 'lib') + ' -Wl,-rpath,' + str(LLVM / 'lib') + ' -lclang -lstdc++',
               P2_PROBE_SOURCE=str(ROOT / 'probe/arith.go'), P2_PROBE_OUT=str(probe), P2_PROBE_STAGE='full')
    run([GO, 'test', '-mod=readonly', '-tags=byollvm,p2probe', './compiler', '-run', '^TestP2ScalarProof$', '-count=1', '-v', '-timeout=10m'], cwd=tinygo, env=env)
    sys.path.insert(0, str(ROOT / 'scripts'))
    from artifactcheck import check_elf, check_ir
    generated = json.loads((probe / 'probe.json').read_text())
    if generated['source_sha256'] != sha(ROOT / 'probe/arith.go'):
        raise SystemExit('unchanged scalar source identity mismatch')
    check_ir((probe / 'go.ll').read_text(), ('p2_add', 'p2_mix'))
    obj = check_elf(probe / 'go.o', 1, True, ('p2_add', 'p2_mix'))
    profile = json.loads(PROFILE.read_text())
    harness = firmware / 'go.o'
    run([LLVM / 'bin/clang', '--target=p2', '--sysroot=' + str(LLVM), '-Os', '-std=gnu11', '-fno-jump-tables', '-ffunction-sections', '-fdata-sections',
         '-DP2_XTAL_HZ=' + str(profile['xtal_hz']), '-DP2_XOSC=' + str(profile['xosc']), '-DP2_TARGET_MHZ=' + str(profile['target_mhz']),
         '-c', ROOT / 'firmware/protocol.c', '-o', harness], cwd=ROOT, env=env)
    elf = firmware / 'go.elf'
    run([LLVM / 'bin/ld.lld', '-T', LLVM / 'p2.ld', '--Map=' + str(firmware / 'go.map'), '-o', elf, harness, probe / 'go.o', '--whole-archive', LLVM / 'libc/lib/libc.a', LLVM / 'libp2/lib/libp2.a', '--no-whole-archive'], cwd=ROOT, env=env)
    linked = check_elf(elf, 2, True, ('p2_add', 'p2_mix'))
    result = {'status': 'WARM_BUILD_PASS', 'scope': 'unchanged-phase1-scalar-source-with-phase2-only-output',
              'go': str(GO), 'go_version': subprocess.check_output([str(GO), 'version'], text=True).strip(),
              'tinygo_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tinygo, text=True).strip(),
              'go_llvm_replace': (tinygo / 'go.mod').read_text().split('replace tinygo.org/x/go-llvm => ')[1].splitlines()[0],
              'llvm_config': str(llvm_config), 'llvm_version': subprocess.check_output([str(llvm_config), '--version'], text=True).strip(),
              'source_sha256': generated['source_sha256'], 'object_sha256': obj['sha256'], 'elf_sha256': linked['sha256'],
              'elf': str(elf), 'profile_sha256': sha(PROFILE)}
    if args.physical:
        from hil import exchange, make_vectors
        port = '/dev/ttyUSB0'
        if not Path(port).exists() or len(list(Path('/dev').glob('ttyUSB*'))) != 1:
            raise SystemExit('serial preflight requires exactly /dev/ttyUSB0')
        if shutil.which('lsof') and subprocess.run(['lsof', '-t', port], capture_output=True, text=True).stdout.strip():
            raise SystemExit('serial port already held; refusing to disturb its owner')
        from datetime import datetime, timezone
        hil_dir = PHASE2 / 'hil' / ('gate2a-scalar-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
        command = [str(LOADER), '-p', port, '-b', '115200', '-l', '115200', '-ZERO', '-v', '-t', str(elf)]
        physical = exchange(command, 'G', make_vectors(8), hil_dir)
        physical.update({'scope': 'physical-P2-via-USB-serial', 'port': port, 'mode': 'go-unchanged-scalar-regression',
                         'elf_sha256': sha(elf), 'loader_sha256': sha(LOADER), 'profile_sha256': sha(PROFILE)})
        (hil_dir / 'hardware.json').write_text(json.dumps(physical, indent=2, sort_keys=True) + '\n')
        result['physical'] = {'status': physical['status'], 'passed': physical['passed'], 'total': physical['total'], 'directory': str(hil_dir)}
    (OUT / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
