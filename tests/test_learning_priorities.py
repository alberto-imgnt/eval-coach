"""Learning-priority alignment (`docs/CONTENT-RULES.md` "Learning priorities").

Tier 1: the participant explains evaluation to a non-technical reader and to a technical one.
Tier 2: the whole series workflow is taught.
Tier 3: Stage 3 is named once, in the last lesson only, and never as a requirement or a set of submission steps.
"""
from __future__ import annotations

import json
import re
import unittest

import course_helpers as ch
import helpers  # noqa: F401
from helpers import ROOT

from eval_coach import lessons as L
from eval_coach import resources

STAGE_THREE = re.compile(r"stage\s*3|certif", re.I)
NOTE_LESSON = "baseline-why"
NOTE_HEADING = "**How this fits the Stage 3 certification.**"
# The three artifacts Stage 3 asks for (the Prompt, the Evaluations and the Log; see the local Stage 3 notes).
ARTIFACTS = ("Prompt", "Evaluations", "Log")
NOTE_MAX_WORDS = 150
SUBMISSION_STEPS = re.compile(r"https?://|@|\bupload\b|\bsubmission form\b|\bsend (it|them) to\b|\bhow to submit\b", re.I)
PLAN = ROOT / "docs" / "local" / "IMPLEMENTATION-PLAN.md"
CONTENT = ROOT / "app" / "eval_coach" / "content"
PART_NAMES = ("Structured prompting", "Defining evaluation criteria", "Running evals and baseline",
              "Iterating with evaluation-driven development", "Load-bearing audit and packaging", "Your own task")


def strings(node):
    """Every string a participant could read inside one lesson, in any field."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def lesson_of(data, lesson_id):
    return next(x for x in data["lessons"] if x["id"] == lesson_id)


def activity_ids(lesson):
    return [a["id"] for a in lesson["activities"]]


def note_of(data):
    """The Stage 3 note: everything after its heading in the last lesson."""
    return lesson_of(data, NOTE_LESSON)["body"].split(NOTE_HEADING, 1)[1]


class TierOneExplainIt(unittest.TestCase):
    def setUp(self):
        self.data = ch.bundled_data()

    def test_plain_words_activities_exist_in_the_three_lessons(self):
        expected = {"hook": "hook-explain", "rules": "build-explain", "baseline-why": "baseline-explain"}
        for lesson_id, activity_id in expected.items():
            with self.subTest(lesson=lesson_id):
                lesson = lesson_of(self.data, lesson_id)
                found = [a for a in lesson["activities"] if a["id"] == activity_id]
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0]["type"], "choice")
                self.assertEqual(sum(1 for o in found[0]["options"] if o["correct"]), 1)

    def test_the_baseline_lesson_asks_for_a_written_explanation(self):
        lesson = lesson_of(self.data, NOTE_LESSON)
        written = [a for a in lesson["activities"] if a["id"] == "baseline-explain-write"]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["type"], "reflection")
        self.assertIn("never used AI", written[0]["prompt"])

    def test_a_technical_audience_item_is_in_the_rules_lesson(self):
        lesson = lesson_of(self.data, "rules")
        self.assertIn("choices-explain-tech", activity_ids(lesson))

    def test_the_boundary_of_what_a_rule_can_check_is_stated(self):
        body = lesson_of(self.data, "rules")["body"]
        self.assertIn("What a rule cannot check", body)
        glossary = json.loads((CONTENT / "glossary.json").read_text(encoding="utf-8"))
        entry = next(t for t in glossary["terms"] if t["term"] == "NOT CHECKED")
        self.assertIn("never hands such a criterion to an AI grader", entry["meaning"])

    def test_new_activities_match_in_word_count(self):
        new_ids = {"hook-explain", "build-explain", "baseline-explain", "choices-explain-tech"}
        seen = set()
        for lesson in self.data["lessons"]:
            for activity in lesson["activities"]:
                if activity["id"] in new_ids:
                    seen.add(activity["id"])
                    counts = {L.word_count(o["text"]) for o in activity["options"]}
                    self.assertEqual(len(counts), 1, activity["id"])
        self.assertEqual(seen, new_ids)


class SeriesIntentFraming(unittest.TestCase):
    """Spec series-intent-framing: purpose, why it matters, the map, the limits of a score and the own-work bridge."""

    def setUp(self):
        self.data = ch.bundled_data()
        self.mission = lesson_of(json.loads(resources.read_text("content/part-1-lessons.json")), "p1-mission")
        self.baseline = lesson_of(self.data, NOTE_LESSON)

    def test_the_mission_states_the_purpose_and_neither_blind_trust_nor_blind_distrust(self):
        body = self.mission["body"]
        self.assertIn("judge the work AI gives you", body)
        self.assertIn("because you checked it", body)
        self.assertIn("blind trust or blind distrust", body)

    def test_the_mission_gives_the_three_reasons_it_matters(self):
        body = self.mission["body"]
        self.assertIn("sounds sure of itself even when it is wrong", body)
        self.assertIn("only an opinion until you measure it", body)
        self.assertIn("Answers change from one try to the next", body)

    def test_the_mission_names_the_method_in_one_line(self):
        self.assertIn("ask clearly, know what you need, turn it into rules, score the result, improve, and keep a record.",
                      self.mission["body"])

    def test_the_mission_stays_one_page_with_no_questions(self):
        self.assertEqual(self.mission["activities"], [])
        self.assertEqual(self.mission["retrieval"], [])
        self.assertNotIn("How you will work", self.mission["body"])
        self.assertNotIn("What to bring", self.mission["body"])

    def test_the_series_map_is_the_only_list_of_the_parts(self):
        for lesson_id, data in (("mission", self.data), ("p1-mission", json.loads(resources.read_text("content/part-1-lessons.json")))):
            body = lesson_of(data, lesson_id)["body"]
            with self.subTest(lesson=lesson_id):
                self.assertNotIn("you-are-here", body)
                self.assertIsNone(re.search(r"(?m)^(done|here|next) \| \d \|", body))
        titles = [p["title"] for p in json.loads(resources.read_text("content/series.json"))["parts"]]
        self.assertEqual(titles, list(PART_NAMES))

    def test_the_baseline_lesson_says_what_a_score_does_and_does_not_tell_you(self):
        body = self.baseline["body"]
        self.assertIn("does not guarantee every future answer", body)
        self.assertIn("NOT CHECKED", body)

    def test_the_baseline_lesson_distinguishes_a_measured_gain_from_other_benefits(self):
        body = self.baseline["body"]
        self.assertIn("Part 4", body)
        self.assertIn("Part 5", body)
        self.assertIn("no measured gain on these rules", body)
        self.assertIn("a simpler prompt can be worth keeping at the same score", body)
        self.assertIn("qualities no rule checks", body)
        self.assertIn("A total can hide a rule that got worse", body)
        self.assertIn("lost coverage, not a gain", body)
        self.assertIn("before you see its score", body)

    def test_lessons_steps_and_glossary_avoid_unwarranted_claims_about_scores(self):
        banned = re.compile(r"\b(?:did not help|no benefit|did better|pick your best answer)\b", re.I)
        for path in sorted(CONTENT.glob("*.json")):
            if not path.stem.endswith(("lessons", "steps", "glossary")):
                continue
            with self.subTest(file=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                for text in strings(data):
                    self.assertNotRegex(" ".join(text.split()), banned)

    def test_the_baseline_lesson_points_the_method_at_the_participants_own_work(self):
        body = self.baseline["body"]
        for example in ("a message after a client call", "a summary of a long thread", "a job description"):
            self.assertIn(example, body)
        for condition in ("repeats", "has clear requirements", "can be checked by rules"):
            self.assertIn(condition, body)
        self.assertIn("In Part 6", body)
        self.assertIn("Practice task is practice only", body)

    def test_part_six_is_informational_and_points_to_office_hours_and_the_air_discussion(self):
        # The one allowed pointer to people (AGENTS.md rule 10 exception); the lesson gives no exercise for it.
        body = self.baseline["body"]
        self.assertIn("It is live: bring ideas to office hours or the AIR discussion", body)
        self.assertIn("office hours", body)
        self.assertIn("AIR discussion", body)

    def test_no_new_activity_holds_back_continue_in_the_baseline_lesson(self):
        self.assertEqual(activity_ids(self.baseline),
                         ["baseline-total", "baseline-settled", "baseline-reflect", "baseline-explain",
                          "baseline-explain-write", "baseline-stage3"])
        self.assertTrue(all(a["type"] in ("choice", "reflection") for a in self.baseline["activities"]))


class TierTwoWorkflow(unittest.TestCase):
    def setUp(self):
        self.data = ch.bundled_data()

    def test_the_mission_lesson_teaches_the_whole_series_without_questions(self):
        mission = lesson_of(self.data, "mission")
        self.assertEqual(mission["activities"], [])
        self.assertEqual(mission["retrieval"], [])
        self.assertNotIn("six-part series", mission["body"])
        self.assertNotIn("you-are-here", mission["body"])

    def test_the_baseline_lesson_says_what_the_next_two_parts_do(self):
        body = lesson_of(self.data, NOTE_LESSON)["body"]
        self.assertIn("Part 4", body)
        self.assertIn("Part 5", body)


class TierThreePartOne(unittest.TestCase):
    """Part 1 carries one optional note, in its last lesson, and it names the Prompt (spec learning-priority-order)."""

    def setUp(self):
        self.data = json.loads((CONTENT / "part-1-lessons.json").read_text(encoding="utf-8"))

    def test_the_part_one_note_names_the_prompt(self):
        body = lesson_of(self.data, "p1-benefits")["body"]
        note = body.split("**Stage 3 note (optional).**", 1)[1]
        self.assertRegex(note, r"\bPrompt\b")
        self.assertIsNone(SUBMISSION_STEPS.search(note))
        self.assertLessEqual(len(note.split()), 60)

    def test_stage_three_is_named_only_in_the_part_one_note(self):
        for lesson in self.data["lessons"]:
            if lesson["id"] == "p1-benefits":
                continue
            with self.subTest(lesson=lesson["id"]):
                self.assertIsNone(STAGE_THREE.search("\n".join(strings(lesson))))
        for group in ("placement", "step_checks"):
            self.assertIsNone(STAGE_THREE.search("\n".join(strings(self.data.get(group, [])))), group)
        steps = (CONTENT / "part-1-steps.json").read_text(encoding="utf-8")
        self.assertIsNone(STAGE_THREE.search(steps))

    def test_part_one_lessons_have_the_same_words_as_the_other_parts_for_the_content_rules(self):
        for lesson in self.data["lessons"]:
            self.assertNotRegex("\n".join(strings(lesson)), r"(?i)\bsessions?\b")


class TierThreePartTwo(unittest.TestCase):
    """Part 2 carries one optional note, in its last lesson, and it names the Evaluations (spec learning-priority-order)."""

    NOTE_HEADING = "**Stage 3 note (optional).**"

    def setUp(self):
        self.data = json.loads((CONTENT / "part-2-lessons.json").read_text(encoding="utf-8"))

    def test_the_part_two_note_names_the_evaluations(self):
        body = lesson_of(self.data, "p2-testfile")["body"]
        note = body.split(self.NOTE_HEADING, 1)[1]
        self.assertRegex(note, r"\bEvaluations\b")
        self.assertIn("Scripts, promptfoo files and written test cases are all accepted", note)
        self.assertIsNone(SUBMISSION_STEPS.search(note))
        self.assertLessEqual(len(note.split()), 60)

    def test_stage_three_is_named_only_in_the_part_two_note(self):
        for lesson in self.data["lessons"]:
            if lesson["id"] == "p2-testfile":
                continue
            with self.subTest(lesson=lesson["id"]):
                self.assertIsNone(STAGE_THREE.search("\n".join(strings(lesson))))
        for group in ("placement", "step_checks"):
            self.assertIsNone(STAGE_THREE.search("\n".join(strings(self.data.get(group, [])))), group)
        steps = CONTENT / "part-2-steps.json"
        if steps.is_file():
            self.assertIsNone(STAGE_THREE.search(steps.read_text(encoding="utf-8")))


class TierThreeStageThree(unittest.TestCase):
    def setUp(self):
        self.data = ch.bundled_data()

    def test_the_note_names_the_prompt_the_evaluations_and_the_log(self):
        note = note_of(self.data)
        self.assertIn("Stage 3 asks for three things: the Prompt, the Evaluations and the Log", note)
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact):
                self.assertRegex(note, rf"\b{artifact}\b")

    def test_the_note_ties_what_part_three_made_to_each_artifact(self):
        note = note_of(self.data)
        self.assertIn("Your prompt file is the start of the Prompt", note)
        self.assertIn("test cases, your checker and the fixtures that tested it are the start of the Evaluations", note)
        self.assertIn("Iteration 0 is the first entry of the Log", note)
        self.assertIn("at least two documented iterations", note)
        self.assertIn("two rounds after Iteration 0", note)
        self.assertIn("Iteration 0 does not count as one", note)

    def test_the_note_keeps_the_three_thresholds_separate(self):
        note = note_of(self.data)
        self.assertRegex(note, r"Part 4[^.]*known-good answer[^.]*95% or more")
        self.assertIn("overall score across five answers is a separate coaching target, not a gate", note)
        self.assertRegex(note, r"Part 5 audits each instruction[^.]*90% or more")

    def test_the_note_is_short(self):
        self.assertLessEqual(len(note_of(self.data).split()), NOTE_MAX_WORDS)

    def test_the_evaluation_approach_is_the_participants_choice(self):
        note = note_of(self.data)
        self.assertIn("Scripts, promptfoo files and written test cases are all accepted", note)
        self.assertIn("file names and layout are course choices", note)

    def test_the_note_says_it_is_orientation_and_not_required_and_carries_no_date(self):
        note = note_of(self.data)
        self.assertIn("nothing here is needed to finish this course", note)
        self.assertIn("decide what to submit", note)
        self.assertNotIn("as of", note)
        self.assertIsNone(re.search(r"\b20\d\d\b", note))

    def test_the_note_gives_no_submission_steps(self):
        text = "\n".join(strings(lesson_of(self.data, NOTE_LESSON)))
        stage_three_text = text.split(NOTE_HEADING, 1)[1]
        self.assertIsNone(SUBMISSION_STEPS.search(stage_three_text))

    def test_stage_three_is_named_only_in_the_last_lesson(self):
        for lesson in self.data["lessons"]:
            if lesson["id"] == NOTE_LESSON:
                continue
            with self.subTest(lesson=lesson["id"]):
                text = "\n".join(strings(lesson))
                self.assertIsNone(STAGE_THREE.search(text))
        for group in ("placement", "step_checks"):
            self.assertIsNone(STAGE_THREE.search("\n".join(strings(self.data.get(group, [])))), group)

    def test_stage_three_is_not_in_the_glossary_or_the_step_text(self):
        for name in ("glossary.json", "steps.json", "lesson-ui.json"):
            with self.subTest(file=name):
                text = (CONTENT / name).read_text(encoding="utf-8")
                self.assertIsNone(STAGE_THREE.search(text))

    def test_the_stage_three_reflection_is_optional(self):
        lesson = lesson_of(self.data, NOTE_LESSON)
        activity = next(a for a in lesson["activities"] if a["id"] == "baseline-stage3")
        self.assertEqual(activity["type"], "reflection")
        self.assertTrue(activity["prompt"].startswith("Optional."))

    @unittest.skipUnless(PLAN.exists(), "the plan is local and not in the repository or the packaged app")
    def test_the_plan_map_and_the_lesson_name_the_same_artifacts(self):
        plan = PLAN.read_text(encoding="utf-8")
        self.assertIn("Stage 3 alignment map", plan)
        section = plan.split("Stage 3 alignment map", 1)[1]
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact):
                self.assertRegex(section, rf"\b{artifact}\b")
        self.assertNotIn("a written evaluation framework with at least three criteria", plan.lower())


CONTENT_RULES = ROOT / "docs" / "CONTENT-RULES.md"
SPEC = ROOT / "docs" / "SPEC.md"
MAP_HEADING = "## Stage 3 traceability map"
MAP_COLUMNS = ("Artifact", "What the program asks (paraphrased)", "Exercise (Part, step)", "Evidence it produces", "Status")
PARTICIPANT_FILES = ("lessons.json", "part-1-lessons.json", "part-2-lessons.json", "steps.json", "part-1-steps.json",
                     "part-2-steps.json", "glossary.json", "lesson-ui.json", "series.json")


def doc_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def section_of(path, heading):
    return doc_text(path).split(heading, 1)[1].split("\n## ", 1)[0]


def map_rows():
    """The header and the rows of the traceability map in docs/CONTENT-RULES.md, each row as {column: cell}."""
    lines = [line for line in section_of(CONTENT_RULES, MAP_HEADING).splitlines() if line.startswith("|")]
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    return header, [dict(zip(header, (cell.strip() for cell in line.strip("|").split("|")))) for line in lines[2:]]


class StageThreeTraceabilityMap(unittest.TestCase):
    def test_the_map_has_its_columns_a_date_a_source_and_a_status_on_every_row(self):
        header, rows = map_rows()
        self.assertEqual(tuple(header), MAP_COLUMNS)
        text = section_of(CONTENT_RULES, MAP_HEADING)
        self.assertRegex(text, r"Checked on 20\d\d-\d\d-\d\d against")
        self.assertIn("What We Examine", text)
        for row in rows:
            with self.subTest(row=row["What the program asks (paraphrased)"][:40]):
                self.assertRegex(row["Status"], r"^(Examiner requirement|Course convention|The program says)")

    def test_each_artifact_has_a_row_with_an_exercise_and_an_evidence_entry(self):
        _, rows = map_rows()
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact):
                mine = [row for row in rows if row["Artifact"] == artifact]
                self.assertTrue(mine, f"no row for the {artifact}")
                for row in mine:
                    self.assertTrue(row["Exercise (Part, step)"], row)
                    self.assertTrue(row["Evidence it produces"], row)

    def test_no_participant_text_carries_the_map_row_labels(self):
        labels = ("Examiner requirement", "Course convention", "What We Examine", "traceability map",
                  "Evidence it produces", "Exercise (Part, step)")
        for name in PARTICIPANT_FILES:
            path = CONTENT / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8").lower()
            for label in labels:
                with self.subTest(file=name, label=label):
                    self.assertNotIn(label.lower(), text)


class ThresholdRules(unittest.TestCase):
    def test_the_rules_name_the_three_thresholds_and_the_evidence_words(self):
        text = doc_text(CONTENT_RULES)
        for phrase in ("measured gain on these rules", "No measured gain on these rules", "observation",
                       "known-good check", "five-answer overall score", "load-bearing audit",
                       "Iteration 0 is not one of the two documented rounds"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_spec_holds_the_unbuilt_handoff_contract(self):
        section = section_of(SPEC, "## Evidence handoff (contract for Parts 4 and 5)")
        self.assertIn("Not yet built", section)
        for code in ("prompt_changed", "rules_changed", "checker_changed", "answers_changed", "results_missing",
                     "log_mismatch", "coverage_changed"):
            with self.subTest(code=code):
                self.assertIn(code, section)


if __name__ == "__main__":
    unittest.main()
