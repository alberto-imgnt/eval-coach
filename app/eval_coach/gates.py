"""File-based "Check my work" verification. Decisions come from files and checker runs only."""
from __future__ import annotations

import fnmatch
import hashlib

from . import project as proj
from . import resources, scan
from .parsers import IterationLogError, parse_iteration_log, parse_promptfoo_config
from .runner import find_file

RUNS = 5
BAD_FILE, POLISHED_FILE = proj.FIXTURE_NAMES
VERDICTS = ("P", "F", "NC")
CLASSES = ("vague", "reads_differently", "predicted_wrong")


def read_text(path):
    try:
        with open(str(path), "rb") as f:
            return f.read().decode("utf-8-sig", errors="replace")
    except OSError:
        return ""


def has_text(path):
    return bool(read_text(path).strip())


def file_sha256(path):
    try:
        with open(str(path), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def is_complete_run(result):
    return bool(result and result.get("ok"))


def rows_of(result, name):
    section = find_file(result, name)
    return section["rows"] if section else []


def polished_fails(result):
    return any(r["verdict"] == "F" for r in rows_of(result, POLISHED_FILE))


def polished_passed_all(result):
    """NOT CHECKED rows do not count, as in the fixtures skill."""
    rows = rows_of(result, POLISHED_FILE)
    return any(r["verdict"] == "P" for r in rows) and not any(r["verdict"] == "F" for r in rows)


def bad_fails_majority(result):
    rows = [r for r in rows_of(result, BAD_FILE) if r["verdict"] in ("P", "F")]
    fails = sum(1 for r in rows if r["verdict"] == "F")
    return bool(rows) and fails * 2 > len(rows)


def compute_grid(criteria, bad_predict, polished_predict, result):
    """One row per criterion, comparing the locked prediction with the actual verdict."""
    if not is_complete_run(result):
        return []
    bad = {r["id"]: r for r in rows_of(result, BAD_FILE)}
    polished = {r["id"]: r for r in rows_of(result, POLISHED_FILE)}
    rows = [dict(c) for c in criteria]
    known = {c["id"] for c in criteria}
    for extra in list(bad.values()) + list(polished.values()):
        if extra["id"] not in known:
            known.add(extra["id"])
            rows.append({"id": extra["id"], "name": extra["name"]})
    grid = []
    for row in rows:
        cid = row["id"]
        bad_actual = bad[cid]["verdict"] if cid in bad else None
        polished_actual = polished[cid]["verdict"] if cid in polished else None
        bad_guess, polished_guess = bad_predict.get(cid), polished_predict.get(cid)
        grid.append({
            "id": cid,
            "name": row["name"],
            "bad_predict": bad_guess,
            "bad_actual": bad_actual,
            "polished_predict": polished_guess,
            "polished_actual": polished_actual,
            "bad_surprise": bool(bad_guess and bad_actual and bad_guess != bad_actual),
            "polished_surprise": bool(polished_guess and polished_actual and polished_guess != polished_actual),
        })
    return grid


def surprise_keys(grid):
    keys = []
    for row in grid:
        if row["bad_surprise"]:
            keys.append(f"{row['id']}:bad")
        if row["polished_surprise"]:
            keys.append(f"{row['id']}:polished")
    return keys


def scan_messages(paths, track="script"):
    target = paths.checker(track)
    if not target.is_file():
        return []
    return scan.scan_config_file(target) if track == "promptfoo" else scan.scan_file(target)


def _missing_checker(track):
    return "promptfooconfig.yaml was not found." if track == "promptfoo" else "check.py was not found."


class Report:
    def __init__(self, messages):
        self.messages = messages
        self.items = []
        self.nudges = []

    def add(self, key, ok, **fmt):
        entry = self.messages[key]
        text = entry.get("ok", "") if ok else entry["fail"]
        self.items.append({"label": entry["label"].format(**fmt), "ok": bool(ok),
                           "detail": text.format(**fmt)})

    def result(self):
        return {"ok": all(i["ok"] for i in self.items), "items": self.items, "nudges": self.nudges}


def check_generate(paths, step, report):
    count = sum(1 for n in range(1, RUNS + 1) if has_text(paths.run_file(n)))
    report.add("runs", count == RUNS, count=count)
    report.add("model", bool(step["model_name"].strip()))
    return report.result()


def check_build(paths, step, checklist_ids, first_look, report, track="script"):
    exists = paths.checker(track).is_file()
    report.add("checker", exists)
    problems = scan_messages(paths, track)
    report.add("scan", exists and not problems,
               messages=" ".join(p["message"] for p in problems) or _missing_checker(track))
    ticked = step["checklist"]
    for item_id in checklist_ids:
        report.add(item_id, ticked.get(item_id) is True)
    report.add("first_look", is_complete_run(first_look))
    return report.result()


def check_fixtures(paths, report):
    report.add("bad", has_text(paths.work_fixtures / BAD_FILE))
    report.add("polished", has_text(paths.work_fixtures / POLISHED_FILE))
    report.add("no_key_in_project", not paths.project_key.exists())
    return report.result()


FIXTURE_TESTS = tuple(name[:-4] for name in proj.FIXTURE_NAMES)


def config_test_names(paths):
    if not paths.config_yaml.is_file():
        return []
    return parse_promptfoo_config(read_text(paths.config_yaml))["test_names"]


def check_fixtures_config(paths, report):
    """promptfoo track: both fixtures are tests in the config, the five runs are still there, and no key exists."""
    exists = paths.config_yaml.is_file()
    names = config_test_names(paths)
    missing = [n for n in FIXTURE_TESTS if n not in names]
    report.add("config", exists)
    report.add("tests", exists and not missing, missing=", ".join(missing))
    lost = [f"run-{n}" for n in range(1, RUNS + 1) if f"run-{n}" not in names]
    report.add("runs_kept", exists and not lost, missing=", ".join(lost))
    problems = scan_messages(paths, "promptfoo")
    report.add("scan", exists and not problems,
               messages=" ".join(p["message"] for p in problems) or _missing_checker("promptfoo"))
    report.add("no_key_in_project", not paths.project_key.exists())
    return report.result()


def live_scan_messages(paths, allowed_clis=()):
    if not paths.live_config.is_file():
        return []
    return scan.scan_live_config_file(paths.live_config, allowed_clis)


def provider_is_bundled(paths):
    """agent-provider.js in the project is exactly the copy that came with the course."""
    mine = file_sha256(paths.agent_provider)
    return mine is not None and mine == hashlib.sha256(resources.read_bytes(proj.AGENT_PROVIDER)).hexdigest()


def live_start_hashes(paths):
    """The files live mode must leave alone, noted when the participant starts the step. None means no such file."""
    return {"config": file_sha256(paths.config_yaml), "log": file_sha256(paths.iteration_log)}


def check_live(paths, step, allowed_clis, report):
    """Optional live mode, promptfoo track. File-based only: the app never runs the live config."""
    report.add("acknowledged", step["acknowledged"] is True)
    exists = paths.live_config.is_file()
    report.add("config", exists)
    problems = live_scan_messages(paths, allowed_clis)
    report.add("scan", exists and not problems,
               messages=" ".join(p["message"] for p in problems)
               or "promptfooconfig.live.yaml was not found. Press Start my AI, then Send to AI, so your AI writes it.")
    report.add("provider", provider_is_bundled(paths))
    start = step["start_hashes"]
    report.add("started", start is not None)
    report.add("main_unchanged", start is not None and file_sha256(paths.config_yaml) == start["config"])
    report.add("log_unchanged", start is not None and file_sha256(paths.iteration_log) == start["log"])
    return report.result()


def check_key(paths, report):
    report.add("key", has_text(paths.key_work_key))
    unchanged = all(
        file_sha256(paths.key_work_fixtures / name) is not None
        and file_sha256(paths.key_work_fixtures / name) == file_sha256(paths.fixtures / name)
        for name in proj.FIXTURE_NAMES)
    report.add("fixtures_unchanged", unchanged)
    report.add("no_key_in_project", not paths.project_key.exists())
    return report.result()


def _has_examples(paths):
    if not paths.examples.is_dir():
        return False
    return any(fnmatch.fnmatch(p.name.lower(), "c*-pass.txt") for p in paths.examples.iterdir() if p.is_file())


def check_readback(paths, step, criteria, report):
    report.add("examples", _has_examples(paths))
    answers = step["answers"]
    missing = [c["id"] for c in criteria if answers.get(c["id"]) not in ("yes", "no")]
    report.add("answers", not missing, missing=", ".join(missing))
    return report.result()


def predict_missing(criteria, step):
    return [c["id"] for c in criteria
            if step["bad"].get(c["id"]) not in VERDICTS or step["polished"].get(c["id"]) not in VERDICTS]


def predict_answers_missing(step):
    return [k for k in ("wrong", "catches", "worst_guess") if not step["answers"].get(k, "").strip()]


def check_predict(step, criteria, report):
    missing = predict_missing(criteria, step)
    report.add("cells", bool(criteria) and not missing, missing=", ".join(missing) or "add your criteria")
    report.add("answers", not predict_answers_missing(step))
    report.add("locked", step["locked"] is True)
    return report.result()


def check_run(step, grid, result, report):
    report.add("ran", is_complete_run(result))
    keys = surprise_keys(grid)
    missing = [k for k in keys if step["classifications"].get(k) not in CLASSES]
    report.add("classified", is_complete_run(result) and not missing, missing=", ".join(missing))
    return report.result()


def check_fix(paths, step, facts, report, track="script"):
    report.add("spec_changed", facts["test_cases_changed"])
    report.add("checker_changed", facts["checker_changed_after"])
    problems = scan_messages(paths, track)
    report.add("scan", paths.checker(track).is_file() and not problems,
               messages=" ".join(p["message"] for p in problems) or _missing_checker(track))
    report.add("rerun", facts["rerun_fresh"])
    report.add("bad_fails", bad_fails_majority(facts["rerun"]))
    report.add("polished", polished_fails(facts["rerun"]) or bool(step["explanation"].strip()))
    if facts["checker_edited_only"]:
        report.nudges.append(report.messages["nudge_check_only"]["text"])
    return report.result()


def _fraction(passes, total):
    return f"{passes} of {total}"


def baseline_log_entry(paths, problems):
    """(entry, problem): the log's single Iteration 0 entry, or the plain reason there is none."""
    if not paths.iteration_log.is_file():
        return None, None
    try:
        entries = parse_iteration_log(read_text(paths.iteration_log))
    except IterationLogError as exc:
        return None, problems["unusable"].format(error=str(exc))
    zero = [e for e in entries if e["number"] == 0]
    if not zero:
        return None, problems["no_entry"]
    if len(zero) > 1:
        return None, problems["two_entries"]
    return zero[0], None


def baseline_count_problems(entry, summary, problems):
    out = []
    rows = {r["id"]: r for r in entry["rows"]}
    for c in summary["criteria"]:
        if c["not_checked"]:
            continue
        row = rows.get(c["id"])
        app = _fraction(c["passes"], c["checked_runs"])
        if row is None:
            out.append(problems["no_row"].format(id=c["id"], app=app))
        elif row["not_checked"]:
            out.append(problems["row_not_checked"].format(id=c["id"], app=app))
        elif row["passes"] is None:
            out.append(problems["row_no_count"].format(id=c["id"], app=app))
        elif (row["passes"], row["checked"]) != (c["passes"], c["checked_runs"]):
            out.append(problems["count"].format(id=c["id"], log=_fraction(row["passes"], row["checked"]), app=app))
    overall = summary["overall"]
    app_total = f"{overall['passes']} / {overall['total']}"
    if entry["overall"] is None:
        out.append(problems["no_overall"].format(app=app_total))
    elif tuple(entry["overall"]) != (overall["passes"], overall["total"]):
        out.append(problems["overall"].format(log=f"{entry['overall'][0]} / {entry['overall'][1]}", app=app_total))
    return out


def baseline_not_checked_problems(entry, summary, problems):
    out = []
    app_nc = set(summary["not_checked"])
    log_nc = set(entry["not_checked_ids"])
    by_id = {c["id"]: c for c in summary["criteria"]}
    rows = {r["id"]: r for r in entry["rows"]}
    for cid in sorted(app_nc - log_nc, key=lambda c: int(c[1:])):
        out.append(problems["nc_missing"].format(id=cid))
    for cid in sorted(log_nc - app_nc, key=lambda c: int(c[1:])):
        c = by_id.get(cid)
        if c is None:
            out.append(problems["nc_unknown"].format(id=cid))
        else:
            out.append(problems["nc_extra"].format(id=cid, app=_fraction(c["passes"], c["checked_runs"])))
    for cid in sorted(app_nc, key=lambda c: int(c[1:])):
        row = rows.get(cid)
        if row is not None and not row["not_checked"] and row["passes"] is not None:
            out.append(problems["nc_row_has_count"].format(id=cid, log=_fraction(row["passes"], row["checked"])))
    count = entry["not_checked_count"]
    if count is not None and entry["not_checked_ids"] and count != len(entry["not_checked_ids"]):
        out.append(problems["nc_count"].format(count=count, listed=len(entry["not_checked_ids"])))
    return out


def check_baseline(paths, facts, report):
    """facts: {"summary": per-criterion results or None, "fresh": the run matches the current files}."""
    problems = report.messages["problems"]
    report.add("log", paths.iteration_log.is_file())
    entry, problem = baseline_log_entry(paths, problems)
    report.add("entry", entry is not None, problem=problem or problems["no_log"])
    summary = facts["summary"] if facts["fresh"] else None
    report.add("ran", summary is not None, problem=problems["stale" if facts["summary"] else "not_run"])
    if entry is None or summary is None:
        why = problems["wait_entry"] if entry is None else problems["wait_run"]
        report.add("counts", False, problem=why)
        report.add("not_checked", False, problem=why)
        report.add("runs", False, problem=why)
        return report.result()
    counts = baseline_count_problems(entry, summary, problems)
    report.add("counts", not counts, problem=" ".join(counts))
    not_checked = baseline_not_checked_problems(entry, summary, problems)
    report.add("not_checked", not not_checked, problem=" ".join(not_checked))
    if entry["runs"] is None:
        runs_problem = problems["no_runs"]
    elif entry["runs"] != summary["runs"]:
        runs_problem = problems["runs"].format(log=entry["runs"], app=summary["runs"])
    else:
        runs_problem = ""
    report.add("runs", not runs_problem, problem=runs_problem)
    if not entry["model"] or not entry["prompt"]:
        report.nudges.append(report.messages["nudge_log_fields"]["text"])
    return report.result()
