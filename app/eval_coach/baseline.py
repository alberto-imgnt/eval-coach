"""The app's own baseline run on the five saved runs, and the per-criterion results.

`run_checks` is the one entry point the engine calls. It picks the runner for the track and
returns the same RunResult shape `runner.run_checker` returns, so a track's own runner can be
registered in RUNNERS without changing the engine or the gate.
"""
from __future__ import annotations

import hashlib

from . import runner

RUNS = 5


def run_names():
    return [f"runs/run-{n}.txt" for n in range(1, RUNS + 1)]


def _run_script(project, env=None, **_options):
    """Script track: one `check.py runs/run-1.txt ... runs/run-5.txt` call."""
    return runner.run_checker(project, run_names(), env=env)


def _run_promptfoo(project, env=None, npx_argv=None, runner=None, python=None, **_options):
    """promptfoo track: one eval of the whole config, then the summary of the run-N tests."""
    from . import promptfoo
    return promptfoo.run_selection(project, "run-", run_names(), env, npx_argv, runner, python)


# track -> function(project, env, **options) -> RunResult. The options are the track's own (the promptfoo runner
# takes npx_argv, runner and python). A track without an entry uses the Script runner.
RUNNERS = {"script": _run_script, "promptfoo": _run_promptfoo}


def run_checks(project, track="script", env=None, **options):
    """Run the checker on all five runs. Exit codes 0 and 1 are normal, as everywhere."""
    result = RUNNERS.get(track, RUNNERS["script"])(project, env, **options)
    if result["ok"]:
        problem = _consistency_problem(result)
        if problem:
            return dict(result, ok=False, error=problem)
    return result


def _basename(path):
    return path.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _sections(result):
    """The five run sections in run order, or None if one is missing."""
    by_name = {_basename(f["file"]): f for f in result.get("files", [])}
    sections = [by_name.get(f"run-{n}.txt") for n in range(1, RUNS + 1)]
    return None if any(s is None for s in sections) else sections


def _consistency_problem(result):
    sections = _sections(result)
    if sections is None:
        return "The checker did not report on all five runs."
    first = [r["id"] for r in sections[0]["rows"]]
    for n, section in enumerate(sections[1:], start=2):
        ids = [r["id"] for r in section["rows"]]
        if ids != first:
            return (f"The checker reported different criteria for run-{n}.txt than for run-1.txt, "
                    "so the five runs cannot be compared. Ask your CLI to fix check.py without "
                    "changing any threshold, then run it again.")
    return None


def summarize(result):
    """Per-criterion results from a good RunResult, or None.

    {"runs": 5, "criteria": [{"id", "name", "passes", "checked_runs", "not_checked",
    "failing_runs", "rate"}], "overall": {"passes", "total"}, "not_checked": [ids]}.
    A criterion is not checked when every run says NOT CHECKED. `total` counts checked results.
    """
    if not result or not result.get("ok"):
        return None
    sections = _sections(result)
    if sections is None or _consistency_problem(result):
        return None
    criteria, passes_all, total_all = [], 0, 0
    for index, row in enumerate(sections[0]["rows"]):
        verdicts = [s["rows"][index]["verdict"] for s in sections]
        checked = [v for v in verdicts if v in ("P", "F")]
        passes = sum(1 for v in verdicts if v == "P")
        not_checked = not checked
        criteria.append({
            "id": row["id"],
            "name": row["name"],
            "passes": passes,
            "checked_runs": len(checked),
            "not_checked": not_checked,
            "failing_runs": [n for n, v in enumerate(verdicts, start=1) if v == "F"],
            "rate": None if not_checked else int(passes * 100 / len(checked) + 0.5),
        })
        passes_all += passes
        total_all += len(checked)
    return {
        "runs": RUNS,
        "criteria": criteria,
        "overall": {"passes": passes_all, "total": total_all},
        "not_checked": [c["id"] for c in criteria if c["not_checked"]],
    }


def runs_hash(paths):
    """One hash over the five run files, so a changed or replaced run shows up."""
    digest = hashlib.sha256()
    for n in range(1, RUNS + 1):
        try:
            data = paths.run_file(n).read_bytes()
        except OSError:
            data = b""
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()
