"""Stdlib-only pseudo-terminal host for macOS. All POSIX terminal code lives here.

Public surface (the same as conpty.py, so terminal.py can use either):
    command_to_argv(text, path=None) -> argv
    resolve_command(argv, path=None) -> program path
    PosixPTY(argv, cwd=None, env=None, cols=120, rows=40, on_output=None)
        .write(bytes)  .type_line(text)  .read_new()  .snapshot()
        .resize(cols, rows)  .alive()  .wait(timeout)  .exit_code  .pids()  .close()

The child starts in its own session and process group with the pty as its controlling terminal, so
`close()` ends the program and everything it started.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import threading
import time

from . import hostos

# Output kept for read_new()/snapshot(); callers wanting everything use on_output.
BUFFER_LIMIT = 4 * 1024 * 1024
DEFAULT_TERM = "xterm-256color"
CLOSE_WAIT_SECONDS = 3.0
# How often the process groups of what the AI started are noted while it runs (see PosixPTY._note_groups).
GROUP_SCAN_SECONDS = 2.0


# --- command strings -------------------------------------------------------

def command_to_argv(text, path=None):
    """Split a command string the way a POSIX shell would, without running anything."""
    if not text or not text.strip():
        raise ValueError("The AI command is empty.")
    try:
        tokens = shlex.split(text)
    except ValueError:
        raise ValueError("The AI command has a quote that is never closed.") from None
    if not tokens:
        raise ValueError("The AI command is empty.")
    return tokens


def resolve_command(argv, path=None):
    """The program to run for argv[0]. A shebang script is left to the operating system."""
    if not argv:
        raise ValueError("The AI command is empty.")
    name = argv[0]
    target = None
    if os.sep in name:
        candidate = os.path.abspath(os.path.expanduser(name))
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            target = candidate
    else:
        target = shutil.which(name, path=path)
    if not target:
        raise FileNotFoundError(f"Could not find the command {name!r}. "
                                "Check the spelling, or enter its full path.")
    return target


def _become_controlling_terminal_argv(app, args):
    """The argv that starts `app` with the pty on fd 0 as its controlling terminal.

    A short helper program, started fresh, does the one terminal call and then becomes `app`. Nothing in
    this process runs between the fork and the start of the helper, which Python code there could stall on
    when another thread holds a lock at the moment of the fork.
    """
    if not sys.executable:
        raise OSError("The Python that runs the app cannot be found, so the AI window cannot start.")
    return [sys.executable, "-I", "-S", "-c", _HELPER, app] + list(args)


# Runs in the new session with the pty on fd 0, then replaces itself with the AI.
_HELPER = """\
import fcntl, os, signal, sys, termios
try:
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
except OSError:
    pass
for name in ("SIGPIPE", "SIGXFSZ"):
    if hasattr(signal, name):
        signal.signal(getattr(signal, name), signal.SIG_DFL)
try:
    os.execv(sys.argv[1], sys.argv[1:])
except OSError as exc:
    sys.stderr.write("Could not start " + sys.argv[1] + ": " + str(exc) + "\\r\\n")
    os._exit(127)
"""


def _exit_code(returncode):
    if returncode is None:
        return None
    return 128 - returncode if returncode < 0 else returncode


# --- pseudo terminal ---------------------------------------------------------

class PosixPTY:
    def __init__(self, argv, cwd=None, env=None, cols=120, rows=40, on_output=None):
        import pty

        self.app = resolve_command(argv, env.get("PATH") if env else None)
        self.exit_code = None
        self.pid = 0
        self._on_output = on_output
        self._buf = bytearray()
        self._pos = 0
        self._buf_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._groups_lock = threading.Lock()
        self._descendants = {}  # pid -> process group of each process the AI started
        self._last_scan = 0.0
        self._closing = False
        self._closed = False
        self._proc = None
        self._master = None
        self._reader = None

        child_env = dict(os.environ if env is None else env)
        if child_env.get("TERM", "dumb") == "dumb":
            child_env["TERM"] = DEFAULT_TERM
        master, slave = pty.openpty()
        try:
            self._master = master
            self._set_size(cols, rows, fd=master)
            self._proc = subprocess.Popen(
                _become_controlling_terminal_argv(self.app, argv[1:]), stdin=slave, stdout=slave, stderr=slave,
                cwd=cwd, env=child_env, close_fds=True, start_new_session=True)
        except BaseException:
            os.close(master)
            self._master = None
            raise
        finally:
            os.close(slave)  # only the child keeps the slave, so the reader sees the end of output
        self.pid = self._proc.pid
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    @staticmethod
    def _set_size(cols, rows, fd):
        import fcntl
        import struct
        import termios
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def _read_loop(self):
        master = self._master
        while True:
            try:
                data = os.read(master, 65536)
            except OSError:
                return  # EIO once every holder of the slave has gone, or the master was closed
            if not data:
                return
            with self._buf_lock:
                self._buf += data
                excess = len(self._buf) - BUFFER_LIMIT
                if excess > 0:
                    del self._buf[:excess]
                    self._pos = max(0, self._pos - excess)
            if self._on_output is not None:
                try:
                    self._on_output(data)
                except Exception:
                    pass  # a broken consumer must not stop the drain

    def write(self, data):
        """Write all of data, or raise. Refused once closing has begun."""
        total = 0
        with self._write_lock:
            if self._closing or self._master is None:
                raise OSError("The terminal is closed.")
            while total < len(data):
                total += os.write(self._master, data[total:])
        return total

    def type_line(self, text, delay=0.4):
        """Type text, wait, then press Enter as a separate write."""
        self.write(text.encode("utf-8"))
        time.sleep(delay)
        self.write(b"\r")

    def read_new(self):
        with self._buf_lock:
            data = bytes(self._buf[self._pos:])
            self._pos = len(self._buf)
        return data

    def snapshot(self):
        with self._buf_lock:
            return bytes(self._buf)

    def resize(self, cols, rows):
        if self._closing or self._master is None:
            return
        self._set_size(cols, rows, fd=self._master)

    def alive(self):
        return not self._closing and self._proc is not None and self._proc.poll() is None

    def wait(self, timeout=None):
        """Return the exit code once the process has exited, else None on timeout."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if self._proc is None:
                return self.exit_code
            code = self._proc.poll()
            if code is not None:
                self.exit_code = _exit_code(code)
                return self.exit_code
            if deadline is not None and time.monotonic() >= deadline:
                return None
            if time.monotonic() - self._last_scan >= GROUP_SCAN_SECONDS:
                self._note_groups()
            time.sleep(0.03)

    # --- what the AI started ---------------------------------------------------

    @staticmethod
    def _process_table():
        """[(pid, ppid, pgid)] for every process, or [] when the list cannot be read."""
        try:
            out = subprocess.run([hostos.tool_path("ps"), "-ax", "-o", "pid=,ppid=,pgid="], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        rows = []
        for line in out.decode("utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 3 and all(part.isdigit() for part in parts):
                rows.append(tuple(int(part) for part in parts))
        return rows

    def _note_groups(self, rows=None):
        """Remember every process the AI started, with its process group.

        A shell can put a background job in a group of its own, which stopping the AI's own group never
        reaches. The children are found through the parent links while the AI is alive; once the AI has
        exited its children are handed to another parent and could no longer be traced.
        """
        self._last_scan = time.monotonic()
        rows = self._process_table() if rows is None else rows
        children = {}
        for pid, ppid, pgid in rows:
            children.setdefault(ppid, []).append((pid, pgid))
        found = {}
        todo = [self.pid]
        while todo:
            for pid, pgid in children.get(todo.pop(), ()):
                if pid not in found:
                    found[pid] = pgid
                    todo.append(pid)
        with self._groups_lock:
            self._descendants.update(found)

    def _own_groups(self, rows):
        """The process groups, other than the AI's own, that still hold a process the AI started."""
        current = {pid: pgid for pid, _, pgid in rows}
        with self._groups_lock:
            noted = dict(self._descendants)
        keep = {pgid for pid, pgid in noted.items() if current.get(pid) == pgid}
        keep.discard(self.pid)
        keep.discard(os.getpgrp())  # never this app's own group
        return sorted(g for g in keep if g > 1)

    def pids(self):
        """Every live process in this terminal's process group, and in the groups its programs started."""
        if self._closed or not self.pid:
            return []
        rows = self._process_table()
        groups = {self.pid, *self._own_groups(rows)}
        return [pid for pid, _, pgid in rows if pgid in groups]

    def close(self):
        """End the whole process tree, then release the terminal. Safe to call twice."""
        with self._close_lock:
            if self._closed:
                return
            self._closing = True
            if self.pid:
                rows = self._process_table()
                if self._proc.poll() is None:
                    self._note_groups(rows)
                groups = [self.pid] + self._own_groups(rows)
                hostos.kill_groups(groups, CLOSE_WAIT_SECONDS, reap=self._proc.poll)
                if self._proc.poll() is None:
                    try:
                        self._proc.kill()
                    except OSError:
                        pass
                self.wait(5)
            reader = self._reader
            if reader is not None:
                reader.join(5)  # output the child left behind is drained first
            got_writer = self._write_lock.acquire(timeout=5)
            try:
                if self._master is not None:
                    try:
                        os.close(self._master)
                    except OSError:
                        pass
                    self._master = None
            finally:
                if got_writer:
                    self._write_lock.release()
            if reader is not None and reader.is_alive():
                reader.join(2)
            self._closed = True
