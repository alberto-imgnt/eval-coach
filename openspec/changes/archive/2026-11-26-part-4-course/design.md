# Design

## Context

See proposal.md for why. Current state that shapes the approach:

- **Slice A built the engine dark.** `attempts.py` holds `Attempts` (create, hypothesis, score, known-good, decide, log gate, completion). `state.PART_4` is in `DARK_PARTS` with five singular step ids; `series.json` keeps the row at `soon`; no route, step kind or panel exists for it.
- **Panels are chosen by step id.** `web/js/views.js` renders `PANELS[step.id]`, and `PANELS` is the spread of `part-steps.js`, `criteria-steps.js` and Part 3's own entries. A step with no entry shows only its words, a checklist and a check button. This is why the interface authorization in the proposal is needed for any Part 4 step the participant works in.
- **Step kinds are Python handlers.** `state.STEP_KINDS` maps a kind to an object with `detail`, `submit`, `start`, `check` (and optional `report`, `settle`). `server.py` has no per-kind routes: everything goes through `/api/step/submit`, `/start`, `/auto-start`, `/check`. Part 1's `WriteAndRun` shows how to run one fresh AI window and watch for `output.txt`.
- **Part 3's `generate` is not reusable as is.** `_launch_step` and `_watch_output` are written for the blind folder and `run-N` of the project; `_start_watcher` and `_ai_start` are generic.
- **The optional-step mechanism is one hard-coded id.** `state.OPTIONAL_STEP = "live"` sits outside the step order, on the promptfoo track only.
- **Lesson activities already withhold answers.** `sort` and `choice` return placements, feedback and extra text only once answered, and review items and per-lesson state are shared by every Part.
- **The reference checker already drives the engine in tests** (`tests/golden/reference-check.py`, used by `test_part_4_attempts.py`), so its output format is what the app's parsers read.

## Goals / Non-Goals

**Goals:**
- A Part 4 the participant can complete end to end on the stand-in, on both tracks, with no change to any existing panel, layout, style or id.
- Everything the participant sees comes from `content/*.json`, and every number in the worked example is computed by the reference checker in a test.
- The Practice baseline gives a participant with no usable baseline a full, labelled practice run without reading or writing their own files.

**Non-Goals:**
- Harness stages (slice C), Part 5 behavior, any real AI run, any interface change beyond the authorization in the proposal.
- Rewriting slice A's manifest, hashes, kept pointer, evidence wording or completion logic. They are called, not changed, except for the three additions below.

## Decisions

### D1. Fixed round-suffixed steps replace slice A's singular ids
`COURSE_4` becomes the order in the `part-4-course` spec. Step ids are `starting-point`, `known-good`, and `hypothesis-n`, `edit-n`, `measure-n`, `decide-n` for n = 1 to 3. A step id maps to `(phase, round)` by its suffix, and round n is attempt n. Part 4 moves from `DARK_PARTS` into `PARTS`, with `restart=None`. *Alternatives:* repeat five singular steps per attempt (needs locking and panel changes, rejected); one attempt panel with a picker (new interface, rejected). Slice A's dark ids never reached saved progress, so no migration is needed; `validate_progress` accepts the new ids and rejects an unknown one as before.

### D2. One Python module of step kinds, no new route
A new `attempt_steps.py` registers six kinds: `choose_start`, `known_good`, `hypothesis`, `edit`, `measure` and `decide`. Each handler is a thin wrapper over `Attempts.for_engine(engine)`. Actions arrive as `{"action": ...}` in `/api/step/submit`, the AI window opens through `/start` and `/auto-start`, and the gate runs through `/check`, so `server.py` gets no new route. Each kind's `detail` returns the round, the attempt's view (`Attempts.view(n)`, which already separates `known_good` from `five_answers`) and the gate report. *Alternative: Part 3-style per-step methods in `engine.py`.* Rejected: `engine.py` is already large and the kind registry exists for this.

### D3. The measure step is a new handler built on Part 1's launch pattern
`measure-n` prepares `<home>\part4\blind\` (cleared at each start) with only the attempt's `prompt.md`, starts the AI through `_ai_start`, and uses `_start_watcher` to save the `output.txt` it sees into the attempt's next empty `runs\run-k.txt`. It records the model it started in the step's own record and gives that to `Attempts` as the model callable, because `engine._model_name` reads Part 3's `generate` record. After five answers an explicit "Score these five answers" action calls `Attempts.score(n)`, which already runs the checker outside the engine lock and refuses a result if a file changed. The paste flow follows `ai-window-paste-flow`: the window opens by itself, the line has a Copy button, the app never types, and the window closes when the step passes.

### D4. A baseline object makes Iteration 0 configurable
`Attempts` reads Iteration 0 only through a small baseline object: `OwnBaseline(paths)` (today's root files) or `PracticeBaseline(paths)` (`part-4\practice\`). Both give `prompt`, `test_cases`, `checker(track)`, `runs`, `run_file(k)`, `iteration_log` and the local files a promptfoo config reads. `AttemptPaths` takes a base folder so a Practice attempt is `part-4\practice\attempts\<n>\`. The choice is saved as `parts.part-4.start` (`"own"` or `"practice"`), is absent in older progress and means `"own"`, is set once, and is refused once attempt 1 exists. Choosing Practice copies the bundled files create-only into `part-4\practice\`. *Alternative: copy the Practice files into the project root as Iteration 0.* Rejected: it overwrites or mixes the participant's own Part 3 files.

### D5. The Practice kit reuses existing bundled files and adds only the checker and the log
Reused: the Practice prompt and test cases (`kit/northwind/…`, with the catch-up comment stripped as setup does) and the five sample answers. New, under `kit/part4/practice/`: `check.py`, `promptfooconfig.yaml` and an `iteration-log.md` with Iteration 0 already written. `check.py` and the config are derived from the reference checker and `tests/golden/promptfoo/promptfooconfig.yaml`, and a test compares their per-rule results with the reference checker's on the same five answers, so they cannot drift. The log entry is checked against the checker's result by the same count helpers the log gate uses.

### D6. The log gate gets one more item, and the decide step writes nothing
`Attempts.check_log()` adds a seventh item per attempt: Change, Result and Reasoning each have text (presence only), reusing the entry fields `parse_iteration_log` already returns. The decide handler shows the line to paste after a decision. The line reuses the skill's `run + log` mode and names the log file for the chosen starting point:

`Read skills/build-eval-script/SKILL.md and follow it in run + log mode. The runs are part-4/attempts/{n}/runs/run-1.txt to run-5.txt. The prompt file is part-4/attempts/{n}/prompt.md. The model was {model}. Append the entry to {log} as Iteration {n}. Copy the Hypothesis word for word from part-4/attempts/{n}/hypothesis.md and leave Change, Result and Reasoning empty.`

The skill stays byte-identical (AGENTS.md rule 8); the changes are in the line. The participant writes Change, Result, Reasoning and the Decision line, and the gate compares. The app never edits the log.

### D7. The worked example is in lessons, and the reveal is the activity's pass
The prediction is a `sort` activity (rises, stays, falls for each of the six rules). The exact edits and the per-rule results are a `reveal` field of the activity that the server returns only when the activity is passed, the same way existing activities return feedback. No `kit:` file holds them, so no kit gate is extended. The ten authored answers (five per round) live under `tests/golden/part4-worked/` and are not shipped. Tests score them with the reference checker, compare the counts with the lesson's table, and assert the reveal text is absent from every response before the pass. *Alternative: ship the answers as gated kit files.* Rejected for now: it needs a lesson-activity variant of `GATED_KIT` for little teaching gain.

### D8. Round 3 needs "optional trailing steps"
`state.Part` gets an `optional_steps` tuple, set from content, listing steps that follow the required order, unlock in their own order after the last required item and never count toward the Part being Done. `OPTIONAL_STEP = "live"` keeps its own path and is untouched. The Series map and sidebar counts use required items only; the optional steps show with the existing "Optional step" label that `views.js` already renders for `step.optional`. *Alternative: a single optional "round 3" step.* Rejected: a round is four distinct steps.

### D9. Panels are additive and keyed by id
`web/js/attempt-steps.js` exports one panel per Part 4 step id, built from a few render functions (starting-point choice, text box that saves and locks, prompt editor, run list with the per-rule table, keep or undo with the log gate), reusing existing components and styles. `panels.js` gains one import and one spread. Existing entries, ids, classes and copy are untouched. New Playwright tests cover the panels, on both tracks.

## Files and storage touched

| Location or key | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/attempt_steps.py` | New: six step kinds | Shipped |
| `app/eval_coach/attempts.py` | Baseline object, round model callable, presence item | Shipped |
| `app/eval_coach/state.py` | `COURSE_4` ids, `PART_4` into `PARTS`, `optional_steps`, `new_part_4_extra` gains `start` | Shipped |
| `app/eval_coach/project.py` | `PracticePaths`, `AttemptPaths` base folder | Shipped |
| `app/eval_coach/lessons.py` | Activity `reveal` returned on pass | Shipped |
| `app/eval_coach/engine.py`, `reset.py` | Kind wiring; `part4` added to `HOME_SCRATCH` | Shipped |
| `app/eval_coach/content/part-4-lessons.json`, `part-4-steps.json` | New | Shipped |
| `app/eval_coach/content/series.json`, `glossary.json`, `part-4-attempts.json` | Part 4 row to `course`; terms; new messages | Shipped |
| `app/eval_coach/kit/part4/practice/` | New: `check.py`, `promptfooconfig.yaml`, `iteration-log.md` | Shipped |
| `app/eval_coach/web/js/attempt-steps.js`, `panels.js` | New panels; one import line | Shipped |
| `tests/golden/part4-worked/` | New: the ten authored answers and the checker proof | Tracked, never shipped |
| `<project>\part-4\practice\` and `part-4\practice\attempts\<n>\` | New | Kept by "Reset lesson progress"; moved by "Reset app configuration" |
| `<project>\part-4\attempts\<n>\` | Used as slice A built it | Kept and moved as above |
| `<home>\part4\blind\` | New scratch folder for `measure-n` | Cleared by both resets (`HOME_SCRATCH`) |
| `progress.json` `parts.part-4` (`start`, `attempts`, `steps`, `rerun`, `iteration_0`) | `start` and the new step records are new | Cleared by a progress reset; hashes and counts only |
| `docs/SPEC.md`, `docs/CONTENT-RULES.md`, `docs/RUNNING-EVALS-COURSE.md` | Part 4 section; Parts table row; note that Part 4 is built | Tracked |

## Risks / Trade-offs

- **The skill's log mode may not follow the line for an attempt folder.** It defaults the log to "next to the test-case file" and leaves Hypothesis empty. → The line names the runs, prompt, log file and Hypothesis explicitly. The stand-in can only test the app's side (the gate); one real run per tool confirms it and needs the user's approval.
- **A participant edits files by hand after scoring.** → Hashes are recomputed at read time, stale evidence is shown and never repaired, and deciding is refused (slice A).
- **A progress reset keeps the attempt folders but clears the manifest.** Round 1 would then find files already there. → `start()` is create-only and never overwrites; the starting-point step says what was kept, and a test covers resuming over kept files.
- **The reveal text is in the shipped content JSON.** → The server never returns it before a pass, a test fails if any pre-pass response contains it, and the content file is not served as a static file.
- **Optional trailing steps touch Part completion and locking**, the engine's most shared code. → Gate it with tests that Parts 1 to 3 give the same course lists, counts and statuses as before.
- **Authored answers are plausible, not real model output.** → The lesson says so, the learner's own rounds are measured, and the numbers are proved by the reference checker, not typed.

## Migration Plan

Ship in one change. Older progress loads unchanged: `parts.part-4` has no `start`, which means `"own"`, and slice A's dark ids never reached saved progress. Rolling back is a revert; the Practice and attempt folders are plain files that Parts 1 to 3 never read.

## Open Questions

1. **Practice results and Part 5.** Part 5 reads the kept version. *Assumed default: a Practice kept version is marked practice in the manifest's `start` and Part 5 offers its labelled Practice path, as `docs/SPEC.md` "Evidence handoff" already says. Part 5 is not built here.*
2. **The reveal's shape.** *Assumed default: `reveal` is markdown (a table and the edit text), rendered by the existing safe markdown renderer, which supports tables. If the activity view cannot carry it without touching an existing panel, the reveal moves into the lesson's own follow-up text.*
3. **The edit step's "a change is needed" check.** *Assumed default: the prompt must differ from its parent ignoring spacing. It does not judge how many things changed; the lesson teaches one change, and the app cannot tell.*
4. **Practice and the promptfoo track.** *Assumed default: the bundled config is verified on the stand-in only unless the private Node is present; one real promptfoo run needs the user's approval.*
