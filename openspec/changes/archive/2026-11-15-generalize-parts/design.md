# Design

## Context

See proposal.md for motivation. Observed in the code today:

- `state.py` defines `COURSE` (16 lesson and step entries), `STEP_IDS`, `LESSON_IDS`, the promptfoo variant (`PROMPTFOO_COURSE`) and `new_progress`, which carries one top-level `done` list, one `steps` map and one `lessons` block. `validate_progress` rejects a `done` list that is not a prefix of the track's step order.
- `lessons.py` validates `content/lessons.json` against those global lists (`missing = [x for x in LESSON_IDS ...]`, `step must be one of STEP_IDS`) and builds one `Course`.
- `engine.py` (about 100 KB) reads `self.progress["done"]`, `self._step(step)`, `self._steps()`, `self._course()` and the single `lessons` block everywhere. `_walk` and the lesson-open checks special-case the literal lesson id `mission` as the one lesson open before setup.
- `review.py` keys items by `lesson:item`, so it already works across any set of lesson ids.
- `series.json` marks Part 3 as `course`; `_series_view` builds Part 3's row from `course`.
- The page asks for `GET /api/state?step=<id>`, `GET /api/lesson?id=<id>` and posts ids; it never names a Part.

Constraints: `docs/SPEC.md` and AGENTS.md rules 1 and 11 (stdlib only; no interface change without authorization). Part 3's behavior must be byte-for-byte the same, so Part 3 storage does not move.

## Goals / Non-Goals

**Goals:**
- A second Part can be added with content files, one registry entry, and (in a later change) its own step handlers, with no edit to Part 3's handlers.
- Every Part 3 test passes unchanged except where it names a global list that is now per Part.
- The generalization is exercised by tests before a real second Part exists.

**Non-Goals:**
- Any participant-visible change; any move of Part 3's saved keys; per-Part tracks; cross-Part locks.

## Decisions

**D1. A registry in `state.py`, with Part 3's names kept as aliases.**
`Part` is a small immutable record: `id` (`part-3`), `n`, `mission` (the lesson open before setup), `course` (ordered `(kind, id)` tuples), `lessons_file`, `steps_file`, `progress_key` (`None` for Part 3, otherwise the id). `PARTS` is an ordered tuple; helpers are `part_by_id`, `part_of(item_id)`, `all_lesson_ids()`, `all_step_ids()`. `COURSE`, `STEP_IDS` and `LESSON_IDS` stay defined as Part 3's, so Part 3 code and tests keep working.
*Alternative:* put the course lists in JSON. Rejected: the order is behavior that tests pin, and the Part 3 lists include a track variant that is code.

**D2. Ids are globally unique; routes are unchanged.**
`part_of(item_id)` finds the Part from a lesson or step id. The page keeps calling the same routes with the same bodies. Only `GET /api/state` gains an optional `part` (default `part-3`; implied by `step`).
*Alternative:* add `part` to every route. Rejected: it touches every call in `web/js/api.js` and the whole HTTP contract for no gain.
Part 1's ids are chosen to stay clear of Part 3's (lesson ids carry a `p1-` prefix; step ids are new words). A load-time check enforces it.

**D3. Storage: Part 3 stays top-level; lessons stay in one block; other Parts get `parts.<id>`.**
`new_progress` adds `"parts": {}`. A Part's block is `{"done": [], "steps": {<defaults>}}` created lazily by `_part_progress(part)`. `validate_progress` runs the same prefix-order check per Part and fills missing step keys from the Part's defaults (`_merge_defaults`). The `lessons` block, its seed, placement, records and review items stay single (ids are unique), and `pending-lessons.json` is untouched.
*Alternatives:* (a) one `lessons` block per Part: rejected, it multiplies the seed, pending file, review and migration code. (b) Move Part 3 under `parts`: rejected, a migration of every saved project with no benefit and risk to the reset inventory.
A `progress.json` with no `parts` key is filled with `{}` in memory by `_merge_defaults` and is only written when something is saved, as other defaults are today.

**D4. The engine resolves a Part from an id; Part 3 handlers are not edited.**
`_progress_of(part)` returns the object holding `done` and `steps` (the progress dict itself for Part 3, `progress["parts"][id]` otherwise). `_walk(passed, part)`, `_status`, `_step`, `_mark_done`, `_lesson_status`, `_require_known` and `_series_view` take or derive the Part. `_steps()` and `_course()` keep their track logic for Part 3 and read the registry for other Parts. The literal `"mission"` checks use `part.mission`.
Step handlers dispatch on a `kind` in the step's content: no `kind` means the existing Part 3 path; a registered kind goes to a handler module added by the change that introduces it. An unknown `kind` fails at start-up with the same "content invalid" exit as other content errors.
*Alternative:* subclass `Engine` per Part. Rejected: lessons, review, setup and the terminal are shared, and a second engine would duplicate the CLI lifecycle that must stay single (one CLI process at a time).

**D5. The loader is per Part and merges.**
`lessons.load_bundled()` iterates `PARTS`, validating each Part's lessons file against that Part's lesson and step ids with the existing checker, then merges lessons, `step_checks` and step text into one `Course` and one `content` map. Each Part's file keeps the same top-level shape (`version`, `mission`, `step_checks`, `placement`, `lessons`). The new files are `content/part-<n>-lessons.json` and `content/part-<n>-steps.json`; Part 3's files keep their names.

**D6. Tests.**
A test helper registers a small synthetic Part (two lessons and one step) through `state.register_part` inside a context manager that restores the registry, so no fake content ships. It drives: the unique-id check, per-Part walk and locks, `parts` migration and corruption messages, shared review, resets, and `series`. Content tests that read `LESSON_IDS` and `STEP_IDS` iterate `PARTS`.

## Files and storage touched

| Location or key | Touched | Kept or cleared |
|---|---|---|
| `<project>\.learning\progress.json` `parts` (new, default `{}`) | read and written | Part 3's keys untouched; `parts` cleared by both resets (a fresh file is written) |
| `<project>\.learning\progress.json` `done`, `steps`, `track`, `lessons` | read, unchanged semantics | as today |
| `<home>\pending-lessons.json` | unchanged shape | as today (cleared by both resets) |
| `app\eval_coach\content\lessons.json`, `steps.json` | read through the registry | unchanged content |
| `app\eval_coach\content\series.json` | read; a test cross-checks `kind: course` against the registry | unchanged |
| `reset.py` inventory | no new entries (this change adds no files) | unchanged |
| Browser `localStorage` | none | unchanged |

## Risks / Trade-offs

- **[A missed global list in `engine.py` makes a second Part misbehave while Part 3 still passes]** → The synthetic-Part tests run the walk, the lessons routes, step locking, review and resets against a second Part; grep every use of `COURSE`, `STEP_IDS`, `LESSON_IDS`, `"mission"` and `["done"]` (30 `COURSE`/`STEP_IDS` hits in `engine.py`, 19 in `state.py`, 14 in `lessons.py`) and review each in the task list.
- **[`validate_progress` becomes stricter or looser for Part 3]** → Part 3's checks are not edited; the per-Part check is a second call. The existing migration tests run unchanged.
- **[Duplicate ids discovered late]** → The unique-id check runs on every start-up and in the content tests.
- **[Registry in module state is awkward in tests]** → `register_part` is only for tests and restores the registry; production code reads `PARTS` only.

## Migration Plan

Ship with the Part 3 registry entry only. No data migration: `parts` is added in memory when missing and persisted when something is first saved. No rollback step is needed: `_merge_defaults` keeps keys it does not know, so a `progress.json` that gained a `parts` key still loads in the previous build. A test loads such a file through the validator to prove it.

## Open Questions

Each has an assumed default; confirm or change before section 1 of tasks.md starts.

1. **Selector name.** `part` on `GET /api/state`, with the ids used in `series.json` (`part-3`). Default: yes.
2. **Aliases.** Keep `COURSE`, `STEP_IDS` and `LESSON_IDS` as Part 3's names. Default: yes (smaller diff, Part 3 tests unchanged).
3. **Unknown step `kind`.** Fail at start-up. Default: yes.
4. **Where a Part's `done` list lives.** `parts.<id>.done`, same prefix rule as Part 3. Default: yes.
