"""The Series map: content/series.json and the `series` key of the state (spec series-map)."""
from __future__ import annotations

import json
import re
import unittest

import helpers  # noqa: F401
from helpers import ROOT

from course_helpers import CourseBase, bundled_data
from eval_coach import resources
from eval_coach.engine import Engine
from eval_coach import state
CONTENT = ROOT / "app" / "eval_coach" / "content"
WEB = ROOT / "app" / "eval_coach" / "web"
PART_6 = 6
POINTERS = ("office hours", "air discussion", "session", "contact ", "reach out", "ask the team", "email us",
            "message us")


def series():
    return json.loads(resources.read_text("content/series.json"))


MISSIONS = (("mission", "lessons.json"), ("p1-mission", "part-1-lessons.json"), ("p2-mission", "part-2-lessons.json"))
PASSAGES = ("**The goal.**", "**Why it matters to you.**", "**What you will do.**", "**What you leave with.**")
SERIES_PASSAGE = "**About this series.**"
PART_NAMES = ("Structured prompting", "Defining evaluation criteria", "Running evals and baseline",
              "Iterating with evaluation-driven development", "Load-bearing audit and packaging")


def mission_lesson(lesson_id, file):
    data = json.loads(resources.read_text(f"content/{file}"))
    return next(x for x in data["lessons"] if x["id"] == lesson_id)


class SeriesContent(unittest.TestCase):
    def test_six_parts_in_order_with_their_kinds(self):
        parts = series()["parts"]
        self.assertEqual([p["n"] for p in parts], [1, 2, 3, 4, 5, 6])
        self.assertEqual([p["kind"] for p in parts], ["course", "course", "course", "soon", "soon", "live"])
        self.assertEqual(len({p["id"] for p in parts}), 6)

    def test_the_intro_is_about_doing_the_work_yourself(self):
        intro = series()["ui"]["intro"]
        self.assertTrue(intro.startswith("Six Parts, one method."))
        self.assertIn("Do each one yourself", intro)
        self.assertNotRegex(intro, r"(?i)look ahead|stage 3")

    def test_no_mission_lists_the_parts(self):
        for lesson_id, file in MISSIONS:
            body = mission_lesson(lesson_id, file)["body"]
            with self.subTest(lesson=lesson_id):
                self.assertNotIn("you-are-here", body)
                self.assertEqual([n for n in PART_NAMES if n in body], [])
                self.assertIsNone(re.search(r"(?m)^(done|here|next) \| \d \|", body))

    def test_the_series_map_still_names_every_part(self):
        titles = [p["title"] for p in series()["parts"]]
        for name in PART_NAMES:
            self.assertIn(name, titles)
        self.assertEqual(len(titles), 6)

    def test_parts_one_and_two_carry_their_own_interface_words_and_the_others_carry_none(self):
        for part in series()["parts"]:
            if part["id"] == "part-1":
                self.assertEqual(part["ui"]["brand_sub"], "Part 1 \u00b7 Structured prompting")
            elif part["id"] == "part-2":
                self.assertEqual(part["ui"]["brand_sub"], "Part 2 \u00b7 Defining evaluation criteria")
            else:
                self.assertNotIn("ui", part)

    def test_part_six_says_it_is_a_live_meeting_and_points_to_no_one(self):
        data = series()
        part = data["parts"][-1]
        self.assertEqual(data["ui"]["live"], "Live meeting")
        self.assertRegex(part["outcome"], r"(?i)\blive\b")
        text = (part["title"] + " " + part["outcome"] + " " + data["ui"]["live"]).lower()
        for needle in POINTERS:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)
        self.assertNotRegex(text, r"https?:|www\.|@")

    def test_the_series_words_are_complete(self):
        ui = series()["ui"]
        self.assertEqual(ui["soon"], "Coming soon")
        for key in ("brand_sub", "start", "continue", "review", "state_not_started", "state_in_progress",
                    "state_done", "count", "expand", "collapse"):
            with self.subTest(key=key):
                self.assertTrue(ui[key].strip())

    def test_the_live_note_stays_in_the_baseline_lesson_only(self):
        for name in sorted(p.name for p in CONTENT.glob("*.json")):
            text = (CONTENT / name).read_text(encoding="utf-8")
            if name == "lessons.json":
                lessons = json.loads(text)["lessons"]
                holders = [x["id"] for x in lessons
                           if re.search(r"office hours|AIR discussion", json.dumps(x))]
                self.assertEqual(holders, ["baseline-why"])
            else:
                with self.subTest(file=name):
                    self.assertNotRegex(text, r"(?i)office hours|AIR discussion")
        for path in sorted(WEB.rglob("*")):
            if path.is_file() and path.suffix in (".js", ".html", ".css") and "vendor" not in path.parts:
                with self.subTest(file=path.name):
                    self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)office hours|AIR discussion")


    def test_every_course_part_on_the_map_is_registered_and_every_registered_part_is_on_the_map(self):
        mapped = {p["id"]: p["n"] for p in series()["parts"] if p["kind"] == "course"}
        registered = {p.id: p.n for p in state.PARTS}
        self.assertEqual(sorted(set(mapped) - set(registered)), [], "on the map as a course, not registered")
        self.assertEqual(sorted(set(registered) - set(mapped)), [], "registered, not a course on the map")
        self.assertEqual(mapped, registered)


class MissionShape(unittest.TestCase):
    def test_each_mission_has_the_four_passages_in_order(self):
        for lesson_id, file in MISSIONS:
            body = mission_lesson(lesson_id, file)["body"]
            labels = re.findall(r"(?m)^\*\*([A-Z][^*]*?\.)\*\*", body)
            expected = ["The goal.", "Why it matters to you.", "What you will do.", "What you leave with."]
            if lesson_id == "p1-mission":
                expected = ["About this series."] + expected
            with self.subTest(lesson=lesson_id):
                self.assertEqual(labels, expected)
                positions = [body.index(p) for p in PASSAGES]
                self.assertEqual(positions, sorted(positions))

    def test_each_mission_is_one_page_with_no_questions_within_the_cap(self):
        for lesson_id, file in MISSIONS:
            lesson = mission_lesson(lesson_id, file)
            with self.subTest(lesson=lesson_id):
                self.assertEqual((lesson["activities"], lesson["retrieval"]), ([], []))
                self.assertLessEqual(len(lesson["body"].split()), 450)

    def test_the_series_passage_is_in_part_one_only(self):
        part_one = mission_lesson("p1-mission", "part-1-lessons.json")["body"]
        self.assertTrue(part_one.startswith(SERIES_PASSAGE))
        for needle in ("judge the work AI gives you", "because you checked it", "blind trust or blind distrust",
                       "AI sounds sure of itself", "\"Better\" is only an opinion", "from one try to the next"):
            self.assertIn(needle, part_one)
        for lesson_id, file in (("mission", "lessons.json"), ("p2-mission", "part-2-lessons.json")):
            body = mission_lesson(lesson_id, file)["body"]
            with self.subTest(lesson=lesson_id):
                self.assertNotIn(SERIES_PASSAGE, body)
                self.assertNotIn("AI sounds sure of itself", body)
                self.assertNotIn("blind trust", body)

    def test_why_it_matters_differs_by_part_and_what_you_leave_with_names_something(self):
        why = []
        for lesson_id, file in MISSIONS:
            body = mission_lesson(lesson_id, file)["body"]
            why.append(re.search(r"\*\*Why it matters to you\.\*\*(.*?)\n\n", body, re.S).group(1))
            leave = body.split("**What you leave with.**", 1)[1]
            with self.subTest(lesson=lesson_id):
                self.assertRegex(leave, r"(?i)prompt|test case|checker|baseline")
        self.assertEqual(len(set(why)), 3)

    def test_the_practice_task_is_named_as_practice_only(self):
        for lesson_id, file in MISSIONS:
            body = mission_lesson(lesson_id, file)["body"]
            with self.subTest(lesson=lesson_id):
                self.assertNotIn("Northwind", body)
                self.assertIn("Practice task", body)
                self.assertIn("for practice only", body)
                self.assertIn("never something to submit", body)

    def test_part_two_opens_on_the_question_from_part_one_and_says_nothing_is_run(self):
        body = mission_lesson("p2-mission", "part-2-lessons.json")["body"]
        goal = body.split("**Why it matters to you.**", 1)[0]
        self.assertIn("how do you know the second answer is better?", goal)
        self.assertIn("before you look at any answer", goal)
        self.assertIn("Nothing is run in this Part", body)
        self.assertIn("starts in Part 3", body)


class SeriesState(CourseBase):
    def part3(self, state=None):
        return next(p for p in (state or self.state())["series"]["parts"] if p["id"] == "part-3")

    def part1(self, state=None):
        return next(p for p in (state or self.state())["series"]["parts"] if p["id"] == "part-1")

    def counted(self):
        return [i for i in self.state()["course"] if i["status"] in ("done", "skipped")]

    def test_the_shape_follows_series_json(self):
        data = self.state()["series"]
        self.assertEqual(data["title"], series()["title"])
        self.assertEqual(data["ui"], series()["ui"])
        self.assertEqual([p["n"] for p in data["parts"]], [1, 2, 3, 4, 5, 6])
        for part in data["parts"]:
            if part["kind"] != "course":
                self.assertEqual(set(part), {"n", "id", "title", "kind", "outcome"})

    def test_part_three_is_not_started_before_anything_is_done(self):
        self.setup_project()
        part = self.part3()
        self.assertEqual((part["state"], part["done"]), ("not_started", 0))
        self.assertEqual(part["total"], len(self.state()["course"]))

    def test_part_three_is_in_progress_after_the_first_lesson(self):
        self.setup_project()
        self.finish("mission")
        part = self.part3()
        self.assertEqual(part["state"], "in_progress")
        self.assertEqual(part["done"], len(self.counted()))
        self.assertGreaterEqual(part["done"], 1)

    def test_part_three_is_done_when_every_item_is_done_or_skipped(self):
        self.setup_project()
        self.finish_before("no-such-item")
        part = self.part3()
        self.assertEqual(part["state"], "done")
        self.assertEqual(part["done"], part["total"])
        self.assertEqual(part["done"], len(self.counted()))

    def test_a_skipped_lesson_counts_like_the_sidebar_counts_it(self):
        self.setup_project()
        self.mark_skipped("hook")
        part = self.part3()
        self.assertEqual(part["done"], len(self.counted()))
        self.assertIn("skipped", [x["status"] for x in self.state()["course"]])

    def test_the_lesson_list_is_the_lessons_in_course_order_with_their_statuses(self):
        self.setup_project()
        part = self.part3()
        lessons = [i for i in self.state()["course"] if i["kind"] == "lesson"]
        self.assertEqual(part["lessons"], [{"id": i["id"], "title": i["title"], "status": i["status"]}
                                           for i in lessons])
        self.assertEqual(len(part["lessons"]), 7)
        self.assertIn("locked", [x["status"] for x in part["lessons"]])

    def test_locked_items_are_listed_before_setup_has_passed(self):
        part = self.part3(self.engine.get_state())
        self.assertEqual(part["total"], len(self.state()["course"]))
        self.assertTrue(part["lessons"])

    def test_an_engine_without_a_course_has_no_series(self):
        engine = Engine(self.home, self.terminal, poll_interval=0.01, lessons=None, clock=self.clock)
        self.addCleanup(engine.shutdown)
        self.assertIsNone(engine.get_state()["series"])

    def test_part_one_counts_its_own_items_and_part_three_its_own(self):
        self.setup_project()
        before = self.part1()
        self.assertEqual((before["state"], before["done"], before["total"]), ("not_started", 0, 9))
        self.assertEqual([x["id"] for x in before["lessons"]], list(state.PART_1.lesson_ids))
        self.assertEqual(len(before["lessons"]), 4)
        self.finish("p1-mission")
        self.engine.progress["parts"].setdefault("part-1", state.new_part_progress(state.PART_1))["done"].extend(
            ["cold", "score"])
        self.engine._save()
        now = self.state()["series"]
        part1 = next(p for p in now["parts"] if p["id"] == "part-1")
        part3 = next(p for p in now["parts"] if p["id"] == "part-3")
        self.assertEqual((part1["state"], part1["done"], part1["total"]), ("in_progress", 3, 9))
        self.assertEqual((part3["state"], part3["done"], part3["total"]), ("not_started", 0, 16))
        self.assertNotIn("ui", part1)  # the interface words go to course_text, not to the map

    def test_a_part_one_row_has_no_coming_soon_state(self):
        part = next(p for p in self.state()["series"]["parts"] if p["id"] == "part-1")
        self.assertEqual(part["kind"], "course")
        self.assertIn("state", part)

    def test_part_two_counts_its_own_eight_items_and_lists_its_four_lessons(self):
        self.setup_project()
        part = next(p for p in self.state()["series"]["parts"] if p["id"] == "part-2")
        self.assertEqual((part["kind"], part["state"], part["done"], part["total"]), ("course", "not_started", 0, 8))
        self.assertEqual([x["id"] for x in part["lessons"]], list(state.PART_2.lesson_ids))
        self.assertEqual(len(part["lessons"]), 4)
        self.assertNotIn("ui", part)  # the interface words go to course_text, not to the map


if __name__ == "__main__":
    unittest.main()
