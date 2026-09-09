#!/usr/bin/env python3
"""Offline corroboration of a real Gate2E record. Never opens serial.

Reuses the reviewed, independent Python oracle from the HIL source, but reads
raw replies independently of declared PASS and responses.jsonl. Only confirms
the specified recorded run and supplied current ELF, not a new hardware run.
"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

BOOT = ['P2 PHASE2 IMPORT INIT', 'P2 PHASE2 INIT', 'READY P2E 1']
REPLY = re.compile(r'R E ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8})')
DIGEST = re.compile(r'[0-9a-f]{64}')

def require(value, message):
    if not value:
        raise ValueError(message)

def verify(root, record, elf):
    root, record, elf = Path(root), Path(record), Path(elf)
    spec = importlib.util.spec_from_file_location('gate2e_reference', root/'.work/phase2/scripts/gate2e_hil.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hw = json.loads((record/'hardware.json').read_text())
    vectors = json.loads((record/'vectors.json').read_text())
    records = [json.loads(x) for x in (record/'responses.jsonl').read_text().splitlines() if x.strip()]
    lines = [x.strip() for x in (record/'terminal.raw').read_text(encoding='ascii').splitlines() if x.strip()]
    require([x for x in lines if x in BOOT] == BOOT, 'boot order/count')
    require('P2 PHASE2 CHECK FAIL' not in lines, 'Go startup failure')
    require(hw['scope'] == 'physical-P2-via-USB-serial', 'scope')
    require(hw['status'] == 'PASS', 'not a recorded positive run')
    for name, path in [('elf_sha256', elf), ('loader_sha256', root/'.work/bin/loadp2'), ('profile_sha256', root/'firmware/p2-edge-tcxo.json')]:
        value = hw.get(name)
        require(isinstance(value,str) and DIGEST.fullmatch(value), name+' format')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == value, name+' mismatch')
    replies = []
    for line in lines:
        if line.startswith('R '):
            match = REPLY.fullmatch(line)
            require(match is not None, 'malformed raw reply')
            replies.append([int(x,16) for x in match.groups()])
    require(len(vectors) >= 138, 'insufficient full-run vectors')
    require(len(replies) == len(records) == len(vectors) == hw['passed'] == hw['total'], 'count mismatch')
    require(len({v['id'] for v in vectors}) == len(vectors), 'duplicate IDs')
    state = {'sum':0, 'count':0, 'fold':0, 'seed':0x91e10da5}
    for index, (v, raw, declared) in enumerate(zip(vectors,replies,records)):
        require(all(type(v[k]) is int and 0 <= v[k] <= 0xffffffff for k in ('id','a','b','n')), 'word format')
        value = module.oracle(v['a'],v['b'],v['n'],state)
        expected = [v['id'],value,state['sum'],state['count']]
        require(raw == expected, 'raw arithmetic/state mismatch at '+str(index))
        require(declared == {'id':v['id'], 'expected':expected, 'observed':raw}, 'JSONL/raw mismatch')
    malformed = lines.count('ERR INPUT')
    require(malformed == hw['malformed_passed'] == 4, 'malformed-input response count')
    return {'status':'PASS','scope':'offline corroboration of an existing physical P2E1 record (Gate2E/2F)','record':str(record),'elf_sha256':hw['elf_sha256'],'raw_validated':len(replies),'unique_ids':len(vectors),'malformed_responses':malformed,'boot':BOOT,'final_state':state}

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    p.add_argument('--record',required=True)
    p.add_argument('--elf',required=True)
    a=p.parse_args()
    print(json.dumps(verify(a.root,a.record,a.elf),indent=2,sort_keys=True))
