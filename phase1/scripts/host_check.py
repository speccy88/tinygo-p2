#!/usr/bin/env python3
"""Run portable checks and explicitly record what has NOT been validated."""
import datetime
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    reports=ROOT/'reports'; reports.mkdir(exist_ok=True)
    go=shutil.which('go'); gofmt=shutil.which('gofmt')
    commands=[[sys.executable,'-m','unittest','discover','-s','tests','-v']]
    if not go or not gofmt:
        print('A host Go installation and gofmt are required.',file=sys.stderr); return 1
    commands+=[[go,'test','-count=1','-v','./probe'],
               [gofmt,'-l','probe','overlays/tinygo/compiler']]
    env=dict(os.environ,GOWORK='off',GOTOOLCHAIN='local',GOPROXY='off')
    env['GOCACHE']=str(ROOT/'.work/cache/host-go')
    results=[]
    for i,cmd in enumerate(commands):
        p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True)
        text=p.stdout+p.stderr
        (reports/f'host-check-{i+1}.txt').write_text(text)
        print(text,end='')
        ok=p.returncode==0 and (i!=2 or not text.strip())
        results.append({'command':cmd,'returncode':p.returncode,'passed':ok})
    version=subprocess.check_output([go,'version'],text=True).strip()
    report={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status':'PASS' if all(x['passed'] for x in results) else 'FAIL',
            'host_go':version, 'execution_host':{'system':platform.system(),'machine':platform.machine(),
                                                  'python':sys.version}, 'checks':results,
            'tested':['standard-Go arithmetic reference (10000 randomized pairs plus edges)',
                      'host C serial protocol through a pseudo-terminal (138 challenges)',
                      'malformed-input, provenance/scope, ELF/IR and safety guards',
                      'syntax/format of the Go compiler overlay'],
            'not_tested':['TinyGo overlay typecheck/link with pinned custom LLVM',
                          'P2 LLVM backend object generation',
                          'real USB serial connection, board clock profile, or execution on a Propeller 2'],
            'limitation':'This is a Linux x86_64 host-only report. It does not establish TinyGo/P2 compilation, linking, or physical hardware execution.'}
    # Preserve the supplied baseline report: this command records the current
    # final Linux rerun separately, so archival evidence is never overwritten.
    (reports/'final-host-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__': sys.exit(main())
