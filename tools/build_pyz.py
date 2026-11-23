"""Build dist/eval-coach.pyz, dist/eval-coach.cmd, dist/eval-coach.command and dist/eval-coach-mac.zip.

dist/eval-coach.cmd is packaging/launcher.cmd followed by the .pyz bytes: one file
that finds or installs Python, then runs the app from itself. dist/eval-coach.command
is the same for a Mac (packaging/launcher.sh), and dist/eval-coach-mac.zip holds it
with the executable bit set so a double-click works. The pinned runtime values in both
launchers are stamped from packaging/runtime-manifest.json.

Usage:
    python tools/build_pyz.py            build all of them
    python tools/build_pyz.py --smoke    build them, then start each launcher the system can
                                         run and check that static files and the kit load
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipapp
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "dist" / "eval-coach.pyz"
LAUNCHER_SOURCE = ROOT / "packaging" / "launcher.cmd"
LAUNCHER_TARGET = ROOT / "dist" / "eval-coach.cmd"
LAUNCHER_MARKER = b"rem ===== eval-coach.pyz follows =====\r\n"
MAC_LAUNCHER_SOURCE = ROOT / "packaging" / "launcher.sh"
MAC_LAUNCHER_TARGET = ROOT / "dist" / "eval-coach.command"
MAC_LAUNCHER_MARKER = b"# ===== eval-coach.pyz follows =====\n"
MAC_ZIP_TARGET = ROOT / "dist" / "eval-coach-mac.zip"
MANIFEST = ROOT / "packaging" / "runtime-manifest.json"
EMBEDDED_PYTHON = ROOT / "spikes" / "phase0-preflight" / "runtime" / "python-embed-3.13.17-nopth" / "python.exe"


def _include(path):
    return "__pycache__" not in path.parts and path.suffix != ".pyc"


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def assemble_launcher(script_bytes, pyz_bytes):
    """The launcher script, which ends with the marker line, followed by the app archive."""
    if not script_bytes.endswith(LAUNCHER_MARKER):
        raise ValueError("the launcher script must end with the marker line")
    return script_bytes + pyz_bytes


def assemble_mac_launcher(script_bytes, pyz_bytes):
    """The Mac launcher script, which must be LF-only and end with its marker line, followed by the app archive."""
    if b"\r" in script_bytes:
        raise ValueError("the Mac launcher script must use LF line endings")
    if not script_bytes.endswith(MAC_LAUNCHER_MARKER):
        raise ValueError("the Mac launcher script must end with the marker line")
    return script_bytes + pyz_bytes


def _stamp(script, pattern, value, name):
    """Replace the quoted value of one pinned variable; fail if the variable is not there exactly once."""
    regex = re.compile(pattern.replace("{name}", re.escape(name)), re.M)
    if len(regex.findall(script)) != 1:
        raise ValueError(f"the launcher must set {name} exactly once")
    return regex.sub(lambda m: m.group(1) + value + m.group(3), script)


def stamp_cmd(script_bytes, manifest):
    """launcher.cmd with its Python pin taken from the manifest."""
    python = manifest["windows"]["python"]
    script = script_bytes.decode("ascii")
    for name, key in (("EC_PY_VERSION", "version"), ("EC_PY_SHA256", "sha256"), ("EC_PY_URL", "url")):
        script = _stamp(script, r'^(set "{name}=)(.*?)(")(?=\r?$)', python[key], name)
    return script.encode("ascii")


def stamp_sh(script_bytes, manifest):
    """launcher.sh with its Python pins taken from the manifest."""
    python = manifest["mac"]["python"]
    script = script_bytes.decode("ascii")
    values = {"EC_PY_VERSION": python["version"], "EC_PY_RELEASE": python["release"]}
    for chip, prefix in (("arm64", "EC_PY_ARM64"), ("x86_64", "EC_PY_X64")):
        values[prefix + "_URL"] = python[chip]["url"]
        values[prefix + "_SHA256"] = python[chip]["sha256"]
        values[prefix + "_BYTES"] = str(python[chip]["download_bytes"])
    for name, value in values.items():
        script = _stamp(script, r'^({name}=")(.*?)(")(?=$)', value, name)
    return script.encode("ascii")


def build_mac_zip(command_bytes, target=MAC_ZIP_TARGET):
    """A zip that holds only eval-coach.command, with mode 0755 so a double-click runs it."""
    info = zipfile.ZipInfo("eval-coach.command", date_time=(2026, 1, 1, 0, 0, 0))
    info.create_system = 3  # Unix, so the mode bits below are read
    info.external_attr = 0o100755 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(info, command_bytes)


def build():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(str(ROOT / "app"), str(TARGET), main="eval_coach.__main__:main",
                          filter=_include, compressed=True)
    pyz = TARGET.read_bytes()
    manifest = load_manifest()
    LAUNCHER_TARGET.write_bytes(assemble_launcher(stamp_cmd(LAUNCHER_SOURCE.read_bytes(), manifest), pyz))
    MAC_LAUNCHER_TARGET.write_bytes(
        assemble_mac_launcher(stamp_sh(MAC_LAUNCHER_SOURCE.read_bytes(), manifest), pyz))
    build_mac_zip(MAC_LAUNCHER_TARGET.read_bytes())
    return TARGET


def _request(url, method="GET", token=None, body=None):
    headers = {}
    data = None
    if token:
        headers["X-Eval-Token"] = token
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def smoke(command, archive=TARGET):
    """Start the app from `command` (a list that ends with the file to run) and walk its main routes."""
    temp = Path(tempfile.mkdtemp(prefix="eval-coach-smoke-"))
    cli = "cmd.exe" if sys.platform == "win32" else "sh"
    proc = subprocess.Popen(list(command) + ["--no-browser", "--port", "0", "--home", str(temp / "home")],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=(sys.platform != "win32"))
    found = {}

    def read_url():
        # A launcher prints its own status lines before the app prints the URL.
        for line in proc.stdout:
            found["line"] = line
            if "?t=" in line:
                break

    reader = threading.Thread(target=read_url, daemon=True)
    reader.start()
    reader.join(30)
    try:
        match = re.search(r"http://127\.0\.0\.1:(\d+)/\?t=(\S+)", found.get("line", ""))
        if not match:
            print("FAIL: no URL printed:", found.get("line"))
            return 1
        base = f"http://127.0.0.1:{match.group(1)}"
        token = match.group(2)
        print("URL printed:", match.group(0).split("?")[0] + "?t=<token>")

        status, page = _request(base + "/")
        print("GET / ->", status, len(page), "bytes")
        if status != 200:
            print("FAIL: static index not served from the archive")
            return 1

        project = temp / "project"
        status, raw = _request(base + "/api/setup", "POST", token,
                               {"project_path": str(project), "cli_command": cli, "starter": "northwind"})
        body = json.loads(raw)
        print("POST /api/setup ->", status, "ok =", body.get("ok"))
        if status != 200 or not body.get("ok"):
            print("FAIL:", raw[:500])
            return 1

        expected = [project / "prompt-v0.md", project / "test-cases.md",
                    project / "skills" / "build-eval-script" / "SKILL.md",
                    project / "skills" / "make-eval-fixtures" / "SKILL.md",
                    project / "skills" / "build-promptfoo-config" / "SKILL.md"]
        missing = [str(p) for p in expected if not p.is_file()]
        if missing:
            print("FAIL: kit files not written:", missing)
            return 1
        print("Kit written from inside the archive:", len(expected), "files checked")

        status, raw = _request(base + "/api/state", token=token)
        state = json.loads(raw)
        print("GET /api/state ->", status, "steps:", [s["id"] for s in state["steps"]])
        status, raw = _request(base + "/api/quit", "POST", token, {})
        print("POST /api/quit ->", status)
        proc.wait(timeout=15)
        print("Process exit code:", proc.returncode)
        return 0 if proc.returncode == 0 else 1
    finally:
        _stop_everything(proc)
        shutil.rmtree(temp, ignore_errors=True)


def _stop_everything(proc):
    """End the launcher and the app it started. Killing only the launcher would leave the app listening."""
    if sys.platform == "win32":
        if proc.poll() is None:
            taskkill = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "taskkill.exe")
            try:
                subprocess.run([taskkill, "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=15)
            except (OSError, subprocess.SubprocessError):
                pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # the smoke command runs in its own process group
        except OSError:
            pass
    if proc.poll() is None:
        proc.kill()
    proc.wait(10)


def check_mac_files():
    """Checks of the Mac files that need no Mac: the launcher's shape, and the zip's mode bit and contents."""
    data = MAC_LAUNCHER_TARGET.read_bytes()
    script, marker, archive = data.partition(MAC_LAUNCHER_MARKER)
    problems = []
    if not script.startswith(b"#!/bin/bash\n"):
        problems.append("the Mac launcher does not start with #!/bin/bash")
    if marker != MAC_LAUNCHER_MARKER or not archive.startswith(b"PK"):
        problems.append("the app archive does not follow the marker line")
    if b"\r" in script:
        problems.append("the Mac launcher script has CR characters")
    with zipfile.ZipFile(MAC_ZIP_TARGET) as bundle:
        names = bundle.namelist()
        if names != ["eval-coach.command"]:
            problems.append(f"the Mac zip holds {names}, not only eval-coach.command")
        else:
            mode = (bundle.getinfo(names[0]).external_attr >> 16) & 0o777
            if mode != 0o755:
                problems.append(f"eval-coach.command has mode {oct(mode)} in the zip, not 0o755")
            if bundle.read(names[0]) != data:
                problems.append("the zip does not hold the built eval-coach.command")
    for problem in problems:
        print("FAIL:", problem)
    return 0 if not problems else 1


def smoke_commands(python):
    """(file, command) pairs this system can start: every launcher on Windows, the Mac launcher itself on a Mac."""
    if sys.platform == "darwin":
        return [(TARGET, [sys.executable, str(TARGET)]), (MAC_LAUNCHER_TARGET, ["/bin/bash", str(MAC_LAUNCHER_TARGET)])]
    return [(path, [str(python), str(path)]) for path in (TARGET, LAUNCHER_TARGET, MAC_LAUNCHER_TARGET)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--python", default=str(EMBEDDED_PYTHON) if EMBEDDED_PYTHON.is_file() else sys.executable)
    args = parser.parse_args()
    target = build()
    print("Built", target, target.stat().st_size, "bytes")
    for built in (LAUNCHER_TARGET, MAC_LAUNCHER_TARGET, MAC_ZIP_TARGET):
        print("Built", built, built.stat().st_size, "bytes")
    if args.smoke:
        if check_mac_files() != 0:
            return 1
        print("Mac launcher shape and zip checked")
        for archive, command in smoke_commands(args.python):
            print("Smoke check:", archive.name)
            if smoke(command, archive) != 0:
                print("FAIL:", archive.name)
                return 1
        print("Smoke checks passed:", ", ".join(path.name for path, _ in smoke_commands(args.python)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
