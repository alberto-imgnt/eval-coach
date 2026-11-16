"""Reference checker for the Northwind end-of-week update (C1-C6, Session 2 thresholds).

Usage: python reference-check.py output1.txt [output2.txt ...]
Presenter-only. Attendees get a checker generated from their own test cases.
"""
import re
import sys
from pathlib import Path

# Supporting lists, copied from the test case file
BANNED_WORDS = ["excited", "thrilled", "proud", "amazing", "incredible", "awesome",
                "delighted", "successfully", "crushed", "happy to report"]
EMAIL_MARKERS = ["Subject:", "Dear", "Regards", "Sincerely"]
CLIENT_LABELS = ["Northwind", "Contoso", "Internal"]
NOTE_KEYWORDS = ["estimate", "onboard", "demo", "lunch", "documentation", "reporting feature"]

# A label is a line that is only the name, or starts with "name:" (bullets, bold and # are ignored)
LINE_START = r"(?:^|\n)[ \t>*#_-]*"
LINE_END = r"[ \t*_]*(?::|\n|$)"
DAY = r"(?:[Mm]on|[Tt]ue|[Ww]ed|[Tt]hu|[Ff]ri)[a-z]*"
DAY_LABEL = re.compile(LINE_START + DAY + r"(?:\s*[–-]\s*" + DAY + r")?" + LINE_END)


def check_c1_length(text):
    """C1: Word count under 150 passes (words split on whitespace)."""
    n = len(text.split())
    return n < 150, f"{n} words (limit: under 150)"


def check_c2_grouped_by_client(text):
    """C2: Northwind, Contoso, Internal all appear as labels; no day name used as a label."""
    missing = [name for name in CLIENT_LABELS
               if not re.search(LINE_START + re.escape(name) + LINE_END, text)]
    day = DAY_LABEL.search(text)
    if missing:
        return False, "missing client label(s): " + ", ".join(missing)
    if day:
        return False, f"day name used as a label: {day.group(0).strip()!r}"
    return True, "all three client labels found, no day labels"


def check_c3_blocker_and_ask(text):
    """C3: A "Blocker:" label and a "Need:" label both appear (exact text, case-sensitive)."""
    missing = [label for label in ("Blocker:", "Need:") if label not in text]
    if missing:
        return False, "missing label(s): " + ", ".join(missing)
    return True, 'found "Blocker:" and "Need:"'


def check_c4_teams_not_email(text):
    """C4: None of "Subject:", "Dear", "Regards", "Sincerely" appear (case-insensitive)."""
    found = [m for m in EMAIL_MARKERS if m.lower() in text.lower()]
    if found:
        return False, "email marker(s) found: " + ", ".join(found)
    return True, "no email markers"


def check_c5_factual_tone(text):
    """C5: Zero banned words (case-insensitive substring) and no exclamation marks."""
    found = [w for w in BANNED_WORDS if w in text.lower()]
    if "!" in text:
        found.append("!")
    if found:
        return False, "found: " + ", ".join(found)
    return True, "no banned words or exclamation marks"


def check_c6_uses_the_notes(text):
    """C6: Every note keyword is found (case-insensitive substring)."""
    missing = [k for k in NOTE_KEYWORDS if k not in text.lower()]
    if missing:
        return False, "missing keyword(s): " + ", ".join(missing)
    return True, "all note keywords found"


CRITERIA = [
    ("C1", "Length", check_c1_length),
    ("C2", "Grouped by client", check_c2_grouped_by_client),
    ("C3", "Blocker and ask", check_c3_blocker_and_ask),
    ("C4", "Teams, not email", check_c4_teams_not_email),
    ("C5", "Factual tone", check_c5_factual_tone),
    ("C6", "Uses the rough notes", check_c6_uses_the_notes),
]


def main(paths):
    totals = {cid: 0 for cid, _, _ in CRITERIA}
    all_passed = True
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        print(f"== {path}")
        passed_count = 0
        for cid, name, fn in CRITERIA:
            ok, reason = fn(text)
            totals[cid] += ok
            passed_count += ok
            print(f"{cid} {'PASS' if ok else 'FAIL'}  {name}: {reason}")
        all_passed = all_passed and passed_count == len(CRITERIA)
        print(f"-> {passed_count}/{len(CRITERIA)} criteria passed\n")
    if len(paths) > 1:
        print("== Pass rate per criterion")
        for cid, name, _ in CRITERIA:
            print(f"{cid} {name}: {totals[cid]}/{len(paths)}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python reference-check.py output1.txt [output2.txt ...]")
    sys.exit(main(sys.argv[1:]))
