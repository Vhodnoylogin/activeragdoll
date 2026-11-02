"""Compile actual PLANCK classification and HIGGS native attribution contracts; no game."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build-dir',required=True,type=Path);args=parser.parse_args()
    out=args.build_dir.resolve()
    if out==ROOT or ROOT in out.parents or any((p/'.git').exists() for p in (out,*out.parents)):parser.error('Use an external output directory')
    out.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('helpers',ROOT/'tests/run_lifecycle_regressions.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    env=helper.msvc_environment() if os.name=='nt' else dict(os.environ)
    compiler=shutil.which('cl' if os.name=='nt' else 'g++',path=env.get('PATH'));assert compiler
    main_source=(ROOT/'src/main.cpp').read_text()
    functions=['IsLeftRigidBody','IsPlayerWeaponRigidBody','IsPlayerHandRigidBody','IsHeldRigidBody','IsHiggsRigidBody']
    actual='\n'.join(helper.extract_function(main_source,'inline bool '+name+'(hkpRigidBody *rigidBody)') for name in functions)
    source=(ROOT/'tests/hand_parts_fixture.cpp.in').read_text().replace('/*@CLASSIFICATION@*/',actual)
    generated=out/'hand_parts_fixture.cpp';generated.write_text(source)
    exe=out/('hand_parts.exe' if os.name=='nt' else 'hand_parts')
    cobj=out/('consumer.obj' if os.name=='nt' else 'consumer.o')
    ccommand=[compiler,'/nologo','/TC','/std:c11','/W4','/WX','/c','/I'+str(ROOT/'include'),ROOT/'tests/hand_parts_c_consumer.c','/Fo'+str(cobj)] if os.name=='nt' else ['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'include'),'-c',ROOT/'tests/hand_parts_c_consumer.c','-o',cobj]
    command=[compiler,'/nologo','/std:c++20','/EHsc','/W4','/WX','/O2','/I'+str(ROOT/'include'),generated,cobj,'/Fe'+str(exe)] if os.name=='nt' else [compiler,'-std=c++20','-Wall','-Wextra','-Werror','-pthread','-I'+str(ROOT/'include'),generated,cobj,'-o',exe]
    for name,cmd in [('c-compile',ccommand),('compile',command),('run',[exe])]:
        result=subprocess.run([str(x) for x in cmd],cwd=out,env=env,capture_output=True,text=True,timeout=90)
        (out/(name+'.log')).write_text(result.stdout+result.stderr);print(result.stdout,end='');print(result.stderr,end='')
        if result.returncode:raise RuntimeError(name+' failed')
    files=['include/synergy_hand_parts.h','include/higgs_contracts/higgshandapi.h','include/higgs_contracts/higgshandparts.h','include/higgs_contracts/higgshandpartsnative.h','src/main.cpp','tests/hand_parts_c_consumer.c','tests/hand_parts_fixture.cpp.in','tests/run_hand_parts_tests.py']
    pins={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    (out/'manifest.json').write_text(json.dumps({'passed':True,'sourcePins':pins,'generatedSha256':hashlib.sha256(generated.read_bytes()).hexdigest(),'gameStarts':0},indent=2)+'\n')
    print('Evidence: '+str(out/'manifest.json'))

if __name__=='__main__':main()
