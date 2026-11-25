# Proposal

## Why

Issue #16 must be settled before Part 4 (#15) and Part 5 (#14) are built. Today each Part reads its own files. Part 3 scores only the project-root `prompt-v0.md` and `test-cases.md` that setup wrote, so a learner can finish Part 1 (a structured rewrite in `part-1\`) and Part 2 (their own file in `part-2\`) and then score something else without being told. The prompt Part 1 saves is also not what Part 3 runs: Part 1 adds the rough notes when it builds the text to paste, and Part 3 copies `prompt-v0.md` as it stands.

Three wording problems have the same cause. Part 1 says "your second prompt did better" whatever the hand score was, Part 3 says "if the score did not move, the change did not help", and Part 3 says to pick your best answer as the known-good output. Parts 4 and 5 would copy this wording and so teach more than one comparison, or one number, can show. The two briefs also disagree on completion: #15 treats the 95% known-good check and the five-answer target as separate, while #14 allows an unmapped requirement but its automated check requires 90%. Neither says how Part 5 finds the version Part 4 kept.

## What Changes

- **Part 3 gets a new first step, "Choose your inputs" (`inputs`), before `generate`.** It shows which prompt and which test cases are active and where each came from, and offers the learner's Part 1 rewrite and Part 2 file as explicit choices. Nothing changes unless the learner chooses it. A choice moves the file it replaces into a backup folder and never deletes or overwrites it. Once `generate` starts, the files are locked as the evidence in use. A missing, blank, unsuitable or stale source is labelled, with the reason, and the Practice task files stay available as the labelled fallback. The step runs no AI and works the same on both tracks.
- **Part 3 gets one rule for evidence wording** and Part 1, Part 3 and the Part 4 and 5 briefs follow it. One comparison is a learning observation. "No measured gain on these rules" is not "no benefit". Per-criterion results and NOT CHECKED stay visible. A known-good answer is chosen from the written requirements before its score is seen.
- **The Part 1 compare and the `p1-benefits` lesson** stop saying the second prompt did better unless the learner's own scores show it. A tie or a drop gets a neutral reading.
- **The Part 3 baseline lesson and the Stage 3 note** drop "the change did not help" and "pick your best answer". They say that Iteration 0 is not one of the two documented rounds, and that the 95% known-good check, the five-answer overall target and the 90% load-bearing share are three different things.
- **Thresholds and the Part 4 to 5 handoff are fixed in the docs** that #15 and #14 cite, and both issue bodies are updated to match. The kept version is identified by an explicit kept-attempt record with a manifest of hashes, not by "the latest".
- **A Stage 3 traceability map** (examiner criterion, exercise, evidence it produces, and whether it is an examiner requirement or a course convention) goes into `docs/CONTENT-RULES.md`. It was checked against the program's "What We Examine" page on 2026-11-24.
- **A pilot plan** (an unseen task, a rerun by a second person) is recorded. Running it is a separate approval.

Interface (authorized by the user on 2026-11-24, AGENTS.md rule 11): **one new step panel only**, a `choose_inputs` step kind rendered by `js/part-steps.js` from `step.ui` and `step.data`, built from existing design tokens and components (`radio-card`, `mono-block`, the inline "What is still missing" list). No other change to `web/`, `lesson-ui.json`, existing step `ui` blocks or element ids. The new step's own words live in `content/steps.json`. The lesson and step wording edits above are content, not interface.

**Out of scope:** building Parts 4 or 5, the live Part 6 format, submission steps or certification scoring, navigation (#9), any real-AI run or learner pilot (each needs separate approval), and changes to Part 3's gates, checker, baseline log format or the sealed answer key.

## Capabilities

### New Capabilities
- `part-3-inputs`: the `inputs` step. It shows the active prompt and test cases with their source, offers the Part 1 and Part 2 files as explicit choices, labels the Practice task fallback, protects original and in-use files, and locks the files once Part 3 starts using them.

### Modified Capabilities
- `series-intent-framing`: replace the "if the score did not move the change did not help" rule with the measured-gain wording, and add requirements for one comparison being an observation, the three separate thresholds, and a known-good answer chosen before its score is seen.
- `learning-priority-order`: the Stage 3 note says Iteration 0 is not one of the two rounds and names the three thresholds apart. Add a traceability-map requirement guarded by a test.
- `course-structure`: the Part 3 order gains the `inputs` step, and the "nine steps do not change" sentence becomes "the existing nine steps' gates and results do not change".
- `part-1-exercise-steps`: the compare step's change text and its "what made the second answer better" prompts stay neutral when the score is equal or lower.
- `part-1-course`: `p1-benefits` no longer asserts that the second prompt did better, and says it saves the rewrite for use in Part 3.
- `part-3-paste-flow`: "Part 3's gates and teaching are unchanged" covers the nine existing steps and states that the `inputs` step is not an AI step, so the paste flow rules do not apply to it.

## Impact

- **Code:** `state.py` (Part 3 step list, default record, older-progress completion), a new step kind registered in `state.STEP_KINDS`, a new project helper that moves, copies and hashes the two files, `reset.py` (the new backup folder and records on the reset lists), `engine.py` (the lock for `generate` and the old-progress migration), and `js/part-steps.js` (the one new panel).
- **Content:** `content/steps.json` (the new step, the `baseline` and `generate` wording), `content/lessons.json` (`baseline-why`), `content/part-1-lessons.json` (`p1-benefits`), `content/part-1-steps.json` (the compare words and the `rescore` prompts), the glossary.
- **Docs:** `docs/SPEC.md` (the Part 3 step list and an "Evidence handoff" section), `docs/CONTENT-RULES.md` (the traceability map and the thresholds), `AGENTS.md` (the step count in Status, only if it names nine).
- **Tests:** `tests/test_learning_priorities.py` (the two assertions that pin the old wording), `test_part_3_content.py`, `test_part_1_content.py`, `test_part_1_steps.py`, `test_course.py`, `test_reset.py`, `test_baseline_step.py`, a new `test_part_3_inputs.py`, `tests/frontend`, and the stand-in harness on both tracks.
- **Issues:** #15 and #14 bodies are edited at apply time, once the contract is confirmed. They are external, so each edit needs the user's go-ahead.
