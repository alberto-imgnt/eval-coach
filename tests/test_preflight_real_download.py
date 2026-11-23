"""One real download: Node.js from nodejs.org, then promptfoo from the npm registry.

Skipped unless EVAL_COACH_TEST_REAL_DOWNLOAD=1. It uses about 1 GB under
tests\\.tmp-preflight\\ and removes that folder when it finishes. It never touches
the real %USERPROFILE%, PATH, the registry or any CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import FakeTerminal, ROOT

if sys.platform != "win32":
    raise unittest.SkipTest("the real download test pins the Windows Node.js build")

from eval_coach import preflight as pf  # noqa: E402
from eval_coach.preflight import Preflight  # noqa: E402
from test_setup_cmd import rmtree_with_retries  # noqa: E402

TMP_ROOT = ROOT / "tests" / ".tmp-preflight"
SPIKE_DOWNLOAD = ROOT / "spikes" / "phase0-preflight" / "downloads" / "node-v26.13.0-win-x64.zip"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@unittest.skipUnless(os.environ.get("EVAL_COACH_TEST_REAL_DOWNLOAD") == "1", "real downloads are off by default")
class RealDownload(unittest.TestCase):
    def setUp(self):
        self.home = TMP_ROOT / f"home-{os.getpid()}"
        rmtree_with_retries(self.home)
        self.home.mkdir(parents=True)
        self.addCleanup(rmtree_with_retries, TMP_ROOT)
        # Hide any existing Node so the test proves the private download path.
        scrubbed = os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                                   if p and "node" not in p.lower() and "volta" not in p.lower())
        patcher = mock.patch.dict(os.environ, {"PATH": scrubbed})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.preflight = Preflight(self.home, FakeTerminal(), registry_paths=lambda: [],
                                   python_path=os.sys.executable)
        self.preflight.set_track("promptfoo")

    def status(self, item):
        return next(i for i in self.preflight.view(None, {"kind": None, "sent": False})["items"] if i["id"] == item)

    def test_node_then_promptfoo(self):
        started = time.monotonic()
        self.preflight.start_check_all()
        self.preflight.wait_for_job(120)
        node = self.status("node")
        self.assertEqual(node["status"], "needs_you", node)

        self.preflight.start_install("node", True)
        self.preflight.wait_for_job(1800)
        node = self.status("node")
        self.assertEqual(node["status"], "passed", node)
        node_exe = self.home / "runtime" / "node" / "node.exe"
        self.assertTrue(node_exe.is_file())
        self.assertIn(pf.NODE_VERSION, node["detail"])
        if SPIKE_DOWNLOAD.is_file():
            self.assertEqual(_sha256(SPIKE_DOWNLOAD), pf.NODE_SHA256, "spike download matches the pinned hash")

        self.preflight.start_check_all()
        self.preflight.wait_for_job(300)
        promptfoo = self.status("promptfoo")
        self.assertEqual(promptfoo["status"], "needs_you", promptfoo)
        self.assertIn("about 1 GB", self.preflight.view(None, {"kind": None, "sent": False})["items"][3]["install"]["consent"]["body"])

        self.preflight.start_install("promptfoo", True)
        self.preflight.wait_for_job(1800)
        promptfoo = self.status("promptfoo")
        self.assertEqual(promptfoo["status"], "passed", promptfoo)
        self.assertTrue((self.home / "npm-cache").is_dir())

        self.preflight.start_check_all()
        self.preflight.wait_for_job(300)
        self.assertEqual(self.status("promptfoo")["status"], "passed", "the offline check must pass after download")
        elapsed = time.monotonic() - started
        print(f"\nreal download test: {elapsed:.0f} seconds", flush=True)
        (TMP_ROOT / "result.json").write_text(json.dumps({"seconds": round(elapsed)}), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
