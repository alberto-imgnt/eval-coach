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
import threading
import time

from . import hostos

# Output kept for read_new()/snapshot(); callers wanting everything use on_output.
BUFFER_LIMIT = 4 * 1024 * 1024
DEFAULT_TERM = "xterm-256color"
CLOSE_WAIT_SECONDS = 3.0


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


def _become_controlling_terminal():
    """Runs in the child after setsid(): make the pty on fd 0 its controlling terminal."""
    import fcntl
    import termios
    try:
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    except OSError:
        pass


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
                [self.app] + list(argv[1:]), stdin=slave, stdout=slave, stderr=slave, cwd=cwd, env=child_env,
                close_fds=True, start_new_session=True, preexec_fn=_become_controlling_terminal)
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
            time.sleep(0.03)

    def pids(self):
        """Every live process in this terminal's process group (root plus descendants)."""
        if self._closed or not self.pid:
            return []
        try:
            out = subprocess.run([hostos.tool_path("ps"), "-ax", "-o", "pid=,pgid="], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        found = []
        for line in out.decode("utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == str(self.pid) and parts[0].isdigit():
                found.append(int(parts[0]))
        return found

    def close(self):
        """End the whole process group, then release the terminal. Safe to call twice."""
        with self._close_lock:
            if self._closed:
                return
            self._closing = True
            if self.pid:
                hostos.kill_group(self.pid, CLOSE_WAIT_SECONDS, reap=self._proc.poll)
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
