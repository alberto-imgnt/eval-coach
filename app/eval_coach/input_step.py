"""Choose Part 3's input pair without touching the source files."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile

from . import criteria_steps, import_checks, parsers, part_steps, project, resources
from . import state as store

FILES = ("prompt", "test_cases")
EARLIER = {"prompt": ("part1", "part-1", "rewrite"), "test_cases": ("part2", "part-2", "test-file")}
PRACTICE = {"prompt": project.NORTHWIND_PROMPT, "test_cases": project.NORTHWIND_TEST_CASES}


def _digest(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _read(path):
    try:
        with path.open("rb") as file:
            data = file.read(import_checks.MAX_BYTES + 1)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    if len(data) > import_checks.MAX_BYTES:
        return None, "too_large"
    return data, _problem(data)


def _problem(data):
    if b"\0" in data:
        return "not_text"
    if not import_checks.decode(data)[0].strip():
        return "blank"
    return None


def _test_input(body):
    return " ".join(criteria_steps._section(body, criteria_steps._TEST_INPUT)).split()


def _findings(raw, problem, key, words):
    if problem:
        return [{"code": problem, "message": words[problem]}]
    if key == "prompt":
        return []
    body = import_checks.decode(raw)[0]
    count = len(parsers.parse_test_cases(body))
    findings = [
        {"code": item["code"], "message": words[item["code"]].format(
            count=count, min=import_checks.MIN_CRITERIA, missing=import_checks.MIN_CRITERIA - count)}
        for item in import_checks.analyze(None, body)["blocking"]
    ]
    if not _test_input(body):
        findings.append({"code": "no_input", "message": words["no_input"]})
    return findings


def _earlier(engine, key, words):
    _, part_id, step = EARLIER[key]
    part = store.part_by_id(part_id)
    fields = {"part": f"Part {part.n}"}
    if part_id in engine._lessons_block()["skipped_parts"]:
        return None, None, words["skipped"].format(**fields)
    progress = engine._progress_of(part, create=False)
    if step not in progress["done"]:
        return None, None, words["unfinished"].format(**fields)
    path = engine.paths.part1_prompt(step) if key == "prompt" else engine.paths.part2_file(key)
    raw, problem = _read(path)
    findings = _findings(raw, problem, key, words)
    if findings:
        return None, raw, " ".join(f["message"] for f in findings)
    if key == "prompt":
        prompt = import_checks.decode(raw)[0].replace("\r\n", "\n").replace("\r", "\n")
        carried = part_steps.run_copy(prompt, engine.content["steps"][step]["divider"]).encode("utf-8")
        if len(carried) > import_checks.MAX_BYTES:
            return None, raw, words["too_large"]
        return carried, raw, None
    return raw, raw, None


def _backup(path, folder):
    digest = store.file_sha256(path)
    destination = folder / f"{path.name}.{digest[:8]}"
    if destination.exists():
        if store.file_sha256(destination) != digest:
            raise FileExistsError(destination)
        return
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temp:
        tmp = folder / os.path.basename(temp.name)
        try:
            with path.open("rb") as source:
                shutil.copyfileobj(source, temp)
        except OSError:
            temp.close()
            tmp.unlink()
            raise
    try:
        if store.file_sha256(tmp) != digest:
            raise OSError("The input changed while it was being copied.")
        try:
            os.link(tmp, destination)
        except FileExistsError:
            if store.file_sha256(destination) != digest:
                raise
    finally:
        tmp.unlink()


class ChooseInputs:
    def _snapshot(self, engine, step):
        text = engine._text(step)
        words, ui = text["reasons"], text["ui"]
        done = engine._status(step) == "done"
        selected = engine._step(step)["choice"]
        result = {}
        for key in FILES:
            kind = EARLIER[key][0]
            practice = project.strip_catch_up_comment(resources.read_bytes(PRACTICE[key]))
            path = getattr(engine.paths, key)
            raw, problem = _read(path)
            carried, original, reason = _earlier(engine, key, words)
            source = "own" if engine.progress["starter"] == "own" else "project"
            if raw is not None and raw == carried:
                source = kind
            elif raw is not None and raw == practice:
                source = "practice"
            saved = selected[key]
            if saved.get("source") and (done or saved["sha256"] == _digest(raw)):
                source = saved["source"]
            state = None
            if done:
                current = carried if source == kind else practice if source == "practice" else raw
                if source == kind and original is not None and carried is None:
                    state = "changed"
                elif current is None:
                    state = "gone" if (problem == "missing" or source == kind) else "changed"
                else:
                    state = "unchanged" if _digest(current) == saved.get("sha256") else "changed"
            warning = None
            if key == "prompt" and carried is not None:
                record = engine._progress_of(store.PART_1, create=False)["steps"]["rewrite"]
                prompt = import_checks.decode(original)[0].replace("\r\n", "\n").replace("\r", "\n")
                if record["prompt_hash"] and part_steps._sha(prompt) != record["prompt_hash"]:
                    warning = ui["changed_after_answer"]
            result[key] = {
                "path": path, "raw": raw, "source": source, "source_state": state,
                "findings": _findings(raw, problem, key, words),
                "sources": {kind: carried, "practice": practice},
                "offer": {"id": kind, "label": ui[kind], "available": carried is not None,
                          "reason": reason, "warning": warning},
            }
        return result

    def _report(self, snapshot, text):
        return {"ok": not any(entry["findings"] for entry in snapshot.values()), "nudges": [],
                "items": [{"label": text["gate"][key]["label"], "ok": False, "detail": item["message"]}
                          for key, entry in snapshot.items() for item in entry["findings"]]}

    def detail(self, engine, step):
        text = engine._text(step)
        ui = text["ui"]
        snapshot = self._snapshot(engine, step)
        files = {}
        for key, entry in snapshot.items():
            raw = entry["raw"]
            files[key] = {
                "name": entry["path"].name, "text": import_checks.decode(raw)[0] if raw is not None else "",
                "source": entry["source"], "label": ui[entry["source"]],
                "state": ui.get(entry["source_state"]),
                "choices": [{"id": "keep", "label": ui["keep"], "available": True},
                            entry["offer"], {"id": "practice", "label": ui["practice"], "available": True}],
            }
        prompt, cases = files["prompt"], files["test_cases"]
        notes = []
        test_input = _test_input(cases["text"])
        prompt_words = prompt["text"].split()
        expected = " ".join(test_input)
        if test_input and prompt_words and f" {expected} " not in f" {' '.join(prompt_words)} ":
            notes.append(ui["mismatch"])
        if engine.progress["starter"] == "own" and any(
            file["source"] in ("practice", "part1", "part2") for file in files.values()
        ):
            notes.append(ui["own_task_mix"])
        view = part_steps._base(engine, step, text, {"files": files, "notes": notes,
                                "both": all(entry["offer"]["available"] for entry in snapshot.values())})
        view["gate"] = self._report(snapshot, text)
        view["ready"] = view["gate"]["ok"]
        return view

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_active(step)
            text = engine._text(step)
            messages = text["messages"]
            if data == {"both": "mine"}:
                use = {key: EARLIER[key][0] for key in FILES}
            elif isinstance(data, dict) and set(data) == {"use"} and isinstance(data["use"], dict):
                use = data["use"]
            else:
                raise part_steps._error("bad_input", messages["bad_input"])
            if not use or any(key not in FILES or value not in ("keep", "practice", EARLIER[key][0])
                              for key, value in use.items()):
                raise part_steps._error("bad_input", messages["bad_input"])
            snapshot = self._snapshot(engine, step)
            picks = []
            for key, source in use.items():
                if source == "keep":
                    continue
                entry = snapshot[key]
                raw = entry["sources"][source]
                if raw is None:
                    raise part_steps._error("input_unavailable",
                                            messages["unavailable"].format(reason=entry["offer"]["reason"]))
                picks.append((key, source, entry, raw))
            choice = engine._step(step)["choice"]
            try:
                for _, _, entry, raw in picks:
                    path = entry["path"]
                    if raw != entry["raw"] and (path.exists() or path.is_symlink()):
                        _backup(path, engine.paths.project / project.REPLACED_INPUTS)
                for key, source, entry, raw in picks:
                    if raw != entry["raw"]:
                        store.write_bytes_atomic(entry["path"], raw)
                    choice[key] = {"source": source, "sha256": _digest(raw)}
                if picks:
                    engine._save()
            except OSError as exc:
                raise part_steps._error("folder_busy", messages["save_failed"]) from exc

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            snapshot = self._snapshot(engine, step)
            result = self._report(snapshot, engine._text(step))
            if result["ok"]:
                engine._step(step)["choice"] = {
                    key: {"source": entry["source"], "sha256": _digest(entry["raw"])}
                    for key, entry in snapshot.items()
                }
            part_steps._finish(engine, step, result)


store.STEP_KINDS.setdefault("choose_inputs", ChooseInputs())
