# Design

## Context

See proposal.md for why. What the code does today, and what that means for each decision:

- Setup creates the project once and writes `prompt-v0.md` and `test-cases.md` at its root, from the Practice task or from files the participant brought (`project.create_project`). Every Part 3 step, the blind-folder copy in `generate`, the fixtures and key work folders and the baseline line read those two names. The project's `progress.json` also records `starter`.
- Part 1 keeps the participant's rewrite at `part-1\prompt-framework.md`. The text its AI ran is `part_steps.run_copy(prompt, divider, instruction)`: the prompt, a divider, the seven rough notes, and the closing line "Save only your answer to output.txt". Part 3's `generate` copies `prompt-v0.md` as it stands, and its own pasted line already says to save to `output.txt`. A file copied from Part 1 without the notes would not be the same task.
- Part 2 keeps `part-2\test-cases.md`. Its `test-file` step already runs `import_checks.analyze`, the check an imported file passes, and Part 2's own `build` writes a `## Test input` with the same seven notes.
- Nothing connects them, and Part 3 has no step before `generate`. A Part 3 step runs through `state.STEP_KINDS` only if its content names a `kind`. Part 3 registers none today, and its progress is the top-level `steps` block, not `parts.<id>`.
- The "nine steps" are a tuple (`state.STEP_IDS`) and a course tuple (`state.COURSE`). Older progress is reconciled by `_add_key_step`, `_add_lessons_block` and `_migrate_new_lessons`.
- Evidence wording is pinned in two places: the `series-intent-framing` spec, and `tests/test_learning_priorities.py` (lines asserting "If the score did not move, the change did not help" and "Part 4 adds those rounds and checks that a known-good answer scores 95% or more").
- The Stage 3 task notes (local, not in git) say the official program page governs when they differ. The user supplied a screenshot of its "What We Examine" section on 2026-11-24, and D12 maps its criteria.

## Goals / Non-Goals

**Goals:**
- A learner always sees, before the first generation, which prompt and test cases Part 3 will score, and chooses any carry-forward explicitly.
- Part 3 and every later step keep reading the same two project-root files, so nothing downstream changes.
- Original and in-use files are never lost, overwritten or replaced behind the learner's back.
- One wording standard for evidence, and one agreed contract for the Part 4 to Part 5 handoff, before either Part is built.

**Non-Goals:**
- No handoff between Part 3 and Part 4 is built (#15 does that). This design fixes the contract it must meet.
- No change to Part 3's gates, checker, log format, answer key or restart behavior (Part 3 still offers none).
- No new storage of file text in `progress.json`.
- No scoring or certification claims. Navigation (#9) is untouched.

## Decisions

### D1. A tenth Part 3 step, `inputs`, placed after `several-runs` and before `generate`
The learner sees the pair before anything is generated from it, so no run is made from one pair and scored against another. It is the one interface change the user authorized.
- *Alternative: a panel inside `generate`.* Rejected: `generate` is an AI step with auto-start and a watcher, and a choice must precede the first start.
- *Alternative: do it in setup.* Rejected: setup runs before Parts 1 and 2 exist.
- *Alternative: copy Part 1 and Part 2 files automatically when each finishes.* Rejected: it is the silent substitution the issue forbids.

Part 3's first step kind, `choose_inputs`, is registered in `state.STEP_KINDS`. It starts no process (`start` and `send` are `not_supported`). Its record `steps.inputs` is `{"last_check": null, "choice": {"prompt": {...}, "test_cases": {...}}}`. The lock rule needs one check during apply: with `inputs` between `several-runs` and `generate`, `generate` has a step directly before it and no lesson. That should resolve to "previous step done", like `fix` after `run`, and a test pins it.

### D2. The project-root files stay the single source of truth
`inputs` changes what `prompt-v0.md` and `test-cases.md` hold, and then locks them. Part 3's steps, helper folders and the baseline line are unchanged. *Alternative: point Part 3 at `part-1\` and `part-2\` paths.* Rejected: it would change the nine steps and make every later copy depend on files Part 1 and Part 2 may restart.

### D3. What is carried from Part 1 is the text the AI ran, minus the closing line
The carried prompt is `prompt.rstrip() + "\n\n" + divider + "\n\n" + notes + "\n"`, built by the same helper Part 1 uses, without the `instruction`. `generate`'s line already says where to save. A rewrite on its own would lack the task input. For test cases, the Part 2 file is carried as it is saved.

### D4. Choices are explicit, reversible until Continue, and lossless
`POST /api/step/submit` takes `{"use": {"prompt": "keep"|"part1"|"practice", "test_cases": "keep"|"part2"|"practice"}}` (or `"both": "mine"`). Before writing, the active file's bytes are hashed. If `part-3\replaced\<name>.<first 8 hex of sha256>` does not exist, the bytes are written there. The new file is then written atomically. Nothing is deleted or overwritten, a switch back is the same operation, and the Part 1 and Part 2 files are only read. Continue (`check`) refuses a blank prompt or test cases that fail `import_checks.analyze`'s blocking findings, records `{source, sha256}` for each file, and marks the step done. After that, `submit` is refused with `step_done`. *Alternative: a `.bak` suffix next to the original.* Rejected: it can overwrite an earlier backup and it clutters the project root.

### D5. Labels come from comparing bytes
Known sources are the bundled Practice files (the catch-up comment stripped, as setup does), the carried Part 1 text and the Part 2 file. The active file's label is the first match. `starter == "own"` with no match reads "files you brought". No match otherwise reads "a file in your project folder". Part 1 offers need `rewrite` done and a non-blank file. A Part 1 file whose hash differs from `rewrite`'s recorded `prompt_hash` is offered as "changed after its answer" and is not preselected. Part 2 offers need `test-file` done and a file that passes the blocking checks now. Part 2 records no hash today, so a Part 2 file that changed but still passes is offered as it is. The check at Continue still blocks an unusable pair. The user decided not to add a stored hash to Part 2.

### D6. Mismatch is a note, never a block
The notes are compared by squashing spacing. A project that holds the participant's own task and a pick of a Practice file shows the note too. A learner may legitimately change the task, so the note informs and does not block.

### D7. Later restarts do not reach Part 3
Part 3's copy is separate bytes. After Continue, the step view compares the chosen source with its recorded hash and shows unchanged, changed or gone. It is information only.

### D8. Older progress is completed, not rewritten
`validate_progress` adds the `inputs` record. If any later Part 3 step is in `done`, or Generate has already started (a recorded start or a saved run), `inputs` is inserted into `done` with `choice.*.source = "existing"` and the hashes of the files now in the project. This preserves the inputs for saved or in-flight answers without asking the learner to reconfirm them. Preserve the selected track if generation already started but the project has not locked its track yet. Otherwise `inputs` is the next step. Migration does not write files. `_add_lessons_block` and `_migrate_new_lessons` use the course tuple, so the new step id is added to `COURSE`, `STEP_IDS` and `PROMPTFOO_*` in one place.

### D9. Evidence wording is a short vocabulary, enforced by a scan
Three phrases: **observation** (one comparison, in Part 1 and Part 3), **measured gain on these rules** (a higher score on the same rules), and **no measured gain on these rules** (equal or lower). The text does not use "did not help", "no benefit" or "did better" for a result. The standard says a total can hide a worse rule, that a rule moving to NOT CHECKED is lost coverage, and that a simpler prompt at the same score can be worth keeping. The wording edits are in `p1-benefits`, `rescore`'s questions, gate label and troubleshooting, the compare `change_same` text, `baseline-why` (its "What comes next", its "How this course does it" passage and a line in its Stage 3 note), the `baseline` step lines in both tracks, and the review item that says Part 4 "tries to beat" the baseline. `baseline-why` is already at its 400-word cap, so the new sentences replace old ones.
A content test fails on the banned phrases in lessons, steps and the glossary. This extends the existing tests; the two assertions that pin the old wording change with the spec.

### D10. Three thresholds, and where each lives
- **Known-good answer (#15).** Chosen from the written requirements before its score is seen. The checker should score it 95% or more. If it does not, investigate the checker or the spec, never loosen a rule to pass it. If a valid repair changes verdicts, rerun the original five answers and record a corrected Iteration 0.
- **Five-answer overall score (#15).** A coaching target, never a gate, and kept apart from the known-good check. Completion is verified evidence of two documented rounds after Iteration 0, each with starting score, hypothesis (written before scoring), change, measured result and reasoning. Flat and reverted attempts are logged as such and never called gains.
- **Load-bearing audit (#14).** Two reported outcomes, never merged. *Audit complete* means every direction is mapped or has a recorded reason, the new log iteration matches the saved results, and the package reruns from another folder. *Meets the rubric criterion* means the exact load-bearing fraction is 90% or more (8 of 9 is 88.9% and does not meet it, and is never rounded). A real requirement with no rule is a coverage gap: flagged, not deleted, not given an invented link. Known filler is still removed. The #14 "done when" that requires 90% for completion is rewritten: the gate checks completeness and shows the exact fraction and whether it meets the criterion.

### D11. The Part 4 to Part 5 handoff contract (normative for #15 and #14, written into `docs/SPEC.md`)
- **Attempts.** Iteration 0 is the Part 3 baseline. Each Part 4 attempt `n` is stored under `part-4\attempts\<n>\` as its own prompt, test cases, checker (the script, or the promptfoo config with the local files it reads), `runs\run-1` to `run-5`, and a per-criterion `results.json`. Part 3's files are never edited.
- **Manifest.** `progress.json` `parts.part-4` holds, in chronological order, `{n, parent, log_entry, model, hashes: {prompt, test_cases, checker, runs}, results: {criterion: {passes, checked_runs}, not_checked: [...]}, decision: "kept"|"undone"|"pending"}`. It holds hashes and counts only, never text.
- **Kept pointer.** The kept version is the last attempt whose decision is `kept` (Iteration 0 if none), set by the learner's explicit keep or undo, never "the latest". Rejected attempts stay in the manifest and the log, in order.
- **Undone second edit.** Attempts 0 and 1 kept, 2 undone: Part 5 starts from 1, the log still shows 2 as undone, and the package contains attempt 1's files only.
- **Mismatch detection.** Part 5 recomputes the hashes from the files and refuses to start the audit on a set that fails any of: `prompt_changed`, `rules_changed`, `checker_changed`, `answers_changed` (not five files, or different bytes), `results_missing`, `log_mismatch` (the log entry for that attempt, read by `parsers.parse_iteration_log`, does not equal the saved results) and `coverage_changed` (the criterion set differs from Iteration 0: flagged, never counted as a gain). It says which one, in plain words, and offers the labelled Practice task path. It never repairs or overwrites.
- **Relocated rerun.** The package built from the kept attempt reruns the check on its own five saved answers from a new folder (script track: `check.py` on `runs\`; promptfoo track: the same config and local files, offline) and must reproduce the logged per-criterion results with no AI call, credentials or original folder.

Part 4's log entry gains a decision line so the parser can verify `kept` against the manifest; the exact parser extension is part of #15's design. *Alternative: infer the kept version from the latest log entry.* Rejected: it fails the undone-second-edit case.

### D12. Traceability and the pilot are documents, not behavior
`docs/CONTENT-RULES.md` gets the map (columns: examiner criterion, Part and step, evidence produced, examiner requirement or course convention) and a short pilot plan (an unseen task; three observable abilities and one rerun by a second person). A test requires a row for each of the Prompt, Evaluations and Log. The program's wording is paraphrased, not quoted.

The map's rows were checked on 2026-11-24 against the program's "What We Examine" page, from a screenshot the user supplied. Results:

| Artifact | What the page asks (paraphrased) | Course exercise (Part, step) | Status |
|---|---|---|---|
| Prompt | A markdown file with the practitioner's prompt; structured prompting (RTCC or similar) | Part 1 `rewrite`, `own` | Examiner requirement |
| Prompt | Deliberate instruction design | Part 1 `rewrite`; Part 5 audit | Examiner requirement |
| Prompt | At least 90% of instructions are load-bearing, each serving at least one criterion | Part 5 audit | Examiner requirement |
| Prompt | No dead weight or filler | Part 5 cut | Examiner requirement |
| Evaluations | Scripts, promptfoo YAML or documented test cases | Part 2 `test-file`; Part 3 `build` | Examiner requirement (the Script and promptfoo tracks are the course's two options) |
| Evaluations | At least 3 distinct criteria, not variations of one check | Part 2 `draft`, `test-file` | Examiner requirement |
| Evaluations | Substantive quality checks, not window dressing | Part 2 `thresholds`; Part 3 `fixtures`, `predict`, `run`, `fix` | Examiner requirement |
| Evaluations | Capable of 95% or more when the prompt performs well | Part 4 known-good check | Examiner requirement. The figure is about what a good answer can score, not a target for every answer |
| Evaluations | Runs on mid-tier models or lower | Sonnet or Haiku choice; Part 3 `generate` | Examiner requirement |
| Evaluations | Clear pass or fail thresholds or scoring rubrics | Part 2 `thresholds` | Examiner requirement |
| Log | At least 2 documented iterations | Part 4 | The program says 2 or more iterations. Two rounds after Iteration 0 is a course convention that meets it either way |
| Log | Each iteration has baseline scores, hypothesis, change, measured results and reasoning | Part 3 `baseline`; Part 4 | Examiner requirement |
| Log | Evidence of the red, green, refactor cycle | Part 4 | Examiner requirement |
| Log | Chronological progression with cause and effect | Part 4; Part 5 audit entry | Examiner requirement |
| Package | A ZIP with the three artifacts; a README is optional | Part 5 package | Examiner requirement |
| (none) | Five saved answers per version, the Script track's `check.py`, Iteration 0 numbering, the 95% five-answer coaching target, the attempt manifest | Parts 3 to 5 | Course convention |

The page does not mention five answers, Iteration 0, `check.py` or a coaching target, so those stay conventions.

## Files and storage touched

| Location or key | Change | Kept or cleared |
|---|---|---|
| `<project>\prompt-v0.md`, `<project>\test-cases.md` | Replaced only by an explicit pick in `inputs`, before Continue | Progress reset keeps them. Configuration reset moves them (unchanged) |
| `<project>\part-3\replaced\<name>.<hash8>` | New. A copy of any file before it is replaced | Progress reset keeps it. Configuration reset moves it, then removes the empty folder. Never read by the app after writing |
| `<project>\part-1\prompt-framework.md`, `<project>\part-2\test-cases.md` | Read only | Unchanged |
| `progress.json` `steps.inputs` | New: `{"last_check", "choice": {"prompt": {"source","sha256"}, "test_cases": {"source","sha256"}}}`. No text | Cleared by a progress reset |
| `progress.json` `done` | `inputs` placed before `generate` (older progress completed as in D8) | As today |
| `<home>\reset-backup\` | Receives the above on a configuration reset | One slot, as today |
| `content/steps.json`, `lessons.json`, `part-1-lessons.json`, `part-1-steps.json` | Words only | Shipped |
| `docs/SPEC.md`, `docs/CONTENT-RULES.md`, `AGENTS.md` | Step list, contract, map, pilot, step count | Tracked |

## Risks / Trade-offs

- **A step before `generate` shifts the step list and the lock rule** → keep the step ids in one tuple, add the `inputs` position tests for both tracks, and run the whole backend suite and the stand-in harness.
- **Older progress** → D8 mirrors `_add_key_step`. Add tests for a project at each point of Part 3 and one with demo access.
- **`baseline-why` is at its word cap** → the new sentences replace old ones, and the content test measures it.
- **Part 2 staleness is weak, since Part 2 records no hash** → the blocking checks at Continue still stop an unusable file. The user chose not to change Part 2.
- **A learner mixes tasks on purpose** → a note, not a block (D6).
- **The new panel is an interface change** → limited to one step kind from existing tokens and components, and covered by one Playwright spec.
- **Wording that bans "did not help" could bleed into unrelated text** → the scan is limited to lessons, steps and the glossary, and the phrase list is short.
- **The contract describes unbuilt behavior** → it lives in `docs/SPEC.md` and the two issues, not in the main OpenSpec specs, until #15 and #14 implement it.

## Migration Plan

Ship in one change. A project saved before this step loads with `inputs` done or next, with no file moved. Rolling back is a revert: `part-3\replaced\` is plain files, and the project-root files stay the participant's.

## Open Questions

Resolved with the user on 2026-11-24:
- **Official wording.** Verified against the program page (D12). The page's "at least 2 documented iterations" does not say whether Iteration 0 counts, so the course asks for two rounds after Iteration 0 and labels that a convention.
- **Part 2 hash.** Not added. Part 2 stays untouched and relies on the blocking checks.
- **Issues #14 and #15.** Edits are drafted at apply time and applied with `gh issue edit` after the user approves the text.

Still open:
1. **The pilot.** *Assumed default: only the plan is recorded. Running it with learners, and any real AI run, need a separate approval.*
