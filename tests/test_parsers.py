from __future__ import annotations

import re
import subprocess
import sys
import unittest

import helpers
from helpers import GOLDEN, NORTHWIND, SOURCE

from eval_coach.parsers import CheckerOutputError, parse_checker_output, parse_test_cases


class TestCaseParser(unittest.TestCase):
    def test_heading_format_on_northwind(self):
        text = (NORTHWIND / "northwind-test-cases-reference.md").read_text(encoding="utf-8")
        found = parse_test_cases(text)
        self.assertEqual([c["id"] for c in found], ["C1", "C2", "C3", "C4", "C5", "C6"])
        self.assertEqual(found[0]["name"], "Length")
        self.assertEqual(found[0]["threshold"], "Word count under 150 passes")
        self.assertEqual(found[2]["requirement"], "Call out the blocker and what you need to resolve it")
        self.assertEqual(found[5]["name"], "Uses the rough notes")

    def test_criteria_table(self):
        text = (
            "# Test cases\n\n## Criteria\n\n"
            "| # | Requirement | Criterion | Format or content | Threshold |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| C1 | Under 150 words | Length | Format | Word count under 150 passes |\n"
            "| C2 | Group by client | Grouped | Format | Labels appear |\n"
        )
        found = parse_test_cases(text)
        self.assertEqual([(c["id"], c["name"]) for c in found], [("C1", "Length"), ("C2", "Grouped")])
        self.assertEqual(found[1]["threshold"], "Labels appear")

    def test_table_without_criterion_column_uses_requirement(self):
        text = "| # | Requirement | Threshold |\n|---|---|---|\n| 1 | Be short | Under 10 words |\n"
        self.assertEqual(parse_test_cases(text)[0], {
            "id": "C1", "name": "Be short", "requirement": "Be short", "threshold": "Under 10 words"})

    def test_numbered_list_in_criteria_section(self):
        text = ("# Test cases\n\n## Test input\n1. a note that is not a criterion\n\n"
                "## Criteria\n1. **Length**: under 100 words\n2) Tone - no exclamation marks\n")
        found = parse_test_cases(text)
        self.assertEqual([(c["id"], c["name"]) for c in found], [("C1", "Length"), ("C2", "Tone")])

    def test_c_prefixed_list(self):
        found = parse_test_cases("- C1: Length under 100\n- C2: Starts with Hello\n")
        self.assertEqual([c["id"] for c in found], ["C1", "C2"])

    def test_no_criteria_fallback(self):
        self.assertEqual(parse_test_cases("# Notes\n\nSome prose, and nothing to check.\n"), [])
        self.assertEqual(parse_test_cases(""), [])

    def test_headings_inside_code_fences_are_ignored(self):
        self.assertEqual(parse_test_cases("```\n### C1: Fake\n```\n"), [])

    def test_crlf(self):
        self.assertEqual(parse_test_cases("### C1: A\r\n- Threshold: x\r\n")[0]["threshold"], "x")


class OutputParser(unittest.TestCase):
    def test_skill_format_with_not_checked(self):
        out = ("== runs/run-1.txt\n"
               "C1 PASS  Length: 58 words (limit: under 150)\n"
               "C2 FAIL  Grouped: missing: Contoso\n"
               "C3 NOT CHECKED  Tone: needs judgment: rewrite as a list of terms\n"
               "-> 1 passed, 1 failed, 1 NOT CHECKED\n\n"
               "== other.txt\n"
               "C1 FAIL  Length: empty output\n"
               "C2 FAIL  Grouped: empty output\n"
               "C3 NOT CHECKED  Tone: needs judgment: rewrite\n"
               "-> 0 passed, 2 failed, 1 NOT CHECKED\n\n"
               "== Pass rate per criterion\n"
               "C1 Length: 1/2\nC2 Grouped: 0/2\nC3 Tone: NOT CHECKED\n")
        files = parse_checker_output(out)
        self.assertEqual([f["file"] for f in files], ["runs/run-1.txt", "other.txt"])
        self.assertEqual([r["verdict"] for r in files[0]["rows"]], ["P", "F", "NC"])
        self.assertEqual(files[0]["rows"][2], {"id": "C3", "name": "Tone", "verdict": "NC",
                                               "reason": "needs judgment: rewrite as a list of terms"})
        self.assertEqual(files[0]["rows"][0]["reason"], "58 words (limit: under 150)")

    def test_older_summary(self):
        files = parse_checker_output("== a.txt\nC1 PASS  X: fine\nC2 FAIL  Y: bad\n-> 1/2 criteria passed\n")
        self.assertEqual([r["verdict"] for r in files[0]["rows"]], ["P", "F"])

    def test_windows_line_endings(self):
        files = parse_checker_output("== a.txt\r\nC1 PASS  X: fine\r\n-> 1 passed, 0 failed, 0 NOT CHECKED\r\n")
        self.assertEqual(files[0]["rows"][0]["verdict"], "P")

    def test_pass_rate_section_is_not_a_file(self):
        files = parse_checker_output("== a.txt\nC1 PASS  X: fine\n-> 1 passed, 0 failed, 0 NOT CHECKED\n\n"
                                     "== Pass rate per criterion\nC1 X: 1/1\n")
        self.assertEqual(len(files), 1)

    def test_unparseable(self):
        for bad in ("hello world", "", "== a.txt\n", "== a.txt\nC1 PASS  X: fine\n",
                    "== a.txt\nC1 PASS  X: fine\n-> 2 passed, 0 failed, 0 NOT CHECKED\n",
                    "== a.txt\nC1 PASS  X: fine\n-> 2/2 criteria passed\n"):
            with self.subTest(bad=bad), self.assertRaises(CheckerOutputError):
                parse_checker_output(bad)


LABELS = {
    "demo-good-output": "demo-good-output.txt",
    "fixture-bad": "fixture-bad.txt",
    "fixture-polished-but-wrong": "fixture-polished-but-wrong.txt",
    "run-1 (sample-run-1)": "sample-run-1.txt",
    "run-2": "sample-run-2.txt",
    "run-3": "sample-run-3.txt",
    "run-4": "sample-run-4.txt",
    "run-5": "sample-run-5.txt",
}
ALL_FILES = ["demo-good-output.txt"] + ["northwind/" + n for n in (
    "fixture-bad.txt", "fixture-polished-but-wrong.txt", "sample-run-1.txt", "sample-run-2.txt",
    "sample-run-3.txt", "sample-run-4.txt", "sample-run-5.txt")]


def expected_matrix():
    """The P/F table in the golden copy of fixture-expected-results.md."""
    matrix = {}
    text = (GOLDEN / "fixture-expected-results.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        name = re.sub(r"\s*\(presenter demo only\)", "", cells[0])
        if len(cells) == 7 and name in LABELS:
            matrix[LABELS[name]] = cells[1:]
    return matrix


def matrix_of(output):
    return {f["file"].replace("\\", "/").rsplit("/", 1)[-1]: [r["verdict"] for r in f["rows"]]
            for f in parse_checker_output(output)}


class GoldenMatrix(unittest.TestCase):
    maxDiff = None

    def test_expected_table_has_all_rows(self):
        self.assertEqual(len(expected_matrix()), 8)

    def test_golden_output_matches_expected_results(self):
        output = (GOLDEN / "reference-output.txt").read_text(encoding="utf-8")
        self.assertEqual(matrix_of(output), expected_matrix())

    def test_running_the_reference_checker_matches(self):
        proc = subprocess.run([sys.executable, "reference-check.py"] + ALL_FILES, cwd=str(GOLDEN),
                              capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(matrix_of(proc.stdout.decode("utf-8")), expected_matrix())

    @unittest.skipUnless((SOURCE / "presenter" / "reference-check.py").is_file(), "source folder absent")
    def test_source_folder_reference_checker_matches(self):
        files = [str(SOURCE / "presenter" / "demo-good-output.txt")] + [
            str(SOURCE / "northwind-examples" / n.split("/")[1]) for n in ALL_FILES[1:]]
        proc = subprocess.run([sys.executable, str(SOURCE / "presenter" / "reference-check.py")] + files,
                              capture_output=True, timeout=30)
        self.assertEqual(matrix_of(proc.stdout.decode("utf-8")), expected_matrix())
        source_table = (SOURCE / "presenter" / "fixture-expected-results.md").read_bytes()
        self.assertEqual(source_table, (GOLDEN / "fixture-expected-results.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
