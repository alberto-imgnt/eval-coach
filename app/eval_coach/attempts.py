"""Part 4's attempt engine: where an attempt is kept, how it is scored and how the log is checked against it.

Each attempt `n` lives in its own folder, `<project>/part-4/attempts/<n>/`, with its own prompt, rules, checker, five
saved answers, hypothesis and `results.json`. Part 3's files are only ever read. The manifest in progress.json
(`parts.part-4.attempts`) holds hashes, counts and ids, never a text.

Nothing here calls a model, reads terminal output or edits the participant's log. A decision comes from the files and
from running the checker directly. The AI window that writes an attempt's five answers belongs to the course content;
this module takes the saved files as they are.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import shutil
import tempfile
import threading
from pathlib import Path

from . import baseline, gates, parsers, project, promptfoo, resources, runner, scan
from . import state as store

PART_ID = store.PART_4.id
MAX_TEXT = 50000
TARGET_PERCENT = 95
ROUNDS_NEEDED = 2
HASH_KEYS = ("prompt", "test_cases", "checker", "runs")
DECISIONS = {"keep": "kept", "undo": "undone"}
START_CHOICES = ("own", "practice")
GENERATED_START = "# eval-coach: known-good test (generated)"
GENERATED_END = "# eval-coach: end of known-good test"
_GENERATED = re.compile(r"^[ \t]*" + re.escape(GENERATED_START) + r"[^\n]*\n.*?^[ \t]*" + re.escape(GENERATED_END)
                        + r"[^\n]*(?:\n|\Z)", re.S | re.M)
_FILE_REF = re.compile(r"file://([^\s\"'(){}\[\],]+)")
_SHARED_FOLDERS = ("runs/", "fixtures/", "examples/")
_RUN_ONE = re.compile(r"\bdescription\s*:\s*[\"']?run-1\b")


@functools.lru_cache(maxsize=None)
def _load_words_json():
    return resources.read_text("content/part-4-attempts.json")


@functools.lru_cache(maxsize=None)
def _baseline_problems_json():
    return json.dumps(json.loads(resources.read_text("content/steps.json"))["steps"]["baseline"]["gate"]["problems"])


def _load_words():
    return json.loads(_load_words_json())


def _baseline_problems():
    return json.loads(_baseline_problems_json())


def _error(code, message):
    from .engine import EngineError  # engine imports modules that import this one, so the import waits
    return EngineError(code, message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _squash(text):
    return " ".join(str(text).split())


# --- the promptfoo config copy ---------------------------------------------------


def strip_generated(text):
    """The config text without the known-good test the app added, exactly the block it wrote and nothing else."""
    return _GENERATED.sub("", text)


def add_known_good_test(text):
    """The config text with a `known-good` test added after the last test.

    The test is a copy of the `run-1` test (its assertions and variables) that reads known-good.txt, wrapped in two
    comment lines so `strip_generated` can take out exactly what was added. Raises ValueError with `no_run_test`
    when the config has no `run-1` test to copy.
    """
    text = strip_generated(text)
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if re.match(r"^tests\s*:", line)), None)
    if start is None:
        raise ValueError("no_run_test")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^[A-Za-z_][\w-]*\s*:", lines[i])), len(lines))
    starts = [i for i in range(start + 1, end) if re.match(r"^\s*-(\s|$)", lines[i])]
    if not starts:
        raise ValueError("no_run_test")
    base = min(len(lines[i]) - len(lines[i].lstrip()) for i in starts)
    starts = [i for i in starts if len(lines[i]) - len(lines[i].lstrip()) == base]
    bounds = starts + [end]
    source = next((lines[a:b] for a, b in zip(bounds, bounds[1:]) if _RUN_ONE.search("".join(lines[a:b]))), None)
    if source is None:
        raise ValueError("no_run_test")
    while source and not source[-1].strip():
        source.pop()
    copy = [re.sub(r"\brun-1\b", promptfoo.KNOWN_GOOD_TEST,
                   re.sub(r"runs/run-1\.txt", promptfoo.KNOWN_GOOD_FILE, line)) for line in source]
    indent = " " * base
    block = [indent + GENERATED_START + eol] + [line if line.endswith(("\n", "\r")) else line + eol for line in copy] \
        + [indent + GENERATED_END + eol]
    at = end
    while at > start + 1 and not lines[at - 1].strip():
        at -= 1
    before = lines[:at]
    if before and not before[-1].endswith(("\n", "\r")):
        before[-1] += eol
    return "".join(before + block + lines[at:])


def checker_hash(path, track):
    """The hash of an attempt's checker, or None when it is missing.

    On the promptfoo track it is the config with the generated known-good test taken out and trailing blank space
    ignored, so adding that test never reads as "the checker changed" while any other edit does.
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if track != "promptfoo":
        return _sha(data)
    return _sha(strip_generated(data.decode("utf-8", errors="replace")).rstrip().encode("utf-8"))


def local_files(config_text):
    """The relative files a config reads besides the five answers and the fixtures, as forward-slash paths."""
    found = []
    for match in _FILE_REF.finditer(config_text):
        rel = match.group(1).replace("\\", "/")
        if re.match(r"^[A-Za-z]:", rel):
            continue  # a drive letter is an absolute path
        rel = rel.split(":", 1)[0]
        rel = rel[2:] if rel.startswith("./") else rel
        parts = rel.split("/")
        if (not rel or rel.startswith("/") or ".." in parts or rel == promptfoo.KNOWN_GOOD_FILE
                or rel.startswith(_SHARED_FOLDERS) or rel in found):
            continue
        found.append(rel)
    return found


# --- results ---------------------------------------------------------------------


def compact(summary):
    """The manifest's form of a summary: {criterion: {passes, checked_runs}, "not_checked": [ids]}. Counts only."""
    out = {c["id"]: {"passes": c["passes"], "checked_runs": c["checked_runs"]} for c in summary["criteria"]}
    out["not_checked"] = list(summary["not_checked"])
    return out


def _ids(results):
    return sorted((k for k in results if k != "not_checked"), key=lambda c: (int(re.sub(r"\D", "", c) or 0), c))


def overall(results):
    """(passes, checked results) over every criterion, the same total `baseline.summarize` gives."""
    ids = _ids(results)
    return sum(results[k]["passes"] for k in ids), sum(results[k]["checked_runs"] for k in ids)


def _better(now, before):
    """True when the score (passes, total) is strictly higher than the other."""
    return now[1] > 0 and before[1] > 0 and now[0] * before[1] > before[0] * now[1]


def _meets(passes, total):
    return total > 0 and passes * 100 >= TARGET_PERCENT * total


def _fraction(score):
    return f"{score[0]} of {score[1]}"


def _list_ids(ids):
    return ", ".join(ids)


class Attempts:
    """The attempts of one project. Every call that changes anything takes the lock and saves the manifest."""

    def __init__(self, paths, progress, save, track="script", runtime=None, iteration_zero=None, model=None,
                 lock=None, words=None):
        self.paths = paths
        self._progress = progress if callable(progress) else (lambda: progress)
        self._save_progress = save
        self._track_of = track if callable(track) else (lambda: track)
        self._runtime = runtime or (lambda: (None, {}))
        self._iteration_zero = iteration_zero or (lambda: None)
        self._model = model or (lambda: "")
        self._lock = lock or threading.RLock()
        self._running = False
        self.words = words or _load_words()
        self._baseline_problems = _baseline_problems()

    @classmethod
    def for_engine(cls, engine, model=None):
        """The attempts of the engine's current project, reading Part 3's saved baseline as Iteration 0.

        `model` gives the model name a scored attempt records; by default it is Part 3's. The Practice baseline has no
        recorded model, so it is never read for it.
        """
        def runtime():
            env = engine._cli_env()
            options = {"npx_argv": engine.preflight.npx_argv(env), "runner": engine.preflight.runner,
                       "python": engine.python_path} if engine._track() == "promptfoo" else {}
            return env, options

        def zero():
            saved = engine._load_result("baseline")
            return saved.get("summary") if saved else None

        return cls(engine.paths, lambda: engine.progress, engine._save, engine._track, runtime, zero,
                   model or engine._model_name, engine._lock)

    # --- the starting point ----------------------------------------------------

    def source(self):
        """"own" (the participant's Part 3 files) or "practice" (the bundled baseline). Unset means "own"."""
        return self._block().get("start") or "own"

    def chosen(self):
        """The starting point the participant chose, or None before they chose one."""
        return self._block().get("start")

    def _practice(self):
        return self.source() == "practice"

    def _base(self):
        """Where Iteration 0's prompt, rules, checker, five answers and log are kept."""
        return self.paths.part4_practice if self._practice() else self.paths

    def _ap(self, n):
        return self.paths.attempt(n, practice=self._practice())

    def _log_name(self):
        return "part-4/practice/iteration-log.md" if self._practice() else "iteration-log.md"

    def _zero_summary(self):
        """Iteration 0's saved summary: Part 3's baseline result, or the Practice baseline's own."""
        if not self._practice():
            return self._iteration_zero()
        try:
            data = store.read_json(self._base().results)
            return {key: data[key] for key in ("criteria", "overall", "not_checked", "runs")}
        except (OSError, KeyError, TypeError, store.CorruptStateError):
            return None

    def choose_start(self, source):
        """Save the starting point, once. The Practice baseline is copied into part-4/practice/ create-only and scored.

        Nothing of the participant's own Part 3 files is read for Practice, and none is written either way. The choice
        cannot change once attempt 1 exists.
        """
        with self._lock:
            if source not in START_CHOICES:
                raise self._fail("bad_start")
            if self.manifest():
                if self._block().get("start") == source or (source == "own" and not self._block().get("start")):
                    return
                raise self._fail("start_fixed")
            if source == "own":
                if not self._baseline_done():
                    raise self._fail("no_baseline")
                self._block(create=True)["start"] = "own"
                self._save_progress()
                return
            try:
                project.write_practice_baseline(self.paths, self.track)
            except OSError as exc:
                raise self._fail("practice_busy", error=exc) from exc
            practice = self.paths.part4_practice
            env, options = self._options()
            self._begin_run()
        try:
            result = baseline.run_checks(practice.project, self.track, env=env, **options)
        finally:
            self._end_run()
        if not result["ok"]:
            raise self._fail("checker_failed", error=result["error"])
        summary = baseline.summarize(result)
        if summary is None:
            raise self._fail("checker_failed", error=baseline._consistency_problem(result) or "")
        with self._lock:
            if self.manifest():
                raise self._fail("start_fixed")
            try:
                store.write_json_atomic(practice.results, dict(summary, track=self.track))
            except OSError as exc:
                raise self._fail("practice_busy", error=exc) from exc
            self._block(create=True)["start"] = "practice"
            self._save_progress()

    # --- the manifest ----------------------------------------------------------

    @property
    def progress(self):
        return self._progress()

    @property
    def track(self):
        return self._track_of()

    def _block(self, create=False):
        parts = self.progress["parts"]
        if PART_ID not in parts:
            if not create:
                return store.new_part_progress(store.PART_4)
            parts[PART_ID] = store.new_part_progress(store.PART_4)
        return parts[PART_ID]

    def manifest(self):
        """The attempts in chronological order. Reading never creates the saved block."""
        return self._block()["attempts"]

    def _find(self, n):
        return next((rec for rec in self.manifest() if rec["n"] == n), None)

    def _require(self, n):
        rec = self._find(n) if isinstance(n, int) and not isinstance(n, bool) else None
        if rec is None:
            raise _error("unknown_attempt", self.words["errors"]["unknown_attempt"].format(n=n))
        return rec

    def _fail(self, code, **fmt):
        return _error(code, self.words["errors"][code].format(**fmt))

    def kept(self):
        """The kept version: the last attempt whose decision is `kept`, or 0 (Iteration 0) when there is none."""
        return next((rec["n"] for rec in reversed(self.manifest()) if rec["decision"] == "kept"), 0)

    def _baseline_done(self):
        """Iteration 0 exists: the participant finished Part 3's baseline, or chose the Practice baseline."""
        return self._practice() or "baseline" in self.progress["done"]

    # --- files -----------------------------------------------------------------

    def _hashes(self, ap):
        return {"prompt": gates.file_sha256(ap.prompt), "test_cases": gates.file_sha256(ap.test_cases),
                "checker": checker_hash(ap.checker(self.track), self.track), "runs": baseline.runs_hash(ap)}

    def _stale(self, rec):
        """Which of prompt, rules, checker and answers differ from what was scored: [] when nothing changed."""
        if rec["hashes"] is None:
            return []
        now = self._hashes(self._ap(rec["n"]))
        return [key for key in HASH_KEYS if rec["hashes"].get(key) != now[key]]

    def _stale_words(self, keys):
        names = self.words["hash_names"]
        return ", ".join(names[k] for k in keys)

    def _run_started(self, ap, rec):
        return rec["hashes"] is not None or any(gates.has_text(ap.run_file(i)) for i in range(1, baseline.RUNS + 1))

    def _sources(self, parent):
        """The files a new attempt starts from: the kept version's, or Iteration 0's own files."""
        src = self._base() if parent == 0 else self._ap(parent)
        track = self.track
        names = {"prompt": (src.prompt, "prompt.md" if parent else "prompt-v0.md"),
                 "test_cases": (src.test_cases, "test-cases.md"),
                 "checker": (src.checker(track), src.checker(track).name)}
        return src, names

    def _copy_new(self, source, dest, transform=None):
        """Copy a file, creating the destination only. An existing file is never replaced."""
        data = source.read_bytes()
        if transform is not None:
            data = transform(data)
        project._write_new(dest, data)

    def _copy_local_files(self, config_text, source_root, dest_root):
        for rel in local_files(config_text):
            source = Path(source_root) / rel
            if source.is_file():
                self._copy_new(source, Path(dest_root) / rel)

    # --- starting an attempt and its hypothesis --------------------------------

    def start(self):
        """Create the next attempt from the kept version and return its view."""
        with self._lock:
            if not self._baseline_done():
                raise self._fail("no_baseline")
            manifest = self._block(create=True)["attempts"]
            if manifest and manifest[-1]["decision"] == "pending":
                raise self._fail("undecided", n=manifest[-1]["n"])
            n = manifest[-1]["n"] + 1 if manifest else 1
            parent = self.kept()
            src, names = self._sources(parent)
            missing = [label for key, (path, label) in names.items() if not path.is_file()]
            if missing:
                raise self._fail("no_start_files", n=n, files=", ".join(missing))
            ap = self._ap(n)
            try:
                self._copy_new(src.prompt, ap.prompt)
                self._copy_new(src.test_cases, ap.test_cases)
                checker = src.checker(self.track)
                if self.track == "promptfoo":
                    text = checker.read_bytes().decode("utf-8", errors="replace")
                    self._copy_new(checker, ap.checker("promptfoo"),
                                   lambda data: strip_generated(data.decode("utf-8", errors="replace")).encode("utf-8"))
                    self._copy_local_files(text, src.project, ap.project)
                else:
                    self._copy_new(checker, ap.checker("script"))
                ap.runs.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise self._fail("folder_busy", n=n, error=exc) from exc
            manifest.append({"n": n, "parent": parent, "log_entry": n, "model": "", "hashes": None, "results": None,
                             "decision": "pending", "hypothesis_hash": None, "known_good": None})
            self._save_progress()
            return self.view(n)

    def save_hypothesis(self, n, text):
        """Save the hypothesis for attempt n. It can change until the attempt is run, and never after."""
        with self._lock:
            rec = self._require(n)
            ap = self._ap(n)
            if not isinstance(text, str) or len(text) > MAX_TEXT or "\0" in text:
                raise self._fail("bad_text")
            if not text.strip():
                raise self._fail("hypothesis_blank")
            if rec["decision"] != "pending" or self._run_started(ap, rec):
                raise self._fail("hypothesis_locked", n=n)
            data = text.replace("\r\n", "\n").encode("utf-8")
            try:
                store.write_bytes_atomic(ap.hypothesis, data)
            except OSError as exc:
                raise self._fail("folder_busy", n=n, error=exc) from exc
            rec["hypothesis_hash"] = _sha(data)
            self._save_progress()

    def require_hypothesis(self, n):
        """Refuse unless attempt n has a saved hypothesis that is still the one on disk."""
        with self._lock:
            self._require_hypothesis(n, self._require(n))

    def run_texts(self, n):
        """Whether each of the five answers of attempt n is saved: [(k, has text, word count)]."""
        ap = self._ap(n)
        out = []
        for k in range(1, baseline.RUNS + 1):
            text = gates.read_text(ap.run_file(k))
            out.append((k, bool(text.strip()), len(text.split())))
        return out

    def _require_hypothesis(self, n, rec):
        ap = self._ap(n)
        if not rec["hypothesis_hash"] or not gates.has_text(ap.hypothesis):
            raise self._fail("hypothesis_needed", n=n)
        if gates.file_sha256(ap.hypothesis) != rec["hypothesis_hash"]:
            raise self._fail("hypothesis_changed", n=n)

    # --- scoring the five answers ----------------------------------------------

    def _prepare(self, n, rec):
        """The checks every checker run starts with. Returns the attempt's paths."""
        ap = self._ap(n)
        for path in (ap.prompt, ap.test_cases, ap.checker(self.track)):
            if not path.is_file():
                raise self._fail("file_missing", n=n, name=path.name)
        problems = gates.scan_messages(ap, self.track)
        if problems:
            raise self._fail("scan_failed", messages=" ".join(p["message"] for p in problems))
        return ap

    def _options(self):
        """The runtime and the options every checker run of an attempt takes: promptfoo writes its own output to another
        file, and runs only the five answers' tests, because an attempt folder has no fixtures for the others to read."""
        env, options = self._runtime()
        return env, dict(options, output=promptfoo.ATTEMPT_OUTPUT, only=promptfoo.RUN_TESTS_PATTERN)

    def _begin_run(self):
        if self._running:
            raise self._fail("busy")
        self._running = True

    def _end_run(self):
        with self._lock:
            self._running = False

    def score(self, n):
        """Run the checker in the attempt's folder on its five saved answers and save `results.json`."""
        with self._lock:
            rec = self._require(n)
            if rec["decision"] != "pending":
                raise self._fail("already_decided", n=n, decision=rec["decision"])
            self._require_hypothesis(n, rec)
            ap = self._prepare(n, rec)
            missing = [f"run-{i}.txt" for i in range(1, baseline.RUNS + 1) if not gates.has_text(ap.run_file(i))]
            if missing:
                raise self._fail("answers_missing", n=n, files=", ".join(missing))
            if self.track == "promptfoo":
                self._sync_known_good_test(ap)
            env, options = self._options()
            before = self._hashes(ap)
            self._begin_run()
        try:
            result = baseline.run_checks(ap.project, self.track, env=env, **options)
        finally:
            self._end_run()
        if not result["ok"]:
            raise self._fail("checker_failed", error=result["error"])
        summary = baseline.summarize(result)
        if summary is None:
            raise self._fail("checker_failed", error=baseline._consistency_problem(result) or "")
        with self._lock:
            if self._hashes(ap) != before or self._find(n) is not rec:
                raise self._fail("changed_while_running", n=n)
            try:
                store.write_json_atomic(ap.results, dict(summary, track=self.track))
            except OSError as exc:
                raise self._fail("folder_busy", n=n, error=exc) from exc
            rec["hashes"], rec["results"], rec["model"] = before, compact(summary), self._model()
            self._save_progress()
        self._check_repair(n)
        return self.view(n)

    def _sync_known_good_test(self, ap):
        """A known-good test in the attempt's config needs its answer file; without the file the test is taken out."""
        config = ap.checker("promptfoo")
        try:
            text = config.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            return
        if GENERATED_START in text and not gates.has_text(ap.known_good):
            store.write_bytes_atomic(config, strip_generated(text).encode("utf-8"))

    # --- the known-good answer ---------------------------------------------------

    def save_known_good(self, n, text):
        """Save the known-good answer. Its score is not returned until this exists, and a new answer drops the old score."""
        with self._lock:
            rec = self._require(n)
            ap = self._ap(n)
            if not isinstance(text, str) or len(text) > MAX_TEXT or "\0" in text:
                raise self._fail("bad_text")
            if not text.strip():
                raise self._fail("known_good_blank")
            if rec["decision"] != "pending":
                raise self._fail("already_decided", n=n, decision=rec["decision"])
            try:
                store.write_bytes_atomic(ap.known_good, text.replace("\r\n", "\n").encode("utf-8"))
            except OSError as exc:
                raise self._fail("folder_busy", n=n, error=exc) from exc
            rec["known_good"] = None
            self._save_progress()

    def score_known_good(self, n):
        """Run the attempt's checker on the known-good answer. The score is kept apart from the five answers'."""
        with self._lock:
            rec = self._require(n)
            ap = self._ap(n)
            if not gates.has_text(ap.known_good):
                raise self._fail("known_good_needed")
            ap = self._prepare(n, rec)
            if self.track == "promptfoo":
                config = ap.checker("promptfoo")
                try:
                    added = add_known_good_test(config.read_bytes().decode("utf-8", errors="replace"))
                except ValueError as exc:
                    raise self._fail("no_run_test") from exc
                store.write_bytes_atomic(config, added.encode("utf-8"))
            env, options = self._options()
            answer, mine = gates.file_sha256(ap.known_good), self._hashes(ap)["checker"]
            self._begin_run()
        try:
            if self.track == "promptfoo":
                result = promptfoo.run_selection(
                    ap.project, promptfoo.KNOWN_GOOD_TEST, [promptfoo.KNOWN_GOOD_FILE], env, options.get("npx_argv"),
                    options.get("runner"), options.get("python"), output=promptfoo.ATTEMPT_OUTPUT,
                    only=promptfoo.KNOWN_GOOD_PATTERN)  # no answer exists yet, and promptfoo stops on a missing file
            else:
                result = runner.run_checker(ap.project, [promptfoo.KNOWN_GOOD_FILE], env=env)
        finally:
            self._end_run()
        if not result["ok"]:
            raise self._fail("checker_failed", error=result["error"])
        section = runner.find_file(result, promptfoo.KNOWN_GOOD_FILE)
        rows = section["rows"] if section else []
        passes = sum(1 for r in rows if r["verdict"] == "P")
        checked = passes + sum(1 for r in rows if r["verdict"] == "F")
        with self._lock:
            if (gates.file_sha256(ap.known_good), self._hashes(ap)["checker"]) != (answer, mine):
                raise self._fail("changed_while_running", n=n)
            rec["known_good"] = {"answer_hash": answer, "checker_hash": mine, "passes": passes, "checked": checked,
                                 "failing": sorted((r["id"] for r in rows if r["verdict"] == "F"),
                                                   key=lambda c: (int(re.sub(r"\D", "", c) or 0), c))}
            self._save_progress()
        self._check_repair(n)
        return self.view(n)

    # --- repairing the checker -----------------------------------------------------

    def _zero(self):
        """Iteration 0's results in the manifest's form, and the hash of the checker that made them."""
        corrected = self._block().get("iteration_0")
        if corrected:
            return corrected["results"], corrected["checker_hash"]
        summary = self._zero_summary()
        results = compact(summary) if summary else None
        return results, checker_hash(self._base().checker(self.track), self.track)

    def _zero_with(self, ap):
        """Iteration 0's five original answers scored by the attempt's checker, in a scratch folder. None if absent."""
        root = self._base()
        if not all(gates.has_text(root.run_file(i)) for i in range(1, baseline.RUNS + 1)):
            return None
        track = self.track
        scratch = Path(tempfile.mkdtemp(prefix="eval-coach-zero-"))
        try:
            config = ap.checker(track)
            data = config.read_bytes()
            if track == "promptfoo":
                text = strip_generated(data.decode("utf-8", errors="replace"))
                self._copy_local_files(text, ap.project, scratch)
                data = text.encode("utf-8")
            store.write_bytes_atomic(scratch / config.name, data)
            store.write_bytes_atomic(scratch / "test-cases.md", ap.test_cases.read_bytes())
            for i in range(1, baseline.RUNS + 1):
                store.write_bytes_atomic(scratch / "runs" / f"run-{i}.txt", root.run_file(i).read_bytes())
            env, options = self._options()
            result = baseline.run_checks(scratch, track, env=env, **options)
            if not result["ok"]:
                raise self._fail("checker_failed", error=result["error"])
            return compact(baseline.summarize(result))
        finally:
            shutil.rmtree(str(scratch), ignore_errors=True)

    def _check_repair(self, n):
        """Note that Iteration 0 has to be rerun when this attempt's checker gives it different verdicts.

        The scratch run happens outside the lock, so a slow checker never holds up the page.
        """
        with self._lock:
            ap = self._ap(n)
            zero, zero_hash = self._zero()
            mine = checker_hash(ap.checker(self.track), self.track)
            if zero is None or mine is None or mine == zero_hash:
                return
        again = self._zero_with(ap)
        with self._lock:
            block = self._block(create=True)
            if again is not None and again != zero:
                block["rerun"] = {"attempt": n, "checker_hash": mine}
            elif block["rerun"] and block["rerun"]["attempt"] == n:
                block["rerun"] = None
            self._save_progress()

    def rerun_needed(self):
        """The note that the original five answers must be run again with the corrected checker, or None."""
        return self._block()["rerun"]

    def rerun_iteration_zero(self):
        """Run the original five answers with the corrected checker and keep the result as the corrected Iteration 0."""
        with self._lock:
            note = self.rerun_needed()
            if not note:
                return None
            ap = self._ap(note["attempt"])
        results = self._zero_with(ap)  # outside the lock, like every checker run
        if results is None:
            raise self._fail("answers_missing", n=0, files="runs/run-1.txt to runs/run-5.txt")
        with self._lock:
            block = self._block(create=True)
            block["iteration_0"] = {"checker_hash": note["checker_hash"], "results": results}
            block["rerun"] = None
            self._save_progress()
            return results

    # --- deciding ------------------------------------------------------------------

    def decide(self, n, choice):
        """Keep or undo a scored, fresh attempt. This is the only thing that moves the kept version."""
        with self._lock:
            rec = self._require(n)
            if choice not in DECISIONS:
                raise self._fail("bad_decision")
            if rec["decision"] != "pending":
                raise self._fail("already_decided", n=n, decision=rec["decision"])
            if rec["hashes"] is None:
                raise self._fail("not_scored", n=n)
            stale = self._stale(rec)
            if stale:
                raise self._fail("stale", n=n, what=self._stale_words(stale))
            if self.rerun_needed():
                raise self._fail("rerun_needed")
            rec["decision"] = DECISIONS[choice]
            self._save_progress()
            return self.view(n)

    # --- what the participant sees -------------------------------------------------

    def _results_of(self, n):
        if n == 0:
            return self._zero()[0]
        rec = self._find(n)
        return rec["results"] if rec else None

    def coverage(self, rec):
        """How the rules this attempt reports differ from Part 3's Iteration 0: {changed, added, removed, lost, text}.

        It is always compared with the original Iteration 0, so a corrected Iteration 0 never hides a changed rule set.
        """
        summary = self._zero_summary()
        zero, now = (compact(summary) if summary else None), rec["results"]
        if zero is None or now is None:
            return {"changed": False, "added": [], "removed": [], "lost": [], "text": None}
        before, after = set(_ids(zero)), set(_ids(now))
        added, removed = _ids({k: 0 for k in after - before}), _ids({k: 0 for k in before - after})
        lost = _ids({k: 0 for k in (set(now["not_checked"]) - set(zero["not_checked"])) & before & after})
        words, details = self.words["coverage"], []
        for key, ids in (("added", added), ("removed", removed), ("lost", lost)):
            if ids:
                details.append(words[key].format(ids=_list_ids(ids)))
        changed = bool(details)
        return {"changed": changed, "added": added, "removed": removed, "lost": lost,
                "text": words["changed"].format(details="; ".join(details)) if changed else None}

    def evidence(self, rec):
        """How the attempt's score compares with its starting point, in the plain words. None until it is decided."""
        results, start = rec["results"], self._results_of(rec["parent"])
        if results is None or start is None or rec["decision"] == "pending":
            return None
        before, after = overall(start), overall(results)
        coverage = self.coverage(rec)
        gain = rec["decision"] == "kept" and not coverage["changed"] and _better(after, before)
        words = self.words["evidence"]
        verdict = words["gain" if gain else "no_gain"]
        text = words["line"].format(n=rec["n"], verdict=verdict, before=_fraction(before), after=_fraction(after))
        if coverage["changed"]:
            text += " " + words["coverage_not_gain"]
        return {"gain": gain, "verdict": verdict, "text": text}

    def _five_answers(self, rec):
        if rec["results"] is None:
            return None
        passes, total = overall(rec["results"])
        words = self.words["five_answers"]
        meets = _meets(passes, total)
        return {"passes": passes, "total": total, "meets_target": meets,
                "text": words["met" if meets else "below"].format(passes=passes, total=total),
                "next_step": None if meets else words["next_step"]}

    def _known_good(self, n, rec):
        """The known-good result, only when its answer is saved. Never merged with the five-answer score."""
        ap = self._ap(n)
        saved = rec["known_good"]
        if saved is None or not gates.has_text(ap.known_good):
            return None
        words = self.words["known_good"]
        passes, checked = saved["passes"], saved["checked"]
        meets = _meets(passes, checked)
        stale = (saved["answer_hash"] != gates.file_sha256(ap.known_good)
                 or saved["checker_hash"] != self._hashes(ap)["checker"])
        if checked == 0:
            text = words["none_checked"]
        else:
            text = words["meets" if meets else "below"].format(passes=passes, checked=checked)
        return {"passes": passes, "checked": checked, "meets": meets, "stale": stale, "failing": saved["failing"],
                "text": text, "next_step": None if meets else words["next_step"]}

    def _names(self, n):
        """{rule id: name}, from Iteration 0's saved summary and the attempt's own results.json."""
        names = {}
        summaries = [self._zero_summary()]
        if n:
            try:
                summaries.append(store.read_json(self._ap(n).results))
            except (OSError, store.CorruptStateError):
                pass
        for summary in summaries:
            for criterion in (summary or {}).get("criteria", []) if isinstance(summary, dict) else []:
                names[criterion["id"]] = criterion["name"]
        return names

    @staticmethod
    def _cell(results, cid):
        if results is None or cid not in results:
            return None
        return {"passes": results[cid]["passes"], "checked": results[cid]["checked_runs"],
                "not_checked": cid in results["not_checked"]}

    def rules_of(self, n):
        """Every rule of version n (0 is Iteration 0) with its pass count; `failing` marks a rule under 5 of 5."""
        results = self._results_of(n)
        if results is None:
            return []
        names = self._names(n)
        out = []
        for cid in _ids(results):
            cell = self._cell(results, cid)
            out.append(dict(cell, id=cid, name=names.get(cid, cid),
                            failing=not cell["not_checked"] and cell["passes"] < cell["checked"]))
        return out

    def compare(self, rec):
        """Every rule's count before (the starting version) and after (this attempt), plus the two overall scores.

        A rule that is NOT CHECKED now but was checked before is `lost`. None until the attempt is scored.
        """
        results, start = rec["results"], self._results_of(rec["parent"])
        if results is None or start is None:
            return None
        names, rows = self._names(rec["n"]), []
        for cid in _ids({**{k: 0 for k in _ids(start)}, **{k: 0 for k in _ids(results)}}):
            before, after = self._cell(start, cid), self._cell(results, cid)
            lost = bool(before and after and after["not_checked"] and not before["not_checked"])
            change = None
            if before and after and not before["not_checked"] and not after["not_checked"]:
                change = "up" if after["passes"] > before["passes"] else "down" if after["passes"] < before["passes"] \
                    else "same"
            rows.append({"id": cid, "name": names.get(cid, cid), "before": before, "after": after, "change": change,
                         "lost": lost})
        first, second = overall(start), overall(results)
        return {"rules": rows, "before": {"passes": first[0], "total": first[1]},
                "after": {"passes": second[0], "total": second[1]}}

    def view(self, n):
        """Everything the page needs about attempt n. The two scores are separate fields and are never combined."""
        with self._lock:
            rec = self._require(n)
            ap = self._ap(n)
            stale = self._stale(rec)
            return {
                "n": n, "parent": rec["parent"], "log_entry": rec["log_entry"], "decision": rec["decision"],
                "model": rec["model"], "hypothesis": gates.read_text(ap.hypothesis),
                "hypothesis_saved": bool(rec["hypothesis_hash"]), "run_started": self._run_started(ap, rec),
                "scored": rec["hashes"] is not None, "stale": stale,
                "stale_text": self._stale_words(stale) if stale else None,
                "five_answers": self._five_answers(rec), "known_good": self._known_good(n, rec),
                "known_good_saved": gates.has_text(ap.known_good),
                "coverage": self.coverage(rec), "evidence": self.evidence(rec),
                "start_rules": self.rules_of(rec["parent"]), "compare": self.compare(rec),
                "source": self.source(),
            }

    def overview(self):
        """The attempts, the kept version, the pending rerun of Iteration 0 and the completion result."""
        with self._lock:
            return {"attempts": [self.view(rec["n"]) for rec in self.manifest()], "kept": self.kept(),
                    "rerun_needed": bool(self.rerun_needed()), "rerun_text": (
                        self.words["errors"]["rerun_needed"] if self.rerun_needed() else None),
                    "completion": self.completion()}

    # --- the log -------------------------------------------------------------------

    def _log_entries(self):
        """(entries, problem): the log's entries in order, or why there are none."""
        problems, log, name = self.words["gate"]["problems"], self._base().iteration_log, self._log_name()
        if not log.is_file():
            return None, problems["no_log"].format(log=name)
        try:
            return parsers.parse_iteration_log(gates.read_text(log)), None
        except parsers.IterationLogError as exc:
            return None, problems["unusable"].format(error=str(exc), log=name)

    def _attempt_items(self, rec, entries, log_problem):
        """[(item key, ok, problem text)] for one attempt: the log entry against the manifest and the saved results."""
        problems = self.words["gate"]["problems"]
        n = rec["n"]
        if entries is None:
            return [("entry", False, log_problem)]
        mine = [e for e in entries if e["number"] == rec["log_entry"]]
        if not mine:
            return [("entry", False, problems["no_entry"].format(n=n))]
        if len(mine) > 1:
            return [("entry", False, problems["two_entries"].format(n=n))]
        entry, items = mine[0], [("entry", True, "")]
        if not entry["decision"]:
            decision = problems["decision_missing"].format(n=n)
        elif entry["decision"] != rec["decision"]:
            decision = problems["decision_differs"].format(n=n, log=entry["decision"], app=rec["decision"])
        else:
            decision = ""
        items.append(("decision", not decision, decision))
        items.append(("hypothesis", *self._hypothesis_problem(rec, entry)))
        stale = self._stale(rec)
        if rec["hashes"] is None:
            items.append(("scored", False, problems["not_scored"].format(n=n)))
        elif stale:
            items.append(("scored", False, problems["stale"].format(n=n, what=self._stale_words(stale))))
        else:
            items.append(("scored", True, ""))
        summary, why = self._saved_summary(rec) if rec["hashes"] is not None and not stale else (None, None)
        if summary is None:
            wait = why or problems["wait_scored"].format(n=n)
            items += [("counts", False, wait), ("not_checked", False, wait)]
        else:
            counts = gates.baseline_count_problems(entry, summary, self._baseline_problems)
            items.append(("counts", not counts, " ".join(counts)))
            nc = gates.baseline_not_checked_problems(entry, summary, self._baseline_problems)
            items.append(("not_checked", not nc, " ".join(nc)))
        items.append(("written", *self._written_problem(rec, entry)))
        return items

    def _written_problem(self, rec, entry):
        """Change, Result and Reasoning each have text. Only their presence is checked, never what they say."""
        problems, n = self.words["gate"]["problems"], rec["n"]
        names = self.words["written_names"]
        empty = [names[key] for key in ("change", "result", "reasoning") if not entry[key].strip()]
        if empty:
            return False, problems["written_missing"].format(n=n, fields=", ".join(empty))
        return True, ""

    def _hypothesis_problem(self, rec, entry):
        problems, n = self.words["gate"]["problems"], rec["n"]
        saved = gates.read_text(self._ap(n).hypothesis)
        if not rec["hypothesis_hash"] or not saved.strip():
            return False, problems["hypothesis_unsaved"].format(n=n)
        shown = _squash(saved)
        if not entry["hypothesis"]:
            return False, problems["hypothesis_missing"].format(n=n, saved=shown)
        if parsers._log_text(shown) != parsers._log_text(entry["hypothesis"]):
            return False, problems["hypothesis_differs"].format(n=n, saved=shown, log=entry["hypothesis"])
        return True, ""

    def _saved_summary(self, rec):
        """(summary, problem): the attempt's results.json, when it still says what the manifest says."""
        problems, n = self.words["gate"]["problems"], rec["n"]
        try:
            data = store.read_json(self._ap(n).results)
            summary = {key: data[key] for key in ("criteria", "overall", "not_checked", "runs")}
            if compact(summary) != rec["results"]:
                return None, problems["results_changed"].format(n=n)
            return summary, None
        except (OSError, KeyError, TypeError, store.CorruptStateError):
            return None, problems["results_missing"].format(n=n)

    def check_log(self, through=None):
        """Compare each attempt's log entry with the manifest and its saved results. Reads only: the log is never edited.

        `through` limits the check to attempts up to that number, so a round's step is not held up by a later round.
        """
        with self._lock:
            report = gates.Report(self.words["gate"])
            entries, log_problem = self._log_entries()
            for rec in self.manifest():
                if through is not None and rec["n"] > through:
                    continue
                for key, ok, problem in self._attempt_items(rec, entries, log_problem):
                    report.add(key, ok, n=rec["n"], problem=problem)
                if self.coverage(rec)["changed"]:
                    report.nudges.append(self.words["gate"]["nudge_coverage"]["text"].format(n=rec["n"]))
            return report.result()

    # --- completion ----------------------------------------------------------------

    def completion(self):
        """Two documented rounds after Iteration 0 finish Part 4. The five-answer score is a target, never a gate."""
        with self._lock:
            entries, log_problem = self._log_entries()
            counted = []
            for rec in self.manifest():
                if rec["decision"] == "pending" or rec["hashes"] is None:
                    continue
                if all(ok for _, ok, _ in self._attempt_items(rec, entries, log_problem)):
                    counted.append(rec)
            words = self.words["completion"]
            count = len(counted)
            if count >= ROUNDS_NEEDED:
                text = words["done"].format(count=count)
            else:
                text = words["need_one" if count == ROUNDS_NEEDED - 1 else "need_two"].format(count=count)
            latest = self._five_answers(counted[-1]) if counted else None
            return {"ok": count >= ROUNDS_NEEDED and not self.rerun_needed(), "rounds": count,
                    "needed": ROUNDS_NEEDED, "text": text, "five_answers": latest,
                    "next_step": latest["next_step"] if latest else None,
                    "evidence": [e["text"] for e in (self.evidence(rec) for rec in counted) if e]}
