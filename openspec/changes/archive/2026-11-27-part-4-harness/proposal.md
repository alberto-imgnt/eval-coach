# Proposal

## Why

Issue #19 is slice C of Part 4 (#15). Slices A (`part-4-attempt-engine`) and B (`part-4-course`) are tested at unit level and with Playwright, but nothing runs Part 4 end to end the way Parts 1 to 3 are run: through the packaged app over HTTP, with the stand-in AI (`fake_cli.py`) and, on the promptfoo track, the real pinned promptfoo. The cases #15 lists (catch-up path, file preservation, early reveal, stale or mismatched results, changed coverage, reverted and flat attempts, the undone second edit, known-good before its score, completion below the coaching target) have never been exercised together through the shipped archive. This change adds that coverage so Part 4 can be called verified on the stand-in.

## What Changes

- Two new stand-in harness stages, run on both tracks:
  - `part4`: Part 4 on the participant's own Part 3 baseline, after `part2` in the main stand-in home.
  - `part4-practice`: the catch-up path, on a second app with a temporary home where Part 3 is unfinished, in the same way `migrate` and `model` use a second app.
- New stand-in behavior in `e2e-work/harness/fake_cli.py` for Part 4's two paste lines: the measure line in the blind folder (answers chosen from the round's prompt, so a changed prompt gives a different, known set of five answers) and the decide line (writes the round's log entry from the saved results, with a mode that writes a wrong entry so the gate messages are seen). The app still types nothing and answers no prompt.
- An early-reveal check over the lesson routes: no response holds the worked edits or results before the prediction is locked.
- Plumbing: add both stages to `SCRIPT_SEQUENCE` and `PF_SEQUENCE` in `run-all.js`, raise the stand-in session budget in `lib.js` to what the stages use, update the stage table and session-count notes in `e2e-work/harness/README.md`, and replace the "Not built here" line for slice C in `docs/SPEC.md`.
- Audit `tests/frontend/part4.spec.js` (slice B) against the #19 list and add only the cases it lacks.
- Two defects the promptfoo pass exposed, fixed as tightly coupled bugs with tests (no change to what participants see): real promptfoo stops on a test whose file is missing even when it was not asked to report on it, so the known-good answer could not be scored before any answer existed, and the five answers could not be scored when the copied config also held the fixture tests (their files are not in the attempt folder). An attempt's eval now runs only the tests it can read (`--filter-pattern`).
- Make the stand-in's five Part 3 answers the five Northwind samples in order (they were picked by the clock), so Iteration 0 is 25 of 30 on every run and a round's gain, flat or worse result is known in advance.
- No change to what participants see or to app behavior. A defect the stages expose is fixed as a tightly coupled bug, with a test, in this change.

## Capabilities

### New Capabilities

None. This change adds test tooling only and sets `skip_specs: true`; the behavior it checks is already specified by `part-4-attempts`, `part-4-course`, `part-4-exercise-steps` and `part-4-practice-baseline`.

### Modified Capabilities

None.

## Impact

- `e2e-work/harness/`: `part4-stages.js` (new, the two stages, handed the helpers of `lesson-stages.js`), `lesson-stages.js` (the helper hand-over, `P4_CONTENT`, a `keepLocked` option of `spawnApp`), `fake_cli.py` (Part 4 branches, the wrong-entry mode, deterministic Part 3 answers), `lib.js` (session budget), `run-all.js` (sequences), `README.md`.
- `app/eval_coach/promptfoo.py`, `baseline.py` and `attempts.py`: the `only` filter for an attempt's eval (the defect fix above). `tests/pf_helpers.py` (the fake honors `--filter-pattern` and can stop on a missing file), `tests/test_part_4_attempts.py` and `tests/test_promptfoo_real.py` (regression tests).
- `docs/SPEC.md`: the Part 4 "Not built here" note, the Tests line and the attempt engine's storage note.
- `tests/frontend/part4.spec.js`: the missing cases the audit found (flat round wording, finishing under the target).
- No change to `web/`, `content/*.json`, `lesson-ui.json`, step `ui` blocks, element ids, the launchers or what participants see.
- Nothing is read from or written to a participant's real home; stages use the stand-in home, project and temp homes under `e2e-work/`, which are generated and git-ignored scratch.

## Out of scope

- Any real AI run. One real run per tool of the `decide` log line, and of the Practice config on the promptfoo track, needs the user's approval and is a separate step (AGENTS.md "Rules for anything that touches a real CLI").
- Part 5, its mismatch codes and its harness stages.
- Interface changes (AGENTS.md rule 11). No authorization is requested or used.
- New unit tests that repeat cases already covered in `tests/test_part_4_*.py`.
- Committing, branching or opening a pull request. Slice B (`part-4-course`) is archived but not yet committed, and #18 is open; the branch and pull request for this change wait for the user's go-ahead after that is settled.
