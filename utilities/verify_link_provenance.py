"""Read-only object-to-ELF provenance checks; does not access serial."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol_bytes(path, info):
    data = path.read_bytes()
    h = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    section = struct.unpack_from('<10I', data, h[6] + info['section'] * h[11])
    relative = info['value'] if h[1] == 1 else info['value'] - section[3]
    assert 0 <= relative and relative + info['size'] <= section[5]
    return data[section[4] + relative:section[4] + relative + info['size']]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root', type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / 'scripts'))
    from artifactcheck import check_elf, check_ir
    probe_dir = root / '.work/out/probe'
    firmware_dir = root / '.work/out/firmware'
    obj_path, elf_path = probe_dir / 'go.o', firmware_dir / 'go.elf'
    metadata = json.loads((firmware_dir / 'go.json').read_text())
    proof = json.loads((probe_dir / 'probe.json').read_text())
    obj = check_elf(obj_path, 1, True)
    elf = check_elf(elf_path, 2, True)
    baseline = check_elf(firmware_dir / 'c.elf', 2, False)
    ir = check_ir((probe_dir / 'go.ll').read_text())
    assert metadata['elf']['sha256'] == elf['sha256']
    assert metadata['proof']['object']['sha256'] == obj['sha256']
    assert metadata['harness_sha256'] == digest(root / 'firmware/protocol.c')
    assert metadata['profile_sha256'] == digest(root / 'firmware/p2-edge-tcxo.json')
    assert metadata['proof']['source_sha256'] == proof['source_sha256'] == digest(root / 'probe/arith.go')
    assert metadata['proof']['overlay_sha256'] == digest(root / 'overlays/tinygo/compiler/zz_p2probe_test.go')
    assert any(x.endswith('/.work/out/probe/go.o') for x in metadata['link_inputs'])
    bodies = {}
    for name in ('p2_add', 'p2_mix'):
        original = symbol_bytes(obj_path, obj['exports'][name])
        linked = symbol_bytes(elf_path, elf['exports'][name])
        assert original == linked, f'{name} differs between Go object and linked ELF'
        bodies[name] = {'bytes': len(linked), 'sha256': hashlib.sha256(linked).hexdigest(),
                        'object_bytes_identical_to_linked_bytes': True}
    assert baseline['exports'] == {}, 'C control unexpectedly defines Go exports'
    print(json.dumps({'scope': 'static-object-to-ELF-NOT-physical-execution', 'status': 'PASS',
                      'source_sha256': proof['source_sha256'], 'object_sha256': obj['sha256'],
                      'go_elf_sha256': elf['sha256'], 'c_elf_sha256': baseline['sha256'],
                      'go_bodies': bodies, 'go_load_segments': elf['load_segments'],
                      'ir': ir}, indent=2))


if __name__ == '__main__':
    main()
