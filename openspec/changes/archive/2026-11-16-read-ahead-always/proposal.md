# Proposal

## Why

Reading ahead only works until setup passes. Before setup, every locked lesson and step opens as a read-only preview. Once setup passes, the same items are greyed out in the sidebar and step list, and the server refuses to show a locked lesson. A participant who is part-way through a Part loses the ability to see what is coming, while one who has not set up yet can read everything. The course order is there to protect hands-on work and saved progress, not to hide the material. Every participant, technical or not, should be able to see the whole Part, and the whole series, at any time.

## What Changes

- A locked lesson or step SHALL always open as a read-only preview, whether or not setup has passed. Locking keeps governing doing and recording: exercises cannot be answered, steps cannot be started or checked, nothing is recorded, and every write route still refuses a locked item.
- Previews apply to lessons and steps in every Part. The optional `live` step is not listed anywhere until the baseline is done, so it is unchanged.
- The course list and step list show locked items as buttons that open the preview. The status word stays "Locked".
- The glossary and a lesson's "related lessons" list link to locked lessons as well.
- After setup, a locked step is shown through the same text-only preview used before setup. It never runs the step's data collection, never starts the CLI and never touches participant files. The sealed answer key stays sealed.
- The preview note gets a second wording for the case where setup has passed: it names the earlier lesson or step that is still to do and offers a button back to the participant's current item. The existing setup wording stays for the case where setup has not passed.
- The "Continue" control after finishing an item is unchanged. It moves to the next item to do and is not a read-ahead control.

Interface authorization (AGENTS.md rule 11), given by the user in this session: "Yes - sidebar, step nav, next/glossary links and banner copy". Scope of the authorization:
- Locked items in the course list and step list become openable buttons.
- Glossary and related-lesson links to locked lessons.
- A second preview-note wording and its button.
- The matching strings in `content/settings.json`.
- No other layout, styling, component or element-id changes.

Out of scope:
- Series map lesson rows. They stay plain text and do not open anything.
- Any change to what unlocks an item, to the order of the course, to step gates or to results.
- Letting a participant answer, start, check or complete a locked item.
- Any change to the answer-key timing or sealed storage.
- Changes to setup, the setup reminder banner, or Settings.
- New Parts or new lesson content.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `setup-access`: the requirement "Learning content is readable before setup" becomes a requirement that locked lessons and steps are readable as previews at any time, with a note wording for each case.
- `part-registry`: "Locking stays inside a Part" says locking governs doing and recording, not reading, and that each Part's locked items can be previewed.
- `series-map`: the scenario "Before setup has passed" no longer says locked items are unreadable, only that they cannot be done.

## Impact

- `app/eval_coach/engine.py`: `lesson_view` and `_step_view` choose a preview for any locked item; the preview carries the item that is holding it back; the preview seed.
- `app/eval_coach/web/js/lessons.js`, `views.js`, `app.js`: locked entries become buttons; glossary and related-lesson links; preview note and its button.
- `app/eval_coach/content/settings.json`: second preview wording for lessons and for steps.
- Tests: `tests/test_course.py`, `tests/test_http_course.py`, `tests/test_part_1_steps.py`, `tests/test_parts.py`, `tests/frontend/ui.spec.js`, `tests/frontend/part1.spec.js` and the mock servers under `tests/frontend/`.
- Docs: `docs/SPEC.md` and the master task table in `docs/IMPLEMENTATION-PLAN.md`.
- No change to storage, `progress.json`, the HTTP routes' shapes (a lesson or step response gains one optional field), dependencies, or the shipped build beyond a rebuild of `dist/eval-coach.pyz`.
