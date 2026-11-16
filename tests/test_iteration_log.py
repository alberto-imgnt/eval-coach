from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import GOLDEN, KIT, NORTHWIND

from eval_coach import baseline
from eval_coach.parsers import IterationLogError, parse_iteration_log
from eval_coach.project import Paths

SKILL = (KIT / "skills" / "build-eval-script" / "SKILL.md").read_text(encoding="utf-8")
STDLIB_CHECKER = GOLDEN / "reference-check.py"


def skill_template():
    """The log format exactly as Mode 3 of the bundled skill prints it."""
    mode3 = SKILL.split("## Mode 3: Run and log", 1)[1]
    return re.search(r"```markdown\n(.*?)\n```", mode3, re.S).group(1)


def read_golden(name):
    return (GOLDEN / name).read_text(encoding="utf-8")


class SkillFormat(unittest.TestCase):
    def test_the_skill_template_parses_with_empty_fields(self):
        entries = parse_iteration_log(skill_template())
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["number"], 0)
        self.assertEqual(entry["title"], "baseline")
        self.assertEqual((entry["date"], entry["prompt"], entry["model"]), ("", "<prompt file name>", ""))
        self.assertIsNone(entry["runs"])
        self.assertIsNone(entry["overall"])
        self.assertEqual(entry["not_checked_ids"], [])
        self.assertEqual([r["id"] for r in entry["rows"]], ["C1", "C3"])

    def test_the_skill_example_rows(self):
        c1, c3 = parse_iteration_log(skill_template())[0]["rows"]
        self.assertEqual((c1["passes"], c1["checked"], c1["rate"], c1["not_checked"]), (4, 5, 80, False))
        self.assertEqual(c1["failing_runs"], [3])
        self.assertEqual(c1["name"], "<name>")
        self.assertIsNone(c3["passes"])
        self.assertTrue(c3["not_checked"])
        self.assertIsNone(c3["rate"])
        self.assertEqual(c3["notes"], "needs a rewrite")

    def test_the_northwind_golden_entry(self):
        (entry,) = parse_iteration_log(read_golden("iteration-log-northwind.md"))
        self.assertEqual(entry["number"], 0)
        self.assertEqual(entry["date"], "2026-11-09")
        self.assertEqual(entry["prompt"], "prompt-v0.md")
        self.assertEqual(entry["model"], "mid-tier-model")
        self.assertEqual(entry["runs"], 5)
        self.assertEqual(entry["overall"], (25, 30))
        self.assertEqual(entry["not_checked_ids"], [])
        self.assertEqual(entry["not_checked_count"], 0)
        self.assertEqual([(r["id"], r["passes"], r["checked"], r["rate"]) for r in entry["rows"]],
                         [("C1", 4, 5, 80), ("C2", 4, 5, 80), ("C3", 4, 5, 80),
                          ("C4", 5, 5, 100), ("C5", 3, 5, 60), ("C6", 5, 5, 100)])
        self.assertEqual(entry["rows"][4]["failing_runs"], [3, 5])
        self.assertEqual(entry["rows"][3]["failing_runs"], [])
        self.assertEqual(entry["rows"][3]["name"], "Teams, not email")
        self.assertEqual(entry["hypothesis"], "")

    def test_two_entries_and_a_not_checked_criterion(self):
        first, second = parse_iteration_log(read_golden("iteration-log-not-checked.md"))
        self.assertEqual((first["number"], first["title"]), (0, "baseline"))
        self.assertEqual((second["number"], second["title"]), (1, "shorter prompt"))
        self.assertEqual(first["overall"], (9, 10))
        self.assertEqual(first["not_checked_ids"], ["C3"])
        self.assertEqual(first["not_checked_count"], 1)
        self.assertTrue(first["rows"][2]["not_checked"])
        self.assertEqual(first["hypothesis"], "The first criterion fails when the model adds an apology.")
        self.assertEqual(second["overall"], (10, 10))
        self.assertEqual(len(second["rows"]), 3)
        self.assertEqual(second["change"], "Cut the prompt to three sentences.")

    def test_the_golden_log_matches_the_checker_run_on_the_same_runs(self):
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-log-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        (tmp / "runs").mkdir()
        for n in range(1, 6):
            shutil.copy(str(NORTHWIND / f"sample-run-{n}.txt"), str(tmp / "runs" / f"run-{n}.txt"))
        shutil.copy(str(STDLIB_CHECKER), str(tmp / "check.py"))
        summary = baseline.summarize(baseline.run_checks(tmp))
        (entry,) = parse_iteration_log(read_golden("iteration-log-northwind.md"))
        self.assertEqual(entry["overall"], (summary["overall"]["passes"], summary["overall"]["total"]))
        for row, crit in zip(entry["rows"], summary["criteria"]):
            self.assertEqual((row["id"], row["name"], row["passes"], row["checked"], row["rate"], row["failing_runs"]),
                             (crit["id"], crit["name"], crit["passes"], crit["checked_runs"], crit["rate"],
                              crit["failing_runs"]))


class Variations(unittest.TestCase):
    BODY = ("- Date: 2026-11-09\n- Prompt: prompt-v0.md\n- Model: m\n- Runs: 5\n- Overall: 3 / 5\n"
            "- Not checked: 1 (C2)\n\n| Criterion | Passed | Rate | Notes |\n| --- | --- | --- | --- |\n"
            "| C1 Length | 3/5 | 60% | fails: run-2, run-4 |\n| C2 Tone | not checked | n/a | needs a rewrite |\n")

    def one(self, text):
        (entry,) = parse_iteration_log(text)
        return entry

    def check_standard(self, entry):
        self.assertEqual(entry["number"], 0)
        self.assertEqual(entry["overall"], (3, 5))
        self.assertEqual(entry["runs"], 5)
        self.assertEqual(entry["not_checked_ids"], ["C2"])
        self.assertEqual([(r["id"], r["passes"], r["not_checked"]) for r in entry["rows"]],
                         [("C1", 3, False), ("C2", None, True)])
        self.assertEqual(entry["rows"][0]["failing_runs"], [2, 4])

    def test_crlf_and_a_byte_order_mark(self):
        text = "\ufeff## Iteration 0: baseline\n" + self.BODY
        self.check_standard(self.one(text.replace("\n", "\r\n")))

    def test_lone_carriage_returns(self):
        self.check_standard(self.one(("## Iteration 0: baseline\n" + self.BODY).replace("\n", "\r")))

    def test_bold_markers_everywhere(self):
        body = ("- **Date:** 2026-11-09\n- **Prompt:** prompt-v0.md\n- **Model**: m\n- **Runs:** 5\n"
                "- **Overall:** **3 / 5**\n- **Not checked:** 1 (**C2**)\n\n"
                "| **Criterion** | **Passed** | **Rate** | **Notes** |\n| --- | --- | --- | --- |\n"
                "| **C1** Length | **3/5** | **60%** | fails: run-2, run-4 |\n"
                "| **C2** Tone | **not checked** | n/a | needs a rewrite |\n")
        for heading in ("## **Iteration 0: baseline**", "### Iteration 0 - baseline", "## Iteration 0",
                        "# Iteration 0: baseline", "## Iteration 0 baseline"):
            with self.subTest(heading=heading):
                entry = self.one(heading + "\n" + body)
                self.check_standard(entry)

    def test_spaces_in_fractions_and_percentages(self):
        body = ("- Runs:   5 \n- Overall:  3  /  5\n- Not checked: 1 (C2)\n\n"
                "|Criterion|Passed|Rate|Notes|\n|---|---|---|---|\n"
                "|  C1   Length  |  3 / 5  |  60 %  |  fails:  run-2,run-4  |\n"
                "|C2 Tone|Not Checked|N/A|needs a rewrite|\n")
        entry = self.one("## Iteration 0: baseline\n" + body)
        self.check_standard(entry)
        self.assertEqual(entry["rows"][0]["rate"], 60)

    def test_not_checked_field_variants(self):
        def ids(value):
            return self.one(f"## Iteration 0: baseline\n- Not checked: {value}\n")
        self.assertEqual(ids("none")["not_checked_ids"], [])
        self.assertEqual(ids("none")["not_checked_count"], 0)
        self.assertEqual(ids("0")["not_checked_count"], 0)
        self.assertEqual(ids("2 (C1, C3)")["not_checked_ids"], ["C1", "C3"])
        self.assertEqual(ids("2 (C1, C3)")["not_checked_count"], 2)
        self.assertEqual(ids("C3 and C10")["not_checked_ids"], ["C3", "C10"])
        self.assertIsNone(ids("C3")["not_checked_count"])
        self.assertTrue(ids("")["has_not_checked"])
        self.assertFalse(self.one("## Iteration 0: baseline\n- Runs: 5\n")["has_not_checked"])

    def test_overall_with_words(self):
        entry = self.one("## Iteration 0: baseline\n- Overall: 20 of 25\n")
        self.assertEqual(entry["overall"], (20, 25))

    def test_rows_from_another_entry_stay_with_their_entry(self):
        first, second = parse_iteration_log(
            "## Iteration 0: baseline\n| C1 A | 1/5 | 20% | |\n\n## Iteration 1: x\n| C1 A | 2/5 | 40% | |\n")
        self.assertEqual(first["rows"][0]["passes"], 1)
        self.assertEqual(second["rows"][0]["passes"], 2)

    def test_a_later_top_level_heading_ends_an_entry(self):
        (entry,) = parse_iteration_log("## Iteration 0: baseline\n- Runs: 5\n\n## Notes\n- Runs: 9\n")
        self.assertEqual(entry["runs"], 5)

    def test_a_title_heading_above_the_entries_is_fine(self):
        entries = parse_iteration_log("# Iteration log\n\nSome words.\n\n## Iteration 0: baseline\n- Runs: 5\n")
        self.assertEqual([e["number"] for e in entries], [0])

    def test_a_table_without_criterion_rows_gives_no_rows(self):
        entry = self.one("## Iteration 0: baseline\n| Criterion | Passed |\n| --- | --- |\n")
        self.assertEqual(entry["rows"], [])


class Unusable(unittest.TestCase):
    def test_these_logs_raise_a_clear_error(self):
        for text in ("", "   \n\n", "# Log\nNothing here.\n", "Iteration 0: baseline without a heading\n",
                     "## Notes\n- Runs: 5\n", "\ufeff", "## Iterations\n"):
            with self.subTest(text=text):
                with self.assertRaises(IterationLogError) as ctx:
                    parse_iteration_log(text)
                self.assertIn("Iteration 0", str(ctx.exception))

    def test_non_text_is_refused(self):
        with self.assertRaises(IterationLogError):
            parse_iteration_log(None)


class BaselineRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-baseline-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        (self.tmp / "runs").mkdir()
        for n in range(1, 6):
            shutil.copy(str(NORTHWIND / f"sample-run-{n}.txt"), str(self.tmp / "runs" / f"run-{n}.txt"))
        shutil.copy(str(STDLIB_CHECKER), str(self.tmp / "check.py"))
        self.paths = Paths(self.tmp / "home", self.tmp)

    def test_one_invocation_covers_all_five_runs(self):
        result = baseline.run_checks(self.tmp)
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual([f["file"] for f in result["files"]], baseline.run_names())

    def test_summary_counts_per_criterion(self):
        summary = baseline.summarize(baseline.run_checks(self.tmp))
        self.assertEqual(summary["runs"], 5)
        self.assertEqual([(c["id"], c["passes"], c["checked_runs"], c["rate"]) for c in summary["criteria"]],
                         [("C1", 4, 5, 80), ("C2", 4, 5, 80), ("C3", 4, 5, 80),
                          ("C4", 5, 5, 100), ("C5", 3, 5, 60), ("C6", 5, 5, 100)])
        self.assertEqual([c["failing_runs"] for c in summary["criteria"]], [[5], [2], [3], [], [3, 5], []])
        self.assertEqual(summary["overall"], {"passes": 25, "total": 30})
        self.assertEqual(summary["not_checked"], [])
        self.assertFalse(any(c["not_checked"] for c in summary["criteria"]))

    def test_a_not_checked_criterion_is_flagged_and_left_out_of_the_total(self):
        rows = []
        for n in range(1, 6):
            rows.append({"file": f"runs/run-{n}.txt", "rows": [
                {"id": "C1", "name": "Length", "reason": "", "verdict": "P" if n != 3 else "F"},
                {"id": "C2", "name": "Tone", "reason": "needs judgment", "verdict": "NC"}]})
        summary = baseline.summarize({"ok": True, "exit_code": 1, "error": None, "raw": "", "files": rows})
        c1, c2 = summary["criteria"]
        self.assertEqual((c1["passes"], c1["checked_runs"], c1["failing_runs"]), (4, 5, [3]))
        self.assertEqual((c2["passes"], c2["checked_runs"], c2["not_checked"], c2["rate"]), (0, 0, True, None))
        self.assertEqual(summary["overall"], {"passes": 4, "total": 5})
        self.assertEqual(summary["not_checked"], ["C2"])

    def test_a_missing_run_in_the_output_is_an_error_not_a_summary(self):
        result = {"ok": True, "exit_code": 1, "error": None, "raw": "",
                  "files": [{"file": "runs/run-1.txt", "rows": []}]}
        self.assertIsNone(baseline.summarize(result))
        self.assertIsNone(baseline.summarize({"ok": False, "files": []}))
        self.assertIsNone(baseline.summarize(None))

    def test_a_runner_for_another_track_can_be_registered(self):
        calls = []

        def fake(project, env):
            calls.append((Path(project), env))
            return {"ok": True, "exit_code": 0, "error": None, "raw": "", "files": []}

        baseline.RUNNERS["fake-track"] = fake
        self.addCleanup(baseline.RUNNERS.pop, "fake-track")
        result = baseline.run_checks(self.tmp, "fake-track", env={"A": "1"})
        self.assertEqual(calls, [(self.tmp, {"A": "1"})])
        self.assertIsNotNone(result)

    def test_an_unknown_track_uses_the_script_runner(self):
        self.assertTrue(baseline.run_checks(self.tmp, "no-such-track")["ok"])

    def test_a_checker_that_stops_with_exit_code_two_is_an_error(self):
        (self.tmp / "check.py").write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
        result = baseline.run_checks(self.tmp)
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 2)
        self.assertIsNone(baseline.summarize(result))

    def test_runs_hash_changes_when_any_run_changes(self):
        before = baseline.runs_hash(self.paths)
        self.assertEqual(before, baseline.runs_hash(self.paths))
        (self.tmp / "runs" / "run-4.txt").write_text("different", encoding="utf-8")
        self.assertNotEqual(before, baseline.runs_hash(self.paths))


if __name__ == "__main__":
    unittest.main()
