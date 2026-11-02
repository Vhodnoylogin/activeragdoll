"""Execute selected production PLANCK cleanup hooks/tasks with a reset-only epoch.

python tests/run_cleanup_epoch_tests.py --build-dir <new external directory>
No SDK/Havok, full plugin, game, native hook or scheduling qualification is implied.
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
ROOT = Path(__file__).resolve().parents[1]
BASELINE = "986a3e7ca5cb42a01934ba0b957aec36fc0930c7"
FUNCTIONS = {
    "ACTIVE_LOOKUP": "bool IsActiveActor(TESObjectREFR *refr)",
    "GENERIC_JOB": "struct GenericJob",
    "DELAYED_JOB": "struct DelayedJob",
    "QUEUE_DELAYED": "void QueueDelayedJob(",
    "RUN_DELAYED": "void RunDelayedJobs(",
    "RESET_OBJECTS": "void ResetObjects()",
    "CLEANUP_TASK": "struct RemoveNonRagdollRigidBodiesFromWorldTask",
    "EXIT_HOOK": "void ActorProcess_ExitFurniture_RemoveCollision_Hook(",
    "ENTER_HOOK": "void ActorProcess_EnterFurniture_SetWorld_Hook(",
    "GETUP_HOOK": "void GetUpEndHandler_Handle_RemoveCollision_Hook(",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--baseline", default=BASELINE, help="explicit immutable source baseline for untouched constraint functions")
    args = parser.parse_args()
    output = args.build_dir.resolve()
    if output == ROOT or ROOT in output.parents or any((p / ".git").exists() for p in (output, *output.parents)):
        parser.error("--build-dir must be outside Git checkouts")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("--build-dir must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    helper = ROOT / "tests/run_lifecycle_regressions.py"
    spec = importlib.util.spec_from_file_location("cleanup_epoch_helpers", helper)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    pins = [ROOT / p for p in ("src/main.cpp", "include/cleanup_epoch.h", "tests/cleanup_epoch_fixture.cpp.in",
        "tests/official001-sha256.json", "include/planckinterface001.h", "src/planckinterface001.cpp")] + [Path(__file__).resolve(), helper]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in pins}
    source = (ROOT / "src/main.cpp").read_text()
    blocks = {key: helpers.extract_function(source, signature) for key, signature in FUNCTIONS.items()}
    # Observe reset after the actual membership result, outside its shared lock.
    # Production body remains unchanged apart from this test-only scope guard.
    blocks["ACTIVE_LOOKUP"] = blocks["ACTIVE_LOOKUP"].replace("{\n", "{\n    ActiveQueryBoundary queryBoundary;\n", 1)
    baseline_hash = subprocess.check_output(["git", "rev-parse", "--verify", args.baseline + "^{commit}"], cwd=ROOT, text=True).strip()
    baseline = subprocess.check_output(["git", "show", baseline_hash + ":src/main.cpp"], cwd=ROOT, text=True)
    untouched = {}
    for signature in ("void RestoreAndClearPendingConstraintSnapshot(", "bool RemoveRagdollFromWorld("):
        current = helpers.extract_function(source, signature)
        if current != helpers.extract_function(baseline, signature):
            raise RuntimeError("Constraint restoration/removal changed: " + signature)
        untouched[signature] = hashlib.sha256(current.encode()).hexdigest()
    expected = json.loads((ROOT / "tests/official001-sha256.json").read_text())
    for name, digest in expected.items():
        if hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() != digest:
            raise RuntimeError("Official001 changed: " + name)
    template = (ROOT / "tests/cleanup_epoch_fixture.cpp.in").read_text()

    def render(values):
        result = template
        for name, block in values.items():
            marker = "/*@" + name + "@*/"
            if result.count(marker) != 1:
                raise RuntimeError("Missing/duplicate marker: " + name)
            result = result.replace(marker, block)
        return '#include "synergy_runtime.h"\n' + result

    variants = {"current": (render(blocks), None)}
    stale = dict(blocks)
    guard = "        if (!PlanckCleanup::IsCurrent(epoch)) return;\n"
    if guard not in stale["CLEANUP_TASK"]:
        raise RuntimeError("Task stale guard not found")
    stale["CLEANUP_TASK"] = stale["CLEANUP_TASK"].replace(guard, "", 1)
    variants["negative-stale-run"] = (render(stale), "stale queued cleanup reached handle lookup")
    recapture = dict(blocks)
    original = "RemoveNonRagdollRigidBodiesFromWorldTask::Create(handle, epoch)"
    if recapture["ENTER_HOOK"].count(original) != 1:
        raise RuntimeError("Delayed original ticket handoff not found")
    recapture["ENTER_HOOK"] = recapture["ENTER_HOOK"].replace(original,
        "RemoveNonRagdollRigidBodiesFromWorldTask::Create(handle, PlanckCleanup::Capture())")
    variants["negative-recapture"] = (render(recapture), "old delayed cleanup adopted new reset scope")
    late = dict(blocks)
    # Move the capture back after the active check, reproducing old-decision adoption.
    for name in ("EXIT_HOOK", "ENTER_HOOK", "GETUP_HOOK"):
        late[name] = late[name].replace("    const auto epoch = PlanckCleanup::Capture();\n", "", 1)
        condition = "if (refr && IsActiveActor(refr)) {" if name == "GETUP_HOOK" else ("if (IsActiveActor(actor)) {" if name == "ENTER_HOOK" else "if (IsActiveActor(refr)) {")
        if condition not in late[name]:
            raise RuntimeError("Active-query boundary not found: " + name)
        late[name] = late[name].replace(condition, condition + "\n        const auto epoch = PlanckCleanup::Capture();", 1)
    variants["negative-late-capture"] = (render(late), "old active decision adopted post-query reset scope")
    env = helpers.msvc_environment() if os.name == "nt" else dict(os.environ)
    compiler = shutil.which("cl", path=env.get("PATH")) if os.name == "nt" else shutil.which("g++")
    if not compiler:
        raise RuntimeError("Standalone C++ compiler unavailable")
    results = {}
    for name, (cpp, expected_failure) in variants.items():
        directory = output / name
        directory.mkdir()
        generated = directory / "cleanup_fixture.cpp"
        generated.write_text(cpp)
        executable = directory / ("cleanup_fixture.exe" if os.name == "nt" else "cleanup_fixture")
        if os.name == "nt":
            command = [compiler, "/nologo", "/std:c++20", "/EHsc", "/W4", "/WX", "/O2", "/I" + str(ROOT / "include"),
                       str(generated), str(ROOT / "src/synergy_runtime.cpp"), "/Fe:" + str(executable), "/link", "/MACHINE:X64"]
        else:
            command = [compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare", "-O2", "-pthread",
                       "-I" + str(ROOT / "include"), str(generated), str(ROOT / "src/synergy_runtime.cpp"), "-o", str(executable)]
        compiled = subprocess.run(command, cwd=directory, env=env, capture_output=True)
        (directory / "compile.log").write_text((compiled.stdout + compiled.stderr).decode(errors="replace"))
        if compiled.returncode:
            raise RuntimeError(name + " compilation failed: " + str(directory / "compile.log"))
        run = subprocess.run([str(executable)], cwd=directory, capture_output=True, text=True, timeout=30)
        (directory / "run.log").write_text(run.stdout + run.stderr)
        if expected_failure:
            if run.returncode == 0 or expected_failure not in run.stderr:
                raise RuntimeError(name + " negative control did not fail at the expected boundary")
            print("PASS detected " + name)
        elif run.returncode:
            raise RuntimeError(name + " failed: " + str(directory / "run.log"))
        else:
            print(run.stdout, end="")
        results[name] = {"command": command, "runExitCode": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
            "generatedSourceSha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
            "executableSha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
    for p in pins:
        if hashlib.sha256(p.read_bytes()).hexdigest() != hashes[str(p)]:
            raise RuntimeError("Source changed during fixture: " + str(p))
    manifest = {"sourcePins": hashes, "baselineCommit": baseline_hash, "baselineSourceSha256": hashlib.sha256(baseline.encode()).hexdigest(), "untouchedConstraintFunctions": untouched, "results": results,
        "official001Unchanged": True, "gameStarts": 0, "nativePluginLoads": 0,
        "boundary": "Actual selected production tasks, all3 enqueue hooks, delayed queue and ResetObjects with fake engine/task interfaces; test-only private numeric owner exhaustion. Reset-only fence; no same-epoch deactivation, concurrent reset/engine transaction or full Havok lifetime qualification."}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Evidence: " + str(output / "manifest.json"))


if __name__ == "__main__":
    main()
