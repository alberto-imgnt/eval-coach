"""Tasks 4.26 and 4.27: every "If something breaks" row of the two session handouts is placed in the app or
recorded as not applicable, and the Windows line-ending guidance is where label checks fail."""
from __future__ import annotations

import json
import re
import unittest

import helpers
from helpers import SOURCE

from eval_coach import resources
from eval_coach.engine import _deep_merge

HANDOUTS = SOURCE / "handouts"
SKILL = "cannot read the skill file"

BOTH = ("script", "promptfoo")
NORTHWIND_ENTRY = ("fixtures", BOTH, "Practice task")


def at(step, tracks, text):
    """One placement: the step, the track(s) it must be present on, and a phrase in the entry's problem text."""
    return [(step, track, text) for track in ([tracks] if isinstance(tracks, str) else tracks)]


def many(*placements):
    return [p for group in placements for p in group]


# Each source row is keyed by the Problem text exactly as the handout prints it. `place` lists where the app
# holds it; `na` is the reason it is not applicable. Exactly one of the two is set.
COVERAGE = [
    {"room": "A", "problem": "The agent cannot read the skill file",
     "place": many(*(at(s, "script", SKILL) for s in ("build", "fixtures", "readback", "key", "baseline"))),
     "note": "The fix step's line does not ask the CLI to read a skill file, so it has no such entry."},
    {"room": "A", "problem": "`python` not found",
     "place": many(*(at(s, "script", "python was not found") for s in ("build", "readback", "fix", "baseline"))),
     "note": "Preflight finds the app's own Python. This covers the CLI running check.py; the app's buttons never need it."},
    {"room": "A", "problem": "`check.py` crashes",
     "place": many(at("build", "script", "check.py crashes"), at("fix", "script", "check.py crashes"),
                   at("baseline", "script", "check.py crashes"), at("run", "script", "The run reports an error"))},
    {"room": "A", "problem": "The agent wants to call an AI model inside the script",
     "place": many(at("build", "script", "call an AI model"), at("fix", "script", "AI model call"),
                   at("baseline", "script", "call an AI model"))},
    {"room": "A", "problem": "The exit code is not 0",
     "place": many(at("build", "script", "The exit code is 1"), at("run", "script", "The exit code is 1"),
                   at("baseline", "script", "The exit code is not 0"))},
    {"room": "A", "problem": "Your fixtures look nothing like your task",
     "place": at("fixtures", BOTH, "look nothing like your task")},
    {"room": "A", "problem": "Using the Northwind example and the fixtures step gave nothing useful",
     "place": at(*NORTHWIND_ENTRY), "note": "Also an in-app button: POST /api/step/use-example-fixtures (task 4.28)."},

    {"room": "B", "problem": "The agent cannot read the skill file",
     "place": many(*(at(s, "promptfoo", SKILL) for s in ("build", "fixtures", "fixtures-config", "readback", "key",
                                                         "baseline", "live")))},
    {"room": "B", "problem": "`npx` is slow the first time",
     "place": many(at("build", "promptfoo", "first look is slow"), at("run", "promptfoo", "run takes a long time")),
     "note": "The app runs the promptfoo that preflight already downloaded, so only a slow disk is left to explain."},
    {"room": "B", "problem": "Config error",
     "place": many(*(at(s, "promptfoo", "config has an error") for s in ("build", "fix", "baseline", "live")),
                   at("readback", "promptfoo", "config reports an error"),
                   at("run", "promptfoo", "The run reports an error"))},
    {"room": "B", "problem": "The agent adds an `llm-rubric` or asks for an API key",
     "place": many(*(at(s, "promptfoo", "llm-rubric") for s in ("build", "fixtures-config", "fix", "baseline", "live")))},
    {"room": "B", "problem": "Live mode says \"Not logged in\" or \"No agent CLI found\"",
     "place": at("live", "promptfoo", "Not logged in"),
     "note": "Live mode is built (task 4.18, decision D2): an optional step after the baseline."},
    {"room": "B", "problem": "Every test shows as failed",
     "place": many(*(at(s, "promptfoo", "Every test shows as failed") for s in ("build", "run", "fix", "baseline", "live")))},
    {"room": "B", "problem": "A label check fails on a file that looks right",
     "place": many(*(at(s, BOTH, "label check fails") for s in ("build", "readback", "run", "fix")))},
    {"room": "B", "problem": "Using the Northwind example and the fixtures step gave nothing useful",
     "place": at(*NORTHWIND_ENTRY), "note": "Also an in-app button: POST /api/step/use-example-fixtures (task 4.28)."},
]


def effective_troubleshooting(steps, step, track):
    """The list a participant on `track` sees: the track's own list replaces the shared one."""
    base = steps[step]
    override = base.get("tracks", {}).get(track) if track != "script" else None
    if not override:
        return base["troubleshooting"]
    merged = dict(base)
    for key, value in override.items():
        merged[key] = _deep_merge(base.get(key), value)
    return merged["troubleshooting"]


def handout_problems(name):
    """The Problem column of the handout's "If something breaks" table, or None when the source is not here."""
    path = HANDOUTS / name
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").split("## If something breaks", 1)[1]
    rows = [line for line in text.splitlines() if line.startswith("|")][2:]
    return [row.strip("|").split(" | ")[0].strip() for row in rows]


def missing_placements(steps):
    """Every (room, source problem, step, track, phrase) that the table promises and steps.json does not hold."""
    missing = []
    for row in COVERAGE:
        for step, track, phrase in row.get("place", []):
            if step not in steps:
                missing.append((row["room"], row["problem"], step, track, phrase))
                continue
            problems = [t["problem"] for t in effective_troubleshooting(steps, step, track)]
            if not [p for p in problems if phrase in p]:
                missing.append((row["room"], row["problem"], step, track, phrase))
    return missing


class Coverage(unittest.TestCase):
    def setUp(self):
        self.steps = json.loads(resources.read_text("content/steps.json"))["steps"]

    def test_each_source_row_is_in_the_table_exactly_once(self):
        self.assertEqual(len([r for r in COVERAGE if r["room"] == "A"]), 7)
        self.assertEqual(len([r for r in COVERAGE if r["room"] == "B"]), 8)
        for room, name in (("A", "room-a-script-handout.md"), ("B", "room-b-promptfoo-handout.md")):
            source = handout_problems(name)
            ours = [r["problem"] for r in COVERAGE if r["room"] == room]
            with self.subTest(source=name):
                self.assertEqual(len(set(ours)), len(ours))
                if source is None:
                    self.skipTest("the session handouts are not on this computer")
                self.assertEqual(source, ours)

    def test_every_row_is_placed_or_not_applicable_with_a_reason(self):
        for row in COVERAGE:
            with self.subTest(problem=row["problem"], room=row["room"]):
                self.assertNotEqual(bool(row.get("place")), bool(row.get("na")), "place it or say why not, not both")
                if row.get("na"):
                    self.assertGreater(len(row["na"]), 20)

    def test_every_placement_is_in_steps_json(self):
        self.assertEqual(missing_placements(self.steps), [])

    def test_a_missing_entry_makes_the_check_fail(self):
        fixtures = self.steps["fixtures"]["troubleshooting"]
        fixtures[:] = [t for t in fixtures if "Practice task" not in t["problem"]]
        missing = missing_placements(self.steps)
        self.assertEqual({(m[2], m[3]) for m in missing}, {("fixtures", "script"), ("fixtures", "promptfoo")})
        self.assertEqual({m[1] for m in missing},
                         {"Using the Northwind example and the fixtures step gave nothing useful"})
        build = self.steps["build"]["tracks"]["promptfoo"]["troubleshooting"]
        build[:] = [t for t in build if "label check fails" not in t["problem"]]
        self.assertIn(("B", "A label check fails on a file that looks right", "build", "promptfoo", "label check fails"),
                      missing_placements(self.steps))

    def test_the_fix_step_has_no_skill_file_entry_because_it_reads_none(self):
        fix = json.loads(resources.read_text("content/steps.json"))["steps"]["fix"]
        for line in (fix["line"], fix["tracks"]["promptfoo"]["line"]):
            self.assertNotIn("SKILL.md", line)

    def test_no_entry_is_listed_twice_in_one_step(self):
        for step_id, step in self.steps.items():
            for track in BOTH:
                problems = [t["problem"] for t in effective_troubleshooting(self.steps, step_id, track)]
                with self.subTest(step=step_id, track=track):
                    self.assertEqual(len(problems), len(set(problems)))

    def test_every_new_entry_is_plain_and_ends_with_a_next_action(self):
        for row in COVERAGE:
            for step, track, phrase in row.get("place", []):
                for entry in effective_troubleshooting(self.steps, step, track):
                    if phrase in entry["problem"]:
                        with self.subTest(step=step, track=track, problem=entry["problem"][:40]):
                            self.assertRegex(entry["fix"].strip(), r'[.!]"?$')
                            self.assertNotRegex(entry["fix"] + entry["problem"],
                                                r"(?i)\b(contact|facilitator|presenter|handout|neighbou?r|room|clock)\b")

    def test_all_fifteen_rows_are_placed_and_none_is_not_applicable(self):
        placed = [r for r in COVERAGE if r.get("place")]
        self.assertEqual((len(placed), len(COVERAGE) - len(placed)), (15, 0))


class LineEndings(unittest.TestCase):
    """Task 4.27: content only. The app does not detect line endings."""

    def setUp(self):
        self.steps = json.loads(resources.read_text("content/steps.json"))["steps"]

    def test_the_guidance_is_where_label_checks_fail_on_both_tracks(self):
        for step in ("build", "readback", "fix", "run"):
            for track in BOTH:
                entries = [t for t in effective_troubleshooting(self.steps, step, track) if "label check fails" in t["problem"]]
                with self.subTest(step=step, track=track):
                    self.assertEqual(len(entries), 1)
                    fix = entries[0]["fix"]
                    self.assertIn("\\r\\n", fix)
                    self.assertIn("Windows", fix)
                    self.assertIn("Allow for \\r\\n line endings in the label checks. Do not change any threshold.", fix)
                    self.assertNotIn("loosen", fix.lower())

    def test_the_run_step_has_no_cli_so_it_points_to_the_next_step(self):
        for track in BOTH:
            fix = [t for t in effective_troubleshooting(self.steps, "run", track) if "label check fails" in t["problem"]][0]["fix"]
            self.assertIn("In the next step", fix)
            self.assertIn("classify", fix)

    def test_other_steps_do_not_carry_the_guidance(self):
        for step in ("generate", "fixtures", "fixtures-config", "predict", "key", "baseline"):
            for track in BOTH:
                with self.subTest(step=step, track=track):
                    self.assertFalse([t for t in effective_troubleshooting(self.steps, step, track)
                                      if "label check fails" in t["problem"]])


class ExampleFixturesContent(unittest.TestCase):
    def setUp(self):
        self.steps = json.loads(resources.read_text("content/steps.json"))["steps"]

    def test_the_northwind_entry_is_on_both_tracks_and_says_it_is_only_for_the_example(self):
        for track in BOTH:
            entries = [t for t in effective_troubleshooting(self.steps, "fixtures", track) if "Practice task" in t["problem"]]
            with self.subTest(track=track):
                self.assertEqual(len(entries), 1)
                fix = entries[0]["fix"]
                self.assertIn("Use the example's fixtures", fix)
                self.assertIn("only with the Practice task", fix)
                self.assertIn("writes no answer key", fix)
                self.assertIn("Check my work", fix)

    def test_the_screen_text_explains_whose_fixtures_these_are(self):
        ui = self.steps["fixtures"]["ui"]
        self.assertIn("Practice task's own fixtures", ui["example_blurb"])
        self.assertIn("test cases only", ui["example_blurb"])
        self.assertIn("No answer key is written now", ui["example_blurb"])
        self.assertTrue(ui["example_button"])

    def test_every_refusal_ends_with_a_next_action(self):
        messages = json.loads(resources.read_text("content/steps.json"))["messages"]
        for key in [k for k in messages if k.startswith("example_fixtures_")]:
            with self.subTest(key=key):
                self.assertRegex(messages[key].strip(), r"[.]$")
                self.assertRegex(messages[key], r"(?i)\b(press|confirm|close|use|then)\b")


if __name__ == "__main__":
    unittest.main()
