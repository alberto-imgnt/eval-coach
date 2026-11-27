"""Part 4 lessons and glossary (OpenSpec change part-4-course, spec part-4-course and the lesson caps in
course-structure and mission-lesson-shape).

The worked example's numbers are not typed here: the lesson's result tables are compared with what the reference
checker computes on the authored answers (tests/golden/part4-worked) and on the Practice task's sample answers.
Step text (content/part-4-steps.json) is tested in its own file.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest

import helpers
from helpers import GOLDEN, NORTHWIND

from eval_coach import lessons as L
from eval_coach import resources, state

LESSON_ORDER = ["p4-mission", "p4-checker-first", "p4-one-change", "p4-worked-example", "p4-read-results",
                "p4-keep-and-log"]
CAPS = {"p4-mission": 450, "p4-checker-first": 300, "p4-one-change": 300, "p4-worked-example": 300,
        "p4-read-results": 300, "p4-keep-and-log": 400}
MISSION_TEXT = ("Understand how to improve a prompt one change at a time, and how to tell from a rerun of the same "
                "rules whether a change was worth keeping.")
MISSION_LABELS = ("**The goal.**", "**Why it matters to you.**", "**What you will do.**", "**What you leave with.**")
STEP_CHECK_STEPS = ["starting-point", "known-good", "hypothesis-1", "edit-1", "measure-1", "decide-1", "hypothesis-2",
                    "edit-2", "measure-2", "hypothesis-3", "edit-3", "measure-3", "decide-3"]
SEVEN_TERMS = {"Hypothesis": "idea", "Iteration": "idea", "Red green refactor": "idea",
               "Known-good answer": "course", "Kept version": "course", "Measured gain on these rules": "idea",
               "Coverage change": "idea"}

BANNED = (
    ("did not help", r"did not help"), ("no benefit", r"no benefit"), ("did better", r"did better"),
    ("pick the best answer", r"(?:pick|choose|take) (?:your|the) best answer"),
    ("Stage 3", r"stage\s*3"), ("certification", r"certif"), ("session", r"\bsessions?\b"),
    ("presenter", r"\bpresenters?\b"), ("facilitator", r"\bfacilitators?\b"), ("room", r"\brooms?\b"),
    ("breakout", r"\bbreakouts?\b"), ("handout", r"\bhandouts?\b"), ("neighbor", r"\bneighbou?rs?\b"),
    ("clock", r"\bclocks?\b"), ("Copilot Chat", r"copilot\s+chat"), ("Northwind", r"Northwind"),
    ("group work", r"\bswap\b|\bpartner\b|share \w+ with|discuss \w+ with|contact |reach out|office hours|"
                   r"AIR discussion"),
    ("submission step", r"https?://|\bupload\b|\bsubmission form\b|\bsend (?:it|them) to\b|\bhow to submit\b"),
)
BARE_CLI = re.compile(r"\bCLIs?\b")
VENDOR_CLI = ("GitHub Copilot CLI", "Copilot CLI", "Devin CLI")

# The worked example (spec part-4-course "The worked edits and results stay hidden until the prediction is locked").
ROUND_1_TONE = ("- Tone: factual. Describe what happened and what is next. Do not use praise or enthusiasm words such "
                "as excited, thrilled, proud, amazing or successfully, and do not use exclamation marks.")
ROUND_2_TONE = "- Tone: factual, no praise words, no exclamation marks."
ROLE_LINE = "Role: You are a delivery consultant writing a quick status message for your project lead."
VAGUE_TONE = "- Tone: factual, not self-promotional."
HIDDEN_BEFORE_PREDICTION = (ROUND_1_TONE, ROUND_2_TONE, "Describe what happened and what is next",
                            "no praise words, no exclamation marks", "26 of 30", "one answer left out the lunch",
                            "delete the Role line")

_spec = importlib.util.spec_from_file_location("reference_check_part_4_content", str(GOLDEN / "reference-check.py"))
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)
RULE_NAMES = {cid: f"{cid} {name}" for cid, name, _fn in reference.CRITERIA}
WORKED = GOLDEN / "part4-worked"


def course_data():
    return json.loads(resources.read_text("content/part-4-lessons.json"))


def glossary_terms():
    return json.loads(resources.read_text("content/glossary.json"))["terms"]


def part_four_glossary():
    return [t for t in glossary_terms() if t["term"] in SEVEN_TERMS]


def lesson(lesson_id):
    return next(x for x in course_data()["lessons"] if x["id"] == lesson_id)


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def text_of(node):
    return "\n".join(strings(node))


def squash(text):
    return " ".join(text.split())


def passage(body, label):
    """The text of one labelled passage, up to the next blank line."""
    return body.split(label, 1)[1].split("\n\n")[0]


def read(path):
    return path.read_text(encoding="utf-8")


def counts(texts):
    return {cid: sum(1 for text in texts if fn(text)[0]) for cid, _name, fn in reference.CRITERIA}


def iteration_0():
    return [read(NORTHWIND / f"sample-run-{n}.txt") for n in range(1, 6)]


def round_answers(n):
    return [read(WORKED / f"round-{n}" / f"run-{k}.txt") for k in range(1, 6)]


def refs_of(lesson_data):
    return [s["ref"] for s in lesson_data["sources"]] + [lesson_data["primary_source"]["ref"]]


class LessonsShape(unittest.TestCase):
    def test_the_lessons_are_in_the_course_order_and_pass_the_schema(self):
        self.assertEqual([x["id"] for x in course_data()["lessons"]], LESSON_ORDER)
        self.assertEqual([item for kind, item in state.COURSE_4 if kind == "lesson"], LESSON_ORDER)
        self.assertEqual(course_data()["mission"], MISSION_TEXT)
        self.assertEqual(course_data()["placement"], [])
        L.validate_course(course_data(), L.validate_glossary({"terms": glossary_terms()}), state.PART_4)
        self.assertTrue(set(LESSON_ORDER) <= set(L.load_bundled().by_id))

    def test_bodies_stay_within_their_caps(self):
        for lesson_id, cap in CAPS.items():
            with self.subTest(lesson=lesson_id):
                self.assertLessEqual(L.word_count(lesson(lesson_id)["body"]), cap)

    def test_no_lesson_is_skippable(self):
        for item in course_data()["lessons"]:
            self.assertIs(item["skippable"], False, item["id"])

    def test_the_mission_has_the_four_passages_in_order_and_no_questions(self):
        mission = lesson("p4-mission")
        body = mission["body"]
        self.assertEqual((mission["activities"], mission["retrieval"]), ([], []))
        self.assertTrue(body.startswith("**The goal.**"))
        positions = [body.index(label) for label in MISSION_LABELS]
        self.assertEqual(positions, sorted(positions))
        for label in MISSION_LABELS:
            self.assertEqual(body.count(label), 1, label)
        self.assertEqual(len(re.findall(r"(?m)^\*\*[^*\n]+\.\*\*", body)), 4)
        self.assertIn(MISSION_TEXT, passage(body, "**The goal.**"))

    def test_what_you_leave_with_names_the_log_and_the_kept_version(self):
        leave = passage(lesson("p4-mission")["body"], "**What you leave with.**")
        self.assertRegex(leave, r"(?i)iteration log")
        self.assertIn("two documented rounds", leave)
        self.assertIn("kept version of your prompt", leave)

    def test_the_mission_is_about_part_four_and_has_no_series_framing_or_map(self):
        body = lesson("p4-mission")["body"]
        self.assertIn("Iteration 0", body)
        self.assertIn("for practice only and never something to submit", body)
        for absent in ("sounds sure of itself", "you-are-here", "six-part", "blind trust"):
            self.assertNotIn(absent, body)

    def test_each_later_lesson_opens_with_the_method_then_the_idea_and_keeps_mechanics_to_one_passage(self):
        for lesson_id in LESSON_ORDER[1:]:
            data = lesson(lesson_id)
            body = data["body"]
            with self.subTest(lesson=lesson_id):
                self.assertTrue(body.startswith("**In the method.**"))
                self.assertLess(body.index("**In the method.**"), body.index("**The idea.**"))
                self.assertEqual(body.count("**How this course does it.**"), 1)
                self.assertLess(body.index("**The idea.**"), body.index("**How this course does it.**"))
                course_passage = passage(body, "**How this course does it.**")
                self.assertLessEqual(L.word_count(course_passage), 120)
                self.assertIn("Other approaches work too", course_passage)
                self.assertIn("answer them or move on", body)
                outside = body.replace(course_passage, "")
                for mechanic in ("attempt folder", "iteration-log.md", "run-1"):
                    self.assertNotIn(mechanic, outside)

    def test_each_later_lesson_has_activities_review_questions_and_sources(self):
        for lesson_id in LESSON_ORDER[1:]:
            data = lesson(lesson_id)
            with self.subTest(lesson=lesson_id):
                self.assertGreaterEqual(len(data["activities"]), 1)
                self.assertGreaterEqual(len(data["retrieval"]), 2)
                self.assertTrue(data["sources"])
                self.assertTrue(data["primary_source"]["why"].strip())
                self.assertIn(data["primary_source"]["ref"], [s["ref"] for s in data["sources"]])
                self.assertTrue(data["win"].strip())

    def test_activity_types_are_existing_ones_and_nothing_gates_continue(self):
        types = {a["type"] for x in course_data()["lessons"] for a in x["activities"]}
        self.assertTrue(types <= {"choice", "order", "sort", "reflection"}, types)

    def test_options_have_equal_word_counts_and_one_right_answer_everywhere(self):
        data = course_data()
        groups = [a for x in data["lessons"] for a in x["activities"] + x["retrieval"] if "options" in a]
        groups += data["step_checks"]
        self.assertGreaterEqual(len(groups), 25)
        for group in groups:
            with self.subTest(item=group["id"]):
                self.assertEqual(len({L.word_count(o["text"]) for o in group["options"]}), 1)
                self.assertEqual(sum(1 for o in group["options"] if o["correct"]), 1)

    def test_every_kit_ref_resolves_to_a_readable_bundled_file(self):
        refs = {ref for x in course_data()["lessons"] for ref in refs_of(x)}
        self.assertTrue(refs)
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertTrue(ref.startswith("kit:"))
                self.assertTrue(L.kit_ref_allowed(ref))
                self.assertTrue(resources.read_text(L.kit_read_path(ref)).strip())

    def test_related_lessons_and_glossary_terms_exist(self):
        known = {t["term"].casefold() for t in glossary_terms()}
        for item in course_data()["lessons"]:
            for other in item["related"]["lessons"]:
                self.assertIn(other, LESSON_ORDER)
            for term in item["related"]["glossary"]:
                self.assertIn(term.casefold(), known, term)
        used = {t.casefold() for x in course_data()["lessons"] for t in x["related"]["glossary"]}
        for term in SEVEN_TERMS:
            self.assertIn(term.casefold(), used, term)


class LessonsTeaching(unittest.TestCase):
    def test_checker_first_chooses_before_scoring_and_never_loosens_a_rule(self):
        body = lesson("p4-checker-first")["body"]
        self.assertIn("known-good answer", body)
        self.assertIn("before you see its score", body)
        self.assertIn("95% or more", body)
        self.assertRegex(body, r"Investigate the checker, or the written requirements")
        self.assertIn("Never loosen a rule", body)
        self.assertIn("Never take the best of the five answers", body)
        self.assertRegex(body, r"(?s)known-good check.*five-answer score.*two separate")

    def test_one_change_says_one_thing_hypothesis_first_and_the_same_input_model_and_rules(self):
        body = lesson("p4-one-change")["body"]
        self.assertIn("change one thing", body)
        self.assertIn("hypothesis", body)
        self.assertIn("Before anything is scored", body)
        self.assertIn("the same input, the same model and the same rules", body)

    def test_read_results_covers_each_rule_coverage_observation_and_simplicity(self):
        body = lesson("p4-read-results")["body"]
        self.assertIn("Read each rule, not only the total", body)
        self.assertIn("A total can rise while one rule gets worse", body)
        self.assertIn("lost coverage, never a gain", body)
        self.assertIn("observation", body)
        self.assertIn("suggest and never prove", body)
        self.assertIn("A simpler prompt at the same score can be worth keeping", body)

    def test_read_results_says_the_95_percent_score_is_a_target_and_what_finishing_needs(self):
        body = lesson("p4-read-results")["body"]
        course_passage = passage(body, "**How this course does it.**")
        self.assertIn("coaching target of 95%", course_passage)
        self.assertIn("a target and not a gate", course_passage)
        self.assertIn("not a failure", course_passage)
        self.assertIn("suggested next step", course_passage)
        self.assertIn("two documented rounds after Iteration 0", course_passage)
        self.assertRegex(course_passage, r"Iteration 0, which is not one of them")
        self.assertIn("this course's convention", course_passage)

    def test_keep_and_log_makes_the_decision_explicit_and_splits_the_log_between_the_ai_and_the_learner(self):
        body = lesson("p4-keep-and-log")["body"]
        self.assertIn("explicit decision: keep it or undo it", body)
        self.assertIn("Never assume the latest version is the kept one", body)
        self.assertIn("An undone round stays in the log, marked as undone", body)
        self.assertIn("Hypothesis, Change, Result, Reasoning and Decision", body)
        self.assertIn("Your AI writes half: the numbers and the Hypothesis you saved", body)
        self.assertIn("You write the rest: Change, Result, Reasoning and Decision", body)
        self.assertIn("never edits the log", body)
        self.assertIn("Red, green, refactor", body)
        self.assertIn("Part 5 starts from that kept version", body)

    def test_the_two_result_phrases_are_in_the_course_and_no_other_wording_is_used(self):
        text = text_of(course_data())
        self.assertIn("measured gain on these rules", text)
        self.assertIn("no measured gain on these rules", text)
        self.assertIn("A higher score on the same rules is a measured gain on these rules", lesson("p4-read-results")["body"])
        self.assertIn("An equal or lower score is no measured gain on these rules", lesson("p4-read-results")["body"])

    def test_every_mention_of_the_practice_task_is_practice_only_and_nothing_offers_a_submission(self):
        for lesson_id in ("p4-mission", "p4-worked-example"):
            self.assertIn("practice only", lesson(lesson_id)["body"], lesson_id)
        for sentence in re.split(r"(?<=[.!?])\s+", text_of(course_data()) + " " + text_of(part_four_glossary())):
            if re.search(r"submi", sentence, re.I):
                self.assertRegex(sentence, r"(?i)never|cannot|can't", sentence)

    def test_no_banned_word_or_phrase_is_in_the_lessons_or_the_new_glossary_entries(self):
        for name, node in (("part-4-lessons.json", course_data()), ("glossary (Part 4 terms)", part_four_glossary())):
            text = squash(text_of(node))
            for label, pattern in BANNED:
                with self.subTest(file=name, phrase=label):
                    self.assertIsNone(re.search(pattern, text, re.I if label != "Northwind" else 0), label)
            stripped = text
            for vendor in VENDOR_CLI:
                stripped = stripped.replace(vendor, "")
            self.assertIsNone(BARE_CLI.search(stripped), name)

    def test_the_lessons_use_part_never_session_and_say_your_ai_or_ai_window(self):
        text = text_of(course_data())
        self.assertNotRegex(text, r"(?i)\bsessions?\b")
        self.assertIn("your AI", text)


class LessonsGlossary(unittest.TestCase):
    def test_the_seven_terms_are_there_with_the_right_kinds_and_lessons(self):
        terms = {t["term"]: t for t in glossary_terms()}
        for term, kind in SEVEN_TERMS.items():
            with self.subTest(term=term):
                self.assertEqual(terms[term]["kind"], kind)
                self.assertIn(terms[term]["lesson"], LESSON_ORDER)
                if kind == "course":
                    self.assertTrue(terms[term]["meaning"].startswith("In this course,"))
                else:
                    self.assertFalse(terms[term]["meaning"].startswith("In this course"))
        self.assertEqual(len(part_four_glossary()), 7)

    def test_the_new_terms_follow_the_existing_card_rule(self):
        # Part 4 terms stay off the one-page card, which holds Part 3 terms only (test_part_1_content).
        for term in part_four_glossary():
            self.assertIs(term.get("card"), False, term["term"])

    def test_the_known_good_and_result_entries_carry_the_evidence_wording(self):
        terms = {t["term"]: t["meaning"] for t in glossary_terms()}
        self.assertIn("95% or more", terms["Known-good answer"])
        self.assertIn("never loosen a rule", terms["Known-good answer"])
        self.assertIn("no measured gain on these rules", terms["Measured gain on these rules"])
        self.assertIn("lost coverage and never a gain", terms["Coverage change"])


class LessonsStepChecks(unittest.TestCase):
    def test_there_is_one_quick_check_for_each_of_the_thirteen_steps_and_none_for_decide_2(self):
        checks = course_data()["step_checks"]
        self.assertEqual([c["step"] for c in checks], STEP_CHECK_STEPS)
        self.assertNotIn("decide-2", [c["step"] for c in checks])
        self.assertEqual(len({c["id"] for c in checks}), 13)
        for check in checks:
            self.assertTrue(check["id"].startswith("sc-p4-"), check["id"])
            self.assertEqual(len(check["options"]), 4)
            self.assertIn(check["step"], state.PART_4.step_ids + state.PART_4.optional_steps)

    def test_step_checks_never_gate_and_use_the_evidence_wording(self):
        text = text_of(course_data()["step_checks"])
        self.assertIn("no measured gain on these rules", text)
        self.assertNotRegex(text, r"(?i)must answer|required to continue")


class LessonsWorkedExample(unittest.TestCase):
    """The worked example is proved by the reference checker and stays hidden until the prediction is passed."""

    @classmethod
    def setUpClass(cls):
        cls.activity = next(a for a in lesson("p4-worked-example")["activities"] if a["id"] == "wx-predict")
        cls.reveal = cls.activity["reveal"]
        cls.round_1_text, cls.round_2_text = cls.reveal.split("**Round 2", 1)

    @staticmethod
    def table(text):
        """{row label: (before, after)} for the first results table in the text, as plain strings."""
        rows = {}
        for line in text.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("|") and len(cells) == 3 and cells[0] not in ("Rule", "---"):
                rows[cells[0]] = (cells[1], cells[2])
        return rows

    @staticmethod
    def of(n, total=5):
        return f"{n} of {total}"

    def check_table(self, text, before, after):
        rows = self.table(text)
        for cid, label in RULE_NAMES.items():
            self.assertEqual(rows[label], (self.of(before[cid]), self.of(after[cid])), label)
        self.assertEqual(rows["Overall"], (self.of(sum(before.values()), 30), self.of(sum(after.values()), 30)))
        self.assertEqual(rows["NOT CHECKED"], ("none", "none"))
        self.assertEqual(len(rows), 8)

    def test_round_1_table_matches_the_reference_checker_on_every_rule(self):
        self.check_table(self.round_1_text, counts(iteration_0()), counts(round_answers(1)))

    def test_round_2_table_matches_the_reference_checker_on_every_rule(self):
        self.check_table(self.round_2_text, counts(round_answers(1)), counts(round_answers(2)))

    def test_the_lessons_iteration_0_is_what_the_checker_gives_the_sample_answers(self):
        body = lesson("p4-worked-example")["body"]
        scored = counts(iteration_0())
        self.assertIn(f"{self.of(sum(scored.values()), 30)} overall", body)
        for cid, label in RULE_NAMES.items():
            self.assertIn(f"- {label}: {self.of(scored[cid])}", body)
        self.assertIn("- NOT CHECKED: none", body)

    def test_the_edits_are_the_ones_in_the_reveal_and_are_one_per_round(self):
        self.assertIn(f"`{ROUND_1_TONE}`", self.round_1_text)
        self.assertIn(f"`{ROUND_2_TONE}`", self.round_2_text)
        self.assertIn(f"`{ROLE_LINE}`", self.round_2_text)
        self.assertIn("delete the Role line", self.round_2_text)

    def test_round_1_names_the_rule_that_fell_says_the_total_rose_and_calls_the_reason_a_guess(self):
        text = self.round_1_text
        self.assertIn("C6 Uses the rough notes fell from 5 of 5 to 4 of 5", text)
        self.assertIn("one answer left out the lunch and learn item", text)
        self.assertIn("The total rose from 25 of 30 to 26 of 30", text)
        self.assertIn("a guess and not a fact", text)
        self.assertIn("Reading only the total would have hidden a worse rule", text)
        self.assertIn("a measured gain on these rules", text)

    def test_round_2_is_flat_and_kept_as_simpler(self):
        text = self.round_2_text
        self.assertIn("no measured gain on these rules", text)
        self.assertIn("A simpler prompt at the same score can be worth keeping", text)
        self.assertIn("qualities no rule checks", text)
        self.assertIn("starting from round 1 kept", text)

    def test_the_reveal_says_it_is_saved_answers_with_no_recorded_model_and_not_a_measurement(self):
        self.assertIn("saved answers, not a measurement", self.reveal)
        self.assertIn("no recorded model", self.reveal)
        self.assertIn("Only your own rounds are measured, so your numbers may differ", self.reveal)
        body = lesson("p4-worked-example")["body"]
        self.assertIn("A worked example, not a measurement", body)
        self.assertIn("no recorded model", body)
        self.assertIn("your numbers may differ", body)

    def test_the_prediction_has_one_item_per_rule_and_the_buckets_are_what_the_checker_shows(self):
        before, after = counts(iteration_0()), counts(round_answers(1))
        self.assertEqual([b["id"] for b in self.activity["buckets"]], ["rises", "stays", "falls"])
        items = {i["text"]: i for i in self.activity["items"]}
        self.assertEqual(set(items), set(RULE_NAMES.values()))
        for cid, label in RULE_NAMES.items():
            expected = "rises" if after[cid] > before[cid] else "falls" if after[cid] < before[cid] else "stays"
            self.assertEqual(items[label]["bucket"], expected, label)
        self.assertEqual({label: i["bucket"] for label, i in items.items()},
                         {"C1 Length": "stays", "C2 Grouped by client": "stays", "C3 Blocker and ask": "stays",
                          "C4 Teams, not email": "stays", "C5 Factual tone": "rises", "C6 Uses the rough notes": "falls"})

    def test_each_rules_feedback_explains_that_rule_only(self):
        for item in self.activity["items"]:
            others = [label for label in RULE_NAMES.values() if label != item["text"]]
            with self.subTest(rule=item["text"]):
                text = item["feedback"]
                for other in others:
                    self.assertNotIn(other, text)
                    self.assertNotIn(other.split(" ", 1)[1].lower(), text.lower().replace("grouping", ""))
                self.assertNotRegex(text, r"\b26\b|of 30")
                for hidden in HIDDEN_BEFORE_PREDICTION:
                    self.assertNotIn(hidden, text)

    def pre_prediction_texts(self):
        """Everything a participant can read before the prediction is passed, as (where, text)."""
        found = []
        for item in course_data()["lessons"]:
            found.append((f"{item['id']} body", item["body"]))
            found.append((f"{item['id']} retrieval", text_of(item["retrieval"])))
            found.append((f"{item['id']} sources", text_of([item["sources"], item["primary_source"]])))
            for activity in item["activities"]:
                without = {k: v for k, v in activity.items() if k != "reveal"}
                found.append((f"{item['id']} activity {activity['id']}", text_of(without)))
                found.append((f"{item['id']} public {activity['id']}", json.dumps(
                    L.public_activity(item["id"], activity, None, "seed", {}))))
            for ref in refs_of(item):
                found.append((f"kit file {ref}", resources.read_text(L.kit_read_path(ref))))
        found.append(("step checks", text_of(course_data()["step_checks"])))
        found.append(("glossary", text_of(glossary_terms())))
        found.append(("mission", course_data()["mission"]))
        return found

    def test_no_edit_and_no_result_is_readable_before_the_prediction(self):
        rows = [line.strip() for line in self.reveal.splitlines() if line.startswith("| C") or line.startswith("| Overall")]
        self.assertEqual(len(rows), 14)
        texts = self.pre_prediction_texts()
        self.assertGreater(len(texts), 40)
        for where, text in texts:
            flat = squash(text)
            for hidden in HIDDEN_BEFORE_PREDICTION + tuple(rows):
                with self.subTest(where=where, hidden=hidden[:40]):
                    self.assertNotIn(hidden, flat)

    def test_before_the_prediction_only_iteration_0_and_the_vague_tone_line_are_shown(self):
        body = lesson("p4-worked-example")["body"]
        self.assertIn(f"`{VAGUE_TONE}`", body)
        self.assertIn("make this line more concrete", body)
        self.assertNotIn("Round 1", body)
        self.assertNotIn("Round 2", body)

    def entry(self, placements, passed):
        return {"passed": passed, "last": {"placements": placements}, "attempts": 1}

    def right_placements(self):
        return {i["id"]: i["bucket"] for i in self.activity["items"]}

    def view(self, entry):
        return L.public_activity("p4-worked-example", self.activity, entry, "seed", {})

    def test_an_unanswered_view_holds_no_answer_feedback_or_reveal(self):
        view = self.view(None)
        self.assertNotIn("reveal", view)
        self.assertIsNone(view["result"])
        dumped = json.dumps(view)
        for item in self.activity["items"]:
            self.assertNotIn(item["feedback"], dumped)
            self.assertNotIn('"bucket"', dumped)
        self.assertEqual({i["text"] for i in view["items"]}, set(RULE_NAMES.values()))

    def test_a_wrong_placement_shows_feedback_for_the_wrong_items_only_and_no_reveal(self):
        placements = self.right_placements()
        ids = {i["text"]: i["id"] for i in self.activity["items"]}
        placements[ids["C5 Factual tone"]] = "stays"
        placements[ids["C6 Uses the rough notes"]] = "stays"
        view = self.view(self.entry(placements, False))
        self.assertNotIn("reveal", view)
        self.assertFalse(view["passed"])
        shown = {f["item"]: f["feedback"] for f in view["result"]["feedback"]}
        self.assertEqual(set(shown), {ids["C5 Factual tone"], ids["C6 Uses the rough notes"]})
        for item in self.activity["items"]:
            if item["id"] in shown:
                self.assertEqual(shown[item["id"]], item["feedback"])
        dumped = squash(json.dumps(view))
        for hidden in HIDDEN_BEFORE_PREDICTION:
            self.assertNotIn(hidden, dumped)

    def test_a_pass_returns_the_reveal_beside_the_prediction(self):
        view = self.view(self.entry(self.right_placements(), True))
        self.assertTrue(view["passed"])
        self.assertEqual(view["reveal"], self.reveal)
        self.assertEqual(len(view["result"]["feedback"]), 6)

    def test_the_authored_answers_exist_for_both_rounds(self):
        for n in (1, 2):
            self.assertEqual(len(round_answers(n)), 5)


def steps_data():
    return json.loads(resources.read_text("content/part-4-steps.json"))


class StepsContent(unittest.TestCase):
    """content/part-4-steps.json: every Part 4 step has words, and the words follow the plain-language and evidence rules."""

    def test_every_part_4_step_has_text_and_a_known_kind(self):
        steps = steps_data()["steps"]
        wanted = set(state.PART_4.step_ids + state.PART_4.optional_steps)
        self.assertEqual(set(steps), wanted)
        kinds = {"starting-point": "choose_start", "known-good": "known_good"}
        for step, text in steps.items():
            phase = step.rsplit("-", 1)[0]
            expected = kinds.get(step, {"hypothesis": "hypothesis", "edit": "edit", "measure": "measure",
                                        "decide": "decide"}.get(phase))
            self.assertEqual(text["kind"], expected, step)
            for key in ("title", "goal", "why", "instructions", "troubleshooting", "ui", "messages", "gate"):
                self.assertIn(key, text, f"{step}.{key}")

    def test_the_paste_steps_hold_the_line_the_app_shows_and_never_types(self):
        steps = steps_data()["steps"]
        for n in (1, 2, 3):
            self.assertEqual(steps[f"measure-{n}"]["cli_mode"], "paste")
            self.assertIn("output.txt", steps[f"measure-{n}"]["line"])
            decide = steps[f"decide-{n}"]
            self.assertEqual(decide["cli_mode"], "paste")
            for line in (decide["line_template"], decide["tracks"]["promptfoo"]["line_template"]):
                self.assertIn("run + log mode", line)
                self.assertIn("leave Change, Result and Reasoning empty", line)
                self.assertIn("{log}", line)
                self.assertIn("Copy the Hypothesis word for word", line)
        self.assertIn("build-eval-script", steps["decide-1"]["line_template"])
        self.assertIn("build-promptfoo-config", steps["decide-1"]["tracks"]["promptfoo"]["line_template"])

    def test_only_decide_2_has_the_written_reflection(self):
        steps = steps_data()["steps"]
        for step, text in steps.items():
            self.assertEqual("reflection" in text["ui"], step == "decide-2", step)
        reflection = steps["decide-2"]["ui"]["reflection"]
        self.assertIn("what can the score not tell you", reflection["prompt"])
        self.assertIn("never blocks", reflection["hint"])

    def test_no_banned_phrase_appears_in_the_step_words(self):
        text = text_of(steps_data())
        for name, pattern in BANNED:
            if name in ("Northwind",):
                continue
            self.assertIsNone(re.search(pattern, text, re.I), name)
        self.assertIsNone(BARE_CLI.search(text))

    def test_the_evidence_words_are_the_two_phrases_only(self):
        text = text_of(steps_data())
        self.assertIn("measured gain on these rules", text)
        self.assertIn("no measured gain on these rules", text)
        for bad in ("did not help", "no benefit", "did better", "improvement"):
            self.assertNotIn(bad, text.lower())

    def test_the_practice_task_is_always_practice_only_and_never_a_submission(self):
        steps = steps_data()["steps"]
        start = steps["starting-point"]["ui"]
        self.assertIn("practice only", start["practice_only"])
        self.assertIn("cannot be submitted", start["practice_only"])
        for step, text in steps.items():
            if "practice_only" in text["ui"]:
                self.assertIn("practice only", text["ui"]["practice_only"], step)
                self.assertIn("cannot be submitted", text["ui"]["practice_only"], step)
        text = text_of(steps_data()).lower()
        self.assertNotRegex(text, r"submit (the|your) practice|practice task (as|for) (your )?submission")

    def test_the_known_good_words_never_offer_to_loosen_a_rule_and_say_what_to_check(self):
        known = steps_data()["steps"]["known-good"]
        text = text_of(known)
        self.assertIn("Do not loosen a rule", text)
        self.assertIn("check the checker or the written requirements", text.lower())
        self.assertNotRegex(text.lower(), r"(strongest|best) (of your five )?answer is the known")

    def test_the_finished_text_names_the_log_and_the_kept_version_and_says_practice_only_when_practiced(self):
        ui = next(p for p in json.loads(resources.read_text("content/series.json"))["parts"]
                  if p["id"] == "part-4")["ui"]
        for key in ("finished_body", "finished_body_practice"):
            self.assertIn("iteration log" if key == "finished_body" else "practice log", ui[key])
            self.assertIn("kept", ui[key])
            self.assertIn("Part 5 starts from the version you kept", ui[key])
            self.assertIsNone(re.search(r"stage\s*3|certif", ui[key], re.I))
        self.assertIn("practice only", ui["finished_body_practice"])
        self.assertIn("cannot be submitted", ui["finished_body_practice"])

    def test_the_words_the_panels_need_are_all_in_the_content(self):
        steps = steps_data()["steps"]
        needed = {
            "starting-point": ("own", "practice", "practice_only", "use_own", "use_practice", "little_gap"),
            "known-good": ("rules_heading", "answer_label", "save", "result_heading"),
            "hypothesis-1": ("rules_heading", "label", "save", "needs_work", "passes_all", "not_checked"),
            "edit-1": ("editor_label", "save", "same_note"),
            "measure-1": ("runs_heading", "score", "results_heading", "before_col", "after_col", "lost"),
            "decide-1": ("keep", "undo", "decision_heading", "log_note", "evidence_heading"),
        }
        for step, keys in needed.items():
            for key in keys:
                self.assertIn(key, steps[step]["ui"], f"{step}.{key}")


if __name__ == "__main__":
    unittest.main()
