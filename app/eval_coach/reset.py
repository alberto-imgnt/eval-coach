"""The two resets: what each one moves, and how it is moved all-or-nothing into one backup.

Nothing here is deleted. Everything a reset clears is moved into one backup folder that the
next reset replaces. The answer key is the one exception: it is never backed up.
"""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

from . import project, resources

BACKUP_NAME = "reset-backup"
STAGING_NAME = "reset-backup.new"
OLD_NAME = "reset-backup.old"

# --- the inventory -----------------------------------------------------------
# Every file the app or the participant's CLI creates is on one of these lists. tests/test_reset.py fails
# when a file in a finished stand-in project or home folder is on none of them.

# In the project folder, moved by both resets.
PROJECT_FILES = ("check.py", "promptfooconfig.yaml", "promptfooconfig.live.yaml", "agent-provider.js",
                 "results.json", "iteration-log.md")
PROJECT_DIRS = (".learning",)  # the whole folder: progress.json, results\, hook\, practice\
PROJECT_FOLDER_CONTENTS = ("runs", "fixtures", "examples")  # contents moved, the folder itself is kept or recreated
# In the project folder, Part 1's own work under part-1\. Both resets move what the CLI produced; the participant's own
# prompts and own-work texts stay after "Reset lesson progress" and move with "Reset app configuration".
PROJECT_PART1_DIR = project.PART1_DIR
PROJECT_PART1_OUTPUTS = tuple(files[1] for files in project.PART1_FILES.values())
PROJECT_PART1_PROMPTS = tuple(files[0] for files in project.PART1_FILES.values()) + tuple(project.PART1_OWN_FILES.values())
# In the project folder, Part 2's worksheet and test cases under part-2\. Part 2 runs nothing, so both are the
# participant's own work: they stay after "Reset lesson progress" and move with "Reset app configuration".
PROJECT_PART2_DIR = project.PART2_DIR
PROJECT_PART2_FILES = tuple(project.PART2_FILES.values())
# In the project folder, Part 4's attempts under part-4\. All of it is the participant's own work: it stays after
# "Reset lesson progress" and moves with "Reset app configuration".
PROJECT_PART4_DIR = project.PART4_DIR
# In the project folder, moved only by "Reset app configuration".
PROJECT_STARTING_FILES = ("prompt-v0.md", "test-cases.md")
PROJECT_SKILLS_DIR = "skills"  # only the bundled skill files in it are moved
# The starting files and skills stay after "Reset lesson progress".
PROJECT_KEPT_BY_PROGRESS = PROJECT_STARTING_FILES + (PROJECT_SKILLS_DIR,)

# In the app's own folder, scratch folders the steps and lessons rebuild every time: moved by both resets.
HOME_SCRATCH = ("blind", "fixtures-work", "key-work", "hook", "demo", "practice", "part1", "part4")
HOME_PENDING = "pending-lessons.json"  # course progress from before a project existed
# In the app's own folder, setup state: moved only by "Reset app configuration".
HOME_SETUP_FILES = ("preflight.json", "app.json", "model-cache.json")
HOME_SETUP_DIRS = ("cli-test", "cli-signin", "cli-install")
# Kept by both resets: downloads and caches, the CLI recipe override, and the backup itself.
HOME_KEPT = ("runtime", "npm-cache", "promptfoo", "promptfoo-work", "cli-recipes.json", "cli-models", BACKUP_NAME,
             STAGING_NAME, OLD_NAME)
# Deleted, never backed up.
HOME_SEALED = "sealed"


class ResetError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def classify_project_path(rel, configuration=True):
    """"move" or "keep" for a path (forward slashes) inside a project folder, or None for an unknown file."""
    first = rel.split("/", 1)[0]
    if first in PROJECT_FILES or first in PROJECT_DIRS:
        return "move"
    if first in PROJECT_FOLDER_CONTENTS and "/" in rel:
        return "move"
    if first == PROJECT_PART1_DIR and rel.count("/") == 1:
        name = rel.split("/", 1)[1]
        if name in PROJECT_PART1_OUTPUTS:
            return "move"
        if name in PROJECT_PART1_PROMPTS:
            return "move" if configuration else "keep"
        return None
    if first == PROJECT_PART2_DIR and rel.count("/") == 1:
        if rel.split("/", 1)[1] in PROJECT_PART2_FILES:
            return "move" if configuration else "keep"
        return None
    if first == PROJECT_PART4_DIR and "/" in rel:
        return "move" if configuration else "keep"
    if rel.startswith(project.REPLACED_INPUTS + "/"):
        return "move" if configuration else "keep"
    if first in PROJECT_STARTING_FILES:
        return "move" if configuration else "keep"
    if first == PROJECT_SKILLS_DIR:
        bundled = {name[len("kit/"):] for name in resources.list_files("kit/skills")}
        if rel in bundled:
            return "move" if configuration else "keep"
    return None


def classify_home_path(rel, configuration=True):
    """"move", "keep" or "delete" for a path inside the app's own folder, or None when it is on no list."""
    first = rel.split("/", 1)[0]
    if first in HOME_SCRATCH or first == HOME_PENDING:
        return "move"
    if first in HOME_SETUP_FILES or first in HOME_SETUP_DIRS:
        return "move" if configuration else "keep"
    if first in HOME_KEPT:
        return "keep"
    if first == HOME_SEALED:
        return "delete"
    return None


def _skill_files():
    return [name[len("kit/"):] for name in resources.list_files("kit/skills")]


def build_plan(home, paths, configuration):
    """The items to move, as (source, backup label). Only things that exist, and only what is on the lists."""
    plan = []
    if paths is not None:
        root = paths.project
        for name in PROJECT_FILES:
            if (root / name).is_file():
                plan.append((root / name, "project/" + name))
        for name in PROJECT_DIRS:
            if (root / name).is_dir():
                plan.append((root / name, "project/" + name))
        for name in PROJECT_FOLDER_CONTENTS:
            folder = root / name
            if folder.is_dir():
                for child in sorted(folder.iterdir()):
                    plan.append((child, f"project/{name}/{child.name}"))
        for name in PROJECT_PART1_OUTPUTS + (PROJECT_PART1_PROMPTS if configuration else ()):
            if (root / PROJECT_PART1_DIR / name).is_file():
                plan.append((root / PROJECT_PART1_DIR / name, f"project/{PROJECT_PART1_DIR}/{name}"))
        if configuration:
            replaced = root / project.REPLACED_INPUTS
            if replaced.is_dir():
                for child in sorted(replaced.iterdir()):
                    plan.append((child, f"project/{project.REPLACED_INPUTS}/{child.name}"))
            for name in PROJECT_PART2_FILES:
                if (root / PROJECT_PART2_DIR / name).is_file():
                    plan.append((root / PROJECT_PART2_DIR / name, f"project/{PROJECT_PART2_DIR}/{name}"))
            if (root / PROJECT_PART4_DIR).is_dir():
                plan.append((root / PROJECT_PART4_DIR, f"project/{PROJECT_PART4_DIR}"))
            for name in PROJECT_STARTING_FILES:
                if (root / name).is_file():
                    plan.append((root / name, "project/" + name))
            for rel in _skill_files():
                if (root / rel).is_file():
                    plan.append((root / rel, "project/" + rel))
    home = Path(home)
    names = list(HOME_SCRATCH) + [HOME_PENDING]
    if configuration:
        names += list(HOME_SETUP_FILES) + list(HOME_SETUP_DIRS)
    for name in names:
        if (home / name).exists():
            plan.append((home / name, "app/" + name))
    if paths is not None and paths.sealed_dir.exists():
        # Moved with everything else so a failed reset can put it back; the key inside is deleted afterwards.
        plan.append((paths.sealed_dir, f"app/{HOME_SEALED}/{paths.sealed_dir.name}"))
    return plan

def build_restart_plan(home, paths, part, steps):
    """What a step restart moves: (plan, rewrites). `plan` is as in build_plan; `rewrites` are project files a
    restart puts back changed, as (path, relative name). Only what exists is listed, and every name must be on the
    reset lists above, so a restart can never move a file the inventory does not know."""
    owned = [part.restart[s] for s in steps]
    names, scratch, rewrites = [], [], []
    for owns in owned:
        for rel in owns.files + owns.rewrite:
            if rel not in names:
                names.append(rel)
        for rel in owns.rewrite:
            if rel not in rewrites:
                rewrites.append(rel)
        scratch.extend(s for s in owns.scratch if s not in scratch)
    plan, rewrite_paths = [], []
    for rel in names:
        if classify_project_path(rel, True) != "move":
            raise ValueError(f"{rel} is on no reset list")
        source = paths.project / Path(*rel.split("/"))
        if source.is_file():
            plan.append((source, "project/" + rel))
            if rel in rewrites and not any(rel in o.files for o in owned):
                rewrite_paths.append((source, rel))
    for name in scratch:
        if classify_home_path(name, True) != "move":
            raise ValueError(f"{name} is on no reset list")
        source = Path(home) / Path(*name.split("/"))
        if source.exists():
            plan.append((source, "app/" + name))
    return plan, rewrite_paths


# --- moving ------------------------------------------------------------------

def _writable(path):
    for folder, dirs, files in os.walk(str(path)):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(folder, name), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except OSError:
                pass


def _tree_files(path):
    path = Path(path)
    if path.is_file():
        return {"": path.stat().st_size}
    return {p.relative_to(path).as_posix(): p.stat().st_size for p in path.rglob("*") if p.is_file()}


def remove_tree(path):
    path = Path(path)
    if not path.exists():
        return
    _writable(path)
    if path.is_dir():
        shutil.rmtree(str(path))
    else:
        os.chmod(str(path), stat.S_IWRITE | stat.S_IREAD)
        path.unlink()


def move(source, dest):
    """Move source to dest. A rename when possible; across volumes, copy, check, then delete the original."""
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(str(source), str(dest))
        return
    except OSError:
        pass
    if source.is_dir():
        shutil.copytree(str(source), str(dest))
    else:
        shutil.copy2(str(source), str(dest))
    if _tree_files(source) != _tree_files(dest):
        remove_tree(dest)
        raise OSError(f"The copy of {source} did not match the original.")
    remove_tree(source)


def stage(plan, staging, text):
    """Move every planned item into the staging folder. If any move fails, put everything back and refuse."""
    staging = Path(staging)
    done = []
    try:
        if staging.exists():
            remove_tree(staging)
        staging.mkdir(parents=True)
        for source, label in plan:
            move(source, staging / Path(*label.split("/")))
            done.append((source, label))
    except OSError as exc:
        rollback(done, staging)
        remove_tree_quietly(staging)
        raise ResetError("reset_backup_failed", text["errors"]["backup_failed"].format(error=exc)) from exc
    return done


def rollback(done, staging):
    """Move moved items back, newest first. Returns the items that could not be put back."""
    failed = []
    for source, label in reversed(done):
        try:
            move(Path(staging) / Path(*label.split("/")), source)
        except OSError:
            failed.append(source)
    return failed


def remove_tree_quietly(path):
    try:
        remove_tree(path)
    except OSError:
        pass


def remove_keys(root):
    """Delete every answer key under root."""
    if Path(root).exists():
        project._remove_keys(root)


def swap_backup(home, staging):
    """Make the staging folder the one backup. The previous backup goes only after the new one is in place."""
    home = Path(home)
    current, old = home / BACKUP_NAME, home / OLD_NAME
    remove_tree_quietly(old)
    if current.exists():
        os.rename(str(current), str(old))
    try:
        os.rename(str(staging), str(current))
    except OSError:
        if old.exists():
            os.rename(str(old), str(current))
        raise
    remove_tree_quietly(old)


def prune_empty(root, names):
    """Remove folders the app created once they are empty. Folders with anything left in them stay."""
    for name in names:
        folder = Path(root) / name
        try:
            for sub in sorted((p for p in folder.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
                if not any(sub.iterdir()):
                    sub.rmdir()
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            pass
