"""Engine behavior for the course: gating, skipping, placement, records, migration and the CLI activities."""
from __future__ import annotations

import json
import threading
import unittest

import course_helpers as ch
import helpers
from helpers import KIT, wait_until
from course_helpers import CourseBase, DemoCourseBase
from eval_coach import lessons as L
from eval_coach import project, state as store
from eval_coach.engine import Engine
from eval_coach.state import COURSE, LESSON_IDS, STEP_IDS, CorruptStateError, new_progress, validate_progress

class Gating(CourseBase):
    def test_before_a_project_only_the_mission_is_open(self):
        course = self.state()["course"]
        self.assertEqual(course[0], {"kind": "lesson", "id": "mission", "title": "Your mission", "status": "active"})
        self.assertTrue(all(i["status"] == "locked" for i in course[1:]))
        self.assertEqual(self.current(), {"kind": "lesson", "id": "mission"})
        self.assertIsNone(self.state()["current_step"])
        self.assertEqual(self.state()["steps"][0]["status"], "locked")

    def test_the_course_lists_lessons_and_steps_in_teaching_order(self):
        self.assertEqual([(i["kind"], i["id"]) for i in self.state()["course"]], list(COURSE))
        for item in self.state()["course"]:
            self.assertTrue(item["title"])

    def test_other_lessons_need_preflight_and_a_project(self):
        # A lesson that order keeps shut cannot be read or answered, with or without setup.
        error = self.assert_code("lesson_locked", self.engine.lesson_view, "hook")
        self.assertEqual(error.message, self.engine.lesson_text["ui"]["locked_tip"])
        self.assert_code("lesson_locked", self.engine.lesson_answer, "hook", "hook-compare", {})

    def test_the_mission_finishes_before_a_project_exists_and_is_kept(self):
        self.finish("mission")
        self.assertEqual(self.status_of("mission"), "done")
        self.assertEqual(self.status_of("hook"), "active")  # the next item can be read before setup
        self.assertTrue((self.home / "pending-lessons.json").is_file())
        again = self.new_engine()
        self.assertEqual(next(i["status"] for i in again.get_state()["course"] if i["id"] == "mission"), "done")
        again.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.engine = again
        self.assertEqual(self.status_of("mission"), "done")
        self.assertEqual(self.status_of("hook"), "active")
        saved = json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["lessons"]["per_lesson"]["mission"]["status"], "done")
        self.assertEqual(saved["lessons"]["review"]["items"], {})

    def test_a_locked_lesson_is_refused_after_setup_and_nothing_changes(self):
        self.setup_project()
        before = self.paths.progress_file.read_bytes()
        self.assert_code("lesson_locked", self.engine.lesson_view, "several-runs")
        self.assert_code("lesson_locked", self.engine.lesson_answer, "several-runs", "generate-spot", {"option": "a"})
        self.assert_code("lesson_locked", self.engine.lesson_complete, "several-runs")
        self.assertEqual(self.paths.progress_file.read_bytes(), before)

    def test_a_locked_step_is_refused_when_asked_for_and_the_key_stays_sealed(self):
        self.setup_project()
        before = self.paths.progress_file.read_bytes()
        error = self.assert_code("step_locked", self.engine.get_state, step="key")
        self.assertEqual(error.message, self.engine.lesson_text["ui"]["locked_tip"])
        self.assertFalse(self.paths.key_work.exists())
        self.assertEqual(self.paths.progress_file.read_bytes(), before)

    def test_a_locked_step_is_still_refused_for_work(self):
        self.setup_project()
        before = self.paths.progress_file.read_bytes()
        self.assert_code("step_locked", self.engine.get_state, step="generate")
        self.assert_code("step_locked", self.engine.step_start, "generate")
        self.assert_code("step_locked", self.engine.step_send, "generate")
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertEqual(self.terminal.starts, [])

    def test_a_step_stays_locked_until_the_lesson_before_it_is_done(self):
        self.setup_project()
        self.finish_before("several-runs")
        self.assertEqual(self.current(), {"kind": "lesson", "id": "several-runs"})
        self.assertEqual(self.status_of("generate"), "locked")
        self.assertIsNone(self.state()["current_step"])
        error = self.assert_code("step_locked", self.engine.step_start, "generate")
        self.assertEqual(error.message, self.engine.lesson_text["ui"]["locked_tip"])
        self.assert_code("step_locked", self.engine.step_send, "generate")
        self.finish("several-runs")
        self.assertEqual(self.status_of("generate"), "active")
        self.assertEqual(self.state()["current_step"], "generate")
        self.engine.step_start("generate")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.paths.blind))

    def test_a_step_stays_locked_when_an_earlier_lesson_is_still_open(self):
        self.setup_project()
        self.finish("mission")
        self.assertEqual(self.status_of("generate"), "locked")
        self.assert_code("step_locked", self.engine.step_start, "generate")

    def test_a_skipped_lesson_also_unlocks_the_step(self):
        self.setup_project()
        self.mark_skipped("several-runs")
        self.assertEqual(self.status_of("several-runs"), "skipped")
        self.finish("mission")
        self.finish("hook")
        self.assertEqual(self.status_of("generate"), "active")

    def test_lessons_after_a_step_wait_for_that_step(self):
        self.setup_project()
        self.finish_before("generate")
        self.assertEqual(self.status_of("rules"), "locked")
        self.mark_step_done("generate")
        self.assertEqual(self.current(), {"kind": "lesson", "id": "rules"})

    def test_the_baseline_step_waits_for_its_lesson_and_for_fix(self):
        self.setup_project()
        self.finish_before("baseline-why")
        self.assertEqual(self.current(), {"kind": "lesson", "id": "baseline-why"})
        self.assertEqual(self.status_of("baseline"), "locked")
        self.assertIsNone(self.state()["current_step"])
        error = self.assert_code("step_locked", self.engine.step_start, "baseline")
        self.assertEqual(error.message, self.engine.lesson_text["ui"]["locked_tip"])
        self.assert_code("step_locked", self.engine.step_run_checker, "baseline", "baseline")
        self.finish("baseline-why")
        self.assertEqual(self.current(), {"kind": "step", "id": "baseline"})
        self.assertEqual(self.state()["current_step"], "baseline")
        self.engine.step_start("baseline")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.project))

    def test_the_baseline_step_stays_locked_while_fix_is_open(self):
        self.setup_project()
        self.finish_before("fix")
        self.assertEqual(self.current(), {"kind": "step", "id": "fix"})
        self.assertEqual(self.status_of("baseline-why"), "locked")
        self.assertEqual(self.status_of("baseline"), "locked")

    def test_the_fix_step_opens_right_after_the_run_step_with_no_lesson_between(self):
        self.assertEqual(COURSE[COURSE.index(("step", "run")) + 1], ("step", "fix"))
        self.setup_project()
        self.finish_before("run")
        self.assertEqual(self.status_of("surprise"), "done")
        self.assertEqual(self.current(), {"kind": "step", "id": "run"})
        self.assertEqual(self.status_of("fix"), "locked")
        self.mark_step_done("run")
        self.assertEqual(self.current(), {"kind": "step", "id": "fix"})
        self.assertEqual(self.state()["current_step"], "fix")

    def test_the_whole_course_opens_one_item_at_a_time_in_order(self):
        self.setup_project()
        seen = []
        while self.current() is not None:
            current = self.current()
            seen.append((current["kind"], current["id"]))
            others = [i for i in self.state()["course"] if i["status"] == "active"]
            self.assertEqual(len(others), 1)
            if current["kind"] == "lesson":
                self.finish(current["id"])
            else:
                self.mark_step_done(current["id"])
        self.assertEqual(seen, list(COURSE))
        self.assertEqual(self.engine.progress["done"], list(STEP_IDS))
        self.assertTrue(all(i["status"] == "done" for i in self.state()["course"]))

    def test_step_routes_still_need_preflight_first(self):
        self.setup_project()
        (self.home / "preflight.json").unlink()
        engine = self.new_engine()
        self.assert_code("preflight_incomplete", engine.step_start, "generate")


class Answering(CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()
        self.finish("mission")
        self.finish("hook")

    def test_a_right_answer_passes_and_a_wrong_one_does_not(self):
        activity = ch_activity(self.course, "generate-spot")
        wrong = self.answer("several-runs", "generate-spot", ch.wrong_answer(activity))
        self.assertFalse(wrong["passed"])
        view = next(a for a in wrong["lesson"]["activities"] if a["id"] == "generate-spot")
        self.assertFalse(view["passed"])
        self.assertTrue(view["result"]["feedback"])
        right = self.answer("several-runs", "generate-spot", ch.correct_answer(activity))
        self.assertTrue(right["passed"])
        self.assertTrue(next(a for a in right["lesson"]["activities"] if a["id"] == "generate-spot")["passed"])

    def test_retry_is_unlimited_and_the_first_try_is_recorded(self):
        activity = ch_activity(self.course, "generate-spot")
        for _ in range(4):
            self.assertFalse(self.answer("several-runs", "generate-spot", ch.wrong_answer(activity))["passed"])
        self.answer("several-runs", "generate-spot", ch.correct_answer(activity))
        entry = self.block()["per_lesson"]["several-runs"]["activities"]["generate-spot"]
        self.assertEqual((entry["passed"], entry["attempts"], entry["first_try"]), (True, 5, False))
        record = [r for r in self.records() if r["item"] == "generate-spot"]
        self.assertEqual(len(record), 1)
        self.assertFalse(record[0]["first_try"])

    def test_a_first_attempt_pass_is_recorded_as_such(self):
        activity = ch_activity(self.course, "generate-spot")
        self.answer("several-runs", "generate-spot", ch.correct_answer(activity))
        entry = self.block()["per_lesson"]["several-runs"]["activities"]["generate-spot"]
        self.assertTrue(entry["first_try"])

    def test_a_wrong_choice_shows_only_its_own_feedback_over_the_engine(self):
        item = ch_activity(self.course, "generate-spot")
        wrong = ch.wrong_option(item)
        view = self.answer("several-runs", "generate-spot", {"option": wrong})["lesson"]
        text = json.dumps(view)
        for option in item["options"]:
            if option["id"] != wrong:
                self.assertNotIn(option["feedback"], text)

    def test_passing_again_changes_nothing(self):
        activity = ch_activity(self.course, "generate-spot")
        self.answer("several-runs", "generate-spot", ch.correct_answer(activity))
        before = json.dumps(self.block())
        again = self.answer("several-runs", "generate-spot", ch.wrong_answer(activity))
        self.assertTrue(again["passed"])
        self.assertEqual(json.dumps(self.block()), before)

    def test_a_sort_is_graded_and_recorded(self):
        self.finish_before("surprise")
        activity = ch_activity(self.course, "compare-sort")
        wrong = self.answer("surprise", "compare-sort", ch.wrong_answer(activity))
        self.assertFalse(wrong["passed"])
        for item in activity["items"]:
            self.assertNotIn(item["feedback"], json.dumps(wrong))
        self.assertTrue(self.answer("surprise", "compare-sort", ch.correct_answer(activity))["passed"])
        self.assertEqual([r["item"] for r in self.records() if r["lesson"] == "surprise"], ["compare-sort"])

    def test_no_question_ever_stops_continue(self):
        self.assertTrue(self.engine.lesson_view("several-runs")["lesson"]["can_complete"])
        self.engine.lesson_complete("several-runs")
        self.assertEqual(self.status_of("several-runs"), "done")
        self.assertEqual([r for r in self.records() if r["lesson"] == "several-runs"], [])

    def test_a_saved_practice_blocks_but_the_lab_and_the_checks_do_not(self):
        self.finish_before("rules")
        self.assertFalse(self.engine.lesson_view("rules")["lesson"]["can_complete"])
        self.assert_code("activities_incomplete", self.engine.lesson_complete, "rules")
        self.save_practice(ch_activity(self.course, "build-try"))
        self.assertTrue(self.engine.lesson_view("rules")["lesson"]["can_complete"])
        self.engine.lesson_complete("rules")
        self.assertEqual(self.status_of("rules"), "done")
        self.assertEqual([r for r in self.records() if r["lesson"] == "rules"], [])

    def test_a_question_answered_before_continuing_is_still_recorded(self):
        self.finish_before("rules")
        self.save_practice(ch_activity(self.course, "build-try"))
        self.answer("rules", "choices-find", ch.correct_answer(ch_activity(self.course, "choices-find")))
        self.assertIn("choices-find", [r["item"] for r in self.records()])

    def test_a_saved_practice_still_blocks_even_though_its_question_does_not(self):
        self.finish_before("surprise")
        self.assertFalse(self.engine.lesson_view("surprise")["lesson"]["can_complete"])
        self.assert_code("activities_incomplete", self.engine.lesson_complete, "surprise")
        self.save_practice(ch_activity(self.course, "fix-try"))
        self.assertTrue(self.engine.lesson_view("surprise")["lesson"]["can_complete"])
        self.engine.lesson_complete("surprise")
        self.assertEqual(self.status_of("surprise"), "done")

    def test_a_finished_lesson_is_closed_but_still_viewable(self):
        self.finish("several-runs")
        self.assert_code("lesson_done", self.engine.lesson_complete, "several-runs")
        self.assert_code("lesson_done", self.engine.lesson_answer, "several-runs", "generate-spot", {"option": "a"})
        view = self.engine.lesson_view("several-runs")["lesson"]
        self.assertEqual(view["status"], "done")
        self.assertFalse(view["can_complete"])

    def test_bad_requests_get_plain_errors(self):
        self.assert_code("unknown_lesson", self.engine.lesson_view, "nope")
        self.assert_code("unknown_lesson", self.engine.lesson_view, None)
        self.assert_code("unknown_activity", self.engine.lesson_answer, "several-runs", "nope", {})
        self.assert_code("bad_answer", self.engine.lesson_answer, "several-runs", "generate-spot", {"option": "zzz"})
        self.assert_code("bad_answer", self.engine.lesson_answer, "several-runs", "generate-spot", "text")
        self.assert_code("bad_answer", self.engine.lesson_answer, "several-runs", "generate-spot", None)
        self.finish_before("rules")
        self.assert_code("bad_answer", self.engine.lesson_answer, "rules", "build-sort", {"placements": {}})

    def test_reflection_is_saved_even_when_short_and_resumes(self):
        self.finish_before("rules")
        self.assertEqual(self.status_of("rules"), "active")
        activity = ch_activity(self.course, "choices-own")
        short = self.answer("rules", "choices-own", {"text": "Only a few words."})
        self.assertFalse(short["passed"])
        again = self.new_engine()
        view = next(a for a in again.lesson_view("rules")["lesson"]["activities"] if a["id"] == "choices-own")
        self.assertEqual(view["result"]["text"], "Only a few words.")
        self.assertEqual(view["result"]["words"], 4)
        self.assertFalse(view["passed"])
        self.assertEqual(view["min_words"], activity["min_words"])
        long = " ".join(["word"] * activity["min_words"])
        self.assertTrue(self.answer("rules", "choices-own", {"text": long})["passed"])
        resumed = self.new_engine()
        view = next(a for a in resumed.lesson_view("rules")["lesson"]["activities"] if a["id"] == "choices-own")
        self.assertEqual((view["passed"], view["result"]["text"]), (True, long))

    def test_a_passed_reflection_stays_passed_when_a_shorter_one_is_saved(self):
        self.finish_before("rules")
        activity = ch_activity(self.course, "choices-own")
        long = " ".join(["word"] * activity["min_words"])
        self.assertTrue(self.answer("rules", "choices-own", {"text": long})["passed"])
        records = len(self.records())
        result = self.answer("rules", "choices-own", {"text": "too short"})
        self.assertTrue(result["passed"])
        view = next(a for a in result["lesson"]["activities"] if a["id"] == "choices-own")
        self.assertTrue(view["passed"])
        self.assertEqual(view["result"]["text"], long)
        entry = self.block()["per_lesson"]["rules"]["activities"]["choices-own"]
        self.assertEqual((entry["passed"], entry["last"]["text"], entry["attempts"]), (True, long, 1))
        self.assertEqual(len(self.records()), records)
        resumed = self.new_engine().lesson_view("rules")["lesson"]
        self.assertTrue(next(a for a in resumed["activities"] if a["id"] == "choices-own")["passed"])

    def test_a_passed_reflection_can_be_replaced_by_another_that_also_passes(self):
        self.finish_before("rules")
        activity = ch_activity(self.course, "choices-own")
        first = " ".join(["one"] * activity["min_words"])
        second = " ".join(["two"] * (activity["min_words"] + 3))
        self.answer("rules", "choices-own", {"text": first})
        self.assertTrue(self.answer("rules", "choices-own", {"text": second})["passed"])
        entry = self.block()["per_lesson"]["rules"]["activities"]["choices-own"]
        self.assertEqual(entry["last"]["text"], second)
        self.assertEqual(len([r for r in self.records() if r["item"] == "choices-own"]), 1)

    def test_progress_holds_ids_and_text_the_participant_wrote_but_no_answers(self):
        self.finish("several-runs")
        raw = (self.project / ".learning" / "progress.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        for key in ("correct", "expected", "feedback", "bucket"):
            self.assertNotIn(f'"{key}"', raw)
        for lesson in self.course.data["lessons"]:
            for item in lesson["retrieval"]:
                for option in item["options"]:
                    self.assertNotIn(option["text"], raw)
        self.assertTrue(data["lessons"]["seed"])


class Records(CourseBase):
    def test_viewing_creates_no_record_but_passing_does(self):
        self.setup_project()
        self.finish_before("several-runs")
        before = self.records()
        self.engine.lesson_view("several-runs")
        self.engine.get_state()
        self.engine.kit_file("kit:skills/build-eval-script/SKILL.md")
        self.engine.review_get()
        self.assertEqual(self.records(), before)
        activity = ch_activity(self.course, "generate-spot")
        self.answer("several-runs", "generate-spot", ch.wrong_answer(activity))
        self.assertEqual(self.records(), before)
        self.answer("several-runs", "generate-spot", ch.correct_answer(activity))
        records = self.records()
        self.assertEqual(len(records), len(before) + 1)
        self.assertEqual((records[-1]["type"], records[-1]["lesson"], records[-1]["item"], records[-1]["source"]),
                         ("activity", "several-runs", "generate-spot", "lesson"))
        self.assertEqual(records[-1]["at"], self.clock())

    def test_completing_a_lesson_adds_no_record_of_its_own(self):
        self.setup_project()
        self.finish("mission")
        self.assertEqual(self.records(), [])
        self.finish("hook")
        self.assertEqual({r["type"] for r in self.records()}, {"activity"})
        self.assertEqual(len(self.records()), len(self.lesson("hook")["activities"]))

    def test_a_view_only_session_writes_nothing_about_the_participant(self):
        self.setup_project()
        before = json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
        self.engine.lesson_view("mission")
        after = json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(before["lessons"]["records"], after["lessons"]["records"])
        self.assertEqual(after["lessons"]["records"], [])
        self.assertEqual(after["lessons"]["per_lesson"], {})


class MissionIntro(CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()

    def view(self):
        return self.engine.lesson_view("mission")["lesson"]

    def test_the_mission_is_a_plain_page_with_no_questions(self):
        view = self.view()
        self.assertEqual(view["activities"], [])
        self.assertEqual(view["placement"], [])
        self.assertEqual(self.course.data["placement"], [])
        self.assertEqual(self.lesson("mission")["retrieval"], [])

    def test_the_mission_can_be_finished_straight_away_and_schedules_no_review(self):
        self.assertTrue(self.view()["can_complete"])
        self.engine.lesson_complete("mission")
        self.assertEqual(self.status_of("mission"), "done")
        self.assertEqual(self.status_of("hook"), "active")
        self.assertEqual(self.block()["review"]["items"], {})
        self.assertEqual(self.records(), [])

    def test_only_the_mission_carries_placement(self):
        self.finish("mission")
        self.assertNotIn("placement", self.engine.lesson_view("hook")["lesson"])

    def test_the_mission_and_hook_cannot_be_skipped(self):
        self.assert_code("cannot_skip", self.engine.lesson_skip, "mission")
        self.finish("mission")
        self.assert_code("cannot_skip", self.engine.lesson_skip, "hook")


class Skipping(CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()

    def test_a_lesson_cannot_be_skipped_on_request(self):
        self.finish("mission")
        self.finish("hook")
        self.assertFalse(self.engine.lesson_view("several-runs")["lesson"]["can_skip"])
        self.assert_code("cannot_skip", self.engine.lesson_skip, "several-runs")

    def test_a_skipped_lesson_has_closed_activities_and_no_review(self):
        self.mark_skipped("several-runs")
        self.finish("mission")
        self.finish("hook")
        self.assertEqual(self.status_of("several-runs"), "skipped")
        self.assert_code("lesson_skipped", self.engine.lesson_answer, "several-runs", "generate-spot", {"option": "a"})
        self.assert_code("lesson_skipped", self.engine.lesson_complete, "several-runs")
        self.clock.advance(days=30)
        keys = [k for k in self.block()["review"]["items"]]
        self.assertFalse([k for k in keys if k.startswith("several-runs:")])

    def test_a_skipped_lesson_does_not_skip_another(self):
        self.mark_skipped("several-runs")
        self.finish("mission")
        self.finish("hook")
        self.assertEqual(self.status_of("generate"), "active")
        self.mark_step_done("generate")
        self.assertEqual(self.status_of("rules"), "active")
        self.assert_code("cannot_skip", self.engine.lesson_skip, "rules")


class Shuffles(CourseBase):
    def option_orders(self, engine):
        view = engine.lesson_view("hook")["lesson"]
        return {a["id"]: [o["id"] for o in a["options"]] for a in view["activities"] if a["type"] == "choice"}

    def participant(self, name):
        home = self.tmp / name
        helpers.write_passed_preflight(home)
        engine = helpers.make_engine(home, self.terminal, poll_interval=0.01, lessons=self.course, clock=self.clock)
        self.addCleanup(engine.shutdown)
        engine.setup({"project_path": str(self.tmp / f"{name}-project"), "cli_command": "mycli",
                      "starter": "northwind"})
        engine.lesson_complete("mission")
        return engine

    def test_the_order_is_stable_across_views_and_restarts(self):
        self.setup_project()
        self.finish("mission")
        first = self.option_orders(self.engine)
        self.assertTrue(first)
        self.assertEqual(first, self.option_orders(self.engine))
        self.assertEqual(first, self.option_orders(self.new_engine()))

    def test_the_seed_is_saved_once(self):
        self.setup_project()
        self.engine.lesson_view("mission")
        seed = self.block()["seed"]
        self.assertTrue(seed)
        self.engine.lesson_view("mission")
        self.assertEqual(self.block()["seed"], seed)
        self.assertEqual(json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
                         ["lessons"]["seed"], seed)

    def test_a_seed_chosen_before_a_project_is_kept(self):
        self.engine.lesson_view("mission")
        seed = self.block()["seed"]
        self.assertTrue(seed)
        self.setup_project()
        self.assertEqual(self.block()["seed"], seed)
        self.finish("mission")
        self.assertEqual(self.block()["seed"], seed)

    def test_different_participants_get_different_orders(self):
        mine, other = self.participant("me"), self.participant("someone-else")
        self.assertNotEqual(mine._seed(), other._seed())
        choices = [a for lesson in self.course.data["lessons"] for a in lesson["activities"] if a["type"] == "choice"]
        def orders(engine):
            return [[o["id"] for o in L.public_options(a, engine._seed(), a["id"])] for a in choices]

        self.assertNotEqual(orders(mine), orders(other))


OLD_LESSON_IDS = ("loop", "generate-why", "build-why", "choices", "verify", "compare", "fix-why")


def old_ids_progress(done):
    """Progress as the 11-lesson course wrote it: records, review items and per-lesson state for every old id."""
    data = new_progress("C:/p", "cli", "northwind")
    data["done"] = list(done)
    block = data["lessons"]
    block["seed"] = "abc"
    block["per_lesson"] = {
        "mission": {"status": "done", "activities": {}},
        "hook": {"status": "done", "activities": {"hook-explain": {"passed": True, "attempts": 1,
                                                                    "first_try": True, "last": None}}},
    }
    for old in OLD_LESSON_IDS:
        block["per_lesson"][old] = {"status": "done", "activities": {}}
    block["records"] = [
        {"type": "activity", "lesson": lesson, "item": item, "source": "lesson", "at": 1.0, "first_try": True}
        for lesson, item in (("hook", "hook-explain"), ("loop", "loop-order"), ("generate-why", "generate-spot"),
                             ("build-why", "build-sort"), ("choices", "choices-own"), ("verify", "verify-order"),
                             ("compare", "compare-exit"), ("fix-why", "fix-sort"))]
    block["review"]["items"] = {
        f"{lesson}:{item}": {"lesson": lesson, "item": item, "stage": 0, "due": 5.0, "retired": False}
        for lesson, item in (("hook", "r-hook-1"), ("loop", "r-loop-1"), ("generate-why", "r-generate-1"),
                             ("verify", "r-verify-2"), ("fix-why", "r-fix-1"))}
    return data


class MigrationState(unittest.TestCase):
    def old(self, done):
        data = new_progress("C:/p", "cli", "northwind")
        del data["lessons"]
        data["done"] = list(done)
        return data

    def test_old_progress_loads_and_keeps_completed_steps(self):
        data = validate_progress(self.old(["generate", "build"]))
        self.assertEqual(data["done"], ["generate", "build"])
        self.assertEqual(data["lessons"]["records"], [])
        self.assertEqual(data["lessons"]["review"], {"items": {}})
        self.assertIsNone(data["lessons"]["seed"])

    def test_lessons_before_the_furthest_step_are_skipped_and_marked_migrated(self):
        data = validate_progress(self.old(["generate", "build"]))
        per = data["lessons"]["per_lesson"]
        self.assertEqual(set(per), {"mission", "hook", "several-runs", "rules"})
        for entry in per.values():
            self.assertEqual((entry["status"], entry["migrated"]), ("skipped", True))
        self.assertNotIn("trust", per)

    def test_a_lesson_right_before_the_next_step_still_has_to_be_done(self):
        per = validate_progress(self.old(["generate"]))["lessons"]["per_lesson"]
        self.assertEqual(set(per), {"mission", "hook", "several-runs"})

    def test_no_progress_yet_means_nothing_to_migrate(self):
        self.assertEqual(validate_progress(self.old([]))["lessons"]["per_lesson"], {})

    def test_progress_from_before_the_baseline_step_loads_with_a_default_entry(self):
        done = [s for s in STEP_IDS if s != "baseline"]
        data = new_progress("C:/p", "cli", "northwind")
        del data["steps"]["baseline"]
        data["done"] = done
        loaded = validate_progress(data)
        self.assertEqual(loaded["done"], done)
        self.assertNotIn("baseline", loaded["done"])
        self.assertEqual(loaded["steps"]["baseline"],
                         {"run_check_hash": None, "run_runs_hash": None, "auto_started": False, "last_check": None,
                          "checklist": {}})

    def test_an_old_progress_with_no_lessons_block_and_no_baseline_entry_keeps_baseline_why_open(self):
        data = self.old([s for s in STEP_IDS if s != "baseline"])
        del data["steps"]["baseline"]
        per = validate_progress(data)["lessons"]["per_lesson"]
        self.assertNotIn("baseline-why", per)
        self.assertEqual(per["surprise"]["status"], "skipped")

    def test_the_furthest_step_counts_even_with_the_key_step_missing(self):
        data = self.old(["generate", "build", "fixtures", "readback", "predict"])
        del data["steps"]["key"]
        loaded = validate_progress(data, sealed_key_exists=False)
        self.assertEqual(loaded["done"], ["generate", "build", "fixtures", "readback", "predict"])
        self.assertIn("rules", loaded["lessons"]["per_lesson"])
        self.assertIn("trust", loaded["lessons"]["per_lesson"])
        self.assertNotIn("surprise", loaded["lessons"]["per_lesson"])

    def test_current_progress_is_left_alone(self):
        data = new_progress("C:/p", "cli", "northwind")
        data["lessons"]["seed"] = "abc"
        data["lessons"]["per_lesson"]["mission"] = {"status": "done", "activities": {}}
        self.assertEqual(validate_progress(data)["lessons"]["per_lesson"],
                         {"mission": {"status": "done", "activities": {}}})

    def test_a_partial_lessons_block_is_filled_in(self):
        data = new_progress("C:/p", "cli", "northwind")
        data["lessons"] = {"seed": "abc"}
        loaded = validate_progress(data)
        self.assertEqual(loaded["lessons"]["seed"], "abc")
        self.assertEqual(loaded["lessons"]["records"], [])
        self.assertEqual(loaded["lessons"]["review"], {"items": {}})

    def test_a_wrong_shape_is_reported_as_corrupt(self):
        data = new_progress("C:/p", "cli", "northwind")
        data["lessons"] = []
        with self.assertRaises(CorruptStateError):
            validate_progress(data)

    def test_new_progress_carries_an_empty_lessons_block(self):
        block = new_progress("C:/p", "cli", "northwind")["lessons"]
        self.assertEqual(block, {"seed": None, "per_lesson": {}, "placement": {}, "records": [],
                                 "review": {"items": {}}, "step_checks": {}, "skipped_parts": []})

    def test_the_course_order_matches_the_lessons_the_content_must_define(self):
        self.assertEqual(LESSON_IDS, ("mission", "hook", "several-runs", "rules", "trust", "surprise", "baseline-why"))
        self.assertEqual([i for k, i in COURSE if k == "step"], list(STEP_IDS))

    def test_progress_written_with_the_old_lesson_ids_loads_and_keeps_the_steps(self):
        data = validate_progress(old_ids_progress(["generate", "build"]))
        self.assertEqual(data["done"], ["generate", "build"])
        block = data["lessons"]
        self.assertEqual(block["seed"], "abc")
        for old in OLD_LESSON_IDS:
            self.assertNotIn(old, block["per_lesson"])
        self.assertEqual([(r["lesson"], r["item"]) for r in block["records"]], [("hook", "hook-explain")])
        self.assertEqual(list(block["review"]["items"]), ["hook:r-hook-1"])

    def test_kept_lessons_stay_and_new_lessons_before_the_furthest_step_are_skipped_and_migrated(self):
        per = validate_progress(old_ids_progress(["generate", "build"]))["lessons"]["per_lesson"]
        self.assertEqual(set(per), {"mission", "hook", "several-runs", "rules"})
        self.assertEqual(per["mission"], {"status": "done", "activities": {}})
        self.assertTrue(per["hook"]["activities"]["hook-explain"]["passed"])
        for lesson in ("several-runs", "rules"):
            self.assertEqual(per[lesson], {"status": "skipped", "migrated": True, "activities": {}})

    def test_old_ids_with_no_steps_done_leave_no_new_lesson_skipped(self):
        per = validate_progress(old_ids_progress([]))["lessons"]["per_lesson"]
        self.assertEqual(set(per), {"mission", "hook"})

    def test_migrated_progress_is_not_migrated_again(self):
        once = validate_progress(old_ids_progress(["generate", "build"]))
        self.assertEqual(validate_progress(json.loads(json.dumps(once))), once)


class MigrationEngine(CourseBase):
    def write_old_progress(self, done):
        self.engine_without_lessons = Engine(self.home, self.terminal, poll_interval=0.01)
        self.addCleanup(self.engine_without_lessons.shutdown)
        self.engine_without_lessons.setup({"project_path": str(self.project), "cli_command": "mycli",
                                           "starter": "northwind"})
        path = self.project / ".learning" / "progress.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        del data["lessons"]
        data["done"] = list(done)
        path.write_text(json.dumps(data), encoding="utf-8")
        self.paths = project.Paths(self.home, self.project)

    def test_an_engine_with_the_course_resumes_old_progress(self):
        self.write_old_progress(["generate", "build"])
        engine = self.new_engine()
        state = engine.get_state()
        self.assertEqual(state["current_item"], {"kind": "lesson", "id": "trust"})
        self.assertEqual([s["status"] for s in state["steps"][:3]], ["done", "done", "locked"])
        statuses = {i["id"]: i["status"] for i in state["course"]}
        for lesson in ("mission", "hook", "several-runs", "rules"):
            self.assertEqual(statuses[lesson], "skipped")
        self.assertEqual(state["review"], {"due": 0, "postponed": False})
        self.assertEqual(engine._lessons_block()["review"]["items"], {})
        self.assertEqual(engine.progress["done"], ["generate", "build"])

    def test_migrated_lessons_schedule_no_reviews_even_after_a_long_time(self):
        self.write_old_progress(["generate", "build"])
        engine = self.new_engine()
        self.clock.advance(days=60)
        self.assertEqual(engine.review_get()["review"]["items"], [])

    def test_the_rest_of_the_course_still_works_after_migration(self):
        self.write_old_progress(["generate", "build"])
        self.engine = self.new_engine()
        self.finish("trust")
        self.assertEqual(self.state()["current_step"], "fixtures")
        self.assertEqual(len(self.engine._lessons_block()["review"]["items"]), len(self.lesson("trust")["retrieval"]))

    def test_old_progress_with_no_steps_done_starts_at_the_mission(self):
        self.write_old_progress([])
        engine = self.new_engine()
        self.assertEqual(engine.get_state()["current_item"], {"kind": "lesson", "id": "mission"})

    def test_the_migrated_progress_is_saved_with_the_new_block_on_the_next_write(self):
        self.write_old_progress(["generate"])
        self.engine = self.new_engine()
        self.finish("rules")
        saved = json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["done"], ["generate"])
        self.assertEqual(saved["lessons"]["per_lesson"]["hook"]["status"], "skipped")
        self.assertEqual(saved["lessons"]["per_lesson"]["rules"]["status"], "done")

    def write_old_ids_progress(self, done):
        self.write_old_progress(done)
        path = self.project / ".learning" / "progress.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["lessons"] = old_ids_progress(done)["lessons"]
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_progress_saved_with_the_old_lesson_ids_opens_and_keeps_the_steps(self):
        self.write_old_ids_progress(["generate", "build"])
        engine = self.new_engine()
        state = engine.get_state()
        self.assertEqual(engine.progress["done"], ["generate", "build"])
        self.assertEqual([s["status"] for s in state["steps"][:3]], ["done", "done", "locked"])
        self.assertEqual(state["current_item"], {"kind": "lesson", "id": "trust"})
        statuses = {i["id"]: i["status"] for i in state["course"]}
        self.assertEqual((statuses["mission"], statuses["hook"]), ("done", "done"))
        self.assertEqual((statuses["several-runs"], statuses["rules"]), ("skipped", "skipped"))
        block = engine._lessons_block()
        self.assertEqual(set(block["per_lesson"]), {"mission", "hook", "several-runs", "rules"})
        self.assertTrue(block["per_lesson"]["several-runs"]["migrated"] and block["per_lesson"]["rules"]["migrated"])
        self.assertEqual({r["lesson"] for r in block["records"]}, {"hook"})
        self.assertEqual(list(block["review"]["items"]), ["hook:r-hook-1"])

    def test_the_old_ids_are_gone_from_the_file_after_the_next_save(self):
        self.write_old_ids_progress(["generate", "build"])
        self.engine = self.new_engine()
        self.finish("trust")
        saved = json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
        text = json.dumps(saved["lessons"])
        for old in OLD_LESSON_IDS:
            self.assertNotIn(f'"{old}"', text)
        self.assertEqual(saved["done"], ["generate", "build"])

    def test_a_pending_file_with_only_the_mission_merges_into_a_new_project(self):
        self.finish("mission")
        pending = json.loads((self.home / "pending-lessons.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pending["per_lesson"]), {"mission"})
        engine = self.new_engine()
        engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.engine = engine
        self.assertEqual(self.status_of("mission"), "done")
        self.assertEqual(self.status_of("hook"), "active")
        self.assertEqual(set(self.block()["per_lesson"]), {"mission"})

    def test_a_pending_file_that_names_an_old_lesson_loses_that_lesson(self):
        self.finish("mission")
        path = self.home / "pending-lessons.json"
        pending = json.loads(path.read_text(encoding="utf-8"))
        pending["per_lesson"]["loop"] = {"status": "done", "activities": {}}
        pending["records"].append({"type": "activity", "lesson": "loop", "item": "loop-order", "source": "lesson",
                                   "at": 1.0, "first_try": True})
        pending["review"]["items"]["loop:r-loop-1"] = {"lesson": "loop", "item": "r-loop-1", "stage": 0, "due": 5.0,
                                                       "retired": False}
        path.write_text(json.dumps(pending), encoding="utf-8")
        engine = self.new_engine()
        self.assertEqual(next(i["status"] for i in engine.get_state()["course"] if i["id"] == "mission"), "done")
        engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        saved = json.loads((self.project / ".learning" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(set(saved["lessons"]["per_lesson"]), {"mission"})
        self.assertEqual(saved["lessons"]["per_lesson"]["mission"]["status"], "done")
        self.assertEqual(saved["lessons"]["records"], [])
        self.assertEqual(saved["lessons"]["review"]["items"], {})


class NoCourse(CourseBase):
    """An engine built without lessons keeps every step test working unchanged."""

    def setUp(self):
        super().setUp()
        self.engine = self.new_engine(lessons=False)
        self.setup_project()

    def test_steps_open_as_before(self):
        state = self.state()
        self.assertEqual(state["current_step"], "generate")
        self.assertEqual(state["current_item"], {"kind": "step", "id": "generate"})
        self.assertEqual([(i["kind"], i["id"]) for i in state["course"]], [("step", s) for s in STEP_IDS])
        self.engine.step_start("generate")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.paths.blind))

    def test_steps_unlock_one_after_another(self):
        self.mark_step_done("generate")
        self.assertEqual(self.state()["current_step"], "build")

    def test_lesson_routes_report_that_there_is_no_course(self):
        self.assert_code("no_lessons", self.engine.lesson_view, "mission")
        self.assert_code("no_lessons", self.engine.lesson_answer, "mission", "x", {})
        self.assert_code("no_lessons", self.engine.lesson_complete, "mission")
        self.assert_code("no_lessons", self.engine.lesson_skip, "mission")
        self.assert_code("no_lessons", self.engine.placement_answer, "p", "a")
        self.assert_code("no_lessons", self.engine.review_get)
        self.assert_code("no_lessons", self.engine.review_answer, "x", "a")
        self.assert_code("no_lessons", self.engine.review_postpone)
        self.assert_code("no_lessons", self.engine.lesson_cli_start, "hook", "hook-compare")

    def test_review_summary_is_empty(self):
        self.assertEqual(self.state()["review"], {"due": 0, "postponed": False})

    def test_the_kit_viewer_needs_no_course(self):
        self.assertIn("build-eval-script", self.engine.kit_file("kit:skills/build-eval-script/SKILL.md")["kit"]["text"])


class KitViewer(CourseBase):
    def test_reads_a_bundled_file_as_text(self):
        kit = self.engine.kit_file("kit:lessons/hook/requirements.md")["kit"]
        self.assertEqual(kit["ref"], "kit:lessons/hook/requirements.md")
        self.assertEqual(kit["name"], "requirements.md")
        self.assertEqual(kit["text"], (KIT / "lessons" / "hook" / "requirements.md").read_text(encoding="utf-8"))

    def test_refuses_anything_outside_the_kit_and_the_answer_key(self):
        for ref in ("kit:../engine.py", "kit:../../tests/helpers.py", "kit:/etc/passwd", "kit:C:\\Windows\\win.ini",
                    "kit:northwind/answer-key.md", "kit:northwind/ANSWER-KEY.md", "kit:", "kit:northwind",
                    "https://example.com/x", "", None, 3, "content/steps.json", "kit:content/steps.json"):
            with self.subTest(ref=ref):
                error = self.assert_code("bad_ref", self.engine.kit_file, ref)
                self.assertEqual(error.message, "That file could not be opened.")

    def test_every_bundled_source_opens(self):
        for lesson in self.course.data["lessons"]:
            for source in lesson["sources"] + [lesson["primary_source"]]:
                if "sample-r" in source["ref"]:
                    continue  # the Part 1 sample prompts open only after the rescore step (test_part_1_steps)
                with self.subTest(lesson=lesson["id"], ref=source["ref"]):
                    self.assertTrue(self.engine.kit_file(source["ref"])["kit"]["text"].strip())


class CliActivities(CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()
        self.finish("mission")

    def activity(self, lesson, activity_id):
        return ch_activity(self.course, activity_id)

    def run_once(self, n, text):
        self.engine.lesson_cli_start("hook", "hook-compare")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.paths.hook_work))
        self.assertTrue(self.terminal.running)
        self.engine.lesson_cli_send("hook", "hook-compare")
        self.paths.hook_output.write_text(text, encoding="utf-8")
        self.assertTrue(wait_until(lambda: self.paths.hook_run_file(n).is_file()), f"run {n} never saved")
        self.assertTrue(wait_until(lambda: not self.terminal.running))

    def test_the_hook_folder_holds_only_the_update_and_its_requirements(self):
        self.engine.lesson_cli_start("hook", "hook-compare")
        self.assertEqual(sorted(p.name for p in self.paths.hook_work.iterdir()), ["requirements.md", "update.txt"])
        self.assertEqual((self.paths.hook_work / "update.txt").read_bytes(),
                         (KIT / "northwind" / "fixture-polished-but-wrong.txt").read_bytes())
        self.assertEqual((self.paths.hook_work / "requirements.md").read_bytes(),
                         (KIT / "lessons" / "hook" / "requirements.md").read_bytes())
        self.assertIn("Hook", self.terminal.starts[-1]["label"] + "Hook")

    def test_the_hook_types_the_exact_line(self):
        self.engine.lesson_cli_start("hook", "hook-compare")
        self.engine.lesson_cli_send("hook", "hook-compare")
        self.assertEqual(self.terminal.typed, [L.HOOK_LINE])

    def test_three_runs_are_saved_and_shown_side_by_side_as_plain_text(self):
        for n in (1, 2, 3):
            self.run_once(n, f"Score {n}/10. <b>fail</b> because of reason {n}.")
        view = self.engine.lesson_view("hook")["lesson"]["activities"][0]
        self.assertTrue(view["all_saved"])
        self.assertEqual([o["n"] for o in view["outputs"]], [1, 2, 3])
        self.assertEqual(view["outputs"][1]["text"], "Score 2/10. <b>fail</b> because of reason 2.")
        for n in (1, 2, 3):
            self.assertEqual(self.paths.hook_run_file(n).read_text(encoding="utf-8"),
                             f"Score {n}/10. <b>fail</b> because of reason {n}.")
        self.assertEqual(self.paths.hook_run_file(1).parent, self.project / ".learning" / "hook")

    def test_each_run_starts_clean_and_a_fourth_is_refused(self):
        self.run_once(1, "first")
        self.engine.lesson_cli_start("hook", "hook-compare")
        self.assertFalse(self.paths.hook_output.exists())
        self.assertEqual(sorted(p.name for p in self.paths.hook_work.iterdir()), ["requirements.md", "update.txt"])
        self.engine.lesson_cli_stop("hook", "hook-compare")
        self.assertFalse(self.terminal.running)
        self.run_once(2, "second")
        self.run_once(3, "third")
        self.assert_code("runs_complete", self.engine.lesson_cli_start, "hook", "hook-compare")

    def test_the_question_waits_for_all_three_runs(self):
        activity = self.activity("hook", "hook-compare")
        self.assert_code("runs_missing", self.answer, "hook", "hook-compare", ch.correct_answer(activity))
        self.run_once(1, "one")
        self.assert_code("runs_missing", self.answer, "hook", "hook-compare", ch.correct_answer(activity))
        self.run_once(2, "two")
        self.run_once(3, "three")
        self.assertFalse(self.answer("hook", "hook-compare", ch.wrong_answer(activity))["passed"])
        self.assertTrue(self.answer("hook", "hook-compare", ch.correct_answer(activity))["passed"])
        self.engine.lesson_complete("hook")
        self.assertEqual(self.status_of("hook"), "done")

    def test_the_lesson_cannot_complete_if_a_saved_run_goes_missing(self):
        activity = self.activity("hook", "hook-compare")
        self.pass_activity("hook", activity)
        self.paths.hook_run_file(2).unlink()
        self.assert_code("activities_incomplete", self.engine.lesson_complete, "hook")

    def test_the_terminal_belongs_to_the_activity_that_started_it_until_it_is_released(self):
        self.assertIsNone(self.state()["terminal"]["owner"])
        self.engine.lesson_cli_start("hook", "hook-compare")
        self.assertEqual(self.state()["terminal"]["owner"], "lesson:hook:hook-compare")
        self.assertTrue(self.state()["terminal"]["running"])
        self.engine.terminal_release()
        status = self.state()["terminal"]
        self.assertEqual((status["running"], status["owner"], status["label"], status["exit_code"]),
                         (False, None, "", None))
        self.assertEqual(self.terminal.releases, 1)
        self.assertFalse(self.engine._cli_active("lesson:hook:hook-compare"))

    def test_releasing_with_nothing_running_is_harmless(self):
        self.engine.terminal_release()
        self.assertEqual(self.state()["terminal"]["owner"], None)

    def test_send_and_stop_need_a_running_cli(self):
        self.assert_code("cli_not_running", self.engine.lesson_cli_send, "hook", "hook-compare")
        stops = self.terminal.stops
        self.engine.lesson_cli_stop("hook", "hook-compare")
        self.assertEqual(self.terminal.stops, stops)

    def test_cli_routes_refuse_other_activities_and_locked_lessons(self):
        self.finish("hook")
        self.assert_code("not_cli", self.engine.lesson_cli_start, "several-runs", "generate-spot")
        self.assert_code("unknown_activity", self.engine.lesson_cli_start, "several-runs", "nope")
        self.assert_code("lesson_locked", self.engine.lesson_cli_start, "rules", "build-try")


class CliDemo(DemoCourseBase):
    """The cli_demo path. The bundled course has no demo activity, so one is injected into `rules` (see demo_course)."""

    def setUp(self):
        super().setUp()
        self.setup_project()
        self.finish("mission")

    def test_the_demo_folder_holds_exactly_three_files_and_types_the_exact_line(self):
        self.finish_before("rules")
        self.engine.lesson_cli_start("rules", "rules-demo")
        names = sorted(p.relative_to(self.paths.demo_work).as_posix() for p in self.paths.demo_work.rglob("*")
                       if p.is_file())
        self.assertEqual(names, ["output.txt", "skills/build-eval-script/SKILL.md", "test-cases.md"])
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.paths.demo_work))
        self.engine.lesson_cli_send("rules", "rules-demo")
        self.assertEqual(self.terminal.typed, [L.DEMO_LINE])
        for name, source in (("test-cases.md", "lessons/demo/test-cases.md"), ("output.txt", "lessons/demo/output.txt")):
            self.assertEqual((self.paths.demo_work / name).read_bytes(), (KIT / source).read_bytes())
        self.assertEqual((self.paths.demo_work / "skills" / "build-eval-script" / "SKILL.md").read_bytes(),
                         (KIT / "skills" / "build-eval-script" / "SKILL.md").read_bytes())

    def test_a_finished_demo_cannot_be_started_again(self):
        self.finish_before("rules")
        self.write_demo_checker()
        self.answer("rules", "rules-demo", {})
        self.assert_code("activity_done", self.engine.lesson_cli_start, "rules", "rules-demo")

    def test_starting_the_demo_clears_an_old_checker_and_old_results(self):
        self.finish_before("rules")
        self.write_demo_checker("raise SystemExit(5)\n")
        self.answer("rules", "rules-demo", {})
        self.assertTrue((self.home / "results" / "demo-1.json").exists() or self.engine._load_result("demo-1"))
        self.engine.lesson_cli_start("rules", "rules-demo")
        self.assertFalse(self.paths.demo_check.exists())
        self.assertIsNone(self.engine._load_result("demo-1"))
        self.assertIsNone(self.engine._load_result("demo-2"))

    def test_the_demo_needs_a_checker_first(self):
        self.finish_before("rules")
        self.engine.lesson_cli_start("rules", "rules-demo")
        self.assert_code("no_checker", self.answer, "rules", "rules-demo", {})
        self.assertFalse(self._demo_view()["checker_exists"])

    def _demo_view(self):
        return next(a for a in self.engine.lesson_view("rules")["lesson"]["activities"] if a["id"] == "rules-demo")

    def test_a_checker_that_calls_the_network_is_refused(self):
        self.finish_before("rules")
        self.write_demo_checker("import urllib.request\nprint('== output.txt')\n")
        error = self.assert_code("scan_failed", self.answer, "rules", "rules-demo", {})
        self.assertTrue(error.message)
        self.assertTrue(self._demo_view()["scan"])

    def test_a_missing_demo_file_is_reported(self):
        self.finish_before("rules")
        self.write_demo_checker()
        (self.paths.demo_work / "output.txt").unlink()
        error = self.assert_code("missing_file", self.answer, "rules", "rules-demo", {})
        self.assertIn("output.txt", error.message)

    def test_two_identical_runs_pass_and_both_lists_are_shown(self):
        self.finish_before("rules")
        self.write_demo_checker()
        result = self.answer("rules", "rules-demo", {})
        self.assertTrue(result["passed"])
        view = next(a for a in result["lesson"]["activities"] if a["id"] == "rules-demo")
        self.assertTrue(view["passed"])
        self.assertTrue(view["identical"])
        self.assertTrue(view["checker_exists"])
        self.assertEqual(len(view["runs"]), 2)
        self.assertEqual(view["runs"][0]["files"], view["runs"][1]["files"])
        self.assertEqual([r["verdict"] for r in view["runs"][0]["files"][0]["rows"]], ["P"] * 6)
        self.assertEqual(self.engine.progress["lessons"]["per_lesson"]["rules"]["activities"]["rules-demo"]["passed"], True)

    def test_the_same_file_gives_the_same_verdict_twice_for_every_checker_run(self):
        self.finish_before("rules")
        self.write_demo_checker()
        first = self.answer("rules", "rules-demo", {})
        again = self.answer("rules", "rules-demo", {})
        self.assertTrue(first["passed"] and again["passed"])
        runs = next(a for a in again["lesson"]["activities"] if a["id"] == "rules-demo")["runs"]
        self.assertEqual(runs[0]["files"], runs[1]["files"])

    def test_verdicts_that_differ_between_the_two_runs_do_not_pass(self):
        self.finish_before("rules")
        flaky = ("import os\n"
                 "n = int(open('count.txt').read()) if os.path.exists('count.txt') else 0\n"
                 "open('count.txt', 'w').write(str(n + 1))\n"
                 "print('== output.txt')\n"
                 "print('C1 ' + ('PASS' if n == 0 else 'FAIL') + '  Length: x')\n"
                 "print('-> 1/1 criteria passed')\n")
        self.write_demo_checker(flaky)
        result = self.answer("rules", "rules-demo", {})
        self.assertFalse(result["passed"])
        view = next(a for a in result["lesson"]["activities"] if a["id"] == "rules-demo")
        self.assertFalse(view["passed"])
        self.assertIs(view["identical"], False)
        self.assertFalse([r for r in self.records() if r["item"] == "rules-demo"])

    def test_a_checker_that_crashes_is_not_a_pass(self):
        self.finish_before("rules")
        self.write_demo_checker("raise SystemExit(5)\n")
        result = self.answer("rules", "rules-demo", {})
        self.assertFalse(result["passed"])

    def test_the_demo_pass_is_recorded_once(self):
        self.finish_before("rules")
        self.write_demo_checker()
        self.answer("rules", "rules-demo", {})
        self.answer("rules", "rules-demo", {})
        self.assertEqual(len([r for r in self.records() if r["item"] == "rules-demo"]), 1)

    def test_the_rules_lesson_completes_with_the_demo_and_the_practice_and_needs_no_lab(self):
        self.finish_before("rules")
        self.assert_code("activities_incomplete", self.engine.lesson_complete, "rules")
        self.write_demo_checker()
        self.answer("rules", "rules-demo", {})
        self.assert_code("activities_incomplete", self.engine.lesson_complete, "rules")
        self.save_practice(ch_activity(self.course, "build-try"))
        self.engine.lesson_complete("rules")
        self.assertEqual(self.status_of("rules"), "done")

    def test_the_demo_blocks_until_it_passes(self):
        self.finish_before("rules")
        self.save_practice(ch_activity(self.course, "build-try"))
        self.assertFalse(self.engine.lesson_view("rules")["lesson"]["can_complete"])
        self.pass_activity("rules", ch_activity(self.course, "rules-demo"))
        self.assertTrue(self.engine.lesson_view("rules")["lesson"]["can_complete"])
        self.assertEqual([r["item"] for r in self.records() if r["lesson"] == "rules"], ["rules-demo"])

    def test_no_real_cli_is_involved(self):
        self.finish_before("rules")
        self.engine.lesson_cli_start("rules", "rules-demo")
        self.assertEqual(self.terminal.starts[-1]["command"], "mycli")
        self.assertEqual(len(self.terminal.starts), 1)


class StepQuestions(CourseBase):
    """The question on a finished step's page: shown after the step, answered freely, never a gate."""

    def setUp(self):
        super().setUp()
        self.setup_project()

    def question(self, step="generate"):
        return self.engine.get_state(step)["step"]["question"]

    def test_the_question_waits_for_the_step_to_be_done(self):
        self.assert_code("step_locked", self.engine.get_state, "generate")
        self.assert_code("step_question_locked", self.engine.step_question_answer, "generate", "a")
        self.mark_step_done("generate")
        view = self.question()
        self.assertEqual(view["id"], "sc-generate")
        self.assertFalse(view["passed"])
        self.assertIsNone(view["result"])

    def test_the_view_never_carries_the_answer(self):
        self.mark_step_done("generate")
        text = json.dumps(self.question())
        for word in ("correct", "feedback", "explanations"):
            self.assertNotIn(word, text)
        self.assertEqual(sorted(o["id"] for o in self.question()["options"]), ["a", "b", "c", "d"])

    def test_a_wrong_answer_explains_only_that_option_and_can_be_retried(self):
        self.mark_step_done("generate")
        item = self.course.step_checks["generate"]
        outcome = self.engine.step_question_answer("generate", ch.wrong_option(item))
        self.assertFalse(outcome["passed"])
        result = outcome["question"]["result"]
        self.assertFalse(result["passed"])
        self.assertNotIn("explanations", result)
        self.assertEqual(self.records(), [])
        again = self.engine.step_question_answer("generate", ch.correct_option(item))
        self.assertTrue(again["passed"])
        self.assertEqual(len(again["question"]["result"]["explanations"]), 4)

    def test_a_pass_is_recorded_once_and_then_closed(self):
        self.mark_step_done("generate")
        item = self.course.step_checks["generate"]
        self.engine.step_question_answer("generate", ch.correct_option(item))
        self.engine.step_question_answer("generate", ch.wrong_option(item))
        self.engine.step_question_answer("generate", ch.correct_option(item))
        records = [r for r in self.records() if r["item"] == "sc-generate"]
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0]["lesson"], records[0]["source"], records[0]["first_try"]), ("generate", "step", True))
        self.assertTrue(self.question()["passed"])

    def test_the_answer_survives_a_restart(self):
        self.mark_step_done("generate")
        item = self.course.step_checks["generate"]
        self.engine.step_question_answer("generate", ch.correct_option(item))
        again = self.new_engine()
        self.assertTrue(again.get_state("generate")["step"]["question"]["passed"])

    def test_the_order_of_the_options_is_stable(self):
        self.mark_step_done("generate")
        first = [o["id"] for o in self.question()["options"]]
        self.assertEqual(first, [o["id"] for o in self.question()["options"]])

    def test_a_bad_request_gets_a_plain_error(self):
        self.mark_step_done("generate")
        self.assert_code("bad_answer", self.engine.step_question_answer, "generate", "zzz")
        self.assert_code("bad_answer", self.engine.step_question_answer, "generate", None)
        self.assert_code("unknown_step", self.engine.step_question_answer, "nope", "a")

    def test_an_unanswered_question_never_holds_anything_back(self):
        self.finish_before("generate")
        self.mark_step_done("generate")
        self.assertIsNone(self.question()["result"])
        self.assertEqual(self.status_of("rules"), "active")

    def test_every_step_with_a_question_shows_it_once_done(self):
        for step in STEP_IDS:
            self.mark_step_done(step)
            self.assertEqual(self.question(step)["id"], f"sc-{step}")

    def test_an_engine_without_a_course_has_no_question(self):
        engine = self.new_engine(lessons=False)
        engine.setup({"project_path": str(self.tmp / "other"), "cli_command": "mycli", "starter": "northwind"})
        self.assert_code("no_step_question", engine.step_question_answer, "generate", "a")


class CliPractice(CourseBase):
    """The reading lessons that mention the CLI each have a short hands-on run with the same Start and Send panel."""

    PRACTICE = {"rules": "build-try", "surprise": "fix-try"}

    def setUp(self):
        super().setUp()
        self.setup_project()

    def open_lesson(self, lesson_id):
        self.finish_before(lesson_id)
        return ch_activity(self.course, self.PRACTICE[lesson_id])

    def save_by_cli(self, activity, text="Saved by the CLI."):
        work = self.paths.practice_work(activity["id"])
        (work / "output.txt").write_text(text, encoding="utf-8")
        self.assertTrue(wait_until(lambda: self.paths.practice_output(activity["id"]).is_file()), "never saved")
        self.assertTrue(wait_until(lambda: not self.terminal.running))

    def test_every_lesson_that_mentions_running_the_cli_has_a_practice(self):
        for lesson_id, activity_id in self.PRACTICE.items():
            with self.subTest(lesson=lesson_id):
                kinds = {a["id"]: a["type"] for a in self.lesson(lesson_id)["activities"]}
                self.assertEqual(kinds[activity_id], "cli_practice")

    def test_the_practice_folder_holds_only_the_lessons_files_and_types_the_exact_line(self):
        for lesson_id in self.PRACTICE:
            with self.subTest(lesson=lesson_id):
                activity = self.open_lesson(lesson_id)
                self.engine.lesson_cli_start(lesson_id, activity["id"])
                work = self.paths.practice_work(activity["id"])
                names = sorted(p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file())
                self.assertEqual(names, sorted(f["name"] for f in activity["files"]))
                self.assertEqual(self.terminal.starts[-1]["cwd"], str(work))
                self.engine.lesson_cli_send(lesson_id, activity["id"])
                self.assertEqual(self.terminal.typed[-1], activity["line"])
                self.engine.lesson_cli_stop(lesson_id, activity["id"])

    def test_the_practice_folders_never_hold_an_answer_key_or_the_participants_files(self):
        for activity_id in self.PRACTICE.values():
            activity = ch_activity(self.course, activity_id)
            for entry in activity["files"]:
                self.assertNotIn("answer-key", entry["source"])
                self.assertTrue(entry["source"].startswith("kit:"))

    def test_the_answer_is_saved_into_the_project_and_the_cli_stops(self):
        activity = self.open_lesson("rules")
        self.engine.lesson_cli_start("rules", activity["id"])
        self.engine.lesson_cli_send("rules", activity["id"])
        self.save_by_cli(activity, "Mon to Fri <b>update</b>")
        view = next(a for a in self.engine.lesson_view("rules")["lesson"]["activities"] if a["id"] == activity["id"])
        self.assertTrue(view["all_saved"])
        self.assertEqual(view["outputs"][0]["text"], "Mon to Fri <b>update</b>")
        self.assertEqual(self.paths.practice_output(activity["id"]).parent, self.project / ".learning" / "practice")
        self.assert_code("runs_complete", self.engine.lesson_cli_start, "rules", activity["id"])

    def test_the_question_waits_for_the_saved_answer(self):
        activity = self.open_lesson("rules")
        self.assert_code("practice_missing", self.answer, "rules", activity["id"], ch.correct_answer(activity))
        self.engine.lesson_cli_start("rules", activity["id"])
        self.save_by_cli(activity)
        self.assertFalse(self.answer("rules", activity["id"], ch.wrong_answer(activity))["passed"])
        self.assertTrue(self.answer("rules", activity["id"], ch.correct_answer(activity))["passed"])

    def test_the_lesson_cannot_complete_without_the_run(self):
        activity = self.open_lesson("surprise")
        for other in self.lesson("surprise")["activities"]:
            if other["id"] != activity["id"]:
                self.answer("surprise", other["id"], ch.correct_answer(other))
        self.assert_code("activities_incomplete", self.engine.lesson_complete, "surprise")
        self.pass_activity("surprise", activity)
        self.engine.lesson_complete("surprise")
        self.assertEqual(self.status_of("surprise"), "done")

    def test_the_question_is_hidden_from_a_failed_answer(self):
        activity = self.open_lesson("surprise")
        self.save_practice(activity)
        self.answer("surprise", activity["id"], ch.wrong_answer(activity))
        view = next(a for a in self.engine.lesson_view("surprise")["lesson"]["activities"] if a["id"] == activity["id"])
        self.assertNotIn("explanations", view["question"]["result"])


class OrderActivity(DemoCourseBase):
    """The order path. The bundled course has no order activity, so one is injected into `several-runs`."""

    def setUp(self):
        super().setUp()
        self.setup_project()
        self.finish("mission")
        self.finish("hook")
        self.activity = ch_activity(self.course, "loop-order")

    def test_a_right_answer_passes_and_a_wrong_one_does_not(self):
        wrong = self.answer("several-runs", "loop-order", ch.wrong_answer(self.activity))
        self.assertFalse(wrong["passed"])
        view = next(a for a in wrong["lesson"]["activities"] if a["id"] == "loop-order")
        self.assertFalse(view["passed"])
        self.assertEqual(view["result"]["feedback"], self.activity["feedback_wrong"])
        right = self.answer("several-runs", "loop-order", ch.correct_answer(self.activity))
        self.assertTrue(right["passed"])
        self.assertTrue(next(a for a in right["lesson"]["activities"] if a["id"] == "loop-order")["passed"])

    def test_a_first_attempt_pass_is_recorded_and_passing_again_changes_nothing(self):
        self.answer("several-runs", "loop-order", ch.correct_answer(self.activity))
        entry = self.block()["per_lesson"]["several-runs"]["activities"]["loop-order"]
        self.assertTrue(entry["first_try"])
        before = json.dumps(self.block())
        self.assertTrue(self.answer("several-runs", "loop-order", ch.wrong_answer(self.activity))["passed"])
        self.assertEqual(json.dumps(self.block()), before)

    def test_an_order_never_stops_continue(self):
        self.assertTrue(self.engine.lesson_view("several-runs")["lesson"]["can_complete"])

    def test_bad_orders_get_plain_errors(self):
        self.assert_code("bad_answer", self.engine.lesson_answer, "several-runs", "loop-order", {"order": ["prompt"]})
        self.assert_code("bad_answer", self.engine.lesson_answer, "several-runs", "loop-order", "text")
        self.assert_code("bad_answer", self.engine.lesson_answer, "several-runs", "loop-order", None)


class RuleLab(CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()
        self.finish_before("rules")
        self.lab = ch_activity(self.course, "rules-lab")

    def run_rule(self, rule, text):
        return self.engine.lesson_rule_run("rules", "rules-lab", rule, text)

    def test_your_own_text_gets_a_verdict_and_a_reason(self):
        result = self.run_rule("r-length", "just a few words here")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["reason"], "5 words (limit: under 20)")
        result = self.run_rule("r-labels", "Blocker: x only")
        self.assertEqual((result["verdict"], result["reason"]), ("fail", "Missing labels: Need:"))

    def test_the_same_input_gives_the_same_verdict_every_time(self):
        results = {json.dumps(self.run_rule("r-labels", "Blocker: a. Need: b.")) for _ in range(20)}
        self.assertEqual(len(results), 1)

    def test_a_sample_cannot_be_run_before_the_predictions_are_made(self):
        for sample in self.lab["samples"]:
            error = self.assert_code("sample_before_answer", self.run_rule, "r-length", sample["text"])
            self.assertIn("predictions", error.message)
        self.assert_code("sample_before_answer", self.run_rule, "r-length", "  " + self.lab["samples"][0]["text"].upper())

    def test_samples_can_be_run_after_the_lab_is_passed(self):
        self.answer("rules", "rules-lab", ch.correct_answer(self.lab))
        for case in self.lab["cases"]:
            sample = next(s for s in self.lab["samples"] if s["id"] == case["sample"])
            self.assertEqual(self.run_rule(case["rule"], sample["text"])["verdict"], case["expected"])

    def test_bad_inputs(self):
        self.assert_code("unknown_rule", self.run_rule, "nope", "text")
        self.assert_code("bad_answer", self.run_rule, "r-length", "   ")
        self.assert_code("bad_answer", self.run_rule, "r-length", None)
        self.assert_code("bad_answer", self.run_rule, "r-length", 5)
        self.assert_code("bad_answer", self.engine.lesson_rule_run, "rules", "build-explain", "r-length", "x")
        self.assert_code("unknown_activity", self.engine.lesson_rule_run, "rules", "nope", "r-length", "x")
        self.assert_code("lesson_locked", self.engine.lesson_rule_run, "surprise", "fix-scenario", "r", "x")

    def test_running_a_rule_changes_no_progress(self):
        before = self.records()
        self.run_rule("r-length", "hello")
        self.assertEqual(self.records(), before)
        entry = self.block()["per_lesson"]["rules"]["activities"]["rules-lab"]
        self.assertEqual((entry["passed"], entry["attempts"], entry["last"]), (False, 0, None))

    def test_the_predictions_must_cover_every_case(self):
        self.assert_code("bad_answer", self.answer, "rules", "rules-lab", {"cases": {}})
        wrong = self.answer("rules", "rules-lab", ch.wrong_answer(self.lab))
        self.assertFalse(wrong["passed"])
        view = next(a for a in wrong["lesson"]["activities"] if a["id"] == "rules-lab")
        self.assertEqual(view["result"]["right"], len(self.lab["cases"]) - 1)


def ch_activity(course, activity_id):
    for lesson in course.data["lessons"]:
        for activity in lesson["activities"]:
            if activity["id"] == activity_id:
                return activity
    raise KeyError(activity_id)


if __name__ == "__main__":
    unittest.main()
