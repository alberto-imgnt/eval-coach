"""Setup is a skippable global gate: the skip, hands-on gating and read-only previews before setup."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from course_helpers import CourseBase, bundled_course
from helpers import FakeTerminal

from eval_coach import project
from eval_coach.engine import Engine


class NoSetupBase(unittest.TestCase):
    """An engine whose setup has not passed: no preflight results are saved."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-gate-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        self.terminal = FakeTerminal()
        self.course = bundled_course()
        self.engine = self.new_engine()

    def new_engine(self):
        engine = Engine(self.home, self.terminal, poll_interval=0.01, lessons=self.course)
        self.addCleanup(engine.shutdown)
        return engine

    def make_project(self):
        self.engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        return project.Paths(self.home, self.project)

    def code_of(self, fn, *args):
        from eval_coach.engine import EngineError
        with self.assertRaises(EngineError) as ctx:
            fn(*args)
        return ctx.exception.code


class SkipTests(NoSetupBase):
    def test_a_fresh_install_has_not_skipped(self):
        state = self.engine.get_state()
        self.assertFalse(state["preflight"]["passed"])
        self.assertFalse(state["preflight"]["skipped"])

    def test_skipping_is_remembered_across_launches(self):
        self.engine.preflight_skip()
        self.assertTrue(self.engine.get_state()["preflight"]["skipped"])
        self.assertTrue(self.new_engine().get_state()["preflight"]["skipped"])
        self.assertTrue(json.loads((self.home / "preflight.json").read_text(encoding="utf-8"))["setup_skipped"])

    def test_a_configuration_reset_forgets_the_skip_and_a_progress_reset_keeps_it(self):
        self.make_project()
        self.engine.preflight_skip()
        self.engine.reset_progress(True)
        self.assertTrue(self.engine.get_state()["preflight"]["skipped"])
        self.engine.reset_configuration(True)
        self.assertFalse(self.engine.get_state()["preflight"]["skipped"])
        self.assertFalse(self.new_engine().get_state()["preflight"]["skipped"])

    def test_skipping_does_not_unlock_hands_on_work(self):
        self.make_project()
        self.engine.preflight_skip()
        state = self.engine.get_state()
        self.assertTrue(all(s["status"] == "locked" for s in state["steps"]))
        self.assertEqual(self.code_of(self.engine.step_start, "generate"), "preflight_incomplete")


class GateBeforeSetup(NoSetupBase):
    def setUp(self):
        super().setUp()
        self.paths = self.make_project()

    def progress_bytes(self):
        return self.paths.progress_file.read_bytes()

    def test_cli_exercises_and_steps_are_refused_before_setup(self):
        for lesson, activity in (("hook", "hook-compare"), ("rules", "build-try"), ("surprise", "fix-try")):
            self.assertIn(self.code_of(self.engine.lesson_cli_start, lesson, activity),
                          ("preflight_incomplete", "lesson_locked"), lesson)
            self.assertIn(self.code_of(self.engine.lesson_cli_send, lesson, activity),
                          ("preflight_incomplete", "lesson_locked"), lesson)
        self.assertEqual(self.code_of(self.engine.step_start, "generate"), "preflight_incomplete")
        self.assertEqual(self.terminal.starts, [])

    def test_an_open_lesson_with_a_cli_exercise_is_still_refused_before_setup(self):
        # The mission is the one lesson open before setup. Make the hook open by normal order to prove the guard.
        self.engine.progress["lessons"]["per_lesson"]["mission"] = {"status": "done", "activities": {}}
        self.engine._save()
        self.engine._walk = lambda passed, part=None: [("lesson", "hook", "active")]
        self.assertEqual(self.code_of(self.engine.lesson_cli_start, "hook", "hook-compare"), "preflight_incomplete")
        self.assertEqual(self.terminal.starts, [])

    def test_a_locked_lesson_opens_as_a_preview_that_records_nothing(self):
        before = self.progress_bytes()
        view = self.engine.lesson_view("hook")["lesson"]
        self.assertEqual(view["status"], "preview")
        self.assertTrue(view["body"])
        self.assertEqual([a["id"] for a in view["activities"]], ["hook-compare", "hook-explain"])
        self.assertFalse(view["can_complete"])
        self.assertFalse(view["can_skip"])
        self.assertEqual(self.progress_bytes(), before)

    def test_every_lesson_can_be_read_in_any_order(self):
        before = self.progress_bytes()
        for lesson in self.course.data["lessons"]:
            if lesson["id"] in ("mission", "p1-mission", "p2-mission"):
                continue
            self.assertEqual(self.engine.lesson_view(lesson["id"])["lesson"]["status"], "preview", lesson["id"])
        self.assertEqual(self.progress_bytes(), before)

    def test_preview_exercises_cannot_be_answered_or_completed(self):
        before = self.progress_bytes()
        self.assertEqual(self.code_of(self.engine.lesson_answer, "several-runs", "generate-spot", {"option": "a"}),
                         "preflight_incomplete")
        self.assertEqual(self.code_of(self.engine.lesson_complete, "several-runs"), "preflight_incomplete")
        self.assertEqual(self.code_of(self.engine.lesson_skip, "several-runs"), "preflight_incomplete")
        self.assertEqual(self.code_of(self.engine.lesson_rule_run, "rules", "rules-lab", "r", "text"),
                         "preflight_incomplete")
        self.assertEqual(self.progress_bytes(), before)

    def test_the_open_lesson_works_as_normal(self):
        view = self.engine.lesson_view("mission")["lesson"]
        self.assertEqual(view["status"], "active")
        self.assertEqual(self.engine.get_state()["current_item"], {"kind": "lesson", "id": "mission"})

    def test_a_step_can_be_read_but_nothing_in_it_starts(self):
        before = self.progress_bytes()
        state = self.engine.get_state("build")
        step = state["step"]
        self.assertTrue(step["preview"])
        self.assertEqual((step["id"], step["status"]), ("build", "locked"))
        self.assertTrue(step["instructions"])
        self.assertIsNone(step["cli"])
        self.assertEqual(self.progress_bytes(), before)
        self.assertEqual(self.code_of(self.engine.step_start, "build"), "preflight_incomplete")

    def test_no_step_detail_unless_one_is_asked_for(self):
        self.assertIsNone(self.engine.get_state()["step"])

    def test_after_setup_the_same_requests_are_allowed(self):
        helpers.write_passed_preflight(self.home)
        engine = self.new_engine()
        engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.assertTrue(engine.get_state()["preflight"]["passed"])
        engine.lesson_complete("mission")
        engine.lesson_cli_start("hook", "hook-compare")
        self.assertEqual(len(self.terminal.starts), 1)
        self.assertEqual(engine.get_state("build")["step"]["status"], "locked")
        self.assertTrue(engine.get_state("build")["step"]["preview"])  # still read-only: its lesson is not done


class PreviewWithoutAProject(NoSetupBase):
    def test_reading_ahead_before_a_project_exists_writes_nothing(self):
        before = sorted(p.name for p in self.home.iterdir())
        view = self.engine.lesson_view("hook")["lesson"]
        self.assertEqual(view["status"], "preview")
        self.assertEqual(self.engine.get_state("generate")["step"]["status"], "locked")
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), before)
        self.assertFalse((self.home / "pending-lessons.json").exists())

    def test_the_cli_exercise_is_refused(self):
        self.assertIn(self.code_of(self.engine.lesson_cli_start, "hook", "hook-compare"),
                      ("preflight_incomplete", "lesson_locked"))


class SetupGateWithPassedSetup(CourseBase):
    def test_a_passed_setup_never_shows_as_skipped_needed(self):
        self.setup_project()
        state = self.engine.get_state()
        self.assertTrue(state["preflight"]["passed"])
        self.assertFalse(state["preflight"]["skipped"])
