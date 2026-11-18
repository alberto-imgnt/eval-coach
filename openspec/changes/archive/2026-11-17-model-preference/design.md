# Design

## Context

Today the model is typed. The `cold` and `rewrite` steps (Part 1) and the `generate`, `baseline` and `live` steps (Part 3) each hold a `model_name` box. The generate step's value is the one home for Part 3 (`Engine._model_name`, `_step_line`), and the `{model}` slot in the `line_template` of the Part 3 log lines reads it. Gates check that it is non-empty (`gates.py` `report.add("model", ...)`, `part_steps.py`), and `part_steps._model_differs` compares the cold and rewrite values for the Part 1 nudge.

Every AI start goes through one of three calls to `TerminalManager.start(self.progress["cli_command"], ...)` in `engine.py` (Part 3 steps, setup test, lesson activities); the command is a plain string such as `copilot`, matched to `cli-recipes.json` by `cli_command`. `TerminalManager` runs one session at a time and has an output ring, with a separate use for processes the app runs itself.

Facts checked with each tool's `--help` and the vendor docs (2026-11-17): Claude Code `--model <alias|name>` (`sonnet`, `haiku`, `opus`); GitHub Copilot CLI `--model <id>` (and `auto`), exact IDs only; Devin CLI `--model <MODEL>` (`opus`, `claude-sonnet-4`, `codex` as examples; also `DEVIN_MODEL`); none lists models outside a session.

Rules that shape this: rule 2 (no permission flags, never answer a prompt), rule 3 (no terminal parsing; this change adds a scoped exception, decision 4), rule 4 (one AI process at a time), rule 5 (no network use by the app, no model calls), rule 6 (tool-specific data only in `cli-recipes.json`), rule 10 (plain words), rule 11 (interface authorization, see the proposal).

## Goals / Non-Goals

**Goals:**
- One preference, a toggle in every AI view, applied at the next start, recorded by the app.
- Tool specifics only in `cli-recipes.json`.
- A participant is never blocked by discovery.
- The test-only typed route and the stand-in keep working with no model option.

**Non-Goals:**
- Part 1 auto-start, Copy button and "Check my work" removal (change 4).
- A model picker with more than two values.
- Choosing the model for the quiet background test.
- Migrating model names already stored in `progress.json`.

## Decisions

### 1. Data per tool in `cli-recipes.json`

Each recipe that has a `cli_command` the course supports gets a `models` object, shared by recipes with the same `cli_command` (Claude's installer and winget entries repeat it, and the lookup takes the first match, as `preflight` already does for `headless`):

```json
"models": {
  "sonnet": {"label": "Sonnet", "launch": ["--model", "sonnet"]},
  "haiku":  {"label": "Haiku",  "launch": ["--model", "haiku"]}
}
```

For a tool that needs an exact ID, the entry names a keyword and a template instead:

```json
"models": {
  "discover": {"command": "/model", "ready_quiet_seconds": 3, "read_quiet_seconds": 2, "max_seconds": 45,
               "stop_words": ["sign in", "log in", "trust", "allow", "approve"], "id_pattern": "[A-Za-z0-9][A-Za-z0-9._-]*"},
  "sonnet": {"label": "Sonnet", "keyword": "sonnet", "launch": ["--model={id}"], "fallback_id": "claude-sonnet-5.5"},
  "haiku":  {"label": "Haiku",  "keyword": "haiku",  "launch": ["--model={id}"], "fallback_id": "claude-haiku-5.5"}
}
```

Rules for the data: an entry with `launch` and no `keyword` is a fixed alias and never triggers discovery; an entry with `keyword` needs an ID from discovery, the saved result or `fallback_id`. `discover` may be missing (no discovery for that tool: fallback only). A recipe with no `models` object gets no toggle and no option. The values above are starting data; Devin's `haiku` is not documented, so its entry starts as an alias and is confirmed in the approved real session (Open Question 3). `<home>\cli-recipes.json` overrides still win, so tests and the stand-in can supply `models` for `fake_cli.py` without touching shipped data. The `stop_words` and patterns are data, not code.

### 2. Preference storage and the toggle

`Preflight` already owns `<home>\preflight.json` and its reset path (a configuration reset moves the file to `<home>\reset-backup\`; a lesson progress reset leaves it). The preference lives there as `model_preference` (`"sonnet"` or `"haiku"`, default `"sonnet"`). New `Engine` calls: `GET` data in the state under `ai_model: {preference, options: [{id, label}], applies_next_start: bool, available: bool}` and `POST /api/model {preference}`; the POST validates the value against `options`, writes `preflight.json` atomically and publishes state so every open view refreshes. `available` is false when the chosen command has no `models` data; the client hides the toggle then. `applies_next_start` is true while an AI process runs. The toggle is a two-option group in the AI window head (`renderTermHead`, `renderLessonTermHead`, `renderPreflightTermHead` in `web/js/app.js`), one shared component, so it appears in every view that has an AI window head. Alternative considered: a Settings-only control. Rejected: the decision (item 7) is a toggle where the AI is used.

### 3. Resolving the option at start (`app/eval_coach/models.py`)

One function `resolve(cli_command, preference)` returns `(argv_extra, model_label)`:

1. Find the recipe by `cli_command`; no `models` data → `([], "the AI's own default model")` (text from content).
2. Alias entry → its `launch` as is; the label is the alias word (`sonnet`, `haiku`).
3. Keyword entry → the ID from the saved result for this tool and version; else run discovery (decision 4) when `discover` data exists and no AI is running; else `fallback_id`. `launch` has `{id}` replaced by the ID; the label is the ID.

`Engine` builds the argv as `terminal.argv_for(cli_command) + argv_extra` and passes the list to `terminal.start` (it already accepts an argv list). The three start sites call one helper `Engine._ai_start(...)`, so a fourth start cannot forget the option. The same helper writes the label into the step record (decision 5). The quiet background test and the visible setup test are not given the option on the quiet path (it keeps its defaults, as stated in the proposal), but the visible working test does show the toggle and uses it, like every other AI window.

Windows quoting: argv is a list, so no shell quoting is involved.

### 4. Discovery (hidden `/model` read) and the rule 3 exception

Discovery is the heaviest part and the one the user chose over an exit-status probe (see Open Questions 1 and 2). Design:

- **Where.** A second `TerminalManager` owned by `models.py` (same PTY factory, its own ring), in `<home>\cli-models\` (created empty, never anything of the participant's). Rule 4 is kept by refusing to start while `Engine.terminal.running` or while another discovery runs; a participant start waits for a running discovery (bounded by `max_seconds`) rather than skipping it.
- **When.** Only for entries with `keyword`, and only when no saved result exists for this tool and version; triggered at an AI start, and also in the background once the working test of the chosen AI has passed (quietly or in the visible window; a passed test shows the tool is signed in and can show its list), so the first AI window does not wait. A failed discovery is not retried in the same app run.
- **Steps.** Start the tool with no model option; wait until its output has been quiet for `ready_quiet_seconds` (timing only) up to `max_seconds`; look at the text so far for any `stop_words` (case-insensitive); if one is present, do not type, stop, and use the fallback; otherwise type `/model` and Enter as two writes (as `type_line` does); wait for `read_quiet_seconds` of quiet; read the ring; strip terminal control sequences; take every token matching `id_pattern` that contains the keyword; keep those that look like an ID (contain a digit); choose the highest by comparing digit groups numerically; stop the process tree. Nothing in the list is selected, no key other than `/model` and Enter is sent, and no setting is changed.
- **Exception to rule 3 (AGENTS.md).** The text is used for exactly two things: the model ID, and the decision not to type when a question is on screen. It never decides a pass or a fail, never feeds a gate, and is never written to a file. The text is held in memory only and dropped when the process stops.
- **Result.** `<home>\model-cache.json`: `{"<cli_command>": {"program": "<path>|<size>|<mtime>", "ids": {"sonnet": "...", "haiku": "..."}}}`. The program marker is read from the file system (path, size, modified time of the resolved executable), not from any tool output. Only IDs are stored; no screen text.
- **Failure.** Any failure (no list, no match, time limit, process error, a `stop_word`, an AI already running) falls back silently and sets nothing in any step result. The fallback may be stale; the worst case is the AI window shows the tool's own "unknown model" message, and the participant can switch the toggle or ask for the other model. Not a block.

Alternative considered and not chosen: an exit-status probe of a candidate ID list with a one-shot run (`-p`), which needs no terminal reading and no rule 3 exception. It costs a model call per candidate (Copilot's one-shot run measured 22 s in guided-setup) and the candidate list still goes stale. The user chose the picker read (Open Question 1).

### 5. Recording the model

`_ai_start` writes the label to the step record `model_name` for the step that starts (Part 1 `cold`/`rewrite`, Part 3 `generate`, `baseline`, `live`) and, for the five-run step, appends it to a new `models_used` list in the generate record when it is not already there. `model_name` holds the latest value; `Engine._model_name` and the `{model}` slot read `models_used` joined with " and " (one model reads as before). The `model_missing` message and the "type the model name" paths are removed: a start always records something, and "no start" is already blocked by `cli_not_running`. The gates' `model` check reads the record, so it is true after any start. `part_steps._model_differs` compares recorded values as before. Old typed values in `progress.json` stay readable and are overwritten at the next start; the `model_name` key is still accepted by the save handlers only for the test-only route and ignored from the participant interface, then removed from the interface payloads (the box is gone). The Part 3 log gate (`entry["model"]` read from the participant's log) is unchanged: it checks the log, which the AI writes from the line.

### 6. Content

`content/steps.json` line 27 and `content/part-1-steps.json` line 17 lose the `/model` instruction and the "write the name in the box" sentence and gain the toggle note (`model-selection-guidance`). `content/steps.json` `model_missing` strings are removed. New keys: `ai_model.toggle_label`, `ai_model.sonnet`, `ai_model.haiku`, `ai_model.applies_next` and `ai_model.default_label` ("the AI's own default model") in `content/lesson-ui.json` (the toggle sits in the AI window head, so it shares that file). A content test flags `/model` and "model name" prompts in participant text.

### 7. Stand-in and tests

`fake_cli.py` logs its `argv` already (`launch`), so tests assert the `--model` option by reading `fake-cli-events.jsonl`. Tests supply a `models` entry for the stand-in in a test `cli-recipes.json` override. For discovery, `fake_cli.py` gains a `--picker` behavior used only by tests: after `/model` + Enter it prints a fixed list (recorded fixtures: only IDs, a masked account line, no email). Parsers are developed against the fixtures recorded in the approved real sessions, then no more real runs are needed.

## Files and storage touched

| Location | Kept or cleared |
|---|---|
| `<home>\preflight.json` | New key `model_preference`. Kept on a lesson progress reset; moved to `<home>\reset-backup\` on a configuration reset (so the preference returns to Sonnet). |
| `<home>\model-cache.json` | New. Discovered IDs per tool and program marker. Moved to `<home>\reset-backup\` on a configuration reset; kept on a progress reset. |
| `<home>\cli-models\` | New scratch folder, empty, used as the discovery working folder. Left in place; holds no screen text. |
| `<home>\cli-recipes.json` override | Still read if present; may carry `models` data. |
| `progress.json` | `model_name` in the Part 1 and Part 3 step records is now written by the app; Part 3 generate also gets `models_used`. No answer key, no fixture text. Cleared with the steps by a lesson progress reset as today. |
| `app/eval_coach/content/cli-recipes.json` | New `models` data per supported tool. |
| `app/eval_coach/content/{steps,part-1-steps,lesson-ui,preflight}.json` | Model instructions and `model_missing` text removed; toggle text added. |
| `app/eval_coach/models.py` | New: data lookup, resolve, discovery, cache. |
| `app/eval_coach/{engine,preflight,state,gates,part_steps,server}.py` | `_ai_start`, preference and route, recorded model in steps, `models_used`. |
| `app/eval_coach/web/js/{app,panels,part-steps,lessons,preflight}.js`, `web/styles.css` | Toggle in the AI window head; model boxes removed. |
| `e2e-work/harness/fake_cli.py` | Test-only `--picker` list. Not under the generated scratch output. |
| `tests/`, `tests/frontend/` | New and updated tests (tasks). |
| `AGENTS.md`, `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md`, `docs/temp/series-review-pending-changes.md` | Updated in the same change. |
| `<home>\reset-backup\` | Unchanged location; receives the two moved files on a configuration reset. |
| `dist/eval-coach.pyz` | Rebuilt. |

## Risks / Trade-offs

- **Typing into a hidden AI.** The app types `/model` and Enter into a process nobody watches. The app cannot tell when the tool is ready, so a first-run question (sign-in, folder trust) could receive that Enter. Guards: its own empty folder, quiet wait, the `stop_words` check before typing, a hard time limit, kill without selecting. This is weaker than the exit-status probe and conflicts with the reason guided-setup rejected a hidden interactive session; it is accepted only because the user chose it (Open Question 2). If a real session shows a question appearing in the empty folder for a tool, that tool's `discover` data is removed and it uses the fallback.
- **Terminal layout changes** break the parse; the fallback means a stale ID, not a block. IDs go stale until a vendor change is noticed; the fallback list is data.
- **Folder trust.** An empty new folder may raise a trust question in some tools. Trust questions are answered only by the participant in a visible window (AGENTS.md), so the app never answers one; discovery abstains.
- **Cost.** Discovery starts a real tool (a few seconds; Copilot cold start was 22 s in a one-shot test) once per tool and version. It does not call a model for a reply and does not run when the saved result exists.
- **Devin's Haiku** is undocumented; if the alias fails, the AI window shows the tool's own error and the participant switches back. Confirmed in the real Haiku session, then data is fixed.
- **Two models in one Part 3 baseline** make the five runs less comparable. The record lists both and the log line names both; no block, same as the Part 1 note. A Part 3 nudge is not added.
- **Wrong ID with no way to tell.** The app never reads the AI window to see whether the model was accepted (rule 3), so the toggle cannot report a bad ID; the AI window's own message does.

## Open Questions

Confirm or change each; the assumed default is what the tasks implement.

1. **Discovery approach.** You chose reading the `/model` list. *Assumed: yes, with the fallback, the cache and the limits above.*
2. **Typing into a hidden session.** Do you accept the app typing `/model` and Enter into a hidden AI process (the `stop_words` check is the only guard against a first-run question)? guided-setup rejected a hidden interactive session on this ground. *Assumed: yes, only in `<home>\cli-models\`, only for tools with `discover` data, and removed per tool if a real session shows a question.* **Confirmed by the user on 2026-11-17.**
3. **Devin Haiku.** Start with the alias `haiku` for Devin, confirmed in the approved real Haiku session. *Assumed: yes.*
4. **Interface authorization (rule 11).** Do you authorize the scope listed in the proposal? *Assumed: yes.* **Authorized by the user on 2026-11-17**, for the scope listed in the proposal only.
5. **Rule 3 wording.** The exception reads: "A tool's own `/model` list may be read in memory only to get a model ID, and the text before it only to avoid typing into a question; never for a result." *Assumed: this wording.*
6. **Part 3 five runs.** Record every model used, list them in the log line, add no nudge. *Assumed: yes.*
7. **The quiet background test** keeps the tool's default model (no option). *Assumed: yes.*
8. **Toggle on the setup test page.** Show it there as in other views. *Assumed: yes.*
9. **Real-CLI sessions.** About 6 approved single-use sessions (per tool, Sonnet and Haiku) record the fixtures and confirm the launch options. *Assumed: yes, each needs your approval when it comes.*
