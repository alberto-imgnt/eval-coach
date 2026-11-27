"""Atomic JSON persistence and the progress.json schema."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

STEP_IDS = ("inputs", "generate", "build", "fixtures", "readback", "predict", "key", "run", "fix", "baseline")
SCHEMA_VERSION = 1

# Every lesson and step in teaching order. Preflight is a screen between mission and hook.
COURSE = (
    ("lesson", "mission"), ("lesson", "hook"), ("lesson", "several-runs"),
    ("step", "inputs"), ("step", "generate"),
    ("lesson", "rules"),
    ("step", "build"),
    ("lesson", "trust"),
    ("step", "fixtures"), ("step", "readback"), ("step", "predict"), ("step", "key"),
    ("lesson", "surprise"),
    ("step", "run"),
    ("step", "fix"),
    ("lesson", "baseline-why"),
    ("step", "baseline"),
)
LESSON_IDS = tuple(item for kind, item in COURSE if kind == "lesson")

TRACKS = ("script", "promptfoo")
# The promptfoo track has one extra typed step, right after fixtures. Every other step is shared.
EXTRA_STEP = "fixtures-config"
# An optional step on the promptfoo track only. It is not in the step order, so it never gates anything and
# never keeps the course from being finished; it is reachable once the baseline step is done.
OPTIONAL_STEP = "live"
PROMPTFOO_COURSE = tuple(
    entry for item in COURSE for entry in ((item, ("step", EXTRA_STEP)) if item == ("step", "fixtures") else (item,)))
PROMPTFOO_STEP_IDS = tuple(item for kind, item in PROMPTFOO_COURSE if kind == "step")


def step_ids(track="script"):
    return PROMPTFOO_STEP_IDS if track == "promptfoo" else STEP_IDS


def course_items(track="script"):
    return PROMPTFOO_COURSE if track == "promptfoo" else COURSE


@dataclass(frozen=True)
class StepOwns:
    """What one step of a restartable Part leaves behind besides its saved record."""

    files: tuple = ()  # project files it made, as forward-slash paths under the project folder
    scratch: tuple = ()  # folders it used in the app's own folder
    rewrite: tuple = ()  # project files a restart keeps but puts back changed (the original goes to the backup)


@dataclass(frozen=True)
class Part:
    """One Part of the series that has content: its course, its content files and where its steps are saved."""

    id: str
    n: int
    mission: str  # the lesson that can be read before setup passes
    course: tuple  # ordered (kind, id) pairs
    lessons_file: str
    steps_file: str
    progress_key: Optional[str] = None  # None: Part 3's steps stay at the top of progress.json
    track_courses: Dict[str, tuple] = field(default_factory=dict)  # a track's own order, when it differs
    extra_steps: tuple = ()  # steps outside the course order that still belong to this Part
    new_steps: Optional[Callable[[], dict]] = None  # default saved record of each step (Parts other than Part 3)
    restart: Optional[Dict[str, StepOwns]] = None  # what each step owns; None means "Start this step again" is not offered
    new_extra: Optional[Callable[[], dict]] = None  # more keys of the saved block besides `done` and `steps`
    # Steps that follow the required order and unlock in their own order once every required item is done. They are
    # saved in `done` after the required steps, and never count toward the Part being done.
    optional_steps: tuple = ()

    def course_for(self, track="script"):
        return self.track_courses.get(track, self.course)

    def step_ids_for(self, track="script"):
        return tuple(item for kind, item in self.course_for(track) if kind == "step")

    @property
    def lesson_ids(self):
        return tuple(item for kind, item in self.course if kind == "lesson")

    @property
    def step_ids(self):
        return self.step_ids_for()

    def saved_step_ids(self, track="script"):
        """The order `done` may hold: the required steps, then the optional ones."""
        return self.step_ids_for(track) + self.optional_steps

    def owns(self, item_id):
        return (item_id in self.lesson_ids or item_id in self.step_ids or item_id in self.extra_steps
                or item_id in self.optional_steps)


PART_3 = Part("part-3", 3, "mission", COURSE, "content/lessons.json", "content/steps.json",
              track_courses={"promptfoo": PROMPTFOO_COURSE}, extra_steps=(EXTRA_STEP, OPTIONAL_STEP))

# Part 1: structured prompting. Its step ids are plain words that Part 3 does not use, and its lesson ids carry
# a `p1-` prefix, so the two Parts never share an id.
COURSE_1 = (
    ("lesson", "p1-mission"),
    ("step", "cold"), ("step", "score"),
    ("lesson", "p1-gaps"), ("lesson", "p1-frameworks"),
    ("step", "rewrite"), ("step", "rescore"),
    ("lesson", "p1-benefits"),
    ("step", "own"),
)


def new_part_1_steps():
    """The saved record of each Part 1 step. It holds only what the participant answered, never a key."""
    return {
        "cold": {"model_name": "", "prompt_hash": None, "auto_started": False, "last_check": None},
        "score": {"answers": {}, "gap": "", "in_prompt": "", "last_check": None},
        "rewrite": {"framework": "", "model_name": "", "prompt_hash": None, "auto_started": False, "last_check": None},
        "rescore": {"answers": {}, "reflections": {}, "last_check": None},
        "own": {"labels": "", "last_check": None},
    }


PART_1 = Part("part-1", 1, "p1-mission", COURSE_1, "content/part-1-lessons.json", "content/part-1-steps.json",
              progress_key="part-1", new_steps=new_part_1_steps,
              restart={
                  "cold": StepOwns(files=("part-1/prompt-cold.md", "part-1/output-cold.txt"), scratch=("part1/cold",)),
                  "score": StepOwns(),
                  "rewrite": StepOwns(files=("part-1/prompt-framework.md", "part-1/output-framework.txt"),
                                      scratch=("part1/rewrite",)),
                  "rescore": StepOwns(),
                  "own": StepOwns(files=("part-1/own-before.md", "part-1/own-after.md")),
              })

# Part 2: defining evaluation criteria. Its lesson ids carry a `p2-` prefix; its step ids are plain words that
# neither Part 1 nor Part 3 uses (`reference` and not `compare`, a retired id).
COURSE_2 = (
    ("lesson", "p2-mission"),
    ("lesson", "p2-criteria"), ("step", "draft"),
    ("lesson", "p2-thresholds"), ("step", "thresholds"),
    ("lesson", "p2-testfile"), ("step", "test-file"),
    ("step", "reference"),
)


def new_part_2_steps():
    """The saved record of each Part 2 step. It holds only the participant's own ticks and choices, never a text."""
    return {
        "draft": {"checks": {"traces": False, "distinct": False}, "last_check": None},
        "thresholds": {"checks": {"script_test": False}, "last_check": None},
        "test-file": {"last_check": None},
        "reference": {"choices": {}, "last_check": None},
    }


PART_2 = Part("part-2", 2, "p2-mission", COURSE_2, "content/part-2-lessons.json", "content/part-2-steps.json",
              progress_key="part-2", new_steps=new_part_2_steps,
              restart={
                  "draft": StepOwns(files=("part-2/worksheet.json", "part-2/test-cases.md")),
                  "thresholds": StepOwns(rewrite=("part-2/worksheet.json",)),
                  "test-file": StepOwns(files=("part-2/test-cases.md",)),
                  "reference": StepOwns(),
              })
# Part 4: improving a prompt one change at a time. Its step ids are plain words that no other Part uses, and its
# lesson ids carry a `p4-` prefix. A round is four steps (hypothesis, edit, measure, decide) and round n is attempt n.
# Its saved block also holds the attempt manifest (see attempts.py): hashes, counts and ids only, never a text.
ROUNDS_4 = (1, 2, 3)
REQUIRED_ROUNDS_4 = (1, 2)
ROUND_PHASES = ("hypothesis", "edit", "measure", "decide")


def round_steps_4(n):
    return tuple(f"{phase}-{n}" for phase in ROUND_PHASES)


COURSE_4 = (
    ("lesson", "p4-mission"),
    ("step", "starting-point"),
    ("lesson", "p4-checker-first"),
    ("step", "known-good"),
    ("lesson", "p4-one-change"), ("lesson", "p4-worked-example"),
    *(("step", s) for s in round_steps_4(1)),
    ("lesson", "p4-read-results"),
    *(("step", s) for s in round_steps_4(2)),
    ("lesson", "p4-keep-and-log"),
)
# Round 3 follows the required order and never keeps the Part from being done.
OPTIONAL_STEPS_4 = round_steps_4(3)


def new_part_4_steps():
    """The saved record of each Part 4 step. Each attempt's own record is in the manifest, not here."""
    steps = {"starting-point": {"last_check": None}, "known-good": {"last_check": None}}
    for n in ROUNDS_4:
        steps[f"hypothesis-{n}"] = {"last_check": None}
        steps[f"edit-{n}"] = {"last_check": None}
        steps[f"measure-{n}"] = {"model": "", "models": [], "auto_started": False, "last_check": None}
        steps[f"decide-{n}"] = {"auto_started": False, "reflection": "", "last_check": None}
    return steps


def new_part_4_extra():
    """The attempt manifest, the starting point (None until chosen; "own" or "practice") and the two notes that gate
    comparing attempts with Iteration 0."""
    return {"attempts": [], "rerun": None, "iteration_0": None, "start": None}


PART_4 = Part("part-4", 4, "p4-mission", COURSE_4, "content/part-4-lessons.json", "content/part-4-steps.json",
              progress_key="part-4", new_steps=new_part_4_steps, new_extra=new_part_4_extra,
              optional_steps=OPTIONAL_STEPS_4)

# Part 3 stays first: its steps file also holds the messages every Part shares.
PARTS = (PART_3, PART_1, PART_2, PART_4)
# Parts whose engine is built and whose saved progress is read, but whose course content has not shipped. They are
# not in PARTS, so no lessons or step text is loaded for them and the Series map is unchanged.
DARK_PARTS = ()


# Step kinds: a step whose content names a `kind` is handled by the object registered for it. A step with no
# kind takes the Part 3 path. Later changes add kinds; none is registered here.
STEP_KINDS = {}


def part_by_id(part_id):
    return next((p for p in PARTS if p.id == part_id), None)


def known_part(part_id):
    """A registered Part, or a dark one whose saved block is still read and checked."""
    return part_by_id(part_id) or next((p for p in DARK_PARTS if p.id == part_id), None)


def part_of(item_id):
    """The Part that owns a lesson or step id, or None."""
    return next((p for p in PARTS if p.owns(item_id)), None)


def all_lesson_ids():
    return tuple(item for p in PARTS for item in p.lesson_ids)


def all_step_ids():
    return tuple(item for p in PARTS for item in p.step_ids + p.extra_steps + p.optional_steps)


def duplicate_ids(parts=None):
    """Lesson and step ids that more than one Part names, as plain messages."""
    seen, problems = {}, []
    for part in PARTS if parts is None else parts:
        for kind, item in [("lesson", i) for i in part.lesson_ids] + [("step", i) for i in part.step_ids + part.extra_steps + part.optional_steps]:
            if item in seen and seen[item] != part.id:
                problems.append(f"{kind} id {item!r} is in both {seen[item]} and {part.id}")
            seen.setdefault(item, part.id)
    return problems


@contextmanager
def register_part(part):
    """Add a Part for the length of a with block. For tests: production code reads PARTS only."""
    global PARTS
    saved = PARTS
    PARTS = saved + (part,)
    try:
        yield part
    finally:
        PARTS = saved


@contextmanager
def register_step_kind(kind, handler):
    """Register a step kind for the length of a with block. For tests."""
    STEP_KINDS[kind] = handler
    try:
        yield handler
    finally:
        STEP_KINDS.pop(kind, None)


class CorruptStateError(Exception):
    """A state file exists but cannot be used."""


def _replace(tmp, path):
    # On Windows a scanner or indexer can hold the target for a moment.
    for attempt in range(20):
        try:
            os.replace(str(tmp), str(path))
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def write_bytes_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(str(tmp), "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_json_atomic(path, obj):
    write_bytes_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8"))


def read_json(path):
    """Read JSON. Raises FileNotFoundError if absent, CorruptStateError if unusable."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CorruptStateError(f"{path} is not valid JSON: {exc}") from exc


def new_lessons_block():
    """Course progress. It holds only what the participant did, never course answers."""
    return {"seed": None, "per_lesson": {}, "placement": {}, "records": [], "review": {"items": {}}, "step_checks": {},
            "skipped_parts": []}


def default_step_entry(step):
    """The saved record of a step that only one track has."""
    if step == EXTRA_STEP:
        return {"last_check": None, "checklist": {}, "auto_started": False}
    if step == OPTIONAL_STEP:
        return {"last_check": None, "checklist": {}, "acknowledged": False, "cli": "", "done": False,
                "start_hashes": None, "auto_started": False}
    raise KeyError(step)


def new_progress(project_path, cli_command, starter):
    progress = {
        "version": SCHEMA_VERSION,
        "project_path": str(project_path),
        "cli_command": cli_command,
        "starter": starter,
        "track": None,  # set when the first step is finished; from then on the project keeps it
        "done": [],
        "skipped": False,
        "lessons": new_lessons_block(),
        "parts": {},  # step progress of every Part but Part 3, each created on first use
        "steps": {
            "inputs": {"last_check": None, "choice": {"prompt": {}, "test_cases": {}}},
            "generate": {"model_name": "", "models_used": [], "auto_started": False, "last_check": None},
            "build": {"checklist": {}, "auto_started": False, "last_check": None},
            "fixtures": {"auto_started": False, "last_check": None},
            "readback": {"answers": {}, "note": "", "auto_started": False, "last_check": None},
            "predict": {"locked": False, "manual_criteria": [], "locked_criteria": [],
                        "bad": {}, "polished": {},
                        "answers": {"wrong": "", "catches": "", "worst_guess": ""},
                        "last_check": None},
            "key": {"auto_started": False, "last_check": None},
            "run": {"classifications": {}, "last_check": None},
            "fix": {"start_tc_hash": None, "start_check_hash": None, "seen_tc_hash": None,
                    "tc_edit_check_hash": None, "rerun_check_hash": None, "rerun_tc_hash": None,
                    "explanation": "", "auto_started": False, "last_check": None},
            "baseline": {"run_check_hash": None, "run_runs_hash": None, "auto_started": False, "last_check": None},
        },
    }
    for step in progress["steps"].values():
        step.setdefault("checklist", {})
    return progress


def new_part_progress(part):
    """The saved progress of a Part other than Part 3: its finished steps and one record for each step."""
    steps = part.new_steps() if part.new_steps is not None else {}
    block = {"done": [], "steps": steps}
    if part.new_extra is not None:
        block.update(part.new_extra())
    return block


def _merge_defaults(value, default, where):
    """Fill missing keys from default; a wrong container type is corruption."""
    if isinstance(default, dict):
        if not isinstance(value, dict):
            raise CorruptStateError(f"{where} should be an object.")
        merged = dict(value)
        for key, sub in default.items():
            merged[key] = _merge_defaults(value[key], sub, f"{where}.{key}") if key in value else sub
        return merged
    if isinstance(default, list) and not isinstance(value, list):
        raise CorruptStateError(f"{where} should be a list.")
    if isinstance(default, str) and not isinstance(value, str):
        raise CorruptStateError(f"{where} should be text.")
    if isinstance(default, bool) and not isinstance(value, bool):
        raise CorruptStateError(f"{where} should be true or false.")
    return value


def _add_key_step(data, sealed_key_exists):
    """Fit progress saved before the key step existed into the current step order.

    With no `key` entry and predict already done, the key step counts as done
    if the sealed key exists. Otherwise it is the next step, and any later
    steps have to be done again.
    """
    if not isinstance(data, dict) or not isinstance(data.get("steps"), dict) or "key" in data["steps"]:
        return data
    done = data.get("done")
    if not isinstance(done, list) or "key" in done or "predict" not in done:
        return data
    upto = done.index("predict") + 1
    return dict(data, done=done[:upto] + ["key"] + done[upto:] if sealed_key_exists else done[:upto])


def _add_lessons_block(data):
    """Fit progress saved before lessons existed into the course.

    Lessons before the furthest completed step do not block and schedule no reviews.
    """
    if not isinstance(data, dict) or "lessons" in data or not isinstance(data.get("done"), list):
        return data
    block = new_lessons_block()
    finished = [COURSE.index(("step", s)) for s in data["done"] if s in STEP_IDS]
    furthest = max(finished) if finished else -1
    for index, (kind, item) in enumerate(COURSE):
        if kind == "lesson" and index < furthest:
            block["per_lesson"][item] = {"status": "skipped", "migrated": True, "activities": {}}
    return dict(data, lessons=block)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _add_inputs_step(data, paths, selected_track):
    steps = data.get("steps") if isinstance(data, dict) else None
    done = data.get("done") if isinstance(data, dict) else None
    if not isinstance(steps, dict) or "inputs" in steps or not isinstance(done, list) or "inputs" in done:
        return data
    generate = steps.get("generate")
    started = isinstance(generate, dict) and generate.get("auto_started") is True
    if not (done or started or (paths is not None and any(paths.run_file(n).is_file() for n in range(1, 6)))):
        return data
    choice = {}
    for key in ("prompt", "test_cases"):
        digest = None
        if paths is not None:
            path = getattr(paths, key)
            try:
                digest = file_sha256(path)
            except FileNotFoundError:
                pass
        choice[key] = {"source": "existing", "sha256": digest}
    track = data.get("track")
    if track is None and (not done or EXTRA_STEP in done):
        track = "promptfoo" if EXTRA_STEP in done else selected_track
    return dict(data, done=["inputs", *done], track=track,
                steps={**steps, "inputs": {"last_check": None, "choice": choice}})


def prune_lessons_block(block):
    """Drop everything saved for a lesson that is no longer in the course. Returns True if anything went."""
    known = set(all_lesson_ids())
    dropped = False
    per_lesson = block.get("per_lesson")
    if isinstance(per_lesson, dict):
        for lesson in [x for x in per_lesson if x not in known]:
            del per_lesson[lesson]
            dropped = True
    records = block.get("records")
    if isinstance(records, list):
        kept = [r for r in records if not isinstance(r, dict) or r.get("lesson") in known]
        dropped = dropped or len(kept) != len(records)
        block["records"] = kept
    skipped = block.get("skipped_parts")
    if isinstance(skipped, list):
        block["skipped_parts"] = [p for p in skipped if part_by_id(p) is not None]
    items = block.get("review", {}).get("items") if isinstance(block.get("review"), dict) else None
    if isinstance(items, dict):
        for key in [k for k, v in items.items() if isinstance(v, dict) and v.get("lesson") not in known]:
            del items[key]
            dropped = True
    return dropped


def _migrate_new_lessons(block, done, parts=None):
    """After old lessons were dropped, lessons before a Part's furthest finished step block nothing.

    `done` is Part 3's list; `parts` maps each other Part's id to its saved block.
    """
    pairs = [(COURSE, done)]
    for part_id, saved in (parts or {}).items():
        part = part_by_id(part_id)
        if part is not None and part.progress_key is not None and isinstance(saved, dict):
            pairs.append((part.course, saved["done"]))
    for course, finished_steps in pairs:
        finished = [course.index(("step", s)) for s in finished_steps if ("step", s) in course]
        furthest = max(finished) if finished else -1
        for index, (kind, item) in enumerate(course):
            if kind == "lesson" and index < furthest and item not in block["per_lesson"]:
                block["per_lesson"][item] = {"status": "skipped", "migrated": True, "activities": {}}


def _validate_parts(data):
    """Check and complete each saved Part block. A Part this build does not know is left as it is."""
    for part_id, saved in data["parts"].items():
        part = known_part(part_id)
        if part is None or part.progress_key is None:
            continue
        saved = _merge_defaults(saved, new_part_progress(part), f"progress.parts.{part_id}")
        bad = [s for s in saved["done"] if s not in part.saved_step_ids()]
        if bad:
            raise CorruptStateError(f"progress lists unknown steps for {part_id}: {bad}")
        if list(saved["done"]) != list(part.saved_step_ids()[: len(saved["done"])]):
            raise CorruptStateError(f"progress lists finished steps out of order for {part_id}.")
        data["parts"][part_id] = saved


def validate_progress(data, sealed_key_exists=False, paths=None, selected_track=None):
    """Return a complete progress dict, or raise CorruptStateError."""
    default = new_progress("", "", "")
    # A progress.json from before the baseline step has no `baseline` entry; it gets the default one
    # here, and the step simply comes next after fix. Nothing is marked done that was not.
    data = _add_inputs_step(_add_key_step(data, sealed_key_exists), paths, selected_track)
    data = _merge_defaults(_add_lessons_block(data), default, "progress")
    _validate_parts(data)
    if prune_lessons_block(data["lessons"]) and isinstance(data["done"], list):
        _migrate_new_lessons(data["lessons"], data["done"], data["parts"])
    if data["track"] not in (None,) + TRACKS:
        raise CorruptStateError("progress names an unknown track.")
    track = data["track"] or ("promptfoo" if EXTRA_STEP in data["done"] else "script")
    ids = step_ids(track)
    bad = [s for s in data["done"] if s not in ids]
    if bad:
        raise CorruptStateError(f"progress lists unknown steps: {bad}")
    expected = list(ids[: len(data["done"])])
    if list(data["done"]) != expected:
        raise CorruptStateError("progress lists finished steps out of order.")
    if "inputs" in data["done"] and all(
        data["steps"]["inputs"]["choice"][key].get("source") == "existing" for key in ("prompt", "test_cases")
    ):
        _migrate_new_lessons(data["lessons"], data["done"])
    return data


def load_progress(path, sealed_key_exists=False, paths=None, selected_track=None):
    return validate_progress(read_json(path), sealed_key_exists, paths, selected_track)


def save_progress(path, progress):
    write_json_atomic(path, progress)
