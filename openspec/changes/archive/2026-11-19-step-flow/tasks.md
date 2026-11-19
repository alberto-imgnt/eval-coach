# Tasks

Apply uses the stand-in `e2e-work\harness\fake_cli.py`; no real CLI runs without the user's approval. Do not edit anything under `web/`, `content/lesson-ui.json` or step `ui` blocks (groups 4 and 6, and the words in group 1) until the user has confirmed the interface scope in `proposal.md`.

## 1. State shape and words

- [x] 1.1 Add `auto_started: False` to the `cold` and `rewrite` records in `new_part_1_steps` (`state.py`) and confirm a `progress.json` without the field loads and gets the default: new case in `tests/test_part_1_steps.py`, run `python -m unittest tests.test_part_1_steps`.
- [x] 1.2 Rewrite the `cold` and `rewrite` instructions, troubleshooting and `ui` words in `content/part-1-steps.json` for the paste flow (save, wait for the AI window, copy, paste, "each step opens a new chat"), drop the typed `line` and the "Press Check my work" and "Send to AI" wording from every Part 1 step, add `cli_mode: "paste"`, the closing `instruction`, the Copy and copied strings, the "Open a new AI chat" label, and the inline-list heading. Verify with `python -m unittest tests.test_part_1_content tests.test_participant_vocabulary tests.test_content_banned_words` (extend `test_part_1_content` to assert none of "Send to AI", "Start my AI", "Check my work" or a bare "CLI" appears in the five steps).

## 2. Paste flow on the server

- [x] 2.1 Add the closing instruction to `run_copy`, write the same text to `prompt.md`, rewrite `prompt.md` on a prompt save while the AI runs without restarting it, and return `data.paste_text` instead of `data.preview` (`part_steps.py`). Verify with new cases in `tests/test_part_1_steps.py` for folder contents, text equality and the rewrite-while-running scenario.
- [x] 2.2 Implement the auto-start rule (`_auto_start_ok`) and call it from `WriteAndRun.submit` after a prompt save; refactor `start` so both share one launch routine; set `auto_started`; report a start failure as `cli.blocked` without failing the save. Verify with cases for each scenario in `ai-window-paste-flow` (first save starts, second save does not restart, stop then save does not restart, revisit does nothing, saved answer blocks, done, locked and pre-setup refuse), run `python -m unittest tests.test_part_1_steps`.
- [x] 2.3 Remove `send` from `WriteAndRun` so `POST /api/step/send` is refused as not supported for Part 1 run steps, and expose `cli.mode` in the step view. Verify with an HTTP case in `tests/test_http_course.py` and `python -m unittest tests.test_http_course`.
- [x] 2.4 Update `docs/SPEC.md` "Part 1" (steps, API fields) for 2.1 to 2.3. Verify by reading the section against the spec delta.

## 3. Completion without a Check button

- [x] 3.1 Split each Part 1 kind's `check` into `report` and `_finish`, add `settle` and the `gate` and `ready` fields to the step view (`part_steps.py`). Verify that existing gate cases in `tests/test_part_1_steps.py` still pass unchanged (`python -m unittest tests.test_part_1_steps`), proving the gate items did not move.
- [x] 3.2 Give `_start_watcher` an optional completion callback run under the engine lock after the output is saved, and settle `cold` and `rewrite` from it (`engine.py`, `part_steps.py`). Verify with stand-in cases: output captured finishes `cold`; `rewrite` with an unchanged prompt stays open; choosing the label set late finishes it; a prompt edit after the run does not.
- [x] 3.3 Settle `own` on a save that leaves its gate met, and keep `POST /api/step/check` working for every kind (it is what Continue calls for `score` and `rescore`). Verify with cases that autosaving a half-typed gap does not finish `score`, and that the check call after all fields are filled does.
- [x] 3.4 Update `docs/SPEC.md` "Part 1" for the completion moments. Verify by reading it against the spec delta.

## 4. Part 1 interface (after the user confirms the interface scope)

- [x] 4.1 In `renderTermHead` (`views.js`), draw paste mode: no typed-line block, no "Send to AI", no "Start again"; keep status, model toggle, Stop; add the new chat note and "Open a new AI chat" (id `cli-start`). Steps without `cli.mode === "paste"` must render exactly as before. Verify with a Playwright case for a Part 1 step and the existing Part 3 header cases in `tests/frontend/ui.spec.js`.
- [x] 4.2 In `part-steps.js`, replace the "What your AI will read" preview with the text to paste and a Copy button (`navigator.clipboard.writeText`, selection fallback with the Ctrl+C line, a `role="status"` copied line, disabled when no prompt is saved). Verify with Playwright cases for copy, refused clipboard (stubbed rejection), empty state and plain-text rendering of angle brackets.
- [x] 4.3 In `views.js`, stop rendering "Check my work" for Part 1, show `step.gate` through `renderCheckResult` while the step is not done, and show a Continue button on `score` and `rescore` that is disabled until `ready` and, when pressed, flushes saves, calls `POST /api/step/check` and then continues. Verify with Playwright cases for each Part 1 step in `tests/frontend/part1.spec.js` (including the "typing is never cut off" scenario and keyboard reachability), and confirm `tests/frontend/part2.spec.js` and the Part 3 cases still show "Check my work".
- [x] 4.4 Update `tests/frontend/mock_api.py` and `tests/frontend/real_server.py` for `paste_text`, `gate`, `ready` and the removed `send`. Run `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` and confirm it passes.

## 5. Restart on the server

- [x] 5.1 Add the optional `restart` plan to `Part` (`state.py`) with the per-step owned records and files for Parts 1 and 2, none for Part 3, and add `reset.build_restart_plan` with every moved name drawn from the existing inventory lists. Verify with a case in `tests/test_parts.py` (Part 3 has no plan) and a coverage case in `tests/test_reset.py` that fails when a restartable file is on no list.
- [x] 5.2 Implement `engine.step_restart(step, confirm)` with the guards, stop-CLI, stage, thresholds worksheet rewrite, swap, rollback, record and done-list clearing, and `lessons.step_checks` clearing described in `design.md` Decision 6, and add `POST /api/step/restart` and the `restart` block in the step view (`engine.py`, `server.py`, `criteria_steps.py` for the stripped worksheet). Verify with cases in `tests/test_reset.py` or a new `tests/test_step_restart.py` for every row of the table in `design.md` and every scenario in `step-restart` (later steps re-lock, other Parts untouched, answer key untouched, backup replaced, failure changes nothing, Part 3 and unfinished steps refused), run `python -m unittest tests.test_step_restart tests.test_reset`.
- [x] 5.3 Update `docs/SPEC.md` (restart, API), and the local plan's master task table (`docs/local/IMPLEMENTATION-PLAN.md`, not in git; the 4b known inconsistency) if it is on this machine. Verify by reading both against the specs.

## 6. Restart interface (after the user confirms the interface scope)

- [x] 6.1 Add the `restart` words to `content/settings.json` and the "Start this step again" control and confirm dialog (default action keeps everything, body lists the steps, the backup folder and that the backup is replaced) on finished Part 1 and Part 2 steps in `views.js` and `app.js`; clear the matching drafts and the step cache after a restart. Verify with Playwright cases in `tests/frontend/part1.spec.js` and `tests/frontend/part2.spec.js` for cancel, confirm, keyboard focus on the keep action, the announced result and absence on Part 3 and unfinished steps.
- [x] 6.2 Run `python -m unittest tests.test_participant_vocabulary tests.test_content_banned_words` to confirm the new words follow the vocabulary rules.

## 7. Harness and integration

- [x] 7.1 Teach `e2e-work\harness\fake_cli.py` to answer the closing instruction line from `prompt.md`, and update `e2e-work\harness\run.js` Part 1 stages to paste (send the last line through `/api/terminal/input`) instead of pressing Send and Check. Verify with `node e2e-work\harness\run-all.js --fresh` written to a file, then `--both` for the promptfoo track.
- [x] 7.2 Integration checks, one at a time: `python -m unittest discover -s tests`, then the same on `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe`, then the Playwright command from 4.4, then `python tools\build_pyz.py --smoke`. All four must pass.
- [x] 7.3 Update `AGENTS.md` Status (Part 1 flow, restart in Parts 1 and 2, 4b pending) and `docs/temp/series-review-pending-changes.md` (change 4 proposed and applied). Verify by reading both.

## Workflow follow-up

- Real-tool confirmation of the paste flow (auto-start, paste, output capture) was done on 2026-11-19 with `e2e-work\harness\real-paste.js`, one cold-step session per tool (GitHub Copilot CLI, Claude Code, Devin CLI; 17 checks each, all passed), with the user's approval.
- Archive after the user's review, running the archive gate with receipts for `backend`, `backend-embedded`, `interface`, `build` and `e2e`.
- Propose change 4b (`part-3-ai-flow`) soon after, so Part 1 and Part 3 do not stay different in the shared AI window.
