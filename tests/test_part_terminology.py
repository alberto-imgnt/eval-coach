"""A part of the series is called a Part, never a session (AGENTS.md rule 10; spec part-terminology)."""
from __future__ import annotations

import json
import re
import unittest

import helpers  # noqa: F401
from helpers import ROOT

APP = ROOT / "app" / "eval_coach"
CONTENT = APP / "content"
SESSION = re.compile(r"\bsessions?\b", re.I)
# Strings that use "session" for something other than a part of the series. Each entry is an exact string, so a new
# one shows up in review. Today there is none: the CLI wording in preflight.json avoids the word.
ALLOWED = ()
JS_FILES = (APP / "web" / "js" / "views.js", APP / "web" / "js" / "markdown.js", APP / "web" / "js" / "series.js",
            APP / "web" / "js" / "part-steps.js")
# criteria-steps.js is Part 2's panel file; it is checked as soon as it exists.
JS_FILES += tuple(p for p in (APP / "web" / "js" / "criteria-steps.js",) if p.is_file())
NORTHWIND = (APP / "kit" / "northwind" / "northwind-prompt-v0.md",
             APP / "kit" / "northwind" / "northwind-test-cases-reference.md")


def walk(node, where=""):
    """Every string value in a JSON-shaped object, with the path to it."""
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{where}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{where}[{i}]")


class PartNotSession(unittest.TestCase):
    def test_the_allow_list_stays_exact_and_empty(self):
        self.assertEqual(ALLOWED, ())

    def test_no_content_string_says_session(self):
        hits = []
        for path in sorted(CONTENT.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for where, text in walk(data):
                if SESSION.search(text) and text not in ALLOWED:
                    hits.append(f"{path.name}{where}: {text[:80]}")
        self.assertEqual(hits, [])

    def test_the_northwind_catch_up_files_say_part(self):
        for path in NORTHWIND:
            with self.subTest(file=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(SESSION.search(text))
                self.assertRegex(text, r"your own Part [12] ")

    def test_the_interface_code_carries_no_part_title_or_session_word(self):
        for path in JS_FILES:
            with self.subTest(file=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(SESSION.search(text))
                self.assertNotIn("Running evals and baseline", text)
                self.assertNotIn("Structured prompting", text)

    def test_interface_copy_never_calls_lessons_and_steps_parts_of_the_course(self):
        ui = json.loads((CONTENT / "lesson-ui.json").read_text(encoding="utf-8"))
        for where, text in walk(ui):
            with self.subTest(where=where):
                self.assertIsNone(re.search(r"parts? of the course|parts complete|earlier parts", text, re.I), text)
        for path in JS_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("parts complete", text)
            self.assertNotIn("steps complete", text)

    def test_the_part_strings_come_from_content(self):
        ui = json.loads((CONTENT / "lesson-ui.json").read_text(encoding="utf-8"))["ui"]
        self.assertEqual(ui["brand_sub"], "Part 3 \u00b7 Running evals and baseline")
        self.assertEqual(ui["map_title"], "Part {n}: ")
        self.assertEqual(ui["map_aria"], "Course map. You are at Part {n} of {total}.")

    def test_the_part_one_and_two_strings_come_from_their_own_series_entry(self):
        series = json.loads((CONTENT / "series.json").read_text(encoding="utf-8"))
        for part_id, brand in (("part-1", "Part 1 \u00b7 Structured prompting"),
                               ("part-2", "Part 2 \u00b7 Defining evaluation criteria")):
            with self.subTest(part=part_id):
                part = next(p for p in series["parts"] if p["id"] == part_id)
                self.assertEqual(part["ui"]["brand_sub"], brand)
                self.assertEqual(part["ui"]["map_title"], "Part {n}: ")
                self.assertEqual(part["ui"]["map_aria"], "Course map. You are at Part {n} of {total}.")

    def test_the_interface_code_carries_no_part_two_title(self):
        for path in JS_FILES:
            with self.subTest(file=path.name):
                self.assertNotIn("Defining evaluation criteria", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
