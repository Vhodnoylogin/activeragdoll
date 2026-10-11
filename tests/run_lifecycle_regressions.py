"""Compile actual PLANCK lifecycle functions with the adjacent fake-engine fixture.

python tests/run_lifecycle_regressions.py --build-dir <external-directory>
No SKSE/Havok layout, native hook installation or game runtime is qualified here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = {
    "MOVEMENT_LOOKUP": "bool IsActorMovementRestricted(Actor *actor)",
    "LOOK_AT_LOOKUP": "bool IsActorLookAtDisabled(Actor *actor)",
    "RESET_OBJECTS": "void ResetObjects()",
    "DISPATCH_HIT": "void ScriptEventSourceHolder_DispatchHitEventFromHitData_DispatchHitEvent_Hook(",
}


def extract_function(source, signature):
    """Read a complete function including nested blocks, ignoring comments/literals."""
    start = source.index(signature)
    opening = source.index("{", start)
    tokens = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    depth = 0
    for token in tokens.finditer(source, opening):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[start:token.end()]
    raise RuntimeError(f"Unterminated production function: {signature}")


def msvc_environment():
    if shutil.which("cl"):
        return dict(os.environ)
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    install = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
    if not install:
        raise RuntimeError("An x64 MSVC C++ toolchain is required")
    vcvars = Path(install) / "VC/Auxiliary/Build/vcvars64.bat"
    command = f'cmd.exe /d /s /c ""{vcvars}" >nul && set"'
    environment = dict(os.environ)
    for line in subprocess.check_output(command, text=True).splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            environment[key.upper()] = value
    return environment


def run(arguments, output, environment=None):
    print("+", subprocess.list2cmdline([str(arg) for arg in arguments]), flush=True)
    subprocess.run([str(arg) for arg in arguments], cwd=output, env=environment, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.build_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("--build-dir must be outside the repository")
    output.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "src/main.cpp").read_text()
    blocks = {name: extract_function(source, signature) for name, signature in FUNCTIONS.items()}
    fixture = (ROOT / "tests/lifecycle_fixture.cpp.in").read_text()
    for name, block in blocks.items():
        marker = f"/*@{name}@*/"
        if fixture.count(marker) != 1:
            raise RuntimeError(f"Missing/duplicate fixture insertion point: {name}")
        fixture = fixture.replace(marker, block)
    # Supplemental integration audit: execution tests below compile the actual
    # helpers/reset/dispatch hook, while engine consumers remain native-unbuilt.
    for signature, helper, container in [
        ("void Character_ModifyMovementData_Hook(", "IsActorMovementRestricted(actor)", "g_actorMoveRestrictions"),
        ("void BSLookAtModifier_modify_Hook(", "IsActorLookAtDisabled(actor)", "g_disableLookAtActors"),
    ]:
        body = extract_function(source, signature)
        if helper not in body or container in body:
            raise RuntimeError(f"Consumer bypasses the locked lookup: {signature}")
    expected = json.loads((ROOT / "tests/official001-sha256.json").read_text())
    for filename, digest in expected.items():
        actual = hashlib.sha256((ROOT / filename).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != digest:
            raise RuntimeError(f"Official001 preservation failed: {filename}")
    print("PASS official001 preservation and supplemental consumer callsite audit", flush=True)
    generated = output / "planck_lifecycle_regressions.cpp"
    generated.write_text(fixture)
    manifest = {
        "production_source": "src/main.cpp",
        "canonical_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "extracted_functions": {name: hashlib.sha256(block.encode()).hexdigest() for name, block in blocks.items()},
        "fixture_sha256": hashlib.sha256((ROOT / "tests/lifecycle_fixture.cpp.in").read_bytes()).hexdigest(),
        "qualification": "C++ production control flow with fake engine; native plugin unbuilt",
    }
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if os.name == "nt":
        environment = msvc_environment()
        compiler = shutil.which("cl", path=environment.get("PATH"))
        if not compiler:
            raise RuntimeError("MSVC environment did not provide cl.exe")
        executable = output / "planck_lifecycle_regressions.exe"
        run([compiler, "/nologo", "/std:c++20", "/EHsc", "/W4", "/WX", "/O2", generated,
             f"/Fe{executable}", "/link", "/MACHINE:X64"], output, environment)
        run([executable], output, environment)
    else:
        executable = output / "planck_lifecycle_regressions"
        run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers",
             "-O2", "-pthread", generated, "-o", executable], output)
        run([executable], output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
