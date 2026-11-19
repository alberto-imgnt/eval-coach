from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import GOLDEN, NORTHWIND, FakeTerminal, wait_until

from eval_coach.engine import Engine, EngineError
from eval_coach.project import Paths, sealed_id
from eval_coach.scan import scan_source
from eval_coach.state import CorruptStateError, load_progress
from eval_coach import gates, runner

KEY_SENTINEL = "SENTINEL-ANSWER-KEY-TEXT"
STDLIB_CHECKER = (GOLDEN / "reference-check.py").read_text(encoding="utf-8")
EXPECTED_LINES = {
    "generate": "Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.",
    "build": "Read skills/build-eval-script/SKILL.md and follow it in build mode on test-cases.md.",
    "fixtures": "Read skills/make-eval-fixtures/SKILL.md and follow it for test-cases.md and prompt-v0.md, with one change: write only the two fixture files. Do not write the answer key, and do not say what is wrong with either fixture.",
    "key": "Read skills/make-eval-fixtures/SKILL.md. The two fixture files are already in fixtures/. Do not change them. Follow only the Answer key section, using test-cases.md, and write fixtures/answer-key.md. Do nothing else.",
    "readback": "Read skills/build-eval-script/SKILL.md and follow it in explain mode on test-cases.md and check.py.",
    "fix": "I changed test-cases.md. Update check.py to match, changing only the functions whose threshold changed. Then run the two fixtures again.",
}
IDS = ["C1", "C2", "C3", "C4", "C5", "C6"]


def tight_checker():
    """The reference checker with the tightened C3 from the expected-results notes."""
    original = "return True, 'found \"Blocker:\" and \"Need:\"'"
    assert original in STDLIB_CHECKER
    return STDLIB_CHECKER.replace(
        original,
        "if 'test data' not in text.split('Blocker:', 1)[1].splitlines()[0]:\n"
        "        return False, 'blocker does not mention test data'\n    " + original)


class EngineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-test-"))
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        self.terminal = FakeTerminal()
        helpers.write_passed_preflight(self.home)
        self.engine = self.new_engine()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def new_engine(self):
        return Engine(self.home, self.terminal, poll_interval=0.01)

    def setup_project(self, **extra):
        body = {"project_path": str(self.project), "cli_command": "mycli --model sonnet", "starter": "northwind"}
        body.update(extra)
        self.engine.setup(body)
        self.paths = Paths(self.home, self.project)

    def state(self, step=None):
        return self.engine.get_state(step)

    def data(self, step):
        return self.state(step)["step"]["data"]

    def status(self, step):
        return next(s["status"] for s in self.state()["steps"] if s["id"] == step)

    def check(self, step):
        self.engine.step_check(step)
        return self.state(step)["step"]["last_check"]

    def assert_code(self, code, fn, *args):
        with self.assertRaises(EngineError) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.code, code)

    def assert_key_hidden(self):
        """The key text appears in no state response, for any selected step."""
        for step in (None, "generate", "build", "fixtures", "readback", "predict", "key", "run", "fix", "baseline"):
            self.assertNotIn(KEY_SENTINEL, json.dumps(self.state(step)))
        self.assertFalse(self.paths.project_key.exists())

    # --- walking the steps ---

    def paste(self, step):
        """Paste the step's line into the AI window, as a participant does. Returns the line."""
        line = helpers.paste_step_line(self.engine, step)
        self.assertEqual(self.terminal.keystrokes[-1], (line + "\r").encode("utf-8"))
        return line

    def do_generate(self, model=None):
        for n in range(1, 6):
            self.engine.step_start("generate")
            self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.paths.blind))
            self.assertEqual(sorted(p.name for p in self.paths.blind.iterdir()), ["prompt.md"])
            self.paste("generate")
            shutil.copy(str(NORTHWIND / f"sample-run-{n}.txt"), str(self.paths.blind_output))
            self.assertTrue(wait_until(lambda: self.paths.run_file(n).is_file()), f"run {n} never saved")
        if model is not None:  # the test-only typed route; the app records the model itself when it starts the AI
            self.engine.step_submit("generate", {"model_name": model})

    def write_checker(self, source=STDLIB_CHECKER):
        self.paths.check_py.write_text(source, encoding="utf-8")

    def do_build(self):
        self.engine.step_start("build")
        self.write_checker()
        self.engine.step_run_checker("build", "first_look")
        self.engine.step_submit("build", {"checklist": {"read_not_checked": True, "read_interpretation": True}})

    def do_fixtures(self):
        self.engine.step_start("fixtures")
        self.paths.work_fixtures.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(NORTHWIND / "fixture-bad.txt"), str(self.paths.work_fixtures))
        shutil.copy(str(NORTHWIND / "fixture-polished-but-wrong.txt"), str(self.paths.work_fixtures))

    def do_key(self):
        self.engine.step_start("key")
        self.write_key()

    def write_key(self, text=f"# Key\n{KEY_SENTINEL}\n"):
        self.paths.key_work_key.write_text(text, encoding="utf-8")

    def do_readback(self):
        self.engine.step_start("readback")
        (self.paths.examples / "c1-pass.txt").write_text("short", encoding="utf-8")
        self.engine.step_submit("readback", {"answers": {c: "yes" for c in IDS}, "note": "ok"})

    PREDICT = {
        "bad": {"C1": "F", "C2": "F", "C3": "F", "C4": "F", "C5": "F", "C6": "P"},
        "polished": {"C1": "P", "C2": "P", "C3": "F", "C4": "P", "C5": "P", "C6": "P"},
        "answers": {"wrong": "the blocker is denied", "catches": "C3", "worst_guess": "C5"},
    }

    def do_predict(self, lock=True, **override):
        body = dict(self.PREDICT, **override)
        if lock:
            body["lock"] = True
        self.engine.step_submit("predict", body)

    def do_run(self):
        self.engine.step_run_checker("run", "fixtures")

    def to_step(self, step):
        order = ["generate", "build", "fixtures", "readback", "predict", "key", "run"]
        actions = {"generate": self.do_generate, "build": self.do_build, "fixtures": self.do_fixtures,
                   "readback": self.do_readback, "predict": self.do_predict, "key": self.do_key, "run": self.do_run}
        self.setup_project()
        for name in order:
            if name == step:
                return
            actions[name]()
            if name == "run":
                self.engine.step_submit("run", {"classifications": {"C3:polished": "predicted_wrong"}})
            result = self.check(name)
            self.assertTrue(result["ok"], (name, result))


class WalkAllSteps(EngineCase):
    def test_full_walk(self):
        self.setup_project()
        self.assertTrue(self.state()["configured"])
        self.assertEqual(self.state()["current_step"], "generate")
        self.assert_key_hidden()

        # generate
        self.assertFalse(self.check("generate")["ok"])
        self.do_generate()
        self.assertEqual(self.state()["step"]["data"]["current_run"], 5)
        self.assertEqual(self.state("generate")["step"]["cli"]["line"], EXPECTED_LINES["generate"])
        self.assertTrue(self.check("generate")["ok"])
        self.assertEqual(self.status("build"), "active")
        self.assert_key_hidden()

        # build
        self.assertFalse(self.check("build")["ok"])
        self.do_build()
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.project))
        self.assertEqual(self.paste("build"), EXPECTED_LINES["build"])
        result = self.data("build")["first_look"]
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual([r["verdict"] for r in result["files"][0]["rows"]], ["P"] * 6)
        self.assertTrue(self.check("build")["ok"])
        self.assert_key_hidden()

        # fixtures
        self.do_fixtures()
        cwd = Path(self.terminal.starts[-1]["cwd"])
        self.assertEqual(cwd, self.paths.fixtures_work)
        self.assertEqual(sorted(p.name for p in cwd.iterdir()),
                         ["fixtures", "prompt-v0.md", "skills", "test-cases.md"])
        self.assertTrue((cwd / "skills" / "make-eval-fixtures" / "SKILL.md").is_file())
        self.assertEqual([p.name for p in (cwd / "skills").iterdir()], ["make-eval-fixtures"])
        self.assertEqual(self.paste("fixtures"), EXPECTED_LINES["fixtures"])
        self.assert_key_hidden()
        self.assertTrue(self.check("fixtures")["ok"])
        self.assertTrue((self.paths.fixtures / "fixture-bad.txt").is_file())
        self.assertTrue((self.paths.fixtures / "fixture-polished-but-wrong.txt").is_file())
        self.assertFalse(self.paths.project_key.exists())
        self.assertFalse((self.paths.work_fixtures / "answer-key.md").exists())
        self.assertFalse(self.paths.sealed_key.exists())
        self.assertEqual(self.data("fixtures"), {"files": [{"name": "fixture-bad.txt", "present": True},
                                                           {"name": "fixture-polished-but-wrong.txt", "present": True}],
                                                 "example": {"offered": True, "would_replace": True}})
        self.assert_key_hidden()

        # readback
        self.assertFalse(self.check("readback")["ok"])
        self.do_readback()
        self.assertEqual(self.paste("readback"), EXPECTED_LINES["readback"])
        self.assertTrue(self.check("readback")["ok"])
        self.assert_key_hidden()

        # predict
        self.assertIn("Blocker:", self.data("predict")["polished_text"])
        self.assertFalse(self.data("predict")["manual_rows"])
        self.do_predict(lock=False)
        self.assertFalse(self.check("predict")["ok"])  # complete, but not locked
        self.engine.step_submit("predict", {"lock": True})
        self.assertTrue(self.check("predict")["ok"])
        self.assert_key_hidden()

        # key
        self.assertEqual(self.status("key"), "active")
        self.assertEqual(self.data("key"), {"files": [{"name": "answer-key.md", "present": False}], "key_held": False})
        self.assertFalse(self.check("key")["ok"])
        self.do_key()
        cwd = Path(self.terminal.starts[-1]["cwd"])
        self.assertEqual(cwd, self.paths.key_work)
        self.assertEqual(self.paste("key"), EXPECTED_LINES["key"])
        self.assertTrue(self.data("key")["files"][0]["present"])
        self.assertFalse(self.data("key")["key_held"])
        self.assert_key_hidden()
        self.assertTrue(self.check("key")["ok"])
        self.assertFalse(self.terminal.running)
        self.assertFalse(self.paths.key_work_key.exists())
        self.assertEqual(self.paths.sealed_dir.name, sealed_id(self.project))
        self.assertIn(KEY_SENTINEL, self.paths.sealed_key.read_text(encoding="utf-8"))
        self.assertTrue(self.data("key")["key_held"])
        self.assert_key_hidden()

        # run
        self.assertEqual(self.data("run")["grid"], [])
        self.assertIsNone(self.data("run")["answer_key_markdown"])
        self.assertFalse(self.check("run")["ok"])
        self.do_run()
        data = self.data("run")
        self.assertEqual(data["result"]["exit_code"], 1)
        self.assertTrue(data["result"]["ok"], data["result"])
        self.assertIn(KEY_SENTINEL, data["answer_key_markdown"])
        self.assertTrue(data["polished_passed_all"])
        surprises = [g["id"] for g in data["grid"] if g["polished_surprise"] or g["bad_surprise"]]
        self.assertEqual(surprises, ["C3"])
        self.assertFalse(self.check("run")["ok"])  # surprise not classified
        self.engine.step_submit("run", {"classifications": {"C3:polished": "predicted_wrong"}})
        self.assertTrue(self.check("run")["ok"])

        # fix
        self.assertFalse(self.data("fix")["can_skip"])
        self.assertFalse(self.check("fix")["ok"])
        text = self.data("fix")["test_cases_text"]
        self.assertIn("### C3", text)
        tightened = text.replace('both appear', 'both appear, and the text after "Blocker:" mentions "test data"')
        self.engine.step_submit("fix", {"test_cases_text": tightened})
        self.assertTrue(self.data("fix")["test_cases_changed"])
        self.assertFalse(self.data("fix")["checker_changed_after"])
        self.engine.step_start("fix")
        self.assertEqual(self.paste("fix"), EXPECTED_LINES["fix"])
        self.write_checker(tight_checker())
        self.assertTrue(self.data("fix")["checker_changed_after"])
        self.engine.step_run_checker("fix", "fixtures")
        data = self.data("fix")
        self.assertTrue(data["polished_fails"], data["rerun"])
        result = self.check("fix")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["nudges"], [])
        self.assertEqual(self.state()["current_step"], "baseline")
        self.assertEqual(self.state("fix")["step"]["status"], "done")
        self.assertFalse(self.paths.project_key.exists())

        # nothing secret reached progress.json
        progress = self.paths.progress_file.read_text(encoding="utf-8")
        self.assertNotIn(KEY_SENTINEL, progress)
        for name in ("fixture-bad.txt", "fixture-polished-but-wrong.txt"):
            for line in (NORTHWIND / name).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.assertNotIn(line.strip(), progress)


class Sequence(EngineCase):
    def test_locked_steps_reject_actions(self):
        self.setup_project()
        self.assert_code("step_locked", self.engine.step_start, "build")
        self.assert_code("step_locked", self.engine.step_check, "run")
        self.assert_code("step_locked", self.engine.step_submit, "fix", {"explanation": "x"})
        self.assert_code("unknown_step", self.engine.step_start, "nope")

    def test_needs_setup_first(self):
        self.assert_code("not_configured", self.engine.step_start, "generate")
        self.assertFalse(self.state()["configured"])
        self.assertIsNone(self.state()["step"])

    def test_done_steps_stay_viewable(self):
        self.to_step("build")
        self.assertEqual(self.state("generate")["step"]["status"], "done")
        self.assert_code("step_done", self.engine.step_start, "generate")

    def test_steps_without_a_cli(self):
        self.to_step("predict")
        self.assertIsNone(self.state("predict")["step"]["cli"])
        self.assert_code("no_cli", self.engine.step_start, "predict")

    def test_send_is_refused_for_every_paste_step(self):
        self.setup_project()
        self.assert_code("not_supported", self.engine.step_send, "generate")
        self.engine.step_start("generate")
        self.assert_code("not_supported", self.engine.step_send, "generate")
        self.assertEqual(self.terminal.typed, [])

    def test_typed_lines_match_the_spec_exactly(self):
        for step, line in EXPECTED_LINES.items():
            self.assertEqual(self.engine.content["steps"][step]["line"], line)
        self.assertNotIn("line", self.engine.content["steps"]["predict"])
        self.assertNotIn("line", self.engine.content["steps"]["run"])


class Generate(EngineCase):
    def test_whitespace_is_not_an_answer(self):
        self.setup_project()
        self.engine.step_start("generate")
        self.paths.blind_output.write_text("   \n", encoding="utf-8")
        self.assertFalse(wait_until(lambda: self.paths.run_file(1).exists(), timeout=0.3))
        self.engine.step_stop("generate")

    def test_waits_until_the_file_is_stable(self):
        self.engine = Engine(self.home, self.terminal, poll_interval=0.05)
        self.setup_project()
        self.engine.step_start("generate")
        self.paths.blind_output.write_text("partial", encoding="utf-8")
        self.paths.blind_output.write_text("the whole answer", encoding="utf-8")
        self.assertTrue(wait_until(lambda: self.paths.run_file(1).exists()))
        self.assertEqual(self.paths.run_file(1).read_text(encoding="utf-8"), "the whole answer")

    def test_finishing_stops_the_cli_and_pushes_state(self):
        self.setup_project()
        self.engine.step_start("generate")
        self.paste("generate")
        self.paths.blind_output.write_text("answer", encoding="utf-8")
        self.assertTrue(wait_until(lambda: self.terminal.state_events == 1))
        self.assertFalse(self.terminal.running)
        data = self.data("generate")
        self.assertEqual(data["current_run"], 2)
        self.assertEqual(data["runs"][0], {"n": 1, "done": True, "words": 1})
        detail = self.state("generate")["step"]
        self.assertFalse(detail["cli"]["started"])
        self.assertFalse(detail["cli"]["sent"])

    def test_stop_cancels_the_watcher(self):
        self.setup_project()
        self.engine.step_start("generate")
        self.engine.step_stop("generate")
        self.paths.blind_output.write_text("late", encoding="utf-8")
        self.assertFalse(wait_until(lambda: self.paths.run_file(1).exists(), timeout=0.3))

    def test_gate_needs_the_model_name(self):
        self.setup_project()
        self.do_generate(model="")
        self.assertFalse(self.check("generate")["ok"])
        self.engine.step_submit("generate", {"model_name": "mid"})
        self.assertTrue(self.check("generate")["ok"])


class Build(EngineCase):
    def test_scan_rejects_a_network_import(self):
        self.to_step("build")
        self.write_checker("import requests\nprint('hi')\n")
        self.assertEqual(len(self.data("build")["scan"]), 1)
        self.assert_code("scan_failed", self.engine.step_run_checker, "build", "first_look")
        result = self.check("build")
        item = next(i for i in result["items"] if i["label"] == "No network or AI calls")
        self.assertFalse(item["ok"])
        self.assertIn("requests", item["detail"])
        self.assertFalse(result["ok"])

    def test_scan_accepts_a_stdlib_checker(self):
        self.to_step("build")
        self.write_checker()
        self.assertEqual(self.data("build")["scan"], [])

    def test_gate_needs_each_handback_ticked(self):
        self.to_step("build")
        self.write_checker()
        self.engine.step_run_checker("build", "first_look")
        self.engine.step_submit("build", {"checklist": {"read_not_checked": True}})
        self.assertFalse(self.check("build")["ok"])
        self.engine.step_submit("build", {"checklist": {"read_interpretation": True}})
        self.assertTrue(self.check("build")["ok"])

    def test_gate_needs_the_first_look(self):
        self.to_step("build")
        self.write_checker()
        self.engine.step_submit("build", {"checklist": {"read_not_checked": True, "read_interpretation": True}})
        self.assertFalse(self.check("build")["ok"])

    def test_unknown_checklist_item(self):
        self.to_step("build")
        self.assert_code("bad_input", self.engine.step_submit, "build", {"checklist": {"bogus": True}})

    def test_any_step_with_checklist_items_accepts_a_checklist(self):
        self.engine.content["steps"]["generate"]["checklist"] = [{"id": "ticked", "label": "A box"}]
        self.setup_project()
        self.engine.step_submit("generate", {"checklist": {"ticked": True}})
        self.assertEqual(self.state("generate")["step"]["checklist"],
                         [{"id": "ticked", "label": "A box", "checked": True}])
        self.assertTrue(self.engine.progress["steps"]["generate"]["checklist"]["ticked"])

    def test_a_step_with_only_a_checklist_accepts_one(self):
        self.engine.content["steps"]["fixtures"]["checklist"] = [{"id": "ticked", "label": "A box"}]
        self.to_step("fixtures")
        self.engine.step_submit("fixtures", {"checklist": {"ticked": True}})
        self.assertTrue(self.state("fixtures")["step"]["checklist"][0]["checked"])

    def test_a_step_without_checklist_items_or_inputs_still_refuses(self):
        self.to_step("fixtures")
        self.assert_code("bad_input", self.engine.step_submit, "fixtures", {"checklist": {"x": True}})


class ScanRules(unittest.TestCase):
    def test_every_blocked_import(self):
        for source in ("import socket", "import http.client", "from urllib.request import urlopen",
                       "import requests", "import httpx", "import aiohttp", "import ftplib", "import smtplib",
                       "import openai", "from anthropic import Anthropic", "import google.generativeai",
                       "from google import generativeai", "import langchain.chains", "import litellm",
                       "import boto3", "import subprocess", "__import__('requests')",
                       "import importlib\nimportlib.import_module('openai')"):
            with self.subTest(source=source):
                self.assertTrue(scan_source(source))

    def test_allowed_imports(self):
        for source in ("import re, sys, json", "from pathlib import Path", "import google",
                       "import httpxlike"):
            with self.subTest(source=source):
                self.assertEqual(scan_source(source), [])

    def test_invalid_python(self):
        self.assertIn("not valid Python", scan_source("def (:")[0]["message"])


class Fixtures(EngineCase):
    def write_stray(self, relative="fixtures/answer-key.md"):
        target = self.paths.fixtures_work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Key\n{KEY_SENTINEL}\n", encoding="utf-8")

    def assert_no_key_anywhere(self):
        for root in (self.paths.fixtures_work, self.paths.key_work, self.paths.sealed_dir, self.paths.fixtures):
            self.assertEqual([p for p in root.rglob("*") if p.name.lower() == "answer-key.md"], [], str(root))
        self.assertFalse(self.paths.sealed_key.exists())
        self.assertFalse(self.paths.project_key.exists())
        self.assertEqual(sorted(p.name for p in self.paths.fixtures.iterdir()),
                         ["fixture-bad.txt", "fixture-polished-but-wrong.txt"])

    def test_gate_passes_with_no_key(self):
        self.to_step("fixtures")
        self.do_fixtures()
        result = self.check("fixtures")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["nudges"], [])
        self.assertEqual(self.status("fixtures"), "done")
        self.assert_no_key_anywhere()

    def test_stray_key_is_deleted_with_a_nudge(self):
        self.to_step("fixtures")
        self.do_fixtures()
        self.write_stray()
        self.write_stray("Answer-Key.md")
        self.write_stray("notes/deep/answer-key.md")
        result = self.check("fixtures")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["nudges"], ["Your AI wrote an answer key anyway. The app deleted it, and a new one "
                                            "will be written after you lock your predictions. If you saw what it "
                                            "said, predict as honestly as you can."])
        self.assert_no_key_anywhere()
        self.assert_key_hidden()

    def test_no_key_anywhere_after_a_pass_even_with_leftovers(self):
        self.to_step("fixtures")
        self.do_fixtures()
        self.paths.sealed_dir.mkdir(parents=True, exist_ok=True)
        self.paths.sealed_key.write_text("old sealed key", encoding="utf-8")
        self.paths.key_work_fixtures.mkdir(parents=True, exist_ok=True)
        self.paths.key_work_key.write_text("old key-work key", encoding="utf-8")
        self.assertTrue(self.check("fixtures")["ok"])
        self.assert_no_key_anywhere()

    def test_gate_failure_leaves_a_stray_key_for_the_next_attempt(self):
        self.to_step("fixtures")
        self.engine.step_start("fixtures")
        self.write_stray()
        self.assertFalse(self.check("fixtures")["ok"])
        self.assertTrue((self.paths.work_fixtures / "answer-key.md").exists())

    def test_gate_needs_both_fixtures(self):
        self.to_step("fixtures")
        self.engine.step_start("fixtures")
        self.paths.work_fixtures.mkdir(parents=True)
        (self.paths.work_fixtures / "fixture-bad.txt").write_text("x", encoding="utf-8")
        result = self.check("fixtures")
        self.assertFalse(result["ok"])
        self.assertFalse((self.paths.fixtures / "fixture-bad.txt").exists())

    def test_answer_key_in_project_blocks_the_gate(self):
        self.to_step("fixtures")
        self.do_fixtures()
        self.paths.project_key.write_text("oops", encoding="utf-8")
        self.addCleanup(self.paths.project_key.unlink)
        self.assertFalse(self.check("fixtures")["ok"])

    def test_start_clears_the_work_folder(self):
        self.to_step("fixtures")
        self.do_fixtures()
        self.engine.step_start("fixtures")
        self.assertFalse(self.paths.work_fixtures.exists())


class KeyStep(EngineCase):
    def to_key(self):
        self.to_step("key")

    def test_locked_until_predict_is_done(self):
        self.to_step("predict")
        for call in (self.engine.step_start, self.engine.step_send, self.engine.step_check):
            with self.subTest(call=call.__name__):
                self.assert_code("step_locked", call, "key")
        self.do_predict()  # locked predictions, but the predict gate has not passed
        self.assert_code("step_locked", self.engine.step_start, "key")
        self.assertTrue(self.check("predict")["ok"])
        self.assertEqual(self.status("key"), "active")

    def test_start_writes_exactly_the_five_files(self):
        self.to_key()
        self.engine.step_start("key")
        self.assertEqual(Path(self.terminal.starts[-1]["cwd"]), self.paths.key_work)
        names = sorted(str(p.relative_to(self.paths.key_work)).replace("\\", "/")
                       for p in self.paths.key_work.rglob("*") if p.is_file())
        self.assertEqual(names, ["fixtures/fixture-bad.txt", "fixtures/fixture-polished-but-wrong.txt",
                                 "prompt-v0.md", "skills/make-eval-fixtures/SKILL.md", "test-cases.md"])
        self.assertEqual((self.paths.key_work / "test-cases.md").read_bytes(), self.paths.test_cases.read_bytes())
        self.assertEqual((self.paths.key_work / "prompt-v0.md").read_bytes(), self.paths.prompt.read_bytes())
        self.assertEqual((self.paths.key_work / "skills" / "make-eval-fixtures" / "SKILL.md").read_bytes(),
                         (helpers.KIT / "skills" / "make-eval-fixtures" / "SKILL.md").read_bytes())
        for name in ("fixture-bad.txt", "fixture-polished-but-wrong.txt"):
            self.assertEqual((self.paths.key_work_fixtures / name).read_bytes(),
                             (self.paths.fixtures / name).read_bytes())

    def test_start_clears_earlier_work_and_restores_fixtures(self):
        self.to_key()
        self.do_key()
        (self.paths.key_work / "leftover.txt").write_text("x", encoding="utf-8")
        (self.paths.key_work_fixtures / "fixture-bad.txt").write_text("changed", encoding="utf-8")
        self.engine.step_start("key")
        self.assertFalse((self.paths.key_work / "leftover.txt").exists())
        self.assertFalse(self.paths.key_work_key.exists())
        self.assertEqual((self.paths.key_work_fixtures / "fixture-bad.txt").read_bytes(),
                         (self.paths.fixtures / "fixture-bad.txt").read_bytes())

    def item(self, result, label):
        return next(i for i in result["items"] if i["label"] == label)

    def test_gate_fails_on_a_missing_or_empty_key(self):
        self.to_key()
        self.engine.step_start("key")
        result = self.check("key")
        self.assertFalse(result["ok"])
        self.assertFalse(self.item(result, "Answer key written")["ok"])
        self.write_key("   \n")
        self.assertFalse(self.item(self.check("key"), "Answer key written")["ok"])
        self.assertEqual(self.status("key"), "active")
        self.assertFalse(self.paths.sealed_key.exists())

    def test_gate_fails_on_a_changed_fixture(self):
        self.to_key()
        self.do_key()
        (self.paths.key_work_fixtures / "fixture-polished-but-wrong.txt").write_text("changed", encoding="utf-8")
        result = self.check("key")
        self.assertFalse(result["ok"])
        self.assertFalse(self.item(result, "Fixtures unchanged")["ok"])
        self.assertFalse(self.paths.sealed_key.exists())

    def test_gate_fails_on_a_missing_fixture(self):
        self.to_key()
        self.do_key()
        (self.paths.key_work_fixtures / "fixture-bad.txt").unlink()
        self.assertFalse(self.item(self.check("key"), "Fixtures unchanged")["ok"])

    def test_gate_fails_when_a_key_is_in_the_project(self):
        self.to_key()
        self.do_key()
        self.paths.project_key.write_text("oops", encoding="utf-8")
        self.addCleanup(self.paths.project_key.unlink)
        result = self.check("key")
        self.assertFalse(result["ok"])
        self.assertFalse(self.item(result, "No answer key in your project")["ok"])

    def test_pass_moves_the_key_to_sealed(self):
        self.to_key()
        self.do_key()
        self.assertTrue(self.check("key")["ok"])
        self.assertFalse(self.paths.key_work_key.exists())
        self.assertIn(KEY_SENTINEL, self.paths.sealed_key.read_text(encoding="utf-8"))
        self.assertFalse(self.paths.project_key.exists())
        self.assertFalse(self.terminal.running)
        self.assertEqual(self.status("key"), "done")
        self.assertEqual(self.status("run"), "active")
        self.assertTrue(self.data("key")["key_held"])

    def test_key_text_is_withheld_until_the_run_succeeds(self):
        self.to_key()
        self.do_key()
        self.assert_key_hidden()
        self.assertTrue(self.check("key")["ok"])
        self.assert_key_hidden()
        self.write_checker("import sys\nsys.exit(3)\n")
        self.do_run()
        self.assert_key_hidden()
        self.write_checker()
        self.do_run()
        self.assertIn(KEY_SENTINEL, self.data("run")["answer_key_markdown"])
        self.assertNotIn(KEY_SENTINEL, json.dumps(self.state("key")["step"]))
        self.assertNotIn(KEY_SENTINEL, self.paths.progress_file.read_text(encoding="utf-8"))

    def test_run_is_locked_until_the_key_is_done(self):
        self.to_key()
        self.assert_code("step_locked", self.engine.step_run_checker, "run", "fixtures")

    def test_step_has_a_cli_and_nothing_to_submit(self):
        self.to_key()
        cli = self.state("key")["step"]["cli"]
        self.assertEqual(cli["line"], EXPECTED_LINES["key"])
        self.assertIn("Answer key folder", cli["folder_label"])
        self.assert_code("bad_input", self.engine.step_submit, "key", {"x": True})


class ResumeOlderProgress(EngineCase):
    """A progress.json from before the key step existed must load and settle by the normal rules."""

    OLD_ORDER = ["generate", "build", "fixtures", "readback", "predict", "run", "fix"]

    def rewrite_as_old(self, done_upto):
        """Rewrite progress.json as an older version would have left it."""
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        data["steps"].pop("key")
        data["done"] = self.OLD_ORDER[:self.OLD_ORDER.index(done_upto) + 1]
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")

    def seal_old_key(self):
        self.paths.sealed_dir.mkdir(parents=True, exist_ok=True)
        self.paths.sealed_key.write_text(f"# Key\n{KEY_SENTINEL}\n", encoding="utf-8")

    def done_list(self):
        return [s["id"] for s in self.state()["steps"] if s["status"] == "done"]

    def reopen(self):
        self.engine = self.new_engine()

    def assert_loaded(self, expected_done):
        self.assertTrue(self.state()["configured"], self.state()["setup"]["warnings"])
        self.assertEqual(self.done_list(), expected_done)
        self.assertEqual(self.state()["setup"]["warnings"], [])

    def test_predict_done_and_key_sealed_marks_key_done(self):
        self.to_step("fix")
        self.seal_old_key()
        self.rewrite_as_old("predict")
        self.reopen()
        self.assert_loaded(["generate", "build", "fixtures", "readback", "predict", "key"])
        self.assertEqual(self.status("run"), "active")
        self.assertTrue(self.data("key")["key_held"])

    def test_predict_done_and_no_sealed_key_makes_key_active(self):
        self.to_step("fix")
        self.paths.sealed_key.unlink()
        self.rewrite_as_old("predict")
        self.reopen()
        self.assert_loaded(["generate", "build", "fixtures", "readback", "predict"])
        self.assertEqual(self.status("key"), "active")
        self.assertEqual(self.status("run"), "locked")

    def test_later_steps_done_and_key_sealed_keeps_them(self):
        self.to_step("fix")
        self.seal_old_key()
        self.rewrite_as_old("run")
        self.reopen()
        self.assert_loaded(["generate", "build", "fixtures", "readback", "predict", "key", "run"])
        self.assertEqual(self.status("fix"), "active")

    def test_later_steps_done_without_a_key_go_back_to_the_key_step(self):
        self.to_step("fix")
        self.paths.sealed_key.unlink()
        self.rewrite_as_old("fix")
        self.reopen()
        self.assert_loaded(["generate", "build", "fixtures", "readback", "predict"])
        self.assertEqual(self.status("key"), "active")
        self.assertEqual(self.status("run"), "locked")
        self.assertEqual(self.status("fix"), "locked")

    def test_a_sealed_key_alone_does_not_mark_a_step_done(self):
        self.to_step("predict")
        self.seal_old_key()
        self.rewrite_as_old("readback")
        self.reopen()
        self.assert_loaded(["generate", "build", "fixtures", "readback"])
        self.assertEqual(self.status("key"), "locked")
        self.assert_key_hidden()

    def test_finishing_predict_later_counts_an_old_sealed_key(self):
        self.to_step("predict")
        self.seal_old_key()
        self.rewrite_as_old("readback")
        self.reopen()
        self.do_predict()
        self.assertTrue(self.check("predict")["ok"])
        self.assertEqual(self.status("key"), "done")
        self.assertEqual(self.status("run"), "active")

    def test_no_older_key_is_needed_when_predict_finishes_normally(self):
        self.to_step("predict")
        self.do_predict()
        self.assertTrue(self.check("predict")["ok"])
        self.assertEqual(self.status("key"), "active")

    def test_resume_through_setup_also_loads(self):
        self.to_step("fix")
        self.seal_old_key()
        self.rewrite_as_old("predict")
        self.reopen()
        self.engine.setup({"project_path": str(self.project), "cli_command": ""})
        self.assert_loaded(["generate", "build", "fixtures", "readback", "predict", "key"])

    def test_progress_with_a_key_entry_is_left_alone(self):
        self.to_step("fix")
        self.reopen()
        self.engine.setup({"project_path": str(self.project), "cli_command": ""})
        self.assertEqual(self.done_list(), ["generate", "build", "fixtures", "readback", "predict", "key", "run"])
        self.paths.sealed_key.unlink()
        self.reopen()
        self.assertEqual(self.done_list(), ["generate", "build", "fixtures", "readback", "predict", "key", "run"])

    def test_older_progress_keeps_the_key_withheld_until_a_run(self):
        self.to_step("fix")
        self.seal_old_key()
        self.rewrite_as_old("predict")
        (self.paths.results_dir / "fixtures.json").unlink()
        self.reopen()
        self.assertIsNone(self.data("run")["answer_key_markdown"])
        self.assert_key_hidden()


class Readback(EngineCase):
    def test_gate_needs_every_answer(self):
        self.to_step("readback")
        self.engine.step_start("readback")
        (self.paths.examples / "c1-pass.txt").write_text("x", encoding="utf-8")
        self.engine.step_submit("readback", {"answers": {"C1": "yes"}})
        self.assertFalse(self.check("readback")["ok"])

    def test_gate_needs_a_pass_example(self):
        self.to_step("readback")
        self.engine.step_submit("readback", {"answers": {c: "no" for c in IDS}})
        self.assertFalse(self.check("readback")["ok"])

    def test_answers_are_validated(self):
        self.to_step("readback")
        self.assert_code("bad_input", self.engine.step_submit, "readback", {"answers": {"C1": "maybe"}})
        self.assert_code("bad_input", self.engine.step_submit, "readback", {"answers": {"C9": "yes"}})


class Predict(EngineCase):
    def test_locked_predictions_reject_change(self):
        self.to_step("predict")
        self.do_predict()
        self.assertTrue(self.data("predict")["locked"])
        before = self.data("predict")
        self.assert_code("locked", self.engine.step_submit, "predict", {"bad": {"C1": "P"}})
        self.assert_code("locked", self.engine.step_submit, "predict", {"answers": {"wrong": "changed"}})
        self.assertEqual(self.data("predict"), before)
        self.check("predict")
        self.assert_code("locked", self.engine.step_submit, "predict", {"bad": {"C1": "P"}})

    def test_gate_requires_lock_even_with_every_cell_filled(self):
        self.to_step("predict")
        self.do_predict(lock=False)
        result = self.check("predict")
        self.assertFalse(result["ok"])
        locked = next(i for i in result["items"] if i["label"] == "Predictions locked")
        self.assertFalse(locked["ok"])
        self.assertEqual(self.status("predict"), "active")

    def test_lock_needs_every_cell(self):
        self.to_step("predict")
        self.assert_code("predict_incomplete", self.engine.step_submit, "predict",
                         {"bad": {"C1": "F"}, "lock": True})
        data = self.data("predict")
        self.assertFalse(data["locked"])
        self.assertEqual(data["bad"], {"C1": "F"})

    def test_cell_values_are_validated(self):
        self.to_step("predict")
        self.assert_code("bad_input", self.engine.step_submit, "predict", {"bad": {"C1": "X"}})
        self.assert_code("bad_input", self.engine.step_submit, "predict", {"bad": {"C42": "P"}})

    def test_run_requires_locked_predictions(self):
        self.to_step("predict")
        self.do_predict(lock=False)
        self.assertFalse(self.check("predict")["ok"])
        self.assert_code("step_locked", self.engine.step_run_checker, "run", "fixtures")

    def test_manual_rows(self):
        self.to_step("predict")
        self.paths.test_cases.write_text("# Notes only\n", encoding="utf-8")
        self.assertTrue(self.data("predict")["manual_rows"])
        self.assertEqual(self.data("predict")["criteria"], [])
        self.engine.step_submit("predict", {"criteria": [{"id": "c1", "name": "Mine"}]})
        self.assertEqual(self.data("predict")["criteria"], [{"id": "C1", "name": "Mine"}])
        self.engine.step_submit("predict", {"bad": {"C1": "F"}, "polished": {"C1": "NC"},
                                            "answers": self.PREDICT["answers"], "lock": True})
        self.assertTrue(self.check("predict")["ok"])
        self.assertEqual(self.state("key")["step"]["status"], "active")


class RunStep(EngineCase):
    def test_key_hidden_until_locked_and_run_succeeded(self):
        self.to_step("run")
        self.assert_key_hidden()
        self.write_checker("import sys\nsys.exit(3)\n")
        self.do_run()
        self.assert_key_hidden()
        self.assertFalse(self.data("run")["result"]["ok"])
        self.write_checker()
        self.do_run()
        self.assertIn(KEY_SENTINEL, self.data("run")["answer_key_markdown"])
        for step in ("generate", "build", "fixtures", "readback", "predict", "fix"):
            self.assertNotIn(KEY_SENTINEL, json.dumps(self.state(step)["step"]))

    def test_classification_values_are_validated(self):
        self.to_step("run")
        self.assert_code("bad_input", self.engine.step_submit, "run", {"classifications": {"C3:polished": "nope"}})
        self.assert_code("bad_input", self.engine.step_submit, "run", {"classifications": {"nope": "vague"}})

    def test_no_surprises_lets_the_gate_pass(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        self.do_build()
        self.check("build")
        self.do_fixtures()
        self.check("fixtures")
        self.do_readback()
        self.check("readback")
        self.do_predict(polished={c: "P" for c in IDS})
        self.check("predict")
        self.do_key()
        self.check("key")
        self.do_run()
        self.assertTrue(self.check("run")["ok"])
        self.assertFalse(self.data("fix")["can_skip"])  # the polished fixture passed everything


class Fix(EngineCase):
    def tighten(self):
        text = self.data("fix")["test_cases_text"]
        self.engine.step_submit("fix", {"test_cases_text": text + "\n<!-- tightened C3 -->\n"})

    def test_checker_changed_without_spec_gives_the_nudge(self):
        self.to_step("fix")
        self.write_checker(tight_checker())
        result = self.check("fix")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["nudges"]), 1)
        self.assertIn("Fix the spec, not the checker", result["nudges"][0])

    def test_no_nudge_when_both_changed(self):
        self.to_step("fix")
        self.tighten()
        self.write_checker(tight_checker())
        self.assertEqual(self.check("fix")["nudges"], [])

    def test_spec_edit_alone_does_not_pass(self):
        self.to_step("fix")
        self.tighten()
        self.assertFalse(self.check("fix")["ok"])

    def test_checker_must_change_after_the_spec_edit(self):
        self.to_step("fix")
        self.write_checker(tight_checker())
        self.tighten()
        self.assertFalse(self.data("fix")["checker_changed_after"])

    def test_external_spec_edit_is_noticed(self):
        self.to_step("fix")
        self.paths.test_cases.write_text(self.paths.test_cases.read_text(encoding="utf-8") + "\nedit\n",
                                         encoding="utf-8")
        self.assertTrue(self.data("fix")["test_cases_changed"])
        self.assertFalse(self.data("fix")["checker_changed_after"])
        self.write_checker(tight_checker())
        self.assertTrue(self.data("fix")["checker_changed_after"])

    def test_gate_needs_a_fresh_rerun(self):
        self.to_step("fix")
        self.tighten()
        self.write_checker(tight_checker())
        self.engine.step_run_checker("fix", "fixtures")
        self.write_checker(tight_checker() + "\n# changed after the rerun\n")
        result = self.check("fix")
        item = next(i for i in result["items"] if i["label"] == "Both fixtures run again")
        self.assertFalse(item["ok"])

    def test_polished_must_fail_or_be_explained(self):
        self.to_step("fix")
        self.tighten()
        self.write_checker(STDLIB_CHECKER + "\n# reworded only\n")
        self.engine.step_run_checker("fix", "fixtures")
        self.assertFalse(self.check("fix")["ok"])
        self.engine.step_submit("fix", {"explanation": "It should pass because the labels are present."})
        self.assertTrue(self.check("fix")["ok"])

    def test_scan_blocks_the_gate(self):
        self.to_step("fix")
        self.tighten()
        self.write_checker("import socket\n" + tight_checker())
        self.assertFalse(self.check("fix")["ok"])

    def test_skip_only_when_allowed(self):
        self.to_step("fix")
        self.assert_code("cannot_skip", self.engine.step_skip, "fix")
        self.assert_code("cannot_skip", self.engine.step_skip, "build")

    def test_empty_spec_is_refused(self):
        self.to_step("fix")
        self.assert_code("bad_input", self.engine.step_submit, "fix", {"test_cases_text": "  "})


class FixSkip(EngineCase):
    def test_skip_when_no_surprises_and_polished_failed(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        self.do_build()
        self.write_checker(tight_checker())
        self.check("build")
        self.do_fixtures()
        self.check("fixtures")
        self.do_readback()
        self.check("readback")
        self.do_predict()  # predicts polished C3 fails, which the tight checker confirms
        self.check("predict")
        self.do_key()
        self.check("key")
        self.do_run()
        self.assertTrue(self.check("run")["ok"])
        self.assertTrue(self.data("fix")["can_skip"])
        self.engine.step_skip("fix")
        self.assertEqual(self.state()["current_step"], "baseline")


class CheckerOutsideTheLock(EngineCase):
    """A hung checker must not freeze the app, and must not produce stale results."""

    def hold_runner(self):
        started, release = threading.Event(), threading.Event()
        real = runner.run_checker

        def held(project, files, timeout=30, env=None):
            started.set()
            release.wait(10)
            return real(project, files, timeout=timeout)

        patcher = mock.patch.object(runner, "run_checker", held)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(release.set)
        return started, release

    def run_in_thread(self, *args):
        outcome = {}

        def body():
            try:
                self.engine.step_run_checker(*args)
                outcome["ok"] = True
            except EngineError as exc:
                outcome["error"] = exc.code

        thread = threading.Thread(target=body, daemon=True)
        thread.start()
        return thread, outcome

    def test_state_answers_while_a_checker_is_running(self):
        self.to_step("build")
        self.engine.step_start("build")
        self.write_checker()
        started, release = self.hold_runner()
        thread, outcome = self.run_in_thread("build", "first_look")
        self.assertTrue(started.wait(5))

        answered = threading.Event()
        threading.Thread(target=lambda: (self.engine.get_state(), answered.set()), daemon=True).start()
        self.assertTrue(answered.wait(2), "get_state blocked while the checker ran")

        self.assert_code("checker_busy", self.engine.step_run_checker, "build", "first_look")
        self.assert_code("checker_busy", self.engine.step_check, "build")

        release.set()
        thread.join(10)
        self.assertEqual(outcome, {"ok": True})
        self.assertTrue(self.data("build")["first_look"]["ok"])
        self.engine.step_run_checker("build", "first_look")  # the flag was cleared

    def test_result_is_dropped_if_the_project_changes_mid_run(self):
        self.to_step("build")
        self.engine.step_start("build")
        self.write_checker()
        started, release = self.hold_runner()
        thread, outcome = self.run_in_thread("build", "first_look")
        self.assertTrue(started.wait(5))
        other = self.tmp / "other-project"
        self.engine.setup({"project_path": str(other), "cli_command": "fake-cli", "starter": "northwind"})
        release.set()
        thread.join(10)
        self.assertEqual(outcome, {"error": "checker_stale"})
        self.assertFalse((other / ".learning" / "results" / "first_look.json").exists())

    def test_fix_hashes_come_from_before_the_run(self):
        self.to_step("run")
        self.engine.step_run_checker("run", "fixtures")
        self.engine.step_submit("run", {"classifications": {"C3:polished": "predicted_wrong"}})
        self.check("run")
        started, release = self.hold_runner()
        thread, outcome = self.run_in_thread("fix", "fixtures")
        self.assertTrue(started.wait(5))
        self.write_checker(STDLIB_CHECKER + "\n# edited while the checker ran\n")
        release.set()
        thread.join(10)
        self.assertEqual(outcome, {"ok": True})
        self.assertFalse(self.engine._fix_facts()["rerun_fresh"])


class Runner(EngineCase):
    def setUp(self):
        super().setUp()
        self.project.mkdir(parents=True)

    def run_with(self, source, timeout=30):
        (self.project / "check.py").write_text(source, encoding="utf-8")
        return runner.run_checker(self.project, ["a.txt"], timeout=timeout)

    def test_exit_zero_and_one_are_normal(self):
        good = "print('== a.txt')\nprint('C1 PASS  X: ok')\nprint('-> 1 passed, 0 failed, 0 NOT CHECKED')\n"
        self.assertTrue(self.run_with(good)["ok"])
        result = self.run_with(good.replace("PASS", "FAIL").replace("1 passed, 0 failed", "0 passed, 1 failed")
                               + "import sys\nsys.exit(1)\n")
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 1)

    def test_other_exit_codes_are_errors(self):
        result = self.run_with("import sys\nsys.exit(2)\n")
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("exit code 2", result["error"])

    def test_timeout_is_an_error(self):
        result = self.run_with("import time\ntime.sleep(20)\n", timeout=0.5)
        self.assertFalse(result["ok"])
        self.assertIn("did not finish", result["error"])

    def test_unparseable_output_is_an_error(self):
        result = self.run_with("print('hello')\n")
        self.assertFalse(result["ok"])
        self.assertIn("could not read", result["error"])
        self.assertIn("hello", result["raw"])

    def test_missing_file_section_is_an_error(self):
        result = self.run_with("print('== other.txt')\nprint('C1 PASS  X: ok')\nprint('-> 1/1 criteria passed')\n")
        self.assertFalse(result["ok"])

    def test_utf8_environment(self):
        result = self.run_with("import sys\nprint('== a.txt')\nprint('C1 PASS  X: ' + sys.stdout.encoding)\n"
                               "print('-> 1 passed, 0 failed, 0 NOT CHECKED')\n")
        self.assertEqual(result["files"][0]["rows"][0]["reason"].lower().replace("-", ""), "utf8")


class Setup(EngineCase):
    def test_creates_the_kit_without_keys_or_presenter_files(self):
        self.setup_project()
        for folder in ("runs", "fixtures", "examples", ".learning", "skills"):
            self.assertTrue((self.project / folder).is_dir(), folder)
        names = sorted(p.name for p in self.project.iterdir())
        self.assertEqual(names, [".learning", "examples", "fixtures", "prompt-v0.md", "runs", "skills", "test-cases.md"])
        self.assertEqual(sorted(p.name for p in (self.project / "skills").iterdir()),
                         ["build-eval-script", "build-promptfoo-config", "make-eval-fixtures"])
        everything = [p.name.lower() for p in self.project.rglob("*")]
        self.assertNotIn("answer-key.md", everything)
        self.assertFalse([n for n in everything if "reference-check" in n or "expected-results" in n])
        self.assertEqual(list((self.project / "fixtures").iterdir()), [])

    def test_catch_up_comment_is_stripped(self):
        self.setup_project()
        for name in ("prompt-v0.md", "test-cases.md"):
            text = (self.project / name).read_text(encoding="utf-8")
            self.assertNotIn("Catch-up", text)
            self.assertNotIn("<!--", text)
            self.assertTrue(text.startswith("# "))

    def test_skills_are_unchanged(self):
        self.setup_project()
        source = helpers.KIT / "skills" / "build-eval-script" / "SKILL.md"
        written = self.project / "skills" / "build-eval-script" / "SKILL.md"
        self.assertEqual(source.read_bytes(), written.read_bytes())

    def test_existing_participant_files_are_not_overwritten(self):
        self.project.mkdir()
        (self.project / "test-cases.md").write_text("mine", encoding="utf-8")
        (self.project / "skills" / "build-eval-script").mkdir(parents=True)
        skill = self.project / "skills" / "build-eval-script" / "SKILL.md"
        skill.write_text("my skill", encoding="utf-8")
        self.setup_project()
        self.assertEqual((self.project / "test-cases.md").read_text(encoding="utf-8"), "mine")
        self.assertEqual(skill.read_text(encoding="utf-8"), "my skill")

    def test_own_starter_copies_my_files(self):
        prompt = self.tmp / "my prompt.md"
        cases = self.tmp / "my cases.md"
        prompt.write_text("my prompt", encoding="utf-8")
        cases.write_text(
            "### C1: Length\n- Requirement: Keep it short\n- Threshold: Word count under 50 passes\n\n"
            "### C2: Order\n- Requirement: Mention the order\n- Threshold: Passes if the text \"4821\" appears\n\n"
            "### C3: Offer\n- Requirement: Offer a refund\n- Threshold: Passes if \"refund\" appears\n",
            encoding="utf-8")
        self.setup_project(starter="own", prompt_path=f'"{prompt}"', test_cases_path=str(cases))
        self.assertEqual((self.project / "prompt-v0.md").read_text(encoding="utf-8"), "my prompt")
        self.assertEqual((self.project / "test-cases.md").read_bytes(), cases.read_bytes())
        self.assertEqual(self.state()["setup"]["starter"], "own")

    def test_own_starter_refuses_test_cases_that_cannot_make_a_checker(self):
        prompt = self.tmp / "my prompt.md"
        cases = self.tmp / "my cases.md"
        prompt.write_text("my prompt", encoding="utf-8")
        cases.write_text("### C1: Mine\n", encoding="utf-8")
        with self.assertRaises(EngineError) as ctx:
            self.setup_project(starter="own", prompt_path=str(prompt), test_cases_path=str(cases))
        self.assertEqual(ctx.exception.code, "import_blocked")
        self.assertFalse(self.project.exists())

    def test_own_starter_needs_files(self):
        with self.assertRaises(EngineError) as ctx:
            self.engine.setup({"project_path": str(self.project), "cli_command": "x", "starter": "own",
                               "prompt_path": "C:\\no\\such.md", "test_cases_path": "C:\\no\\such2.md"})
        self.assertEqual(ctx.exception.code, "missing_file")

    def test_resume_keeps_progress(self):
        self.setup_project()
        self.do_generate()
        self.engine = self.new_engine()
        state = self.state()
        self.assertTrue(state["configured"])  # reopened from app.json at startup
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["sonnet"])
        self.engine.setup({"project_path": str(self.project), "cli_command": ""})
        self.assertEqual(self.state()["setup"]["cli_command"], "mycli --model sonnet")
        self.assertEqual(self.state()["step"]["data"]["current_run"], 5)

    def test_new_project_in_onedrive_is_refused(self):
        self.project = self.tmp / "OneDrive - Acme" / "project"
        self.assert_code("project_in_onedrive", self.setup_project)
        self.assertFalse(self.project.exists())

    def test_resumed_project_in_onedrive_warns(self):
        from eval_coach import project as project_module
        from eval_coach import state as store
        self.project = self.tmp / "OneDrive - Acme" / "project"
        paths = Paths(self.home, self.project)
        project_module.create_project(paths, "northwind")
        store.save_progress(paths.progress_file, store.new_progress(str(self.project), "fake-cli", "northwind"))
        self.engine.setup({"project_path": str(self.project), "cli_command": ""})
        self.assertIn("OneDrive", self.state()["setup"]["warnings"][0])

    def test_defaults(self):
        defaults = self.state()["setup"]["defaults"]
        self.assertTrue(defaults["project_path"].endswith("eval-project"))
        self.assertEqual(defaults["cli_command"], "")

    def test_bad_inputs(self):
        cases = [
            ({"project_path": ""}, "project_path_required"),
            ({"project_path": "relative\\path", "cli_command": "x", "starter": "northwind"}, "bad_project_path"),
            ({"project_path": str(self.home / "inner"), "cli_command": "x", "starter": "northwind"}, "bad_project_path"),
            ({"project_path": str(self.project), "cli_command": "", "starter": "northwind"}, "cli_required"),
            ({"project_path": str(self.project), "cli_command": "no-such-cli", "starter": "northwind"}, "cli_not_found"),
            ({"project_path": str(self.project), "cli_command": "x", "starter": "wrong"}, "bad_starter"),
        ]
        for body, code in cases:
            with self.subTest(body=body):
                self.assert_code(code, self.engine.setup, body)

    def test_cli_command_may_have_arguments(self):
        self.setup_project()
        self.engine.step_start("generate")
        self.assertEqual(self.terminal.starts[-1]["command"], "mycli --model sonnet")


class Corrupt(EngineCase):
    def corrupt(self, text="{ not json"):
        self.paths.progress_file.write_text(text, encoding="utf-8")

    def test_setup_reports_a_clear_error_and_keeps_the_file(self):
        self.setup_project()
        self.corrupt()
        self.assert_code("corrupt_progress", self.engine.setup,
                         {"project_path": str(self.project), "cli_command": "x"})
        self.assertEqual(self.paths.progress_file.read_text(encoding="utf-8"), "{ not json")
        self.assertIn(str(self.paths.progress_file), self.state()["setup"]["warnings"][0])

    def test_startup_reports_instead_of_crashing(self):
        self.setup_project()
        self.corrupt()
        self.engine = self.new_engine()
        state = self.state()
        self.assertFalse(state["configured"])
        self.assertIn("could not be read", state["setup"]["warnings"][0])

    def test_valid_json_with_the_wrong_shape(self):
        self.setup_project()
        for text in ("[]", '{"done": "nope"}', '{"done": ["bogus"]}', '{"steps": 3}', '{"done": ["build"]}'):
            with self.subTest(text=text):
                self.corrupt(text)
                with self.assertRaises(CorruptStateError):
                    load_progress(self.paths.progress_file)


class AutoStart(EngineCase):
    """A Part 3 AI step opens its AI window by itself, once, and only when nothing would be lost."""

    def starts(self):
        return len(self.terminal.starts)

    def cli(self, step):
        return self.state(step)["step"]["cli"]

    def test_fields_for_every_kind_of_step(self):
        self.setup_project()
        cli = self.cli("generate")
        self.assertEqual((cli["mode"], cli["can_auto_start"], cli["has_result"], cli["paste_ready"]),
                         ("paste", True, False, True))
        self.assertEqual(cli["line"], EXPECTED_LINES["generate"])
        self.assertFalse(cli["blocked"])
        self.assertEqual(self.engine.progress["steps"]["generate"]["auto_started"], False)

    def test_first_visit_starts_one_window_in_the_blind_folder(self):
        self.setup_project()
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 1)
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.paths.blind))
        self.assertEqual(self.terminal.starts[-1]["label"], "Collect your answers: run 1 of 5")
        self.assertTrue(self.engine.progress["steps"]["generate"]["auto_started"])
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["sonnet"])
        self.assertEqual(self.terminal.typed, [])
        self.assertFalse(self.cli("generate")["can_auto_start"])

    def test_second_visit_and_stop_then_revisit_start_nothing(self):
        self.setup_project()
        self.engine.step_auto_start("generate")
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 1)
        self.engine.step_stop("generate")
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 1)
        self.assertFalse(self.cli("generate")["can_auto_start"])

    def test_a_start_by_the_button_also_uses_up_the_automatic_start(self):
        self.setup_project()
        self.engine.step_start("generate")
        self.engine.step_stop("generate")
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 1)

    def test_later_runs_are_only_started_by_the_button(self):
        self.setup_project()
        self.engine.step_auto_start("generate")
        shutil.copy(str(NORTHWIND / "sample-run-1.txt"), str(self.paths.blind_output))
        self.assertTrue(wait_until(lambda: self.paths.run_file(1).is_file()))
        self.assertFalse(self.cli("generate")["can_auto_start"])
        self.assertFalse(self.cli("generate")["has_result"])  # run 1 is saved, so nothing is lost
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 1)
        self.engine.step_start("generate")
        self.assertEqual(self.terminal.starts[-1]["label"], "Collect your answers: run 2 of 5")

    def test_reading_ahead_a_locked_step_starts_nothing_and_prepares_nothing(self):
        self.setup_project()
        self.assertTrue(self.state("build")["step"]["preview"])
        self.assertIsNone(self.state("build")["step"]["cli"])
        self.engine.step_auto_start("build")
        self.assertEqual(self.starts(), 0)
        self.assertFalse(self.paths.fixtures_work.exists())

    def test_a_finished_step_starts_nothing(self):
        self.to_step("build")
        self.assertEqual(self.state("generate")["step"]["status"], "done")
        starts = self.starts()
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), starts)
        self.assertFalse(self.cli("generate")["can_auto_start"])

    def test_before_setup_is_a_quiet_no_op(self):
        self.engine.step_auto_start("generate")  # nothing is configured yet: no error, no window
        self.assertEqual(self.starts(), 0)
        self.setup_project()
        (self.home / "preflight.json").unlink()
        engine = self.new_engine()
        engine.step_auto_start("generate")  # the project is open, but setup has not passed
        self.assertEqual(self.starts(), 0)

    def test_another_window_running_blocks_it(self):
        self.setup_project()
        self.terminal.running = True
        self.assertFalse(self.cli("generate")["can_auto_start"])
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 0)

    def test_a_file_the_ai_made_in_the_blind_folder_blocks_it_and_is_kept(self):
        self.setup_project()
        self.paths.blind.mkdir(parents=True)
        (self.paths.blind / "notes.txt").write_text("keep me", encoding="utf-8")
        self.assertTrue(self.cli("generate")["has_result"])
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 0)
        self.assertEqual((self.paths.blind / "notes.txt").read_text(encoding="utf-8"), "keep me")

    def test_fixture_text_in_the_work_folder_blocks_it(self):
        self.to_step("fixtures")
        before = self.starts()
        self.paths.work_fixtures.mkdir(parents=True)
        (self.paths.work_fixtures / "fixture-bad.txt").write_text("text", encoding="utf-8")
        self.assertTrue(self.cli("fixtures")["has_result"])
        self.engine.step_auto_start("fixtures")
        self.assertEqual(self.starts(), before)
        self.assertEqual((self.paths.work_fixtures / "fixture-bad.txt").read_text(encoding="utf-8"), "text")

    def test_fixtures_already_in_the_project_block_it(self):
        self.to_step("fixtures")
        self.paths.fixtures.mkdir(parents=True, exist_ok=True)
        (self.paths.fixtures / "fixture-bad.txt").write_text("text", encoding="utf-8")
        self.assertFalse(self.cli("fixtures")["can_auto_start"])
        self.assertFalse(self.cli("fixtures")["has_result"])  # a new start would not clear the project's copy

    def test_a_step_that_passes_closes_its_window_so_the_next_step_can_open_its_own(self):
        self.to_step("fixtures")
        self.assertFalse(self.terminal.running)
        self.assertTrue(self.cli("fixtures")["can_auto_start"])
        before = self.starts()
        self.engine.step_auto_start("fixtures")
        self.assertEqual(self.starts(), before + 1)
        self.assertEqual(Path(self.terminal.starts[-1]["cwd"]), self.paths.fixtures_work)

    def test_the_sealed_key_blocks_the_key_step_and_is_never_opened(self):
        self.to_step("key")
        before = self.starts()
        self.paths.sealed_dir.mkdir(parents=True, exist_ok=True)
        self.paths.sealed_key.write_text(f"# Key\n{KEY_SENTINEL}\n", encoding="utf-8")
        opened = []
        real_has_text, real_read_text = gates.has_text, gates.read_text

        def has_text(path, *args):
            opened.append(Path(path))
            return real_has_text(path, *args)

        def read_text(path, *args):
            opened.append(Path(path))
            return real_read_text(path, *args)

        with mock.patch.object(gates, "has_text", has_text), mock.patch.object(gates, "read_text", read_text):
            self.engine.step_auto_start("key")
            self.assertFalse(self.cli("key")["can_auto_start"])
        self.assertEqual(self.starts(), before)
        self.assertNotIn(self.paths.sealed_key, opened)

    def test_a_key_in_the_key_work_folder_blocks_it(self):
        self.to_step("key")
        before = self.starts()
        self.paths.key_work_key.parent.mkdir(parents=True, exist_ok=True)
        self.write_key()
        self.assertTrue(self.cli("key")["has_result"])
        self.engine.step_auto_start("key")
        self.assertEqual(self.starts(), before)

    def test_project_folder_steps_start_without_extra_conditions(self):
        self.to_step("build")
        before = self.starts()
        self.assertTrue(self.cli("build")["can_auto_start"])
        self.assertFalse(self.cli("build")["has_result"])
        self.engine.step_auto_start("build")
        self.assertEqual(self.starts(), before + 1)
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.project))

    def test_a_failed_start_is_shown_and_the_button_is_the_way_to_retry(self):
        self.setup_project()
        with mock.patch.object(self.terminal, "start", side_effect=OSError("no such program")):
            self.engine.step_auto_start("generate")  # never raises
        cli = self.cli("generate")
        self.assertIn("could not be started", cli["blocked"])
        self.assertFalse(cli["can_auto_start"])
        self.assertFalse(self.engine.progress["steps"]["generate"]["auto_started"])
        self.engine.step_auto_start("generate")
        self.assertEqual(self.starts(), 0)
        self.engine.step_start("generate")
        self.assertEqual(self.starts(), 1)
        self.assertIsNone(self.cli("generate")["blocked"])

    def test_every_start_records_the_model(self):
        self.setup_project()
        self.engine.step_auto_start("generate")
        self.engine.step_start("generate")
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["sonnet"])
        self.assertEqual(self.engine._model_name(), "sonnet")

    def test_progress_without_the_field_gets_the_default(self):
        self.setup_project()
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        for record in data["steps"].values():
            record.pop("auto_started", None)
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")
        engine = self.new_engine()
        for step in ("generate", "build", "fixtures", "readback", "key", "fix", "baseline"):
            self.assertIs(engine.progress["steps"][step]["auto_started"], False, step)


if __name__ == "__main__":
    unittest.main()
