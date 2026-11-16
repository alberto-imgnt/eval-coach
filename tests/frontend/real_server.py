"""The real app for the Part 1 and Part 2 interface tests (part1.spec.js, part2.spec.js).

It runs the real engine, the real course content and the real server, with a pseudo console that never starts a
program. A second port takes a few control calls so a test can set up where the participant is and play the part
of the CLI (write output.txt). Dev-only; it never touches the participant's own storage.

  python tests/frontend/real_server.py --port 38927 --token dev-token
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tests"))

import helpers  # noqa: E402
import course_helpers  # noqa: E402
from helpers import FakePty  # noqa: E402

from eval_coach import project, state  # noqa: E402
from eval_coach.engine import Engine  # noqa: E402
from eval_coach.lessons import load_bundled  # noqa: E402
from eval_coach.server import AppServer  # noqa: E402
from eval_coach.terminal import TerminalManager  # noqa: E402

COLD_PROMPT = "Please turn my notes into a Friday update for my lead."
LABELLED = "Role: a consultant\nTask: write the Friday update\nContext: I work on two clients\nConstraints: under 150 words"
ANSWER = "Update for Friday.\nNorthwind: reporting feature and demo.\nBlocker: test data access."
SECOND_ANSWER = "Teams message\nNorthwind: demo done.\nContoso: estimate reviewed.\nInternal: onboarding.\nBlocker: test data. Need: access."


def marks(yes):
    return {f"r{i}": "yes" if i <= yes else "no" for i in range(1, 6)}


# Part 2 (part2.spec.js): a worksheet that passes both worksheet steps, and what a participant would tick.
ROWS = [
    {"requirement": "It is under 150 words", "criterion": "The update is short", "type": "format",
     "threshold": "Word count under 100 passes"},
    {"requirement": "The work is grouped by client (Northwind, Contoso, Internal), not by day", "criterion": "Work is grouped by client",
     "type": "format", "threshold": "Passes if the labels Alpha and Beta both appear"},
    {"requirement": "It calls out the blocker and what you need to resolve it", "criterion": "The blocker is named", "type": "content",
     "threshold": 'Passes if the word "stuck" appears'},
]


class Session:
    """One engine over a throwaway home and project folder."""

    def __init__(self, scenario):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-part1-ui-"))
        self.home, self.project = self.tmp / "home", self.tmp / "project"
        if scenario != "no-setup":
            helpers.write_passed_preflight(self.home)
        self.terminal = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: c.split(),
                                        command_checker=lambda c, env=None: None)
        self.course = load_bundled()
        self.engine = Engine(self.home, self.terminal, poll_interval=0.05, lessons=self.course)
        self.paths = None
        if scenario != "no-setup":
            self.engine.setup({"project_path": str(self.project), "cli_command": "fake-cli", "starter": "northwind"})
            self.paths = project.Paths(self.home, self.project)

    def close(self):
        self.engine.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- moving the participant forward ----------------------------------------

    def reach(self, item, answer=ANSWER, second_answer=SECOND_ANSWER):
        """Finish everything in Part 1 before `item`, the way a participant would (the CLI's file is written directly)."""
        engine, paths = self.engine, self.paths
        for kind, name in state.PART_1.course:
            if name == item:
                return
            if kind == "lesson":
                engine.lesson_complete(name)
            elif name == "cold":
                engine.step_submit("cold", {"prompt": COLD_PROMPT, "model_name": "everyday-model"})
                paths.part1_output("cold").parent.mkdir(parents=True, exist_ok=True)
                paths.part1_output("cold").write_text(answer, encoding="utf-8")
                engine.step_check("cold")
            elif name == "score":
                engine.step_submit("score", {"answers": marks(2), "gap": "No ask for my lead", "in_prompt": "no"})
                engine.step_check("score")
            elif name == "rewrite":
                engine.step_submit("rewrite", {"prompt": LABELLED, "model_name": "everyday-model", "framework": "rtcc"})
                paths.part1_output("rewrite").write_text(second_answer, encoding="utf-8")
                engine.step_check("rewrite")
            elif name == "rescore":
                engine.step_submit("rescore", {"answers": marks(4), "reflections": {"added": "The reader.", "better": "More detail."}})
                engine.step_check("rescore")
            elif name == "own":
                return

    def reach_part_two(self, item):
        """Finish everything in Part 2 before `item` (every item when it is None), the way a participant would."""
        engine = self.engine
        for kind, name in state.PART_2.course:
            if name == item:
                return
            if kind == "lesson":
                for activity in self.course.get(name)["activities"]:
                    engine.lesson_answer(name, activity["id"], course_helpers.correct_answer(activity))
                engine.lesson_complete(name)
            elif name == "draft":
                engine.step_submit("draft", {"rows": [dict(row, threshold="") for row in ROWS],
                                             "checks": {"traces": True, "distinct": True}})
                engine.step_check("draft")
            elif name == "thresholds":
                engine.step_submit("thresholds", {"rows": ROWS, "checks": {"script_test": True}})
                engine.step_check("thresholds")
            elif name == "test-file":
                engine.step_submit("test-file", {"build": True})
                engine.step_check("test-file")

    def write_output(self, step, text):
        work = self.paths.part1_work(step)
        work.mkdir(parents=True, exist_ok=True)
        (work / "output.txt").write_text(text, encoding="utf-8")


class Control(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        session = self.server.holder
        if self.path == "/control/ping":
            self._json(200, {"ok": True})
        elif self.path == "/control/files":
            paths = session.current.paths
            listing = {"part1": sorted(p.name for p in paths.part1.iterdir()) if paths.part1.exists() else [],
                       "cold_work": sorted(p.name for p in paths.part1_work("cold").iterdir()) if paths.part1_work("cold").exists() else [],
                       "typed": [line for pty in FakePty.created for line in pty.lines]}
            self._json(200, listing)
        elif self.path.startswith("/control/read?"):
            name = self.path.split("=", 1)[1]
            target = session.current.paths.part1 / name
            self._json(200, {"text": target.read_text(encoding="utf-8") if target.is_file() else None})
        elif self.path.startswith("/control/read2?"):
            name = self.path.split("=", 1)[1]
            target = session.current.paths.part2 / name
            self._json(200, {"text": target.read_text(encoding="utf-8") if target.is_file() else None})
        elif self.path.startswith("/control/readroot?"):
            name = self.path.split("=", 1)[1]
            target = session.current.paths.project / name
            self._json(200, {"text": target.read_text(encoding="utf-8") if target.is_file() else None})
        elif self.path == "/control/files2":
            paths = session.current.paths
            self._json(200, {"part2": sorted(p.name for p in paths.part2.iterdir()) if paths.part2.exists() else [],
                             "started": len(FakePty.created)})
        else:
            self._json(404, {"ok": False})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        holder = self.server.holder
        with holder.lock:
            if self.path == "/control/reset":
                holder.reset(body.get("scenario", "ready"))
                if body.get("part1_reach"):
                    holder.current.reach(body["part1_reach"])
                if body.get("reach"):
                    holder.current.reach(body["reach"], **{k: body[k] for k in ("answer", "second_answer") if k in body})
                if "reach2" in body:
                    holder.current.reach_part_two(body["reach2"])
            elif self.path == "/control/reach":
                holder.current.reach(body["item"])
            elif self.path == "/control/reach2":
                holder.current.reach_part_two(body["item"])
            elif self.path == "/control/write2":
                target = holder.current.paths.part2 / body["name"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body["text"], encoding="utf-8")
            elif self.path == "/control/output":
                holder.current.write_output(body["step"], body["text"])
            else:
                self._json(404, {"ok": False})
                return
        self._json(200, {"ok": True})


class Holder:
    def __init__(self, app_server):
        self.app_server = app_server
        self.lock = threading.Lock()
        self.current = None

    def reset(self, scenario):
        old = self.current
        FakePty.created = []
        self.current = Session(scenario)
        self.app_server.engine = self.current.engine
        if old is not None:
            old.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=38927)
    parser.add_argument("--token", default="dev-token")
    args = parser.parse_args()
    first = Session("ready")
    server = AppServer(first.engine, port=args.port, token=args.token, heartbeat=0.5)
    holder = Holder(server)
    holder.current = first
    control = ThreadingHTTPServer(("127.0.0.1", args.port + 1), Control)
    control.daemon_threads = True
    control.holder = holder
    threading.Thread(target=control.serve_forever, daemon=True).start()
    print(f"real app on http://127.0.0.1:{args.port}/?t={args.token}, control on {args.port + 1}", flush=True)
    try:
        server.serve_forever()
    finally:
        holder.current.close()
        control.server_close()
        server.server_close()


if __name__ == "__main__":
    main()
