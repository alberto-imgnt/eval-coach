"""Preflight items, with fake runners. Nothing here downloads or launches anything real."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import FakePty, FakeTerminal

from eval_coach import preflight as pf
from eval_coach import hostos, project, runner
from eval_coach.engine import Engine, EngineError
from eval_coach.preflight import Result, SystemRunner
from eval_coach.terminal import TerminalManager


class FakeRunner:
    """Stands in for the programs preflight would run. Records every call."""

    def __init__(self):
        self.calls = []
        self.programs = {}
        self.which_map = {"python": r"C:\fake\python.exe"}
        self.free = 500 * 10**9
        self.gate = None
        self.active = 0  # programs running right now, to prove two never overlap
        self.max_active = 0
        self.exit_delay = 0.0  # how long a cancelled program takes to be gone

    def name_of(self, argv):
        return Path(str(argv[0])).stem.lower()

    def run(self, argv, timeout, env=None, cwd=None, on_tick=None, cancel=None):
        self.calls.append({"argv": list(argv), "timeout": timeout, "env": env, "cwd": cwd})
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.gate is not None:
                while not self.gate.is_set():
                    if cancel is not None and cancel.is_set():
                        time.sleep(self.exit_delay)
                        return Result(code=-1, cancelled=True)
                    time.sleep(0.005)
            if on_tick is not None:
                on_tick()
            handler = self.programs.get(self.name_of(argv))
            if handler is None:
                return Result(code=-1, started=False, stderr="fake: no program")
            return handler(argv, env, cwd)
        finally:
            self.active -= 1

    def which(self, name, path):
        return self.which_map.get(name)

    def disk_free(self, path):
        return self.free

    def calls_named(self, name):
        return [c for c in self.calls if self.name_of(c["argv"]) == name]


def text_result(stdout="", code=0, stderr="", timed_out=False):
    return lambda argv, env, cwd: Result(code=code, stdout=stdout, stderr=stderr, timed_out=timed_out)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-pf-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.project_dir = self.tmp / "project"
        self.fake = FakeRunner()
        self.fake.programs["python"] = text_result("Python 3.13.17\n")
        self.terminal = FakeTerminal()
        self.engine = self.build_engine()

    def build_engine(self):
        return Engine(self.home, self.terminal, poll_interval=0.01, preflight_runner=self.fake,
                      registry_paths=lambda: [])

    @property
    def state(self):
        return self.engine.get_state()

    def item(self, item_id, state=None):
        return next(i for i in (state or self.state)["preflight"]["items"] if i["id"] == item_id)

    def run_check_all(self):
        self.engine.preflight_check()
        self.engine.preflight.wait_for_job(10)

    def assert_code(self, code, fn, *args, **kwargs):
        with self.assertRaises(EngineError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def setup_project(self):
        self.engine.setup({"project_path": str(self.project_dir), "starter": "northwind"})


WINDOWS_ONLY = unittest.skipUnless(sys.platform == "win32", "uses the Windows pins and paths; the Mac equivalents are the Mac* classes")


@WINDOWS_ONLY
class Environment(Base):
    def test_prepends_found_python_when_no_private_copy(self):
        self.engine.python_path = r"C:\Found Python\python.exe"
        env = self.engine._cli_env()
        self.assertTrue(env["PATH"].startswith(r"C:\Found Python;"), env["PATH"][:40])

    def test_private_runtime_folders_are_first_when_present(self):
        (self.home / "runtime" / "python").mkdir(parents=True)
        (self.home / "runtime" / "python" / "python.exe").write_bytes(b"x")
        (self.home / "runtime" / "node").mkdir(parents=True)
        (self.home / "runtime" / "node" / "node.exe").write_bytes(b"x")
        parts = self.engine._cli_env()["PATH"].split(";")
        self.assertEqual(parts[0], str(self.home / "runtime" / "python"))
        self.assertEqual(parts[1], str(self.home / "runtime" / "node"))

    def test_adds_exactly_the_npm_and_promptfoo_variables(self):
        env = self.engine._cli_env()
        self.assertEqual(env["npm_config_cache"], str(self.home / "npm-cache"))
        self.assertEqual(env["PROMPTFOO_DISABLE_TELEMETRY"], "1")
        self.assertEqual(env["PROMPTFOO_CONFIG_DIR"], str(self.home / "promptfoo"))
        import os
        added = {k for k, v in env.items() if os.environ.get(k) != v and k != "PATH"}
        self.assertEqual(added, {"npm_config_cache", "PROMPTFOO_DISABLE_TELEMETRY", "PROMPTFOO_CONFIG_DIR"})

    def test_no_permission_setting_is_ever_added(self):
        import os
        # The host may define variables such as AUTO_APPROVAL; only what the app adds counts.
        clean = {"PATH": r"C:\Windows\System32", "SystemRoot": r"C:\Windows"}
        with mock.patch.dict(os.environ, clean, clear=True):
            env = self.engine._cli_env()
            added = [key for key, value in env.items() if clean.get(key) != value]
        self.assertTrue(added)
        for key in env:
            self.assertNotRegex(key.lower(), r"permission|approval|yolo|dangerous|bypass")

    def test_registry_path_entries_are_appended_for_a_fresh_install(self):
        engine = Engine(self.home, self.terminal, preflight_runner=self.fake,
                        registry_paths=lambda: [r"C:\NewlyInstalled"])
        self.assertIn(r"C:\NewlyInstalled", engine._cli_env()["PATH"].split(";"))

    def test_terminal_and_checker_receive_it(self):
        helpers.write_passed_preflight(self.home)
        engine = self.build_engine()
        engine.setup({"project_path": str(self.project_dir), "cli_command": "fake-cli", "starter": "northwind"})
        engine.step_start("generate")
        start = self.terminal.starts[-1]
        self.assertIn("npm_config_cache", start["env"])
        seen = {}

        def capture(project, files, timeout=30, env=None):
            seen["env"] = env
            return {"ok": True, "exit_code": 0, "error": None, "raw": "", "files": []}

        for n in range(1, 6):
            (self.project_dir / "runs" / f"run-{n}.txt").write_text("words", encoding="utf-8")
        engine.step_stop("generate")
        (self.project_dir / "check.py").write_text("print('hi')\n", encoding="utf-8")
        engine.progress["steps"]["generate"]["model_name"] = "m"
        engine.step_check("generate")
        with mock.patch.object(runner, "run_checker", capture):
            engine.step_run_checker("build", "first_look")
        self.assertEqual(seen["env"]["PROMPTFOO_DISABLE_TELEMETRY"], "1")


class Compare(unittest.TestCase):
    def test_node_version_comparison_around_the_minimum(self):
        for text, ok in (("v22.21.9", False), ("v22.22.0", True), ("v22.22.1", True), ("v24.0.0", True),
                         ("v21.9.0", False), ("v18.20.3", False), ("v26.13.0", True), ("garbage", False)):
            with self.subTest(text=text):
                self.assertEqual(pf.node_is_new_enough(pf.parse_node_version(text)), ok)


@WINDOWS_ONLY
class Python(Base):
    def test_passes_with_a_working_python(self):
        self.run_check_all()
        item = self.item("python")
        self.assertEqual(item["status"], "passed")
        self.assertIn("3.13.17", item["detail"])

    def test_missing_from_path(self):
        self.fake.which_map["python"] = None
        self.run_check_all()
        item = self.item("python")
        self.assertEqual(item["status"], "failed")
        self.assertTrue(item["next"])

    def test_store_stub_is_skipped(self):
        seen = {}
        original = self.fake.which

        def spy(name, path):
            seen[name] = path
            return original(name, path)

        self.fake.which = spy
        self.engine.preflight._find_tool("python", {"PATH": r"C:\Users\x\AppData\Local\Microsoft\WindowsApps;C:\Py"})
        self.assertEqual(seen["python"], r"C:\Py")

    def test_pwsh_may_be_found_in_the_store_alias_folder(self):
        seen = {}
        original = self.fake.which

        def spy(name, path):
            seen[name] = path
            return original(name, path)

        self.fake.which = spy
        store = r"C:\Users\x\AppData\Local\Microsoft\WindowsApps"
        path = f"{store};C:\\Py"
        self.engine.preflight._find_tool("pwsh", {"PATH": path})
        self.assertEqual(seen["pwsh"], path)
        self.engine.preflight._find_tool("python", {"PATH": path})
        self.assertEqual(seen["python"], r"C:\Py")

    def test_too_old(self):
        self.fake.programs["python"] = text_result("Python 3.8.10\n")
        self.run_check_all()
        self.assertEqual(self.item("python")["status"], "failed")

    def test_a_hung_check_times_out_and_explains_itself(self):
        self.fake.programs["python"] = text_result("", code=-1, timed_out=True)
        self.run_check_all()
        item = self.item("python")
        self.assertEqual(item["status"], "failed")
        self.assertIn("did not finish", item["detail"])


@WINDOWS_ONLY
class Node(Base):
    def setUp(self):
        super().setUp()
        self.engine.preflight_track("promptfoo")

    def test_not_applicable_on_script_track(self):
        self.engine.preflight_track("script")
        self.assertFalse(self.item("node")["applies"])
        self.assertFalse(self.item("promptfoo")["applies"])
        self.run_check_all()
        self.assertEqual(self.fake.calls_named("node"), [])

    def test_needs_you_when_missing(self):
        self.fake.which_map["node"] = None
        self.run_check_all()
        item = self.item("node")
        self.assertEqual(item["status"], "needs_you")
        self.assertIsNotNone(item["install"])

    def test_old_version_is_not_reused(self):
        self.fake.which_map["node"] = r"C:\fake\node.exe"
        self.fake.programs["node"] = text_result("v20.11.0\n")
        self.run_check_all()
        item = self.item("node")
        self.assertEqual(item["status"], "needs_you")
        self.assertIn("20.11.0", item["detail"])

    def test_new_enough_is_reused(self):
        self.fake.which_map["node"] = r"C:\fake\node.exe"
        self.fake.programs["node"] = text_result("v22.22.0\n")
        self.run_check_all()
        self.assertEqual(self.item("node")["status"], "passed")

    def test_consent_text_names_the_disk_amount(self):
        self.fake.which_map["node"] = None
        self.run_check_all()
        body = self.item("node")["install"]["consent"]["body"]
        self.assertIn("500.0 GB", body)
        self.assertIn("about 41 MB", body)


@WINDOWS_ONLY
class Install(Base):
    def setUp(self):
        super().setUp()
        self.engine.preflight_track("promptfoo")
        self.fake.which_map["node"] = None
        self.payload = b"pretend node zip" * 100
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.patcher = mock.patch.object(pf, "NODE_SHA256", self.sha)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def fake_curl(self, payload=None):
        data = self.payload if payload is None else payload

        def curl(argv, env, cwd):
            name = argv[argv.index("--output") + 1]
            (Path(cwd) / name).write_bytes(data)
            return Result(code=0)

        return curl

    def fake_tar_success(self):
        def tar(argv, env, cwd):
            target = Path(cwd) / argv[argv.index("-C") + 1] / pf.NODE_FOLDER
            target.mkdir(parents=True)
            (target / "node.exe").write_bytes(b"exe")
            return Result(code=0)

        return tar

    def install_node(self):
        self.engine.preflight_install("node", True)
        self.engine.preflight.wait_for_job(10)

    def test_consent_is_required(self):
        self.assert_code("consent_required", self.engine.preflight_install, "node", False)
        self.assert_code("consent_required", self.engine.preflight_install, "node", None)
        self.assertEqual(self.fake.calls, [])

    def test_full_install_uses_system_curl_and_tar_and_verifies(self):
        self.fake.programs["curl"] = self.fake_curl()
        self.fake.programs["tar"] = self.fake_tar_success()
        self.fake.programs["node"] = text_result("v26.13.0\n")
        self.install_node()
        self.assertEqual(self.item("node")["status"], "passed")
        self.assertTrue((self.home / "runtime" / "node" / "node.exe").is_file())
        curl = self.fake.calls_named("curl")[0]
        self.assertEqual(curl["argv"][0].lower(), pf.CURL.lower())
        self.assertTrue(curl["argv"][0].lower().endswith(r"system32\curl.exe"))
        self.assertIn("--ssl-no-revoke", curl["argv"])
        self.assertEqual(pf.TAR.lower().split("\\")[-2:], ["system32", "tar.exe"])
        self.assertFalse((self.home / "runtime" / f"{pf.NODE_FOLDER}.zip").exists(), "the archive is removed")
        self.assertFalse((self.home / "runtime" / "node.new").exists())

    def test_hash_mismatch_deletes_the_file_and_is_never_bypassed(self):
        self.fake.programs["curl"] = self.fake_curl(payload=b"tampered bytes")
        self.fake.programs["tar"] = self.fake_tar_success()
        self.fake.programs["node"] = text_result("v26.13.0\n")
        self.install_node()
        item = self.item("node")
        self.assertEqual(item["status"], "failed")
        self.assertIn("fingerprint", item["detail"])
        self.assertIn("cannot be turned off", item["detail"])
        self.assertFalse((self.home / "runtime" / f"{pf.NODE_FOLDER}.zip").exists())
        self.assertFalse((self.home / "runtime" / "node").exists())
        self.assertEqual(self.fake.calls_named("tar"), [], "tar must not run on a bad file")

    def test_no_network_is_explained(self):
        self.fake.programs["curl"] = lambda argv, env, cwd: Result(code=6, stderr="could not resolve")
        self.install_node()
        item = self.item("node")
        self.assertEqual(item["status"], "failed")
        self.assertIn("Company Portal or Software Center", item["next"])
        self.assertIn("Check everything again", item["next"])

    def test_download_timeout_is_explained(self):
        self.fake.programs["curl"] = lambda argv, env, cwd: Result(code=28)
        self.install_node()
        self.assertIn("timed out", self.item("node")["detail"])

    def test_not_enough_disk_stops_before_any_download(self):
        self.fake.free = 10 * 10**6
        self.install_node()
        item = self.item("node")
        self.assertEqual(item["status"], "failed")
        self.assertIn("10 MB", item["detail"])
        self.assertEqual(self.fake.calls, [])

    def test_antivirus_removed_the_file_after_extracting(self):
        self.fake.programs["curl"] = self.fake_curl()

        def tar_without_exe(argv, env, cwd):
            (Path(cwd) / argv[argv.index("-C") + 1] / pf.NODE_FOLDER).mkdir(parents=True)
            return Result(code=0)

        self.fake.programs["tar"] = tar_without_exe
        self.install_node()
        self.assertIn("security software", self.item("node")["detail"])

    def test_a_second_install_while_one_runs_is_refused(self):
        self.fake.gate = threading.Event()
        self.fake.programs["curl"] = self.fake_curl()
        self.fake.programs["tar"] = self.fake_tar_success()
        self.fake.programs["node"] = text_result("v26.13.0\n")
        self.engine.preflight_install("node", True)
        try:
            self.assert_code("job_busy", self.engine.preflight_install, "node", True)
            self.assert_code("job_busy", self.engine.preflight_check)
            job = self.state["preflight"]["job"]
            self.assertTrue(job["running"])
            self.assertEqual(job["kind"], "node")
            self.assertEqual(self.engine.get_state()["preflight"]["job"]["kind"], "node", "a state fetch after a reload still shows the job")
        finally:
            self.fake.gate.set()
            self.engine.preflight.wait_for_job(10)
        self.assertIsNone(self.state["preflight"]["job"])

    def test_install_runs_off_the_request_thread(self):
        self.fake.gate = threading.Event()
        self.fake.programs["curl"] = self.fake_curl()
        started = time.monotonic()
        self.engine.preflight_install("node", True)
        self.assertLess(time.monotonic() - started, 2)
        self.fake.gate.set()
        self.engine.preflight.wait_for_job(10)

    def test_download_progress_is_reported(self):
        written = threading.Event()

        def curl(argv, env, cwd):
            name = argv[argv.index("--output") + 1]
            (Path(cwd) / name).write_bytes(self.payload[:1000])
            written.set()
            self.fake.gate2.wait(10)
            (Path(cwd) / name).write_bytes(self.payload)
            return Result(code=0)

        self.fake.gate2 = threading.Event()
        self.fake.programs["curl"] = curl
        self.fake.programs["tar"] = self.fake_tar_success()
        self.fake.programs["node"] = text_result("v26.13.0\n")
        self.engine.preflight_install("node", True)
        self.assertTrue(written.wait(5))
        job = self.state["preflight"]["job"]
        self.assertEqual(job["total_bytes"], pf.NODE_DOWNLOAD_BYTES)
        self.fake.gate2.set()
        self.engine.preflight.wait_for_job(10)


@WINDOWS_ONLY
class Promptfoo(Base):
    def setUp(self):
        super().setUp()
        self.engine.preflight_track("promptfoo")
        self.fake.which_map["node"] = r"C:\fake\node.exe"
        self.fake.which_map["npx"] = r"C:\fake\npx.exe"
        self.fake.programs["node"] = text_result("v26.13.0\n")

    def test_check_does_not_download_without_consent(self):
        self.fake.programs["npx"] = text_result("", code=1, stderr="ENOTCACHED")
        self.run_check_all()
        item = self.item("promptfoo")
        self.assertEqual(item["status"], "needs_you")
        self.assertIsNotNone(item["install"])
        call = self.fake.calls_named("npx")[0]
        self.assertEqual(call["env"]["npm_config_offline"], "true")
        self.assertEqual(call["argv"][1:], ["--yes", "promptfoo@0.125.1", "--version"])

    def test_passes_when_cached_and_right_version(self):
        self.fake.programs["npx"] = text_result("0.125.1\n")
        self.run_check_all()
        self.assertEqual(self.item("promptfoo")["status"], "passed")

    def test_wrong_version_needs_install(self):
        self.fake.programs["npx"] = text_result("0.100.0\n")
        self.run_check_all()
        self.assertEqual(self.item("promptfoo")["status"], "needs_you")

    def test_install_consent_states_one_gigabyte(self):
        self.fake.programs["npx"] = text_result("", code=1)
        self.run_check_all()
        self.assertIn("about 1 GB", self.item("promptfoo")["install"]["consent"]["body"])

    def test_install_requires_node(self):
        self.fake.which_map["node"] = None
        self.run_check_all()
        self.assert_code("needs_node", self.engine.preflight_install, "promptfoo", True)

    def test_predownload_uses_private_cache_and_env(self):
        self.fake.programs["npx"] = text_result("", code=1)
        self.run_check_all()
        self.fake.programs["npx"] = text_result("0.125.1\n")
        self.engine.preflight_install("promptfoo", True)
        self.engine.preflight.wait_for_job(10)
        self.assertEqual(self.item("promptfoo")["status"], "passed")
        call = self.fake.calls_named("npx")[-1]
        self.assertEqual(call["env"]["npm_config_cache"], str(self.home / "npm-cache"))
        self.assertEqual(call["env"]["PROMPTFOO_DISABLE_TELEMETRY"], "1")
        self.assertEqual(call["env"]["PROMPTFOO_CONFIG_DIR"], str(self.home / "promptfoo"))
        self.assertNotIn("npm_config_offline", call["env"])

    def test_npm_errors_are_explained_with_a_next_action(self):
        self.fake.programs["npx"] = text_result("", code=1)
        self.run_check_all()
        self.fake.programs["npx"] = text_result("", code=1, stderr="some npm problem")
        self.engine.preflight_install("promptfoo", True)
        self.engine.preflight.wait_for_job(10)
        item = self.item("promptfoo")
        self.assertEqual(item["status"], "failed")
        self.assertTrue(item["next"])

    def test_npm_network_block_is_explained(self):
        self.fake.programs["npx"] = text_result("", code=1)
        self.run_check_all()
        self.fake.programs["npx"] = text_result("", code=1, stderr="npm ERR! code ENOTFOUND")
        self.engine.preflight_install("promptfoo", True)
        self.engine.preflight.wait_for_job(10)
        self.assertIn("registry", self.item("promptfoo")["detail"])

    def test_not_enough_disk_blocks_before_download(self):
        self.fake.programs["npx"] = text_result("", code=1)
        self.run_check_all()
        calls_before = len(self.fake.calls)
        self.fake.free = 2 * 10**8
        self.engine.preflight_install("promptfoo", True)
        self.assertEqual(self.item("promptfoo")["status"], "failed")
        self.assertEqual(len(self.fake.calls), calls_before)

    def test_track_note_is_one_plain_line(self):
        self.assertIn("Script track", self.state["preflight"]["track_note"])
        self.engine.preflight_track("script")
        self.assertIsNone(self.state["preflight"]["track_note"])


class Cli(Base):
    def test_starts_as_needs_you_with_no_command(self):
        self.run_check_all()
        self.assertEqual(self.item("cli")["status"], "needs_you")

    def test_a_command_that_is_not_found_explains_itself(self):
        self.engine.preflight_cli("no-such-cli --flag")
        item = self.item("cli")
        self.assertEqual(item["status"], "failed")
        self.assertIn("no-such-cli --flag", item["detail"])
        self.assertTrue(item["next"])

    def test_a_found_command_passes_without_starting_anything(self):
        self.engine.preflight_cli("fake-cli")
        self.assertEqual(self.item("cli")["status"], "passed")
        self.assertEqual(self.terminal.starts, [])

    def test_not_found_after_install_uses_its_own_message(self):
        self.engine.preflight.mark_recipe_ran()
        self.engine.preflight_cli("no-such-cli")
        self.assertIn("install finished", self.item("cli")["detail"])

    def test_there_is_no_sign_in_item(self):
        self.assertNotIn("signin", [i["id"] for i in self.state["preflight"]["items"]])

    def test_changing_the_command_clears_the_passed_test(self):
        self.engine.preflight_cli("fake-cli")
        self.engine.preflight_test_start()
        folder = self.home / "cli-test"
        (folder / "output.txt").write_text("HELLO FROM EVAL COACH", encoding="utf-8")
        (folder / "version.txt").write_text("Python 3.13\n", encoding="utf-8")
        self.engine.preflight_test_check()
        self.assertEqual(self.item("working_test")["status"], "passed")
        self.engine.preflight_cli("other-cli")
        self.assertEqual(self.item("working_test")["status"], "needs_you")
        self.run_check_all()
        self.assertEqual(self.item("working_test")["status"], "needs_you")

    def test_a_missing_command_closes_the_working_test(self):
        self.engine.preflight_cli("no-such-cli")
        self.assertEqual(self.item("working_test")["status"], "not_checked")
        self.assert_code("needs_cli_command", self.engine.preflight_test_start)

    def test_app_never_answers_the_cli(self):
        self.engine.preflight_cli("fake-cli")
        self.engine.preflight_test_start()
        self.assertEqual(self.terminal.keystrokes, [])
        self.assertEqual(self.terminal.typed, [])


@WINDOWS_ONLY
class BackgroundTest(Base):
    """Choosing an AI starts a quiet one-shot test. Only the exit status decides, and it never records a failure."""

    def setUp(self):
        super().setUp()
        self.line = self.engine.preflight.content["working_test"]["headless_line"]
        self.fake.programs["copilot"] = text_result("OK\n")

    def wait(self):
        record = self.engine.preflight._ai_test
        if record is not None and record.thread is not None:
            record.thread.join(10)

    def choose(self, command="copilot"):
        self.engine.preflight_cli(command)
        self.wait()
        return self.state["preflight"]

    def test_choosing_an_ai_runs_its_one_shot_mode_with_no_window_or_typing(self):
        pf_state = self.choose()
        call = self.fake.calls_named("copilot")[0]
        self.assertEqual(call["argv"], ["copilot", "-p", self.line])
        self.assertEqual(call["timeout"], 120)
        self.assertEqual(Path(call["cwd"]), self.home / "cli-test")
        self.assertEqual(self.terminal.starts, [])
        self.assertEqual(self.terminal.typed, [])
        self.assertEqual(self.terminal.keystrokes, [])
        self.assertEqual(pf_state["working_test"]["background"]["state"], "passed")

    def test_an_exit_status_of_zero_passes_the_working_test_for_this_ai(self):
        self.choose()
        item = self.item("working_test")
        self.assertEqual(item["status"], "passed")
        self.assertIn("quiet test", item["detail"])
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "copilot")

    def test_a_pass_survives_a_later_check_of_everything(self):
        self.choose()
        self.run_check_all()
        self.assertEqual(self.item("working_test")["status"], "passed")

    def test_a_non_zero_exit_needs_the_participant_and_is_never_a_failure(self):
        self.fake.programs["copilot"] = text_result("OK\n", code=1)
        pf_state = self.choose()
        item = self.item("working_test")
        self.assertEqual(item["status"], "needs_you")
        self.assertIn("sign in", item["detail"])
        self.assertEqual(pf_state["working_test"]["background"]["state"], "needs_you")
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "")

    def test_the_printed_text_decides_nothing(self):
        self.fake.programs["copilot"] = text_result("not signed in, error", code=0)
        self.choose()
        self.assertEqual(self.item("working_test")["status"], "passed")
        self.fake.programs["copilot"] = text_result("OK", code=2)
        self.choose("claude")
        self.fake.programs["claude"] = text_result("OK", code=2)
        self.choose("claude")
        self.assertEqual(self.item("working_test")["status"], "needs_you")

    def test_a_timeout_needs_the_participant(self):
        self.fake.programs["copilot"] = text_result("", code=-1, timed_out=True)
        self.choose()
        self.assertEqual(self.item("working_test")["status"], "needs_you")

    def test_a_tool_that_cannot_start_needs_the_participant(self):
        del self.fake.programs["copilot"]
        self.choose()
        self.assertEqual(self.item("working_test")["status"], "needs_you")

    def test_a_command_without_one_shot_data_runs_nothing(self):
        pf_state = self.choose("fake-cli")
        self.assertEqual(self.fake.calls_named("fake-cli"), [])
        self.assertEqual(pf_state["working_test"]["background"]["state"], "idle")
        self.assertEqual(self.item("working_test")["status"], "needs_you")

    def test_a_command_that_is_not_found_runs_nothing(self):
        self.choose("no-such-cli")
        self.assertEqual(self.fake.calls, [])

    def test_the_same_passed_ai_is_not_tested_again(self):
        self.choose()
        self.choose()
        self.assertEqual(len(self.fake.calls_named("copilot")), 1)

    def test_a_needs_you_result_is_tried_again_when_the_ai_is_chosen_again(self):
        self.fake.programs["copilot"] = text_result("", code=1)
        self.choose()
        self.fake.programs["copilot"] = text_result("OK")
        self.choose()
        self.assertEqual(self.item("working_test")["status"], "passed")
        self.assertEqual(len(self.fake.calls_named("copilot")), 2)

    def test_it_never_starts_while_an_ai_window_is_running(self):
        self.terminal.running = True
        self.choose()
        self.assertEqual(self.fake.calls_named("copilot"), [])

    def test_the_visible_test_cancels_a_running_quiet_test(self):
        self.fake.gate = threading.Event()
        self.engine.preflight_cli("copilot")
        record = self.engine.preflight._ai_test
        self.assertEqual(self.state["preflight"]["working_test"]["background"]["state"], "running")
        self.engine.preflight_test_start()
        self.fake.gate.set()
        record.thread.join(10)
        self.assertEqual(self.state["preflight"]["working_test"]["background"]["state"], "idle")
        self.assertEqual(self.item("working_test")["status"], "needs_you")
        self.assertNotIn("quiet test", self.item("working_test")["detail"])

    def test_choosing_another_ai_cancels_a_running_quiet_test(self):
        self.fake.gate = threading.Event()
        self.engine.preflight_cli("copilot")
        record = self.engine.preflight._ai_test
        self.engine.preflight_cli("fake-cli")
        self.fake.gate.set()
        record.thread.join(10)
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "")
        self.assertNotEqual(self.item("working_test")["detail"], "")
        self.assertNotIn("quiet test", self.item("working_test")["detail"])

    def test_an_install_cancels_a_running_quiet_test(self):
        self.fake.gate = threading.Event()
        self.engine.preflight_cli("copilot")
        record = self.engine.preflight._ai_test
        self.engine.preflight_recipe("claude-winget", True)
        self.fake.gate.set()
        record.thread.join(10)
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "")

    def test_a_check_of_everything_leaves_a_running_test_alone(self):
        self.fake.gate = threading.Event()
        self.engine.preflight_cli("copilot")
        record = self.engine.preflight._ai_test
        before = self.item("working_test")
        self.engine.preflight._check_working_test()
        self.assertEqual(self.item("working_test"), before)
        self.fake.gate.set()
        record.thread.join(10)

    def test_a_cancel_returns_only_when_the_process_is_gone(self):
        self.fake.gate = threading.Event()
        self.fake.exit_delay = 0.3
        self.engine.preflight_cli("copilot")
        while not self.fake.active:
            time.sleep(0.005)
        self.engine.preflight.cancel_ai_test()
        self.assertEqual(self.fake.active, 0)

    def test_a_replacement_test_never_overlaps_the_one_it_replaces(self):
        self.fake.gate = threading.Event()
        self.fake.exit_delay = 0.2
        self.engine.preflight_cli("copilot")
        while not self.fake.active:
            time.sleep(0.005)
        self.engine.preflight.start_ai_test()
        self.fake.gate.set()
        self.wait()
        self.assertEqual(self.fake.max_active, 1)
        self.assertEqual(self.item("working_test")["status"], "passed")

    def test_a_quiet_pass_looks_up_the_models_in_the_background(self):
        looked_up = []
        self.engine.models.prefetch = lambda command, env=None, can_discover=None: looked_up.append(command)
        self.choose()
        self.assertEqual(self.item("working_test")["status"], "passed")
        self.assertEqual(looked_up, ["copilot"])

    def test_choosing_the_same_ai_again_keeps_its_pass(self):
        self.choose()
        self.choose()
        self.assertEqual(self.item("working_test")["status"], "passed")
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "copilot")

    def test_a_reset_cancels_it(self):
        self.fake.gate = threading.Event()
        self.engine.preflight_cli("copilot")
        record = self.engine.preflight._ai_test
        self.engine.preflight.reset_state()
        self.fake.gate.set()
        record.thread.join(10)
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "")

    def test_a_recipe_without_usable_one_shot_data_is_ignored(self):
        for bad in ({"args": ["-p"], "timeout_seconds": 5}, {"args": ["-p", "{line}"], "timeout_seconds": 0},
                    {"args": "-p {line}", "timeout_seconds": 5}, "no"):
            with self.subTest(bad=bad):
                override = self.home / "cli-recipes.json"
                override.write_text(json.dumps({"recipes": [
                    {"id": "fake", "name": "Fake", "cli_command": "fake-cli", "shell": "cmd", "command": "x",
                     "needs_mb": 1, "headless": bad}]}), encoding="utf-8")
                engine = self.build_engine()
                engine.preflight_cli("fake-cli")
                self.assertEqual(self.fake.calls_named("fake-cli"), [])

    def test_the_stand_in_can_be_tested_through_a_recipe_override(self):
        override = self.home / "cli-recipes.json"
        override.write_text(json.dumps({"recipes": [
            {"id": "fake", "name": "Fake", "cli_command": "fake-cli --x", "shell": "cmd", "command": "x",
             "needs_mb": 1, "headless": {"args": ["-p", "{line}"], "timeout_seconds": 9}}]}), encoding="utf-8")
        self.engine = self.build_engine()
        self.fake.programs["fake-cli"] = text_result("OK")
        self.engine.preflight_cli("fake-cli --x")
        self.wait()
        call = self.fake.calls_named("fake-cli")[0]
        self.assertEqual(call["argv"], ["fake-cli", "--x", "-p", self.line])
        self.assertEqual(call["timeout"], 9)


@WINDOWS_ONLY
class DetectAis(Base):
    """Item 6: the checks find which supported AIs resolve, without starting any."""

    def found_names(self):
        return [t["cli_command"] for t in self.state["preflight"]["cli"]["tools"] if t["found"]]

    def only_found(self, *commands):
        self.terminal.check_command = lambda command, env=None: (
            None if command in commands else (_ for _ in ()).throw(FileNotFoundError(command)))

    def test_lists_the_three_tools_and_never_the_free_text_one(self):
        tools = self.state["preflight"]["cli"]["tools"]
        self.assertEqual([t["cli_command"] for t in tools], ["copilot", "claude", "devin"])
        self.assertEqual([t["name"] for t in tools], ["GitHub Copilot CLI", "Claude Code", "Devin CLI"])

    def test_claude_has_one_entry_with_the_second_install_behind_it(self):
        claude = next(t for t in self.state["preflight"]["cli"]["tools"] if t["cli_command"] == "claude")
        self.assertEqual(claude["install"]["id"], "claude-installer")
        self.assertEqual([r["id"] for r in claude["other_installs"]], ["claude-winget"])

    def test_none_found(self):
        self.only_found()
        self.run_check_all()
        self.assertEqual(self.found_names(), [])
        self.assertFalse(any(t["preselect"] for t in self.state["preflight"]["cli"]["tools"]))

    def test_one_found_is_preselected(self):
        self.only_found("claude")
        self.run_check_all()
        tools = {t["cli_command"]: t for t in self.state["preflight"]["cli"]["tools"]}
        self.assertEqual(self.found_names(), ["claude"])
        self.assertTrue(tools["claude"]["preselect"])

    def test_several_found_preselects_none(self):
        self.only_found("claude", "copilot")
        self.run_check_all()
        self.assertEqual(self.found_names(), ["copilot", "claude"])
        self.assertFalse(any(t["preselect"] for t in self.state["preflight"]["cli"]["tools"]))

    def test_nothing_is_started_and_nothing_is_typed(self):
        self.only_found("claude", "copilot", "devin")
        self.run_check_all()
        self.assertEqual(self.terminal.starts, [])
        self.assertEqual(self.terminal.typed, [])

    def test_a_chosen_tool_is_not_preselected_again(self):
        self.only_found("claude")
        self.engine.preflight_cli("claude")
        self.run_check_all()
        self.assertFalse(any(t["preselect"] for t in self.state["preflight"]["cli"]["tools"]))

    def test_saved_results_still_know_which_ais_are_installed_after_a_restart(self):
        self.only_found("claude")
        self.engine = self.build_engine()
        self.assertEqual(self.found_names(), ["claude"])

    def test_the_typed_route_is_off_by_default_and_on_with_the_flag(self):
        self.assertFalse(self.state["preflight"]["custom_ai"])
        engine = Engine(self.home, self.terminal, preflight_runner=self.fake, registry_paths=lambda: [],
                        custom_ai=True)
        self.assertTrue(engine.get_state()["preflight"]["custom_ai"])


@WINDOWS_ONLY
class Recipes(Base):
    def test_recipe_needs_consent(self):
        self.assert_code("consent_required", self.engine.preflight_recipe, "claude-winget", False)
        self.assertEqual(self.terminal.starts, [])

    def test_recipe_runs_visibly_in_the_terminal_with_the_exact_command(self):
        self.engine.preflight_recipe("claude-winget", True)
        start = self.terminal.starts[-1]
        self.assertEqual(start["command"][-1], "winget install Anthropic.ClaudeCode")
        self.assertTrue(start["command"][0].lower().endswith("cmd.exe"))

    def test_powershell_recipe_uses_windows_powershell_without_changing_policy(self):
        self.engine.preflight_recipe("devin", True)
        argv = self.terminal.starts[-1]["command"]
        self.assertTrue(argv[0].lower().endswith(r"windowspowershell\v1.0\powershell.exe"))
        self.assertNotIn("-ExecutionPolicy", argv)
        self.assertEqual(argv[-1], "irm https://static.devin.ai/cli/setup.ps1 | iex")

    def test_other_recipe_has_nothing_to_run(self):
        self.assert_code("recipe_no_command", self.engine.preflight_recipe, "other", True)

    def test_unknown_recipe(self):
        self.assert_code("bad_recipe", self.engine.preflight_recipe, "nope", True)

    def test_not_enough_disk_blocks_a_recipe(self):
        self.fake.free = 10
        self.assert_code("not_enough_disk", self.engine.preflight_recipe, "copilot", True)

    def test_consent_text_shows_the_command_and_free_space(self):
        recipes = {r["id"]: r for r in self.state["preflight"]["cli"]["recipes"]}
        body = recipes["copilot"]["consent"]["body"]
        self.assertIn("winget install GitHub.Copilot", body)
        self.assertIn("500.0 GB", body)

    def test_copilot_shows_pwsh_requirement_when_missing(self):
        recipes = {r["id"]: r for r in self.state["preflight"]["cli"]["recipes"]}
        requirement = recipes["copilot"]["requirement"]
        self.assertIn("PowerShell", requirement["detail"])
        self.assertEqual(requirement["recipe"], "powershell")

    def test_copilot_requirement_clears_when_pwsh_exists(self):
        self.fake.which_map["pwsh"] = r"C:\fake\pwsh.exe"
        recipes = {r["id"]: r for r in self.state["preflight"]["cli"]["recipes"]}
        self.assertIsNone(recipes["copilot"]["requirement"])

    def test_the_app_never_answers_a_recipe(self):
        self.engine.preflight_recipe("devin", True)
        self.assertEqual(self.terminal.keystrokes, [])
        self.assertEqual(self.terminal.typed, [])

    def test_override_file_replaces_the_bundled_recipes(self):
        override = self.home / "cli-recipes.json"
        override.write_text(json.dumps({"recipes": [
            {"id": "fake", "name": "Fake", "cli_command": "fake", "shell": "cmd", "command": "echo hi", "needs_mb": 1}]}),
            encoding="utf-8")
        engine = self.build_engine()
        recipes = engine.get_state()["preflight"]["cli"]["recipes"]
        self.assertEqual([r["id"] for r in recipes], ["fake"])


@WINDOWS_ONLY
class WorkingTest(Base):
    def setUp(self):
        super().setUp()
        self.engine.preflight_cli("fake-cli")
        self.engine.preflight_test_start()
        self.folder = self.home / "cli-test"

    def test_folder_is_cleared_and_holds_only_the_input(self):
        self.assertEqual([p.name for p in self.folder.iterdir()], ["input.txt"])
        self.assertEqual((self.folder / "input.txt").read_text(encoding="utf-8"), "hello from eval coach")
        self.assertEqual(Path(self.terminal.starts[-1]["cwd"]), self.folder)

    def test_send_types_the_exact_line_only_on_request(self):
        self.assertEqual(self.terminal.typed, [])
        self.engine.preflight_test_send()
        self.assertEqual(self.terminal.typed, [
            "Read input.txt, write its contents in uppercase to output.txt, then run python --version "
            "and write what it prints to version.txt. Do nothing else."])
        self.assertTrue(self.state["preflight"]["session"]["sent"])

    def finish(self, output=None, version=None):
        if output is not None:
            (self.folder / "output.txt").write_text(output, encoding="utf-8")
        if version is not None:
            (self.folder / "version.txt").write_text(version, encoding="utf-8")
        self.engine.preflight_test_check()
        return self.item("working_test")

    def test_passing(self):
        item = self.finish("HELLO FROM EVAL COACH\r\n", "Python 3.13.17\n")
        self.assertEqual(item["status"], "passed")

    def test_trailing_whitespace_is_ignored(self):
        self.assertEqual(self.finish("HELLO FROM EVAL COACH   \n\n", "Python 3.9.1")["status"], "passed")

    def test_utf16_redirect_output_still_passes(self):
        (self.folder / "output.txt").write_text("HELLO FROM EVAL COACH", encoding="utf-8")
        (self.folder / "version.txt").write_bytes("Python 3.12.4\r\n".encode("utf-16"))
        self.engine.preflight_test_check()
        self.assertEqual(self.item("working_test")["status"], "passed")

    def test_wrong_output_content_names_reading_files(self):
        item = self.finish("hello from eval coach", "Python 3.13")
        self.assertEqual(item["status"], "failed")
        self.assertIn("reading", item["detail"])

    def test_missing_output_names_writing_files(self):
        item = self.finish(version="Python 3.13")
        self.assertEqual(item["status"], "failed")
        self.assertIn("write files", item["detail"])

    def test_missing_version_names_running_a_command(self):
        item = self.finish("HELLO FROM EVAL COACH")
        self.assertEqual(item["status"], "failed")
        self.assertIn("running a command", item["detail"])

    def test_bad_version_names_the_command(self):
        item = self.finish("HELLO FROM EVAL COACH", "not a version")
        self.assertEqual(item["status"], "failed")
        self.assertIn("not a version", item["detail"])

    def test_chat_only_tool_cannot_pass(self):
        item = self.finish()
        self.assertEqual(item["status"], "failed")
        self.assertIn("chat-only", item["next"])

    def test_missing_output_also_explains_sign_in(self):
        item = self.finish()
        self.assertIn("not signed in", item["detail"])
        self.assertIn("sign in", item["next"])

    def test_checking_before_any_test_ran_is_incomplete(self):
        shutil.rmtree(self.folder)
        self.engine.preflight_test_check()
        item = self.item("working_test")
        self.assertEqual(item["status"], "needs_you")
        self.assertIn("not finished", item["detail"])

    def test_needs_a_found_ai_first(self):
        self.engine.preflight.set_cli_command("no-such-cli")
        self.assert_code("needs_cli_command", self.engine.preflight_test_start)

    def test_poll_records_a_pass_and_stops_the_ai(self):
        (self.folder / "output.txt").write_text("HELLO FROM EVAL COACH", encoding="utf-8")
        (self.folder / "version.txt").write_text("Python 3.13.17\n", encoding="utf-8")
        stops = self.terminal.stops
        self.engine.preflight_test_poll()
        self.assertEqual(self.item("working_test")["status"], "passed")
        self.assertGreater(self.terminal.stops, stops)

    def test_poll_before_the_files_exist_records_nothing(self):
        before = self.item("working_test")
        self.engine.preflight_test_poll()
        self.assertEqual(self.item("working_test"), before)
        self.assertTrue(self.terminal.running)

    def test_poll_never_records_a_failure(self):
        (self.folder / "output.txt").write_text("wrong", encoding="utf-8")
        (self.folder / "version.txt").write_text("nothing", encoding="utf-8")
        before = self.item("working_test")
        self.engine.preflight_test_poll()
        self.assertEqual(self.item("working_test"), before)
        self.assertNotEqual(before["status"], "failed")

    def test_choosing_another_ai_ends_the_test_and_drops_its_files(self):
        (self.folder / "output.txt").write_text("HELLO FROM EVAL COACH", encoding="utf-8")
        (self.folder / "version.txt").write_text("Python 3.13.17\n", encoding="utf-8")
        stops = self.terminal.stops
        self.engine.preflight_cli("claude")
        self.assertGreater(self.terminal.stops, stops)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.engine.preflight_test_poll()
        self.engine.preflight_test_check()
        self.assertNotEqual(self.item("working_test")["status"], "passed")
        self.assertEqual(self.engine.preflight._data["test_passed_command"], "")

    def test_choosing_the_same_ai_again_leaves_the_running_test_alone(self):
        stops = self.terminal.stops
        self.engine.preflight_cli("fake-cli")
        self.assertEqual(self.terminal.stops, stops)
        self.assertTrue(self.terminal.running)
        self.assertTrue((self.folder / "input.txt").is_file())

    def test_poll_without_a_test_session_does_nothing(self):
        self.engine.preflight_stop()
        (self.folder / "output.txt").write_text("HELLO FROM EVAL COACH", encoding="utf-8")
        (self.folder / "version.txt").write_text("Python 3.13.17\n", encoding="utf-8")
        self.engine.preflight_test_poll()
        self.assertNotEqual(self.item("working_test")["status"], "passed")

    def test_check_everything_rereads_the_files(self):
        self.finish("HELLO FROM EVAL COACH", "Python 3.13.17\n")
        self.assertEqual(self.item("working_test")["status"], "passed")
        (self.folder / "output.txt").write_text("stale", encoding="utf-8")
        self.run_check_all()
        self.assertEqual(self.item("working_test")["status"], "failed")

    def test_passing_stops_the_cli(self):
        stops = self.terminal.stops
        self.finish("HELLO FROM EVAL COACH", "Python 3.13.17\n")
        self.assertGreater(self.terminal.stops, stops)


class ProjectFolder(Base):
    def test_needs_a_choice_at_first(self):
        self.run_check_all()
        self.assertEqual(self.item("project")["status"], "needs_you")

    def test_setup_passes_the_item(self):
        self.engine.preflight_cli("fake-cli")
        self.setup_project()
        item = self.item("project")
        self.assertEqual(item["status"], "passed")
        self.assertIn(str(self.project_dir), item["detail"])

    def test_refuses_to_create_a_project_in_onedrive(self):
        self.engine.preflight_cli("fake-cli")
        path = self.tmp / "OneDrive - Acme" / "project"
        self.assert_code("project_in_onedrive", self.engine.setup,
                         {"project_path": str(path), "starter": "northwind"})
        self.assertFalse(path.exists())

    def test_existing_project_in_onedrive_fails_but_keeps_progress(self):
        path = self.tmp / "OneDrive - Acme" / "project"
        paths = project.Paths(self.home, path)
        project.create_project(paths, "northwind")
        from eval_coach import state as store
        store.save_progress(paths.progress_file, store.new_progress(str(path), "fake-cli", "northwind"))
        self.engine.setup({"project_path": str(path), "starter": "northwind"})
        item = self.item("project")
        self.assertEqual(item["status"], "failed")
        self.assertIn("OneDrive", item["detail"])
        self.assertTrue(paths.progress_file.is_file())

    def test_missing_files_fail_with_a_next_action(self):
        self.setup_project_with_cli()
        (self.project_dir / "prompt-v0.md").unlink()
        self.run_check_all()
        item = self.item("project")
        self.assertEqual(item["status"], "failed")
        self.assertIn("prompt-v0.md", item["detail"])

    def setup_project_with_cli(self):
        self.engine.preflight_cli("fake-cli")
        self.setup_project()


@WINDOWS_ONLY
class Lock(Base):
    def pass_everything(self):
        self.engine.preflight_cli("fake-cli")
        self.engine.preflight_test_start()
        folder = self.home / "cli-test"
        (folder / "output.txt").write_text("HELLO FROM EVAL COACH", encoding="utf-8")
        (folder / "version.txt").write_text("Python 3.13\n", encoding="utf-8")
        self.engine.preflight_test_check()
        self.run_check_all()

    def test_steps_are_locked_until_every_item_passes(self):
        self.engine.preflight_cli("fake-cli")
        self.setup_project()
        self.assertFalse(self.state["preflight"]["passed"])
        words = self.state["step"]  # the step next to do shows its words only, with nothing to start
        self.assertTrue(words["preview"])
        self.assertIsNone(words["cli"])
        self.assertTrue(all(s["status"] == "locked" for s in self.state["steps"]))
        self.assert_code("preflight_incomplete", self.engine.step_start, "generate")

    def test_full_pass_opens_the_steps(self):
        self.pass_everything()
        self.setup_project()
        state = self.state
        self.assertTrue(state["preflight"]["passed"])
        self.assertEqual(state["current_step"], "generate")
        self.engine.step_start("generate")

    def test_preflight_passing_stops_any_preflight_cli_session(self):
        self.pass_everything()
        self.engine.preflight_recipe("claude-winget", True)
        self.assertTrue(self.terminal.running)
        stops = self.terminal.stops
        self.setup_project()
        self.assertGreater(self.terminal.stops, stops)

    def test_results_persist_across_restart(self):
        self.pass_everything()
        self.setup_project()
        engine = self.build_engine()
        state = engine.get_state()
        self.assertTrue(state["preflight"]["passed"])
        self.assertEqual(state["current_step"], "generate")

    def test_existing_project_resumes_after_preflight_passes(self):
        self.pass_everything()
        self.setup_project()
        self.engine.progress["done"].append("generate")
        self.engine._save()
        (self.home / "preflight.json").unlink()
        engine = self.build_engine()
        self.engine = engine
        state = engine.get_state()
        self.assertTrue(state["configured"], "the project is still known")
        self.assertFalse(state["preflight"]["passed"], "preflight must run again")
        self.assertTrue(state["step"]["preview"])  # words only until setup passes
        self.assertEqual(self.item("cli")["status"], "not_checked")
        self.assertEqual(state["preflight"]["cli"]["command"], "fake-cli", "the saved command carries over")
        self.assert_code("preflight_incomplete", engine.step_start, "build")
        self.pass_everything()
        state = engine.get_state()
        self.assertTrue(state["preflight"]["passed"])
        self.assertEqual(state["current_step"], "build", "the saved step is kept")
        self.assertEqual(engine.progress["done"], ["generate"])

    def test_corrupt_preflight_file_starts_over_and_says_so(self):
        (self.home / "preflight.json").write_text("{nope", encoding="utf-8")
        engine = self.build_engine()
        state = engine.get_state()
        self.assertEqual(state["preflight"]["items"][1]["status"], "not_checked")
        self.assertIn("run again", " ".join(state["setup"]["warnings"]))

    def test_a_command_that_was_not_found_does_not_replace_the_saved_one(self):
        self.pass_everything()
        self.setup_project()
        self.engine.preflight_cli("no-such-cli")
        self.assertEqual(self.engine.progress["cli_command"], "fake-cli")


class RealRunner(unittest.TestCase):
    def test_a_hung_program_is_stopped_by_its_timeout(self):
        started = time.monotonic()
        result = SystemRunner().run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=1)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - started, 20)

    def test_captures_output(self):
        result = SystemRunner().run([sys.executable, "-c", "print('hi')"], timeout=20)
        self.assertEqual(result.code, 0)
        self.assertIn("hi", result.stdout)

    def test_missing_program_does_not_raise(self):
        result = SystemRunner().run([r"C:\no\such\thing.exe"], timeout=5)
        self.assertFalse(result.started)
        self.assertNotEqual(result.code, 0)

    def test_cancel_stops_a_program(self):
        cancel = threading.Event()
        cancel.set()
        result = SystemRunner().run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=60, cancel=cancel)
        self.assertTrue(result.cancelled)


@WINDOWS_ONLY
class TerminalOutputIsIgnored(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-pf-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        FakePty.created = []
        self.terminal = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: c.split(),
                                        command_checker=lambda c, env=None: None)
        self.addCleanup(self.terminal.stop)
        self.engine = Engine(self.tmp / "home", self.terminal, preflight_runner=FakeRunner(), registry_paths=lambda: [])

    def test_a_terminal_that_prints_the_right_answers_still_fails(self):
        self.engine.preflight_cli("fake-cli")
        self.engine.preflight_test_start()
        FakePty.created[-1].feed(b"HELLO FROM EVAL COACH\r\nPython 3.13.17\r\n")
        self.engine.preflight_test_check()
        item = next(i for i in self.engine.get_state()["preflight"]["items"] if i["id"] == "working_test")
        self.assertEqual(item["status"], "failed")
        self.assertEqual(FakePty.created[-1].written, [], "the app never answers the CLI")

    def test_devin_gets_a_terminal_marker_and_other_clis_do_not(self):
        env = {"PATH": "C:\\x"}
        self.terminal.start("devin", str(self.tmp), "x", env=env)
        self.assertIn("WT_SESSION", FakePty.created[-1].env)
        self.terminal.start("fake-cli", str(self.tmp), "x", env=env)
        self.assertEqual(FakePty.created[-1].env, env)
        self.terminal.start("devin", str(self.tmp), "x", env={"PATH": "C:\\x", "TERM_PROGRAM": "vscode"})
        self.assertNotIn("WT_SESSION", FakePty.created[-1].env)

    def test_items_are_numbered_without_gaps(self):
        def numbers():
            items = self.engine.get_state()["preflight"]["items"]
            return [i["number"] for i in items if i["applies"]]

        self.engine.preflight_track("script")
        self.assertEqual(numbers(), list(range(1, len(numbers()) + 1)))
        self.engine.preflight_track("promptfoo")
        self.assertEqual(numbers(), list(range(1, len(numbers()) + 1)))


class Shutdown(Base):
    def test_cancels_a_running_job(self):
        self.engine.preflight_track("promptfoo")
        self.fake.which_map["node"] = None
        released = threading.Event()

        def slow_curl(argv, env, cwd):
            released.wait(5)
            return Result(code=1)

        self.fake.programs["curl"] = slow_curl
        self.engine.preflight_install("node", True)
        job = self.engine.preflight._job
        self.engine.preflight.shutdown()
        self.assertTrue(job.cancel.is_set())
        released.set()


class MacBase(unittest.TestCase):
    """Preflight on a Mac, run on any system: the platform is injected and every program is a fake."""

    MACOS = "14.5"
    MACHINE = "arm64"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-mac-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.user = self.tmp / "user"
        self.user.mkdir()
        self.fake = FakeRunner()
        self.fake.which_map = {"python3": "/usr/local/bin/python3"}
        self.fake.programs["python3"] = text_result("Python 3.13.18\n")
        self.terminal = FakeTerminal()
        self.pre = self.build()

    def build(self, **kwargs):
        options = dict(runner=self.fake, platform="darwin", machine=self.MACHINE, user_home=str(self.user),
                       mac_version_text=self.MACOS, python_path="/opt/py/bin/python3")
        options.update(kwargs)
        return pf.Preflight(self.home, self.terminal, **options)

    def check_all(self):
        self.pre.start_check_all()
        self.pre.wait_for_job(10)

    def item(self, item_id):
        return next(i for i in self.pre.view(None, None)["items"] if i["id"] == item_id)

    def path_entries(self, env=None):
        return (env or self.pre.env())["PATH"].split(os.pathsep)


class MacPython(MacBase):
    def test_the_python_page_shows_the_path_and_version(self):
        self.check_all()
        item = self.item("python")
        self.assertEqual(item["status"], "passed")
        self.assertIn("3.13.18", item["detail"])
        self.assertIn("/usr/local/bin/python3", item["detail"])
        self.assertEqual(self.fake.calls_named("python3")[0]["argv"], ["/usr/local/bin/python3", "--version"])

    def test_python_below_3_9_asks_to_start_again(self):
        self.fake.programs["python3"] = text_result("Python 3.8.10\n")
        self.check_all()
        item = self.item("python")
        self.assertEqual(item["status"], "failed")
        self.assertIn("3.8.10", item["detail"])
        self.assertIn("start eval-coach again", item["next"])

    def test_no_python_asks_to_start_again(self):
        self.fake.which_map = {}
        self.check_all()
        item = self.item("python")
        self.assertEqual(item["status"], "failed")
        self.assertIn("start eval-coach again", item["next"])

    def test_apples_stub_is_never_run(self):
        self.fake.which_map = {"python3": "/usr/bin/python3"}
        with mock.patch.object(pf.os.path, "exists", return_value=False):
            self.check_all()
        self.assertEqual(self.item("python")["status"], "failed")
        self.assertEqual(self.fake.calls_named("python3"), [], "running the stub would open Apple's installer")

    def test_apples_python_is_used_when_the_command_line_tools_exist(self):
        self.fake.which_map = {"python3": "/usr/bin/python3"}
        with mock.patch.object(pf.os.path, "exists", return_value=True):
            self.check_all()
        self.assertEqual(self.item("python")["status"], "passed")

    def test_the_private_python_comes_first_on_the_path(self):
        private = self.home / "runtime" / "python" / "bin"
        private.mkdir(parents=True)
        (private / "python3").write_bytes(b"x")
        self.assertEqual(self.path_entries()[0], str(private))

    def test_the_found_python_comes_first_without_a_private_copy(self):
        self.assertEqual(self.path_entries()[0], os.path.dirname(os.path.abspath("/opt/py/bin/python3")))


class MacPathDiscovery(MacBase):
    class PathTerminal(FakeTerminal):
        """check_command succeeds only when a file with that name sits in a folder of the given PATH."""

        def check_command(self, command, env=None):
            for folder in (env or {}).get("PATH", "").split(os.pathsep):
                if folder and (Path(folder) / command).is_file():
                    return
            raise FileNotFoundError(command)

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"PATH": str(self.tmp / "empty")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.terminal = self.PathTerminal()
        self.pre = self.build()

    def test_an_ai_installed_while_the_app_is_open_is_found(self):
        self.assertEqual(self.pre.view(None, None)["cli"]["found"], [])
        local = self.user / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "claude").write_bytes(b"x")
        self.check_all()
        view = self.pre.view(None, None)
        self.assertEqual(view["cli"]["found"], ["claude"])
        self.assertIn(str(local), self.path_entries())

    def test_the_ai_s_own_folder_from_the_recipes_is_searched(self):
        own = self.user / "own-ai" / "bin"
        own.mkdir(parents=True)
        (own / "devin").write_bytes(b"x")
        recipes = {"recipes": [{"id": "devin", "name": "Devin CLI", "cli_command": "devin", "shell": "cmd",
                                "command": "x", "needs_mb": 1, "plain": "p", "source": "s",
                                "platforms": {"windows": {"available": True},
                                              "mac": {"shell": "zsh", "path_dirs": ["own-ai/bin"]}}}]}
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "cli-recipes.json").write_text(json.dumps(recipes), encoding="utf-8")
        self.pre = self.build()
        self.check_all()
        self.assertEqual(self.pre.view(None, None)["cli"]["found"], ["devin"])

    def test_nothing_is_started_by_the_search(self):
        local = self.user / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "copilot").write_bytes(b"x")
        self.check_all()
        self.assertEqual([c for c in self.fake.calls if self.fake.name_of(c["argv"]) == "copilot"], [])
        self.assertEqual(self.terminal.starts, [])


class MacNodeInstall(MacBase):
    def setUp(self):
        super().setUp()
        self.pre.set_track("promptfoo")
        self.fake.which_map = {"python3": "/usr/local/bin/python3"}
        self.payload = b"pretend node tarball" * 100
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.pin_name = "mac-arm64" if self.MACHINE == "arm64" else "mac-x64"
        pin = hostos.NODE_PINS[self.pin_name]._replace(sha256=self.sha)
        patcher = mock.patch.dict(hostos.NODE_PINS, {self.pin_name: pin})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pin = pin

        def curl(argv, env, cwd):
            (Path(cwd) / argv[argv.index("--output") + 1]).write_bytes(self.payload)
            return Result(code=0)

        def tar(argv, env, cwd):
            target = Path(cwd) / argv[argv.index("-C") + 1] / self.pin.folder / "bin"
            target.mkdir(parents=True)
            (target / "node").write_bytes(b"binary")
            return Result(code=0)

        self.fake.programs["curl"] = curl
        self.fake.programs["tar"] = tar
        self.fake.programs["node"] = text_result("v26.13.0\n")

    def install(self):
        self.pre.start_install("node", True)
        self.pre.wait_for_job(10)

    def test_the_build_for_this_chip_is_downloaded_unpacked_and_put_in_place(self):
        self.install()
        self.assertEqual(self.item("node")["status"], "passed", self.item("node"))
        curl = self.fake.calls_named("curl")[0]["argv"]
        self.assertEqual(curl[0], "/usr/bin/curl")
        self.assertNotIn("--ssl-no-revoke", curl)
        self.assertEqual(curl[-1], self.pin.url)
        self.assertIn("darwin-arm64", curl[-1])
        tar = self.fake.calls_named("tar")[0]["argv"]
        self.assertEqual(tar[:2], ["/usr/bin/tar", "-xzf"])
        self.assertTrue((self.home / "runtime" / "node" / "bin" / "node").is_file())
        self.assertFalse((self.home / "runtime" / f"{self.pin.folder}.tar.gz").exists())
        self.assertFalse((self.home / "runtime" / "node.new").exists())
        self.assertIn(str(self.home / "runtime" / "node" / "bin"), self.path_entries())

    def test_a_wrong_fingerprint_installs_nothing(self):
        def tampered(argv, env, cwd):
            (Path(cwd) / argv[argv.index("--output") + 1]).write_bytes(b"tampered")
            return Result(code=0)

        self.fake.programs["curl"] = tampered
        self.install()
        item = self.item("node")
        self.assertEqual(item["status"], "failed")
        self.assertIn("fingerprint", item["detail"])
        self.assertEqual(self.fake.calls_named("tar"), [])
        self.assertFalse((self.home / "runtime" / "node").exists())
        self.assertFalse((self.home / "runtime" / f"{self.pin.folder}.tar.gz").exists())

    def test_the_download_must_fit_the_mac_disk_need(self):
        self.fake.free = 100 * 10**6
        self.install()
        self.assertEqual(self.item("node")["status"], "failed")
        self.assertEqual(self.fake.calls, [])

    def test_the_consent_text_has_the_mac_sizes_and_no_windows_words(self):
        self.fake.which_map = {"python3": "/usr/local/bin/python3"}
        self.check_all()
        body = self.item("node")["install"]["consent"]["body"]
        self.assertIn("58 MB", body)
        self.assertNotIn("registry", body)
        self.assertNotIn("113 MB", body)

    def test_npx_runs_the_private_npx_script_directly(self):
        node = self.home / "runtime" / "node"
        (node / "bin").mkdir(parents=True)
        (node / "bin" / "node").write_bytes(b"x")
        script = node / "lib" / "node_modules" / "npm" / "bin" / "npx-cli.js"
        script.parent.mkdir(parents=True)
        script.write_text("//", encoding="utf-8")
        self.fake.which_map["node"] = str(node / "bin" / "node")
        self.assertEqual(self.pre.npx_argv(self.pre.env()), [str(node / "bin" / "node"), str(script)])


class MacNodeInstallOnIntel(MacNodeInstall):
    MACHINE = "x86_64"

    def test_the_build_for_this_chip_is_downloaded_unpacked_and_put_in_place(self):
        self.pin_name = "mac-x64"
        self.pin = hostos.NODE_PINS["mac-x64"]
        self.assertIn("darwin-x64", self.pin.url)
        self.install()
        self.assertIn("darwin-x64", self.fake.calls_named("curl")[0]["argv"][-1])


class MacOldMacos(MacBase):
    MACOS = "13.2.1"

    def setUp(self):
        super().setUp()
        self.pre.set_track("promptfoo")

    def test_nothing_is_downloaded_and_the_script_track_is_suggested(self):
        with self.assertRaises(pf.PreflightError) as caught:
            self.pre.start_install("node", True)
        self.assertEqual(caught.exception.code, "node_needs_newer_macos")
        self.assertIn("13.2.1", caught.exception.message)
        self.assertIn("13.5", caught.exception.message)
        self.assertEqual(self.fake.calls, [])

    def test_the_node_page_says_why_and_offers_no_install(self):
        self.check_all()
        item = self.item("node")
        self.assertEqual(item["status"], "needs_you")
        self.assertIn("13.5", item["detail"])
        self.assertIn("13.2.1", item["detail"])
        self.assertIn("Script track", item["next"])
        self.assertIsNone(item["install"])

    def test_the_track_choice_says_the_promptfoo_track_needs_a_newer_macos(self):
        hint = self.pre.view(None, None)["track_options"]["promptfoo"]["hint"]
        self.assertIn("13.5", hint)
        self.assertIn("Script track", hint)

    def test_a_node_already_on_the_computer_still_counts(self):
        self.fake.which_map["node"] = "/opt/homebrew/bin/node"
        self.fake.programs["node"] = text_result("v24.1.0\n")
        self.check_all()
        self.assertEqual(self.item("node")["status"], "passed")


class MacCurrentMacosShowsNoOldMacosText(MacBase):
    def test_track_hint_is_unchanged(self):
        hint = self.pre.view(None, None)["track_options"]["promptfoo"]["hint"]
        self.assertNotIn("13.5", hint)


class MacRecipes(MacBase):
    def recipes(self):
        return {r["id"]: r for r in self.pre.recipes}

    def test_only_the_mac_installs_are_offered(self):
        self.assertEqual(sorted(self.recipes()), ["claude-installer", "copilot", "devin", "other"])

    def test_commands_run_in_zsh_and_need_no_powershell(self):
        recipes = self.recipes()
        self.assertEqual(recipes["copilot"]["command"], "curl -fsSL https://gh.io/copilot-install | bash")
        self.assertEqual(recipes["claude-installer"]["command"], "curl -fsSL https://claude.ai/install.sh | bash")
        self.assertEqual(recipes["devin"]["command"], "curl -fsSL https://cli.devin.ai/install.sh | bash")
        self.assertNotIn("requires", recipes["copilot"])
        for name in ("copilot", "claude-installer", "devin"):
            self.assertEqual(recipes[name]["shell"], "zsh")
            self.assertNotIn("winget", recipes[name]["command"])

    def test_the_recipe_runs_through_a_login_zsh(self):
        argv = self.pre.recipe_argv("devin", True)
        self.assertEqual(argv, ["/bin/zsh", "-lc", "curl -fsSL https://cli.devin.ai/install.sh | bash"])

    def test_the_choose_page_lists_one_install_per_tool(self):
        tools = self.pre.view(None, None)["cli"]["tools"]
        self.assertEqual([t["cli_command"] for t in tools], ["copilot", "claude", "devin"])
        self.assertTrue(all(t["install"]["command"].startswith("curl -fsSL https://") for t in tools))
        self.assertEqual([t["other_installs"] for t in tools], [[], [], []])

    def test_every_tool_keeps_its_model_data(self):
        for name in ("copilot", "claude-installer", "devin"):
            self.assertIn("sonnet", self.recipes()[name]["models"])


class RecipePlatforms(unittest.TestCase):
    """The shipped recipes: Windows values are the committed baseline, and every recipe says where it is offered."""

    def setUp(self):
        self.shipped = json.loads(resources_text("content/cli-recipes.json"))["recipes"]

    def test_every_recipe_names_both_platforms(self):
        for recipe in self.shipped:
            self.assertEqual(set(recipe["platforms"]), {"windows", "mac"}, recipe["id"])

    def test_windows_values_equal_the_baseline(self):
        baseline = json.loads((helpers.GOLDEN / "cli-recipes-windows.json").read_text(encoding="utf-8"))["recipes"]
        without = [{k: v for k, v in r.items() if k != "platforms"} for r in self.shipped]
        self.assertEqual(without, baseline)

    def test_windows_offers_exactly_the_baseline_recipes(self):
        baseline = json.loads((helpers.GOLDEN / "cli-recipes-windows.json").read_text(encoding="utf-8"))["recipes"]
        with tempfile.TemporaryDirectory() as tmp:
            offered = pf.Preflight(Path(tmp) / "home", FakeTerminal(), runner=FakeRunner(), platform="win32").recipes
        self.assertEqual(offered, baseline)

    def test_a_mac_recipe_changes_only_what_differs(self):
        for recipe in self.shipped:
            mac = recipe["platforms"]["mac"]
            for field in mac:
                self.assertIn(field, ("available", "shell", "command", "needs_mb", "plain", "requires", "path_dirs",
                                      "source"), recipe["id"])


def resources_text(name):
    from eval_coach import resources
    return resources.read_text(name)


class MacTerminalWords(unittest.TestCase):
    def test_the_words_of_the_mac_run_have_no_windows_install_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            pre = pf.Preflight(Path(tmp) / "home", FakeTerminal(), runner=FakeRunner(), platform="darwin",
                               machine="arm64", mac_version_text="14.5")
            text = json.dumps(pre.content)
        self.assertNotIn("Company Portal or Software Center", text)
        self.assertNotIn("platform_overrides", text)


if __name__ == "__main__":
    unittest.main()
