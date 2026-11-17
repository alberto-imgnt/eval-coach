"""Preflight: dependency checks, consented installs, the CLI working test, and the CLI environment.

Every decision here comes from running a program and reading its exit code and
stdout, or from reading a file. Terminal output is never read.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import project, resources
from . import state as store
from .state import CorruptStateError

ITEM_IDS = ("track", "python", "node", "promptfoo", "cli", "working_test", "project")
PROMPTFOO_ITEMS = ("node", "promptfoo")
TRACKS = ("script", "promptfoo")
STATUSES = ("not_checked", "passed", "failed", "needs_you")

# Pinned values: spikes/phase0-preflight/runtime-manifest.json.
NODE_MIN = (22, 22, 0)
NODE_VERSION = "26.13.0"
NODE_URL = "https://nodejs.org/dist/v26.13.0/node-v26.13.0-win-x64.zip"
NODE_SHA256 = "dcc60d59a0746999f99064a01c020445d54d84228c691cdbf25b49ac3b59150a"
NODE_FOLDER = "node-v26.13.0-win-x64"
NODE_DOWNLOAD_BYTES = 41157375
NODE_NEEDS_BYTES = 200 * 10**6
PROMPTFOO_VERSION = "0.125.1"
PROMPTFOO_CACHE_BYTES = 1050855363
PROMPTFOO_NEEDS_BYTES = 12 * 10**8

CHECK_TIMEOUT = 20
NPX_CHECK_TIMEOUT = 120
DOWNLOAD_MAX_TIME = 900
DOWNLOAD_TIMEOUT = 2800
EXTRACT_TIMEOUT = 300
NPM_TIMEOUT = 1800
SIZE_POLL_SECONDS = 3.0
PUBLISH_SECONDS = 1.0
AI_TEST_SECONDS = 120  # the quiet test's limit when a recipe does not name one
AI_TEST_STOP_SECONDS = 45  # how long to wait for a cancelled quiet test's process to be gone
CREATE_NO_WINDOW = 0x08000000
_SYSTEM32 = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32")
CURL = os.path.join(_SYSTEM32, "curl.exe")
TAR = os.path.join(_SYSTEM32, "tar.exe")
TASKKILL = os.path.join(_SYSTEM32, "taskkill.exe")
CMD = os.path.join(_SYSTEM32, "cmd.exe")
POWERSHELL = os.path.join(_SYSTEM32, "WindowsPowerShell", "v1.0", "powershell.exe")
NPM_NETWORK_RE = re.compile(r"ENOTFOUND|ETIMEDOUT|EAI_AGAIN|ECONN\w*|E403|E407|proxy|network", re.I)
NPM_DISK_RE = re.compile(r"ENOSPC", re.I)

_RECIPE_SHELLS = ("cmd", "powershell", "none")
_MAX_OUTPUT = 200_000


class PreflightError(Exception):
    """A preflight request that cannot be done. The message is shown to the participant."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Result:
    def __init__(self, code=-1, stdout="", stderr="", timed_out=False, cancelled=False, started=True):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.cancelled = cancelled
        self.started = started


class SystemRunner:
    """Runs real programs. Tests replace this with a fake."""

    def run(self, argv, timeout, env=None, cwd=None, on_tick=None, cancel=None):
        flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env, cwd=cwd, creationflags=flags)
        except OSError as exc:
            return Result(code=-1, stderr=str(exc), started=False)
        out, err = bytearray(), bytearray()
        readers = [threading.Thread(target=self._drain, args=(proc.stdout, out), daemon=True),
                   threading.Thread(target=self._drain, args=(proc.stderr, err), daemon=True)]
        for reader in readers:
            reader.start()
        deadline = time.monotonic() + timeout
        timed_out = cancelled = False
        while True:
            try:
                proc.wait(0.5)
                break
            except subprocess.TimeoutExpired:
                pass
            if cancel is not None and cancel.is_set():
                cancelled = True
            elif time.monotonic() > deadline:
                timed_out = True
            if cancelled or timed_out:
                self._kill_tree(proc)
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
            if on_tick is not None:
                on_tick()
        for reader in readers:
            reader.join(5)
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
        return Result(proc.returncode if proc.returncode is not None else -1,
                      bytes(out).decode("utf-8", errors="replace"),
                      bytes(err).decode("utf-8", errors="replace"), timed_out, cancelled)

    @staticmethod
    def _drain(stream, sink):
        try:
            for chunk in iter(lambda: stream.read(65536), b""):
                sink.extend(chunk)
                del sink[:-_MAX_OUTPUT]
        except (OSError, ValueError):
            pass

    @staticmethod
    def _kill_tree(proc):
        try:
            subprocess.run([TASKKILL, "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            proc.kill()

    def which(self, name, path):
        return shutil.which(name, path=path)

    def disk_free(self, path):
        return shutil.disk_usage(str(path)).free


def read_registry_paths():
    """PATH entries a new terminal would get, so a CLI installed a minute ago can be found.

    Read only. Nothing here writes to the registry.
    """
    if sys.platform != "win32":
        return []
    import winreg

    found = []
    for root, key_path in ((winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                           (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(root, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        found.extend(os.path.expandvars(part) for part in str(value).split(os.pathsep) if part.strip())
    return found


def human_bytes(number):
    if number is None:
        return "an unknown amount"
    if number >= 10**9:
        return f"{number / 10**9:.1f} GB"
    return f"{number / 10**6:.0f} MB"


def parse_node_version(text):
    """A (major, minor, patch) tuple from `node --version` output, or None."""
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(n) for n in match.groups()) if match else None


def node_is_new_enough(version):
    return version is not None and version >= NODE_MIN


def _read_decoded(path):
    """File text, tolerating the UTF-16 a Windows shell redirect writes. None if absent."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def _is_store_folder(entry):
    return "\\microsoft\\windowsapps" in entry.lower()


def _without_store(path_value):
    return os.pathsep.join(p for p in path_value.split(os.pathsep) if not _is_store_folder(p))


def _unlink(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def _rmtree(path):
    if not Path(path).exists():
        return
    project.clear_dir(path)
    shutil.rmtree(str(path), ignore_errors=True)


def _dir_size(path):
    total = 0
    for folder, _, files in os.walk(str(path)):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass
    return total


class Job:
    def __init__(self, kind, label):
        self.kind = kind
        self.label = label
        self.running = True
        self.done_bytes = 0
        self.total_bytes = None
        self.detail = ""
        self.cancel = threading.Event()
        self.thread = None

    def view(self):
        percent = None
        if self.total_bytes:
            percent = min(100, int(self.done_bytes * 100 / self.total_bytes))
        return {"kind": self.kind, "label": self.label, "running": self.running, "done_bytes": self.done_bytes,
                "total_bytes": self.total_bytes, "percent": percent, "detail": self.detail}


class _AiTest:
    """One quiet background test of the chosen AI. `state` is running, passed or needs_you."""

    def __init__(self, command):
        self.command = command
        self.state = "running"
        self.cancel = threading.Event()
        self.thread = None


class Preflight:
    def __init__(self, home, terminal, publish=None, runner=None, registry_paths=read_registry_paths,
                 python_path=None, paths_provider=None, custom_ai=False):
        self.custom_ai = bool(custom_ai)
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.terminal = terminal
        self.publish = publish or (lambda: None)
        self.runner = runner or SystemRunner()
        self.registry_paths = registry_paths
        self.python_path = python_path or sys.executable
        self.paths_provider = paths_provider or (lambda: None)
        self.content = json.loads(resources.read_text("content/preflight.json"))
        self.recipes = self._load_recipes()
        self.path = self.home / "preflight.json"
        self._lock = threading.RLock()
        self._job = None
        self._ai_test = None
        self._last_publish = 0.0
        self.load_problem = False
        self._found_commands = []
        self._data = self._load()
        self._detect_ais()  # saved results can reopen setup on the AI choice without a fresh check

    # --- persistence -------------------------------------------------------

    def _load_recipes(self):
        override = self.home / "cli-recipes.json"
        if override.is_file():
            try:
                data = store.read_json(override)
                self._validate_recipes(data)
                return data["recipes"]
            except (CorruptStateError, OSError, KeyError, TypeError, ValueError):
                pass
        data = json.loads(resources.read_text("content/cli-recipes.json"))
        self._validate_recipes(data)
        return data["recipes"]

    @staticmethod
    def _validate_recipes(data):
        if not isinstance(data.get("recipes"), list) or not data["recipes"]:
            raise ValueError("no recipes")
        for recipe in data["recipes"]:
            if not isinstance(recipe.get("id"), str) or recipe.get("shell") not in _RECIPE_SHELLS:
                raise ValueError("bad recipe")

    def _new_data(self):
        m = self.content["messages"]["not_checked"]
        items = {item: {"status": "not_checked", "detail": m["detail"], "next": m["next"]} for item in ITEM_IDS}
        data = {"version": 1, "track": "script", "cli_command": "", "test_passed_command": "",
                "test_passed_quietly": False,
                "recipe_ran": False, "ran_once": False, "setup_skipped": False, "items": items}
        self._apply_track_item(data)
        return data

    def _load(self):
        try:
            data = store.read_json(self.path)
        except FileNotFoundError:
            data = None
        except (CorruptStateError, OSError):
            data = None
            self.load_problem = True
        default = self._new_data()
        if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
            return default
        for key, value in default.items():
            if key != "items":
                data.setdefault(key, value)
        for item in ITEM_IDS:
            saved = data["items"].get(item)
            if isinstance(saved, dict) and saved.get("status") in STATUSES:
                saved.setdefault("detail", "")
                saved.setdefault("next", "")
            else:
                data["items"][item] = default["items"][item]
        if data["track"] not in TRACKS:
            data["track"] = "script"
        self._apply_track_item(data)
        return data

    def _save(self):
        store.write_json_atomic(self.path, self._data)

    def reset_state(self):
        """Forget every saved setup result, as on first run. The caller has moved preflight.json away."""
        self.cancel_ai_test()
        with self._lock:
            self._data = self._new_data()
            self.load_problem = False

    def _apply_track_item(self, data):
        key = "track_promptfoo" if data["track"] == "promptfoo" else "track_script"
        m = self.content["messages"][key]
        data["items"]["track"] = {"status": "passed", "detail": m["detail"], "next": m["next"]}

    # --- item helpers ------------------------------------------------------

    def _set(self, item, status, key, also=None, **values):
        m = self.content["messages"][key]
        detail, following = m["detail"].format(**values), m["next"].format(**values)
        if also:
            extra = self.content["messages"][also]
            detail, following = f"{detail} {extra['detail']}", f"{following} {extra['next']}"
        with self._lock:
            self._data["items"][item] = {"status": status, "detail": detail, "next": following}
            self._save()

    def _status(self, item):
        return self._data["items"][item]["status"]

    def _applies(self, item):
        return item not in PROMPTFOO_ITEMS or self._data["track"] == "promptfoo"

    def _error(self, code):
        return PreflightError(code, self.content["errors"][code])

    @property
    def cli_command(self):
        with self._lock:
            return self._data["cli_command"]

    @property
    def skipped(self):
        """True once the participant chose to skip setup for now. It is forgotten by a configuration reset."""
        with self._lock:
            return self._data.get("setup_skipped") is True

    def skip_setup(self):
        with self._lock:
            self._data["setup_skipped"] = True
            self._save()

    def adopt_cli_command(self, command):
        """A resumed project brings its CLI command along, unless one is already saved."""
        with self._lock:
            if command and not self._data["cli_command"]:
                self._data["cli_command"] = command
                self._save()

    def is_passed(self, paths):
        with self._lock:
            if paths is None:
                return False
            return all(self._status(item) == "passed" for item in ITEM_IDS if self._applies(item))

    # --- environment -------------------------------------------------------

    def env(self):
        """Environment for every CLI and checker: PATH entries and npm/promptfoo variables only."""
        base = dict(os.environ)
        runtime = self.home / "runtime"
        entries = []
        private_python = runtime / "python"
        if (private_python / "python.exe").is_file():
            entries.append(str(private_python))
        elif self.python_path:
            entries.append(os.path.dirname(os.path.abspath(self.python_path)))
        private_node = runtime / "node"
        if (private_node / "node.exe").is_file():
            entries.append(str(private_node))
        path_value = base.get("PATH", "")
        merged, seen = [], set()
        for entry in entries + path_value.split(os.pathsep) + list(self.registry_paths()):
            folded = os.path.normcase(entry.strip())
            if entry.strip() and folded not in seen:
                seen.add(folded)
                merged.append(entry.strip())
        base["PATH"] = os.pathsep.join(merged)
        base["npm_config_cache"] = str(self.home / "npm-cache")
        base["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
        base["PROMPTFOO_CONFIG_DIR"] = str(self.home / "promptfoo")
        return base

    def _find_tool(self, name, env):
        path = env.get("PATH", "")
        # The Store's python and node aliases are stubs that open the Store. Store PowerShell has no stub:
        # its alias exists only when PowerShell is installed, and a normal launch sees only that alias folder.
        if name.lower() != "pwsh":
            path = _without_store(path)
        return self.runner.which(name, path)

    # --- jobs --------------------------------------------------------------

    def _start_job(self, kind, label, target):
        with self._lock:
            if self._job is not None and self._job.running:
                raise self._error("job_busy")
            job = Job(kind, label)
            self._job = job
        self.publish()

        def run():
            try:
                target(job)
            except Exception as exc:  # noqa: BLE001 - a job must never kill the thread silently
                if kind in ITEM_IDS:
                    self._set(kind, "failed", "check_error", error=f"{type(exc).__name__}: {exc}")
            finally:
                with self._lock:
                    job.running = False
                    self._job = None
                self.publish()

        job.thread = threading.Thread(target=run, daemon=True)
        job.thread.start()

    def _tick(self, job, done, total=None):
        job.done_bytes = done
        if total is not None:
            job.total_bytes = total
        now = time.monotonic()
        if now - self._last_publish >= PUBLISH_SECONDS:
            self._last_publish = now
            self.publish()

    def job_running(self):
        with self._lock:
            return self._job is not None and self._job.running

    def wait_for_job(self, timeout=None):
        """Test and shutdown helper: wait until the current job, if any, finishes."""
        job = self._job
        if job is not None and job.thread is not None:
            job.thread.join(timeout)

    def shutdown(self):
        with self._lock:
            job = self._job
            if job is not None:
                job.cancel.set()
            test = self._ai_test
            self._cancel_ai_test()
        if job is not None and job.thread is not None:
            job.thread.join(15)
        if test is not None and test.thread is not None:
            test.thread.join(15)

    # --- check everything --------------------------------------------------

    def start_check_all(self):
        self._start_job("check", self.content["ui"]["checking"], self._job_check_all)

    def _guarded(self, item, check, *args):
        """One item's unexpected error must not stop the checks after it."""
        try:
            check(*args)
        except Exception as exc:  # noqa: BLE001
            self._set(item, "failed", "check_error", error=f"{type(exc).__name__}: {exc}")

    def _job_check_all(self, job):
        steps = [("python", self._check_python)]
        if self._applies("node"):
            steps += [("node", self._check_node), ("promptfoo", self._check_promptfoo)]
        steps += [("cli", self._check_cli), ("working_test", self._check_working_test)]
        for item, check in steps:
            job.detail = self.content["items"][item]["title"]
            self.publish()
            if item == "cli":
                self._detect_ais()
            self._guarded(item, check)
        self._guarded("project", self.check_project, self.paths_provider())
        with self._lock:
            self._data["ran_once"] = True
            self._save()

    def _check_python(self):
        if sys.version_info[:2] < (3, 9):
            self._set("python", "failed", "python_too_old", found=sys.version.split()[0])
            return
        env = self.env()
        exe = self._find_tool("python", env)
        if not exe:
            self._set("python", "failed", "python_missing")
            return
        result = self.runner.run([exe, "--version"], timeout=CHECK_TIMEOUT, env=env)
        if result.timed_out:
            self._set("python", "failed", "check_timeout", seconds=CHECK_TIMEOUT)
            return
        text = (result.stdout + result.stderr).strip()
        match = re.search(r"Python (\d+)\.(\d+)\.?(\d*)", text)
        if result.code != 0 or not match:
            self._set("python", "failed", "python_missing")
            return
        version = (int(match.group(1)), int(match.group(2)))
        found = ".".join(g for g in match.groups() if g)
        if version < (3, 9):
            self._set("python", "failed", "python_too_old", found=found)
            return
        self._set("python", "passed", "python_ok", version=found)

    def _check_node(self):
        env = self.env()
        exe = self._find_tool("node", env)
        if not exe:
            self._set("node", "needs_you", "node_missing")
            return
        result = self.runner.run([exe, "--version"], timeout=CHECK_TIMEOUT, env=env)
        if result.timed_out:
            self._set("node", "failed", "check_timeout", seconds=CHECK_TIMEOUT)
            return
        version = parse_node_version(result.stdout)
        if result.code != 0 or version is None:
            self._set("node", "needs_you", "node_missing")
            return
        found = ".".join(str(n) for n in version)
        if not node_is_new_enough(version):
            self._set("node", "needs_you", "node_too_old", found=found)
            return
        self._set("node", "passed", "node_ok", version=found)

    def _npx_argv(self, env):
        """The launch command for npx, avoiding cmd.exe when a plain Node path works."""
        node = self._find_tool("node", env)
        if node:
            script = Path(node).parent / "node_modules" / "npm" / "bin" / "npx-cli.js"
            if script.is_file():
                return [node, str(script)]
        npx = self._find_tool("npx", env)
        if not npx:
            return None
        if npx.lower().endswith((".cmd", ".bat")):
            # cmd.exe resolves the plain name through the child's PATH, so no path needs quoting.
            return [CMD, "/d", "/s", "/c", Path(npx).name]
        return [npx]

    def _check_promptfoo(self):
        env = self.env()
        env["npm_config_offline"] = "true"  # this check must not download anything without consent
        if self._status("node") != "passed":
            self._set("promptfoo", "needs_you", "promptfoo_needs_node")
            return
        npx = self._npx_argv(env)
        if not npx:
            self._set("promptfoo", "needs_you", "promptfoo_needs_node")
            return
        work = self.home / "promptfoo-work"
        work.mkdir(parents=True, exist_ok=True)
        result = self.runner.run(npx + ["--yes", f"promptfoo@{PROMPTFOO_VERSION}", "--version"],
                                 timeout=NPX_CHECK_TIMEOUT, env=env, cwd=str(work))
        if result.timed_out:
            self._set("promptfoo", "failed", "check_timeout", seconds=NPX_CHECK_TIMEOUT)
            return
        if result.code == 0 and PROMPTFOO_VERSION in result.stdout:
            self._set("promptfoo", "passed", "promptfoo_ok", version=PROMPTFOO_VERSION)
            return
        self._set("promptfoo", "needs_you", "promptfoo_needs_install")

    def _check_cli(self):
        with self._lock:
            command = self._data["cli_command"]
            recipe_ran = self._data["recipe_ran"]
        if not command:
            self._set("cli", "needs_you", "cli_enter_command")
            return
        try:
            self.terminal.check_command(command, self.env())
        except (ValueError, OSError):
            key = "cli_not_found_after_install" if recipe_ran else "cli_not_found"
            self._set("cli", "failed", key, command=command)
            return
        self._set("cli", "passed", "cli_chosen", command=command)

    def _detect_ais(self):
        """Which supported AIs resolve on this computer. Names are resolved; no tool is started."""
        env = self.env()
        found = []
        for command in self._tool_commands():
            try:
                self.terminal.check_command(command, env)
            except (ValueError, OSError):
                continue
            found.append(command)
        with self._lock:
            self._found_commands = found

    def _tool_commands(self):
        """One launch command per supported tool, in recipe order. The free-text recipe is left out."""
        commands = []
        for recipe in self.recipes:
            command = recipe.get("cli_command", "")
            if command and recipe.get("participant") is not False and command not in commands:
                commands.append(command)
        return commands

    def _check_working_test(self):
        with self._lock:
            command = self._data["cli_command"]
            tested = self._data["test_passed_command"]
            quietly = self._data["test_passed_quietly"] is True
            if self._ai_test is not None and self._ai_test.state == "running":
                return
        if self._status("cli") != "passed":
            self._set("working_test", "not_checked", "working_test_needs_previous")
        elif tested and tested == command and quietly:
            self._set("working_test", "passed", "working_test_passed_background")  # no test files to re-read
        elif tested and tested == command:
            self.check_test_result()
        else:
            self._set("working_test", "needs_you", "working_test_ready")

    def check_project(self, paths):
        """Item 8. Reading the folder is the check; creating it happens in Engine.setup."""
        if paths is None:
            self._set("project", "needs_you", "project_needs_choice")
            return
        if "onedrive" in str(paths.project).lower():
            self._set("project", "failed", "project_onedrive", path=str(paths.project))
            return
        if not (paths.project.is_dir() and paths.prompt.is_file() and paths.test_cases.is_file()):
            self._set("project", "failed", "project_files_missing")
            return
        self._set("project", "passed", "project_ok", path=str(paths.project))

    # --- track -------------------------------------------------------------

    def set_track(self, track):
        if track not in TRACKS:
            raise self._error("track_required")
        with self._lock:
            self._data["track"] = track
            self._apply_track_item(self._data)
            self._save()

    @property
    def track(self):
        with self._lock:
            return self._data["track"]

    def adopt_track(self, track):
        """A project that already has finished steps brings its track along."""
        if track in TRACKS and track != self.track:
            self.set_track(track)

    def npx_argv(self, env):
        """The command that starts npx, or None. Private Node runs npx-cli.js directly; otherwise npx.cmd goes through cmd.exe."""
        return self._npx_argv(env)

    # --- installs ----------------------------------------------------------

    def _disk_free(self):
        try:
            return self.runner.disk_free(self.home)
        except OSError:
            return None

    def _ensure_disk(self, item, needed):
        free = self._disk_free()
        if free is not None and free < needed:
            self._set(item, "failed", "not_enough_disk", need=human_bytes(needed), free=human_bytes(free))
            return False
        return True

    def start_install(self, item, consent):
        if consent is not True:
            raise self._error("consent_required")
        if item == "node":
            if self._status("node") == "passed":
                raise self._error("node_not_needed")
            if self._ensure_disk("node", NODE_NEEDS_BYTES):
                self._start_job("node", self.content["ui"]["progress_downloading"].format(label="Node.js"), self._job_node)
        elif item == "promptfoo":
            if self._status("node") != "passed":
                raise self._error("needs_node")
            if self._status("promptfoo") == "passed":
                raise self._error("not_found_for_install")
            if self._ensure_disk("promptfoo", PROMPTFOO_NEEDS_BYTES):
                self._start_job("promptfoo", self.content["ui"]["progress_downloading"].format(label="promptfoo"),
                                self._job_promptfoo)
        else:
            raise self._error("bad_install_item")

    def _download(self, job, item, url, dest, sha256, total, need):
        name = dest.name
        job.total_bytes = total

        def tick():
            try:
                done = dest.stat().st_size
            except OSError:
                done = 0
            self._tick(job, done)

        result = self.runner.run(
            [CURL, "--fail", "--location", "--ssl-no-revoke", "--connect-timeout", "30",
             "--max-time", str(DOWNLOAD_MAX_TIME), "--retry", "2", "--retry-delay", "3",
             "--silent", "--show-error", "--output", name, url],
            timeout=DOWNLOAD_TIMEOUT, cwd=str(dest.parent), on_tick=tick, cancel=job.cancel)
        if result.cancelled:
            _unlink(dest)
            self._set(item, "failed", "install_cancelled")
            return False
        if result.timed_out or result.code == 28:
            _unlink(dest)
            self._set(item, "failed", "download_timeout")
            return False
        if result.code == 23:
            _unlink(dest)
            self._set(item, "failed", "not_enough_disk", need=human_bytes(need), free=human_bytes(self._disk_free()))
            return False
        if result.code != 0 or not result.started:
            _unlink(dest)
            self._set(item, "failed", "no_network")
            return False
        if not dest.is_file():
            self._set(item, "failed", "antivirus_removed")
            return False
        digest = hashlib.sha256()
        try:
            with open(str(dest), "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            self._set(item, "failed", "antivirus_removed")
            return False
        if digest.hexdigest().lower() != sha256.lower():
            _unlink(dest)
            self._set(item, "failed", "hash_mismatch")
            return False
        return True

    def _job_node(self, job):
        runtime = self.home / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        archive = runtime / f"{NODE_FOLDER}.zip"
        staging = runtime / "node.new"
        _unlink(archive)
        _rmtree(staging)
        if not self._download(job, "node", NODE_URL, archive, NODE_SHA256, NODE_DOWNLOAD_BYTES, NODE_NEEDS_BYTES):
            return
        staging.mkdir(parents=True, exist_ok=True)
        job.total_bytes = None
        job.detail = self.content["ui"]["progress_unpacking"]
        self.publish()
        result = self.runner.run([TAR, "-xf", archive.name, "-C", staging.name], timeout=EXTRACT_TIMEOUT,
                                 cwd=str(runtime), cancel=job.cancel)
        if result.cancelled:
            _rmtree(staging)
            _unlink(archive)
            self._set("node", "failed", "install_cancelled")
            return
        extracted = staging / NODE_FOLDER / "node.exe"
        if result.code != 0 or not extracted.is_file():
            _rmtree(staging)
            _unlink(archive)
            self._set("node", "failed", "antivirus_removed")
            return
        checked = self.runner.run([str(extracted), "--version"], timeout=CHECK_TIMEOUT)
        version = parse_node_version(checked.stdout)
        if checked.code != 0 or not node_is_new_enough(version):
            _rmtree(staging)
            _unlink(archive)
            self._set("node", "failed", "antivirus_removed")
            return
        target = runtime / "node"
        _rmtree(target)
        shutil.move(str(staging / NODE_FOLDER), str(target))
        _rmtree(staging)
        _unlink(archive)
        self._set("node", "passed", "installed_node", version=".".join(str(n) for n in version))
        self._check_promptfoo()

    def _job_promptfoo(self, job):
        env = self.env()
        npx = self._npx_argv(env)
        if not npx:
            self._set("promptfoo", "needs_you", "promptfoo_needs_node")
            return
        cache = self.home / "npm-cache"
        cache.mkdir(parents=True, exist_ok=True)
        job.total_bytes = PROMPTFOO_CACHE_BYTES
        work = self.home / "promptfoo-work"
        work.mkdir(parents=True, exist_ok=True)
        last_measure = [0.0]

        def tick():
            now = time.monotonic()
            if now - last_measure[0] < SIZE_POLL_SECONDS:
                return
            last_measure[0] = now
            self._tick(job, min(_dir_size(cache), PROMPTFOO_CACHE_BYTES))

        result = self.runner.run(npx + ["--yes", f"promptfoo@{PROMPTFOO_VERSION}", "--version"],
                                 timeout=NPM_TIMEOUT, env=env, cwd=str(work), on_tick=tick, cancel=job.cancel)
        if result.cancelled:
            self._set("promptfoo", "failed", "install_cancelled")
            return
        if result.timed_out:
            self._set("promptfoo", "failed", "npm_timeout", minutes=NPM_TIMEOUT // 60)
            return
        if result.code == 0 and PROMPTFOO_VERSION in result.stdout:
            self._set("promptfoo", "passed", "promptfoo_ok", version=PROMPTFOO_VERSION)
            return
        text = result.stdout + result.stderr
        if NPM_DISK_RE.search(text):
            self._set("promptfoo", "failed", "npm_no_space")
        elif NPM_NETWORK_RE.search(text):
            self._set("promptfoo", "failed", "npm_network")
        else:
            self._set("promptfoo", "failed", "npm_error")

    # --- CLI command, sign-in, working test ----------------------------------

    def set_cli_command(self, command):
        command = command.strip() if isinstance(command, str) else ""
        if not command:
            raise self._error("needs_cli_command")
        with self._lock:
            changed = command != self._data["cli_command"]
            stale = self._cancel_ai_test() if changed else None
        self._wait_ai_test(stale)
        with self._lock:
            if changed:
                self._data["cli_command"] = command
                self._data["test_passed_command"] = ""
                self._discard_test_files()
                self._set("working_test", "not_checked", "working_test_needs_previous")
            self._save()
        self._check_cli()
        self._check_working_test()

    def _discard_test_files(self):
        """Another AI's test files must never count for the AI chosen now."""
        folder = self.home / "cli-test"
        for name in ("input.txt", "output.txt", "version.txt"):
            _unlink(folder / name)

    def command_usable(self):
        with self._lock:
            return bool(self._data["cli_command"]) and self._status("cli") != "failed"

    def require_cli_ready(self):
        """Raise unless a command is saved and found on this computer."""
        command = self.cli_command
        if not command:
            raise self._error("needs_cli_command")
        return command

    def cli_start_failed(self, error):
        self._set("working_test", "failed", "cli_start_failed", error=str(error))

    def require_test_ready(self):
        command = self.require_cli_ready()
        if self._status("cli") != "passed":
            raise self._error("needs_cli_command")
        return command

    # --- quiet background test of the chosen AI ------------------------------

    def _headless(self, command):
        """(args, seconds) of the one-shot run for this exact command, or None when its recipe has none."""
        for recipe in self.recipes:
            data = recipe.get("headless")
            if recipe.get("cli_command") != command or not isinstance(data, dict):
                continue
            args, seconds = data.get("args"), data.get("timeout_seconds", AI_TEST_SECONDS)
            if (isinstance(args, list) and all(isinstance(a, str) for a in args) and any("{line}" in a for a in args)
                    and isinstance(seconds, int) and not isinstance(seconds, bool) and seconds > 0):
                return args, seconds
        return None

    def start_ai_test(self):
        """Test the chosen AI in the background with its one-shot mode. True when a test was started.

        Nothing is typed, no window opens, and no permission flag is used. Only the process's exit status
        decides: it never records a failure, so an AI that cannot finish quietly goes to the visible test.
        """
        while True:
            with self._lock:
                command = self._data["cli_command"]
                if (not command or self._status("cli") != "passed" or self._data["test_passed_command"] == command
                        or self.terminal.running):
                    return False
                headless = self._headless(command)
                if headless is None:
                    return False
                stale = self._cancel_ai_test()
                if stale is None:
                    record = _AiTest(command)
                    self._ai_test = record
                    record.thread = threading.Thread(target=self._run_ai_test, args=(record, headless), daemon=True)
                    record.thread.start()
                    break
            self._wait_ai_test(stale)  # without the lock: the old worker needs it to finish
        self.publish()
        return True

    def cancel_ai_test(self):
        """Stop the quiet test and return only once its process is gone."""
        with self._lock:
            stale = self._cancel_ai_test()
        self._wait_ai_test(stale)
        self.publish()

    def _cancel_ai_test(self):
        """Signal the running test to stop and return its record. The caller waits with `_wait_ai_test`."""
        record, self._ai_test = self._ai_test, None
        if record is not None:
            record.cancel.set()
        return record

    @staticmethod
    def _wait_ai_test(record):
        if record is not None and record.thread is not None and record.thread is not threading.current_thread():
            record.thread.join(AI_TEST_STOP_SECONDS)

    def _run_ai_test(self, record, headless):
        args, seconds = headless
        passed = False
        try:
            env = self.env()
            argv = self.terminal.argv_for(record.command, env)
            argv[0] = self._find_tool(argv[0], env) or argv[0]
            line = self.content["working_test"]["headless_line"]
            argv += [arg.replace("{line}", line) for arg in args]
            folder = self.home / "cli-test"
            folder.mkdir(parents=True, exist_ok=True)
            result = self.runner.run(argv, seconds, env=env, cwd=str(folder), cancel=record.cancel)
            passed = result.started and result.code == 0 and not result.timed_out and not result.cancelled
        except Exception:  # noqa: BLE001 - whatever went wrong, the visible test is the way forward
            passed = False
        with self._lock:
            if self._ai_test is not record or record.cancel.is_set():
                return
            if passed:
                record.state = "passed"
                self._data["test_passed_command"] = record.command
                self._data["test_passed_quietly"] = True
                self._save()
                self._set("working_test", "passed", "working_test_passed_background")
            else:
                record.state = "needs_you"
                self._set("working_test", "needs_you", "ai_test_background_needs_you")
        self.publish()

    def prepare_test_folder(self):
        folder = self.home / "cli-test"
        project.clear_dir(folder)
        (folder / "input.txt").write_text(self.content["working_test"]["input_text"], encoding="utf-8")
        self._set("working_test", "needs_you", "working_test_started")
        return folder

    @property
    def test_line(self):
        return self.content["working_test"]["line"]

    def poll_test_result(self):
        """Quiet re-read of the test folder: records a pass, never a failure. True when it passed."""
        wt = self.content["working_test"]
        folder = self.home / "cli-test"
        output = _read_decoded(folder / "output.txt")
        version = _read_decoded(folder / "version.txt")
        if (output is None or version is None or output.rstrip() != wt["expected_output"]
                or wt["expected_version"] not in version):
            return False
        with self._lock:
            if self._status("cli") != "passed":
                return False
            self._data["test_passed_command"] = self._data["cli_command"]
            self._data["test_passed_quietly"] = False
            self._save()
        self._set("working_test", "passed", "working_test_passed")
        return True

    def check_test_result(self):
        wt = self.content["working_test"]
        folder = self.home / "cli-test"
        if not (folder / "input.txt").is_file():
            self._set("working_test", "needs_you", "test_incomplete_generic")
            return False
        output = _read_decoded(folder / "output.txt")
        version = _read_decoded(folder / "version.txt")
        if output is None:
            self._set("working_test", "failed", "test_missing_output", also="cli_not_signed_in")
            return False
        if output.rstrip() != wt["expected_output"]:
            self._set("working_test", "failed", "test_wrong_output")
            return False
        if version is None:
            self._set("working_test", "failed", "test_missing_version")
            return False
        if wt["expected_version"] not in version:
            self._set("working_test", "failed", "test_bad_version", found=version.strip()[:200])
            return False
        with self._lock:
            self._data["test_passed_command"] = self._data["cli_command"]
            self._data["test_passed_quietly"] = False
            self._save()
        self._set("working_test", "passed", "working_test_passed")
        return True

    def mark_recipe_ran(self):
        with self._lock:
            self._data["recipe_ran"] = True
            self._save()

    # --- recipes -------------------------------------------------------------

    def recipe_by_id(self, recipe_id):
        for recipe in self.recipes:
            if recipe["id"] == recipe_id:
                return recipe
        raise self._error("bad_recipe")

    def recipe_argv(self, recipe_id, consent):
        """The argv to run for a recipe. The command is shown exactly as it runs."""
        if consent is not True:
            raise self._error("consent_required")
        recipe = self.recipe_by_id(recipe_id)
        command = recipe.get("command", "")
        if recipe.get("shell") == "none" or not command:
            raise self._error("recipe_no_command")
        needed = int(recipe.get("needs_mb", 0)) * 10**6
        free = self._disk_free()
        if free is not None and free < needed:
            raise PreflightError("not_enough_disk", self.content["messages"]["not_enough_disk"]["detail"].format(
                need=human_bytes(needed), free=human_bytes(free)) + " " +
                self.content["messages"]["not_enough_disk"]["next"])
        if recipe["shell"] == "powershell":
            return [POWERSHELL, "-NoProfile", "-Command", command]
        return [CMD, "/d", "/s", "/c", command]

    # --- state ---------------------------------------------------------------

    def _consent_view(self, title_key, body_key, confirm_key, **values):
        c = self.content["consent"]
        return {"title": c[title_key], "body": c[body_key].format(**values), "confirm_label": c[confirm_key],
                "cancel_label": c["cancel"]}

    def _item_view(self, number, item, free, job_running):
        text = self.content["items"][item]
        info = self._data["items"][item]
        view = {"id": item, "number": number, "title": text["title"], "applies": self._applies(item),
                "status": info["status"], "detail": info["detail"], "next": info["next"], "install": None}
        if item == "node" and self._applies(item) and info["status"] != "passed":
            view["install"] = {"available": not job_running, "consent": self._consent_view(
                "node_title", "node_body", "node_confirm", version=NODE_VERSION,
                path=str(self.home / "runtime" / "node"), free=human_bytes(free))}
        elif item == "promptfoo" and self._applies(item) and info["status"] != "passed":
            ready = self._status("node") == "passed"
            view["install"] = {"available": ready and not job_running, "consent": self._consent_view(
                "promptfoo_title", "promptfoo_body", "promptfoo_confirm",
                path=str(self.home / "npm-cache"), free=human_bytes(free))} if ready else None
        return view

    def _recipes_view(self, free):
        env = self.env()
        result = []
        for recipe in self.recipes:
            entry = {"id": recipe["id"], "name": recipe["name"], "cli_command": recipe.get("cli_command", ""),
                     "command": recipe.get("command", ""), "note": recipe.get("note", ""),
                     "source": recipe.get("source", ""), "hidden": bool(recipe.get("hidden")),
                     "requirement": None, "consent": None}
            if entry["command"]:
                need = human_bytes(int(recipe.get("needs_mb", 0)) * 10**6)
                entry["consent"] = self._consent_view("recipe_title", "recipe_body", "recipe_confirm",
                                                      command=entry["command"], name=recipe["name"],
                                                      need=need, free=human_bytes(free))
            req = recipe.get("requires")
            if req and not self._find_tool(req["command"], env):
                entry["requirement"] = {"name": req["name"], "detail": req["detail"], "recipe": req["recipe"]}
            result.append(entry)
        return result

    def _cli_view(self, free):
        """The chosen command, and one entry per supported tool for the Choose your AI page."""
        recipes = self._recipes_view(free)
        found = list(self._found_commands)
        chosen = self._data["cli_command"]
        tools, seen = [], {}
        for entry in recipes:
            command = entry["cli_command"]
            recipe = next(r for r in self.recipes if r["id"] == entry["id"])
            if not command or recipe.get("participant") is False:
                continue
            entry = dict(entry, plain=recipe.get("plain") or recipe.get("note", ""))
            if command in seen:
                seen[command]["other_installs"].append(entry)
                continue
            tool = {"id": recipe["id"], "name": recipe.get("tool_name") or entry["name"], "cli_command": command,
                    "found": command in found, "chosen": command == chosen, "preselect": False,
                    "install": entry, "other_installs": []}
            seen[command] = tool
            tools.append(tool)
        found_tools = [t for t in tools if t["found"]]
        if len(found_tools) == 1 and not chosen:
            found_tools[0]["preselect"] = True
        return {"command": chosen, "found": found, "tools": tools, "recipes": recipes,
                "tool": self._tool_key(chosen)}

    @staticmethod
    def _tool_key(command):
        """The launch name of the chosen tool, whatever options or path were typed."""
        parts = (command or "").strip().split()
        if not parts:
            return ""
        name = parts[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        return name[:-4] if name.endswith(".exe") else name

    def view(self, paths, session):
        free = self._disk_free()
        with self._lock:
            job = self._job.view() if self._job is not None else None
            job_running = job is not None and job["running"]
            if job is not None and job["total_bytes"]:
                job["progress_text"] = self.content["ui"]["progress_detail"].format(
                    done=human_bytes(job["done_bytes"]), total=human_bytes(job["total_bytes"]))
            items = [self._item_view(0, item, free, job_running) for item in ITEM_IDS]
            # Items that do not apply to the chosen track are hidden, so number only the ones shown.
            for number, view_item in enumerate((i for i in items if i["applies"]), 1):
                view_item["number"] = number
            if paths is None:
                project_item = next(i for i in items if i["id"] == "project")
                m = self.content["messages"]["project_needs_choice"]
                project_item.update(status="needs_you", detail=m["detail"], next=m["next"])
            cli = self._cli_view(free)
            wt = self.content["working_test"]
            passed = self.is_passed(paths)
            view = {
                "passed": passed,
                "skipped": self._data.get("setup_skipped") is True,
                "track": self._data["track"],
                "track_options": copy.deepcopy(self.content["track_options"]),
                "track_note": self.content["track_promptfoo_note"] if self._data["track"] == "promptfoo" else None,
                "items": items,
                "job": job,
                "cli": cli,
                "ran_once": self._data["ran_once"],
                "custom_ai": self.custom_ai,
                "working_test": {"line": wt["line"], "folder_label": wt["folder_label"],
                                 "background": {"state": self._ai_test.state if self._ai_test else "idle"}},
                "session": session,
                "disk": {"free_bytes": free, "free_text": human_bytes(free)},
                "text": copy.deepcopy(self.content["ui"]),
                "pages": copy.deepcopy(self.content["pages"]),
                "test_only": copy.deepcopy(self.content["test_only"]),
                "ai_window_lesson": copy.deepcopy(self.content["ai_window_lesson"]),
            }
        return view
