"""Project creation, kit writing, blind/isolated folders, and the sealed answer key."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import time
from pathlib import Path

from . import resources
from . import state as store

SKILL_PREFIX = "kit/skills/"
AGENT_PROVIDER = SKILL_PREFIX + "build-promptfoo-config/agent-provider.js"
NORTHWIND_DIR = "kit/northwind/"
NORTHWIND_PROMPT = "kit/northwind/northwind-prompt-v0.md"
NORTHWIND_TEST_CASES = "kit/northwind/northwind-test-cases-reference.md"
FIXTURES_SKILL = SKILL_PREFIX + "make-eval-fixtures/SKILL.md"
FIXTURE_NAMES = ("fixture-bad.txt", "fixture-polished-but-wrong.txt")
KEY_NAME = "answer-key.md"
HOOK_FILES = {"update.txt": "kit/northwind/fixture-polished-but-wrong.txt",
              "requirements.md": "kit/lessons/hook/requirements.md"}
DEMO_FILES = {"test-cases.md": "kit/lessons/demo/test-cases.md",
              "output.txt": "kit/lessons/demo/output.txt",
              "skills/build-eval-script/SKILL.md": "kit/skills/build-eval-script/SKILL.md"}
# Part 1 keeps its own work under <project>\part-1\: a prompt and an output for each CLI run, and the own-work pair.
PART1_DIR = "part-1"
PART1_FILES = {"cold": ("prompt-cold.md", "output-cold.txt"), "rewrite": ("prompt-framework.md", "output-framework.txt")}
PART1_OWN_FILES = {"before": "own-before.md", "after": "own-after.md"}
PART1_NOTES = "kit/part1/rough-notes.txt"
# Part 2 keeps the participant's worksheet and test case file under <project>\part-2\. It runs nothing, so it has no scratch folder.
PART2_DIR = "part-2"
PART2_FILES = {"worksheet": "worksheet.json", "test_cases": "test-cases.md"}

_CATCH_UP = re.compile(rb"(?im)^[ \t]*<!--\s*catch-up copy.*?-->[ \t]*\r?\n(?:[ \t]*\r?\n)?")


class ProjectError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def sealed_id(project_path):
    norm = os.path.normcase(os.path.abspath(str(project_path)))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


class Paths:
    """Every location the app uses for one project."""

    def __init__(self, home, project):
        self.home = Path(home)
        self.project = Path(project)
        self.blind = self.home / "blind"
        self.blind_prompt = self.blind / "prompt.md"
        self.blind_output = self.blind / "output.txt"
        self.fixtures_work = self.home / "fixtures-work"
        self.work_fixtures = self.fixtures_work / "fixtures"
        self.key_work = self.home / "key-work"
        self.key_work_fixtures = self.key_work / "fixtures"
        self.key_work_key = self.key_work_fixtures / KEY_NAME
        self.sealed_dir = self.home / "sealed" / sealed_id(project)
        self.sealed_key = self.sealed_dir / KEY_NAME
        self.app_settings = self.home / "app.json"
        self.learning = self.project / ".learning"
        self.progress_file = self.learning / "progress.json"
        self.results_dir = self.learning / "results"
        self.test_cases = self.project / "test-cases.md"
        self.prompt = self.project / "prompt-v0.md"
        self.check_py = self.project / "check.py"
        self.config_yaml = self.project / "promptfooconfig.yaml"
        self.live_config = self.project / "promptfooconfig.live.yaml"
        self.agent_provider = self.project / "agent-provider.js"
        self.runs = self.project / "runs"
        self.fixtures = self.project / "fixtures"
        self.examples = self.project / "examples"
        self.iteration_log = self.project / "iteration-log.md"
        self.project_key = self.fixtures / KEY_NAME
        self.hook_work = self.home / "hook"
        self.hook_output = self.hook_work / "output.txt"
        self.hook_runs = self.learning / "hook"
        self.demo_work = self.home / "demo"
        self.demo_check = self.demo_work / "check.py"
        self.practice_root = self.home / "practice"
        self.practice_runs = self.learning / "practice"
        self.part1 = self.project / PART1_DIR
        self.part1_root = self.home / "part1"
        self.part2 = self.project / PART2_DIR

    def part2_file(self, which):
        return self.part2 / PART2_FILES[which]

    def part1_prompt(self, step):
        return self.part1 / PART1_FILES[step][0]

    def part1_output(self, step):
        return self.part1 / PART1_FILES[step][1]

    def part1_work(self, step):
        """The scratch folder of a Part 1 run: it holds only prompt.md and what the CLI saves."""
        return self.part1_root / step

    def part1_own(self, which):
        return self.part1 / PART1_OWN_FILES[which]

    def practice_work(self, activity_id):
        return self.practice_root / activity_id

    def practice_output(self, activity_id):
        """Where the app keeps what the practice CLI saved, so a restart cannot lose it."""
        return self.practice_runs / f"{activity_id}.txt"

    def run_file(self, n):
        return self.runs / f"run-{n}.txt"

    def checker(self, track="script"):
        """The file that holds the checks: check.py, or promptfooconfig.yaml on the promptfoo track."""
        return self.config_yaml if track == "promptfoo" else self.check_py

    def hook_run_file(self, n):
        return self.hook_runs / f"run-{n}.txt"


def default_home():
    return os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".eval-coach")


def default_project_path():
    return os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), "eval-project")


def clean_path(text):
    """Tidy a path a person pasted: surrounding quotes, ~, and %VARS%."""
    if not isinstance(text, str):
        return ""
    text = text.strip().strip('"').strip("'").strip()
    return os.path.expandvars(os.path.expanduser(text)) if text else ""


def _inside(child, parent):
    child = os.path.normcase(os.path.abspath(str(child)))
    parent = os.path.normcase(os.path.abspath(str(parent)))
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives
        return False


def validate_project_path(home, project):
    if not Path(project).is_absolute():
        raise ProjectError("bad_project_path", "Enter the full path of the project folder, for example C:\\Users\\you\\eval-project.")
    if _inside(project, home) or _inside(home, project):
        raise ProjectError(
            "bad_project_path",
            "Choose a project folder that is separate from the app's own storage folder, "
            "so the blind folder really cannot see your project.")
    if Path(project).exists() and not Path(project).is_dir():
        raise ProjectError("bad_project_path", "That path is a file, not a folder.")


def _write_new(path, data):
    """Create path with data. An existing file is left alone."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(str(path), "xb") as f:
            f.write(data)
    except FileExistsError:
        pass


def strip_catch_up_comment(data):
    return _CATCH_UP.sub(b"", data, count=1)


def _read_own_file(path_text, label):
    path = clean_path(path_text)
    if not path or not os.path.isfile(path):
        raise ProjectError("missing_file", f"Your {label} file was not found. Check the path: {path_text!r}.")
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as exc:
        raise ProjectError("missing_file", f"Your {label} file could not be read: {exc}.") from exc


def create_project(paths, starter, prompt_path=None, test_cases_path=None, own_data=None):
    """Write the kit into a new project. Existing participant files are never overwritten.

    own_data ({"prompt": bytes, "test_cases": bytes}) is what the import checks already read from the
    participant's files, so the copy is of exactly what was checked.
    """
    if starter == "northwind":
        prompt_data = strip_catch_up_comment(resources.read_bytes(NORTHWIND_PROMPT))
        cases_data = strip_catch_up_comment(resources.read_bytes(NORTHWIND_TEST_CASES))
    elif starter == "own" and own_data is not None:
        prompt_data, cases_data = own_data["prompt"], own_data["test_cases"]
    elif starter == "own":
        prompt_data = None if not prompt_path and paths.prompt.is_file() \
            else _read_own_file(prompt_path, "prompt")
        cases_data = None if not test_cases_path and paths.test_cases.is_file() \
            else _read_own_file(test_cases_path, "test cases")
    else:
        raise ProjectError("bad_starter", 'Pick either "northwind" or "own" as your starting point.')

    for folder in (paths.project, paths.runs, paths.fixtures, paths.examples, paths.learning):
        folder.mkdir(parents=True, exist_ok=True)
    for rel in resources.list_files(SKILL_PREFIX.rstrip("/")):
        _write_new(paths.project / "skills" / rel[len(SKILL_PREFIX):], resources.read_bytes(rel))
    if prompt_data is not None:
        _write_new(paths.prompt, prompt_data)
    if cases_data is not None:
        _write_new(paths.test_cases, cases_data)


def _make_writable(root):
    for folder, dirs, files in os.walk(str(root)):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(folder, name), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except OSError:
                pass


def clear_dir(path):
    """Empty a folder the app owns. A just-killed process can hold it briefly, so retry."""
    path = Path(path)
    for attempt in range(20):
        try:
            if path.exists():
                _make_writable(path)
                shutil.rmtree(str(path))
            path.mkdir(parents=True, exist_ok=True)
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.1)


def prepare_blind(paths):
    """Clear the blind folder and leave only prompt.md in it."""
    if not paths.prompt.is_file():
        raise ProjectError("missing_file", "prompt-v0.md was not found in your project folder.")
    clear_dir(paths.blind)
    store.write_bytes_atomic(paths.blind_prompt, paths.prompt.read_bytes())


def prepare_fixtures_work(paths):
    """Clear the fixtures folder and leave only what the fixtures skill may read."""
    if not paths.test_cases.is_file() or not paths.prompt.is_file():
        raise ProjectError("missing_file", "test-cases.md and prompt-v0.md must both be in your project folder.")
    clear_dir(paths.fixtures_work)
    store.write_bytes_atomic(paths.fixtures_work / "test-cases.md", paths.test_cases.read_bytes())
    store.write_bytes_atomic(paths.fixtures_work / "prompt-v0.md", paths.prompt.read_bytes())
    store.write_bytes_atomic(paths.fixtures_work / "skills" / "make-eval-fixtures" / "SKILL.md",
                             resources.read_bytes(FIXTURES_SKILL))


def write_example_fixtures(paths):
    """Write the two bundled Northwind fixtures where the fixtures CLI would have written them.

    Only these two files are written. The Northwind answer key stays in the kit and is never copied.
    """
    for name in FIXTURE_NAMES:
        store.write_bytes_atomic(paths.work_fixtures / name, resources.read_bytes(NORTHWIND_DIR + name))


def prepare_key_work(paths):
    """Clear the answer key folder and leave only what the answer key step may read."""
    sources = [paths.test_cases, paths.prompt] + [paths.fixtures / name for name in FIXTURE_NAMES]
    if not all(source.is_file() for source in sources):
        raise ProjectError("missing_file", "test-cases.md, prompt-v0.md and both fixtures must be in your project folder.")
    clear_dir(paths.key_work)
    store.write_bytes_atomic(paths.key_work / "test-cases.md", paths.test_cases.read_bytes())
    store.write_bytes_atomic(paths.key_work / "prompt-v0.md", paths.prompt.read_bytes())
    store.write_bytes_atomic(paths.key_work / "skills" / "make-eval-fixtures" / "SKILL.md",
                             resources.read_bytes(FIXTURES_SKILL))
    for name in FIXTURE_NAMES:
        store.write_bytes_atomic(paths.key_work_fixtures / name, (paths.fixtures / name).read_bytes())


def prepare_hook(paths):
    """Clear the hook folder and leave only the update and its requirements."""
    clear_dir(paths.hook_work)
    for name, source in HOOK_FILES.items():
        store.write_bytes_atomic(paths.hook_work / name, resources.read_bytes(source))


def prepare_demo(paths):
    """Clear the demo folder and leave only what the anatomy demo may read."""
    clear_dir(paths.demo_work)
    for name, source in DEMO_FILES.items():
        store.write_bytes_atomic(paths.demo_work / name, resources.read_bytes(source))


def prepare_practice(paths, activity_id, sources):
    """Clear one practice folder and leave only the files that lesson's practice may read.

    `sources` maps a file name inside the folder to a bundled resource path.
    """
    work = paths.practice_work(activity_id)
    clear_dir(work)
    for name, source in sources.items():
        store.write_bytes_atomic(work / name, resources.read_bytes(source))
    return work


def _remove_keys(root):
    """Delete every answer key under root. Returns True if there was one."""
    removed = False
    for folder, _, files in os.walk(str(root)):
        for name in files:
            if name.lower() == KEY_NAME:
                target = os.path.join(folder, name)
                try:
                    os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass
                os.unlink(target)
                removed = True
    return removed


def finish_fixtures(paths):
    """Copy the two outputs to the project and leave no answer key anywhere.

    Returns True if the CLI wrote a key under the fixtures folder anyway.
    """
    paths.fixtures.mkdir(parents=True, exist_ok=True)
    for name in FIXTURE_NAMES:
        store.write_bytes_atomic(paths.fixtures / name, (paths.work_fixtures / name).read_bytes())
    stray = _remove_keys(paths.fixtures_work)
    if paths.sealed_key.exists():
        paths.sealed_key.unlink()
    if paths.key_work.exists():
        clear_dir(paths.key_work)
    return stray


def seal_key(paths):
    """Move the answer key from the answer key folder to sealed storage."""
    paths.sealed_dir.mkdir(parents=True, exist_ok=True)
    if paths.sealed_key.exists():
        paths.sealed_key.unlink()
    shutil.move(str(paths.key_work_key), str(paths.sealed_key))
