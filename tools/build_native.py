"""Build the complete native plugin without invoking deployment project hooks.

All SDK inputs are explicit external dependencies. The generated compatibility
overlay changes access visibility, redirects SDK TLS/heap access to the game's
existing wrappers and declares the explicitly initialized build config as an
aggregate. It changes no layout or virtual slots and vendors no SDK files.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
NS = {"p": "http://schemas.microsoft.com/developer/msbuild/2003"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment():
    if shutil.which("cl"):
        return dict(os.environ)
    finder = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    install = subprocess.check_output([str(finder), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
    if not install:
        raise RuntimeError("An x64 MSVC toolchain is required")
    setup = Path(install) / "VC/Auxiliary/Build/vcvars64.bat"
    values = subprocess.check_output(f'cmd.exe /d /s /c ""{setup}" >nul && set"', text=True)
    result = dict(os.environ)
    for line in values.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            result[key.upper()] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path, help="SKSE source root containing common/ and sksevr/")
    parser.add_argument("--havok-root", required=True, type=Path, help="External compatible 2010.2.0-r1 Source/ tree")
    parser.add_argument("--support-library", type=Path, action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents:
        raise RuntimeError("Build output must remain outside the source checkout")
    out.mkdir(parents=True, exist_ok=True)
    sdk, havok = args.sdk_root.resolve(), args.havok_root.resolve()
    version = havok / "Common/Base/Config/hkConfigVersion.h"
    content = version.read_text()
    for suffix, value in (("MAJOR", "2010"), ("MINOR", "2"), ("POINT", "0")):
        if not re.search(r"#define\s+HAVOK_SDK_VERSION_" + suffix + r"\s+" + value + r"\b", content):
            raise RuntimeError("Expected Havok 2010.2.0 declaration tree")
    havok_inputs = {src.relative_to(havok).as_posix(): digest(src) for src in havok.rglob("*") if src.is_file() and src.suffix.lower() in (".h", ".inl")}
    sdk_inputs = {src.relative_to(sdk).as_posix(): digest(src) for folder in ("common", "sksevr") for src in (sdk / folder).rglob("*") if src.is_file() and src.suffix.lower() in (".h", ".inl")}
    havok_key = hashlib.sha256(json.dumps(havok_inputs,sort_keys=True).encode()).hexdigest()[:16]
    sdk_key = hashlib.sha256(json.dumps(sdk_inputs,sort_keys=True).encode()).hexdigest()[:16]
    overlay = out / ("havok-compat-"+havok_key)
    patches = {}
    for src in havok.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in (".h", ".inl"):
            continue
        original = src.read_bytes()
        changed = re.sub(rb"\b(?:private|protected)(\s*):", rb"public\1:", original)
        relative = src.relative_to(havok)
        if relative == Path("Common/Base/Memory/Router/hkMemoryRouter.h"):
            changed = b'#include "RE/sdk_allocator_bridge.h"\n' + changed
            changed = changed.replace(b'return *HK_THREAD_LOCAL_GET(s_memoryRouter);', b'return hkGetMemoryRouter();')
            changed = changed.replace(b'return HK_THREAD_LOCAL_GET(s_memoryRouter);', b'return &hkGetMemoryRouter();')
        if relative == Path("Common/Base/Container/hkContainerAllocators.h"):
            changed = b'#include "RE/sdk_allocator_bridge.h"\n' + changed
            start = changed.index(b'struct hkContainerHeapAllocator')
            end = changed.index(b'struct hkContainerDebugAllocator', start)
            changed = changed[:start] + changed[start:end].replace(b'return s_alloc;', b'return SkyrimGetContainerHeapAllocator();') + changed[end:]
        if relative == Path("Physics/Collide/Shape/Convex/ConvexVertices/hkpConvexVerticesShape.h"):
            # The mods supply all eight fields explicitly. This developer-only
            # aggregate declaration avoids importing an unused SDK constructor.
            changed = changed.replace(b'BuildConfig();', b'')
        target = overlay / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(changed)
        if changed != original:
            patches[relative.as_posix()] = {"original": hashlib.sha256(original).hexdigest(), "accessOverlay": digest(target)}
    sdk_overlay = out / ("sdk-compat-"+sdk_key)
    sdk_patches = {}
    for src in (sdk / "sksevr").rglob("*"):
        if not src.is_file() or src.suffix.lower() not in (".h", ".inl"):
            continue
        relative = src.relative_to(sdk / "sksevr")
        original = src.read_bytes()
        changed = re.sub(rb"\b(?:private|protected)(\s*):", rb"public\1:", original) if relative == Path("skse64/GameTypes.h") else original
        target = sdk_overlay / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(changed)
        if changed != original:
            sdk_patches[relative.as_posix()] = {"original": hashlib.sha256(original).hexdigest(), "accessOverlay": digest(target)}
    env = environment()
    compiler = shutil.which("cl", path=env["PATH"])
    linker = shutil.which("link", path=env["PATH"])
    project_path, = ROOT.glob("*.vcxproj")
    project = ET.parse(project_path).getroot()
    sources = [ROOT / x.attrib["Include"].replace("\\", "/") for x in project.findall(".//p:ClCompile[@Include]", NS)]
    obj = out / "obj"
    obj.mkdir(exist_ok=True)
    flags = ["/nologo", "/std:c++20", "/EHsc", "/MT", "/O2", "/Zi", "/Gy", "/permissive", "/Zc:twoPhase-", "/DWIN32", "/DNDEBUG", "/DNOMINMAX", "/D_WINDOWS", "/D_USRDLL", "/D_ENABLE_EXTENDED_ALIGNED_STORAGE", "/FI" + str(ROOT / "tools/native_prefix.h")]
    flags += ["/I" + str(p) for p in (ROOT / "include", sdk_overlay, sdk, sdk / "sksevr", overlay, havok)]
    commands = []

    def compile_one(src):
        name = src.relative_to(ROOT).as_posix().replace("/", "_")
        target = obj / (name + ".obj")
        argv = [compiler, *flags, "/c", str(src), "/Fo" + str(target), "/Fd" + str(obj / (name + ".pdb"))]
        process = subprocess.run(argv, env=env, cwd=out, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (out / (name + ".log")).write_text(process.stdout, encoding="utf-8")
        return {"source": src.relative_to(ROOT).as_posix(), "command": argv, "exitCode": process.returncode}, target, process.stdout

    failures = []
    objects = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, 8))) as pool:
        for record, target, log in pool.map(compile_one, sources):
            commands.append(record)
            if record["exitCode"]:
                failures.append(record["source"])
                errors = [line for line in log.splitlines() if ": error " in line or "fatal error" in line]
                print(record["source"], *errors[:12], sep="\n", flush=True)
            else:
                objects.append(target)
                print("Compiled", record["source"], flush=True)
    name = project_path.stem
    artifact = out / (name + ".dll")
    link_ok = False
    if not failures and not args.compile_only:
        if not args.support_library:
            raise RuntimeError("Supply explicit x64 /MT SKSE support libraries")
        libraries = [p.resolve() for p in args.support_library]
        for library in libraries:
            if not library.is_file():
                raise RuntimeError("Missing support library: " + str(library))
        argv = [linker, "/NOLOGO", "/DLL", "/DEBUG", "/OPT:REF", "/OPT:ICF", "/DEF:" + str(ROOT / "exports.def"), "/OUT:" + str(artifact), *map(str, objects), *map(str, libraries), "winmm.lib", "d3dcompiler.lib", "kernel32.lib", "user32.lib", "advapi32.lib", "shell32.lib", "ole32.lib", "comdlg32.lib"]
        process = subprocess.run(argv, env=env, cwd=out, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (out / "link.log").write_text(process.stdout, encoding="utf-8")
        commands.append({"command": argv, "exitCode": process.returncode})
        link_ok = process.returncode == 0
        print(process.stdout[-20000:], flush=True)
    pins = {p.relative_to(ROOT).as_posix(): digest(p) for folder in ("src", "include", "tools") for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".h", ".cpp", ".py")}
    pins.update({p.relative_to(ROOT).as_posix():digest(p) for p in (project_path,ROOT/"exports.def")})
    support_manifests={}
    for library in args.support_library:
        support_manifest=library.resolve().parent/"manifest.json"
        if support_manifest.is_file():
            support_manifests[str(support_manifest)]=digest(support_manifest)
    manifest = {"project": name, "sourceSha256": pins, "sdkHeaderSha256":sdk_inputs,"havokHeaderSha256":havok_inputs,"sdkPrefixSha256": digest(sdk / "common/IPrefix.h"), "havokVersionSha256": digest(version), "havokCompatibilityOverlay": patches, "sdkAccessOnlyPatches": sdk_patches, "commands": commands, "failedSources": failures, "nativePluginBuilt": link_ok, "compileOnly": args.compile_only, "postBuildEventsInvoked": False, "gameStarts": 0, "supportSourceManifests":support_manifests,"supportLibraries": {str(p.resolve()): digest(p.resolve()) for p in args.support_library}}
    if link_ok:
        manifest["artifact"] = {"path": str(artifact), "sha256": digest(artifact), "bytes": artifact.stat().st_size}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 1 if failures or (not args.compile_only and not link_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
