# Tasks

Interface tasks (groups 5 and 6) are authorized by the user (2026-11-17) for the scope in the proposal only (rule 11). Run the two backend suites one after the other, and use the stand-in `e2e-work/harness/fake_cli.py`; never run a real CLI without approval.

## 1. Model data and resolving the option (backend)

- [x] 1.1 Add `models` data to the three supported tools in `app/eval_coach/content/cli-recipes.json` as in `design.md` decision 1 (Claude Code aliases; GitHub Copilot CLI keyword entries with `discover` and `fallback_id`; Devin alias entries), shared by recipes with the same `cli_command`. Verify: `python -m unittest tests.test_content_and_resources`.
- [x] 1.2 Create `app/eval_coach/models.py` with the data lookup (first recipe per `cli_command`, `<home>\cli-recipes.json` override honored) and `resolve(cli_command, preference)` returning the extra argv and the recorded label; no `models` data means no option and the "AI's own default model" label. Tests in a new `tests/test_models.py`: alias, keyword with saved ID, keyword with fallback, no data, `{id}` substitution, no permission flag ever added. Verify: `python -m unittest tests.test_models`.
- [x] 1.3 Add the preference to `Preflight` (`model_preference` in `<home>\preflight.json`, default `sonnet`, validated against the recipe's options) and `POST /api/model` plus the `ai_model` block in the state (`preference`, `options`, `applies_next_start`, `available`) in `engine.py` and `server.py`; the POST publishes state. Tests: default, set and persist across a new `Engine`, invalid value refused, `available` false for the stand-in. Verify: `python -m unittest tests.test_preflight tests.test_http`.
- [x] 1.4 Replace the three `terminal.start(self.progress["cli_command"], ...)` sites in `engine.py` with one `Engine._ai_start(...)` that builds the argv with the resolved option, starts the AI, and returns the label. The quiet background test is not changed. Tests: `fake-cli-events.jsonl` shows `--model` for a stand-in recipe with `models` data and none without. Verify: `python -m unittest tests.test_models tests.test_part_1_steps tests.test_baseline_step`.

## 2. Discovery, cache and reset (backend)

- [x] 2.1 In `models.py` add discovery per `design.md` decision 4: a private `TerminalManager` in `<home>\cli-models\`, quiet wait, `stop_words` check before typing, `/model` and Enter, quiet read, control-sequence stripping, keyword and `id_pattern` match, highest-version choice, process stopped, text kept in memory only; refuse to run while an AI window runs; any failure returns the fallback and changes no step or check result. Verify: `python -m unittest tests.test_models` with fixtures (two Sonnet IDs, none, a trust question, a sign-in question, a time-out).
- [x] 2.2 Add `<home>\model-cache.json` (IDs per tool with a program marker from path, size and modified time, never screen text); reuse while the marker matches; run again when it changes. Tests: reused, program changed, only IDs stored. Verify: `python -m unittest tests.test_models`.
- [x] 2.3 Wire reset: a configuration reset moves `model-cache.json` with `preflight.json` to `<home>\reset-backup\` and the preference returns to Sonnet; a lesson progress reset keeps both. Verify: `python -m unittest tests.test_reset`.
- [x] 2.4 Add the test-only `--picker` list to `e2e-work/harness/fake_cli.py` (fixed fixture; no email or account name) and a recipe override for tests in `tests/helpers.py`. Verify: `python -m unittest tests.test_models` and `node e2e-work\harness\classifier-check.js`.

## 3. Recorded model in the steps (backend)

- [x] 3.1 Write the label from `_ai_start` to the step record `model_name` (Part 1 `cold` and `rewrite`; Part 3 `generate`, `baseline`, `live`) and add `models_used` to the Part 3 generate record in `state.py`; `Engine._model_name` and the `{model}` slot read `models_used` joined with " and ". Remove the `model_missing` blocking path and the box payload fields from the participant interface; keep the save handlers accepting `model_name` for tests. Verify: `python -m unittest tests.test_part_1_steps tests.test_baseline_step tests.test_live_mode`.
- [x] 3.2 Update gates in `gates.py` and `part_steps.py` so "Model name recorded" is met by the record, and `_model_differs` compares recorded values. Tests: gate passes after an AI start with no typing; the nudge appears when the toggle changed between the runs and not otherwise. Verify: `python -m unittest tests.test_part_1_steps tests.test_engine_gates`.

## 4. Content, docs and rules

- [x] 4.1 Remove the `/model` instruction and the "write the name in the box" text from `content/steps.json` and `content/part-1-steps.json` and the `model_missing` strings; add the toggle note per `model-selection-guidance`; add the `ai_model` keys to `content/lesson-ui.json`. Verify: `python -m unittest tests.test_content_banned_words tests.test_participant_vocabulary tests.test_part_1_content`.
- [x] 4.2 Add content tests: participant step text has no "/model" and no instruction to write a model name; the toggle text has no bare "CLI". Verify: `python -m unittest tests.test_participant_vocabulary`.
- [x] 4.3 Update `AGENTS.md`: rule 3 (scoped exception, wording per Open Question 5), rule 6 (tool list fixed to three with the Sonnet and Haiku choice in data, typed route test-only), the real-CLI paragraph (budget wording removed, single-use approval kept). Verify: read the changed lines against the code.
- [x] 4.4 Update `docs/SPEC.md` (state `ai_model`, `POST /api/model`, `models` recipe data, discovery, storage keys, recorded model), the `docs/IMPLEMENTATION-PLAN.md` master task table, and `docs/temp/series-review-pending-changes.md` (change 3 proposed). Edit the Purpose of `openspec/specs/model-selection-guidance/spec.md` so it no longer says the participant records the name. Verify: read the changed sections against the code.

## 5. Toggle (interface; needs authorization)

- [x] 5.1 Add one shared toggle component to the AI window head in `web/js/app.js` (`renderTermHead`, `renderLessonTermHead`, `renderPreflightTermHead`), with the note that a change applies the next time the AI starts, keyboard reachable with an accessible name, hidden when `ai_model.available` is false; styles in `web/styles.css` per `docs/DESIGN.md`. Verify: Playwright interface tests (step, lesson activity, wizard test page, 390 px wide).
- [x] 5.2 Wire the toggle to `POST /api/model` and refresh every open view from the state. Verify: Playwright (change in one view, same value in another; running window untouched).

## 6. Remove the model boxes (interface; needs authorization)

- [x] 6.1 Remove the model box from `web/js/part-steps.js` (cold, rewrite) and from `web/js/panels.js` (generate, baseline, live) with their draft keys and save payload fields; keep the Part 1 fairness note. Update `tests/frontend/part1.spec.js`, `ui.spec.js` and `mock_api.py`. Verify: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`.

## 7. Verification

- [x] 7.1 Run the backend suites one after the other (`python -m unittest discover -s tests`, then the embedded 3.13 suite), the interface tests, and `python tools\build_pyz.py --smoke`. Verify: all pass; rebuild `dist/eval-coach.pyz`.
- [x] 7.2 Stand-in end to end: `node e2e-work\harness\run-all.js --fresh` (add `--both`), writing output to a file. Verify: passes with the toggle on Sonnet and one run on Haiku.
- [x] 7.3 Real-CLI confirmation (needs the user's single-use approval each time): per tool one session on Sonnet and one on Haiku, to confirm the launch option, record the `/model` fixture (mask any account name or email) and confirm Devin's Haiku option. Verify: the AI window shows the chosen model; fixtures hold no personal data. If a tool cannot run, leave its fallback data and note it in `docs/IMPLEMENTATION-PLAN.md`.
