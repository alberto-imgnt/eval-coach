"""Runs check.py directly and turns its output into a RunResult."""
from __future__ import annotations

import os
import subprocess
import sys

from .parsers import CheckerOutputError, parse_checker_output

TIMEOUT_SECONDS = 30
RAW_LIMIT = 200_000
CREATE_NO_WINDOW = 0x08000000


def _basename(path):
    return path.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _result(ok, exit_code, error, raw, files):
    return {"ok": ok, "exit_code": exit_code, "error": error, "raw": raw, "files": files}


def run_checker(project, files, timeout=TIMEOUT_SECONDS, env=None):
    """Run `python check.py <files>` in project and return a RunResult dict.

    `env` is the CLI environment (PATH and npm/promptfoo variables); None uses this process's.
    """
    env = dict(env if env is not None else os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run([sys.executable, "check.py"] + list(files), cwd=str(project),
                              timeout=timeout, capture_output=True, stdin=subprocess.DEVNULL,
                              env=env, creationflags=flags)
    except subprocess.TimeoutExpired:
        return _result(False, -1, f"check.py did not finish within {timeout} seconds.", "", [])
    except OSError as exc:
        return _result(False, -1, f"check.py could not be started: {exc}", "", [])

    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    raw = (out + ("\n" + err if err.strip() else ""))[:RAW_LIMIT]

    if proc.returncode not in (0, 1):
        return _result(False, proc.returncode,
                       f"check.py stopped with exit code {proc.returncode}, so its result "
                       "cannot be trusted. Exit codes 0 and 1 are the normal ones.",
                       raw, [])
    try:
        parsed = parse_checker_output(out)
    except CheckerOutputError as exc:
        return _result(False, proc.returncode,
                       f"The app could not read the checker's output: {exc}", raw, [])

    reported = {_basename(f["file"]) for f in parsed}
    missing = [f for f in files if _basename(f) not in reported]
    if missing:
        return _result(False, proc.returncode,
                       "The checker did not report on: " + ", ".join(missing), raw, parsed)
    return _result(True, proc.returncode, None, raw, parsed)


def find_file(result, name):
    """The section of a RunResult for the file with this basename, or None."""
    if not result:
        return None
    wanted = name.lower()
    for item in result.get("files", []):
        if _basename(item["file"]) == wanted:
            return item
    return None
