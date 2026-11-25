"""Test doubles for the promptfoo track: a config builder and a runner that stands in for npx and promptfoo.

The fake "promptfoo" reads the project's promptfooconfig.yaml for its test names, scores each test's file with the
Northwind reference checker (the same rules the Script track tests use), and writes a results.json in promptfoo's
real shape, so the app's own parsing and summary code run on it unchanged.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import helpers
from helpers import GOLDEN

from eval_coach.parsers import parse_promptfoo_config
from eval_coach.preflight import Result

_spec = importlib.util.spec_from_file_location("reference_check", str(GOLDEN / "reference-check.py"))
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)

NC_STUB = "\"({ pass: false, score: 0, reason: 'NOT CHECKED: needs judgment' })\""


def metric_of(cid, name):
    return f"{cid}_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}"


def pf_config(tests, nc=(), extra="", tightened=False, provider="echo"):
    """A promptfooconfig.yaml shaped like the build skill's. `tests` are test names; nc are criterion ids left NOT CHECKED."""
    lines = ["description: Northwind end-of-week update checks", "prompts:", '  - "{{output}}"', "providers:",
             f"  - {provider}", "defaultTest:", "  assert:"]
    for cid, name, _fn in reference.CRITERIA:
        lines.append(f"    # {cid}: {name}")
        if cid in nc:
            lines += ["    - type: javascript", f"      metric: {metric_of(cid, name)}", f"      value: {NC_STUB}"]
        else:
            lines += ["    - type: javascript", f"      metric: {metric_of(cid, name)}", "      value: output.length > 0"]
    if tightened:
        lines.append("    # C3 tightened: the text after Blocker: mentions test data")
    if extra:
        lines.append(extra)
    lines.append("tests:")
    for name in tests:
        lines += [f"  - description: {name}", "    vars:", f"      output: file://{file_for(name)}"]
    return "\n".join(lines) + "\n"


def file_for(name):
    m = re.match(r"^run-(\d+)$", name)
    if m:
        return f"runs/run-{m.group(1)}.txt"
    if name.startswith("fixture-"):
        return f"fixtures/{name}.txt"
    if name == "known-good":
        return "known-good.txt"
    return f"examples/{name}.txt"


RUN_TESTS = [f"run-{n}" for n in range(1, 6)]
FIXTURE_TESTS = ["fixture-bad", "fixture-polished-but-wrong"]


def _criterion(cid, name, fn, text, tightened):
    if cid == "C3" and tightened:
        after = text.split("Blocker:", 1)[1].splitlines()[0] if "Blocker:" in text else ""
        if "Blocker:" in text and "Need:" in text and "test data" not in after:
            return False, "blocker does not mention test data"
    return fn(text)


def build_results(project, config_text):
    """The results.json promptfoo would write for this config, as a dict."""
    parsed = parse_promptfoo_config(config_text)
    nc = set(re.findall(r"metric:\s*(C\d+)_[^\n]*\n\s*value:[^\n]*NOT CHECKED", config_text))
    tightened = "tightened" in config_text
    rows = []
    for idx, name in enumerate(parsed["test_names"]):
        path = Path(project) / file_for(name)
        text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        comps = []
        for cid, cname, fn in reference.CRITERIA:
            metric = metric_of(cid, cname)
            if cid in nc:
                ok, reason = False, "NOT CHECKED: needs judgment"
            else:
                ok, reason = _criterion(cid, cname, fn, text, tightened)
                reason = "Assertion passed" if ok else reason
            comps.append({"pass": bool(ok), "score": 1 if ok else 0, "reason": reason,
                          "assertion": {"type": "javascript", "metric": metric}})
        comps.append({"pass": bool(text.strip()), "score": 1, "reason": "Assertion passed",
                      "assertion": {"type": "javascript", "metric": "non_empty"}})
        rows.append({"testIdx": idx, "testCase": {"description": name}, "success": all(c["pass"] for c in comps),
                     "gradingResult": {"pass": all(c["pass"] for c in comps), "componentResults": comps}})
    return {"evalId": "eval-fake", "results": {"version": 3, "results": rows, "stats": {}}}


class FakePromptfoo:
    """Stands in for the preflight runner: finds a fake npx and "runs" promptfoo."""

    def __init__(self):
        self.calls = []
        self.mode = "normal"  # normal | no_results | timeout | cache_miss | bad_json | not_started

    def which(self, name, path):
        return r"C:\fake\npx.exe" if name == "npx" else None

    def disk_free(self, path):
        return 10**12

    def run(self, argv, timeout, env=None, cwd=None, on_tick=None, cancel=None):
        out = argv[argv.index("-o") + 1] if "-o" in argv else "results.json"
        self.calls.append({"argv": list(argv), "timeout": timeout, "env": dict(env or {}), "cwd": cwd,
                           "results_existed": (Path(cwd) / out).exists()})
        if self.mode == "not_started":
            return Result(code=-1, stderr="access denied", started=False)
        if self.mode == "timeout":
            return Result(code=-1, timed_out=True)
        if self.mode == "cache_miss":
            return Result(code=1, stderr="npm error code ENOTCACHED\nnpm error request to registry failed: cache mode is 'only-if-cached'")
        if self.mode == "no_results":
            return Result(code=1, stderr="Error: Invalid config\n  tests[0] is not valid\n")
        config = (Path(cwd) / "promptfooconfig.yaml").read_text(encoding="utf-8-sig")
        if self.mode == "bad_json":
            (Path(cwd) / out).write_text("{not json", encoding="utf-8")
            return Result(code=100, stdout="Writing output to results.json\n")
        data = build_results(cwd, config)
        (Path(cwd) / out).write_text(json.dumps(data), encoding="utf-8")
        failed = any(not r["success"] for r in data["results"]["results"])
        return Result(code=100 if failed else 0, stdout="Results:\n  0 errors (0%)\nWriting output to results.json\n")
