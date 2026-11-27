"""Part 4's attempt engine (OpenSpec change part-4-attempt-engine): storage, manifest, kept pointer, hypothesis, scoring on
both tracks, the known-good check, the log gate and completion. Everything runs on the stand-in files; no AI is called."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import GOLDEN, NORTHWIND

import course_helpers as ch
import pf_helpers as pf
from eval_coach import attempts as A
from eval_coach import baseline, project, promptfoo, resources, state as store
from eval_coach.engine import EngineError
from eval_coach.parsers import parse_iteration_log

REFERENCE = (GOLDEN / "reference-check.py").read_text(encoding="utf-8")
SAMPLE = {n: (NORTHWIND / f"sample-run-{n}.txt").read_text(encoding="utf-8") for n in range(1, 6)}
BAD = (NORTHWIND / "fixture-bad.txt").read_text(encoding="utf-8")
HYPOTHESIS = "Naming the Blocker and Need labels in the prompt will fix C3."
DROP_C6 = REFERENCE.replace('    ("C6", "Uses the rough notes", check_c6_uses_the_notes),\n', "")
C5_NOT_CHECKED = REFERENCE.replace(
    "            ok, reason = fn(text)\n",
    '            ok, reason = fn(text)\n            if cid == "C5":\n'
    '                print(f"{cid} NOT CHECKED  {name}: needs judgment")\n                continue\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log_entry(summary, n, decision, hypothesis, tweak=None, title="a change"):
    """An iteration log entry in the skill's format, built from the app's own numbers."""
    tweak = tweak or {}
    rows, not_checked = [], []
    for c in summary["criteria"]:
        if c["not_checked"]:
            not_checked.append(c["id"])
            rows.append(f"| {c['id']} {c['name']} | not checked | n/a | needs a rewrite |")
            continue
        fails = ", ".join(f"run-{r}" for r in c["failing_runs"])
        rows.append(f"| {c['id']} {c['name']} | {tweak.get(c['id'], c['passes'])}/{c['checked_runs']} | {c['rate']}% "
                    f"| {'fails: ' + fails if fails else ''} |")
    total = summary["overall"]
    listed = tweak.get("not_checked", not_checked)
    lines = [f"## Iteration {n}: {title}", "- Date: 2026-11-25", "- Prompt: prompt.md", "- Model: sonnet", "- Runs: 5",
             f"- Overall: {tweak.get('overall', str(total['passes']) + ' / ' + str(total['total']))}",
             f"- Not checked: {len(listed)}{' (' + ', '.join(listed) + ')' if listed else ''}"]
    if decision is not None:
        lines.append(f"- Decision: {decision}")
    lines += [f"- Hypothesis: {hypothesis}", "", "| Criterion | Passed | Rate | Notes |", "| --- | --- | --- | --- |",
              *rows, "", "- Change: one change", "- Result: counted", "- Reasoning: because", ""]
    return "\n".join(lines)


class Base(unittest.TestCase):
    track = "script"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-p4-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.proj = self.tmp / "project"
        self.paths = project.Paths(self.tmp / "home", self.proj)
        self.fake = pf.FakePromptfoo()
        self.write_part_3()
        self.progress = store.new_progress(str(self.proj), "fake", "northwind")
        self.progress["done"] = list(store.STEP_IDS)
        self.saves = 0
        self.zero = self.score_part_3()
        self.attempts = self.make()

    # --- Part 3 as it was left -----------------------------------------------

    def write_part_3(self):
        self.proj.mkdir(parents=True)
        (self.proj / "prompt-v0.md").write_text("Write the Northwind update.\n", encoding="utf-8")
        (self.proj / "test-cases.md").write_text((NORTHWIND / "northwind-test-cases-reference.md").read_text(
            encoding="utf-8"), encoding="utf-8")
        for n in range(1, 6):
            self.paths.run_file(n).parent.mkdir(exist_ok=True)
            self.paths.run_file(n).write_text(SAMPLE[n], encoding="utf-8")
        if self.track == "promptfoo":
            (self.proj / "promptfooconfig.yaml").write_text(pf.pf_config(pf.RUN_TESTS), encoding="utf-8")
        else:
            (self.proj / "check.py").write_text(REFERENCE, encoding="utf-8")
        (self.proj / "iteration-log.md").write_text("# Log\n", encoding="utf-8")

    def score_part_3(self):
        env, options = self.runtime()
        result = baseline.run_checks(self.proj, self.track, env=env, **options)
        self.assertTrue(result["ok"], result["error"])
        return baseline.summarize(result)

    def runtime(self):
        if self.track != "promptfoo":
            return None, {}
        return None, {"npx_argv": [r"C:\fake\npx.exe"], "runner": self.fake, "python": sys.executable}

    def save(self):
        self.saves += 1

    def make(self):
        return A.Attempts(self.paths, self.progress, self.save, track=self.track, runtime=self.runtime,
                          iteration_zero=lambda: self.zero, model=lambda: "sonnet")

    # --- an attempt's life -----------------------------------------------------

    def answers(self, n, sources=(1, 1, 1, 1, 1)):
        ap = self.paths.attempt(n)
        for i, source in enumerate(sources, start=1):
            ap.run_file(i).write_text(SAMPLE[source], encoding="utf-8")

    def run_attempt(self, sources=(1, 1, 1, 1, 1), hypothesis=HYPOTHESIS, decide=None):
        """Start the next attempt, write its hypothesis and answers, score it, and optionally decide."""
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, hypothesis)
        self.answers(n, sources)
        view = self.attempts.score(n)
        if decide:
            view = self.attempts.decide(n, decide)
        return n, view

    def code(self, call, *args, **kwargs):
        with self.assertRaises(EngineError) as ctx:
            call(*args, **kwargs)
        return ctx.exception

    def manifest(self):
        return self.progress["parts"]["part-4"]["attempts"]

    def part_3_bytes(self):
        return {str(p.relative_to(self.proj)): p.read_bytes() for p in sorted(self.proj.rglob("*"))
                if p.is_file() and "part-4" not in p.relative_to(self.proj).parts}

    def write_log(self, text):
        (self.proj / "iteration-log.md").write_text(text, encoding="utf-8")

    def saved_summary(self, n):
        return store.read_json(self.paths.attempt(n).results)

    def log_for(self, *attempts, zero_entry=True):
        """The log with Iteration 0 and one entry for each (n, decision) that matches the saved results."""
        parts = [log_entry(self.zero, 0, None, "")] if zero_entry else []
        for n, decision in attempts:
            parts.append(log_entry(self.saved_summary(n), n, decision, HYPOTHESIS))
        return "\n".join(parts)


class Storage(Base):
    def test_attempt_one_starts_from_iteration_0_and_leaves_part_3_alone(self):
        before = self.part_3_bytes()
        view = self.attempts.start()
        ap = self.paths.attempt(1)
        self.assertEqual((view["n"], view["parent"], view["decision"]), (1, 0, "pending"))
        self.assertEqual(ap.project, self.proj / "part-4" / "attempts" / "1")
        self.assertEqual(ap.prompt.read_bytes(), (self.proj / "prompt-v0.md").read_bytes())
        self.assertEqual(ap.test_cases.read_bytes(), (self.proj / "test-cases.md").read_bytes())
        self.assertEqual(ap.check_py.read_bytes(), (self.proj / "check.py").read_bytes())
        self.assertTrue(ap.runs.is_dir())
        self.assertEqual(self.part_3_bytes(), before)

    def test_a_full_attempt_changes_no_part_3_file(self):
        before = self.part_3_bytes()
        self.run_attempt(decide="keep")
        self.run_attempt(sources=(4, 4, 4, 4, 4))
        self.assertEqual(self.part_3_bytes(), before)

    def test_a_second_attempt_starts_from_the_kept_first_one(self):
        n, _ = self.run_attempt(decide="keep")
        self.paths.attempt(n).prompt.write_text("The better prompt.\n", encoding="utf-8")
        view = self.attempts.start()
        ap = self.paths.attempt(2)
        self.assertEqual((view["n"], view["parent"]), (2, 1))
        self.assertEqual(ap.prompt.read_text(encoding="utf-8"), "The better prompt.\n")
        self.assertEqual(ap.check_py.read_bytes(), self.paths.attempt(1).check_py.read_bytes())

    def test_an_undone_attempt_is_not_the_starting_point(self):
        n, _ = self.run_attempt(decide="undo")
        self.paths.attempt(n).prompt.write_text("The rejected prompt.\n", encoding="utf-8")
        self.attempts.start()
        self.assertEqual(self.manifest()[1]["parent"], 0)
        self.assertEqual(self.paths.attempt(2).prompt.read_text(encoding="utf-8"), "Write the Northwind update.\n")

    def test_an_existing_attempt_file_is_never_overwritten(self):
        ap = self.paths.attempt(1)
        ap.project.mkdir(parents=True)
        ap.prompt.write_text("mine\n", encoding="utf-8")
        self.attempts.start()
        self.assertEqual(ap.prompt.read_text(encoding="utf-8"), "mine\n")
        self.assertEqual(ap.test_cases.read_bytes(), (self.proj / "test-cases.md").read_bytes())

    def test_the_next_attempt_waits_for_the_decision_on_the_last(self):
        self.attempts.start()
        error = self.code(self.attempts.start)
        self.assertEqual(error.code, "undecided")
        self.assertIn("keep or undo", error.message)

    def test_nothing_starts_before_part_3_is_finished(self):
        self.progress["done"] = []
        self.assertEqual(self.code(self.attempts.start).code, "no_baseline")
        self.assertNotIn("part-4", self.progress["parts"])

    def test_a_missing_starting_file_is_named(self):
        (self.proj / "test-cases.md").unlink()
        error = self.code(self.attempts.start)
        self.assertEqual(error.code, "no_start_files")
        self.assertIn("test-cases.md", error.message)
        self.assertFalse(self.paths.attempt(1).project.exists())

    def test_an_unknown_attempt_is_refused(self):
        for call in (lambda: self.attempts.score(7), lambda: self.attempts.decide(7, "keep"),
                     lambda: self.attempts.save_hypothesis(7, "x"), lambda: self.attempts.view(7)):
            self.assertEqual(self.code(call).code, "unknown_attempt")


class AttemptFolderIsASmallProject(Base):
    """The runners, the summary and the runs hash treat an attempt folder like Part 3's project folder."""

    def test_the_accessors_the_runners_read_exist_and_point_into_the_folder(self):
        ap = self.paths.attempt(3)
        self.assertEqual(ap.project, self.proj / "part-4" / "attempts" / "3")
        self.assertEqual(ap.run_file(2), ap.project / "runs" / "run-2.txt")
        self.assertEqual(ap.checker("script"), ap.project / "check.py")
        self.assertEqual(ap.checker("promptfoo"), ap.project / "promptfooconfig.yaml")
        self.assertEqual((ap.hypothesis.name, ap.known_good.name, ap.results.name),
                         ("hypothesis.md", "known-good.txt", "results.json"))

    def test_the_same_files_give_the_same_summary_and_hash_as_the_project_root(self):
        n = self.attempts.start()["n"]
        ap = self.paths.attempt(n)
        for i in range(1, 6):
            ap.run_file(i).write_text(SAMPLE[i], encoding="utf-8")
        env, options = self.runtime()
        result = baseline.run_checks(ap.project, self.track, env=env, **options)
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(baseline.summarize(result), self.zero)
        self.assertEqual(baseline.runs_hash(ap), baseline.runs_hash(self.paths))
        ap.run_file(4).write_text("changed", encoding="utf-8")
        self.assertNotEqual(baseline.runs_hash(ap), baseline.runs_hash(self.paths))

    def test_an_empty_folder_hashes_without_failing(self):
        self.assertIsInstance(baseline.runs_hash(self.paths.attempt(9)), str)


class AttemptFolderOnThePromptfooTrack(AttemptFolderIsASmallProject):
    track = "promptfoo"


class Manifest(Base):
    def test_the_manifest_holds_hashes_counts_and_ids_only(self):
        n, _ = self.run_attempt()
        self.attempts.save_known_good(n, SAMPLE[1])
        self.attempts.score_known_good(n)
        rec = self.manifest()[0]
        self.assertEqual(set(rec["hashes"]), {"prompt", "test_cases", "checker", "runs"})
        self.assertEqual((rec["n"], rec["parent"], rec["log_entry"], rec["decision"]), (1, 0, 1, "pending"))
        self.assertEqual(rec["results"]["C5"], {"passes": 5, "checked_runs": 5})
        self.assertEqual(rec["results"]["not_checked"], [])
        dumped = json.dumps(self.progress)
        for text in (HYPOTHESIS, SAMPLE[1][:40], "Write the Northwind update", "Grouped by client", "Factual tone"):
            self.assertNotIn(text, dumped)

    def test_the_manifest_is_saved_and_resumes(self):
        self.run_attempt(decide="keep")
        self.assertGreater(self.saves, 0)
        loaded = store.validate_progress(copy.deepcopy(self.progress))
        again = A.Attempts(self.paths, loaded, self.save, runtime=self.runtime, iteration_zero=lambda: self.zero)
        self.assertEqual((again.kept(), [r["n"] for r in again.manifest()]), (1, [1]))
        self.assertEqual(again.view(1)["decision"], "kept")

    def test_older_progress_loads_unchanged_with_no_part_4_block(self):
        old = store.new_progress("p", "cli", "northwind")
        loaded = store.validate_progress(copy.deepcopy(old))
        self.assertEqual(loaded["parts"], {})
        self.assertEqual(loaded, old)

    def test_an_empty_part_4_block_is_completed_and_a_wrong_one_is_corrupt(self):
        data = store.new_progress("p", "cli", "northwind")
        data["parts"]["part-4"] = {}
        block = store.validate_progress(data)["parts"]["part-4"]
        self.assertEqual(block["attempts"], [])
        self.assertEqual(set(block["steps"]), set(store.PART_4.saved_step_ids()))
        for bad in ({"attempts": "x"}, {"done": "x"}, {"done": ["generate"]}):
            data = store.new_progress("p", "cli", "northwind")
            data["parts"]["part-4"] = bad
            with self.assertRaises(store.CorruptStateError):
                store.validate_progress(data)

    def test_reading_creates_no_saved_block(self):
        self.assertEqual(self.attempts.manifest(), [])
        self.assertEqual(self.attempts.kept(), 0)
        self.assertEqual(self.attempts.overview()["attempts"], [])
        self.assertNotIn("part-4", self.progress["parts"])


class Registration(unittest.TestCase):
    def test_part_4_uses_ids_no_other_part_uses(self):
        self.assertEqual(store.duplicate_ids(), [])
        self.assertIs(store.part_by_id("part-4"), store.PART_4)
        self.assertIs(store.known_part("part-4"), store.PART_4)
        self.assertEqual(store.PART_4.progress_key, "part-4")
        self.assertEqual(set(store.PART_4.new_steps()), set(store.PART_4.saved_step_ids()))

    def test_the_default_block_has_an_empty_manifest(self):
        block = store.new_part_progress(store.PART_4)
        self.assertEqual((block["done"], block["attempts"], block["rerun"], block["iteration_0"], block["start"]),
                         ([], [], None, None, None))
        self.assertNotIn("attempts", store.new_part_progress(store.PART_1))


class KeptPointer(Base):
    def test_the_kept_version_is_iteration_0_until_an_explicit_keep(self):
        self.assertEqual(self.attempts.kept(), 0)
        self.run_attempt()
        self.assertEqual(self.attempts.kept(), 0)
        self.attempts.decide(1, "keep")
        self.assertEqual(self.attempts.kept(), 1)

    def test_an_undone_second_edit_leaves_attempt_1_kept_and_listed(self):
        self.run_attempt(decide="keep")
        self.run_attempt(sources=(2, 2, 2, 2, 2), decide="undo")
        self.assertEqual(self.attempts.kept(), 1)
        self.assertEqual([r["decision"] for r in self.manifest()], ["kept", "undone"])
        self.assertEqual(self.attempts.view(2)["decision"], "undone")
        self.assertTrue(self.paths.attempt(2).results.is_file())

    def test_a_pending_latest_attempt_is_never_assumed_kept(self):
        self.run_attempt(decide="keep")
        self.run_attempt()
        self.assertEqual(self.manifest()[1]["decision"], "pending")
        self.assertEqual(self.attempts.kept(), 1)

    def test_a_decision_needs_a_scored_attempt(self):
        n = self.attempts.start()["n"]
        self.assertEqual(self.code(self.attempts.decide, n, "keep").code, "not_scored")
        self.assertEqual(self.attempts.kept(), 0)

    def test_a_decision_is_refused_when_a_file_changed_after_scoring_until_it_is_scored_again(self):
        n, _ = self.run_attempt()
        for name, change in (("answers", lambda: self.paths.attempt(n).run_file(2).write_text("different\n")),
                             ("prompt", lambda: self.paths.attempt(n).prompt.write_text("edited\n")),
                             ("rules", lambda: self.paths.attempt(n).test_cases.write_text("edited\n"))):
            with self.subTest(changed=name):
                good = {"answers": SAMPLE[1], "prompt": "Write the Northwind update.\n",
                        "rules": (self.proj / "test-cases.md").read_text(encoding="utf-8")}[name]
                change()
                error = self.code(self.attempts.decide, n, "keep")
                self.assertEqual(error.code, "stale")
                self.assertIn(name, error.message)
                self.assertEqual(self.attempts.view(n)["stale"], [{"answers": "runs", "prompt": "prompt",
                                                                    "rules": "test_cases"}[name]])
                restore = {"answers": lambda: self.paths.attempt(n).run_file(2).write_text(good, encoding="utf-8"),
                           "prompt": lambda: self.paths.attempt(n).prompt.write_text(good, encoding="utf-8"),
                           "rules": lambda: self.paths.attempt(n).test_cases.write_text(good, encoding="utf-8")}
                restore[name]()
        self.assertEqual(self.attempts.decide(n, "keep")["decision"], "kept")

    def test_a_decided_attempt_cannot_be_decided_or_scored_again(self):
        n, _ = self.run_attempt(decide="undo")
        self.assertEqual(self.code(self.attempts.decide, n, "keep").code, "already_decided")
        self.assertEqual(self.code(self.attempts.score, n).code, "already_decided")
        self.assertEqual(self.code(self.attempts.save_hypothesis, n, "new").code, "hypothesis_locked")

    def test_only_keep_and_undo_are_choices(self):
        n, _ = self.run_attempt()
        for choice in ("kept", "", None, "pending", 3):
            self.assertEqual(self.code(self.attempts.decide, n, choice).code, "bad_decision")


class Hypothesis(Base):
    def test_scoring_is_refused_until_a_hypothesis_is_saved(self):
        n = self.attempts.start()["n"]
        self.answers(n)
        error = self.code(self.attempts.score, n)
        self.assertEqual(error.code, "hypothesis_needed")
        self.assertIn("hypothesis", error.message)
        self.assertIsNone(self.manifest()[0]["hashes"])
        self.assertFalse(self.paths.attempt(n).results.exists())

    def test_saving_writes_the_file_and_records_its_hash(self):
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, "Line one\r\nline two")
        ap = self.paths.attempt(n)
        self.assertEqual(ap.hypothesis.read_text(encoding="utf-8"), "Line one\nline two")
        self.assertEqual(self.manifest()[0]["hypothesis_hash"], sha(ap.hypothesis))
        self.assertTrue(self.attempts.view(n)["hypothesis_saved"])

    def test_it_can_change_before_the_run_and_is_hashed_again(self):
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, "First idea")
        first = self.manifest()[0]["hypothesis_hash"]
        self.attempts.save_hypothesis(n, "Better idea")
        self.assertNotEqual(self.manifest()[0]["hypothesis_hash"], first)
        self.assertEqual(self.attempts.view(n)["hypothesis"], "Better idea")

    def test_it_cannot_change_after_the_run(self):
        n, _ = self.run_attempt()
        error = self.code(self.attempts.save_hypothesis, n, "Now I know the answer")
        self.assertEqual(error.code, "hypothesis_locked")
        self.assertEqual(self.attempts.view(n)["hypothesis"], HYPOTHESIS)

    def test_answers_that_already_exist_also_lock_it(self):
        n = self.attempts.start()["n"]
        self.answers(n)
        self.assertEqual(self.code(self.attempts.save_hypothesis, n, "late").code, "hypothesis_locked")

    def test_blank_or_odd_text_is_refused(self):
        n = self.attempts.start()["n"]
        self.assertEqual(self.code(self.attempts.save_hypothesis, n, "  \n ").code, "hypothesis_blank")
        for bad in (None, 5, "a\0b", "x" * (A.MAX_TEXT + 1)):
            self.assertEqual(self.code(self.attempts.save_hypothesis, n, bad).code, "bad_text")

    def test_a_hypothesis_changed_outside_the_app_stops_the_run(self):
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.paths.attempt(n).hypothesis.write_text("edited by hand", encoding="utf-8")
        self.assertEqual(self.code(self.attempts.score, n).code, "hypothesis_changed")

    def test_scoring_needs_all_five_answers(self):
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.paths.attempt(n).run_file(4).write_text(" \n", encoding="utf-8")
        error = self.code(self.attempts.score, n)
        self.assertEqual(error.code, "answers_missing")
        self.assertIn("run-4.txt", error.message)


class ScoreOnTheScriptTrack(Base):
    def test_the_checker_runs_in_the_attempt_folder_and_results_json_holds_counts(self):
        n, view = self.run_attempt()
        saved = self.saved_summary(n)
        self.assertEqual(saved["track"], "script")
        self.assertEqual({c["id"]: (c["passes"], c["checked_runs"]) for c in saved["criteria"]},
                         {f"C{i}": (5, 5) for i in range(1, 7)})
        self.assertEqual(saved["overall"], {"passes": 30, "total": 30})
        self.assertEqual(view["five_answers"]["passes"], 30)
        self.assertEqual(self.manifest()[0]["model"], "sonnet")
        self.assertFalse((self.proj / "results.json").exists())
        self.assertEqual(saved["criteria"][0]["name"], "Length")

    def test_five_weaker_answers_count_what_they_earn(self):
        _, view = self.run_attempt(sources=(2, 3, 5, 5, 3))
        passes = {c["id"]: c["passes"] for c in self.saved_summary(1)["criteria"]}
        self.assertEqual(passes["C2"], 4)
        self.assertEqual(passes["C5"], 1)
        self.assertLess(view["five_answers"]["passes"], 30)

    def test_the_result_is_out_of_date_after_a_run_file_changes(self):
        n, view = self.run_attempt()
        self.assertEqual(view["stale"], [])
        self.paths.attempt(n).run_file(3).write_text(SAMPLE[3], encoding="utf-8")
        view = self.attempts.view(n)
        self.assertEqual(view["stale"], ["runs"])
        self.assertEqual(view["stale_text"], "answers")
        self.assertEqual(self.attempts.score(n)["stale"], [])

    def test_the_same_rules_give_no_coverage_flag(self):
        _, view = self.run_attempt()
        self.assertEqual(view["coverage"], {"changed": False, "added": [], "removed": [], "lost": [], "text": None})

    def test_a_different_set_of_rules_is_flagged_and_never_a_gain(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(DROP_C6, encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        view = self.attempts.score(n)
        self.assertEqual(view["coverage"]["removed"], ["C6"])
        self.assertIn("C6", view["coverage"]["text"])
        self.attempts.rerun_iteration_zero()  # the changed rules change Iteration 0's verdicts too
        view = self.attempts.decide(n, "keep")
        self.assertTrue(view["coverage"]["changed"])  # still compared with the original Iteration 0
        self.assertFalse(view["evidence"]["gain"])
        self.assertEqual(view["evidence"]["verdict"], "no measured gain on these rules")
        self.assertIn("not counted as a gain", view["evidence"]["text"])

    def test_a_rule_that_became_not_checked_is_lost_coverage(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(C5_NOT_CHECKED, encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        view = self.attempts.score(n)
        self.assertEqual(self.manifest()[0]["results"]["not_checked"], ["C5"])
        self.assertEqual(view["coverage"]["lost"], ["C5"])
        self.assertIn("lost", view["coverage"]["text"])

    def test_a_checker_that_cannot_run_saves_nothing(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.assertEqual(self.code(self.attempts.score, n).code, "checker_failed")
        self.assertIsNone(self.manifest()[0]["hashes"])
        self.assertFalse(self.paths.attempt(n).results.exists())

    def test_a_checker_that_does_something_unsafe_is_refused_before_it_runs(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(REFERENCE + "\nimport socket\n", encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.assertEqual(self.code(self.attempts.score, n).code, "scan_failed")

    def test_a_missing_checker_is_named(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.unlink()
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        error = self.code(self.attempts.score, n)
        self.assertEqual(error.code, "file_missing")
        self.assertIn("check.py", error.message)


class ScoreOnThePromptfooTrack(Base):
    track = "promptfoo"

    def test_the_copy_is_scored_and_the_original_config_is_untouched(self):
        original = (self.proj / "promptfooconfig.yaml").read_bytes()
        n, view = self.run_attempt(sources=(1, 2, 3, 4, 5))
        self.assertEqual((self.proj / "promptfooconfig.yaml").read_bytes(), original)
        self.assertEqual(self.paths.attempt(n).config_yaml.read_bytes(), original)
        self.assertEqual(self.fake.calls[-1]["cwd"], str(self.paths.attempt(n).project))
        self.assertEqual(self.manifest()[0]["results"], A.compact(self.zero))
        saved = self.saved_summary(n)
        self.assertEqual(saved["track"], "promptfoo")
        self.assertEqual(saved["overall"], {"passes": 25, "total": 30})

    def test_promptfoos_own_output_never_replaces_the_saved_counts(self):
        n, _ = self.run_attempt()
        ap = self.paths.attempt(n)
        self.assertIn("eval-output.json", self.fake.calls[-1]["argv"])
        self.assertIn("criteria", json.loads(ap.results.read_text(encoding="utf-8")))
        self.assertTrue((ap.project / "eval-output.json").is_file())

    def test_the_local_files_a_config_reads_are_copied_without_overwriting(self):
        config = pf.pf_config(pf.RUN_TESTS, extra="    - type: javascript\n      value: file://rules/extra.js")
        (self.proj / "promptfooconfig.yaml").write_text(config, encoding="utf-8")
        (self.proj / "rules").mkdir()
        (self.proj / "rules" / "extra.js").write_text("module.exports = 1;\n", encoding="utf-8")
        (self.proj / "secret.txt").write_text("nope", encoding="utf-8")
        ap = self.paths.attempt(1)
        (ap.project / "rules").mkdir(parents=True)
        (ap.project / "rules" / "extra.js").write_text("mine\n", encoding="utf-8")
        self.attempts.start()
        self.assertEqual((ap.project / "rules" / "extra.js").read_text(encoding="utf-8"), "mine\n")
        self.assertFalse((ap.project / "secret.txt").exists())
        self.assertEqual(A.local_files(config), ["rules/extra.js"])

    def test_known_good_scoring_adds_a_test_to_the_copy_and_the_checker_hash_ignores_it(self):
        n, _ = self.run_attempt()
        ap = self.paths.attempt(n)
        before = self.manifest()[0]["hashes"]["checker"]
        original = (self.proj / "promptfooconfig.yaml").read_bytes()
        self.attempts.save_known_good(n, SAMPLE[1])
        view = self.attempts.score_known_good(n)
        text = ap.config_yaml.read_text(encoding="utf-8")
        self.assertIn("description: known-good", text)
        self.assertIn("file://known-good.txt", text)
        self.assertEqual((self.proj / "promptfooconfig.yaml").read_bytes(), original)
        self.assertEqual(view["stale"], [])  # the added test never reads as "the checker changed"
        self.assertEqual(self.attempts._hashes(ap)["checker"], before)
        self.assertEqual((view["known_good"]["passes"], view["known_good"]["checked"]), (6, 6))
        self.assertEqual(self.fake.calls[-1]["argv"][-1], "eval-output.json")

    def test_the_five_answers_are_scored_on_a_config_with_fixture_tests_the_attempt_folder_has_no_files_for(self):
        (self.proj / "promptfooconfig.yaml").write_text(pf.pf_config(pf.RUN_TESTS + pf.FIXTURE_TESTS), encoding="utf-8")
        self.fake.strict_files = True  # real promptfoo stops on a test whose file is missing
        n, view = self.run_attempt()
        self.assertTrue(view["scored"])
        argv = self.fake.calls[-1]["argv"]
        self.assertEqual(argv[argv.index("--filter-pattern") + 1], "^run-[1-5]$")
        self.assertFalse((self.paths.attempt(n).project / "fixtures").exists())

    def test_known_good_is_scored_before_any_answer_exists_by_running_only_that_test(self):
        self.fake.strict_files = True  # real promptfoo stops when a test it runs reads a file that is not there
        n = self.attempts.start()["n"]
        self.attempts.save_known_good(n, SAMPLE[1])
        view = self.attempts.score_known_good(n)
        self.assertEqual((view["known_good"]["passes"], view["known_good"]["checked"]), (6, 6))
        argv = self.fake.calls[-1]["argv"]
        self.assertEqual(argv[argv.index("--filter-pattern") + 1], "^known-good$")
        self.assertEqual(argv[-2:], ["-o", "eval-output.json"])
        self.assertFalse(self.paths.attempt(n).run_file(1).exists())

    def test_a_config_without_a_run_1_test_is_refused_plainly(self):
        (self.proj / "promptfooconfig.yaml").write_text(pf.pf_config(["run-2", "run-3"]), encoding="utf-8")
        n = self.attempts.start()["n"]
        self.attempts.save_known_good(n, SAMPLE[1])
        self.assertEqual(self.code(self.attempts.score_known_good, n).code, "no_run_test")

    def test_scoring_five_answers_after_the_known_good_answer_is_gone_takes_the_test_out(self):
        n, _ = self.run_attempt()
        ap = self.paths.attempt(n)
        self.attempts.save_known_good(n, SAMPLE[1])
        self.attempts.score_known_good(n)
        ap.known_good.unlink()
        self.attempts.score(n)
        self.assertNotIn("known-good", ap.config_yaml.read_text(encoding="utf-8"))

    def test_a_repaired_config_that_changes_iteration_0_asks_for_a_rerun(self):
        n = self.attempts.start()["n"]
        ap = self.paths.attempt(n)
        ap.config_yaml.write_text(pf.pf_config(pf.RUN_TESTS, nc=("C5",)), encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.attempts.score(n)
        self.assertIsNotNone(self.attempts.rerun_needed())
        self.assertEqual(self.code(self.attempts.decide, n, "keep").code, "rerun_needed")


class ConfigCopy(unittest.TestCase):
    def config(self, eol="\n"):
        return pf.pf_config(pf.RUN_TESTS).replace("\n", eol)

    def test_the_added_test_is_a_copy_of_run_1_and_comes_out_exactly(self):
        for eol in ("\n", "\r\n"):
            with self.subTest(eol=repr(eol)):
                text = self.config(eol)
                added = A.add_known_good_test(text)
                self.assertIn(A.GENERATED_START, added)
                self.assertIn(f"description: known-good{eol}", added)
                self.assertIn(f"output: file://known-good.txt{eol}", added)
                self.assertEqual(A.strip_generated(added), text)
                self.assertEqual(A.add_known_good_test(added), added)  # adding twice keeps one block

    def test_assertions_written_inside_a_test_are_copied(self):
        text = ("providers:\n  - echo\ntests:\n  - description: run-1\n    vars:\n      output: file://runs/run-1.txt\n"
                "    assert:\n      - type: javascript\n        metric: C1_length\n        value: output.length > 1\n"
                "  - description: run-2\n    vars:\n      output: file://runs/run-2.txt\n    assert:\n"
                "      - type: javascript\n        metric: C1_length\n        value: output.length > 2\n")
        added = A.add_known_good_test(text)
        copy_part = added.split(A.GENERATED_START, 1)[1]
        self.assertIn("output.length > 1", copy_part)
        self.assertNotIn("output.length > 2", copy_part)
        self.assertNotIn("run-1", copy_part)

    def test_a_test_section_that_is_not_last_and_a_file_with_no_final_newline(self):
        middle = "tests:\n  - description: run-1\n    vars:\n      output: file://runs/run-1.txt\nother: 1\n"
        added = A.add_known_good_test(middle)
        self.assertLess(added.index("known-good"), added.index("other: 1"))
        self.assertEqual(A.strip_generated(added), middle)
        bare = middle.replace("other: 1\n", "").rstrip("\n")
        self.assertEqual(A.strip_generated(A.add_known_good_test(bare)).rstrip(), bare)

    def test_the_hash_ignores_the_added_test_and_sees_every_other_edit(self):
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-hash-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        path = tmp / "promptfooconfig.yaml"
        text = self.config()
        path.write_text(text, encoding="utf-8")
        base = A.checker_hash(path, "promptfoo")
        path.write_text(A.add_known_good_test(text), encoding="utf-8")
        self.assertEqual(A.checker_hash(path, "promptfoo"), base)
        for name, edited in (("an assertion", text.replace("output.length > 0", "output.length > 9")),
                             ("another test", text.replace("run-2.txt", "run-3.txt")),
                             ("a new test", text + "  - description: extra\n    vars:\n      output: file://x.txt\n"),
                             ("the generated test", A.add_known_good_test(text).replace(
                                 "file://known-good.txt", "file://runs/run-3.txt").replace(
                                 A.GENERATED_START, "# changed"))):
            with self.subTest(edit=name):
                path.write_text(edited, encoding="utf-8")
                self.assertNotEqual(A.checker_hash(path, "promptfoo"), base)

    def test_a_missing_file_has_no_hash(self):
        self.assertIsNone(A.checker_hash(Path("nope.yaml"), "promptfoo"))
        self.assertIsNone(A.checker_hash(Path("nope.py"), "script"))

    def test_only_safe_relative_local_files_are_named(self):
        text = ("a: file://runs/run-1.txt\nb: file://fixtures/x.txt\nc: file://known-good.txt\nd: file://../up.js\n"
                "e: file:///abs.js\nf: file://C:/abs.js\ng: file://./rules.js:check\nh: file://rules.js\n")
        self.assertEqual(A.local_files(text), ["rules.js"])
        self.assertEqual(A.local_files("x: file://a/b.js:fn"), ["a/b.js"])


class KnownGood(Base):
    def test_no_score_exists_before_the_answer_is_saved(self):
        n, view = self.run_attempt()
        self.assertIsNone(view["known_good"])
        self.assertFalse(view["known_good_saved"])
        error = self.code(self.attempts.score_known_good, n)
        self.assertEqual(error.code, "known_good_needed")
        self.assertIsNone(self.manifest()[0]["known_good"])

    def test_saving_the_answer_shows_no_score_until_it_is_scored(self):
        n, _ = self.run_attempt()
        self.attempts.save_known_good(n, SAMPLE[1])
        view = self.attempts.view(n)
        self.assertTrue(view["known_good_saved"])
        self.assertIsNone(view["known_good"])
        self.assertEqual(self.paths.attempt(n).known_good.read_text(encoding="utf-8"), SAMPLE[1])

    def test_95_percent_or_more_meets_the_mark(self):
        n, _ = self.run_attempt(sources=(2, 3, 5, 5, 3))
        self.attempts.save_known_good(n, SAMPLE[1])
        view = self.attempts.score_known_good(n)
        good = view["known_good"]
        self.assertEqual((good["passes"], good["checked"], good["meets"]), (6, 6, True))
        self.assertIn("meets the 95% mark", good["text"])
        self.assertIsNone(good["next_step"])
        # Reported apart: the five answers are still weak, and the two scores are never one value.
        self.assertFalse(view["five_answers"]["meets_target"])
        self.assertNotEqual(view["five_answers"]["text"], good["text"])
        self.assertTrue({"passes", "total"} <= set(view["five_answers"]))
        self.assertNotIn("total", good)

    def test_below_95_percent_gives_a_next_step_and_no_way_to_loosen_a_rule(self):
        n, _ = self.run_attempt()
        self.attempts.save_known_good(n, BAD)
        view = self.attempts.score_known_good(n)
        good = view["known_good"]
        self.assertFalse(good["meets"])
        self.assertLess(good["passes"], good["checked"])
        self.assertTrue(good["failing"])
        self.assertIn("under the 95% mark", good["text"])
        self.assertIn("checker or the written requirements", good["next_step"])
        self.assertIn("Do not loosen a rule", good["next_step"])
        self.assertFalse([key for key in view if "loosen" in key or "threshold" in key])
        self.assertEqual(view["decision"], "pending")  # it never decides anything by itself

    def test_exactly_95_percent_meets_and_just_below_does_not(self):
        self.assertTrue(A._meets(19, 20))
        self.assertFalse(A._meets(18, 19))
        self.assertTrue(A._meets(95, 100))
        self.assertFalse(A._meets(94, 100))
        self.assertFalse(A._meets(0, 0))

    def test_a_new_known_good_answer_drops_the_old_score(self):
        n, _ = self.run_attempt()
        self.attempts.save_known_good(n, SAMPLE[1])
        self.attempts.score_known_good(n)
        self.attempts.save_known_good(n, BAD)
        self.assertIsNone(self.attempts.view(n)["known_good"])
        self.assertEqual(self.code(self.attempts.save_known_good, n, " ").code, "known_good_blank")

    def test_an_edited_checker_marks_the_known_good_result_out_of_date(self):
        n, _ = self.run_attempt()
        self.attempts.save_known_good(n, SAMPLE[1])
        self.attempts.score_known_good(n)
        self.paths.attempt(n).check_py.write_text(REFERENCE + "\n# a note\n", encoding="utf-8")
        self.assertTrue(self.attempts.view(n)["known_good"]["stale"])

    def test_a_repair_that_changes_iteration_0_verdicts_needs_a_rerun_before_any_comparison(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(C5_NOT_CHECKED, encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.attempts.score(n)
        self.attempts.save_known_good(n, SAMPLE[1])
        self.attempts.score_known_good(n)
        note = self.attempts.rerun_needed()
        self.assertEqual(note["attempt"], n)
        error = self.code(self.attempts.decide, n, "keep")
        self.assertEqual(error.code, "rerun_needed")
        self.assertIn("original five answers", error.message)
        overview = self.attempts.overview()
        self.assertTrue(overview["rerun_needed"])
        self.assertFalse(overview["completion"]["ok"])
        corrected = self.attempts.rerun_iteration_zero()
        self.assertEqual(corrected["not_checked"], ["C5"])
        self.assertIsNone(self.attempts.rerun_needed())
        self.assertEqual(self.progress["parts"]["part-4"]["iteration_0"]["results"], corrected)
        self.assertEqual(self.attempts.decide(n, "keep")["decision"], "kept")
        self.assertEqual(self.attempts.coverage(self.manifest()[0])["lost"], ["C5"])  # still flagged

    def test_a_repair_that_changes_no_verdict_asks_for_nothing(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(REFERENCE + "\n# only a comment\n", encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.attempts.score(n)
        self.assertIsNone(self.attempts.rerun_needed())
        self.assertIsNone(self.attempts.rerun_iteration_zero())

    def test_the_original_five_answers_are_never_changed_by_the_check(self):
        before = self.part_3_bytes()
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(C5_NOT_CHECKED, encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.attempts.score(n)
        self.attempts.rerun_iteration_zero()
        self.assertEqual(self.part_3_bytes(), before)


class LogGate(Base):
    def gate(self):
        result = self.attempts.check_log()
        return result, {i["label"]: i for i in result["items"]}

    def failures(self, result):
        return " ".join(i["detail"] for i in result["items"] if not i["ok"])

    def test_a_matching_log_passes_every_item(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, "kept")))
        result, items = self.gate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["items"]), 7)
        self.assertTrue(all(i["ok"] for i in items.values()))

    def test_the_log_is_never_changed(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, "undone")))
        before = (self.proj / "iteration-log.md").read_bytes()
        self.gate()
        self.attempts.completion()
        self.assertEqual((self.proj / "iteration-log.md").read_bytes(), before)

    def test_a_missing_log_or_entry_is_said_plainly(self):
        self.run_attempt(decide="keep")
        (self.proj / "iteration-log.md").unlink()
        result, _ = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("iteration-log.md was not found", self.failures(result))
        self.write_log(self.log_for(zero_entry=True))
        self.assertIn("no entry for attempt 1", self.failures(self.gate()[0]))
        self.write_log("# Notes\nnothing here\n")
        self.assertIn("no entry that starts with a heading", self.failures(self.gate()[0]))

    def test_two_entries_for_one_attempt_are_refused(self):
        self.run_attempt(decide="keep")
        entry = log_entry(self.saved_summary(1), 1, "kept", HYPOTHESIS)
        self.write_log(self.log_for() + "\n" + entry + "\n" + entry)
        self.assertIn("more than one entry for attempt 1", self.failures(self.gate()[0]))

    def test_a_decision_that_differs_names_both_values(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, "undone")))
        result, _ = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("The log says attempt 1 was undone. The app has it as kept.", self.failures(result))

    def test_a_missing_decision_line_is_flagged(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, None)))
        self.assertIn("no Decision line", self.failures(self.gate()[0]))

    def test_the_decision_matches_for_an_undone_attempt(self):
        self.run_attempt(decide="undo")
        self.write_log(self.log_for((1, "undone")))
        self.assertTrue(self.gate()[0]["ok"])

    def test_the_hypothesis_must_be_the_saved_one_ignoring_spacing(self):
        self.run_attempt(decide="keep")
        spaced = "  Naming the   Blocker and Need\tlabels in the prompt will fix C3. "
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(self.saved_summary(1), 1, "kept", spaced))
        self.assertTrue(self.gate()[0]["ok"])
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(
            self.saved_summary(1), 1, "kept", "I knew it would work."))
        result, _ = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("is not the one you saved", self.failures(result))
        self.assertIn(HYPOTHESIS, self.failures(result))
        self.assertIn("I knew it would work.", self.failures(result))
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(self.saved_summary(1), 1, "kept", ""))
        self.assertIn("has no Hypothesis", self.failures(self.gate()[0]))

    def test_a_hypothesis_with_markdown_marks_still_matches(self):
        text = "The **Blocker:** label will fix `C3`."
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, text)
        self.answers(n)
        self.attempts.score(n)
        self.attempts.decide(n, "keep")
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(self.saved_summary(1), 1, "kept", text))
        self.assertTrue(self.gate()[0]["ok"])

    def test_counts_are_compared_with_the_saved_results(self):
        self.run_attempt(sources=(2, 3, 5, 5, 3), decide="keep")
        self.write_log(self.log_for((1, "kept")))
        self.assertTrue(self.gate()[0]["ok"])
        summary = self.saved_summary(1)
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(summary, 1, "kept", HYPOTHESIS, tweak={"C5": 5}))
        result, items = self.gate()
        self.assertFalse(items["Attempt 1 pass counts match the app's count"]["ok"])
        self.assertIn("The log says C5 passed 5 of 5 runs.", self.failures(result))
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(
            summary, 1, "kept", HYPOTHESIS, tweak={"overall": "30 / 30"}))
        self.assertIn("overall was 30 / 30", self.failures(self.gate()[0]))

    def test_not_checked_items_are_compared_with_the_saved_results(self):
        n = self.attempts.start()["n"]
        self.paths.attempt(n).check_py.write_text(C5_NOT_CHECKED, encoding="utf-8")
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.answers(n)
        self.attempts.score(n)
        self.attempts.rerun_iteration_zero()
        self.attempts.decide(n, "keep")
        summary = self.saved_summary(1)
        self.write_log(self.log_for((1, "kept")))
        result, _ = self.gate()
        self.assertTrue(result["ok"], self.failures(result))
        self.assertTrue(any("different set of rules" in nudge or "flagged" in nudge for nudge in result["nudges"]))
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(summary, 1, "kept", HYPOTHESIS, tweak={
            "not_checked": []}))
        self.assertIn("C5 as not checked", self.failures(self.gate()[0]))

    def test_an_unscored_or_changed_attempt_is_not_compared(self):
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.write_log(self.log_for().rstrip() + "\n" + log_entry(self.zero, 1, "pending", HYPOTHESIS))
        result, _ = self.gate()
        self.assertIn("Attempt 1 has not been scored yet.", self.failures(result))
        self.answers(n)
        self.attempts.score(n)
        self.write_log(self.log_for((1, "pending")))
        self.assertTrue(self.gate()[0]["ok"])
        self.paths.attempt(n).run_file(1).write_text(SAMPLE[2], encoding="utf-8")
        result, _ = self.gate()
        self.assertIn("answers for attempt 1 changed after it was scored", self.failures(result))

    def test_results_json_that_no_longer_matches_the_manifest_is_refused(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, "kept")))
        data = self.saved_summary(1)
        data["criteria"][0]["passes"] = 0
        store.write_json_atomic(self.paths.attempt(1).results, data)
        self.assertIn("do not match the app's record", self.failures(self.gate()[0]))
        self.paths.attempt(1).results.unlink()
        self.assertIn("could not be read", self.failures(self.gate()[0]))

    def test_every_attempt_is_checked_in_order(self):
        self.run_attempt(decide="keep")
        self.run_attempt(sources=(2, 2, 2, 2, 2), decide="undo")
        self.write_log(self.log_for((1, "kept"), (2, "undone")))
        result, _ = self.gate()
        self.assertTrue(result["ok"])
        self.assertEqual([i["label"][:9] for i in result["items"]], ["Attempt 1"] * 7 + ["Attempt 2"] * 7)

    def test_an_empty_reasoning_fails_the_presence_item_and_the_log_is_not_changed(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, "kept")).replace("- Reasoning: because", "- Reasoning:"))
        before = (self.proj / "iteration-log.md").read_bytes()
        result, items = self.gate()
        self.assertFalse(result["ok"])
        item = items["Attempt 1 has your Change, Result and Reasoning"]
        self.assertFalse(item["ok"])
        self.assertEqual(item["detail"], "The log entry for attempt 1 has no text for: Reasoning. Write them in your "
                                         "own words.")
        self.assertEqual((self.proj / "iteration-log.md").read_bytes(), before)

    def test_each_missing_field_is_named(self):
        self.run_attempt(decide="keep")
        text = self.log_for((1, "kept")).replace("- Change: one change", "- Change:").replace("- Result: counted",
                                                                                              "- Result:")
        self.write_log(text)
        self.assertIn("Change, Result", self.failures(self.gate()[0]))

    def test_any_text_passes_the_presence_item(self):
        self.run_attempt(decide="keep")
        text = (self.log_for((1, "kept")).replace("- Change: one change", "- Change: x")
                .replace("- Result: counted", "- Result: it rose").replace("- Reasoning: because", "- Reasoning: ?"))
        self.write_log(text)
        result, items = self.gate()
        self.assertTrue(items["Attempt 1 has your Change, Result and Reasoning"]["ok"])
        self.assertTrue(result["ok"], result)

    def test_a_round_needs_the_presence_item_to_count_toward_completion(self):
        self.run_attempt(decide="keep")
        self.write_log(self.log_for((1, "kept")).replace("- Reasoning: because", "- Reasoning:"))
        self.assertEqual(self.attempts.completion()["rounds"], 0)

    def test_the_check_can_stop_at_a_round(self):
        self.run_attempt(decide="keep")
        self.run_attempt(sources=(2, 2, 2, 2, 2), decide="undo")
        self.write_log(self.log_for((1, "kept")))
        self.assertTrue(self.attempts.check_log(through=1)["ok"])
        self.assertFalse(self.attempts.check_log()["ok"])


class Completion(Base):
    def finish_round(self, sources, decision):
        n, _ = self.run_attempt(sources=sources, decide=decision)
        return n

    def document(self, *decisions):
        self.write_log(self.log_for(*[(i, d) for i, d in enumerate(decisions, start=1)]))

    def test_no_round_does_not_pass_and_asks_for_two(self):
        done = self.attempts.completion()
        self.assertFalse(done["ok"])
        self.assertEqual(done["rounds"], 0)
        self.assertIn("Two more rounds are needed", done["text"])

    def test_one_documented_round_does_not_pass(self):
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.document("kept")
        done = self.attempts.completion()
        self.assertFalse(done["ok"])
        self.assertEqual(done["rounds"], 1)
        self.assertIn("One more round is needed", done["text"])

    def test_a_round_that_is_not_in_the_log_does_not_count(self):
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.document("kept")
        self.assertEqual(self.attempts.completion()["rounds"], 1)

    def test_a_pending_attempt_is_not_a_finished_round(self):
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.run_attempt()
        self.document("kept", "pending")
        self.assertEqual(self.attempts.completion()["rounds"], 1)

    def test_two_documented_rounds_below_the_target_still_pass_and_show_a_next_step(self):
        self.finish_round((2, 3, 5, 5, 3), "keep")
        self.finish_round((2, 3, 5, 2, 3), "keep")
        self.document("kept", "kept")
        done = self.attempts.completion()
        self.assertTrue(done["ok"])
        self.assertEqual(done["rounds"], 2)
        self.assertFalse(done["five_answers"]["meets_target"])
        self.assertIn("The target is 95%", done["five_answers"]["text"])
        self.assertIn("one hypothesis", done["next_step"])

    def test_two_rounds_that_meet_the_target_pass_with_no_next_step(self):
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.finish_round((4, 4, 4, 4, 4), "keep")
        self.document("kept", "kept")
        done = self.attempts.completion()
        self.assertTrue(done["ok"])
        self.assertTrue(done["five_answers"]["meets_target"])
        self.assertIsNone(done["next_step"])

    def test_a_kept_improvement_is_a_measured_gain_and_a_flat_attempt_is_not(self):
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.finish_round((1, 1, 1, 1, 1), "keep")
        first, second = self.attempts.view(1)["evidence"], self.attempts.view(2)["evidence"]
        self.assertEqual((first["gain"], first["verdict"]), (True, "measured gain on these rules"))
        self.assertIn("from 25 of 30 to 30 of 30", first["text"])
        self.assertEqual((second["gain"], second["verdict"]), (False, "no measured gain on these rules"))
        self.assertIn("from 30 of 30 to 30 of 30", second["text"])

    def test_a_reverted_attempt_is_never_described_as_a_gain_even_if_its_score_rose(self):
        self.finish_round((1, 1, 1, 1, 1), "undo")
        evidence = self.attempts.view(1)["evidence"]
        self.assertFalse(evidence["gain"])
        self.assertEqual(evidence["verdict"], "no measured gain on these rules")

    def test_a_worse_attempt_is_not_a_gain(self):
        self.finish_round((2, 3, 5, 5, 3), "undo")
        self.assertEqual(self.attempts.view(1)["evidence"]["verdict"], "no measured gain on these rules")

    def test_a_pending_attempt_has_no_evidence_wording_yet(self):
        self.run_attempt()
        self.assertIsNone(self.attempts.view(1)["evidence"])

    def test_the_completion_lists_the_wording_of_each_counted_round(self):
        self.finish_round((1, 1, 1, 1, 1), "keep")
        self.finish_round((1, 1, 1, 1, 1), "undo")
        self.document("kept", "undone")
        lines = self.attempts.completion()["evidence"]
        self.assertEqual(len(lines), 2)
        self.assertIn("Attempt 1: measured gain on these rules.", lines[0])
        self.assertIn("Attempt 2: no measured gain on these rules.", lines[1])

    def test_a_score_comparison_never_rounds_up(self):
        self.assertTrue(A._better((30, 30), (25, 30)))
        self.assertFalse(A._better((25, 30), (25, 30)))
        self.assertFalse(A._better((24, 30), (25, 30)))
        self.assertTrue(A._better((5, 6), (4, 5)))
        self.assertFalse(A._better((4, 5), (5, 6)))
        self.assertFalse(A._better((0, 0), (0, 0)))


class WithTheEngine(ch.CourseBase):
    """`Attempts.for_engine` reads Part 3's saved baseline as Iteration 0 and saves into the engine's own progress file."""

    def test_an_attempt_runs_through_the_engines_progress_and_files(self):
        self.setup_project()
        paths = self.paths
        paths.check_py.write_text(REFERENCE, encoding="utf-8")
        for n in range(1, 6):
            paths.run_file(n).write_text(SAMPLE[n], encoding="utf-8")
        result = baseline.run_checks(paths.project, "script")
        self.engine.progress["done"] = list(store.STEP_IDS)
        self.engine._save_result("baseline", {"track": "script", "result": result, "summary": baseline.summarize(result)})
        attempts = A.Attempts.for_engine(self.engine)
        self.assertEqual(attempts.manifest(), [])
        n = attempts.start()["n"]
        attempts.save_hypothesis(n, HYPOTHESIS)
        for i in range(1, 6):
            paths.attempt(n).run_file(i).write_text(SAMPLE[1], encoding="utf-8")
        view = attempts.score(n)
        self.assertEqual(view["five_answers"]["passes"], 30)
        self.assertEqual(view["model"], self.engine._model_name())
        view = attempts.decide(n, "keep")
        self.assertEqual((view["decision"], view["evidence"]["verdict"]), ("kept", "measured gain on these rules"))
        saved = store.read_json(paths.progress_file)
        self.assertEqual(saved["parts"]["part-4"]["attempts"][0]["decision"], "kept")
        self.assertEqual(saved["done"], list(store.STEP_IDS))
        again = A.Attempts.for_engine(self.new_engine())
        self.assertEqual(again.kept(), 1)

    def test_nothing_starts_before_part_3_is_done(self):
        self.setup_project()
        with self.assertRaises(EngineError) as ctx:
            A.Attempts.for_engine(self.engine).start()
        self.assertEqual(ctx.exception.code, "no_baseline")
        self.assertEqual(self.engine.progress["parts"], {})

    def test_part_4_is_registered_after_the_other_parts(self):
        self.assertEqual([p.id for p in store.PARTS], ["part-3", "part-1", "part-2", "part-4"])


class Wording(unittest.TestCase):
    def test_every_message_is_plain_and_has_its_fields(self):
        words = json.loads(resources.read_text("content/part-4-attempts.json"))
        text = json.dumps(words)
        for banned in ("CLI", "session", "Northwind", "presenter", "facilitator", "handout"):
            self.assertNotIn(banned, text)
        self.assertEqual(words["evidence"]["gain"], "measured gain on these rules")
        self.assertEqual(words["evidence"]["no_gain"], "no measured gain on these rules")
        for key in ("entry", "decision", "hypothesis", "scored", "counts", "not_checked", "written"):
            self.assertEqual(set(words["gate"][key]), {"label", "ok", "fail"})

    def test_the_two_gate_helpers_it_reuses_are_part_3s(self):
        problems = json.loads(resources.read_text("content/steps.json"))["steps"]["baseline"]["gate"]["problems"]
        for key in ("count", "overall", "nc_missing", "nc_extra", "no_row"):
            self.assertIn(key, problems)


class Parsing(unittest.TestCase):
    def test_the_log_entry_reads_a_decision_line(self):
        for value, expected in (("kept", "kept"), ("Undone", "undone"), ("**PENDING**", "pending"),
                                ("maybe later", "maybe later"), ("", "")):
            with self.subTest(value=value):
                entry = parse_iteration_log(f"## Iteration 1: x\n- Decision: {value}\n")[0]
                self.assertEqual(entry["decision"], expected)
        self.assertEqual(parse_iteration_log("## Iteration 1: x\n- Hypothesis: y\n")[0]["decision"], "")


if __name__ == "__main__":
    unittest.main()
