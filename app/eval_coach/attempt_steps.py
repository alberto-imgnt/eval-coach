"""The six step kinds Part 4 uses, each driven by the step's content in content/part-4-steps.json.

choose_start  pick the participant's own Part 3 baseline or the bundled Practice baseline (`starting-point`)
known_good    save a known-good answer and see its score, apart from the five-answer score (`known-good`)
hypothesis    write the prediction before anything is edited or run (`hypothesis-n`)
edit          change the round's own copy of the prompt (`edit-n`)
measure       collect five fresh answers in new AI chats, then score them with no AI call (`measure-n`)
decide        keep or undo the round, then check the log the AI and the participant wrote (`decide-n`)

Round n is attempt n. Every step is a thin wrapper over `attempts.Attempts`, which holds the manifest, the scoring and the
log gate. Nothing here reads terminal output, answers a prompt in the AI window, edits the participant's log or calls a
model. The app decides from the files and from running the checker itself.
"""
from __future__ import annotations

import re

from . import gates, part_steps, project
from . import state as store
from .attempts import TARGET_PERCENT, Attempts

KNOWN_GOOD_ROUND = 1
RUNS = 5


def _round(step):
    """The round number a step id such as `edit-2` belongs to, or None for `starting-point` and `known-good`."""
    tail = step.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def _attempts(engine, step=None):
    model = None
    if step is not None and step.startswith("measure-"):
        model = lambda: engine._step(step)["model"]  # noqa: E731  the models the round's AI windows used
    return Attempts.for_engine(engine, model)


def _require_open(engine, step):
    """Refuse a step the participant may not work in. A finished step stays open for what its page still allows."""
    engine._require_configured()
    engine._require_known(step)
    engine._require_preflight()
    if engine._status(step) not in ("active", "done"):
        raise part_steps._error("step_locked", engine._lock_message())


def _data(data, actions):
    if not isinstance(data, dict) or data.get("action") not in actions:
        raise part_steps._error("bad_input", "This step does not do that.")
    return data["action"]


def _text_field(value, words):
    if not isinstance(value, str) or len(value) > part_steps.MAX_TEXT or "\0" in value:
        raise part_steps._error("bad_input", words.get("bad_text", "That text could not be saved."))
    return value


def _settle(engine, step, result, ends_cli=False):
    """Finish an active step whose gate passed. A finished step is left as it is: a sticky Done."""
    if engine._status(step) == "active":
        part_steps._finish(engine, step, result, ends_cli=ends_cli)


def _report(text, items):
    report = gates.Report(text["gate"])
    for key, ok, fmt in items:
        report.add(key, ok, **fmt)
    return report


def _view(engine, step, text, data, optional=False):
    view = part_steps._base(engine, step, text, data)
    if optional:
        view["optional"] = True
    return view


def _practice_note(at, text):
    return text["ui"].get("practice_only") if at.source() == "practice" else None


def _squash(value):
    return " ".join(str(value).split()).casefold()


def _cli(engine, step, text, line):
    return {"line": line, "folder_label": text["folder_label"], "mode": "paste", "started": engine._cli_active(step),
            "sent": engine._cli_active(step) and engine._sent, "blocked": engine._cli_blocked.get(step),
            "can_auto_start": False, "has_result": False, "paste_ready": "<model>" not in line}


def _start_ai(engine, step, text, cwd, record):
    """Start a fresh AI window for a step in `cwd` and note the model it was started with. Call with the lock held."""
    engine._stop_cli()
    try:
        model = engine._ai_start(engine.progress["cli_command"], cwd, text["title"], step)
    except (ValueError, OSError) as exc:
        raise part_steps._error("cli_start_failed", f"Your AI could not be started: {exc}") from exc
    engine._cli_step = step
    engine._sent = False
    engine._cli_blocked.pop(step, None)
    if "models" in record:  # a step that collects answers notes each model its windows used, once each
        if model and model not in record["models"]:
            record["models"].append(model)
        record["model"] = " and ".join(record["models"])
    record["auto_started"] = True
    engine._save()


def _auto(engine, step, ready, launch):
    """Open the AI window by itself once per step when `ready()` says so. A failed start never raises."""
    from .engine import EngineError
    if not ready():
        return
    try:
        launch()
    except EngineError as exc:
        engine._cli_blocked[step] = exc.message


# --- the starting point -------------------------------------------------------


class ChooseStart:
    def _own(self, engine, text):
        """(available, plain reason when not, True when there is little to improve)."""
        words = text["messages"]
        if "part-3" in engine._lessons_block()["skipped_parts"]:
            return False, words["own_skipped"], False
        if "baseline" not in engine.progress["done"]:
            return False, words["own_unfinished"], False
        facts = engine._baseline_facts()
        if not facts["fresh"]:
            return False, words["own_changed"], False
        overall = facts["summary"]["overall"]
        return True, None, overall["total"] > 0 and overall["passes"] * 100 >= TARGET_PERCENT * overall["total"]

    def report(self, engine, step):
        return _report(engine._text(step), [("chosen", _attempts(engine).chosen() in ("own", "practice"), {})]).result()

    def detail(self, engine, step):
        text = engine._text(step)
        ui = text["ui"]
        at = _attempts(engine)
        available, reason, little = self._own(engine, text)
        data = {
            "choices": [
                {"id": "own", "label": ui["own"], "available": available, "reason": reason},
                {"id": "practice", "label": ui["practice"], "available": True, "reason": None,
                 "note": ui["practice_only"]},
            ],
            "chosen": at.chosen(),
            "fixed": bool(at.manifest()),
            "fixed_note": text["messages"]["start_fixed"] if at.manifest() else None,
            "little_gap": ui["little_gap"] if little else None,
            "practice_only": ui["practice_only"],
        }
        return _view(engine, step, text, data)

    def submit(self, engine, step, data):
        with engine._lock:
            _require_open(engine, step)
            text = engine._text(step)
            _data(data, ("choose",))
            choice = data.get("choice")
            if choice not in ("own", "practice"):
                raise part_steps._error("bad_input", text["messages"]["bad_choice"])
            at = _attempts(engine)
            if at.manifest():
                raise part_steps._error("start_fixed", text["messages"]["start_fixed"])
            if choice == "own":
                available, reason, _ = self._own(engine, text)
                if not available:
                    raise part_steps._error("start_unavailable", reason)
        at.choose_start(choice)  # the Practice choice runs a checker, so the page is not held while it does
        with engine._lock:
            _settle(engine, step, self.report(engine, step))

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            _settle(engine, step, self.report(engine, step))


# --- the known-good answer ----------------------------------------------------


class KnownGood:
    def _facts(self, engine, at):
        view = at.view(KNOWN_GOOD_ROUND) if at.manifest() else None
        return view, view["known_good"] if view else None

    def report(self, engine, step):
        at = _attempts(engine)
        view, result = self._facts(engine, at)
        return _report(engine._text(step), [
            ("saved", bool(view and view["known_good_saved"]), {}),
            ("scored", result is not None and not result["stale"], {}),
            ("meets", bool(result and result["meets"] and not result["stale"]), {}),
            ("rerun", not at.rerun_needed(), {}),
        ]).result()

    def detail(self, engine, step):
        text = engine._text(step)
        at = _attempts(engine)
        view, result = self._facts(engine, at)
        base = at._base()
        answer = gates.read_text(at._ap(KNOWN_GOOD_ROUND).known_good) if at.manifest() else ""
        data = {
            "round": KNOWN_GOOD_ROUND, "answer": answer, "saved": bool(answer.strip()), "result": result,
            "rules_name": base.test_cases.name, "rules": gates.read_text(base.test_cases),
            "rerun_needed": bool(at.rerun_needed()), "rerun_text": at.rerun_needed() and at.words["errors"]["rerun_needed"],
            "target": TARGET_PERCENT, "practice_only": _practice_note(at, text),
        }
        return _view(engine, step, text, data)

    def submit(self, engine, step, data):
        with engine._lock:
            _require_open(engine, step)
            action = _data(data, ("save", "score", "rerun"))
            if engine._status(step) == "done" and action != "rerun":
                raise part_steps._error("step_done", "This step is already done.")
            text = engine._text(step)
            answer = _text_field(data.get("text"), text["messages"]) if action == "save" else None
            at = _attempts(engine)
            if action == "save" and not at.manifest():
                at.start()
        if action == "save":
            at.save_known_good(KNOWN_GOOD_ROUND, answer)
        if action == "rerun":
            at.rerun_iteration_zero()
        else:
            at.score_known_good(KNOWN_GOOD_ROUND)
        with engine._lock:
            _settle(engine, step, self.report(engine, step))

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            _settle(engine, step, self.report(engine, step))


# --- a round ------------------------------------------------------------------


class _Round:
    """What the four steps of a round share: the attempt, its view and the starting version's rules."""

    optional = False

    def _n(self, step):
        return _round(step)

    def _open(self, engine, step):
        _require_open(engine, step)
        return self._n(step), _attempts(engine, step)

    def _ensure(self, at, n):
        """The attempt for round n, created from the kept version when the previous round was decided."""
        if not any(rec["n"] == n for rec in at.manifest()):
            at.start()

    def _attempt(self, at, n):
        return at.view(n) if any(rec["n"] == n for rec in at.manifest()) else None

    def _base(self, engine, step, text, at, n, data):
        view = _view(engine, step, text, dict(data, round=n, source=at.source(), practice_only=_practice_note(at, text)),
                     optional=step in store.PART_4.optional_steps)
        return view


class Hypothesis(_Round):
    def report(self, engine, step):
        n = self._n(step)
        view = self._attempt(_attempts(engine), n)
        return _report(engine._text(step), [("saved", bool(view and view["hypothesis_saved"]), {})]).result()

    def detail(self, engine, step):
        n = self._n(step)
        text = engine._text(step)
        at = _attempts(engine)
        view = self._attempt(at, n)
        start = view["parent"] if view else at.kept()
        data = {
            "attempt": view, "start": start, "start_rules": at.rules_of(start),
            "start_overall": self._overall(at, start),
            "hypothesis": view["hypothesis"] if view else "",
            "saved": bool(view and view["hypothesis_saved"]),
            "locked": bool(view and (view["run_started"] or view["decision"] != "pending")),
            "locked_note": text["messages"]["locked"] if view and view["run_started"] else None,
        }
        return self._base(engine, step, text, at, n, data)

    @staticmethod
    def _overall(at, n):
        from .attempts import overall
        results = at._results_of(n)
        if results is None:
            return None
        passes, total = overall(results)
        return {"passes": passes, "total": total}

    def submit(self, engine, step, data):
        with engine._lock:
            n, at = self._open(engine, step)
            _data(data, ("save",))
            text = _text_field(data.get("text"), engine._text(step)["messages"])
            self._ensure(at, n)
            at.save_hypothesis(n, text)
            _settle(engine, step, self.report(engine, step))

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            _settle(engine, step, self.report(engine, step))


class Edit(_Round):
    def _parent_prompt(self, at, view):
        parent = view["parent"]
        src = at._base() if parent == 0 else at._ap(parent)
        return gates.read_text(src.prompt)

    def _facts(self, at, n):
        view = self._attempt(at, n)
        if view is None:
            return None, "", "", False
        prompt = gates.read_text(at._ap(n).prompt)
        start = self._parent_prompt(at, view)
        return view, prompt, start, bool(prompt.strip()) and _squash(prompt) != _squash(start)

    def report(self, engine, step):
        n = self._n(step)
        _, _, _, changed = self._facts(_attempts(engine), n)
        return _report(engine._text(step), [("changed", changed, {})]).result()

    def detail(self, engine, step):
        n = self._n(step)
        text = engine._text(step)
        at = _attempts(engine)
        view, prompt, start, changed = self._facts(at, n)
        saved_runs = any(done for _, done, _ in at.run_texts(n)) if view else False
        data = {"attempt": view, "prompt": prompt, "start_prompt": start, "changed": changed,
                "prompt_name": "prompt.md", "locked": saved_runs or bool(view and view["decision"] != "pending"),
                "locked_note": text["messages"]["locked"] if saved_runs else None,
                "hypothesis": view["hypothesis"] if view else ""}
        return self._base(engine, step, text, at, n, data)

    def submit(self, engine, step, data):
        with engine._lock:
            n, at = self._open(engine, step)
            _data(data, ("save",))
            text = engine._text(step)
            prompt = _text_field(data.get("prompt"), text["messages"])
            if not prompt.strip():
                raise part_steps._error("bad_input", text["messages"]["blank"])
            view = self._attempt(at, n)
            if view is None or not view["hypothesis_saved"]:
                raise part_steps._error("hypothesis_needed", at.words["errors"]["hypothesis_needed"].format(n=n))
            if view["decision"] != "pending" or any(done for _, done, _ in at.run_texts(n)):
                raise part_steps._error("edit_locked", text["messages"]["locked"])
            try:
                store.write_bytes_atomic(at._ap(n).prompt, prompt.replace("\r\n", "\n").encode("utf-8"))
            except OSError as exc:
                raise part_steps._error("folder_busy", text["messages"]["save_failed"].format(error=exc)) from exc
            _settle(engine, step, self.report(engine, step))

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            _settle(engine, step, self.report(engine, step))


class Measure(_Round):
    def _runs(self, at, n):
        return [{"n": k, "done": done, "words": words} for k, done, words in at.run_texts(n)]

    def _previous_model(self, engine, at, n):
        """The model of the attempt before this one; for round 1 on the participant's baseline, Part 3's model."""
        earlier = [rec for rec in at.manifest() if rec["n"] < n]
        if earlier:
            return earlier[-1]["model"]
        return "" if at.source() == "practice" else engine._model_name()

    def report(self, engine, step):
        n = self._n(step)
        at = _attempts(engine, step)
        view = self._attempt(at, n)
        saved = sum(1 for _, done, _ in at.run_texts(n) if done) if view else 0
        return _report(engine._text(step), [
            ("hypothesis", bool(view and view["hypothesis_saved"]), {}),
            ("answers", saved == RUNS, {"count": saved}),
            ("scored", bool(view and view["scored"] and not view["stale"]), {}),
        ]).result()

    def _can_auto_start(self, engine, step, at, n):
        if engine._status(step) != "active" or engine.terminal.running or engine._step(step)["auto_started"]:
            return False
        if step in engine._cli_blocked or self._attempt(at, n) is None:
            return False
        try:
            at.require_hypothesis(n)
        except Exception:
            return False
        return not any(done for _, done, _ in at.run_texts(n))

    def detail(self, engine, step):
        n = self._n(step)
        text = engine._text(step)
        at = _attempts(engine, step)
        view = self._attempt(at, n)
        runs = self._runs(at, n) if view else [{"n": k, "done": False, "words": 0} for k in range(1, RUNS + 1)]
        record = engine._step(step)
        model = record["model"] or (view["model"] if view else "")
        previous = self._previous_model(engine, at, n)
        differs = bool(model and previous and _squash(model) != _squash(previous))
        pending = bool(view and view["decision"] == "pending")
        data = {
            "attempt": view, "runs": runs, "current_run": next((r["n"] for r in runs if not r["done"]), RUNS),
            "all_saved": all(r["done"] for r in runs), "model": model,
            "model_note": text["messages"]["model_differs"] if differs else None,
            "can_score": bool(view and pending and all(r["done"] for r in runs) and view["hypothesis_saved"]),
            "rerun_needed": bool(at.rerun_needed()),
            "rerun_text": at.rerun_needed() and at.words["errors"]["rerun_needed"],
            "target": TARGET_PERCENT,
        }
        out = self._base(engine, step, text, at, n, data)
        cli = _cli(engine, step, text, text["line"])
        cli["can_auto_start"] = self._can_auto_start(engine, step, at, n)
        cli["start_blocked"] = None if view and view["hypothesis_saved"] else text["messages"]["start_blocked"]
        out["cli"] = cli
        return out

    def _launch(self, engine, step, at, n):
        text = engine._text(step)
        view = self._attempt(at, n)
        if view is None:
            raise part_steps._error("hypothesis_needed", at.words["errors"]["hypothesis_needed"].format(n=n))
        at.require_hypothesis(n)
        if view["decision"] != "pending":
            raise part_steps._error("already_decided", at.words["errors"]["already_decided"].format(
                n=n, decision=view["decision"]))
        runs = at.run_texts(n)
        run = next((k for k, done, _ in runs if not done), None)
        if run is None:
            raise part_steps._error("runs_complete", text["messages"]["runs_complete"])
        ap = at._ap(n)
        engine._stop_cli()
        try:
            project.prepare_part4_blind(engine.paths, ap.prompt.read_bytes())
        except OSError as exc:
            raise part_steps._error("folder_busy", f"The working folder could not be prepared: {exc}") from exc
        _start_ai(engine, step, dict(text, title=f"{text['title']}: run {run} of {RUNS}"), engine.paths.part4_blind,
                  engine._step(step))
        engine._start_watcher(engine.paths.part4_blind_output, ap.run_file(run), None)

    def start(self, engine, step):
        with engine._lock:
            n, at = self._open(engine, step)
            if engine._status(step) != "active":
                raise part_steps._error("step_done", "This step is already done.")
            self._launch(engine, step, at, n)

    def auto_start(self, engine, step):
        n = self._n(step)
        at = _attempts(engine, step)
        _auto(engine, step, lambda: self._can_auto_start(engine, step, at, n),
              lambda: self._launch(engine, step, at, n))

    def submit(self, engine, step, data):
        with engine._lock:
            n, at = self._open(engine, step)
            action = _data(data, ("score", "rerun"))
        if action == "rerun":
            at.rerun_iteration_zero()
        else:
            at.score(n)
        with engine._lock:
            _settle(engine, step, self.report(engine, step), ends_cli=True)

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            _settle(engine, step, self.report(engine, step), ends_cli=True)


class Decide(_Round):
    def _line(self, engine, step, at, n, view):
        text = engine._text(step)
        base = "part-4/practice" if at.source() == "practice" else "part-4"
        model = view["model"] or "<model>"
        return text["line_template"].format(n=n, base=base, log=at._log_name(), model=model)

    def _can_auto_start(self, engine, step, at, n):
        view = self._attempt(at, n)
        record = engine._step(step)
        return bool(view and view["decision"] != "pending" and engine._status(step) == "active"
                    and not engine.terminal.running and not record["auto_started"] and step not in engine._cli_blocked)

    def detail(self, engine, step):
        n = self._n(step)
        text = engine._text(step)
        at = _attempts(engine)
        view = self._attempt(at, n)
        decided = bool(view and view["decision"] != "pending")
        done = engine._status(step) == "done"
        reflection = text["ui"].get("reflection")
        data = {
            "attempt": view, "decided": decided, "decision": view["decision"] if view else "pending",
            "can_decide": bool(view and view["scored"] and not view["stale"] and view["decision"] == "pending"
                               and not at.rerun_needed()),
            "log_file": at._log_name(), "rerun_needed": bool(at.rerun_needed()),
            "rerun_text": at.rerun_needed() and at.words["errors"]["rerun_needed"],
            "target": TARGET_PERCENT,
            "reflection": ({"heading": reflection["heading"], "prompt": reflection["prompt"],
                            "hint": reflection["hint"], "text": engine._step(step)["reflection"]}
                           if reflection and done else None),
        }
        out = self._base(engine, step, text, at, n, data)
        if decided and view:
            cli = _cli(engine, step, text, self._line(engine, step, at, n, view))
            cli["can_auto_start"] = self._can_auto_start(engine, step, at, n)
            out["cli"] = cli
        return out

    def _launch(self, engine, step, at, n):
        view = self._attempt(at, n)
        if view is None or view["decision"] == "pending":
            raise part_steps._error("not_decided", engine._text(step)["messages"]["not_decided"])
        _start_ai(engine, step, engine._text(step), engine.paths.project, engine._step(step))

    def start(self, engine, step):
        with engine._lock:
            n, at = self._open(engine, step)
            if engine._status(step) != "active":
                raise part_steps._error("step_done", "This step is already done.")
            self._launch(engine, step, at, n)

    def auto_start(self, engine, step):
        n = self._n(step)
        at = _attempts(engine)
        _auto(engine, step, lambda: self._can_auto_start(engine, step, at, n),
              lambda: self._launch(engine, step, at, n))

    def submit(self, engine, step, data):
        with engine._lock:
            n, at = self._open(engine, step)
            action = _data(data, ("decide", "rerun", "reflect"))
            text = engine._text(step)
            if action == "reflect":
                if engine._status(step) != "done" or not text["ui"].get("reflection"):
                    raise part_steps._error("bad_input", "This step does not do that.")
                engine._step(step)["reflection"] = _text_field(data.get("text"), text["messages"])
                engine._save()
                return
            if action == "decide":
                if engine._status(step) != "active":
                    raise part_steps._error("step_done", "This step is already done.")
                if data.get("choice") not in ("keep", "undo"):
                    raise part_steps._error("bad_input", text["messages"]["bad_choice"])
                at.decide(n, data["choice"])
                engine._save()
                return
        at.rerun_iteration_zero()

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            n = self._n(step)
            at = _attempts(engine)
            text = engine._text(step)
            view = self._attempt(at, n)
            if view is None or view["decision"] == "pending":
                result = {"ok": False, "nudges": [], "items": [
                    {"label": text["gate"]["decided"]["label"], "ok": False, "detail": text["gate"]["decided"]["fail"]}]}
            else:
                result = at.check_log(through=n)
            _settle(engine, step, result, ends_cli=True)


def finished_text(engine, course_text):
    """Part 4's finished words: the Practice version when the participant worked on the Practice baseline."""
    if "finished_body_practice" not in course_text or engine.paths is None:
        return course_text
    if _attempts(engine).source() != "practice":
        return course_text
    return dict(course_text, finished_body=course_text["finished_body_practice"])


store.STEP_KINDS.setdefault("choose_start", ChooseStart())
store.STEP_KINDS.setdefault("known_good", KnownGood())
store.STEP_KINDS.setdefault("hypothesis", Hypothesis())
store.STEP_KINDS.setdefault("edit", Edit())
store.STEP_KINDS.setdefault("measure", Measure())
store.STEP_KINDS.setdefault("decide", Decide())
