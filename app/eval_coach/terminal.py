"""One-session terminal manager and the output ring buffer with sequence numbers."""
from __future__ import annotations

import itertools
import json
import os
import threading
import uuid
from collections import deque
from pathlib import Path

from . import resources

RING_BYTES = 2 * 1024 * 1024
OUTPUT, EXIT = "output", "exit"
MIN_COLS, MIN_ROWS = 10, 2
MAX_COLS, MAX_ROWS = 500, 300


def _real_factory(argv, cwd=None, cols=120, rows=40, on_output=None, env=None):
    from .conpty import ConPTY  # imported late: Windows only
    return ConPTY(argv, cwd=cwd, env=env, cols=cols, rows=rows, on_output=on_output)


def _real_argv(command, env=None):
    from .conpty import command_to_argv
    return command_to_argv(command, env.get("PATH") if env else None)


def _real_check(command, env=None):
    from .conpty import command_to_argv, resolve_command
    path = env.get("PATH") if env else None
    resolve_command(command_to_argv(command, path), path)


def _terminal_hints():
    try:
        return json.loads(resources.read_text("content/terminal-hints.json"))
    except (resources.ResourceNotFound, ValueError):
        return {}


def _with_terminal_hint(argv, env):
    """Some CLIs warn "Unsupported terminal" unless the environment names a terminal they know.

    The page terminal is xterm.js on a ConPTY, which those CLIs handle fine, so they get a
    Windows Terminal marker. Only the commands listed in content/terminal-hints.json get it,
    so no other CLI sees a changed environment.
    """
    hints = _terminal_hints()
    names = {str(n).lower() for n in hints.get("commands_that_need_a_terminal_marker", [])}
    variable = hints.get("marker_variable")
    if not argv or not variable or Path(str(argv[0])).stem.lower() not in names:
        return env
    merged = dict(os.environ) if env is None else dict(env)
    if not any(k.upper() in (variable, "TERM_PROGRAM") for k in merged):
        merged[variable] = str(uuid.uuid4())
    return merged


class _Session:
    __slots__ = ("id", "pty", "waiter")

    def __init__(self, session_id):
        self.id = session_id
        self.pty = None
        self.waiter = None


class TerminalManager:
    def __init__(self, pty_factory=None, argv_parser=None, command_checker=None,
                 ring_bytes=RING_BYTES):
        self._pty_factory = pty_factory or _real_factory
        self._parse = argv_parser or _real_argv
        self._check = command_checker or _real_check
        self._ring_limit = ring_bytes
        self._cond = threading.Condition()
        self._ring = deque()  # (seq, kind, payload)
        self._ring_size = 0
        self._seq = 0
        self._state_gen = 0
        self._session = None
        self._session_ids = itertools.count(1)
        self._session_lock = threading.RLock()  # serializes start/stop
        self._label = ""
        self._owner = None
        self._exit_code = None
        self._running = False
        self._cols, self._rows = 120, 40

    # --- lifecycle ---------------------------------------------------------

    def check_command(self, command, env=None):
        """Raise ValueError or OSError if the command cannot be launched."""
        self._check(command, env)

    def start(self, command, cwd, label, env=None, owner=None):
        """Stop any running CLI, then start this one. Only one runs at a time.

        `command` is a string from the participant, or an argv list the app built.
        `env` is the full environment for the new process (None keeps this process's).
        `owner` names the lesson activity, step or setup page the session belongs to. It stays after the CLI
        exits, so a page that is not the owner knows the output on screen is left over from somewhere else.
        """
        with self._session_lock:
            self._stop_locked()
            argv = list(command) if isinstance(command, (list, tuple)) else self._parse(command, env)
            env = _with_terminal_hint(argv, env)
            session = _Session(next(self._session_ids))
            with self._cond:
                self._ring.clear()
                self._ring_size = 0
                self._session = session
                self._label = label
                self._owner = owner
                self._exit_code = None
                self._running = True
            try:
                session.pty = self._pty_factory(
                    argv, cwd=cwd, env=env, cols=self._cols, rows=self._rows,
                    on_output=lambda data: self._on_output(session, data))
            except BaseException:
                with self._cond:
                    self._running = False
                    self._session = None
                raise
            session.waiter = threading.Thread(target=self._wait_loop, args=(session,), daemon=True)
            session.waiter.start()

    def stop(self):
        """Kill the process tree of the running CLI, if any."""
        with self._session_lock:
            self._stop_locked()

    def release(self):
        """Stop any CLI and forget its label, owner, exit code and output, so the next page starts clear."""
        with self._session_lock:
            self._stop_locked()
            with self._cond:
                self._ring.clear()
                self._ring_size = 0
                self._label = ""
                self._owner = None
                self._exit_code = None
                self._running = False
                self._state_gen += 1
                self._cond.notify_all()

    def _stop_locked(self):
        session = self._session
        if session is None or session.pty is None:
            return
        session.pty.close()
        if session.waiter is not None:
            session.waiter.join(10)
        with self._cond:
            if self._session is session:
                self._session = None

    def _wait_loop(self, session):
        code = session.pty.wait()
        session.pty.close()  # drains output, so the exit event comes last
        if code is None:
            code = getattr(session.pty, "exit_code", None)
        with self._cond:
            if self._session is not session:
                return
            self._running = False
            self._exit_code = code
            self._append(EXIT, code if code is not None else -1)
            self._cond.notify_all()

    # --- input -------------------------------------------------------------

    def _current_pty(self):
        with self._cond:
            session = self._session
            if session is None or not self._running:
                return None
            return session.pty

    def write(self, data):
        """Keystrokes from the page. Ignored when no CLI is running."""
        pty = self._current_pty()
        if pty is None:
            return
        try:
            pty.write(data)
        except OSError:
            pass  # the CLI exited between the check and the write

    def type_line(self, text):
        pty = self._current_pty()
        if pty is None:
            raise OSError("No CLI is running.")
        pty.type_line(text)

    def resize(self, cols, rows):
        cols = max(MIN_COLS, min(MAX_COLS, cols))
        rows = max(MIN_ROWS, min(MAX_ROWS, rows))
        self._cols, self._rows = cols, rows
        pty = self._current_pty()
        if pty is not None:
            try:
                pty.resize(cols, rows)
            except OSError:
                pass

    # --- status ------------------------------------------------------------

    @property
    def running(self):
        with self._cond:
            return self._running

    def status(self):
        with self._cond:
            return {"running": self._running, "label": self._label, "exit_code": self._exit_code,
                    "owner": self._owner}

    # --- events ------------------------------------------------------------

    def _append(self, kind, payload):
        self._seq += 1
        self._ring.append((self._seq, kind, payload))
        if kind == OUTPUT:
            self._ring_size += len(payload)
            while self._ring_size > self._ring_limit and len(self._ring) > 1:
                _, old_kind, old = self._ring.popleft()
                if old_kind == OUTPUT:
                    self._ring_size -= len(old)

    def _on_output(self, session, data):
        with self._cond:
            if self._session is not session:
                return
            self._append(OUTPUT, data)
            self._cond.notify_all()

    def publish_state(self):
        """Tell every stream to refetch the state."""
        with self._cond:
            self._state_gen += 1
            self._cond.notify_all()

    @property
    def state_generation(self):
        with self._cond:
            return self._state_gen

    def wait_events(self, cursor, state_gen, timeout):
        """Wait for news after cursor. Returns (events, new_cursor, state_generation)."""
        with self._cond:
            if cursor > self._seq:
                cursor = 0  # a cursor from before a restart

            def ready():
                return state_gen != self._state_gen or (self._ring and self._ring[-1][0] > cursor)

            self._cond.wait_for(ready, timeout)
            events = [e for e in self._ring if e[0] > cursor]
            return events, max(cursor, self._seq), self._state_gen
