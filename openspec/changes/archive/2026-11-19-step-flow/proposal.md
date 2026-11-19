# Proposal

## Why

The series review (2026-11-16, items 8, 10b and 11 in `docs/temp/series-review-pending-changes.md`, change 4) found that Part 1's steps ask the participant to press too many buttons in a fixed order: Save, Start my AI, wait, Send to AI, wait, Check my work, Continue. The reviewer also asked for a way to redo a finished step without resetting the whole course. Change 3 (`model-preference`) is archived, so the model is no longer typed and Part 1 can now drop the last of its button choreography.

This change is named `step-flow` (not `part-1-ai-flow`) because the restart control also covers Part 2, which has no AI window. Part 3 shares the AI window with Part 1 and gets the same paste flow in the follow-up `part-3-ai-flow` (4b); this change defines the shared rules once so 4b only reuses them.

## What Changes

- **The AI window starts by itself in Part 1 (item 8, 8a).** In `cold` and `rewrite`, saving a non-empty prompt starts a fresh AI window (a new process, on the model the toggle chose) when the auto-start rule allows it. A note says each step opens a new chat. The rule is defined once, for reuse by 4b: start only when the step is active, not done, not read-only and not blocked, no AI window is already running, the AI was not already auto-started for this step, and nothing in the scratch folder or the saved output would be lost. It never runs on a plain revisit.
- **Copy and paste replaces Send to AI (item 8).** `prompt.md` is still saved in the scratch folder. The full text (the participant's prompt, the rough notes and the save instruction) is shown with a **Copy** button, and the participant pastes it into the AI window. The app no longer types a line into the AI for Part 1 steps. The "Send to AI" button and the line it typed are removed from Part 1.
- **"Check my work" is removed from the five Part 1 steps (item 10b).** `cold`, `score`, `rewrite`, `rescore` and `own` become done when their own file or form gate is met, and the existing "Continue to: <next step>" appears. What is still missing shows inline, in the same list the check used, and never needs a button. The one-question "Quick check" is unchanged and still never blocks. How each step reaches done, and why `score` and `rescore` use Continue as the moment of completion, is in `design.md`. Parts 2 and 3 keep "Check my work".
- **"Start this step again" (item 11), Parts 1 and 2.** A finished step offers a button with a confirm. It moves that step's files and every later step's files in the same Part to the one reset backup folder, clears those steps' saved records, answers and quick-check answers, stops any running AI window, and leaves earlier steps and other Parts alone. It is built once through the Part registry and the reset inventory. Part 3 is not offered it.
- **Rule and doc updates.** `docs/SPEC.md` (Part 1 steps), the local plan (`docs/local/`, not in git), `AGENTS.md` Status, the series review file.

### Interface authorization (AGENTS.md rule 11)

The review file lists these as needing your explicit authorization. **Requested, not yet granted**: apply starts only after you confirm this scope (it may touch `web/` and interface copy within it, and nothing else).

- Part 1 AI window header: no "line that will be typed" block and no "Send to AI" button for Part 1 steps; a note that each step opens a new chat; "Stop" kept; the restart button for the AI window renamed so it is not confused with "Start this step again" (see Open Questions in `design.md`).
- Part 1 `cold` and `rewrite` panels: the "What your AI will read" section becomes the text to paste, with a **Copy** button and a copied confirmation read by screen readers, and a short fallback when the browser refuses the clipboard.
- Removal of "Check my work" from Part 1 steps; the "what is still missing" list and the Continue button for `score` and `rescore`.
- A **Start this step again** button and its confirm dialog on a finished Part 1 or Part 2 step.
- Interface copy: `content/part-1-steps.json` (instructions, troubleshooting, `ui`), `content/lesson-ui.json` and `content/settings.json` for the restart words and the AI window note.

No other layout, styling, element id or component changes.

## Capabilities

### New Capabilities
- `ai-window-paste-flow`: how a step starts the AI window by itself (the auto-start rule), what is saved in the scratch folder, the text the participant copies and pastes, and that the app types nothing into the AI for such a step. Written to be shared by Part 1 now and Part 3 in 4b.
- `step-restart`: restarting a finished step of a Part that registers a restart plan (Parts 1 and 2): confirm, what is cleared and moved to the backup, what is kept, and that Part 3 is not offered it.

### Modified Capabilities
- `part-1-exercise-steps`: the "line the app types" requirement and the Start and Send wording are replaced by the paste flow; the step gates remain but are met without a Check button; the "Each step has one short check" requirement keeps its meaning with the new completion moment; the cold-step scenarios that say "press Start" and "Notes added" change.
- `part-registry`: a Part may register a restart plan; Part 3 registers none.

## Out of Scope

- Part 3's auto-start, Copy and Send removal (change 4b, `part-3-ai-flow`), and "Start this step again" for Part 3 (series review section 7: shared project files and the sealed key need their own design).
- Removing "Check my work" from Parts 2 and 3 (kept on purpose; revisit Part 2 after Part 1's version is seen working).
- Running the AI for the participant, or answering any AI prompt (AGENTS.md rules 2 to 5).
- Lesson AI activities, the setup AI working test page and the AI window mini lesson. They keep their own Start and Send.
- Course locking, skipping and demo access (change 5), a technical mode (item 0), and any change to the Sonnet / Haiku toggle.
- Real-CLI runs during planning or apply without the user's approval. The pasted-text flow is verified on the stand-in; the real tools are covered by the approved real-CLI sessions in the series plan.
- Migrating progress made before this change: the app is not live, and a Part 1 step already done stays done.

## Impact

- **Code:** `app/eval_coach/{part_steps,criteria_steps,engine,state,reset,project,server}.py`; `web/js/{views,part-steps,app,ui}.js` and `web/styles.css` for the header, Copy and Continue; the stand-in `e2e-work/harness/fake_cli.py`.
- **Content:** `content/part-1-steps.json`, `content/part-2-steps.json` (restart words only), `content/lesson-ui.json`, `content/settings.json`.
- **Storage:** `<home>\part1\<step>\prompt.md` (now holds the full pasted text), `<project>\part-1\` and `<project>\part-2\` files (moved on a restart), `progress.json` step records and `lessons.step_checks` (cleared on a restart), `<home>\reset-backup\` (replaced by a restart), one new field per Part 1 run step recording that the AI was auto-started.
- **Docs:** `docs/SPEC.md`, the local plan (`docs/local/`, not in git), `AGENTS.md` Status, `docs/temp/series-review-pending-changes.md`.
- **Tests:** `tests/test_part_1_steps.py`, `tests/test_part_1_content.py`, `tests/test_reset.py`, `tests/test_parts.py`, `tests/frontend/part1.spec.js`, `tests/frontend/part2.spec.js`, `tests/frontend/mock_api.py`, the harness runs.
