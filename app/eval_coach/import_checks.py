"""Checks on a participant's own prompt and test cases, run before a project is created.

Everything here only reads: the two source files are opened for reading and never changed. The checks are
deterministic text rules, so the same files always give the same result. They are a floor, not a judge: a
blocking result means the files cannot give a useful checker yet, and a warning means the files can be
imported but the checker will be weaker than it could be.

Blocking:  readable text, three or more criteria, at least one criterion about the content of the answer,
           and no different file already in the project folder.
Warnings:  a criterion that cannot be traced to a requirement, a threshold with vague words, a criterion with
           no threshold, a file that is not UTF-8, a project folder that already has progress.
"""
from __future__ import annotations

import json
import os
import re

from . import parsers, resources
from .project import clean_path

MIN_CRITERIA = 3
MAX_BYTES = 1024 * 1024
PROMPT_NAME = "prompt-v0.md"
TEST_CASES_NAME = "test-cases.md"
_KINDS = ("prompt", "test_cases")
_NAMES = {"prompt": PROMPT_NAME, "test_cases": TEST_CASES_NAME}

_messages_cache = None


def _messages():
    global _messages_cache
    if _messages_cache is None:
        _messages_cache = json.loads(resources.read_text("content/import-checks.json"))
    return _messages_cache


def _item(severity, code, criterion=None, kind=None, **fields):
    """One finding: a stable code, the plain message, and what it is about."""
    group = _messages()["blocking" if severity == "blocking" else "warnings"]
    if "{label}" in group[code] and kind is not None:
        fields.setdefault("label", _messages()["labels"][kind])
    return {"code": code, "message": group[code].format(**fields), "criterion": criterion, "file": kind}


# --- reading ---------------------------------------------------------------

def _read_source(path_text, kind, fallback):
    """Return (bytes, None) or (None, blocking finding). Opens the file read-only."""
    path = clean_path(path_text)
    if not path and fallback is not None and os.path.isfile(str(fallback)):
        path = str(fallback)  # the project folder already holds this file
    if not path:
        return None, _item("blocking", f"missing_{kind}_path", kind=kind)
    if not os.path.isabs(path) or path.startswith("\\\\.\\"):
        return None, _item("blocking", "not_absolute", kind=kind)
    if os.path.isdir(path):
        return None, _item("blocking", "not_a_file", kind=kind)
    if not os.path.isfile(path):
        return None, _item("blocking", "file_not_found", kind=kind, path=path)
    try:
        with open(path, "rb") as f:
            data = f.read(MAX_BYTES + 1)
    except OSError as exc:
        return None, _item("blocking", "file_unreadable", kind=kind, reason=exc.strerror or type(exc).__name__)
    if len(data) > MAX_BYTES:
        return None, _item("blocking", "too_large", kind=kind)
    return data, None


def decode(data):
    """Return (text, was_utf8). A leading BOM is dropped; any other encoding is read as Windows-1252."""
    try:
        return data.decode("utf-8-sig"), True
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), False


# --- the content heuristic (task 4.22) --------------------------------------
#
# A criterion is about the CONTENT of the answer when its threshold requires particular information to be
# present: named terms, labels, topics, facts, or things copied from the input. It is NOT about content when it
# only measures size or shape (counts of words, characters, lines or sentences, case, punctuation, how it starts
# or ends), only forbids things (a banned list, "no exclamation marks"), or relies on judgment.
#
# Rules, applied to the threshold text:
#   1. Count phrases such as "under 150 words" or "at least 3 sentences" are removed first, so a count never
#      looks like a required term.
#   2. The threshold is content if what is left has a coverage word (all, any, each, every, both, at least,
#      one of, some) followed by "appear", "present", "found", "included", "mentioned" or "contains"; OR a
#      presence verb (contains, includes, mentions, covers, states, names, cites, quotes, lists, references,
#      says) followed by an object (all, any, the, a, a quoted term, ...); OR a term or label word followed by
#      "appears"; OR a quoted term together with a presence word, provided there is no negation anywhere.
#   3. If the rules above do not apply but the criterion's own Type line says it is content, it still counts,
#      unless the threshold is only a count or leans on a vague word. The participant's own label is trusted
#      when the wording is unusual, so a good file is not blocked by a phrasing the rules did not foresee.
# Thresholds that only forbid things ("none of", "no", "zero") are not content, even when a list is named.

_QUOTED = re.compile(r'"[^"\n]+"|“[^”\n]+”|`[^`\n]+`')
_COUNT_UNITS = r"(?:words?|characters?|chars?|lines?|sentences?|paragraphs?|bullets?|items?|sections?|headings?|letters?|digits)"
_COUNT_PHRASE = re.compile(
    r"(?:\b(?:at\s+least|at\s+most|fewer\s+than|less\s+than|more\s+than|greater\s+than|under|over|exactly|"
    r"between|up\s+to|no\s+more\s+than|no\s+fewer\s+than)\s+)?\d[\d,.]*(?:\s*(?:-|to|and)\s*\d[\d,.]*)?"
    r"\s+(?:\w+\s+)?" + _COUNT_UNITS + r"\b", re.I)
_COUNT_WORDS = re.compile(r"\b(?:word|character|line|sentence|paragraph)\s+count\b|" + r"\b" + _COUNT_UNITS + r"\b", re.I)
_COVERAGE = r"(?:all|any|each|every|both|at\s+least\s+\w+|one\s+of|some)"
_PRESENT_WORDS = r"(?:appears?|present|found|included?|mentioned|contain(?:ed|s)?|covered|cited|listed)"
_PRESENCE = [
    re.compile(r"\b" + _COVERAGE + r"\b[^.;]*?\b" + _PRESENT_WORDS + r"\b", re.I),
    re.compile(r"\b(?:contains?|includes?|mentions?|covers?|states?|names?|cites?|quotes?|lists?|references?|says)\s+"
               r"(?:(?:all|any|each|every|both|the|a|an|at\s+least|one|some)\b|[\"“`])", re.I),
    re.compile(r"\b(?:labels?|terms?|keywords?|phrases?|headings?|topics?|names?)\b[^.;]*?"
               r"\b(?:appears?|present|found|included|mentioned)\b", re.I),
]
_QUOTED_PRESENCE = re.compile(r"\b(?:appears?|present|found|included?|mentioned|contains?|includes?|used)\b", re.I)
_NEGATION = re.compile(r"\b(?:no|none|not|never|without|zero|neither|nor|banned|forbidden|avoid)\b|n't", re.I)


def is_content_threshold(threshold):
    """True if the threshold requires particular information to be present in the answer (rules 1 and 2)."""
    cleaned = _COUNT_PHRASE.sub(" ", threshold or "")
    if any(p.search(cleaned) for p in _PRESENCE):
        return True
    return bool(_QUOTED.search(cleaned) and _QUOTED_PRESENCE.search(cleaned) and not _NEGATION.search(cleaned))


# --- vague words (task 4.24) ------------------------------------------------
# The words the build skill says need judgment (its NOT CHECKED rule), plus close relatives. Words inside
# quotation marks or backticks are terms the participant chose, so they are never flagged.

_VAGUE = re.compile(
    r"\b(clear(?:ly)?|good|great|concise(?:ly)?|professional(?:ly)?|relevant|accurate(?:ly)?|helpful|natural(?:ly)?|"
    r"appropriate(?:ly)?|easy|easily|nice(?:ly)?|engaging|effective(?:ly)?|friendly|polite(?:ly)?|readable|"
    r"coherent|useful|informative|well[- ]written|well[- ]structured|high[- ]quality)\b", re.I)


def vague_words(threshold):
    """The vague words in a threshold, lower case, in the order they first appear."""
    found = []
    for match in _VAGUE.finditer(_QUOTED.sub(" ", threshold or "")):
        word = match.group(1).lower().replace(" ", "-")
        if word not in found:
            found.append(word)
    return found


# --- tracing to the prompt (task 4.23) ----------------------------------------
# A criterion is traced when it has Requirement text of its own, or when its name shares a key word with the
# prompt, or its threshold shares a number or at least two key words with the prompt. A key word is a word of
# four letters or more that is not a generic checking word. Words are compared by their first five letters, so
# "grouped" matches "group" and "clients" matches "client". This is a forgiving check on purpose, which is why
# it only warns.

_STOP = frozenset("""
about above across after again also another answer answers appear appears because been before being below between
both bullets check checked checker checks contain contains count criterion criteria each either ensure every fail fails
from have having include includes into just label labels least less like make many mention mentions more most must much
only other output outputs over pass passes passed passing please present rule same should some such text than that their
them then there these they this those threshold through under unless until used uses using very want when where which
while whole will with within without word words would your
""".split())
_TOKEN = re.compile(r"[A-Za-z]+|\d[\d,.]*")


def _key_tokens(text):
    tokens = set()
    for raw in _TOKEN.findall(text or ""):
        token = raw.lower().rstrip(".,")
        if token[0].isdigit():
            tokens.add(token)
        elif len(token) >= 4 and token not in _STOP:
            tokens.add(token[:5])
    return tokens


def _prompt_tokens(text):
    tokens = set()
    for raw in _TOKEN.findall(text or ""):
        token = raw.lower().rstrip(".,")
        tokens.add(token if token[0].isdigit() else token[:5])
    return tokens


def is_traced(criterion, prompt_tokens):
    if (criterion.get("requirement") or "").strip():
        return True
    if _key_tokens(criterion["name"]) & prompt_tokens:
        return True
    shared = _key_tokens(criterion["threshold"]) & prompt_tokens
    return any(token[0].isdigit() for token in shared) or len(shared) >= 2


# --- the Type label ---------------------------------------------------------

_TYPE_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**\s*Type\s*\**\s*:\s*\**\s*(.*?)\s*$", re.I)
_CRITERION_HEAD = re.compile(r"^\s*(?:#{1,6}\s*|\*\*\s*)C\s*(\d+)\b", re.I)
_ANY_HEADING = re.compile(r"^\s*#{1,6}\s")


def criterion_types(text):
    """{"C1": "Format", ...} from `Type:` lines under criterion headings, or a Type / Format or content column."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    found, current = {}, None
    for i, line in enumerate(lines):
        head = _CRITERION_HEAD.match(line)
        if head:
            current = f"C{int(head.group(1))}"
            continue
        if _ANY_HEADING.match(line):
            current = None
            continue
        if current is not None:
            m = _TYPE_LINE.match(line)
            if m and current not in found:
                found[current] = m.group(1).replace("*", "").strip()
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            found.update(_table_types(lines, i))
    return found


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table_types(lines, start):
    header = [c.replace("*", "").strip().lower() for c in _cells(lines[start])]
    col = next((header.index(n) for n in ("type", "format or content", "format/content") if n in header), None)
    if col is None:
        return {}
    ident = next((header.index(n) for n in ("#", "id", "no", "no.", "number") if n in header), None)
    out, count = {}, 0
    for row_line in lines[start + 2:]:
        if "|" not in row_line or not row_line.strip():
            break
        row = _cells(row_line)
        count += 1
        probe = row[ident] if ident is not None and ident < len(row) else row[0]
        m = re.search(r"\d+", probe)
        number = int(m.group(0)) if m else count
        if col < len(row):
            out[f"C{number}"] = row[col].replace("*", "").strip()
    return out


def _counts_only(threshold):
    return bool(_COUNT_WORDS.search(threshold)) and not is_content_threshold(threshold)


def is_content_criterion(criterion, type_label=""):
    threshold = criterion["threshold"] or ""
    if is_content_threshold(threshold):
        return True
    if not threshold.strip() or vague_words(threshold) or _counts_only(threshold):
        return False
    return bool(re.search(r"\bcontent\b", type_label or "", re.I))


# --- the review ---------------------------------------------------------------

def analyze(prompt_text, cases_text):
    """Check the two texts. Returns {"blocking", "warnings", "criteria", "ready", "copies"}."""
    blocking, warnings = [], []
    criteria = parsers.parse_test_cases(cases_text or "")
    shown = [{"id": c["id"], "name": c["name"]} for c in criteria]
    if cases_text is not None:
        if not criteria:
            blocking.append(_item("blocking", "no_criteria", kind="test_cases"))
        else:
            if len(criteria) < MIN_CRITERIA:
                blocking.append(_item("blocking", "few_criteria", kind="test_cases", count=len(criteria),
                                      min=MIN_CRITERIA, missing=MIN_CRITERIA - len(criteria)))
            types = criterion_types(cases_text)
            if not any(is_content_criterion(c, types.get(c["id"], "")) for c in criteria):
                blocking.append(_item("blocking", "no_content_criterion", kind="test_cases"))
            for c in criteria:
                if not c["threshold"].strip():
                    warnings.append(_item("warnings", "missing_threshold", criterion=c["id"], kind="test_cases",
                                          id=c["id"], name=c["name"]))
            if prompt_text is not None:
                tokens = _prompt_tokens(prompt_text)
                for c in criteria:
                    if not is_traced(c, tokens):
                        warnings.append(_item("warnings", "untraced", criterion=c["id"], kind="test_cases",
                                              id=c["id"], name=c["name"]))
            for c in criteria:
                words = vague_words(c["threshold"])
                if words:
                    warnings.append(_item("warnings", "vague", criterion=c["id"], kind="test_cases", id=c["id"],
                                          name=c["name"], words=", ".join(f"“{w}”" for w in words)))
    return {"blocking": blocking, "warnings": warnings, "criteria": shown, "ready": not blocking,
            "copies": dict(_NAMES)}


def review_files(prompt_path, cases_path, destinations=None):
    """Read the two source files, read-only, and check them.

    destinations maps "prompt" and "test_cases" to the files the project would hold. A blank path falls back to
    the file already there, and a different file already there is a blocking problem, because the app never
    replaces a participant file. Returns (result, data) where data holds the bytes read, for the copy.
    """
    destinations = destinations or {}
    blocking, warnings, data, texts = [], [], {}, {}
    for kind, given in (("prompt", prompt_path), ("test_cases", cases_path)):
        raw, problem = _read_source(given if isinstance(given, str) else "", kind, destinations.get(kind))
        if problem is not None:
            blocking.append(problem)
            continue
        if b"\x00" in raw[:8192]:
            blocking.append(_item("blocking", "not_text", kind=kind))
        elif not raw.strip():
            blocking.append(_item("blocking", "empty", kind=kind))
        else:
            text, utf8 = decode(raw)
            data[kind], texts[kind] = raw, text
            if not utf8:
                warnings.append(_item("warnings", "not_utf8", kind=kind))
        existing = destinations.get(kind)
        if kind in data and existing is not None and os.path.isfile(str(existing)):
            try:
                with open(str(existing), "rb") as f:
                    same = f.read(MAX_BYTES + 1) == raw
            except OSError:
                same = True
            if not same:
                blocking.append(_item("blocking", "destination_exists", kind=kind, name=_NAMES[kind]))
    result = analyze(texts.get("prompt"), texts.get("test_cases"))
    result["blocking"] = blocking + result["blocking"]
    result["warnings"] = warnings + result["warnings"]
    result["ready"] = not result["blocking"]
    return result, data


def project_exists_warning():
    return _item("warnings", "project_exists")
