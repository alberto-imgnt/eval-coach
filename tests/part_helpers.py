"""A synthetic second Part for tests: two lessons, one step and one step kind, registered only inside a with block.

No fake content ships. The lessons are copies of bundled ones under new ids, served through a patched
resources.read_text, and the Part is added to the registry by state.register_part.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from unittest import mock

import course_helpers as ch

from eval_coach import resources, state

LESSONS_FILE = "content/test-part-lessons.json"
STEPS_FILE = "content/test-part-steps.json"
KIND = "test-kind"
INTRO, CHOICE, STEP = "p9-intro", "p9-choice", "p9-step"


def new_steps():
    return {STEP: {"last_check": None, "checklist": {}}}


def make_part(part_id="part-9", progress_key="part-9"):
    return state.Part(part_id, 9, INTRO, (("lesson", INTRO), ("lesson", CHOICE), ("step", STEP)),
                      LESSONS_FILE, STEPS_FILE, progress_key=progress_key, new_steps=new_steps)


def lessons_data():
    base = ch.bundled_data()
    by_id = {lesson["id"]: lesson for lesson in base["lessons"]}
    intro, choice = ch.clone(by_id["mission"]), ch.clone(by_id["trust"])
    intro["id"], choice["id"] = INTRO, CHOICE
    for lesson in (intro, choice):
        lesson.pop("related", None)
    check = ch.clone(next(c for c in base["step_checks"] if c["step"] == "generate"))
    check.update(id="p9-sc", step=STEP)
    return {"version": 1, "mission": "The test Part's mission.", "step_checks": [check], "placement": [],
            "lessons": [intro, choice]}


def ui_key():
    """An interface word the test Part overrides."""
    return next(iter(json.loads(resources.read_text("content/lesson-ui.json"))["ui"]))


def steps_data():
    text = ch.clone(json.loads(resources.read_text("content/steps.json"))["steps"]["key"])
    text.pop("tracks", None)
    text["kind"] = KIND
    return {"steps": {STEP: text}, "ui": {ui_key(): "Words for the test Part"}}


class Handler:
    """The step kind of the synthetic Part. It records what the engine hands it."""

    def __init__(self):
        self.calls = []

    def check(self, engine, step):
        self.calls.append(("check", step))
        with engine._lock:
            engine._require_active(step)
            engine._step(step)["last_check"] = {"ok": True}
            engine._mark_done(step)
            engine._save()

    def detail(self, engine, step):
        return {"id": step, "title": engine._text(step)["title"], "status": engine._status(step), "handled": True}


@contextmanager
def synthetic_part(handler=None, register_kind=True, extra_parts=()):
    """Register the synthetic Part (and any `extra_parts`, served the same content) for the length of the block."""
    handler = handler if handler is not None else Handler()
    lessons, steps = lessons_data(), steps_data()
    real = resources.read_text

    def read_text(relpath):
        if relpath == LESSONS_FILE:
            return json.dumps(lessons)
        if relpath == STEPS_FILE:
            return json.dumps(steps)
        return real(relpath)

    parts = (make_part(),) + tuple(extra_parts)
    patch = mock.patch.object(resources, "read_text", read_text)
    patch.start()
    registered = []
    try:
        for part in parts:
            cm = state.register_part(part)
            cm.__enter__()
            registered.append(cm)
        if register_kind:
            state.STEP_KINDS[KIND] = handler
        yield handler
    finally:
        state.STEP_KINDS.pop(KIND, None)
        for cm in reversed(registered):
            cm.__exit__(None, None, None)
        patch.stop()
