#!/usr/bin/env python3
"""Offline verification of preserved mutation/restoration and real panic records."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

def need(condition,message):
    if not condition: raise ValueError(message)
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify(root):
    root=Path(root); p=root/'.work/phase2'
    mut=p/'artifacts/gate2f-mutation-20260908T131809.889528543Z'
    restored=p/'artifacts/gate2f-restored-20260908T131856.889558316Z'
    mr=p/'hil/gate2f-mutation-20260908T131831.929435Z'
    pr=p/'hil/gate2f-panic-20260908T132003.741335Z'
    pa=p/'artifacts/gate2f-panic-20260908T131933.458767181Z'
    original=(mut/'core-original.go').read_bytes()
    mutated=(mut/'core-mutated.go').read_bytes()
    old=b'return local ^ st.sum ^ st.fold'; new=b'return (local ^ st.sum ^ st.fold) ^ 1'
    need(original.count(old)==1,'mutation anchor')
    need(mutated==original.replace(old,new),'not the exact single Go mutation')
    need((p/'src/p2goapp/core.go').read_bytes()==original,'live Go source not restored')
    need((restored/'core-restored.go').read_bytes()==original,'restored snapshot differs')
    hw=json.loads((mr/'hardware.json').read_text())
    need(digest(mut/'p2goapp-mutated.elf')==hw['elf_sha256'],'mutated image identity')
    final=p/'artifacts/gate2f-final-cli-20260908T131540.392502595Z/p2goapp-final.elf'
    need(digest(restored/'p2goapp-restored.elf')==digest(final),'restored ELF not byte-identical')
    spec=importlib.util.spec_from_file_location('gate2f_reference',p/'scripts/gate2e_hil.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    v=hw['vector']; st={'sum':0,'count':0,'fold':0,'seed':0x91e10da5}
    normal=[v['id'],module.oracle(v['a'],v['b'],v['n'],st),st['sum'],st['count']]
    predicted=[normal[0],normal[1]^1,normal[2],normal[3]]
    lines=[x.strip() for x in (mr/'terminal.raw').read_text(encoding='ascii').splitlines()]
    regex=re.compile(r'R E ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8})')
    replies=[[int(x,16) for x in m.groups()] for s in lines if (m:=regex.fullmatch(s))]
    need(replies==[predicted],'raw mutation not predicted XOR1')
    need(hw['observed']==predicted==hw['predicted_mutated'] and hw['normal_expected']==normal,'mutation metadata')
    need(normal!=predicted and hw['normal_validation_failed'] is True,'normal validation did not fail')
    ph=json.loads((pr/'hardware.json').read_text()); raw=(pr/'terminal.raw').read_bytes()
    pl=[x.strip() for x in raw.decode('ascii').splitlines() if x.strip()]
    expected=['P2 GO BOUNDS ARMED','P2 GO BOUNDS TRIGGER','panic: runtime error: index out of range']
    need([x for x in pl if x in expected]==expected,'missing/duplicate/out-of-order actual panic diagnostic')
    need(not any('FORBIDDEN CONTINUATION' in x or x.startswith('R E ') for x in pl),'panic continuation/success')
    need(digest(pa/'p2panic.elf')==ph['elf_sha256'],'panic image identity')
    need(hashlib.sha256(raw).hexdigest()==ph['raw_sha256'] and len(raw)==ph['raw_bytes'],'panic raw identity')
    for h in (hw,ph):
        need(h['loader_sha256']==digest(root/'.work/bin/loadp2'),'loader identity')
        need(h['profile_sha256']==digest(root/'firmware/p2-edge-tcxo.json'),'board profile identity')
    return {'status':'PASS','scope':'offline corroboration of existing physical controls; not a new hardware run','exact_single_go_mutation':True,'normal_expected':normal,'predicted_and_observed_mutated':predicted,'current_and_saved_source_restored_byte_identically':True,'restored_elf_sha256':digest(final),'real_target_panic_lines':expected,'no_forbidden_continuation_in_captured_window':True,'qualification':'Historical panic helper had a filename-substring false-positive bug; this verifier instead requires the exact target diagnostic. Corrected live helper and duration/EOF rejection tests are separate release checks.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    print(json.dumps(verify(parser.parse_args().root),indent=2,sort_keys=True))
