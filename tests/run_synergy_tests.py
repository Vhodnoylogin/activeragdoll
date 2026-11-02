"""Compile the actual production service and a C11 ABI consumer, outside Git.
No Skyrim, Havok headers, plugin install or game start is performed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,required=True)
    args=parser.parse_args(); output=args.build_dir.resolve()
    if output==ROOT or ROOT in output.parents or any((p/'.git').exists() for p in (output,*output.parents)):
        parser.error('Build output must be outside Git')
    output.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('planck_test_helpers',ROOT/'tests/run_lifecycle_regressions.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    environment=helper.msvc_environment() if os.name=='nt' else dict(os.environ)
    compiler=shutil.which('cl' if os.name=='nt' else 'g++',path=environment.get('PATH'))
    if not compiler: raise RuntimeError('C/C++ compiler unavailable')
    sources=[ROOT/p for p in ('include/planck_synergy.h','include/planck_physical_interop.h','include/synergy_runtime.h','src/synergy_runtime.cpp',
        'tests/synergy_c_consumer.c','tests/synergy_runtime_tests.cpp','tests/synergy_native_fixture.cpp.in',
        'tests/run_synergy_tests.py','src/main.cpp','src/pluginapi.cpp')]
    expected=json.loads((ROOT/'tests/official001-sha256.json').read_text())
    for name,digest in expected.items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest,name
    manifest={'sourcePins':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'official001Unchanged':True,
        'nativePluginBuilt':False,'gameStarts':0,'commands':[]}
    def run(command):
        manifest['commands'].append([str(x) for x in command])
        result=subprocess.run(command,cwd=output,env=environment,capture_output=True,text=True,timeout=90)
        print(result.stdout,end='');print(result.stderr,end='')
        if result.returncode:raise RuntimeError('Command failed: '+subprocess.list2cmdline([str(x) for x in command]))
    if os.name=='nt':
        cobj=output/'consumer.obj';executable=output/'synergy_tests.exe'
        run([compiler,'/nologo','/TC','/std:c11','/W4','/WX','/c','/I'+str(ROOT/'include'),ROOT/'tests/synergy_c_consumer.c','/Fo'+str(cobj)])
        run([compiler,'/nologo','/std:c++20','/EHsc','/W4','/WX','/O2','/I'+str(ROOT/'include'),
            ROOT/'src/synergy_runtime.cpp',ROOT/'tests/synergy_runtime_tests.cpp',cobj,'/Fe'+str(executable)])
    else:
        cobj=output/'consumer.o';executable=output/'synergy_tests'
        run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'include'),'-c',ROOT/'tests/synergy_c_consumer.c','-o',cobj])
        run([compiler,'-std=c++20','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-pthread','-I'+str(ROOT/'include'),
            ROOT/'src/synergy_runtime.cpp',ROOT/'tests/synergy_runtime_tests.cpp',cobj,'-o',executable])
    run([executable])
    native=(ROOT/'tests/synergy_native_fixture.cpp.in').read_text()
    main=(ROOT/'src/main.cpp').read_text()
    for marker,signature in [('ACTOR_PUBLICATION','void PublishSynergyActor(Actor* actor)\n{'),
        ('ENDPOINT_RESOLVER','PlanckStatus ResolveSynergyEndpoint(PlanckToken owner,PlanckToken lease,const PlanckEndpoint& endpoint,\n    PlanckEndpointVisitor visitor,void* context)\n{'),
        ('CLUTTER_HIT','    void ApplyPhysicsDamage(')]:
        native=native.replace('/*@'+marker+'@*/',helper.extract_function(main,signature))
    begin=main.index('struct SynergyGeometryShape {');end=main.index('void PublishSynergyActor(Actor* actor)\n{',begin)
    native=native.replace('/*@GEOMETRY_NATIVE@*/',main[begin:end])
    generated=output/'native_fixture.cpp';generated.write_text(native)
    manifest['nativeFixtureSha256']=hashlib.sha256(generated.read_bytes()).hexdigest()
    native_exe=output/('native_fixture.exe' if os.name=='nt' else 'native_fixture')
    if os.name=='nt':
        run([compiler,'/nologo','/std:c++20','/EHsc','/W4','/WX','/O2','/I'+str(ROOT/'include'),generated,
            ROOT/'src/synergy_runtime.cpp','/Fe'+str(native_exe)])
    else:
        run([compiler,'-std=c++20','-Wall','-Wextra','-Werror','-pthread','-I'+str(ROOT/'include'),generated,
            ROOT/'src/synergy_runtime.cpp','-o',native_exe])
    run([native_exe]);manifest['passed']=True
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Evidence: '+str(output/'manifest.json'))
if __name__=='__main__':main()
