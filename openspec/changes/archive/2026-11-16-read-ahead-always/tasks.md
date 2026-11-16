# Tasks

## 1. Engine: locked items preview at any time

- [x] 1.1 In `engine.lesson_view`, return the preview whenever `_lesson_status` is `locked`, whatever the setup state, and keep every write path refusing locked lessons. Verify with `python -m unittest tests.test_course tests.test_http_course`, after updating the cases that expected `lesson_locked` on a read (for example `test_course.py` around L53 and `test_http_course.py` around L234) to expect a `preview`, and keeping the answer, complete, CLI-start and rule-run cases refusing with `lesson_locked`.
- [x] 1.2 In `engine._step_view`, send a requested step whose status is `locked` to `_step_preview` even after setup, so `_detail` and `_data_*` never run for it. Verify with a new test in `tests/test_course.py` that, with setup passed, `get_state(step="key")` before predictions are locked returns `preview: True`, `cli: None`, `data == {}` and no answer key text; and with `tests.test_part_1_steps` for a locked Part 1 step.
- [x] 1.3 Add `held_by` (`{kind, id, title}` of the Part's current item, else `null`) to the lesson preview and the step preview through a small helper using `_walk`. Verify with tests that it names the active item after setup, and is `null` before setup.
- [x] 1.4 Add tests that reading a locked lesson or step in another Part after setup changes no progress (compare `progress.json` bytes before and after), and that every mutator still refuses a locked item. Verify with `python -m unittest tests.test_parts tests.test_engine_gates`.

## 2. Copy: second preview wording

- [x] 2.1 Add `preview_lesson_after`, `preview_step_after` (each with a `{title}` slot) and `preview_back` to the gate group in `app/eval_coach/content/settings.json`, in plain language and without session, presenter or room words. Verify with `python -m unittest tests.test_content_and_resources tests.test_content_banned_words`, after adding the new keys to the required list in `test_content_and_resources.py`.

## 3. Interface: locked items open as previews

- [x] 3.1 In `web/js/lessons.js` `renderCourseNav`, make every entry a button that calls `openCourseItem`, keeping the status word; in `web/js/views.js` do the same for the step list. Verify with the Playwright test in 3.4 that a locked entry is a focusable button labelled "Locked" and opens its preview.
- [x] 3.2 In `web/js/lessons.js` (related-lessons list) and `web/js/app.js` (`openGlossary.lessonLink`), link to locked lessons too. Verify with the Playwright test in 3.4.
- [x] 3.3 Render the "after setup" note in `lessons.js` and `views.js` when a preview is shown and `state.preflight.passed`: the `held_by` title in the text and a `#preview-back` button that opens `held_by`. Keep the setup note and `#preview-setup` when setup has not passed. Leave `nextStepOf` and the "Continue" control unchanged. Verify with the Playwright test in 3.4.
- [x] 3.4 Update `tests/frontend/mock_api.py` and `mock_course.py` to match the engine (preview for locked items after setup, `held_by`), then update `tests/frontend/ui.spec.js` and `part1.spec.js` and add cases: after setup a later lesson and a later step open as previews with no enabled exercise controls; the note names the earlier item and the button returns to it; a glossary link opens a locked lesson; "Continue" is unchanged. Verify with `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`.

## 4. Specs, docs and final checks

- [x] 4.1 Update `docs/SPEC.md` where it describes locking and reading before setup, and the master task table and phase section in `docs/IMPLEMENTATION-PLAN.md`. Verify by reading both for any statement that a locked item cannot be read after setup.
- [x] 4.2 Run `openspec validate read-ahead-always --strict` and verify it passes.
- [x] 4.3 Run the backend suites one after the other: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests`. Verify both pass (rerun `test_conpty.RealConsole.test_type_line_sends_enter_separately` once if it alone fails).
- [x] 4.4 Run `python tools\build_pyz.py --smoke` and verify it passes, then run `node e2e-work\harness\run-all.js --fresh` with the stand-in CLI, writing output to a file, and verify it passes.

## Workflow follow-up

- Archive the change after review. The archive summary lists the `docs/SPEC.md` sections now superseded by `setup-access`, `part-registry` and `series-map`.
