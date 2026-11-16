"""Build dist/eval-coach.pyz with the stdlib zipapp module.

Usage:
    python tools/build_pyz.py            build the archive
    python tools/build_pyz.py --smoke    build it, then start it on the embedded Python
                                         and check that static files and the kit load
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "dist" / "eval-coach.pyz"
EMBEDDED_PYTHON = ROOT / "spikes" / "phase0-preflight" / "runtime" / "python-embed-3.13.17-nopth" / "python.exe"


def _include(path):
    return "__pycache__" not in path.parts and path.suffix != ".pyc"


def build():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(str(ROOT / "app"), str(TARGET), main="eval_coach.__main__:main",
                          filter=_include, compressed=True)
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


def smoke(python):
    temp = Path(tempfile.mkdtemp(prefix="eval-coach-smoke-"))
    proc = subprocess.Popen([str(python), str(TARGET), "--no-browser", "--port", "0",
                             "--home", str(temp / "home")],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    found = {}

    def read_url():
        found["line"] = proc.stdout.readline()

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
                               {"project_path": str(project), "cli_command": "cmd.exe", "starter": "northwind"})
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
        if proc.poll() is None:
            proc.kill()
            proc.wait(10)
        shutil.rmtree(temp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--python", default=str(EMBEDDED_PYTHON))
    args = parser.parse_args()
    target = build()
    print("Built", target, target.stat().st_size, "bytes")
    if args.smoke:
        return smoke(args.python)
    return 0


if __name__ == "__main__":
    sys.exit(main())
