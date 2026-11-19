# Design

## Context

See `proposal.md` for the why. Facts about the code today (checked 2026-11-19, after `step-flow` was applied and before it was archived):

- Part 3's steps have no `kind`. They go through `engine.step_start`, `step_send`, `step_stop` and `_detail`, which build `cli = {line, folder_label, mode: "typed", started, sent, blocked}` from the step's `line` or `line_template` in `content/steps.json`.
- `step_start` clears the step's scratch folder through `_prepare_folder` (`generate` → `blind`, `fixtures` → `fixtures-work`, `key` → `key-work`; every other step uses the project folder and clears nothing), starts the AI through `_ai_start`, records the model through `_record_model` and, for `generate`, starts the watcher that saves `output.txt` as `runs\run-N.txt` and stops the window. `live` also notes `start_hashes` once.
- `step_send` types `_step_line(step)` (the line, with `{model}` and `{cli}` filled in). Part 1's paste steps already refuse it through `_kind_call`; Part 3 has no kind, so it does not.
- `renderTermHead` (`views.js`) already has a paste branch (`cli.mode === "paste"`, `renderPasteTermHead`) for Part 1. The Copy button, selection fallback and `role="status"` line live in `part-steps.js` (`copyPasteText`) and draw inside Part 1's step panel, not in the head.
- `engine._cli_blocked` (step id → plain message) already carries "the AI could not start by itself" for Part 1.
- Tests and the harness drive Part 3 through `engine.step_send` / `POST /api/step/send` (about 100 call sites across `tests/` and `e2e-work/harness/`; about 60 in `tests/frontend/ui.spec.js`).

## Goals / Non-Goals

**Goals:**
- Part 3's AI steps behave like Part 1's in the shared window: the window opens by itself once, the participant pastes, the app types nothing.
- One start rule, in one tested place, with Part 3's own "nothing to lose" check per kind of folder.
- No change to any Part 3 gate, nudge, folder lifecycle, sealed-key handling or "Check my work".

**Non-Goals:**
- No change to Part 1, Part 2, lessons, the setup AI test page or the model toggle.
- No restart for Part 3. No change to what a Part 3 step writes or to its checker.
- No parsing of terminal output; no typing into the AI.

## Decisions

### 1. Steps opt in with `cli_mode: "paste"` in `steps.json`
The nine AI steps gain `"cli_mode": "paste"`. `_detail` reports `cli.mode` from it (`"typed"` otherwise, as now), and `step_send` raises `not_supported` for a paste-mode step, as it already does for Part 1. `predict` and `run` have no line and no flag.
*Alternative:* a flag per Part. Rejected for the same reason as in `step-flow`: `step-flow` already uses the per-step flag, and `live` needs different behavior from its neighbors.

### 2. Auto-start is a server rule, triggered by opening the step
Part 3 has no save to trigger on. The page calls a new `POST /api/step/auto-start {step}` once each time it shows an active paste-mode Part 3 step whose view says `cli.can_auto_start` is true. The server runs `_auto_start_ok(step)` and, if true, the same launch routine `step_start` uses; otherwise it returns the current state unchanged (a no-op is a success, so the page may call it freely).
`_auto_start_ok` requires: paste mode, `live` excluded, `_require_active` passes (so locked, done and pre-setup all refuse), `terminal.running` false, `record["auto_started"]` false, and the per-step "nothing to lose" check in Decision 3. On launch it sets `auto_started` and clears `_cli_blocked[step]`. A failure never raises to the page: it sets `_cli_blocked[step]` so the head shows the reason, and `auto_started` stays false so "Open a new AI chat" works.
`cli.can_auto_start` is computed by the same function (read-only), so the page asks only when the answer will be yes. A plain `GET /api/state` never starts anything, and the read-ahead preview (`cli: None`) never offers it.
*Alternatives:* start inside `get_state` when a step is requested (rejected: a read with side effects, and it would fire on every poll); start when Copy is pressed (viable: Copy is a clear "ready" signal, but the AI would start loading only then and the participant would paste into a window still starting; see Open Questions); start only from the old Start button (rejected: that is the click this change removes).

### 3. "Nothing to lose" per folder kind
| Step | Folder | Auto-start allowed when |
|---|---|---|
| `generate` | `blind` | next run file is empty and `blind` holds nothing but `prompt.md` (or does not exist) |
| `fixtures` | `fixtures-work` | `fixtures-work\fixtures` holds no fixture text and `<project>\fixtures` holds none |
| `key` | `key-work` | `key-work\fixtures\answer-key.md` has no text and no sealed key exists (checked by file presence only; the key is never read) |
| `build`, `fixtures-config`, `readback`, `fix`, `baseline` | project folder | no extra condition: a start clears nothing |
| `live` | project folder | never automatic |

`generate` runs 2 to 5 are always started by "Open a new AI chat", because `auto_started` is true after run 1. The `_prepare_folder`, label (`run n of 5`), `_record_model` and watcher code move into one `_launch_step(step)` shared by `step_start` and the auto-start, so a start by either route is identical. `live`'s `start_hashes` note stays in `_launch_step`.

### 4. "Open a new AI chat" is the old start, with a confirm
`POST /api/step/start` stays the one route behind the button (the existing `cli-start` id, relabelled in paste mode, the same wiring `newChat()` already has for Part 1). The page asks first, with the same confirm helper Part 1 uses, when `cli.started` is true (window running) or the view says `cli.has_result` (the step's scratch folder or saved run would be cleared by a new start). `cli.has_result` is computed by the same folder check as Decision 3, inverted, and is false for the project-folder steps. There is no separate "Start again": a second press is a new chat.
The server does not enforce the confirm (Part 1 does not either); `step_start` keeps its current behavior, including clearing the scratch folder and replacing a running window.

### 5. The text to paste is the step's line, shown in the head
`cli.line` stays the field name for the text (it is what `_step_line` already returns, with `{model}` and `{cli}` filled in); a new `cli.paste_ready` is false while a part is unknown: `live` before the warning is ticked and an AI chosen (the existing `start_blocked` message says what is missing). `baseline` has its model after `generate`, so it is always ready in practice; if the placeholder `<model>` would still show, `paste_ready` is false.
The page draws the line in the head, in the block that held "This exact line will be typed into your AI", with the Part 1 Copy control: `copyPasteText` and its status line move from `part-steps.js` into a small shared helper (`web/js/paste.js` is not needed; export from `part-steps.js`, import in `views.js`). The ids stay: `copy-paste` for the button, `copy-status` for the line. The text is always a text node, never HTML.
No new file is written to a scratch folder: Part 3's folders already hold what the skills read (`prompt.md` in `blind`, the skills and inputs in the others), and the line is not a file the AI reads.

### 6. Words
A shared `paste_ui` block at the top of `steps.json` (next to `messages`) holds the strings Part 1 keeps per step (`ai_note`, `new_chat`, `ready_hint`, `copy`, `copied`, `copy_failed`, `paste_heading`, `paste_note`, confirm title and body). It is merged under each paste-mode step's own `ui` when the step loads, so a step can still override one string. The nine steps' instructions, troubleshooting and gate failure lines are rewritten for: it opens by itself, wait until it is ready, copy, paste, press Check my work. About 70 hits of "Start my AI", "Send to AI", "Press Send" and "Press Start" in `steps.json` go. `tests/test_part_1_content.py`'s scan is generalized to a content test over every paste-mode step in both files.

### 7. State
`state.py` default records for `generate`, `build`, `fixtures`, `fixtures-config`, `readback`, `key`, `fix`, `baseline` and `live` gain `auto_started: False`. `default_step_entry` and the load path already fill a missing field from the default (the `step-flow` mechanism), so an older `progress.json` loads. It is not cleared by "Reset lesson progress" differently from the rest of the record (the whole record resets).

### 8. Stand-in, tests and harness
`fake_cli.py` already answers the Part 3 lines when they arrive as typed input. The new test helper `paste_step_line(engine, step)` types the step's line through `engine.terminal_input` (the endpoint a participant's keystrokes use) followed by Enter. Existing tests that called `step_send` call the helper instead; tests that assert Send's behavior assert the refusal. The harness `run.js` does the same through `/api/terminal/input`. No test-only server route is added. Part 3's Playwright cases drop Send and Start again and assert Copy, the note, "Open a new AI chat" and the confirm. Rule 3 holds: the app still decides only from files and checker runs.

## Files and storage touched

| Location | Change | Kept or cleared |
|---|---|---|
| `<home>\blind\prompt.md`, `<home>\blind\output.txt` | none (same lifecycle) | cleared at each start, as today |
| `<home>\fixtures-work\`, `<home>\key-work\` | none (same lifecycle) | cleared at each start; `key-work` removed by `finish_fixtures` as today |
| `<project>\runs\run-N.txt`, `check.py`, `test-cases.md`, `fixtures\`, `examples\`, `iteration-log.md`, `promptfooconfig*.yaml` | none | untouched |
| Sealed answer key | none; the auto-start checks only that the file exists | never read, never in a backup (rule 9) |
| `progress.json` `parts.part-3.steps.<step>.auto_started` | new field for nine steps, default false | cleared with the record by a lesson-progress reset |
| `progress.json` Part 3 `generate.models_used`, `model_name` | unchanged meaning, written by every start | as today |
| `content/steps.json` | `cli_mode`, shared `paste_ui` block, rewritten words | n/a |
| Browser local state | `copy-<step>` entries for the Copy status (as Part 1) | per page |
| API | `POST /api/step/auto-start`; step view `cli.mode`, `cli.can_auto_start`, `cli.has_result`, `cli.paste_ready`; `send` refused for paste-mode steps | n/a |

## Risks / Trade-offs

- [The AI starts the moment a step opens, before the participant has read it] → the note says so, Stop and "Open a new AI chat" are always there, and the model toggle applies at the next start; the toggle note sits above the line in these steps.
- [Opening a step in two tabs or by a fast double render calls auto-start twice] → the server holds the lock and sets `auto_started` in the same critical section, so the second call is a no-op.
- [A participant pastes before the AI is ready] → "Wait until your AI is ready for a message" stays in the head while the window runs.
- [A scratch folder holds a result the new chat would clear] → the confirm names it; auto-start never clears it.
- [About 100 existing tests call Send] → one helper replaces them mechanically; behavior assertions stay.
- [Part 1 and Part 3 trigger differently (save vs. open)] → each is stated once in the shared spec and in the Part's own section; a participant sees the same note in both.
- [`step-flow` is not archived yet] → the shared-spec modification here applies to a capability that exists in `openspec/specs/` only after that archive. Apply this change after it, or archive both together.

## Migration Plan

No migration (the app is not live). A `progress.json` written before this change loads: the missing `auto_started` fields take their default, done steps stay done, and a step that was running when the app closed simply has no window. Rollback is reverting the change; the only stored shape that changes is the added field.

## Open Questions

Each default below is what the artifacts assume; say so if one should change before apply.

1. **Trigger: when the step is opened (assumed) or when Copy is pressed?** Opening gives the AI time to load while the participant reads; Copy ties the start to an explicit "I am ready".
2. **`generate` runs 2 to 5: should the next window open by itself when a run is saved?** *Assumed: no. Each later run is "Open a new AI chat", so a window never starts without a participant action after run 1.*
3. **`live`: never automatic (assumed), or automatic once the warning is ticked and an AI is chosen?** *Assumed never automatic, because it is optional and carries its own warning.*
4. **Confirm on "Open a new AI chat" only when a window is running or a result would be cleared (assumed), or always?**
5. **Should the setup AI test page and the AI window mini lesson move to paste in this change?** *Assumed no (as in `step-flow`): they keep Start and Send, and the series review's note about their words is a separate item.*
6. **Is it acceptable for this change to be applied only after `step-flow` is archived?** *Assumed yes.*
7. **Real-tool confirmation:** one `generate` run 1 and one `build` start per tool (three sessions), driven by a Part 3 version of `e2e-work\harness\real-paste.js`, each needing your single-use approval. *Assumed as in `tasks.md`.*
