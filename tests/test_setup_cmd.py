"""Runs the real packaging/setup.cmd under a scrubbed PATH and a temporary profile.

Nothing here touches the real %USERPROFILE%. Set EVAL_COACH_TEST_REAL_DOWNLOAD=1
to also run the one test that downloads from python.org.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import unittest
import zipapp
import zipfile
from pathlib import Path
from unittest import mock

from helpers import ROOT

SETUP = ROOT / "packaging" / "setup.cmd"
TMP_ROOT = ROOT / "tests" / ".tmp-setup"
PREFLIGHT = ROOT / "spikes" / "phase0-preflight"
ARCHIVE = PREFLIGHT / "downloads" / "python-3.13.17-embed-amd64.zip"
PRIVATE_FIXTURE = PREFLIGHT / "runtime" / "python-embed-3.13.17-nopth"
MANIFEST = json.loads((PREFLIGHT / "runtime-manifest.json").read_text(encoding="utf-8"))["python"]

SYSTEM_ROOT = os.environ["SystemRoot"]
CMD_EXE = os.path.join(SYSTEM_ROOT, "System32", "cmd.exe")
SHADOWED_TOOLS = ("curl", "tar", "certutil", "where", "ping", "powershell", "taskkill", "cmd")

STUB_MAIN = (
    "import json, os, sys\n"
    "with open(os.environ['EC_TEST_RECORD'], 'w', encoding='utf-8') as handle:\n"
    "    json.dump({'argv': sys.argv[1:], 'executable': sys.executable}, handle)\n"
    "sys.exit(int(os.environ.get('EC_TEST_EXIT', '0')))\n"
)

REAL_PROFILE_RUNTIME = Path(os.environ["USERPROFILE"]) / ".eval-coach" / "runtime"


def real_python_dir() -> Path:
    base = Path(getattr(sys, "_base_executable", sys.executable))
    return base.parent


def rmtree_with_retries(path: Path, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.25)


def setUpModule():
    TMP_ROOT.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    rmtree_with_retries(TMP_ROOT)


class Result:
    def __init__(self, proc, output):
        self.code = proc.returncode
        self.output = output


class SetupTestCase(unittest.TestCase):
    profile_name = "Plain User"

    def setUp(self):
        self.real_runtime_before = REAL_PROFILE_RUNTIME.exists()
        self.work = TMP_ROOT / f"{self.id().rsplit('.', 1)[-1]}-{os.getpid()}"
        self.work.mkdir(parents=True)
        self.addCleanup(rmtree_with_retries, self.work)
        self.profile = self.work / self.profile_name
        self.temp = self.profile / "AppData" / "Local" / "Temp"
        self.temp.mkdir(parents=True)
        self.install_dir = self.profile / "Downloads" / "eval-coach"
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.shadow_marker = self.work / "shadow-used.txt"
        self.record = self.work / "launched.json"
        self.make_shadows()
        self.put_package(self.install_dir)
        self.private_exe = self.profile / ".eval-coach" / "runtime" / "python" / "python.exe"
        self.runtime = self.private_exe.parent.parent

    def tearDown(self):
        self.assertEqual(self.real_runtime_before, REAL_PROFILE_RUNTIME.exists(),
                         "the real profile runtime folder must not change")

    def make_shadows(self):
        for tool in SHADOWED_TOOLS:
            (self.bin / f"{tool}.cmd").write_text(
                f'@echo {tool}>>"{self.shadow_marker}"\r\n@exit /b 99\r\n', encoding="ascii")

    def put_package(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SETUP, folder / "setup.cmd")
        source = self.work / "stub-src"
        source.mkdir(exist_ok=True)
        (source / "__main__.py").write_text(STUB_MAIN, encoding="utf-8")
        zipapp.create_archive(source, folder / "eval-coach.pyz")

    def run_setup(self, answers="", url=ARCHIVE.as_uri(), path_extra=(), script=None, extra_env=None, timeout=180):
        path = os.pathsep.join([str(self.bin), *[str(p) for p in path_extra]])
        env = {
            "SystemRoot": SYSTEM_ROOT,
            "windir": SYSTEM_ROOT,
            "SystemDrive": os.environ["SystemDrive"],
            "ComSpec": CMD_EXE,
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "PATH": path,
            "USERPROFILE": str(self.profile),
            "TEMP": str(self.temp),
            "TMP": str(self.temp),
            "EC_TEST_RECORD": str(self.record),
        }
        if url is not None:
            env["EVAL_COACH_PYTHON_URL"] = url
        if extra_env:
            env.update(extra_env)
        target = script or (self.install_dir / "setup.cmd")
        # A raw command line, quoted the way Explorer does it. subprocess would
        # leave a path with an ampersand but no spaces unquoted.
        command = f'"{CMD_EXE}" /d /c ""{target}""'
        # A file, not a pipe: set /p discards buffered lines when reading a pipe.
        answers_file = self.work / "answers.txt"
        answers_file.write_bytes(answers.encode("ascii"))
        with open(answers_file, "rb") as stdin:
            proc = subprocess.run(command, stdin=stdin, env=env, cwd=str(self.work),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output = proc.stdout.decode("mbcs", errors="replace")
        return Result(proc, output)

    def patch_setup(self, *replacements):
        """Edits this test's copy of setup.cmd to reach a branch that needs a broken machine."""
        target = self.install_dir / "setup.cmd"
        data = target.read_bytes()
        for old, new in replacements:
            self.assertIn(old.encode("ascii"), data)
            data = data.replace(old.encode("ascii"), new.encode("ascii"))
        target.write_bytes(data)

    def pin_hash_of(self, payload: bytes):
        self.patch_setup((MANIFEST["sha256"], hashlib.sha256(payload).hexdigest()))

    def launched(self):
        self.assertTrue(self.record.exists(), "eval-coach.pyz was not launched")
        return json.loads(self.record.read_text(encoding="utf-8"))

    def assert_no_shadow_used(self):
        used = self.shadow_marker.read_text(encoding="ascii") if self.shadow_marker.exists() else ""
        self.assertEqual("", used, "a tool was called through PATH instead of by full path")

    def assert_launched_with(self, python: Path):
        data = self.launched()
        self.assertEqual(["--python", str(python)], data["argv"])
        self.assertEqual(os.path.normcase(str(python)), os.path.normcase(data["executable"]))

    def assert_private_installed(self):
        self.assertTrue(self.private_exe.exists())
        self.assertFalse((self.private_exe.parent / "python313._pth").exists(), "the _pth file must be deleted")
        self.assertFalse((self.runtime / "python.new").exists())
        self.assertFalse((self.runtime / "python-embed-3.13.17.zip").exists())

    def assert_nothing_installed(self):
        self.assertFalse(self.private_exe.exists())
        if self.runtime.exists():
            self.assertEqual([], [p.name for p in self.runtime.iterdir()])

    def assert_consent_text(self, output):
        for phrase in ("Python 3.13.17", "about 11 MB", "about 22 MB", "No administrator rights",
                       str(self.runtime), "Free space on this drive"):
            self.assertIn(phrase, output)

    def assert_no_contact_instruction(self, output):
        self.assertNotRegex(output.lower(), r"\bcontact\b")
        self.assertNotRegex(output.lower(), r"facilitator|presenter|help ?desk")

    def copy_private_runtime(self):
        shutil.copytree(PRIVATE_FIXTURE, self.private_exe.parent)


class ScriptShapeTests(unittest.TestCase):
    def setUp(self):
        self.data = SETUP.read_bytes()
        self.text = self.data.decode("ascii")

    def test_uses_crlf_only(self):
        self.assertEqual(0, len(re.findall(rb"(?<!\r)\n", self.data)))

    def test_pinned_values_match_manifest(self):
        self.assertIn(f'set "EC_PY_SHA256={MANIFEST["sha256"]}"', self.text)
        self.assertIn(f'set "EC_PY_URL={MANIFEST["url"]}"', self.text)

    def test_local_archive_matches_pinned_hash(self):
        self.assertEqual(MANIFEST["sha256"], hashlib.sha256(ARCHIVE.read_bytes()).hexdigest())

    def test_hash_cannot_be_overridden_from_the_environment(self):
        self.assertEqual(1, len(re.findall(r'^set "EC_PY_SHA256=', self.text, re.M)))


class NoPythonTests(SetupTestCase):
    def test_no_python_installs_private_copy_and_launches(self):
        result = self.run_setup("Y\r\n")
        self.assertEqual(0, result.code, result.output)
        self.assert_consent_text(result.output)
        self.assert_private_installed()
        self.assert_launched_with(self.private_exe)
        self.assert_no_shadow_used()
        self.assert_no_contact_instruction(result.output)

    def test_declined_consent_exits_cleanly_with_next_step(self):
        result = self.run_setup("N\r\n")
        self.assertEqual(0, result.code, result.output)
        self.assert_consent_text(result.output)
        self.assertIn("Nothing was installed", result.output)
        self.assertIn("run setup.cmd again", result.output)
        self.assertIn("Company Portal or Software Center", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()
        self.assert_no_shadow_used()
        self.assert_no_contact_instruction(result.output)

    def test_no_answer_at_all_counts_as_declined(self):
        result = self.run_setup("")
        self.assertEqual(0, result.code, result.output)
        self.assertIn("Nothing was installed", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()

    def test_unclear_answer_asks_again(self):
        result = self.run_setup('maybe & "\r\nY\r\n')
        self.assertEqual(0, result.code, result.output)
        self.assertIn("Please type Y for yes or N for no.", result.output)
        self.assert_private_installed()

    def test_corrupted_archive_is_rejected_and_deleted(self):
        corrupted = self.work / "corrupted.zip"
        data = bytearray(ARCHIVE.read_bytes())
        data[len(data) // 2] ^= 0xFF
        corrupted.write_bytes(bytes(data))
        result = self.run_setup("Y\r\n", url=corrupted.as_uri())
        self.assertEqual(1, result.code, result.output)
        self.assertIn("failed its safety check", result.output)
        self.assertIn("It has been deleted", result.output)
        self.assertIn("cannot be turned off", result.output)
        self.assertIn("Company Portal or Software Center", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()
        self.assertTrue(corrupted.exists(), "the source copy must be left alone")
        self.assert_no_shadow_used()
        self.assert_no_contact_instruction(result.output)

    def test_failed_download_explains_the_next_step(self):
        missing = self.work / "does-not-exist.zip"
        result = self.run_setup("Y\r\n", url=missing.as_uri())
        self.assertEqual(1, result.code, result.output)
        self.assertIn("could not be downloaded", result.output)
        self.assertIn("Company Portal or Software Center", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()
        self.assert_no_contact_instruction(result.output)

    def test_timed_out_download_says_so(self):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        self.patch_setup(("--max-time 900", "--max-time 2"), ("--retry 2", "--retry 0"))
        result = self.run_setup("Y\r\n", url=f"http://127.0.0.1:{port}/python.zip")
        self.assertEqual(1, result.code, result.output)
        self.assertIn("timed out", result.output)
        self.assertIn("Company Portal or Software Center", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()
        self.assert_no_contact_instruction(result.output)

    def test_not_enough_disk_stops_before_asking(self):
        self.patch_setup(("%EC_FREE_MB% lss 50", "%EC_FREE_MB% lss 999999999"))
        result = self.run_setup("Y\r\n")
        self.assertEqual(1, result.code, result.output)
        self.assertIn("Not enough free disk space", result.output)
        self.assertIn("free up at least 50 MB", result.output)
        self.assertNotIn("Install it now", result.output)
        self.assert_nothing_installed()
        self.assert_no_contact_instruction(result.output)

    def test_file_removed_after_extract_blames_security_software(self):
        archive = self.work / "no-python-inside.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("readme.txt", "no python.exe in here")
        self.pin_hash_of(archive.read_bytes())
        result = self.run_setup("Y\r\n", url=archive.as_uri())
        self.assertEqual(1, result.code, result.output)
        self.assertIn("Antivirus", result.output)
        self.assertIn("Company Portal or Software Center", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()
        self.assert_no_contact_instruction(result.output)

    def test_unreadable_archive_with_matching_hash_cannot_be_unpacked(self):
        archive = self.work / "not-a-zip.zip"
        archive.write_bytes(b"this file is not an archive of any kind")
        self.pin_hash_of(archive.read_bytes())
        result = self.run_setup("Y\r\n", url=archive.as_uri())
        self.assertEqual(1, result.code, result.output)
        self.assertIn("could not be unpacked", result.output)
        self.assertIn("Company Portal or Software Center", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()
        self.assert_no_contact_instruction(result.output)

    def test_missing_pyz_explains_how_to_extract(self):
        (self.install_dir / "eval-coach.pyz").unlink()
        result = self.run_setup("Y\r\n")
        self.assertEqual(1, result.code, result.output)
        self.assertIn("Extract All", result.output)
        self.assert_nothing_installed()
        self.assert_no_contact_instruction(result.output)

    def test_app_failure_is_reported_with_its_code(self):
        self.copy_private_runtime()
        result = self.run_setup("", extra_env={"EC_TEST_EXIT": "7"})
        self.assertEqual(7, result.code, result.output)
        self.assertIn("eval-coach stopped because of a problem (code 7)", result.output)
        self.assertIn("run setup.cmd again", result.output)
        self.assert_no_contact_instruction(result.output)


class DetectionTests(SetupTestCase):
    def test_real_python_on_path_is_used_without_asking(self):
        python_dir = real_python_dir()
        self.assertNotIn("windowsapps", str(python_dir).lower())
        result = self.run_setup("", path_extra=[python_dir], url=(self.work / "never.zip").as_uri())
        self.assertEqual(0, result.code, result.output)
        self.assertNotIn("Install it now", result.output)
        self.assert_launched_with(python_dir / "python.exe")
        self.assertFalse(self.runtime.exists())
        self.assert_no_shadow_used()

    def test_windowsapps_stub_is_skipped_without_running(self):
        marker = self.work / "stub-ran.txt"
        stub_dir = self.work / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        stub_dir.mkdir(parents=True)
        for name in ("python", "python3", "py"):
            (stub_dir / f"{name}.cmd").write_text(f'@echo ran>>"{marker}"\r\n', encoding="ascii")
        result = self.run_setup("Y\r\n", path_extra=[stub_dir])
        self.assertEqual(0, result.code, result.output)
        self.assertFalse(marker.exists(), "a WindowsApps candidate was executed")
        self.assert_consent_text(result.output)
        self.assert_private_installed()
        self.assert_launched_with(self.private_exe)
        self.assert_no_shadow_used()

    def test_shim_that_prints_no_token_is_rejected(self):
        shim_dir = self.work / "shims"
        shim_dir.mkdir()
        (shim_dir / "python.cmd").write_text("@echo Python 3.12.0\r\n", encoding="ascii")
        result = self.run_setup("N\r\n", path_extra=[shim_dir])
        self.assertEqual(0, result.code, result.output)
        self.assertIn("Install it now", result.output)
        self.assertFalse(self.record.exists())

    def test_hung_candidate_times_out_and_moves_on(self):
        shim_dir = self.work / "hung"
        shim_dir.mkdir()
        (shim_dir / "python.cmd").write_text(
            f'@"{SYSTEM_ROOT}\\System32\\ping.exe" -n 45 127.0.0.1 >nul\r\n', encoding="ascii")
        started = time.monotonic()
        result = self.run_setup("N\r\n", path_extra=[shim_dir])
        self.assertLess(time.monotonic() - started, 40)
        self.assertEqual(0, result.code, result.output)
        self.assertIn("Install it now", result.output)

    def test_private_python_is_used_without_asking_or_downloading(self):
        self.copy_private_runtime()
        result = self.run_setup("", url=(self.work / "never.zip").as_uri())
        self.assertEqual(0, result.code, result.output)
        self.assertNotIn("Install it now", result.output)
        self.assertNotIn("Downloading", result.output)
        self.assert_launched_with(self.private_exe)
        self.assert_no_shadow_used()

    def test_damaged_private_python_is_replaced_after_asking(self):
        self.private_exe.parent.mkdir(parents=True)
        self.private_exe.write_bytes(b"not a program")
        (self.private_exe.parent / "leftover.txt").write_text("old", encoding="ascii")
        result = self.run_setup("Y\r\n")
        self.assertEqual(0, result.code, result.output)
        self.assertIn("damaged", result.output)
        self.assert_private_installed()
        self.assertFalse((self.private_exe.parent / "leftover.txt").exists())
        self.assert_launched_with(self.private_exe)


class AwkwardProfileTests(SetupTestCase):
    profile_name = "Ann & Bob (R&D) Smith"

    def setUp(self):
        super().setUp()
        self.weird_install = self.profile / "Downloads" / "eval-coach (1) & more"
        self.put_package(self.weird_install)
        self.weird_setup = self.weird_install / "setup.cmd"

    def test_install_and_launch(self):
        result = self.run_setup("Y\r\n", script=self.weird_setup)
        self.assertEqual(0, result.code, result.output)
        self.assert_consent_text(result.output)
        self.assert_private_installed()
        self.assert_launched_with(self.private_exe)
        self.assert_no_shadow_used()

    def test_private_python_already_present(self):
        self.copy_private_runtime()
        result = self.run_setup("", script=self.weird_setup, url=(self.work / "never.zip").as_uri())
        self.assertEqual(0, result.code, result.output)
        self.assertNotIn("Install it now", result.output)
        self.assert_launched_with(self.private_exe)

    def test_declined(self):
        result = self.run_setup("N\r\n", script=self.weird_setup)
        self.assertEqual(0, result.code, result.output)
        self.assertIn("Nothing was installed", result.output)
        self.assert_nothing_installed()

    def test_corrupted_archive(self):
        corrupted = self.work / "corrupted.zip"
        corrupted.write_bytes(b"this is not the real archive")
        result = self.run_setup("Y\r\n", script=self.weird_setup, url=corrupted.as_uri())
        self.assertEqual(1, result.code, result.output)
        self.assertIn("failed its safety check", result.output)
        self.assertFalse(self.record.exists())
        self.assert_nothing_installed()

    def test_python_on_a_path_with_special_characters(self):
        python_dir = self.work / "Py & Tools (x64)"
        shutil.copytree(PRIVATE_FIXTURE, python_dir)
        result = self.run_setup("", script=self.weird_setup, path_extra=[python_dir],
                                url=(self.work / "never.zip").as_uri())
        self.assertEqual(0, result.code, result.output)
        self.assert_launched_with(python_dir / "python.exe")


class AccentedProfileTests(SetupTestCase):
    profile_name = "Jos\u00e9 N\u00fa\u00f1ez"

    def test_install_and_launch(self):
        result = self.run_setup("Y\r\n")
        self.assertEqual(0, result.code, result.output)
        self.assert_private_installed()
        self.assert_launched_with(self.private_exe)


class RealDownloadTests(SetupTestCase):
    @unittest.skipUnless(os.environ.get("EVAL_COACH_TEST_REAL_DOWNLOAD") == "1",
                         "set EVAL_COACH_TEST_REAL_DOWNLOAD=1 to download from python.org")
    def test_real_url_and_hash(self):
        result = self.run_setup("Y\r\n", url=None, timeout=600)
        self.assertEqual(0, result.code, result.output)
        self.assertIn("https://www.python.org/ftp/python/3.13.17/", result.output)
        self.assert_private_installed()
        self.assert_launched_with(self.private_exe)
        self.assert_no_shadow_used()


class PythonArgumentTests(unittest.TestCase):
    def run_main(self, argv):
        from eval_coach import __main__ as entry
        with mock.patch.object(entry, "Engine") as engine, \
                mock.patch.object(entry, "AppServer"), \
                mock.patch.object(entry, "TerminalManager"), \
                mock.patch.object(entry, "webbrowser"), \
                mock.patch("builtins.print"):
            self.assertEqual(0, entry.main(argv))
        return engine.return_value

    def test_python_argument_is_stored(self):
        path = r"C:\Users\Ann & Bob (R&D)\.eval-coach\runtime\python\python.exe"
        engine = self.run_main(["--no-browser", "--python", path])
        self.assertEqual(path, engine.python_path)

    def test_defaults_to_the_running_interpreter(self):
        engine = self.run_main(["--no-browser"])
        self.assertEqual(sys.executable, engine.python_path)


if __name__ == "__main__":
    unittest.main()
