# Tasks

Interface tasks (groups 4 to 7) wait for the user's authorization of the scope in the proposal (rule 11). Groups 1 to 3 change server behavior and content only. Run the two backend suites one after the other, and use the stand-in `e2e-work/harness/fake_cli.py`; never run a real CLI without approval.

## 1. Preflight items and AI detection (backend)

- [x] 1.1 In `app/eval_coach/preflight.py` remove `signin` from `ITEM_IDS`, `_check_signin`, `confirm_signin` and `signed_in_command` use; make `cli` pass when a command is saved and resolves; make `require_test_ready` need only `cli`. Update `tests/test_preflight.py` and `tests/helpers.py`. Verify: `python -m unittest tests.test_preflight`.
- [x] 1.2 Add `_detect_ais` to `_job_check_all` and `cli.tools`/`cli.found`/`preselect` to `Preflight.view` (one entry per distinct `cli_command`, `other` excluded, `other_installs` for extra recipes). Tests: none, one and several found with a fake runner; no tool started. Verify: `python -m unittest tests.test_preflight`.
- [x] 1.3 Add `poll_test_result()` (reads the test folder, records a pass only, never a failure) and the `POST /api/preflight/test/poll` route in `engine.py` and `server.py`; stop the AI process on a pass. Tests: pass, not yet, wrong output records nothing. Verify: `python -m unittest tests.test_preflight tests.test_http`.
- [x] 1.4 Remove `PF_SIGNIN`, `preflight_cli_start`, `preflight_signin_confirm` and their routes in `engine.py`/`server.py`; keep `PF_TEST` and `PF_RECIPE`. Verify: `python -m unittest discover -s tests`.
- [x] 1.5 Add the hidden `--custom-ai` flag in `__main__.py`, carry it to the preflight view as `custom_ai`, and start the app with it in `tests/helpers.py` and the harness. Verify: `python -m unittest discover -s tests` and `node e2e-work\harness\classifier-check.js`.

## 2. Content (words and data)

- [x] 2.1 `content/cli-recipes.json`: add a `plain` field (plain words and size) to every recipe, mark `other` as not for participants. Verify: `python -m unittest tests.test_content_and_resources`.
- [x] 2.2 `content/preflight.json`: wording for the summary page, Choose your AI, the merged test page, the lesson (`ai_window_lesson` with intro, legend heading and a generic marker set), the reopen label and the lesson dialog close label; remove sign-in wording and text about typing a command from the participant text. Verify: `python -m unittest tests.test_content_banned_words tests.test_content_and_resources`.
- [x] 2.3 `content/settings.json`: "What am I looking at?" label and the summary row names. Verify: `python -m unittest tests.test_content_banned_words`.
- [x] 2.4 Add content tests: participant text has no "CLI" outside product names (extend the `participant-vocabulary` test to the new keys); every marker has a number, label and text; no account name or email in `ai_window_lesson`; the recipe `plain` field exists for each shown recipe. Verify: `python -m unittest discover -s tests`.

## 3. Docs in step with the backend

- [x] 3.1 Update `docs/SPEC.md` (setup, preflight API, view fields, removed routes, new poll route, `--custom-ai`), `docs/PHASE2.md` and the `docs/IMPLEMENTATION-PLAN.md` master task table; update `AGENTS.md` rule 6 (tool list fixed to three with a test-only free-text route). Verify: read the changed sections against the code.

## 4. Wizard pages (interface; needs authorization)

- [x] 4.1 `web/js/preflight.js`: client page list with `summary` and `ai_window`, forward navigation that skips passed pages, Next/Back/page dots, "n of total". Verify: Playwright interface tests.
- [x] 4.2 Summary page: starts the check on arrival (no double start while a job runs), shows one row per check, Next goes to the first page that needs the participant. Verify: Playwright.
- [x] 4.3 Choose your AI page: found tools with "Use this AI" (preselect when one), install per missing tool with consent and "Show the command", "Another way to install" for extra recipes, requirement-first for GitHub Copilot CLI, re-check after an install ends; typed field only when `custom_ai`. Verify: Playwright (stand-in with `--custom-ai`).
- [x] 4.4 Merged working test page: Start, Send, Check, quiet polling after Send, no sign-in button; remove the old sign-in page code and ids from `preflight.js`. Verify: Playwright.
- [x] 4.5 Terminal only on `working_test` and during a recipe install, framed "Your AI window" (`wizardUsesTerminal`, `app.js` layout). Verify: Playwright (no terminal on Python, Project folder, lesson pages).
- [x] 4.6 `app.js`: `pfProject` moves to `ai_window` instead of closing the wizard; Finish closes as before; the wizard stays open while the flag is set though `pf.passed` is true; Settings-opened wizard closes back to Settings. Verify: Playwright (first run, from Settings, from the banner).

## 5. Mini lesson component (interface; needs authorization)

- [x] 5.1 `renderAiWindowLesson` (image, numbered focusable markers positioned in percent, tooltip on hover and focus, legend list, alt text, generic variant without an image) and styles in `web/styles.css` using the design system. Verify: Playwright (hover, keyboard focus, legend text, 390 px wide).
- [x] 5.2 Reopen entries: "What am I looking at?" in the Settings setup group and in the AI window head, opened with `dialog.js`; the AI process keeps running. Verify: Playwright.
- [x] 5.3 Settings summary lists the same items as the wizard without a sign-in row. Verify: Playwright.

## 6. Screenshots (needs real-CLI approval per session)

- [x] 6.1 Ask the user for approval, then capture one masked screenshot per tool (GitHub Copilot CLI, Claude Code, Devin CLI) with Playwright from this app's AI window into `web/img/ai-window/`; single-use approvals only, no install recipes, no settings or credential edits; mask account name and email; review by eye. Verify: the image shows no personal data.
- [x] 6.2 Write the marker data, alt text and `captured` date for each tool in `content/preflight.json`. Verify: `python -m unittest tests.test_content_and_resources`.

## 7. Verification

- [x] 7.1 Backend on system Python, then on embedded 3.13: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests` (one after the other).
- [x] 7.2 Interface tests: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`.
- [x] 7.3 Rebuild and smoke test: `python tools\build_pyz.py --smoke`.
- [x] 7.4 Stand-in end to end, writing output to a file: `node e2e-work\harness\run-all.js --fresh` (and `--track promptfoo` or `--both`); update the harness to the merged test page.
- [x] 7.5 Update `docs/temp/series-review-pending-changes.md` to mark change 2 as proposed and, after archive, applied.

## 8. Background AI test (added 2026-11-17)

Group 8 follows the same rules: backend and content first on the stand-in, interface after (already authorized, see the proposal's 2026-11-17 addition), and no real CLI without single-use approval.

- [x] 8.1 `content/cli-recipes.json`: add `headless` (`args` with `{line}`, `timeout_seconds` 120) to the Copilot, Claude and Devin recipes, using each vendor's one-shot flag (`-p`) and no permission flags. `content/preflight.json`: `working_test.headless_line`, messages `working_test_passed_background` and `ai_test_background_needs_you` (plain words naming sign-in, a question in the AI window and no network), and the Choose your AI "Testing your AI" line. Tests: every shown tool's `headless` data has a `{line}` argument, a positive limit and none of the permission flags (`--allow-all`, `--allow-all-tools`, `--yolo`, `--permission-mode`, `--dangerously-skip-permissions`, `--allowedTools`, `bypass`); the new text passes the banned-words and "CLI" vocabulary tests. Verify: `python -m unittest tests.test_content_and_resources tests.test_content_banned_words tests.test_participant_vocabulary`.
- [x] 8.2 `e2e-work/harness/fake_cli.py`: a one-shot mode (`-p <line>`) that exits 0, plus switches to exit non-zero, hang past the limit and never open a window, so the stand-in can drive every outcome. Verify: the harness classifier check and the tests in 8.3.
- [x] 8.3 `preflight.py`: `start_ai_test()` thread (look up `headless` by `cli_command`, no window, stdin `DEVNULL`, output to a log file in `cli-test` that is never read, time limit, process-tree kill, exit 0 → `working_test` passed with `test_passed_command`, anything else → `needs_you`, never `failed`), `cancel_ai_test()`, and the running state in the view (`working_test.background`). Tests: pass, non-zero exit, timeout, start error, no `headless` data, cancel, nothing read from the log, no permission flag in the argv. Verify: `python -m unittest tests.test_preflight`.
- [x] 8.4 `engine.py`/`server.py`: `preflight_cli` starts the background test after a usable command is saved and the test has not already passed for it; refuse to start while any AI session runs; `preflight_test_start`, an install start and a changed command cancel a running one. Tests: starts on choose, no terminal session is created, cancelled by a visible start and an install, only one AI process at a time. Verify: `python -m unittest tests.test_preflight tests.test_http tests.test_engine_gates`.
- [x] 8.5 `web/js/preflight.js`/`app.js`: after "Use this AI" show "Testing your AI" with no terminal while the job runs; when it ends move to the first page that has not passed (Project folder or Your AI window after a pass, the AI working test page after "needs you" with its plain line); the AI working test page counts as passed after a background pass. Tests: Playwright with the stand-in for pass, exit non-zero, timeout, and no terminal while testing. Verify: Playwright interface tests.
- [x] 8.6 Docs: `docs/SPEC.md` (background test, `headless` data, view fields, no new routes), `docs/PHASE2.md`, the `docs/IMPLEMENTATION-PLAN.md` task table, and `AGENTS.md` rule 3 clarified: a process the app started itself may be judged by its exit status, never by what it printed. Verify: read the changed sections against the code.
- [x] 8.7 Real runs, one per tool and each only with the user's single-use approval after the full command text is verified: confirm the argv works, that none opens a browser, and the time limit; adjust the data if needed. Verify: the stand-in suites still pass and the recorded timings are noted in `design.md` decision 9.
- [x] 8.8 Re-run verification: both backend suites one after the other, the Playwright interface tests, `python tools\build_pyz.py --smoke`, and the stand-in end to end (`node e2e-work\harness\run-all.js --fresh`, writing to a file; the harness must handle the automatic move past the AI working test page).

## 9. Check everything only where it helps (added 2026-11-17)

- [x] 9.1 `web/js/preflight.js` (`renderWizard`): render the footer Check everything button (`#pf-check-all`, same label and action) only on the `python`, `node`, `promptfoo`, `cli` and `project` pages. Update the interface tests and the harness setup stage that pressed it on the Track page (the Checking your computer page now starts the checks). Verify: Playwright interface tests.
- [x] 9.2 `docs/SPEC.md` (wizard paragraph) and `docs/PHASE2.md` say where the button shows. Rebuild `dist\eval-coach.pyz` and run the stand-in end to end (`node e2e-work\harness\run-all.js --fresh`, to a file). Verify: both pass.
