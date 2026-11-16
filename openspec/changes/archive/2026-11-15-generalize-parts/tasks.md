# Tasks

Open questions in design.md carry assumed defaults (`part` selector, Part 3 aliases kept, unknown `kind` fails at start-up, `parts.<id>.done`). Confirm or change them before section 1 starts. This change has no interface or content change; run it before `add-part-1`.

## 1. Registry and saved progress

- [x] 1.1 In `state.py` add the `Part` record, `PARTS` (Part 3 only), `part_by_id`, `part_of`, `all_lesson_ids`, `all_step_ids` and a test-only `register_part` context manager; keep `COURSE`, `STEP_IDS`, `LESSON_IDS` as Part 3's. Verify with a new `tests/test_parts.py`: Part 3 lists equal the current ones, `part_of` finds an id, an unknown id gives `None`, `register_part` restores the registry on exit.
- [x] 1.2 Add `"parts": {}` to `new_progress`; add `new_part_progress(part)`; make `validate_progress` validate each stored Part block (prefix order of its `done`, step defaults filled, wrong container types raise `CorruptStateError`); make `prune_lessons_block` and `_migrate_new_lessons` use every Part's lesson ids and each Part's own furthest finished step. Verify in `tests/test_parts.py` and the existing `tests/test_course.py` migration cases: old progress loads and is byte-identical after load; a file with `parts` loads; a wrong-shaped Part block raises the existing corrupt-progress message; the previous validator accepts a file that has `parts`.
- [x] 1.3 Run the existing backend suite on the current interpreter, `python -m unittest discover -s tests`, and verify no Part 3 test changed outcome.

## 2. Content loader per Part

- [x] 2.1 In `lessons.py` make `validate_course` and `load_bundled` take a Part's lesson and step ids (the `missing`, `extra` and `step must be one of` checks use them), merge every registered Part into one `Course`, and fail on a duplicate lesson or step id across Parts. Each Part's file keeps the `version`, `mission`, `step_checks`, `placement`, `lessons` shape. Verify in `tests/test_lessons.py` with the synthetic Part: a duplicate id is reported, a lesson outside its Part's list is reported, and the real bundled content still loads.
- [x] 2.2 Merge each Part's step text into `Engine.content["steps"]` and each Part's `ui` overrides (none for Part 3) into the text sent as `course_text`. Verify with `tests/test_content_and_resources.py`: Part 3's merged step text equals `steps.json`.
- [x] 2.3 Make the content tests that read `LESSON_IDS` or `STEP_IDS` (word caps, glossary references, removed ids, step checks, banned words, parity of option word counts) iterate `PARTS`. Verify they pass unchanged for Part 3 and that adding the synthetic Part's lessons makes the same checks run on them.

## 3. Engine and server

- [x] 3.1 In `engine.py` add `_part_of(item_id)` and `_progress_of(part)`; make `_walk`, `_status`, `_step`, `_require_known`, `_mark_done`, `_lesson_status`, `_lesson_blocking`, `_item_title` and the lesson-open checks resolve the Part from the id, and replace the literal `"mission"` checks with the Part's first lesson. Review every use of `COURSE`, `STEP_IDS`, `LESSON_IDS`, `["done"]` and `"mission"` in `engine.py` (list them in the task notes). Verify with `tests/test_engine_gates.py` and `tests/test_course.py` unchanged, plus new synthetic-Part cases: its first lesson opens before setup, its step opens only after the lesson, Part 3 items do not change when it progresses.
- [x] 3.2 Add the step `kind` hook: no `kind` runs the existing Part 3 path; a registered kind runs its handler; an unknown kind is a start-up content error. Verify in `tests/test_parts.py` with a registered test kind and an unknown kind.
- [x] 3.3 Add `part` to `get_state` and to `GET /api/state` in `server.py` (default `part-3`, implied by `step`, unknown value refused with a plain `unknown_part` message); build `series` for every registered Part with content by the Part 3 rules. Verify in `tests/test_http_course.py` and `tests/test_series.py`: no selector gives Part 3's state byte-for-byte as before; a selector for the synthetic Part gives its course; an unknown selector is refused; `series` counts equal each Part's own list.
- [x] 3.4 Check the shared parts with two Parts: the review sitting mixes lessons from both, pending progress merges a synthetic first lesson, and both resets leave `parts` empty. Verify in `tests/test_review.py`, `tests/test_course.py` and `tests/test_reset.py`.
- [x] 3.5 Add the cross-check that every `kind: course` Part in `series.json` is registered and every registered Part is on the map. Verify in `tests/test_series.py`.

Task 3.1 notes. Uses of the global lists left in `engine.py` are Part 3 only by design: `_steps` and `_course` (the track variants, through `store.step_ids` and `store.course_items`), `_track`, `_track_locked` and `_live_open` (`progress["done"]`: the track and the optional live step are Part 3 concepts) and the Part 3 branch of `_mark_done`. Every `"mission"` literal was replaced by `part.mission` (`_walk`, `_require_lesson_open`, `_lesson_public`, `placement_answer`). One Part 3 test needed a signature change, not an expectation change: `tests/test_setup_gate.py` stubs `_walk` and now accepts the optional `part` argument.

## 4. Docs and integration

- [x] 4.1 Update `docs/SPEC.md` (layout: `PARTS` and per-Part content files; storage: `parts`; state shape: `part` selector; "Course and lessons": Part registry paragraph) and the master task table and phase text in `docs/IMPLEMENTATION-PLAN.md` (new phase G, "Generalize Parts"). Verify by reading each changed section against `specs/part-registry/spec.md`.
- [x] 4.2 Final integration check, one after the other: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests`, then the whole Playwright suite (`node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`), `python tools\build_pyz.py --smoke`, and the stand-in harness `node e2e-work\harness\run-all.js --fresh` written to a file. All pass with no edit to a Part 3 test expectation; `openspec validate generalize-parts --strict` passes.

## Workflow follow-up

- Review, then archive with `/opsx-archive` before starting `add-part-1`. The archive summary names the `docs/SPEC.md` sections now superseded by the `part-registry` spec.
