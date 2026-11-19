# Tasks

Apply uses the stand-in `e2e-work\harness\fake_cli.py`; no real CLI runs without the user's approval. Do not edit anything under `web/`, `content/lesson-ui.json` or step `ui` blocks (groups 4 and 5, and the words in group 1) until the user has confirmed the interface scope in `proposal.md`. Apply after `step-flow` is archived (design, Open Question 6).

## 1. State shape and words

- [x] 1.1 Add `auto_started: False` to the default records of `generate`, `build`, `fixtures`, `fixtures-config`, `readback`, `key`, `fix`, `baseline` and `live` (`state.py`) and confirm a `progress.json` without the field loads and gets the default: new case in `tests/test_engine_gates.py`, run `python -m unittest tests.test_engine_gates`.
- [x] 1.2 In `content/steps.json` add `cli_mode: "paste"` to the nine AI steps and a shared `paste_ui` block (note, new chat label, ready hint, Copy strings, paste heading and note, confirm title and body), merged under each step's own `ui` on load. Rewrite the nine steps' instructions, troubleshooting and gate failure lines for the paste flow (it opens by itself, wait until ready, copy, paste, press Check my work) and drop every "Start my AI", "Send to AI", "Start again", "Press Send" and "Press Start". Verify by extending `tests/test_part_1_content.py` (or a new `tests/test_part_3_content.py`) to scan every paste-mode step in both files for those phrases and a bare "CLI", then run `python -m unittest tests.test_part_3_content tests.test_part_1_content tests.test_participant_vocabulary tests.test_content_banned_words`.

## 2. The rule and the flow on the server

- [x] 2.1 Move `step_start`'s folder preparation, label, model recording, `live` start hashes and `generate` watcher into one `_launch_step(step)` and make `step_start` call it, with no change in behavior. Verify with the existing start cases (`python -m unittest tests.test_engine_gates tests.test_live_mode tests.test_baseline_step`) passing unchanged.
- [x] 2.2 Report `cli.mode`, `cli.can_auto_start`, `cli.has_result` and `cli.paste_ready` from `_detail`, and refuse `step_send` for a paste-mode step as not supported (`engine.py`). Verify with cases in `tests/test_engine_gates.py` for each field per step kind and an HTTP case in `tests/test_http.py` for the refused send.
- [x] 2.3 Implement `_auto_start_ok` (design Decisions 2 and 3, including the per-folder "nothing to lose" check and `live` excluded), `engine.step_auto_start(step)` and `POST /api/step/auto-start` (`engine.py`, `server.py`). A start failure sets `_cli_blocked[step]` and never raises. Verify with cases for every scenario in `part-3-paste-flow` (first visit starts, second visit and Stop-then-revisit start nothing, reading ahead, locked, done, before setup, another window running, `live`, a file or fixture text or sealed key in the folder, a start that fails and the manual retry), run `python -m unittest tests.test_engine_gates tests.test_http tests.test_live_mode`. Include a case that the sealed key file is never opened.
- [x] 2.4 Confirm the model is recorded by every start route and that `generate` runs 2 to 5 start through `step_start` with the label "run n of 5". Verify with cases in `tests/test_engine_gates.py` and `tests/test_baseline_step.py`.
- [x] 2.5 Update `docs/SPEC.md` (Part 3 steps, the new route, the view fields, the removed Send) against the spec delta. Verify by reading the section.

## 3. Existing tests move off Send

- [x] 3.1 Add a test helper `paste_step_line(engine, step)` that types the step's line and Enter through `engine.terminal_input` (the participant's keystroke path). Replace the `step_send` and `/api/step/send` calls in `tests/test_engine_gates.py`, `test_baseline_step.py`, `test_live_mode.py`, `test_promptfoo_track.py`, `test_course.py`, `test_http.py`, `test_example_fixtures.py` and `test_setup_gate.py` with it where they need the AI to answer, and assert the refusal where they tested Send itself. Verify with `python -m unittest discover -s tests`, run once, and keep Parts 1 and 2 passing unchanged.

## 4. Part 3 interface (after the user confirms the interface scope)

- [x] 4.1 In `views.js`, draw Part 3 paste mode in `renderPasteTermHead`: the note, the line as the text to paste with the Copy control (reusing `copyPasteText` from `part-steps.js`, ids `copy-paste` and `copy-status`), Stop, and "Open a new AI chat" (id `cli-start`) with a confirm when `cli.started` or `cli.has_result`; no `cli-send` and no `cli-retry`. Steps without `cli.mode === "paste"` render as before. Verify with Playwright cases in `tests/frontend/ui.spec.js` for `generate`, `build`, `live` (Copy and chat off before the warning is ticked) and a finished step (controls off), run the Playwright command from AGENTS.md.
- [x] 4.2 In `app.js`, call `POST /api/step/auto-start` once when an active paste-mode step is shown and `cli.can_auto_start` is true (not on reading ahead, not on a poll), then refresh the state. Verify with Playwright cases for a first visit, a revisit and a locked step, and that no request is sent when `can_auto_start` is false.
- [x] 4.3 Update `tests/frontend/mock_api.py` and `tests/frontend/real_server.py` for the new fields and route and the removed Send, and move the roughly 60 Start and Send assertions in `tests/frontend/ui.spec.js` to Copy, the note and "Open a new AI chat". Verify with the full Playwright command from AGENTS.md; confirm Part 1 and Part 2 specs and "Check my work" in Part 3 pass unchanged.

## 5. Harness and integration

- [x] 5.1 Update `e2e-work\harness\run.js` and `lesson-stages.js` Part 3 stages to wait for the automatic start (or call `/api/step/auto-start`) and paste (type the step's line through `/api/terminal/input`) instead of pressing Start and Send; `fake_cli.py` already answers the Part 3 lines. Verify with `node e2e-work\harness\run-all.js --fresh` written to a file, then `--both` for the promptfoo track, and `node e2e-work\harness\classifier-check.js`.
- [x] 5.2 Integration checks, one at a time: `python -m unittest discover -s tests`, then the same on `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe`, then the Playwright command, then `python tools\build_pyz.py --smoke`. All four must pass.
- [x] 5.3 Update `AGENTS.md` Status (Part 3 flow, the Part 1 and Part 3 inconsistency note removed), `docs/temp/series-review-pending-changes.md` (change 4b proposed and applied) and, if it is on this machine, the master task table in `docs/local/IMPLEMENTATION-PLAN.md` (never staged). Verify by reading them.

## Workflow follow-up

- Real-tool confirmation of the Part 3 paste flow (automatic start on opening `generate` and `build`, paste, run capture) needs the user's single-use approval per run: a Part 3 version of `e2e-work\harness\real-paste.js`, one session per tool (GitHub Copilot CLI, Claude Code, Devin CLI). Mask any account name or email; do not commit transcripts.
- Archive after the user's review, running the archive gate with receipts for `backend`, `backend-embedded`, `interface`, `build` and `e2e` (and `e2e-promptfoo`, since the harness covers both tracks).
