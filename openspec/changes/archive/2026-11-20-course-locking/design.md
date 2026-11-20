# Design

## Context

Locking today lives in the engine's `_walk` (per Part, in `engine.py`): a lesson or step is `active`, `done`, `skipped` or `locked`, and `locked` items already open as read-only previews (`lesson_view`, `_step_preview`, `_held_by`) with two note wordings in `content/settings.json`. Parts never lock each other, and `series` state is built by `_series_view`. The Series map expands every Part by default (`app.js` `seriesOpen`). Progress is a Part-3 list in `progress.json` plus one block per other Part under `parts`, and one shared `lessons` block that also lives in `pending-lessons.json` before a project exists. See `proposal.md` for the reasons and the interface scope.

## Goals / Non-Goals

**Goals:**
- One server-side rule decides what opens; the page only shows it (the Series map, course list, step list and links never decide).
- Keep the saved progress shape valid: a Part's finished steps stay an ordered prefix.
- Demo access that tests and the harness can use without a real password in the repo.

**Non-Goals:**
- Changing what completes a lesson or step, the order of any course, or the answer-key timing.
- Out-of-order doing inside a Part, even with demo access (decision below).
- A stronger secret scheme than a salted hash: demo access is a deterrent only.

## Decisions

**1. Status model.** `_walk` gets two changes and keeps its shape `(kind, id, status)`:
- A Part gate. `part_open(part)` is true when every Part with a lower number is finished (all its items done or skipped by their stored status, or its id is in `skipped_parts`) or demo access is on. When it is false every item of the Part is `locked`. "Finished" is computed from stored status only (an ungated walk), so there is no recursion.
- A Part skipped by id makes every item that is not done come out as `skipped`.
- The `preview` value for locked items goes away. `locked` now means refused.

*Alternative:* gate in each route. Rejected: dozens of routes already call `_require_lesson_open` / `_require_active`, which already go through `_walk`, so the gate in one place covers them all, including direct requests.

**2. Refusal instead of preview.** `lesson_view` raises the existing `lesson_locked` error for a locked lesson; `get_state(step=...)` raises `step_locked` for a locked step (and for a step of a locked Part). `_held_by`, the two `preview_*_after` words, `preview_back` and the `held_by` fields go. One refusal text in `content/lesson-ui.json` errors ("opens when the previous ones are done") serves both, and is the same text as the tooltip (one key, two places). The `key` step is refused like any other locked step, so the sealed storage is never read for a locked request (AGENTS rule 9).

**3. Setup skipped (item 18).** Setup no longer decides whether a lesson opens: the lesson that is next to do in an open Part is `active` whether or not setup has passed (the spec says the current item can be read before setup, and a Part 2 or Part 3 participant who finished the mission would otherwise meet a lock that is not true), and its CLI exercises stay refused by `_require_preflight`. A step that is next to do is `active` in the course list before setup too, and opens through `_step_view`'s words-only view (`_step_preview`, renamed `_step_words`, with no `held_by`), the only remaining caller; `state.steps` and `current_step` stay locked and null until setup passes. No participant file is read.

**4. Skipped Part.** Stored as `lessons.skipped_parts` (a list of Part ids) in the shared lessons block, so it also works before a project exists (`pending-lessons.json`, merged by `_adopt_pending`). `store.new_lessons_block` gains the key; `_merge_defaults` fills it in older files without rewriting them; `prune` drops ids of Parts this build does not know. New route `POST /api/part/skip {part, confirm: true}`; the server refuses a Part that is locked, finished, already skipped or has no content, and `confirm` that is not `true` (same pattern as the resets). If the AI window belongs to a step of that Part, it is stopped first (`_stop_cli`). No file is moved or deleted.

Items of a skipped Part open read-only: `lesson_view` builds the existing read view with `preview=True` extras (so no hook or practice file is read) and sets `status: "skipped"` plus `part_skipped: true`; a step returns the words-only view with `status: "skipped"`. Every write route refuses through `_walk` status `skipped` (`lesson_skipped` already exists; steps get a `step_skipped` message). The client note wording switches on `part_skipped`.

**5. Demo access.** A small module `demo_access.py` holds hash handling: PBKDF2-HMAC-SHA256 with a 16-byte random salt and 200,000 iterations (stdlib `hashlib`), compared with `hmac.compare_digest`. The record is `{"salt": hex, "hash": hex, "iterations": n}` in `app/eval_coach/demo_hash.json`, read through `resources`. `Engine(..., demo_hash=None)` takes a record (tests); when omitted it reads the shipped file; when neither exists, demo access is unavailable. The hidden launch flag `--demo-hash-file <path>` (suppressed from help, like `--custom-ai`) lets the harness and the Playwright servers start with a test hash. `tools/make_demo_hash.py` reads the password with `getpass`, writes the file, and never prints or stores the password.

The on/off flag is an attribute on the engine only; it is not written anywhere and not cleared by the resets. It affects one thing: `part_open` is true for every Part. It does not touch the setup check, the track, the answer key, or the order inside a Part. `GET /api/state` returns `demo: {available, on}`; `POST /api/demo/unlock {password}` and `POST /api/demo/lock` change it. A wrong password returns one generic refusal; there is no throttle (deterrent only).

*Alternatives:* a password in an environment variable or a hidden CLI flag (no UI, but then a participant cannot be shown it, and the user asked for the Settings route). Letting demo access also open items out of order inside a Part: rejected on 2026-11-19 ("every part/lesson must be done sequentially"); it would also break the saved-progress prefix check.

**6. Series view and default expansion.** `_series_view` adds per Part: `state` (`locked`, `not_started`, `in_progress`, `done`, `skipped`), `can_skip`, and per-lesson `status` (now including `locked` and `skipped`). The top level adds `active_part`: the Part in progress, else the first open Part not started, else `null`. The page seeds `seriesOpen` from `active_part` on the first state it receives after a launch or reload, and leaves it alone afterwards, so the participant's own expanding sticks.

**7. Interface.** All changes reuse the existing element structure.
- A shared helper in `ui.js` draws the locked marker: an inline SVG lock (`aria-hidden`) beside the status word "Not started", and the tooltip text in a visually hidden element referenced by `aria-describedby`. A locked item is a button with `aria-disabled="true"` that does nothing on click and stays focusable, so the text shows on focus (a CSS `:focus-visible` tooltip) as well as on hover (`title`). Used by the course list (`lessons.js`), the step list (`views.js`) and the Series map open control (`series.js`).
- Glossary entries and `related.lessons` get the lesson's open flag from the server (`related.lessons[].open`; the glossary reads the lesson statuses already in `series.parts[].lessons`) and render plain text when false.
- `STATUS_WORD` in `views.js` and `statusWord` in `lessons.js` read their words from `content/lesson-ui.json`.
- "Skip this Part" is a quiet button on the open Part's row; its confirm reuses the existing dialog component (`dialog.js`) as the resets do, with the per-Part text from `content/series.json`.
- Settings gets a version line at the end. It is a button styled as text: the fifth selection in a row (a local counter that resets on leaving Settings) reveals the demo group. The demo notice reuses the setup banner's slot and styles with its own class and `role="status"`.

**8. Tests and harness.** Engine and HTTP tests that walk Part 3 or Part 2 directly call a helper that supplies a test hash and turns demo access on (or skips earlier Parts). The harness (`e2e-work/harness/run.js`, `lesson-stages.js`) and the Playwright servers start with `--demo-hash-file` and unlock through `/api/demo/unlock` as the first request. The throwaway test password lives only in test code and the hash it produces; it has nothing to do with the real one.

## File locations and storage keys

| Where | Change | Kept or cleared |
|---|---|---|
| `progress.json` `lessons.skipped_parts` (new, default `[]`) | Part ids the participant skipped | Cleared by both resets (they clear the whole lessons block) |
| `pending-lessons.json` `skipped_parts` | Same, before a project exists | Cleared by Reset lesson progress with no project (`_discard_pending`); merged into the project by `_adopt_pending` |
| `app/eval_coach/demo_hash.json` (new, in the app, not the home) | Salt, iterations, hash | Part of the shipped app; never in the home folder, never reset |
| Demo access flag | In memory only | Gone when the app closes; resets leave it alone |
| `content/lesson-ui.json` | `status_locked`, `locked_tip`, `lock_refusal`; the two read-ahead words go | Content |
| `content/series.json` | Per Part: `skip` (teaches, matters, no-artifact line, buttons), `state_locked`, `state_skipped`, `skip_button`, `locked_tip` | Content |
| `content/settings.json` | Version, demo group, demo notice, errors; reset "clears" lists name skipped Parts; `preview_*` and `preview_back` removed | Content |
| `app/eval_coach/state.py` | `new_lessons_block`, `prune_lessons_block`, `_validate_parts` untouched otherwise | Code |
| `tools/make_demo_hash.py` (new) | Creates `demo_hash.json` | Tool |

`docs/SPEC.md` (the "Series map", "Locking" and Settings sections), `AGENTS.md` (Status, the demo password under Sensitive items, rule 11 stays), the series review file and the local plan are updated in the same change.

## Risks / Trade-offs

- **Large test churn.** Many tests and the harness open Part 3 or a later lesson directly. → One helper and one harness unlock, added first (task group 1), so the rest of the suite keeps its shape.
- **A tester cannot see ahead any more.** Previews were a way to check wording. → Demo access opens Parts, not items; the content tests and the harness already read content directly. Reviewing text remains possible from the content files.
- **A participant already ahead (O2).** → Their saved work is kept, the later Part simply locks until the earlier ones are done or skipped; a skip is one click.
- **Hash in the shipped app.** Anyone with the archive can attack it offline. → Accepted: deterrent only (item 1e); 200,000 iterations and a salt keep casual guessing slow.
- **Hidden entry and accessibility.** A button whose fifth press does something unexpected. → It is a labelled button, keyboard operable; nothing is announced until revealed. The reveal is an ordinary labelled group.
- **Content words.** A banned-word or "Stage 3" slip in the skip texts. → The content tests scan them (`participant-vocabulary`).

## Migration Plan

No data migration (decision O2). `skipped_parts` is added by default-fill on load; older files are not rewritten until something changes. Rollback is reverting the change; a file written with `skipped_parts` still loads (unknown keys are kept as they are by the older reader's merge).

## Open Questions

The user must confirm each; the assumed default is what the specs and tasks use.

1. **Skip wording per Part.** Assumed: drafted in `series.json` from `docs/COURSE-CONTEXT.md` (what the Part teaches, why it matters, and "no artifact and no evaluator"), and shown to you for review before archive, as `add-part-2` did.
2. **Hash strength.** Assumed: PBKDF2-HMAC-SHA256, 200,000 iterations, 16-byte salt.
3. **Skipping Part 3.** Assumed allowed (it is the last Part with content); the map then shows every Part Done or Skipped.
4. **Hidden flag name.** Assumed `--demo-hash-file` (hidden from help).
5. **Skipping before setup.** Assumed allowed and saved in `pending-lessons.json` until a project exists.
6. **Running AI window when a Part is skipped.** Assumed: the AI window is stopped without asking, if it belongs to that Part.
