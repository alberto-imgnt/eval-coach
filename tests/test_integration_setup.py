"""The built eval-coach.cmd, alone in its folder, finds Python, starts the real app and it answers /api/state."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from helpers import ROOT

if sys.platform != "win32":
    raise unittest.SkipTest("this runs the built Windows launcher")

from test_setup_cmd import CMD_EXE, SYSTEM_ROOT, real_python_dir, rmtree_with_retries  # noqa: E402

LAUNCHER = ROOT / "dist" / "eval-coach.cmd"
TMP_ROOT = ROOT / "tests" / ".tmp-integration"
REAL_PROFILE = Path(os.environ["USERPROFILE"]) / ".eval-coach"


def _request(url, method="GET", token=None, body=None):
    headers = {}
    data = None
    if token:
        headers["X-Eval-Token"] = token
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.status, json.loads(res.read())


def _listing(folder):
    if not folder.exists():
        return None
    return sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir())


class LauncherStartsTheRealApp(unittest.TestCase):
    def setUp(self):
        self.real_profile_before = _listing(REAL_PROFILE)
        self.work = TMP_ROOT / f"run-{os.getpid()}"
        rmtree_with_retries(self.work)
        self.work.mkdir(parents=True)
        self.addCleanup(rmtree_with_retries, TMP_ROOT)
        self.profile = self.work / "Plain User"
        self.temp = self.profile / "AppData" / "Local" / "Temp"
        self.temp.mkdir(parents=True)
        self.install_dir = self.work / "package"
        self.install_dir.mkdir()

    def tearDown(self):
        self.assertEqual(self.real_profile_before, _listing(REAL_PROFILE), "the real profile must not change")

    def test_launcher_alone_starts_the_built_app(self):
        build = subprocess.run([sys.executable, str(ROOT / "tools" / "build_pyz.py")], capture_output=True, text=True, timeout=120)
        self.assertEqual(build.returncode, 0, build.stderr)
        self.assertTrue(LAUNCHER.is_file())
        shutil.copyfile(LAUNCHER, self.install_dir / "eval-coach.cmd")
        self.assertEqual(["eval-coach.cmd"], [p.name for p in self.install_dir.iterdir()])

        browser_marker = self.work / "browser-opened.txt"
        fake_browser = self.work / "fake-browser.cmd"
        # %* keeps the "=" that batch files otherwise treat as an argument separator.
        fake_browser.write_text(f'@echo %*>"{browser_marker}"\r\n', encoding="ascii")

        env = {
            "SystemRoot": SYSTEM_ROOT,
            "windir": SYSTEM_ROOT,
            "SystemDrive": os.environ["SystemDrive"],
            "ComSpec": CMD_EXE,
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "PATH": str(real_python_dir()),
            "USERPROFILE": str(self.profile),
            "TEMP": str(self.temp),
            "TMP": str(self.temp),
            "BROWSER": str(fake_browser),
        }
        command = f'"{CMD_EXE}" /d /c ""{self.install_dir / "eval-coach.cmd"}""'
        log_path = self.work / "setup-output.txt"
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, env=env, cwd=str(self.work),
                                    stdout=log, stderr=subprocess.STDOUT)
        try:
            url = self._wait_for_browser_url(browser_marker, proc)
            match = re.search(r"http://127\.0\.0\.1:(\d+)/\?t=([\w-]+)", url)
            self.assertIsNotNone(match, url)
            base = f"http://127.0.0.1:{match.group(1)}"
            token = match.group(2)

            status, state = _request(f"{base}/api/state", token=token)
            self.assertEqual(status, 200)
            self.assertFalse(state["configured"])
            self.assertFalse(state["preflight"]["passed"], "preflight must still be incomplete")
            self.assertEqual(state["preflight"]["track"], "script")
            self.assertEqual(state["setup"]["defaults"]["project_path"],
                             os.path.join(str(self.profile), "eval-project"))

            status, body = _request(f"{base}/api/quit", method="POST", token=token, body={})
            self.assertEqual(status, 200)
            self.assertTrue(body["ok"])
            proc.wait(timeout=60)
        finally:
            if proc.poll() is None:
                subprocess.run([os.path.join(SYSTEM_ROOT, "System32", "taskkill.exe"), "/T", "/F", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait(20)
        self.assertEqual(proc.returncode, 0, log_path.read_bytes().decode("mbcs", errors="replace"))
        output = log_path.read_bytes().decode("mbcs", errors="replace")
        self.assertIn("Starting eval-coach", output)
        # The launcher only ever invoked the stand-in browser, so no real browser opened.
        self.assertTrue(browser_marker.is_file(), "the app did not request a browser")
        self.assertFalse((Path(self.profile) / ".eval-coach" / "runtime" / "python").exists(),
                         "a working Python was already available, so no private copy should exist")

    def _wait_for_browser_url(self, marker, proc):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                self.fail(f"eval-coach.cmd exited early with code {proc.returncode}")
            if marker.is_file():
                text = marker.read_text(encoding="mbcs", errors="replace").strip()
                if text:
                    return text
            time.sleep(0.2)
        self.fail("the app never asked to open a browser")


if __name__ == "__main__":
    unittest.main()
