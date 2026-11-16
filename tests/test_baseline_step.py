from __future__ import annotations

import hashlib
import json
from unittest import mock

import test_engine_gates as base
from test_engine_gates import EngineError, runner, tight_checker

LINE = ("Read skills/build-eval-script/SKILL.md and follow it in run + log mode. The runs are runs/run-1.txt "
        "to runs/run-5.txt. The prompt file is prompt-v0.md. The model was {model}.")

# Prints C3 as NOT CHECKED, in the checker output format of the build skill.
NC_CHECKER = '''
import sys
from pathlib import Path

def main(paths):
    totals = [0, 0]
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        words = len(text.split())
        rows = [("C1", "Length", words < 150, "%d words (limit: under 150)" % words),
                ("C2", "Blocker label", "Blocker:" in text, "label check")]
        print("== " + path)
        for n, (cid, name, ok, reason) in enumerate(rows):
            totals[n] += ok
            print("%s %s  %s: %s" % (cid, "PASS" if ok else "FAIL", name, reason))
        print("C3 NOT CHECKED  Tone: needs judgment: Passes if at least 1 of <your terms> appears")
        passed = sum(1 for r in rows if r[2])
        print("-> %d passed, %d failed, 1 NOT CHECKED\\n" % (passed, len(rows) - passed))
    if len(paths) > 1:
        print("== Pass rate per criterion")
        print("C1 Length: %d/%d" % (totals[0], len(paths)))
        print("C2 Blocker label: %d/%d" % (totals[1], len(paths)))
        print("C3 Tone: NOT CHECKED")
    return 1

sys.exit(main(sys.argv[1:]))
'''


def log_text(summary, tweak=None, runs=5, number=0, prompt="prompt-v0.md", model="mid-tier-model"):
    """An Iteration entry in the skill's format, built from the app's own numbers, with optional changes."""
    tweak = tweak or {}
    rows, nc = [], []
    for c in summary["criteria"]:
        cid = c["id"]
        if c["not_checked"]:
            nc.append(cid)
            rows.append(f"| {cid} {c['name']} | not checked | n/a | needs a rewrite |")
            continue
        passes = tweak.get(cid, c["passes"])
        fails = ", ".join(f"run-{n}" for n in c["failing_runs"])
        rows.append(f"| {cid} {c['name']} | {passes}/{c['checked_runs']} | {c['rate']}% | "
                    f"{'fails: ' + fails if fails else ''} |")
    overall = summary["overall"]
    if "overall" in tweak:
        total = tweak["overall"]
    else:
        total = f"{overall['passes']} / {overall['total']}"
    listed = tweak.get("not_checked", nc)
    return "\n".join([
        f"## Iteration {number}: baseline", "- Date: 2026-11-09", f"- Prompt: {prompt}", f"- Model: {model}",
        f"- Runs: {runs}", f"- Overall: {total}",
        f"- Not checked: {len(listed)}{' (' + ', '.join(listed) + ')' if listed else ''}", "",
        "| Criterion | Passed | Rate | Notes |", "| --- | --- | --- | --- |", *rows, "",
        "- Hypothesis:", "- Change:", "- Result:", "- Reasoning:", ""])


class BaselineCase(base.EngineCase):
    def do_fix(self):
        text = self.data("fix")["test_cases_text"]
        self.engine.step_submit("fix", {"test_cases_text": text.replace(
            "both appear", 'both appear, and the text after "Blocker:" mentions "test data"')})
        self.engine.step_start("fix")
        self.write_checker(tight_checker())
        self.engine.step_run_checker("fix", "fixtures")

    def to_baseline(self, checker=None):
        self.to_step("run")
        self.do_run()
        self.engine.step_submit("run", {"classifications": {"C3:polished": "predicted_wrong"}})
        self.assertTrue(self.check("run")["ok"])
        self.do_fix()
        self.assertTrue(self.check("fix")["ok"])
        if checker:
            self.write_checker(checker)
        self.assertEqual(self.state()["current_step"], "baseline")

    def run_app(self):
        self.engine.step_run_checker("baseline", "baseline")
        return self.data("baseline")

    def write_log(self, text):
        self.paths.iteration_log.write_text(text, encoding="utf-8")

    def gate(self):
        result = self.check("baseline")
        return result, {i["label"]: i for i in result["items"]}

    def failed(self, result):
        return " ".join(i["detail"] for i in result["items"] if not i["ok"])


class Order(BaselineCase):
    def test_baseline_is_locked_until_fix_is_done(self):
        self.to_step("fix")
        self.assertEqual(self.status("baseline"), "locked")
        self.assert_code("step_locked", self.engine.step_start, "baseline")
        self.assert_code("step_locked", self.engine.step_send, "baseline")
        self.assert_code("step_locked", self.engine.step_check, "baseline")
        self.assert_code("step_locked", self.engine.step_run_checker, "baseline", "baseline")
        self.assert_code("step_locked", self.engine.step_submit, "baseline", {"model_name": "x"})

    def test_it_is_next_after_fix_and_last(self):
        self.to_baseline()
        self.assertEqual(self.status("baseline"), "active")
        self.assertEqual([s["id"] for s in self.state()["steps"]][-2:], ["fix", "baseline"])

    def test_it_is_next_after_a_skipped_fix(self):
        self.setup_project()
        self.do_generate(); self.check("generate")
        self.do_build(); self.write_checker(tight_checker()); self.check("build")
        self.do_fixtures(); self.check("fixtures")
        self.do_readback(); self.check("readback")
        self.do_predict(); self.check("predict")
        self.do_key(); self.check("key")
        self.do_run(); self.check("run")
        self.engine.step_skip("fix")
        self.assertEqual(self.status("baseline"), "active")

    def test_finishing_baseline_finishes_the_course(self):
        self.to_baseline()
        self.run_app()
        self.write_log(log_text(self.data("baseline")["summary"]))
        self.assertTrue(self.check("baseline")["ok"])
        self.assertIsNone(self.state()["current_step"])
        self.assertIsNone(self.state()["current_item"])


class TypedLine(BaselineCase):
    def test_the_line_names_the_saved_model(self):
        self.to_baseline()
        self.engine.step_start("baseline")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(self.project))
        cli = self.state()["step"]["cli"]
        self.assertEqual(cli["line"], LINE.format(model="mid-tier-model"))
        self.assertIsNone(cli["blocked"])
        self.engine.step_send("baseline")
        self.assertEqual(self.terminal.typed[-1], LINE.format(model="mid-tier-model"))

    def test_the_template_in_the_content_is_the_exact_line(self):
        text = self.engine.content["steps"]["baseline"]
        self.assertEqual(text["line_template"].format(model="M"), LINE.format(model="M"))
        self.assertEqual(text["line_template"].count("{"), 1)
        self.assertNotIn("line", text)

    def test_the_model_is_forced_to_one_line(self):
        self.to_baseline()
        for raw, expected in (("  Model\nName  v2 ", "Model Name v2"),
                              ("a\r\nb\tc\x07d\x1b[0me", "a b c d [0me"),
                              ("x\u2028y\u00a0z\x85w", "x y z w"),
                              ("line one\n\n\nline two", "line one line two")):
            with self.subTest(raw=raw):
                self.engine.step_submit("baseline", {"model_name": raw})
                self.engine.step_start("baseline")
                self.engine.step_send("baseline")
                typed = self.terminal.typed[-1]
                self.assertEqual(typed, LINE.format(model=expected))
                self.assertNotRegex(typed, r"[\r\n\t\x00-\x1f\x7f]")
                self.assertEqual(self.state()["step"]["cli"]["line"], typed)

    def test_the_saved_model_is_kept_as_written(self):
        self.to_baseline()
        self.engine.step_submit("baseline", {"model_name": "a\nb"})
        progress = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        self.assertEqual(progress["steps"]["generate"]["model_name"], "a\nb")
        self.assertEqual(self.data("generate")["model_name"], "a\nb")

    def test_an_empty_model_cannot_be_sent_and_says_why(self):
        self.to_baseline()
        for empty in ("", "   ", "\n\t\x07 "):
            with self.subTest(empty=empty):
                self.engine.step_submit("baseline", {"model_name": empty})
                self.engine.step_start("baseline")
                cli = self.state()["step"]["cli"]
                self.assertIn("model name is empty", cli["blocked"])
                self.assertTrue(cli["blocked"].rstrip().endswith("."))
                before = list(self.terminal.typed)
                self.assert_code("no_model", self.engine.step_send, "baseline")
                self.assertEqual(self.terminal.typed, before)

    def test_a_model_with_braces_is_typed_as_written(self):
        self.to_baseline()
        self.engine.step_submit("baseline", {"model_name": "m {x} {0}"})
        self.engine.step_start("baseline")
        self.engine.step_send("baseline")
        self.assertEqual(self.terminal.typed[-1], LINE.format(model="m {x} {0}"))

    def test_the_model_must_be_text(self):
        self.to_baseline()
        self.assert_code("bad_input", self.engine.step_submit, "baseline", {"model_name": 5})


class AppRun(BaselineCase):
    def test_one_invocation_covers_all_five_runs_and_results_are_stored(self):
        self.to_baseline()
        real = runner.run_checker
        calls = []

        def spy(project, files, timeout=30, env=None):
            calls.append(list(files))
            return real(project, files, timeout=timeout)

        with mock.patch.object(runner, "run_checker", spy):
            data = self.run_app()
        self.assertEqual(calls, [[f"runs/run-{n}.txt" for n in range(1, 6)]])
        self.assertTrue(data["result"]["ok"])
        self.assertEqual(data["result"]["exit_code"], 1)
        self.assertTrue(data["fresh"])
        self.assertEqual(data["summary"]["overall"], {"passes": data["summary"]["overall"]["passes"], "total": 30})
        saved = json.loads((self.paths.results_dir / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["summary"], data["summary"])
        self.assertEqual(saved["track"], "script")
        self.assertEqual([(c["id"], c["checked_runs"], c["not_checked"]) for c in saved["summary"]["criteria"]],
                         [(c, 5, False) for c in base.IDS])

    def test_data_before_any_run(self):
        self.to_baseline()
        data = self.data("baseline")
        self.assertEqual((data["result"], data["summary"], data["fresh"]), (None, None, False))
        self.assertTrue(data["runs_ready"])
        self.assertTrue(data["checker_exists"])
        self.assertFalse(data["log_exists"])
        self.assertEqual(data["model_name"], "mid-tier-model")
        self.assertEqual([r["done"] for r in data["runs"]], [True] * 5)

    def test_it_needs_all_five_runs(self):
        self.to_baseline()
        self.paths.run_file(3).write_text("  \n", encoding="utf-8")
        with self.assertRaises(EngineError) as ctx:
            self.engine.step_run_checker("baseline", "baseline")
        self.assertEqual(ctx.exception.code, "missing_file")
        self.assertIn("runs/run-3.txt", ctx.exception.message)
        self.paths.run_file(3).unlink()
        self.assert_code("missing_file", self.engine.step_run_checker, "baseline", "baseline")

    def test_it_needs_a_checker_that_passes_the_scan(self):
        self.to_baseline()
        self.paths.check_py.write_text("import requests\n", encoding="utf-8")
        self.assert_code("scan_failed", self.engine.step_run_checker, "baseline", "baseline")
        self.paths.check_py.unlink()
        self.assert_code("no_checker", self.engine.step_run_checker, "baseline", "baseline")

    def test_other_steps_cannot_run_it_and_it_runs_nothing_else(self):
        self.to_baseline()
        self.assert_code("bad_input", self.engine.step_run_checker, "baseline", "fixtures")
        self.assert_code("bad_input", self.engine.step_run_checker, "baseline", "first_look")
        self.assert_code("step_done", self.engine.step_run_checker, "fix", "fixtures")

    def test_an_earlier_step_cannot_run_the_baseline(self):
        self.to_step("fix")
        self.assert_code("bad_input", self.engine.step_run_checker, "fix", "baseline")
        self.assert_code("step_locked", self.engine.step_run_checker, "baseline", "baseline")

    def test_exit_code_two_is_reported_not_counted(self):
        self.to_baseline(checker="import sys\nsys.exit(2)\n")
        data = self.run_app()
        self.assertFalse(data["result"]["ok"])
        self.assertIsNone(data["summary"])
        self.write_log("## Iteration 0: baseline\n- Runs: 5\n")
        result, _ = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("Press Run my checker", self.failed(result))

    def test_a_run_checker_busy_is_refused(self):
        self.to_baseline()
        self.engine._checker_running = True
        self.assert_code("checker_busy", self.engine.step_run_checker, "baseline", "baseline")
        self.assert_code("checker_busy", self.engine.step_check, "baseline")

    def test_a_replaceable_runner_feeds_the_same_gate(self):
        self.to_baseline()
        real = self.run_app()["summary"]
        calls = []

        def other(project, env):
            calls.append(project)
            return runner.run_checker(project, ["runs/run-%d.txt" % n for n in range(1, 6)], env=env)

        from eval_coach import baseline
        baseline.RUNNERS["script"], original = other, baseline.RUNNERS["script"]
        self.addCleanup(baseline.RUNNERS.__setitem__, "script", original)
        again = self.run_app()["summary"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(again, real)


class Gate(BaselineCase):
    def ready(self, **tweak):
        self.to_baseline()
        self.summary = self.run_app()["summary"]
        self.write_log(log_text(self.summary, **tweak))

    def test_a_matching_log_passes_and_is_never_edited(self):
        self.ready()
        before = hashlib.sha256(self.paths.iteration_log.read_bytes()).hexdigest()
        checker_before = hashlib.sha256(self.paths.check_py.read_bytes()).hexdigest()
        self.engine.step_start("baseline")
        result, items = self.gate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["nudges"], [])
        self.assertEqual(self.status("baseline"), "done")
        self.assertFalse(self.terminal.running)
        self.assertEqual(hashlib.sha256(self.paths.iteration_log.read_bytes()).hexdigest(), before)
        self.assertEqual(hashlib.sha256(self.paths.check_py.read_bytes()).hexdigest(), checker_before)

    def test_progress_marks_it_done_after_a_restart(self):
        self.ready()
        self.assertTrue(self.check("baseline")["ok"])
        self.engine = self.new_engine()
        self.assertEqual(self.status("baseline"), "done")

    def test_tolerant_variations_still_pass(self):
        self.to_baseline()
        self.summary = self.run_app()["summary"]
        text = "\ufeff" + log_text(self.summary).replace("/", " / ").replace("%", " %").replace("\n", "\r\n")
        self.paths.iteration_log.write_bytes(text.encode("utf-8"))
        self.assertTrue(self.check("baseline")["ok"])

    def test_no_log(self):
        self.to_baseline()
        self.run_app()
        result, items = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("iteration-log.md was not found", items["iteration-log.md exists"]["detail"])
        self.assertIn("Press Start my CLI", items["iteration-log.md exists"]["detail"])
        self.assertFalse(items["Iteration 0 entry found"]["ok"])

    def test_an_unusable_log(self):
        self.ready()
        self.write_log("hello\n")
        result, items = self.gate()
        self.assertFalse(items["Iteration 0 entry found"]["ok"])
        self.assertIn("Iteration 0", items["Iteration 0 entry found"]["detail"])
        self.assertTrue(items["Iteration 0 entry found"]["detail"].rstrip().endswith("yourself."))
        self.write_log("")
        self.assertFalse(self.check("baseline")["ok"])

    def test_a_log_without_iteration_zero(self):
        self.ready()
        self.write_log(log_text(self.summary, number=1))
        result, items = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("no Iteration 0 entry", items["Iteration 0 entry found"]["detail"])

    def test_two_iteration_zero_entries(self):
        self.ready()
        self.write_log(log_text(self.summary) + "\n" + log_text(self.summary))
        result, items = self.gate()
        self.assertIn("more than one Iteration 0", items["Iteration 0 entry found"]["detail"])

    def test_the_gate_reads_iteration_zero_among_later_entries(self):
        self.ready()
        self.write_log(log_text(self.summary, number=1, tweak={"C1": 1}) + "\n" + log_text(self.summary))
        self.assertTrue(self.check("baseline")["ok"])

    def test_the_app_must_have_run_first(self):
        self.to_baseline()
        self.write_log("## Iteration 0: baseline\n- Runs: 5\n")
        result, items = self.gate()
        self.assertFalse(items["The app counted your five runs"]["ok"])
        self.assertIn("Press Run my checker on the five runs", items["The app counted your five runs"]["detail"])
        self.assertFalse(items["Pass counts match the app's count"]["ok"])

    def test_the_run_goes_stale_when_check_py_changes(self):
        self.ready()
        self.write_checker(tight_checker() + "\n# edited\n")
        result, items = self.gate()
        self.assertFalse(result["ok"])
        self.assertIn("changed after the app counted", items["The app counted your five runs"]["detail"])
        self.assertFalse(self.data("baseline")["fresh"])
        self.run_app()
        self.assertTrue(self.check("baseline")["ok"])

    def test_the_run_goes_stale_when_a_run_file_changes(self):
        self.ready()
        self.paths.run_file(2).write_text(self.paths.run_file(2).read_text(encoding="utf-8") + "\nNew line.\n",
                                          encoding="utf-8")
        result, items = self.gate()
        self.assertFalse(items["The app counted your five runs"]["ok"])
        self.assertTrue(items["The app counted your five runs"]["detail"].endswith("again."))

    def test_a_wrong_count_names_the_criterion_and_both_numbers(self):
        self.to_baseline()
        self.summary = self.run_app()["summary"]
        by_id = {c["id"]: c for c in self.summary["criteria"]}
        wrong = by_id["C2"]["passes"] - 1
        self.write_log(log_text(self.summary, tweak={"C2": wrong}))
        result, items = self.gate()
        self.assertFalse(result["ok"])
        self.assertEqual(
            items["Pass counts match the app's count"]["detail"],
            f"The log says C2 passed {wrong} of 5 runs. The app counted {by_id['C2']['passes']} of 5.")
        self.assertEqual(self.status("baseline"), "active")

    def test_several_wrong_counts_are_all_named(self):
        self.ready()
        self.write_log(log_text(self.summary, tweak={"C1": 0, "C5": 5, "overall": "7 / 30"}))
        detail = self.gate()[1]["Pass counts match the app's count"]["detail"]
        self.assertIn("The log says C1 passed 0 of 5 runs.", detail)
        self.assertIn("The log says C5 passed 5 of 5 runs.", detail)
        self.assertIn("The log says the overall was 7 / 30. The app counted", detail)
        self.assertNotIn("C3", detail)

    def test_a_wrong_overall_alone_fails(self):
        self.ready()
        self.write_log(log_text(self.summary, tweak={"overall": "1 / 30"}))
        result, items = self.gate()
        self.assertFalse(items["Pass counts match the app's count"]["ok"])
        self.assertTrue(items["Iteration 0 entry found"]["ok"])

    def test_a_missing_row_and_a_missing_overall(self):
        self.ready()
        lines = [l for l in log_text(self.summary).split("\n") if not l.startswith("| C4") and not l.startswith("- Overall")]
        self.write_log("\n".join(lines))
        detail = self.gate()[1]["Pass counts match the app's count"]["detail"]
        self.assertIn("The log has no row for C4.", detail)
        self.assertIn("The log has no Overall line.", detail)

    def test_the_runs_line_must_say_five(self):
        self.ready(runs=3)
        result, items = self.gate()
        self.assertEqual(items["The log says 5 runs"]["detail"], "The log says Runs: 3. Your baseline uses 5 runs.")
        self.write_log(log_text(self.summary).replace("- Runs: 5\n", ""))
        self.assertIn("no Runs line", self.gate()[1]["The log says 5 runs"]["detail"])

    def test_empty_prompt_or_model_is_only_a_nudge(self):
        self.ready(model="")
        result, items = self.gate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["nudges"]), 1)
        self.assertIn("Prompt or Model", result["nudges"][0])


class NotChecked(BaselineCase):
    def ready(self, **tweak):
        self.to_baseline(checker=NC_CHECKER)
        self.summary = self.run_app()["summary"]
        self.write_log(log_text(self.summary, **tweak))

    def test_the_app_sees_the_not_checked_criterion(self):
        self.ready()
        self.assertEqual(self.summary["not_checked"], ["C3"])
        c1, c2, c3 = self.summary["criteria"]
        self.assertEqual((c1["passes"], c1["checked_runs"]), (4, 5))
        self.assertEqual((c2["passes"], c2["checked_runs"]), (4, 5))
        self.assertTrue(c3["not_checked"])
        self.assertEqual(self.summary["overall"], {"passes": 8, "total": 10})

    def test_a_log_that_lists_it_passes(self):
        self.ready()
        result, items = self.gate()
        self.assertTrue(result["ok"], result)

    def test_leaving_it_out_of_the_not_checked_line_fails(self):
        self.ready(tweak={"not_checked": []})
        result, items = self.gate()
        self.assertEqual(
            items["NOT CHECKED criteria are listed"]["detail"],
            "The log does not list C3 as not checked. The app saw it as NOT CHECKED, "
            "so add it to the Not checked line.")
        self.assertFalse(result["ok"])

    def test_giving_it_a_pass_count_fails(self):
        self.ready()
        text = log_text(self.summary).replace("| C3 Tone | not checked | n/a | needs a rewrite |",
                                              "| C3 Tone | 3/5 | 60% | |")
        self.write_log(text)
        detail = self.gate()[1]["NOT CHECKED criteria are listed"]["detail"]
        self.assertIn("The log gives C3 a pass count of 3 of 5 runs.", detail)

    def test_listing_a_checked_criterion_as_not_checked_fails(self):
        self.ready(tweak={"not_checked": ["C2", "C3"]})
        detail = self.gate()[1]["NOT CHECKED criteria are listed"]["detail"]
        self.assertIn("The log lists C2 as not checked. The app checked it and counted 4 of 5.", detail)

    def test_an_unknown_id_and_a_wrong_count(self):
        self.ready(tweak={"not_checked": ["C3", "C9"]})
        detail = self.gate()[1]["NOT CHECKED criteria are listed"]["detail"]
        self.assertIn("The log lists C9 as not checked, but your checker has no criterion with that ID.", detail)
        self.write_log(log_text(self.summary).replace("- Not checked: 1 (C3)", "- Not checked: 2 (C3)"))
        detail = self.gate()[1]["NOT CHECKED criteria are listed"]["detail"]
        self.assertIn("The log says 2 criteria were not checked but lists 1.", detail)

    def test_the_overall_total_leaves_it_out(self):
        self.ready(tweak={"overall": "8 / 15"})
        detail = self.gate()[1]["Pass counts match the app's count"]["detail"]
        self.assertIn("The log says the overall was 8 / 15. The app counted 8 / 10.", detail)


class OlderProgress(BaselineCase):
    def rewrite_without_baseline(self):
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        data["steps"].pop("baseline")
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")

    def test_progress_without_a_baseline_entry_loads_and_baseline_is_next(self):
        self.to_baseline()
        self.rewrite_without_baseline()
        self.engine = self.new_engine()
        self.assertTrue(self.state()["configured"], self.state()["setup"]["warnings"])
        self.assertEqual(self.status("fix"), "done")
        self.assertEqual(self.status("baseline"), "active")
        self.assertEqual(self.state()["step"]["data"]["fresh"], False)

    def test_nothing_is_marked_done_that_was_not(self):
        self.to_step("fix")
        self.rewrite_without_baseline()
        self.engine = self.new_engine()
        self.assertEqual([s["id"] for s in self.state()["steps"] if s["status"] == "done"],
                         ["generate", "build", "fixtures", "readback", "predict", "key", "run"])
        self.assertEqual(self.status("fix"), "active")
        self.assertEqual(self.status("baseline"), "locked")

    def test_the_old_progress_file_is_read_through_setup_too(self):
        self.to_baseline()
        self.rewrite_without_baseline()
        self.engine = self.new_engine()
        self.engine.setup({"project_path": str(self.project), "cli_command": ""})
        self.assertEqual(self.status("baseline"), "active")


if __name__ == "__main__":
    import unittest
    unittest.main()
