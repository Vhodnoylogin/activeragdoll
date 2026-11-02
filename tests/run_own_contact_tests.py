"""Actual PLANCK own-contact branch + common-point velocity forwarding, read-only fixtures."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
def block(source,needle):
    begin=source.index(needle);start=source.index('{',begin);depth=0
    for i in range(start,len(source)):
        if source[i]=='{':depth+=1
        elif source[i]=='}':
            depth-=1
            if not depth:return source[begin:i+1]
    raise RuntimeError('Unterminated source block '+needle)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build-dir',required=True,type=Path);args=parser.parse_args();out=args.build_dir.resolve()
    if out==ROOT or ROOT in out.parents:parser.error('External output required')
    out.mkdir(parents=True,exist_ok=True);spec=importlib.util.spec_from_file_location('helpers',ROOT/'tests/run_lifecycle_regressions.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);env=helper.msvc_environment();env['PYTHONDONTWRITEBYTECODE']='1';cl=shutil.which('cl',path=env['PATH']);commands=[]
    files=[ROOT/p for p in ['src/main.cpp','src/RE/havok.cpp','include/synergy_own_contact.h','include/higgs_contracts/higgsowncontactnative.h','include/higgs_contracts/higgsowncontact.h','include/higgs_contracts/higgshandapi.h','tests/own_contact_fixture.cpp.in','tests/own_contact_c_consumer.c','tests/run_own_contact_tests.py']];pins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    source=(ROOT/'src/main.cpp').read_text();own=block(source,'        if (isAhiggs && isBhiggs) {');original=subprocess.check_output(['git','show','ea5472aabc8b3d7701ef684c1412f69a6480a7dd:src/main.cpp'],cwd=ROOT,text=True);old=block(original,'        if (isAhiggs && isBhiggs) {')
    removed=('ForwardOwnItemCosmeticContact(', '// A held/equipped mixed pair still follows', '// Cosmetic evidence neither certifies')
    legacy='\n'.join(line for line in own.splitlines() if not any(x in line for x in removed))
    if legacy!=old:raise RuntimeError('Nonadditive legacy own-contact behavior change')
    callback=source[source.index('virtual void contactPointCallback(const hkpContactPointEvent &evnt) override'):];guard=block(callback,'if (evnt.m_contactPointProperties->m_flags & hkContactPointMaterial::FlagEnum::CONTACT_IS_DISABLED ||')
    template=(ROOT/'tests/own_contact_fixture.cpp.in').read_text();template=template.replace('/*@POINT_WRAPPER@*/',block((ROOT/'src/RE/havok.cpp').read_text(),'NiPoint3 hkpRigidBody_getPointVelocity(')).replace('/*@FORWARDER@*/',block(source,'void ForwardOwnItemCosmeticContact(')).replace('/*@ENTRY_GUARD@*/',guard).replace('/*@OWN_BRANCH@*/',own)
    fixture=out/'own_contact.cpp';fixture.write_text(template)
    def run(name,argv,negative=False):
        argv=list(map(str,argv));r=subprocess.run(argv,cwd=out,env=env,capture_output=True);(out/(name+'.log')).write_bytes(r.stdout+r.stderr);commands.append({'name':name,'argv':argv,'exitCode':r.returncode,'negative':negative})
        if (r.returncode==0)==negative:raise RuntimeError(name+' failed; '+str(out/(name+'.log')))
        print(name+': passed',flush=True)
    cobj=out/'consumer.obj';run('c',[cl,'/nologo','/TC','/std:c11','/W4','/WX',f'/I{ROOT/"include"}','/c',ROOT/'tests/own_contact_c_consumer.c',f'/Fo{cobj}'])
    flags=[cl,'/nologo','/std:c++20','/EHsc','/W4','/WX','/O2',f'/I{ROOT/"include"}'];exe=out/'own_contact.exe';run('compile',[*flags,fixture,cobj,f'/Fe{exe}']);run('production',[exe])
    needle='ForwardOwnItemCosmeticContact(evnt,false,false);'
    if template.count(needle)!=1:raise RuntimeError('Mixed-path negative seam changed')
    bad=out/'own_contact_missing_mixed.cpp';bad.write_text(template.replace(needle,'/* negative: missing mixed handoff */'));badexe=out/'own_contact_missing_mixed.exe';run('negative-compile',[*flags,bad,cobj,f'/Fe{badexe}']);run('negative-mixed',[badexe],True)
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=pins[str(p.relative_to(ROOT))] for p in files):raise RuntimeError('Source changed during checks')
    (out/'manifest.json').write_text(json.dumps({'passed':True,'commands':commands,'sourceSha256':pins,'unchangedLegacyOwnBranch':True,'baselineCommit':'ea5472aabc8b3d7701ef684c1412f69a6480a7dd','gameStarts':0,'qualification':'Actual native callback entry guard/own-item branches, paired point-velocity wrapper and copied bridge executed on explicit engine doubles. No full callback/engine/feedback qualification.'},indent=2)+'\n')
if __name__=='__main__':main()
