"""Part 1 content: kit files, lessons, steps, glossary and the discovery-before-theory rule.

Specs part-1-course and part-1-exercise-steps. The engine behavior is in test_part_1_steps.py.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import course_helpers as ch
import helpers
from helpers import KIT, ROOT

from eval_coach import lessons as L
from eval_coach import project, resources, state
from eval_coach.engine import Engine, EngineError

PART1_KIT = KIT / "part1"
KIT_FILES = {"rough-notes.txt", "typical-gaps.md", "frameworks-map.md", "sample-rtcc.md", "sample-rise.md"}
LESSON_ORDER = ["p1-mission", "p1-gaps", "p1-frameworks", "p1-benefits"]
PRE_REVEAL_LESSONS = ("p1-mission", "p1-gaps")
PRE_REVEAL_STEPS = ("cold", "score")
FRAMEWORK_NAMES = re.compile(r"\b(RTCC|RISE|CO-STAR|RISEN)\b|framework", re.I)
STAGE_THREE = re.compile(r"stage\s*3|certif", re.I)
TAKEAWAY = "Give the AI what it needs. Use a framework, or build your own."
# p1-frameworks holds the list of five categories and one table per framework, so it is capped at 420.
CAPS = {"p1-mission": 450, "p1-gaps": 300, "p1-frameworks": 420, "p1-benefits": 400}
NOTE_HEADING = "**Stage 3 note (optional).**"
SUBMISSION_STEPS = re.compile(r"https?://|@|\bupload\b|\bsubmission form\b|\bsend (it|them) to\b|\bhow to submit\b", re.I)
RECOMMENDS = re.compile(
    r"(best|better|recommended|preferred|ideal|superior)\s+(prompting\s+)?framework|framework\s+is\s+(better|best)|"
    r"\b(RTCC|RISE)\s+is\s+(better|best|the best|recommended)|the one to use|you should (use|choose|pick) (RTCC|RISE)|"
    r"we recommend|i recommend", re.I)


def lessons_data():
    return json.loads(resources.read_text("content/part-1-lessons.json"))


def steps_data():
    return json.loads(resources.read_text("content/part-1-steps.json"))["steps"]


def lesson(lesson_id):
    return next(x for x in lessons_data()["lessons"] if x["id"] == lesson_id)


def strings(node):
    """Every string a participant could read inside one JSON-shaped value, keys excluded."""
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


def refs_of(lesson_data):
    return [s["ref"] for s in lesson_data["sources"]] + [lesson_data["primary_source"]["ref"]]


EXPECTED_TABLES = {
    "RTCC": [("R", "Role", "1"), ("T", "Task", "2"), ("C", "Context", "3"), ("C", "Constraints", "4")],
    "RISE": [("R", "Role", "1"), ("I", "Input", "3"), ("S", "Steps", "2"), ("E", "Expectation", "5")],
}


def framework_tables(text):
    """The rows of each framework's table as (letter, label, first category number), keyed by framework."""
    found = {}
    for name in ("RTCC", "RISE"):
        block = text.split(f"{name}:", 1)[1]
        rows = [line for line in block.split("\n\n", 2)[1].splitlines()]
        assert rows[0].startswith("| Letter | Label | What you write there | Covers category |"), rows[0]
        cells = [[c.strip() for c in row.strip("|").split("|")] for row in rows[2:]]
        found[name] = [(c[0], c[1], c[3][0]) for c in cells]
    return found


def northwind_notes():
    reference = (KIT / "northwind" / "northwind-test-cases-reference.md").read_text(encoding="utf-8")
    block = reference.split("## Test input", 1)[1].split("##", 1)[0]
    return [line for line in block.splitlines() if line.strip()]


class KitFiles(unittest.TestCase):
    def test_the_part_one_kit_holds_exactly_these_files(self):
        self.assertEqual({p.name for p in PART1_KIT.iterdir()}, KIT_FILES)

    def test_the_rough_notes_are_the_northwind_notes(self):
        notes = [line for line in (PART1_KIT / "rough-notes.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(notes), 7)
        self.assertEqual(notes, northwind_notes())

    def test_typical_gaps_hold_the_listed_gaps_each_with_its_bucket(self):
        text = (PART1_KIT / "typical-gaps.md").read_text(encoding="utf-8")
        expected = {
            "Sounds like I'm bragging": "1.", "Reads like a formal report, not a quick note": "1.",
            "An email with a subject line, not a Teams message": "2.", "Didn't know who the update was for": "3.",
            "Left out that I work on two clients plus internal work": "3.", "Way over 150 words": "4.",
            "Went Monday to Friday instead of by client": "4.", "Blocker buried and no clear ask": "5.",
            "Never said what I need from my lead": "5.",
        }
        for gap, bucket in expected.items():
            with self.subTest(gap=gap):
                row = next(line for line in text.splitlines() if line.startswith(f"| {gap} |"))
                self.assertIn(f"| {bucket} ", row)
        for gap in ("Made up a detail about Contoso", "Just felt boring"):
            self.assertIn(f"| {gap} |", text.split("## Gaps to set aside for now", 1)[1])

    def test_the_reveal_table_maps_both_samples_and_marks_the_partial_fits(self):
        text = (PART1_KIT / "frameworks-map.md").read_text(encoding="utf-8")
        for name in ("RTCC", "RISE", "CO-STAR", "RISEN"):
            self.assertIn(name, text)
        self.assertEqual(text.count("(also touches"), 2)
        self.assertIn("4. Limits and format (also touches 5)", text)
        self.assertIn("(also touches 4)", text)
        self.assertRegex(text, r"(?i)covering what your task needs matters more than the letters")
        self.assertRegex(text, r"(?i)more exist")
        self.assertRegex(text, r"(?i)build your own labels")
        self.assertEqual(framework_tables(text), EXPECTED_TABLES)

    def test_the_samples_carry_the_notes_and_no_placeholder(self):
        notes = northwind_notes()
        for name in ("sample-rtcc.md", "sample-rise.md"):
            text = (PART1_KIT / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertNotIn("[paste notes]", text)
                for note in notes:
                    self.assertIn(note, text)
                self.assertRegex(text, r"(?m)^Role:")

    def test_no_kit_file_uses_meeting_tool_or_room_wording(self):
        for path in PART1_KIT.iterdir():
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotRegex(text, r"(?i)copilot|breakout|facilitator|presenter|\broom\b|handout|session")

    def test_the_kit_viewer_reads_the_open_files_and_holds_the_samples_back(self):
        home = Path(tempfile.mkdtemp(prefix="eval-coach-kit-"))
        self.addCleanup(shutil.rmtree, home, True)
        engine = Engine(home, helpers.FakeTerminal())
        self.addCleanup(engine.shutdown)
        for name in ("rough-notes.txt", "typical-gaps.md", "frameworks-map.md"):
            self.assertEqual(engine.kit_file(f"kit:part1/{name}")["kit"]["name"], name)
        for name in ("sample-rtcc.md", "sample-rise.md"):
            with self.assertRaises(EngineError) as ctx:
                engine.kit_file(f"kit:part1/{name}")
            self.assertEqual(ctx.exception.code, "bad_ref")


class Lessons(unittest.TestCase):
    def test_the_course_has_four_lessons_and_five_steps_in_the_fixed_order(self):
        part = state.PART_1
        self.assertEqual(list(part.course), [
            ("lesson", "p1-mission"), ("step", "cold"), ("step", "score"), ("lesson", "p1-gaps"),
            ("lesson", "p1-frameworks"), ("step", "rewrite"), ("step", "rescore"), ("lesson", "p1-benefits"),
            ("step", "own")])
        self.assertEqual([x["id"] for x in lessons_data()["lessons"]], LESSON_ORDER)
        self.assertEqual(part.mission, "p1-mission")

    def test_lesson_titles_say_what_the_learner_gets_and_the_sorting_device_is_never_named(self):
        titles = [x["title"] for x in lessons_data()["lessons"]]
        self.assertEqual(titles, ["Your mission", "What your first prompt left out",
                                  "Frameworks: ready-made labels for what a prompt needs",
                                  "Four ways a structured prompt helps you"])
        pieces = [text_of(lessons_data()), text_of(steps_data())]
        pieces += [(PART1_KIT / name).read_text(encoding="utf-8") for name in KIT_FILES]
        pieces += [text_of([t for t in json.loads(resources.read_text("content/glossary.json"))["terms"]
                            if t["lesson"].startswith("p1-")])]
        for text in pieces:
            self.assertIsNone(re.search(r"(?i)\bbuckets?\b", text))

    def test_the_bundled_course_loads_and_ids_are_unique_across_parts(self):
        course = L.load_bundled()
        self.assertTrue(set(LESSON_ORDER) <= set(course.by_id))
        self.assertEqual(state.duplicate_ids(), [])

    def test_bodies_stay_within_their_caps(self):
        for lesson_id, cap in CAPS.items():
            with self.subTest(lesson=lesson_id):
                self.assertLessEqual(len(lesson(lesson_id)["body"].split()), cap)

    def test_the_mission_is_one_page_with_no_questions(self):
        mission = lesson("p1-mission")
        self.assertEqual((mission["activities"], mission["retrieval"]), ([], []))
        body = mission["body"]
        self.assertIn("blind trust or blind distrust", body)
        self.assertIn("because you checked it", body)
        self.assertIn("the Practice task: a ready-made example, for practice only and never something to submit", body)
        self.assertNotIn("Northwind", body)
        self.assertIn("ask clearly, know what you need, turn it into rules, score the result, improve, and keep a record.", body)
        for reason in ("sounds sure of itself even when it is wrong", "only an opinion until you measure it",
                       "Answers change from one try to the next"):
            self.assertIn(reason, body)
        self.assertRegex(body, r"(?i)in your own words")

    def test_each_lesson_after_the_mission_has_the_shape_of_part_threes(self):
        for lesson_id in LESSON_ORDER[1:]:
            data = lesson(lesson_id)
            body = data["body"]
            with self.subTest(lesson=lesson_id):
                self.assertTrue(body.startswith("**In the method.**"))
                self.assertLess(body.index("**In the method.**"), body.index("**The idea.**"))
                self.assertEqual(body.count("**How this course does it.**"), 1)
                passage = body.split("**How this course does it.**", 1)[1].split("\n\n")[0]
                self.assertLessEqual(len(passage.split()), 120)
                self.assertRegex(passage, r"(?i)other approaches work too|another way")
                self.assertGreaterEqual(len(data["activities"]), 1)
                self.assertGreaterEqual(len(data["retrieval"]), 2)
                self.assertTrue(data["sources"])
                self.assertTrue(data["primary_source"]["why"].strip())

    def test_lessons_cite_only_kit_files_and_each_kit_file_is_cited(self):
        cited = set()
        for lesson_id in LESSON_ORDER:
            for ref in refs_of(lesson(lesson_id)):
                self.assertTrue(ref.startswith("kit:part1/"), ref)
                self.assertTrue(L.kit_ref_allowed(ref), ref)
                cited.add(ref.split("/", 1)[1])
        self.assertEqual(cited, KIT_FILES)

    def test_citation_boundaries_hold_back_the_reveal_and_the_samples(self):
        refs = {lesson_id: refs_of(lesson(lesson_id)) for lesson_id in LESSON_ORDER}
        for lesson_id in PRE_REVEAL_LESSONS:
            self.assertFalse([r for r in refs[lesson_id] if "frameworks-map" in r or "sample-" in r], lesson_id)
        self.assertIn("kit:part1/frameworks-map.md", refs["p1-frameworks"])
        for lesson_id in ("p1-mission", "p1-gaps", "p1-frameworks"):
            self.assertFalse([r for r in refs[lesson_id] if "sample-" in r], lesson_id)
        self.assertIn("kit:part1/sample-rtcc.md", refs["p1-benefits"])
        self.assertIn("kit:part1/sample-rise.md", refs["p1-benefits"])
        for lesson_id in LESSON_ORDER:
            for step in steps_data().values():
                self.assertNotIn("sample-r", json.dumps(step))

    def test_the_sort_in_the_gaps_lesson_has_five_numbered_buckets_and_a_set_aside_group(self):
        sort = next(a for a in lesson("p1-gaps")["activities"] if a["id"] == "gaps-sort")
        labels = [b["label"] for b in sort["buckets"]]
        self.assertEqual(labels[:5], ["1. Who the AI should act as", "2. What exactly to produce",
                                      "3. Background it needs", "4. Limits and format",
                                      "5. What a good result looks like"])
        self.assertIn("aside", [b["id"] for b in sort["buckets"]])
        asides = [i["text"] for i in sort["items"] if i["bucket"] == "aside"]
        self.assertTrue(any("made up" in t.lower() or "invent" in t.lower() for t in asides))
        self.assertTrue(any("boring" in t.lower() for t in asides))
        self.assertEqual(len(sort["items"]), 11)

    def test_the_gaps_lesson_says_the_set_aside_gaps_belong_to_later_parts(self):
        body = lesson("p1-gaps")["body"]
        self.assertIn("Set aside for later.", body)
        self.assertRegex(body, r"(?i)belong to evaluation")
        self.assertRegex(body, r"(?i)typical gaps")
        self.assertRegex(body, r"(?i)not from other people using this app")
        self.assertRegex(body, r"(?i)five common categories")
        self.assertRegex(body, r"(?i)an example, not a complete list")
        self.assertRegex(body, r"(?i)other categories exist")

    def test_the_frameworks_lesson_names_the_mapping_the_partial_fits_and_the_others(self):
        body = lesson("p1-frameworks")["body"]
        for needle in ("samples, not recommendations", "common expansions that other sources define differently",
                       "also touches", "Covering what your task needs matters more than the letters", "CO-STAR and RISEN",
                       "build your own labels", "These are the five categories this course uses. Others exist.",
                       "add the categories your task needs", "The five categories of what a prompt needs"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        self.assertEqual(body.count("| Letter | Label | What you write there | Covers category |"), 2)
        self.assertEqual(framework_tables(body), EXPECTED_TABLES)
        self.assertLess(body.index("The five categories of what a prompt needs"), body.index("RTCC:"))

    def test_the_frameworks_sort_names_the_partial_fits_in_its_feedback(self):
        sort = next(a for a in lesson("p1-frameworks")["activities"] if a["id"] == "fw-map")
        feedback = text_of([i["feedback"] for i in sort["items"]])
        self.assertIn("category 5 fits only partly", feedback)
        self.assertIn("category 4 fits only partly", feedback)
        self.assertEqual(len(sort["items"]), 8)

    def test_the_benefits_lesson_names_four_benefits_the_takeaway_and_the_open_question(self):
        body = lesson("p1-benefits")["body"]
        for label in ("**Completeness.**", "**Better first results.**", "**Easier fixes.**", "**Repeatability.**"):
            self.assertIn(label, body)
        self.assertIn(TAKEAWAY, body)
        self.assertIn("hold the same information under different labels", body)
        self.assertIn("The benefit comes from the structure", body)
        self.assertIn("Real work does not come with a card of requirements. So how do you know the second answer is better?", body)
        self.assertRegex(body, r"(?i)two prompts and two outputs are saved in your project folder")
        question = body.index("how do you know the second answer is better?")
        self.assertLess(question, body.index(NOTE_HEADING))
        self.assertNotRegex(body[question:body.index(NOTE_HEADING)], r"(?i)\bbecause\b|the answer is")

    def test_the_benefits_lesson_asks_for_both_explanations_and_blocks_nothing(self):
        activities = {a["id"]: a for a in lesson("p1-benefits")["activities"]}
        self.assertEqual(activities["ben-explain-plain"]["type"], "reflection")
        self.assertGreaterEqual(activities["ben-explain-plain"]["min_words"], 20)
        self.assertRegex(activities["ben-explain-plain"]["prompt"], r"(?i)not technical")
        self.assertEqual(activities["ben-explain-tech"]["type"], "choice")
        self.assertRegex(activities["ben-explain-tech"]["prompt"], r"(?i)technical colleague")
        for data in lessons_data()["lessons"]:
            for activity in data["activities"]:
                self.assertIn(activity["type"], ("choice", "sort", "reflection"), data["id"])

    def test_the_stage_three_note_is_short_optional_and_names_the_prompt(self):
        body = lesson("p1-benefits")["body"]
        self.assertTrue(body.rstrip().endswith("finish this Part."))
        note = body.split(NOTE_HEADING, 1)[1]
        self.assertLessEqual(len(note.split()), 60)
        self.assertRegex(note, r"\bPrompt\b")
        self.assertIn("The program's own instructions decide what to submit", note)
        self.assertIn("nothing in this note is needed to finish this Part", note)
        self.assertIsNone(SUBMISSION_STEPS.search(note))
        self.assertIsNone(re.search(r"\b20\d\d\b", note))

    def test_stage_three_is_named_nowhere_else_in_part_one(self):
        data = lessons_data()
        for item in data["lessons"]:
            text = text_of(item)
            if item["id"] == "p1-benefits":
                text = text.replace(lesson("p1-benefits")["body"].split(NOTE_HEADING, 1)[1], "")
                text = text.replace(NOTE_HEADING, "")
            with self.subTest(lesson=item["id"]):
                self.assertIsNone(STAGE_THREE.search(text))
        self.assertIsNone(STAGE_THREE.search(text_of(data["step_checks"])))
        self.assertIsNone(STAGE_THREE.search(text_of(steps_data())))
        series_part = next(p for p in json.loads(resources.read_text("content/series.json"))["parts"] if p["id"] == "part-1")
        self.assertIsNone(STAGE_THREE.search(text_of(series_part)))

    def test_no_course_text_recommends_one_framework(self):
        pieces = {"lessons": text_of(lessons_data()), "steps": text_of(steps_data())}
        glossary = json.loads(resources.read_text("content/glossary.json"))["terms"]
        pieces["glossary"] = text_of([t for t in glossary if t["lesson"].startswith("p1-")])
        for kit_name in KIT_FILES:
            pieces[kit_name] = (PART1_KIT / kit_name).read_text(encoding="utf-8")
        for name, text in pieces.items():
            with self.subTest(text=name):
                self.assertIsNone(RECOMMENDS.search(text))

    def test_the_gaps_buckets_and_the_reveal_do_not_leak_before_the_reveal(self):
        for lesson_id in PRE_REVEAL_LESSONS:
            with self.subTest(lesson=lesson_id):
                self.assertIsNone(FRAMEWORK_NAMES.search(text_of(lesson(lesson_id))))
        for step in PRE_REVEAL_STEPS:
            with self.subTest(step=step):
                self.assertIsNone(FRAMEWORK_NAMES.search(text_of(steps_data()[step])))
                check = next(c for c in lessons_data()["step_checks"] if c["step"] == step)
                self.assertIsNone(FRAMEWORK_NAMES.search(text_of(check)))
        for name in ("rough-notes.txt", "typical-gaps.md"):
            self.assertIsNone(FRAMEWORK_NAMES.search((PART1_KIT / name).read_text(encoding="utf-8")), name)
        series_part = next(p for p in json.loads(resources.read_text("content/series.json"))["parts"] if p["id"] == "part-1")
        self.assertIsNone(FRAMEWORK_NAMES.search(series_part["outcome"]))

    def test_the_names_first_appear_in_the_frameworks_lesson(self):
        body = lesson("p1-frameworks")["body"]
        self.assertRegex(body, r"\bRTCC\b")
        self.assertRegex(body, r"\bRISE\b")
        self.assertRegex(body, r"(?i)framework")

    def test_the_step_checks_cover_the_five_steps_once_each_and_never_block(self):
        checks = lessons_data()["step_checks"]
        self.assertEqual(sorted(c["step"] for c in checks), sorted(state.PART_1.step_ids))
        self.assertEqual(len({c["id"] for c in checks}), 5)


class Glossary(unittest.TestCase):
    TERMS = {"Prompt": "idea", "Prompting framework": "idea", "Gap": "idea", "RTCC": "idea",
             "RISE": "idea", "Cold prompt": "course", "Scenario card": "course"}

    def test_the_part_one_terms_are_there_with_the_right_kinds(self):
        terms = {t["term"]: t for t in json.loads(resources.read_text("content/glossary.json"))["terms"]}
        for term, kind in self.TERMS.items():
            with self.subTest(term=term):
                self.assertEqual(terms[term]["kind"], kind)
                self.assertIn(terms[term]["lesson"], LESSON_ORDER)
                if kind == "course":
                    self.assertTrue(terms[term]["meaning"].startswith("In this course,"))

    def test_part_one_and_two_terms_stay_off_the_one_page_card_and_part_three_terms_stay_on_it(self):
        terms = json.loads(resources.read_text("content/glossary.json"))["terms"]
        for term in terms:
            with self.subTest(term=term["term"]):
                if term["term"] in self.TERMS or term["lesson"].startswith("p2-"):
                    self.assertIs(term.get("card"), False)
                else:
                    self.assertNotIn("card", term)

    def test_related_glossary_references_resolve(self):
        L.load_bundled()  # validates every related.glossary against the glossary
        known = {t["term"].casefold() for t in json.loads(resources.read_text("content/glossary.json"))["terms"]}
        for item in lessons_data()["lessons"]:
            for term in item.get("related", {}).get("glossary", []):
                self.assertIn(term.casefold(), known, term)


class Steps(unittest.TestCase):
    def test_the_five_steps_name_their_kinds(self):
        kinds = {step: data["kind"] for step, data in steps_data().items()}
        self.assertEqual(kinds, {"cold": "write_and_run", "score": "score_form", "rewrite": "write_and_run",
                                 "rescore": "score_form", "own": "write_pair"})
        self.assertEqual(set(steps_data()), set(state.PART_1.step_ids))
        for kind in kinds.values():
            self.assertIn(kind, state.STEP_KINDS)

    def test_the_content_loader_accepts_the_steps_and_merges_them(self):
        content, _ = L.load_step_content()
        for step in state.PART_1.step_ids:
            self.assertIn(step, content["steps"])

    def test_every_step_has_the_words_the_page_reads(self):
        for step, data in steps_data().items():
            with self.subTest(step=step):
                for key in ("title", "goal", "why", "instructions", "troubleshooting", "gate", "ui"):
                    self.assertTrue(data[key], key)
                for problem in data["troubleshooting"]:
                    self.assertTrue(problem["problem"].strip() and problem["fix"].strip())
                for gate in data["gate"].values():
                    if "label" in gate:
                        self.assertEqual(set(gate), {"label", "ok", "fail"})

    def test_the_run_steps_type_the_exact_line_and_name_the_best_guess_reply(self):
        part3 = json.loads(resources.read_text("content/steps.json"))["steps"]["generate"]["line"]
        for step in ("cold", "rewrite"):
            data = steps_data()[step]
            self.assertEqual(data["line"], part3)
            self.assertEqual(data["line"], "Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.")
            self.assertIn("go ahead with your best guess", text_of(data["troubleshooting"]))
            self.assertRegex(text_of(data["why"]), r"(?i)other approaches work too")
            self.assertRegex(text_of(data["why"]), r"(?i)holds only your prompt")

    def test_the_divider_is_a_plain_line_that_is_not_a_label(self):
        for step in ("cold", "rewrite"):
            divider = steps_data()[step]["divider"]
            self.assertFalse(re.match(r"^\w[\w ]*:", divider), divider)
            self.assertNotIn("\n", divider)
        self.assertEqual(steps_data()["cold"]["divider"], steps_data()["rewrite"]["divider"])

    def test_the_scenario_card_has_the_five_requirements_and_the_cold_step_does_not_coach(self):
        cold = steps_data()["cold"]
        requirements = cold["scenario"]["requirements"]
        self.assertEqual([r["id"] for r in requirements], ["r1", "r2", "r3", "r4", "r5"])
        self.assertEqual(len(requirements), 5)
        joined = text_of(requirements)
        for needle in ("Teams message", "under 150 words", "grouped by client", "blocker", "factual"):
            self.assertIn(needle, joined)
        text = text_of(cold)
        self.assertNotRegex(text, r"(?i)bucket|label|structure|role|framework")
        self.assertIn("no hints", text)

    def test_the_score_steps_take_their_requirements_from_the_card(self):
        for step in ("score", "rescore"):
            self.assertEqual(steps_data()[step]["requirements_from"], "cold")
        self.assertEqual(steps_data()["score"]["source_step"], "cold")
        self.assertEqual(steps_data()["rescore"]["source_step"], "rewrite")
        self.assertEqual(steps_data()["rescore"]["compare_with"], "score")

    def test_the_score_step_asks_for_a_gap_and_whether_it_was_in_the_prompt(self):
        score = steps_data()["score"]
        self.assertEqual(score["fields"], ["gap", "in_prompt"])
        self.assertEqual([o["id"] for o in score["ui"]["in_prompt_options"]], ["yes", "no", "not_sure"])
        self.assertNotEqual(score["ui"]["gap_label"], score["ui"]["gap_label_all_yes"])
        self.assertRegex(score["ui"]["gap_label_all_yes"], r"(?i)what did your prompt include")

    def test_the_three_label_sets_have_equal_descriptions_and_none_is_chosen_for_you(self):
        labels = steps_data()["rewrite"]["labels"]
        self.assertEqual([x["id"] for x in labels], ["rtcc", "rise", "own"])
        self.assertEqual(len({L.word_count(x["description"]) for x in labels}), 1)
        for item in labels:
            self.assertNotIn("default", item)
            self.assertNotIn("selected", item)
            self.assertNotIn("recommended", json.dumps(item).lower())
        self.assertTrue(steps_data()["rewrite"]["labels"][0]["skeleton"].startswith("Role:"))
        for item in labels[:2]:
            self.assertEqual(len(item["skeleton"].splitlines()), 4)

    def test_the_compare_wording_covers_a_worse_second_answer_and_run_to_run_variation(self):
        compare = steps_data()["rescore"]["compare"]
        self.assertRegex(compare["variation_note"], r"(?i)one run each cannot show how much answers vary")
        self.assertIn("Part 3", compare["variation_note"])
        self.assertRegex(compare["worse_note"], r"(?i)can happen")
        self.assertRegex(compare["worse_note"], r"(?i)still missing")
        self.assertRegex(compare["worse_note"], r"(?i)rather than blaming")
        reflections = steps_data()["rescore"]["reflections"]
        self.assertEqual([r["id"] for r in reflections], ["added", "better"])
        self.assertRegex(reflections[0]["label"], r"(?i)what did your labels make you add")

    def test_the_own_step_says_what_is_private_and_starts_no_cli(self):
        own = steps_data()["own"]
        self.assertNotIn("line", own)
        self.assertNotIn("folder_label", own)
        self.assertRegex(own["ui"]["privacy_note"], r"(?i)leave out anything confidential")
        self.assertRegex(own["ui"]["privacy_note"], r"(?i)stays on this computer")
        self.assertRegex(text_of(own["instructions"]), r"(?i)leave out anything confidential")

    def test_the_rewrite_step_warns_about_a_different_model_without_blocking(self):
        gate = steps_data()["rewrite"]["gate"]
        self.assertRegex(gate["nudge_model"]["text"], r"(?i)different model")
        self.assertRegex(gate["nudge_model"]["text"], r"(?i)less fair")
        self.assertNotIn("model_same", gate)

    def test_no_step_text_mentions_a_session_a_room_or_a_person_to_contact(self):
        text = text_of(steps_data()) + text_of(lessons_data())
        self.assertNotRegex(text, r"(?i)\bsessions?\b|facilitator|presenter|\broom\b|contact |reach out")

    def test_part_one_progress_holds_only_the_participants_own_answers(self):
        record = state.new_part_1_steps()
        allowed = {"model_name", "prompt_hash", "last_check", "answers", "gap", "in_prompt", "framework", "reflections",
                   "labels"}
        for step, entry in record.items():
            self.assertTrue(set(entry) <= allowed, (step, set(entry) - allowed))
        for step in record:
            self.assertEqual(record[step].get("last_check"), None)


class SeriesRow(unittest.TestCase):
    def test_part_one_is_a_course_with_its_own_words(self):
        part = next(p for p in json.loads(resources.read_text("content/series.json"))["parts"] if p["id"] == "part-1")
        self.assertEqual(part["kind"], "course")
        ui = part["ui"]
        self.assertEqual(ui["brand_sub"], "Part 1 \u00b7 Structured prompting")
        grouped = [item for group in ui["course_groups"] for item in group["items"]]
        self.assertEqual(grouped, [item for _, item in state.PART_1.course])
        self.assertRegex(ui["finished_body"], r"Part 2")
        self.assertIn("clear pass or fail rules", ui["finished_body"])
        self.assertNotRegex(ui["finished_body"], r"(?i)session|facilitator|contact")

    def test_the_part_one_words_reach_the_page_only_for_part_one(self):
        home = Path(tempfile.mkdtemp(prefix="eval-coach-series-"))
        self.addCleanup(shutil.rmtree, home, True)
        engine = Engine(home, helpers.FakeTerminal(), lessons=ch.bundled_course())
        self.addCleanup(engine.shutdown)
        one, three = engine.get_state(part="part-1"), engine.get_state()
        self.assertEqual(one["course_text"]["brand_sub"], "Part 1 \u00b7 Structured prompting")
        self.assertEqual(three["course_text"]["brand_sub"], "Part 3 \u00b7 Running evals and baseline")
        self.assertEqual([x["id"] for x in one["course"]], [item for _, item in state.PART_1.course])


if __name__ == "__main__":
    unittest.main()
