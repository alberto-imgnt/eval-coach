"""Task 4.28: the Northwind example's fixtures as a recovery path in the fixtures step."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import test_engine_gates as base
from helpers import NORTHWIND
from test_http import ServerCase
from test_promptfoo_track import PfCase

from eval_coach import resources
from eval_coach.project import FIXTURE_NAMES

OWN_FILES = {"prompt_path": str(NORTHWIND / "northwind-prompt-v0.md"),
             "test_cases_path": str(NORTHWIND / "northwind-test-cases-reference.md")}


def keys_under(root):
    root = Path(root)
    return [p for p in root.rglob("*") if p.is_file() and p.name.lower() == "answer-key.md"] if root.exists() else []


class ExampleFixtures(base.EngineCase):
    def to_fixtures(self, **setup):
        """Done: generate and build. The fixtures step is active and its CLI has not been started."""
        self.setup_project(**setup)
        self.do_generate()
        self.assertTrue(self.check("generate")["ok"])
        self.do_build()
        self.assertTrue(self.check("build")["ok"])
        self.assertEqual(self.status("fixtures"), "active")
        self.engine.step_stop("fixtures")  # the build chat stays open until someone stops it

    def use(self, **body):
        self.engine.step_use_example_fixtures(body.get("step", "fixtures"), body.get("replace"))

    def assert_code(self, code, fn, *args, **kw):
        with self.assertRaises(base.EngineError) as ctx:
            fn(*args, **kw)
        self.assertEqual(ctx.exception.code, code)

    def example_bytes(self, name):
        return (NORTHWIND / name).read_bytes()

    def assert_no_key_in_tmp(self):
        self.assertEqual(keys_under(self.tmp), [])

    def assert_work_untouched(self):
        self.assertFalse(self.paths.work_fixtures.exists() and any(self.paths.work_fixtures.iterdir()))

    def test_writes_only_the_two_fixtures_where_the_cli_writes_them(self):
        self.to_fixtures()
        self.use()
        self.assertEqual(sorted(p.name for p in self.paths.work_fixtures.iterdir()), sorted(FIXTURE_NAMES))
        for name in FIXTURE_NAMES:
            self.assertEqual((self.paths.work_fixtures / name).read_bytes(), self.example_bytes(name))
        self.assertEqual(self.paths.work_fixtures, self.paths.home / "fixtures-work" / "fixtures")
        self.assertFalse(self.paths.fixtures.exists() and any(self.paths.fixtures.iterdir()))
        self.assert_no_key_in_tmp()

    def test_the_normal_gate_then_runs_unchanged_and_copies_the_files(self):
        self.to_fixtures()
        self.engine.step_start("fixtures")
        self.engine.step_stop("fixtures")
        self.assertFalse(self.check("fixtures")["ok"])
        self.use()
        result = self.check("fixtures")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["nudges"], [])
        self.assertEqual(self.status("fixtures"), "done")
        for name in FIXTURE_NAMES:
            self.assertEqual((self.paths.fixtures / name).read_bytes(), self.example_bytes(name))
        self.assertEqual(sorted(p.name for p in self.paths.fixtures.iterdir()), sorted(FIXTURE_NAMES))
        self.assert_no_key_in_tmp()
        self.assert_key_hidden()

    def test_no_answer_key_exists_anywhere_after_the_action_or_after_the_gate(self):
        self.to_fixtures()
        self.use()
        self.assert_no_key_in_tmp()
        self.assertFalse(self.paths.sealed_key.exists())
        self.assertFalse(self.paths.project_key.exists())
        self.assertFalse(self.paths.key_work_key.exists())
        self.assertNotIn("answer-key", json.dumps(self.state("fixtures")["step"]["data"]).replace("fixture-", ""))
        self.assertTrue(self.check("fixtures")["ok"])
        self.assert_no_key_in_tmp()
        self.assertEqual(sorted(p.name for p in self.paths.fixtures.iterdir()), sorted(FIXTURE_NAMES))

    def test_the_key_step_still_happens_after_predictions_lock(self):
        self.to_fixtures()
        self.use()
        self.assertTrue(self.check("fixtures")["ok"])
        self.do_readback()
        self.assertTrue(self.check("readback")["ok"])
        self.assertFalse(self.paths.sealed_key.exists())
        self.assert_code("step_locked", self.engine.step_start, "key")
        self.do_predict()
        self.assertTrue(self.check("predict")["ok"])
        self.assert_no_key_in_tmp()
        self.do_key()
        self.assertTrue(self.check("key")["ok"])
        self.assertTrue(self.paths.sealed_key.is_file())

    def test_it_works_before_start_and_after_the_cli_was_stopped(self):
        self.to_fixtures()
        self.assertFalse(self.paths.fixtures_work.exists())
        self.use()
        self.assertTrue((self.paths.work_fixtures / FIXTURE_NAMES[0]).is_file())
        self.engine.step_start("fixtures")
        self.assertFalse(self.paths.work_fixtures.exists())  # Start clears the folder, as it always did
        self.engine.step_stop("fixtures")
        self.use()
        self.assertTrue((self.paths.work_fixtures / FIXTURE_NAMES[1]).is_file())

    # --- refusals ---

    def test_refused_for_the_own_starter(self):
        self.to_fixtures(starter="own", **OWN_FILES)
        self.assertEqual(self.state()["setup"]["starter"], "own")
        self.assertEqual(self.data("fixtures")["example"], {"offered": False, "would_replace": False})
        for replace in (None, True):
            with self.subTest(replace=replace):
                self.assert_code("example_fixtures_northwind_only", self.use, replace=replace)
        self.assert_work_untouched()
        self.assert_no_key_in_tmp()
        message = self.capture_message(self.use)
        self.assertIn("Practice task", message)
        self.assertIn("paste its line", message)
        self.assertFalse(self.check("fixtures")["ok"])

    def capture_message(self, fn, **kw):
        with self.assertRaises(base.EngineError) as ctx:
            fn(**kw)
        return ctx.exception.message

    def test_refused_before_the_project_exists(self):
        self.assert_code("not_configured", self.engine.step_use_example_fixtures, "fixtures", None)

    def test_refused_when_the_step_is_not_active(self):
        self.setup_project()
        self.assert_code("step_locked", self.use)  # generate is still the active step
        self.assertEqual(self.status("generate"), "active")
        self.assert_work_untouched()
        self.do_generate()
        self.assertTrue(self.check("generate")["ok"])
        self.assert_code("step_locked", self.use)  # build is next
        self.do_build()
        self.assertTrue(self.check("build")["ok"])
        self.engine.step_stop("build")
        self.use()  # now fixtures is active
        self.assertTrue(self.check("fixtures")["ok"])
        self.assert_code("step_done", self.use)

    def test_refused_for_any_other_step(self):
        self.setup_project()
        self.assert_code("no_example_fixtures", self.use, step="generate")
        self.assert_code("unknown_step", self.use, step="bogus")
        self.assert_code("unknown_step", self.use, step=None)
        self.assert_work_untouched()

    def test_refused_while_the_cli_is_running(self):
        self.to_fixtures()
        self.engine.step_start("fixtures")
        self.assertTrue(self.terminal.running)
        self.assert_code("cli_running", self.use)
        self.assert_code("cli_running", self.use, replace=True)
        self.assertFalse(self.paths.work_fixtures.exists())
        self.engine.step_stop("fixtures")
        self.use()
        self.assertTrue((self.paths.work_fixtures / FIXTURE_NAMES[0]).is_file())

    def test_refused_while_a_lesson_or_other_cli_is_running(self):
        self.to_fixtures()
        self.terminal.running = True
        self.assert_code("cli_running", self.use)
        self.assert_work_untouched()

    def test_never_replaces_text_without_confirmation(self):
        self.to_fixtures()
        self.paths.work_fixtures.mkdir(parents=True)
        mine = self.paths.work_fixtures / FIXTURE_NAMES[0]
        mine.write_text("my own fixture", encoding="utf-8")
        self.assertEqual(self.data("fixtures")["example"], {"offered": True, "would_replace": True})
        for replace in (None, False):
            with self.subTest(replace=replace):
                self.assert_code("confirm_replace", self.use, replace=replace)
                self.assertEqual(mine.read_text(encoding="utf-8"), "my own fixture")
                self.assertFalse((self.paths.work_fixtures / FIXTURE_NAMES[1]).exists())
        for bad in ("yes", 1, "true", [True]):
            with self.subTest(replace=bad):
                self.assert_code("bad_input", self.use, replace=bad)
                self.assertEqual(mine.read_text(encoding="utf-8"), "my own fixture")
        self.use(replace=True)
        self.assertEqual(mine.read_bytes(), self.example_bytes(FIXTURE_NAMES[0]))
        self.assertEqual((self.paths.work_fixtures / FIXTURE_NAMES[1]).read_bytes(), self.example_bytes(FIXTURE_NAMES[1]))
        self.assert_no_key_in_tmp()

    def test_the_second_file_alone_also_needs_confirmation(self):
        self.to_fixtures()
        self.paths.work_fixtures.mkdir(parents=True)
        (self.paths.work_fixtures / FIXTURE_NAMES[1]).write_text("kept", encoding="utf-8")
        self.assert_code("confirm_replace", self.use)
        self.assertEqual((self.paths.work_fixtures / FIXTURE_NAMES[1]).read_text(encoding="utf-8"), "kept")
        self.assertFalse((self.paths.work_fixtures / FIXTURE_NAMES[0]).exists())

    def test_empty_or_blank_files_are_replaced_without_asking(self):
        self.to_fixtures()
        self.paths.work_fixtures.mkdir(parents=True)
        (self.paths.work_fixtures / FIXTURE_NAMES[0]).write_text("", encoding="utf-8")
        (self.paths.work_fixtures / FIXTURE_NAMES[1]).write_text("  \n\t\n", encoding="utf-8")
        self.assertEqual(self.data("fixtures")["example"]["would_replace"], False)
        self.use()
        for name in FIXTURE_NAMES:
            self.assertEqual((self.paths.work_fixtures / name).read_bytes(), self.example_bytes(name))

    def test_a_key_the_cli_wrote_is_left_to_the_normal_gate_to_delete(self):
        self.to_fixtures()
        self.paths.work_fixtures.mkdir(parents=True)
        (self.paths.work_fixtures / "answer-key.md").write_text("stray", encoding="utf-8")
        self.use()
        self.assertEqual([p.name for p in keys_under(self.tmp)], ["answer-key.md"])  # the action neither wrote nor needed it
        result = self.check("fixtures")
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["nudges"]), 1)
        self.assert_no_key_in_tmp()

    def test_the_answer_key_text_never_leaves_the_kit(self):
        self.to_fixtures()
        sentinels = ("Answer key: Northwind example fixtures", "What is wrong with it", "Tighten C3, for example")
        for sentinel in sentinels:
            self.assertIn(sentinel, (NORTHWIND / "answer-key.md").read_text(encoding="utf-8"))
        self.use()
        self.assertTrue(self.check("fixtures")["ok"])
        for path in self.tmp.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                for sentinel in sentinels:
                    self.assertNotIn(sentinel, text, str(path))
        self.assertNotIn("Tighten C3", json.dumps(self.state("fixtures")))

    def test_state_says_what_the_panel_needs(self):
        self.to_fixtures()
        self.assertEqual(self.data("fixtures")["example"], {"offered": True, "would_replace": False})
        ui = self.state("fixtures")["step"]["ui"]
        for key in ("example_heading", "example_blurb", "example_button", "example_confirm_title",
                    "example_confirm_body", "example_confirm_label"):
            self.assertTrue(ui[key], key)
        self.assertIn("Practice task", ui["example_blurb"])
        self.assertIn("fit its test cases only", ui["example_blurb"])
        self.use()
        self.assertEqual(self.data("fixtures")["example"], {"offered": True, "would_replace": True})
        self.assertEqual(self.data("fixtures")["files"], [{"name": n, "present": True} for n in FIXTURE_NAMES])

    def test_the_older_progress_without_a_starter_is_refused(self):
        self.to_fixtures()
        del self.engine.progress["starter"]
        self.assert_code("example_fixtures_northwind_only", self.use)
        self.assert_work_untouched()


class ExampleFixturesPromptfoo(PfCase):
    def test_the_recovery_works_on_the_promptfoo_track_and_the_next_step_follows(self):
        self.setup_project()
        self.do_generate()
        self.assertTrue(self.check("generate")["ok"])
        self.pf_build()
        self.assertTrue(self.check("build")["ok"])
        self.engine.step_stop("build")
        self.engine.step_use_example_fixtures("fixtures", None)
        self.assertEqual(sorted(p.name for p in self.paths.work_fixtures.iterdir()), sorted(FIXTURE_NAMES))
        self.assertTrue(self.check("fixtures")["ok"])
        self.assertEqual(self.status("fixtures-config"), "active")
        self.assertEqual(keys_under(self.tmp), [])
        self.assert_code("no_example_fixtures", self.engine.step_use_example_fixtures, "fixtures-config", None)

    def test_the_troubleshooting_entry_is_on_both_tracks_for_the_fixtures_step(self):
        self.setup_project()
        self.engine.progress["done"] = ["generate", "build"]
        self.engine._save()
        text = self.state("fixtures")["step"]["troubleshooting"]
        self.assertTrue([t for t in text if "Practice task" in t["problem"]])


class ExampleFixturesHttp(ServerCase):
    ROUTE = "/api/step/use-example-fixtures"

    def to_fixtures(self):
        self.setup_project()
        self.engine.progress["done"] = ["generate", "build"]
        self.engine._save()
        self.work = Path(self.engine.paths.work_fixtures)

    def test_route_writes_the_two_files_and_returns_the_new_state(self):
        self.to_fixtures()
        status, body = self.post(self.ROUTE, {"step": "fixtures"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["state"]["step"]["id"], "fixtures")
        self.assertEqual(body["state"]["step"]["data"]["example"], {"offered": True, "would_replace": True})
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), sorted(FIXTURE_NAMES))
        for name in FIXTURE_NAMES:
            self.assertEqual((self.work / name).read_bytes(), resources.read_bytes("kit/northwind/" + name))
        self.assertEqual(keys_under(self.tmp), [])
        status, body = self.post("/api/step/check", {"step": "fixtures"})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["state"]["step"]["last_check"]["ok"])
        self.assertEqual(keys_under(self.tmp), [])

    def test_route_needs_the_token_and_a_step(self):
        self.to_fixtures()
        status, _ = self.post(self.ROUTE, {"step": "fixtures"}, token=False)
        self.assertEqual(status, 401)
        status, body = self.post(self.ROUTE, {})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unknown_step")
        self.assertFalse(self.work.exists())

    def test_confirmation_over_http(self):
        self.to_fixtures()
        self.work.mkdir(parents=True)
        (self.work / FIXTURE_NAMES[0]).write_text("mine", encoding="utf-8")
        status, body = self.post(self.ROUTE, {"step": "fixtures"})
        self.assertEqual((status, body["error"]["code"]), (400, "confirm_replace"))
        self.assertEqual((self.work / FIXTURE_NAMES[0]).read_text(encoding="utf-8"), "mine")
        self.assertEqual(body["state"]["step"]["data"]["example"]["would_replace"], True)
        status, body = self.post(self.ROUTE, {"step": "fixtures", "replace": "yes"})
        self.assertEqual((status, body["error"]["code"]), (400, "bad_input"))
        status, body = self.post(self.ROUTE, {"step": "fixtures", "replace": True})
        self.assertEqual(status, 200, body)
        self.assertEqual((self.work / FIXTURE_NAMES[0]).read_bytes(), resources.read_bytes("kit/northwind/" + FIXTURE_NAMES[0]))

    def test_refused_while_the_cli_runs_and_when_not_active(self):
        self.setup_project()
        status, body = self.post(self.ROUTE, {"step": "fixtures"})
        self.assertEqual((status, body["error"]["code"]), (400, "step_locked"))
        self.engine.progress["done"] = ["generate", "build"]
        self.engine._save()
        status, body = self.post("/api/step/start", {"step": "fixtures"})
        self.assertEqual(status, 200, body)
        status, body = self.post(self.ROUTE, {"step": "fixtures"})
        self.assertEqual((status, body["error"]["code"]), (400, "cli_running"))
        self.assertFalse((Path(self.engine.paths.work_fixtures)).exists())
        self.post("/api/step/stop", {"step": "fixtures"})
        status, body = self.post(self.ROUTE, {"step": "fixtures"})
        self.assertEqual(status, 200, body)

    def test_refused_for_the_own_starter_over_http(self):
        status, body = self.post("/api/setup", dict(OWN_FILES, project_path=str(self.tmp / "own"),
                                                    cli_command="cli", starter="own"))
        self.assertEqual(status, 200, body)
        self.engine.progress["done"] = ["generate", "build"]
        self.engine._save()
        status, body = self.post(self.ROUTE, {"step": "fixtures", "replace": True})
        self.assertEqual((status, body["error"]["code"]), (400, "example_fixtures_northwind_only"))
        self.assertEqual(body["state"]["step"]["data"]["example"], {"offered": False, "would_replace": False})
        self.assertFalse(Path(self.engine.paths.work_fixtures).exists())
        self.assertEqual(keys_under(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
