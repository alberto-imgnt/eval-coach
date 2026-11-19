# Proposal

## Why

Change 4 (`step-flow`) moved Part 1 to a copy-and-paste flow: the AI window opens by itself, the participant copies one text and pastes it, and the app types nothing. Part 3 shares the same AI window but still uses the old flow in every step that runs the AI: Start my AI, wait, Send to AI, wait, Start again. Until Part 3 follows, one AI window behaves two ways depending on the Part (series review items 8 and 8a, change 4b; `docs/temp/series-review-pending-changes.md`).

Part 3 differs from Part 1 in three ways that the shared rules do not yet cover: the participant writes no prompt (the line the app used to type is fixed by the step), there is no save to hang an automatic start on, and the AI runs in several kinds of folder (a blind scratch folder, two other scratch folders, or the participant's project folder). This change adapts the shared paste flow to those facts and leaves Part 3's gates, teaching and "Check my work" as they are.

## What Changes

- **The AI window starts by itself when a Part 3 AI step is opened (item 8, 8a).** The page asks the server to apply the shared auto-start rule once when it shows an open step. The server starts a fresh AI window (a new process, on the model the toggle chose) only when the step is active, not done, no AI window is running, the AI was not already auto-started for this step, and nothing in the step's scratch folder or its saved result would be lost. It never starts on a read-ahead view, a locked step, a finished step or a second visit. A note says each step opens a new chat.
- **Copy and paste replaces Send to AI in the Part 3 AI steps.** The line the app typed becomes the **text to paste**, shown with a **Copy** button. The scratch folders keep their existing files (`blind\prompt.md`, the fixtures and key folders' inputs); nothing new is written there. The app no longer types a line into the AI for these steps, and "Send to AI" and "Start again" are removed from them.
- **"Open a new AI chat" replaces "Start my AI" and "Start again"** in these steps. It is the one way to try again or to start run 2 to 5 of `generate`, and it asks first when a window is running or the step's scratch folder holds a result.
- **Steps covered:** `generate`, `build`, `fixtures`, `fixtures-config`, `readback`, `key`, `fix`, `baseline`, and the optional `live` step. `live` keeps its warning and AI choice first, and its window is never started by itself (only by "Open a new AI chat"). `predict` and `run` start no AI and are unchanged.
- **Part 3 keeps "Check my work", its nudges and the other gates.** `step-flow` removed the button from Part 1 only; the series review keeps it here because Check is where the teaching happens.
- **No "Start this step again" for Part 3** (series review section 7 still applies).
- **Words and docs.** Part 3's instructions, troubleshooting and gate failure lines in `content/steps.json` stop naming Start my AI, Send to AI, "Press Send" and "Press Start". `docs/SPEC.md`, `AGENTS.md` Status and the series review file are updated. The known-inconsistency note about Part 1 and Part 3 is removed.

### Interface authorization (AGENTS.md rule 11)

**Requested, not yet granted**: apply starts only after you confirm this scope (it may touch `web/` and interface copy within it, and nothing else).

- Part 3 AI window header for the steps above: no "This exact line will be typed" block, no "Send to AI" and no "Start again"; a note that each step opens a new chat; "Stop" kept; one "Open a new AI chat" button (the existing `cli-start` id, relabelled; `cli-send` and `cli-retry` are not drawn for these steps).
- A **text to paste** block with a **Copy** button, a copied confirmation read by screen readers and the Ctrl+C fallback, drawn in the AI window head (Part 3 has no prompt editor to put it in). It reuses Part 1's Copy behavior.
- A confirm dialog on "Open a new AI chat" when a window is running or the folder holds a result.
- Interface copy: the `ui` blocks and instructions in `content/steps.json`, and the shared paste words for Part 3.

No other layout, styling, element id or component changes. Part 3's step panels, gates and result lists are not touched.

## Capabilities

### New Capabilities
- `part-3-paste-flow`: how Part 3's AI steps start the AI window by themselves when opened, what text the participant copies, what counts as "nothing to lose" in each kind of folder, how "Open a new AI chat" replaces Start and Start again, and which Part 3 steps and behaviors do not change.

### Modified Capabilities
- `ai-window-paste-flow` (introduced by `step-flow`): the shared requirement that a step opts in by content now says each Part defines its own trigger for the automatic start and its own pasted text; Part 1's first-save trigger and Part 3's step-open trigger are both instances of it. **Archive `step-flow` first**, because this capability does not exist in `openspec/specs/` until then.

## Out of Scope

- "Start this step again" for Part 3 (shared project files and the sealed answer key need their own design).
- Removing "Check my work" from Part 3, or changing any Part 3 gate, nudge or teaching message.
- Part 2 (starts no AI), lesson AI activities, the setup AI working test page and the AI window mini lesson. They keep their own Start and Send.
- Running the AI for the participant, answering any AI prompt, or setting a permission flag (AGENTS.md rules 2 to 5).
- Course locking, skipping and demo access (change 5), a technical mode (item 0), and any change to the Sonnet / Haiku toggle.
- Real-CLI runs during planning or apply without the user's approval. The flow is verified on the stand-in; the real tools are covered by approved sessions (see `tasks.md`).
- Migrating progress made before this change: the app is not live, and a Part 3 step already done stays done.

## Impact

- **Code:** `app/eval_coach/{engine,server,state,project}.py`; `web/js/{views,app,part-steps}.js` (shared Copy helper) and `web/styles.css` only if the paste block needs a rule Part 1 does not already have; the stand-in `e2e-work/harness/fake_cli.py`.
- **Content:** `content/steps.json` (step instructions, troubleshooting, gate failure lines, `ui` blocks, a shared paste-words block), `content/lesson-ui.json` only where a Part 3 step reads from it.
- **Storage:** `progress.json` Part 3 step records gain `auto_started` (nine AI-capable steps); scratch folders `<home>\blind`, `<home>\fixtures-work`, `<home>\key-work` keep their present contents and lifecycle.
- **Docs:** `docs/SPEC.md`, `AGENTS.md` Status, `docs/temp/series-review-pending-changes.md`, the local plan (`docs/local/`, not in git).
- **Tests and harness:** `tests/frontend/ui.spec.js` (about 60 hits on Start and Send), `tests/test_engine_gates.py`, `test_baseline_step.py`, `test_live_mode.py`, `test_promptfoo_track.py`, `test_course.py`, `test_http.py`, `test_example_fixtures.py`, `test_setup_gate.py`, `e2e-work/harness/run.js` and `lesson-stages.js`.
