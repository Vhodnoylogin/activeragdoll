"""Compile external SKSE support libraries from source, without project hooks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
from build_native import environment, NS, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    sdk, out = args.sdk_root.resolve(), args.output.resolve()
    if out == ROOT or ROOT in out.parents or out == sdk or sdk in out.parents:
        raise RuntimeError("Support output must remain outside source and SDK checkouts")
    out.mkdir(parents=True, exist_ok=True)
    stage = out / "source"
    pins = {}
    for src in sdk.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in (".h", ".inl", ".cpp"):
            continue
        # Ignore SDK build output; only the two named source trees participate.
        relative = src.relative_to(sdk)
        if relative.parts[0] not in ("common", "sksevr"):
            continue
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        target.write_bytes(data)
        pins[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    env = environment()
    compiler = shutil.which("cl", path=env["PATH"])
    librarian = shutil.which("lib", path=env["PATH"])
    projects = [("common_vc14", sdk / "common/common_vc14.vcxproj"), ("skse64_common", sdk / "sksevr/skse64_common/skse64_common.vcxproj"), ("sksevr_1_4_15", sdk / "sksevr/skse64/skse64.vcxproj")]
    commands, failed, artifacts = [], [], {}
    for name, project in projects:
        obj = out / name
        obj.mkdir(exist_ok=True)
        sources = [stage / (project.parent / node.attrib["Include"].replace("\\", "/")).resolve().relative_to(sdk) for node in ET.parse(project).getroot().findall(".//p:ClCompile[@Include]", NS)]
        flags = ["/nologo", "/c", "/std:c++20", "/EHsc", "/MT", "/O2", "/Gy", "/permissive", "/Zc:twoPhase-", "/DNDEBUG", "/DNOMINMAX", "/D_WIN32", "/DRUNTIME", "/DRUNTIME_VERSION=0x010400F1", "/DIS_VR", "/DSKSE64_EXPORTS", "/D_ENABLE_EXTENDED_ALIGNED_STORAGE", "/FI" + str(ROOT / "tools/native_prefix.h"), "/I" + str(stage), "/I" + str(stage / "sksevr")]

        def compile_one(src):
            filename = src.stem + ".obj"
            target = obj / filename
            argv = [compiler, *flags, str(src), "/Fo" + str(target)]
            run = subprocess.run(argv, cwd=obj, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            (obj / (src.stem + ".log")).write_text(run.stdout, encoding="utf-8")
            return {"command": argv, "exitCode": run.returncode}, target, run.stdout

        objects = []
        with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, 8))) as pool:
            for record, target, log in pool.map(compile_one, sources):
                commands.append(record)
                if record["exitCode"]:
                    failed.append(str(target))
                    print(*[line for line in log.splitlines() if ": error " in line or "fatal error" in line][:12], sep="\n", flush=True)
                else:
                    objects.append(target)
        if len(objects) == len(sources):
            artifact = out / (name + ".lib")
            argv = [librarian, "/NOLOGO", "/OUT:" + str(artifact), *map(str, objects)]
            run = subprocess.run(argv, cwd=out, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            (obj / "library.log").write_text(run.stdout, encoding="utf-8")
            commands.append({"command": argv, "exitCode": run.returncode})
            if run.returncode:
                failed.append(str(artifact))
            else:
                artifacts[name] = {"sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "sources": len(sources), "path": str(artifact)}
                print("Built", name, len(sources), "source units", flush=True)
    (out / "manifest.json").write_text(json.dumps({"sourceSha256": pins, "commands": commands, "artifacts": artifacts, "failed": failed, "deploymentInvoked": False, "gameStarts": 0}, indent=2) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
