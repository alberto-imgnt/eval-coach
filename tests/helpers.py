"""Shared test helpers. Importing this puts app/ on sys.path."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

GOLDEN = ROOT / "tests" / "golden"
KIT = ROOT / "app" / "eval_coach" / "kit"
NORTHWIND = KIT / "northwind"
# The read-only source materials live outside the repository. Set EVAL_COACH_SOURCE_MATERIALS to that folder to run
# the tests that compare the bundled files with their source; without it those tests skip.
SOURCE = Path(os.environ.get("EVAL_COACH_SOURCE_MATERIALS") or ROOT / "tests" / ".source-materials-not-set")


def write_passed_preflight(home, track="script"):
    """Mark items 1-7 passed so step tests start from a machine that is already set up.

    Item 8 (project folder) passes when the test calls Engine.setup.
    """
    items = {item: {"status": "passed", "detail": "ok", "next": ""}
             for item in ("track", "python", "node", "promptfoo", "cli", "working_test")}
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    (home / "preflight.json").write_text(json.dumps(
        {"version": 1, "track": track, "cli_command": "", "test_passed_command": "fake", "recipe_ran": False,
         "ran_once": True, "items": items}), encoding="utf-8")


def write_recipes(home, command, models, recipe_id="mycli"):
    """A `<home>\\cli-recipes.json` override that gives `command` model data, so a stand-in can have a model option.

    Call it before the Engine is created: the recipes are read when the Engine starts.
    """
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    recipe = {"id": recipe_id, "name": "Test AI", "cli_command": command, "shell": "none", "command": "", "models": models}
    (home / "cli-recipes.json").write_text(json.dumps({"recipes": [recipe]}), encoding="utf-8")


ALIAS_MODELS = {"sonnet": {"label": "Sonnet", "launch": ["--model", "sonnet"]},
                "haiku": {"label": "Haiku", "launch": ["--model", "haiku"]}}


def wait_until(predicate, timeout=10.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


class FakeTerminal:
    """Stands in for TerminalManager in engine tests. Never launches anything."""

    def __init__(self):
        self.running = False
        self.label = ""
        self.owner = None
        self.releases = 0
        self.exit_code = None
        self.starts = []
        self.typed = []
        self.keystrokes = []
        self.sizes = []
        self.stops = 0
        self.state_events = 0

    def check_command(self, command, env=None):
        if command.startswith("no-such-cli"):
            raise FileNotFoundError("Could not find the command.")

    def argv_for(self, command, env=None):
        return command.split()

    def start(self, command, cwd, label, env=None, owner=None):
        self.running = True
        self.label = label
        self.owner = owner
        self.exit_code = None
        self.starts.append({"command": command, "cwd": cwd, "label": label, "env": env})

    def stop(self):
        self.stops += 1
        self.running = False

    def release(self):
        self.running = False
        self.label = ""
        self.owner = None
        self.exit_code = None
        self.releases += 1

    def write(self, data):
        self.keystrokes.append(data)

    def type_line(self, text):
        self.typed.append(text)

    def resize(self, cols, rows):
        self.sizes.append((cols, rows))

    def status(self):
        return {"running": self.running, "label": self.label, "exit_code": self.exit_code, "owner": self.owner}

    def publish_state(self):
        self.state_events += 1


class FakePty:
    """A pseudo console stand-in for real-TerminalManager tests."""

    created = []

    def __init__(self, argv, cwd=None, cols=120, rows=40, on_output=None, env=None):
        self.argv, self.cwd, self.cols, self.rows = argv, cwd, cols, rows
        self.env = env
        self.on_output = on_output
        self.exit_code = None
        self.written = []
        self.lines = []
        self.closed = False
        self._done = threading.Event()
        FakePty.created.append(self)

    def feed(self, data):
        self.on_output(data)

    def finish(self, code=0):
        self.exit_code = code
        self._done.set()

    def write(self, data):
        self.written.append(data)

    def type_line(self, text):
        self.lines.append(text)

    def resize(self, cols, rows):
        self.cols, self.rows = cols, rows

    def wait(self, timeout=None):
        self._done.wait(timeout)
        return self.exit_code

    def close(self):
        self.closed = True
        if self.exit_code is None:
            self.exit_code = 1
        self._done.set()
