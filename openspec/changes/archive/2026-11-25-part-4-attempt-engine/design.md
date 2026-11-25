# Design

## Context

See proposal.md for why. Current state that shapes the approach:

- Part 3 reads fixed project-root files: `Paths.check_py`, `runs\run-N.txt`, `iteration-log.md`. `baseline.run_checks(project, track)` calls `runner.run_checker(project, files)` or `promptfoo.run_selection(project, prefix, ...)`. Both take a folder as their working directory, so they can run in an attempt folder unchanged. `baseline.runs_hash(paths)` and `summarize` read through `Paths`, which is tied to the project root.
- `state.Part` already supports a Part with its own `progress_key`, `new_steps` and `restart` (Parts 1 and 2). `STEP_KINDS` already hosts per-Part step handlers (`part_steps.py`, `criteria_steps.py`, `input_step.py`).
- `gates.baseline_log_entry` keeps only the entry numbered 0, and `baseline_count_problems` / `baseline_not_checked_problems` compare a log entry with a `summarize` result. Both work for any entry.
- `parse_iteration_log` already returns `hypothesis`, `change`, `result` and `reasoning` as free fields. It has no `Decision`.
- The contract is in `docs/SPEC.md` "Evidence handoff" and the archived change `curriculum-handoffs-stage3-alignment` (D10, D11). The issue is #15.

## Goals / Non-Goals

**Goals:**
- A tested engine for attempt storage, the manifest, the kept pointer, scoring in an attempt folder on both tracks, and the log checks, with no participant-facing course.
- The ordering rules (hypothesis first, known-good before its score) enforced by step order and hashes, never by reading terminal output.

**Non-Goals:**
- Lessons, glossary, the worked Practice task, the Series row and the interface (slice B). Harness stages (slice C).
- Part 5's mismatch codes, packaging and relocated rerun. This change only keeps the manifest in the shape those need.
- Any AI call, any real-CLI run, any change to `web/`, `lesson-ui.json`, step `ui` blocks or element ids.

## Decisions

### D1. An attempt folder is treated as a small project for the runners
Add an `AttemptPaths` with the same accessors the runners and `runs_hash` need (`check_py`, `runs`, `run_file(n)`, config), rooted at `part-4\attempts\<n>\`. `run_checks`, `summarize` and `runs_hash` take it in place of `Paths` through a narrow interface. *Alternative: copy the attempt into the project root and run there.* Rejected: it overwrites Part 3's files, which breaks "Part 3's files are never edited".

### D2. Creating an attempt copies from the kept version
The new attempt's prompt, test cases and checker are copies of the kept attempt's (Iteration 0's root files for attempt 1), written with create-only semantics. An existing file is never replaced. The manifest records `parent`. *Alternative: always start from Iteration 0.* Rejected: it breaks connected rounds.

### D3. Manifest shape and the kept pointer
The manifest is the contract's, stored under `parts.part-4`. `kept` is derived (last attempt with `decision == "kept"`, else Iteration 0) and never stored, so it cannot drift. Keep or undo are explicit submits and require a scored, fresh attempt. An undone attempt keeps its files and entry.

### D4. Hypothesis is a step of its own, saved before the edit
The order is hypothesis, edit, answers, score, decision. Saving writes `hypothesis.md` in the attempt folder (create-only; an edit before the run is allowed and re-hashes, after the run it is refused) and records its hash. The run and score handlers refuse without it. The log gate compares the entry's Hypothesis with the saved text with spacing squashed. *Alternative: read the hypothesis only from the log.* Rejected: it proves nothing about timing.

### D5. Known-good answer and the promptfoo copy
The known-good answer is saved to `known-good.txt` in the attempt folder; the score is computed only after that file exists, so the participant cannot pick it with the score in view. On the Script track `check.py` runs on that file. On the promptfoo track the attempt's copied config gains a `known-good` test whose assertions are copied from the existing run tests. `run_selection` is called with the prefix `known-good`. The checker hash covers the config with that test removed, so adding it never reads as "checker changed". The original config is never edited. *Alternative: a second config file.* Rejected: two files to keep consistent.

### D6. Log parser and gate
Add `Decision` to `_LOG_FIELD` in `parsers.py`, returned as `entry["decision"]` (lower-cased `kept`, `undone`, `pending`, else the raw text for the gate to report). A Part 4 gate walks the manifest in order and, per attempt, checks the entry exists once, the decision matches, the Hypothesis matches, and counts and NOT CHECKED items match `results.json` by reusing `baseline_count_problems` and `baseline_not_checked_problems`. The Part 3 gate is unchanged because it already filters on entry 0.

### D7. Completion and thresholds
Completion is two attempts with a documented, fresh, scored entry after Iteration 0, whatever their decisions. The five-answer score and the known-good score are two separate fields in the view data and never combined. The plain wording is "measured gain on these rules" and "no measured gain on these rules", through `content/` (the wording content for this slice is minimal and engine-facing; the course text is slice B).

### D8. Registration stays dark
Part 4 is added to `state.PARTS` with its own `progress_key` and step ids that no other Part uses (a test checks duplicates), but `series.json` keeps `kind: "soon"` so the Series map does not change. Older progress loads with `parts.part-4` empty.

## Files and storage touched

| Location or key | Change | Kept or cleared |
|---|---|---|
| `<project>\part-4\attempts\<n>\` (prompt, test cases, checker or config, `runs\run-1..5`, `known-good.txt`, `hypothesis.md`, `results.json`) | New | Progress reset keeps them. Configuration reset moves them with the project (as for Part 1 and 2 files) |
| `progress.json` `parts.part-4` | New: manifest, hashes and counts only | Cleared by a progress reset |
| `<project>\prompt-v0.md`, `test-cases.md`, `check.py`, `runs\`, `iteration-log.md` | Read only | Unchanged |
| `app/eval_coach/*.py` (new attempt module, `state.py`, `parsers.py`, `baseline.py`, `gates.py`, `promptfoo.py`) | Code | Shipped |
| `content/series.json` | Unchanged in this slice | Shipped |
| `docs/SPEC.md` "Evidence handoff" | Attempt side marked built | Tracked |

## Risks / Trade-offs

- [`Paths`-shaped accessors leak into the runners] -> a narrow `AttemptPaths` plus tests that run both tracks on an attempt folder and compare with the root result.
- [The checker hash that ignores the `known-good` test hides a real change] -> hash the config after removing exactly the generated test block, and test that editing any other test changes the hash.
- [Resume after the participant edits files by hand] -> hashes are recomputed from files at read time, and stale evidence is shown, never repaired.
- [Part 5 needs more fields later] -> the manifest is exactly the agreed contract, with additions possible because it is read by key.

## Migration Plan

Ship in one change. Older progress loads unchanged and `parts.part-4` starts empty. Rolling back is a revert: the attempt folders are plain files in the project and are never read by Part 3.

## Open Questions

1. **Who produces an attempt's five answers.** *Assumed default: this change provides storage, scoring and gates and tests them with files the stand-in writes. The AI-window step that makes the five answers reuses Part 3's `generate` mechanism and is built in slice B with the course. If that reuse needs engine changes, they are added to the slice B change.*
2. **Interface.** *Assumed default: none. Any Part 4 step panel is slice B and needs the user's explicit authorization recorded there.*
