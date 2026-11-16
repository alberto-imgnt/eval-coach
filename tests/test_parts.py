"""The Part registry (spec part-registry): the course, content and saved progress of more than one Part.

Part 3 and Part 1 are the registered Parts. A synthetic extra Part (part_helpers) is registered inside each test so
the generalization is exercised with a Part that ships no content.
"""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import course_helpers as ch
import helpers
import part_helpers as ph

from eval_coach import lessons as L
from eval_coach import project, resources, state as store
from eval_coach.engine import NOT_KIND, Engine, EngineError
from eval_coach.state import CorruptStateError

PART_9 = "part-9"


def part_three_state(engine):
    state = engine.get_state()
    return {key: state[key] for key in ("course", "steps", "current_step", "current_item", "course_text")}


class Registry(unittest.TestCase):
    def test_parts_three_one_and_two_are_registered_and_keep_their_lists(self):
        self.assertEqual(store.PARTS, (store.PART_3, store.PART_1, store.PART_2))
        part = store.PART_3
        self.assertEqual((part.id, part.n, part.mission), ("part-3", 3, "mission"))
        self.assertEqual(part.course, store.COURSE)
        self.assertEqual(part.lesson_ids, store.LESSON_IDS)
        self.assertEqual(part.step_ids, store.STEP_IDS)
        self.assertEqual(part.course_for("promptfoo"), store.PROMPTFOO_COURSE)
        self.assertEqual(part.step_ids_for("promptfoo"), store.PROMPTFOO_STEP_IDS)
        self.assertEqual(store.all_lesson_ids(),
                         store.LESSON_IDS + store.PART_1.lesson_ids + store.PART_2.lesson_ids)
        self.assertEqual(store.all_step_ids(),
                         store.STEP_IDS + (store.EXTRA_STEP, store.OPTIONAL_STEP) + store.PART_1.step_ids
                         + store.PART_2.step_ids)
        self.assertEqual(store.part_by_id("part-3"), part)
        self.assertIsNone(store.part_by_id("part-9"))

    def test_part_of_finds_the_part_from_any_id_and_gives_none_for_an_unknown_one(self):
        for item in ("mission", "baseline-why", "generate", "baseline", store.EXTRA_STEP, store.OPTIONAL_STEP):
            self.assertIs(store.part_of(item), store.PART_3, item)
        for item in ("p1-mission", "p1-benefits", "cold", "own"):
            self.assertIs(store.part_of(item), store.PART_1, item)
        for item in ("p2-mission", "p2-testfile", "draft", "thresholds", "test-file", "reference"):
            self.assertIs(store.part_of(item), store.PART_2, item)
        self.assertIsNone(store.part_of("no-such-id"))
        with ph.synthetic_part():
            self.assertEqual(store.part_of(ph.CHOICE).id, PART_9)
            self.assertEqual(store.part_of(ph.STEP).id, PART_9)
            self.assertEqual(store.part_of("mission"), store.PART_3)
            self.assertEqual(store.all_lesson_ids(),
                             store.LESSON_IDS + store.PART_1.lesson_ids + store.PART_2.lesson_ids
                             + (ph.INTRO, ph.CHOICE))
        self.assertIsNone(store.part_of(ph.CHOICE))

    def test_register_part_restores_the_registry_even_after_an_error(self):
        before = store.PARTS
        with self.assertRaises(RuntimeError):
            with store.register_part(ph.make_part()):
                self.assertEqual(len(store.PARTS), 4)
                raise RuntimeError("boom")
        self.assertIs(store.PARTS, before)

    def test_a_shared_id_is_reported_with_both_parts(self):
        twin = ph.make_part("part-8", "part-8")
        self.assertEqual(store.duplicate_ids(), [])
        problems = store.duplicate_ids([ph.make_part(), twin])
        self.assertEqual(len(problems), 3)
        self.assertIn("'p9-intro' is in both part-9 and part-8", problems[0])


class SavedProgress(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-parts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def progress_with_parts(self, parts):
        data = store.new_progress("p", "cli", "northwind")
        data["parts"] = parts
        return data

    def test_new_progress_has_an_empty_parts_object(self):
        self.assertEqual(store.new_progress("p", "cli", "northwind")["parts"], {})

    def test_progress_from_before_this_change_loads_and_the_file_is_untouched(self):
        old = store.new_progress("p", "cli", "northwind")
        del old["parts"]
        path = self.tmp / "progress.json"
        store.write_json_atomic(path, old)
        before = path.read_bytes()
        loaded = store.load_progress(path)
        self.assertEqual(loaded["parts"], {})
        self.assertEqual(loaded["done"], [])
        self.assertEqual(path.read_bytes(), before)

    def test_a_part_block_is_completed_from_the_parts_defaults(self):
        with ph.synthetic_part():
            loaded = store.validate_progress(self.progress_with_parts({PART_9: {}}))
        self.assertEqual(loaded["parts"][PART_9], {"done": [], "steps": ph.new_steps()})

    def test_a_part_block_with_progress_loads_unchanged(self):
        block = {"done": [ph.STEP], "steps": {ph.STEP: {"last_check": {"ok": True}, "checklist": {"x": True}}}}
        with ph.synthetic_part():
            loaded = store.validate_progress(self.progress_with_parts({PART_9: copy.deepcopy(block)}))
        self.assertEqual(loaded["parts"][PART_9], block)

    def test_a_wrong_shaped_part_block_is_corrupt_and_names_the_part(self):
        bad = {"parts is a list": [], "block is a list": {PART_9: []}, "done is text": {PART_9: {"done": "x"}},
               "steps is a list": {PART_9: {"steps": []}},
               "a step record is text": {PART_9: {"steps": {ph.STEP: "x"}}},
               "an unknown finished step": {PART_9: {"done": ["generate"]}}}
        with ph.synthetic_part():
            for name, parts in bad.items():
                with self.subTest(case=name), self.assertRaises(CorruptStateError) as ctx:
                    store.validate_progress(self.progress_with_parts(parts))
                if name != "parts is a list":
                    self.assertIn(PART_9, str(ctx.exception))

    def test_the_engine_shows_the_usual_message_for_a_corrupt_part_block_and_changes_no_file(self):
        home, project_dir = self.tmp / "home", self.tmp / "project"
        paths = project.Paths(home, project_dir)
        paths.progress_file.parent.mkdir(parents=True)
        store.write_json_atomic(paths.progress_file, self.progress_with_parts({PART_9: {"done": "x"}}))
        store.write_json_atomic(home / "app.json", {"last_project": str(project_dir)})
        before = paths.progress_file.read_bytes()
        with ph.synthetic_part():
            engine = Engine(home, helpers.FakeTerminal(), lessons=ch.bundled_course())
            self.addCleanup(engine.shutdown)
            self.assertIsNone(engine.progress)
            self.assertIn(engine.content["messages"]["corrupt_progress"].format(path=str(paths.progress_file)),
                          engine.get_state()["setup"]["warnings"])
        self.assertEqual(paths.progress_file.read_bytes(), before)

    def test_a_block_for_a_part_this_build_does_not_know_is_kept_as_it_is(self):
        block = {"done": ["anything"], "extra": [1]}
        loaded = store.validate_progress(self.progress_with_parts({"part-77": copy.deepcopy(block)}))
        self.assertEqual(loaded["parts"], {"part-77": block})

    def test_lesson_records_of_every_registered_part_are_kept_and_the_rest_dropped(self):
        data = store.new_progress("p", "cli", "northwind")
        records = data["lessons"]["records"]
        records.extend({"type": "activity", "lesson": lesson, "item": "x", "source": "s", "at": 1.0}
                       for lesson in ("hook", ph.CHOICE, "gone"))
        with ph.synthetic_part():
            kept = store.validate_progress(copy.deepcopy(data))["lessons"]["records"]
        self.assertEqual([r["lesson"] for r in kept], ["hook", ph.CHOICE])

    def test_lessons_before_a_parts_furthest_finished_step_block_nothing(self):
        data = self.progress_with_parts({PART_9: {"done": [ph.STEP]}})
        data["lessons"]["per_lesson"]["old-lesson"] = {"status": "done", "activities": {}}  # makes the loader migrate
        with ph.synthetic_part():
            block = store.validate_progress(data)["lessons"]["per_lesson"]
        self.assertNotIn("old-lesson", block)
        for lesson in (ph.INTRO, ph.CHOICE):
            self.assertEqual(block[lesson]["status"], "skipped", lesson)
        self.assertNotIn("mission", block)

    def test_a_file_that_gained_a_parts_key_still_loads_in_a_build_that_has_no_such_part(self):
        parts = {PART_9: {"done": [ph.STEP], "steps": ph.new_steps()}}
        loaded = store.validate_progress(self.progress_with_parts(copy.deepcopy(parts)))
        self.assertEqual(loaded["parts"], parts)


class Loader(unittest.TestCase):
    def test_every_registered_part_is_loaded_and_merged_into_one_course(self):
        with ph.synthetic_part():
            course = L.load_bundled()
            self.assertEqual(course.mission_of("hook"), course.mission)
            self.assertEqual(course.mission_of(ph.CHOICE), "The test Part's mission.")
        self.assertEqual(list(course.by_id), list(store.LESSON_IDS) + list(store.PART_1.lesson_ids)
                         + list(store.PART_2.lesson_ids) + [ph.INTRO, ph.CHOICE])
        self.assertIn(ph.STEP, course.step_checks)
        self.assertEqual(list(L.load_bundled().by_id),
                         list(store.LESSON_IDS) + list(store.PART_1.lesson_ids) + list(store.PART_2.lesson_ids))

    def test_a_lesson_id_that_two_parts_share_stops_the_load(self):
        with ph.synthetic_part(extra_parts=[ph.make_part("part-8", "part-8")]):
            with self.assertRaises(L.LessonError) as ctx:
                L.load_bundled()
            self.assertIn("'p9-intro' is in both part-9 and part-8", str(ctx.exception))
            with self.assertRaises(L.LessonError) as ctx:
                L.load_step_content()
            self.assertIn("'p9-step'", str(ctx.exception))

    def test_a_lesson_outside_its_parts_list_is_reported(self):
        data = ph.lessons_data()
        extra = copy.deepcopy(data["lessons"][1])
        extra["id"] = "stray"
        data["lessons"].append(extra)
        with self.assertRaises(L.LessonError) as ctx:
            L.validate_course(data, None, ph.make_part())
        self.assertIn("lessons not in the course order: ['stray']", str(ctx.exception))
        with self.assertRaises(L.LessonError) as ctx:
            L.validate_course(ph.lessons_data())  # Part 3's list: the test Part's lessons are outside it
        self.assertIn("missing lessons", str(ctx.exception))

    def test_a_parts_first_lesson_is_its_mission_for_the_no_questions_rule(self):
        data = ph.lessons_data()
        L.validate_course(data, None, ph.make_part())
        data["lessons"][1]["activities"] = []
        with self.assertRaises(L.LessonError):
            L.validate_course(data, None, ph.make_part())

    def test_part_three_step_text_is_the_file_and_other_steps_are_added(self):
        file = json.loads(resources.read_text("content/steps.json"))
        part_one = json.loads(resources.read_text("content/part-1-steps.json"))["steps"]
        part_two = json.loads(resources.read_text("content/part-2-steps.json"))["steps"]
        content, ui = L.load_step_content()
        self.assertEqual({k: v for k, v in content["steps"].items() if k not in part_one and k not in part_two},
                         file["steps"])
        self.assertEqual({k: v for k, v in content.items() if k != "steps"}, {k: v for k, v in file.items() if k != "steps"})
        self.assertEqual(ui, {})
        with ph.synthetic_part():
            content, ui = L.load_step_content()
        self.assertEqual({k: v for k, v in content["steps"].items()
                          if k not in part_one and k not in part_two and k != ph.STEP}, file["steps"])
        self.assertEqual(content["steps"][ph.STEP]["kind"], ph.KIND)
        self.assertEqual(content["messages"], file["messages"])
        self.assertEqual(ui, {PART_9: {ph.ui_key(): "Words for the test Part"}})

    def test_a_step_kind_nobody_handles_stops_the_start(self):
        with ph.synthetic_part(register_kind=False):
            with self.assertRaises(L.LessonError) as ctx:
                L.load_step_content()
            self.assertIn(f"unknown kind {ph.KIND!r}", str(ctx.exception))
            with self.assertRaises(L.LessonError):
                Engine(Path(tempfile.mkdtemp(prefix="eval-coach-kind-")), helpers.FakeTerminal())

    def test_a_part_with_no_text_for_one_of_its_steps_stops_the_start(self):
        with ph.synthetic_part():
            real = resources.read_text

            def without_step(relpath):
                if relpath == ph.STEPS_FILE:
                    return json.dumps({"steps": {}})
                return real(relpath)

            from unittest import mock
            with mock.patch.object(resources, "read_text", without_step), self.assertRaises(L.LessonError) as ctx:
                L.load_step_content()
        self.assertIn(f"no text for step {ph.STEP!r}", str(ctx.exception))

    def test_the_content_checks_read_every_registered_part(self):
        with ph.synthetic_part():
            parts = ch.parts_data()
        self.assertEqual([p.id for p, _ in parts], ["part-3", "part-1", "part-2", PART_9])
        for part, data in parts:
            self.assertEqual(sorted(c["step"] for c in data["step_checks"]), sorted(part.step_ids))
            self.assertEqual([x["id"] for x in data["lessons"]], list(part.lesson_ids))


class TwoParts(ch.CourseBase):
    """An engine over the bundled course and the synthetic Part."""

    def setUp(self):
        self.handler = ph.Handler()
        registered = ph.synthetic_part(self.handler)
        registered.__enter__()
        self.addCleanup(registered.__exit__, None, None, None)
        super().setUp()

    def part_state(self, part=PART_9):
        return self.engine.get_state(part=part)

    def statuses(self, part=PART_9):
        return [(i["id"], i["status"]) for i in self.part_state(part)["course"]]

    def finish_lessons_of_part(self):
        self.finish(ph.INTRO)
        self.finish(ph.CHOICE)


class Walk(TwoParts):
    def test_the_first_lesson_of_a_part_opens_before_setup_and_nothing_else_does(self):
        self.assertEqual(self.statuses(), [(ph.INTRO, "active"), (ph.CHOICE, "locked"), (ph.STEP, "locked")])
        self.assertEqual(self.engine.lesson_view(ph.INTRO)["lesson"]["status"], "active")
        self.assertEqual(self.engine.lesson_view(ph.CHOICE)["lesson"]["status"], "preview")
        self.assert_code("preflight_incomplete", self.engine.lesson_complete, ph.CHOICE)

    def test_a_step_is_refused_before_setup_the_way_a_part_three_step_is(self):
        self.assert_code("not_configured", self.engine.step_check, "generate")
        self.assert_code("not_configured", self.engine.step_check, ph.STEP)

    def test_parts_do_not_lock_each_other(self):
        self.setup_project()
        self.assertEqual(self.status_of("mission"), "active")
        self.assertEqual(self.statuses()[0], (ph.INTRO, "active"))
        self.finish(ph.INTRO)
        self.assertEqual(self.statuses(), [(ph.INTRO, "done"), (ph.CHOICE, "active"), (ph.STEP, "locked")])
        self.assertEqual(self.status_of("mission"), "active")
        self.assertEqual(self.status_of("hook"), "locked")

    def test_a_step_opens_only_after_the_lesson_before_it(self):
        self.setup_project()
        self.finish(ph.INTRO)
        error = self.assert_code("step_locked", self.engine.step_check, ph.STEP)
        self.assertIn(self.lesson(ph.CHOICE)["title"], error.message)
        self.finish(ph.CHOICE)
        self.assertEqual(self.statuses()[-1], (ph.STEP, "active"))

    def test_part_three_does_not_change_while_the_other_part_progresses(self):
        self.setup_project()
        before = part_three_state(self.engine)
        self.finish_lessons_of_part()
        self.engine.step_check(ph.STEP)
        self.assertEqual(part_three_state(self.engine), before)

    def test_progress_of_the_other_part_is_saved_under_its_own_key_only(self):
        self.setup_project()
        defaults = store.new_progress("", "", "")
        self.assertEqual(self.engine.progress["parts"], {})
        self.finish_lessons_of_part()
        self.engine.step_check(ph.STEP)
        saved = store.read_json(self.paths.progress_file)
        self.assertEqual(saved["parts"][PART_9]["done"], [ph.STEP])
        self.assertEqual(saved["parts"][PART_9]["steps"][ph.STEP]["last_check"], {"ok": True})
        self.assertEqual((saved["done"], saved["track"]), ([], None))
        self.assertEqual(saved["steps"], defaults["steps"])
        self.assertEqual(self.statuses()[-1], (ph.STEP, "done"))
        self.assertEqual(self.part_state()["steps"], [{"id": ph.STEP, "title": self.engine._text(ph.STEP)["title"],
                                                       "status": "done"}])

    def test_reading_a_part_creates_no_saved_block(self):
        self.setup_project()
        before = store.read_json(self.paths.progress_file)
        self.part_state()
        self.assertEqual(self.engine.progress["parts"], {})
        self.assertEqual(store.read_json(self.paths.progress_file), before)


class Kinds(TwoParts):
    def test_a_registered_kind_handles_the_step_and_a_step_with_no_kind_takes_the_part_three_path(self):
        self.setup_project()
        self.finish_lessons_of_part()
        self.assertIs(self.engine._kind_call("generate", "check"), NOT_KIND)
        self.engine.step_check(ph.STEP)
        self.assertEqual(self.handler.calls, [("check", ph.STEP)])
        self.assertEqual(self.engine.progress["done"], [])

    def test_the_step_detail_comes_from_the_kind(self):
        self.setup_project()
        self.finish_lessons_of_part()
        step = self.engine.get_state(step=ph.STEP)["step"]
        self.assertTrue(step["handled"])
        self.assertEqual(step["status"], "active")

    def test_an_action_the_kind_does_not_offer_is_refused_plainly(self):
        self.setup_project()
        self.assert_code("not_supported", self.engine.step_start, ph.STEP)
        self.assert_code("not_supported", self.engine.step_submit, ph.STEP, {})
        self.assert_code("not_supported", self.engine.step_skip, ph.STEP)


class StateOfAPart(TwoParts):
    def test_no_selector_describes_part_three_exactly_as_before(self):
        self.setup_project()
        with_part = part_three_state(self.engine)
        plain = self.engine.get_state()
        self.assertEqual(self.engine.get_state(part="part-3")["course"], plain["course"])
        self.assertEqual([i["id"] for i in plain["course"]], [i for _, i in store.COURSE])
        self.assertEqual([s["id"] for s in plain["steps"]], list(store.STEP_IDS))
        self.assertEqual(with_part["course_text"], self.engine.lesson_text["ui"])

    def test_a_selector_gives_that_parts_course_steps_and_current_item(self):
        self.setup_project()
        state = self.part_state()
        self.assertEqual([(i["kind"], i["id"]) for i in state["course"]], list(ph.make_part().course))
        self.assertEqual([s["id"] for s in state["steps"]], [ph.STEP])
        self.assertEqual(state["current_item"], {"kind": "lesson", "id": ph.INTRO})
        self.assertIsNone(state["current_step"])
        self.assertEqual(state["optional_steps"], [])
        self.finish_lessons_of_part()
        state = self.part_state()
        self.assertEqual((state["current_step"], state["current_item"]),
                         (ph.STEP, {"kind": "step", "id": ph.STEP}))
        self.assertEqual(state["step"]["id"], ph.STEP)

    def test_a_step_implies_its_part(self):
        self.setup_project()
        state = self.engine.get_state(step=ph.STEP)
        self.assertEqual([i["id"] for i in state["course"]], [ph.INTRO, ph.CHOICE, ph.STEP])
        self.assertEqual(self.engine.get_state(step=ph.STEP, part="part-3")["steps"], state["steps"])

    def test_the_parts_own_interface_words_sit_on_top_of_the_shared_ones(self):
        shared = self.engine.lesson_text["ui"]
        words = self.part_state()["course_text"]
        self.assertEqual(words[ph.ui_key()], "Words for the test Part")
        self.assertEqual({k: v for k, v in words.items() if k != ph.ui_key()},
                         {k: v for k, v in shared.items() if k != ph.ui_key()})
        self.assertEqual(self.engine.get_state()["course_text"], shared)

    def test_an_unknown_part_is_refused_with_a_plain_message_and_nothing_changes(self):
        self.setup_project()
        before = store.read_json(self.paths.progress_file)
        error = self.assert_code("unknown_part", self.engine.get_state, part="part-99")
        self.assertEqual(error.message, self.engine.content["messages"]["unknown_part"])
        self.assertEqual(store.read_json(self.paths.progress_file), before)

    def test_the_series_counts_every_part_from_its_own_list(self):
        self.setup_project()
        data = copy.deepcopy(self.engine.series_text)
        data["parts"].append({"n": 9, "id": PART_9, "title": "Nine", "kind": "course", "outcome": "The ninth."})
        self.engine.series_text = data
        row = self.engine.get_state()["series"]["parts"][-1]
        self.assertEqual((row["state"], row["done"], row["total"]), ("not_started", 0, 3))
        self.assertEqual([x["id"] for x in row["lessons"]], [ph.INTRO, ph.CHOICE])
        self.finish(ph.INTRO)
        row = self.engine.get_state()["series"]["parts"][-1]
        self.assertEqual((row["state"], row["done"], row["total"]), ("in_progress", 1, 3))
        part_three = next(p for p in self.engine.get_state()["series"]["parts"] if p["id"] == "part-3")
        self.assertEqual((part_three["done"], part_three["total"]), (0, len(store.COURSE)))


class SharedPieces(TwoParts):
    def test_a_review_sitting_mixes_lessons_from_both_parts(self):
        self.setup_project()
        self.finish("mission")
        self.finish("hook")
        self.finish_lessons_of_part()
        self.clock.advance(days=1)
        lessons = {item["lesson"] for item in self.engine.review_get()["review"]["items"]}
        self.assertIn(ph.CHOICE, lessons)
        self.assertIn("hook", lessons)

    def test_progress_made_before_a_project_exists_is_merged_whatever_the_part(self):
        self.finish(ph.INTRO)
        self.assertEqual(store.read_json(self.home / "pending-lessons.json")["per_lesson"][ph.INTRO]["status"], "done")
        self.setup_project()
        self.assertEqual(self.engine.progress["lessons"]["per_lesson"][ph.INTRO]["status"], "done")
        self.assertEqual(self.statuses()[:2], [(ph.INTRO, "done"), (ph.CHOICE, "active")])

    def progress_in_the_other_part(self):
        self.setup_project()
        self.finish_lessons_of_part()
        self.engine.step_check(ph.STEP)
        self.assertEqual(self.engine.progress["parts"][PART_9]["done"], [ph.STEP])

    def assert_fresh_in_every_part(self):
        self.assertEqual(self.engine.progress["parts"], {})
        self.assertEqual(self.engine.progress["done"], [])
        self.assertEqual(self.statuses(), [(ph.INTRO, "active"), (ph.CHOICE, "locked"), (ph.STEP, "locked")])
        self.assertEqual(store.read_json(self.paths.progress_file)["parts"], {})

    def test_reset_lesson_progress_clears_every_parts_progress(self):
        self.progress_in_the_other_part()
        self.engine.reset_progress(True)
        self.assert_fresh_in_every_part()

    def test_reset_app_configuration_clears_every_parts_progress(self):
        self.progress_in_the_other_part()
        self.engine.reset_configuration(True)
        self.assertIsNone(self.engine.progress)
        self.setup_project()
        self.assert_fresh_in_every_part()


if __name__ == "__main__":
    unittest.main()
