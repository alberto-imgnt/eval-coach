"""Shared helpers for the course tests: the bundled content, answers built from it, and a fake clock."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import GOLDEN, FakeTerminal

from eval_coach import lessons as lesson_lib
from eval_coach import project, resources, state
from eval_coach.engine import Engine
from eval_coach.state import COURSE

DAY = 86400
CHECKER = (GOLDEN / "reference-check.py").read_text(encoding="utf-8")


def bundled_data():
    """A fresh copy of content/lessons.json that a test may change."""
    return json.loads(resources.read_text("content/lessons.json"))


def parts_data():
    """[(Part, lessons data)] for every registered Part, read from each Part's own lessons file."""
    return [(part, json.loads(resources.read_text(part.lessons_file))) for part in state.PARTS]


def bundled_glossary():
    return json.loads(resources.read_text("content/glossary.json"))


def bundled_course():
    return lesson_lib.load_bundled()


# The bundled course has no `order` or `cli_demo` activity any more, but the engine still supports both.
# These copies of the old activities are injected into a copy of the bundled course to keep those paths tested.
DEMO_ACTIVITY = {
    "id": "rules-demo",
    "type": "cli_demo",
    "line": "Read skills/build-eval-script/SKILL.md and follow it in build mode on test-cases.md.",
    "files": [
        {"name": "test-cases.md", "source": "kit:lessons/demo/test-cases.md"},
        {"name": "output.txt", "source": "kit:lessons/demo/output.txt"},
        {"name": "skills/build-eval-script/SKILL.md", "source": "kit:skills/build-eval-script/SKILL.md"},
    ],
    "run_args": ["output.txt"],
}
ORDER_ACTIVITY = {
    "id": "loop-order",
    "type": "order",
    "prompt": "Put the five links of the loop in order, starting from the first thing you do.",
    "items": [
        {"id": "prompt", "text": "Prompt: your prompt and rough notes go to a new chat"},
        {"id": "answer", "text": "Answer: the AI writes one answer"},
        {"id": "file", "text": "File: the answer is saved as a file"},
        {"id": "checker", "text": "Checker: you run the checker on the saved file"},
        {"id": "verdict", "text": "Verdict: PASS, FAIL or NOT CHECKED for each criterion"},
    ],
    "feedback_right": "That is the loop. You will repeat it, unchanged, every time you test a prompt.",
    "feedback_wrong": "Not yet. Ask what each link needs to exist before it can happen.",
}
DEMO_LESSON = "rules"  # the only lesson that may hold a cli_demo
ORDER_LESSON = "several-runs"


def demo_course():
    """The bundled course plus a cli_demo activity first in `rules` and an order activity first in `several-runs`."""
    data = bundled_data()
    by_id = {lesson["id"]: lesson for lesson in data["lessons"]}
    by_id[DEMO_LESSON]["activities"].insert(0, clone(DEMO_ACTIVITY))
    by_id[ORDER_LESSON]["activities"].insert(0, clone(ORDER_ACTIVITY))
    return lesson_lib.Course.from_data(data, lesson_lib.validate_glossary(bundled_glossary()))


def clone(data):
    return copy.deepcopy(data)


class FakeClock:
    """An injected clock. Calling it returns the current fake time in seconds."""

    def __init__(self, start=1_800_000_000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, days=0, seconds=0):
        self.now += days * DAY + seconds


def correct_option(item):
    return next(o["id"] for o in item["options"] if o["correct"])


def wrong_option(item):
    return next(o["id"] for o in item["options"] if not o["correct"])


def correct_answer(activity):
    """The body of a passing /api/lesson/answer for this activity (None when the app decides alone)."""
    kind = activity["type"]
    if kind == "choice":
        return {"option": correct_option(activity)}
    if kind == "order":
        return {"order": [item["id"] for item in activity["items"]]}
    if kind == "sort":
        return {"placements": {item["id"]: item["bucket"] for item in activity["items"]}}
    if kind == "rule_lab":
        return {"cases": {lesson_lib.case_key(c): c["expected"] for c in activity["cases"]}}
    if kind == "reflection":
        return {"text": " ".join(["thinking"] * activity["min_words"])}
    if kind in ("cli_compare", "cli_practice"):
        return {"option": correct_option(activity["question"])}
    return None


def wrong_answer(activity):
    """A well-formed answer that does not pass."""
    kind = activity["type"]
    if kind == "choice":
        return {"option": wrong_option(activity)}
    if kind == "order":
        ids = [item["id"] for item in activity["items"]]
        return {"order": ids[1:] + ids[:1]}
    if kind == "sort":
        buckets = [b["id"] for b in activity["buckets"]]
        placements = {item["id"]: item["bucket"] for item in activity["items"]}
        first = activity["items"][0]
        placements[first["id"]] = next(b for b in buckets if b != first["bucket"])
        return {"placements": placements}
    if kind == "rule_lab":
        cases = {lesson_lib.case_key(c): c["expected"] for c in activity["cases"]}
        key = next(iter(cases))
        cases[key] = "fail" if cases[key] == "pass" else "pass"
        return {"cases": cases}
    if kind == "reflection":
        return {"text": "too short"}
    if kind in ("cli_compare", "cli_practice"):
        return {"option": wrong_option(activity["question"])}
    return None


def walk_keys(value):
    """Every dict key anywhere inside a JSON-shaped value."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


class CourseBase(unittest.TestCase):
    """An engine with the bundled course, a fake terminal, a fake clock and preflight already passed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-course-"))
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        self.terminal = FakeTerminal()
        self.clock = FakeClock()
        self.course = self.build_course()
        helpers.write_passed_preflight(self.home)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.engine = self.new_engine()
        self.paths = None

    def build_course(self):
        return bundled_course()

    def new_engine(self, lessons=True, demo=True):
        engine = helpers.make_engine(self.home, self.terminal, poll_interval=0.01,
                                     lessons=self.course if lessons else None, clock=self.clock, demo=demo)
        self.addCleanup(engine.shutdown)
        return engine

    def setup_project(self):
        self.engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.paths = project.Paths(self.home, self.project)

    def lesson(self, lesson_id):
        return self.course.get(lesson_id)

    def state(self):
        return self.engine.get_state()

    def status_of(self, item_id):
        return next(i["status"] for i in self.state()["course"] if i["id"] == item_id)

    def current(self):
        return self.state()["current_item"]

    def block(self):
        return self.engine._lessons_block()

    def records(self):
        return list(self.block()["records"])

    def answer(self, lesson_id, activity_id, body):
        return self.engine.lesson_answer(lesson_id, activity_id, body)

    def pass_activity(self, lesson_id, activity):
        if activity["type"] == "cli_compare":
            self.paths.hook_runs.mkdir(parents=True, exist_ok=True)
            for n in range(1, activity["runs"] + 1):
                self.paths.hook_run_file(n).write_text(f"Score {n}: pass. Reasoning for run {n}.", encoding="utf-8")
        elif activity["type"] == "cli_practice":
            self.save_practice(activity)
        elif activity["type"] == "cli_demo":
            self.write_demo_checker()
            return self.answer(lesson_id, activity["id"], {})
        return self.answer(lesson_id, activity["id"], correct_answer(activity))

    def save_practice(self, activity, text="A saved practice answer."):
        self.paths.practice_runs.mkdir(parents=True, exist_ok=True)
        self.paths.practice_output(activity["id"]).write_text(text, encoding="utf-8")

    def write_demo_checker(self, source=CHECKER):
        project.prepare_demo(self.paths)
        (self.paths.demo_work / "check.py").write_text(source, encoding="utf-8")

    def finish(self, lesson_id):
        for activity in self.lesson(lesson_id)["activities"]:
            self.pass_activity(lesson_id, activity)
        self.engine.lesson_complete(lesson_id)

    def mark_skipped(self, lesson_id):
        self.engine._lesson_entry(lesson_id)["status"] = "skipped"
        self.engine._save_lessons()

    def mark_step_done(self, step):
        self.engine.progress["done"].append(step)
        self.engine._save()

    def finish_before(self, item_id):
        """Finish every lesson and mark every step done that comes before item_id in the course."""
        for kind, item in COURSE:
            if item == item_id:
                return
            if kind == "step":
                self.mark_step_done(item)
            elif self.status_of(item) == "active":
                self.finish(item)

    def assert_code(self, code, fn, *args, **kwargs):
        from eval_coach.engine import EngineError
        with self.assertRaises(EngineError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception


class DemoCourseBase(CourseBase):
    """CourseBase over the bundled course with the old `order` and `cli_demo` activities injected (see demo_course)."""

    def build_course(self):
        return demo_course()
