import os
import re
import shutil
import subprocess
from pathlib import Path

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
