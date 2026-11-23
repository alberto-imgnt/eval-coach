"""Real pseudo console tests. These use cmd.exe only: no AI CLI and no model use."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import helpers
from helpers import wait_until

if sys.platform != "win32":
    raise unittest.SkipTest("ConPTY is the Windows terminal; the Mac terminal is tested in test_ptyterm.py")

from eval_coach.conpty import ConPTY, command_to_argv, parse_command, resolve_command  # noqa: E402
from eval_coach.terminal import TerminalManager  # noqa: E402


def visible(pty):
    """Output with escape sequences left in, decoded for searching."""
    return pty.snapshot().decode("utf-8", errors="replace")


def process_exists(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                         capture_output=True, timeout=30).stdout.decode("utf-8", "replace")
    return f'"{pid}"' in out


class ParseCommand(unittest.TestCase):
    def tokens(self, text):
        return parse_command(text)[0]

    def test_simple(self):
        self.assertEqual(self.tokens("claude --model sonnet"), ["claude", "--model", "sonnet"])

    def test_windows_path_keeps_backslashes(self):
        self.assertEqual(self.tokens(r"C:\Tools\claude.exe --x"), [r"C:\Tools\claude.exe", "--x"])

    def test_quoted_path_with_spaces(self):
        self.assertEqual(self.tokens(r'"C:\Program Files\Foo\claude.cmd" --model sonnet'),
                         [r"C:\Program Files\Foo\claude.cmd", "--model", "sonnet"])

    def test_single_quoted_path(self):
        self.assertEqual(self.tokens(r"'C:\Program Files\x.exe' a"), [r"C:\Program Files\x.exe", "a"])

    def test_quoted_folder_ending_in_backslash(self):
        self.assertEqual(self.tokens(r'"C:\Tools\" --x'), ["C:\\Tools\\", "--x"])

    def test_escaped_quote_inside_an_argument(self):
        self.assertEqual(self.tokens(r'run "say \"hi\" now"'), ["run", 'say "hi" now'])

    def test_folder_ending_in_backslash_before_another_quoted_argument(self):
        self.assertEqual(self.tokens(r'"C:\Tools\" "D:\a b"'), ["C:\\Tools\\", "D:\\a b"])

    def test_apostrophe_in_a_path(self):
        self.assertEqual(self.tokens(r"C:\Users\O'Brien\x.exe"), [r"C:\Users\O'Brien\x.exe"])

    def test_empty_and_unbalanced(self):
        with self.assertRaises(ValueError):
            parse_command("   ")
        with self.assertRaises(ValueError):
            parse_command('"C:\\no end')

    def test_unquoted_path_with_spaces_is_recognized_if_it_exists(self):
        folder = Path(tempfile.mkdtemp(prefix="eval coach "))
        self.addCleanup(shutil.rmtree, folder, True)
        exe = folder / "my tool.cmd"
        exe.write_text("@echo hi\r\n", encoding="utf-8")
        self.assertEqual(command_to_argv(f"{exe} --flag"), [str(exe), "--flag"])

    def test_unknown_command_is_left_alone(self):
        self.assertEqual(command_to_argv("no-such-cli-xyz --a"), ["no-such-cli-xyz", "--a"])


class ResolveCommand(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="eval-coach-pty-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_exe(self):
        app, line, kind = resolve_command(["cmd.exe", "/c", "echo hi"])
        self.assertEqual(kind, "exe")
        self.assertTrue(app.lower().endswith("cmd.exe"))
        self.assertIn('"echo hi"', line)

    def test_cmd_shim_goes_through_cmd_exe(self):
        shim = self.dir / "tool.cmd"
        shim.write_text("@echo hi\r\n", encoding="utf-8")
        app, line, kind = resolve_command([str(shim), "--model", "sonnet"])
        self.assertEqual(kind, "cmd")
        self.assertTrue(app.lower().endswith("cmd.exe"))
        self.assertIn("/d /s /c", line)
        self.assertIn("--model sonnet", line)

    def test_bat_shim(self):
        shim = self.dir / "tool.bat"
        shim.write_text("@echo hi\r\n", encoding="utf-8")
        self.assertEqual(resolve_command([str(shim)])[2], "bat")

    def test_extensionless_path_falls_back_to_sibling_shim(self):
        (self.dir / "tool").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.dir / "tool.cmd").write_text("@echo hi\r\n", encoding="utf-8")
        app, line, kind = resolve_command([str(self.dir / "tool")])
        self.assertEqual(kind, "cmd")
        self.assertIn("tool.cmd", line.lower())

    def test_batch_argument_cannot_inject(self):
        shim = self.dir / "tool.cmd"
        shim.write_text("@echo hi\r\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            resolve_command([str(shim), "%PATH%"])
        line = resolve_command([str(shim), "a&b"])[1]
        self.assertIn('"a&b"', line)

    def test_missing(self):
        with self.assertRaises(FileNotFoundError):
            resolve_command(["no-such-cli-xyz"])


class RealConsole(unittest.TestCase):
    def start(self, argv=None):
        pty = ConPTY(argv or ["cmd.exe", "/d", "/q"], cwd=str(Path.home()), cols=100, rows=30)
        self.addCleanup(pty.close)
        return pty

    def test_interactive_echo_and_type_line(self):
        pty = self.start()
        self.assertTrue(wait_until(lambda: b">" in pty.snapshot(), timeout=15), visible(pty))
        pty.type_line("echo marker-one-two")
        self.assertTrue(wait_until(lambda: visible(pty).count("marker-one-two") >= 2, timeout=15), visible(pty))
        self.assertTrue(pty.alive())

    def test_type_line_sends_enter_separately(self):
        pty = self.start()
        wait_until(lambda: b">" in pty.snapshot(), timeout=15)
        writes = []
        original = pty.write
        pty.write = lambda data: (writes.append((data, time.monotonic())), original(data))[1]
        pty.type_line("rem hello")
        self.assertEqual([w[0] for w in writes], [b"rem hello", b"\r"])
        self.assertGreaterEqual(writes[1][1] - writes[0][1], 0.39)

    def test_resize(self):
        pty = self.start()
        wait_until(lambda: b">" in pty.snapshot(), timeout=15)
        pty.resize(132, 50)
        pty.read_new()
        pty.type_line("mode con")
        self.assertTrue(wait_until(lambda: "132" in visible(pty), timeout=15), visible(pty))

    def test_kill_takes_the_whole_tree_and_alive_is_false_after_close(self):
        pty = self.start()
        wait_until(lambda: b">" in pty.snapshot(), timeout=15)
        pty.write(b"ping -n 60 127.0.0.1\r")
        self.assertTrue(wait_until(lambda: len(pty.pids()) >= 2, timeout=15), pty.pids())
        pids = pty.pids()
        self.assertTrue(pty.alive())
        pty.close()
        self.assertFalse(pty.alive())
        self.assertEqual(pty.pids(), [])
        self.assertIsNotNone(pty.exit_code)
        for pid in pids:
            self.assertTrue(wait_until(lambda: not process_exists(pid), timeout=15), f"pid {pid} survived")

    def test_close_is_idempotent_and_write_is_refused_afterwards(self):
        pty = self.start()
        pty.close()
        pty.close()
        with self.assertRaises(OSError):
            pty.write(b"x")
        pty.resize(80, 25)  # ignored, no crash
        self.assertFalse(pty.alive())
        self.assertIsNotNone(pty.wait(1))

    def test_exit_is_detected_and_output_is_kept(self):
        pty = self.start(["cmd.exe", "/d", "/c", "echo finished-here"])
        self.assertEqual(pty.wait(15), 0)
        self.assertTrue(wait_until(lambda: "finished-here" in visible(pty), timeout=15), visible(pty))
        pty.close()
        self.assertFalse(pty.alive())
        self.assertEqual(pty.exit_code, 0)

    def test_launches_a_cmd_shim_with_arguments(self):
        folder = Path(tempfile.mkdtemp(prefix="eval coach shim "))
        self.addCleanup(shutil.rmtree, folder, True)
        shim = folder / "tool.cmd"
        shim.write_text("@echo shim-saw %1 %2\r\n", encoding="utf-8")
        pty = self.start([str(shim), "--model", "sonnet"])
        self.assertEqual(pty.wait(15), 0)
        self.assertTrue(wait_until(lambda: "shim-saw --model sonnet" in visible(pty), timeout=15), visible(pty))

    def test_extensionless_shim_runs(self):
        folder = Path(tempfile.mkdtemp(prefix="eval-coach-shim-"))
        self.addCleanup(shutil.rmtree, folder, True)
        (folder / "tool").write_text("#!/bin/sh\n", encoding="utf-8")
        (folder / "tool.cmd").write_text("@echo sibling-ran\r\n", encoding="utf-8")
        pty = self.start([str(folder / "tool")])
        self.assertEqual(pty.wait(15), 0)
        self.assertTrue(wait_until(lambda: "sibling-ran" in visible(pty), timeout=15), visible(pty))

    def test_output_is_drained_on_close(self):
        pty = self.start(["cmd.exe", "/d", "/c", "for /l %i in (1,1,400) do @echo drained-line-%i"])
        pty.wait(15)
        pty.close()
        self.assertIn("drained-line-400", visible(pty))

    def test_cwd_is_honored(self):
        folder = Path(tempfile.mkdtemp(prefix="eval-coach-cwd-"))
        self.addCleanup(shutil.rmtree, folder, True)
        pty = ConPTY(["cmd.exe", "/d", "/c", "cd"], cwd=str(folder), cols=200, rows=30)
        self.addCleanup(pty.close)
        pty.wait(15)
        self.assertTrue(wait_until(lambda: folder.name in visible(pty), timeout=15), visible(pty))

    @unittest.skipUnless(os.environ.get("ComSpec"), "needs ComSpec")
    def test_missing_cwd_fails_cleanly(self):
        with self.assertRaises(OSError):
            ConPTY(["cmd.exe"], cwd=r"C:\no\such\folder\anywhere")


class RealManager(unittest.TestCase):
    """The real TerminalManager over a real pseudo console, using cmd.exe."""

    def collect(self, term, needle, timeout=15):
        deadline = time.monotonic() + timeout
        cursor, seen = 0, b""
        gen = term.state_generation
        while time.monotonic() < deadline:
            events, cursor, gen = term.wait_events(cursor, gen, 0.2)
            seen += b"".join(e[2] for e in events if e[1] == "output")
            if needle in seen:
                return seen, cursor
        self.fail(f"{needle!r} not seen in {seen!r}")

    def test_start_type_stop_and_restart(self):
        term = TerminalManager()
        self.addCleanup(term.stop)
        term.resize(101, 33)
        term.start("cmd.exe /d /q", str(Path.home()), "First")
        self.assertTrue(term.running)
        self.collect(term, b">")
        term.type_line("echo manager-marker")
        _, cursor = self.collect(term, b"manager-marker")
        first_pids = term._session.pty.pids()
        self.assertEqual((term._session.pty.resize(120, 30)), None)

        term.start("cmd.exe /d /q", str(Path.home()), "Second")  # replaces the first
        self.assertTrue(term.running)
        self.assertEqual(term.status()["label"], "Second")
        for pid in first_pids:
            self.assertTrue(wait_until(lambda: not process_exists(pid), timeout=15), f"pid {pid} survived")
        events, _, _ = term.wait_events(cursor, term.state_generation, 5)
        self.assertTrue(all(e[0] > cursor for e in events))

        term.stop()
        self.assertTrue(wait_until(lambda: not term.running, timeout=15))
        self.assertIsNotNone(term.status()["exit_code"])
        self.assertEqual(term._session, None)

    def test_natural_exit_reports_the_code(self):
        term = TerminalManager()
        self.addCleanup(term.stop)
        term.start("cmd.exe /d /c exit 3", str(Path.home()), "Exit")
        self.assertTrue(wait_until(lambda: not term.running, timeout=15))
        self.assertEqual(term.status()["exit_code"], 3)
        events, _, _ = term.wait_events(0, term.state_generation, 0)
        self.assertEqual(events[-1][1:], ("exit", 3))


if __name__ == "__main__":
    unittest.main()
