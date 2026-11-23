"""Part 2 content: kit files, lessons, glossary, series row and the rule that the Northwind reference stays held back.

Spec part-2-course (and the lesson caps in course-structure, the Stage 3 note in learning-priority-order). Engine
behavior is in test_part_2_steps.py. Tests about the words of content/part-2-steps.json go in a class appended at the
end of this file; `steps_data()` returns None until that file exists, so no scan here depends on it.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import KIT, ROOT

from eval_coach import lessons as L
from eval_coach import parsers, resources, state
from eval_coach.engine import Engine

PART2_KIT = KIT / "part2"
KIT_FILES = {"worked-examples.md", "test-case-template.md"}
LESSON_ORDER = ["p2-mission", "p2-criteria", "p2-thresholds", "p2-testfile"]
COURSE_ORDER = [("lesson", "p2-mission"), ("lesson", "p2-criteria"), ("step", "draft"), ("lesson", "p2-thresholds"),
                ("step", "thresholds"), ("lesson", "p2-testfile"), ("step", "test-file"), ("step", "reference")]
CAPS = {"p2-mission": 450, "p2-criteria": 300, "p2-thresholds": 300, "p2-testfile": 400}
ACTIVITIES = {"p2-mission": [], "p2-criteria": ["crit-sort", "crit-trace", "crit-same"],
              "p2-thresholds": ["thr-sort", "thr-lab", "thr-pattern", "thr-explain-tech", "thr-explain-plain"],
              "p2-testfile": ["tf-sort", "tf-why", "tf-own"]}
RETRIEVAL = {"p2-mission": [], "p2-criteria": ["r-crit-1", "r-crit-2"], "p2-thresholds": ["r-thr-1", "r-thr-2", "r-thr-3"],
             "p2-testfile": ["r-tf-1", "r-tf-2"]}
STEP_CHECKS = {"draft": "sc-draft", "thresholds": "sc-thresholds", "test-file": "sc-test-file", "reference": "sc-reference"}
RETIRED_IDS = ("loop", "generate-why", "build-why", "choices", "verify", "compare", "fix-why")
PART_NAMES = ("Structured prompting", "Defining evaluation criteria", "Running evals and baseline",
              "Iterating with evaluation-driven development", "Load-bearing audit and packaging", "Your own task")
NOTE_HEADING = "**Stage 3 note (optional).**"
STAGE_THREE = re.compile(r"stage\s*3|certif", re.I)
SUBMISSION_STEPS = re.compile(r"https?://|@|\bupload\b|\bsubmission form\b|\bsend (it|them) to\b|\bhow to submit\b", re.I)
GROUP_WORK = re.compile(r"(?i)\bswap\b|\bpartner\b|\bbreakout\b|share \w+ with|discuss \w+ with|contact |reach out|"
                        r"office hours|AIR discussion|\bsessions?\b")
ABSOLUTES = ("the right way", "the only way", "the correct way", "the proper way", "the standard way",
             "this is how it is done")
REFERENCE_FILE = KIT / "northwind" / "northwind-test-cases-reference.md"
# What the reference holds beyond its length and blocker criteria (C1 and C3), which are the two worked examples.
HELD_BACK_IDS = ("C2", "C4", "C5", "C6")
HELD_BACK_NAMES = ("Grouped by client", "Teams, not email", "Factual tone", "Uses the rough notes")


def lessons_data():
    return json.loads(resources.read_text("content/part-2-lessons.json"))


def steps_data():
    """The text of content/part-2-steps.json, or None while the file does not exist."""
    try:
        return json.loads(resources.read_text("content/part-2-steps.json"))
    except resources.ResourceNotFound:
        return None


def glossary_terms():
    return json.loads(resources.read_text("content/glossary.json"))["terms"]


def part_two_glossary():
    return [t for t in glossary_terms() if t["lesson"].startswith("p2-")]


def series_part(part_id):
    return next(p for p in json.loads(resources.read_text("content/series.json"))["parts"] if p["id"] == part_id)


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


def kit_text(name):
    return (PART2_KIT / name).read_text(encoding="utf-8")


def squash(text):
    return " ".join(text.split()).casefold()


def reference_criteria():
    text = REFERENCE_FILE.read_text(encoding="utf-8")
    return {c["id"]: c for c in parsers.parse_test_cases(text)}


def reference_banned_words():
    text = REFERENCE_FILE.read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith("- Banned words:"))
    return [w.strip().strip('"') for w in line.split(":", 1)[1].split(",") if w.strip()]


def leak_findings(text, names=True):
    """What a text shows of the reference beyond the two worked examples (design D7)."""
    found = []
    for word in reference_banned_words():
        if re.search(r"\b" + re.escape(word) + r"\b", text, re.I):
            found.append(f"banned word {word!r}")
    for label, pattern in (("email marker", r"\b(Sincerely|Regards)\b|\bDear\b|\bSubject:"),
                           ("day-name rule", r"(?i)\bday names?\b"), ("exclamation rule", r"(?i)exclamation"),
                           ("required labels list", r"(?i)required labels"),
                           ("client labels", r"(?i)Northwind,\s*Contoso,?\s+and\s+Internal"),
                           ("keyword list", r"(?i)estimate\W+onboard\W+demo\W+lunch"),
                           ("every note item", r"(?i)every note item")):
        if re.search(pattern, text):
            found.append(label)
    flat = squash(text)
    for criterion_id in HELD_BACK_IDS:
        threshold = squash(reference_criteria()[criterion_id]["threshold"])
        if threshold in flat:
            found.append(f"the threshold of {criterion_id}")
    if names:
        for name in HELD_BACK_NAMES:
            if name.casefold() in flat:
                found.append(f"the criterion name {name!r}")
    return found


class KitFiles(unittest.TestCase):
    def test_the_part_two_kit_holds_exactly_these_files(self):
        self.assertEqual({p.name for p in PART2_KIT.iterdir()}, KIT_FILES)

    def test_the_worked_examples_hold_the_length_and_blocker_criteria_and_no_other(self):
        text = kit_text("worked-examples.md")
        reference = reference_criteria()
        self.assertEqual(len(re.findall(r"(?m)^- Requirement:", text)), 2)
        self.assertEqual(len(re.findall(r"(?m)^- Threshold:", text)), 2)
        for criterion_id in ("C1", "C3"):
            with self.subTest(criterion=criterion_id):
                item = reference[criterion_id]
                self.assertIn(f"- Requirement: {item['requirement']}\n", text)
                self.assertIn(f"- Threshold: {item['threshold']}\n", text)
        self.assertIn("- Type: Format\n", text)
        self.assertIn("- Type: Content\n", text)
        self.assertNotRegex(text, r"(?i)supporting lists?|banned words|required labels")

    def test_each_worked_example_has_a_passing_and_a_failing_text_that_really_pass_and_fail(self):
        text = kit_text("worked-examples.md")
        passing = text.split("## A passing update", 1)[1].split("## Example 1", 1)[0].strip()
        longer = re.search(r"(?m)^> (Monday:.*)$", text).group(1)
        blockers = re.findall(r"(?m)^> (Northwind: .*)$", text)
        length = {"kind": "word_count_under", "params": {"limit": 150}}
        labels = {"kind": "all_labels", "params": {"labels": ["Blocker:", "Need:"]}}
        self.assertTrue(L.evaluate_rule(length, passing)[0])
        self.assertFalse(L.evaluate_rule(length, longer)[0])
        self.assertTrue(L.evaluate_rule(labels, passing)[0])
        self.assertEqual(len(blockers), 2)
        for failing in blockers:
            self.assertTrue(L.evaluate_rule(length, failing)[0])
            self.assertFalse(L.evaluate_rule(labels, failing)[0])

    def test_the_template_has_the_layout_part_three_reads_and_nothing_filled_in(self):
        text = kit_text("test-case-template.md")
        self.assertTrue(text.startswith("# Test cases: "))
        order = [text.index(h) for h in ("## Test input", "## Criteria", "## Supporting lists")]
        self.assertEqual(order, sorted(order))
        parsed = parsers.parse_test_cases(text)
        self.assertEqual([c["id"] for c in parsed], ["C1", "C2", "C3"])
        for field in ("requirement", "threshold"):
            for item in parsed:
                self.assertRegex(item[field], r"^<.+>$")
        self.assertEqual(len(re.findall(r"(?m)^- Requirement: ", text)), 3)
        self.assertEqual(len(re.findall(r"(?m)^- Type: <Format or Content>$", text)), 3)
        self.assertEqual(len(re.findall(r"(?m)^- Threshold: ", text)), 3)
        self.assertNotIn("Northwind", text)

    def test_the_template_holds_one_placeholder_list_line_and_no_northwind_list_word(self):
        lists = kit_text("test-case-template.md").split("## Supporting lists", 1)[1]
        lines = [x for x in lists.splitlines() if x.strip()]
        self.assertEqual(lines, ["- Example: Terms to avoid: word one, word two"])
        built = steps_data()
        if built is not None:
            self.assertEqual(lines[0], built["steps"]["test-file"]["build"]["supporting_placeholder"])
        self.assertEqual(leak_findings(kit_text("test-case-template.md")), [])

    def test_no_kit_file_uses_meeting_tool_room_or_facilitator_wording(self):
        for path in PART2_KIT.iterdir():
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotRegex(text, r"(?i)copilot|breakout|facilitator|presenter|\broom\b|handout|session|"
                                          r"\bslides?\b|zoom|teams meeting")

    def test_the_kit_viewer_reads_both_files(self):
        home = Path(tempfile.mkdtemp(prefix="eval-coach-kit-"))
        self.addCleanup(shutil.rmtree, home, True)
        engine = Engine(home, helpers.FakeTerminal())
        self.addCleanup(engine.shutdown)
        for name in KIT_FILES:
            shown = engine.kit_file(f"kit:part2/{name}")["kit"]
            self.assertEqual(shown["name"], name)
            self.assertEqual(shown["text"].replace("\r\n", "\n"), kit_text(name))

    def test_every_kit_file_is_cited_by_a_lesson_and_lessons_cite_only_readable_kit_files(self):
        cited = set()
        for lesson_id in LESSON_ORDER:
            for ref in refs_of(lesson(lesson_id)):
                self.assertTrue(ref.startswith("kit:"), ref)
                self.assertTrue(L.kit_ref_allowed(ref), ref)
                if ref.startswith("kit:part2/"):
                    cited.add(ref.split("/", 1)[1])
        self.assertEqual(cited, KIT_FILES)


class Lessons(unittest.TestCase):
    def test_the_course_has_four_lessons_and_four_steps_in_the_fixed_order(self):
        part = state.PART_2
        self.assertEqual(list(part.course), COURSE_ORDER)
        self.assertEqual(part.mission, "p2-mission")
        self.assertEqual([x["id"] for x in lessons_data()["lessons"]], LESSON_ORDER)
        self.assertEqual(state.duplicate_ids(), [])

    def test_the_file_passes_the_course_schema_and_loads_with_the_other_parts(self):
        L.validate_course(lessons_data(), L.validate_glossary({"terms": glossary_terms()}), state.PART_2)
        self.assertTrue(set(LESSON_ORDER) <= set(L.load_bundled().by_id))

    def test_titles_say_what_the_learner_gets(self):
        self.assertEqual([x["title"] for x in lessons_data()["lessons"]],
                         ["Your mission", "From requirements to criteria", "Rules a script could check",
                          "Writing your rules down"])

    def test_bodies_stay_within_their_caps(self):
        for lesson_id, cap in CAPS.items():
            with self.subTest(lesson=lesson_id):
                self.assertLessEqual(len(lesson(lesson_id)["body"].split()), cap)

    def test_no_id_in_part_two_is_a_retired_id(self):
        data = lessons_data()
        ids = [x["id"] for x in data["lessons"]] + [c["id"] for c in data["step_checks"]] + list(state.PART_2.step_ids)
        for item in data["lessons"]:
            ids += [a["id"] for a in item["activities"]] + [r["id"] for r in item["retrieval"]]
        for retired in RETIRED_IDS:
            self.assertNotIn(retired, ids)

    def test_activities_and_review_items_follow_the_outline(self):
        for lesson_id in LESSON_ORDER:
            with self.subTest(lesson=lesson_id):
                self.assertEqual([a["id"] for a in lesson(lesson_id)["activities"]], ACTIVITIES[lesson_id])
                self.assertEqual([r["id"] for r in lesson(lesson_id)["retrieval"]], RETRIEVAL[lesson_id])
        types = {a["id"]: a["type"] for x in lessons_data()["lessons"] for a in x["activities"]}
        self.assertEqual(types, {"crit-sort": "sort", "crit-trace": "choice", "crit-same": "choice", "thr-sort": "sort",
                                 "thr-lab": "rule_lab", "thr-pattern": "choice", "thr-explain-tech": "choice",
                                 "thr-explain-plain": "reflection", "tf-sort": "sort", "tf-why": "choice",
                                 "tf-own": "reflection"})

    def test_no_lesson_is_skippable_and_the_placement_is_empty(self):
        self.assertEqual(lessons_data()["placement"], [])
        for item in lessons_data()["lessons"]:
            self.assertIs(item["skippable"], False, item["id"])

    def test_the_mission_follows_the_shape_and_opens_on_the_question_from_part_one(self):
        mission = lesson("p2-mission")
        self.assertEqual((mission["activities"], mission["retrieval"]), ([], []))
        body = mission["body"]
        self.assertTrue(body.startswith("**The goal.**"))
        for label in ("**The goal.**", "**Why it matters to you.**", "**What you will do.**", "**What you leave with.**"):
            self.assertEqual(body.count(label), 1, label)
        self.assertIn("how do you know the second answer is better?", body)
        self.assertIn("You write down what good means, before you look at any answer.", body)
        self.assertRegex(body, r"(?i)nothing is run in this part")
        self.assertIn("Running the rules on real answers starts in Part 3", body)
        self.assertIn("The Practice task is a ready-made example, for practice only and never something to submit", body)
        self.assertNotIn("Northwind", body)
        self.assertNotIn("you-are-here", body)
        self.assertNotIn("blind trust", body)
        self.assertNotIn("sounds sure of itself", body)
        self.assertIn("A rule written down before you see an answer cannot bend", body)

    def test_each_lesson_after_the_mission_has_the_shape_of_the_other_parts(self):
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
                self.assertIn(data["primary_source"]["ref"], [s["ref"] for s in data["sources"]])
                self.assertIn("answer them or move on", body)

    def test_options_have_equal_word_counts_everywhere(self):
        data = lessons_data()
        groups = [a for x in data["lessons"] for a in x["activities"] + x["retrieval"] if "options" in a]
        groups += data["step_checks"]
        self.assertGreaterEqual(len(groups), 15)
        for group in groups:
            with self.subTest(item=group["id"]):
                self.assertEqual(len({L.word_count(o["text"]) for o in group["options"]}), 1)
                self.assertEqual(sum(1 for o in group["options"] if o["correct"]), 1)

    def test_sort_buckets_cover_what_each_activity_teaches(self):
        crit = next(a for a in lesson("p2-criteria")["activities"] if a["id"] == "crit-sort")
        self.assertEqual([b["id"] for b in crit["buckets"]], ["format", "content"])
        self.assertEqual({i["bucket"] for i in crit["items"]}, {"format", "content"})
        self.assertEqual(len(crit["items"]), 8)
        thr = next(a for a in lesson("p2-thresholds")["activities"] if a["id"] == "thr-sort")
        self.assertEqual([b["id"] for b in thr["buckets"]], ["decide", "tighten"])
        self.assertEqual(len(thr["items"]), 8)
        tf = next(a for a in lesson("p2-testfile")["activities"] if a["id"] == "tf-sort")
        self.assertEqual([b["id"] for b in tf["buckets"]], ["input", "criteria", "lists"])
        for activity in (crit, thr, tf):
            for item in activity["items"]:
                self.assertTrue(item["feedback"].strip())

    def test_the_criteria_lesson_defines_the_rules_and_models_only_the_two_worked_examples(self):
        body = lesson("p2-criteria")["body"]
        for needle in ("A criterion is one thing a good answer must do", "traces to a requirement", "at least three",
                       "**Format** is how an answer looks", "**Content** is what an answer says",
                       "No two criteria should check the same thing", "polished but wrong test", "return",
                       "under 150 words", "names the blocker and says what you need"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        self.assertEqual(leak_findings(body), [])

    def test_the_thresholds_lesson_teaches_the_script_test_two_patterns_and_the_limits_of_rules(self):
        body = lesson("p2-thresholds")["body"]
        for needle in ("script test: could a script decide this with no human judgment? If not, tighten it",
                       "becomes a number", "becomes terms", "becomes a label", "ties an instruction in the prompt",
                       "**Required term**", "A list of words to avoid is a proxy", "still miss the point",
                       "do not pretend", "Not checked", "for your own task"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        self.assertLess(body.index("**Structure**"), body.index("**Required term**"))
        self.assertEqual(leak_findings(body), [])

    def test_the_lab_cases_cover_every_pair_and_include_a_polished_text_that_passes_format_and_fails_content(self):
        lab = next(a for a in lesson("p2-thresholds")["activities"] if a["id"] == "thr-lab")
        self.assertEqual(len(lab["samples"]), 3)
        self.assertEqual(len(lab["cases"]), 6)
        rules = {r["id"]: r for r in lab["rules"]}
        samples = {s["id"]: s["text"] for s in lab["samples"]}
        for rule in rules.values():
            self.assertTrue(rule["explain"].strip())
        for case in lab["cases"]:
            passed, _ = L.evaluate_rule(rules[case["rule"]], samples[case["sample"]])
            self.assertEqual("pass" if passed else "fail", case["expected"], case)
        verdicts = {(c["sample"], c["rule"]): c["expected"] for c in lab["cases"]}
        self.assertEqual(verdicts[("s-polished", "r-length")], "pass")
        self.assertEqual(verdicts[("s-polished", "r-labels")], "fail")
        self.assertEqual(verdicts[("s-long", "r-length")], "fail")
        self.assertEqual(leak_findings(text_of(lab), names=False), [])

    def test_the_two_explain_it_activities_are_for_different_audiences_and_block_nothing(self):
        activities = {a["id"]: a for a in lesson("p2-thresholds")["activities"]}
        plain = activities["thr-explain-plain"]
        self.assertEqual(plain["type"], "reflection")
        self.assertGreaterEqual(plain["min_words"], 20)
        self.assertRegex(plain["prompt"], r"(?i)not technical")
        self.assertRegex(activities["thr-explain-tech"]["prompt"], r"(?i)technical colleague")
        for item in lessons_data()["lessons"]:
            for activity in item["activities"]:
                self.assertIn(activity["type"], ("choice", "sort", "reflection", "rule_lab"), item["id"])

    def test_the_test_file_lesson_shows_the_parts_the_hand_off_and_the_honest_score(self):
        body = lesson("p2-testfile")["body"]
        for needle in ("**Test input.**", "**Criteria.**", "**Supporting lists.**", "The list lives in the same file",
                       "You write the list for your own task", "Writing the rules first keeps the score honest",
                       "In Part 3, an AI agent turns a file like this into a checker and runs it on real answers",
                       "saved in your project folder", "A script or a promptfoo file can hold the same rules",
                       "The Practice task is a ready-made example for practice only, and it cannot be submitted",
                       "repeats, has clear requirements and could be checked by rules"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        self.assertEqual(body.count("```"), 2)
        own = next(a for a in lesson("p2-testfile")["activities"] if a["id"] == "tf-own")
        self.assertTrue(own["prompt"].startswith("Optional."))
        self.assertEqual(own["min_words"], 8)
        self.assertNotRegex(own["prompt"], r"(?i)office hours|discussion|people|place")

    def test_step_checks_cover_the_four_steps_once_each(self):
        checks = lessons_data()["step_checks"]
        self.assertEqual({c["step"]: c["id"] for c in checks}, STEP_CHECKS)
        self.assertEqual(sorted(c["step"] for c in checks), sorted(state.PART_2.step_ids))

    def test_the_step_check_for_the_reference_step_gives_nothing_away(self):
        check = next(c for c in lessons_data()["step_checks"] if c["step"] == "reference")
        self.assertEqual(leak_findings(text_of(check)), [])

    def test_no_course_practice_reads_as_the_only_way_and_nothing_asks_for_another_person(self):
        pieces = [text_of(lessons_data()), text_of(part_two_glossary()), text_of(series_part("part-2"))]
        pieces += [kit_text(name) for name in KIT_FILES]
        for text in pieces:
            self.assertIsNone(GROUP_WORK.search(text), GROUP_WORK.search(text))
            for phrase in ABSOLUTES:
                self.assertNotIn(phrase, text.lower())
            self.assertIsNone(re.search(r"(?i)\bbuckets?\b", text))

    def test_the_sources_are_the_part_two_kit_and_the_notes_from_part_one(self):
        for lesson_id in LESSON_ORDER:
            for ref in refs_of(lesson(lesson_id)):
                self.assertRegex(ref, r"^kit:(part2/[\w.-]+|part1/rough-notes\.txt)$")
        self.assertEqual(lesson("p2-mission")["primary_source"]["ref"], "kit:part1/rough-notes.txt")
        self.assertEqual(lesson("p2-criteria")["primary_source"]["ref"], "kit:part2/worked-examples.md")
        self.assertEqual(lesson("p2-testfile")["primary_source"]["ref"], "kit:part2/test-case-template.md")


class NoReferenceLeak(unittest.TestCase):
    """The Northwind reference criteria beyond length and blocker stay held back (spec part-2-course)."""

    def sources(self):
        found = {"lessons": text_of(lessons_data()), "glossary": text_of(part_two_glossary()),
                 "series": text_of(series_part("part-2"))}
        for name in KIT_FILES:
            found[f"kit/part2/{name}"] = kit_text(name)
        return found

    def test_the_scan_has_something_to_find(self):
        self.assertEqual(reference_banned_words()[:2], ["excited", "thrilled"])
        self.assertEqual(len(reference_banned_words()), 10)
        self.assertEqual(sorted(reference_criteria()), ["C1", "C2", "C3", "C4", "C5", "C6"])
        planted = "Passes only if " + reference_criteria()["C2"]["threshold"].split("Passes only if ")[-1]
        self.assertTrue(leak_findings(planted))
        self.assertTrue(leak_findings("The update sounds thrilled."))
        self.assertTrue(leak_findings("Factual tone is a proxy."))
        self.assertEqual(leak_findings("Word count under 150 passes"), [])

    def test_no_lesson_glossary_entry_series_text_or_kit_file_leaks_the_reference(self):
        for name, text in self.sources().items():
            with self.subTest(source=name):
                self.assertEqual(leak_findings(text), [])

    def test_every_string_in_the_part_two_text_is_clean_one_by_one(self):
        pieces = list(strings(lessons_data())) + list(strings(part_two_glossary())) + list(strings(series_part("part-2")))
        for text in pieces:
            with self.subTest(text=text[:50]):
                self.assertEqual(leak_findings(text), [])

    def test_the_part_two_steps_words_leak_nothing_when_the_file_exists(self):
        data = steps_data()
        if data is None:
            self.skipTest("content/part-2-steps.json does not exist yet")
        for step, item in data["steps"].items():
            with self.subTest(step=step):
                self.assertEqual(leak_findings(text_of(item), names=False), [])

    def test_the_two_worked_criteria_are_the_only_reference_thresholds_in_the_kit_files(self):
        text = kit_text("worked-examples.md")
        reference = reference_criteria()
        self.assertIn(reference["C1"]["threshold"], text)
        self.assertIn(reference["C3"]["threshold"], text)
        for criterion_id in HELD_BACK_IDS:
            self.assertNotIn(squash(reference[criterion_id]["threshold"]), squash(text))


class StageThreeNote(unittest.TestCase):
    def test_the_note_ends_the_last_lesson_is_short_optional_and_names_the_evaluations(self):
        body = lesson("p2-testfile")["body"]
        self.assertEqual(body.count(NOTE_HEADING), 1)
        self.assertTrue(body.rstrip().endswith("finish this Part."))
        note = body.split(NOTE_HEADING, 1)[1]
        self.assertLessEqual(len(note.split()), 60)
        self.assertRegex(note, r"\bEvaluations\b")
        self.assertNotRegex(note, r"\b(Prompt|Log)\b")
        self.assertIn("at least three different rules with clear pass or fail limits", note)
        for form in ("Scripts", "promptfoo files", "written test cases", "all accepted"):
            self.assertIn(form, note)
        self.assertIn("The program's own instructions decide what to submit", note)
        self.assertIn("nothing in this note is needed to finish this Part", note)
        self.assertIsNone(SUBMISSION_STEPS.search(note))
        self.assertIsNone(re.search(r"\b20\d\d\b", note))

    def test_stage_three_is_named_nowhere_else_in_part_two(self):
        data = lessons_data()
        for item in data["lessons"]:
            text = text_of(item)
            if item["id"] == "p2-testfile":
                text = text.replace(lesson("p2-testfile")["body"].split(NOTE_HEADING, 1)[1], "")
                text = text.replace(NOTE_HEADING, "")
            with self.subTest(lesson=item["id"]):
                self.assertIsNone(STAGE_THREE.search(text))
        self.assertIsNone(STAGE_THREE.search(text_of(data["step_checks"])))
        self.assertIsNone(STAGE_THREE.search(text_of(part_two_glossary())))
        self.assertIsNone(STAGE_THREE.search(text_of(series_part("part-2"))))
        for name in KIT_FILES:
            self.assertIsNone(STAGE_THREE.search(kit_text(name)), name)
        if steps_data() is not None:
            self.assertIsNone(STAGE_THREE.search(text_of(steps_data())))


class Glossary(unittest.TestCase):
    TERMS = {"Test case": ("idea", "p2-testfile"), "Format check": ("idea", "p2-criteria"),
             "Content check": ("idea", "p2-criteria"), "Supporting list": ("idea", "p2-testfile"),
             "Script test": ("idea", "p2-thresholds"), "Worksheet": ("course", "p2-criteria")}

    def test_the_part_two_terms_are_there_with_the_right_kinds_and_lessons(self):
        terms = {t["term"]: t for t in glossary_terms()}
        for term, (kind, lesson_id) in self.TERMS.items():
            with self.subTest(term=term):
                self.assertEqual(terms[term]["kind"], kind)
                self.assertEqual(terms[term]["lesson"], lesson_id)
                if kind == "course":
                    self.assertTrue(terms[term]["meaning"].startswith("In this course,"))
                else:
                    self.assertFalse(terms[term]["meaning"].startswith("In this course"))
        self.assertEqual({t["term"] for t in part_two_glossary()}, set(self.TERMS))

    def test_part_two_terms_stay_off_the_one_page_card(self):
        for term in part_two_glossary():
            self.assertIs(term.get("card"), False, term["term"])

    def test_the_criterion_and_threshold_entries_still_point_to_part_threes_lesson(self):
        terms = {t["term"]: t for t in glossary_terms()}
        for term in ("Criterion", "Threshold"):
            self.assertEqual(terms[term]["lesson"], "rules")

    def test_related_glossary_references_and_lessons_resolve(self):
        known = {t["term"].casefold() for t in glossary_terms()}
        for item in lessons_data()["lessons"]:
            for term in item["related"]["glossary"]:
                self.assertIn(term.casefold(), known, term)
            for other in item["related"]["lessons"]:
                self.assertIn(other, LESSON_ORDER)
        used = {t.casefold() for x in lessons_data()["lessons"] for t in x["related"]["glossary"]}
        for term in self.TERMS:
            self.assertIn(term.casefold(), used, term)


class SeriesRow(unittest.TestCase):
    def test_part_two_is_a_course_with_its_own_words(self):
        part = series_part("part-2")
        self.assertEqual((part["kind"], part["title"]), ("course", "Defining evaluation criteria"))
        ui = part["ui"]
        self.assertEqual(ui["brand_sub"], "Part 2 \u00b7 Defining evaluation criteria")
        self.assertEqual(ui["map_title"], "Part {n}: ")
        self.assertEqual(ui["map_aria"], "Course map. You are at Part {n} of {total}.")
        self.assertEqual(ui["finished_title"], "You have finished Part 2")

    def test_the_course_groups_follow_design_d1_and_cover_every_item_once(self):
        groups = series_part("part-2")["ui"]["course_groups"]
        self.assertEqual([(g["label"], g["items"]) for g in groups], [
            ("Know what you need", ["p2-mission", "p2-criteria", "draft"]),
            ("Turn it into rules", ["p2-thresholds", "thresholds"]),
            ("Write it down", ["p2-testfile", "test-file"]),
            ("Compare with an example", ["reference"])])
        self.assertEqual([item for g in groups for item in g["items"]], [item for _, item in state.PART_2.course])
        self.assertEqual(len({g["id"] for g in groups}), 4)

    def test_the_finished_screen_names_the_file_says_what_part_three_does_and_that_the_practice_task_is_practice(self):
        with resources.platform_words("windows"):
            body = series_part("part-2")["ui"]["finished_body"]
        self.assertIn("part-2\\test-cases.md", body)
        self.assertRegex(body, r"In Part 3 an AI agent turns a file like this into a checker")
        self.assertIn("distinct criteria", body)
        self.assertIn("threshold a script could decide", body)
        self.assertIn("test cases", body)
        self.assertRegex(body, r"The Practice task is for practice only and is not something to submit")
        self.assertIsNone(GROUP_WORK.search(body))

    def test_part_two_is_a_course_and_parts_four_and_five_are_still_coming_soon(self):
        kinds = {p["n"]: p["kind"] for p in json.loads(resources.read_text("content/series.json"))["parts"]}
        self.assertEqual(kinds, {1: "course", 2: "course", 3: "course", 4: "soon", 5: "soon", 6: "live"})

    def test_the_part_two_words_reach_the_page_only_for_part_two(self):
        home = Path(tempfile.mkdtemp(prefix="eval-coach-series-"))
        self.addCleanup(shutil.rmtree, home, True)
        import course_helpers as ch
        engine = helpers.make_engine(home, helpers.FakeTerminal(), lessons=ch.bundled_course())
        self.addCleanup(engine.shutdown)
        two, three = engine.get_state(part="part-2"), engine.get_state()
        self.assertEqual(two["course_text"]["brand_sub"], "Part 2 \u00b7 Defining evaluation criteria")
        self.assertEqual(three["course_text"]["brand_sub"], "Part 3 \u00b7 Running evals and baseline")
        self.assertEqual([x["id"] for x in two["course"]], [item for _, item in state.PART_2.course])


# Tests about the words of content/part-2-steps.json.


class StepText(unittest.TestCase):
    # The fields criteria_steps.py supplies to each kind of message.
    SUPPLIED = {"gate": {"rows", "count", "missing", "min", "message"},
                "findings": {"id", "name", "words", "count", "min", "missing"},
                "notes": {"n", "words"}, "messages": {"error"}, "words": {"n", "list"}}
    PLACEHOLDER = re.compile(r"\{(\w+)\}")

    def setUp(self):
        data = steps_data()
        if data is None:
            self.skipTest("content/part-2-steps.json does not exist yet")
        self.steps = data["steps"]

    def test_the_file_holds_the_four_steps_and_each_names_a_registered_kind(self):
        self.assertEqual(list(self.steps), list(state.PART_2.step_ids))
        self.assertEqual({s: d["kind"] for s, d in self.steps.items()},
                         {"draft": "criteria_table", "thresholds": "criteria_table", "test-file": "test_file",
                          "reference": "reveal_compare"})
        for data in self.steps.values():
            self.assertIn(data["kind"], state.STEP_KINDS)

    def test_every_step_has_the_words_the_page_reads_and_a_question_after_it(self):
        checks = {c["step"] for c in lessons_data()["step_checks"]}
        for step, data in self.steps.items():
            with self.subTest(step=step):
                for key in ("title", "goal", "why", "instructions", "troubleshooting", "gate", "ui"):
                    self.assertTrue(data[key], key)
                for problem in data["troubleshooting"]:
                    self.assertEqual(set(problem), {"problem", "fix"})
                    self.assertTrue(problem["problem"].strip() and problem["fix"].strip())
                self.assertIn(step, checks)

    def test_the_five_requirements_equal_part_ones_cold_scenario(self):
        part_one = json.loads(resources.read_text("content/part-1-steps.json"))["steps"]["cold"]["scenario"]
        card = self.steps["draft"]["scenario"]
        self.assertEqual([r["id"] for r in card["requirements"]], ["r1", "r2", "r3", "r4", "r5"])
        self.assertEqual(card["requirements"], part_one["requirements"])

    def test_no_step_text_carries_a_reference_criterion_threshold_or_northwind_list_word(self):
        for step, data in self.steps.items():
            with self.subTest(step=step):
                # The five requirements on the card are the scenario, not reference criteria.
                text = text_of({k: v for k, v in data.items() if k != "scenario"})
                self.assertEqual(leak_findings(text), [])
                if "scenario" in data:
                    card = {k: v for k, v in data["scenario"].items() if k != "requirements"}
                    self.assertEqual(leak_findings(text_of(card)), [])
                    self.assertEqual(leak_findings(text_of(data["scenario"]["requirements"]), names=False), [])

    def test_the_reference_step_shows_no_reference_before_the_gate(self):
        text = text_of(self.steps["reference"])
        for criterion in reference_criteria().values():
            self.assertNotIn(squash(criterion["threshold"]), squash(text))

    def test_the_reference_options_have_equal_word_counts_and_the_four_ids(self):
        options = self.steps["reference"]["options"]
        self.assertEqual([o["id"] for o in options], ["had", "missed", "different", "vague"])
        self.assertEqual(len({L.word_count(o["label"]) for o in options}), 1)
        for step in ("draft", "thresholds"):
            self.assertEqual(len({L.word_count(t["label"]) for t in self.steps[step]["types"]}), 1)

    def test_no_step_names_stage_three_and_none_asks_for_another_person(self):
        text = text_of(self.steps)
        self.assertIsNone(STAGE_THREE.search(text))
        self.assertIsNone(GROUP_WORK.search(text), GROUP_WORK.search(text))
        for phrase in ABSOLUTES:
            self.assertNotIn(phrase, text.lower())

    def test_no_step_text_uses_a_banned_word(self):
        from test_content_banned_words import banned_in
        for text in strings(self.steps):
            with self.subTest(text=text[:50]):
                self.assertEqual(banned_in(text), [])

    def test_messages_never_tell_the_participant_to_press_check_my_files(self):
        for text in strings(self.steps):
            with self.subTest(text=text[:50]):
                self.assertNotRegex(text, r"(?i)check my files")
        for step, data in self.steps.items():
            for section in ("gate", "findings", "notes", "messages"):
                for text in strings(data.get(section, {})):
                    self.assertNotRegex(text, r"(?i)press check my")  # the step's own button is Check my work

    def test_every_placeholder_in_a_message_is_one_the_code_supplies(self):
        for step, data in self.steps.items():
            for section, allowed in self.SUPPLIED.items():
                for text in strings(data.get(section, {})):
                    with self.subTest(step=step, section=section, text=text[:50]):
                        self.assertLessEqual(set(self.PLACEHOLDER.findall(text)), allowed)

    def test_the_file_findings_exist_for_every_code_the_checks_can_raise(self):
        codes = {"no_input", "no_criteria", "few_criteria", "no_content_criterion", "missing_threshold", "vague",
                 "no_requirement", "list_missing"}
        for step in ("test-file", "reference"):
            self.assertEqual(set(self.steps[step]["findings"]), codes)
        self.assertEqual(self.steps["test-file"]["findings"], self.steps["reference"]["findings"])

    def test_the_build_words_use_part_threes_headings_and_the_placeholder_names_no_northwind_list_word(self):
        build = self.steps["test-file"]["build"]
        self.assertEqual(build["title"], "Test cases: Northwind end-of-week update")
        self.assertTrue(build["supporting_placeholder"].startswith("- Example"))
        self.assertEqual(leak_findings(build["supporting_placeholder"]), [])

    def test_the_two_worksheet_steps_have_the_ticks_the_lessons_name(self):
        self.assertEqual([t["id"] for t in self.steps["draft"]["ticks"]], ["traces", "distinct"])
        self.assertEqual([t["id"] for t in self.steps["thresholds"]["ticks"]], ["script_test"])


if __name__ == "__main__":
    unittest.main()
