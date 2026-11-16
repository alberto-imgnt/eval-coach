# Proposal

## Why

The app is built for the whole six-Part series, but the engine, the saved progress and the content loader know exactly one course: Part 3's (`state.COURSE`, `STEP_IDS`, `LESSON_IDS`, one `done` list, one `content/lessons.json`). The Series map already says a Part is "switched on by adding content", but nothing in the engine can hold a second course. Part 1 (and later Parts 2, 4 and 5) cannot be added until the engine can. Doing that groundwork first, with no visible change, keeps the Part 3 course, its 1,000-plus tests and its saved progress safe while Part 1 is built on top (see change `add-part-1`).

## What Changes

- **A Part registry.** Each Part with content is described once: its id, its ordered list of lessons and steps, its content files, and where its step progress is saved. Part 3 is the first entry and keeps today's lists, files and storage unchanged. The Series map's `kind: course` rows must each name a registry entry.
- **Content loaded per Part.** The lesson loader and its validation take a Part's lesson list and step list instead of the global ones. Every existing validation rule (equal option word counts, citations, caps, retrieval items, kit references) applies to every Part. The loader merges all Parts into one course object keyed by lesson id; the step text is merged the same way.
- **Ids are unique across Parts.** A lesson or step id names exactly one Part, so every existing route (`/api/lesson`, `/api/step/*`, `/api/lesson/*`, `/api/review/*`) keeps its shape and finds the Part from the id. A load-time check fails on a duplicate id.
- **Saved progress, additive.** Part 3 keeps its top-level keys in `progress.json` (`done`, `steps`, `track`). Lesson progress, learning records and the review queue stay in the one `lessons` block (ids are unique, so one block serves every Part), and `pending-lessons.json` keeps its shape. Other Parts save their step progress under a new `parts.<part-id>` key, created on first use with defaults. A `progress.json` written before this change loads unchanged and is not rewritten until something changes.
- **State for a chosen Part.** `GET /api/state` accepts an optional `part` selector (default `part-3`; implied by `step`). `steps`, `course`, `current_step`, `current_item` and `step` describe that Part. `series` describes every Part with content (state, count, lesson list), built by the same rules as Part 3's today.
- **A generic step kind hook.** A step in a Part's content names a `kind`. Part 3's nine steps keep their existing handlers; new kinds are added by later changes without touching them.
- **Tests run per Part.** Content tests that scan `LESSON_IDS` and `STEP_IDS` iterate the registry. Progress-migration, review, reset and series-view tests gain a second, synthetic Part so the generalization is exercised before any real second Part exists.

No participant can tell the difference: no interface change, no new route, no content change, no change to Part 3's order, steps, gates, files or reset behavior.

## Capabilities

### New Capabilities
- `part-registry`: how the app holds more than one Part's course, content and progress, how an id finds its Part, how old progress still loads, and what stays shared (lesson progress, review, pending progress, setup).

### Modified Capabilities
<!-- None. Participant-visible behavior does not change; the series-map, course-structure and learning-priority-order changes that Part 1 needs belong to `add-part-1`. -->

## Impact

- `app/eval_coach/state.py`: registry (`PARTS`), per-Part course helpers, `parts` default in `new_progress`, per-Part progress validation and migration, `prune_lessons_block` known ids from every Part.
- `app/eval_coach/lessons.py`: `load_bundled` and `validate_course` take a Part; `Course` holds all Parts; a duplicate-id check.
- `app/eval_coach/engine.py`: `_walk`, `_status`, `_step`, `_require_known`, `_mark_done`, `_lesson_status`, `get_state` and `_series_view` resolve the Part from an id; step dispatch by `kind`. Part 3 handlers are not edited.
- `app/eval_coach/server.py`: optional `part` query parameter on `GET /api/state`.
- `app/eval_coach/reset.py`: no change in behavior; the fresh `progress.json` it writes already carries `parts: {}`.
- Tests: `tests/test_series.py`, `tests/test_course.py`, `tests/test_lessons.py`, `tests/test_content_and_resources.py`, `tests/test_reset.py`, `tests/helpers.py` and `tests/course_helpers.py` (a synthetic second Part for the tests).
- Docs: `docs/SPEC.md` (layout, storage, state shape, course section), `docs/IMPLEMENTATION-PLAN.md`.
- `dist/eval-coach.pyz` must be rebuilt.
- No change to HTTP route shapes, `progress.json` keys that exist today, the reset inventory, `web/`, or any `content/*.json` that participants read.

## Out of scope

- Any Part 1 content, step kind, interface or storage (change `add-part-1`).
- Any interface change (AGENTS.md rule 11): the page still reads `state.course` and `state.steps` for Part 3 and passes no `part` selector.
- Moving Part 3's `done`/`steps`/`track` under `parts` (a storage migration with no benefit; Part 3 stays where it is).
- Per-Part tracks. The Script and promptfoo tracks are a Part 3 concept; the registry carries an optional step-order-per-track hook only for Part 3.
- Changing the lock rules: a lesson still opens when every item before it in its own Part is done or skipped, and a step when the previous step and the lesson immediately before it are done or skipped. Parts do not lock each other.
- Parts 2, 4, 5 and 6.
