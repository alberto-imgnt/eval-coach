"""The promptfoo track: the app runs the eval and the bundled summary helper itself, then reads the result.

Nothing here talks to a model. The eval uses promptfoo's echo provider, so the only programs run are
npx (for the exact promptfoo version the preflight downloaded) and Python (for the summary helper).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from . import hostos, resources
from .parsers import CheckerOutputError, parse_promptfoo_summary, parse_test_cases
from .preflight import PROMPTFOO_VERSION, SystemRunner

CONFIG_NAME = "promptfooconfig.yaml"
RESULTS_NAME = "results.json"
SUMMARY_SCRIPT = "kit/skills/build-promptfoo-config/summarize_results.py"
EVAL_ARGS = ["--yes", f"promptfoo@{PROMPTFOO_VERSION}", "eval", "-c", CONFIG_NAME,
             "--no-cache", "--no-table", "--no-write", "-o", RESULTS_NAME]
# The first run on a slow disk can take a while; an echo eval itself takes a few seconds.
EVAL_TIMEOUT = 600
SUMMARY_TIMEOUT = 60
RAW_LIMIT = 200_000
TAIL_LINES = 12
# A closed local port: anything that honors the proxy settings (promptfoo does) cannot leave this computer.
DEAD_PROXY = "http://127.0.0.1:9"

REASON_PASS = "All checks for this criterion passed."
_FIXTURE_TESTS = ("fixture-bad", "fixture-polished-but-wrong")
_CACHE_MISS = re.compile(r"ENOTCACHED|ENOTFOUND|offline|EAI_AGAIN|ECONN|E404", re.I)


def eval_env(base_env):
    """The environment for the eval: the CLI environment plus settings that keep it off the network.

    `npm_config_offline` makes npx use the downloaded copy without asking the registry (without it npx still
    contacts the registry, even when the package is cached). The promptfoo variables turn off telemetry, the
    update check and sharing. promptfoo 0.125.1 still posts one anonymous "telemetry disabled" event, so the
    proxy settings point at a closed local port and that post fails on this computer. No permission or API
    setting is added.
    """
    env = dict(base_env if base_env is not None else os.environ)
    for key in [k for k in env if k.lower() in ("no_proxy", "all_proxy")]:
        del env[key]
    env.update({
        "npm_config_offline": "true",
        "PROMPTFOO_DISABLE_TELEMETRY": "1",
        "PROMPTFOO_DISABLE_UPDATE": "1",
        "PROMPTFOO_DISABLE_SHARING": "1",
        "HTTP_PROXY": DEAD_PROXY, "HTTPS_PROXY": DEAD_PROXY,
        "http_proxy": DEAD_PROXY, "https_proxy": DEAD_PROXY,
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
    })
    return env


def _result(ok, exit_code, error, raw, files):
    return {"ok": ok, "exit_code": exit_code, "error": error, "raw": raw, "files": files}


def _tail(text):
    lines = [l.rstrip() for l in re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).splitlines() if l.strip()]
    return "\n".join(lines[-TAIL_LINES:])


def file_for_test(name):
    """The file a test reads, so both tracks give the same RunResult files."""
    m = re.match(r"^run-(\d+)$", name)
    if m:
        return f"runs/run-{int(m.group(1))}.txt"
    if name in _FIXTURE_TESTS:
        return f"fixtures/{name}.txt"
    return name


def run_eval(project, env, npx_argv, runner=None, timeout=EVAL_TIMEOUT):
    """Run the exact eval command in the project folder. Returns (exit_code, raw_output, error or None).

    A non-zero exit code from failed checks is normal. results.json is deleted first, so one that exists
    afterwards was written by this run.
    """
    results = os.path.join(str(project), RESULTS_NAME)
    try:
        if os.path.exists(results):
            os.unlink(results)
    except OSError as exc:
        return -1, "", (f"The old results.json could not be removed ({exc}). Close any program that has it "
                        "open, then try again.")
    if not npx_argv:
        return -1, "", ("The app could not find Node.js, which promptfoo needs. Open the setup page, finish the "
                        "Node.js and promptfoo items, choose Check everything again, then try again.")
    runner = runner or SystemRunner()
    outcome = runner.run(list(npx_argv) + EVAL_ARGS, timeout=timeout, env=eval_env(env), cwd=str(project))
    raw = ((outcome.stdout or "") + ("\n" + outcome.stderr if (outcome.stderr or "").strip() else ""))[:RAW_LIMIT]
    if not getattr(outcome, "started", True):
        return -1, raw, ("promptfoo could not be started: " + (outcome.stderr or "").strip()
                         + " Open the setup page, choose Check everything again, then try again.")
    if outcome.timed_out:
        return -1, raw, (f"promptfoo did not finish within {timeout // 60} minutes, so it was stopped. Press the "
                         "button again. If it keeps happening, ask your AI to look for a test in "
                         "promptfooconfig.yaml that points at a file that does not exist.")
    if not os.path.isfile(results):
        if _CACHE_MISS.search(raw):
            return outcome.code, raw, ("promptfoo is not downloaded on this computer yet. Open the setup page, "
                                       "press Install for promptfoo, then try again.")
        detail = _tail(raw)
        return outcome.code, raw, ("promptfoo stopped before it wrote results.json"
                                   + (f":\n{detail}" if detail else ".")
                                   + "\nAsk your AI to fix the error in promptfooconfig.yaml without changing "
                                     "any threshold, then try again.")
    return outcome.code, raw, None


def summarize(project, prefix, python=None, timeout=SUMMARY_TIMEOUT):
    """Run the bundled summarize_results.py (never the participant's copy) on results.json. Returns (text, error)."""
    results = os.path.join(str(project), RESULTS_NAME)
    if not os.path.isfile(results):
        return "", "results.json was not found, so there is nothing to summarize. Run the eval again."
    script = resources.read_bytes(SUMMARY_SCRIPT)
    argv = [python or sys.executable, "-", RESULTS_NAME] + ([prefix] if prefix else [])
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(argv, input=script, cwd=str(project), capture_output=True, timeout=timeout,
                              env=env, **hostos.popen_flags(new_group=False))
    except subprocess.TimeoutExpired:
        return "", "The summary did not finish within a minute. Run the eval again."
    except OSError as exc:
        return "", f"The summary could not be started: {exc}"
    out = proc.stdout.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        stderr = [l.strip() for l in proc.stderr.decode("utf-8", errors="replace").splitlines() if l.strip()]
        detail = stderr[-1] if stderr else ""
        return out, ("The summary of results.json stopped with an error"
                     + (f": {detail}" if detail else ".") + "\nRun the eval again.")
    return out, None


def read_reasons(project):
    """{test name: {metric: reason}} from results.json: the first failing check's reason, or a pass note."""
    path = os.path.join(str(project), RESULTS_NAME)
    with open(path, "rb") as f:
        data = json.loads(f.read().decode("utf-8-sig"))
    rows = data["results"]["results"]
    out = {}
    for row in sorted(rows, key=lambda r: r.get("testIdx", 0)):
        name = (row.get("testCase") or {}).get("description") or f"test-{row.get('testIdx', '?')}"
        per_metric = {}
        for comp in (row.get("gradingResult") or {}).get("componentResults", []):
            metric = (comp.get("assertion") or {}).get("metric") or "(no metric)"
            reason = " ".join(str(comp.get("reason", "")).split())[:240]
            entry = per_metric.setdefault(metric, {"fail": None, "nc": None})
            if reason.startswith("NOT CHECKED"):
                entry["nc"] = entry["nc"] or reason
            elif not comp.get("pass") and entry["fail"] is None:
                entry["fail"] = reason or "The check failed."
        out[name] = per_metric
    return out


def _nc_reason(reason):
    text = re.sub(r"^NOT CHECKED\s*[:\-]?\s*", "", reason).strip()
    return text or "needs judgment"


def _add_reasons(files, reasons):
    for entry in files:
        per_metric = reasons.get(entry["file"], {})
        by_id = {}
        for metric, info in per_metric.items():
            m = re.match(r"^C(\d+)", metric, re.I)
            if m:
                by_id[f"C{int(m.group(1))}"] = info
        for row in entry["rows"]:
            info = by_id.get(row["id"], {"fail": None, "nc": None})
            if row["verdict"] == "NC":
                row["reason"] = _nc_reason(info["nc"] or "")
            elif row["verdict"] == "F":
                row["reason"] = info["fail"] or "The check failed."
            else:
                row["reason"] = REASON_PASS


def criterion_names(project):
    """{"C1": name} from test-cases.md when it can be read."""
    try:
        with open(os.path.join(str(project), "test-cases.md"), "rb") as f:
            text = f.read().decode("utf-8-sig", errors="replace")
    except OSError:
        return {}
    return {c["id"]: c["name"] for c in parse_test_cases(text) if c.get("name")}


def run_selection(project, prefix, expect, env, npx_argv, runner=None, python=None):
    """Run the eval, summarize the tests whose names start with prefix, and return a RunResult.

    `expect` lists the files the result must report on (for example runs/run-1.txt). The files in the result
    are the ones the tests read, so the rest of the app treats this like a checker run on those files.
    """
    code, raw, error = run_eval(project, env, npx_argv, runner)
    if error:
        return _result(False, code, error, raw, [])
    text, error = summarize(project, prefix, python)
    if error:
        return _result(False, code, error, raw, [])
    try:
        files = parse_promptfoo_summary(text, criterion_names(project))
    except CheckerOutputError as exc:
        return _result(False, code, f"The app could not read the summary of the results: {exc}", raw, [])
    try:
        _add_reasons(files, read_reasons(project))
    except (OSError, ValueError, KeyError, TypeError):
        return _result(False, code, "The app could not read results.json. Run the eval again.", raw, [])
    for entry in files:
        entry["file"] = file_for_test(entry["file"])
    reported = {e["file"].replace("\\", "/").rsplit("/", 1)[-1].lower() for e in files}
    missing = [f for f in expect if f.replace("\\", "/").rsplit("/", 1)[-1].lower() not in reported]
    if missing:
        return _result(False, code, "promptfoo did not report on: " + ", ".join(missing)
                       + ". Check that each of those has a test with the right name in promptfooconfig.yaml.",
                       raw, files)
    return _result(True, code, None, raw, files)
