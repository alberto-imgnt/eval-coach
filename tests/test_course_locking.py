"""Course locking: what opens for a participant, what is refused, and how a skipped Part behaves."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import course_helpers as ch
import helpers

from eval_coach import project, state
from eval_coach.engine import EngineError

PART_1, PART_2, PART_3 = state.PART_1, state.PART_2, state.PART_3


class LockBase(ch.CourseBase):
    """Demo access off, as for a participant. Setup has passed and a project exists."""

    def setUp(self):
        super().setUp()
        self.engine.demo_lock()
        self.setup_project()

    def finish_part(self, part):
        """Mark every lesson and step of a Part done, as if the participant had finished it."""
        block = self.engine._lessons_block()
        for kind, item in part.course:
            if kind == "lesson":
                block["per_lesson"][item] = {"status": "done", "activities": {}}
        if part.progress_key is None:
            self.engine.progress["done"][:] = list(part.step_ids)
        else:
            self.engine._progress_of(part)["done"][:] = list(part.step_ids)
        self.engine._save()

    def series_row(self, part_id, snapshot=None):
        return next(p for p in (snapshot or self.engine.get_state())["series"]["parts"] if p["id"] == part_id)

    def statuses(self, part):
        return {i["id"]: i["status"] for i in self.engine.get_state(part=part.id)["course"]}

    def progress_bytes(self):
        return self.paths.progress_file.read_bytes()


class PartGate(LockBase):
    def test_a_later_part_is_locked_as_a_whole_while_the_earlier_one_is_unfinished(self):
        self.assertEqual(set(self.statuses(PART_2).values()), {"locked"})
        self.assertEqual(set(self.statuses(PART_3).values()), {"locked"})
        self.assertEqual(self.series_row("part-2")["state"], "locked")
        self.assertEqual(self.series_row("part-3")["state"], "locked")
        self.assertEqual(self.statuses(PART_1)["p1-mission"], "active")

    def test_a_locked_part_refuses_every_lesson_and_step_and_changes_nothing(self):
        before = self.progress_bytes()
        message = self.engine.lesson_text["ui"]["locked_tip"]
        for lesson in ("p2-mission", "mission"):
            self.assertEqual(self.assert_code("lesson_locked", self.engine.lesson_view, lesson).message, message)
        self.assert_code("lesson_locked", self.engine.lesson_complete, "p2-mission")
        for step in ("draft", "generate"):
            self.assertEqual(self.assert_code("step_locked", self.engine.get_state, step=step).message, message)
            self.assert_code("step_locked", self.engine.step_start, step)
        self.assertEqual(self.progress_bytes(), before)
        self.assertEqual(self.terminal.starts, [])

    def test_selecting_a_locked_part_does_not_start_or_record_anything(self):
        before = self.progress_bytes()
        view = self.engine.get_state(part="part-3")
        self.assertEqual(set(i["status"] for i in view["course"]), {"locked"})
        self.assertIsNone(view["current_item"])
        self.assertEqual(self.series_row("part-3", view)["state"], "locked")
        self.assertEqual(self.progress_bytes(), before)

    def test_part_two_opens_when_part_one_is_done(self):
        self.finish_part(PART_1)
        self.assertEqual(self.statuses(PART_2)["p2-mission"], "active")
        self.assertEqual(self.series_row("part-2")["state"], "not_started")
        self.assertEqual(self.series_row("part-3")["state"], "locked")
        self.assertEqual(self.engine.lesson_view("p2-mission")["lesson"]["status"], "active")

    def test_part_three_opens_after_part_one_skipped_and_part_two_done(self):
        self.engine.part_skip("part-1", True)
        self.finish_part(PART_2)
        self.assertEqual(self.statuses(PART_3)["mission"], "active")
        self.assertEqual(self.series_row("part-3")["state"], "not_started")

    def test_a_participant_already_ahead_is_held_but_keeps_their_work(self):
        self.engine.progress["done"][:] = ["inputs", "generate"]
        self.engine._save()
        self.assertEqual(set(self.statuses(PART_3).values()), {"locked"})
        self.finish_part(PART_1)
        self.finish_part(PART_2)
        self.assertEqual(self.statuses(PART_3)["generate"], "done")

    def test_an_engine_with_no_course_has_nothing_gated(self):
        engine = self.new_engine(lessons=False, demo=False)
        self.assertEqual(engine.get_state()["steps"][0]["status"], "active")
        self.assertTrue(engine._part_open(PART_3))


class WithinAPart(LockBase):
    def test_demo_access_does_not_skip_the_input_choice(self):
        self.engine._demo_on = True
        self.finish_before("inputs")
        self.assertEqual(self.statuses(PART_3)["inputs"], "active")
        self.assert_code("step_locked", self.engine.step_start, "generate")
        self.engine.step_check("inputs")
        self.assertEqual(self.statuses(PART_3)["generate"], "active")

    def test_only_the_next_item_opens_in_an_open_part(self):
        statuses = self.statuses(PART_1)
        self.assertEqual([k for k, v in statuses.items() if v == "active"], ["p1-mission"])
        self.assert_code("step_locked", self.engine.get_state, step="score")
        self.assert_code("lesson_locked", self.engine.lesson_view, "p1-gaps")

    def test_a_finished_item_can_be_read_again(self):
        self.engine.lesson_complete("p1-mission")
        self.assertEqual(self.engine.lesson_view("p1-mission")["lesson"]["status"], "done")
        self.assertEqual(self.statuses(PART_1)["cold"], "active")

    def test_the_key_step_is_refused_and_the_sealed_key_is_never_read(self):
        self.finish_part(PART_1)
        self.finish_part(PART_2)
        self.engine.progress["done"][:] = ["inputs", "generate", "build", "fixtures", "readback"]
        self.engine._save()
        self.paths.sealed_key.parent.mkdir(parents=True, exist_ok=True)
        self.paths.sealed_key.write_text("SEALED-KEY-TEXT", encoding="utf-8")
        error = self.assert_code("step_locked", self.engine.get_state, step="key")
        self.assertNotIn("SEALED-KEY-TEXT", error.message)
        self.assertNotIn("SEALED-KEY-TEXT", json.dumps(self.engine.get_state()))

    def test_locked_lessons_are_links_only_when_open(self):
        self.engine.lesson_complete("p1-mission")
        self.finish_part(PART_1)
        related = self.engine.lesson_view("p1-mission")["lesson"]["related"]["lessons"]
        for entry in related:
            self.assertEqual(entry["open"], self.engine._lesson_status(entry["id"]) != "locked")


class BeforeSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-lock-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home, self.project = self.tmp / "home", self.tmp / "project"
        self.terminal = helpers.FakeTerminal()
        self.engine = helpers.make_engine(self.home, self.terminal, lessons=ch.bundled_course(), demo=False)
        self.addCleanup(self.engine.shutdown)

    def test_with_setup_skipped_only_the_current_item_of_an_open_part_can_be_read(self):
        statuses = {i["id"]: i["status"] for i in self.engine.get_state(part="part-1")["course"]}
        self.assertEqual([k for k, v in statuses.items() if v == "active"], ["p1-mission"])
        self.assertEqual(self.engine.lesson_view("p1-mission")["lesson"]["status"], "active")
        self.assert_locked(self.engine.lesson_view, "p1-gaps")
        self.assert_locked(self.engine.get_state, "cold")

    def test_the_first_step_after_a_lesson_opens_as_words_only_with_setup_skipped(self):
        self.engine.lesson_complete("p1-mission")
        words = self.engine.get_state(step="cold")["step"]
        self.assertTrue(words["preview"])
        self.assertEqual(words["status"], "active")
        self.assertIsNone(words["cli"])
        self.assertEqual(words["data"], {})
        self.assertFalse((self.home / "part-1").exists())
        code = self.code_of(self.engine.step_start, "cold")
        self.assertEqual(code, "not_configured")

    def test_a_skip_before_a_project_exists_is_kept_and_merged_when_the_project_is_made(self):
        self.engine.part_skip("part-1", True)
        pending = json.loads((self.home / "pending-lessons.json").read_text(encoding="utf-8"))
        self.assertEqual(pending["skipped_parts"], ["part-1"])
        self.assertEqual(self.engine.get_state(part="part-2")["course"][0]["status"], "active")
        again = helpers.make_engine(self.home, self.terminal, lessons=ch.bundled_course(), demo=False)
        self.addCleanup(again.shutdown)
        again.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.assertEqual(again.progress["lessons"]["skipped_parts"], ["part-1"])

    def code_of(self, fn, *args):
        with self.assertRaises(EngineError) as ctx:
            fn(*args)
        return ctx.exception.code

    def assert_locked(self, fn, *args):
        self.assertIn(self.code_of(fn, *args), ("lesson_locked", "step_locked"))


class SavedShape(LockBase):
    def test_a_progress_file_without_skipped_parts_loads_with_an_empty_list_and_is_not_rewritten(self):
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        del data["lessons"]["skipped_parts"]
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")
        before = self.paths.progress_file.read_bytes()
        loaded = state.load_progress(self.paths.progress_file)
        self.assertEqual(loaded["lessons"]["skipped_parts"], [])
        self.assertEqual(self.paths.progress_file.read_bytes(), before)

    def test_an_unknown_part_id_is_dropped_on_load(self):
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        data["lessons"]["skipped_parts"] = ["part-1", "part-77"]
        self.assertEqual(state.validate_progress(data)["lessons"]["skipped_parts"], ["part-1"])


class SkipAPart(LockBase):
    def test_the_open_part_can_be_skipped_and_the_next_part_opens(self):
        self.assertTrue(self.series_row("part-1")["can_skip"])
        self.assertFalse(self.series_row("part-2")["can_skip"])
        self.engine.part_skip("part-1", True)
        self.assertEqual(self.series_row("part-1")["state"], "skipped")
        self.assertIsNone(self.series_row("part-1")["done"])
        self.assertFalse(self.series_row("part-1")["can_skip"])
        self.assertEqual(self.statuses(PART_2)["p2-mission"], "active")

    def test_a_skip_needs_confirmation_and_an_open_unfinished_part(self):
        before = self.progress_bytes()
        for confirm in (None, False, "yes", 1):
            self.assert_code("confirm_required", self.engine.part_skip, "part-1", confirm)
        self.assert_code("skip_unavailable", self.engine.part_skip, "part-2", True)  # locked
        self.assert_code("skip_unavailable", self.engine.part_skip, "part-3", True)
        self.assert_code("unknown_part", self.engine.part_skip, "part-4", True)  # coming soon, no content
        self.assert_code("unknown_part", self.engine.part_skip, None, True)
        self.finish_part(PART_1)
        self.assert_code("skip_unavailable", self.engine.part_skip, "part-1", True)  # finished
        self.engine.part_skip("part-2", True)
        self.assert_code("skip_unavailable", self.engine.part_skip, "part-2", True)  # already skipped
        self.assertNotEqual(self.progress_bytes(), before)
        self.assertEqual(self.engine._lessons_block()["skipped_parts"], ["part-2"])

    def test_part_three_can_be_skipped_and_every_part_then_counts_as_finished(self):
        self.engine.part_skip("part-1", True)
        self.engine.part_skip("part-2", True)
        self.engine.part_skip("part-3", True)
        self.assertEqual([p["state"] for p in self.engine.get_state()["series"]["parts"] if "state" in p],
                         ["skipped", "skipped", "skipped"])
        self.assertIsNone(self.engine.get_state()["series"]["active_part"])

    def test_the_skip_is_remembered_and_saved_work_stays(self):
        self.engine.progress["parts"]["part-1"] = state.new_part_progress(PART_1)
        self.engine.progress["parts"]["part-1"]["done"][:] = ["cold"]
        self.engine.progress["parts"]["part-1"]["steps"]["cold"]["model_name"] = "my model"
        self.engine._save()
        part_before = json.loads(json.dumps(self.engine.progress["parts"]))
        self.engine.part_skip("part-1", True)
        again = self.new_engine(demo=False)
        self.assertEqual(again.progress["lessons"]["skipped_parts"], ["part-1"])
        self.assertEqual(again.progress["parts"], part_before)

    def test_items_of_a_skipped_part_open_read_only(self):
        self.engine.part_skip("part-1", True)
        statuses = self.statuses(PART_1)
        self.assertEqual(set(statuses.values()), {"skipped"})
        before = self.progress_bytes()
        view = self.engine.lesson_view("p1-gaps")["lesson"]
        self.assertEqual((view["status"], view["part_skipped"]), ("skipped", True))
        self.assertTrue(view["body"])
        self.assertFalse(view["can_complete"] or view["can_skip"])
        words = self.engine.get_state(step="score")["step"]
        self.assertEqual((words["status"], words["part_skipped"], words["cli"], words["data"]),
                         ("skipped", True, None, {}))
        self.assertTrue(words["instructions"])
        self.assertEqual(self.progress_bytes(), before)
        self.assertFalse(self.paths.part1_root.exists())

    def test_nothing_in_a_skipped_part_can_be_done(self):
        self.engine.part_skip("part-1", True)
        before = self.progress_bytes()
        self.assert_code("lesson_skipped", self.engine.lesson_complete, "p1-mission")
        self.assert_code("lesson_skipped", self.engine.lesson_answer, "p1-mission", "x", {})
        for step in ("cold", "score"):
            self.assert_code("step_skipped", self.engine.step_start, step)
            self.assert_code("step_skipped", self.engine.step_check, step)
            self.assert_code("step_skipped", self.engine.step_submit, step, {})
        self.assertEqual(self.progress_bytes(), before)
        self.assertEqual(self.terminal.starts, [])

    def test_a_running_ai_window_is_stopped_only_when_its_own_part_is_skipped(self):
        stops = self.terminal.stops
        self.engine._cli_step = "cold"  # a Part 1 step's window
        self.terminal.running = True
        self.engine.part_skip("part-1", True)
        self.assertEqual(self.terminal.stops, stops + 1)
        self.assertIsNone(self.engine._cli_step)
        self.engine._cli_step = "generate"  # Part 3's window stays when Part 2 is skipped
        self.engine.part_skip("part-2", True)
        self.assertEqual(self.terminal.stops, stops + 1)
        self.assertEqual(self.engine._cli_step, "generate")

    def test_resetting_lesson_progress_clears_a_skip_and_locks_the_later_parts_again(self):
        self.engine.part_skip("part-1", True)
        self.engine.reset_progress(True)
        self.assertEqual(self.engine.progress["lessons"]["skipped_parts"], [])
        self.assertEqual(self.series_row("part-1")["state"], "not_started")
        self.assertEqual(self.series_row("part-2")["state"], "locked")

    def test_the_series_view_carries_the_skip_words_for_each_part(self):
        for part_id in ("part-1", "part-2", "part-3"):
            skip = self.series_row(part_id)["skip"]
            self.assertTrue(skip["teaches"] and skip["matters"], part_id)
        self.assertNotIn("skip", self.series_row("part-4"))


class SeriesStates(LockBase):
    def test_the_active_part_is_the_one_in_progress_else_the_first_open_one(self):
        self.assertEqual(self.engine.get_state()["series"]["active_part"], "part-1")
        self.engine.lesson_complete("p1-mission")
        self.assertEqual(self.engine.get_state()["series"]["active_part"], "part-1")
        self.finish_part(PART_1)
        self.assertEqual(self.engine.get_state()["series"]["active_part"], "part-2")
        self.engine.lesson_complete("p2-mission")
        self.assertEqual(self.engine.get_state()["series"]["active_part"], "part-2")
        self.finish_part(PART_2)
        self.finish_part(PART_3)
        self.assertIsNone(self.engine.get_state()["series"]["active_part"])

    def test_counts_belong_to_open_parts_only(self):
        self.engine.lesson_complete("p1-mission")
        part_1, part_2 = self.series_row("part-1"), self.series_row("part-2")
        self.assertEqual((part_1["state"], part_1["done"], part_1["total"]), ("in_progress", 1, 9))
        self.assertEqual((part_2["state"], part_2["done"], part_2["total"]), ("locked", None, None))
        self.assertEqual({x["status"] for x in part_2["lessons"]}, {"locked"})


if __name__ == "__main__":
    unittest.main()
