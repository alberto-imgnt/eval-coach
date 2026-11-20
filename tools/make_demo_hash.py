"""Create app/eval_coach/demo_hash.json from a password typed at a prompt.

Usage:
    python tools/make_demo_hash.py [--out PATH]

The password is read with getpass. Only a salt, the iteration count and the hash are written; the password is
never printed, stored or passed on a command line.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from eval_coach import demo_access  # noqa: E402

DEFAULT_OUT = ROOT / "app" / "eval_coach" / demo_access.HASH_FILE


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create the demo access hash file.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Where to write the hash file.")
    args = parser.parse_args(argv)
    password = getpass.getpass("Demo access password: ")
    if not password:
        print("No password typed; nothing written.", file=sys.stderr)
        return 1
    if getpass.getpass("Type it again: ") != password:
        print("The two entries differ; nothing written.", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.write_text(json.dumps(demo_access.make_record(password), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
