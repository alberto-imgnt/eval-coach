"""Step state machine: the only class the server calls for domain work."""
from __future__ import annotations

import base64
import json
import os
import posixpath
import re
import secrets
import shutil
import sys
import threading
import time
from pathlib import Path

from . import baseline, criteria_steps, gates, import_checks, parsers, part_steps, project, promptfoo, resources, runner, scan
from . import lessons as lesson_lib
from . import reset as reset_lib
from . import review as review_lib
from . import state as store
from .preflight import Preflight, PreflightError
from .state import CorruptStateError

STARTERS = ("northwind", "own")
LIVE = store.OPTIONAL_STEP
IMPORT_READ_CODES = ("missing_prompt_path", "missing_test_cases_path", "not_absolute", "file_not_found",
                     "not_a_file", "file_unreadable")
_ID_RE = re.compile(r"^C\d+$")
_CLASS_KEY_RE = re.compile(r"^C\d+:(bad|polished)$")
ANSWER_FIELDS = ("wrong", "catches", "worst_guess")
PF_SIGNIN, PF_TEST, PF_RECIPE = "preflight:signin", "preflight:test", "preflight:recipe"
PF_SESSIONS = (PF_SIGNIN, PF_TEST, PF_RECIPE)
NOT_KIND = object()  # what _kind_call returns for a step that has no kind


class EngineError(Exception):
    """A request that cannot be done. The message is shown to the participant."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _deep_merge(base, override):
    """Objects merge key by key, and anything else (text, lists) is replaced by the override."""
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = _deep_merge(base.get(key), value)
        return merged
    return override


def _preflight_errors(method):
    """Turn a preflight refusal into the error the server already knows how to report."""

    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except PreflightError as exc:
            raise EngineError(exc.code, exc.message) from exc

    return wrapper


class Engine:
    def __init__(self, home, terminal, poll_interval=1.0, preflight_runner=None, registry_paths=None,
                 lessons=None, clock=None):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.terminal = terminal
        self.poll_interval = poll_interval
        self.python_path = sys.executable
        self.content, self.part_ui = lesson_lib.load_step_content()
        self.lesson_text = json.loads(resources.read_text("content/lesson-ui.json"))
        self.settings_text = json.loads(resources.read_text("content/settings.json"))
        self.series_text = json.loads(resources.read_text("content/series.json"))
        self.lessons = lessons  # a lessons.Course, or None for an engine with no course
        self._clock = clock if clock is not None else time.time
        self._pending_block = None  # course progress from before a project exists
        self._review_sitting = None
        self._review_postponed = False
        self._lock = threading.RLock()
        self.paths = None
        self.progress = None
        self._warnings = []
        self._cli_step = None
        self._sent = False
        self._watcher_cancel = None
        self._checker_running = False
        pf_kwargs = {"runner": preflight_runner, "python_path": self.python_path,
                     "publish": self.terminal.publish_state if hasattr(self.terminal, "publish_state") else None,
                     "paths_provider": lambda: self.paths}
        if registry_paths is not None:
            pf_kwargs["registry_paths"] = registry_paths
        self.preflight = Preflight(self.home, self.terminal, **pf_kwargs)
        self._load_last_project()
        if self.progress is not None:
            self.preflight.adopt_cli_command(self.progress.get("cli_command", ""))
            if self._track_locked():
                self.preflight.adopt_track(self._track())
        if self.preflight.load_problem:
            self._warn(self.preflight.content["errors"]["corrupt_preflight"])

    # --- persistence -------------------------------------------------------

    def _settings_path(self):
        return self.home / "app.json"

    def _load_last_project(self):
        try:
            data = store.read_json(self._settings_path())
        except FileNotFoundError:
            return
        except CorruptStateError:
            self._warn(self.content["messages"]["bad_settings"])
            return
        last = data.get("last_project") if isinstance(data, dict) else None
        if not isinstance(last, str) or not last:
            return
        paths = project.Paths(self.home, last)
        if not paths.progress_file.is_file():
            return
        try:
            self.progress = self._read_progress(paths)
            self.paths = paths
        except (CorruptStateError, OSError):
            self._warn(self._corrupt_message(paths))

    @staticmethod
    def _read_progress(paths):
        return store.load_progress(paths.progress_file, paths.sealed_key.is_file())

    def _save(self):
        store.save_progress(self.paths.progress_file, self.progress)

    def _warn(self, text):
        if text not in self._warnings:
            self._warnings.append(text)

    def _corrupt_message(self, paths):
        return self.content["messages"]["corrupt_progress"].format(path=str(paths.progress_file))

    def _result_path(self, name):
        return self.paths.results_dir / f"{name}.json"

    def _load_result(self, name):
        try:
            data = store.read_json(self._result_path(name))
        except (FileNotFoundError, CorruptStateError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _save_result(self, name, result):
        store.write_json_atomic(self._result_path(name), result)

    # --- guards ------------------------------------------------------------

    def _require_configured(self):
        if self.progress is None:
            raise EngineError("not_configured", "Finish the setup page first.")

    def _require_known(self, step):
        if step not in self._steps(self._part_of(step)) and not self._live_exists(step):
            raise EngineError("unknown_step", f"There is no step called {step!r}.")

    def _live_exists(self, step):
        """The optional live-mode step exists on the promptfoo track only."""
        return step == LIVE and self._track() == "promptfoo"

    def _live_open(self):
        """Live mode can be used once the baseline step is done. It is never part of the step order."""
        return self.progress is not None and "baseline" in self.progress["done"]

    def _status(self, step):
        if step == LIVE:
            if not self._live_open():
                return "locked"
            return "done" if self._step(LIVE)["done"] else "active"
        for kind, item, status in self._walk(True, self._part_of(step)):
            if kind == "step" and item == step:
                return status
        return "locked"

    def _require_preflight(self):
        if not self.preflight.is_passed(self.paths):
            raise EngineError("preflight_incomplete", self.preflight.content["errors"]["preflight_incomplete"])

    def _require_active(self, step):
        self._require_configured()
        self._require_known(step)
        self._require_preflight()
        status = self._status(step)
        if status == "done":
            raise EngineError("step_done", "This step is already done.")
        if status == "locked":
            lesson = self._lesson_blocking(step)
            if lesson is not None:
                raise EngineError("step_locked", self._err("step_needs_lesson", lesson=self.lessons.get(lesson)["title"]))
            raise EngineError("step_locked", "Finish the earlier steps first.")

    def _step(self, step):
        part = self._part_of(step)
        steps = self._progress_of(part)["steps"]
        if step not in steps:
            steps[step] = store.default_step_entry(step)  # a step only one track has
        return steps[step]

    def _text(self, step):
        """The step's guidance for this participant's track: shared text with the track's own lines on top."""
        base = self.content["steps"][step]
        override = base.get("tracks", {}).get(self._track()) if self._track() != "script" else None
        if not override:
            return base
        merged = dict(base)
        for key, value in override.items():
            merged[key] = _deep_merge(base.get(key), value)
        return merged

    def _track(self):
        """The project's track: fixed once a step is finished, otherwise the one chosen in the preflight."""
        if self.progress is not None and self.progress["done"]:
            return self.progress.get("track") or "script"
        return self.preflight.track

    def _track_locked(self):
        return self.progress is not None and bool(self.progress["done"])

    def _part_of(self, item_id):
        """The Part an id belongs to. An id no Part owns is treated as Part 3's, as before."""
        return store.part_of(item_id) or store.PART_3

    def _progress_of(self, part, create=True):
        """The saved block holding a Part's `done` and `steps`: the progress file itself for Part 3, else `parts.<id>`."""
        if part.progress_key is None:
            return self.progress
        parts = self.progress["parts"]
        if part.progress_key not in parts:
            if not create:
                return store.new_part_progress(part)
            parts[part.progress_key] = store.new_part_progress(part)
        return parts[part.progress_key]

    def _done_of(self, part):
        return self._progress_of(part, create=False)["done"] if self.progress is not None else []

    def _steps(self, part=None):
        if part is None or part.progress_key is None:
            return store.step_ids(self._track())
        return part.step_ids_for(self._track())

    def _course(self, part=None):
        if part is None or part.progress_key is None:
            return store.course_items(self._track())
        return part.course_for(self._track())

    def _kind_call(self, step, action, *args):
        """Run a step's registered kind handler for `action`. Returns NOT_KIND when the step has no kind (the Part 3 path)."""
        kind = self.content["steps"].get(step, {}).get("kind")
        if kind is None:
            return NOT_KIND
        method = getattr(store.STEP_KINDS[kind], action, None)
        if method is None:
            raise EngineError("not_supported", "This step does not do that.")
        return method(self, step, *args)

    def _checker(self):
        """The file that holds this track's checks."""
        return self.paths.checker(self._track())

    def _model_name(self):
        """The model saved in the generate step as one plain line: whitespace and control characters become single spaces."""
        return re.sub(r"[\s\x00-\x1f\x7f-\x9f]+", " ", self._step("generate")["model_name"]).strip()

    def _step_line(self, step):
        """(line to type, reason it cannot be sent or None). Only lines with a template hold the model name."""
        text = self._text(step)
        if text.get("line_template"):
            model = self._model_name()
            cli = self._live_cli_id(text) if step == LIVE else ""
            if step == LIVE and not cli:
                cli = "<" + " | ".join(c["id"] for c in text["clis"]) + ">"
            if not model:
                return text["line_template"].format(model="<model>", cli=cli), text["model_missing"]
            return text["line_template"].format(model=model, cli=cli), None
        return text.get("line"), None

    def _live_cli_id(self, text):
        """The CLI the participant chose for live mode, when it is one of the options in the content."""
        chosen = self._step(LIVE)["cli"]
        return chosen if chosen in [c["id"] for c in text["clis"]] else ""

    def _live_not_ready(self):
        """(error code, plain message) while live mode may not start or send, otherwise None."""
        text, s = self._text(LIVE), self._step(LIVE)
        if s["acknowledged"] is not True:
            return "warning_not_acknowledged", text["messages"]["not_acknowledged"]
        if not self._live_cli_id(text):
            return "cli_not_chosen", text["messages"]["no_cli"]
        return None

    def _cli_active(self, step):
        return self._cli_step == step and self.terminal.running

    def _cli_env(self):
        """The environment for every CLI, checker and preflight program."""
        self.preflight.python_path = self.python_path
        return self.preflight.env()

    def _preflight_session(self):
        kind = None
        if self._cli_step in PF_SESSIONS and self.terminal.running:
            kind = self._cli_step.split(":", 1)[1]
        return {"kind": kind, "sent": self._sent and kind is not None}

    # --- state -------------------------------------------------------------

    def get_state(self, step=None, part=None):
        with self._lock:
            chosen = store.PART_3
            if part is not None:
                chosen = store.part_by_id(part)
                if chosen is None:
                    raise EngineError("unknown_part", self.content["messages"]["unknown_part"])
            if step is not None:
                self._require_known(step)
                chosen = self._part_of(step)  # a step names its own Part
            p = self.progress
            warnings = list(self._warnings)
            if p is not None:
                self._sync_fix()
                if "onedrive" in p["project_path"].lower():
                    warnings.insert(0, self.content["messages"]["onedrive_warning"])
            passed = self.preflight.is_passed(self.paths)
            course = self._course_list(chosen, passed)
            current_item = next(({"kind": x["kind"], "id": x["id"]} for x in course if x["status"] == "active"), None)
            current = None
            if p is not None and passed and current_item is not None and current_item["kind"] == "step":
                current = current_item["id"]
            selected = step if step is not None else current
            steps = [{"id": s, "title": self._text(s)["title"],
                      "status": self._status(s) if p and passed else "locked"} for s in self._steps(chosen)]
            # Optional extras sit outside `steps` and `course`, so those two keep meaning "the required work".
            optional_steps = []
            if (chosen.progress_key is None and p is not None and passed and self._live_exists(LIVE)
                    and self._live_open()):
                optional_steps.append({"id": LIVE, "title": self._text(LIVE)["title"],
                                       "status": "done" if self._step(LIVE)["done"] else "optional"})
            course_text = self.lesson_text["ui"]
            series_entry = next((x for x in self.series_text["parts"] if x["id"] == chosen.id), None)
            if series_entry is not None and isinstance(series_entry.get("ui"), dict):
                course_text = _deep_merge(course_text, series_entry["ui"])  # a Part's own header, groups and finished text
            if chosen.id in self.part_ui:
                course_text = _deep_merge(course_text, self.part_ui[chosen.id])
            return {
                "configured": p is not None,
                "setup": {
                    "project_path": p["project_path"] if p else "",
                    "cli_command": p["cli_command"] if p else "",
                    "starter": p["starter"] if p else "",
                    "defaults": {"project_path": project.default_project_path(), "cli_command": ""},
                    "warnings": warnings,
                },
                "current_step": current,
                "steps": steps,
                "step": self._step_view(p, passed, selected, step),
                "terminal": self.terminal.status(),
                "preflight": self._preflight_view(),
                "course": course,
                "optional_steps": optional_steps,
                "current_item": current_item,
                "review": self._review_summary(),
                "course_text": course_text,
                "series": self._series_view(passed),
                "settings": self._settings_view(),
            }

    def _course_list(self, part, passed):
        return [{"kind": k, "id": i, "title": self._item_title(k, i), "status": s}
                for k, i, s in self._walk(passed, part)]

    def _series_view(self, passed):
        """The Series map: every Part from series.json, with the course list folded into the Part that has content."""
        if self.lessons is None:
            return None
        parts = []
        for part in self.series_text["parts"]:
            entry = {k: part[k] for k in ("n", "id", "title", "kind", "outcome")}
            registered = store.part_by_id(part["id"]) if part["kind"] == "course" else None
            if registered is not None:
                course = self._course_list(registered, passed)
                counted = [x for x in course if x["status"] in ("done", "skipped")]
                done, total = len(counted), len(course)
                entry["state"] = "done" if total and done == total else ("in_progress" if done else "not_started")
                entry["done"], entry["total"] = done, total
                entry["lessons"] = [{"id": x["id"], "title": x["title"], "status": x["status"]}
                                    for x in course if x["kind"] == "lesson"]
            parts.append(entry)
        return {"title": self.series_text["title"], "ui": self.series_text["ui"], "parts": parts}

    def _step_view(self, progress, passed, selected, requested):
        if progress is not None and passed and selected:
            if selected != LIVE and self._status(selected) == "locked":
                return self._step_preview(selected)  # reading ahead: the words only, never the step's data
            return self._detail(selected)
        if requested is not None and not passed:
            return self._step_preview(requested)  # reading ahead before setup
        return None

    def _held_by(self, item_id):
        """The item of this Part that is still to do, shown in a preview once setup has passed; None before setup."""
        if not self.preflight.is_passed(self.paths):
            return None
        for kind, item, status in self._walk(True, self._part_of(item_id)):
            if status == "active":
                return {"kind": kind, "id": item, "title": self._item_title(kind, item)}
        return None

    def _step_preview(self, step):
        """A step's words with nothing to do in them: shown for any locked step, never starts the CLI, records nothing."""
        text = self._text(step)
        return {"id": step, "title": text["title"], "status": "locked", "preview": True, "track": self._track(),
                "held_by": self._held_by(step),
                "goal": text["goal"], "why": text["why"], "instructions": text["instructions"], "cli": None,
                "checklist": [], "last_check": None, "question": None, "troubleshooting": text["troubleshooting"],
                "ui": text.get("ui", {}), "data": {}}

    def _settings_view(self):
        """What the Settings panel needs: its words and where a reset would put the backup."""
        text = {key: value for key, value in self.settings_text.items() if key != "errors"}
        return {"text": text, "backup_folder": str(self.home / reset_lib.BACKUP_NAME),
                "has_project": self.paths is not None}

    def _preflight_view(self):
        view = self.preflight.view(self.paths, self._preflight_session())
        if self._track_locked():
            # A project with finished steps keeps its track, so the screen shows that one and cannot change it.
            self.preflight.adopt_track(self._track())
            view = self.preflight.view(self.paths, self._preflight_session())
        view["track_locked"] = self._track_locked()
        view["track_locked_note"] = self.preflight.content["track_locked_note"] if self._track_locked() else None
        return view

    def _detail(self, step):
        handled = self._kind_call(step, "detail")
        if handled is not NOT_KIND:
            return handled
        text = self._text(step)
        cli = None
        if text.get("line") or text.get("line_template"):
            line, blocked = self._step_line(step)
            cli = {"line": line, "folder_label": text["folder_label"],
                   "started": self._cli_active(step),
                   "sent": self._cli_active(step) and self._sent,
                   "blocked": blocked}
            if step == LIVE:
                not_ready = self._live_not_ready()
                cli["start_blocked"] = not_ready[1] if not_ready else None
        ticked = self._step(step)["checklist"]
        detail = {
            "id": step,
            "title": text["title"],
            "status": self._status(step),
            "track": self._track(),
            "goal": text["goal"],
            "why": text["why"],
            "instructions": text["instructions"],
            "cli": cli,
            "checklist": [{"id": c["id"], "label": c["label"], "checked": ticked.get(c["id"]) is True}
                          for c in text.get("checklist", [])],
            "last_check": self._step(step)["last_check"],
            "question": self._step_question_public(step),
            "troubleshooting": text["troubleshooting"],
            "ui": text.get("ui", {}),
            "data": getattr(self, "_data_" + step.replace("-", "_"))(),
        }
        if step == LIVE:
            detail["optional"] = True
        return detail

    def _parsed_criteria(self):
        items = parsers.parse_test_cases(gates.read_text(self.paths.test_cases))
        return [{"id": c["id"], "name": c["name"]} for c in items]

    def _data_generate(self):
        runs = []
        for n in range(1, gates.RUNS + 1):
            text = gates.read_text(self.paths.run_file(n))
            done = bool(text.strip())
            runs.append({"n": n, "done": done, "words": len(text.split()) if done else 0})
        return {"runs": runs, "current_run": self._next_run() or gates.RUNS,
                "model_name": self._step("generate")["model_name"]}

    def _next_run(self):
        for n in range(1, gates.RUNS + 1):
            if not gates.has_text(self.paths.run_file(n)):
                return n
        return None

    def _data_build(self):
        track = self._track()
        return {"checker_exists": self._checker().is_file(),
                "first_look": self._load_result("first_look"),
                "scan": gates.scan_messages(self.paths, track)}

    def _data_fixtures_config(self):
        p = self.paths
        names = gates.config_test_names(p)
        return {"config_exists": p.config_yaml.is_file(),
                "tests": [{"name": name, "present": name in names} for name in gates.FIXTURE_TESTS],
                "scan": gates.scan_messages(p, "promptfoo"),
                "fixtures_ready": all(gates.has_text(p.fixtures / n) for n in project.FIXTURE_NAMES)}

    def _data_fixtures(self):
        p = self.paths
        return {"files": [{"name": name, "present": gates.has_text(p.work_fixtures / name)
                           or gates.has_text(p.fixtures / name)} for name in project.FIXTURE_NAMES],
                "example": {"offered": self.progress.get("starter") == "northwind",
                            "would_replace": self._work_fixtures_have_text()}}

    def _data_key(self):
        p = self.paths
        key_held = p.sealed_key.is_file()
        return {"files": [{"name": project.KEY_NAME, "present": gates.has_text(p.key_work_key) or key_held}],
                "key_held": key_held}

    def _data_readback(self):
        s = self._step("readback")
        return {"criteria": [dict(c, answer=s["answers"].get(c["id"])) for c in self._parsed_criteria()],
                "note": s["note"]}

    def _predict_rows(self):
        s = self._step("predict")
        if s["locked"]:
            return s["locked_criteria"], not self._parsed_criteria()
        parsed = self._parsed_criteria()
        return (parsed, False) if parsed else (s["manual_criteria"], True)

    def _data_predict(self):
        s = self._step("predict")
        rows, manual = self._predict_rows()
        return {"locked": s["locked"], "manual_rows": manual, "criteria": rows,
                "bad": s["bad"], "polished": s["polished"], "answers": s["answers"],
                "polished_text": gates.read_text(self.paths.fixtures / gates.POLISHED_FILE)}

    def _grid(self):
        s = self._step("predict")
        return gates.compute_grid(s["locked_criteria"], s["bad"], s["polished"],
                                  self._load_result("fixtures"))

    def _data_run(self):
        result = self._load_result("fixtures")
        grid = self._grid()
        s = self._step("run")
        valid = set(gates.surprise_keys(grid))
        unlocked = (self._step("predict")["locked"] and gates.is_complete_run(result)
                    and self.paths.sealed_key.is_file())
        return {
            "result": result,
            "grid": grid,
            "classifications": {k: v for k, v in s["classifications"].items() if k in valid},
            "answer_key_markdown": gates.read_text(self.paths.sealed_key) if unlocked else None,
            "polished_passed_all": gates.polished_passed_all(result) if result else False,
        }

    def _fix_facts(self):
        f = self._step("fix")
        tc_hash = gates.file_sha256(self.paths.test_cases)
        check_hash = gates.file_sha256(self._checker())
        tc_changed = f["start_tc_hash"] is not None and tc_hash != f["start_tc_hash"]
        rerun = self._load_result("rerun")
        return {
            "test_cases_changed": tc_changed,
            "checker_changed_after": tc_changed and f["tc_edit_check_hash"] is not None
                and check_hash != f["tc_edit_check_hash"],
            "checker_edited_only": f["start_check_hash"] is not None
                and check_hash != f["start_check_hash"] and not tc_changed,
            "rerun": rerun,
            "rerun_fresh": gates.is_complete_run(rerun) and f["rerun_check_hash"] == check_hash
                and f["rerun_tc_hash"] == tc_hash,
        }

    def _data_fix(self):
        facts = self._fix_facts()
        run_result = self._load_result("fixtures")
        no_surprises = gates.is_complete_run(run_result) and not gates.surprise_keys(self._grid())
        return {
            "test_cases_text": gates.read_text(self.paths.test_cases),
            "test_cases_changed": facts["test_cases_changed"],
            "checker_changed_after": facts["checker_changed_after"],
            "rerun": facts["rerun"],
            "polished_fails": gates.polished_fails(facts["rerun"]),
            "explanation": self._step("fix")["explanation"],
            "can_skip": no_surprises and gates.polished_fails(run_result),
        }

    def _baseline_facts(self):
        """The app's own run on the five runs, and whether it still matches the files on disk."""
        saved = self._load_result("baseline")
        result = saved.get("result") if saved else None
        summary = saved.get("summary") if saved else None
        b = self._step("baseline")
        fresh = (gates.is_complete_run(result) and summary is not None
                 and b["run_check_hash"] == gates.file_sha256(self._checker())
                 and b["run_runs_hash"] == baseline.runs_hash(self.paths))
        return {"result": result, "summary": summary, "fresh": fresh}

    def _data_baseline(self):
        facts = self._baseline_facts()
        runs = [{"n": n, "done": gates.has_text(self.paths.run_file(n))} for n in range(1, gates.RUNS + 1)]
        return {
            "runs": runs,
            "runs_ready": all(r["done"] for r in runs),
            "checker_exists": self._checker().is_file(),
            "model_name": self._step("generate")["model_name"],
            "result": facts["result"],
            "summary": facts["summary"],
            "fresh": facts["fresh"],
            "log_exists": self.paths.iteration_log.is_file(),
        }

    def _data_live(self):
        text, s, p = self._text(LIVE), self._step(LIVE), self.paths
        clis = text["clis"]
        return {
            "clis": clis,
            "cli": self._live_cli_id(text),
            "acknowledged": s["acknowledged"] is True,
            "model_name": self._step("generate")["model_name"],
            "config_exists": p.live_config.is_file(),
            "provider_exists": p.agent_provider.is_file(),
            "provider_ok": gates.provider_is_bundled(p),
            "scan": gates.live_scan_messages(p, [c["id"] for c in clis]),
            "started": s["start_hashes"] is not None,
        }

    def _capture_fix_baseline(self):
        f = self._step("fix")
        f["start_tc_hash"] = gates.file_sha256(self.paths.test_cases)
        f["start_check_hash"] = gates.file_sha256(self._checker())
        f["seen_tc_hash"] = f["start_tc_hash"]
        f["tc_edit_check_hash"] = None

    def _sync_fix(self):
        """Notice edits made to test-cases.md outside the app."""
        if self._status("fix") != "active":
            return
        f = self._step("fix")
        if f["start_tc_hash"] is None:
            self._capture_fix_baseline()
            self._save()
            return
        current = gates.file_sha256(self.paths.test_cases)
        if current == f["seen_tc_hash"]:
            return
        f["seen_tc_hash"] = current
        check_hash = gates.file_sha256(self._checker())
        try:
            checker_is_newer = (self._checker().stat().st_mtime_ns
                                > self.paths.test_cases.stat().st_mtime_ns)
        except OSError:
            checker_is_newer = False
        # Both may have changed since the last look; only file times can order them.
        f["tc_edit_check_hash"] = f["start_check_hash"] if checker_is_newer else check_hash
        self._save()

    # --- importing the participant's own files --------------------------------

    def _review_own(self, body, paths=None):
        """Read and check the participant's own files. Read-only: the sources are never changed.

        Returns (result, data) where data holds the bytes read, so the copy is of exactly what was checked.
        """
        resumed = paths is not None and paths.progress_file.exists()
        destinations = None
        if paths is not None and not resumed:
            destinations = {"prompt": paths.prompt, "test_cases": paths.test_cases}
        result, data = import_checks.review_files(body.get("prompt_path"), body.get("test_cases_path"), destinations)
        if resumed:
            result["warnings"].insert(0, import_checks.project_exists_warning())
        return result, data

    def import_check(self, body):
        """POST /api/setup/import-check: check the two files and say what would go wrong. Changes nothing."""
        project_path = project.clean_path(body.get("project_path", ""))
        paths = project.Paths(self.home, project_path) if project_path and Path(project_path).is_absolute() else None
        result, _ = self._review_own(body, paths)
        return result

    # --- setup -------------------------------------------------------------

    def setup(self, body):
        with self._lock:
            project_path = project.clean_path(body.get("project_path", ""))
            if not project_path:
                raise EngineError("project_path_required", "Enter a folder for your project.")
            try:
                project.validate_project_path(self.home, project_path)
            except project.ProjectError as exc:
                raise EngineError(exc.code, exc.message) from exc
            cli = body.get("cli_command", "")
            cli = cli.strip() if isinstance(cli, str) else ""
            cli = cli or self.preflight.cli_command
            paths = project.Paths(self.home, project_path)

            resume = paths.progress_file.exists()
            progress = None
            if resume:
                try:
                    progress = self._read_progress(paths)
                except (CorruptStateError, OSError) as exc:
                    message = self._corrupt_message(paths)
                    self._warn(message)
                    raise EngineError("corrupt_progress", message) from exc
            if not resume and not cli:
                raise EngineError("cli_required", "Enter the command that starts your AI CLI.")
            if cli:
                try:
                    self.terminal.check_command(cli, self._cli_env())
                except (ValueError, OSError) as exc:
                    raise EngineError("cli_not_found", str(exc)) from exc

            if not resume and "onedrive" in project_path.lower():
                raise EngineError("project_in_onedrive", self.preflight.content["errors"]["project_onedrive_create"])

            if not resume:
                starter = body.get("starter")
                if starter not in STARTERS:
                    raise EngineError("bad_starter", 'Pick either "northwind" or "own" as your starting point.')
                own_data = None
                if starter == "own":
                    review, own_data = self._review_own(body, paths)
                    if review["blocking"]:
                        reading = any(item["code"] in IMPORT_READ_CODES for item in review["blocking"])
                        raise EngineError("missing_file" if reading else "import_blocked",
                                          " ".join(item["message"] for item in review["blocking"]))
                try:
                    project.create_project(paths, starter, body.get("prompt_path"), body.get("test_cases_path"),
                                           own_data)
                except project.ProjectError as exc:
                    raise EngineError(exc.code, exc.message) from exc
                except OSError as exc:
                    raise EngineError("project_write_failed", f"The project folder could not be written: {exc}") from exc
                progress = store.new_progress(project_path, cli, starter)
            elif cli:
                progress["cli_command"] = cli

            if self._cli_step not in PF_SESSIONS:  # a preflight session stays open until preflight passes
                self._stop_cli()
            if self.lessons is not None:
                self._adopt_pending(progress)
            self.paths = paths
            self.progress = progress
            self._review_sitting = None
            self._review_postponed = False
            self._warnings = []
            self._save()
            store.write_json_atomic(self._settings_path(), {"last_project": project_path})
            self.preflight.adopt_cli_command(progress.get("cli_command", ""))
            if self._track_locked():
                self.preflight.adopt_track(self._track())
            self.preflight.check_project(self.paths)
            self._after_preflight_change()

    # --- preflight -----------------------------------------------------------

    def _after_preflight_change(self):
        """Once preflight passes, a preflight CLI session should not stay open."""
        if self._cli_step in PF_SESSIONS and self.preflight.is_passed(self.paths):
            self._stop_cli()

    @_preflight_errors
    def preflight_track(self, track):
        with self._lock:
            if self._track_locked() and track != self._track():
                raise EngineError("track_locked", self.preflight.content["errors"]["track_locked"])
            self.preflight.set_track(track)
            self._after_preflight_change()

    @_preflight_errors
    def preflight_skip(self):
        """Skip setup for now. It is remembered across launches until the configuration is reset."""
        with self._lock:
            self.preflight.skip_setup()

    @_preflight_errors
    def preflight_check(self):
        self._cli_env()
        self.preflight.start_check_all()

    @_preflight_errors
    def preflight_install(self, item, consent):
        self._cli_env()
        self.preflight.start_install(item, consent)

    @_preflight_errors
    def preflight_cli(self, command):
        with self._lock:
            self._cli_env()
            self.preflight.set_cli_command(command)
            if self.progress is not None and self.preflight.command_usable():
                self.progress["cli_command"] = self.preflight.cli_command
                self._save()

    def _start_preflight_session(self, command, cwd, label, session):
        try:
            self.terminal.start(command, str(cwd), label, env=self._cli_env(), owner=session)
        except (ValueError, OSError) as exc:
            self._cli_step = None
            return exc
        except (ValueError, OSError) as exc:
            self._cli_step = None
            return exc
        self._cli_step = session
        self._sent = False
        return None

    @_preflight_errors
    def preflight_cli_start(self):
        """Item 5: start the CLI in the terminal, so the participant can sign in (item 6)."""
        with self._lock:
            command = self.preflight.require_cli_ready()
            self._stop_cli()
            folder = self.home / "cli-signin"
            project.clear_dir(folder)
            label = self.preflight.content["session_labels"]["signin"]
            error = self._start_preflight_session(command, folder, label, PF_SIGNIN)
            if error is not None:
                self.preflight.cli_start_failed(error)
                return
            self.preflight.cli_launched(command)

    @_preflight_errors
    def preflight_signin_confirm(self):
        with self._lock:
            self.preflight.confirm_signin()

    @_preflight_errors
    def preflight_recipe(self, recipe_id, consent):
        with self._lock:
            if self.preflight.job_running():
                raise PreflightError("job_busy", self.preflight.content["errors"]["job_busy"])
            argv = self.preflight.recipe_argv(recipe_id, consent)
            self._stop_cli()
            folder = self.home / "cli-install"
            project.clear_dir(folder)
            label = self.preflight.content["session_labels"]["recipe"]
            error = self._start_preflight_session(argv, folder, label, PF_RECIPE)
            if error is not None:
                m = self.preflight.content["messages"]["cli_start_failed"]
                raise EngineError("cli_start_failed", f"{m['detail'].format(error=error)} {m['next']}")
            self.preflight.mark_recipe_ran()

    @_preflight_errors
    def preflight_test_start(self):
        with self._lock:
            command = self.preflight.require_test_ready()
            self._stop_cli()
            folder = self.preflight.prepare_test_folder()
            label = self.preflight.content["working_test"]["terminal_label"]
            error = self._start_preflight_session(command, folder, label, PF_TEST)
            if error is not None:
                self.preflight.cli_start_failed(error)

    @_preflight_errors
    def preflight_test_send(self):
        with self._lock:
            if not self._cli_active(PF_TEST):
                raise PreflightError("no_session", self.preflight.content["errors"]["no_session"])
            line = self.preflight.test_line
        try:
            self.terminal.type_line(line)
        except OSError as exc:
            raise EngineError("cli_not_running", self.preflight.content["errors"]["type_failed"].format(error=exc)) from exc
        with self._lock:
            if self._cli_active(PF_TEST):
                self._sent = True

    @_preflight_errors
    def preflight_test_check(self):
        with self._lock:
            passed = self.preflight.check_test_result()
            if passed and self._cli_step == PF_TEST:
                self._stop_cli()  # that chat was only for the test
            self._after_preflight_change()

    @_preflight_errors
    def preflight_stop(self):
        with self._lock:
            if self._cli_step in PF_SESSIONS:
                self._stop_cli()

    # --- resets --------------------------------------------------------------

    def reset_progress(self, confirm):
        """POST /api/reset/progress: start the course again, keeping setup and the starting files."""
        return self._reset(False, confirm)

    def reset_configuration(self, confirm):
        """POST /api/reset/configuration: return the app to its first-run state."""
        return self._reset(True, confirm)

    def _reset(self, configuration, confirm):
        text = self.settings_text
        errors = text["errors"]
        if confirm is not True:
            raise EngineError("confirm_required", errors["confirm_required"])
        with self._lock:
            if self.preflight.job_running():
                raise EngineError("job_busy", errors["job_busy"])
            self._stop_cli()
            paths = self.paths
            kind = "configuration" if configuration else "progress"
            words = text["reset"][kind]
            if paths is None and not configuration:
                self._discard_pending()
                return {"kind": kind, "backup_folder": None, "message": words["done_no_backup"]}
            plan = reset_lib.build_plan(self.home, paths, configuration)
            staging = self.home / reset_lib.STAGING_NAME
            done = []
            try:
                done = reset_lib.stage(plan, staging, text)
                if done:
                    reset_lib.swap_backup(self.home, staging)
                else:
                    reset_lib.remove_tree_quietly(staging)
            except reset_lib.ResetError as exc:
                raise EngineError(exc.code, exc.message) from exc
            except OSError as exc:
                reset_lib.rollback(done, staging)
                reset_lib.remove_tree_quietly(staging)
                raise EngineError("reset_failed", errors["reset_failed"].format(error=exc)) from exc
            backup = self.home / reset_lib.BACKUP_NAME
            error = self._finish_reset(paths, configuration, errors)
            if done:
                try:
                    reset_lib.remove_keys(backup)
                except OSError as exc:
                    raise EngineError("key_failed", errors["key_failed"].format(error=exc)) from exc
            if error is not None:
                raise error
            message = words["done"].format(folder=str(backup)) if done else words["done_no_backup"]
            return {"kind": kind, "backup_folder": str(backup) if done else None, "message": message}

    def _discard_pending(self):
        """Clear course progress held outside a project (kept by earlier versions of the app)."""
        try:
            self._pending_path().unlink()
        except OSError:
            pass
        self._pending_block = None
        self._review_sitting = None
        self._review_postponed = False

    def _finish_reset(self, paths, configuration, errors):
        """Rebuild the in-memory state and the empty course folders. Returns an error to raise afterwards, or None."""
        self._pending_block = None
        self._review_sitting = None
        self._review_postponed = False
        self._warnings = []
        if configuration:
            if paths is not None:
                reset_lib.prune_empty(paths.project, reset_lib.PROJECT_FOLDER_CONTENTS
                                      + (reset_lib.PROJECT_SKILLS_DIR, reset_lib.PROJECT_PART1_DIR,
                                         reset_lib.PROJECT_PART2_DIR))
            self.paths = None
            self.progress = None
            self.preflight.reset_state()
            return None
        old = self.progress
        try:
            for folder in (paths.learning, paths.runs, paths.fixtures, paths.examples):
                folder.mkdir(parents=True, exist_ok=True)
            fresh = store.new_progress(old["project_path"], old["cli_command"], old["starter"])
            self.progress = fresh
            self._save()
        except OSError as exc:
            self.progress = store.new_progress(old["project_path"], old["cli_command"], old["starter"])
            return EngineError("reset_scaffold_failed", errors["scaffold_failed"].format(error=exc))
        self.preflight.check_project(paths)
        return None

    # --- CLI control -------------------------------------------------------

    def _cancel_watcher(self):
        if self._watcher_cancel is not None:
            self._watcher_cancel.set()
            self._watcher_cancel = None

    def _stop_cli(self):
        self._cancel_watcher()
        self.terminal.stop()
        self._cli_step = None
        self._sent = False

    def _prepare_folder(self, step):
        if step == "generate":
            project.prepare_blind(self.paths)
            return self.paths.blind
        if step == "fixtures":
            project.prepare_fixtures_work(self.paths)
            return self.paths.fixtures_work
        if step == "key":
            project.prepare_key_work(self.paths)
            return self.paths.key_work
        return self.paths.project

    def step_start(self, step):
        handled = self._kind_call(step, "start")
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            self._require_active(step)
            text = self._text(step)
            if not (text.get("line") or text.get("line_template")):
                raise EngineError("no_cli", "This step does not use your CLI.")
            if step == LIVE:
                self._require_live_ready()
            run_n = None
            if step == "generate":
                run_n = self._next_run()
                if run_n is None:
                    raise EngineError("runs_complete", "All five runs are saved.")
            self._stop_cli()
            try:
                cwd = self._prepare_folder(step)
            except project.ProjectError as exc:
                raise EngineError(exc.code, exc.message) from exc
            except OSError as exc:
                raise EngineError("folder_busy", f"The working folder could not be prepared: {exc}") from exc
            label = text["title"] if run_n is None else f"{text['title']}: run {run_n} of {gates.RUNS}"
            try:
                self.terminal.start(self.progress["cli_command"], str(cwd), label, env=self._cli_env(), owner=step)
            except (ValueError, OSError) as exc:
                raise EngineError("cli_start_failed", f"Your CLI could not be started: {exc}") from exc
            self._cli_step = step
            self._sent = False
            if step == LIVE and self._step(LIVE)["start_hashes"] is None:
                # Noted once, before the CLI can touch anything, so the gate can tell whether these files changed.
                self._step(LIVE)["start_hashes"] = gates.live_start_hashes(self.paths)
                self._save()
            if run_n is not None:
                self._start_watcher(self.paths.blind_output, self.paths.run_file(run_n))

    def _require_live_ready(self):
        not_ready = self._live_not_ready()
        if not_ready:
            raise EngineError(not_ready[0], not_ready[1])

    def step_send(self, step):
        handled = self._kind_call(step, "send")
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            self._require_active(step)
            line, blocked = self._step_line(step)
            if not line:
                raise EngineError("no_cli", "This step does not use your CLI.")
            if step == LIVE:
                self._require_live_ready()
            if blocked:
                raise EngineError("no_model", blocked)
            if not self._cli_active(step):
                raise EngineError("cli_not_running", "Start your CLI first.")
        try:
            self.terminal.type_line(line)  # outside the lock: it takes 400 ms
        except OSError as exc:
            raise EngineError("cli_not_running", f"The line could not be typed: {exc}") from exc
        with self._lock:
            if self._cli_active(step):
                self._sent = True

    def step_stop(self, step):
        with self._lock:
            self._require_configured()
            self._require_known(step)
            self._stop_cli()

    def terminal_release(self):
        """The page moved to a section that does not own the terminal: stop any CLI and clear what it left."""
        with self._lock:
            self._stop_cli()
            self.terminal.release()

    def step_use_example_fixtures(self, step, replace=None):
        """Recovery for the fixtures step: write the Northwind example's two fixtures where the CLI would have.

        The normal gate then runs unchanged. Only the Northwind starter can use this, and no answer key is written.
        """
        handled = self._kind_call(step, "use_example_fixtures", replace)
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            self._require_active(step)
            messages = self.content["messages"]
            if step != "fixtures":
                raise EngineError("no_example_fixtures", messages["example_fixtures_wrong_step"])
            if self.progress.get("starter") != "northwind":
                raise EngineError("example_fixtures_northwind_only", messages["example_fixtures_own_project"])
            if self.terminal.running:
                raise EngineError("cli_running", messages["example_fixtures_cli_running"])
            if replace is not None and not isinstance(replace, bool):
                raise EngineError("bad_input", "The replace field must be true or false.")
            if self._work_fixtures_have_text() and replace is not True:
                raise EngineError("confirm_replace", messages["example_fixtures_confirm_replace"])
            try:
                project.write_example_fixtures(self.paths)
            except OSError as exc:
                raise EngineError("folder_busy", messages["example_fixtures_write_failed"].format(error=exc)) from exc

    def _work_fixtures_have_text(self):
        return any(gates.has_text(self.paths.work_fixtures / name) for name in project.FIXTURE_NAMES)

    def terminal_input(self, data):
        if not isinstance(data, str):
            raise EngineError("bad_input", "Terminal input must be base64 text.")
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as exc:
            raise EngineError("bad_input", "Terminal input must be base64 text.") from exc
        if raw:
            self.terminal.write(raw)

    def terminal_resize(self, cols, rows):
        for value in (cols, rows):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise EngineError("bad_input", "Terminal size must be two positive whole numbers.")
        self.terminal.resize(cols, rows)

    def shutdown(self):
        with self._lock:
            self._stop_cli()
        self.preflight.shutdown()

    # --- generate watcher --------------------------------------------------

    def _start_watcher(self, source, destination):
        cancel = threading.Event()
        self._watcher_cancel = cancel
        threading.Thread(target=self._watch_output, args=(self.paths, source, destination, cancel), daemon=True).start()

    def _watch_output(self, paths, source, destination, cancel):
        """Wait until output.txt is non-empty and unchanged across two polls."""
        previous, unchanged = None, 0
        while not cancel.wait(self.poll_interval):
            data = None
            try:
                with open(str(source), "rb") as f:
                    data = f.read()
            except OSError:
                pass
            if not data or not data.decode("utf-8-sig", errors="replace").strip():
                previous, unchanged = None, 0
                continue
            if data != previous:
                previous, unchanged = data, 0
                continue
            unchanged += 1
            if unchanged >= 2:
                self._finish_run(paths, destination, data, cancel)
                return

    def _finish_run(self, paths, destination, data, cancel):
        with self._lock:
            if cancel.is_set() or self.paths is not paths:
                return
            store.write_bytes_atomic(destination, data)
            self._watcher_cancel = None
            self.terminal.stop()
            self._cli_step = None
            self._sent = False
            self._save()
        self.terminal.publish_state()

    # --- submit ------------------------------------------------------------

    def step_submit(self, step, data):
        handled = self._kind_call(step, "submit", data)
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            self._require_configured()
            self._require_known(step)
            if not isinstance(data, dict):
                raise EngineError("bad_input", "The submitted data must be an object.")
            if step == "predict" and self._step("predict")["locked"]:
                raise EngineError("locked", "Your predictions are locked and cannot be changed.")
            self._require_active(step)
            handler = getattr(self, "_submit_" + step.replace("-", "_"), None)
            has_checklist = bool(self._text(step).get("checklist"))
            if handler is None and not has_checklist:
                raise EngineError("bad_input", "This step has nothing to save.")
            if has_checklist and "checklist" in data:
                self._save_checklist(step, data["checklist"])
            if handler is not None:
                handler(data)
            self._save()

    def _save_checklist(self, step, items):
        if not isinstance(items, dict):
            raise EngineError("bad_input", "The checklist must be an object.")
        known = {c["id"] for c in self._text(step)["checklist"]}
        for item_id, value in items.items():
            if item_id not in known or not isinstance(value, bool):
                raise EngineError("bad_input", f"Unknown checklist item: {item_id!r}.")
        self._step(step)["checklist"].update(items)

    def _submit_generate(self, data):
        if "model_name" in data:
            self._step("generate")["model_name"] = self._text_value(data["model_name"], "model_name")

    def _submit_baseline(self, data):
        # The model name has one home, the generate step's record, so the typed line and the log agree.
        if "model_name" in data:
            self._step("generate")["model_name"] = self._text_value(data["model_name"], "model_name")

    def _submit_live(self, data):
        s = self._step(LIVE)
        if "acknowledged" in data:
            if not isinstance(data["acknowledged"], bool):
                raise EngineError("bad_input", "The acknowledgement must be true or false.")
            s["acknowledged"] = data["acknowledged"]
        if "cli" in data:
            known = [c["id"] for c in self._text(LIVE)["clis"]]
            if data["cli"] != "" and data["cli"] not in known:
                raise EngineError("bad_input", "Choose one of the CLIs in the list.")
            s["cli"] = data["cli"]
        if "model_name" in data:
            self._step("generate")["model_name"] = self._text_value(data["model_name"], "model_name")

    def _submit_readback(self, data):
        s = self._step("readback")
        answers = data.get("answers", {})
        if not isinstance(answers, dict):
            raise EngineError("bad_input", "Answers must be an object.")
        known = {c["id"] for c in self._parsed_criteria()}
        for cid, value in answers.items():
            if cid not in known:
                raise EngineError("bad_input", f"Unknown criterion: {cid!r}.")
            if value is None:
                s["answers"].pop(cid, None)
                continue
            value = value.strip().lower() if isinstance(value, str) else value
            if value not in ("yes", "no"):
                raise EngineError("bad_input", "Each answer must be Yes or No.")
            s["answers"][cid] = value
        if "note" in data:
            s["note"] = self._text_value(data["note"], "note")

    def _submit_predict(self, data):
        s = self._step("predict")
        if "criteria" in data and not self._parsed_criteria():
            s["manual_criteria"] = self._clean_criteria(data["criteria"])
        rows, _ = self._predict_rows()
        known = {r["id"] for r in rows}
        for field in ("bad", "polished"):
            if field in data:
                self._merge_cells(s[field], data[field], known)
        answers = data.get("answers", {})
        if not isinstance(answers, dict):
            raise EngineError("bad_input", "Answers must be an object.")
        for key in ANSWER_FIELDS:
            if key in answers:
                s["answers"][key] = self._text_value(answers[key], key)
        if data.get("lock") is True:
            if gates.predict_missing(rows, s) or gates.predict_answers_missing(s) or not rows:
                self._save()  # keep what was entered
                raise EngineError("predict_incomplete", "Fill every cell and all three answers before you lock.")
            s["locked"] = True
            s["locked_criteria"] = [dict(r) for r in rows]

    def _clean_criteria(self, items):
        if not isinstance(items, list):
            raise EngineError("bad_input", "Criteria must be a list.")
        cleaned, seen = [], set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise EngineError("bad_input", "Each criterion needs an id such as C1.")
            cid = item["id"].strip().upper()
            if not _ID_RE.match(cid) or cid in seen:
                raise EngineError("bad_input", f"Use a unique id such as C1, not {item['id']!r}.")
            seen.add(cid)
            name = item.get("name", "")
            cleaned.append({"id": cid, "name": name.strip() if isinstance(name, str) else ""})
        return cleaned

    def _merge_cells(self, target, cells, known):
        if not isinstance(cells, dict):
            raise EngineError("bad_input", "Predictions must be an object.")
        for cid, verdict in cells.items():
            if cid not in known:
                raise EngineError("bad_input", f"Unknown criterion: {cid!r}.")
            if verdict is None:
                target.pop(cid, None)
                continue
            if verdict not in gates.VERDICTS:
                raise EngineError("bad_input", "Each prediction must be P, F or NC.")
            target[cid] = verdict

    def _submit_run(self, data):
        items = data.get("classifications", {})
        if not isinstance(items, dict):
            raise EngineError("bad_input", "Classifications must be an object.")
        for key, value in items.items():
            if not _CLASS_KEY_RE.match(key) or value not in gates.CLASSES:
                raise EngineError("bad_input", f"Unknown classification for {key!r}.")
        self._step("run")["classifications"].update(items)

    def _submit_fix(self, data):
        f = self._step("fix")
        if "test_cases_text" in data:
            text = data["test_cases_text"]
            if not isinstance(text, str) or not text.strip():
                raise EngineError("bad_input", "test-cases.md cannot be empty.")
            if gates.read_text(self.paths.test_cases) != text:
                store.write_bytes_atomic(self.paths.test_cases, text.encode("utf-8"))
                f["seen_tc_hash"] = gates.file_sha256(self.paths.test_cases)
                f["tc_edit_check_hash"] = gates.file_sha256(self._checker())
        if "explanation" in data:
            f["explanation"] = self._text_value(data["explanation"], "explanation")

    @staticmethod
    def _text_value(value, field):
        if not isinstance(value, str):
            raise EngineError("bad_input", f"{field} must be text.")
        return value

    # --- run checker -------------------------------------------------------

    def step_run_checker(self, step, which):
        """Validate under the lock, run the checker outside it, then store the result."""
        handled = self._kind_call(step, "run_checker", which)
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            self._require_active(step)
            if self._checker_running:
                raise EngineError("checker_busy", "Your checker is still running. Wait for it to finish.")
            if step == "build" and which == "first_look":
                files = ["runs/run-1.txt"]
                name = "first_look"
            elif step in ("run", "fix") and which == "fixtures":
                if step == "run" and not self._step("predict")["locked"]:
                    raise EngineError("predictions_not_locked", "Lock your predictions before you run the checker.")
                files = ["fixtures/" + n for n in project.FIXTURE_NAMES]
                name = "fixtures" if step == "run" else "rerun"
            elif step == "baseline" and which == "baseline":
                files = baseline.run_names()
                name = "baseline"
            else:
                raise EngineError("bad_input", f"This step cannot run {which!r}.")
            track = self._track()
            if not self._checker().is_file():
                raise EngineError("no_checker", f"{self._checker().name} was not found in your project folder.")
            problems = gates.scan_messages(self.paths, track)
            if problems:
                raise EngineError("scan_failed", " ".join(p["message"] for p in problems))
            missing = [f for f in files if not gates.has_text(self.paths.project / f)]
            if missing:
                if step == "baseline":
                    raise EngineError("missing_file", self._text("baseline")["messages"]["missing_runs"].format(
                        files=", ".join(missing)))
                raise EngineError("missing_file", "Not found or empty: " + ", ".join(missing))
            paths = self.paths
            env = self._cli_env()
            # Only the promptfoo track needs a way to start npx and a test-name prefix to summarize.
            options = {"npx_argv": self.preflight.npx_argv(env), "runner": self.preflight.runner,
                       "python": self.python_path} if track == "promptfoo" else {}
            prefix = {"first_look": "run-1", "fixtures": "fixture-"}.get(which)
            # Hashed before the run, so a file changed mid-run cannot look fresh later.
            check_hash = gates.file_sha256(self._checker())
            tc_hash = gates.file_sha256(paths.test_cases)
            runs_hash = baseline.runs_hash(paths)
            self._checker_running = True
        try:
            # Outside the lock: a hung checker must not block /api/state for 30 seconds.
            if step == "baseline":
                result = baseline.run_checks(paths.project, track, env=env, **options)
            elif track == "promptfoo":
                result = promptfoo.run_selection(paths.project, prefix, files, env, **options)
            else:
                result = runner.run_checker(paths.project, files, env=env)
        finally:
            with self._lock:
                self._checker_running = False
        with self._lock:
            if self.paths is not paths or self._status(step) != "active":
                raise EngineError("checker_stale", "That checker run was for an earlier state, so it was not saved.")
            if step == "baseline":
                self._save_result(name, {"track": track, "result": result, "summary": baseline.summarize(result)})
                b = self._step("baseline")
                b["run_check_hash"] = check_hash
                b["run_runs_hash"] = runs_hash
            else:
                self._save_result(name, result)
            if step == "fix":
                f = self._step("fix")
                f["rerun_check_hash"] = check_hash
                f["rerun_tc_hash"] = tc_hash
            self._save()

    # --- gates -------------------------------------------------------------

    def step_check(self, step):
        handled = self._kind_call(step, "check")
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            self._require_active(step)
            if self._checker_running:
                raise EngineError("checker_busy", "Your checker is still running. Wait for it to finish, then check your work.")
            s = self._step(step)
            report = gates.Report(self._text(step)["gate"])
            if step == "generate":
                result = gates.check_generate(self.paths, s, report)
            elif step == "build":
                ids = [c["id"] for c in self._text("build").get("checklist", [])]
                result = gates.check_build(self.paths, s, ids, self._load_result("first_look"), report, self._track())
            elif step == "fixtures":
                result = gates.check_fixtures(self.paths, report)
            elif step == "fixtures-config":
                result = gates.check_fixtures_config(self.paths, report)
            elif step == "readback":
                result = gates.check_readback(self.paths, s, self._parsed_criteria(), report)
            elif step == "predict":
                rows, _ = self._predict_rows()
                result = gates.check_predict(s, rows, report)
            elif step == "key":
                result = gates.check_key(self.paths, report)
            elif step == "run":
                result = gates.check_run(s, self._grid(), self._load_result("fixtures"), report)
            elif step == "baseline":
                result = gates.check_baseline(self.paths, self._baseline_facts(), report)
            elif step == LIVE:
                result = gates.check_live(self.paths, s, [c["id"] for c in self._text(LIVE)["clis"]], report)
            else:
                self._sync_fix()
                result = gates.check_fix(self.paths, s, self._fix_facts(), report, self._track())
            s["last_check"] = result
            if result["ok"]:
                if step == "fixtures":
                    self._stop_cli()  # that chat is finished; it should not stay open
                    try:
                        stray = project.finish_fixtures(self.paths)
                    except OSError as exc:
                        self._save()
                        raise EngineError("seal_failed", f"The fixtures could not be saved: {exc}") from exc
                    if stray:
                        result["nudges"].append(self._text("fixtures")["gate"]["nudge_stray_key"]["text"])
                elif step == "key":
                    self._stop_cli()  # that chat wrote the key; it should not stay open
                    try:
                        project.seal_key(self.paths)
                    except OSError as exc:
                        self._save()
                        raise EngineError("seal_failed", f"The answer key could not be sealed: {exc}") from exc
                elif step in ("baseline", "fixtures-config", LIVE):
                    self._stop_cli()  # that chat wrote its file; it should not stay open
                if step == LIVE:
                    s["done"] = True  # not part of the step order: nothing else changes
                else:
                    self._mark_done(step)
            self._save()

    def _mark_done(self, step):
        part = self._part_of(step)
        if part.progress_key is not None:
            self._progress_of(part)["done"].append(step)
            return
        if not self.progress["done"]:
            self.progress["track"] = self._track()  # the first finished step fixes the project's track
        self.progress["done"].append(step)
        if step == "predict" and self.paths.sealed_key.is_file():
            # Only progress from before the key step can reach this with a key already sealed.
            self.progress["done"].append("key")
        elif step == "key":
            # A key may be read only after a run that took place with this key in place.
            try:
                self._result_path("fixtures").unlink()
            except OSError:
                pass
        elif step == "run":
            self._capture_fix_baseline()

    def step_skip(self, step):
        handled = self._kind_call(step, "skip")
        if handled is not NOT_KIND:
            return handled
        with self._lock:
            if step != "fix":
                raise EngineError("cannot_skip", "Only the fix step can be skipped.")
            self._require_active(step)
            if not self._data_fix()["can_skip"]:
                raise EngineError("cannot_skip", "You can skip this step only if there were no surprises "
                                                 "and the polished fixture already failed at least one criterion.")
            self.progress["skipped"] = True
            self._mark_done(step)
            self._save()

    # --- course ------------------------------------------------------------

    def _err(self, code, **fields):
        text = self.lesson_text["errors"][code]
        return text.format(**fields) if fields else text

    def _pending_path(self):
        return self.home / "pending-lessons.json"

    def _read_pending(self):
        try:
            data = store.read_json(self._pending_path())
        except (FileNotFoundError, CorruptStateError, OSError):
            return store.new_lessons_block()
        block = store.new_lessons_block()
        if isinstance(data, dict):
            block.update({k: v for k, v in data.items() if k in block})
            store.prune_lessons_block(block)
        return block

    def _lessons_block(self):
        if self.progress is not None:
            return self.progress["lessons"]
        if self._pending_block is None:
            self._pending_block = self._read_pending()
        return self._pending_block

    def _save_lessons(self):
        if self.progress is not None:
            self._save()
        else:
            store.write_json_atomic(self._pending_path(), self._lessons_block())

    def _seed(self):
        """The participant's shuffle seed, saved the first time so order survives reloads."""
        block = self._lessons_block()
        if block["seed"] is None:
            block["seed"] = secrets.token_hex(8)
            self._save_lessons()
        return block["seed"]

    def _adopt_pending(self, progress):
        """Bring what happened before the project existed (the mission) into the project."""
        pending = self._read_pending()
        block = progress["lessons"]
        if block["seed"] is None:
            block["seed"] = pending["seed"]
        for lesson, entry in pending["per_lesson"].items():
            block["per_lesson"].setdefault(lesson, entry)
        for item, entry in pending["placement"].items():
            block["placement"].setdefault(item, entry)
        for record in pending["records"]:
            if record not in block["records"]:
                block["records"].append(record)
        for key, entry in pending["review"]["items"].items():
            block["review"]["items"].setdefault(key, entry)

    def _item_title(self, kind, item):
        if kind == "lesson":
            return self.lessons.get(item)["title"]
        return self._text(item)["title"]

    def _lesson_entry(self, lesson_id):
        return self._lessons_block()["per_lesson"].setdefault(lesson_id, {"status": None, "activities": {}})

    def _walk(self, passed, part=None):
        """Every item of a Part's course (Part 3 by default) in teaching order, as (kind, id, status)."""
        part = part or store.PART_3
        block = self._lessons_block()
        done = list(self._done_of(part))
        steps, course = self._steps(part), self._course(part)
        next_step = steps[len(done)] if self.progress is not None and len(done) < len(steps) else None
        out, blocked = [], False
        for kind, item in course:
            if kind == "lesson":
                if self.lessons is None or item not in self.lessons:
                    continue
                stored = block["per_lesson"].get(item, {}).get("status")
                if stored in ("done", "skipped"):
                    out.append((kind, item, stored))
                    continue
                allowed = passed or item == part.mission
                out.append((kind, item, "active" if allowed and not blocked else "locked"))
                blocked = True
            else:
                if item in done:
                    out.append((kind, item, "done"))
                    continue
                allowed = passed and not blocked and item == next_step
                out.append((kind, item, "active" if allowed else "locked"))
                blocked = True
        return out

    def _lesson_blocking(self, step):
        """The lesson holding this step back, if a lesson is the reason it is locked."""
        if self.lessons is None:
            return None
        for kind, item, status in self._walk(True, self._part_of(step)):
            if kind == "step" and item == step:
                return None
            if kind == "lesson" and status == "active":
                return item
            if status == "locked":
                return None
        return None

    def _require_course(self):
        if self.lessons is None:
            raise EngineError("no_lessons", self._err("no_lessons"))

    def _require_lesson(self, lesson_id):
        self._require_course()
        lesson = self.lessons.get(lesson_id) if isinstance(lesson_id, str) else None
        if lesson is None:
            raise EngineError("unknown_lesson", self._err("unknown_lesson"))
        return lesson

    def _lesson_status(self, lesson_id):
        passed = self.preflight.is_passed(self.paths)
        for kind, item, status in self._walk(passed, self._part_of(lesson_id)):
            if kind == "lesson" and item == lesson_id:
                return status
        return "locked"

    def _require_lesson_open(self, lesson_id):
        """Refuse a locked lesson. Returns (lesson, status)."""
        lesson = self._require_lesson(lesson_id)
        status = self._lesson_status(lesson_id)
        if status == "locked":
            if lesson_id != self._part_of(lesson_id).mission and not self.preflight.is_passed(self.paths):
                raise EngineError("preflight_incomplete", self._err("preflight_first"))
            raise EngineError("lesson_locked", self._err("lesson_locked"))
        return lesson, status

    def _require_lesson_active(self, lesson_id):
        lesson, status = self._require_lesson_open(lesson_id)
        if status == "done":
            raise EngineError("lesson_done", self._err("lesson_finished"))
        if status == "skipped":
            raise EngineError("lesson_skipped", self._err("lesson_skipped"))
        return lesson

    def _activity(self, lesson, activity_id):
        activity = next((a for a in lesson["activities"] if a["id"] == activity_id), None)
        if activity is None:
            raise EngineError("unknown_activity", self._err("unknown_activity"))
        return activity

    def _activity_entry(self, lesson_id, activity_id):
        activities = self._lesson_entry(lesson_id)["activities"]
        return activities.setdefault(activity_id, {"passed": False, "attempts": 0, "first_try": None, "last": None})

    def _add_record(self, kind, lesson, item, source, **extra):
        self._lessons_block()["records"].append(
            dict({"type": kind, "lesson": lesson, "item": item, "source": source, "at": self._clock()}, **extra))

    # --- lesson views ------------------------------------------------------

    def lesson_view(self, lesson_id):
        with self._lock:
            lesson = self._require_lesson(lesson_id)
            status = self._lesson_status(lesson_id)
            if status == "locked":
                # Reading ahead: the text and the exercises are shown, and nothing is recorded.
                view = self._lesson_public(lesson, "preview", record_seed=False)
                view["held_by"] = self._held_by(lesson_id)
                return {"lesson": view}
            return {"lesson": self._lesson_public(lesson, status)}

    def _lesson_public(self, lesson, status, record_seed=True):
        preview = status == "preview"
        seed = self._seed() if record_seed else (self._lessons_block()["seed"] or "preview")
        reasons = self.lesson_text["rule_reasons"]
        entries = self._lessons_block()["per_lesson"].get(lesson["id"], {}).get("activities", {})
        views = []
        for activity in lesson["activities"]:
            entry = entries.get(activity["id"])
            view = lesson_lib.public_activity(lesson["id"], activity, entry, seed, reasons)
            if activity["type"] == "cli_compare":
                view.update(self._compare_extras(lesson, activity, entry, seed, preview))
            elif activity["type"] == "cli_demo":
                view.update(self._demo_extras(lesson, activity, preview))
            elif activity["type"] == "cli_practice":
                view.update(self._practice_extras(lesson, activity, entry, seed, preview))
            views.append(view)
        placement_done = {item["lesson"] for item in self.lessons.data["placement"]
                          if self._placement_passed(item["id"])}
        related = lesson.get("related") or {}
        result = {
            "id": lesson["id"],
            "title": lesson["title"],
            "win": lesson["win"],
            "minutes": lesson["minutes"],
            "skippable": lesson["skippable"],
            "status": status,
            "mission": self.lessons.mission_of(lesson["id"]),
            "body": lesson["body"],
            "activities": views,
            "sources": [{"label": s["label"], "ref": s["ref"]} for s in lesson["sources"]],
            "primary_source": {k: lesson["primary_source"][k] for k in ("label", "ref", "why")},
            "related": {"lessons": [{"id": i, "title": self.lessons.get(i)["title"]}
                                    for i in related.get("lessons", []) if i in self.lessons],
                        "glossary": list(related.get("glossary", []))},
            "can_complete": status == "active" and self._all_passed(lesson),
            "can_skip": status == "active" and lesson["skippable"] and lesson["id"] in placement_done,
        }
        part = self._part_of(lesson["id"])
        if lesson["id"] == part.mission:
            result["placement"] = self._placement_public(seed, part)
        return result

    def _cli_key(self, lesson_id, activity_id):
        return f"lesson:{lesson_id}:{activity_id}"

    def _compare_saved(self, activity):
        if self.paths is None:
            return False
        return all(gates.has_text(self.paths.hook_run_file(n)) for n in range(1, activity["runs"] + 1))

    def _compare_extras(self, lesson, activity, entry, seed, preview=False):
        outputs = []
        for n in range(1, activity["runs"] + 1):
            text = gates.read_text(self.paths.hook_run_file(n)) if self.paths is not None and not preview else ""
            outputs.append({"n": n, "done": bool(text.strip()), "text": text})
        key = self._cli_key(lesson["id"], activity["id"])
        context = f"{lesson['id']}:{activity['id']}:question"
        return {
            "runs": activity["runs"],
            "files": lesson_lib.file_names(activity),
            "cli": {"line": activity["line"], "folder_label": self.lesson_text["folders"]["hook"],
                    "started": self._cli_active(key), "sent": self._cli_active(key) and self._sent},
            "outputs": outputs,
            "all_saved": all(o["done"] for o in outputs),
            "question": lesson_lib.public_choice(activity["question"], seed, context, entry),
        }

    def _practice_saved(self, activity):
        return self.paths is not None and gates.has_text(self.paths.practice_output(activity["id"]))

    def _practice_extras(self, lesson, activity, entry, seed, preview=False):
        text = gates.read_text(self.paths.practice_output(activity["id"])) if self.paths is not None and not preview else ""
        key = self._cli_key(lesson["id"], activity["id"])
        context = f"{lesson['id']}:{activity['id']}:question"
        return {
            "runs": 1,
            "files": lesson_lib.file_names(activity),
            "cli": {"line": activity["line"], "folder_label": activity["folder_label"],
                    "started": self._cli_active(key), "sent": self._cli_active(key) and self._sent},
            "outputs": [{"n": 1, "done": bool(text.strip()), "text": text}],
            "all_saved": bool(text.strip()),
            "question": lesson_lib.public_choice(activity["question"], seed, context, entry),
        }

    def _demo_extras(self, lesson, activity, preview=False):
        reads = self.paths is not None and not preview
        check = self.paths.demo_check if reads else None
        exists = bool(check and check.is_file())
        first = self._load_result("demo-1") if reads else None
        second = self._load_result("demo-2") if reads else None
        key = self._cli_key(lesson["id"], activity["id"])
        return {
            "files": lesson_lib.file_names(activity),
            "cli": {"line": activity["line"], "folder_label": self.lesson_text["folders"]["demo"],
                    "started": self._cli_active(key), "sent": self._cli_active(key) and self._sent},
            "checker_exists": exists,
            "scan": scan.scan_file(check) if exists else [],
            "runs": [r for r in (first, second) if r is not None],
            "identical": self._verdicts_match(first, second) if first and second else None,
        }

    @staticmethod
    def _verdicts_match(first, second):
        def verdicts(result):
            return [(f["file"], r["id"], r["verdict"]) for f in result["files"] for r in f["rows"]]
        return bool(first.get("ok") and second.get("ok") and verdicts(first)
                    and verdicts(first) == verdicts(second))

    def _all_passed(self, lesson):
        """Only the exercises block Continue: the demo, and the output a CLI exercise must save.

        Every question, sort, order, lab and reflection is a learning check and never blocks.
        """
        entries = self._lessons_block()["per_lesson"].get(lesson["id"], {}).get("activities", {})
        for activity in lesson["activities"]:
            kind = activity["type"]
            if kind == "cli_demo" and not entries.get(activity["id"], {}).get("passed"):
                return False
            if kind == "cli_compare" and not self._compare_saved(activity):
                return False
            if kind == "cli_practice" and not self._practice_saved(activity):
                return False
        return True

    # --- answers -----------------------------------------------------------

    def lesson_answer(self, lesson_id, activity_id, answer):
        with self._lock:
            lesson = self._require_lesson_active(lesson_id)
            activity = self._activity(lesson, activity_id)
            if activity["type"] != "cli_demo":
                return self._grade_answer(lesson, activity, answer)
        return self._demo_run(lesson_id, activity_id)

    def _grade_answer(self, lesson, activity, answer):
        kind = activity["type"]
        if kind == "cli_compare" and not self._compare_saved(activity):
            raise EngineError("runs_missing", self._err("runs_missing"))
        if kind == "cli_practice" and not self._practice_saved(activity):
            raise EngineError("practice_missing", self._err("practice_missing"))
        try:
            if kind in ("cli_compare", "cli_practice"):
                if not isinstance(answer, dict):
                    raise lesson_lib.AnswerError("the answer must be an object")
                passed, last = lesson_lib.grade_choice(activity["question"], answer)
            else:
                passed, last = lesson_lib.grade(activity, answer)
        except lesson_lib.AnswerError as exc:
            raise EngineError("bad_answer", self._err("bad_answer")) from exc
        entry = self._activity_entry(lesson["id"], activity["id"])
        if entry["passed"] and kind != "reflection":
            return {"passed": True, "lesson": self._lesson_public(lesson, self._lesson_status(lesson["id"]))}
        was_passed = entry["passed"]
        if was_passed and not passed:
            # A passed reflection stays passed; a shorter rewrite is not saved.
            return {"passed": True, "lesson": self._lesson_public(lesson, self._lesson_status(lesson["id"]))}
        if not was_passed:
            entry["attempts"] += 1
        entry["last"] = last
        entry["passed"] = passed
        if passed and not was_passed:
            entry["first_try"] = entry["attempts"] == 1
            self._add_record("activity", lesson["id"], activity["id"], "lesson", first_try=entry["first_try"])
        self._save_lessons()
        return {"passed": passed, "lesson": self._lesson_public(lesson, self._lesson_status(lesson["id"]))}

    def _demo_run(self, lesson_id, activity_id):
        """Run check.py twice from the demo folder and compare the verdicts."""
        with self._lock:
            lesson = self._require_lesson_active(lesson_id)
            activity = self._activity(lesson, activity_id)
            if self._activity_entry(lesson_id, activity_id)["passed"]:
                return {"passed": True, "lesson": self._lesson_public(lesson, self._lesson_status(lesson_id))}
            if self._checker_running:
                raise EngineError("checker_busy", self._err("checker_busy"))
            if not self.paths.demo_check.is_file():
                raise EngineError("no_checker", self._err("no_checker"))
            problems = scan.scan_file(self.paths.demo_check)
            if problems:
                raise EngineError("scan_failed", " ".join(p["message"] for p in problems))
            missing = [a for a in activity["run_args"] if not gates.has_text(self.paths.demo_work / a)]
            if missing:
                raise EngineError("missing_file", self._err("missing_file", names=", ".join(missing)))
            paths = self.paths
            args = list(activity["run_args"])
            self._checker_running = True
        try:
            env = self._cli_env()
            first = runner.run_checker(paths.demo_work, args, env=env)
            second = runner.run_checker(paths.demo_work, args, env=env)
        finally:
            with self._lock:
                self._checker_running = False
        with self._lock:
            if self.paths is not paths:
                raise EngineError("checker_stale", self._err("lesson_locked"))
            self._save_result("demo-1", first)
            self._save_result("demo-2", second)
            entry = self._activity_entry(lesson_id, activity_id)
            entry["attempts"] += 1
            entry["last"] = {"run": True}
            passed = self._verdicts_match(first, second)
            if passed and not entry["passed"]:
                entry["passed"] = True
                entry["first_try"] = entry["attempts"] == 1
                self._add_record("activity", lesson_id, activity_id, "lesson", first_try=entry["first_try"])
            self._save_lessons()
            return {"passed": entry["passed"], "lesson": self._lesson_public(lesson, self._lesson_status(lesson_id))}

    def lesson_rule_run(self, lesson_id, activity_id, rule_id, text):
        with self._lock:
            lesson, _status = self._require_lesson_open(lesson_id)
            activity = self._activity(lesson, activity_id)
            if activity["type"] != "rule_lab":
                raise EngineError("bad_answer", self._err("bad_answer"))
            if not isinstance(text, str) or not text.strip():
                raise EngineError("bad_answer", self._err("bad_rule_text"))
            rule = next((r for r in activity["rules"] if r["id"] == rule_id), None)
            if rule is None:
                raise EngineError("unknown_rule", self._err("unknown_rule"))
            passed = self._activity_entry(lesson_id, activity_id)["passed"]
            if not passed and lesson_lib.rule_is_sample_text(activity, text):
                raise EngineError("sample_before_answer", self._err("sample_before_answer"))
            return lesson_lib.rule_result(rule, text, self.lesson_text["rule_reasons"])

    # --- complete, skip, placement -------------------------------------------

    def lesson_complete(self, lesson_id):
        with self._lock:
            lesson = self._require_lesson_active(lesson_id)
            if not self._all_passed(lesson):
                raise EngineError("activities_incomplete", self._err("activities_incomplete"))
            entry = self._lesson_entry(lesson_id)
            entry["status"] = "done"
            review_lib.schedule(self._lessons_block()["review"]["items"], lesson_id,
                                [item["id"] for item in lesson["retrieval"]], self._clock())
            self._save_lessons()

    # --- the question that follows a finished step ---------------------------

    def _step_question(self, step):
        return self.lessons.step_checks.get(step) if self.lessons is not None else None

    def _step_question_entry(self, step):
        return self._lessons_block().setdefault("step_checks", {}).get(step)

    def _step_question_public(self, step):
        """The learning question for a finished step, with its answer removed. None until the step is done."""
        item = self._step_question(step)
        if item is None or self._status(step) != "done":
            return None
        entry = self._step_question_entry(step)
        view = lesson_lib.public_choice(item, self._seed(), f"step-question:{step}", entry)
        view.update(id=item["id"], passed=bool(entry and entry.get("passed")))
        return view

    def step_question_answer(self, step, option):
        """Grade the question after a step. It never gates anything; a pass is recorded once."""
        with self._lock:
            self._require_known(step)
            item = self._step_question(step)
            if item is None:
                raise EngineError("no_step_question", self._err("no_step_question"))
            if self.progress is None or self._status(step) != "done":
                raise EngineError("step_question_locked", self._err("step_question_locked"))
            try:
                passed, last = lesson_lib.grade_choice(item, {"option": option})
            except lesson_lib.AnswerError as exc:
                raise EngineError("bad_answer", self._err("bad_answer")) from exc
            entries = self._lessons_block().setdefault("step_checks", {})
            entry = entries.setdefault(step, {"passed": False, "attempts": 0, "first_try": None, "last": None})
            if not entry["passed"]:
                entry["attempts"] += 1
                entry["last"] = last
                entry["passed"] = passed
                if passed:
                    entry["first_try"] = entry["attempts"] == 1
                    self._add_record("activity", step, item["id"], "step", first_try=entry["first_try"])
                self._save_lessons()
            return {"passed": entry["passed"], "question": self._step_question_public(step)}

    def lesson_skip(self, lesson_id):
        with self._lock:
            lesson = self._require_lesson_active(lesson_id)
            if not lesson["skippable"]:
                raise EngineError("cannot_skip", self._err("not_skippable"))
            if not any(item["lesson"] == lesson_id and self._placement_passed(item["id"])
                       for item in self.lessons.data["placement"]):
                raise EngineError("cannot_skip", self._err("cannot_skip"))
            self._lesson_entry(lesson_id)["status"] = "skipped"
            self._save_lessons()

    def _placement_passed(self, item_id):
        return self._lessons_block()["placement"].get(item_id, {}).get("correct") is True

    def _placement_public(self, seed, part):
        views = []
        for item in self.lessons.data["placement"]:
            if item["lesson"] not in part.lesson_ids:
                continue
            lesson = self.lessons.get(item["lesson"])
            stored = self._lessons_block()["placement"].get(item["id"])
            context = f"placement:{item['id']}"
            result = None
            if stored:
                option = next(o for o in item["options"] if o["id"] == stored["option"])
                result = {"passed": stored["correct"], "chosen": option["id"], "feedback": option["feedback"],
                          "offer_skip": stored["correct"] and lesson["skippable"],
                          "decision": stored.get("decision")}
            views.append({"id": item["id"], "prompt": item["prompt"], "lesson": item["lesson"],
                          "lesson_title": lesson["title"],
                          "options": lesson_lib.public_options(item, seed, context),
                          "result": result})
        return views

    def placement_answer(self, item_id, option=None, accept_skip=None):
        with self._lock:
            self._require_course()
            item = self.lessons.placement.get(item_id) if isinstance(item_id, str) else None
            if item is None:
                raise EngineError("unknown_placement", self._err("unknown_placement"))
            mission = self._part_of(item["lesson"]).mission
            if self._lesson_status(mission) != "active":
                raise EngineError("placement_closed", self._err("placement_closed"))
            lesson = self.lessons.get(item["lesson"])
            stored = self._lessons_block()["placement"].get(item_id)
            if accept_skip is not None:
                if not (stored and stored["correct"] and lesson["skippable"]) or not isinstance(accept_skip, bool):
                    raise EngineError("no_skip_offer", self._err("no_skip_offer"))
                if stored.get("decision") is not None:
                    raise EngineError("placement_decided", self._err("placement_decided"))
                stored["decision"] = "accepted" if accept_skip else "declined"
                status = self._lessons_block()["per_lesson"].get(lesson["id"], {}).get("status")
                if accept_skip and status != "done":
                    self._lesson_entry(lesson["id"])["status"] = "skipped"
                self._save_lessons()
                return {"lesson": self._lesson_public(self.lessons.get(mission), self._lesson_status(mission))}
            if stored is not None:
                raise EngineError("placement_answered", self._err("placement_answered"))
            try:
                correct, _last = lesson_lib.grade_choice(item, {"option": option})
            except lesson_lib.AnswerError as exc:
                raise EngineError("bad_answer", self._err("bad_answer")) from exc
            self._lessons_block()["placement"][item_id] = {"correct": correct, "option": option, "decision": None}
            if correct:
                self._add_record("placement", lesson["id"], item_id, "placement")
            self._save_lessons()
            return {"lesson": self._lesson_public(self.lessons.get(mission), self._lesson_status(mission))}

    # --- lesson CLI ----------------------------------------------------------

    def _require_cli_activity(self, lesson_id, activity_id):
        lesson = self._require_lesson_active(lesson_id)
        activity = self._activity(lesson, activity_id)
        if activity["type"] not in ("cli_compare", "cli_demo", "cli_practice"):
            raise EngineError("not_cli", self._err("not_cli"))
        self._require_preflight()  # hands-on work needs setup
        return lesson, activity

    def lesson_cli_start(self, lesson_id, activity_id):
        with self._lock:
            lesson, activity = self._require_cli_activity(lesson_id, activity_id)
            if self._activity_entry(lesson_id, activity_id)["passed"]:
                raise EngineError("activity_done", self._err("activity_done"))
            run_n = None
            if activity["type"] == "cli_compare":
                run_n = next((n for n in range(1, activity["runs"] + 1)
                              if not gates.has_text(self.paths.hook_run_file(n))), None)
                if run_n is None:
                    raise EngineError("runs_complete", self._err("runs_complete"))
            elif activity["type"] == "cli_practice" and self._practice_saved(activity):
                raise EngineError("runs_complete", self._err("runs_complete"))
            self._stop_cli()
            labels = self.lesson_text["terminal_labels"]
            watch = None
            try:
                if activity["type"] == "cli_practice":
                    sources = {entry["name"]: lesson_lib.kit_read_path(entry["source"]) for entry in activity["files"]}
                    cwd = project.prepare_practice(self.paths, activity["id"], sources)
                    label = labels["practice"]
                    watch = (cwd / lesson_lib.PRACTICE_OUTPUT, self.paths.practice_output(activity["id"]))
                elif run_n is not None:
                    project.prepare_hook(self.paths)
                    cwd = self.paths.hook_work
                    label = labels["hook"].format(n=run_n, total=activity["runs"])
                    watch = (self.paths.hook_output, self.paths.hook_run_file(run_n))
                else:
                    project.prepare_demo(self.paths)
                    cwd = self.paths.demo_work
                    label = labels["demo"]
                    for name in ("demo-1", "demo-2"):
                        try:
                            self._result_path(name).unlink()
                        except OSError:
                            pass
            except (OSError, resources.ResourceNotFound) as exc:
                raise EngineError("folder_busy", self._err("folder_busy", error=exc)) from exc
            try:
                self.terminal.start(self.progress["cli_command"], str(cwd), label, env=self._cli_env(),
                                    owner=self._cli_key(lesson_id, activity_id))
            except (ValueError, OSError) as exc:
                raise EngineError("cli_start_failed", self._err("cli_start_failed", error=exc)) from exc
            self._cli_step = self._cli_key(lesson_id, activity_id)
            self._sent = False
            if watch is not None:
                self._start_watcher(*watch)

    def lesson_cli_send(self, lesson_id, activity_id):
        with self._lock:
            _lesson, activity = self._require_cli_activity(lesson_id, activity_id)
            key = self._cli_key(lesson_id, activity_id)
            if not self._cli_active(key):
                raise EngineError("cli_not_running", self._err("cli_not_running"))
            line = activity["line"]
        try:
            self.terminal.type_line(line)
        except OSError as exc:
            raise EngineError("cli_not_running", self._err("type_failed", error=exc)) from exc
        with self._lock:
            if self._cli_active(key):
                self._sent = True

    def lesson_cli_stop(self, lesson_id, activity_id):
        with self._lock:
            self._require_course()
            self._require_lesson(lesson_id)
            if self._cli_step == self._cli_key(lesson_id, activity_id):
                self._stop_cli()

    # --- kit viewer ----------------------------------------------------------

    def kit_file(self, ref):
        try:
            path = lesson_lib.kit_read_path(ref)
            text = resources.read_text(path)
        except (resources.ResourceNotFound, UnicodeDecodeError) as exc:
            raise EngineError("bad_ref", self._err("bad_ref")) from exc
        gate = part_steps.GATED_KIT.get(path)
        if gate is not None and not self._kit_open(*gate):
            raise EngineError("bad_ref", self._err("bad_ref"))
        return {"kit": {"ref": ref, "name": posixpath.basename(path), "text": text}}

    def _kit_open(self, part_id, step):
        """A gated kit file opens once the step that makes it useful is done."""
        part = store.part_by_id(part_id)
        return self.progress is not None and part is not None and step in self._done_of(part)

    # --- review --------------------------------------------------------------

    def _review_items(self):
        return self._lessons_block()["review"]["items"]

    def _retrieval(self, key):
        entry = self._review_items().get(key)
        if entry is None or self.lessons is None or entry["lesson"] not in self.lessons:
            return None, None
        lesson = self.lessons.get(entry["lesson"])
        item = next((r for r in lesson["retrieval"] if r["id"] == entry["item"]), None)
        return (lesson, item) if item is not None else (None, None)

    def _review_summary(self):
        if self.lessons is None or self._review_postponed:
            return {"due": 0, "postponed": self._review_postponed}
        if self._review_sitting is not None:
            return {"due": len(self._review_sitting), "postponed": False}
        keys = review_lib.due_keys(self._review_items(), self._clock())
        return {"due": min(len(keys), review_lib.MAX_PER_SITTING), "postponed": False}

    def review_get(self):
        with self._lock:
            self._require_course()
            if self._review_postponed:
                return {"review": {"items": [], "postponed": True}}
            items = self._review_items()
            if self._review_sitting is None:
                now = self._clock()
                keys = [k for k in review_lib.due_keys(items, now) if self._retrieval(k)[1] is not None]
                if keys:
                    self._review_sitting = review_lib.pick_sitting(items, keys)
            seed = self._seed()
            views = []
            for key in list(self._review_sitting or []):
                lesson, retrieval = self._retrieval(key)
                if retrieval is None:
                    self._review_sitting.remove(key)
                    continue
                views.append(dict({"item": key, "lesson": lesson["id"], "lesson_title": lesson["title"]},
                                  **lesson_lib.public_retrieval(lesson["id"], retrieval, seed)))
            return {"review": {"items": views, "postponed": False}}

    def review_answer(self, key, option):
        with self._lock:
            self._require_course()
            if not isinstance(key, str) or key not in (self._review_sitting or []):
                raise EngineError("review_unknown", self._err("review_unknown"))
            lesson, retrieval = self._retrieval(key)
            if retrieval is None:
                raise EngineError("review_unknown", self._err("review_unknown"))
            try:
                correct, _last = lesson_lib.grade_choice(retrieval, {"option": option})
            except lesson_lib.AnswerError as exc:
                raise EngineError("bad_answer", self._err("bad_answer")) from exc
            feedback = next(o["feedback"] for o in retrieval["options"] if o["id"] == option)
            now = self._clock()
            review_lib.apply_answer(self._review_items()[key], correct, now)
            self._review_sitting.remove(key)
            if correct:
                self._add_record("review", lesson["id"], retrieval["id"], "review")
            self._save_lessons()
            return {"passed": correct, "feedback": feedback}

    def review_postpone(self):
        with self._lock:
            self._require_course()
            self._review_postponed = True
            self._review_sitting = None
