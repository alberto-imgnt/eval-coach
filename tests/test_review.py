"""The review scheduler (1, 3 and 7 days) and the review queue in the engine, all on an injected clock."""
from __future__ import annotations

import itertools
import json
import unittest

import course_helpers as ch
from course_helpers import DAY, CourseBase

from eval_coach import review as R

ITEM = {"lesson": "hook", "item": "r-hook-1", "stage": 0, "due": None, "retired": False}


def entry(stage=0, due=0, retired=False, lesson="hook", item="r"):
    return {"lesson": lesson, "item": item, "stage": stage, "due": due, "retired": retired}


class Scheduler(unittest.TestCase):
    def test_the_intervals_are_one_three_and_seven_days(self):
        self.assertEqual(R.INTERVAL_DAYS, (1, 3, 7))
        self.assertEqual(R.DAY_SECONDS, 86400)
        self.assertEqual(R.MAX_PER_SITTING, 5)

    def test_every_item_of_a_lesson_is_scheduled_one_day_after_completion(self):
        items = {}
        R.schedule(items, "hook", ["a", "b"], 1000.0)
        self.assertEqual(set(items), {"hook:a", "hook:b"})
        for key, value in items.items():
            self.assertEqual(value["due"], 1000.0 + DAY)
            self.assertEqual((value["stage"], value["retired"]), (0, False))
        self.assertEqual((items["hook:a"]["lesson"], items["hook:a"]["item"]), ("hook", "a"))

    def test_scheduling_again_never_resets_an_item(self):
        items = {}
        R.schedule(items, "hook", ["a"], 0.0)
        R.apply_answer(items["hook:a"], True, 5 * DAY)
        before = dict(items["hook:a"])
        R.schedule(items, "hook", ["a"], 9 * DAY)
        self.assertEqual(items["hook:a"], before)

    def test_nothing_is_due_early_and_it_is_due_at_the_exact_time(self):
        self.assertFalse(R.is_due(entry(due=100.0), 99.999))
        self.assertTrue(R.is_due(entry(due=100.0), 100.0))
        self.assertTrue(R.is_due(entry(due=100.0), 5000.0))

    def test_a_retired_or_unscheduled_item_is_never_due(self):
        self.assertFalse(R.is_due(entry(due=None, retired=True), 10 ** 9))
        self.assertFalse(R.is_due(entry(due=0, retired=True), 10 ** 9))
        self.assertFalse(R.is_due(entry(due=None), 10 ** 9))

    def test_due_keys_lists_the_oldest_first_and_leaves_out_what_is_not_due(self):
        items = {"b:1": entry(due=50, lesson="b"), "a:1": entry(due=50, lesson="a"), "c:1": entry(due=10, lesson="c"),
                 "d:1": entry(due=500, lesson="d"), "e:1": entry(due=None, retired=True, lesson="e")}
        self.assertEqual(R.due_keys(items, 100), ["c:1", "a:1", "b:1"])
        self.assertEqual(R.due_keys(items, 5), [])

    def test_a_right_answer_moves_through_one_three_seven_then_retires(self):
        e = entry(stage=0, due=1 * DAY)
        R.apply_answer(e, True, 1 * DAY)
        self.assertEqual((e["stage"], e["due"], e["retired"]), (1, 1 * DAY + 3 * DAY, False))
        R.apply_answer(e, True, 4 * DAY)
        self.assertEqual((e["stage"], e["due"], e["retired"]), (2, 4 * DAY + 7 * DAY, False))
        R.apply_answer(e, True, 11 * DAY)
        self.assertEqual((e["stage"], e["due"], e["retired"]), (3, None, True))

    def test_the_interval_runs_from_the_moment_of_the_answer_not_the_due_date(self):
        e = entry(stage=0, due=1 * DAY)
        R.apply_answer(e, True, 10 * DAY)
        self.assertEqual(e["due"], 13 * DAY)

    def test_a_wrong_answer_goes_back_to_one_day_from_any_stage(self):
        for stage in (0, 1, 2):
            with self.subTest(stage=stage):
                e = entry(stage=stage, due=0)
                R.apply_answer(e, False, 50 * DAY)
                self.assertEqual((e["stage"], e["due"], e["retired"]), (0, 51 * DAY, False))

    def test_a_wrong_answer_restarts_the_whole_climb(self):
        e = entry(stage=0, due=0)
        R.apply_answer(e, True, 0)
        R.apply_answer(e, False, 3 * DAY)
        R.apply_answer(e, True, 4 * DAY)
        R.apply_answer(e, True, 7 * DAY)
        self.assertFalse(e["retired"])
        R.apply_answer(e, True, 14 * DAY)
        self.assertTrue(e["retired"])

    def test_a_retired_item_stays_out_of_the_queue_for_good(self):
        e = entry(stage=2, due=0)
        R.apply_answer(e, True, 0)
        items = {"hook:r": e}
        self.assertEqual(R.due_keys(items, 10 ** 10), [])


class Interleaving(unittest.TestCase):
    def build(self, counts):
        items, keys = {}, []
        for lesson, count in counts.items():
            for n in range(count):
                key = f"{lesson}:{n}"
                items[key] = entry(lesson=lesson, item=str(n), due=0)
                keys.append(key)
        return items, keys

    def adjacent_same(self, items, order):
        return sum(1 for a, b in zip(order, order[1:]) if items[a]["lesson"] == items[b]["lesson"])

    def test_at_most_five_items_are_picked(self):
        items, keys = self.build({"a": 4, "b": 4, "c": 4})
        self.assertEqual(len(R.pick_sitting(items, keys)), 5)
        self.assertEqual(len(R.pick_sitting(items, keys, limit=2)), 2)
        self.assertEqual(len(R.pick_sitting(items, keys[:3])), 3)
        self.assertEqual(R.pick_sitting(items, []), [])

    def test_consecutive_items_come_from_different_lessons_when_possible(self):
        items, keys = self.build({"a": 2, "b": 2, "c": 1})
        order = R.pick_sitting(items, keys)
        self.assertEqual(sorted(order), sorted(keys))
        self.assertEqual(self.adjacent_same(items, order), 0)

    def test_the_fewest_possible_neighbours_share_a_lesson_for_every_mix(self):
        for sizes in itertools.product(range(0, 6), repeat=4):
            counts = {name: size for name, size in zip("abcd", sizes) if size}
            if not counts:
                continue
            items, keys = self.build(counts)
            order = R.pick_sitting(items, keys)
            total = len(order)
            biggest = max(sum(1 for k in order if items[k]["lesson"] == lesson) for lesson in counts)
            allowed = max(0, 2 * biggest - total - 1)
            with self.subTest(sizes=sizes):
                self.assertEqual(self.adjacent_same(items, order), allowed)
                self.assertLessEqual(total, 5)
                self.assertEqual(len(set(order)), total)

    def test_one_big_lesson_cannot_crowd_the_others_out_of_a_sitting(self):
        items, keys = self.build({"a": 8, "b": 1, "c": 1})
        order = R.pick_sitting(items, keys)
        lessons = [items[k]["lesson"] for k in order]
        self.assertIn("b", lessons)
        self.assertIn("c", lessons)
        self.assertEqual(lessons.count("a"), 3)

    def test_a_single_lesson_is_still_picked(self):
        items, keys = self.build({"a": 7})
        self.assertEqual(R.pick_sitting(items, keys), keys[:5])

    def test_the_result_is_the_same_every_time(self):
        items, keys = self.build({"a": 3, "b": 3, "c": 3})
        self.assertEqual(R.pick_sitting(items, keys), R.pick_sitting(items, keys))

    def test_items_inside_one_lesson_keep_their_due_order(self):
        items, keys = self.build({"a": 3, "b": 3})
        order = R.pick_sitting(items, keys)
        for lesson in "ab":
            mine = [k for k in order if k.startswith(lesson)]
            self.assertEqual(mine, sorted(mine))


class ReviewQueue(CourseBase):
    """The queue through the engine, with a controlled clock."""

    def setUp(self):
        super().setUp()
        self.setup_project()

    def complete(self, *lessons):
        for lesson in lessons:
            self.finish(lesson)

    def complete_three(self):
        """Hook, several-runs and rules: eleven retrieval items from three lessons."""
        self.complete("mission", "hook", "several-runs")
        self.mark_step_done("generate")
        self.complete("rules")

    def complete_hook(self):
        self.complete("mission", "hook")

    def items(self):
        return self.engine.review_get()["review"]["items"]

    def reopen(self):
        """Close and reopen the app: a new sitting is chosen from whatever is due."""
        self.engine = self.new_engine()

    def answer_review(self, key, correct=True):
        item = next(i for i in self.items() if i["item"] == key)
        lesson = self.lesson(item["lesson"])
        retrieval = next(r for r in lesson["retrieval"] if r["id"] == self.engine.progress["lessons"]["review"]
                         ["items"][key]["item"])
        option = ch.correct_option(retrieval) if correct else ch.wrong_option(retrieval)
        return self.engine.review_answer(key, option)

    def test_completing_a_lesson_schedules_each_retrieval_item_for_tomorrow(self):
        self.complete_hook()
        scheduled = self.block()["review"]["items"]
        self.assertEqual(set(scheduled), {"hook:r-hook-1", "hook:r-hook-2"})
        for value in scheduled.values():
            self.assertEqual(value["due"], self.clock() + DAY)

    def test_the_mission_has_nothing_to_review(self):
        self.finish("mission")
        self.assertEqual(self.block()["review"]["items"], {})
        self.clock.advance(days=30)
        self.assertEqual(self.items(), [])

    def test_a_lesson_that_is_not_complete_schedules_nothing(self):
        self.finish("mission")
        self.engine.lesson_view("hook")
        self.answer("hook", "hook-explain", ch.correct_answer(ch_activity(self.course, "hook-explain")))
        self.assertEqual(self.block()["review"]["items"], {})

    def test_nothing_is_shown_early(self):
        self.complete_three()
        self.assertEqual(self.items(), [])
        self.assertEqual(self.state()["review"], {"due": 0, "postponed": False})
        self.clock.advance(seconds=DAY - 1)
        self.assertEqual(self.items(), [])
        self.assertEqual(self.state()["review"]["due"], 0)

    def test_items_appear_on_the_day_they_are_due(self):
        self.complete_three()
        self.clock.advance(days=1)
        self.assertEqual(self.state()["review"], {"due": 5, "postponed": False})
        self.assertEqual(len(self.items()), 5)

    def test_a_sitting_has_at_most_five_items_from_mixed_lessons(self):
        self.complete_three()
        self.clock.advance(days=2)
        items = self.items()
        self.assertEqual(len(items), 5)
        lessons = [i["lesson"] for i in items]
        for a, b in zip(lessons, lessons[1:]):
            self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(set(lessons)), 3)

    def test_the_rest_wait_for_the_next_sitting_when_the_app_reopens(self):
        self.complete_three()
        self.clock.advance(days=1)
        seen = []
        for _ in range(3):
            batch = self.items()
            for item in batch:
                seen.append(item["item"])
                self.answer_review(item["item"])
            self.assertEqual(self.items(), [])
            self.assertEqual(self.state()["review"]["due"], 0)
            self.reopen()
        expected = sum(len(self.lesson(lesson)["retrieval"]) for lesson in ("hook", "several-runs", "rules"))
        self.assertEqual(len(seen), expected)
        self.assertEqual(len(set(seen)), expected)
        self.assertEqual(self.items(), [])

    def test_the_same_sitting_is_shown_until_it_is_answered(self):
        self.complete_three()
        self.clock.advance(days=1)
        first = [i["item"] for i in self.items()]
        self.assertEqual(first, [i["item"] for i in self.items()])
        self.answer_review(first[0])
        self.assertEqual([i["item"] for i in self.items()], first[1:])
        self.assertEqual(self.state()["review"]["due"], 4)

    def test_review_views_carry_no_answers(self):
        self.complete_three()
        self.clock.advance(days=1)
        for item in self.items():
            self.assertEqual(set(item), {"item", "lesson", "lesson_title", "prompt", "options"})
            self.assertTrue(all(set(o) == {"id", "text"} for o in item["options"]))
        self.assertNotIn('"correct"', json.dumps(self.items()))

    def test_a_right_answer_moves_the_item_to_three_days(self):
        self.complete_hook()
        self.clock.advance(days=1)
        result = self.answer_review("hook:r-hook-1")
        self.assertTrue(result["passed"])
        entry = self.block()["review"]["items"]["hook:r-hook-1"]
        self.assertEqual((entry["stage"], entry["due"]), (1, self.clock() + 3 * DAY))
        self.assertNotIn("hook:r-hook-1", [i["item"] for i in self.items()])

    def test_the_full_climb_one_three_seven_then_retired(self):
        self.complete_hook()
        key = "hook:r-hook-1"
        self.clock.advance(days=1)
        self.answer_review(key)
        self.clock.advance(days=3, seconds=-1)
        self.reopen()
        self.assertNotIn(key, [i["item"] for i in self.items()])
        self.clock.advance(seconds=1)
        self.reopen()
        self.assertIn(key, [i["item"] for i in self.items()])
        self.answer_review(key)
        self.clock.advance(days=7, seconds=-1)
        self.reopen()
        self.assertNotIn(key, [i["item"] for i in self.items()])
        self.clock.advance(seconds=1)
        self.reopen()
        self.assertIn(key, [i["item"] for i in self.items()])
        self.answer_review(key)
        entry = self.block()["review"]["items"][key]
        self.assertTrue(entry["retired"])
        self.assertIsNone(entry["due"])
        self.clock.advance(days=365)
        self.reopen()
        self.assertNotIn(key, [i["item"] for i in self.items()])

    def test_a_wrong_answer_goes_back_to_one_day(self):
        self.complete_hook()
        key = "hook:r-hook-1"
        self.clock.advance(days=1)
        self.answer_review(key)
        self.clock.advance(days=3)
        self.reopen()
        result = self.answer_review(key, correct=False)
        self.assertFalse(result["passed"])
        entry = self.block()["review"]["items"][key]
        self.assertEqual((entry["stage"], entry["due"], entry["retired"]), (0, self.clock() + DAY, False))
        self.clock.advance(days=1)
        self.reopen()
        self.assertIn(key, [i["item"] for i in self.items()])

    def test_feedback_covers_only_the_option_that_was_chosen(self):
        self.complete_hook()
        self.clock.advance(days=1)
        retrieval = self.lesson("hook")["retrieval"][0]
        key = "hook:" + retrieval["id"]
        self.items()
        wrong = ch.wrong_option(retrieval)
        result = self.engine.review_answer(key, wrong)
        self.assertEqual(result, {"passed": False,
                                  "feedback": next(o["feedback"] for o in retrieval["options"] if o["id"] == wrong)})

    def test_a_right_answer_is_recorded_and_a_wrong_one_is_not(self):
        self.complete_hook()
        before = len(self.records())
        self.clock.advance(days=1)
        self.answer_review("hook:r-hook-1", correct=False)
        self.assertEqual(len(self.records()), before)
        self.answer_review("hook:r-hook-2")
        added = self.records()[before:]
        self.assertEqual(len(added), 1)
        self.assertEqual((added[0]["type"], added[0]["source"], added[0]["lesson"]), ("review", "review", "hook"))

    def test_bad_answers_are_refused(self):
        self.complete_hook()
        self.clock.advance(days=1)
        self.items()
        self.assert_code("review_unknown", self.engine.review_answer, "nope", "a")
        self.assert_code("review_unknown", self.engine.review_answer, None, "a")
        self.assert_code("review_unknown", self.engine.review_answer, "several-runs:r-generate-1", "a")
        self.assert_code("bad_answer", self.engine.review_answer, "hook:r-hook-1", "zzz")
        self.assert_code("bad_answer", self.engine.review_answer, "hook:r-hook-1", None)
        self.answer_review("hook:r-hook-1")
        self.assert_code("review_unknown", self.engine.review_answer, "hook:r-hook-1", "a")

    def test_an_item_that_is_not_due_cannot_be_answered(self):
        self.complete_hook()
        self.items()
        self.assert_code("review_unknown", self.engine.review_answer, "hook:r-hook-1", "a")

    def test_postpone_hides_the_queue_and_never_blocks_the_course(self):
        self.complete_three()
        self.clock.advance(days=1)
        self.assertEqual(self.state()["review"]["due"], 5)
        self.engine.review_postpone()
        self.assertEqual(self.state()["review"], {"due": 0, "postponed": True})
        self.assertEqual(self.engine.review_get(), {"review": {"items": [], "postponed": True}})
        self.assertEqual(self.state()["current_item"], {"kind": "step", "id": "build"})
        self.engine.step_start("build")
        self.assertEqual(self.state()["current_step"], "build")

    def test_postponed_items_come_back_the_next_time_the_app_opens(self):
        self.complete_three()
        self.clock.advance(days=1)
        self.engine.review_postpone()
        reopened = self.new_engine()
        self.assertEqual(reopened.get_state()["review"], {"due": 5, "postponed": False})
        self.assertEqual(len(reopened.review_get()["review"]["items"]), 5)

    def test_postponing_changes_no_schedule(self):
        self.complete_hook()
        self.clock.advance(days=1)
        before = json.dumps(self.block()["review"])
        self.engine.review_postpone()
        self.assertEqual(json.dumps(self.block()["review"]), before)

    def test_the_schedule_survives_a_restart(self):
        self.complete_hook()
        self.clock.advance(days=1)
        self.answer_review("hook:r-hook-1")
        reopened = self.new_engine()
        entry = reopened._lessons_block()["review"]["items"]["hook:r-hook-1"]
        self.assertEqual(entry["stage"], 1)
        self.clock.advance(days=1)
        self.assertEqual([i["item"] for i in reopened.review_get()["review"]["items"]], ["hook:r-hook-2"])

    def test_reviews_work_after_the_course_is_finished(self):
        while self.current() is not None:
            current = self.current()
            if current["kind"] == "lesson":
                self.finish(current["id"])
            else:
                self.mark_step_done(current["id"])
        self.assertIsNone(self.current())
        self.assertEqual(self.items(), [])
        self.clock.advance(days=1)
        batch = self.items()
        self.assertEqual(len(batch), 5)
        self.answer_review(batch[0]["item"])
        self.assertEqual(self.state()["review"]["due"], 4)

    def test_skipped_lessons_schedule_no_reviews(self):
        self.mark_skipped("several-runs")
        self.complete("mission", "hook")
        self.finish_before("generate")
        self.assertEqual(self.status_of("several-runs"), "skipped")
        self.assertFalse([k for k in self.block()["review"]["items"] if k.startswith("several-runs:")])

    def test_an_item_whose_question_left_the_content_is_ignored(self):
        self.complete_hook()
        self.block()["review"]["items"]["gone:r-1"] = entry(lesson="gone", item="r-1", due=0)
        self.block()["review"]["items"]["hook:r-old"] = entry(lesson="hook", item="r-old", due=0)
        self.clock.advance(days=1)
        self.assertEqual(sorted(i["item"] for i in self.items()), ["hook:r-hook-1", "hook:r-hook-2"])

    def test_the_clock_is_injected_and_defaults_to_real_time(self):
        import time
        from eval_coach.engine import Engine
        self.assertIs(self.engine._clock, self.clock)
        default = Engine(self.tmp / "default-home", self.terminal, poll_interval=0.01, lessons=self.course)
        self.addCleanup(default.shutdown)
        self.assertIs(default._clock, time.time)

    def test_the_order_of_options_in_a_review_matches_the_participants_seed(self):
        self.complete_hook()
        self.clock.advance(days=1)
        first = [[o["id"] for o in i["options"]] for i in self.items()]
        again = [[o["id"] for o in i["options"]] for i in self.new_engine().review_get()["review"]["items"]]
        self.assertEqual(first, again)


def ch_activity(course, activity_id):
    for lesson in course.data["lessons"]:
        for activity in lesson["activities"]:
            if activity["id"] == activity_id:
                return activity
    raise KeyError(activity_id)


if __name__ == "__main__":
    unittest.main()
