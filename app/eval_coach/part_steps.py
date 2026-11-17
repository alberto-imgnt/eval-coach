"""The three step kinds Part 1 uses, each driven by the step's content in content/part-1-steps.json.

write_and_run  a prompt editor and one blind CLI run (the `cold` and `rewrite` steps)
score_form     the participant's own yes or no marks against five requirements (`score` and `rescore`)
write_pair     two texts and a note, with no CLI (`own`)

Nothing here reads an output to decide anything. A gate reads the participant's own saved words and the files the
app wrote, and the score is counted from the participant's own answers.
"""
from __future__ import annotations

import hashlib
import re

from . import gates, project
from . import resources
from . import state as store

MAX_TEXT = 50000
MAX_LINE = 200
YES_NO = ("yes", "no")
# Kit files that stay closed until the step that makes them useful is done: seeing the sample prompts earlier
# would replace the participant's own discovery.
GATED_KIT = {
    "kit/part1/sample-rtcc.md": ("part-1", "rescore"),
    "kit/part1/sample-rise.md": ("part-1", "rescore"),
}


def _error(code, message):
    from .engine import EngineError  # engine imports this module, so the import waits until it is needed
    return EngineError(code, message)


def _squash(text):
    return " ".join(str(text).split())


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _line(value, step_text):
    """One plain line of text: whitespace and control characters become single spaces."""
    if not isinstance(value, str):
        raise _error("bad_input", step_text["messages"].get("bad_text", "That text could not be saved."))
    return re.sub(r"[\s\x00-\x1f\x7f-\x9f]+", " ", value).strip()[:MAX_LINE]


def _body(value, step_text):
    if not isinstance(value, str) or len(value) > MAX_TEXT or "\0" in value:
        raise _error("bad_input", step_text["messages"].get("bad_text", "That text could not be saved."))
    return value


def rough_notes():
    return resources.read_text(project.PART1_NOTES).replace("\r\n", "\n").strip("\n")


def run_copy(prompt, divider):
    """What the CLI reads: the participant's words, a plain divider and the rough notes."""
    return prompt.rstrip() + "\n\n" + divider + "\n\n" + rough_notes() + "\n"


def requirements(engine, text):
    """The five requirements, kept once in the scenario of the step that names them."""
    return engine.content["steps"][text["requirements_from"]]["scenario"]["requirements"]


def score_of(rows, answers):
    """The participant's own count: how many of the rows they marked yes. None until every row is answered."""
    marked = [answers.get(row["id"]) for row in rows]
    if not all(mark in YES_NO for mark in marked):
        return None
    return marked.count("yes")


def _base(engine, step, text, data):
    return {
        "id": step, "title": text["title"], "status": engine._status(step), "track": engine._track(),
        "kind": text["kind"], "goal": text["goal"], "why": text["why"], "instructions": text["instructions"],
        "cli": None, "checklist": [], "last_check": engine._step(step)["last_check"],
        "question": engine._step_question_public(step), "troubleshooting": text["troubleshooting"],
        "ui": text.get("ui", {}), "data": data,
    }


def _finish(engine, step, result, ends_cli=False):
    """Record a gate's result; a pass marks the step done (and closes the CLI of a step that ran one)."""
    engine._step(step)["last_check"] = result
    if result["ok"]:
        if ends_cli:
            engine._stop_cli()
        engine._mark_done(step)
    engine._save()


class WriteAndRun:
    """A prompt editor and one run of the participant's own CLI in a folder that holds only the prompt."""

    def _record(self, engine, step):
        return engine._step(step)

    def _prompt(self, engine, step):
        return gates.read_text(engine.paths.part1_prompt(step))

    def _output(self, engine, step):
        return gates.read_text(engine.paths.part1_output(step))

    def _labels(self, text):
        return text.get("labels", [])

    def _model_differs(self, engine, step):
        if step != "rewrite":
            return False
        mine = _squash(engine._step(step)["model_name"]).casefold()
        first = _squash(engine._step("cold")["model_name"]).casefold()
        return bool(mine and first and mine != first)

    def detail(self, engine, step):
        text = engine._text(step)
        record = engine._step(step)
        prompt, output = self._prompt(engine, step), self._output(engine, step)
        saved = bool(prompt.strip())
        data = {
            "scenario": text.get("scenario"),
            "prompt": prompt, "prompt_saved": saved,
            "notes": rough_notes(), "divider": text["divider"],
            "preview": run_copy(prompt, text["divider"]) if saved else "",
            "model_name": record["model_name"],
            "output": output if output.strip() else None,
            "prompt_changed": bool(record["prompt_hash"]) and saved and _sha(prompt) != record["prompt_hash"],
        }
        if self._labels(text):
            data["labels"] = self._labels(text)
            data["framework"] = record["framework"]
            data["cold_prompt"] = self._prompt(engine, "cold")
            data["model_note"] = text["gate"]["nudge_model"]["text"] if self._model_differs(engine, step) else None
        active = engine._cli_active(step)
        view = _base(engine, step, text, data)
        view["cli"] = {"line": text["line"], "folder_label": text["folder_label"], "started": active,
                       "sent": active and engine._sent, "blocked": None,
                       "start_blocked": None if saved else text["messages"]["start_blocked"]}
        return view

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_configured()
            engine._require_known(step)
            if not isinstance(data, dict):
                raise _error("bad_input", "The submitted data must be an object.")
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            known = {"prompt", "model_name"} | ({"framework"} if self._labels(text) else set())
            if not known & set(data):
                raise _error("bad_input", "This step has nothing to save.")
            if "framework" in data:
                ids = [label["id"] for label in self._labels(text)]
                if data["framework"] not in ids + [""]:
                    raise _error("bad_input", text["messages"]["bad_framework"])
            if "prompt" in data:
                value = _body(data["prompt"], text)
                try:
                    store.write_bytes_atomic(engine.paths.part1_prompt(step), value.encode("utf-8"))
                except OSError as exc:
                    raise _error("folder_busy", f"Your prompt could not be saved: {exc}") from exc
            if "model_name" in data:
                record["model_name"] = _line(data["model_name"], text)
            if "framework" in data:
                record["framework"] = data["framework"]
            engine._save()

    def start(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text, record, paths = engine._text(step), engine._step(step), engine.paths
            prompt = self._prompt(engine, step)
            if not prompt.strip():
                raise _error("prompt_missing", text["messages"]["prompt_missing"])
            engine._stop_cli()
            work = paths.part1_work(step)
            try:
                project.clear_dir(work)
                store.write_bytes_atomic(work / "prompt.md", run_copy(prompt, text["divider"]).encode("utf-8"))
                try:
                    paths.part1_output(step).unlink()  # an earlier run's answer must not pass for this run's
                except FileNotFoundError:
                    pass
            except OSError as exc:
                raise _error("folder_busy", f"The working folder could not be prepared: {exc}") from exc
            try:
                engine.terminal.start(engine.progress["cli_command"], str(work), text["title"],
                                      env=engine._cli_env(), owner=step)
            except (ValueError, OSError) as exc:
                raise _error("cli_start_failed", f"Your AI could not be started: {exc}") from exc
            engine._cli_step = step
            engine._sent = False
            record["prompt_hash"] = _sha(prompt)
            engine._save()
            engine._start_watcher(work / "output.txt", paths.part1_output(step))

    def send(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text = engine._text(step)
            if not engine._cli_active(step):
                raise _error("cli_not_running", text["messages"]["cli_not_running"])
        try:
            engine.terminal.type_line(text["line"])  # outside the lock: it takes 400 ms
        except OSError as exc:
            raise _error("cli_not_running", f"The line could not be typed: {exc}") from exc
        with engine._lock:
            if engine._cli_active(step):
                engine._sent = True

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            prompt, output = self._prompt(engine, step), self._output(engine, step)
            report = gates.Report(text["gate"])
            if self._labels(text):
                report.add("framework", record["framework"] in [label["id"] for label in self._labels(text)])
            report.add("prompt", bool(prompt.strip()))
            if step == "rewrite":
                first = self._prompt(engine, "cold")
                report.add("differs", not prompt.strip() or _squash(prompt) != _squash(first))
            report.add("output", bool(output.strip()))
            report.add("model", bool(record["model_name"].strip()))
            if self._model_differs(engine, step):
                report.nudges.append(text["gate"]["nudge_model"]["text"])
            if record["prompt_hash"] and prompt.strip() and _sha(prompt) != record["prompt_hash"]:
                report.nudges.append(text["gate"]["nudge_prompt_changed"]["text"])
            _finish(engine, step, report.result(), ends_cli=True)


class ScoreForm:
    """Yes or no marks against the five requirements, counted from the participant's own answers."""

    def _view_data(self, engine, step, text):
        rows = requirements(engine, text)
        record = engine._step(step)
        answers = record["answers"]
        paths = engine.paths
        output = gates.read_text(paths.part1_output(text["source_step"]))
        yes = score_of(rows, answers)
        score = None if yes is None else {"yes": yes, "total": len(rows),
                                          "text": text["ui"]["score_text"].format(yes=yes, total=len(rows))}
        fields = text.get("fields", [])
        data = {
            "output": output if output.strip() else None,
            "rows": [{"id": row["id"], "label": row["label"], "answer": answers.get(row["id"], "")} for row in rows],
            "answered": sum(1 for row in rows if answers.get(row["id"]) in YES_NO),
            "score": score,
            "all_yes": yes == len(rows),
            "fields": fields,
            "gap": record.get("gap", "") if "gap" in fields else None,
            "in_prompt": record.get("in_prompt", "") if "in_prompt" in fields else None,
            "reflections": [{"id": r["id"], "label": r["label"], "value": record["reflections"].get(r["id"], "")}
                            for r in text.get("reflections", [])],
        }
        if text.get("compare_with"):
            data["compare"] = self._compare(engine, step, text, rows, score)
        return data

    def _compare(self, engine, step, text, rows, second_score):
        words = text["compare"]
        paths = engine.paths
        first_answers = engine._step(text["compare_with"])["answers"]
        first_yes = score_of(rows, first_answers)

        def side(prompt_step, yes):
            return {"prompt": gates.read_text(paths.part1_prompt(prompt_step)),
                    "output": gates.read_text(paths.part1_output(prompt_step)),
                    "score": None if yes is None else {"yes": yes, "total": len(rows),
                                                       "text": text["ui"]["score_text"].format(yes=yes, total=len(rows))}}

        second_yes = None if second_score is None else second_score["yes"]
        change = None if first_yes is None or second_yes is None else second_yes - first_yes
        change_text = None
        if change is not None:
            key = "change_up" if change > 0 else "change_down" if change < 0 else "change_same"
            change_text = words[key].format(n=abs(change))
        notes = [words["variation_note"]]
        if change is not None and change < 0:
            notes.append(words["worse_note"])
        return {"first": side("cold", first_yes), "second": side("rewrite", second_yes), "change": change,
                "change_text": change_text, "notes": notes,
                "words": {k: words[k] for k in ("heading", "first_heading", "second_heading", "prompt_label",
                                                 "output_label", "score_label", "score_empty")}}

    def detail(self, engine, step):
        text = engine._text(step)
        return _base(engine, step, text, self._view_data(engine, step, text))

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_configured()
            engine._require_known(step)
            if not isinstance(data, dict):
                raise _error("bad_input", "The submitted data must be an object.")
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            bad = _error("bad_input", text["messages"]["bad_answers"])
            fields = text.get("fields", [])
            reflections = [r["id"] for r in text.get("reflections", [])]
            if not {"answers", "gap", "in_prompt", "reflections"} & set(data):
                raise _error("bad_input", "This step has nothing to save.")
            ids = [row["id"] for row in requirements(engine, text)]
            if "answers" in data:
                answers = data["answers"]
                if not isinstance(answers, dict) or any(k not in ids or v not in YES_NO for k, v in answers.items()):
                    raise bad
                record["answers"].update(answers)
            if "gap" in data:
                if "gap" not in fields:
                    raise bad
                record["gap"] = _body(data["gap"], text)
            if "in_prompt" in data:
                options = [o["id"] for o in text["ui"].get("in_prompt_options", [])]
                if "in_prompt" not in fields or data["in_prompt"] not in options + [""]:
                    raise bad
                record["in_prompt"] = data["in_prompt"]
            if "reflections" in data:
                given = data["reflections"]
                if not isinstance(given, dict) or any(k not in reflections for k in given):
                    raise bad
                for key, value in given.items():
                    record["reflections"][key] = _body(value, text)
            engine._save()

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            rows = requirements(engine, text)
            fields = text.get("fields", [])
            report = gates.Report(text["gate"])
            answered = sum(1 for row in rows if record["answers"].get(row["id"]) in YES_NO)
            report.add("rows", answered == len(rows), count=answered)
            if "gap" in fields:
                report.add("gap", bool(record["gap"].strip()))
            if "in_prompt" in fields:
                report.add("in_prompt", bool(record["in_prompt"]))
            for item in text.get("reflections", []):
                report.add(item["id"], bool(record["reflections"].get(item["id"], "").strip()))
            _finish(engine, step, report.result())


class WritePair:
    """A before and an after text and a note on the labels. No CLI is started."""

    def _texts(self, engine):
        return {which: gates.read_text(engine.paths.part1_own(which)) for which in project.PART1_OWN_FILES}

    def detail(self, engine, step):
        text = engine._text(step)
        data = dict(self._texts(engine), labels=engine._step(step)["labels"])
        return _base(engine, step, text, data)

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_configured()
            engine._require_known(step)
            if not isinstance(data, dict):
                raise _error("bad_input", "The submitted data must be an object.")
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            if not {"before", "after", "labels"} & set(data):
                raise _error("bad_input", "This step has nothing to save.")
            for which in project.PART1_OWN_FILES:
                if which in data:
                    value = _body(data[which], text)
                    try:
                        store.write_bytes_atomic(engine.paths.part1_own(which), value.encode("utf-8"))
                    except OSError as exc:
                        raise _error("folder_busy", f"Your text could not be saved: {exc}") from exc
            if "labels" in data:
                record["labels"] = _line(data["labels"], text)
            engine._save()

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            texts = self._texts(engine)
            report = gates.Report(text["gate"])
            report.add("before", bool(texts["before"].strip()))
            report.add("after", bool(texts["after"].strip()))
            report.add("labels", bool(record["labels"].strip()))
            both = bool(texts["before"].strip() and texts["after"].strip())
            report.add("differs", not both or _squash(texts["before"]) != _squash(texts["after"]))
            _finish(engine, step, report.result())


KINDS = {"write_and_run": WriteAndRun(), "score_form": ScoreForm(), "write_pair": WritePair()}
for _kind, _handler in KINDS.items():
    store.STEP_KINDS.setdefault(_kind, _handler)
