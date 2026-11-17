from __future__ import annotations

import json
import re
import unittest

import helpers
from helpers import GOLDEN, SOURCE

from eval_coach import promptfoo, scan
from eval_coach.parsers import (CheckerOutputError, metric_name, parse_checker_output, parse_promptfoo_config,
                                parse_promptfoo_summary)

PF = GOLDEN / "promptfoo"
NAMES = {"C1": "Length", "C2": "Grouped by client", "C3": "Blocker and ask", "C4": "Teams, not email"}


def read(name):
    return (PF / name).read_text(encoding="utf-8")


def verdicts(entry):
    return {r["id"]: r["verdict"] for r in entry["rows"]}


class SummaryParser(unittest.TestCase):
    """Golden files: the real output of the bundled summarize_results.py on a real results.json from promptfoo 0.125.1."""

    def test_all_tests_in_config_order_with_only_the_c_criteria(self):
        files = parse_promptfoo_summary(read("summary-all.txt"), NAMES)
        self.assertEqual([f["file"] for f in files],
                         ["fixture-bad", "fixture-polished-but-wrong", "run-1", "run-2", "run-3", "run-4", "run-5"])
        for entry in files:
            self.assertEqual([r["id"] for r in entry["rows"]], ["C1", "C2", "C3", "C4"])
            self.assertEqual([r["name"] for r in entry["rows"]],
                             ["Length", "Grouped by client", "Blocker and ask", "Teams, not email"])

    def test_verdicts_match_the_real_summary(self):
        by_name = {f["file"]: verdicts(f) for f in parse_promptfoo_summary(read("summary-all.txt"), NAMES)}
        self.assertEqual(by_name["fixture-bad"], {"C1": "F", "C2": "F", "C3": "F", "C4": "NC"})
        self.assertEqual(by_name["fixture-polished-but-wrong"], {"C1": "P", "C2": "P", "C3": "P", "C4": "NC"})
        self.assertEqual(by_name["run-2"], {"C1": "P", "C2": "F", "C3": "P", "C4": "NC"})
        self.assertEqual(by_name["run-5"], {"C1": "F", "C2": "P", "C3": "P", "C4": "NC"})

    def test_the_non_empty_metric_and_the_pass_rate_section_are_left_out(self):
        text = read("summary-all.txt")
        self.assertIn("non_empty PASS", text)
        self.assertIn("== Pass rate per criterion", text)
        files = parse_promptfoo_summary(text, NAMES)
        self.assertNotIn("Pass rate per criterion", [f["file"] for f in files])
        self.assertFalse(any(r["id"].lower().startswith("non") for f in files for r in f["rows"]))

    def test_prefixes_give_the_same_shape_for_fewer_tests(self):
        runs = parse_promptfoo_summary(read("summary-run.txt"), NAMES)
        self.assertEqual([f["file"] for f in runs], [f"run-{n}" for n in range(1, 6)])
        self.assertEqual([f["file"] for f in parse_promptfoo_summary(read("summary-fixture.txt"), NAMES)],
                         ["fixture-bad", "fixture-polished-but-wrong"])
        self.assertEqual([f["file"] for f in parse_promptfoo_summary(read("summary-run-1.txt"), NAMES)], ["run-1"])

    def test_names_come_from_the_metric_when_test_cases_has_none(self):
        files = parse_promptfoo_summary(read("summary-run-1.txt"))
        self.assertEqual([r["name"] for r in files[0]["rows"]],
                         ["Length", "Grouped by client", "Blocker and ask", "Teams not email"])
        self.assertEqual(metric_name("C2_grouped_by_client"), "Grouped by client")
        self.assertEqual(metric_name("C7"), "C7")
        self.assertEqual(metric_name("tone_check"), "Tone check")

    def test_rows_have_the_same_shape_as_the_script_track(self):
        files = parse_promptfoo_summary(read("summary-run-1.txt"), NAMES)
        self.assertEqual(set(files[0]), {"file", "rows"})
        self.assertEqual(set(files[0]["rows"][0]), {"id", "name", "verdict", "reason"})

    def test_crlf_output_is_read_the_same(self):
        text = read("summary-all.txt").replace("\n", "\r\n")
        self.assertEqual(parse_promptfoo_summary(text, NAMES), parse_promptfoo_summary(read("summary-all.txt"), NAMES))

    def test_a_summary_that_does_not_match_its_lines_is_refused(self):
        bad = read("summary-run-1.txt").replace("-> 4 passed, 0 failed, 1 NOT CHECKED", "-> 5 passed, 0 failed, 0 NOT CHECKED")
        with self.assertRaises(CheckerOutputError):
            parse_promptfoo_summary(bad, NAMES)

    def test_missing_summary_line_or_sections_are_refused(self):
        for text in ("", "nothing here\n", "== run-1\nC1_length PASS\n",
                     "== run-1\nnon_empty PASS\n-> 1 passed, 0 failed, 0 NOT CHECKED\n"):
            with self.subTest(text=text):
                with self.assertRaises(CheckerOutputError):
                    parse_promptfoo_summary(text, NAMES)

    def test_a_metric_with_a_space_in_it_still_counts_in_the_summary_line(self):
        text = "== run-1\nC1_length PASS\n(no metric) FAIL\n-> 1 passed, 1 failed, 0 NOT CHECKED\n"
        files = parse_promptfoo_summary(text)
        self.assertEqual([r["id"] for r in files[0]["rows"]], ["C1"])


class SameAsTheScriptTrack(unittest.TestCase):
    def test_checked_criteria_give_the_same_verdicts_as_the_reference_checker(self):
        script = {f["file"].split("/")[-1].replace("sample-", ""): {r["id"]: r["verdict"] for r in f["rows"]}
                  for f in parse_checker_output((GOLDEN / "reference-output.txt").read_text(encoding="utf-8"))}
        for entry in parse_promptfoo_summary(read("summary-all.txt"), NAMES):
            key = {"fixture-bad": "fixture-bad.txt", "fixture-polished-but-wrong": "fixture-polished-but-wrong.txt"}.get(
                entry["file"], entry["file"] + ".txt")
            with self.subTest(test=entry["file"]):
                for cid in ("C1", "C2", "C3"):
                    self.assertEqual(verdicts(entry)[cid], script[key][cid], cid)


class Reasons(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-pf-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        shutil.copy(str(PF / "results.json"), str(self.tmp / "results.json"))

    def test_reasons_come_from_results_json(self):
        reasons = promptfoo.read_reasons(self.tmp)
        bad = reasons["fixture-bad"]
        self.assertEqual(bad["C1_length"]["fail"], "Word count 154 is greater than maximum 149")
        self.assertIn("Northwind", bad["C2_grouped_by_client"]["fail"])  # the first failing assertion
        self.assertIn("Missing: [Blocker:, Need:]", bad["C3_blocker_and_ask"]["fail"])
        self.assertEqual(bad["C4_teams_not_email"]["nc"], "NOT CHECKED: needs judgment")
        self.assertIsNone(reasons["run-1"]["C1_length"]["fail"])

    def test_added_reasons_are_plain_and_deterministic(self):
        files = parse_promptfoo_summary(read("summary-all.txt"), NAMES)
        promptfoo._add_reasons(files, promptfoo.read_reasons(self.tmp))
        again = parse_promptfoo_summary(read("summary-all.txt"), NAMES)
        promptfoo._add_reasons(again, promptfoo.read_reasons(self.tmp))
        self.assertEqual(files, again)
        rows = {f["file"]: {r["id"]: r for r in f["rows"]} for f in files}
        self.assertEqual(rows["fixture-bad"]["C1"]["reason"], "Word count 154 is greater than maximum 149")
        self.assertEqual(rows["fixture-bad"]["C4"]["reason"], "needs judgment")
        self.assertEqual(rows["run-1"]["C1"]["reason"], promptfoo.REASON_PASS)
        self.assertTrue(all(r["reason"] for f in files for r in f["rows"]))

    def test_the_file_entries_name_the_files_the_tests_read(self):
        self.assertEqual(promptfoo.file_for_test("run-3"), "runs/run-3.txt")
        self.assertEqual(promptfoo.file_for_test("fixture-bad"), "fixtures/fixture-bad.txt")
        self.assertEqual(promptfoo.file_for_test("fixture-polished-but-wrong"), "fixtures/fixture-polished-but-wrong.txt")
        self.assertEqual(promptfoo.file_for_test("example-c1-pass"), "example-c1-pass")


class ConfigParser(unittest.TestCase):
    def test_the_golden_config(self):
        config = parse_promptfoo_config(read("promptfooconfig.yaml"))
        self.assertEqual(config["providers"], ["echo"])
        self.assertFalse(config["provider_keys"])
        self.assertEqual(config["test_names"], ["fixture-bad", "fixture-polished-but-wrong",
                                                "run-1", "run-2", "run-3", "run-4", "run-5"])
        self.assertEqual(sorted(set(config["assert_types"])), ["contains-all", "javascript", "regex", "word-count"])

    def test_the_reference_config_from_the_session_materials(self):
        path = SOURCE / "presenter" / "reference-promptfooconfig.yaml"
        if not path.is_file():
            self.skipTest("source folder absent")
        config = parse_promptfoo_config(path.read_text(encoding="utf-8"))
        self.assertEqual(config["providers"], ["echo"])
        self.assertEqual(config["test_names"][:3], ["demo-good", "fixture-bad", "fixture-polished-but-wrong"])
        self.assertEqual(len(config["test_names"]), 8)
        self.assertIn("not-icontains-any", config["assert_types"])
        self.assertEqual(scan.scan_config_source(path.read_text(encoding="utf-8")), [])

    def names(self, text):
        return parse_promptfoo_config(text)["test_names"]

    def test_tests_variations(self):
        base = "tests:\n  - description: a\n    vars:\n      output: file://x\n  - vars:\n      output: y\n    description: \"b c\"\n"
        self.assertEqual(self.names(base), ["a", "b c"])
        self.assertEqual(self.names(base.replace("\n", "\r\n")), ["a", "b c"])
        self.assertEqual(self.names("\ufeff" + base), ["a", "b c"])
        self.assertEqual(self.names("tests:\n- description: a\n  vars: {output: x}\n- description: 'b'\n"), ["a", "b"])
        self.assertEqual(self.names("tests:\n    -   description:   a   # note\n        vars: {}\n"), ["a"])
        self.assertEqual(self.names("tests:\n  - {description: a, vars: {output: x}}\n  - {description: 'b c'}\n"), ["a", "b c"])
        self.assertEqual(self.names("# tests:\n#  - description: no\ntests: file://tests.csv\n"), [])
        self.assertEqual(self.names("description: x\n"), [])

    def test_only_the_test_list_names_tests(self):
        text = ("description: top\ndefaultTest:\n  options:\n    description: not a test\ntests:\n  - description: real\n"
                "scenarios:\n  - description: other\n")
        self.assertEqual(self.names(text), ["real"])

    def test_a_nested_description_is_not_the_tests_name(self):
        text = "tests:\n  - vars:\n      description: inner\n    description: outer\n"
        self.assertEqual(self.names(text), ["outer"])

    def test_provider_forms(self):
        def providers(text):
            return parse_promptfoo_config(text)["providers"]
        self.assertEqual(providers("providers:\n  - echo\n"), ["echo"])
        self.assertEqual(providers("providers:\n- \"echo\"\n"), ["echo"])
        self.assertEqual(providers("providers: [echo]\n"), ["echo"])
        self.assertEqual(providers("providers: echo\n"), ["echo"])
        self.assertEqual(providers("providers:\n  - id: echo\n    label: x\n"), ["echo"])
        self.assertEqual(providers("providers:\n  - label: x\n    id: echo\n"), ["echo"])
        self.assertEqual(providers("providers:\n  - openai:gpt-4o\n  - id: 'exec: node ./agent-provider.js'\n"),
                         ["openai:gpt-4o", "exec: node ./agent-provider.js"])
        self.assertEqual(providers("prompts: [x]\n"), [])


class ConfigScan(unittest.TestCase):
    BASE = "providers:\n  - echo\ndefaultTest:\n  assert:\n    - type: contains-all\n      metric: C1_x\n      value: [a]\ntests:\n  - description: run-1\n"

    def problems(self, text):
        return [m["message"] for m in scan.scan_config_source(text)]

    def test_the_golden_config_and_a_plain_config_pass(self):
        self.assertEqual(self.problems(read("promptfooconfig.yaml")), [])
        self.assertEqual(self.problems(self.BASE), [])
        self.assertEqual(scan.scan_config_file(PF / "promptfooconfig.yaml"), [])

    def test_model_graded_assertions_are_refused(self):
        for kind in ("llm-rubric", "similar", "model-graded-closedqa", "model-graded-factuality", "factuality",
                     "select-best", "answer-relevance", "context-faithfulness", "context-recall", "context-relevance",
                     "g-eval", "moderation", "classifier", "webhook", "not-llm-rubric", "LLM-Rubric", "llm-future-thing"):
            with self.subTest(kind=kind):
                text = self.BASE + f"    assert:\n      - type: {kind}\n        value: be nice\n"
                problems = self.problems(text)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(kind, problems[0])

    def test_inline_and_quoted_forms(self):
        self.assertEqual(len(self.problems(self.BASE.replace("- type: contains-all", "- {type: llm-rubric, value: x}"))), 1)
        self.assertEqual(len(self.problems(self.BASE.replace("type: contains-all", "type: 'llm-rubric'"))), 1)
        self.assertEqual(len(self.problems(self.BASE.replace("type: contains-all", 'type: "similar"'))), 1)

    def test_rule_assertions_and_schema_types_are_fine(self):
        text = self.BASE + ("      - type: is-json\n        metric: C2_y\n        value:\n          type: object\n"
                            "          required: [a]\n      - type: not-icontains-any\n        value: [x]\n"
                            "      - type: word-count\n        value: {max: 3}\n      - type: starts-with\n        value: Hi\n")
        self.assertEqual(self.problems(text), [])

    def test_only_the_echo_provider_is_allowed(self):
        for provider in ("openai:gpt-4o", "file://provider.js", "exec: node ./agent-provider.js", "anthropic:messages:x",
                         "https://example.com/api"):
            with self.subTest(provider=provider):
                problems = self.problems(f"providers:\n  - '{provider}'\ntests:\n  - description: a\n")
                self.assertEqual(len(problems), 1)
                self.assertIn(provider, problems[0])
                self.assertIn("echo", problems[0])
        self.assertEqual(len(self.problems("providers:\n  - echo\n  - id: openai:gpt-4o\n")), 1)

    def test_a_grading_provider_inside_a_check_is_refused(self):
        text = "providers:\n  - echo\ndefaultTest:\n  assert:\n    - type: contains\n      value: a\n      provider: openai:gpt-4o\n"
        problems = self.problems(text)
        self.assertEqual(len(problems), 1)
        self.assertIn("model would grade", problems[0])

    def test_a_config_with_no_provider_is_flagged(self):
        problems = self.problems("tests:\n  - description: a\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("echo", problems[0])

    def test_every_message_says_what_to_do_next(self):
        for text in (self.BASE + "    assert:\n      - type: llm-rubric\n", "providers:\n  - openai:x\n", "tests: []\n",
                     "providers:\n  - echo\nassert:\n  - provider: x\n"):
            for message in self.problems(text):
                self.assertTrue(message.startswith("promptfooconfig.yaml"), message)
                self.assertRegex(message, r"(?i)ask your AI")
                self.assertTrue(message.rstrip().endswith("."), message)

    def test_bytes_and_a_byte_order_mark_are_accepted(self):
        self.assertEqual(scan.scan_config_source(("\ufeff" + self.BASE).encode("utf-8")), [])
        self.assertEqual(self.problems(self.BASE.replace("\n", "\r\n")), [])


class Environment(unittest.TestCase):
    def test_the_eval_environment_keeps_the_run_off_the_network_and_adds_no_api_setting(self):
        base = {"PATH": "p", "NO_PROXY": "x", "all_proxy": "y", "HTTPS_PROXY": "http://corp:8080", "Keep": "me"}
        env = promptfoo.eval_env(base)
        self.assertEqual(env["npm_config_offline"], "true")
        for key in ("PROMPTFOO_DISABLE_TELEMETRY", "PROMPTFOO_DISABLE_UPDATE", "PROMPTFOO_DISABLE_SHARING"):
            self.assertEqual(env[key], "1")
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self.assertEqual(env[key], "http://127.0.0.1:9")
        self.assertNotIn("NO_PROXY", env)
        self.assertNotIn("all_proxy", env)
        self.assertEqual((env["PATH"], env["Keep"]), ("p", "me"))
        added = set(env) - set(base)
        self.assertFalse([k for k in added if re.search(r"(?i)key|token|secret|permission|approve", k)])
        self.assertEqual(base["HTTPS_PROXY"], "http://corp:8080")  # the caller's environment is not changed

    def test_the_command_is_exactly_the_documented_one(self):
        self.assertEqual(promptfoo.EVAL_ARGS, ["--yes", "promptfoo@0.125.1", "eval", "-c", "promptfooconfig.yaml",
                                               "--no-cache", "--no-table", "--no-write", "-o", "results.json"])
        skill = (helpers.KIT / "skills" / "build-promptfoo-config" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("npx " + " ".join(promptfoo.EVAL_ARGS), skill)


if __name__ == "__main__":
    unittest.main()
