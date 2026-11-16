"""Runs the real, pinned promptfoo 0.125.1 from the Phase 0 spike's private Node and npm cache, with no network.

Skipped when that runtime is not on this machine. It is the check that the app's exact command, environment and
summary parsing work on promptfoo's real output, not only on the stand-in.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import GOLDEN, ROOT

from eval_coach import promptfoo
from eval_coach.parsers import parse_promptfoo_summary

SPIKE = ROOT / "spikes" / "phase0-preflight"
NODE = SPIKE / "runtime" / "node-v26.13.0-win-x64"
CACHE = SPIKE / "npm-cache"
NPX_CLI = NODE / "node_modules" / "npm" / "bin" / "npx-cli.js"
READY = (NODE / "node.exe").is_file() and NPX_CLI.is_file() and (CACHE / "_cacache").is_dir()


@unittest.skipUnless(READY, "the spike's private Node and promptfoo cache are not on this machine")
class RealPromptfoo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-realpf-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.project = self.tmp / "promptfoo"
        self.project.mkdir()
        shutil.copy(str(GOLDEN / "promptfoo" / "promptfooconfig.yaml"), str(self.project / "promptfooconfig.yaml"))
        shutil.copytree(str(GOLDEN / "northwind"), str(self.tmp / "northwind"))
        env = dict(os.environ)
        env["PATH"] = str(NODE) + os.pathsep + env.get("PATH", "")
        env["npm_config_cache"] = str(CACHE)
        env["PROMPTFOO_CONFIG_DIR"] = str(self.tmp / "pfconfig")
        self.env = env
        self.npx = [str(NODE / "node.exe"), str(NPX_CLI)]

    def golden(self, name):
        return parse_promptfoo_summary((GOLDEN / "promptfoo" / name).read_text(encoding="utf-8"))

    def test_the_fixtures_and_the_runs_come_back_in_the_shape_the_script_track_gives(self):
        (self.project / "results.json").write_text("{\"stale\": true}", encoding="utf-8")
        files = ["fixtures/fixture-bad.txt", "fixtures/fixture-polished-but-wrong.txt"]
        result = promptfoo.run_selection(self.project, "fixture-", files, self.env, self.npx)
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(result["exit_code"], 100)  # failed checks are normal
        self.assertEqual([f["file"] for f in result["files"]], files)
        golden = {f["file"]: [(r["id"], r["verdict"]) for r in f["rows"]] for f in self.golden("summary-fixture.txt")}
        for entry in result["files"]:
            name = Path(entry["file"]).stem
            self.assertEqual([(r["id"], r["verdict"]) for r in entry["rows"]], golden[name])
            self.assertTrue(all(r["reason"] for r in entry["rows"]))
        bad = {r["id"]: r for r in result["files"][0]["rows"]}
        self.assertEqual(bad["C1"]["reason"], "Word count 154 is greater than maximum 149")
        self.assertEqual(bad["C4"]["verdict"], "NC")

    def test_the_first_look_reads_only_run_1_and_the_baseline_only_the_runs(self):
        first = promptfoo.run_selection(self.project, "run-1", ["runs/run-1.txt"], self.env, self.npx)
        self.assertTrue(first["ok"], first["error"])
        self.assertEqual([f["file"] for f in first["files"]], ["runs/run-1.txt"])
        from eval_coach import baseline
        runs = baseline.run_checks(self.project, "promptfoo", env=self.env, npx_argv=self.npx)
        self.assertTrue(runs["ok"], runs["error"])
        summary = baseline.summarize(runs)
        self.assertEqual([(c["id"], c["passes"], c["checked_runs"], c["not_checked"]) for c in summary["criteria"]],
                         [("C1", 4, 5, False), ("C2", 4, 5, False), ("C3", 4, 5, False), ("C4", 0, 0, True)])
        self.assertEqual(summary["overall"], {"passes": 12, "total": 15})

    def test_a_broken_config_is_a_plain_error_with_no_stale_results(self):
        (self.project / "results.json").write_text("{\"stale\": true}", encoding="utf-8")
        (self.project / "promptfooconfig.yaml").write_text("tests: [this is: not valid: yaml\n", encoding="utf-8")
        result = promptfoo.run_selection(self.project, "run-", ["runs/run-1.txt"], self.env, self.npx)
        self.assertFalse(result["ok"])
        self.assertIn("promptfooconfig.yaml", result["error"])
        self.assertFalse((self.project / "results.json").exists())


if __name__ == "__main__":
    unittest.main()
