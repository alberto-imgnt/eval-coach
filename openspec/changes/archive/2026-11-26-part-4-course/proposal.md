# Proposal

## Why

Issue #18 (slice B of Part 4, parent #15) asks for the participant-facing Part 4 course. Slice A (`part-4-attempt-engine`, archived) built and tested the attempt engine dark, with no lessons, no step text, no interface and no Series row. Nothing yet teaches a participant to change a prompt one step at a time, measure it against the same rules and keep a log of why. Part 4 has no source session, so its worked example has to be authored and proved against the real reference checker, and the engine needs a few additions that only a real course reveals.

## What Changes

- **A Part 4 course.** A mission, five lessons, one concept each, with Quick checks, retrieval questions and glossary terms. It teaches: confirm the checker first with a known-good answer, make one change with a prediction written before the run, read every rule and not only the total, red then green then refactor, and keep or undo with a log.
- **A worked Practice task, in lessons only.** It starts from Iteration 0 (25/30; C5 factual tone 3/5). Round 1 makes the tone line concrete (26/30: C5 +2, C6 -1). Round 2 shortens it and drops the Role line (26/30, flat). The learner predicts first and the exact edits and results are revealed only after the prediction is locked. Every authored answer is scored by the reference checker in a test, so no number is typed by hand. It is called a worked example, never a measurement.
- **The learner's own rounds, in steps.** The fixed order is: start, known-good, round 1, round 2, optional round 3. Each round is hypothesis, edit, measure and decide and log. Step ids carry a round suffix (`hypothesis-1`, `edit-1`, `measure-1`, `decide-1`, then `-2`, `-3`). This replaces slice A's dark `COURSE_4` ids and order, so the known-good check comes before any comparison, as issue #15 requires.
- **An answers step.** A new step handler runs five fresh AI-window answers for a round and saves them to `part-4\attempts\<n>\runs\`. It is built on Part 1's `WriteAndRun._launch` pattern and Part 3's output watcher, because Part 3's `generate` is hard-wired to the project's blind folder and `run-N` files. It records the model and nudges when it differs from the previous attempt.
- **Decide and log.** One step per round: the participant keeps or undoes the attempt, then the AI window writes the factual log entry (counts, overall, NOT CHECKED, the saved Hypothesis) and the participant writes Change, Result and Reasoning in their own words. The app compares and never edits the log.
- **An isolated Practice baseline.** A new first step, "Choose your starting point", offers the participant's own Part 3 baseline or a bundled Practice baseline under `part-4\practice\`. It holds Iteration 0 files, the five sample answers, a ready-made Practice checker on both tracks, its own attempts folder and its own `iteration-log.md` with Iteration 0 filled in. The participant's own files are never touched. It is practice only and never a submission.
- **Engine additions to slice A.** A configurable Iteration 0 source, a log presence check (Change, Result and Reasoning must not be empty; the gate checks presence only, never content), round-suffixed step ids, and Part 4 moved from dark to registered.
- **Series map.** Part 4's row becomes `kind: "course"` in `series.json`, with its skip text, `ui` block, course groups and finished text. Part 5 stays "Coming soon" and Part 6 stays "Live meeting".
- **Evidence wording.** "measured gain on these rules" and "no measured gain on these rules" only, as the engine already derives it. Participant text never says "did not help" or "no benefit".
- **Docs and tests.** `docs/SPEC.md`, `docs/CONTENT-RULES.md` (Parts table) and `docs/RUNNING-EVALS-COURSE.md` (its note that Parts 4 and 5 are not built) are updated in the same change. Tests cover the content rules, the worked answers against the reference checker, the reveal gate, the answers step, the Practice baseline and the new panels.

### Interface authorization (AGENTS.md rule 11)

Granted by the user in the exploration of this change, on 2026-11-26. **Scope: additive panels only.**

- One new file, `app/eval_coach/web/js/attempt-steps.js`, adds panels for Part 4's step ids to the `PANELS` table, with the one-line import and spread in `panels.js`. The web app picks a panel by step id, so every Part 4 step the participant works in needs one: a text box that saves and locks, a prompt editor, a five-run list with the per-rule compare table, keep or undo with the log gate, and the starting-point choice.
- The panels are built from existing components and styles: text box, run list, copy button, result tables, the paste head. They add no new layout, styling or component, and new element ids only inside the new panels.
- No change to an existing panel, layout, styling, existing element id, `content/lesson-ui.json` entry or Part 1 to 3 copy. Part 4's words live in `content/`.
- New Playwright tests cover the new panels.

Anything beyond this scope needs a fresh authorization.

## Capabilities

### New Capabilities
- `part-4-course`: what the Part 4 course teaches and in what order: the mission, the lessons, the worked Practice task with its prediction gate, evidence wording, quick checks, glossary, the plain-language rules, the finished screen and the one optional Stage 3 note.
- `part-4-exercise-steps`: the Part 4 steps and what each one does: choose a starting point, known-good, and per round hypothesis, edit, measure, and decide and log, with an optional round 3.
- `part-4-practice-baseline`: the isolated Practice baseline: what is bundled, where it is stored, how its checker and log work on both tracks, and that it is practice only and never touches the participant's files.

### Modified Capabilities
- `part-4-attempts`: Iteration 0 can come from the project or from the Practice baseline; the log gate also checks that Change, Result and Reasoning are present; the step ids are round-suffixed; and Part 4 is registered, no longer dark.
- `part-registry`: Part 4 offers no "Start this step again", like Part 3, because a decision cannot be silently undone.
- `series-map`: Part 4 has content and shows a state, a count and an action; only Part 5 shows "Coming soon".
- `mission-lesson-shape`: `p4-mission` follows the same four passages.
- `course-structure`: word caps include `p4-mission` (450) and the closing lesson `p4-keep-and-log` (400).

## Impact

- **Code:** `state.py` (Part 4 registered with new ids and a `source` key), `attempts.py` (Iteration 0 source, log presence check), a new step kinds module for Part 4 (starting point, answers, decide and log, and the thin step wrappers over `Attempts`), `engine.py` and `server.py` (routes for the new kinds), `gates.py` and `parsers.py` (the log presence check), `lessons.py` (the reveal gate on a lesson activity), `project.py` (the Practice folder), and `reset.py` (the Practice folder on the reset inventory, kept by a progress reset and moved by a configuration reset).
- **Interface:** `web/js/attempt-steps.js` and one import line in `panels.js`, as authorized above.
- **Content:** `content/part-4-lessons.json`, `content/part-4-steps.json`, `content/series.json`, `content/glossary.json`, and `content/part-4-attempts.json` (existing).
- **Bundled files:** a new `kit/part4/` with the worked example, the Practice baseline files and the Practice checker (Script and promptfoo).
- **Storage:** `part-4\practice\` and `part-4\attempts\<n>\` in the project, and `parts.part-4` in `progress.json` (hashes and counts only, plus the chosen source).
- **Docs:** as listed above. Tests land with each task group.

### Out of scope
- Harness stages and end-to-end coverage for Part 4 (slice C, issue #19).
- Part 5 behavior: the audit, the mismatch codes and packaging.
- Any real AI run; each needs the user's approval. The promptfoo Practice checker is verified on the stand-in only unless the private Node is present.
- Any interface change beyond the authorization above.
- A third, learner-authored worked round; round 3 is optional and the learner's own.
