# Expected results (presenter only)

All results come from running `reference-check.py` and `reference-promptfooconfig.yaml` against the Northwind example files, and from two agents following each builder skill on their own (Python and promptfoo). All three give identical results. The sample runs are hand-written to look like typical model outputs; they are a fallback, not real model output.

This is the answer key for the Northwind example only. Attendees who use their own task get their own fixtures and answer key from the fixtures skill, so their results will differ.

## Reference thresholds (the Session 2 test cases, C1 to C6)

P = pass, F = fail.

| File | C1 Length | C2 Grouped by client | C3 Blocker and ask | C4 Teams, not email | C5 Factual tone | C6 Uses the notes |
| --- | --- | --- | --- | --- | --- | --- |
| demo-good-output (presenter demo only) | P | P | P | P | P | P |
| fixture-bad | F | F | F | F | F | P |
| fixture-polished-but-wrong | P | P | **P** | P | P | P |
| run-1 (sample-run-1) | P | P | P | P | P | P |
| run-2 | P | F | P | P | P | P |
| run-3 | P | P | F | P | F | P |
| run-4 | P | P | P | P | P | P |
| run-5 | F | P | P | P | F | P |

Baseline for the five sample runs: C1 4/5, C2 4/5, C3 4/5, C4 5/5, C5 3/5, C6 5/5. Overall 25/30 (checked criteria x runs). The tightened C3 below does not change these numbers.

## The finding that drives the room block

The polished fixture passes all six criteria and is wrong. It says "Blocker: none this week. Need: nothing further" when the real blocker was test data access, and it invents a $50k estimate. C3 only checks that the two labels exist, so it cannot tell. This is the window-dressing check from Session 2, now caught by running it.

Attendees whose own thresholds were tighter will see their polished fixture fail; that is fine. Ask them what in their threshold caught it.

How to frame it: Session 2 taught label-based thresholds as a starting point, and the checker found their limit. That is the checker doing its job, not a mistake in Session 2.

## The fix: tighten the spec

C3 threshold, tightened (change it in the markdown, then update the script or config):

> Passes if a "Blocker:" label and a "Need:" label both appear, the text after "Blocker:" mentions "test data", and the text after "Need:" mentions "access"

| File | C3 before | C3 after |
| --- | --- | --- |
| fixture-polished-but-wrong | P | **F** |
| every other file | unchanged | unchanged |

Verified in both lanes: only the polished fixture changes.

Say out loud that this is still a proxy: "Blocker: test data is fine. Need: access is not needed" passes it. Tightening a keyword check is an arms race. Deterministic checks narrow the gap; they do not close it.

Optional extra criterion: `Passes if every number (digits) in the output also appears in the test input`. The Northwind test input has no digits, so any digit fails; the polished fixture fails it on "$50k".

## Interpretation choices to expect

Agents list these in their Interpretation choices. They are good discussion material because the threshold text does not settle them.

- **Word counting:** whether a lone `-` or `&` is a word. The bad fixture is 154 words counting every whitespace-separated token and 152 if bare symbols are ignored. Both are over 150, so no result changes.
- **What counts as a label:** client names are labels only at the start of a line; `Blocker:` and `Need:` can appear anywhere.
- **Case and substring:** `Dear` versus `dear`, `proud` inside `proudly`.
- **Where the day-name list comes from:** C2 needs a list of day names that is not in the test case file. A well-behaved agent marks it as invented.
- **What the keyword list covers:** C6 has six keywords for seven note lines.
- **Line endings:** promptfoo reads Windows line endings as is, so label patterns must allow `\r\n`.

## What each artifact is for

| File | Use |
| --- | --- |
| `reference-check.py` | Last resort if a room cannot get a script working; the answer key for the Python lane |
| `reference-promptfooconfig.yaml` | Same for the promptfoo lane. Run it from this folder (commands are in its header) |
| `demo-test-cases.md` | Two-criterion test case file for the live build |
| `demo-good-output.txt` | A passing output for the live demo. Not in the attendee kit |
