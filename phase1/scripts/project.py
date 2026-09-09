#!/usr/bin/env python3
"""Workspace-local build driver for the pinned TinyGo/P2 scalar experiment."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from artifactcheck import CheckError, check_elf, check_ir, sha256
from hil import exchange, make_vectors

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'.work'
SRC = WORK/'src'
BUILD = WORK/'build'
LLVM = BUILD/'llvm'
OUT = WORK/'out'
LOCK = json.loads((ROOT/'sources.lock.json').read_text())

class BuildError(RuntimeError): pass

def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')

def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def capture(cmd: list[str], **kwargs) -> str:
    return subprocess.check_output([str(x) for x in cmd], text=True, stderr=subprocess.STDOUT, **kwargs).strip()

def run(cmd: list[str], *, cwd: Path = ROOT, env: dict | None = None, name: str = 'command'):
    cmd = [str(x) for x in cmd]
    logs = WORK/'logs'; logs.mkdir(parents=True, exist_ok=True)
    # Do not use Path.with_suffix here: stamp() deliberately has a fractional
    # seconds dot, and with_suffix would collapse distinct command stems.
    stem = stamp()+'-'+name
    metadata_path = logs/(stem+'.json')
    log_path = logs/(stem+'.log')
    metadata = {'command': cmd, 'cwd': str(cwd)}
    write_json(metadata_path, metadata)
    print('+', ' '.join(cmd), flush=True)
    with log_path.open('w') as log:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors='replace')
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line); log.flush(); print(line, end='', flush=True)
            rc = proc.wait()
        except BaseException:
            proc.terminate()
            try: rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill(); rc = proc.wait()
            metadata.update({'returncode': rc, 'interrupted': True})
            write_json(metadata_path, metadata)
            raise
    metadata['returncode'] = rc
    write_json(metadata_path, metadata)
    if rc: raise BuildError(f'{name} exited {rc}; see {log_path}')

def require(program: str) -> str:
    result = shutil.which(program)
    if not result: raise BuildError(f'missing prerequisite: {program}')
    return result

def jobs() -> int:
    n = int(os.environ.get('P2_JOBS', '2'))
    if not 1 <= n <= 8: raise BuildError('P2_JOBS must be between 1 and 8')
    return n

def cmake_policy() -> list[str]:
    version = capture([require('cmake'), '--version'])
    return ['-DCMAKE_POLICY_VERSION_MINIMUM=3.5'] if re.search(r'version [4-9]\.', version) else []

def preflight():
    if re.search(r'\s', str(ROOT)):
        raise BuildError('Use a workspace path without whitespace (legacy CGO flags).')
    host = {'system': platform.system(), 'machine': platform.machine(),
            'python': sys.version, 'workspace': str(ROOT),
            'free_disk_gib': round(shutil.disk_usage(ROOT).free/2**30, 2), 'build_jobs': jobs()}
    if platform.system() == 'Darwin':
        try: translated = capture(['sysctl','-in','sysctl.proc_translated'])
        except subprocess.CalledProcessError: translated = '0'
        if translated == '1' or platform.machine() != 'arm64':
            raise BuildError('Run this M2 workflow natively as arm64, not under Rosetta.')
        host['sdk'] = capture(['xcrun', '--show-sdk-path'])
        host['memory_bytes'] = int(capture(['sysctl','-n','hw.memsize']))
    for program in ['git','cmake','ninja','clang','clang++','make']:
        host[program] = require(program)
    write_json(WORK/'reports'/'preflight.json', host)
    print(json.dumps(host, indent=2))

def fetch_sources():
    SRC.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    for name in ['tinygo','p2llvm','llvm','loadp2']:
        item = LOCK[name]; dest = SRC/name
        if dest.exists():
            if not (dest/'.git').exists(): raise BuildError(f'{dest} exists but is not an owned git checkout')
            if capture(['git','rev-parse','HEAD'], cwd=dest) != item['revision']:
                raise BuildError(f'{dest} is not at the locked revision; preserving it unchanged')
            print('Already pinned:', name); continue
        temporary = Path(tempfile.mkdtemp(prefix=name+'-', dir=SRC))
        try:
            run(['git','init',str(temporary)], env=env, name='init-'+name)
            run(['git','remote','add','origin',item['url']], cwd=temporary, env=env, name='remote-'+name)
            run(['git','fetch','--depth=1','origin',item['revision']], cwd=temporary, env=env, name='fetch-'+name)
            run(['git','checkout','--detach','FETCH_HEAD'], cwd=temporary, env=env, name='checkout-'+name)
            if capture(['git','rev-parse','HEAD'], cwd=temporary) != item['revision']:
                raise BuildError('downloaded source revision mismatch')
            temporary.rename(dest)
        except BaseException:
            print(f'Partial checkout kept at {temporary}', file=sys.stderr); raise
    # Deliberately do not recursively initialize SDK or unrelated SSH submodules.

def fetch_go():
    version = LOCK['go']['version']
    destination = WORK/'toolchains'/version
    if (destination/'bin'/'go').is_file():
        if capture([destination/'bin'/'go','version']).split()[2] != version:
            raise BuildError('existing local Go version mismatch')
        print(destination); return
    system = {'Darwin':'darwin','Linux':'linux'}.get(platform.system())
    arch = {'arm64':'arm64','aarch64':'arm64','x86_64':'amd64'}.get(platform.machine())
    if not system or not arch: raise BuildError('unsupported toolchain host')
    filename = f'{version}.{system}-{arch}.tar.gz'
    with urllib.request.urlopen(LOCK['go']['manifest'], timeout=60) as response:
        manifest = json.load(response)
    releases = [r for r in manifest if r['version'] == version]
    if len(releases) != 1: raise BuildError('exact Go release absent from official manifest')
    entries = [x for x in releases[0]['files'] if x['filename'] == filename]
    if len(entries) != 1: raise BuildError('exact Go archive absent from official manifest')
    item = entries[0]
    cache = WORK/'downloads'; cache.mkdir(parents=True, exist_ok=True)
    archive = cache/filename
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        with urllib.request.urlopen('https://go.dev/dl/'+filename, timeout=120) as response, partial.open('wb') as f:
            shutil.copyfileobj(response, f)
        partial.rename(archive)
    if sha256(archive) != item['sha256']: raise BuildError('Go archive SHA256 mismatch; not extracting')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='extract-go-', dir=destination.parent))
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'go':
                raise BuildError('unsafe archive member')
            if not (member.isdir() or member.isfile()): raise BuildError('non-regular archive member rejected')
        # All member paths/types have been checked for older Python versions too.
        tf.extractall(temporary, filter='data') if sys.version_info >= (3,12) else tf.extractall(temporary)
    (temporary/'go').rename(destination); temporary.rmdir()
    write_json(WORK/'reports'/'go-download.json', {'vendor_manifest': LOCK['go']['manifest'], 'archive': filename,
               'sha256': item['sha256'], 'version': version, 'note': 'Digest verified against official HTTPS manifest.'})
    print(destination)

def legacy_go() -> Path:
    p = Path(os.environ.get('GO18', str(WORK/'toolchains'/LOCK['go']['version']/'bin'/'go'))).expanduser()
    if not p.is_file(): raise BuildError('Run fetch-go or set GO18 to an existing go1.18.10 binary')
    if capture([p,'version']).split()[2] != LOCK['go']['version']:
        raise BuildError('This baseline requires Go 1.18.10; do not silently use current Go')
    return p

def source(name: str) -> Path:
    p = SRC/name
    if not (p/'.git').is_dir(): raise BuildError('Run fetch first: missing '+name)
    if capture(['git','rev-parse','HEAD'], cwd=p) != LOCK[name]['revision']:
        raise BuildError('Unexpected source revision: '+name)
    return p

def build_llvm():
    s = source('llvm'); LLVM.mkdir(parents=True, exist_ok=True)
    host_target = 'AArch64' if platform.machine() in ('arm64','aarch64') else 'X86'
    cmd = ['cmake','-G','Ninja','-S',s/'llvm','-B',LLVM,
        '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_C_COMPILER='+require('clang'),
        '-DCMAKE_CXX_COMPILER='+require('clang++'), '-DLLVM_ENABLE_PROJECTS=clang;lld',
        '-DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=P2', '-DLLVM_TARGETS_TO_BUILD='+host_target,
        '-DLLVM_BUILD_LLVM_DYLIB=ON', '-DLLVM_LINK_LLVM_DYLIB=ON', '-DLLVM_DYLIB_COMPONENTS=all',
        '-DLLVM_ENABLE_ASSERTIONS=ON', '-DLLVM_INCLUDE_TESTS=OFF', '-DLLVM_INCLUDE_BENCHMARKS=OFF',
        '-DLLVM_ENABLE_BINDINGS=OFF', '-DLLVM_ENABLE_TERMINFO=OFF', '-DLLVM_ENABLE_ZLIB=OFF',
        '-DLLVM_ENABLE_LIBXML2=OFF', '-DLLVM_ENABLE_LIBEDIT=OFF', '-DLLVM_ENABLE_Z3_SOLVER=OFF',
        '-DCLANG_ENABLE_STATIC_ANALYZER=OFF', '-DCLANG_ENABLE_ARCMT=OFF'] + cmake_policy()
    if platform.system() == 'Darwin': cmd.append('-DCMAKE_OSX_ARCHITECTURES=arm64')
    run(cmd, name='configure-llvm')
    run(['cmake','--build',LLVM,'--parallel',str(jobs()),'--target','clang','libclang','LLVM',
         'llc','opt','llvm-config','llvm-as','llvm-dis','llvm-nm','llvm-readobj','llvm-objdump',
         'llvm-ar','llvm-ranlib','lld'], name='build-llvm')
    version = capture([LLVM/'bin/llvm-config','--version'])
    if not version.startswith('14.'): raise BuildError('wrong LLVM version')
    info = capture([LLVM/'bin/llc','--version'])
    if not re.search(r'^\s*p2\s+-', info, re.M | re.I): raise BuildError('built llc does not register P2')
    write_json(WORK/'reports'/'llvm.json', {'status':'BUILT','version':version,'llc':info})

def backend_control():
    directory = OUT/'c-control'; directory.mkdir(parents=True, exist_ok=True)
    obj = directory/'c-control.o'
    run([LLVM/'bin/clang','--target=p2','-ffreestanding','-fno-jump-tables','-Os','-c',
         ROOT/'firmware/codegen_control.c','-o',obj], name='c-backend-control')
    identity = check_elf(obj, 1, False)
    (directory/'disassembly.txt').write_text(capture([LLVM/'bin/llvm-objdump','-d',obj])+'\n')
    write_json(directory/'control.json', {'status':'C_BACKEND_CONTROL_ONLY_NOT_GO','elf':identity})

def build_libraries():
    s = source('p2llvm')
    if not (LLVM/'bin/clang').is_file(): raise BuildError('Build LLVM first')
    generator = ['-G', 'Ninja'] if shutil.which('ninja') else ['-G', 'Unix Makefiles']
    generator_name = generator[1]
    # The P2 Clang driver treats ../libp2/include and ../libc/include as its
    # target sysroot. Seed both header trees before compiling either archive so
    # target <stdint.h> wins over the host fallback in Clang's resource header.
    for name in ['libp2', 'libc']:
        shutil.copytree(s/name/'include', LLVM/name/'include', dirs_exist_ok=True)
    for name in ['libp2','libc']:
        b = BUILD/name
        cache = b/'CMakeCache.txt'
        if cache.is_file() and (f'CMAKE_HOME_DIRECTORY:INTERNAL={s/name}' not in cache.read_text(errors='replace')
                                or f'CMAKE_GENERATOR:INTERNAL={generator_name}' not in cache.read_text(errors='replace')):
            # A prior container bind used /work while this host uses /opt/data.
            # These small target-library build files are not reusable across the
            # absolute-path change; LLVM itself is deliberately untouched.
            shutil.rmtree(b)
        run(['cmake',*generator,'-S',s/name,'-B',b,'-Dllvm='+str(LLVM/'bin')]+cmake_policy(), name='configure-'+name)
        run(['cmake','--build',b,'--parallel',str(jobs())], name='build-'+name)
        destination = LLVM/name
        (destination/'lib').mkdir(parents=True, exist_ok=True)
        shutil.copytree(s/name/'include', destination/'include', dirs_exist_ok=True)
        lib = b/'lib/libp2.a' if name == 'libp2' else b/'libc.a'
        if not lib.is_file(): raise BuildError('expected library missing: '+str(lib))
        shutil.copy2(lib, destination/'lib'/lib.name)
    for filename in ['p2.ld','p2_debug.ld']:
        shutil.copy2(s/'libp2'/filename, LLVM/filename)

def build_loader():
    s = source('loadp2')
    # Do not use the default target: it also builds flash/SD helpers via flexspin.
    run(['make','build/loadp2','CC='+require('cc')], cwd=s, name='build-loadp2')
    (WORK/'bin').mkdir(parents=True, exist_ok=True)
    shutil.copy2(s/'build/loadp2', WORK/'bin/loadp2')

def build_probe(stage: str):
    s = source('tinygo'); llvmsrc = source('llvm'); go = legacy_go()
    overlay = ROOT/'overlays/tinygo/compiler/zz_p2probe_test.go'
    dest = s/'compiler'/overlay.name
    if dest.exists() and dest.read_bytes() != overlay.read_bytes():
        raise BuildError('Existing probe hook differs. Preserve/merge Codex edits rather than overwriting them.')
    shutil.copy2(overlay, dest)
    llvmconfig = LLVM/'bin/llvm-config'
    if not llvmconfig.exists(): raise BuildError('Build LLVM first')
    if not capture([llvmconfig,'--version']).startswith('14.'): raise BuildError('LLVM 14 required')
    output = OUT/('probe-add' if stage == 'add' else 'probe'); output.mkdir(parents=True, exist_ok=True)
    # Prevent old successful outputs from being mistaken for this attempt.
    for name in ['go.ll','go.s','go.o','probe.json','checked.json']:
        if (output/name).exists():
            archive = output/('previous-'+stamp()); archive.mkdir()
            for old in ['go.ll','go.s','go.o','probe.json','checked.json']:
                if (output/old).exists(): shutil.move(output/old, archive/old)
            break
    env = dict(os.environ)
    env.update({'CGO_ENABLED':'1','GOWORK':'off','GOFLAGS':'',
       'GOROOT':str(go.parent.parent),'PATH':str(go.parent)+os.pathsep+os.environ.get('PATH',''),
       'GOCACHE':str(WORK/'cache/go-build'), 'GOMODCACHE':str(WORK/'cache/go-mod'),
       'CC':require('clang'),'CXX':require('clang++'),
       'CGO_CPPFLAGS':capture([llvmconfig,'--cppflags'])+' -I'+str(llvmsrc/'clang/include'),
       'CGO_CFLAGS':'-Wno-deprecated-declarations', 'CGO_CXXFLAGS':'-std=c++14',
       'CGO_LDFLAGS':capture([llvmconfig,'--link-shared','--ldflags','--libs','all','--system-libs']).replace('\n',' ')
          +' -L'+str(LLVM/'lib')+' -Wl,-rpath,'+str(LLVM/'lib')+' -lclang '
          +('-lc++' if platform.system() == 'Darwin' else '-lstdc++'),
       'P2_PROBE_SOURCE':str(ROOT/'probe/arith.go'), 'P2_PROBE_OUT':str(output), 'P2_PROBE_STAGE':stage})
    write_json(WORK/'reports'/'probe-build-env.json', {k:env[k] for k in ['GOROOT','CGO_CPPFLAGS','CGO_CFLAGS','CGO_CXXFLAGS','CGO_LDFLAGS','CC','CXX','P2_PROBE_SOURCE','P2_PROBE_OUT','P2_PROBE_STAGE']})
    run([go,'test','-mod=readonly','-tags=byollvm,p2probe','./compiler','-run','^TestP2ScalarProof$',
         '-count=1','-v','-timeout=10m'], cwd=s, env=env, name='tinygo-p2-proof')
    checked = validate_probe(stage)
    for command, name in [([LLVM/'bin/llvm-objdump','-d',output/'go.o'],'go.disassembly.txt'),
                           ([LLVM/'bin/llvm-readobj','--file-headers','--symbols',output/'go.o'],'go.readobj.txt')]:
        (output/name).write_text(capture(command)+'\n')
    write_json(output/'checked.json', checked)

def validate_probe(stage: str = 'full') -> dict:
    p = OUT/('probe-add' if stage == 'add' else 'probe')
    exports = ('p2_add',) if stage == 'add' else ('p2_add','p2_mix')
    for name in ['go.ll','go.s','go.o','probe.json']:
        if not (p/name).is_file(): raise BuildError('Missing current generated artifact: '+name)
    m = json.loads((p/'probe.json').read_text())
    if m.get('stage') != stage or m.get('exports') != list(exports):
        raise BuildError('Selected proof stage does not match the generated manifest')
    if m.get('source_sha256') != sha256(ROOT/'probe/arith.go'):
        raise BuildError('Go source provenance mismatch')
    for name in ['go.ll','go.o','go.s']:
        if m.get('artifacts_sha256',{}).get(name) != sha256(p/name):
            raise BuildError('Generated artifact hash mismatch: '+name)
    ir = check_ir((p/'go.ll').read_text(), exports)
    obj = check_elf(p/'go.o', 1, True, exports)
    return {'status':'OBJECT_CHECKS_PASS_NOT_HARDWARE_VALIDATED', 'ir':ir, 'object':obj,
            'source_sha256':m['source_sha256'], 'ir_sha256':sha256(p/'go.ll'),
            'overlay_sha256':sha256(ROOT/'overlays/tinygo/compiler/zz_p2probe_test.go')}

def build_firmware(mode: str):
    dest = OUT/'firmware'; dest.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT/'firmware/p2-edge-tcxo.json').read_text())
    if profile['serial_baud'] != 115200: raise BuildError('protocol firmware is pinned to 115200 baud')
    manifest_path = dest/(mode+'.json')
    if manifest_path.exists(): manifest_path.rename(dest/(mode+'-previous-'+stamp()+'.json'))
    command = [LLVM/'bin/clang','--target=p2','--sysroot='+str(LLVM),'-Os','-std=gnu11',
          '-fno-jump-tables','-ffunction-sections','-fdata-sections',
          '-DP2_XTAL_HZ='+str(profile['xtal_hz']),'-DP2_XOSC='+str(profile['xosc']),
          '-DP2_TARGET_MHZ='+str(profile['target_mhz']),'-c',ROOT/'firmware/protocol.c',
          '-o',dest/(mode+'.o')]
    inputs = [dest/(mode+'.o')]
    proof = None
    if mode == 'c': command.append('-DBASELINE')
    else:
        proof = validate_probe(); inputs.append(OUT/'probe/go.o')
    run(command, name='compile-'+mode+'-harness')
    # Explicit linker path/libraries: the old Clang driver searches global /opt paths.
    link = [LLVM/'bin/ld.lld','-T',LLVM/'p2.ld','--Map='+str(dest/(mode+'.map')), '-o',dest/(mode+'.elf')]
    link += inputs + ['--whole-archive',LLVM/'libc/lib/libc.a',LLVM/'libp2/lib/libp2.a','--no-whole-archive']
    run(link, name='link-'+mode+'-firmware')
    identity = check_elf(dest/(mode+'.elf'), 2, mode=='go')
    (dest/(mode+'.disassembly.txt')).write_text(capture([LLVM/'bin/llvm-objdump','-d',dest/(mode+'.elf')])+'\n')
    write_json(manifest_path, {'status':'LINKED_NOT_HARDWARE_VALIDATED','mode':mode,
               'elf':identity,'proof':proof, 'profile':profile,
               'profile_sha256':sha256(ROOT/'firmware/p2-edge-tcxo.json'),
               'harness_sha256':sha256(ROOT/'firmware/protocol.c'),
               'link_inputs':[str(x) for x in inputs],
               'link_command':[str(x) for x in link]})

def list_ports() -> list[str]:
    patterns = ['/dev/cu.usbserial*','/dev/cu.usbmodem*'] if platform.system() == 'Darwin' else ['/dev/ttyUSB*','/dev/ttyACM*']
    return sorted({p for pattern in patterns for p in glob.glob(pattern)})

def hil(args):
    if not args.allow_ram_reset: raise BuildError('Hardware execution requires --allow-ram-reset; RAM download resets the P2')
    ports = list_ports()
    port = args.port
    if port == 'auto':
        if len(ports) != 1: raise BuildError('Auto-selection requires exactly one eligible serial device; found '+repr(ports))
        port = ports[0]
    if port not in ports: raise BuildError('Port is not a currently detected eligible USB serial device: '+port)
    if shutil.which('lsof'):
        busy = subprocess.run(['lsof','-t',port], capture_output=True, text=True)
        if busy.returncode == 0 and busy.stdout.strip(): raise BuildError('Serial port is in use; do not kill other applications automatically')
    mode = args.mode
    image = OUT/'firmware'/(mode+'.elf')
    manifest = json.loads((OUT/'firmware'/(mode+'.json')).read_text())
    if manifest.get('mode') != mode: raise BuildError('firmware mode mismatch')
    if manifest['elf']['sha256'] != sha256(image): raise BuildError('ELF changed since validated link')
    if manifest['harness_sha256'] != sha256(ROOT/'firmware/protocol.c'): raise BuildError('C harness changed; rebuild')
    if manifest['profile_sha256'] != sha256(ROOT/'firmware/p2-edge-tcxo.json'): raise BuildError('board profile changed; rebuild')
    check_elf(image, 2, mode=='go')
    if mode == 'go':
        current = validate_probe()
        if current['object']['sha256'] != manifest['proof']['object']['sha256']: raise BuildError('linked object is stale')
        # A C transport/clock baseline must have passed on this exact port/profile first.
        baseline = WORK/'reports/baseline-hardware.json'
        if not baseline.is_file(): raise BuildError('Run hil --mode c first')
        previous = json.loads(baseline.read_text())
        if previous.get('status') != 'PASS' or previous.get('port') != port or previous.get('profile_sha256') != manifest['profile_sha256']:
            raise BuildError('baseline hardware/profile/port does not match')
    loader = WORK/'bin/loadp2'
    if not loader.is_file(): raise BuildError('Build the pinned ne75 loadp2 first')
    (WORK/'locks').mkdir(parents=True, exist_ok=True)
    lockfile = WORK/'locks'/(hashlib.sha256(port.encode()).hexdigest()+'.lock')
    with lockfile.open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        directory = WORK/'hil'/(stamp()+'-'+mode)
        command = [str(loader),'-p',port,'-b','115200','-l','115200','-ZERO','-v','-t',str(image)]
        # No -PATCH, -9, flash helper, @address payload, SD script, or shell command.
        if mode == 'c':
            write_json(WORK/'reports/baseline-hardware.json', {'status':'RUNNING_NOT_PASSED','port':port})
        provenance = {'scope':'physical-P2-via-USB-serial', 'port':port, 'mode':mode,
                      'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                      'elf_sha256':sha256(image), 'loader_sha256':sha256(loader),
                      'profile_sha256':manifest['profile_sha256'], 'log_directory':str(directory)}
        try:
            result = exchange(command, 'C' if mode=='c' else 'G', make_vectors(args.random), directory)
        except BaseException:
            # exchange always retains raw terminal/transport evidence after it
            # creates its directory. Add the artifact provenance before the
            # command failure propagates to main's honest nonzero result.
            transport = directory/'transport.json'
            if transport.is_file():
                failed = json.loads(transport.read_text())
                failed.update(provenance)
                write_json(directory/'hardware.json', failed)
                if mode == 'c': write_json(WORK/'reports/baseline-hardware.json', failed)
            raise
        result.update(provenance)
        write_json(directory/'hardware.json', result)
        if mode == 'c': write_json(WORK/'reports/baseline-hardware.json', result)
        print(json.dumps(result, indent=2))

def evidence():
    directory = WORK/'evidence'; directory.mkdir(parents=True, exist_ok=True)
    for name in ['tinygo','p2llvm','llvm','loadp2']:
        p = SRC/name
        if not (p/'.git').exists(): continue
        (directory/(name+'.diff')).write_text(capture(['git','diff','--binary','HEAD'],cwd=p)+'\n')
        (directory/(name+'.status')).write_text(capture(['git','status','--short'],cwd=p)+'\n')
    hashes = {}
    for folder in [OUT,WORK/'reports',WORK/'hil']:
        if folder.exists():
            for p in sorted(folder.rglob('*')):
                if p.is_file(): hashes[str(p.relative_to(WORK))] = sha256(p)
    write_json(directory/'SHA256.json', hashes)
    print('Evidence:',directory)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ['preflight','fetch','fetch-go','llvm','backend-control','libraries','loader','ports','evidence']:
        sub.add_parser(name)
    p = sub.add_parser('probe'); p.add_argument('--stage',choices=['add','full'],default='add')
    p = sub.add_parser('firmware'); p.add_argument('--mode',choices=['c','go'],required=True)
    p = sub.add_parser('hil'); p.add_argument('--mode',choices=['c','go'],required=True)
    p.add_argument('--port',required=True); p.add_argument('--allow-ram-reset',action='store_true')
    p.add_argument('--random',type=int,default=128)
    args = parser.parse_args()
    actions = {'preflight':preflight,'fetch':fetch_sources,'fetch-go':fetch_go,'llvm':build_llvm,
               'backend-control':backend_control,'libraries':build_libraries,'loader':build_loader,'probe':lambda:build_probe(args.stage),'evidence':evidence,
               'ports':lambda: print(json.dumps(list_ports(),indent=2)),
               'firmware':lambda:build_firmware(args.mode),'hil':lambda:hil(args)}
    try: actions[args.action]()
    except (BuildError, CheckError, OSError, subprocess.CalledProcessError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr); return 1
    return 0
if __name__ == '__main__': sys.exit(main())
