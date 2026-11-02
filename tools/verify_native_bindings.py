"""Check PE metadata and run SDK numerical code without loading the game plugin.

Requires pefile. Does not execute Skyrim, decrypt its text, or load the plugin DLL.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
sys.dont_write_bytecode = True
import pefile
from build_native import environment, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-build", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    args = parser.parse_args()
    output = args.native_build.resolve()
    native = json.loads((output / "manifest.json").read_text())
    if not native["nativePluginBuilt"]:
        raise RuntimeError("A fully linked native build is required")
    for name in ("src/RE/sdk_bindings.cpp", "src/RE/offsets.cpp", "tools/native_prefix.h"):
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=native["sourceSha256"][name]:
            raise RuntimeError("Stale compiled input: "+name)
    pe = pefile.PE(str(args.image), fast_load=True)
    expected = [(0x15DA7B8,1,0xA01800),(0x15DA7B8,2,0xA01810),(0x17ADF48,13,0xACC460),(0x17ADF48,14,0xACC470)]
    checks=[]
    for table,slot,target in expected:
        actual,=struct.unpack("<Q",pe.get_data(table+8*slot,8))
        if actual-pe.OPTIONAL_HEADER.ImageBase!=target:
            raise RuntimeError("Unexpected game vtable target")
        section=pe.get_section_by_rva(target)
        if section is None or not section.Characteristics&0x20000000:
            raise RuntimeError("Non-executable native binding target")
        checks.append({"tableRva":hex(table),"slot":slot,"targetRva":hex(target),"instructionVerified":False})
    source=output/"sdk-numerical-probe.cpp"
    source.write_text('''#include "RE/offsets.h"
#include <Common/Base/Types/Color/hkColor.h>
#include <cstdio>
#include <type_traits>
static_assert(!std::is_reference_v<decltype(min(1.f,2.f))>);
static_assert(!std::is_reference_v<decltype(max(1,2))>);
int main(int count,char** args){
    if(count!=2||min(-2.f,3.)!=-2.||max(2,3.f)!=3.f)return 1;
    if(static_cast<unsigned>(hkColor::rgbFromChars(1,2,3,4))!=0x04010203u)return 2;
    if(hkColor::rgbFromChars(0,0,0,0)!=0)return 3;
    FILE* out=nullptr;if(fopen_s(&out,args[1],"wb")||!out)return 4;
    const auto written=fwrite(g_vectorConstants,16,HK_QUADREAL_END,out);fclose(out);
    return written==36?0:5;
}
''',encoding="utf-8")
    previous=next(record["command"] for record in native["commands"] if record.get("source")=="src/RE/sdk_bindings.cpp")
    prefix=previous[:previous.index("/c")]
    obj=output/"sdk-numerical-probe.obj"
    env=environment()
    command=prefix+["/c",str(source),"/Fo"+str(obj),"/Fd"+str(output/"sdk-numerical-probe.pdb")]
    compile_run=subprocess.run(command,env=env,cwd=output,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (output/"sdk-probe-compile.log").write_text(compile_run.stdout,encoding="utf-8")
    compile_run.check_returncode()
    executable=output/"sdk-numerical-probe.exe"
    linker=shutil.which("link",path=env["PATH"])
    command=[linker,"/NOLOGO","/OPT:REF","/OPT:ICF","/SUBSYSTEM:CONSOLE","/OUT:"+str(executable),str(obj),str(output/"obj/src_RE_sdk_bindings.cpp.obj"),str(output/"obj/src_RE_offsets.cpp.obj"),*native["supportLibraries"].keys(),"kernel32.lib","user32.lib","advapi32.lib","shell32.lib","comdlg32.lib","ole32.lib"]
    link_run=subprocess.run(command,env=env,cwd=output,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (output/"sdk-probe-link.log").write_text(link_run.stdout,encoding="utf-8")
    link_run.check_returncode()
    data=output/"sdk-numerics.bin"
    subprocess.run([str(executable),str(data)],cwd=output,env=env,check=True)
    if data.read_bytes()!=pe.get_data(0x177CF50,36*16):
        raise RuntimeError("SDK enum-ordered numerical constants differ from the pinned game image")
    module=pefile.PE(native["artifact"]["path"])
    if hashlib.sha256(Path(native["artifact"]["path"]).read_bytes()).hexdigest()!=native["artifact"]["sha256"]:
        raise RuntimeError("Native DLL no longer matches its build manifest")
    exports=[entry.name.decode() for entry in module.DIRECTORY_ENTRY_EXPORT.symbols if entry.name]
    if module.FILE_HEADER.Machine!=0x8664 or not {"SKSEPlugin_Load","SKSEPlugin_Query"}.issubset(exports):
        raise RuntimeError("Unexpected native machine or missing SKSE entry points")
    imports=[entry.dll.decode() for entry in module.DIRECTORY_ENTRY_IMPORT]
    if any("havok" in name.lower() for name in imports):
        raise RuntimeError("Unexpected external Havok runtime dependency")
    result={"imageSha256":hashlib.sha256(args.image.read_bytes()).hexdigest(),"nativeDllSha256":native["artifact"]["sha256"],"vtableTargets":checks,"mathematicalBytesCompared":576,"numericalProbePassed":True,"exports":exports,"imports":imports,"gameStarts":0,"pluginLoaded":False,"limits":"PE/rdata/layout/compiler evidence; not game execution or instruction-level verification"}
    (output/"sdk-binding-verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("PASS native metadata, four exact vtable targets, 576 numerical bytes and production numerical probe; no plugin/game load")


if __name__=="__main__":main()
