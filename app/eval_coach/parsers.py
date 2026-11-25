"""Parsers for test-cases.md and for the checker's printed output."""
from __future__ import annotations

import re

# --- test-cases.md ---------------------------------------------------------

_HEADING_CRITERION = re.compile(r"^\s*#{1,6}\s*C\s*(\d+)\s*(?:[:.)\-–—]\s*(.*))?$", re.I)
_BOLD_CRITERION = re.compile(r"^\s*\*\*\s*C\s*(\d+)\s*[:.)\-–—]\s*(.*?)\s*\*\*\s*:?\s*$", re.I)
_C_LIST = re.compile(r"^\s*(?:[-*]\s+)?\**C\s*(\d+)\**\s*[:.)\-–—]\s*(.+)$", re.I)
_NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")
_HEADING = re.compile(r"^\s*#{1,6}\s*(.+?)\s*#*\s*$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_DECORATION = re.compile(r"[*_`]+")


def _plain(text):
    return _DECORATION.sub("", text).strip()


def _without_fences(lines):
    out, fenced = [], False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def _cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _from_headings(lines):
    """`### C1: Name` blocks, with optional Requirement and Threshold lines."""
    found = []
    current = None
    for line in lines:
        m = _HEADING_CRITERION.match(line) or _BOLD_CRITERION.match(line)
        if m:
            current = {"id": f"C{int(m.group(1))}", "name": _plain(m.group(2) or ""),
                       "requirement": "", "threshold": ""}
            found.append(current)
            continue
        if _HEADING.match(line):
            current = None
            continue
        if current is not None:
            field = re.match(r"^\s*(?:[-*]\s+)?\**\s*(Requirement|Threshold)\s*\**\s*:\s*\**\s*(.*)$",
                             line, re.I)
            if field:
                current[field.group(1).lower()] = field.group(2).strip()
    for item in found:
        if not item["name"]:
            item["name"] = item["requirement"] or item["id"]
    return found


def _column(header, *names):
    for name in names:
        for i, cell in enumerate(header):
            if cell == name:
                return i
    return None


def _from_table(lines):
    """A table with a Threshold, Criterion or Requirement column."""
    for i in range(len(lines) - 1):
        if "|" not in lines[i] or not _TABLE_RULE.match(lines[i + 1]):
            continue
        header = [_plain(c).lower() for c in _cells(lines[i])]
        crit = _column(header, "criterion", "name", "criteria")
        req = _column(header, "requirement")
        thr = _column(header, "threshold", "pass threshold", "pass/fail threshold")
        if thr is None and crit is None and req is None:
            continue
        ident = _column(header, "#", "id", "no", "no.", "number")
        name_col = crit if crit is not None else req
        if name_col is None:
            continue
        found = []
        for row_line in lines[i + 2:]:
            if "|" not in row_line or not row_line.strip():
                break
            row = _cells(row_line)
            if name_col >= len(row):
                continue
            number = None
            if ident is not None and ident < len(row):
                m = re.search(r"\d+", row[ident])
                if m:
                    number = int(m.group(0))
            if number is None:
                m = re.match(r"^\s*C\s*(\d+)\b", _plain(row[0]), re.I)
                number = int(m.group(1)) if m else len(found) + 1
            found.append({
                "id": f"C{number}",
                "name": _plain(row[name_col]) or f"C{number}",
                "requirement": row[req] if req is not None and req < len(row) else "",
                "threshold": row[thr] if thr is not None and thr < len(row) else "",
            })
        if found:
            return found
    return []


def _criteria_section(lines):
    """Lines under a heading that names the criteria; everything if there are no headings."""
    has_heading = any(_HEADING.match(line) for line in lines)
    if not has_heading:
        return lines
    out, inside = [], False
    for line in lines:
        m = _HEADING.match(line)
        if m:
            inside = bool(re.search(r"criteri|\bchecks\b", m.group(1), re.I))
            continue
        if inside:
            out.append(line)
    return out


def _from_list(lines):
    """`C1: ...` lines anywhere, or a numbered list in the criteria section."""
    found = []
    for line in lines:
        m = _C_LIST.match(line)
        if m:
            found.append({"id": f"C{int(m.group(1))}", "name": _name_from_text(m.group(2)),
                          "requirement": "", "threshold": m.group(2).strip()})
    if found:
        return found
    for line in _criteria_section(lines):
        m = _NUMBERED.match(line)
        if m:
            found.append({"id": f"C{int(m.group(1))}", "name": _name_from_text(m.group(2)),
                          "requirement": "", "threshold": m.group(2).strip()})
    return found


def _name_from_text(text):
    plain = _plain(text)
    for sep in (": ", " - ", " – ", " — "):
        if sep in plain:
            return plain.split(sep, 1)[0].strip()
    return plain[:60].strip()


def parse_test_cases(text):
    """Return [{"id","name","requirement","threshold"}]; empty if no criteria are found."""
    lines = _without_fences(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    found = _from_headings(lines) or _from_table(lines) or _from_list(lines)
    seen, unique = set(), []
    for item in found:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)
    return unique


# --- checker output --------------------------------------------------------

_FILE = re.compile(r"^==\s+(.+?)\s*$")
_ROW = re.compile(r"^(C\d+)\s+(PASS|FAIL|NOT CHECKED)\b\s*(.*)$")
_SUMMARY_NEW = re.compile(r"^->\s*(\d+)\s+passed,\s*(\d+)\s+failed,\s*(\d+)\s+NOT CHECKED\s*$")
_SUMMARY_OLD = re.compile(r"^->\s*(\d+)\s*/\s*(\d+)\s+criteria passed\s*$")
_RATE_SECTION = re.compile(r"^==\s*Pass rate per criterion\b", re.I)
_VERDICTS = {"PASS": "P", "FAIL": "F", "NOT CHECKED": "NC"}


class CheckerOutputError(Exception):
    """The printed output does not follow the checker format."""


def _split_row_text(text):
    text = text.strip()
    if ": " in text:
        name, reason = text.split(": ", 1)
        return name.strip(), reason.strip()
    if text.endswith(":"):
        return text[:-1].strip(), ""
    return text, ""


def parse_checker_output(text):
    """Return [{"file", "rows": [ResultRow]}] or raise CheckerOutputError."""
    files = []
    current = None
    skipping = False
    summary_seen = False

    def finish():
        if current is not None and not summary_seen:
            raise CheckerOutputError(f"No summary line was printed for {current['file']}.")

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if _RATE_SECTION.match(line):
            finish()
            current, skipping, summary_seen = None, True, False
            continue
        m = _FILE.match(line)
        if m:
            finish()
            current = {"file": m.group(1), "rows": []}
            files.append(current)
            skipping, summary_seen = False, False
            continue
        if skipping or current is None:
            continue
        m = _ROW.match(line)
        if m:
            name, reason = _split_row_text(m.group(3))
            current["rows"].append({"id": m.group(1), "name": name, "reason": reason,
                                    "verdict": _VERDICTS[m.group(2)]})
            continue
        counts = _rows_counts(current["rows"])
        m = _SUMMARY_NEW.match(line)
        if m:
            if (int(m.group(1)), int(m.group(2)), int(m.group(3))) != counts:
                raise CheckerOutputError(f"The summary for {current['file']} does not match its lines.")
            summary_seen = True
            continue
        m = _SUMMARY_OLD.match(line)
        if m:
            if int(m.group(1)) != counts[0] or int(m.group(2)) != len(current["rows"]):
                raise CheckerOutputError(f"The summary for {current['file']} does not match its lines.")
            summary_seen = True
            continue
    finish()
    if not files:
        raise CheckerOutputError("The output has no '== <file>' section.")
    for item in files:
        if not item["rows"]:
            raise CheckerOutputError(f"No criteria were printed for {item['file']}.")
    return files


def _rows_counts(rows):
    return (sum(1 for r in rows if r["verdict"] == "P"),
            sum(1 for r in rows if r["verdict"] == "F"),
            sum(1 for r in rows if r["verdict"] == "NC"))


# --- iteration-log.md ------------------------------------------------------

_LOG_HEADING = re.compile(r"^\s*(#{1,6})\s*(.*?)\s*#*\s*$")
_LOG_ENTRY = re.compile(r"^(?:\*\*|__)?\s*Iteration\s+(\d+)\b\s*(?:\*\*|__)?\s*(?:[:.\-–—]\s*)?(.*?)\s*$", re.I)
_LOG_FIELD = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?\s*(Date|Prompt|Model|Runs|Overall|Not[ _-]?checked|Hypothesis|Change|Result|Reasoning|Decision)"
    r"\s*(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*(.*?)\s*$", re.I)
_LOG_FRACTION = re.compile(r"(\d+)\s*(?:/|\bof\b|\bout of\b)\s*(\d+)", re.I)
_LOG_ROW_ID = re.compile(r"^(?:\*\*|__)?\s*C\s*(\d+)\b\s*(?:\*\*|__)?\s*[:.\-–—]?\s*(.*?)\s*$", re.I)
_LOG_NOT_CHECKED = re.compile(r"not\s*[-_]?\s*checked|^\s*n\s*/\s*a\s*$|^\s*[-–—]\s*$", re.I)
_LOG_FIELD_KEYS = {"date": "date", "prompt": "prompt", "model": "model", "runs": "runs", "overall": "overall",
                   "notchecked": "not_checked", "hypothesis": "hypothesis", "change": "change",
                   "result": "result", "reasoning": "reasoning", "decision": "decision"}


LOG_DECISIONS = ("kept", "undone", "pending")


class IterationLogError(Exception):
    """The log cannot be read as an iteration log."""


def _log_text(value):
    return re.sub(r"\s+", " ", re.sub(r"\*\*|__|`", "", value)).strip()


def _log_field_key(name):
    return _LOG_FIELD_KEYS[re.sub(r"[ _-]", "", name.lower())]


def _log_row(line):
    cells = _cells(line)
    if len(cells) < 2:
        return None
    m = _LOG_ROW_ID.match(cells[0])
    if not m:
        return None
    passed_text = _log_text(cells[1])
    fraction = _LOG_FRACTION.search(passed_text)
    not_checked = fraction is None and bool(_LOG_NOT_CHECKED.search(passed_text))
    rate = None
    if len(cells) > 2:
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", cells[2])
        rate = int(float(pct.group(1)) + 0.5) if pct else None
    notes = _log_text(" | ".join(cells[3:])) if len(cells) > 3 else ""
    return {
        "id": f"C{int(m.group(1))}",
        "name": _log_text(m.group(2)),
        "passes": int(fraction.group(1)) if fraction else None,
        "checked": int(fraction.group(2)) if fraction else None,
        "not_checked": not_checked,
        "passed_text": passed_text,
        "rate": rate,
        "notes": notes,
        "failing_runs": sorted({int(n) for n in re.findall(r"run[-_ ]?(\d+)", notes, re.I)}),
    }


def _log_entry(number, title, lines):
    entry = {"number": number, "title": title, "date": "", "prompt": "", "model": "", "runs": None,
             "runs_text": "", "overall": None, "overall_text": "", "not_checked_ids": [],
             "not_checked_count": None, "not_checked_text": "", "has_not_checked": False,
             "rows": [], "hypothesis": "", "change": "", "result": "", "reasoning": "", "decision": ""}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            if not _TABLE_RULE.match(stripped):
                row = _log_row(stripped)
                if row:
                    entry["rows"].append(row)
            continue
        m = _LOG_FIELD.match(line)
        if not m:
            continue
        key, value = _log_field_key(m.group(1)), _log_text(m.group(2))
        if key == "runs":
            entry["runs_text"] = value
            digits = re.search(r"\d+", value)
            entry["runs"] = int(digits.group(0)) if digits else None
        elif key == "overall":
            entry["overall_text"] = value
            fraction = _LOG_FRACTION.search(value)
            entry["overall"] = (int(fraction.group(1)), int(fraction.group(2))) if fraction else None
        elif key == "not_checked":
            entry["has_not_checked"] = True
            entry["not_checked_text"] = value
            entry["not_checked_ids"] = sorted({f"C{int(n)}" for n in re.findall(r"\bC\s*(\d+)\b", value, re.I)},
                                              key=lambda c: int(c[1:]))
            count = re.match(r"^(\d+)\b", value)
            if count:
                entry["not_checked_count"] = int(count.group(1))
            elif re.match(r"^(none|no|nil|zero)\b", value, re.I):
                entry["not_checked_count"] = 0
        elif key == "decision":
            entry["decision"] = value.lower() if value.lower() in LOG_DECISIONS else value
        else:
            entry[key] = value
    return entry


def parse_iteration_log(text):
    """Return the log's entries in file order, or raise IterationLogError.

    Each entry: number, title, date, prompt, model, runs, overall (passes, total) or None,
    not_checked_ids, not_checked_count, rows [{id, name, passes, checked, not_checked, rate,
    notes, failing_runs}], hypothesis, change, result, reasoning and decision. `decision` is `kept`, `undone` or
    `pending` (lower-cased), or the text as written when it is anything else. A field that is missing or left
    empty comes back empty or None, so the caller decides what it needs.
    """
    if not isinstance(text, str):
        raise IterationLogError("The log could not be read as text.")
    lines = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    entries = []
    current, level = None, 0
    for line in lines:
        heading = _LOG_HEADING.match(line) if line.lstrip().startswith("#") else None
        if heading:
            title = _LOG_ENTRY.match(heading.group(2))
            if title:
                if current is not None:
                    entries.append(_log_entry(*current))
                current = [int(title.group(1)), _log_text(title.group(2) or ""), []]
                level = len(heading.group(1))
                continue
            if current is not None and len(heading.group(1)) <= level:
                entries.append(_log_entry(*current))
                current = None
                continue
        if current is not None:
            current[2].append(line)
    if current is not None:
        entries.append(_log_entry(*current))
    if not entries:
        raise IterationLogError(
            "The log has no entry that starts with a heading such as '## Iteration 0: baseline'.")
    return entries


# --- promptfoo track: summarize_results.py output and promptfooconfig.yaml --------------------

_PF_ROW = re.compile(r"^(.+?) (PASS|FAIL|NOT CHECKED)\s*$")
_PF_CRITERION = re.compile(r"^C(\d+)(?:_(.*))?$", re.I)


def metric_name(metric):
    """A readable name from a metric such as C2_grouped_by_client."""
    m = _PF_CRITERION.match(metric)
    words = (m.group(2) if m else metric) or ""
    words = words.replace("_", " ").strip()
    return (words[:1].upper() + words[1:]) if words else metric


def parse_promptfoo_summary(text, names=None):
    """Return [{"file": <test name>, "rows": [ResultRow]}] from summarize_results.py output, or raise CheckerOutputError.

    A metric such as `C1_short_name` becomes id C1 with the name from `names` ({"C1": "Length"}) when it has
    one, otherwise from the metric. Other metrics (for example non_empty) and the pass rate section are
    left out of the rows, but the summary line of each test is still checked against every metric.
    Reasons are empty here; the caller adds them from results.json.
    """
    names = names or {}
    files, current, skipping, summary_seen = [], None, False, False
    all_verdicts = []

    def finish():
        if current is not None and not summary_seen:
            raise CheckerOutputError(f"No summary line was printed for {current['file']}.")

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if _RATE_SECTION.match(line):
            finish()
            current, skipping, summary_seen = None, True, False
            continue
        m = _FILE.match(line)
        if m:
            finish()
            current = {"file": m.group(1), "rows": []}
            files.append(current)
            all_verdicts, skipping, summary_seen = [], False, False
            continue
        if skipping or current is None:
            continue
        m = _SUMMARY_NEW.match(line)
        if m:
            counts = (all_verdicts.count("P"), all_verdicts.count("F"), all_verdicts.count("NC"))
            if (int(m.group(1)), int(m.group(2)), int(m.group(3))) != counts:
                raise CheckerOutputError(f"The summary for {current['file']} does not match its lines.")
            summary_seen = True
            continue
        m = _PF_ROW.match(line)
        if m:
            verdict = _VERDICTS[m.group(2)]
            all_verdicts.append(verdict)
            c = _PF_CRITERION.match(m.group(1))
            if c:
                cid = f"C{int(c.group(1))}"
                current["rows"].append({"id": cid, "name": names.get(cid) or metric_name(m.group(1)),
                                        "reason": "", "verdict": verdict})
    finish()
    if not files:
        raise CheckerOutputError("The output has no '== <test name>' section.")
    for item in files:
        if not item["rows"]:
            raise CheckerOutputError(f"No criteria (metrics named C1_..., C2_...) were printed for {item['file']}.")
    return files


def _unquote(value):
    value = value.strip()
    if value[:1] in "\"'":
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end > 0 else value[1:]
    return re.sub(r"\s+#.*$", "", value).strip()


def _config_lines(text):
    out = []
    for raw in text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped in ("---", "..."):
            continue
        out.append((len(raw) - len(raw.lstrip(" ")), stripped))
    return out


def _config_sections(lines):
    """{top-level key: (inline value, [(indent, text)])}. A list at indent 0 belongs to the key above it."""
    sections, key = {}, None
    for indent, text in lines:
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:(.*)$", text) if indent == 0 and not text.startswith("- ") else None
        if m:
            key = m.group(1)
            sections[key] = (m.group(2).strip(), [])
        elif key is not None:
            sections[key][1].append((indent, text))
    return sections


def _config_items(body):
    """Split the lines of a list section into items: [(key_indent, [(indent, text)])]."""
    starts = [i for i, (indent, text) in enumerate(body) if text.startswith("- ") or text == "-"]
    if not starts:
        return []
    base = min(body[i][0] for i in starts)
    starts = [i for i in starts if body[i][0] == base]
    items = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(body)
        indent, text = body[start]
        rest = text[1:].lstrip()
        key_indent = indent + (len(text) - len(rest))
        items.append((key_indent, [(key_indent, rest)] + body[start + 1:end]))
    return items


def _item_value(item, key):
    key_indent, lines = item
    for indent, text in lines:
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.*)$", text) if indent == key_indent else None
        if m:
            return _unquote(m.group(1))
    first = lines[0][1] if lines else ""
    if first.startswith("{"):
        m = re.search(rf"\b{re.escape(key)}\s*:\s*(\"[^\"]*\"|'[^']*'|[^,}}]+)", first)
        if m:
            return _unquote(m.group(1))
    return None


def parse_promptfoo_config(text):
    """What the app needs from promptfooconfig.yaml, read without a YAML library.

    {"providers": [str], "provider_keys": bool, "assert_types": [str], "test_names": [str]}.
    `provider_keys` is true when a `provider:` key sits anywhere (a model-graded assertion's grader).
    """
    lines = _config_lines(text)
    sections = _config_sections(lines)

    providers = []
    inline, body = sections.get("providers", ("", []))
    if inline.startswith("["):
        providers = [_unquote(p) for p in inline.strip("[]").split(",") if p.strip()]
    elif inline and not inline.startswith("#"):
        providers = [_unquote(inline)]
    for item in _config_items(body):
        ident = _item_value(item, "id")
        providers.append(ident if ident is not None else _unquote(item[1][0][1] if item[1] else ""))
    types = []
    for _indent, text in lines:
        for m in re.finditer(r"(?:^|[\s{,-])type\s*:\s*(\"[^\"]*\"|'[^']*'|[^\s,}]+)", text):
            types.append(_unquote(m.group(1)))

    names = []
    inline, body = sections.get("tests", ("", []))
    for item in _config_items(body):
        name = _item_value(item, "description")
        if name:
            names.append(name)

    provider_keys = any(re.match(r"^(?:-\s*)?provider\s*:", text) for _indent, text in lines)
    return {"providers": providers, "provider_keys": provider_keys, "assert_types": types, "test_names": names}


_LIVE_CLI = re.compile(r"^cli\s*:\s*(.*)$")
_LIVE_SECRET_KEY = re.compile(r"^(?:-\s*)?(api[_-]?key\w*|api[_-]?base[_-]?url|api[_-]?host)\s*:", re.I)


def parse_live_config(text):
    """What the app needs from promptfooconfig.live.yaml, read without a YAML library.

    The same fields as parse_promptfoo_config, plus "clis" (every `cli:` value) and "secret_keys" (any api key
    or API address setting, which live mode never uses).
    """
    parsed = parse_promptfoo_config(text)
    clis, secrets = [], []
    for _indent, line in _config_lines(text):
        m = _LIVE_CLI.match(line.lstrip("- ").strip())
        if m and m.group(1).strip():
            clis.append(_unquote(m.group(1)))
        m = _LIVE_SECRET_KEY.match(line)
        if m:
            secrets.append(m.group(1))
    return dict(parsed, clis=clis, secret_keys=secrets)
