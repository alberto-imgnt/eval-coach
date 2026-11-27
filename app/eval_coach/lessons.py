"""Course content: loading, schema validation, grading and views with the answers removed."""
from __future__ import annotations

import hashlib
import json
import posixpath

from . import resources
from . import state
from .state import PART_3

HOOK_LINE = ("Read update.txt and requirements.md. Score the update from 1 to 10 against the "
             "requirements, say pass or fail, and give one sentence of reasoning. Save only that to "
             "output.txt. Do nothing else.")
DEMO_LINE = "Read skills/build-eval-script/SKILL.md and follow it in build mode on test-cases.md."

ACTIVITY_TYPES = ("choice", "order", "sort", "rule_lab", "reflection", "cli_compare", "cli_demo", "cli_practice")
PRACTICE_OUTPUT = "output.txt"
RULE_KINDS = ("word_count_under", "all_present", "none_present", "all_labels")
MAX_PLACEMENT = 6
GLOSSARY_KINDS = ("idea", "course")
KIT_PREFIX = "kit:"
HIDDEN_KIT_NAMES = ("answer-key.md",)
VERDICT_WORDS = {"pass": "pass", "fail": "fail", "p": "pass", "f": "fail"}


class LessonError(Exception):
    """lessons.json or glossary.json breaks the schema in docs/CONTENT-RULES.md."""

    def __init__(self, problems):
        self.problems = list(problems) if isinstance(problems, (list, tuple)) else [problems]
        super().__init__("; ".join(self.problems))


class AnswerError(Exception):
    """An answer is not shaped the way the activity expects."""


# --- rules -----------------------------------------------------------------


def evaluate_rule(rule, text):
    """The fixed rule kinds. Returns (passed, facts for the reason text)."""
    kind, params = rule["kind"], rule.get("params", {})
    if kind == "word_count_under":
        count = len(text.split())
        return count < params["limit"], {"count": count, "limit": params["limit"]}
    lowered = text.lower()
    if kind == "all_present":
        missing = [t for t in params["terms"] if t.lower() not in lowered]
        return not missing, {"missing": missing, "terms": params["terms"]}
    if kind == "none_present":
        found = [t for t in params["terms"] if t.lower() in lowered]
        return not found, {"found": found, "terms": params["terms"]}
    if kind == "all_labels":
        missing = [t for t in params["labels"] if t not in text]
        return not missing, {"missing": missing, "labels": params["labels"]}
    raise AnswerError(f"unknown rule kind {kind!r}")


def rule_result(rule, text, reasons):
    """A rule's verdict and the plain-language reason, worded from the content file."""
    passed, facts = evaluate_rule(rule, text)
    template = reasons[rule["kind"]]["pass" if passed else "fail"]
    joined = {key: ", ".join(value) if isinstance(value, list) else value for key, value in facts.items()}
    return {"verdict": "pass" if passed else "fail", "reason": template.format(**joined)}


def case_key(case):
    return f"{case['sample']}|{case['rule']}"


def normal_verdict(value):
    return VERDICT_WORDS.get(value.strip().lower()) if isinstance(value, str) else None


# --- validation ------------------------------------------------------------


def word_count(text):
    """Word-count parity counts whitespace-separated tokens."""
    return len(text.split())


class _Checker:
    def __init__(self, part=PART_3):
        self.problems = []
        self.part = part

    def bad(self, where, message):
        self.problems.append(f"{where}: {message}")

    def nonempty_text(self, obj, field, where):
        value = obj.get(field) if isinstance(obj, dict) else None
        if not isinstance(value, str) or not value.strip():
            self.bad(where, f"{field} must be non-empty text")
            return False
        return True

    def ids(self, items, where):
        seen = set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                self.bad(where, "every entry needs a text id")
                continue
            if item["id"] in seen:
                self.bad(where, f"duplicate id {item['id']!r}")
            seen.add(item["id"])
        return seen

    def choice(self, item, where):
        self.nonempty_text(item, "prompt", where)
        options = item.get("options") if isinstance(item, dict) else None
        if not isinstance(options, list) or len(options) < 2:
            self.bad(where, "needs at least two options")
            return
        self.ids(options, f"{where}.options")
        corrects = 0
        words = set()
        for i, option in enumerate(options):
            at = f"{where}.options[{i}]"
            if not isinstance(option, dict):
                self.bad(at, "must be an object")
                continue
            self.nonempty_text(option, "text", at)
            self.nonempty_text(option, "feedback", at)
            if not isinstance(option.get("correct"), bool):
                self.bad(at, "correct must be true or false")
            elif option["correct"]:
                corrects += 1
            if isinstance(option.get("text"), str):
                words.add(word_count(option["text"]))
        if corrects != 1:
            self.bad(where, f"needs exactly one correct option, found {corrects}")
        if len(words) > 1:
            self.bad(where, f"answer-word-count mismatch: every option must have the same number of "
                            f"words, found counts {sorted(words)}")

    def order(self, activity, where):
        self.nonempty_text(activity, "prompt", where)
        self.nonempty_text(activity, "feedback_right", where)
        self.nonempty_text(activity, "feedback_wrong", where)
        items = activity.get("items")
        if not isinstance(items, list) or len(items) < 2:
            self.bad(where, "needs at least two items")
            return
        self.ids(items, f"{where}.items")
        for i, item in enumerate(items):
            self.nonempty_text(item, "text", f"{where}.items[{i}]")

    def sort(self, activity, where):
        self.nonempty_text(activity, "prompt", where)
        buckets = activity.get("buckets")
        items = activity.get("items")
        if not isinstance(buckets, list) or len(buckets) < 2:
            self.bad(where, "needs at least two buckets")
            return
        bucket_ids = self.ids(buckets, f"{where}.buckets")
        for i, bucket in enumerate(buckets):
            self.nonempty_text(bucket, "label", f"{where}.buckets[{i}]")
        if not isinstance(items, list) or len(items) < 2:
            self.bad(where, "needs at least two items")
            return
        self.ids(items, f"{where}.items")
        for i, item in enumerate(items):
            at = f"{where}.items[{i}]"
            self.nonempty_text(item, "text", at)
            self.nonempty_text(item, "feedback", at)
            if not isinstance(item, dict) or item.get("bucket") not in bucket_ids:
                self.bad(at, "bucket must name one of the buckets")
        if "reveal" in activity:
            self.nonempty_text(activity, "reveal", where)  # shown only after the activity is passed

    def rule_lab(self, activity, where):
        self.nonempty_text(activity, "prompt", where)
        samples = activity.get("samples")
        rules = activity.get("rules")
        cases = activity.get("cases")
        if not isinstance(samples, list) or not samples:
            self.bad(where, "needs samples")
            return
        if not isinstance(rules, list) or not rules:
            self.bad(where, "needs rules")
            return
        if not isinstance(cases, list) or not cases:
            self.bad(where, "needs cases")
            return
        self.ids(samples, f"{where}.samples")
        self.ids(rules, f"{where}.rules")
        rule_by_id = {}
        for i, rule in enumerate(rules):
            at = f"{where}.rules[{i}]"
            self.nonempty_text(rule, "label", at)
            if isinstance(rule, dict) and "explain" in rule:
                self.nonempty_text(rule, "explain", at)
            if self._rule(rule, at):
                rule_by_id[rule["id"]] = rule
        sample_text = {}
        for i, sample in enumerate(samples):
            at = f"{where}.samples[{i}]"
            self.nonempty_text(sample, "label", at)
            if self.nonempty_text(sample, "text", at) and isinstance(sample.get("id"), str):
                sample_text[sample["id"]] = sample["text"]
        seen = set()
        for i, case in enumerate(cases):
            at = f"{where}.cases[{i}]"
            if not isinstance(case, dict):
                self.bad(at, "must be an object")
                continue
            sample, rule, expected = case.get("sample"), case.get("rule"), normal_verdict(case.get("expected"))
            if sample not in sample_text:
                self.bad(at, f"unknown sample {sample!r}")
            if rule not in rule_by_id:
                self.bad(at, f"unknown rule {rule!r}")
            if expected is None:
                self.bad(at, "expected must be pass or fail")
            pair = (sample, rule)
            if pair in seen:
                self.bad(at, "duplicate case")
            seen.add(pair)
            if sample in sample_text and rule in rule_by_id and expected is not None:
                passed, _ = evaluate_rule(rule_by_id[rule], sample_text[sample])
                if ("pass" if passed else "fail") != expected:
                    self.bad(at, f"expected {expected!r} does not match the rule's real result")

    def _rule(self, rule, where):
        if not isinstance(rule, dict) or rule.get("kind") not in RULE_KINDS:
            self.bad(where, f"kind must be one of {RULE_KINDS}")
            return False
        params = rule.get("params")
        if not isinstance(params, dict):
            self.bad(where, "params must be an object")
            return False
        kind = rule["kind"]
        if kind == "word_count_under":
            limit = params.get("limit")
            if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                self.bad(where, "limit must be a positive whole number")
                return False
            return True
        field = "labels" if kind == "all_labels" else "terms"
        terms = params.get(field)
        if not isinstance(terms, list) or not terms or not all(isinstance(t, str) and t.strip() for t in terms):
            self.bad(where, f"{field} must be a non-empty list of text")
            return False
        return True

    def reflection(self, activity, where):
        self.nonempty_text(activity, "prompt", where)
        minimum = activity.get("min_words")
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum <= 0:
            self.bad(where, "min_words must be a positive whole number")

    def cli_files(self, activity, where):
        files = activity.get("files")
        if not isinstance(files, list) or not files:
            self.bad(where, "files must be a non-empty list")
            return
        for i, entry in enumerate(files):
            name = entry.get("name") if isinstance(entry, dict) else entry
            if not isinstance(name, str) or not name.strip():
                self.bad(f"{where}.files[{i}]", "must be a file name or an object with a name")

    def cli_line(self, activity, where, expected):
        if activity.get("line") != expected:
            self.bad(where, "line must be the exact line from docs/RUNNING-EVALS-COURSE.md")

    def cli_compare(self, activity, where):
        runs = activity.get("runs")
        if isinstance(runs, bool) or not isinstance(runs, int) or runs <= 0:
            self.bad(where, "runs must be a positive whole number")
        self.cli_line(activity, where, HOOK_LINE)
        self.cli_files(activity, where)
        question = activity.get("question")
        if not isinstance(question, dict):
            self.bad(where, "question must be a choice question")
        else:
            self.choice(question, f"{where}.question")

    def cli_demo(self, activity, where):
        self.cli_line(activity, where, DEMO_LINE)
        self.cli_files(activity, where)
        args = activity.get("run_args")
        if not isinstance(args, list) or not args:
            self.bad(where, "run_args must be a non-empty list")
            return
        for arg in args:
            safe = isinstance(arg, str) and arg and "\\" not in arg and ":" not in arg \
                and not arg.startswith("/") and ".." not in arg.split("/")
            if not safe:
                self.bad(where, f"run_args entry {arg!r} must be a file inside the demo folder")

    def cli_practice(self, activity, where):
        self.nonempty_text(activity, "line", where)
        self.nonempty_text(activity, "folder_label", where)
        line = activity.get("line")
        if isinstance(line, str) and PRACTICE_OUTPUT not in line:
            self.bad(where, f"line must tell the CLI to save its answer to {PRACTICE_OUTPUT}")
        self.cli_files(activity, where)
        for i, entry in enumerate(activity.get("files") or []):
            at = f"{where}.files[{i}]"
            if not isinstance(entry, dict):
                self.bad(at, "must be an object with a name and a source")
                continue
            name = entry.get("name")
            safe = isinstance(name, str) and name and "\\" not in name and ":" not in name \
                and not name.startswith("/") and ".." not in name.split("/") and name != PRACTICE_OUTPUT
            if not safe:
                self.bad(at, f"name {name!r} must be a file inside the practice folder, and not {PRACTICE_OUTPUT}")
            if not kit_ref_allowed(entry.get("source")):
                self.bad(at, f"source {entry.get('source')!r} is not a readable kit file")
        question = activity.get("question")
        if not isinstance(question, dict):
            self.bad(where, "question must be a choice question")
        else:
            self.choice(question, f"{where}.question")

    def activity(self, activity, where):
        if not isinstance(activity, dict) or activity.get("type") not in ACTIVITY_TYPES:
            self.bad(where, f"type must be one of {ACTIVITY_TYPES}")
            return
        if "reveal" in activity and activity["type"] != "sort":
            self.bad(where, "only a sort activity can have a reveal")
        getattr(self, activity["type"])(activity, where)

    def ref(self, ref, where):
        if not isinstance(ref, str) or not ref:
            self.bad(where, "ref must be text")
            return
        if ref.startswith("https://"):
            return
        if not ref.startswith(KIT_PREFIX):
            self.bad(where, f"ref must start with {KIT_PREFIX} or https://, got {ref!r}")
            return
        if not kit_ref_allowed(ref):
            self.bad(where, f"ref {ref!r} is not a readable kit file")

    def lesson(self, lesson, glossary_terms, lesson_ids):
        where = f"lesson {lesson.get('id')!r}" if isinstance(lesson, dict) else "lesson"
        if not isinstance(lesson, dict):
            self.bad(where, "must be an object")
            return
        for field in ("title", "win", "body"):
            self.nonempty_text(lesson, field, where)
        minutes = lesson.get("minutes")
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
            self.bad(where, "minutes must be a positive whole number")
        if not isinstance(lesson.get("skippable"), bool):
            self.bad(where, "skippable must be true or false")
        activities = lesson.get("activities")
        # Only a Part's first lesson is a plain introduction with no questions.
        if not isinstance(activities, list) or (not activities and lesson.get("id") != self.part.mission):
            self.bad(where, "needs at least one activity")
            activities = []
        activity_ids = self.ids(activities, f"{where}.activities")
        for i, activity in enumerate(activities):
            self.activity(activity, f"{where}.activities[{i}]")
        retrieval = lesson.get("retrieval")
        if not isinstance(retrieval, list) or (len(retrieval) < 2 and lesson.get("id") != self.part.mission):
            self.bad(where, "needs at least two retrieval items")
            retrieval = []
        self.ids(retrieval, f"{where}.retrieval")
        for i, item in enumerate(retrieval):
            self.choice(item, f"{where}.retrieval[{i}]")
        self._retrieval_differs(lesson, activities, retrieval, where)
        self._practice_not_skippable(lesson, activities, where)
        self._cli_placement(lesson, activities, where)
        sources = lesson.get("sources")
        if not isinstance(sources, list) or not sources:
            self.bad(where, "sources must name at least one source")
            sources = []
        for i, source in enumerate(sources):
            at = f"{where}.sources[{i}]"
            self.nonempty_text(source, "label", at)
            self.ref(source.get("ref") if isinstance(source, dict) else None, at)
        primary = lesson.get("primary_source")
        at = f"{where}.primary_source"
        self.nonempty_text(primary, "label", at)
        self.nonempty_text(primary, "why", at)
        self.ref(primary.get("ref") if isinstance(primary, dict) else None, at)
        related = lesson.get("related")
        if related is not None:
            at = f"{where}.related"
            if not isinstance(related, dict):
                self.bad(at, "must be an object")
                return
            for other in related.get("lessons", []):
                if other not in lesson_ids:
                    self.bad(at, f"unknown lesson {other!r}")
            for term in related.get("glossary", []):
                if glossary_terms is not None and (not isinstance(term, str)
                                                   or term.casefold() not in glossary_terms):
                    self.bad(at, f"unknown glossary term {term!r}")

    def _retrieval_differs(self, lesson, activities, retrieval, where):
        seen = set()
        for activity in activities:
            if isinstance(activity, dict):
                source = activity.get("question") if activity.get("type") in ("cli_compare", "cli_practice") else activity
                prompt = source.get("prompt") if isinstance(source, dict) else None
                if isinstance(prompt, str):
                    seen.add(" ".join(prompt.split()).casefold())
        for item in retrieval:
            prompt = item.get("prompt") if isinstance(item, dict) else None
            if isinstance(prompt, str) and " ".join(prompt.split()).casefold() in seen:
                self.bad(where, f"retrieval item {item.get('id')!r} repeats an activity")

    def _practice_not_skippable(self, lesson, activities, where):
        hands_on = {"rule_lab", "cli_compare", "cli_demo"}
        if lesson.get("skippable") is True and any(isinstance(a, dict) and a.get("type") in hands_on for a in activities):
            self.bad(where, "practice and CLI lessons cannot be skippable")

    def _cli_placement(self, lesson, activities, where):
        allowed = {"cli_compare": "hook", "cli_demo": "rules"}
        for activity in activities:
            if isinstance(activity, dict) and activity.get("type") in allowed:
                if lesson.get("id") != allowed[activity["type"]]:
                    self.bad(where, f"{activity['type']} may appear only in lesson {allowed[activity['type']]!r}")

    def course(self, data, glossary_terms):
        if not isinstance(data, dict):
            self.bad("lessons.json", "must be an object")
            return
        if data.get("version") != 1:
            self.bad("lessons.json", "version must be 1")
        self.nonempty_text(data, "mission", "lessons.json")
        lessons = data.get("lessons")
        if not isinstance(lessons, list):
            self.bad("lessons.json", "lessons must be a list")
            lessons = []
        ids = [x.get("id") for x in lessons if isinstance(x, dict)]
        lesson_ids = self.part.lesson_ids
        missing = [x for x in lesson_ids if x not in ids]
        extra = [x for x in ids if x not in lesson_ids]
        if missing:
            self.bad("lessons.json", f"missing lessons: {missing}")
        if extra:
            self.bad("lessons.json", f"lessons not in the course order: {extra}")
        if len(ids) != len(set(ids)):
            self.bad("lessons.json", "duplicate lesson ids")
        known = set(ids)
        for lesson in lessons:
            self.lesson(lesson, glossary_terms, known)
        placement = data.get("placement")
        if not isinstance(placement, list):
            self.bad("lessons.json", "placement must be a list")
            placement = []
        if len(placement) > MAX_PLACEMENT:
            self.bad("lessons.json", f"at most {MAX_PLACEMENT} placement questions, found {len(placement)}")
        self.ids(placement, "placement")
        for i, item in enumerate(placement):
            where = f"placement[{i}]"
            self.choice(item, where)
            target = item.get("lesson") if isinstance(item, dict) else None
            if target == self.part.mission or target not in known:
                self.bad(where, f"lesson must name a lesson after {self.part.mission}, got {target!r}")
        self.step_checks(data.get("step_checks", []))

    def step_checks(self, checks):
        if not isinstance(checks, list):
            self.bad("lessons.json", "step_checks must be a list")
            return
        self.ids(checks, "step_checks")
        steps = [c.get("step") for c in checks if isinstance(c, dict)]
        if len(steps) != len(set(steps)):
            self.bad("step_checks", "at most one check for each step")
        for i, item in enumerate(checks):
            where = f"step_checks[{i}]"
            self.choice(item, where)
            if isinstance(item, dict) and item.get("step") not in self.part.step_ids + self.part.optional_steps:
                self.bad(where, f"step must be one of {list(self.part.step_ids + self.part.optional_steps)}, "
                                f"got {item.get('step')!r}")


def kit_ref_allowed(ref):
    """Is this a kit: reference to a bundled file that participants may read?"""
    try:
        return kit_read_path(ref) is not None
    except resources.ResourceNotFound:
        return False


def kit_read_path(ref):
    """The bundled path for a kit: reference. Raises ResourceNotFound for anything else."""
    if not isinstance(ref, str) or not ref.startswith(KIT_PREFIX):
        raise resources.ResourceNotFound(repr(ref))
    rel = ref[len(KIT_PREFIX):]
    if "~" in rel:  # 8.3 short names such as ANSWER~1.MD
        raise resources.ResourceNotFound(ref)
    path = "kit/" + rel
    for name in (path, resources.canonical(path)):
        if posixpath.basename(name).lower() in HIDDEN_KIT_NAMES:
            raise resources.ResourceNotFound(ref)
    resources.read_bytes(path)  # raises for unsafe or absent paths
    return path


def validate_course(data, glossary_terms=None, part=PART_3):
    """Raise LessonError unless the course data meets the schema. `part` is the Part the file belongs to."""
    checker = _Checker(part)
    checker.course(data, glossary_terms)
    if checker.problems:
        raise LessonError(checker.problems)


def validate_glossary(data):
    """Check glossary.json's shape. Returns the set of casefolded terms."""
    problems = []
    terms = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(terms, list) or not terms:
        raise LessonError("glossary.json: terms must be a non-empty list")
    seen = set()
    for i, term in enumerate(terms):
        where = f"glossary.terms[{i}]"
        if not isinstance(term, dict):
            problems.append(f"{where}: must be an object")
            continue
        for field in ("term", "meaning"):
            if not isinstance(term.get(field), str) or not term[field].strip():
                problems.append(f"{where}: {field} must be non-empty text")
        if term.get("kind") not in GLOSSARY_KINDS:
            problems.append(f"{where}: kind must be one of {list(GLOSSARY_KINDS)}")
        if "card" in term and not isinstance(term["card"], bool):
            problems.append(f"{where}: card must be true or false")
        name = term.get("term")
        if isinstance(name, str):
            if name.casefold() in seen:
                problems.append(f"{where}: duplicate term {name!r}")
            seen.add(name.casefold())
    if problems:
        raise LessonError(problems)
    return seen


class Course:
    """A validated course: the lessons of every registered Part, keyed by lesson id."""

    def __init__(self, data, missions=None):
        self.data = data
        self.mission = data["mission"]
        self.missions = dict(missions or {})  # Part id -> that Part's mission text
        self.by_id = {lesson["id"]: lesson for lesson in data["lessons"]}
        self.placement = {item["id"]: item for item in data["placement"]}
        self.step_checks = {item["step"]: item for item in data.get("step_checks", [])}

    def __contains__(self, lesson_id):
        return lesson_id in self.by_id

    def get(self, lesson_id):
        return self.by_id.get(lesson_id)

    def mission_of(self, lesson_id):
        """The mission text of the Part the lesson belongs to."""
        part = state.part_of(lesson_id)
        return self.missions.get(part.id, self.mission) if part is not None else self.mission

    @classmethod
    def from_data(cls, data, glossary_terms=None, part=PART_3):
        validate_course(data, glossary_terms, part)
        return cls(data, {part.id: data["mission"]})

    @classmethod
    def merge(cls, courses):
        """One Course from [(part, Course), ...]. Raises LessonError when two Parts share an id."""
        if len(courses) == 1:
            return courses[0][1]
        problems = state.duplicate_ids([part for part, _ in courses])
        merged = {"version": 1, "mission": courses[0][1].mission, "step_checks": [], "placement": [], "lessons": []}
        seen = {"placement": set(), "step check": set()}
        for part, course in courses:
            merged["lessons"].extend(course.data["lessons"])
            merged["placement"].extend(course.data["placement"])
            merged["step_checks"].extend(course.data.get("step_checks", []))
            for kind, key, items in (("placement", "id", course.data["placement"]),
                                     ("step check", "id", course.data.get("step_checks", []))):
                for item in items:
                    if item[key] in seen[kind]:
                        problems.append(f"{kind} id {item[key]!r} in {part.id} is used by an earlier Part")
                    seen[kind].add(item[key])
        if problems:
            raise LessonError(problems)
        return cls(merged, {part.id: course.mission for part, course in courses})


def load_bundled():
    """Load the lessons of every registered Part and content/glossary.json from the bundle.

    Raises LessonError if a file is missing, unreadable or invalid, or if two Parts share an id.
    """
    try:
        lessons = [(part, json.loads(resources.read_text(part.lessons_file))) for part in state.PARTS]
        glossary = json.loads(resources.read_text("content/glossary.json"))
    except resources.ResourceNotFound as exc:
        raise LessonError(f"a bundled content file is missing: {exc}") from exc
    except ValueError as exc:
        raise LessonError(f"a bundled content file is not valid JSON: {exc}") from exc
    terms = validate_glossary(glossary)
    return Course.merge([(part, Course.from_data(data, terms, part)) for part, data in lessons])


def load_step_content():
    """Load the step text of every registered Part: (content, ui).

    `content` is Part 3's file (the shared messages and its steps) with every other Part's steps added to
    `steps`. `ui` maps a Part's id to the interface words its file overrides. Raises LessonError for a
    missing or invalid file, a step with no text, a step id two Parts share, or a step `kind` nobody handles.
    """
    problems = []
    from . import attempt_steps, criteria_steps, input_step, part_steps  # noqa: F401  registers the step kinds
    content, ui = None, {}
    for part in state.PARTS:
        try:
            data = json.loads(resources.read_text(part.steps_file))
        except resources.ResourceNotFound as exc:
            raise LessonError(f"a bundled content file is missing: {exc}") from exc
        except ValueError as exc:
            raise LessonError(f"a bundled content file is not valid JSON: {exc}") from exc
        steps = data.get("steps") if isinstance(data, dict) else None
        if not isinstance(steps, dict):
            raise LessonError(f"{part.steps_file}: steps must be an object")
        for step in part.step_ids + part.extra_steps + part.optional_steps:
            if step not in steps:
                problems.append(f"{part.steps_file}: no text for step {step!r}")
        for step, text in steps.items():
            kind = text.get("kind") if isinstance(text, dict) else None
            if kind is not None and kind not in state.STEP_KINDS:
                problems.append(f"{part.steps_file}: step {step!r} names the unknown kind {kind!r}")
        shared = data.get("paste_ui")
        if isinstance(shared, dict):  # the words every paste-mode step shares; a step's own `ui` wins
            for text in steps.values():
                if isinstance(text, dict) and text.get("cli_mode") == "paste":
                    text["ui"] = {**shared, **text.get("ui", {})}
        if content is None:
            content = data
        else:
            problems.extend(f"step text {step!r} in {part.id} is used by an earlier Part"
                            for step in steps if step in content["steps"])
            content["steps"].update({k: v for k, v in steps.items() if k not in content["steps"]})
        if isinstance(data.get("ui"), dict):
            ui[part.id] = data["ui"]
    problems = state.duplicate_ids() + problems
    if problems:
        raise LessonError(problems)
    return content, ui


# --- grading ---------------------------------------------------------------


def grade(activity, answer):
    """Grade an answer. Returns (passed, what to store). Raises AnswerError if malformed."""
    if not isinstance(answer, dict):
        raise AnswerError("the answer must be an object")
    kind = activity["type"]
    if kind == "choice":
        return grade_choice(activity, answer)
    if kind == "order":
        submitted = answer.get("order")
        items = [item["id"] for item in activity["items"]]
        if not isinstance(submitted, list) or sorted(map(str, submitted)) != sorted(items):
            raise AnswerError("order must list every item once")
        return submitted == items, {"order": submitted}
    if kind == "sort":
        placements = answer.get("placements")
        ids = {item["id"] for item in activity["items"]}
        buckets = {bucket["id"] for bucket in activity["buckets"]}
        if not isinstance(placements, dict) or set(placements) != ids \
                or not all(v in buckets for v in placements.values()):
            raise AnswerError("placements must put every item in a bucket")
        return all(placements[item["id"]] == item["bucket"] for item in activity["items"]), \
            {"placements": placements}
    if kind == "rule_lab":
        predictions = answer.get("cases")
        keys = {case_key(case) for case in activity["cases"]}
        if not isinstance(predictions, dict) or set(predictions) != keys:
            raise AnswerError("cases must cover every sample and rule")
        cleaned = {}
        for key, value in predictions.items():
            verdict = normal_verdict(value)
            if verdict is None:
                raise AnswerError("every prediction must be pass or fail")
            cleaned[key] = verdict
        passed = all(cleaned[case_key(c)] == normal_verdict(c["expected"]) for c in activity["cases"])
        return passed, {"cases": cleaned}
    if kind == "reflection":
        text = answer.get("text")
        if not isinstance(text, str):
            raise AnswerError("the reflection must be text")
        return word_count(text) >= activity["min_words"], {"text": text}
    raise AnswerError("this activity is not graded here")


def grade_choice(item, answer):
    option_id = answer.get("option")
    option = next((o for o in item["options"] if o["id"] == option_id), None)
    if option is None:
        raise AnswerError("the option is not one of this question's options")
    return bool(option["correct"]), {"option": option_id}


def rule_is_sample_text(activity, text):
    """Would running this text reveal a case's expected verdict?"""
    wanted = " ".join(text.split()).casefold()
    return any(" ".join(s["text"].split()).casefold() == wanted for s in activity["samples"])


# --- views with the answers removed ----------------------------------------


def _shuffled(seed, context, items):
    def sort_key(item):
        return hashlib.sha256(f"{seed}:{context}:{item['id']}".encode("utf-8")).hexdigest()

    return sorted(items, key=sort_key)


def _shuffled_order(seed, context, items):
    """Shuffle an order activity so the listed order is never already the answer."""
    result = _shuffled(seed, context, items)
    if [item["id"] for item in result] == [item["id"] for item in items]:
        result = result[1:] + result[:1]
    return result


def public_options(item, seed, context):
    return [{"id": option["id"], "text": option["text"]} for option in _shuffled(seed, context, item["options"])]


def choice_result(item, entry):
    last = (entry or {}).get("last")
    if not last:
        return None
    option = next((o for o in item["options"] if o["id"] == last.get("option")), None)
    if option is None:
        return None
    result = {"passed": bool(entry.get("passed")), "chosen": option["id"], "feedback": option["feedback"]}
    if result["passed"]:
        result["explanations"] = [{"id": o["id"], "correct": bool(o["correct"]), "feedback": o["feedback"]}
                                  for o in item["options"]]
    return result


def public_choice(item, seed, context, entry):
    return {"prompt": item["prompt"], "options": public_options(item, seed, context),
            "result": choice_result(item, entry)}


def _order_result(activity, entry):
    last = (entry or {}).get("last")
    if not last:
        return None
    passed = bool(entry.get("passed"))
    return {"passed": passed, "submitted": last.get("order", []),
            "feedback": activity["feedback_right"] if passed else activity["feedback_wrong"]}


def _sort_result(activity, entry):
    last = (entry or {}).get("last")
    if not last:
        return None
    placements = last.get("placements", {})
    right = sum(1 for item in activity["items"] if placements.get(item["id"]) == item["bucket"])
    result = {"passed": bool(entry.get("passed")), "placements": placements,
              "right": right, "total": len(activity["items"])}
    if result["passed"]:
        result["feedback"] = [{"item": item["id"], "feedback": item["feedback"]} for item in activity["items"]]
    elif activity.get("reveal"):
        # A prediction with a reveal gives feedback for the items placed wrongly and for no other.
        result["feedback"] = [{"item": item["id"], "feedback": item["feedback"]} for item in activity["items"]
                              if placements.get(item["id"]) != item["bucket"]]
    return result


def _rule_result(activity, entry, reasons):
    last = (entry or {}).get("last")
    if not last:
        return None
    predictions = last.get("cases", {})
    samples = {sample["id"]: sample["text"] for sample in activity["samples"]}
    rules = {rule["id"]: rule for rule in activity["rules"]}
    right = sum(1 for c in activity["cases"] if predictions.get(case_key(c)) == normal_verdict(c["expected"]))
    result = {"passed": bool(entry.get("passed")), "predictions": predictions,
              "right": right, "total": len(activity["cases"])}
    if result["passed"]:
        details = []
        for case in activity["cases"]:
            actual = rule_result(rules[case["rule"]], samples[case["sample"]], reasons)
            details.append({"key": case_key(case), "verdict": actual["verdict"], "reason": actual["reason"]})
        result["details"] = details
    return result


def _reflection_result(activity, entry):
    last = (entry or {}).get("last")
    if last is None:
        return None
    return {"passed": bool(entry.get("passed")), "text": last.get("text", ""),
            "words": word_count(last.get("text", ""))}


def public_activity(lesson_id, activity, entry, seed, reasons):
    """An activity with its answers removed; the result of any attempt so far is included."""
    kind = activity["type"]
    context = f"{lesson_id}:{activity['id']}"
    view = {"id": activity["id"], "type": kind, "passed": bool((entry or {}).get("passed"))}
    if kind == "choice":
        view.update(public_choice(activity, seed, context, entry))
    elif kind == "order":
        view.update(prompt=activity["prompt"],
                    items=[{"id": i["id"], "text": i["text"]}
                           for i in _shuffled_order(seed, context, activity["items"])],
                    result=_order_result(activity, entry))
    elif kind == "sort":
        view.update(prompt=activity["prompt"],
                    buckets=[{"id": b["id"], "label": b["label"]} for b in activity["buckets"]],
                    items=[{"id": i["id"], "text": i["text"]} for i in _shuffled(seed, context, activity["items"])],
                    result=_sort_result(activity, entry))
        if activity.get("reveal") and view["passed"]:
            view["reveal"] = activity["reveal"]  # what a prediction was about, only once it is made
    elif kind == "rule_lab":
        cases = [{"key": case_key(c), "sample": c["sample"], "rule": c["rule"]} for c in activity["cases"]]
        view.update(prompt=activity["prompt"],
                    samples=[{"id": s["id"], "label": s["label"], "text": s["text"]} for s in activity["samples"]],
                    rules=[{"id": r["id"], "label": r["label"], **({"explain": r["explain"]} if r.get("explain") else {})}
                           for r in activity["rules"]],
                    cases=_shuffled(seed, context, [dict(c, id=c["key"]) for c in cases]),
                    result=_rule_result(activity, entry, reasons))
    elif kind == "reflection":
        view.update(prompt=activity["prompt"], min_words=activity["min_words"],
                    result=_reflection_result(activity, entry))
    return view


def file_names(activity):
    return [(entry.get("name") if isinstance(entry, dict) else entry) for entry in activity["files"]]


def public_retrieval(lesson_id, item, seed):
    context = f"review:{lesson_id}:{item['id']}"
    return {"prompt": item["prompt"], "options": public_options(item, seed, context)}
