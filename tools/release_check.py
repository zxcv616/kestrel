"""Fail closed on release build invariants and record reproducible inspection data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def check(build, output, analyze=True):
    sources=sorted((ROOT/'fsw').rglob('*.c'))+sorted((ROOT/'fsw').rglob('*.h'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    forbidden=r'\b(malloc|calloc|realloc|free|pvPortMalloc|vPortFree|xTaskCreate|xQueueCreate|xSemaphoreCreateMutex|xTaskNotify|xStreamBufferSend)\s*\('
    for path in sources:
        assert not re.search(forbidden,path.read_text()), str(path)
    config=(ROOT/'fsw/FreeRTOSConfig.h').read_text()
    for name,value in [('configSUPPORT_DYNAMIC_ALLOCATION',0),('configSUPPORT_STATIC_ALLOCATION',1),('configUSE_MUTEXES',0),('configCHECK_FOR_STACK_OVERFLOW',2),('INCLUDE_uxTaskGetStackHighWaterMark',1)]:
        assert re.search(r'#define\s+'+name+r'\s+'+str(value)+r'\b',config), name
    entries=json.loads((build/'compile_commands.json').read_text())
    flight=[]
    for entry in entries:
        if '/fsw/' not in entry['file']:continue
        args=entry.get('arguments') or shlex.split(entry['command'])
        assert all(flag in args for flag in ['-Wall','-Wextra','-Werror']),entry['file']
        if entry['file'].endswith(('/flight.c', '/tasks/mode.c')):
            pre=[]; skip=False
            for arg in args:
                if skip:skip=False;continue
                if arg=='-o':skip=True;continue
                if arg=='-c':continue
                pre.append(arg)
            source=subprocess.check_output(pre+['-E','-P'],cwd=entry['directory'],text=True)
            is_test=any(a.startswith('-DKESTREL_TEST') for a in args)
            if entry['file'].endswith('/tasks/mode.c'):
                assert ('injection = (Injection)' in source)==is_test
                assert ('static void observe(' in source)==is_test
                flight.append('test' if is_test else 'production')
            else:
                assert ('"--observe"' in source)==is_test
                assert ('"--event-burst"' in source)==is_test
    assert sorted(flight)==['production','test'],flight
    analysis='not run on this host'
    if analyze:
        run=subprocess.run(['cppcheck','--project='+str(build/'compile_commands.json'),'--file-filter=*fsw/src/*',
            '--inline-suppr','--enable=warning,style,performance,portability','--error-exitcode=1','--suppress=missingIncludeSystem'],text=True,capture_output=True)
        output.mkdir(parents=True,exist_ok=True)
        (output/'cppcheck.txt').write_text(run.stdout+run.stderr)
        assert run.returncode==0,run.stdout+run.stderr
        analysis='pass'
    result={'result':'pass','recordedAt':datetime.now(timezone.utc).isoformat(),'sourceHashes':hashes,
            'checks':['No application heap/dynamic task/queue or alternate IPC calls',
                      'Static allocation enabled; dynamic allocation and mutexes disabled',
                      'All application translation units use -Wall -Wextra -Werror',
                      'Preprocessed production excludes injection activation and observer; test includes both'],
            'cppcheck':analysis}
    output.mkdir(parents=True,exist_ok=True)
    (output/'inspection.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'inspection':'pass','cppcheck':analysis}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--skip-analysis',action='store_true')
    a=p.parse_args();check(a.build.resolve(),a.output.resolve(),not a.skip_analysis)
