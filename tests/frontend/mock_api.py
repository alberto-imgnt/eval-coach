"""Mock eval-coach backend for UI tests. Dev-only, standard library only.

Implements the HTTP contract in docs/SPEC.md with canned states for every step
and a fake terminal stream. Extra routes under /__mock/ let tests set scenarios,
push SSE events and read what the page sent.

Usage: python mock_api.py [--port 38917] [--token dev-token]
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import mock_course
from mock_course import CourseState, MockError

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "app" / "eval_coach"
# MOCK_WEB_ROOT serves another copy of the web files, for comparing the interface before and after a change.
WEB_ROOT = Path(os.environ.get("MOCK_WEB_ROOT") or PACKAGE_ROOT / "web")
CONTENT_ROOT = PACKAGE_ROOT / "content"
PREFLIGHT_TEXT = json.loads((CONTENT_ROOT / "preflight.json").read_text(encoding="utf-8"))
SETTINGS_FULL = json.loads((CONTENT_ROOT / "settings.json").read_text(encoding="utf-8"))
SETTINGS_TEXT = {k: v for k, v in SETTINGS_FULL.items() if k != "errors"}
SERIES = json.loads((CONTENT_ROOT / "series.json").read_text(encoding="utf-8"))
# Part 1 is a real Part with its own course; the mock only needs its row on the Series map (its screens are
# tested against the real engine in part1.spec.js).
PART1_LESSONS = json.loads((CONTENT_ROOT / "part-1-lessons.json").read_text(encoding="utf-8"))["lessons"]
PART1_ITEMS = 9
# Part 2 is the same: only its row on the Series map is mocked (its screens run against the real engine in part2.spec.js).
PART2_LESSONS = json.loads((CONTENT_ROOT / "part-2-lessons.json").read_text(encoding="utf-8"))["lessons"]
PART2_ITEMS = 8
BACKUP_FOLDER = "C:\\Users\\tester\\.eval-coach\\reset-backup"
CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
MAX_BODY = 2 * 1024 * 1024

SCRIPT_ORDER = ["generate", "build", "fixtures", "readback", "predict", "key", "run", "fix", "baseline"]
PF_ORDER = ["generate", "build", "fixtures", "fixtures-config", "readback", "predict", "key", "run", "fix", "baseline"]
STEP_ORDER = list(SCRIPT_ORDER)  # changed in place when a scenario or the preflight picks the promptfoo track
TRACK = {"name": "script"}
mock_course.ACTIVE_STEPS = STEP_ORDER  # the course list shows the steps of the current track
STEPS_CONTENT = json.loads((CONTENT_ROOT / "steps.json").read_text(encoding="utf-8"))["steps"]
LIVE_TEXT = STEPS_CONTENT["live"]
LIVE_LINE = LIVE_TEXT["line_template"]
TITLES = {
    "generate": "Collect your answers",
    "build": "Build the checker",
    "fixtures": "Make the fixtures",
    "fixtures-config": "Add the fixtures to the config",
    "readback": "Read back the checks",
    "predict": "Predict the results",
    "key": "Write the answer key",
    "run": "Run and compare",
    "fix": "Fix the spec",
    "baseline": "Log your baseline",
}
PF_TITLES = {"build": "Build the config"}


def title_of(step_id):
    return PF_TITLES.get(step_id, TITLES[step_id]) if TRACK["name"] == "promptfoo" else TITLES[step_id]


def set_track(track):
    TRACK["name"] = track
    STEP_ORDER[:] = PF_ORDER if track == "promptfoo" else SCRIPT_ORDER


def resolved_text(step_id):
    """The real step content for the current track, merged like the engine does."""
    base = STEPS_CONTENT[step_id]
    override = base.get("tracks", {}).get("promptfoo") if TRACK["name"] == "promptfoo" else None
    if not override:
        return base

    def merge(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            return {**a, **{k: merge(a.get(k), v) for k, v in b.items()}}
        return b

    return {**base, **{k: merge(base.get(k), v) for k, v in override.items()}}
CRITERIA = [
    {"id": "C1", "name": "Length under 150 words"},
    {"id": "C2", "name": "Mentions the order number"},
    {"id": "C3", "name": "Tone is professional"},
    {"id": "C4", "name": "Offers a next step"},
]
LINES = {
    "generate": "Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.",
    "build": "Read skills/build-eval-script/SKILL.md and follow it in build mode on test-cases.md.",
    "fixtures": "Read skills/make-eval-fixtures/SKILL.md and follow it for test-cases.md and prompt-v0.md, with one change: write only the two fixture files. Do not write the answer key, and do not say what is wrong with either fixture.",
    "key": "Read skills/make-eval-fixtures/SKILL.md. The two fixture files are already in fixtures/. Do not change them. Follow only the Answer key section, using test-cases.md, and write fixtures/answer-key.md. Do nothing else.",
    "readback": "Read skills/build-eval-script/SKILL.md and follow it in explain mode on test-cases.md and check.py.",
    "fix": "I changed test-cases.md. Update check.py to match, changing only the functions whose threshold changed. Then run the two fixtures again.",
    "baseline": "Read skills/build-eval-script/SKILL.md and follow it in run + log mode. The runs are runs/run-1.txt to runs/run-5.txt. The prompt file is prompt-v0.md. The model was {model}.",
}
FOLDER = {"generate": "A blind folder", "build": "Your project", "fixtures": "A clean folder", "key": "Answer key folder", "readback": "Your project", "fix": "Your project", "baseline": "Your project"}
MODEL_MISSING = "The model name is empty, so the line cannot be sent. Write the name of the model you used for your five runs in the box, then press Send to CLI."

ANSWER_KEY = """# Answer key

The polished fixture **passes the length rule** but makes up a refund policy.

<script>window.__xss = 1</script>

| Fixture | Rule | Note |
| --- | --- | --- |
| Bad | C2 | Missing the order number |
| Polished | C3 | <img src=x onerror="window.__xss = 2"> |

- First **bold** point
- Second point with `code`

## Next

Ignore [this link](javascript:alert(1)) please.
"""


ITEM_ORDER = ["track", "python", "node", "promptfoo", "cli", "signin", "working_test", "project"]


def pf_item(item_id, status, applies=True):
    n = ITEM_ORDER.index(item_id) + 1
    return {"id": item_id, "number": n, "title": PREFLIGHT_TEXT["items"][item_id]["title"], "applies": applies,
            "status": status, "detail": f"Detail for {item_id}.", "next": f"Next for {item_id}." if status != "passed" else "",
            "install": None}


def recipes_view(free="500.0 GB"):
    recipes = json.loads((CONTENT_ROOT / "cli-recipes.json").read_text(encoding="utf-8"))["recipes"]
    consent = PREFLIGHT_TEXT["consent"]
    out = []
    for r in recipes:
        entry = {"id": r["id"], "name": r["name"], "cli_command": r.get("cli_command", ""), "command": r.get("command", ""),
                 "note": r.get("note", ""), "source": r.get("source", ""), "hidden": bool(r.get("hidden")),
                 "requirement": None, "consent": None}
        if entry["command"]:
            entry["consent"] = {"title": consent["recipe_title"], "body": consent["recipe_body"].format(
                command=entry["command"], name=r["name"], need="400 MB", free=free),
                "confirm_label": consent["recipe_confirm"], "cancel_label": consent["cancel"]}
        req = r.get("requires")
        if req:
            entry["requirement"] = {"name": req["name"], "detail": req["detail"], "recipe": req["recipe"]}
        out.append(entry)
    return out


def build_preflight(passed, skipped=False, fresh=False):
    statuses = {i: "passed" for i in ITEM_ORDER}
    if fresh:
        # Nothing has been checked yet, except the track, which always counts as chosen.
        statuses = {i: "not_checked" for i in ITEM_ORDER}
        statuses["track"] = "passed"
    elif not passed:
        statuses["project"] = "not_checked"
    return {
        "passed": passed,
        "skipped": skipped,
        "track": TRACK["name"],
        "track_options": copy.deepcopy(PREFLIGHT_TEXT["track_options"]),
        "track_note": PREFLIGHT_TEXT["track_promptfoo_note"] if TRACK["name"] == "promptfoo" else None,
        "items": [pf_item(i, statuses[i], applies=i not in ("node", "promptfoo") or TRACK["name"] == "promptfoo") for i in ITEM_ORDER],
        "job": None,
        "cli": {"command": "mycli" if not passed else "", "launched": False, "recipes": recipes_view()},
        "ran_once": False,
        "working_test": {"line": PREFLIGHT_TEXT["working_test"]["line"], "folder_label": PREFLIGHT_TEXT["working_test"]["folder_label"]},
        "session": {"kind": None, "sent": False},
        "disk": {"free_bytes": 500 * 10**9, "free_text": "500.0 GB"},
        "text": copy.deepcopy(PREFLIGHT_TEXT["ui"]),
    }


def import_check_result(body):
    """A canned ImportResult chosen by words in the paths, so tests control what the screen shows."""
    prompt, cases = body.get("prompt_path", ""), body.get("test_cases_path", "")
    blocking, warnings = [], []
    criteria = [{"id": "C1", "name": "Length"}, {"id": "C2", "name": "Order number"}, {"id": "C3", "name": "Offer"}]

    def finding(code, message, criterion=None):
        return {"code": code, "message": message, "criterion": criterion, "file": "test_cases"}

    if "nope" in prompt:
        blocking.append(finding("file_not_found", f"Your prompt file was not found at {prompt}. Check the path, or right-click the file in File Explorer, choose Copy as path, paste it here and press Check my files again."))
    if "few" in cases:
        criteria = criteria[:2]
        blocking.append(finding("few_criteria", "Your test cases file has 2 of the 3 criteria the app needs. Add 1 more, each with a Requirement and a Threshold, then press Check my files again."))
    if "vague" in cases:
        warnings.append(finding("vague", "C3 Offer: the threshold uses “clear”, which a checker cannot judge. This criterion will show as NOT CHECKED and count as not covered. To make it checkable, rewrite the threshold using a number, a list of terms you choose, or a label.", "C3"))
        warnings.append(finding("untraced", "C2 Order number has no Requirement line, and your prompt does not seem to mention it. Add a Requirement line that says where it comes from, or add the matching instruction to your prompt.", "C2"))
    return {"blocking": blocking, "warnings": warnings, "criteria": criteria, "ready": not blocking,
            "copies": {"prompt": "prompt-v0.md", "test_cases": "test-cases.md"}}


def rows(verdicts):
    return [
        {"id": c["id"], "name": c["name"], "verdict": v, "reason": f"Reason for {c['id']}."}
        for c, v in zip(CRITERIA, verdicts)
    ]


def run_result(file_rows):
    return {
        "ok": True,
        "exit_code": 100 if TRACK["name"] == "promptfoo" else 1,
        "error": None,
        "raw": "== fixtures/fixture-bad.txt\nC1 PASS  Length\n-> 1 passed, 3 failed, 0 NOT CHECKED",
        "files": [{"file": name, "rows": r} for name, r in file_rows],
    }


def base_detail(step_id):
    cli = None
    text = resolved_text(step_id)
    if step_id in LINES or text.get("line"):
        raw = text.get("line") or text.get("line_template") if TRACK["name"] == "promptfoo" else LINES[step_id]
        line = raw.replace("{model}", "mid-tier-model")
        cli = {"line": line, "folder_label": text.get("folder_label") or FOLDER[step_id], "started": False, "sent": False, "blocked": None}
    return {
        "id": step_id,
        "title": title_of(step_id),
        "status": "active",
        "track": TRACK["name"],
        "goal": f"The goal of {title_of(step_id).lower()}.",
        "why": ["You decide what good means. The agent writes the code."],
        "instructions": ["Start your CLI.", "Press Send to CLI when it is ready.", "Answer any approvals in the terminal."],
        "cli": cli,
        "checklist": [],
        "last_check": None,
        "troubleshooting": [{"problem": "Nothing happens", "fix": "Press Start again."}],
        "ui": copy.deepcopy(text.get("ui", {})),
        "data": {},
    }


def live_cli_view(detail):
    """The typed line and the reason Start is blocked, rebuilt like the real engine does."""
    data, cli = detail["data"], detail["cli"]
    ids = [c["id"] for c in data["clis"]]
    name = " ".join(data["model_name"].split())
    chosen = data["cli"] if data["cli"] in ids else ""
    cli["line"] = LIVE_LINE.format(cli=chosen or "<" + " | ".join(ids) + ">", model=name or "<model>")
    cli["blocked"] = None if name else MODEL_MISSING
    cli["start_blocked"] = (LIVE_TEXT["messages"]["not_acknowledged"] if not data["acknowledged"]
                            else None if chosen else LIVE_TEXT["messages"]["no_cli"])


def live_detail():
    detail = {
        "id": "live", "title": LIVE_TEXT["title"], "status": "active", "track": "promptfoo", "optional": True,
        "goal": LIVE_TEXT["goal"], "why": LIVE_TEXT["why"], "instructions": LIVE_TEXT["instructions"],
        "cli": {"line": "", "folder_label": LIVE_TEXT["folder_label"], "started": False, "sent": False, "blocked": None,
                "start_blocked": None},
        "checklist": [], "last_check": None, "troubleshooting": LIVE_TEXT["troubleshooting"],
        "ui": copy.deepcopy(LIVE_TEXT["ui"]),
        "data": {"clis": copy.deepcopy(LIVE_TEXT["clis"]), "cli": "", "acknowledged": False, "model_name": "mid-tier-model",
                 "config_exists": False, "provider_exists": False, "provider_ok": False, "scan": [], "started": False},
    }
    live_cli_view(detail)
    return detail


def build_details():
    d = {s: base_detail(s) for s in STEP_ORDER}
    if TRACK["name"] == "promptfoo":
        d["live"] = live_detail()
    d["generate"]["data"] = {
        "runs": [
            {"n": 1, "done": True, "words": 58},
            {"n": 2, "done": True, "words": 61},
            {"n": 3, "done": False, "words": 0},
            {"n": 4, "done": False, "words": 0},
            {"n": 5, "done": False, "words": 0},
        ],
        "current_run": 3,
        "model_name": "",
    }
    d["build"]["data"] = {"checker_exists": True, "first_look": None, "scan": [{"message": (
        "promptfooconfig.yaml uses the \"llm-rubric\" check, which needs an AI model or the network."
        if TRACK["name"] == "promptfoo" else "check.py imports requests, which talks to the network.")}]}
    d["build"]["checklist"] = [
        {"id": "read_nc", "label": "I read the NOT CHECKED list", "checked": False},
        {"id": "read_ic", "label": "I read the Interpretation choices", "checked": False},
    ]
    d["fixtures"]["data"] = {
        "files": [
            {"name": "fixture-bad.txt", "present": True},
            {"name": "fixture-polished-but-wrong.txt", "present": False},
        ],
        "example": {"offered": True, "would_replace": False},
    }
    if "fixtures-config" in d:
        d["fixtures-config"]["data"] = {
            "config_exists": True,
            "tests": [{"name": "fixture-bad", "present": True}, {"name": "fixture-polished-but-wrong", "present": False}],
            "scan": [],
            "fixtures_ready": True,
        }
    d["key"]["data"] = {"files": [{"name": "answer-key.md", "present": False}], "key_held": False}
    d["readback"]["data"] = {"criteria": [{**c, "answer": None} for c in CRITERIA], "note": ""}
    d["predict"]["data"] = {
        "locked": False,
        "manual_rows": False,
        "criteria": copy.deepcopy(CRITERIA),
        "bad": {},
        "polished": {},
        "answers": {"wrong": "", "catches": "", "worst_guess": ""},
        "polished_text": "Dear customer, your refund of $50 has been processed. <b>Thanks</b>",
    }
    d["run"]["data"] = {"result": None, "grid": [], "classifications": {}, "answer_key_markdown": None, "polished_passed_all": False}
    d["fix"]["data"] = {
        "test_cases_text": "# Test cases\nC1: under 150 words\n",
        "test_cases_changed": False,
        "checker_changed_after": False,
        "rerun": None,
        "polished_fails": False,
        "explanation": "",
        "can_skip": False,
    }
    d["baseline"]["data"] = {
        "runs": [{"n": n, "done": True} for n in range(1, 6)],
        "runs_ready": True,
        "checker_exists": True,
        "model_name": "mid-tier-model",
        "result": None,
        "summary": None,
        "fresh": False,
        "log_exists": False,
    }
    return d


RUN_GRID = [
    {"id": "C1", "name": CRITERIA[0]["name"], "bad_predict": "P", "bad_actual": "P", "polished_predict": "P", "polished_actual": "P", "bad_surprise": False, "polished_surprise": False},
    {"id": "C2", "name": CRITERIA[1]["name"], "bad_predict": "P", "bad_actual": "F", "polished_predict": "P", "polished_actual": "P", "bad_surprise": True, "polished_surprise": False},
    {"id": "C3", "name": CRITERIA[2]["name"], "bad_predict": "NC", "bad_actual": "NC", "polished_predict": "F", "polished_actual": "NC", "bad_surprise": False, "polished_surprise": True},
    {"id": "C4", "name": CRITERIA[3]["name"], "bad_predict": "F", "bad_actual": "F", "polished_predict": "P", "polished_actual": "F", "bad_surprise": False, "polished_surprise": True},
]

BASELINE_SUMMARY = {
    "runs": 5,
    "criteria": [
        {"id": "C1", "name": CRITERIA[0]["name"], "passes": 4, "checked_runs": 5, "not_checked": False, "failing_runs": [3], "rate": 80},
        {"id": "C2", "name": CRITERIA[1]["name"], "passes": 5, "checked_runs": 5, "not_checked": False, "failing_runs": [], "rate": 100},
        {"id": "C3", "name": CRITERIA[2]["name"], "passes": 0, "checked_runs": 0, "not_checked": True, "failing_runs": [], "rate": None},
        {"id": "C4", "name": CRITERIA[3]["name"], "passes": 3, "checked_runs": 5, "not_checked": False, "failing_runs": [4, 5], "rate": 60},
    ],
    "overall": {"passes": 12, "total": 15},
    "not_checked": ["C3"],
}


class World:
    def __init__(self):
        self.lock = threading.Condition()
        self.reset("setup")

    def reset(self, scenario):
        with self.lock:
            promptfoo = scenario.startswith("pf-")
            if promptfoo:
                scenario = scenario[3:]
            set_track("promptfoo" if promptfoo else "script")
            self.course_mode = scenario.startswith("course")
            if self.course_mode:
                ready = scenario == "course-main"
                self.configured = ready
                # The course scenarios mimic a participant who skipped setup, except "course-first-run".
                self.preflight = build_preflight(ready, skipped=not ready and scenario != "course-first-run")
                self.course = CourseState()
                if scenario in ("course-pf", "course-main"):
                    self.course.status["mission"] = "done"
            else:
                self.configured = scenario not in ("setup", "preflight")
                self.preflight = build_preflight(scenario not in ("setup", "preflight"))
                self.course = CourseState()
            self.details = build_details()
            self.part1 = {"done": 0, "statuses": {}}
            self.part2 = {"done": 0, "statuses": {}}
            self.live_done = False
            if self.course_mode or scenario in ("setup", "preflight", "generate"):                self.current_index = 0
            else:
                self.current_index = STEP_ORDER.index(scenario) if scenario not in ("done", "live") else len(STEP_ORDER)
            self.terminal = {"running": False, "label": "Your CLI", "exit_code": None, "owner": None}
            self.setup = {
                "project_path": "",
                "cli_command": "",
                "starter": "northwind",
                "defaults": {"project_path": "C:\\Users\\tester\\eval-project", "cli_command": ""},
                "warnings": ["Heads up: this folder has limited disk space."],
            }
            self.log = []
            self.inputs = []
            self.resizes = []
            self.fail_next = {}
            self.check_passes = True
            self.quit_called = False
            self.seq = 100
            self.outputs = []
            self.events = []
            self.drop_generation = getattr(self, "drop_generation", 0) + 1
            self.lock.notify_all()

    def steps_list(self):
        result = []
        for i, sid in enumerate(STEP_ORDER):
            status = "done" if i < self.current_index else "active" if i == self.current_index else "locked"
            result.append({"id": sid, "title": title_of(sid), "status": status})
        return result

    def optional_steps(self):
        """The optional live step shows up once every step of the promptfoo track is done."""
        if TRACK["name"] == "promptfoo" and self.configured and "live" in self.details and self.current_index >= len(STEP_ORDER):
            return [{"id": "live", "title": LIVE_TEXT["title"], "status": "done" if self.live_done else "optional"}]
        return []

    def current_id(self):
        return STEP_ORDER[self.current_index] if self.current_index < len(STEP_ORDER) else None

    def step_status(self, sid):
        index = STEP_ORDER.index(sid)
        return "done" if index < self.current_index else "active" if index == self.current_index else "locked"

    def walk(self):
        return self.course.walk(self.preflight["passed"], self.step_status)

    def course_state(self):
        if not self.course_mode:
            steps = self.steps_list()
            course = [{"kind": "step", "id": s["id"], "title": s["title"], "status": s["status"]} for s in steps]
            current = self.current_id()
            return {"course": course, "current_item": {"kind": "step", "id": current} if self.configured and current else None}
        walk = self.walk()
        titles = {**TITLES, **{lid: mock_course.LESSONS[lid]["title"] for lid in mock_course.LESSONS}}
        return {
            "course": [{"kind": k, "id": i, "title": titles[i], "status": s} for k, i, s in walk],
            "current_item": next(({"kind": k, "id": i} for k, i, s in walk if s == "active"), None),
        }

    def series_state(self, course):
        """The Series map, built by the engine's rules: Part 3 comes from the course list, Part 1 from its own record, the rest from series.json."""
        if not self.course_mode:
            return None
        counted = [x for x in course if x["status"] in ("done", "skipped")]
        done, total = len(counted), len(course)
        parts = []
        for part in SERIES["parts"]:
            entry = {k: part[k] for k in ("n", "id", "title", "kind", "outcome")}
            if part["kind"] == "course" and part["id"] == "part-1":
                entry.update(self.own_part_row(self.part1, PART1_LESSONS, PART1_ITEMS))
            elif part["kind"] == "course" and part["id"] == "part-2":
                entry.update(self.own_part_row(self.part2, PART2_LESSONS, PART2_ITEMS))
            elif part["kind"] == "course":
                entry["state"] = "done" if done == total else "in_progress" if done else "not_started"
                entry["done"], entry["total"] = done, total
                entry["lessons"] = [{"id": x["id"], "title": x["title"], "status": x["status"]} for x in course if x["kind"] == "lesson"]
            parts.append(entry)
        return {"title": SERIES["title"], "ui": copy.deepcopy(SERIES["ui"]), "parts": parts}

    def own_part_row(self, record, lesson_list, total):
        """A Part with its own course (Part 1 or Part 2): `total` items, of which `record["done"]` are done; lesson statuses come from `record["statuses"]`."""
        done = record["done"]
        lessons = []
        for i, lesson in enumerate(lesson_list):
            default = "active" if i == 0 and done == 0 else "locked"
            lessons.append({"id": lesson["id"], "title": lesson["title"], "status": record["statuses"].get(lesson["id"], default)})
        return {"state": "done" if done == total else "in_progress" if done else "not_started", "done": done, "total": total,
                "lessons": lessons}

    def state(self, step_id=None):
        step = None
        steps = self.steps_list()
        current_step = self.current_id() if self.configured else None
        extra = self.course_state()
        if self.course_mode:
            passed = self.preflight["passed"]
            statuses = {i: s for k, i, s in self.walk() if k == "step"}
            steps = [{"id": sid, "title": title_of(sid), "status": statuses[sid] if passed else "locked"} for sid in STEP_ORDER]
            item = extra["current_item"]
            current_step = item["id"] if passed and item and item["kind"] == "step" else None
        if self.configured and (not self.course_mode or self.preflight["passed"]):
            sid = step_id or current_step
            if sid:
                step = copy.deepcopy(self.details[sid])
                if sid == "live":
                    step["status"] = "done" if self.live_done else "active"
                else:
                    step["status"] = next(s["status"] for s in steps if s["id"] == sid)
                if step["status"] == "locked" and sid != "live":
                    step = self.step_preview(sid)  # reading ahead: the words only, never the step's data
                elif self.course_mode and step["status"] == "done" and sid in STEP_ORDER:
                    step["question"] = self.course.step_question_view(sid)
        elif self.course_mode and not self.preflight["passed"] and step_id in STEP_ORDER:
            step = self.step_preview(step_id)
        locked = self.configured and self.current_index > 0 and not self.course_mode
        preflight = copy.deepcopy(self.preflight)
        preflight["track_locked"] = bool(locked)
        preflight["track_locked_note"] = PREFLIGHT_TEXT["track_locked_note"] if locked else None
        return {
            "configured": self.configured,
            "setup": copy.deepcopy(self.setup),
            "current_step": current_step,
            "steps": steps,
            "step": step,
            "terminal": dict(self.terminal),
            "preflight": preflight,
            "course": extra["course"],
            "optional_steps": self.optional_steps(),
            "current_item": extra["current_item"],
            "review": self.course.review_summary(),
            "course_text": copy.deepcopy(mock_course.UI),
            "series": self.series_state(extra["course"]),
            "settings": {"text": copy.deepcopy(SETTINGS_TEXT), "backup_folder": BACKUP_FOLDER, "has_project": self.configured},
        }

    def held_by(self):
        """The item still to do, which a preview names once setup has passed; None before setup."""
        if not self.preflight["passed"]:
            return None
        if self.course_mode:
            titles = {**TITLES, **{lid: mock_course.LESSONS[lid]["title"] for lid in mock_course.LESSONS}}
            return next(({"kind": k, "id": i, "title": titles[i]} for k, i, s in self.walk() if s == "active"), None)
        current = self.current_id()
        return {"kind": "step", "id": current, "title": title_of(current)} if self.configured and current else None

    def step_preview(self, sid):
        """A locked step read ahead: its words only, like the real engine."""
        detail = copy.deepcopy(self.details[sid])
        return {"id": sid, "title": detail["title"], "status": "locked", "preview": True, "track": TRACK["name"],
                "held_by": self.held_by(),
                "goal": detail["goal"], "why": detail["why"], "instructions": detail["instructions"], "cli": None,
                "checklist": [], "last_check": None, "question": None, "troubleshooting": detail["troubleshooting"],
                "ui": detail.get("ui", {}), "data": {}}

    def push_event(self, event):
        with self.lock:
            self.events.append(event)
            self.lock.notify_all()

    def emit_output(self, data: bytes):
        with self.lock:
            self.seq += 1
            event = {"event": "output", "seq": self.seq, "data": base64.b64encode(data).decode("ascii")}
            self.outputs.append(event)
            self.events.append(event)
            self.lock.notify_all()

    def emit_state(self):
        self.push_event({"event": "state"})


world = World()


class Handler(BaseHTTPRequestHandler):
    server_version = "mock/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):  # noqa: D102
        pass

    # ---- helpers ------------------------------------------------------
    def _json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _reject(self, status=403):
        self._json(status, {"ok": False, "error": {"code": "forbidden", "message": "Forbidden."}, "state": None})

    def _host_ok(self):
        port = self.server.server_address[1]
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        if host != f"127.0.0.1:{port}":
            return False
        return origin is None or origin == f"http://127.0.0.1:{port}"

    def _token_ok(self):
        return self.headers.get("X-Eval-Token") == self.server.token

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode())
        except ValueError:
            return None

    # ---- routing ------------------------------------------------------
    def do_GET(self):  # noqa: N802
        parts = urlsplit(self.path)
        if not self._host_ok():
            self._reject()
            return
        if parts.path.startswith("/__mock/"):
            self._mock_get(parts)
            return
        if parts.path == "/api/terminal/stream":
            self._stream(parse_qs(parts.query))
            return
        if parts.path.startswith("/api/"):
            with world.lock:
                world.log.append({"method": "GET", "path": self.path, "token_header": self._token_ok()})
            if not self._token_ok():
                self._reject()
                return
            if parts.path == "/api/state":
                query = parse_qs(parts.query)
                step = query.get("step", [None])[0]
                with world.lock:
                    self._json(200, world.state(step))
                return
            if parts.path in ("/api/lesson", "/api/kit", "/api/review"):
                query = parse_qs(parts.query)
                with world.lock:
                    try:
                        if parts.path == "/api/lesson":
                            body = {"lesson": world.course.view(query.get("id", [""])[0], world.preflight["passed"], world.step_status, world.held_by())}
                        elif parts.path == "/api/kit":
                            body = world.course.kit(query.get("ref", [""])[0])
                        else:
                            body = world.course.review_get()
                        self._json(200, dict({"ok": True}, **body))
                    except (MockError, KeyError) as exc:
                        code = getattr(exc, "code", "unknown_lesson")
                        self._json(400, {"ok": False, "error": {"code": code, "message": str(exc)}, "state": world.state()})
                return
            self._reject(404)
            return
        self._static(parts.path)

    def do_POST(self):  # noqa: N802
        parts = urlsplit(self.path)
        if not self._host_ok():
            self._reject()
            return
        if parts.path.startswith("/__mock/"):
            self._mock_post(parts)
            return
        body = self._read_body()
        with world.lock:
            world.log.append({"method": "POST", "path": self.path, "token_header": self._token_ok(), "body": body})
        if not self._token_ok():
            self._reject()
            return
        if self.headers.get("Content-Type") != "application/json" or body is None:
            self._json(400, {"ok": False, "error": {"code": "bad_request", "message": "Bad request."}, "state": None})
            return
        with world.lock:
            fail = world.fail_next.pop(parts.path, None)
            if fail:
                self._json(400, {"ok": False, "error": fail, "state": world.state()})
                return
            try:
                result = self._route(parts.path, body)
                payload = {"ok": True, "state": world.state()}
                if result is not None:
                    payload["result"] = result
                self._json(200, payload)
            except MockError as exc:
                self._json(400, {"ok": False, "error": {"code": exc.code, "message": str(exc)}, "state": world.state()})
            except ValueError as exc:
                self._json(400, {"ok": False, "error": {"code": "invalid", "message": str(exc)}, "state": world.state()})

    # ---- contract ------------------------------------------------------
    def _lesson_route(self, path, body):
        course, passed, steps = world.course, world.preflight["passed"], world.step_status
        if path == "/api/lesson/answer":
            return course.answer(body["lesson"], body["activity"], body.get("answer") or {}, passed, steps)
        if path == "/api/lesson/rule-run":
            return course.rule_run(body["lesson"], body["activity"], body["rule"], body.get("text"), passed, steps)
        if path == "/api/lesson/complete":
            course.complete(body["lesson"], passed, steps)
        elif path == "/api/lesson/skip":
            course.skip(body["lesson"], passed, steps)
        elif path == "/api/placement/answer":
            return course.placement_answer(body["id"], body.get("option"), body.get("accept_skip"), passed, steps)
        elif path == "/api/lesson/cli/start":
            if not passed:
                raise MockError("preflight_incomplete", mock_course.ERRORS["preflight_first"])
            course.require_active(body["lesson"], passed, steps)
            if body["activity"] == "hook-compare" and all(course.hook_runs[n].strip() for n in course.hook_runs):
                raise MockError("runs_complete", mock_course.ERRORS["runs_complete"])
            course.cli_key = f"lesson:{body['lesson']}:{body['activity']}"
            course.sent = False
            world.terminal.update(running=True, exit_code=None, label="Grading the update: run 1 of 3", owner=course.cli_key)
            self._greet()
        elif path == "/api/lesson/cli/send":
            if course.cli_key != f"lesson:{body['lesson']}:{body['activity']}":
                raise MockError("cli_not_running", mock_course.ERRORS["cli_not_running"])
            course.sent = True
        elif path == "/api/lesson/cli/stop":
            course.cli_key = None
            world.terminal.update(running=False, exit_code=0)
        elif path == "/api/review/answer":
            return course.review_answer(body["item"], body.get("option"))
        elif path == "/api/review/postpone":
            course.review_postpone()
        return None

    def _route(self, path, body):
        if path.startswith("/api/lesson/") or path.startswith("/api/placement/") or path.startswith("/api/review/"):
            return self._lesson_route(path, body)
        if path == "/api/setup/import-check":
            return import_check_result(body)
        if path == "/api/setup":
            world.configured = True
            world.current_index = 0
            world.setup.update({"project_path": body["project_path"], "cli_command": body.get("cli_command", ""), "starter": body["starter"]})
            world.setup["warnings"] = []
            world.preflight = build_preflight(True)
        elif path == "/api/preflight/track":
            if world.configured and world.current_index > 0 and body["track"] != TRACK["name"]:
                raise ValueError(PREFLIGHT_TEXT["errors"]["track_locked"])
            if body["track"] != TRACK["name"]:
                set_track(body["track"])
                world.details = build_details()
            world.preflight["track"] = body["track"]
            world.preflight["track_note"] = PREFLIGHT_TEXT["track_promptfoo_note"] if body["track"] == "promptfoo" else None
            for item in world.preflight["items"]:
                if item["id"] in ("node", "promptfoo"):
                    item["applies"] = body["track"] == "promptfoo"
        elif path == "/api/preflight/skip":
            world.preflight["skipped"] = True
        elif path in ("/api/reset/progress", "/api/reset/configuration"):
            if body.get("confirm") is not True:
                raise MockError("confirm_required", SETTINGS_FULL["errors"]["confirm_required"])
            kind = path.rsplit("/", 1)[1]
            world.log.append({"method": "RESET", "path": path, "kind": kind})
            world.course = CourseState()
            world.current_index = 0
            world.terminal.update(running=False, exit_code=None)
            if kind == "configuration":
                world.configured = False
                world.preflight = build_preflight(False, fresh=True)
                world.setup.update({"project_path": "", "cli_command": "", "starter": "northwind"})
            return {"kind": kind, "backup_folder": BACKUP_FOLDER,
                    "message": SETTINGS_FULL["reset"][kind]["done"].format(folder=BACKUP_FOLDER)}
        elif path == "/api/preflight/check":
            world.preflight["ran_once"] = True
        elif path == "/api/preflight/install":
            world.preflight["job"] = {"kind": body["item"], "label": f"Downloading {body['item']}", "running": True,
                                      "done_bytes": 10 * 10**6, "total_bytes": 41 * 10**6, "percent": 24,
                                      "detail": "", "progress_text": "10 MB of about 41 MB"}
            for item in world.preflight["items"]:
                if item["id"] == body["item"] and item["install"]:
                    item["install"]["available"] = False
        elif path == "/api/preflight/cli":
            world.preflight["cli"]["command"] = body["cli_command"]
        elif path in ("/api/preflight/cli/start", "/api/preflight/test/start", "/api/preflight/cli/recipe"):
            kind = {"/api/preflight/test/start": "test", "/api/preflight/cli/start": "signin"}.get(path, "recipe")
            world.terminal.update(running=True, exit_code=None, owner=f"preflight:{kind}")
            if path == "/api/preflight/test/start":
                world.preflight["session"] = {"kind": "test", "sent": False}
            elif path == "/api/preflight/cli/start":
                world.preflight["session"] = {"kind": "signin", "sent": False}
            else:
                world.preflight["session"] = {"kind": "recipe", "sent": False}
            self._greet()
        elif path == "/api/preflight/test/send":
            world.preflight["session"] = {"kind": "test", "sent": True}
        elif path == "/api/preflight/test/check":
            for item in world.preflight["items"]:
                if item["id"] == "working_test":
                    item.update(status="passed", detail="Your CLI read a file, wrote files and ran a command correctly.", next="")
        elif path == "/api/preflight/signin":
            for item in world.preflight["items"]:
                if item["id"] == "signin":
                    item.update(status="passed", detail="You confirmed that you are signed in.", next="")
        elif path == "/api/preflight/stop":
            world.terminal.update(running=False, exit_code=0)
            world.preflight["session"] = {"kind": None, "sent": False}
        elif path == "/api/step/start":
            if body["step"] == "live" and world.details["live"]["cli"]["start_blocked"]:
                raise MockError("warning_not_acknowledged", world.details["live"]["cli"]["start_blocked"])
            cli = world.details[body["step"]]["cli"]
            cli["started"] = True
            cli["sent"] = False
            world.terminal.update(running=True, exit_code=None, owner=body["step"])
            self._greet()
        elif path == "/api/step/send":
            if body["step"] == "live" and world.details["live"]["cli"]["start_blocked"]:
                raise MockError("warning_not_acknowledged", world.details["live"]["cli"]["start_blocked"])
            blocked = world.details[body["step"]]["cli"].get("blocked")
            if blocked:
                raise ValueError(blocked)
            world.details[body["step"]]["cli"]["sent"] = True
        elif path == "/api/step/stop":
            world.details[body["step"]]["cli"]["started"] = False
            world.terminal.update(running=False, exit_code=0)
            world.events.append({"event": "exit", "code": 0})
            world.lock.notify_all()
        elif path == "/api/step/check":
            self._check(body["step"])
        elif path == "/api/step/question":
            return world.course.step_question_answer(body["step"], body["option"])
        elif path == "/api/step/submit":
            self._submit(body["step"], body["data"])
        elif path == "/api/step/run-checker":
            self._run_checker(body["step"], body["which"])
        elif path == "/api/step/skip":
            world.current_index = STEP_ORDER.index("fix") + 1
        elif path == "/api/step/use-example-fixtures":
            self._use_example_fixtures(body)
        elif path == "/api/terminal/release":
            world.course.cli_key = None
            for detail in world.details.values():
                if isinstance(detail.get("cli"), dict):
                    detail["cli"]["started"] = False
            world.terminal.update(running=False, exit_code=None, label="", owner=None)
        elif path == "/api/terminal/input":
            world.inputs.append(base64.b64decode(body["data"]))
        elif path == "/api/terminal/resize":
            world.resizes.append({"cols": body["cols"], "rows": body["rows"]})
        elif path == "/api/quit":
            world.quit_called = True
        else:
            raise ValueError(f"unknown route {path}")
        return None

    def _use_example_fixtures(self, body):
        """The same refusals as the real route, so the page's error handling is exercised."""
        if body.get("step") != "fixtures":
            raise MockError("no_example_fixtures", "The example's fixtures can only be used in the fixtures step. Open that step to use them there.")
        if world.step_status("fixtures") != "active":
            raise MockError("step_locked", "Finish the earlier steps first.")
        if world.setup["starter"] != "northwind":
            raise MockError("example_fixtures_northwind_only", "These fixtures belong to the Northwind example, so they would not test the checker for your own task.")
        if world.terminal["running"]:
            raise MockError("cli_running", "Your CLI is still running. Press Stop, then use the example's fixtures.")
        example = world.details["fixtures"]["data"]["example"]
        if example["would_replace"] and body.get("replace") is not True:
            raise MockError("confirm_replace", "The fixtures folder already has text in it. Confirm that you want to replace it with the example's two fixtures, then try again.")
        world.details["fixtures"]["data"]["files"] = [
            {"name": "fixture-bad.txt", "present": True},
            {"name": "fixture-polished-but-wrong.txt", "present": True},
        ]
        example["would_replace"] = True

    def _greet(self):
        # Colored text plus multi-byte characters, split mid-character.
        data = "\x1b[32mFake CLI ready\x1b[0m café ✓\r\n".encode("utf-8")
        cut = data.index("✓".encode("utf-8")) + 1
        world.seq += 1
        first = {"event": "output", "seq": world.seq, "data": base64.b64encode(data[:cut]).decode("ascii")}
        world.seq += 1
        second = {"event": "output", "seq": world.seq, "data": base64.b64encode(data[cut:]).decode("ascii")}
        world.outputs.extend([first, second])
        world.events.extend([first, second])
        world.lock.notify_all()

    def _check(self, step_id):
        detail = world.details[step_id]
        if step_id == "live":
            data = detail["data"]
            items = [
                {"label": "Warning read", "ok": data["acknowledged"], "detail": "" if data["acknowledged"] else "Read the warning and tick the box that says you have read it."},
                {"label": "promptfooconfig.live.yaml exists", "ok": data["config_exists"], "detail": "" if data["config_exists"] else "promptfooconfig.live.yaml was not found in your project folder. Press Start my CLI, then Send to CLI, so your CLI writes it."},
            ]
            ok = all(i["ok"] for i in items)
            detail["last_check"] = {"ok": ok, "items": items, "nudges": []}
            world.live_done = ok
            return
        if world.check_passes:
            detail["last_check"] = {"ok": True, "items": [{"label": "All good", "ok": True, "detail": ""}], "nudges": []}
            world.current_index = STEP_ORDER.index(step_id) + 1
        else:
            detail["last_check"] = {
                "ok": False,
                "items": [
                    {"label": "check.py exists", "ok": True, "detail": ""},
                    {"label": "First look was run", "ok": False, "detail": "Press Run the first look."},
                ],
                "nudges": ["Fix the spec, not the checker."],
            }

    def _submit(self, step_id, data):
        d = world.details[step_id]
        if step_id == "live":
            for key in ("acknowledged", "cli"):
                if key in data:
                    d["data"][key] = data[key]
            if "model_name" in data:
                d["data"]["model_name"] = data["model_name"]
            live_cli_view(d)
            return
        if step_id == "generate":
            if "model_name" in data:
                d["data"]["model_name"] = data["model_name"]
        elif step_id == "build":
            for item in d["checklist"]:
                if item["id"] in data.get("checklist", {}):
                    item["checked"] = data["checklist"][item["id"]]
        elif step_id == "readback":
            for c in d["data"]["criteria"]:
                if c["id"] in data.get("answers", {}):
                    c["answer"] = data["answers"][c["id"]]
            if "note" in data:
                d["data"]["note"] = data["note"]
        elif step_id == "predict":
            if d["data"]["locked"]:
                raise ValueError("Your predictions are locked and cannot be changed.")
            for key in ("bad", "polished"):
                if key in data:
                    d["data"][key] = data[key]
            if "answers" in data:
                d["data"]["answers"].update(data["answers"])
            if "criteria" in data:
                d["data"]["criteria"] = data["criteria"]
            if data.get("lock"):
                d["data"]["locked"] = True
        elif step_id == "run":
            d["data"]["classifications"].update(data.get("classifications", {}))
        elif step_id == "baseline":
            if "model_name" in data:
                name = " ".join(data["model_name"].split())
                d["data"]["model_name"] = data["model_name"]
                d["cli"]["line"] = LINES["baseline"].format(model=name or "<model>")
                d["cli"]["blocked"] = None if name else MODEL_MISSING
        elif step_id == "fix":
            if "test_cases_text" in data:
                d["data"]["test_cases_text"] = data["test_cases_text"]
                d["data"]["test_cases_changed"] = True
            if "explanation" in data:
                d["data"]["explanation"] = data["explanation"]

    def _run_checker(self, step_id, which):
        if which == "baseline":
            world.details["baseline"]["data"].update(
                result=run_result([(f"runs/run-{n}.txt", rows(["F" if n == 3 else "P", "P", "NC", "P" if n < 4 else "F"])) for n in range(1, 6)]),
                summary=copy.deepcopy(BASELINE_SUMMARY), fresh=True)
        elif which == "first_look":
            world.details["build"]["data"]["first_look"] = run_result([("runs/run-1.txt", rows(["P", "F", "NC", "F"]))])
        elif step_id == "run":
            result = run_result([("fixtures/fixture-bad.txt", rows(["P", "F", "NC", "F"])), ("fixtures/fixture-polished-but-wrong.txt", rows(["P", "P", "NC", "F"]))])
            world.details["run"]["data"].update(result=result, grid=copy.deepcopy(RUN_GRID), answer_key_markdown=ANSWER_KEY)
        else:
            world.details["fix"]["data"].update(
                rerun=run_result([("fixtures/fixture-bad.txt", rows(["F", "F", "NC", "F"])), ("fixtures/fixture-polished-but-wrong.txt", rows(["P", "F", "NC", "F"]))]),
                polished_fails=True,
                checker_changed_after=True,
            )

    # ---- SSE -----------------------------------------------------------
    def _stream(self, query):
        if query.get("t", [None])[0] != self.server.token:
            self._reject()
            return
        after = query.get("after", [None])[0]
        with world.lock:
            world.log.append({"method": "GET", "path": self.path})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        with world.lock:
            cursor = len(world.events)
            generation = world.drop_generation
            replay = [e for e in world.outputs if after is None or e["seq"] > int(after)]
        try:
            for event in replay:
                self._write_event(event)
            last_beat = time.monotonic()
            while True:
                with world.lock:
                    world.lock.wait_for(lambda: len(world.events) > cursor or world.drop_generation != generation, timeout=1.0)
                    if world.drop_generation != generation:
                        return
                    pending = world.events[cursor:]
                    cursor = len(world.events)
                for event in pending:
                    self._write_event(event)
                if time.monotonic() - last_beat > 15:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    last_beat = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _write_event(self, event):
        name = event["event"]
        payload = {k: v for k, v in event.items() if k != "event"}
        self.wfile.write(f"event: {name}\ndata: {json.dumps(payload)}\n\n".encode())
        self.wfile.flush()

    # ---- static --------------------------------------------------------
    def _static(self, path):
        if path == "/reference-data.json":
            body = json.dumps({"glossary": mock_course.GLOSSARY["terms"], "reference": mock_course.LESSON_UI["reference"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            self.wfile.write(body)
            return
        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_ROOT / rel).resolve()
        if WEB_ROOT.resolve() not in target.parents or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    # ---- test controls ---------------------------------------------------
    def _mock_get(self, parts):
        if parts.path == "/__mock/log":
            with world.lock:
                self._json(200, {
                    "log": world.log,
                    "inputs_b64": [base64.b64encode(b).decode("ascii") for b in world.inputs],
                    "inputs_text": b"".join(world.inputs).decode("utf-8", "replace"),
                    "resizes": world.resizes,
                    "quit_called": world.quit_called,
                })
        elif parts.path == "/__mock/ping":
            self._json(200, {"ok": True})
        else:
            self._reject(404)

    def _mock_post(self, parts):
        body = self._read_body() or {}
        with world.lock:
            if parts.path == "/__mock/reset":
                world.reset(body.get("scenario", "setup"))
            elif parts.path == "/__mock/set_data":
                world.details[body["step"]]["data"].update(body["data"])
            elif parts.path == "/__mock/set_starter":
                world.setup["starter"] = body["starter"]
                world.details["fixtures"]["data"]["example"]["offered"] = body["starter"] == "northwind"
            elif parts.path == "/__mock/set_terminal":
                world.terminal.update(body)
            elif parts.path == "/__mock/check_passes":
                world.check_passes = bool(body.get("value"))
            elif parts.path == "/__mock/fail":
                world.fail_next[body["path"]] = {"code": body.get("code", "nope"), "message": body["message"]}
            elif parts.path == "/__mock/pf_item":
                for item in world.preflight["items"]:
                    if item["id"] == body["id"]:
                        item.update(body["changes"])
            elif parts.path == "/__mock/pf_set":
                world.preflight.update(body)
            elif parts.path == "/__mock/hook_run":
                world.course.hook_runs[int(body["n"])] = body["text"]
                world.course.cli_key = None
                world.terminal.update(running=False, exit_code=0)
                world.emit_state()
            elif parts.path == "/__mock/demo_checker":
                world.course.demo["checker"] = bool(body.get("exists", True))
                world.emit_state()
            elif parts.path == "/__mock/review_items":
                world.course.set_review(body.get("keys", []))
            elif parts.path == "/__mock/placement_pass":
                item = next(p for p in mock_course.PLACEMENT if p["id"] == body["id"])
                good = next(o["id"] for o in item["options"] if o["correct"])
                world.course.placement[body["id"]] = {"correct": True, "option": good, "decision": None}
            elif parts.path == "/__mock/step_index":
                world.current_index = int(body["index"])
            elif parts.path == "/__mock/part1":
                world.part1["done"] = int(body.get("done", 0))
                world.part1["statuses"] = dict(body.get("statuses", {}))
            elif parts.path == "/__mock/part2":
                world.part2["done"] = int(body.get("done", 0))
                world.part2["statuses"] = dict(body.get("statuses", {}))
            elif parts.path == "/__mock/lesson_status":
                world.course.status[body["id"]] = body["status"]
            elif parts.path == "/__mock/emit_state":
                world.emit_state()
            elif parts.path == "/__mock/emit_exit":
                world.terminal.update(running=False, exit_code=body.get("code", 0))
                world.events.append({"event": "exit", "code": body.get("code", 0)})
                world.lock.notify_all()
            elif parts.path == "/__mock/emit_output":
                for chunk in body.get("chunks_b64", []):
                    world.emit_output(base64.b64decode(chunk))
            elif parts.path == "/__mock/drop_streams":
                world.drop_generation += 1
                world.lock.notify_all()
            else:
                self._reject(404)
                return
            self._json(200, {"ok": True})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=38917)
    parser.add_argument("--token", default="dev-token")
    args = parser.parse_args()
    server = Server(("127.0.0.1", args.port), Handler)
    server.token = args.token
    print(f"mock listening on http://127.0.0.1:{args.port}/?t={args.token}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
