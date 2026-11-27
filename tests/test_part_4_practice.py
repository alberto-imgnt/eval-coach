"""The Practice baseline of Part 4 (OpenSpec change part-4-course): its bundled checker, config and log, and an attempt
that starts from it instead of from the participant's own Part 3 files. Everything runs on stand-in files; no AI is called."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import GOLDEN, KIT, NORTHWIND, ROOT

import pf_helpers as pf
from eval_coach import attempts as A
from eval_coach import baseline, gates, project, promptfoo, resources, state as store
from eval_coach.engine import EngineError
from eval_coach.parsers import parse_iteration_log
from test_part_4_attempts import HYPOTHESIS, REFERENCE, SAMPLE, Base as AttemptBase, log_entry, sha

PRACTICE = KIT / "part4" / "practice"
EXPECTED = {"C1": 4, "C2": 4, "C3": 4, "C4": 5, "C5": 3, "C6": 5}
BASELINE_PROBLEMS = resources.read_text("content/steps.json")


def counts(summary):
    return {c["id"]: c["passes"] for c in summary["criteria"]}


def scratch(test):
    tmp = Path(tempfile.mkdtemp(prefix="eval-coach-practice-"))
    test.addCleanup(shutil.rmtree, str(tmp), True)
    return tmp


class BundledChecker(unittest.TestCase):
    def folder(self, name):
        root = scratch(self) / "practice"
        (root / "runs").mkdir(parents=True)
        shutil.copy(str(PRACTICE / name), str(root / name))
        for n in range(1, 6):
            shutil.copy(str(NORTHWIND / f"sample-run-{n}.txt"), str(root / "runs" / f"run-{n}.txt"))
        return root

    def test_the_script_gives_the_reference_counts_and_25_of_30(self):
        result = baseline.run_checks(self.folder("check.py"), "script")
        self.assertTrue(result["ok"], result["error"])
        summary = baseline.summarize(result)
        self.assertEqual(counts(summary), EXPECTED)
        self.assertEqual(summary["overall"], {"passes": 25, "total": 30})
        self.assertEqual(summary["not_checked"], [])

    def test_the_script_judges_every_rule_like_the_reference_checker(self):
        spec_ref = (GOLDEN / "reference-check.py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("practice_reference", str(spec_ref))
        reference = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference)
        spec = importlib.util.spec_from_file_location("practice_script", str(PRACTICE / "check.py"))
        practice = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(practice)
        extra = [(GOLDEN / "northwind" / "fixture-bad.txt").read_text(encoding="utf-8"),
                 (GOLDEN / "northwind" / "fixture-polished-but-wrong.txt").read_text(encoding="utf-8")]
        extra += [p.read_text(encoding="utf-8") for p in sorted((GOLDEN / "part4-worked").rglob("run-*.txt"))]
        for text in extra + list(SAMPLE.values()):
            self.assertEqual([fn(text) for _, _, fn in practice.CRITERIA], [fn(text) for _, _, fn in reference.CRITERIA])

    def test_the_script_says_it_is_practice_only(self):
        self.assertIn("practice only", (PRACTICE / "check.py").read_text(encoding="utf-8"))

    def test_the_config_has_the_six_rules_the_script_has(self):
        text = (PRACTICE / "promptfooconfig.yaml").read_text(encoding="utf-8")
        for metric in ("C1_length", "C2_grouped_by_client", "C3_blocker_and_ask", "C4_teams_not_email",
                       "C5_factual_tone", "C6_uses_the_rough_notes"):
            self.assertIn(f"metric: {metric}", text)
        for n in range(1, 6):
            self.assertIn(f"output: file://runs/run-{n}.txt", text)
        self.assertNotIn("llm-rubric", text)

    def test_the_config_passes_the_app_s_own_scan(self):
        root = self.folder("promptfooconfig.yaml")
        paths = project.Paths(scratch(self) / "home", root)
        paths.config_yaml.write_text((PRACTICE / "promptfooconfig.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(gates.scan_messages(paths, "promptfoo"), [])


SPIKE = ROOT / "spikes" / "phase0-preflight"
NODE = SPIKE / "runtime" / "node-v26.13.0-win-x64"
CACHE = SPIKE / "npm-cache"
NPX_CLI = NODE / "node_modules" / "npm" / "bin" / "npx-cli.js"
NODE_READY = (NODE / "node.exe").is_file() and NPX_CLI.is_file() and (CACHE / "_cacache").is_dir()


@unittest.skipUnless(NODE_READY, "the spike's private Node and promptfoo cache are not on this machine")
class BundledConfigWithRealPromptfoo(unittest.TestCase):
    def test_the_config_gives_the_same_counts_as_the_script(self):
        root = scratch(self) / "practice"
        (root / "runs").mkdir(parents=True)
        shutil.copy(str(PRACTICE / "promptfooconfig.yaml"), str(root / "promptfooconfig.yaml"))
        for n in range(1, 6):
            shutil.copy(str(NORTHWIND / f"sample-run-{n}.txt"), str(root / "runs" / f"run-{n}.txt"))
        env = dict(os.environ)
        env["PATH"] = str(NODE) + os.pathsep + env.get("PATH", "")
        env["npm_config_cache"] = str(CACHE)
        env["PROMPTFOO_CONFIG_DIR"] = str(root.parent / "pfconfig")
        result = baseline.run_checks(root, "promptfoo", env=env, npx_argv=[str(NODE / "node.exe"), str(NPX_CLI)])
        self.assertTrue(result["ok"], result["error"])
        summary = baseline.summarize(result)
        self.assertEqual(counts(summary), EXPECTED)
        self.assertEqual(summary["overall"], {"passes": 25, "total": 30})


class BundledLog(unittest.TestCase):
    def test_iteration_0_matches_what_the_checker_counts(self):
        root = scratch(self) / "practice"
        (root / "runs").mkdir(parents=True)
        shutil.copy(str(PRACTICE / "check.py"), str(root / "check.py"))
        for n in range(1, 6):
            shutil.copy(str(NORTHWIND / f"sample-run-{n}.txt"), str(root / "runs" / f"run-{n}.txt"))
        summary = baseline.summarize(baseline.run_checks(root, "script"))
        entries = parse_iteration_log((PRACTICE / "iteration-log.md").read_text(encoding="utf-8"))
        self.assertEqual([e["number"] for e in entries], [0])
        problems = A._baseline_problems()
        self.assertEqual(gates.baseline_count_problems(entries[0], summary, problems), [])
        self.assertEqual(gates.baseline_not_checked_problems(entries[0], summary, problems), [])
        self.assertEqual(entries[0]["not_checked_ids"], summary["not_checked"])
        self.assertIn("practice only", (PRACTICE / "iteration-log.md").read_text(encoding="utf-8"))

    def test_a_new_entry_is_for_the_ai_and_the_participant_to_add(self):
        entries = parse_iteration_log((PRACTICE / "iteration-log.md").read_text(encoding="utf-8"))
        self.assertEqual((entries[0]["hypothesis"], entries[0]["change"], entries[0]["result"], entries[0]["reasoning"]),
                         ("", "", "", ""))


class PracticeStart(AttemptBase):
    """An attempt that starts from the Practice baseline, with Part 3's own files present and untouched."""

    def practice(self):
        return self.paths.part4_practice

    def choose(self):
        self.attempts.choose_start("practice")

    def own_and_practice_log(self, n, decision):
        """The Practice log with Iteration 0 and the entry for attempt n, built from the app's own numbers."""
        summary = store.read_json(self.paths.attempt(n, practice=True).results)
        text = self.practice().iteration_log.read_text(encoding="utf-8")
        return text + "\n" + log_entry(summary, n, decision, HYPOTHESIS)

    def test_choosing_copies_the_bundled_files_and_scores_iteration_0(self):
        before = self.part_3_bytes()
        self.choose()
        p = self.practice()
        for path in (p.prompt, p.test_cases, p.checker(self.track), p.iteration_log, *[p.run_file(n) for n in range(1, 6)]):
            self.assertTrue(path.is_file(), path)
        self.assertEqual(p.prompt.read_text(encoding="utf-8").count("Catch-up copy"), 0)
        self.assertEqual(self.attempts.chosen(), "practice")
        self.assertEqual(self.attempts._zero_summary()["overall"], {"passes": 25, "total": 30})
        self.assertEqual(self.part_3_bytes(), before)
        self.assertEqual(self.progress["parts"]["part-4"]["start"], "practice")

    def test_only_the_checker_for_the_track_is_copied(self):
        self.choose()
        other = self.practice().checker("promptfoo" if self.track == "script" else "script")
        self.assertFalse(other.exists())

    def test_the_participants_own_files_are_never_read_for_practice(self):
        (self.proj / "prompt-v0.md").write_text("MY OWN PROMPT\n", encoding="utf-8")
        self.progress["done"] = []  # not even Part 3's baseline step is needed
        self.choose()
        n = self.attempts.start()["n"]
        self.assertNotIn("MY OWN PROMPT", self.paths.attempt(n, practice=True).prompt.read_text(encoding="utf-8"))

    def test_attempt_1_starts_from_the_practice_files_and_is_stored_apart(self):
        self.choose()
        before = self.part_3_bytes()
        view = self.attempts.start()
        ap = self.paths.attempt(1, practice=True)
        self.assertEqual(ap.project, self.proj / "part-4" / "practice" / "attempts" / "1")
        self.assertEqual((view["n"], view["parent"], view["source"]), (1, 0, "practice"))
        self.assertEqual(ap.prompt.read_bytes(), self.practice().prompt.read_bytes())
        self.assertEqual(ap.test_cases.read_bytes(), self.practice().test_cases.read_bytes())
        self.assertEqual(ap.checker(self.track).read_bytes(), self.practice().checker(self.track).read_bytes())
        self.assertFalse((self.proj / "part-4" / "attempts").exists())
        self.assertEqual(self.part_3_bytes(), before)

    def test_a_full_practice_round_scores_and_is_documented_in_the_practice_log_only(self):
        self.choose()
        own_log = (self.proj / "iteration-log.md").read_bytes()
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        for i in range(1, 6):
            self.paths.attempt(n, practice=True).run_file(i).write_text(SAMPLE[1], encoding="utf-8")
        self.attempts.score(n)
        view = self.attempts.decide(n, "keep")
        self.assertEqual(view["evidence"]["verdict"], "measured gain on these rules")
        self.assertIn("part-4/practice/iteration-log.md", self.attempts.check_log()["items"][0]["detail"] + "part-4/practice/iteration-log.md")
        self.assertFalse(self.attempts.check_log()["ok"])  # the Practice log has no entry for attempt 1 yet
        self.practice().iteration_log.write_text(self.own_and_practice_log(n, "kept"), encoding="utf-8")
        self.assertTrue(self.attempts.check_log()["ok"], self.attempts.check_log())
        self.assertEqual((self.proj / "iteration-log.md").read_bytes(), own_log)
        self.assertEqual(self.attempts.completion()["rounds"], 1)

    def test_the_participants_own_log_is_not_read_for_practice(self):
        self.choose()
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        for i in range(1, 6):
            self.paths.attempt(n, practice=True).run_file(i).write_text(SAMPLE[1], encoding="utf-8")
        self.attempts.score(n)
        self.attempts.decide(n, "keep")
        summary = store.read_json(self.paths.attempt(n, practice=True).results)
        self.write_log(log_entry(self.zero, 0, None, "") + "\n" + log_entry(summary, n, "kept", HYPOTHESIS))
        self.assertFalse(self.attempts.check_log()["ok"])
        self.assertIn("no entry for attempt 1", " ".join(i["detail"] for i in self.attempts.check_log()["items"]))

    def test_a_missing_practice_log_names_its_own_path(self):
        self.choose()
        n = self.attempts.start()["n"]
        self.practice().iteration_log.unlink()
        detail = self.attempts.check_log()["items"][0]["detail"]
        self.assertIn("part-4/practice/iteration-log.md", detail)

    def test_an_existing_practice_file_is_never_overwritten(self):
        self.practice().project.mkdir(parents=True)
        self.practice().prompt.write_text("My edited practice prompt.\n", encoding="utf-8")
        self.choose()
        self.assertEqual(self.practice().prompt.read_text(encoding="utf-8"), "My edited practice prompt.\n")
        self.assertTrue(self.practice().checker(self.track).is_file())
        before = sha(self.practice().prompt)
        self.attempts.choose_start("practice")
        self.assertEqual(sha(self.practice().prompt), before)

    def test_the_choice_is_refused_once_round_1_exists(self):
        self.choose()
        self.attempts.start()
        before = self.part_3_bytes()
        with self.assertRaises(EngineError) as ctx:
            self.attempts.choose_start("own")
        self.assertEqual(ctx.exception.code, "start_fixed")
        self.assertIn("reset your lesson progress", ctx.exception.message)
        self.attempts.choose_start("practice")  # the same choice again changes nothing
        self.assertEqual(self.attempts.chosen(), "practice")
        self.assertEqual(self.part_3_bytes(), before)

    def test_own_is_refused_after_round_1_on_the_own_baseline_too(self):
        self.attempts.choose_start("own")
        self.attempts.start()
        with self.assertRaises(EngineError) as ctx:
            self.attempts.choose_start("practice")
        self.assertEqual(ctx.exception.code, "start_fixed")

    def test_own_needs_part_3_s_baseline(self):
        self.progress["done"] = []
        with self.assertRaises(EngineError) as ctx:
            self.attempts.choose_start("own")
        self.assertEqual(ctx.exception.code, "no_baseline")
        self.assertNotIn("part-4", self.progress["parts"])

    def test_an_unknown_choice_is_refused(self):
        with self.assertRaises(EngineError) as ctx:
            self.attempts.choose_start("both")
        self.assertEqual(ctx.exception.code, "bad_start")

    def test_older_progress_with_no_starting_point_means_the_participants_own_baseline(self):
        self.run_attempt(decide="keep")
        self.assertIsNone(self.attempts.chosen())
        self.assertEqual(self.attempts.source(), "own")
        self.assertTrue(self.paths.attempt(1).project.is_dir())

    def test_a_second_practice_round_starts_from_the_kept_practice_round(self):
        self.choose()
        n = self.attempts.start()["n"]
        self.attempts.save_hypothesis(n, HYPOTHESIS)
        self.paths.attempt(n, practice=True).prompt.write_text("The kept practice prompt.\n", encoding="utf-8")
        for i in range(1, 6):
            self.paths.attempt(n, practice=True).run_file(i).write_text(SAMPLE[1], encoding="utf-8")
        self.attempts.score(n)
        self.attempts.decide(n, "keep")
        view = self.attempts.start()
        self.assertEqual((view["n"], view["parent"]), (2, 1))
        self.assertEqual(self.paths.attempt(2, practice=True).prompt.read_text(encoding="utf-8"),
                         "The kept practice prompt.\n")

    def test_the_manifest_holds_the_choice_as_an_id_and_no_text(self):
        self.choose()
        self.attempts.start()
        block = self.progress["parts"]["part-4"]
        self.assertEqual(block["start"], "practice")
        self.assertNotIn("Northwind", str(block))


class PracticeStartOnThePromptfooTrack(PracticeStart):
    track = "promptfoo"


if __name__ == "__main__":
    unittest.main()
