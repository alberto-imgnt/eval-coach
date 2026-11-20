"""Mock course for the UI tests: a small stand-in for the lesson side of the backend.

It keeps the correct answers on the "server" side and returns views with the answers
removed, like the real engine does. Dev-only, standard library only.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "app" / "eval_coach" / "content"
LESSON_UI = json.loads((CONTENT_ROOT / "lesson-ui.json").read_text(encoding="utf-8"))
GLOSSARY = json.loads((CONTENT_ROOT / "glossary.json").read_text(encoding="utf-8"))
UI = LESSON_UI["ui"]
REASONS = LESSON_UI["rule_reasons"]
ERRORS = LESSON_UI["errors"]
SEED = "mock-seed"
HOOK_LINE = ("Read update.txt and requirements.md. Score the update from 1 to 10 against the requirements, "
             "say pass or fail, and give one sentence of reasoning. Save only that to output.txt. Do nothing else.")
DEMO_LINE = "Read skills/build-eval-script/SKILL.md and follow it in build mode on test-cases.md."

KIT_FILES = {
    "kit:lessons/hook/requirements.md": "Requirements\n- under 150 words\n- <b>group by client</b>, not by day\n<script>window.__xss = 3</script>\n",
    "kit:skills/build-eval-script/SKILL.md": "# Build eval script\nRead test-cases.md and write check.py.\n",
}


def opt(oid, text, correct, feedback):
    return {"id": oid, "text": text, "correct": correct, "feedback": feedback}


def choice(cid, prompt, options):
    return {"id": cid, "type": "choice", "prompt": prompt, "options": options}


def step_question(step):
    return choice(f"sc-{step}", "What made your five answers fair to score?", [
        opt("a", "Each came from a new chat that never saw your tests", True, "Right. Each run was blind and separate."),
        opt("b", "Each came from a retry that replaced a weaker answer", False, "A retry hides the variation you are measuring."),
        opt("c", "Each came from one chat that remembered earlier answers", False, "A shared chat carries earlier answers forward."),
    ])


LESSONS = {
    "mission": {
        "title": "Your mission",
        "win": "You know what you will leave with.",
        "minutes": 3,
        "skippable": False,
        "body": "You will build a **checker** you can trust.\n\n- Short steps\n- Plain language\n\n```you-are-here\ndone | 1 | Structured prompting | I tell the AI clearly what I want.\ndone | 2 | Defining evaluation criteria | I captured what a good answer looks like.\nhere | 3 | Running evals and baseline | A computer applies my rules every time.\nnext | 4 | Iterating with evaluation-driven development | The score proves whether a change helped.\nnext | 5 | Load-bearing audit and packaging | I know which rules carry the weight.\nnext | 6 | Your own task | I apply all of this to my own work.\n```\n\n<script>window.__xss = 4</script>",
        "activities": [
            choice("m-choice", "Which describes a checker you can trust?", [
                opt("a", "Different verdicts each run", False, "A checker that changes its mind cannot be trusted."),
                opt("b", "The same verdict always", True, "Right. The same input gives the same verdict."),
                opt("c", "Verdicts that follow mood", False, "Mood is what a checker must not depend on."),
            ]),
            {"id": "m-sort", "type": "sort", "prompt": "Who does each job?",
             "buckets": [{"id": "gen", "label": "Generator"}, {"id": "chk", "label": "Checker"}],
             "items": [
                 {"id": "i1", "text": "Writes the answer", "bucket": "gen", "feedback": "The generator writes the answer."},
                 {"id": "i2", "text": "Applies the threshold", "bucket": "chk", "feedback": "The checker applies the threshold."},
                 {"id": "i3", "text": "Varies run to run", "bucket": "gen", "feedback": "Only the generator varies."},
             ]},
        ],
        "sources": [{"label": "The requirements file", "ref": "kit:lessons/hook/requirements.md"}],
        "primary_source": {"label": "The checker skill", "ref": "kit:skills/build-eval-script/SKILL.md", "why": "Read how the checker gets built."},
        "related": {"lessons": ["several-runs"], "glossary": ["Checker"]},
    },
    "hook": {
        "title": "One update, three grades",
        "win": "You have three grades to compare.",
        "minutes": 6,
        "skippable": False,
        "body": "Grade the same update three times.",
        "activities": [
            {"id": "hook-compare", "type": "cli_compare", "runs": 3, "line": HOOK_LINE, "files": ["update.txt", "requirements.md"],
             "question": choice("hook-q", "Which conclusion holds whatever your results show?", [
                 opt("a", "Three matching scores prove it", False, "Three agreeing runs are a small sample."),
                 opt("b", "One grade cannot promise next", True, "Right. A checker gives the same verdict every time."),
                 opt("c", "Averaging gives the true grade", False, "An average of opinions is still an opinion."),
             ])},
        ],
        "sources": [{"label": "Requirements", "ref": "kit:lessons/hook/requirements.md"}],
        "primary_source": {"label": "An outside article", "ref": "https://example.com/article", "why": "It explains grading drift."},
        "related": {"lessons": [], "glossary": []},
    },
    "several-runs": {
        "title": "Why several answers",
        "win": "You can explain why one answer is not enough.",
        "minutes": 4,
        "skippable": True,
        "body": "Ask for several answers, each from a new chat, then compare them.",
        "activities": [
            {"id": "runs-order", "type": "order", "prompt": "Put the work in order.",
             "items": [{"id": "a", "text": "Prompt"}, {"id": "b", "text": "Answer"}, {"id": "c", "text": "File"},
                       {"id": "d", "text": "Checker"}, {"id": "e", "text": "Verdict"}],
             "feedback_right": "That is the order.", "feedback_wrong": "Not the right order yet."},
        ],
        "sources": [{"label": "Requirements", "ref": "kit:lessons/hook/requirements.md"}],
        "primary_source": {"label": "The checker skill", "ref": "kit:skills/build-eval-script/SKILL.md", "why": "Read it."},
        "related": {"lessons": [], "glossary": ["Checker"]},
        "retrieval": [
            choice("r-runs-1", "What comes right before the verdict?", [
                opt("a", "The prompt", False, "The prompt starts the work."),
                opt("b", "The checker", True, "Right. The checker produces the verdict."),
            ]),
            choice("r-runs-2", "What does the checker read?", [
                opt("a", "The saved file", True, "Right. It reads the saved answer."),
                opt("b", "Your thoughts", False, "It reads files only."),
            ]),
        ],
    },
    "rules": {
        "title": "From threshold to rule",
        "win": "You can predict what a rule does.",
        "minutes": 8,
        "skippable": False,
        "body": "A rule gives the same verdict every time.",
        "activities": [
            {"id": "rules-lab", "type": "rule_lab", "prompt": "Predict each verdict.",
             "samples": [
                 {"id": "s1", "label": "Short update", "text": "Shipped the report. Blocker: none."},
                 {"id": "s2", "label": "Long update", "text": "We shipped the weekly report to every client today and everything went smoothly with no issues at all"},
             ],
             "rules": [
                 {"id": "r1", "label": "Under 10 words", "explain": "Passes with fewer than 10 words.", "kind": "word_count_under", "params": {"limit": 10}},
                 {"id": "r2", "label": "Mentions the blocker", "kind": "all_present", "params": {"terms": ["blocker"]}},
             ],
             "cases": [
                 {"sample": "s1", "rule": "r1", "expected": "pass"}, {"sample": "s1", "rule": "r2", "expected": "pass"},
                 {"sample": "s2", "rule": "r1", "expected": "fail"}, {"sample": "s2", "rule": "r2", "expected": "fail"},
             ]},
            {"id": "rules-refl", "type": "reflection", "prompt": "Which threshold in your prompt is hardest to check?", "min_words": 5},
            {"id": "rules-demo", "type": "cli_demo", "line": DEMO_LINE, "files": ["test-cases.md", "output.txt"], "run_args": ["output.txt"]},
        ],
        "sources": [{"label": "The checker skill", "ref": "kit:skills/build-eval-script/SKILL.md"}],
        "primary_source": {"label": "The checker skill", "ref": "kit:skills/build-eval-script/SKILL.md", "why": "Read how rules are written."},
        "related": {"lessons": ["several-runs", "hook"], "glossary": ["Checker", "Deterministic"]},
    },
    "trust": {
        "title": "Test the checker before you trust it",
        "win": "You can say why a checker needs testing.",
        "minutes": 5,
        "skippable": False,
        "body": "A checker can be wrong. Test it on answers you already know.",
        "activities": [
            choice("trust-why", "Why test a checker before you rely on it?", [
                opt("a", "It may pass answers it should fail", True, "Right. A checker can be wrong too."),
                opt("b", "It always works the first time", False, "A new checker has not earned trust yet."),
            ]),
        ],
        "sources": [], "primary_source": None,
        "related": {"lessons": [], "glossary": ["Checker"]},
    },
    "surprise": {
        "title": "Reading a surprise",
        "win": "You can tell what a surprise is teaching you.",
        "minutes": 4,
        "skippable": False,
        "body": "A result you did not predict is the most useful one.",
        "activities": [
            choice("surprise-why", "What do you do with a result you did not predict?", [
                opt("a", "Find out why it differed", True, "Right. The difference is the information."),
                opt("b", "Ignore it", False, "Ignoring it hides what you could learn."),
            ]),
        ],
        "sources": [], "primary_source": None,
        "related": {"lessons": [], "glossary": []},
    },
    "baseline-why": {
        "title": "Your baseline, and what comes next",
        "win": "You can say what a baseline is for.",
        "minutes": 6,
        "skippable": False,
        "body": "Your baseline is the score you compare every later change with.",
        "activities": [
            choice("baseline-total", "What is a baseline for?", [
                opt("a", "Comparing later scores with it", True, "Right. It is the starting point."),
                opt("b", "Replacing your checker", False, "A baseline does not replace anything."),
            ]),
        ],
        "sources": [], "primary_source": None,
        "related": {"lessons": [], "glossary": ["Baseline (Iteration 0)"]},
    },
}
LESSON_ORDER = ["mission", "hook", "several-runs", "rules", "trust", "surprise", "baseline-why"]
# The course in the real order: lessons with their steps between them.
SEQUENCE = [
    ("lesson", "mission"), ("lesson", "hook"), ("lesson", "several-runs"), ("steps", ["generate"]),
    ("lesson", "rules"), ("steps", ["build"]),
    ("lesson", "trust"), ("steps", ["fixtures", "fixtures-config", "readback", "predict", "key"]),
    ("lesson", "surprise"), ("steps", ["run", "fix"]),
    ("lesson", "baseline-why"), ("steps", ["baseline"]),
]
PLACEMENT = [
    choice("p-runs", "Which comes first in the work?", [
        opt("a", "The checker", False, "The checker comes later."),
        opt("b", "The prompt", True, "Right. The prompt comes first."),
    ]) | {"lesson": "several-runs"},
    choice("p-hook", "Can a grader change its mind?", [
        opt("a", "Yes it can", True, "Right. It can change between runs."),
        opt("b", "No never", False, "It can and does."),
    ]) | {"lesson": "hook"},
]
REVIEW_POOL = [
    {"key": "several-runs:r-runs-1", "lesson": "several-runs", "lesson_title": "Why several answers"},
    {"key": "several-runs:r-runs-2", "lesson": "several-runs", "lesson_title": "Why several answers"},
    {"key": "rules:r-rules-1", "lesson": "rules", "lesson_title": "From threshold to rule"},
]
REVIEW_QUESTIONS = {
    "several-runs:r-runs-1": LESSONS["several-runs"]["retrieval"][0],
    "several-runs:r-runs-2": LESSONS["several-runs"]["retrieval"][1],
    "rules:r-rules-1": choice("r-rules-1", "Same rule, same text: what verdict?", [
        opt("a", "The same one", True, "Right. A rule is deterministic."),
        opt("b", "A random one", False, "Rules never use chance."),
    ]),
}
COURSE_STEPS = [step for kind, ids in SEQUENCE if kind == "steps" for step in ids]
# The steps of the current track. The mock server points this at its own step list, which changes with the track.
ACTIVE_STEPS = [s for s in COURSE_STEPS if s != "fixtures-config"]


class MockError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def shuffled(context, items):
    return sorted(items, key=lambda i: hashlib.sha256(f"{SEED}:{context}:{i['id']}".encode()).hexdigest())


def fmt(text, **vars_):
    return text.format(**vars_)


def evaluate(rule, text):
    kind, params = rule["kind"], rule["params"]
    if kind == "word_count_under":
        count = len(text.split())
        return count < params["limit"], {"count": count, "limit": params["limit"]}
    if kind == "all_present":
        missing = [t for t in params["terms"] if t.lower() not in text.lower()]
        return not missing, {"missing": ", ".join(missing), "terms": ", ".join(params["terms"])}
    raise MockError("bad_answer", ERRORS["bad_answer"])


def rule_result(rule, text):
    passed, facts = evaluate(rule, text)
    return {"verdict": "pass" if passed else "fail", "reason": REASONS[rule["kind"]]["pass" if passed else "fail"].format(**facts)}


def case_key(case):
    return f"{case['sample']}|{case['rule']}"


class CourseState:
    def __init__(self):
        self.status = {}
        self.acts = {}
        self.step_entries = {}
        self.placement = {}
        self.hook_runs = {1: "", 2: "", 3: ""}
        self.demo = {"checker": False, "runs": []}
        self.cli_key = None
        self.sent = False
        self.review_postponed = False
        self.review_sitting = []
        self.review_answers = []
        self.review_log = []

    # ---- ordering ------------------------------------------------------
    def walk(self, passed, step_status):
        """Every course item as (kind, id, status), like the real engine. Only the steps of the current track appear."""
        wanted = set(ACTIVE_STEPS)
        out, blocked = [], False
        for kind, entry in SEQUENCE:
            if kind == "lesson":
                lid = entry
                stored = self.status.get(lid)
                if stored in ("done", "skipped"):
                    out.append(("lesson", lid, stored))
                    continue
                allowed = True  # the lesson that is next to do opens, with or without setup
                out.append(("lesson", lid, "active" if allowed and not blocked else "locked"))
                blocked = True
                continue
            for step in entry:
                if step not in wanted:
                    continue
                status = step_status(step)
                if status == "done":
                    out.append(("step", step, "done"))
                    continue
                out.append(("step", step, "active" if not blocked and status == "active" else "locked"))
                blocked = True
        return out

    def lesson_status(self, lid, passed, step_status):
        return next(s for k, i, s in self.walk(passed, step_status) if k == "lesson" and i == lid)

    # ---- views ---------------------------------------------------------
    def entry(self, lid, aid):
        return self.acts.setdefault((lid, aid), {"passed": False, "attempts": 0, "last": None})

    def all_passed(self, lid):
        """Only exercises hold Continue back. Every question, sort, lab and reflection is optional."""
        for activity in LESSONS[lid]["activities"]:
            if activity["type"] == "cli_demo" and not self.entry(lid, activity["id"])["passed"]:
                return False
            if activity["type"] == "cli_compare" and not all(self.hook_runs[n].strip() for n in self.hook_runs):
                return False
        return True

    def placement_passed(self, item_id):
        return self.placement.get(item_id, {}).get("correct") is True

    def choice_view(self, item, entry, context):
        options = [{"id": o["id"], "text": o["text"]} for o in shuffled(context, item["options"])]
        last = (entry or {}).get("last")
        result = None
        if last:
            chosen = next(o for o in item["options"] if o["id"] == last["option"])
            result = {"passed": bool(entry["passed"]), "chosen": chosen["id"], "feedback": chosen["feedback"]}
            if result["passed"]:
                result["explanations"] = [{"id": o["id"], "correct": o["correct"], "feedback": o["feedback"]} for o in item["options"]]
        return {"prompt": item["prompt"], "options": options, "result": result}

    def activity_view(self, lid, activity):
        aid, kind = activity["id"], activity["type"]
        entry = self.entry(lid, aid)
        last = entry["last"]
        context = f"{lid}:{aid}"
        view = {"id": aid, "type": kind, "passed": bool(entry["passed"])}
        if kind == "choice":
            view.update(self.choice_view(activity, entry if last else None, context))
        elif kind == "order":
            items = [{"id": i["id"], "text": i["text"]} for i in shuffled(context, activity["items"])]
            if [i["id"] for i in items] == [i["id"] for i in activity["items"]]:
                items = items[1:] + items[:1]
            result = None
            if last:
                result = {"passed": entry["passed"], "submitted": last["order"],
                          "feedback": activity["feedback_right"] if entry["passed"] else activity["feedback_wrong"]}
            view.update(prompt=activity["prompt"], items=items, result=result)
        elif kind == "sort":
            result = None
            if last:
                right = sum(1 for i in activity["items"] if last["placements"].get(i["id"]) == i["bucket"])
                result = {"passed": entry["passed"], "placements": last["placements"], "right": right, "total": len(activity["items"])}
                if entry["passed"]:
                    result["feedback"] = [{"item": i["id"], "feedback": i["feedback"]} for i in activity["items"]]
            view.update(prompt=activity["prompt"], buckets=[{"id": b["id"], "label": b["label"]} for b in activity["buckets"]],
                        items=[{"id": i["id"], "text": i["text"]} for i in shuffled(context, activity["items"])], result=result)
        elif kind == "rule_lab":
            result = None
            if last:
                right = sum(1 for c in activity["cases"] if last["cases"].get(case_key(c)) == c["expected"])
                result = {"passed": entry["passed"], "predictions": last["cases"], "right": right, "total": len(activity["cases"])}
                if entry["passed"]:
                    rules = {r["id"]: r for r in activity["rules"]}
                    texts = {s["id"]: s["text"] for s in activity["samples"]}
                    result["details"] = [dict(key=case_key(c), **rule_result(rules[c["rule"]], texts[c["sample"]])) for c in activity["cases"]]
            cases = [{"key": case_key(c), "sample": c["sample"], "rule": c["rule"], "id": case_key(c)} for c in activity["cases"]]
            view.update(prompt=activity["prompt"], samples=copy.deepcopy(activity["samples"]),
                        rules=[{"id": r["id"], "label": r["label"], **({"explain": r["explain"]} if "explain" in r else {})}
                               for r in activity["rules"]],
                        cases=shuffled(context, cases), result=result)
        elif kind == "reflection":
            result = None
            if last is not None:
                from_text = last["text"]
                result = {"passed": entry["passed"], "text": from_text, "words": len(from_text.split())}
            view.update(prompt=activity["prompt"], min_words=activity["min_words"], result=result)
        elif kind == "cli_compare":
            outputs = [{"n": n, "done": bool(self.hook_runs[n].strip()), "text": self.hook_runs[n]} for n in sorted(self.hook_runs)]
            started = self.cli_key == f"lesson:{lid}:{aid}"
            view.update(runs=activity["runs"], files=list(activity["files"]),
                        cli={"line": activity["line"], "folder_label": "A clean folder that holds only the update and its requirements",
                             "started": started, "sent": started and self.sent},
                        outputs=outputs, all_saved=all(o["done"] for o in outputs),
                        question=self.choice_view(activity["question"], entry if last else None, f"{context}:question"))
        elif kind == "cli_demo":
            started = self.cli_key == f"lesson:{lid}:{aid}"
            runs = self.demo["runs"]
            view.update(files=list(activity["files"]),
                        cli={"line": activity["line"], "folder_label": "A demo folder, separate from your project",
                             "started": started, "sent": started and self.sent},
                        checker_exists=self.demo["checker"], scan=[], runs=copy.deepcopy(runs),
                        identical=(runs[0] == runs[1]) if len(runs) == 2 else None)
        return view

    def view(self, lid, passed, step_status):
        if lid not in LESSONS:
            raise MockError("unknown_lesson", ERRORS["unknown_lesson"])
        lesson = LESSONS[lid]
        status = self.lesson_status(lid, passed, step_status)
        if status == "locked":
            raise MockError("lesson_locked", UI["locked_tip"])  # a locked lesson is refused: no text is returned
        placement_done = {p["lesson"] for p in PLACEMENT if self.placement_passed(p["id"])}
        related = lesson.get("related") or {"lessons": [], "glossary": []}
        result = {
            "id": lid, "title": lesson["title"], "win": lesson["win"], "minutes": lesson["minutes"],
            "skippable": lesson["skippable"], "status": status, "mission": "Leave with a checker you can trust.",
            "body": lesson["body"], "activities": [self.activity_view(lid, a) for a in lesson["activities"]],
            "sources": copy.deepcopy(lesson["sources"]), "primary_source": copy.deepcopy(lesson["primary_source"]),
            "related": {"lessons": [{"id": i, "title": LESSONS[i]["title"],
                                     "open": self.lesson_status(i, passed, step_status) != "locked"} for i in related["lessons"]],
                        "glossary": list(related["glossary"])},
            "can_complete": status == "active" and self.all_passed(lid),
            "can_skip": status == "active" and lesson["skippable"] and lid in placement_done,
            "part_skipped": False,
        }
        if lid == "mission":
            result["placement"] = self.placement_view()
        return result

    def placement_view(self):
        views = []
        for item in PLACEMENT:
            lesson = LESSONS[item["lesson"]]
            stored = self.placement.get(item["id"])
            result = None
            if stored:
                option = next(o for o in item["options"] if o["id"] == stored["option"])
                result = {"passed": stored["correct"], "chosen": option["id"], "feedback": option["feedback"],
                          "offer_skip": stored["correct"] and lesson["skippable"], "decision": stored.get("decision")}
            views.append({"id": item["id"], "prompt": item["prompt"], "lesson": item["lesson"], "lesson_title": lesson["title"],
                          "options": [{"id": o["id"], "text": o["text"]} for o in shuffled(f"placement:{item['id']}", item["options"])],
                          "result": result})
        return views

    # ---- actions ---------------------------------------------------------
    def require_active(self, lid, passed, step_status):
        if lid not in LESSONS:
            raise MockError("unknown_lesson", ERRORS["unknown_lesson"])
        status = self.lesson_status(lid, passed, step_status)
        if status == "locked":
            raise MockError("lesson_locked", UI["locked_tip"])
        if status in ("done", "skipped"):
            raise MockError("lesson_done", ERRORS["lesson_finished"])
        return LESSONS[lid]

    def answer(self, lid, aid, answer, passed, step_status):
        lesson = self.require_active(lid, passed, step_status)
        activity = next(a for a in lesson["activities"] if a["id"] == aid)
        entry = self.entry(lid, aid)
        kind = activity["type"]
        if kind == "cli_demo":
            return self.demo_run(activity, entry)
        if kind == "cli_compare":
            if not all(self.hook_runs[n].strip() for n in self.hook_runs):
                raise MockError("runs_missing", ERRORS["runs_missing"])
            ok, last = self.grade_choice(activity["question"], answer)
        elif kind == "choice":
            ok, last = self.grade_choice(activity, answer)
        elif kind == "order":
            order = answer.get("order")
            ids = [i["id"] for i in activity["items"]]
            if sorted(order or []) != sorted(ids):
                raise MockError("bad_answer", ERRORS["bad_answer"])
            ok, last = order == ids, {"order": order}
        elif kind == "sort":
            placements = answer.get("placements") or {}
            if set(placements) != {i["id"] for i in activity["items"]}:
                raise MockError("bad_answer", ERRORS["bad_answer"])
            ok, last = all(placements[i["id"]] == i["bucket"] for i in activity["items"]), {"placements": placements}
        elif kind == "rule_lab":
            cases = answer.get("cases") or {}
            if set(cases) != {case_key(c) for c in activity["cases"]}:
                raise MockError("bad_answer", ERRORS["bad_answer"])
            ok, last = all(cases[case_key(c)] == c["expected"] for c in activity["cases"]), {"cases": cases}
        elif kind == "reflection":
            text = answer.get("text")
            if not isinstance(text, str):
                raise MockError("bad_answer", ERRORS["bad_answer"])
            ok, last = len(text.split()) >= activity["min_words"], {"text": text}
        else:
            raise MockError("bad_answer", ERRORS["bad_answer"])
        if entry["passed"] and kind != "reflection":
            return {"passed": True, "lesson": self.view(lid, passed, step_status)}
        if not entry["passed"]:
            entry["attempts"] += 1
        entry["last"] = last
        entry["passed"] = ok
        return {"passed": ok, "lesson": self.view(lid, passed, step_status)}

    @staticmethod
    def grade_choice(item, answer):
        option = next((o for o in item["options"] if o["id"] == answer.get("option")), None)
        if option is None:
            raise MockError("bad_answer", ERRORS["bad_answer"])
        return bool(option["correct"]), {"option": option["id"]}

    def step_question_view(self, step):
        item = step_question(step)
        entry = self.step_entries.get(step)
        view = self.choice_view(item, entry, f"step-question:{step}")
        view.update(id=item["id"], passed=bool(entry and entry["passed"]))
        return view

    def step_question_answer(self, step, option):
        item = step_question(step)
        ok, last = self.grade_choice(item, {"option": option})
        entry = self.step_entries.setdefault(step, {"passed": False, "attempts": 0, "last": None})
        if not entry["passed"]:
            entry["attempts"] += 1
            entry["last"] = last
            entry["passed"] = ok
        return {"passed": entry["passed"], "question": self.step_question_view(step)}

    def demo_run(self, activity, entry):
        if not self.demo["checker"]:
            raise MockError("no_checker", ERRORS["no_checker"])
        rows = [{"id": "C1", "name": "Length", "verdict": "P", "reason": "58 words"}, {"id": "C2", "name": "Order number", "verdict": "F", "reason": "missing"}]
        run = {"ok": True, "exit_code": 1, "error": None, "raw": "", "files": [{"file": "output.txt", "rows": rows}]}
        self.demo["runs"] = [copy.deepcopy(run), copy.deepcopy(run)]
        entry["passed"] = True
        entry["last"] = {"run": True}
        return {"passed": True}

    def rule_run(self, lid, aid, rule_id, text, passed, step_status):
        if lid not in LESSONS:
            raise MockError("unknown_lesson", ERRORS["unknown_lesson"])
        if self.lesson_status(lid, passed, step_status) == "locked":
            raise MockError("lesson_locked", UI["locked_tip"])
        activity = next(a for a in LESSONS[lid]["activities"] if a["id"] == aid)
        if not isinstance(text, str) or not text.strip():
            raise MockError("bad_answer", ERRORS["bad_rule_text"])
        rule = next((r for r in activity["rules"] if r["id"] == rule_id), None)
        if rule is None:
            raise MockError("unknown_rule", ERRORS["unknown_rule"])
        wanted = " ".join(text.split()).casefold()
        if not self.entry(lid, aid)["passed"] and any(" ".join(s["text"].split()).casefold() == wanted for s in activity["samples"]):
            raise MockError("sample_before_answer", ERRORS["sample_before_answer"])
        return rule_result(rule, text)

    def complete(self, lid, passed, step_status):
        self.require_active(lid, passed, step_status)
        if not self.all_passed(lid):
            raise MockError("activities_incomplete", ERRORS["activities_incomplete"])
        self.status[lid] = "done"

    def skip(self, lid, passed, step_status):
        lesson = self.require_active(lid, passed, step_status)
        if not lesson["skippable"]:
            raise MockError("cannot_skip", ERRORS["not_skippable"])
        if not any(p["lesson"] == lid and self.placement_passed(p["id"]) for p in PLACEMENT):
            raise MockError("cannot_skip", ERRORS["cannot_skip"])
        self.status[lid] = "skipped"

    def placement_answer(self, item_id, option, accept_skip, passed, step_status):
        item = next((p for p in PLACEMENT if p["id"] == item_id), None)
        if item is None:
            raise MockError("unknown_placement", ERRORS["unknown_placement"])
        if self.lesson_status("mission", passed, step_status) != "active":
            raise MockError("placement_closed", ERRORS["placement_closed"])
        lesson = LESSONS[item["lesson"]]
        stored = self.placement.get(item_id)
        if accept_skip is not None:
            if not (stored and stored["correct"] and lesson["skippable"]):
                raise MockError("no_skip_offer", ERRORS["no_skip_offer"])
            stored["decision"] = "accepted" if accept_skip else "declined"
            if accept_skip:
                self.status[item["lesson"]] = "skipped"
            return {"lesson": self.view("mission", passed, step_status)}
        if stored is not None:
            raise MockError("placement_answered", ERRORS["placement_answered"])
        correct, _ = self.grade_choice(item, {"option": option})
        self.placement[item_id] = {"correct": correct, "option": option, "decision": None}
        return {"lesson": self.view("mission", passed, step_status)}

    # ---- kit and review --------------------------------------------------------
    @staticmethod
    def kit(ref):
        if ref not in KIT_FILES:
            raise MockError("bad_ref", ERRORS["bad_ref"])
        return {"kit": {"ref": ref, "name": ref.rsplit("/", 1)[-1], "text": KIT_FILES[ref]}}

    def set_review(self, keys):
        self.review_sitting = list(keys)
        self.review_postponed = False

    def review_summary(self):
        if self.review_postponed:
            return {"due": 0, "postponed": True}
        return {"due": len(self.review_sitting), "postponed": False}

    def review_get(self):
        if self.review_postponed:
            return {"review": {"items": [], "postponed": True}}
        items = []
        for key in self.review_sitting:
            meta = next(m for m in REVIEW_POOL if m["key"] == key)
            question = REVIEW_QUESTIONS[key]
            items.append({"item": key, "lesson": meta["lesson"], "lesson_title": meta["lesson_title"], "prompt": question["prompt"],
                          "options": [{"id": o["id"], "text": o["text"]} for o in shuffled(f"review:{key}", question["options"])]})
        return {"review": {"items": items, "postponed": False}}

    def review_answer(self, key, option):
        if key not in self.review_sitting:
            raise MockError("review_unknown", ERRORS["review_unknown"])
        correct, _ = self.grade_choice(REVIEW_QUESTIONS[key], {"option": option})
        feedback = next(o["feedback"] for o in REVIEW_QUESTIONS[key]["options"] if o["id"] == option)
        self.review_sitting.remove(key)
        self.review_log.append({"item": key, "option": option, "passed": correct})
        return {"passed": correct, "feedback": feedback}

    def review_postpone(self):
        self.review_postponed = True
        self.review_sitting = []
