# Tasks

Interface tasks (groups 4 to 7) wait for the user's authorization of the scope in the proposal (rule 11). Groups 1 to 3 change server behavior and content only. Run the two backend suites one after the other, and use the stand-in `e2e-work/harness/fake_cli.py`; never run a real CLI without approval.

## 1. Preflight items and AI detection (backend)

- [ ] 1.1 In `app/eval_coach/preflight.py` remove `signin` from `ITEM_IDS`, `_check_signin`, `confirm_signin` and `signed_in_command` use; make `cli` pass when a command is saved and resolves; make `require_test_ready` need only `cli`. Update `tests/test_preflight.py` and `tests/helpers.py`. Verify: `python -m unittest tests.test_preflight`.
- [ ] 1.2 Add `_detect_ais` to `_job_check_all` and `cli.tools`/`cli.found`/`preselect` to `Preflight.view` (one entry per distinct `cli_command`, `other` excluded, `other_installs` for extra recipes). Tests: none, one and several found with a fake runner; no tool started. Verify: `python -m unittest tests.test_preflight`.
- [ ] 1.3 Add `poll_test_result()` (reads the test folder, records a pass only, never a failure) and the `POST /api/preflight/test/poll` route in `engine.py` and `server.py`; stop the AI process on a pass. Tests: pass, not yet, wrong output records nothing. Verify: `python -m unittest tests.test_preflight tests.test_http`.
- [ ] 1.4 Remove `PF_SIGNIN`, `preflight_cli_start`, `preflight_signin_confirm` and their routes in `engine.py`/`server.py`; keep `PF_TEST` and `PF_RECIPE`. Verify: `python -m unittest discover -s tests`.
- [ ] 1.5 Add the hidden `--custom-ai` flag in `__main__.py`, carry it to the preflight view as `custom_ai`, and start the app with it in `tests/helpers.py` and the harness. Verify: `python -m unittest discover -s tests` and `node e2e-work\harness\classifier-check.js`.

## 2. Content (words and data)

- [ ] 2.1 `content/cli-recipes.json`: add a `plain` field (plain words and size) to every recipe, mark `other` as not for participants. Verify: `python -m unittest tests.test_content_and_resources`.
- [ ] 2.2 `content/preflight.json`: wording for the summary page, Choose your AI, the merged test page, the lesson (`ai_window_lesson` with intro, legend heading and a generic marker set), the reopen label and the lesson dialog close label; remove sign-in wording and text about typing a command from the participant text. Verify: `python -m unittest tests.test_content_banned_words tests.test_content_and_resources`.
- [ ] 2.3 `content/settings.json`: "What am I looking at?" label and the summary row names. Verify: `python -m unittest tests.test_content_banned_words`.
- [ ] 2.4 Add content tests: participant text has no "CLI" outside product names (extend the `participant-vocabulary` test to the new keys); every marker has a number, label and text; no account name or email in `ai_window_lesson`; the recipe `plain` field exists for each shown recipe. Verify: `python -m unittest discover -s tests`.

## 3. Docs in step with the backend

- [ ] 3.1 Update `docs/SPEC.md` (setup, preflight API, view fields, removed routes, new poll route, `--custom-ai`), `docs/PHASE2.md` and the `docs/IMPLEMENTATION-PLAN.md` master task table; update `AGENTS.md` rule 6 (tool list fixed to three with a test-only free-text route). Verify: read the changed sections against the code.

## 4. Wizard pages (interface; needs authorization)

- [ ] 4.1 `web/js/preflight.js`: client page list with `summary` and `ai_window`, forward navigation that skips passed pages, Next/Back/page dots, "n of total". Verify: Playwright interface tests.
- [ ] 4.2 Summary page: starts the check on arrival (no double start while a job runs), shows one row per check, Next goes to the first page that needs the participant. Verify: Playwright.
- [ ] 4.3 Choose your AI page: found tools with "Use this AI" (preselect when one), install per missing tool with consent and "Show the command", "Another way to install" for extra recipes, requirement-first for GitHub Copilot CLI, re-check after an install ends; typed field only when `custom_ai`. Verify: Playwright (stand-in with `--custom-ai`).
- [ ] 4.4 Merged working test page: Start, Send, Check, quiet polling after Send, no sign-in button; remove the old sign-in page code and ids from `preflight.js`. Verify: Playwright.
- [ ] 4.5 Terminal only on `working_test` and during a recipe install, framed "Your AI window" (`wizardUsesTerminal`, `app.js` layout). Verify: Playwright (no terminal on Python, Project folder, lesson pages).
- [ ] 4.6 `app.js`: `pfProject` moves to `ai_window` instead of closing the wizard; Finish closes as before; the wizard stays open while the flag is set though `pf.passed` is true; Settings-opened wizard closes back to Settings. Verify: Playwright (first run, from Settings, from the banner).

## 5. Mini lesson component (interface; needs authorization)

- [ ] 5.1 `renderAiWindowLesson` (image, numbered focusable markers positioned in percent, tooltip on hover and focus, legend list, alt text, generic variant without an image) and styles in `web/styles.css` using the design system. Verify: Playwright (hover, keyboard focus, legend text, 390 px wide).
- [ ] 5.2 Reopen entries: "What am I looking at?" in the Settings setup group and in the AI window head, opened with `dialog.js`; the AI process keeps running. Verify: Playwright.
- [ ] 5.3 Settings summary lists the same items as the wizard without a sign-in row. Verify: Playwright.

## 6. Screenshots (needs real-CLI approval per session)

- [ ] 6.1 Ask the user for approval, then capture one masked screenshot per tool (GitHub Copilot CLI, Claude Code, Devin CLI) with Playwright from this app's AI window into `web/img/ai-window/`; single-use approvals only, no install recipes, no settings or credential edits; mask account name and email; review by eye. Verify: the image shows no personal data.
- [ ] 6.2 Write the marker data, alt text and `captured` date for each tool in `content/preflight.json`. Verify: `python -m unittest tests.test_content_and_resources`.

## 7. Verification

- [ ] 7.1 Backend on system Python, then on embedded 3.13: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests` (one after the other).
- [ ] 7.2 Interface tests: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`.
- [ ] 7.3 Rebuild and smoke test: `python tools\build_pyz.py --smoke`.
- [ ] 7.4 Stand-in end to end, writing output to a file: `node e2e-work\harness\run-all.js --fresh` (and `--track promptfoo` or `--both`); update the harness to the merged test page.
- [ ] 7.5 Update `docs/temp/series-review-pending-changes.md` to mark change 2 as proposed and, after archive, applied.
