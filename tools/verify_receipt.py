"""Verification receipts: record that checks passed on an exact state of the working tree,
and later tell whether that state is unchanged.

The fingerprint is a git tree hash of the working tree, ignoring everything git ignores and
the openspec/ folder (archiving moves files there without changing what the checks exercised).
It is computed in a temporary index, so the real index and working tree are never touched.

Usage:
    python tools/verify_receipt.py write --change <name> --name <check> -- <command...>
        run the command; if it passes and the tree did not change during the run, record it
        in <change folder>/verification.json
    python tools/verify_receipt.py check --change <name> [--require <check> ...] [--staged]
        print JSON: status valid | stale | missing | incomplete, plus the files changed since
        a stale receipt. Exit code 0 valid, 1 stale, 2 missing, 3 incomplete. With --staged the
        receipt is compared with the staged snapshot, so `valid` means a commit of exactly what
        is staged holds the tested files (anything left unstaged or untracked makes it stale).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECEIPT_NAME = "verification.json"
EXCLUDES = ["openspec"]
EXIT = {"valid": 0, "stale": 1, "missing": 2, "incomplete": 3}


def _git(root, *args, env=None):
    return subprocess.run(["git", *args], cwd=str(root), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def fingerprint(root):
    """Return the tree hash of the working tree, minus EXCLUDES and ignored files."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        pathspec = [".", *(":(exclude)" + e for e in EXCLUDES)]
        added = _git(root, "add", "-A", "--", *pathspec, env=env)
        if added.returncode != 0:
            raise RuntimeError("git add failed: " + added.stderr.strip())
        tree = _git(root, "write-tree", env=env)
        if tree.returncode != 0:
            raise RuntimeError("git write-tree failed: " + tree.stderr.strip())
        return tree.stdout.strip()


def staged_fingerprint(root):
    """Return the tree hash of what is staged now, minus EXCLUDES. Same recipe as `fingerprint`, so the two
    compare equal only when every change outside EXCLUDES is staged and nothing else is."""
    index = Path(_git(root, "rev-parse", "--git-path", "index").stdout.strip())
    index = index if index.is_absolute() else Path(root) / index
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "index"
        if index.is_file():
            shutil.copyfile(str(index), str(copy))
        env = dict(os.environ, GIT_INDEX_FILE=str(copy))
        removed = _git(root, "rm", "--cached", "-r", "-q", "--ignore-unmatch", "--", *EXCLUDES, env=env)
        if removed.returncode != 0:
            raise RuntimeError("git rm failed: " + removed.stderr.strip())
        tree = _git(root, "write-tree", env=env)
        if tree.returncode != 0:
            raise RuntimeError("git write-tree failed: " + tree.stderr.strip())
        return tree.stdout.strip()


def head(root):
    result = _git(root, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def find_change(root, name):
    changes = Path(root) / "openspec" / "changes"
    active = changes / name
    if active.is_dir():
        return active
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-" + re.escape(name) + r"$")
    archive = changes / "archive"
    matches = sorted(p for p in archive.iterdir() if p.is_dir() and pattern.match(p.name)) \
        if archive.is_dir() else []
    return matches[-1] if matches else None


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def changed_files(root, old_tree, new_tree):
    """Paths that differ between two tree hashes, or None if the old tree is gone."""
    result = _git(root, "diff-tree", "-r", "--name-status", "--no-renames", old_tree, new_tree)
    if result.returncode != 0:
        return None
    return [line.replace("\t", " ", 1) for line in result.stdout.splitlines() if line]


def count_tests(output):
    found = re.findall(r"^Ran (\d+) tests?", output, re.MULTILINE)
    return int(found[-1]) if found else None


def write(root, change, name, command):
    folder = find_change(root, change)
    if folder is None:
        print("error: no change named '%s' under openspec/changes" % change, file=sys.stderr)
        return 4
    before = fingerprint(root)
    proc = subprocess.Popen(command, cwd=str(root), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    lines = []
    for line in proc.stdout:
        sys.stdout.write(line)
        lines.append(line)
    code = proc.wait()
    after = fingerprint(root)

    path = folder / RECEIPT_NAME
    receipt = _load(path)
    same_tree = bool(receipt) and receipt.get("tree") == before
    checks = [c for c in receipt.get("checks", []) if c.get("name") != name] if same_tree else []

    if code != 0:
        if same_tree:
            _save(path, change, before, root, checks)
        print("\nnot recorded: '%s' failed (exit code %d)" % (name, code), file=sys.stderr)
        return code
    if before != after:
        print("\nnot recorded: files changed while '%s' ran; run it again" % name, file=sys.stderr)
        return 5
    checks.append({"name": name, "command": " ".join(command), "exit_code": 0,
                   "tests": count_tests("".join(lines)),
                   "finished": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _save(path, change, before, root, checks)
    print("\nrecorded '%s' in %s" % (name, path))
    return 0


def _save(path, change, tree, root, checks):
    receipt = {"version": 1, "change": change, "tree": tree, "excludes": EXCLUDES,
               "head": head(root), "checks": checks}
    if checks:
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def check(root, change, required, staged=False):
    folder = find_change(root, change)
    receipt = _load(folder / RECEIPT_NAME) if folder else None
    if not receipt:
        return {"status": "missing", "change": change}
    current = staged_fingerprint(root) if staged else fingerprint(root)
    have = {c["name"] for c in receipt.get("checks", [])}
    result = {"change": change, "scope": "staged" if staged else "working-tree",
              "recorded_tree": receipt["tree"], "current_tree": current,
              "checks": receipt.get("checks", [])}
    if receipt["tree"] != current:
        result["status"] = "stale"
        result["changed"] = changed_files(root, receipt["tree"], current)
    elif set(required) - have:
        result["status"] = "incomplete"
        result["missing_checks"] = sorted(set(required) - have)
    else:
        result["status"] = "valid"
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="action", required=True)
    w = sub.add_parser("write")
    w.add_argument("--change", required=True)
    w.add_argument("--name", required=True, help="check label, for example backend")
    c = sub.add_parser("check")
    c.add_argument("--change", required=True)
    c.add_argument("--require", action="append", default=[], help="check label that must be recorded")
    c.add_argument("--staged", action="store_true",
                   help="compare the receipt with the staged snapshot (what a commit would hold), not the working tree")
    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.action == "write":
        if not command:
            parser.error("write needs a command after --")
        return write(root, args.change, args.name, command)
    result = check(root, args.change, args.require, args.staged)
    print(json.dumps(result, indent=2))
    return EXIT[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
