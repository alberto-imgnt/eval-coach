# Design

## Context

See `proposal.md` for the why. Facts about the code today (checked 2026-11-18):

- Part 1's `cold` and `rewrite` use the `WriteAndRun` kind in `part_steps.py`. `start` clears `<home>\part1\<step>\`, writes `prompt.md` (the prompt, a divider and the rough notes), starts the AI through `engine._ai_start` (which applies the Sonnet / Haiku preference) and starts a file watcher. `send` types a fixed line into the terminal. `check` evaluates the gate and, on a pass, marks the step done and stops the AI.
- The watcher (`engine._watch_output` / `_finish_run`) saves the AI's `output.txt` into the project and stops the AI, but marks nothing done. Done always comes from a Check press.
- `ScoreForm` (`score`, `rescore`) saves every radio at once and every text box on a short delay (`queueSave` / `flushSave` in `app.js`). `WritePair` (`own`) saves on an explicit Save press.
- `renderTermHead` in `views.js` is shared by every step with a `cli` block (Parts 1 and 3). `renderCheckSection` draws "Check my work", the last result, the Quick check and "Continue to".
- `reset.py` holds the one inventory of files and the all-or-nothing move into `<home>\reset-backup\` (`stage`, `swap_backup`, `rollback`). Part 2 (`criteria_steps.py`) starts no AI and keeps "Check my work".

## Goals / Non-Goals

**Goals:**
- One shared auto-start rule and one paste flow that Part 3 can adopt in 4b by content, not by new code paths.
- Part 1 steps become done without a Check button and without cutting off typing.
- One restart mechanism, registered per Part, that reuses the reset inventory and backup.

**Non-Goals:**
- No change to any gate item, gate wording or the Quick check.
- No parsing of terminal output; no typing into the AI for a paste-flow step.
- No Part 3 changes, and no change to Part 2's "Check my work".

## Decisions

### 1. A step opts in with `cli.mode = "paste"`
The step's content gains `"cli_mode": "paste"` and the step view's `cli` block reports `mode`. `renderTermHead` branches on it: in paste mode it omits the typed-line block and "Send to AI" and keeps the status, the model toggle, a note that each step opens a new chat, Stop, and one "Open a new AI chat" button (the existing `cli-start` id, relabelled; `cli-send` and `cli-retry` are not drawn). Steps without the flag, lesson activities and the setup pages are untouched.
*Alternative:* a Part-level flag. Rejected: Part 3 has steps (`build`, `readback`) that must not change, and 4b can switch steps one at a time.

### 2. Auto-start is server-side, on saving a prompt
In `WriteAndRun.submit`, after a prompt is written, the server runs `_auto_start_ok` and, if true, the same launch routine `start` uses. The rule: step active (`_require_active` passes), preflight passed, prompt non-empty, `cli_mode == paste`, no AI running (`engine.terminal.running` false), `record["auto_started"]` false, the project output file empty, and no `output.txt` in the scratch folder. On launch the record's `auto_started` is set. A failure to start never fails the save: the save stands, `auto_started` stays false, and the step view carries a plain `cli.blocked` message so the participant can press "Open a new AI chat".
Putting the rule on the server keeps it in one tested place and lets 4b call the same function with Part 3's own "nothing to lose" check (its scratch folders `blind`, `fixtures-work`, `key-work`).
*Alternatives:* start when the step opens (rejected: the AI would sit idle while the participant writes, a changed toggle would not apply, and it breaks "never on a plain revisit"); start from the browser after a save (rejected: the rule would live in two places).

### 3. One text, in the file and on screen
`part_steps.run_copy(prompt, divider)` gains a closing `instruction` from content (`"Save only your answer to output.txt. Do nothing else."`) and its result is both written to `prompt.md` and returned to the page as `data.paste_text` (replacing `data.preview`). The participant's own prompt file in the project (`part-1\prompt-cold.md`, `prompt-framework.md`) still holds only their words. Saving a prompt while the AI runs rewrites `prompt.md` (same path, atomic write) without restarting.
The Copy button uses `navigator.clipboard.writeText`. On a refusal or a missing API it selects the text node (`Range` / `Selection`) and shows the Ctrl+C line. The copied message sits in a `role="status"` line. The text is always a text node.

### 4. Completion moment per kind, one `settle` routine
Each kind gets a read-only `report(engine, step)` that builds the same `gates.Report` the check used, and `check` becomes `report` plus `_finish`. A new `settle(engine, step, trigger)` calls `report`, stores the result as `last_check` and, only when the result is ok, marks the step done (and stops the AI for a run step).

| Kind | Trigger | Condition |
|---|---|---|
| `write_and_run` | output captured (a callback passed to `_start_watcher`, run under the engine lock after the file is written) | gate ok |
| `write_and_run` | a save of the label set or a prompt | gate ok **and** a saved answer exists **and** `prompt_hash` equals the saved prompt's hash |
| `write_pair` | a save | gate ok |
| `score_form` | `POST /api/step/check` from the Continue button | gate ok |

`POST /api/step/check` stays for every kind (the harness and tests use it, Parts 2 and 3 use it); Part 1's page simply has no button for it except Continue on score forms. The step view also carries `gate` (a live, unsaved `report` result) and `ready` (gate ok), so the inline list and the Continue button need no request.
*Why `score` and `rescore` complete on Continue:* their answers autosave. If "gate met" marked them done, the first autosave after the last field gained one character would finish the step and refuse further saves (a done step is read-only), cutting off typing. Continue is the participant's own "I am done here". Alternatives considered: marking done at the first autosave (rejected, the cut-off above); letting a done form stay editable (rejected: it changes "done steps are viewable records" for the whole course and lets a gate un-meet itself after done).

### 5. Inline list reuses the check result view
`renderCheckResult` already draws the "Not yet" and "OK" items and the nudges. For Part 1 it is fed `step.gate` while the step is not done, with a heading that does not say "Check". When the step is done it shows nothing but the Quick check and Continue. The "Check my work" row is not rendered for Part 1; Parts 2 and 3 are unchanged. Continue shows (a) for done steps, as today, and (b) for `score` and `rescore` while not done, disabled until `ready`.

### 6. "Start this step again" through the Part registry
`Part` gains an optional `restart` field (a small object, set for Parts 1 and 2, `None` for Part 3) holding, per step, the record to reset to (`part.new_steps()[step]`), the project files the step owns and the scratch folders. Engine `step_restart(step, confirm)` follows the same shape as `_reset`:

1. Guards: configured, preflight passed, Part has a plan, step is done, `confirm is True`, no preflight job running.
2. `_stop_cli()`.
3. Steps to clear = the chosen step and every later step of its Part in course order.
4. `reset.build_restart_plan` lists what exists: project files from the table below, `<home>\part1\<step>\` for Part 1 run steps.
5. `reset.stage` moves them into `<home>\reset-backup.new\`; the `thresholds` restart also writes the stripped worksheet back into `part-2\` at this point; `swap_backup` makes it the one backup; any error rolls back exactly as `_reset` does.
6. Only then are in-memory records replaced by defaults, cleared steps removed from the Part's `done` list, their `lessons.step_checks` entries removed, and `_save()` called.

| Chosen step | Files moved to the backup | Records cleared |
|---|---|---|
| Part 1 `cold` | `prompt-cold.md`, `output-cold.txt`, `prompt-framework.md`, `output-framework.txt`, `own-before.md`, `own-after.md`; scratch `part1\cold`, `part1\rewrite` | `cold`, `score`, `rewrite`, `rescore`, `own` |
| Part 1 `score` | the six files of `rewrite` and `own` (not `cold`'s); scratch `part1\rewrite` | `score`, `rewrite`, `rescore`, `own` |
| Part 1 `rewrite` | `prompt-framework.md`, `output-framework.txt`, `own-*`; scratch `part1\rewrite` | `rewrite`, `rescore`, `own` |
| Part 1 `rescore` | `own-*` | `rescore`, `own` |
| Part 1 `own` | `own-*` | `own` |
| Part 2 `draft` | `worksheet.json`, `test-cases.md` | all four |
| Part 2 `thresholds` | `worksheet.json` (put back with empty thresholds), `test-cases.md` | `thresholds`, `test-file`, `reference` |
| Part 2 `test-file` | `test-cases.md` | `test-file`, `reference` |
| Part 2 `reference` | none | `reference` |

Lessons, other Parts, setup and the model preference are not touched. The Part's locking (`part-registry`) re-locks later steps by itself because the `done` list shrank. The browser clears `app.drafts` entries that start with a cleared step's id and the step cache, then refreshes.
*Alternative:* keep the prompts and clear only outputs, like "Reset lesson progress". Rejected as the default because an empty editor is what lets a restarted run step start cleanly (Save triggers the auto-start) and a kept `own` pair would make the step finish on the next Save with nothing new.

### 7. Words and where they live
Restart dialog and message: a `restart` block in `content/settings.json` next to `reset`, with `{steps}` and `{folder}` placeholders. Paste-flow words, the new chat note and the Copy strings: Part 1's step `ui` blocks in `content/part-1-steps.json`. Inline-list heading: `content/lesson-ui.json`. The old "Press Check my work", "Press Start my AI" and "Send to AI" instructions and troubleshooting are rewritten for the new flow, and `tests/test_part_1_content.py` asserts they are gone.

### 8. The stand-in and the tests
`fake_cli.py` already answers a typed line that starts "Read prompt.md, follow it". It also answers the new closing instruction line ("Save only your answer to output.txt") by reading `prompt.md`, so a test or the harness plays the participant by sending that last line through `/api/terminal/input` (the endpoint a participant's keystrokes use). No test-only server route is added. Rule 3 holds: the app still decides only from `output.txt`.

## Files and storage touched

| Location | Change | Kept or cleared |
|---|---|---|
| `<home>\part1\<step>\prompt.md` | now holds the full pasted text (words, divider, notes, instruction) and is rewritten on a save | cleared at every AI start; moved by a restart and both resets |
| `<project>\part-1\prompt-cold.md`, `output-cold.txt`, `prompt-framework.md`, `output-framework.txt`, `own-before.md`, `own-after.md` | unchanged content | moved to the backup by a Part 1 restart (table above); existing resets unchanged |
| `<project>\part-2\worksheet.json`, `test-cases.md` | unchanged content | moved by a Part 2 restart; `worksheet.json` is put back stripped on a `thresholds` restart |
| `<project>\test-cases.md` (Part 3's) | none | never touched |
| `progress.json` `parts.part-1.steps.cold` and `.rewrite` | new field `auto_started` (default false); missing field filled from the default on load | reset to defaults on restart |
| `progress.json` `parts.part-1` and `parts.part-2` `steps` and `done` | records and done entries of restarted steps | cleared on restart |
| `progress.json` `lessons.step_checks.<step>` | Quick check answers of restarted steps | cleared on restart |
| `progress.json` `last_check` of Part 1 steps | now written by `settle` | as before |
| `<home>\reset-backup\` | now also written by a restart | replaced by the next restart or reset |
| `<home>\reset-backup.new\`, `reset-backup.old\` | staging, as in `reset.py` | removed after the swap or a rollback |
| Browser `app.drafts` | draft keys of restarted steps removed | cleared on restart |
| API | `GET /api/state` step view: `cli.mode`, `data.paste_text` (replaces `data.preview`), `gate`, `ready`, `restart`; new `POST /api/step/restart`; `send` refused for paste steps | n/a |

## Risks / Trade-offs

- [A participant pastes before the AI is ready] → the AI window shows its own prompt; the step says to wait until the AI is ready, and "Open a new AI chat" restarts it.
- [The clipboard is refused] → the text stays selectable and the Ctrl+C line shows; covered by a test that stubs a rejected `writeText`.
- [Auto-start surprises someone who saved only to keep a draft] → it fires once per step, the step says so in its note, and Stop is always there. The model toggle applies at that start, so the toggle note moves above the editor in these steps.
- [A restart replaces the backup of an earlier reset] → the dialog says so in plain words, as the reset dialog does. See Open Questions.
- [Marking done from a background thread] → `settle` runs under the engine lock, like `_finish_run` today; tests drive it with the stand-in's short poll.
- [Two Part 1 steps differ in how they finish (output, Save, Continue)] → each page says what finishes it, and the inline list shows what is missing, so none needs a hidden rule.
- [4b lands later] → until then Part 1 and Part 3 differ inside the shared AI window; this is recorded as a known inconsistency in the local plan (`docs/local/`) and in `AGENTS.md` Status, as the series plan asks.

## Migration Plan

No migration (the app is not live). A `progress.json` written before this change loads: the missing `auto_started` field is filled from its default, done steps stay done, and `data.preview` disappears from the API with the page that read it. Rollback is reverting the change; no stored file changes shape except the one added field.

## Open Questions

Each default below is what the artifacts assume; say so if one should change before apply.

1. **Does `rescore` also lose "Check my work"?** The review file's item 10b lists `cold`, `rewrite`, `score`, `own`. *Assumed: yes, all five Part 1 steps, since `rescore` is a score form like `score`.*
2. **Do `score` and `rescore` finish on the Continue press rather than the moment their gate is met?** Needed so autosave does not freeze a half-typed answer (Decision 4). *Assumed: yes.*
3. **When does the AI window start by itself: when a non-empty prompt is first saved, or when the step is opened?** *Assumed: first save, once per step.*
4. **Does a restart move the participant's own prompts and own-work texts too, or keep them like "Reset lesson progress" does?** *Assumed: move them (they are in the backup).*
5. **Restarting Part 2 `thresholds`: keep the criteria rows and clear only the thresholds?** *Assumed: yes.*
6. **Should a restart use a backup slot of its own so it does not replace a full reset's backup?** The review decision says "the existing reset-backup folder". *Assumed: the one existing slot, replaced, with the dialog saying so.*
7. **Button names:** "Open a new AI chat" for the AI window and "Start this step again" for the restart. *Assumed as written.*
8. **A saved answer exists but the step is not done (for example `rewrite` with an unchanged prompt): may the participant open a new AI chat by hand?** *Assumed: yes, it replaces that answer, as Start did.*
