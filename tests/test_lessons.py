"""Lesson schema, bundled content, kit references, shuffling and grading. No server and no engine here."""
from __future__ import annotations

import json
import re
import unittest
from unittest import mock

import course_helpers as ch
import helpers  # noqa: F401

from eval_coach import lessons as L
from eval_coach import resources
from eval_coach.state import COURSE, LESSON_IDS, PART_1, PART_2, PART_4, all_lesson_ids

CONTENT = helpers.ROOT / "app" / "eval_coach" / "content"

REQUIRED_GLOSSARY = ("Checker", "Deterministic", "Criterion", "Threshold", "NOT CHECKED", "Interpretation choice",
                     "Fixture", "Polished but wrong", "Answer key", "Run", "Baseline (Iteration 0)", "Exit code",
                     "promptfoo", "Agent skill", "The loop")
HANDS_ON = ("rule_lab", "cli_compare", "cli_demo")
MISSION = ("Understand how to turn the test cases, criteria and thresholds from Part 2 into reusable parts, "
           "and how those parts fit into an evaluated AI process.")
NEW_LESSONS = ["mission", "hook", "several-runs", "rules", "trust", "surprise", "baseline-why"]
# Activities that tested only this course's mechanics (design D8). None may come back.
REMOVED_ACTIVITIES = ("loop-order", "loop-actors", "generate-fair", "generate-try", "rules-demo", "rules-anatomy",
                      "build-first-look", "verify-order", "verify-try", "compare-exit")
# Where every kept activity lives now (design D8).
KEPT_ACTIVITIES = {
    "hook": ["hook-compare", "hook-explain"],
    "several-runs": ["generate-spot"],
    "rules": ["rules-lab", "build-sort", "build-explain", "build-try", "choices-lab", "choices-find",
              "choices-explain-tech", "choices-own"],
    "trust": ["verify-polished", "verify-unsure"],
    "surprise": ["compare-sort", "fix-scenario", "fix-sort", "fix-try"],
    "baseline-why": ["baseline-total", "baseline-settled", "baseline-reflect", "baseline-explain",
                     "baseline-explain-write", "baseline-stage3"],
}
METHOD_LINKS = ("ask clearly", "know what you need", "turn it into rules", "score the result", "improve",
                "keep a record")
WORD_CAPS = {"mission": 450, "baseline-why": 400}
DEFAULT_WORD_CAP = 300
LABEL = "**How this course does it.**"
ABSOLUTES = ("the right way", "the only way", "the correct way", "the proper way", "the standard way",
             "this is how it is done")
# Course types that the bundled content no longer uses but the engine still supports (tests build them here).
ORDER_ACTIVITY = {
    "id": "x-order", "type": "order", "prompt": "Put the five links in order, starting from the first thing you do.",
    "items": [{"id": "prompt", "text": "Prompt: your prompt and rough notes go to a new chat"},
              {"id": "answer", "text": "Answer: the AI writes one answer"},
              {"id": "file", "text": "File: the answer is saved as a file"},
              {"id": "checker", "text": "Checker: you run the checker on the saved file"},
              {"id": "verdict", "text": "Verdict: PASS, FAIL or NOT CHECKED for each criterion"}],
    "feedback_right": "That is the loop.", "feedback_wrong": "Not yet. A checker cannot score anything unsaved.",
}
DEMO_ACTIVITY = {
    "id": "x-demo", "type": "cli_demo", "line": L.DEMO_LINE,
    "files": [{"name": "test-cases.md", "source": "kit:lessons/demo/test-cases.md"},
              {"name": "output.txt", "source": "kit:lessons/demo/output.txt"},
              {"name": "skills/build-eval-script/SKILL.md", "source": "kit:skills/build-eval-script/SKILL.md"}],
    "run_args": ["output.txt"],
}


def paragraphs(body):
    return [p for p in body.split("\n\n") if p.strip()]


def labelled(body):
    """The 'How this course does it' paragraphs of a lesson body."""
    return [p for p in paragraphs(body) if p.startswith(LABEL)]


def lesson_of(data, lesson_id):
    return next(x for x in data["lessons"] if x["id"] == lesson_id)


def activity_of(data, activity_id):
    for lesson in data["lessons"]:
        for activity in lesson["activities"]:
            if activity["id"] == activity_id:
                return activity
    raise KeyError(activity_id)


def all_choices(data):
    """Every choice-shaped item in the course, as (where, item)."""
    for item in data["placement"]:
        yield f"placement {item['id']}", item
    for item in data.get("step_checks", []):
        yield f"step check {item['id']}", item
    for lesson in data["lessons"]:
        for activity in lesson["activities"]:
            if activity["type"] == "choice":
                yield f"{lesson['id']}/{activity['id']}", activity
            elif activity["type"] in ("cli_compare", "cli_practice"):
                yield f"{lesson['id']}/{activity['id']}/question", activity["question"]
        for item in lesson["retrieval"]:
            yield f"{lesson['id']}/retrieval {item['id']}", item


def mini_choice(texts=("one two", "three four", "five six"), correct=0):
    return {"id": "q", "type": "choice", "prompt": "Which?",
            "options": [{"id": "abcdef"[i], "text": t, "correct": i == correct, "feedback": f"note {i}"}
                        for i, t in enumerate(texts)]}


class BundledCourse(unittest.TestCase):
    def setUp(self):
        self.data = ch.bundled_data()

    def test_loads_and_validates_from_disk(self):
        course = L.load_bundled()
        self.assertEqual(course.mission, MISSION)
        self.assertEqual(list(course.by_id), list(LESSON_IDS) + list(PART_1.lesson_ids) + list(PART_2.lesson_ids)
                         + list(PART_4.lesson_ids))

    def test_course_order_is_the_documented_one(self):
        self.assertEqual(
            [i for k, i in COURSE],
            ["mission", "hook", "several-runs", "inputs", "generate", "rules", "build", "trust", "fixtures", "readback",
             "predict", "key", "surprise", "run", "fix", "baseline-why", "baseline"])
        self.assertEqual(list(LESSON_IDS), NEW_LESSONS)

    def test_the_seven_lessons_come_in_the_order_of_the_method(self):
        self.assertEqual([x["id"] for x in self.data["lessons"]], NEW_LESSONS)
        for lesson in self.data["lessons"]:
            self.assertTrue(lesson["win"].strip(), lesson["id"])

    def test_the_removed_activities_are_gone_and_every_kept_one_is_under_its_new_lesson(self):
        ids = {a["id"] for lesson in self.data["lessons"] for a in lesson["activities"]}
        self.assertEqual(ids & set(REMOVED_ACTIVITIES), set())
        for lesson_id, expected in KEPT_ACTIVITIES.items():
            with self.subTest(lesson=lesson_id):
                self.assertEqual([a["id"] for a in lesson_of(self.data, lesson_id)["activities"]], expected)
        self.assertEqual(sum(len(v) for v in KEPT_ACTIVITIES.values()), 23)

    def test_every_lesson_has_an_activity_or_a_review_question(self):
        for lesson in self.data["lessons"]:
            if lesson["id"] != "mission":
                with self.subTest(lesson=lesson["id"]):
                    self.assertTrue(lesson["activities"] or lesson["retrieval"])

    def test_every_lesson_body_stays_within_its_word_cap(self):
        for lesson in self.data["lessons"]:
            words = len(lesson["body"].split())
            cap = WORD_CAPS.get(lesson["id"], DEFAULT_WORD_CAP)
            with self.subTest(lesson=lesson["id"]):
                self.assertLessEqual(words, cap, f"{words} words")

    def test_every_lesson_after_the_mission_opens_with_the_method_link_it_covers(self):
        for lesson in self.data["lessons"]:
            if lesson["id"] == "mission":
                self.assertTrue(lesson["body"].startswith("**The goal.**"), lesson["body"][:60])
                continue
            with self.subTest(lesson=lesson["id"]):
                first = paragraphs(lesson["body"])[0]
                self.assertTrue(first.startswith("**In the method.**"), first[:60])
                self.assertTrue(any(link in first.lower() for link in METHOD_LINKS), first)

    def test_course_mechanics_sit_under_a_label_after_the_first_idea(self):
        for lesson in self.data["lessons"]:
            body = lesson["body"]
            blocks = paragraphs(body)
            marked = [i for i, p in enumerate(blocks) if p.startswith(LABEL)]
            with self.subTest(lesson=lesson["id"]):
                self.assertEqual(body.count(LABEL), len(marked), "the label may only start a paragraph")
                if lesson["id"] == "mission":
                    self.assertEqual(marked, [])
                    continue
                # Opening line, then the first concept paragraph, then anything labelled.
                self.assertTrue(all(i >= 2 for i in marked), marked)
                before = "\n\n".join(blocks[: marked[0]]) if marked else body
                self.assertIsNone(re.search(r"\b[\w-]+\.(md|py|txt|yaml|json)\b", before), before)

    def test_labelled_passages_are_short_and_say_other_approaches_work(self):
        for lesson in self.data["lessons"]:
            passages = labelled(lesson["body"])
            if not passages:
                continue
            with self.subTest(lesson=lesson["id"]):
                self.assertLessEqual(sum(len(p.split()) for p in passages), 120)
                for passage in passages:
                    self.assertLessEqual(len(passage.split()), 60)
                self.assertIn("other approaches work too", " ".join(passages).lower())

    def test_the_true_principles_stay_firm_with_their_reason(self):
        body = lesson_of(self.data, "surprise")["body"]
        self.assertIn("Never edit the checker to make a failing answer pass, because a failing result is the information",
                      body)
        trust = lesson_of(self.data, "trust")["body"]
        self.assertIn("Commit before you see any result", trust)
        self.assertIn("NOT CHECKED so the gap stays visible", lesson_of(self.data, "rules")["body"])

    def test_no_course_practice_reads_as_the_only_way(self):
        texts = [json.dumps(self.data["lessons"]), (CONTENT / "steps.json").read_text(encoding="utf-8"),
                 (CONTENT / "glossary.json").read_text(encoding="utf-8")]
        for text in texts:
            lowered = text.lower()
            for phrase in ABSOLUTES:
                self.assertNotIn(phrase, lowered)

    def test_the_lessons_do_not_teach_the_procedure_that_belongs_to_the_steps(self):
        several = lesson_of(self.data, "several-runs")["body"]
        for word in ("generator", "builder", "blind folder", "exit code"):
            self.assertNotIn(word, several.lower())
        for lesson in self.data["lessons"]:
            self.assertNotIn("answer-key.md", lesson["body"])

    def test_every_bundled_lesson_file_is_cited(self):
        cited = set()
        for path in (CONTENT / "lessons.json", CONTENT / "steps.json", CONTENT / "glossary.json"):
            cited |= set(re.findall(r"kit:([\w./-]+)", path.read_text(encoding="utf-8")))
        code = "".join(p.read_text(encoding="utf-8") for p in (helpers.ROOT / "app" / "eval_coach").glob("*.py"))
        code += "".join(p.read_text(encoding="utf-8") for p in helpers.ROOT.joinpath("tests").glob("test_*.py"))
        for path in sorted((helpers.ROOT / "app" / "eval_coach" / "kit" / "lessons").rglob("*")):
            if path.is_file():
                rel = path.relative_to(helpers.ROOT / "app" / "eval_coach" / "kit").as_posix()
                with self.subTest(file=rel):
                    self.assertTrue(rel in cited or f"kit/{rel}" in code, f"{rel} is not cited by anything")

    def test_every_lesson_with_an_exercise_says_questions_never_stop_you(self):
        for lesson_id in ("hook", "several-runs", "rules", "trust", "surprise"):
            with self.subTest(lesson=lesson_id):
                self.assertRegex(lesson_of(self.data, lesson_id)["body"],
                                 r"(It is|They are) for you, so answer (it|them) or move on")

    def test_every_step_has_a_question_after_it(self):
        for part, data in ch.parts_data():
            with self.subTest(part=part.id):
                # Part 4's decide-2 has a written reflection kept by the step instead of a choice question.
                expected = set(part.step_ids + part.optional_steps) - ({"decide-2"} if part.id == "part-4" else set())
                self.assertEqual(sorted(c["step"] for c in data["step_checks"]), sorted(expected))

    def test_no_activity_carries_a_blocking_flag(self):
        for lesson in self.data["lessons"]:
            for activity in lesson["activities"]:
                self.assertNotIn("blocking", activity, activity["id"])

    def test_every_lesson_has_the_required_parts(self):
        for lesson in self.data["lessons"]:
            with self.subTest(lesson=lesson["id"]):
                for field in ("title", "win", "body"):
                    self.assertTrue(lesson[field].strip(), field)
                self.assertGreater(lesson["minutes"], 0)
                if lesson["id"] != "mission":
                    self.assertGreaterEqual(len(lesson["activities"]), 1)
                    self.assertGreaterEqual(len(lesson["retrieval"]), 2)
                self.assertGreaterEqual(len(lesson["sources"]), 1)
                self.assertTrue(lesson["primary_source"]["why"].strip())

    def test_every_lesson_names_a_kit_file_as_source_and_primary_reading(self):
        for lesson in self.data["lessons"]:
            with self.subTest(lesson=lesson["id"]):
                refs = [s["ref"] for s in lesson["sources"]] + [lesson["primary_source"]["ref"]]
                self.assertTrue(any(r.startswith("kit:") for r in refs))
                self.assertTrue(lesson["primary_source"]["ref"].startswith("kit:"))

    def test_sources_cite_only_bundled_kit_files_for_now(self):
        for lesson in self.data["lessons"]:
            refs = [s["ref"] for s in lesson["sources"]] + [lesson["primary_source"]["ref"]]
            for ref in refs:
                with self.subTest(lesson=lesson["id"], ref=ref):
                    self.assertTrue(ref.startswith("kit:"), "external citations wait for decision D5")
                    self.assertTrue(L.kit_ref_allowed(ref))

    def test_sources_never_cite_the_session_plan_or_the_answer_key(self):
        text = json.dumps(self.data).lower()
        for needle in ("session-3-running-evals", "answer-key.md", "presenter/", "handouts/", "onedrive"):
            self.assertNotIn(needle, text)

    def test_retrieval_is_choice_shaped_and_not_a_repeat_of_an_activity(self):
        for lesson in self.data["lessons"]:
            prompts = set()
            for activity in lesson["activities"]:
                source = activity["question"] if activity["type"] in ("cli_compare", "cli_practice") else activity
                prompts.add(" ".join(source.get("prompt", "").split()).casefold())
            for item in lesson["retrieval"]:
                with self.subTest(lesson=lesson["id"], item=item["id"]):
                    self.assertIn("options", item)
                    self.assertNotIn(" ".join(item["prompt"].split()).casefold(), prompts)

    def test_every_choice_has_exactly_one_correct_option_and_feedback_on_each(self):
        for where, item in all_choices(self.data):
            with self.subTest(where=where):
                self.assertEqual(sum(1 for o in item["options"] if o["correct"]), 1)
                self.assertGreaterEqual(len(item["options"]), 2)
                for option in item["options"]:
                    self.assertTrue(option["feedback"].strip())

    def test_word_count_parity_across_every_choice_placement_and_retrieval(self):
        checked = 0
        for where, item in all_choices(self.data):
            counts = {len(o["text"].split()) for o in item["options"]}
            with self.subTest(where=where):
                self.assertEqual(len(counts), 1, f"option word counts differ: {sorted(counts)}")
            checked += 1
        self.assertGreater(checked, 30)

    def test_the_correct_option_is_not_always_in_the_same_position(self):
        positions = {next(i for i, o in enumerate(item["options"]) if o["correct"])
                     for _where, item in all_choices(self.data)}
        self.assertGreater(len(positions), 1)

    def test_practice_and_cli_lessons_are_never_skippable(self):
        for lesson in self.data["lessons"]:
            kinds = {a["type"] for a in lesson["activities"]}
            if kinds & set(HANDS_ON):
                with self.subTest(lesson=lesson["id"]):
                    self.assertFalse(lesson["skippable"])
        self.assertFalse(lesson_of(self.data, "mission")["skippable"])
        self.assertFalse(lesson_of(self.data, "hook")["skippable"])
        self.assertFalse(lesson_of(self.data, "rules")["skippable"])

    def test_cli_activities_live_only_in_the_hook_with_the_exact_line(self):
        hook = activity_of(self.data, "hook-compare")
        self.assertEqual(hook["runs"], 3)
        self.assertEqual(hook["line"], "Read update.txt and requirements.md. Score the update from 1 to 10 against the "
                                       "requirements, say pass or fail, and give one sentence of reasoning. Save only "
                                       "that to output.txt. Do nothing else.")
        owners = {a["id"]: lesson["id"] for lesson in self.data["lessons"] for a in lesson["activities"]
                  if a["type"] in ("cli_compare", "cli_demo")}
        self.assertEqual(owners, {"hook-compare": "hook"})
        self.assertEqual(DEMO_ACTIVITY["line"], "Read skills/build-eval-script/SKILL.md and follow it in build mode on "
                                                "test-cases.md.")

    def test_placement_is_empty_until_the_tracks_replace_it(self):
        self.assertEqual(self.data["placement"], [])

    def test_the_mission_is_an_introduction_with_no_questions(self):
        mission = lesson_of(self.data, "mission")
        self.assertEqual(mission["activities"], [])
        self.assertEqual(mission["retrieval"], [])

    def test_rule_lab_expected_verdicts_match_the_real_rules(self):
        labs = [a for lesson in self.data["lessons"] for a in lesson["activities"] if a["type"] == "rule_lab"]
        self.assertGreaterEqual(len(labs), 2)
        for lab in labs:
            samples = {s["id"]: s["text"] for s in lab["samples"]}
            rules = {r["id"]: r for r in lab["rules"]}
            for case in lab["cases"]:
                with self.subTest(lab=lab["id"], case=case):
                    passed, _ = L.evaluate_rule(rules[case["rule"]], samples[case["sample"]])
                    self.assertEqual("pass" if passed else "fail", case["expected"])

    def test_every_bundled_rule_lab_rule_is_explained(self):
        for lesson in self.data["lessons"]:
            for lab in (a for a in lesson["activities"] if a["type"] == "rule_lab"):
                for rule in lab["rules"]:
                    with self.subTest(lab=lab["id"], rule=rule["id"]):
                        self.assertTrue(rule.get("explain", "").strip())

    def test_mission_text_is_the_agreed_wording(self):
        self.assertEqual(self.data["mission"], MISSION)

    def test_lessons_do_not_leak_the_northwind_answer_key(self):
        trust = json.dumps(lesson_of(self.data, "trust")).lower()
        for needle in ("northwind", "contoso", "$50k", "blocker: none", "test data", "invented", "window dressing"):
            self.assertNotIn(needle, trust)

    def test_related_lessons_and_glossary_terms_exist(self):
        terms = {t["term"].casefold() for t in ch.bundled_glossary()["terms"]}
        for part, data in ch.parts_data():
            for lesson in data["lessons"]:
                related = lesson.get("related", {})
                for other in related.get("lessons", []):
                    self.assertIn(other, part.lesson_ids)
                for term in related.get("glossary", []):
                    with self.subTest(lesson=lesson["id"], term=term):
                        self.assertIn(term.casefold(), terms)

    def test_works_from_disk_and_from_resources(self):
        text = resources.read_text("content/lessons.json")
        self.assertEqual(json.loads(text), self.data)


class Glossary(unittest.TestCase):
    def setUp(self):
        self.terms = ch.bundled_glossary()["terms"]
        self.names = {t["term"] for t in self.terms}

    def test_covers_every_required_term(self):
        for term in REQUIRED_GLOSSARY:
            with self.subTest(term=term):
                self.assertIn(term, self.names)

    def test_covers_the_working_files_from_the_session_glossary(self):
        for term in ("prompt-v0.md", "test-cases.md", "runs/run-1.txt to run-5.txt",
                     "check.py or promptfooconfig.yaml", "fixtures/", "iteration-log.md"):
            self.assertIn(term, self.names)

    def test_terms_used_in_lessons_are_explained(self):
        for term in ("AI window", "Agent"):
            self.assertIn(term, self.names)

    def test_every_entry_has_a_meaning_a_kind_and_a_real_lesson(self):
        for entry in self.terms:
            with self.subTest(term=entry["term"]):
                self.assertTrue(entry["meaning"].strip())
                self.assertIn(entry["lesson"], all_lesson_ids())
                self.assertIn(entry["kind"], ("idea", "course"))

    def test_course_terms_begin_in_this_course_and_ideas_stay_tool_neutral(self):
        for entry in self.terms:
            with self.subTest(term=entry["term"]):
                if entry["kind"] == "course":
                    self.assertTrue(entry["meaning"].startswith("In this course, "), entry["meaning"])
                else:
                    self.assertFalse(entry["meaning"].startswith("In this course"), entry["meaning"])
        by_kind = {name: {t["term"] for t in self.terms if t["kind"] == name} for name in ("idea", "course")}
        for term in ("Criterion", "Threshold", "NOT CHECKED", "Deterministic", "Proxy", "Baseline (Iteration 0)"):
            self.assertIn(term, by_kind["idea"])
        for term in ("Blind folder", "Generator", "Builder", "Verdict", "First look", "Known-good output", "Run",
                     "fixtures/", "check.py or promptfooconfig.yaml", "Agent skill"):
            self.assertIn(term, by_kind["course"])

    def test_every_glossary_term_named_by_a_lesson_exists(self):
        names = {t["term"].casefold() for t in self.terms}
        for part, data in ch.parts_data():
            for lesson in data["lessons"]:
                for term in lesson.get("related", {}).get("glossary", []):
                    with self.subTest(lesson=lesson["id"], term=term):
                        self.assertIn(term.casefold(), names)

    def test_session_wording_is_gone(self):
        for entry in self.terms:
            for text in (entry["term"], entry["meaning"]):
                self.assertNotRegex(text, r"(?i)\btoday\b")
                self.assertNotRegex(text, r"(?i)\broom\b")

    def test_no_duplicates(self):
        folded = [t["term"].casefold() for t in self.terms]
        self.assertEqual(len(folded), len(set(folded)))

    def test_validate_glossary_rejects_bad_shapes(self):
        for bad in ({}, {"terms": []}, {"terms": [{"term": "A", "kind": "idea"}]},
                    {"terms": [{"term": "", "meaning": "x", "kind": "idea"}]},
                    {"terms": [{"term": "A", "meaning": "x", "kind": "idea"},
                               {"term": "a", "meaning": "y", "kind": "idea"}]}, []):
            with self.subTest(bad=bad), self.assertRaises(L.LessonError):
                L.validate_glossary(bad)

    def test_validate_glossary_requires_a_known_kind_on_every_term(self):
        for kind in (None, "", "tool", 3):
            with self.subTest(kind=kind), self.assertRaises(L.LessonError) as ctx:
                L.validate_glossary({"terms": [{"term": "A", "meaning": "x", "kind": kind}]})
            self.assertIn("kind must be one of", ctx.exception.problems[0])
        with self.assertRaises(L.LessonError):
            L.validate_glossary({"terms": [{"term": "A", "meaning": "x"}]})
        L.validate_glossary({"terms": [{"term": "A", "meaning": "x", "kind": "course"}]})


class Validation(unittest.TestCase):
    """Every schema rule has a test that breaks it and expects a plain problem message."""

    def setUp(self):
        self.data = ch.bundled_data()

    def fails(self, expect):
        with self.assertRaises(L.LessonError) as ctx:
            L.validate_course(self.data)
        self.assertTrue(any(expect in p for p in ctx.exception.problems), ctx.exception.problems)

    def test_bundled_data_is_valid(self):
        L.validate_course(self.data)

    def test_not_an_object(self):
        self.data = []
        self.fails("must be an object")

    def test_wrong_version(self):
        self.data["version"] = 2
        self.fails("version must be 1")

    def test_mission_is_required(self):
        self.data["mission"] = " "
        self.fails("mission must be non-empty text")

    def test_missing_lesson(self):
        self.data["lessons"] = [x for x in self.data["lessons"] if x["id"] != "several-runs"]
        self.fails("missing lessons")

    def test_lesson_outside_the_course_order(self):
        extra = ch.clone(lesson_of(self.data, "several-runs"))
        extra["id"] = "bonus"
        self.data["lessons"].append(extra)
        self.fails("not in the course order")

    def test_a_removed_lesson_id_is_refused(self):
        lesson_of(self.data, "several-runs")["id"] = "loop"
        self.fails("lessons not in the course order")

    def test_duplicate_lesson(self):
        self.data["lessons"].append(ch.clone(lesson_of(self.data, "several-runs")))
        self.fails("duplicate lesson ids")

    def test_missing_text_fields(self):
        for field in ("title", "win", "body"):
            with self.subTest(field=field):
                data = ch.clone(self.data)
                lesson_of(data, "several-runs")[field] = ""
                with self.assertRaises(L.LessonError):
                    L.validate_course(data)

    def test_bad_minutes_and_skippable(self):
        lesson_of(self.data, "several-runs")["minutes"] = 0
        self.fails("minutes must be a positive whole number")
        self.data = ch.bundled_data()
        lesson_of(self.data, "several-runs")["skippable"] = "yes"
        self.fails("skippable must be true or false")

    def test_a_lesson_needs_an_activity(self):
        lesson_of(self.data, "several-runs")["activities"] = []
        self.fails("needs at least one activity")

    def test_only_the_mission_may_have_no_activities_or_retrieval(self):
        mission = lesson_of(self.data, "mission")
        self.assertEqual((mission["activities"], mission["retrieval"]), ([], []))
        L.validate_course(self.data)
        for lesson_id in ("hook", "several-runs", "trust"):
            with self.subTest(lesson=lesson_id):
                data = ch.bundled_data()
                lesson_of(data, lesson_id)["activities"] = []
                with self.assertRaises(L.LessonError) as ctx:
                    L.validate_course(data)
                self.assertTrue(any("needs at least one activity" in p for p in ctx.exception.problems))
                data = ch.bundled_data()
                lesson_of(data, lesson_id)["retrieval"] = []
                with self.assertRaises(L.LessonError) as ctx:
                    L.validate_course(data)
                self.assertTrue(any("at least two retrieval items" in p for p in ctx.exception.problems))

    def test_the_mission_may_still_carry_questions(self):
        mission = lesson_of(self.data, "mission")
        donor = lesson_of(ch.bundled_data(), "several-runs")
        mission["activities"] = [ch.clone(a) for a in donor["activities"]]
        mission["retrieval"] = [ch.clone(r) for r in donor["retrieval"]]
        for item in mission["activities"] + mission["retrieval"]:
            item["id"] = "m-" + item["id"]
        L.validate_course(self.data)

    def test_unknown_activity_type(self):
        lesson_of(self.data, "several-runs")["activities"][0]["type"] = "essay"
        self.fails("type must be one of")

    def test_a_step_check_is_validated_like_any_other_question(self):
        self.data["step_checks"][0]["options"][1]["text"] += " extra"
        self.fails("answer-word-count mismatch")

    def test_a_step_check_names_a_real_step(self):
        self.data["step_checks"][0]["step"] = "nope"
        self.fails("step must be one of")

    def test_one_check_for_each_step_at_most(self):
        self.data["step_checks"][1]["step"] = self.data["step_checks"][0]["step"]
        self.fails("at most one check for each step")

    def test_step_checks_must_be_a_list(self):
        self.data["step_checks"] = {}
        self.fails("step_checks must be a list")

    def test_a_course_without_step_checks_is_still_valid(self):
        del self.data["step_checks"]
        L.validate_course(self.data)

    def test_duplicate_activity_ids(self):
        lesson = lesson_of(self.data, "trust")
        lesson["activities"][1]["id"] = lesson["activities"][0]["id"]
        self.fails("duplicate id")

    def test_option_word_count_mismatch_in_an_activity(self):
        activity_of(self.data, "generate-spot")["options"][0]["text"] = "Five runs are too few to be worth anything at all"
        self.fails("answer-word-count mismatch")

    def test_option_word_count_mismatch_in_the_cli_question(self):
        activity_of(self.data, "hook-compare")["question"]["options"][2]["text"] += " really"
        self.fails("answer-word-count mismatch")

    def test_option_word_count_mismatch_in_retrieval(self):
        lesson_of(self.data, "trust")["retrieval"][0]["options"][3]["text"] += " plus"
        self.fails("answer-word-count mismatch")

    def test_parity_counts_whitespace_separated_tokens(self):
        activity_of(self.data, "generate-spot")["options"][0]["text"] = "Five   runs  are too few to be worth anything"
        L.validate_course(self.data)
        activity_of(self.data, "generate-spot")["options"][1]["text"] = "Each run needed the same chat for better"
        self.fails("answer-word-count mismatch")

    def test_choice_needs_exactly_one_correct_option(self):
        options = activity_of(self.data, "generate-spot")["options"]
        for option in options:
            option["correct"] = False
        self.fails("exactly one correct option, found 0")
        for option in options[:2]:
            option["correct"] = True
        self.fails("exactly one correct option, found 2")

    def test_choice_needs_feedback_on_every_option(self):
        activity_of(self.data, "generate-spot")["options"][0]["feedback"] = ""
        self.fails("feedback must be non-empty text")

    def test_choice_needs_two_options_and_unique_ids(self):
        activity_of(self.data, "generate-spot")["options"] = activity_of(self.data, "generate-spot")["options"][:1]
        self.fails("needs at least two options")
        self.data = ch.bundled_data()
        activity_of(self.data, "generate-spot")["options"][1]["id"] = "a"
        self.fails("duplicate id")

    def test_retrieval_needs_two_items(self):
        lesson_of(self.data, "several-runs")["retrieval"] = lesson_of(self.data, "several-runs")["retrieval"][:1]
        self.fails("at least two retrieval items")

    def test_retrieval_must_differ_from_the_activities(self):
        lesson = lesson_of(self.data, "several-runs")
        lesson["retrieval"][0]["prompt"] = "  " + lesson["activities"][0]["prompt"].upper()
        self.fails("repeats an activity")

    def test_retrieval_must_differ_from_the_cli_question(self):
        lesson = lesson_of(self.data, "hook")
        lesson["retrieval"][0]["prompt"] = lesson["activities"][0]["question"]["prompt"]
        self.fails("repeats an activity")

    def test_practice_lesson_cannot_be_skippable(self):
        lesson_of(self.data, "rules")["skippable"] = True
        self.fails("cannot be skippable")

    def test_cli_lesson_cannot_be_skippable(self):
        lesson_of(self.data, "hook")["skippable"] = True
        self.fails("cannot be skippable")

    def test_cli_activities_only_in_their_own_lesson(self):
        lesson_of(self.data, "several-runs")["activities"].append(dict(ch.clone(DEMO_ACTIVITY), id="x"))
        self.fails("may appear only in lesson")
        self.data = ch.bundled_data()
        lesson_of(self.data, "rules")["activities"].append(ch.clone(DEMO_ACTIVITY))
        L.validate_course(self.data)

    def test_order_needs_two_items_and_both_feedbacks(self):
        activity = ch.clone(ORDER_ACTIVITY)
        activity["feedback_wrong"] = ""
        lesson_of(self.data, "several-runs")["activities"].append(activity)
        self.fails("feedback_wrong must be non-empty text")
        self.data = ch.bundled_data()
        activity = ch.clone(ORDER_ACTIVITY)
        activity["items"] = activity["items"][:1]
        lesson_of(self.data, "several-runs")["activities"].append(activity)
        self.fails("needs at least two items")

    def test_sort_item_must_name_a_real_bucket(self):
        activity_of(self.data, "compare-sort")["items"][0]["bucket"] = "nowhere"
        self.fails("bucket must name one of the buckets")

    def test_sort_needs_two_buckets_and_item_feedback(self):
        activity_of(self.data, "compare-sort")["items"][0]["feedback"] = ""
        self.fails("feedback must be non-empty text")
        self.data = ch.bundled_data()
        activity = activity_of(self.data, "compare-sort")
        activity["buckets"] = activity["buckets"][:1]
        self.fails("needs at least two buckets")

    def test_rule_lab_expected_must_match_the_real_result(self):
        case = activity_of(self.data, "rules-lab")["cases"][0]
        case["expected"] = "fail" if case["expected"] == "pass" else "pass"
        self.fails("does not match the rule's real result")

    def test_rule_lab_rejects_unknown_rule_kind_sample_and_rule(self):
        lab = activity_of(self.data, "rules-lab")
        lab["rules"][0]["kind"] = "run_python"
        self.fails("kind must be one of")
        self.data = ch.bundled_data()
        activity_of(self.data, "rules-lab")["cases"][0]["sample"] = "missing"
        self.fails("unknown sample")
        self.data = ch.bundled_data()
        activity_of(self.data, "rules-lab")["cases"][0]["rule"] = "missing"
        self.fails("unknown rule")

    def test_rule_lab_rejects_bad_params_and_duplicate_cases(self):
        activity_of(self.data, "rules-lab")["rules"][0]["params"] = {"limit": 0}
        self.fails("limit must be a positive whole number")
        self.data = ch.bundled_data()
        activity_of(self.data, "rules-lab")["rules"][1]["params"] = {"labels": []}
        self.fails("labels must be a non-empty list of text")
        self.data = ch.bundled_data()
        lab = activity_of(self.data, "rules-lab")
        lab["cases"].append(dict(lab["cases"][0]))
        self.fails("duplicate case")

    def test_rule_lab_explain_must_be_text_when_present(self):
        activity_of(self.data, "rules-lab")["rules"][0]["explain"] = "  "
        self.fails("explain must be non-empty text")

    def test_rule_lab_expected_must_be_pass_or_fail(self):
        activity_of(self.data, "rules-lab")["cases"][0]["expected"] = "maybe"
        self.fails("expected must be pass or fail")

    def test_reflection_needs_a_positive_minimum(self):
        activity_of(self.data, "choices-own")["min_words"] = 0
        self.fails("min_words must be a positive whole number")

    def test_cli_compare_line_and_runs_are_checked(self):
        activity_of(self.data, "hook-compare")["line"] = "Grade it."
        self.fails("line must be the exact line")
        self.data = ch.bundled_data()
        activity_of(self.data, "hook-compare")["runs"] = 0
        self.fails("runs must be a positive whole number")

    def test_cli_demo_arguments_cannot_leave_the_demo_folder(self):
        for bad in ("../check.py", "C:\\x.txt", "/etc/passwd", "a\\b", "..", ""):
            with self.subTest(arg=bad):
                data = ch.bundled_data()
                demo = ch.clone(DEMO_ACTIVITY)
                demo["run_args"] = [bad]
                lesson_of(data, "rules")["activities"].append(demo)
                with self.assertRaises(L.LessonError):
                    L.validate_course(data)

    def test_cli_practice_files_and_line_are_checked(self):
        practice = activity_of(self.data, "build-try")
        practice["line"] = "Read test-cases.md and follow it."
        self.fails("output.txt")
        for bad_name in ("../x.md", "C:\\x.md", "/etc/x", "output.txt", ""):
            with self.subTest(name=bad_name):
                data = ch.bundled_data()
                activity_of(data, "build-try")["files"][0]["name"] = bad_name
                with self.assertRaises(L.LessonError):
                    L.validate_course(data)
        for bad_source in ("kit:northwind/answer-key.md", "kit:lessons/missing.md", "prompt.md"):
            with self.subTest(source=bad_source):
                data = ch.bundled_data()
                activity_of(data, "build-try")["files"][0]["source"] = bad_source
                with self.assertRaises(L.LessonError):
                    L.validate_course(data)

    def test_sources_and_primary_source_are_required(self):
        lesson_of(self.data, "several-runs")["sources"] = []
        self.fails("sources must name at least one source")
        self.data = ch.bundled_data()
        lesson_of(self.data, "several-runs")["primary_source"]["why"] = ""
        self.fails("why must be non-empty text")

    def test_refs_must_be_kit_files_or_https(self):
        for ref in ("http://example.com/x", "ftp://x", "file:///c:/x", "skills/build-eval-script/SKILL.md",
                    "kit:../server.py", "kit:/etc/passwd", "kit:C:\\Windows\\win.ini", "kit:northwind/answer-key.md",
                    "kit:northwind/missing.md", "kit:", ""):
            with self.subTest(ref=ref):
                data = ch.bundled_data()
                lesson_of(data, "several-runs")["sources"][0]["ref"] = ref
                with self.assertRaises(L.LessonError):
                    L.validate_course(data)

    def test_https_refs_pass_the_schema(self):
        lesson_of(self.data, "several-runs")["sources"][0]["ref"] = "https://example.com/page"
        L.validate_course(self.data)

    def test_related_must_name_real_lessons_and_glossary_terms(self):
        lesson_of(self.data, "several-runs")["related"] = {"lessons": ["nope"]}
        self.fails("unknown lesson")
        lesson_of(self.data, "several-runs")["related"] = {"glossary": ["Nope"]}
        with self.assertRaises(L.LessonError):
            L.validate_course(self.data, {"checker"})

    def test_course_from_data_refuses_invalid_content(self):
        self.data["version"] = 9
        with self.assertRaises(L.LessonError):
            L.Course.from_data(self.data)

    def test_load_bundled_reports_missing_or_broken_files(self):
        with mock.patch.object(L.resources, "read_text", side_effect=resources.ResourceNotFound("x")):
            with self.assertRaises(L.LessonError):
                L.load_bundled()
        with mock.patch.object(L.resources, "read_text", return_value="{not json"):
            with self.assertRaises(L.LessonError):
                L.load_bundled()

    def test_every_problem_is_listed_not_just_the_first(self):
        lesson_of(self.data, "several-runs")["minutes"] = 0
        lesson_of(self.data, "several-runs")["title"] = ""
        with self.assertRaises(L.LessonError) as ctx:
            L.validate_course(self.data)
        self.assertGreaterEqual(len(ctx.exception.problems), 2)


class KitReferences(unittest.TestCase):
    def test_bundled_files_are_readable(self):
        for ref in ("kit:skills/build-eval-script/SKILL.md", "kit:skills/make-eval-fixtures/SKILL.md",
                    "kit:northwind/northwind-test-cases-reference.md", "kit:lessons/hook/requirements.md",
                    "kit:lessons/demo/test-cases.md"):
            with self.subTest(ref=ref):
                self.assertEqual(L.kit_read_path(ref), "kit/" + ref[4:])
                self.assertTrue(L.kit_ref_allowed(ref))

    def test_traversal_and_absolute_paths_are_refused(self):
        bad = ("kit:../server.py", "kit:../../eval_coach/engine.py", "kit:northwind/../../engine.py",
               "kit:skills/../../content/steps.json", "kit:/etc/passwd", "kit:\\Windows\\win.ini",
               "kit:C:\\Windows\\win.ini", "kit:C:/Windows/win.ini", "kit:..\\server.py", "kit:./skills/x",
               "kit:skills//build-eval-script/SKILL.md", "kit:skills/build-eval-script/SKILL.md/",
               "kit:skills/build-eval-script/SKILL.md.", "kit:skills/build-eval-script/SKILL.md ",
               "kit:northwind/fixture-bad.txt:stream", "kit:\x00", "kit:", "kit:skills", "kit:northwind/NUL",
               "kit:northwind/CON", "kit:%2e%2e/server.py", "http://example.com", "skills/build-eval-script/SKILL.md",
               "", None, 5)
        for ref in bad:
            with self.subTest(ref=ref):
                with self.assertRaises(resources.ResourceNotFound):
                    L.kit_read_path(ref)
                self.assertFalse(L.kit_ref_allowed(ref))

    def test_the_answer_key_is_never_readable_in_any_spelling(self):
        for ref in ("kit:northwind/answer-key.md", "kit:northwind/Answer-Key.md", "kit:NORTHWIND/ANSWER-KEY.MD",
                    "kit:lessons/answer-key.md"):
            with self.subTest(ref=ref), self.assertRaises(resources.ResourceNotFound):
                L.kit_read_path(ref)

    def test_short_names_and_aliases_of_the_answer_key_are_refused(self):
        for ref in ("kit:northwind/ANSWER~1.MD", "kit:northwind/answer~1.md", "kit:NORTHWIND/ANSWER~1.MD",
                    "kit:NORTHW~1/answer-key.md", "kit:northwind/ANSWER~1", "kit:northwind/FIXTUR~1.TXT",
                    "kit:northwind/answer-key.md::$DATA", "kit:northwind/answer-key.md:stream",
                    "kit:northwind/answer-key.md.", "kit:northwind/answer-key.md ", "kit:northwind/answer-key.md..."):
            with self.subTest(ref=ref), self.assertRaises(resources.ResourceNotFound):
                L.kit_read_path(ref)
            self.assertFalse(L.kit_ref_allowed(ref))

    def test_a_path_that_resolves_to_the_answer_key_is_refused_by_identity(self):
        real = "kit/northwind/answer-key.md"
        with mock.patch.object(L.resources, "canonical", return_value=real):
            with self.assertRaises(resources.ResourceNotFound):
                L.kit_read_path("kit:northwind/harmless-alias.txt")

    def test_canonical_resolves_case_and_short_name_aliases_on_disk(self):
        self.assertEqual(resources.canonical("kit/northwind/ANSWER-KEY.MD").lower(), "kit/northwind/answer-key.md")
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            target = str(helpers.KIT / "northwind" / "answer-key.md")
            if not ctypes.windll.kernel32.GetShortPathNameW(target, buf, 260) or "~" not in buf.value:
                self.skipTest("this volume has no 8.3 short names")
            short = buf.value.split("\\")[-1]
        except (AttributeError, OSError):
            self.skipTest("short names are a Windows feature")
        self.assertEqual(resources.canonical("kit/northwind/" + short), "kit/northwind/answer-key.md")

    def test_only_the_kit_folder_is_reachable(self):
        for ref in ("kit:content/steps.json", "kit:../content/steps.json", "kit:web/index.html"):
            with self.subTest(ref=ref), self.assertRaises(resources.ResourceNotFound):
                L.kit_read_path(ref)


class Shuffling(unittest.TestCase):
    def setUp(self):
        self.item = mini_choice(("a b", "c d", "e f", "g h"))

    def order(self, seed, context="ctx"):
        return [o["id"] for o in L.public_options(self.item, seed, context)]

    def test_same_seed_gives_the_same_order_every_time(self):
        for seed in ("alpha", "beta", "0123456789abcdef"):
            self.assertEqual(self.order(seed), self.order(seed))

    def test_order_survives_a_reload(self):
        course = ch.bundled_course()
        first = L.public_activity("several-runs", course.get("several-runs")["activities"][0], None, "seed-1", {})
        again = L.public_activity("several-runs", ch.bundled_course().get("several-runs")["activities"][0], None,
                                  "seed-1", {})
        self.assertEqual(first, again)

    def test_different_seeds_give_different_orders(self):
        orders = {tuple(self.order(f"seed-{n}")) for n in range(30)}
        self.assertGreater(len(orders), 3)

    def test_context_changes_the_order_too(self):
        orders = {tuple(self.order("seed", f"ctx-{n}")) for n in range(30)}
        self.assertGreater(len(orders), 3)

    def test_every_option_is_present_once(self):
        self.assertEqual(sorted(self.order("x")), ["a", "b", "c", "d"])

    def test_public_options_carry_only_id_and_text(self):
        for option in L.public_options(self.item, "x", "c"):
            self.assertEqual(set(option), {"id", "text"})

    def test_an_order_activity_is_never_shown_already_solved(self):
        answer = [i["id"] for i in ORDER_ACTIVITY["items"]]
        for n in range(25):
            view = L.public_activity("several-runs", ORDER_ACTIVITY, None, f"seed-{n}", {})
            with self.subTest(seed=n):
                self.assertNotEqual([i["id"] for i in view["items"]], answer)
                self.assertEqual(sorted(i["id"] for i in view["items"]), sorted(answer))

    def test_sort_items_are_shuffled_by_seed_not_listed_in_authoring_order(self):
        activity = activity_of(ch.bundled_data(), "compare-sort")
        orders = {tuple(i["id"] for i in L.public_activity("surprise", activity, None, f"s{n}", {})["items"])
                  for n in range(20)}
        self.assertGreater(len(orders), 3)


class NoEarlyAnswers(unittest.TestCase):
    """Correct answers, buckets, expected verdicts and the right order stay on the server until answered."""

    SECRET_KEYS = {"correct", "expected", "bucket", "feedback_right", "feedback_wrong", "min_correct"}

    def setUp(self):
        self.course = ch.bundled_course()
        self.reasons = json.loads(resources.read_text("content/lesson-ui.json"))["rule_reasons"]

    def test_no_activity_view_contains_an_answer_before_it_is_answered(self):
        for lesson in self.course.data["lessons"]:
            for activity in lesson["activities"]:
                view = L.public_activity(lesson["id"], activity, None, "seed", self.reasons)
                with self.subTest(activity=activity["id"]):
                    self.assertFalse(set(ch.walk_keys(view)) & self.SECRET_KEYS)
                    self.assertIsNone(view.get("result"))
                    self.assertFalse(view["passed"])

    def test_no_option_feedback_is_shown_before_answering(self):
        for lesson in self.course.data["lessons"]:
            for activity in lesson["activities"]:
                if activity["type"] != "choice":
                    continue
                text = json.dumps(L.public_activity(lesson["id"], activity, None, "seed", self.reasons))
                for option in activity["options"]:
                    self.assertNotIn(option["feedback"], text)

    def test_sort_and_rule_lab_views_omit_item_feedback_and_expected_text(self):
        sort = activity_of(self.course.data, "compare-sort")
        text = json.dumps(L.public_activity("surprise", sort, None, "seed", self.reasons))
        for item in sort["items"]:
            self.assertNotIn(item["feedback"], text)
        lab = activity_of(self.course.data, "rules-lab")
        view = L.public_activity("rules", lab, None, "seed", self.reasons)
        self.assertEqual(set(view["cases"][0]), {"key", "sample", "rule", "id"})
        self.assertNotIn("expected", json.dumps(view))

    def test_rule_lab_view_carries_each_rules_explanation_when_present(self):
        lab = activity_of(self.course.data, "rules-lab")
        view = L.public_activity("rules", lab, None, "seed", self.reasons)
        self.assertEqual([r["explain"] for r in view["rules"]], [r["explain"] for r in lab["rules"]])
        bare = dict(lab, rules=[{k: v for k, v in r.items() if k != "explain"} for r in lab["rules"]])
        view = L.public_activity("rules", bare, None, "seed", self.reasons)
        self.assertTrue(all(set(r) == {"id", "label"} for r in view["rules"]))

    def test_order_feedback_is_not_in_the_view(self):
        order = ORDER_ACTIVITY
        text = json.dumps(L.public_activity("several-runs", order, None, "seed", self.reasons))
        self.assertNotIn(order["feedback_right"], text)
        self.assertNotIn(order["feedback_wrong"], text)

    def test_a_wrong_choice_shows_only_that_options_feedback(self):
        activity = activity_of(self.course.data, "generate-spot")
        wrong = ch.wrong_option(activity)
        entry = {"passed": False, "last": {"option": wrong}}
        view = L.public_activity("several-runs", activity, entry, "seed", self.reasons)
        self.assertEqual(view["result"]["chosen"], wrong)
        self.assertNotIn("explanations", view["result"])
        text = json.dumps(view)
        chosen = next(o for o in activity["options"] if o["id"] == wrong)
        self.assertIn(chosen["feedback"], text)
        for option in activity["options"]:
            if option["id"] != wrong:
                self.assertNotIn(option["feedback"], text)

    def test_a_passed_choice_explains_every_option(self):
        activity = activity_of(self.course.data, "generate-spot")
        entry = {"passed": True, "last": {"option": ch.correct_option(activity)}}
        view = L.public_activity("several-runs", activity, entry, "seed", self.reasons)
        self.assertEqual(len(view["result"]["explanations"]), len(activity["options"]))

    def test_a_failed_order_does_not_reveal_the_answer(self):
        activity = ORDER_ACTIVITY
        wrong = ch.wrong_answer(activity)
        entry = {"passed": False, "last": wrong}
        view = L.public_activity("several-runs", activity, entry, "seed", self.reasons)
        self.assertEqual(view["result"]["feedback"], activity["feedback_wrong"])
        self.assertFalse(set(ch.walk_keys(view)) & self.SECRET_KEYS)

    def test_a_failed_sort_reports_only_a_count(self):
        activity = activity_of(self.course.data, "compare-sort")
        entry = {"passed": False, "last": ch.wrong_answer(activity)}
        view = L.public_activity("surprise", activity, entry, "seed", self.reasons)
        self.assertEqual(view["result"]["right"], len(activity["items"]) - 1)
        self.assertNotIn("feedback", view["result"])
        self.assertFalse(set(ch.walk_keys(view)) & self.SECRET_KEYS)

    def test_a_failed_rule_lab_reports_only_a_count(self):
        activity = activity_of(self.course.data, "rules-lab")
        entry = {"passed": False, "last": ch.wrong_answer(activity)}
        view = L.public_activity("rules", activity, entry, "seed", self.reasons)
        self.assertEqual(view["result"]["right"], len(activity["cases"]) - 1)
        self.assertNotIn("details", view["result"])

    def test_a_passed_rule_lab_shows_real_verdicts_and_reasons(self):
        activity = activity_of(self.course.data, "rules-lab")
        entry = {"passed": True, "last": ch.correct_answer(activity)}
        details = L.public_activity("rules", activity, entry, "seed", self.reasons)["result"]["details"]
        self.assertEqual(len(details), len(activity["cases"]))
        by_key = {d["key"]: d for d in details}
        for case in activity["cases"]:
            self.assertEqual(by_key[L.case_key(case)]["verdict"], case["expected"])
            self.assertTrue(by_key[L.case_key(case)]["reason"])

    def test_public_retrieval_has_no_answers(self):
        lesson = self.course.get("several-runs")
        view = L.public_retrieval("several-runs", lesson["retrieval"][0], "seed")
        self.assertEqual(set(view), {"prompt", "options"})
        self.assertFalse(set(ch.walk_keys(view)) & self.SECRET_KEYS)
        self.assertNotIn("feedback", json.dumps(view))


class RuleKinds(unittest.TestCase):
    def rule(self, kind, **params):
        return {"id": "r", "label": "x", "kind": kind, "params": params}

    def test_word_count_under_is_strict(self):
        rule = self.rule("word_count_under", limit=5)
        self.assertTrue(L.evaluate_rule(rule, "one two three four")[0])
        self.assertFalse(L.evaluate_rule(rule, "one two three four five")[0])
        self.assertFalse(L.evaluate_rule(rule, "one two three four five six")[0])
        self.assertEqual(L.evaluate_rule(rule, "a  b\n c\t d")[1], {"count": 4, "limit": 5})

    def test_word_count_counts_whitespace_separated_tokens(self):
        rule = self.rule("word_count_under", limit=3)
        self.assertTrue(L.evaluate_rule(rule, "a & b")[0] is False)
        self.assertTrue(L.evaluate_rule(rule, "")[0])

    def test_all_present_ignores_case_and_matches_inside_words(self):
        rule = self.rule("all_present", terms=["budget", "Date"])
        self.assertTrue(L.evaluate_rule(rule, "BUDGET and updated")[0])
        passed, facts = L.evaluate_rule(rule, "budget only")
        self.assertFalse(passed)
        self.assertEqual(facts["missing"], ["Date"])

    def test_none_present_ignores_case_and_matches_inside_words(self):
        rule = self.rule("none_present", terms=["proud"])
        self.assertFalse(L.evaluate_rule(rule, "The team proudly shipped it")[0])
        self.assertFalse(L.evaluate_rule(rule, "PROUD")[0])
        self.assertTrue(L.evaluate_rule(rule, "Shipped on Friday")[0])
        self.assertEqual(L.evaluate_rule(rule, "so proud")[1]["found"], ["proud"])

    def test_all_labels_are_exact_and_may_appear_anywhere(self):
        rule = self.rule("all_labels", labels=["Blocker:", "Need:"])
        self.assertTrue(L.evaluate_rule(rule, "x Blocker: y. Need: z")[0])
        self.assertFalse(L.evaluate_rule(rule, "blocker: y. Need: z")[0])
        self.assertFalse(L.evaluate_rule(rule, "Blocker y. Need: z")[0])
        self.assertEqual(L.evaluate_rule(rule, "Need: z")[1]["missing"], ["Blocker:"])

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(L.AnswerError):
            L.evaluate_rule(self.rule("run_code"), "x")

    def test_same_input_gives_the_same_verdict_every_time(self):
        reasons = json.loads(resources.read_text("content/lesson-ui.json"))["rule_reasons"]
        cases = (("word_count_under", {"limit": 4}, "one two three"), ("all_present", {"terms": ["a", "b"]}, "a"),
                 ("none_present", {"terms": ["zz"]}, "zz"), ("all_labels", {"labels": ["X:"]}, "X: y"))
        for kind, params, text in cases:
            with self.subTest(kind=kind):
                results = {json.dumps(L.rule_result(self.rule(kind, **params), text, reasons)) for _ in range(50)}
                self.assertEqual(len(results), 1)

    def test_result_has_a_verdict_and_a_plain_reason_for_every_kind(self):
        reasons = json.loads(resources.read_text("content/lesson-ui.json"))["rule_reasons"]
        pairs = (("word_count_under", {"limit": 2}, "a", "pass", "1 words"), ("word_count_under", {"limit": 2}, "a b", "fail", "2 words"),
                 ("all_present", {"terms": ["a"]}, "a", "pass", "All found: a"),
                 ("all_present", {"terms": ["a", "b"]}, "a", "fail", "Missing: b"),
                 ("none_present", {"terms": ["a"]}, "b", "pass", "None of these appear: a"),
                 ("none_present", {"terms": ["a"]}, "a", "fail", "Found: a"),
                 ("all_labels", {"labels": ["X:"]}, "X:", "pass", "All labels found: X:"),
                 ("all_labels", {"labels": ["X:", "Y:"]}, "X:", "fail", "Missing labels: Y:"))
        for kind, params, text, verdict, reason in pairs:
            with self.subTest(kind=kind, text=text):
                result = L.rule_result(self.rule(kind, **params), text, reasons)
                self.assertEqual(result["verdict"], verdict)
                self.assertIn(reason, result["reason"])

    def test_every_rule_kind_in_the_schema_has_reason_wording(self):
        reasons = json.loads(resources.read_text("content/lesson-ui.json"))["rule_reasons"]
        for kind in L.RULE_KINDS:
            self.assertEqual(set(reasons[kind]), {"pass", "fail"})

    def test_sample_text_detection_ignores_spacing_and_case(self):
        lab = {"samples": [{"id": "s", "label": "x", "text": "Blocker: none. Need: nothing."}]}
        self.assertTrue(L.rule_is_sample_text(lab, "  blocker:   NONE. need: nothing. "))
        self.assertFalse(L.rule_is_sample_text(lab, "Blocker: none. Need: nothing else."))


class Grading(unittest.TestCase):
    def test_choice(self):
        item = mini_choice()
        self.assertEqual(L.grade(item, {"option": "a"}), (True, {"option": "a"}))
        self.assertEqual(L.grade(item, {"option": "b"}), (False, {"option": "b"}))

    def test_choice_rejects_unknown_options_and_bad_shapes(self):
        item = mini_choice()
        for answer in ({"option": "z"}, {}, {"option": None}, {"option": 1}, [], "a", None):
            with self.subTest(answer=answer), self.assertRaises(L.AnswerError):
                L.grade(item, answer)

    def order_activity(self):
        return {"type": "order", "items": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}]}

    def test_order(self):
        activity = self.order_activity()
        self.assertTrue(L.grade(activity, {"order": ["a", "b", "c"]})[0])
        self.assertFalse(L.grade(activity, {"order": ["b", "a", "c"]})[0])
        self.assertFalse(L.grade(activity, {"order": ["c", "b", "a"]})[0])

    def test_order_must_list_every_item_once(self):
        activity = self.order_activity()
        for answer in ({"order": ["a", "b"]}, {"order": ["a", "a", "b"]}, {"order": ["a", "b", "c", "d"]},
                       {"order": "abc"}, {}, {"order": ["a", "b", "x"]}):
            with self.subTest(answer=answer), self.assertRaises(L.AnswerError):
                L.grade(activity, answer)

    def sort_activity(self):
        return {"type": "sort", "buckets": [{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}],
                "items": [{"id": "1", "bucket": "x"}, {"id": "2", "bucket": "y"}, {"id": "3", "bucket": "x"}]}

    def test_sort(self):
        activity = self.sort_activity()
        self.assertTrue(L.grade(activity, {"placements": {"1": "x", "2": "y", "3": "x"}})[0])
        self.assertFalse(L.grade(activity, {"placements": {"1": "x", "2": "x", "3": "x"}})[0])

    def test_sort_must_place_every_item_in_a_real_bucket(self):
        activity = self.sort_activity()
        for answer in ({"placements": {"1": "x", "2": "y"}}, {"placements": {"1": "x", "2": "y", "3": "q"}},
                       {"placements": {"1": "x", "2": "y", "3": "x", "4": "x"}}, {"placements": []}, {}):
            with self.subTest(answer=answer), self.assertRaises(L.AnswerError):
                L.grade(activity, answer)

    def lab(self):
        return {"type": "rule_lab", "cases": [{"sample": "s", "rule": "r1", "expected": "pass"},
                                              {"sample": "s", "rule": "r2", "expected": "fail"}]}

    def test_rule_lab_needs_every_case_right(self):
        lab = self.lab()
        self.assertTrue(L.grade(lab, {"cases": {"s|r1": "pass", "s|r2": "fail"}})[0])
        self.assertFalse(L.grade(lab, {"cases": {"s|r1": "pass", "s|r2": "pass"}})[0])

    def test_rule_lab_accepts_pass_fail_in_any_case_and_stores_clean_words(self):
        passed, last = L.grade(self.lab(), {"cases": {"s|r1": " PASS ", "s|r2": "F"}})
        self.assertTrue(passed)
        self.assertEqual(last, {"cases": {"s|r1": "pass", "s|r2": "fail"}})

    def test_rule_lab_rejects_missing_extra_and_invalid_predictions(self):
        for answer in ({"cases": {"s|r1": "pass"}}, {"cases": {"s|r1": "pass", "s|r2": "fail", "s|r3": "pass"}},
                       {"cases": {"s|r1": "pass", "s|r2": "maybe"}}, {"cases": {"s|r1": 1, "s|r2": 0}},
                       {"cases": []}, {}):
            with self.subTest(answer=answer), self.assertRaises(L.AnswerError):
                L.grade(self.lab(), answer)

    def test_reflection_passes_at_the_minimum_word_count(self):
        activity = {"type": "reflection", "min_words": 4}
        self.assertFalse(L.grade(activity, {"text": "one two three"})[0])
        self.assertTrue(L.grade(activity, {"text": "one two three four"})[0])
        self.assertTrue(L.grade(activity, {"text": "one  two\nthree\tfour five"})[0])
        self.assertFalse(L.grade(activity, {"text": "   "})[0])

    def test_reflection_text_is_saved_even_when_too_short(self):
        self.assertEqual(L.grade({"type": "reflection", "min_words": 4}, {"text": "short"}), (False, {"text": "short"}))

    def test_reflection_must_be_text(self):
        for answer in ({"text": 5}, {}, {"text": None}):
            with self.subTest(answer=answer), self.assertRaises(L.AnswerError):
                L.grade({"type": "reflection", "min_words": 1}, answer)

    def test_the_answer_must_be_an_object(self):
        for answer in (None, [], "x", 3):
            with self.subTest(answer=answer), self.assertRaises(L.AnswerError):
                L.grade(mini_choice(), answer)

    def test_cli_activities_are_not_graded_here(self):
        with self.assertRaises(L.AnswerError):
            L.grade({"type": "cli_demo"}, {})

    def test_every_bundled_activity_passes_with_its_own_answer_and_fails_with_a_wrong_one(self):
        course = ch.bundled_course()
        graded = 0
        for lesson in course.data["lessons"]:
            for activity in lesson["activities"]:
                if activity["type"] == "cli_demo":
                    continue
                with self.subTest(activity=activity["id"]):
                    target = activity["question"] if activity["type"] in ("cli_compare", "cli_practice") else activity
                    body = ch.correct_answer(activity)
                    passed = (L.grade_choice(target, body) if target is not activity
                              else L.grade(activity, body))[0]
                    self.assertTrue(passed)
                    wrong = ch.wrong_answer(activity)
                    failed = (L.grade_choice(target, wrong) if target is not activity
                              else L.grade(activity, wrong))[0]
                    self.assertFalse(failed)
                    graded += 1
        self.assertGreater(graded, 20)


class StartUp(unittest.TestCase):
    def test_broken_course_content_stops_the_app_with_a_plain_message(self):
        import contextlib
        import io

        from eval_coach import __main__ as entry

        stderr = io.StringIO()
        with mock.patch.object(entry, "load_bundled", side_effect=L.LessonError(["lesson 'rules': minutes must be a positive whole number"])), \
                contextlib.redirect_stderr(stderr):
            code = entry.main(["--no-browser"])
        self.assertEqual(code, 1)
        self.assertIn("could not load its course content", stderr.getvalue())
        self.assertIn("minutes must be a positive whole number", stderr.getvalue())


class FromTheZipapp(unittest.TestCase):
    def test_the_course_loads_and_the_kit_is_readable_inside_a_zipapp(self):
        import shutil
        import subprocess
        import sys
        import tempfile
        import zipapp
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-zip-lessons-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        target = tmp / "app.pyz"
        zipapp.create_archive(str(helpers.ROOT / "app"), str(target), main="eval_coach.__main__:main",
                              filter=lambda p: "__pycache__" not in p.parts)
        script = (
            "import sys, json; sys.path.insert(0, sys.argv[1])\n"
            "from eval_coach import lessons as L, resources as r\n"
            "course = L.load_bundled()\n"
            "refused = []\n"
            "for ref in ('kit:../content/steps.json', 'kit:northwind/answer-key.md', 'kit:/etc/passwd'):\n"
            "    try:\n"
            "        L.kit_read_path(ref)\n"
            "    except r.ResourceNotFound:\n"
            "        refused.append(ref)\n"
            "print(json.dumps({'archive': bool(r._ARCHIVE), 'lessons': list(course.by_id),\n"
            "  'kit': len(r.read_text(L.kit_read_path('kit:lessons/hook/requirements.md'))),\n"
            "  'refused': refused, 'ui': 'errors' in json.loads(r.read_text('content/lesson-ui.json'))}))\n"
        )
        out = subprocess.run([sys.executable, "-c", script, str(target)], capture_output=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr.decode())
        data = json.loads(out.stdout)
        self.assertTrue(data["archive"])
        self.assertEqual(data["lessons"], list(LESSON_IDS) + list(PART_1.lesson_ids) + list(PART_2.lesson_ids)
                         + list(PART_4.lesson_ids))
        self.assertGreater(data["kit"], 100)
        self.assertEqual(len(data["refused"]), 3)
        self.assertTrue(data["ui"])


if __name__ == "__main__":
    unittest.main()
