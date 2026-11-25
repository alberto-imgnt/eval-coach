from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

import helpers
import test_engine_gates as base
from helpers import FakeTerminal, NORTHWIND
from pf_helpers import FIXTURE_TESTS, RUN_TESTS, FakePromptfoo, pf_config

from eval_coach import promptfoo, state as store
from eval_coach.engine import Engine, EngineError
from eval_coach.project import Paths
from eval_coach.state import CorruptStateError, new_progress, validate_progress

BUILD_LINE = ("Read skills/build-promptfoo-config/SKILL.md and follow it in build mode on test-cases.md. "
              "Add runs/run-1.txt to runs/run-5.txt as tests named run-1 to run-5.")
CONFIG_LINE = ("Read skills/build-promptfoo-config/SKILL.md. Add fixtures/fixture-bad.txt and "
               "fixtures/fixture-polished-but-wrong.txt to promptfooconfig.yaml as tests named fixture-bad and "
               "fixture-polished-but-wrong. Change nothing else.")
READBACK_LINE = ("Read skills/build-promptfoo-config/SKILL.md and follow it in explain mode on test-cases.md "
                 "and promptfooconfig.yaml.")
FIX_LINE = ("I changed test-cases.md. Update promptfooconfig.yaml to match, changing only the assertions whose "
            "threshold changed. Then run the two fixtures again.")
BASELINE_LINE = ("Read skills/build-promptfoo-config/SKILL.md and follow it in run + log mode. The runs are the tests "
                 "named run-1 to run-5. The prompt file is prompt-v0.md. The model was {model}.")
PF_STEPS = ["inputs", "generate", "build", "fixtures", "fixtures-config", "readback", "predict", "key", "run", "fix", "baseline"]
SCRIPT_STEPS = ["inputs", "generate", "build", "fixtures", "readback", "predict", "key", "run", "fix", "baseline"]


class PfCase(base.EngineCase):
    TRACK = "promptfoo"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-test-"))
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        self.terminal = FakeTerminal()
        self.fake = FakePromptfoo()
        helpers.write_passed_preflight(self.home, self.TRACK)
        self.engine = self.new_engine()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def new_engine(self):
        return Engine(self.home, self.terminal, poll_interval=0.01, preflight_runner=self.fake)

    def step_ids(self):
        return [s["id"] for s in self.state()["steps"]]

    def write_config(self, tests=RUN_TESTS, **kw):
        self.paths.config_yaml.write_text(pf_config(tests, **kw), encoding="utf-8")

    def pf_build(self):
        self.engine.step_start("build")
        self.write_config()
        self.engine.step_run_checker("build", "first_look")
        self.engine.step_submit("build", {"checklist": {"read_not_checked": True, "read_interpretation": True}})

    def pf_fixtures_config(self, **kw):
        self.engine.step_start("fixtures-config")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, **kw)

    def pf_run(self):
        self.engine.step_run_checker("run", "fixtures")
        self.engine.step_submit("run", {"classifications": {"C3:polished": "predicted_wrong"}})

    def pf_fix(self, **kw):
        text = self.data("fix")["test_cases_text"]
        self.engine.step_submit("fix", {"test_cases_text": text.replace(
            "both appear", 'both appear, and the text after "Blocker:" mentions "test data"')})
        self.engine.step_start("fix")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True, **kw)
        self.engine.step_run_checker("fix", "fixtures")

    def to_pf(self, upto, **config_kw):
        """Walk the promptfoo track up to (not including) `upto`."""
        self.setup_project()
        actions = [("generate", self.do_generate), ("build", self.pf_build), ("fixtures", self.do_fixtures),
                   ("fixtures-config", lambda: self.pf_fixtures_config(**config_kw)), ("readback", self.do_readback),
                   ("predict", self.do_predict), ("key", self.do_key), ("run", lambda: (self.do_run(), self.pf_run())),
                   ("fix", self.pf_fix)]
        for name, action in actions:
            if name == upto:
                return
            action()
            result = self.check(name)
            self.assertTrue(result["ok"], (name, result))

    def write_log(self, text):
        self.paths.iteration_log.write_text(text, encoding="utf-8")


class Steps(PfCase):
    def test_the_promptfoo_track_has_one_extra_step_after_fixtures(self):
        self.setup_project()
        self.assertEqual(self.step_ids(), PF_STEPS)
        self.assertEqual([i["id"] for i in self.state()["course"] if i["kind"] == "step"], PF_STEPS)

    def test_the_script_track_keeps_its_steps(self):
        script = base.EngineCase()
        script.setUp()
        self.addCleanup(script.tearDown)
        script.setup_project()
        self.assertEqual([s["id"] for s in script.state()["steps"]], SCRIPT_STEPS)
        self.assertEqual(store.STEP_IDS, tuple(SCRIPT_STEPS))
        self.assert_code("unknown_step", script.engine.step_start, "fixtures-config")
        saved = json.loads(script.paths.progress_file.read_text(encoding="utf-8"))
        self.assertNotIn("fixtures-config", saved["steps"])

    def test_fixtures_config_comes_after_fixtures_and_before_readback(self):
        self.to_pf("fixtures-config")
        self.assertEqual(self.status("fixtures-config"), "active")
        self.assertEqual(self.status("readback"), "locked")
        self.assertEqual(self.status("fixtures"), "done")
        self.assert_code("step_locked", self.engine.step_start, "readback")

    def test_fixtures_config_is_locked_until_fixtures_is_done(self):
        self.to_pf("fixtures")
        self.assert_code("step_locked", self.engine.step_start, "fixtures-config")
        self.assert_code("step_locked", self.engine.step_check, "fixtures-config")

    def test_the_typed_lines_are_exact(self):
        self.to_pf("fixtures-config")
        lines = {}
        for step in ("build", "fixtures", "fixtures-config", "readback", "key", "fix", "baseline"):
            lines[step] = self.engine._detail(step)["cli"]["line"]  # a locked step's state is a preview with no line
        self.assertEqual(lines["build"], BUILD_LINE)
        self.assertEqual(lines["fixtures-config"], CONFIG_LINE)
        self.assertEqual(lines["readback"], READBACK_LINE)
        self.assertEqual(lines["fix"], FIX_LINE)
        self.assertEqual(lines["baseline"], BASELINE_LINE.format(model="sonnet"))
        for step in ("fixtures", "key"):
            self.assertEqual(lines[step], base.EXPECTED_LINES[step])
        self.assertEqual(self.engine._detail("generate")["cli"]["line"], base.EXPECTED_LINES["generate"])

    def test_the_content_has_the_exact_build_line(self):
        self.setup_project()
        self.assertEqual(self.engine._text("build")["line"], BUILD_LINE)
        self.assertEqual(self.engine.content["steps"]["build"]["tracks"]["promptfoo"]["line"], BUILD_LINE)
        self.assertEqual(self.engine.content["steps"]["fixtures-config"]["line"], CONFIG_LINE)
        self.assertEqual(self.engine.content["steps"]["baseline"]["tracks"]["promptfoo"]["line_template"].format(model="M"),
                         BASELINE_LINE.format(model="M"))
        self.assertNotEqual(self.engine.content["steps"]["build"]["line"], BUILD_LINE)  # the Script line is the base

    def test_each_cli_step_starts_in_the_right_folder(self):
        self.to_pf("readback")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.project))  # fixtures-config
        self.engine.step_start("readback")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.project))

    def test_the_baseline_model_is_forced_to_one_line_on_this_track_too(self):
        self.to_pf("baseline")
        self.engine.step_start("baseline")
        self.engine.step_submit("baseline", {"model_name": "  my\nmodel\t\x07 v2 "})
        self.assertEqual(self.paste("baseline"), BASELINE_LINE.format(model="my model v2"))
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["  my\nmodel\t\x07 v2 "])


class Text(PfCase):
    def texts(self, track):
        self.setup_project(choose_inputs=False)
        self.engine.preflight.set_track(track)
        return {step: self.engine._text(step) for step in store.step_ids(track)}

    def flat(self, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from self.flat(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from self.flat(item)

    def test_every_step_has_text_for_both_tracks(self):
        for track in store.TRACKS:
            for step, text in self.texts(track).items():
                for field in ("title", "goal", "why", "instructions", "troubleshooting", "gate"):
                    with self.subTest(track=track, step=step, field=field):
                        self.assertTrue(text.get(field))

    def test_promptfoo_text_never_sends_people_to_check_py(self):
        for step, text in self.texts("promptfoo").items():
            for string in self.flat({k: v for k, v in text.items() if k != "tracks"}):
                with self.subTest(step=step, text=string[:50]):
                    self.assertNotRegex(string, r"check\.py")

    def test_script_text_never_mentions_promptfoo_in_steps_both_tracks_share(self):
        for step, text in self.texts("script").items():
            for string in self.flat({k: v for k, v in text.items() if k != "tracks"}):
                with self.subTest(step=step, text=string[:50]):
                    self.assertNotRegex(string, r"(?i)promptfoo")

    def test_script_text_is_exactly_the_shared_text(self):
        self.setup_project(choose_inputs=False)
        for step in SCRIPT_STEPS:
            self.engine.preflight.set_track("script")
            self.assertIs(self.engine._text(step), self.engine.content["steps"][step])

    def test_live_mode_text_is_only_in_the_live_step_and_carries_the_warning(self):
        data = self.engine.content["steps"]
        pattern = re.compile(r"(?i)\blive\b|agent-provider|exec:|\bprovider\b.*\b(copilot|claude|devin)\b")
        for step, text in data.items():
            if step == "live":
                continue
            for string in self.flat(text):
                with self.subTest(step=step, text=string[:50]):
                    self.assertIsNone(pattern.search(string), string)
        preflight = json.loads((helpers.ROOT / "app" / "eval_coach" / "content" / "preflight.json").read_text(encoding="utf-8"))
        self.assertIsNone(pattern.search(json.dumps(preflight["track_promptfoo_note"])))
        live = " ".join(self.flat(data["live"]))
        for needle in ("agent-provider.js", "--permission-mode auto", "auto mode", "signed-in AI tool", "No API key",
                       "empty temporary folder", "never changes your baseline", "skip this step"):
            self.assertIn(needle, live)

    def test_the_run_text_explains_why_every_test_can_show_as_failed(self):
        run = self.texts("promptfoo")["run"]
        why = " ".join(run["why"])
        self.assertIn("every test as failed", why)
        self.assertIn("NOT CHECKED", why)
        self.assertTrue(any("Every test shows as failed" in t["problem"] and "NOT CHECKED" in t["fix"]
                            for t in run["troubleshooting"]))
        for step in ("build", "fix", "baseline"):
            self.assertTrue(any("Every test shows as failed" in t["problem"]
                                for t in self.texts("promptfoo")[step]["troubleshooting"]), step)

    def test_the_fix_nudge_says_config(self):
        nudge = self.texts("promptfoo")["fix"]["gate"]["nudge_check_only"]["text"]
        self.assertIn("Fix the spec, not the config.", nudge)
        self.assertIn("promptfooconfig.yaml", nudge)
        self.assertEqual(self.texts("script")["fix"]["gate"]["nudge_check_only"]["text"].count("Fix the spec, not the checker."), 1)

    def test_every_troubleshooting_fix_ends_like_a_sentence(self):
        for step, text in self.texts("promptfoo").items():
            for item in text["troubleshooting"]:
                with self.subTest(step=step, problem=item["problem"]):
                    self.assertTrue(item["fix"].rstrip().endswith((".", "\"")), item["fix"])


class FixturesConfig(PfCase):
    def test_the_gate_passes_when_both_tests_are_in_the_config(self):
        self.to_pf("fixtures-config")
        self.assertEqual(self.data("fixtures-config")["tests"],
                         [{"name": "fixture-bad", "present": False}, {"name": "fixture-polished-but-wrong", "present": False}])
        self.assertFalse(self.check("fixtures-config")["ok"])
        self.pf_fixtures_config()
        self.assertEqual(self.paste("fixtures-config"), CONFIG_LINE)
        data = self.data("fixtures-config")
        self.assertTrue(all(t["present"] for t in data["tests"]))
        self.assertTrue(data["config_exists"] and data["fixtures_ready"] and data["scan"] == [])
        result = self.check("fixtures-config")
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.terminal.running)
        self.assertEqual(self.status("readback"), "active")

    def test_a_missing_test_name_is_named(self):
        self.to_pf("fixtures-config")
        self.engine.step_start("fixtures-config")
        self.write_config(RUN_TESTS + ["fixture-bad"])
        result = self.check("fixtures-config")
        self.assertFalse(result["ok"])
        detail = " ".join(i["detail"] for i in result["items"] if not i["ok"])
        self.assertIn("fixture-polished-but-wrong", detail)
        self.assertNotIn("fixture-bad,", detail)
        self.assertEqual(self.status("fixtures-config"), "active")

    def test_a_wrong_name_does_not_count(self):
        self.to_pf("fixtures-config")
        self.engine.step_start("fixtures-config")
        self.write_config(RUN_TESTS + ["fixture-bad", "fixture-polished"])
        self.assertFalse(self.check("fixtures-config")["ok"])

    def test_losing_a_run_test_fails(self):
        self.to_pf("fixtures-config")
        self.engine.step_start("fixtures-config")
        self.write_config(["run-1", "run-2", "run-3"] + FIXTURE_TESTS)
        result = self.check("fixtures-config")
        self.assertFalse(result["ok"])
        self.assertIn("run-4, run-5", " ".join(i["detail"] for i in result["items"]))

    def test_no_config_fails_and_says_what_to_do(self):
        self.to_pf("fixtures-config")
        self.paths.config_yaml.unlink()
        result = self.check("fixtures-config")
        self.assertFalse(result["ok"])
        self.assertIn("Ask your AI", " ".join(i["detail"] for i in result["items"] if not i["ok"]))

    def test_a_model_graded_check_fails_the_scan(self):
        self.to_pf("fixtures-config")
        self.engine.step_start("fixtures-config")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, extra="    - type: llm-rubric\n      value: be nice")
        result = self.check("fixtures-config")
        self.assertFalse(result["ok"])
        self.assertIn("llm-rubric", " ".join(i["detail"] for i in result["items"] if not i["ok"]))
        self.assertTrue(self.data("fixtures-config")["scan"])

    def test_a_provider_other_than_echo_fails_the_scan(self):
        self.to_pf("fixtures-config")
        self.engine.step_start("fixtures-config")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, provider="openai:gpt-4o")
        self.assertFalse(self.check("fixtures-config")["ok"])

    def test_no_answer_key_may_exist_and_none_is_written(self):
        self.to_pf("fixtures-config")
        self.pf_fixtures_config()
        self.paths.project_key.write_text("key", encoding="utf-8")
        self.assertFalse(self.check("fixtures-config")["ok"])
        self.paths.project_key.unlink()
        self.assertTrue(self.check("fixtures-config")["ok"])
        self.assertFalse(self.paths.project_key.exists())
        self.assertFalse(self.paths.sealed_key.exists())
        self.assertFalse((self.paths.key_work).exists() and any(self.paths.key_work.rglob("answer-key.md")))
        self.assert_key_hidden()

    def test_the_step_can_be_done_once_only_and_does_not_run_promptfoo(self):
        self.to_pf("fixtures-config")
        self.pf_fixtures_config()
        self.check("fixtures-config")
        self.assert_code("step_done", self.engine.step_start, "fixtures-config")
        runs = [c for c in self.fake.calls if "eval" in c["argv"]]
        self.assertEqual(len(runs), 1)  # only the build step's first look ran promptfoo


class Runner(PfCase):
    def test_the_command_cwd_and_environment(self):
        self.to_pf("run")
        first = self.fake.calls[0]  # the build step's first look
        self.assertEqual(first["argv"], [r"C:\fake\npx.exe"] + promptfoo.EVAL_ARGS)
        self.assertEqual(first["cwd"], str(self.project))
        env = first["env"]
        self.assertEqual(env["npm_config_offline"], "true")
        self.assertEqual(env["PROMPTFOO_DISABLE_TELEMETRY"], "1")
        self.assertEqual(env["PROMPTFOO_DISABLE_UPDATE"], "1")
        self.assertEqual(env["npm_config_cache"], str(self.home / "npm-cache"))
        self.assertEqual(env["PROMPTFOO_CONFIG_DIR"], str(self.home / "promptfoo"))
        self.assertEqual(env["HTTPS_PROXY"], "http://127.0.0.1:9")
        self.assertGreaterEqual(first["timeout"], 300)

    def test_results_json_is_deleted_before_every_run(self):
        self.to_pf("run")
        (self.project / "results.json").write_text("{\"stale\": true}", encoding="utf-8")
        self.do_run()
        self.assertFalse(self.fake.calls[-1]["results_existed"])
        self.assertTrue(self.data("run")["result"]["ok"])

    def test_a_stale_results_json_never_stands_in_for_a_failed_run(self):
        self.to_pf("run")
        (self.project / "results.json").write_text(json.dumps(
            {"results": {"results": []}}), encoding="utf-8")
        self.fake.mode = "no_results"
        self.engine.step_run_checker("run", "fixtures")
        result = self.data("run")["result"]
        self.assertFalse(result["ok"])
        self.assertIn("stopped before it wrote results.json", result["error"])
        self.assertIn("Invalid config", result["error"])
        self.assertTrue(result["error"].rstrip().endswith("then try again."))

    def test_failed_checks_are_normal_and_the_exit_code_is_reported(self):
        self.to_pf("run")
        self.do_run()
        result = self.data("run")["result"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 100)
        self.assertIsNone(result["error"])
        self.assertEqual([f["file"] for f in result["files"]],
                         ["fixtures/fixture-bad.txt", "fixtures/fixture-polished-but-wrong.txt"])

    def test_error_messages_are_plain_and_end_with_a_next_action(self):
        self.to_pf("run")
        cases = {"timeout": "10 minutes", "cache_miss": "Install for promptfoo", "no_results": "fix the error",
                 "bad_json": "results.json", "not_started": "could not be started"}
        for mode, expected in cases.items():
            with self.subTest(mode=mode):
                self.fake.mode = mode
                self.engine.step_run_checker("run", "fixtures")
                result = self.data("run")["result"]
                self.assertFalse(result["ok"])
                self.assertIn(expected, result["error"])
                self.assertTrue(result["error"].rstrip().endswith("."), result["error"])
                self.assertEqual(result["files"], [])
                self.assertNotIn("Traceback", result["error"])
        self.fake.mode = "normal"
        self.do_run()
        self.assertTrue(self.data("run")["result"]["ok"])

    def test_no_node_gives_a_plain_message(self):
        self.to_pf("run")
        self.fake.which = lambda name, path: None
        self.engine.step_run_checker("run", "fixtures")
        error = self.data("run")["result"]["error"]
        self.assertIn("Node.js", error)
        self.assertIn("Check everything again", error)

    def test_the_bundled_summary_helper_is_used_not_the_participants_copy(self):
        self.to_pf("run")
        mine = self.project / "skills" / "build-promptfoo-config" / "summarize_results.py"
        mine.write_text("print('== run-1\\nC1_x PASS\\n-> 99 passed, 0 failed, 0 NOT CHECKED')\n", encoding="utf-8")
        (self.project / "summarize_results.py").write_text(mine.read_text(encoding="utf-8"), encoding="utf-8")
        self.do_run()
        self.assertTrue(self.data("run")["result"]["ok"])
        self.assertEqual(len(self.data("run")["result"]["files"]), 2)

    def test_the_run_needs_the_checker_and_the_files(self):
        self.to_pf("run")
        self.paths.config_yaml.unlink()
        self.assert_code("no_checker", self.engine.step_run_checker, "run", "fixtures")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, extra="    - type: llm-rubric\n      value: x")
        self.assert_code("scan_failed", self.engine.step_run_checker, "run", "fixtures")
        self.write_config(RUN_TESTS + FIXTURE_TESTS)
        (self.paths.fixtures / "fixture-bad.txt").write_text("", encoding="utf-8")
        self.assert_code("missing_file", self.engine.step_run_checker, "run", "fixtures")


class BuildAndRun(PfCase):
    def test_first_look_runs_the_config_and_reads_only_run_1(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        self.engine.step_start("build")
        self.write_config()
        self.engine.step_run_checker("build", "first_look")
        result = self.data("build")["first_look"]
        self.assertTrue(result["ok"], result)
        self.assertEqual([f["file"] for f in result["files"]], ["runs/run-1.txt"])
        rows = result["files"][0]["rows"]
        self.assertEqual([r["id"] for r in rows], base.IDS)
        self.assertEqual([r["name"] for r in rows],
                         ["Length", "Grouped by client", "Blocker and ask", "Teams, not email", "Factual tone", "Uses the rough notes"])
        self.assertEqual([r["verdict"] for r in rows], ["P"] * 6)
        self.assertTrue(all(r["reason"] for r in rows))
        self.assertEqual(self.data("build")["scan"], [])

    def test_build_gate(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        result = self.check("build")
        self.assertFalse(result["ok"])
        labels = {i["label"]: i for i in result["items"]}
        self.assertIn("promptfooconfig.yaml exists", labels)
        self.assertIn("promptfooconfig.yaml was not found", labels["promptfooconfig.yaml exists"]["detail"])
        self.pf_build()
        self.assertTrue(self.check("build")["ok"])

    def test_build_gate_rejects_a_model_graded_config(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        self.engine.step_start("build")
        self.write_config(extra="    - type: llm-rubric\n      value: x")
        scan_item = next(i for i in self.check("build")["items"] if i["label"] == "Rules only")
        self.assertFalse(scan_item["ok"])
        self.assertIn("llm-rubric", scan_item["detail"])
        self.assertTrue(self.data("build")["scan"])

    def test_build_gate_needs_the_first_look(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        self.engine.step_start("build")
        self.write_config()
        self.engine.step_submit("build", {"checklist": {"read_not_checked": True, "read_interpretation": True}})
        result = self.check("build")
        self.assertFalse(result["ok"])
        self.assertFalse(next(i for i in result["items"] if i["label"] == "First look run")["ok"])

    def test_run_step_compares_with_the_predictions_and_reveals_the_key_after_the_run(self):
        self.to_pf("run")
        self.assertEqual(self.data("run")["grid"], [])
        self.assertIsNone(self.data("run")["answer_key_markdown"])
        self.do_run()
        data = self.data("run")
        self.assertIn(base.KEY_SENTINEL, data["answer_key_markdown"])
        self.assertEqual([g["id"] for g in data["grid"] if g["polished_surprise"] or g["bad_surprise"]], ["C3"])
        self.assertTrue(data["polished_passed_all"])
        self.engine.step_submit("run", {"classifications": {"C3:polished": "predicted_wrong"}})
        self.assertTrue(self.check("run")["ok"])

    def test_the_run_gate_needs_a_good_run(self):
        self.to_pf("run")
        self.fake.mode = "no_results"
        self.engine.step_run_checker("run", "fixtures")
        self.assertFalse(self.check("run")["ok"])


class Fix(PfCase):
    def test_the_gate_uses_the_config_hashes(self):
        self.to_pf("fix")
        self.assertFalse(self.data("fix")["can_skip"])
        self.assertFalse(self.check("fix")["ok"])
        text = self.data("fix")["test_cases_text"]
        self.engine.step_submit("fix", {"test_cases_text": text.replace(
            "both appear", 'both appear, and the text after "Blocker:" mentions "test data"')})
        self.assertTrue(self.data("fix")["test_cases_changed"])
        self.assertFalse(self.data("fix")["checker_changed_after"])
        self.engine.step_start("fix")
        self.assertEqual(self.paste("fix"), FIX_LINE)
        self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True)
        self.assertTrue(self.data("fix")["checker_changed_after"])
        self.engine.step_run_checker("fix", "fixtures")
        data = self.data("fix")
        self.assertTrue(data["polished_fails"], data["rerun"])
        result = self.check("fix")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["nudges"], [])
        self.assertEqual(self.status("baseline"), "active")

    def test_editing_only_the_config_gets_the_config_nudge(self):
        self.to_pf("fix")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True)
        result = self.check("fix")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["nudges"]), 1)
        self.assertIn("Fix the spec, not the config.", result["nudges"][0])

    def test_the_rerun_must_be_fresh(self):
        self.to_pf("fix")
        text = self.data("fix")["test_cases_text"]
        self.engine.step_submit("fix", {"test_cases_text": text + "\n<!-- tightened -->\n"})
        self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True)
        self.engine.step_run_checker("fix", "fixtures")
        self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True, extra="    # edited after the run")
        result = self.check("fix")
        self.assertFalse(result["ok"])
        self.assertFalse(next(i for i in result["items"] if i["label"] == "Both fixtures run again")["ok"])

    def test_skip_when_nothing_surprised(self):
        self.setup_project()
        self.do_generate(); self.check("generate")
        self.pf_build(); self.check("build")
        self.do_fixtures(); self.check("fixtures")
        self.pf_fixtures_config(tightened=True); self.check("fixtures-config")
        self.do_readback(); self.check("readback")
        self.do_predict(); self.check("predict")
        self.do_key(); self.check("key")
        self.do_run()
        self.assertTrue(self.check("run")["ok"])
        self.assertTrue(self.data("fix")["can_skip"])
        self.engine.step_skip("fix")
        self.assertEqual(self.state()["current_step"], "baseline")


class Baseline(PfCase):
    def ready(self, nc=()):
        self.to_pf("baseline")
        if nc:
            self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True, nc=nc)
        self.engine.step_run_checker("baseline", "baseline")
        self.summary = self.data("baseline")["summary"]

    def log(self, **kw):
        from test_baseline_step import log_text
        self.write_log(log_text(self.summary, **kw))

    def test_the_app_runs_the_whole_eval_once_and_summarizes_the_run_tests(self):
        self.ready()
        data = self.data("baseline")
        self.assertTrue(data["result"]["ok"])
        self.assertEqual([f["file"] for f in data["result"]["files"]], [f"runs/run-{n}.txt" for n in range(1, 6)])
        self.assertTrue(data["fresh"])
        self.assertEqual(self.fake.calls[-1]["argv"], [r"C:\fake\npx.exe"] + promptfoo.EVAL_ARGS)
        saved = json.loads((self.paths.results_dir / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["track"], "promptfoo")
        self.assertEqual(saved["summary"], data["summary"])

    def test_numbers_equal_the_script_track_on_the_same_runs(self):
        self.ready()
        script = base.EngineCase()
        script.setUp()
        self.addCleanup(script.tearDown)
        script.to_step("fix")
        text = script.data("fix")["test_cases_text"]
        script.engine.step_submit("fix", {"test_cases_text": text.replace(
            "both appear", 'both appear, and the text after "Blocker:" mentions "test data"')})
        script.engine.step_start("fix")
        script.write_checker(base.tight_checker())
        script.engine.step_run_checker("fix", "fixtures")
        self.assertTrue(script.check("fix")["ok"])
        script.engine.step_run_checker("baseline", "baseline")
        other = script.data("baseline")["summary"]
        self.assertEqual(self.summary["overall"], other["overall"])
        for mine, theirs in zip(self.summary["criteria"], other["criteria"]):
            self.assertEqual({k: mine[k] for k in ("id", "name", "passes", "checked_runs", "failing_runs", "rate")},
                             {k: theirs[k] for k in ("id", "name", "passes", "checked_runs", "failing_runs", "rate")})

    def test_a_matching_log_passes(self):
        self.ready()
        self.log()
        self.engine.step_start("baseline")
        result = self.check("baseline")
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.terminal.running)
        self.assertIsNone(self.state()["current_step"])

    def test_a_wrong_count_names_the_criterion_and_both_numbers(self):
        self.ready()
        c2 = next(c for c in self.summary["criteria"] if c["id"] == "C2")
        self.log(tweak={"C2": c2["passes"] - 1})
        result = self.check("baseline")
        self.assertFalse(result["ok"])
        item = next(i for i in result["items"] if i["label"].startswith("Pass counts"))
        self.assertEqual(item["detail"], f"The log says C2 passed {c2['passes'] - 1} of 5 runs. The app counted {c2['passes']} of 5.")

    def test_not_checked_must_be_listed(self):
        self.ready(nc=("C3",))
        self.assertEqual(self.summary["not_checked"], ["C3"])
        c3 = next(c for c in self.summary["criteria"] if c["id"] == "C3")
        self.assertTrue(c3["not_checked"])
        self.assertEqual(self.summary["overall"]["total"], 25)
        self.log(tweak={"not_checked": []})
        item = next(i for i in self.check("baseline")["items"] if i["label"].startswith("NOT CHECKED"))
        self.assertFalse(item["ok"])
        self.assertIn("C3", item["detail"])
        self.log()
        self.assertTrue(self.check("baseline")["ok"])

    def test_the_run_goes_stale_when_the_config_changes(self):
        self.ready()
        self.log()
        self.write_config(RUN_TESTS + FIXTURE_TESTS, tightened=True, extra="    # edited")
        result = self.check("baseline")
        self.assertFalse(result["ok"])
        item = next(i for i in result["items"] if i["label"] == "The app counted your five runs")
        self.assertIn("promptfooconfig.yaml or a run file changed", item["detail"])
        self.assertFalse(self.data("baseline")["fresh"])

    def test_the_fixtures_and_examples_never_reach_the_baseline(self):
        self.ready()
        self.assertEqual({c["id"] for c in self.summary["criteria"]}, set(base.IDS))
        self.assertEqual(len(self.data("baseline")["result"]["files"]), 5)

    def test_the_baseline_run_needs_all_five_runs(self):
        self.to_pf("baseline")
        self.paths.run_file(2).unlink()
        self.assert_code("missing_file", self.engine.step_run_checker, "baseline", "baseline")


class TrackFixed(PfCase):
    def test_before_any_step_the_track_can_change_and_the_steps_follow(self):
        self.setup_project(choose_inputs=False)
        self.engine.preflight_track("script")
        self.assertEqual(self.step_ids(), SCRIPT_STEPS)
        self.engine.preflight_track("promptfoo")
        self.assertEqual(self.step_ids(), PF_STEPS)
        self.assertFalse(self.state()["preflight"]["track_locked"])

    def test_after_a_step_is_done_the_track_is_fixed(self):
        self.setup_project()
        self.do_generate()
        self.assertTrue(self.check("generate")["ok"])
        self.assertEqual(self.engine.progress["track"], "promptfoo")
        with self.assertRaises(EngineError) as ctx:
            self.engine.preflight_track("script")
        self.assertEqual(ctx.exception.code, "track_locked")
        error = ctx.exception
        self.assertIn("track is fixed", error.message)
        self.assertEqual(self.engine.preflight.track, "promptfoo")
        self.engine.preflight_track("promptfoo")  # choosing the same track is harmless
        view = self.state()["preflight"]
        self.assertTrue(view["track_locked"])
        self.assertIn("start a new project in a different folder", view["track_locked_note"])
        self.assertEqual(view["track"], "promptfoo")

    def test_a_resumed_project_brings_its_track_along(self):
        self.setup_project()
        self.do_generate()
        self.check("generate")
        # The machine's choice says Script, but this project has a finished step on the promptfoo track.
        data = json.loads((self.home / "preflight.json").read_text(encoding="utf-8"))
        data["track"] = "script"
        (self.home / "preflight.json").write_text(json.dumps(data), encoding="utf-8")
        self.engine = self.new_engine()
        self.assertEqual(self.step_ids(), PF_STEPS)
        self.assertEqual(self.state()["preflight"]["track"], "promptfoo")
        self.assertEqual(self.engine.preflight.track, "promptfoo")
        self.assertEqual(self.status("build"), "active")

    def test_a_script_project_keeps_the_script_track_when_the_machine_says_promptfoo(self):
        script = base.EngineCase()
        script.setUp()
        self.addCleanup(script.tearDown)
        script.setup_project()
        script.do_generate()
        script.check("generate")
        self.assertEqual(script.engine.progress["track"], "script")
        data = json.loads((script.home / "preflight.json").read_text(encoding="utf-8"))
        data["track"] = "promptfoo"
        (script.home / "preflight.json").write_text(json.dumps(data), encoding="utf-8")
        reopened = script.new_engine()
        self.assertEqual([s["id"] for s in reopened.get_state()["steps"]], SCRIPT_STEPS)
        self.assertEqual(reopened.preflight.track, "script")
        self.assertEqual(reopened.get_state()["step"]["id"], "build")

    def test_a_progress_file_from_before_tracks_loads_as_script(self):
        script = base.EngineCase()
        script.setUp()
        self.addCleanup(script.tearDown)
        script.to_step("fix")
        data = json.loads(script.paths.progress_file.read_text(encoding="utf-8"))
        del data["track"]
        script.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")
        reopened = script.new_engine()
        self.assertEqual([s["id"] for s in reopened.get_state()["steps"]], SCRIPT_STEPS)
        self.assertEqual(reopened.get_state()["current_step"], "fix")

    def test_progress_validation_knows_both_orders(self):
        pf_done = ["inputs", "generate", "build", "fixtures", "fixtures-config", "readback"]
        data = new_progress("p", "c", "northwind")
        data["track"] = "promptfoo"
        data["done"] = pf_done
        self.assertEqual(validate_progress(data)["done"], pf_done)
        data["track"] = None  # the extra step alone says which track it is
        self.assertEqual(validate_progress(data)["done"], pf_done)
        script = new_progress("p", "c", "northwind")
        script["done"] = ["inputs", "generate", "build", "fixtures", "readback"]
        self.assertEqual(validate_progress(script)["done"], script["done"])
        script["track"] = "promptfoo"
        with self.assertRaises(CorruptStateError):
            validate_progress(script)
        script["track"] = "script"
        script["done"] = pf_done
        with self.assertRaises(CorruptStateError):
            validate_progress(script)
        script["track"] = "nonsense"
        script["done"] = []
        with self.assertRaises(CorruptStateError):
            validate_progress(script)

    def test_new_progress_has_no_extra_step_record_until_it_is_needed(self):
        self.assertNotIn("fixtures-config", new_progress("p", "c", "northwind")["steps"])
        self.setup_project()
        self.assertNotIn("fixtures-config", json.loads(self.paths.progress_file.read_text(encoding="utf-8"))["steps"])
        self.do_generate()
        self.check("generate")
        self.pf_build()
        self.check("build")
        self.do_fixtures()
        self.check("fixtures")
        self.state("fixtures-config")
        self.assertIn("fixtures-config", self.engine.progress["steps"])

    def test_the_preflight_exposes_the_track_and_npx_without_private_fields(self):
        self.setup_project()
        self.assertEqual(self.engine.preflight.track, "promptfoo")
        env = self.engine._cli_env()
        self.assertEqual(self.engine.preflight.npx_argv(env), [r"C:\fake\npx.exe"])
        self.engine.preflight.adopt_track("script")
        self.assertEqual(self.engine.preflight.track, "script")
        self.engine.preflight.adopt_track("bogus")
        self.assertEqual(self.engine.preflight.track, "script")


if __name__ == "__main__":
    import unittest
    unittest.main()
