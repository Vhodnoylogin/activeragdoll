"""Run additive drive ABI and actual-hook fixtures; no game/installation."""
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
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-dir',required=True,type=Path);args=p.parse_args();out=args.build_dir.resolve()
 if out==ROOT or ROOT in out.parents or any((x/'.git').exists() for x in (out,*out.parents)):p.error('Use external build output')
 out.mkdir(parents=True,exist_ok=True)
 spec=importlib.util.spec_from_file_location('helpers',ROOT/'tests/run_lifecycle_regressions.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 env=helper.msvc_environment() if os.name=='nt' else dict(os.environ)
 compiler=shutil.which('cl' if os.name=='nt' else 'g++',path=env.get('PATH'));assert compiler
 source=(ROOT/'src/main.cpp').read_text();fixture=(ROOT/'tests/drive_native_fixture.cpp.in').read_text()
 for key,signature in [('OUTER_DRIVE','void DriveToPoseHook(hkbRagdollDriver *driver, hkReal deltaTime, const hkbContext &context, hkbGeneratorOutput &generatorOutput)'),('INNER_DRIVE','void hkbRagdollDriver_driveToPose_hkaRagdollRigidBodyController_driveToPose_Hook(hkaRagdollRigidBodyController *_this, hkReal deltaTime, hkQsTransform *poseLocalSpace, const hkQsTransform &worldFromModel, hkaKeyFrameHierarchyUtility::Output *stressOut)')]:
  fixture=fixture.replace('/*@'+key+'@*/',helper.extract_function(source,signature))
 start=source.index('    const bool loosenActorPivots=PlanckSynergy::MayLoosenPivots(');end=source.index(';',start)+1
 fixture=fixture.replace('/*@PIVOT_POLICY@*/',source[start:end])
 assert 'if (loosenActorPivots)' in source
 restore=helper.extract_function(source,'void RestoreAndClearPendingConstraintSnapshot(ActiveRagdoll &ragdoll, hkbRagdollDriver *driver)')
 assert 'if (!ragdoll.originalConstraintPivots.empty())' in restore
 fixture=fixture.replace('/*@RESTORE_CONSTRAINTS@*/',restore)
 pivot_start=source.index('if (loosenActorPivots)',source.index('// Pivots\n'))
 pivot=helper.extract_function(source[pivot_start:],'if (loosenActorPivots)')
 fixture=fixture.replace('/*@GRADUAL_PIVOT@*/',pivot)
 generated=out/'drive_native_fixture.cpp';generated.write_text(fixture)
 cobject=out/('drive_c.obj' if os.name=='nt' else 'drive_c.o');exe=out/('drive_tests.exe' if os.name=='nt' else 'drive_tests')
 commands=[]
 def run(cmd):
  commands.append([str(x) for x in cmd]);r=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,timeout=90);print(r.stdout,end='');print(r.stderr,end='')
  if r.returncode:raise RuntimeError('Command failed: '+subprocess.list2cmdline([str(x) for x in cmd]))
 if os.name=='nt':
  run([compiler,'/nologo','/TC','/std:c11','/W4','/WX','/c','/I'+str(ROOT/'include'),ROOT/'tests/drive_c_consumer.c','/Fo'+str(cobject)])
  run([compiler,'/nologo','/std:c++20','/EHsc','/W4','/WX','/O2','/I'+str(ROOT/'include'),generated,ROOT/'src/synergy_runtime.cpp',cobject,'/Fe'+str(exe)])
 else:
  run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'include'),'-c',ROOT/'tests/drive_c_consumer.c','-o',cobject])
  run([compiler,'-std=c++20','-Wall','-Wextra','-Werror','-pthread','-I'+str(ROOT/'include'),generated,ROOT/'src/synergy_runtime.cpp',cobject,'-o',exe])
 run([exe])
 negatives={
  'no-extrapolation-clamp':('?(std::min)(requested,1.f/hierarchy)', '?requested'),
  'no-weight-restoration':('if(weightsApplied_)controller_.m_bodyData.m_boneWeights=savedWeights_;','if(weightsApplied_){}')}
 native_header=(ROOT/'include/synergy_drive_native.h').read_text()
 negative_results={}
 for name,(old,new) in negatives.items():
  assert old in native_header
  folder=out/name;folder.mkdir(exist_ok=True);(folder/'synergy_drive_native.h').write_text(native_header.replace(old,new))
  negative_exe=folder/('negative.exe' if os.name=='nt' else 'negative')
  if os.name=='nt':run([compiler,'/nologo','/std:c++20','/EHsc','/W4','/WX','/O2','/I'+str(folder),'/I'+str(ROOT/'include'),generated,ROOT/'src/synergy_runtime.cpp',cobject,'/Fe'+str(negative_exe)])
  else:run([compiler,'-std=c++20','-Wall','-Wextra','-Werror','-pthread','-I'+str(folder),'-I'+str(ROOT/'include'),generated,ROOT/'src/synergy_runtime.cpp',cobject,'-o',negative_exe])
  result=subprocess.run([str(negative_exe)],cwd=folder,env=env,capture_output=True,text=True,timeout=20)
  assert result.returncode!=0,'Undetected negative control: '+name
  (folder/'run.log').write_text(result.stdout+result.stderr)
  negative_results[name]={'detected':True,'returnCode':result.returncode}
  print('PASS detected '+name)
 files=['include/planck_drive_api.h','include/synergy_drive_runtime.h','include/synergy_drive_native.h','include/synergy_runtime.h','src/synergy_runtime.cpp','src/main.cpp','src/pluginapi.cpp','tests/drive_c_consumer.c','tests/drive_native_fixture.cpp.in','tests/run_drive_tests.py']
 pins={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
 (out/'manifest.json').write_text(json.dumps({'passed':True,'sourcePins':pins,'generatedFixtureSha256':hashlib.sha256(generated.read_bytes()).hexdigest(),'commands':commands,'negativeControls':negative_results,'gameStarts':0},indent=2)+'\n')
 print('Evidence: '+str(out/'manifest.json'))
if __name__=='__main__':main()
