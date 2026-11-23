"""The Mac launcher (packaging/launcher.sh). The static checks run everywhere; the runs need macOS (its own system
tools) and use fake Python programs, never a real download or an AI."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import threading
import unittest
import zipfile
from pathlib import Path

import helpers

ROOT = helpers.ROOT
sys.path.insert(0, str(ROOT / "tools"))

import build_pyz  # noqa: E402

LAUNCHER = ROOT / "packaging" / "launcher.sh"
MAC_START = ROOT / "packaging" / "mac-start.txt"
SETUP_DOC = ROOT / "docs" / "SETUP.md"
MANIFEST = json.loads((ROOT / "packaging" / "runtime-manifest.json").read_text(encoding="utf-8"))
MAC = sys.platform == "darwin"
PRIVATE = Path(".eval-coach") / "runtime" / "python" / "bin" / "python3"

FAKE_PYTHON = textwrap.dedent("""\
    #!/bin/sh
    if [ "$1" = "-c" ]; then
      token=$(printf '%s' "$2" | /usr/bin/sed "s/.*print('\\(EC[0-9]*\\)').*/\\1/")
      echo "$token"
      echo "$0"
      exit 0
    fi
    echo "FAKE-PYTHON-STARTED $*"
    exit ${FAKE_RC:-0}
""")


def script_text():
    return LAUNCHER.read_text(encoding="ascii")


def code_lines():
    """The script's commands: no comments and no message text."""
    return "\n".join(l for l in script_text().splitlines()
                     if not l.lstrip().startswith("#") and not re.match(r"\s*say \"", l))


def say_lines(text):
    """The text of every message the launcher shows."""
    return re.findall(r'^\s*(?:say|printf) (["\'])(.*)\1\s*$', text, re.M)


class StaticChecks(unittest.TestCase):
    def test_plain_ascii_with_lf_endings_and_a_marker_at_the_end(self):
        data = LAUNCHER.read_bytes()
        self.assertNotIn(b"\r", data)
        self.assertEqual([b for b in data if b > 127], [])
        self.assertTrue(data.startswith(b"#!/bin/bash\n"))
        self.assertTrue(data.endswith(build_pyz.MAC_LAUNCHER_MARKER))

    def test_the_last_command_before_the_marker_is_an_exit(self):
        lines = script_text().rstrip("\n").splitlines()
        self.assertEqual(lines[-1], "# ===== eval-coach.pyz follows =====")
        self.assertTrue(lines[-2].startswith("exit"), lines[-2])

    def test_it_never_uses_eval_or_bash_4_features(self):
        code = code_lines()
        self.assertIsNone(re.search(r"(?<![\w-])eval(?![\w-])", code))
        self.assertIsNone(re.search(r"declare -A|mapfile|readarray|\$\{[A-Za-z_]+(,,|\^\^)", code))

    def test_system_tools_are_called_by_full_path(self):
        code = code_lines()
        for tool in ("curl", "tar", "shasum", "sw_vers", "uname", "sysctl", "mktemp"):
            for match in re.finditer(r"(?<![\w/.-])" + tool + r"(?=\s)", code):
                self.fail(f"{tool} is called without a full path near: {code[match.start():match.start() + 40]!r}")

    def test_messages_never_name_a_file(self):
        messages = [text for _, text in say_lines(script_text())]
        self.assertGreater(len(messages), 40)
        for text in messages:
            for banned in (".command", ".cmd", "launcher", "setup.cmd", ".sh", ".pyz"):
                self.assertNotIn(banned, text)

    def test_every_failure_says_what_to_do_next(self):
        text = script_text()
        for name in re.findall(r"^(fail_\w+)\(\) \{", text, re.M):
            body = text.split(name + "() {", 1)[1].split("\n}\n", 1)[0]
            self.assertRegex(body, r"What to do next", name)
            self.assertIn("stop_with", body, name)

    def test_there_are_no_contact_someone_instructions(self):
        text = script_text().lower()
        for banned in ("contact", "call us", "help desk", "administrator rights are required"):
            self.assertNotIn(banned, text)

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_bash_accepts_the_syntax(self):
        result = subprocess.run([shutil.which("bash"), "-n", str(LAUNCHER)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_built_launcher_and_zip(self):
        stub = io.BytesIO()
        with zipfile.ZipFile(stub, "w") as archive:
            archive.writestr("__main__.py", "print('stub')\n")
        built = build_pyz.assemble_mac_launcher(build_pyz.stamp_sh(LAUNCHER.read_bytes(), MANIFEST), stub.getvalue())
        script, marker, archive = built.partition(build_pyz.MAC_LAUNCHER_MARKER)
        self.assertEqual(marker, build_pyz.MAC_LAUNCHER_MARKER)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(archive)))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "eval-coach-mac.zip"
            build_pyz.build_mac_zip(built, target)
            with zipfile.ZipFile(target) as bundle:
                self.assertEqual(bundle.namelist(), ["eval-coach.command"])
                info = bundle.getinfo("eval-coach.command")
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o755)
                self.assertEqual(bundle.read("eval-coach.command"), built)


class InstructionsTest(unittest.TestCase):
    """The Mac start instructions: what they say, in order, and what they must never say."""

    def texts(self):
        setup = SETUP_DOC.read_text(encoding="utf-8")
        start = setup.index("### Starting it for the first time on a Mac")
        end = setup.index("\n## ", start)
        return {"packaging/mac-start.txt": MAC_START.read_text(encoding="utf-8"), "docs/SETUP.md": setup[start:end]}

    def test_the_steps_come_in_order(self):
        for name, text in self.texts().items():
            right_click = text.lower().index("right-click")
            open_anyway = text.index("Open Anyway")
            terminal_line = text.index("bash ")
            self.assertLess(right_click, open_anyway, name)
            self.assertLess(open_anyway, terminal_line, name)
            self.assertIn("Privacy & Security", text, name)
            self.assertIn("macOS 15", text, name)

    def test_there_is_one_line_to_paste_into_terminal(self):
        for name, text in self.texts().items():
            self.assertRegex(text, r"bash ~/Downloads/eval-coach\.command", name)

    def test_no_advice_that_weakens_macos(self):
        for name, text in self.texts().items():
            lowered = text.lower()
            for banned in ("sudo", "xattr", "spctl", "master-disable", "turn off gatekeeper", "disable gatekeeper",
                           "anywhere", "chmod", "quarantine"):
                self.assertNotIn(banned, lowered, f"{name} mentions {banned}")

    def test_plain_words(self):
        for name, text in self.texts().items():
            for banned in ("presenter", "facilitator", "handout", "neighbor", "contact someone"):
                self.assertNotIn(banned, text.lower(), name)


@unittest.skipUnless(MAC, "the launcher runs only on macOS, which has the system tools it calls")
class RunTheLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ec-launcher-")).resolve()
        self.addCleanup(self.cleanup)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.work = self.tmp / "tmp"
        self.work.mkdir()
        self.folder = self.tmp / "install"
        self.folder.mkdir()

    def cleanup(self):
        for path in self.tmp.rglob("*"):
            try:
                path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers ---------------------------------------------------------------

    def fake_python(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FAKE_PYTHON, encoding="ascii")
        path.chmod(0o755)
        return path

    def archive(self, name="python.tar.gz"):
        """A python-build-standalone shaped archive: python/bin/python3 is a fake Python. Returns (path, sha256)."""
        source = self.tmp / "archive-src" / "python" / "bin"
        source.mkdir(parents=True, exist_ok=True)
        self.fake_python(source / "python3")
        target = self.tmp / name
        with tarfile.open(target, "w:gz") as bundle:
            bundle.add(str(self.tmp / "archive-src" / "python"), arcname="python")
        return target, hashlib.sha256(target.read_bytes()).hexdigest()

    def launcher(self, sha=None, name="eval-coach.command", folder=None, extra=b""):
        """The built launcher with a stub app archive. `sha` replaces the pinned hash of both chips."""
        script = build_pyz.stamp_sh(LAUNCHER.read_bytes(), MANIFEST)
        if sha:
            script = re.sub(rb'(EC_PY_(?:ARM64|X64)_SHA256=")[0-9a-f]{64}(")', rb"\g<1>" + sha.encode() + rb"\g<2>", script)
        stub = io.BytesIO()
        with zipfile.ZipFile(stub, "w") as archive:
            archive.writestr("__main__.py", "print('stub')\n")
        folder = folder or self.folder
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(build_pyz.assemble_mac_launcher(script, stub.getvalue()) + extra)
        path.chmod(0o755)
        return path

    def run_launcher(self, path, stdin="", args=(), env_extra=None, home=None):
        env = {"HOME": str(home or self.home), "PATH": f"{self.bin}:/bin", "TMPDIR": str(self.work) + "/",
               "EVAL_COACH_PATH_ONLY": "1", "LANG": "en_US.UTF-8"}
        env.update(env_extra or {})
        return subprocess.run(["/bin/bash", str(path)] + list(args), input=stdin, capture_output=True, text=True,
                              env=env, timeout=180, cwd=str(path.parent))

    # --- Python already there --------------------------------------------------

    def test_python_on_the_path_starts_the_app_without_a_question(self):
        self.fake_python(self.bin / "python3")
        path = self.launcher()
        result = self.run_launcher(path, args=["--no-browser"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"FAKE-PYTHON-STARTED -B {path} --python {self.bin}/python3 --no-browser", result.stdout)
        self.assertNotIn("Install it now", result.stdout)

    def test_an_unusual_folder_name_works(self):
        self.fake_python(self.bin / "python3")
        weird = self.tmp / "My Files & (Old)! 'x'"
        path = self.launcher(folder=weird)
        result = self.run_launcher(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"-B {path} ", result.stdout)

    def test_an_unusual_home_folder_works(self):
        weird_home = self.tmp / "Jo's Home & (Old)!"
        weird_home.mkdir()
        self.fake_python(weird_home / PRIVATE)
        result = self.run_launcher(self.launcher(), home=weird_home)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("FAKE-PYTHON-STARTED", result.stdout)

    def test_a_read_only_folder_works(self):
        self.fake_python(self.bin / "python3")
        path = self.launcher()
        self.folder.chmod(0o555)
        result = self.run_launcher(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_run_through_a_relative_path(self):
        self.fake_python(self.bin / "python3")
        path = self.launcher()
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/bin", "TMPDIR": str(self.work), "EVAL_COACH_PATH_ONLY": "1"}
        result = subprocess.run(["/bin/bash", path.name], capture_output=True, text=True, env=env, timeout=120,
                                cwd=str(self.folder))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"-B {path} ", result.stdout)

    def test_the_apps_exit_code_is_shown_and_returned(self):
        self.fake_python(self.bin / "python3")
        result = self.run_launcher(self.launcher(), env_extra={"FAKE_RC": "3"})
        self.assertEqual(result.returncode, 3)
        self.assertIn("code 3", result.stdout)
        self.assertIn("start eval-coach again", result.stdout)

    def test_no_working_python_on_the_path_is_ignored(self):
        broken = self.bin / "python3"
        broken.write_text("#!/bin/sh\necho nothing useful\n", encoding="ascii")
        broken.chmod(0o755)
        self.fake_python(self.home / PRIVATE)
        result = self.run_launcher(self.launcher())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"--python {self.home / PRIVATE}", result.stdout)

    def test_apples_stub_is_not_run_without_the_command_line_tools(self):
        check = subprocess.run(["/bin/bash", "-c", f'EC_SOURCE_ONLY=1; . "{LAUNCHER}"; apple_stub_unsafe /usr/local/bin/python3'],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(check.returncode, 1, "only /usr/bin/python3 is Apple's stub")
        tools_installed = subprocess.run(["/usr/bin/xcode-select", "-p"], capture_output=True).returncode == 0
        stub = subprocess.run(["/bin/bash", "-c", f'EC_SOURCE_ONLY=1; . "{LAUNCHER}"; apple_stub_unsafe /usr/bin/python3'],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(stub.returncode, 1 if tools_installed else 0)

    def test_a_link_to_apples_stub_is_the_stub_too(self):
        link = self.tmp / "python3"
        os.symlink("/usr/bin/python3", str(link))
        tools_installed = subprocess.run(["/usr/bin/xcode-select", "-p"], capture_output=True).returncode == 0
        check = subprocess.run(["/bin/bash", "-c", f'EC_SOURCE_ONLY=1; . "{LAUNCHER}"; apple_stub_unsafe "{link}"'],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(check.returncode, 1 if tools_installed else 0)

    def test_the_python_that_answered_is_the_one_started(self):
        real = self.tmp / "real" / "python3"
        self.fake_python(real)
        shim = self.bin / "python3"
        shim.write_text(FAKE_PYTHON.replace('echo "$0"', f'echo "{real}"').replace(
            'echo "FAKE-PYTHON-STARTED', 'echo "SHIM-STARTED'), encoding="ascii")
        shim.chmod(0o755)
        result = self.run_launcher(self.launcher())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"--python {real}", result.stdout)
        self.assertNotIn("SHIM-STARTED", result.stdout)

    def test_a_python_that_exits_with_an_error_is_not_used(self):
        failing = self.bin / "python3"
        failing.write_text(FAKE_PYTHON.replace("exit 0", "exit 1", 1), encoding="ascii")
        failing.chmod(0o755)
        self.fake_python(self.home / PRIVATE)
        result = self.run_launcher(self.launcher())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"--python {self.home / PRIVATE}", result.stdout)

    # --- the private copy ------------------------------------------------------

    def test_the_private_copy_from_an_earlier_run_is_used_without_a_download(self):
        self.fake_python(self.home / PRIVATE)
        result = self.run_launcher(self.launcher())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"--python {self.home / PRIVATE}", result.stdout)
        self.assertNotIn("Install it now", result.stdout)
        self.assertNotIn("Downloading", result.stdout)

    def test_a_newer_file_keeps_the_private_python_and_the_progress(self):
        self.fake_python(self.home / PRIVATE)
        progress = self.home / ".eval-coach" / "progress.txt"
        progress.write_text("done", encoding="utf-8")
        first = self.launcher()
        before = first.read_bytes()
        self.assertEqual(self.run_launcher(first).returncode, 0)
        newer = self.launcher(extra=b"newer build")
        self.assertNotEqual(before, newer.read_bytes())
        result = self.run_launcher(newer)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(progress.read_text(encoding="utf-8"), "done")
        self.assertTrue((self.home / PRIVATE).is_file())

    # --- consent and the download ----------------------------------------------

    def consent_run(self, stdin, sha_matches=True, extra_env=None):
        archive, sha = self.archive()
        path = self.launcher(sha=sha if sha_matches else None)
        env = {"EVAL_COACH_PYTHON_URL": archive.as_uri()}
        env.update(extra_env or {})
        return self.run_launcher(path, stdin=stdin, env_extra=env)

    def test_consent_is_shown_before_anything_downloads(self):
        result = self.consent_run("y\n")
        out = result.stdout
        for needed in ("What:", "Size:", "Where:", "Download address:", "Free space on this drive", "No administrator rights"):
            self.assertIn(needed, out)
        self.assertLess(out.index("Download address:"), out.index("Install it now"))
        self.assertLess(out.index("Install it now"), out.index("Downloading"))

    def test_yes_downloads_checks_unpacks_and_starts_the_app(self):
        result = self.consent_run("y\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Python 3.13.18 is installed.", result.stdout)
        self.assertIn("FAKE-PYTHON-STARTED", result.stdout)
        self.assertTrue((self.home / PRIVATE).is_file())
        runtime = self.home / ".eval-coach" / "runtime"
        self.assertEqual(sorted(p.name for p in runtime.iterdir()), ["python"], "no archive or work folder is left")
        self.assertEqual(list(self.work.iterdir()), [], "the temporary folder is removed")

    def test_no_declines_and_changes_nothing(self):
        for answer in ("n\n", "no\n", "", "N\n"):
            with self.subTest(answer=answer):
                result = self.consent_run(answer)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Nothing was installed", result.stdout)
                self.assertNotIn("Downloading", result.stdout)
                self.assertFalse((self.home / ".eval-coach").exists())
                self.assertIn("start eval-coach again", result.stdout)

    def test_unclear_answers_three_times_count_as_no(self):
        result = self.consent_run("maybe\nperhaps\nwhat\ny\n")
        self.assertIn("Nothing was installed", result.stdout)
        self.assertEqual(result.stdout.count("Please type Y for yes or N for no."), 2)
        self.assertNotIn("Downloading", result.stdout)

    def test_an_unclear_answer_then_yes_is_asked_again(self):
        result = self.consent_run("hm\nyes\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is installed", result.stdout)

    def test_a_wrong_hash_deletes_the_file_and_installs_nothing(self):
        result = self.consent_run("y\n", sha_matches=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("failed its safety check", result.stdout)
        self.assertIn("This check cannot be turned off", result.stdout)
        self.assertFalse((self.home / PRIVATE).exists())
        runtime = self.home / ".eval-coach" / "runtime"
        self.assertEqual(list(runtime.iterdir()) if runtime.exists() else [], [], "the file was deleted")

    def test_an_environment_value_cannot_change_the_required_hash(self):
        archive, sha = self.archive()
        path = self.launcher()  # keeps the real pinned hashes
        env = {"EVAL_COACH_PYTHON_URL": archive.as_uri(), "EC_SHA256": sha, "EC_PY_ARM64_SHA256": sha,
               "EC_PY_X64_SHA256": sha, "EVAL_COACH_PYTHON_SHA256": sha}
        result = self.run_launcher(path, stdin="y\n", env_extra=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("failed its safety check", result.stdout)
        self.assertFalse((self.home / PRIVATE).exists())

    def test_a_blocked_download_says_what_to_do_next(self):
        path = self.launcher()
        result = self.run_launcher(path, stdin="y\n", env_extra={"EVAL_COACH_PYTHON_URL": (self.tmp / "missing.tar.gz").as_uri()})
        self.assertEqual(result.returncode, 1)
        self.assertIn("Nothing was installed", result.stdout)
        self.assertIn("What to do next", result.stdout)
        self.assertNotIn("eval-coach.command", result.stdout)

    # --- two windows ----------------------------------------------------------

    @property
    def lock(self):
        return self.home / ".eval-coach" / "runtime" / "install.lock"

    def test_a_lock_left_by_a_window_that_is_gone_is_replaced(self):
        gone = subprocess.Popen(["/usr/bin/true"])
        gone.wait()
        self.lock.mkdir(parents=True)
        (self.lock / "pid").write_text(f"{gone.pid}\n", encoding="ascii")
        result = self.consent_run("y\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is installed", result.stdout)
        self.assertFalse(self.lock.exists(), "the lock is given back")

    def test_a_second_window_waits_and_then_uses_the_python_the_first_one_installed(self):
        archive, sha = self.archive()
        path = self.launcher(sha=sha)
        holder = subprocess.Popen(["/bin/sleep", "120"])
        self.addCleanup(holder.kill)
        self.lock.mkdir(parents=True)
        (self.lock / "pid").write_text(f"{holder.pid}\n", encoding="ascii")
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/bin", "TMPDIR": str(self.work) + "/",
               "EVAL_COACH_PATH_ONLY": "1", "LANG": "en_US.UTF-8", "EVAL_COACH_PYTHON_URL": archive.as_uri()}
        window = subprocess.Popen(["/bin/bash", str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, env=env, cwd=str(path.parent))
        watchdog = threading.Timer(90, window.kill)
        watchdog.start()
        self.addCleanup(watchdog.cancel)
        window.stdin.write("y\n")
        window.stdin.flush()
        seen = ""
        while "Waiting for it to finish" not in seen:
            line = window.stdout.readline()
            self.assertNotEqual(line, "", "the window ended before it waited: " + seen)
            seen += line
        self.fake_python(self.home / PRIVATE)  # the first window finishes its install ...
        shutil.rmtree(str(self.lock))  # ... and gives the lock back
        rest, _ = window.communicate(timeout=60)
        self.assertEqual(window.returncode, 0, seen + rest)
        self.assertIn("installed by another eval-coach window", rest)
        self.assertNotIn("Downloading", rest)
        self.assertIn(f"--python {self.home / PRIVATE}", rest)

    def test_the_chip_decides_which_build_is_offered(self):
        def pick(machine, translated):
            code = f'EC_SOURCE_ONLY=1; . "{LAUNCHER}"; pick_pin {machine} {translated}; printf "%s" "$EC_SHA256"'
            return subprocess.run(["/bin/bash", "-c", code], capture_output=True, text=True, timeout=30).stdout

        python = MANIFEST["mac"]["python"]
        self.assertEqual(pick("arm64", "0"), python["arm64"]["sha256"])
        self.assertEqual(pick("x86_64", "0"), python["x86_64"]["sha256"])
        self.assertEqual(pick("x86_64", "1"), python["arm64"]["sha256"], "under Rosetta the Mac is Apple Silicon")

    def test_old_macos_versions_are_refused(self):
        def at_least(version):
            code = f'EC_SOURCE_ONLY=1; . "{LAUNCHER}"; macos_at_least {version} 13'
            return subprocess.run(["/bin/bash", "-c", code], capture_output=True, timeout=30).returncode == 0

        self.assertTrue(at_least("13.0"))
        self.assertTrue(at_least("15.1"))
        self.assertFalse(at_least("12.7.4"))
        self.assertFalse(at_least("11.7.10"))
        self.assertFalse(at_least("10.15.7"))


if __name__ == "__main__":
    unittest.main()
