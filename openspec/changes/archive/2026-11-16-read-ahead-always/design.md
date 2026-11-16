# Design

## Context

See `proposal.md` for motivation. Today:

- `engine.lesson_view` returns a preview only when the lesson is locked **and** setup has not passed. After setup a locked lesson raises `lesson_locked`.
- `engine._step_view` returns a text-only `_step_preview` only when setup has not passed. After setup it returns `_detail(selected)`, which runs the step's `_data_*` and reads participant files. The UI never asks for a locked step, because its button is a disabled span.
- The write paths (`_require_lesson_active`, `_require_active`, every `lesson_*` and `step_*` mutator) refuse a locked item on their own. They do not depend on the read path.
- The web UI treats locked entries as non-interactive. `lessons.js` does so unless `!ctx.state.preflight.passed`. `views.js` does so for every locked step. `app.js` hides locked lessons from glossary links.
- The preview note's wording in `settings.json` (`preview_lesson`, `preview_step`) says "Setup is not finished".

Constraints: stdlib only, no build step, never parse terminal output, no answer key before predictions are locked, every participant word lives in `content/*.json`, interface changes authorized in `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Reading is decoupled from locking, in every Part, before and after setup.
- One preview path for lessons and one for steps, so the sealed key and participant files cannot be reached by reading ahead.
- The preview note tells the participant what to do to unlock the item.

**Non-Goals:**
- Changing what unlocks an item or any gate.
- Previews on the Series map rows, or for the optional `live` step.
- Any change to storage or `progress.json`.

## Decisions

**D1. Preview is chosen by "locked", not by "locked and setup not passed".**
`lesson_view` returns the preview when `_lesson_status(id) == "locked"`, whatever the setup state. `_require_lesson_open` is left as it is, so every write path still refuses.
Alternative: a new `lesson_preview` route. Rejected: it adds a route and a second place to keep in step with the lock rules, and the existing `status: "preview"` already makes the UI inert (`readOnly` when `status !== 'active'`).

**D2. A locked step after setup uses `_step_preview`, not `_detail`.**
In `_step_view`, a requested step whose `_status` is `locked` goes to `_step_preview`, with or without setup. Only the active or done step reaches `_detail`. This keeps `data: {}`, `cli: None` and no file reads, and keeps the answer key out of reach (`_data_key` is never called for a locked `key` step).
Alternative: have `_detail` blank out its data when locked. Rejected: it leaves the risky code path reachable and each `_data_*` would have to be audited.

**D3. The preview says what holds it back.**
Both previews gain one optional field, `held_by`: `{kind, id, title}` of the Part's current item, taken from `_walk(True, part)` as the first item with status `active`. It is `null` when setup has not passed or when nothing is active. The client picks the wording: the setup wording when `!state.preflight.passed`, else the "finish {title} first" wording with a button to `held_by`. Part 1's steps have their own `_detail` through `part_steps`, but the preview path does not use it.
Alternative: compute the wording on the server. Rejected: the client already chooses between setup and not for the note, and wording lives in `settings.json` with `{title}` filled in by the client.

**D4. Locked list entries become buttons.**
- `lessons.js` `renderCourseNav`: drop the `e.status === 'locked' && !readAhead` branch, so every entry is a button.
- `views.js` step list: same.
- `lessons.js` related-lessons list (around L955): a locked lesson becomes a button too.
- `app.js` `openGlossary.lessonLink`: stop returning `null` for a locked lesson.
The status word "Locked" stays in each entry, and the existing `s-locked` class keeps its look. No new element ids, styles or components. The only new DOM is the second note wording and its button, which reuse `#preview-note` and `#preview-setup`'s markup. The button gets the id `preview-back`.
`app.js` `openCourseItem` already sends a non-current lesson or step to `viewLesson` or `viewStep`, so no routing change is needed.

**D5. "Continue" is not touched.**
`nextStepOf` returns `null` for a locked next item. That is correct for "Continue" (the next item to do) and is not a read-ahead control. Reading ahead goes through the course list.

**D6. Copy.**
`settings.json` gate group gains `preview_lesson_after` and `preview_step_after` (with `{title}`) and `preview_back`. The existing `preview_lesson`, `preview_step` and `button` keep their wording. Plain language, "lesson" and "step", no session words. `test_content_and_resources.py` checks the required keys, so the new keys are added there.

**Files and storage touched**

| Location | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/engine.py` (`lesson_view`, `_step_view`, `_step_preview`, a small `_held_by` helper) | read logic | n/a |
| `app/eval_coach/web/js/lessons.js`, `views.js`, `app.js` | locked entries become buttons, links, note | n/a |
| `app/eval_coach/content/settings.json` | new strings | n/a |
| `tests/test_course.py`, `test_http_course.py`, `test_part_1_steps.py`, `test_parts.py`, `test_content_and_resources.py` | updated and new cases | n/a |
| `tests/frontend/ui.spec.js`, `part1.spec.js`, `mock_api.py`, `mock_course.py` | mock and browser tests follow the new behavior | n/a |
| `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md` | updated | n/a |
| `progress.json`, `pending-lessons.json`, sealed key, `key-work`, `app.json` | not touched | kept |
| `dist/eval-coach.pyz` | rebuilt, never hand-edited | regenerated |

## Risks / Trade-offs

- [A read-ahead lesson exercise could shuffle differently from the live one] → The preview already uses the stored seed (`_lessons_block()["seed"]`); only before any seed exists does it use a fixed one, and the mission lesson creates it first. Accepted.
- [A participant mistakes a preview for the real thing and loses typed text] → Preview controls are disabled and the note says nothing is saved. The existing `readOnly` rendering is reused.
- [Existing tests asserting `lesson_locked` on a read] → Those assertions flip to "preview"; the ones on write routes stay. Listed in tasks.
- [Reading ahead might reveal exercise answers] → Preview exercises already ship without answers before setup (`public_activity`), so this change adds no new exposure. A test pins it for a locked lesson after setup.
- [A step preview exposes track text] → `_text` already picks the participant's track; no participant file is read.

## Open Questions

- Should the Series map's expanded lesson rows open the lesson? Assumed default: no, they stay plain text (out of scope in `proposal.md`).
- Should the glossary show a locked lesson's link with a "Locked" word next to it? Assumed default: no, the link is the same as for an open lesson, and the preview note explains.
- The optional `live` step is only listed once the baseline is done. Assumed default: leave it as is.
