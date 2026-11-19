"""The three step kinds Part 2 uses, each driven by the step's content in content/part-2-steps.json.

criteria_table  the criteria worksheet shared by `draft` and `thresholds`
test_file       build, edit and check test-cases.md from the worksheet (`test-file`)
reveal_compare  the Northwind reference beside the participant's own file (`reference`)

Part 2 runs nothing: no CLI, no checker, no model. A gate reads the participant's own saved worksheet and file and
their own ticks and choices. Nothing here reads terminal output to decide anything.
"""
from __future__ import annotations

import json
import re

from . import gates, import_checks, parsers, project, resources
from . import state as store
from .part_steps import _base, _body, _error, _finish, _squash, rough_notes

MAX_ROWS = 12
MAX_CELL = 400
NOT_CHECKED = re.compile(r"^\s*not\s+checked\s*:", re.I)
_HEADING = re.compile(r"^\s*#{1,6}\s")
_TEST_INPUT = re.compile(r"^\s*#{1,6}\s*test\s+input\b", re.I)
_LISTS = re.compile(r"^\s*#{1,6}\s*supporting\s+lists?\b", re.I)
_LIST_WORD = re.compile(r"\b(?:banned|required|list)\b", re.I)
_QUOTED = re.compile(r'"[^"\n]+"|“[^”\n]+”|`[^`\n]+`')


# --- shared helpers ------------------------------------------------------------------------------------------------

def _cell(value, text):
    """One plain line: whitespace and control characters become single spaces."""
    if not isinstance(value, str):
        raise _error("bad_input", text["messages"]["bad_rows"])
    return re.sub(r"[\s\x00-\x1f\x7f-\x9f]+", " ", value).strip()[:MAX_CELL]


def _requirements(engine):
    """The five requirements, kept once in the scenario of `draft`."""
    return engine.content["steps"]["draft"]["scenario"]["requirements"]


def _type_ids(text):
    return [t["id"] for t in text["types"]]


def _list_text(numbers, words):
    """'row 2', 'rows 2 and 3' or 'rows 1, 2 and 4' from row numbers."""
    if len(numbers) == 1:
        return words["row"].format(n=numbers[0])
    names = [str(n) for n in numbers]
    return words["rows"].format(list=", ".join(names[:-1]) + " " + words["and"] + " " + names[-1])


def _read_rows(engine):
    """The saved worksheet rows, cleaned. A missing or unreadable file is an empty worksheet."""
    raw = gates.read_text(engine.paths.part2_file("worksheet"))
    try:
        rows = json.loads(raw).get("rows", []) if raw.strip() else []
    except (ValueError, AttributeError):
        return []
    clean = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            clean.append({key: row.get(key, "") if isinstance(row.get(key, ""), str) else ""
                          for key in ("requirement", "criterion", "type", "threshold")})
    return clean[:MAX_ROWS]


def _write_rows(engine, rows, text):
    try:
        store.write_json_atomic(engine.paths.part2_file("worksheet"), {"rows": rows})
    except OSError as exc:
        raise _error("folder_busy", text["messages"]["save_failed"].format(error=exc)) from exc


def _section(text, start):
    """The non-empty lines under the first heading that matches `start`, up to the next heading."""
    lines, inside, found = text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), False, []
    for line in lines:
        if inside and _HEADING.match(line):
            break
        if inside:
            found.append(line.strip())
        elif start.match(line):
            inside = True
    return [line for line in found if line]


def _write_file(engine, text_value, text):
    try:
        store.write_bytes_atomic(engine.paths.part2_file("test_cases"), text_value.encode("utf-8"))
    except OSError as exc:
        raise _error("folder_busy", text["messages"]["save_failed"].format(error=exc)) from exc


# --- criteria_table --------------------------------------------------------------------------------------------------

class CriteriaTable:
    """The worksheet. `draft` edits every field; `thresholds` edits only the threshold column."""

    def _thresholds_only(self, text):
        return text.get("edit") == "thresholds"

    def _part1(self, engine, text):
        """The participant's own Part 1 marks and gap, for reading only. None when Part 1 has none."""
        part = store.part_by_id("part-1")
        words = text.get("part1")
        if part is None or not words or engine.progress is None:
            return None
        record = engine._progress_of(part, create=False)["steps"].get("score")
        if not isinstance(record, dict):
            return None
        answers = record.get("answers") if isinstance(record.get("answers"), dict) else {}
        gap = record.get("gap") if isinstance(record.get("gap"), str) else ""
        if not answers and not gap.strip():
            return None
        marks = [{"id": r["id"], "label": r["label"], "answer": answers.get(r["id"], "")}
                 for r in _requirements(engine)]
        return {"marks": marks, "gap": gap}

    def _notes(self, engine, text, rows):
        """Vague words in a threshold: a note for the row, never a block. Quoted words are the participant's own terms."""
        notes = []
        for number, row in enumerate(rows, 1):
            if NOT_CHECKED.match(row["threshold"]):
                continue
            words = import_checks.vague_words(row["threshold"])
            if words:
                notes.append({"row": number, "words": words,
                              "text": text["notes"]["vague"]["text"].format(
                                  n=number, words=", ".join(f"“{w}”" for w in words))})
        return notes

    def detail(self, engine, step):
        text, record = engine._text(step), engine._step(step)
        rows = _read_rows(engine)
        thresholds_only = self._thresholds_only(text)
        data = {
            "rows": rows,
            "saved": engine.paths.part2_file("worksheet").is_file(),
            "requirements": _requirements(engine),
            "types": text["types"],
            "ticks": [{"id": t["id"], "label": t["label"], "checked": record["checks"].get(t["id"]) is True}
                      for t in text["ticks"]],
            "max_rows": MAX_ROWS,
            "min_rows": text.get("min_rows", 3),
            "thresholds_only": thresholds_only,
            "show_threshold": thresholds_only,
            "scenario": text.get("scenario"),
            "notes": [],
        }
        if text.get("scenario"):
            data["rough_notes"] = rough_notes()
        if "part1" in text:
            data["part1"] = self._part1(engine, text)
        if thresholds_only:
            data["notes"] = self._notes(engine, text, rows)
        return _base(engine, step, text, data)

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_configured()
            engine._require_known(step)
            if not isinstance(data, dict):
                raise _error("bad_input", "The submitted data must be an object.")
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            bad = _error("bad_input", text["messages"]["bad_rows"])
            if not {"rows", "checks"} & set(data):
                raise _error("bad_input", "This step has nothing to save.")
            if "checks" in data:
                given, ids = data["checks"], [t["id"] for t in text["ticks"]]
                if not isinstance(given, dict) or any(k not in ids or not isinstance(v, bool) for k, v in given.items()):
                    raise bad
                record["checks"].update(given)
            if "rows" in data:
                self._save_rows(engine, step, text, data["rows"], bad)
            engine._save()

    def _save_rows(self, engine, step, text, given, bad):
        if not isinstance(given, list) or len(given) > MAX_ROWS or not all(isinstance(r, dict) for r in given):
            raise bad
        types = _type_ids(text) + [""]
        rows = []
        for row in given:
            kind = row.get("type", "")
            if kind not in types:
                raise bad
            rows.append({"requirement": _cell(row.get("requirement", ""), text),
                         "criterion": _cell(row.get("criterion", ""), text), "type": kind,
                         "threshold": _cell(row.get("threshold", ""), text)})
        if self._thresholds_only(text):
            saved = _read_rows(engine)
            if len(rows) != len(saved):
                raise _error("bad_input", text["messages"]["rows_locked"])
            rows = [dict(old, threshold=new["threshold"]) for old, new in zip(saved, rows)]
        _write_rows(engine, rows, text)

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            rows = _read_rows(engine)
            report = gates.Report(text["gate"])
            if self._thresholds_only(text):
                self._gate_thresholds(text, rows, report)
            else:
                self._gate_rows(text, rows, report)
            for tick in text["ticks"]:
                report.add(tick["id"], record["checks"].get(tick["id"]) is True)
            _finish(engine, step, report.result())

    def _gate_rows(self, text, rows, report):
        words = text["words"]
        minimum = text.get("min_rows", 3)
        report.add("rows", len(rows) >= minimum, count=len(rows), missing=max(0, minimum - len(rows)), min=minimum)
        known = _type_ids(text)
        incomplete = [n for n, r in enumerate(rows, 1)
                      if not (r["requirement"].strip() and r["criterion"].strip() and r["type"] in known)]
        report.add("filled", not incomplete, rows=_list_text(incomplete, words) if incomplete else "")
        report.add("content", any(r["type"] == "content" for r in rows))
        seen, repeated = {}, []
        for n, row in enumerate(rows, 1):
            key = _squash(row["criterion"]).casefold()
            if key and key in seen:
                repeated += [seen[key], n] if seen[key] not in repeated else [n]
            elif key:
                seen[key] = n
        report.add("unique", not repeated, rows=_list_text(sorted(set(repeated)), words) if repeated else "")

    def _gate_thresholds(self, text, rows, report):
        missing = [n for n, r in enumerate(rows, 1) if not r["threshold"].strip()]
        report.add("thresholds", bool(rows) and not missing,
                   rows=_list_text(missing, text["words"]) if missing else "")


# --- the test case file --------------------------------------------------------------------------------------------

def build_file(engine, text, rows):
    """The layout Part 3 reads, with the participant's own words under each criterion."""
    build = text["build"]
    labels = {t["id"]: t["label"] for t in engine.content["steps"]["draft"]["types"]}
    out = [f"# {build['title']}", "", "## Test input", rough_notes(), "", "## Criteria", ""]
    for n, row in enumerate(rows, 1):
        out += [f"### C{n}: {row['criterion']}", f"- Requirement: {row['requirement']}",
                f"- Type: {labels.get(row['type'], row['type'])}", f"- Threshold: {row['threshold']}", ""]
    out += ["## Supporting lists", build["supporting_placeholder"], ""]
    return "\n".join(out)


def file_view(engine, text):
    """The saved file and what the checks say about it. `text` holds the findings' words."""
    path = engine.paths.part2_file("test_cases")
    body = gates.read_text(path)
    saved = bool(body.strip())
    criteria = parsers.parse_test_cases(body) if saved else []
    blocking, notes = _findings(text, body, criteria, saved)
    return {"text": body, "saved": saved, "has_worksheet": bool(_read_rows(engine)),
            "criteria": [{"id": c["id"], "name": c["name"]} for c in criteria],
            "findings": {"blocking": blocking, "notes": notes}}


def _finding(texts, code, **fields):
    return {"code": code, "message": texts[code]["text"].format(**fields), "criterion": fields.get("id")}


def _findings(text, body, criteria, saved):
    """(blocking, notes) for the saved file, worded for this step. Notes never block."""
    words = text["findings"]
    blocking, notes = [], []
    if not saved:
        return blocking, notes
    if not _section(body, _TEST_INPUT):
        blocking.append(_finding(words, "no_input"))
    analysis = import_checks.analyze(None, body)
    for item in analysis["blocking"]:
        if item["code"] == "no_criteria":
            blocking.append(_finding(words, "no_criteria"))
        elif item["code"] == "few_criteria":
            minimum = import_checks.MIN_CRITERIA
            blocking.append(_finding(words, "few_criteria", count=len(criteria), min=minimum,
                                     missing=minimum - len(criteria)))
        elif item["code"] == "no_content_criterion":
            blocking.append(_finding(words, "no_content_criterion"))
    entries = [line for line in _section(body, _LISTS) if not re.match(r"^[-*]?\s*example\b", line, re.I)]
    for c in criteria:
        if NOT_CHECKED.match(c["threshold"]):
            continue
        fields = {"id": c["id"], "name": c["name"]}
        if not c["threshold"].strip():
            notes.append(_finding(words, "missing_threshold", **fields))
        else:
            vague = import_checks.vague_words(c["threshold"])
            if vague:
                notes.append(_finding(words, "vague", words=", ".join(f"“{w}”" for w in vague), **fields))
            if not entries and _LIST_WORD.search(_QUOTED.sub(" ", c["threshold"])):
                notes.append(_finding(words, "list_missing", **fields))
        if not c["requirement"].strip():
            notes.append(_finding(words, "no_requirement", **fields))
    return blocking, notes


class TestCaseFile:
    """Build `test-cases.md` from the worksheet, edit it, and pass the file checks."""

    def detail(self, engine, step):
        text = engine._text(step)
        return _base(engine, step, text, file_view(engine, text))

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_configured()
            engine._require_known(step)
            if not isinstance(data, dict):
                raise _error("bad_input", "The submitted data must be an object.")
            engine._require_active(step)
            _apply_file(engine, engine._text(step), data)
            engine._save()

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text = engine._text(step)
            view = file_view(engine, text)
            report = gates.Report(text["gate"])
            blocking = {f["code"]: f["message"] for f in view["findings"]["blocking"]}
            report.add("file", view["saved"])
            report.add("input", view["saved"] and "no_input" not in blocking, message=blocking.get("no_input", ""))
            criteria_message = blocking.get("no_criteria") or blocking.get("few_criteria", "")
            report.add("criteria", view["saved"] and not criteria_message, message=criteria_message)
            report.add("content", view["saved"] and "no_content_criterion" not in blocking and not criteria_message,
                       message=blocking.get("no_content_criterion") or criteria_message)
            _finish(engine, step, report.result())


def _apply_file(engine, text, data):
    """Save the file text, or build it from the worksheet. A saved file is replaced by a build only with `replace`."""
    allowed = {"text", "build", "replace"}
    if not data or not set(data) <= allowed or not ({"text", "build"} & set(data)) or ("text" in data and "build" in data):
        raise _error("bad_input", text["messages"]["bad_file"])
    if "text" in data:
        _write_file(engine, _body(data["text"], text), text)
        return
    if data["build"] is not True or ("replace" in data and not isinstance(data["replace"], bool)):
        raise _error("bad_input", text["messages"]["bad_file"])
    rows = _read_rows(engine)
    if not rows:
        raise _error("no_worksheet", text["messages"]["no_worksheet"])
    if gates.read_text(engine.paths.part2_file("test_cases")).strip() and data.get("replace") is not True:
        raise _error("confirm_replace", text["messages"]["confirm_replace"])
    _write_file(engine, build_file(engine, text, rows), text)


# --- reveal_compare --------------------------------------------------------------------------------------------------

def reference():
    """The Northwind reference criteria and lists, parsed from the bundled file."""
    body = resources.read_text(project.NORTHWIND_TEST_CASES)
    types = import_checks.criterion_types(body)
    rows = [{"id": c["id"], "name": c["name"], "requirement": c["requirement"], "type": types.get(c["id"], ""),
             "threshold": c["threshold"]} for c in parsers.parse_test_cases(body)]
    return rows, _section(body, _LISTS)


class RevealCompare:
    """The reference criteria beside the participant's own file, once `test-file` is done."""

    def _revealed(self, engine, step):
        return "test-file" in engine._done_of(engine._part_of(step))

    def detail(self, engine, step):
        text, record = engine._text(step), engine._step(step)
        data = file_view(engine, text)
        revealed = self._revealed(engine, step)
        rows, lists = reference() if revealed else ([], [])
        data.update({
            "revealed": revealed, "reference": rows, "lists": lists, "options": text["options"],
            "choices": {k: v for k, v in record["choices"].items() if k in [r["id"] for r in rows]},
            "mine": [{"id": c["id"], "name": c["name"], "threshold": c["threshold"]}
                     for c in parsers.parse_test_cases(data["text"])] if data["saved"] else [],
        })
        return _base(engine, step, text, data)

    def submit(self, engine, step, data):
        with engine._lock:
            engine._require_configured()
            engine._require_known(step)
            if not isinstance(data, dict):
                raise _error("bad_input", "The submitted data must be an object.")
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            if not {"choices", "text"} & set(data) or not set(data) <= {"choices", "text"}:
                raise _error("bad_input", "This step has nothing to save.")
            if "choices" in data:
                given = data["choices"]
                ids = [r["id"] for r in reference()[0]] if self._revealed(engine, step) else []
                options = [o["id"] for o in text["options"]]
                if not isinstance(given, dict) or any(k not in ids or v not in options for k, v in given.items()):
                    raise _error("bad_input", text["messages"]["bad_choices"])
                record["choices"].update(given)
            if "text" in data:
                _apply_file(engine, text, {"text": data["text"]})
            engine._save()

    def check(self, engine, step):
        with engine._lock:
            engine._require_active(step)
            text, record = engine._text(step), engine._step(step)
            rows, _ = reference()
            options = [o["id"] for o in text["options"]]
            missing = [r["name"] for r in rows if record["choices"].get(r["id"]) not in options]
            report = gates.Report(text["gate"])
            report.add("choices", not missing, missing=", ".join(missing))
            _finish(engine, step, report.result())


def strip_thresholds(raw):
    """The worksheet with every threshold emptied. A restart of `thresholds` puts this back in place."""
    try:
        rows = json.loads(raw).get("rows", []) if raw.strip() else []
    except (ValueError, AttributeError):
        rows = []
    clean = [{key: (row.get(key, "") if key != "threshold" and isinstance(row.get(key, ""), str) else "")
              for key in ("requirement", "criterion", "type", "threshold")}
             for row in (rows if isinstance(rows, list) else []) if isinstance(row, dict)]
    return json.dumps({"rows": clean[:MAX_ROWS]}, indent=2, ensure_ascii=False)


# What a step restart puts back, by project file: the original goes to the backup first.
REWRITES = {"part-2/worksheet.json": strip_thresholds}

KINDS = {"criteria_table": CriteriaTable(), "test_file": TestCaseFile(), "reveal_compare": RevealCompare()}
for _kind, _handler in KINDS.items():
    store.STEP_KINDS.setdefault(_kind, _handler)
