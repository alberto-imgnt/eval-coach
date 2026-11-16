"""Phase 4C: the import checks (4.21 to 4.24), the import route (4.19), copies and names (4.20), Northwind (4.25)."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import FakeTerminal, GOLDEN, NORTHWIND
from test_http import ServerCase

from eval_coach import import_checks as ic
from eval_coach import resources
from eval_coach.engine import Engine, EngineError
from eval_coach.project import Paths

IMPORT = GOLDEN / "import"
NORTHWIND_PROMPT = NORTHWIND / "northwind-prompt-v0.md"
NORTHWIND_CASES = NORTHWIND / "northwind-test-cases-reference.md"
NEXT_ACTION = re.compile(r"(press Check my files|choose it again|choose a new project folder|Check my files again|"
                         r"Check my files\.|rewrite|Add |add |re-save)", re.I)


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def review(prompt_text, cases_text):
    """Run the text checks on strings, through the same code path as files."""
    return ic.analyze(prompt_text, cases_text)


def codes(items):
    return [item["code"] for item in items]


class ContentRule(unittest.TestCase):
    """4.22: which thresholds are about what the answer says."""

    CONTENT = [
        'Passes only if Northwind, Contoso and Internal all appear as labels and no day name is used as a label',
        'Passes if a "Blocker:" label and a "Need:" label both appear',
        'Passes only if every note item is found by keyword (estimate, onboard, demo)',
        'Every number in the output also appears in the test input',
        'Includes at least 2 of: refund, replacement, exchange',
        'Mentions the order number',
        'The reply states a refund policy',
        'Passes if "refund" appears',
        'Passes if at least 1 of refund, replacement appears',
        'Contains all of the three terms',
    ]
    NOT_CONTENT = [
        'Word count under 150 passes',
        'Passes if none of "Subject:", "Dear", "Regards", "Sincerely" appear',
        'Passes if zero words from the banned list appear and there are no exclamation marks',
        'Contains at least 3 sentences',
        'Has between 3 and 5 bullets',
        'Starts with "Hello"',
        'Ends with a question mark',
        'The answer is clear and professional',
        'Fewer than 800 characters',
        '',
    ]

    def test_thresholds_that_require_information(self):
        for text in self.CONTENT:
            with self.subTest(text=text):
                self.assertTrue(ic.is_content_threshold(text))

    def test_thresholds_about_size_shape_bans_or_judgment(self):
        for text in self.NOT_CONTENT:
            with self.subTest(text=text):
                self.assertFalse(ic.is_content_threshold(text))

    def test_the_type_label_is_trusted_for_unusual_wording(self):
        odd = {"id": "C1", "name": "Topics", "requirement": "", "threshold": "Passes when the three topics are covered"}
        self.assertFalse(ic.is_content_threshold(odd["threshold"]))
        self.assertTrue(ic.is_content_criterion(odd, "Content"))

    def test_the_type_label_alone_never_rescues_a_count_or_a_vague_word(self):
        count = {"id": "C1", "name": "Length", "requirement": "", "threshold": "Word count under 150 passes"}
        vague = {"id": "C2", "name": "Tone", "requirement": "", "threshold": "The tone is friendly"}
        self.assertFalse(ic.is_content_criterion(count, "Content"))
        self.assertFalse(ic.is_content_criterion(vague, "Content"))

    def test_a_format_label_does_not_hide_a_content_threshold(self):
        crit = {"id": "C2", "name": "Grouped", "requirement": "",
                "threshold": "Passes only if Northwind and Contoso both appear as labels"}
        self.assertTrue(ic.is_content_criterion(crit, "Format"))

    def test_type_labels_are_read_from_headings_and_tables(self):
        types = ic.criterion_types(read_text(NORTHWIND_CASES))
        self.assertEqual(types["C1"], "Format")
        self.assertEqual(types["C3"], "Content")
        self.assertEqual(types["C5"], "Format (proxy)")
        table = ic.criterion_types(read_text(IMPORT / "good-cases-table.md"))
        self.assertEqual(table, {"C1": "Format", "C2": "Content", "C3": "Content"})

    def test_good_and_bad_files(self):
        prompt = read_text(IMPORT / "good-prompt-support.md")
        good = review(prompt, read_text(IMPORT / "good-cases-support.md"))
        self.assertEqual(codes(good["blocking"]), [])
        bad = review(prompt, read_text(IMPORT / "bad-format-only.md"))
        self.assertEqual(codes(bad["blocking"]), ["no_content_criterion"])
        vague = review(prompt, read_text(IMPORT / "bad-all-vague.md"))
        self.assertEqual(codes(vague["blocking"]), ["no_content_criterion"])

    def test_the_message_says_what_to_add(self):
        bad = review("x", read_text(IMPORT / "bad-format-only.md"))
        message = bad["blocking"][0]["message"]
        self.assertIn("names the terms, labels or facts the answer must include", message)
        self.assertIn("Check my files again", message)


class CriteriaCount(unittest.TestCase):
    """4.21"""

    def test_two_criteria_block_and_say_how_many_to_add(self):
        result = review("x", read_text(IMPORT / "bad-two-criteria.md"))
        self.assertIn("few_criteria", codes(result["blocking"]))
        message = next(i["message"] for i in result["blocking"] if i["code"] == "few_criteria")
        self.assertIn("2 of the 3 criteria", message)
        self.assertIn("Add 1 more", message)
        self.assertFalse(result["ready"])
        self.assertEqual([c["id"] for c in result["criteria"]], ["C1", "C2"])

    def test_one_criterion_asks_for_two_more(self):
        result = review("x", "### C1: Only\n- Requirement: r\n- Threshold: Passes if \"a\" appears\n")
        message = next(i["message"] for i in result["blocking"] if i["code"] == "few_criteria")
        self.assertIn("1 of the 3", message)
        self.assertIn("Add 2 more", message)

    def test_no_criteria_explains_the_layout(self):
        result = review("x", read_text(IMPORT / "bad-no-criteria.md"))
        self.assertEqual(codes(result["blocking"]), ["no_criteria"])
        self.assertIn("### C1: Length", result["blocking"][0]["message"])
        self.assertEqual(result["criteria"], [])
        self.assertEqual(result["warnings"], [])

    def test_three_is_enough_in_every_layout(self):
        prompt = read_text(IMPORT / "good-prompt-support.md")
        for name in ("good-cases-support.md", "good-cases-table.md", "good-cases-list.md"):
            with self.subTest(name=name):
                result = review(prompt, read_text(IMPORT / name))
                self.assertEqual(codes(result["blocking"]), [])
                self.assertTrue(result["ready"])
                self.assertGreaterEqual(len(result["criteria"]), 3)


class NorthwindIsGood(unittest.TestCase):
    """The Northwind reference file must pass every check cleanly, whatever its line endings or BOM."""

    def variants(self):
        raw = NORTHWIND_CASES.read_bytes()
        crlf = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        bom = b"\xef\xbb\xbf"
        return {"lf": raw.replace(b"\r\n", b"\n"), "crlf": crlf, "bom": bom + raw, "bom+crlf": bom + crlf}

    def test_passes_with_nothing_to_report(self):
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-import-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        for label, data in self.variants().items():
            with self.subTest(variant=label):
                cases = tmp / f"cases-{label}.md"
                cases.write_bytes(data)
                result, got = ic.review_files(str(NORTHWIND_PROMPT), str(cases))
                self.assertEqual(result["blocking"], [])
                self.assertEqual(result["warnings"], [])
                self.assertTrue(result["ready"])
                self.assertEqual([c["id"] for c in result["criteria"]], ["C1", "C2", "C3", "C4", "C5", "C6"])
                self.assertEqual(got["test_cases"], data)

    def test_prompt_with_crlf_and_bom_is_fine(self):
        raw = NORTHWIND_PROMPT.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-import-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        prompt = tmp / "p.md"
        prompt.write_bytes(b"\xef\xbb\xbf" + raw)
        result, _ = ic.review_files(str(prompt), str(NORTHWIND_CASES))
        self.assertEqual((result["blocking"], result["warnings"]), ([], []))

    def test_the_demo_file_has_two_criteria_and_is_refused_for_that_reason_only(self):
        demo = helpers.KIT / "lessons" / "demo" / "test-cases.md"
        result, _ = ic.review_files(str(NORTHWIND_PROMPT), str(demo))
        self.assertEqual(codes(result["blocking"]), ["few_criteria"])

    def test_the_golden_support_files_are_clean_too(self):
        result, _ = ic.review_files(str(IMPORT / "good-prompt-support.md"), str(IMPORT / "good-cases-support.md"))
        self.assertEqual((result["blocking"], result["warnings"]), ([], []))


class Traceability(unittest.TestCase):
    """4.23: a warning, never a block."""

    def test_a_criterion_with_a_requirement_line_is_traced(self):
        text = "### C1: Mystery\n- Requirement: Something from my brief\n- Threshold: Passes if \"zzz\" appears\n"
        self.assertEqual(codes(review("unrelated prompt", text + text.replace("C1", "C2") + text.replace("C1", "C3"))["warnings"]), [])

    def test_a_criterion_with_no_requirement_needs_the_prompt_to_mention_it(self):
        prompt = read_text(IMPORT / "good-prompt-support.md")
        result = review(prompt, read_text(IMPORT / "warn-vague-and-untraced.md"))
        untraced = [w for w in result["warnings"] if w["code"] == "untraced"]
        self.assertEqual([w["criterion"] for w in untraced], ["C4"])
        self.assertIn("Requirement line", untraced[0]["message"])
        self.assertIn("matching instruction to your prompt", untraced[0]["message"])
        self.assertEqual(result["blocking"], [])
        self.assertTrue(result["ready"])

    def test_good_list_layout_is_traced_by_name_number_or_shared_words(self):
        result = review(read_text(IMPORT / "good-prompt-support.md"), read_text(IMPORT / "good-cases-list.md"))
        self.assertEqual([w for w in result["warnings"] if w["code"] == "untraced"], [])

    def test_matching_is_by_word_stem(self):
        text = ("1. **Grouped**: grouped by client\n2. **Order**: mentions the refund or the replacement\n"
                "3. **Count**: under 120 words\n")
        prompt = "Group the work by clients. Refunds and replacements are common. Under 120 words."
        self.assertEqual([w for w in review(prompt, text)["warnings"] if w["code"] == "untraced"], [])

    def test_without_a_readable_prompt_nothing_is_flagged(self):
        result = review(None, read_text(IMPORT / "warn-vague-and-untraced.md"))
        self.assertEqual([w for w in result["warnings"] if w["code"] == "untraced"], [])

    def test_a_missing_threshold_warns(self):
        text = ("### C1: A\n- Requirement: r\n- Threshold: Passes if \"a\" appears\n\n### C2: B\n- Requirement: r\n\n"
                "### C3: C\n- Requirement: r\n- Threshold: Word count under 9 passes\n")
        result = review("r", text)
        self.assertEqual([w["criterion"] for w in result["warnings"] if w["code"] == "missing_threshold"], ["C2"])
        self.assertIn("Threshold line", result["warnings"][0]["message"])


class VagueWords(unittest.TestCase):
    """4.24: a warning that leads to the NOT CHECKED guidance."""

    def test_the_canonical_words_are_flagged(self):
        for word in ("clear", "good", "concise", "professional", "relevant", "accurate", "helpful", "natural",
                     "appropriate", "easy", "nice", "engaging", "effective"):
            with self.subTest(word=word):
                self.assertEqual(ic.vague_words(f"Passes if the reply is {word}"), [word])
                self.assertEqual(ic.vague_words(f"PASSES IF THE REPLY IS {word.upper()}"), [word])

    def test_ordinary_words_and_other_forms(self):
        self.assertEqual(ic.vague_words("Word count under 150 passes"), [])
        self.assertEqual(ic.vague_words("Passes if clearly written and concisely put"), ["clearly", "concisely"])
        self.assertEqual(ic.vague_words("clear, clear and clear"), ["clear"])
        self.assertEqual(ic.vague_words("unclear or goodwill"), [])

    def test_terms_the_participant_chose_are_not_flagged(self):
        self.assertEqual(ic.vague_words('Passes if "good" or `helpful` appears'), [])
        self.assertEqual(ic.vague_words('Passes if "good" appears and the tone is friendly'), ["friendly"])

    def test_a_flag_is_a_warning_and_never_blocks(self):
        prompt = read_text(IMPORT / "good-prompt-support.md")
        result = review(prompt, read_text(IMPORT / "warn-vague-and-untraced.md"))
        vague = [w for w in result["warnings"] if w["code"] == "vague"]
        self.assertEqual([w["criterion"] for w in vague], ["C4"])
        self.assertEqual(result["blocking"], [])
        self.assertTrue(result["ready"])

    def test_the_message_leads_to_the_not_checked_guidance(self):
        result = review("x", read_text(IMPORT / "warn-vague-and-untraced.md"))
        message = next(w["message"] for w in result["warnings"] if w["code"] == "vague")
        self.assertIn("C4 Warranty", message)
        self.assertIn("“accurate”, “easy”", message)
        self.assertIn("NOT CHECKED", message)
        self.assertIn("count as not covered", message)
        self.assertIn("a number, a list of terms you choose, or a label", message)

    def test_the_vague_threshold_is_flagged_even_when_a_content_criterion_exists(self):
        result = review("x", read_text(IMPORT / "bad-all-vague.md"))
        self.assertEqual([w["criterion"] for w in result["warnings"] if w["code"] == "vague"], ["C1", "C2"])

    def test_the_words_come_from_the_skills_not_checked_section(self):
        skill = read_text(helpers.KIT / "skills" / "build-eval-script" / "SKILL.md")
        section = skill.split("**NOT CHECKED** applies when", 1)[1].split("Do not guess", 1)[0]
        for word in ("clear", "good", "concise", "professional", "relevant", "accurate", "helpful", "natural",
                     "appropriate"):
            self.assertIn(word, section)
            self.assertEqual(ic.vague_words(word), [word])


class Reading(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-import-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prompt = self.tmp / "my prompt.md"
        self.cases = self.tmp / "my cases.md"
        shutil.copy(str(IMPORT / "good-prompt-support.md"), str(self.prompt))
        shutil.copy(str(IMPORT / "good-cases-support.md"), str(self.cases))

    def run_review(self, prompt=None, cases=None, destinations=None):
        return ic.review_files(str(self.prompt) if prompt is None else prompt,
                               str(self.cases) if cases is None else cases, destinations)

    def test_quotes_around_a_pasted_path_are_fine(self):
        result, _ = self.run_review(prompt=f'"{self.prompt}"')
        self.assertTrue(result["ready"])

    def test_sources_are_only_read(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.prompt, self.cases)}
        os.utime(str(self.prompt), ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
        before[self.prompt] = (self.prompt.read_bytes(), self.prompt.stat().st_mtime_ns)
        for _ in range(3):
            self.run_review()
        for path, (data, mtime) in before.items():
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_missing_blank_relative_and_folder_paths(self):
        cases = [
            ({"prompt": ""}, "missing_prompt_path"),
            ({"cases": "   "}, "missing_test_cases_path"),
            ({"prompt": "relative\\prompt.md"}, "not_absolute"),
            ({"prompt": str(self.tmp)}, "not_a_file"),
            ({"prompt": str(self.tmp / "nope.md")}, "file_not_found"),
            ({"cases": "\\\\.\\pipe\\x"}, "not_absolute"),
        ]
        for kwargs, code in cases:
            with self.subTest(code=code, kwargs=kwargs):
                result, data = self.run_review(**{"prompt": kwargs.get("prompt"), "cases": kwargs.get("cases")})
                self.assertIn(code, codes(result["blocking"]))
                self.assertFalse(result["ready"])
                self.assertTrue(NEXT_ACTION.search(result["blocking"][0]["message"]), result["blocking"][0]["message"])

    def test_non_text_inputs_do_not_crash(self):
        result, _ = ic.review_files(None, 5)
        self.assertEqual(codes(result["blocking"]), ["missing_prompt_path", "missing_test_cases_path"])

    def test_the_path_is_named_in_the_not_found_message(self):
        result, _ = self.run_review(prompt=str(self.tmp / "nope.md"))
        self.assertIn(str(self.tmp / "nope.md"), result["blocking"][0]["message"])

    def test_empty_and_binary_files(self):
        self.prompt.write_bytes(b"  \r\n \n")
        self.cases.write_bytes(b"PK\x03\x04\x00\x00binary")
        result, _ = self.run_review()
        self.assertEqual(codes(result["blocking"]), ["empty", "not_text"])
        self.assertIn("Your prompt file is empty", result["blocking"][0]["message"])
        self.assertIn("Word document", result["blocking"][1]["message"])

    def test_utf16_is_refused_as_not_plain_text(self):
        self.cases.write_bytes(read_text(IMPORT / "good-cases-support.md").encode("utf-16"))
        result, _ = self.run_review()
        self.assertEqual(codes(result["blocking"]), ["not_text"])

    def test_a_file_over_the_size_limit_is_refused(self):
        with mock.patch.object(ic, "MAX_BYTES", 100):
            result, _ = self.run_review()
        self.assertEqual(codes(result["blocking"]), ["too_large", "too_large"])

    def test_a_windows_1252_file_warns_but_can_be_imported(self):
        self.cases.write_bytes(read_text(IMPORT / "good-cases-support.md").encode("utf-8")
                               .replace(b"customer", b"caf\xc3\xa9").decode("utf-8").encode("cp1252"))
        result, data = self.run_review()
        self.assertTrue(result["ready"])
        self.assertEqual(codes(result["warnings"]), ["not_utf8"])
        self.assertEqual(data["test_cases"], self.cases.read_bytes())

    def test_a_different_file_already_in_the_project_blocks_and_the_same_one_does_not(self):
        project = self.tmp / "project"
        project.mkdir()
        dest = {"prompt": project / "prompt-v0.md", "test_cases": project / "test-cases.md"}
        dest["prompt"].write_bytes(b"something else")
        shutil.copy(str(self.cases), str(dest["test_cases"]))
        result, _ = self.run_review(destinations=dest)
        self.assertEqual(codes(result["blocking"]), ["destination_exists"])
        self.assertIn("prompt-v0.md", result["blocking"][0]["message"])
        self.assertIn("never replaces your files", result["blocking"][0]["message"])
        self.assertEqual(dest["prompt"].read_bytes(), b"something else")

    def test_blank_paths_use_the_files_already_in_the_project(self):
        project = self.tmp / "project"
        project.mkdir()
        dest = {"prompt": project / "prompt-v0.md", "test_cases": project / "test-cases.md"}
        shutil.copy(str(self.prompt), str(dest["prompt"]))
        shutil.copy(str(self.cases), str(dest["test_cases"]))
        result, data = ic.review_files("", "", dest)
        self.assertTrue(result["ready"])
        self.assertEqual(data["prompt"], self.prompt.read_bytes())

    def test_no_content_but_a_clean_read_still_reports_criteria(self):
        result, _ = self.run_review(cases=str(IMPORT / "bad-format-only.md"))
        self.assertEqual(codes(result["blocking"]), ["no_content_criterion"])
        self.assertEqual(len(result["criteria"]), 4)


class Messages(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(resources.read_text("content/import-checks.json"))
        self.source = (Path(ic.__file__)).read_text(encoding="utf-8")

    def test_every_code_used_has_a_message_and_every_message_is_used(self):
        used_blocking = set(re.findall(r'_item\("blocking", "(\w+)"', self.source)) | {
            f"missing_{k}_path" for k in ("prompt", "test_cases")}
        used_warnings = set(re.findall(r'_item\("warnings", "(\w+)"', self.source))
        self.assertEqual(used_blocking - {"missing_{kind}_path"}, set(self.data["blocking"]))
        self.assertEqual(used_warnings, set(self.data["warnings"]))

    def test_every_blocking_message_ends_with_a_next_action(self):
        for code, text in self.data["blocking"].items():
            with self.subTest(code=code):
                self.assertTrue(text.endswith("."))
                self.assertTrue(NEXT_ACTION.search(text), text)

    def test_wording_rules(self):
        for group in ("blocking", "warnings"):
            for code, text in self.data[group].items():
                with self.subTest(code=code):
                    self.assertNotRegex(text, r"(?i)\b(presenter|facilitator|rooms?|breakouts?|handouts?|neighbou?rs?|clocks?|contact)\b")
                    self.assertNotIn("Copilot Chat", text)

    def test_every_message_formats_cleanly(self):
        fields = {"label": "prompt", "path": "C:\\x", "reason": "r", "count": 1, "min": 3, "missing": 2,
                  "name": "n", "id": "C1", "words": "w"}
        for group in ("blocking", "warnings"):
            for code, text in self.data[group].items():
                with self.subTest(code=code):
                    text.format(**fields)

    def test_file_names_match_the_project(self):
        paths = Paths("C:\\home", "C:\\proj")
        self.assertEqual(ic.PROMPT_NAME, paths.prompt.name)
        self.assertEqual(ic.TEST_CASES_NAME, paths.test_cases.name)
        self.assertEqual(ic.analyze("p", "t")["copies"], {"prompt": "prompt-v0.md", "test_cases": "test-cases.md"})


class ScreenText(unittest.TestCase):
    """4.20 and 4.25: every word of the import screen is in content, and it says what it must."""

    def setUp(self):
        self.ui = json.loads(resources.read_text("content/preflight.json"))["ui"]

    def test_the_copies_are_named_and_the_originals_are_not_touched(self):
        text = self.ui["import_copies"]
        self.assertIn("Your original files are not touched", text)
        self.assertIn("prompt-v0.md", text)
        self.assertIn("test-cases.md", text)
        self.assertIn("do not need to rename", text)

    def test_northwind_is_a_learning_example_and_not_a_submission(self):
        note = self.ui["northwind_note"]
        self.assertIn("Northwind is a learning example", note)
        self.assertIn("cannot be your submission", note)
        self.assertIn("no way to submit it as your own work", note)
        self.assertIn("for practice only", self.ui["starter_northwind_hint"])

    def test_every_import_key_exists(self):
        for key in ("import_heading", "import_intro", "import_check", "import_checking", "import_check_first",
                    "import_stale", "import_ready", "import_ready_notes", "import_blocked", "import_blocking_title",
                    "import_warnings_title", "import_criteria_title"):
            self.assertTrue(self.ui[key].strip(), key)


class EngineImport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-import-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        helpers.write_passed_preflight(self.home)
        self.engine = Engine(self.home, FakeTerminal(), poll_interval=0.01)
        self.src = self.tmp / "originals"
        self.src.mkdir()
        self.prompt = self.src / "My Prompt.md"
        self.cases = self.src / "My Cases.md"
        shutil.copy(str(IMPORT / "good-prompt-support.md"), str(self.prompt))
        shutil.copy(str(IMPORT / "good-cases-support.md"), str(self.cases))

    def body(self, **extra):
        body = {"project_path": str(self.project), "cli_command": "mycli", "starter": "own",
                "prompt_path": str(self.prompt), "test_cases_path": str(self.cases)}
        body.update(extra)
        return body

    def code_of(self, body):
        with self.assertRaises(EngineError) as ctx:
            self.engine.setup(body)
        return ctx.exception.code, ctx.exception.message

    def test_check_is_read_only_and_creates_nothing(self):
        result = self.engine.import_check({"prompt_path": str(self.prompt), "test_cases_path": str(self.cases),
                                           "project_path": str(self.project)})
        self.assertTrue(result["ready"])
        self.assertFalse(self.project.exists())
        self.assertFalse(self.engine.get_state()["configured"])
        self.assertFalse((self.home / "app.json").exists())

    def test_setup_copies_under_the_expected_names_and_never_touches_the_originals(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.prompt, self.cases)}
        self.engine.setup(self.body())
        self.assertEqual((self.project / "prompt-v0.md").read_bytes(), self.prompt.read_bytes())
        self.assertEqual((self.project / "test-cases.md").read_bytes(), self.cases.read_bytes())
        self.assertEqual(self.state_starter(), "own")
        for path, (data, mtime) in before.items():
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_mtime_ns, mtime)
        self.assertEqual(sorted(p.name for p in self.src.iterdir()), ["My Cases.md", "My Prompt.md"])

    def state_starter(self):
        return self.engine.get_state()["setup"]["starter"]

    def test_crlf_and_bom_files_are_copied_byte_for_byte(self):
        data = b"\xef\xbb\xbf" + read_text(IMPORT / "good-cases-support.md").replace("\n", "\r\n").encode("utf-8")
        self.cases.write_bytes(data)
        self.engine.setup(self.body())
        self.assertEqual((self.project / "test-cases.md").read_bytes(), data)

    def test_a_blocking_problem_refuses_with_a_plain_message_and_creates_nothing(self):
        shutil.copy(str(IMPORT / "bad-two-criteria.md"), str(self.cases))
        code, message = self.code_of(self.body())
        self.assertEqual(code, "import_blocked")
        self.assertIn("2 of the 3 criteria", message)
        self.assertFalse(self.project.exists())
        self.assertFalse(self.engine.get_state()["configured"])

    def test_no_content_criterion_refuses_setup(self):
        shutil.copy(str(IMPORT / "bad-format-only.md"), str(self.cases))
        code, message = self.code_of(self.body())
        self.assertEqual(code, "import_blocked")
        self.assertIn("names the terms, labels or facts", message)

    def test_unreadable_files_keep_the_missing_file_code(self):
        code, _ = self.code_of(self.body(prompt_path=str(self.tmp / "nope.md")))
        self.assertEqual(code, "missing_file")
        self.assertFalse(self.project.exists())

    def test_warnings_do_not_stop_setup(self):
        shutil.copy(str(IMPORT / "warn-vague-and-untraced.md"), str(self.cases))
        self.engine.setup(self.body())
        self.assertTrue(self.engine.get_state()["configured"])

    def test_a_different_file_in_the_project_stops_setup_and_is_kept(self):
        self.project.mkdir()
        (self.project / "prompt-v0.md").write_bytes(b"an older prompt")
        code, message = self.code_of(self.body())
        self.assertEqual(code, "import_blocked")
        self.assertIn("never replaces your files", message)
        self.assertEqual((self.project / "prompt-v0.md").read_bytes(), b"an older prompt")

    def test_the_check_names_a_project_that_already_has_progress(self):
        self.engine.setup(self.body())
        result = self.engine.import_check(self.body())
        self.assertEqual(codes(result["warnings"])[:1], ["project_exists"])
        self.assertEqual(result["blocking"], [])

    def test_northwind_setup_does_not_run_the_checks(self):
        self.engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.assertTrue((self.project / "test-cases.md").is_file())

    def test_northwind_is_never_a_choice_that_skips_the_checks_for_own_files(self):
        shutil.copy(str(IMPORT / "bad-no-criteria.md"), str(self.cases))
        code, _ = self.code_of(self.body())
        self.assertEqual(code, "import_blocked")

    def test_the_result_shape(self):
        result = self.engine.import_check(self.body())
        self.assertEqual(sorted(result), ["blocking", "copies", "criteria", "ready", "warnings"])
        self.assertEqual(result["criteria"][0], {"id": "C1", "name": "Length"})


class HttpImport(ServerCase):
    def setUp(self):
        super().setUp()
        self.src = self.tmp / "originals"
        self.src.mkdir()
        self.prompt = self.src / "p.md"
        self.cases = self.src / "c.md"
        shutil.copy(str(IMPORT / "good-prompt-support.md"), str(self.prompt))
        shutil.copy(str(IMPORT / "good-cases-support.md"), str(self.cases))

    def test_import_check_route_shape_and_token(self):
        body = {"prompt_path": str(self.prompt), "test_cases_path": str(self.cases)}
        status, payload = self.post("/api/setup/import-check", body, token=False)
        self.assertEqual(status, 401)
        status, payload = self.post("/api/setup/import-check", body)
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["ok"])
        self.assertIn("state", payload)
        result = payload["result"]
        self.assertTrue(result["ready"])
        self.assertEqual(result["blocking"], [])
        self.assertEqual([c["id"] for c in result["criteria"]], ["C1", "C2", "C3", "C4"])
        self.assertFalse(payload["state"]["configured"])

    def test_blocking_results_are_a_normal_answer_not_an_error(self):
        shutil.copy(str(IMPORT / "bad-two-criteria.md"), str(self.cases))
        status, payload = self.post("/api/setup/import-check", {"prompt_path": str(self.prompt),
                                                                 "test_cases_path": str(self.cases)})
        self.assertEqual(status, 200)
        self.assertFalse(payload["result"]["ready"])
        self.assertEqual(payload["result"]["blocking"][0]["code"], "few_criteria")

    def test_setup_with_own_files_refuses_with_the_error_body_shape(self):
        shutil.copy(str(IMPORT / "bad-two-criteria.md"), str(self.cases))
        status, payload = self.post("/api/setup", {"project_path": str(self.tmp / "project"), "cli_command": "cli",
                                                    "starter": "own", "prompt_path": str(self.prompt),
                                                    "test_cases_path": str(self.cases)})
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "import_blocked")
        self.assertIn("criteria", payload["error"]["message"])
        self.assertIn("state", payload)
        self.assertFalse((self.tmp / "project").exists())

    def test_setup_with_good_own_files_works_and_leaves_originals_alone(self):
        before = (self.prompt.read_bytes(), self.prompt.stat().st_mtime_ns, self.cases.read_bytes(),
                  self.cases.stat().st_mtime_ns)
        status, payload = self.post("/api/setup", {"project_path": str(self.tmp / "project"), "cli_command": "cli",
                                                    "starter": "own", "prompt_path": str(self.prompt),
                                                    "test_cases_path": str(self.cases)})
        self.assertEqual(status, 200, payload)
        self.assertEqual((self.prompt.read_bytes(), self.prompt.stat().st_mtime_ns, self.cases.read_bytes(),
                          self.cases.stat().st_mtime_ns), before)
        self.assertTrue((self.tmp / "project" / "prompt-v0.md").is_file())

    def test_import_check_is_post_only(self):
        status, _, _ = self.request("GET", "/api/setup/import-check")
        self.assertNotEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
