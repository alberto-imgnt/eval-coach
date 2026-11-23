"""The Mac terminal. The real pty tests run only on a POSIX system (macOS CI); they use a small Python
child, never an AI CLI or a model."""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import time
import unittest

import helpers
from helpers import wait_until

from eval_coach import ptyterm

POSIX = os.name == "posix"


class Parsing(unittest.TestCase):
    def test_splits_like_a_shell(self):
        self.assertEqual(ptyterm.command_to_argv('claude --model "a b"'), ["claude", "--model", "a b"])

    def test_empty_and_unbalanced(self):
        with self.assertRaises(ValueError):
            ptyterm.command_to_argv("   ")
        with self.assertRaises(ValueError):
            ptyterm.command_to_argv('claude "oops')

    @unittest.skipUnless(POSIX, "needs a POSIX file system")
    def test_resolves_a_path_and_a_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool = os.path.join(tmp, "my-tool")
            with open(tool, "w") as handle:
                handle.write("#!/bin/sh\nexit 0\n")
            os.chmod(tool, 0o755)
            plain = os.path.join(tmp, "plain")
            with open(plain, "w") as handle:
                handle.write("data")
            self.assertEqual(ptyterm.resolve_command([tool]), tool)
            self.assertEqual(ptyterm.resolve_command(["my-tool"], path=tmp), tool)
            with self.assertRaises(FileNotFoundError):
                ptyterm.resolve_command([plain])
            with self.assertRaises(FileNotFoundError):
                ptyterm.resolve_command(["no-such-tool-xyz"], path=tmp)

    def test_exit_code_of_a_signal(self):
        self.assertEqual(ptyterm._exit_code(-9), 137)
        self.assertEqual(ptyterm._exit_code(3), 3)
        self.assertIsNone(ptyterm._exit_code(None))


def text(pty):
    return pty.snapshot().decode("utf-8", errors="replace")


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


ECHO = textwrap.dedent("""
    import sys
    sys.stdout.write("ready\\n"); sys.stdout.flush()
    line = sys.stdin.readline().strip()
    sys.stdout.write("got:" + line + "\\n"); sys.stdout.flush()
    sys.exit(3)
""")

SIZE = textwrap.dedent("""
    import os, sys
    sys.stdout.write("ready\\n"); sys.stdout.flush()
    sys.stdin.readline()
    size = os.get_terminal_size(1)
    sys.stdout.write("size:%dx%d\\n" % (size.columns, size.lines)); sys.stdout.flush()
""")

TREE = textwrap.dedent("""
    import subprocess, sys, time
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    sys.stdout.write("pids:%d\\n" % child.pid); sys.stdout.flush()
    time.sleep(120)
""")

NOISY = "import sys\nsys.stdout.write('x' * 5000); sys.stdout.flush()\n"


@unittest.skipUnless(POSIX, "the pty terminal needs a POSIX system")
class RealPty(unittest.TestCase):
    def start(self, script, **kwargs):
        pty = ptyterm.PosixPTY([sys.executable, "-u", "-c", script], cwd=tempfile.gettempdir(),
                               env=dict(os.environ), **kwargs)
        self.addCleanup(pty.close)
        return pty

    def test_round_trip_and_exit_code(self):
        pty = self.start(ECHO)
        self.assertTrue(wait_until(lambda: "ready" in text(pty), 15))
        pty.type_line("hello", delay=0.05)
        self.assertEqual(pty.wait(15), 3)
        pty.close()
        self.assertIn("got:hello", text(pty))
        self.assertEqual(pty.exit_code, 3)
        self.assertFalse(pty.alive())

    def test_output_reaches_the_callback_and_read_new_once(self):
        seen = []
        pty = self.start(ECHO, on_output=seen.append)
        self.assertTrue(wait_until(lambda: b"ready" in b"".join(seen), 15))
        first = pty.read_new()
        self.assertIn(b"ready", first)
        self.assertEqual(pty.read_new(), b"")

    def test_resize_is_seen_by_the_child(self):
        pty = self.start(SIZE, cols=100, rows=30)
        self.assertTrue(wait_until(lambda: "ready" in text(pty), 15))
        pty.resize(132, 41)
        pty.type_line("go", delay=0.05)
        self.assertTrue(wait_until(lambda: "size:132x41" in text(pty), 15), text(pty))

    def test_close_ends_a_child_and_a_grandchild(self):
        pty = self.start(TREE)
        self.assertTrue(wait_until(lambda: "pids:" in text(pty), 15))
        grandchild = int(text(pty).split("pids:")[1].split()[0])
        self.assertTrue(alive(grandchild))
        self.assertIn(grandchild, pty.pids())
        pty.close()
        self.assertTrue(wait_until(lambda: not alive(grandchild), 10), "the grandchild is gone")
        self.assertFalse(pty.alive())
        self.assertEqual(pty.pids(), [])
        pty.close()  # a second close is harmless

    def test_write_after_close_is_refused(self):
        pty = self.start(ECHO)
        pty.close()
        with self.assertRaises(OSError):
            pty.write(b"x")

    def test_a_process_that_ignores_the_polite_stop_is_forced(self):
        script = textwrap.dedent("""
            import signal, sys, time
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            sys.stdout.write("stubborn\\n"); sys.stdout.flush()
            time.sleep(120)
        """)
        pty = self.start(script)
        self.assertTrue(wait_until(lambda: "stubborn" in text(pty), 15))
        started = time.monotonic()
        pty.close()
        self.assertLess(time.monotonic() - started, 15)
        self.assertFalse(pty.alive())

    def test_output_ring_buffer_is_limited(self):
        original = ptyterm.BUFFER_LIMIT
        ptyterm.BUFFER_LIMIT = 1000
        self.addCleanup(setattr, ptyterm, "BUFFER_LIMIT", original)
        pty = self.start(NOISY)
        self.assertEqual(pty.wait(15), 0)
        pty.close()
        self.assertLessEqual(len(pty.snapshot()), 1000)
        self.assertGreater(len(pty.snapshot()), 0)


@unittest.skipUnless(POSIX, "the pty terminal needs a POSIX system")
class QuietTestRunner(unittest.TestCase):
    """The quiet background AI test runs through SystemRunner: a time limit and a process-group stop."""

    SPAWN = textwrap.dedent("""
        import subprocess, sys, time
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        sys.stdout.write("pids:%d\\n" % child.pid); sys.stdout.flush()
        time.sleep(120)
    """)

    def test_the_time_limit_ends_the_program_and_what_it_started(self):
        from eval_coach.preflight import SystemRunner
        result = SystemRunner().run([sys.executable, "-u", "-c", self.SPAWN], timeout=3)
        self.assertTrue(result.timed_out)
        grandchild = int(result.stdout.split("pids:")[1].split()[0])
        self.assertTrue(wait_until(lambda: not alive(grandchild), 10), "the grandchild is gone")

    def test_cancelling_stops_the_group(self):
        import threading
        from eval_coach.preflight import SystemRunner
        cancel = threading.Event()
        threading.Timer(1.5, cancel.set).start()
        result = SystemRunner().run([sys.executable, "-u", "-c", self.SPAWN], timeout=60, cancel=cancel)
        self.assertTrue(result.cancelled)
        grandchild = int(result.stdout.split("pids:")[1].split()[0])
        self.assertTrue(wait_until(lambda: not alive(grandchild), 10), "the grandchild is gone")

    def test_a_normal_exit_code_is_returned(self):
        from eval_coach.preflight import SystemRunner
        result = SystemRunner().run([sys.executable, "-c", "import sys; sys.exit(7)"], timeout=30)
        self.assertEqual(result.code, 7)
        self.assertFalse(result.timed_out)


@unittest.skipUnless(POSIX, "the pty terminal needs a POSIX system")
class WithTheManager(unittest.TestCase):
    def test_the_manager_runs_a_program_and_reports_its_exit(self):
        from eval_coach.terminal import TerminalManager
        manager = TerminalManager()
        self.addCleanup(manager.stop)
        manager.start([sys.executable, "-u", "-c", "print('manager ok')"], cwd=tempfile.gettempdir(), label="t",
                      env=dict(os.environ))
        self.assertTrue(wait_until(lambda: not manager.running, 15))
        self.assertEqual(manager.status()["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
