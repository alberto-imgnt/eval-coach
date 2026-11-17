"""Verification receipts: a receipt is valid only while the working tree is unchanged."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("verify_receipt", ROOT / "tools" / "verify_receipt.py")
vr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vr)

PASS = [sys.executable, "-c", "print('Ran 3 tests')"]
FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("dist/\n", encoding="utf-8")
        self.change = self.root / "openspec" / "changes" / "demo"
        self.change.mkdir(parents=True)
        (self.change / "tasks.md").write_text("- [x] one\n", encoding="utf-8")

    def write(self, name="backend", command=PASS):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return vr.write(self.root, "demo", name, command)

    def status(self, *required):
        return vr.check(self.root, "demo", list(required))

    def test_missing_without_receipt(self):
        self.assertEqual(self.status()["status"], "missing")

    def test_valid_after_passing_run(self):
        self.assertEqual(self.write(), 0)
        result = self.status("backend")
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["checks"][0]["tests"], 3)

    def test_edit_makes_it_stale_and_names_the_file(self):
        self.write()
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        result = self.status()
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["changed"], ["M app.py"])

    def test_new_untracked_file_makes_it_stale(self):
        self.write()
        (self.root / "extra.py").write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(self.status()["status"], "stale")

    def test_openspec_and_ignored_files_do_not_matter(self):
        self.write()
        (self.change / "tasks.md").write_text("- [x] one\n- [x] two\n", encoding="utf-8")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "out.bin").write_bytes(b"x")
        self.assertEqual(self.status()["status"], "valid")

    def test_survives_archiving(self):
        self.write()
        archive = self.root / "openspec" / "changes" / "archive"
        archive.mkdir()
        self.change.rename(archive / "2026-11-17-demo")
        self.assertEqual(self.status()["status"], "valid")

    def test_failed_run_records_nothing(self):
        self.assertEqual(self.write(command=FAIL), 1)
        self.assertEqual(self.status()["status"], "missing")

    def test_failure_drops_an_earlier_pass_of_the_same_check(self):
        self.write()
        self.assertEqual(self.write(command=FAIL), 1)
        self.assertEqual(self.status()["status"], "missing")

    def test_edit_during_run_is_not_recorded(self):
        edit = [sys.executable, "-c", "open('app.py','a').write('#')"]
        self.assertEqual(self.write(command=edit), 5)
        self.assertEqual(self.status()["status"], "missing")

    def test_required_checks_must_all_be_recorded(self):
        self.write("backend")
        result = self.status("backend", "interface")
        self.assertEqual((result["status"], result["missing_checks"]), ("incomplete", ["interface"]))
        self.write("interface")
        self.assertEqual(self.status("backend", "interface")["status"], "valid")

    def test_new_tree_replaces_checks_from_an_old_tree(self):
        self.write("backend")
        (self.root / "app.py").write_text("print('v2')\n", encoding="utf-8")
        self.write("interface")
        receipt = json.loads((self.change / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual([c["name"] for c in receipt["checks"]], ["interface"])

    def test_real_index_is_untouched(self):
        self.write()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.root,
                                capture_output=True, text=True).stdout
        self.assertIn("?? app.py", status)


if __name__ == "__main__":
    unittest.main()
