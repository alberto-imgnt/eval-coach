# Design

## Context

See proposal.md for the outcome, the live-session mapping and the authorizations. Built on `generalize-parts` (the Part registry, per-Part progress under `parts.<id>`, unique ids, a step `kind` hook, per-Part interface strings). Observed in the repository:

- Part 3's steps each have a bespoke renderer in `web/js/panels.js` and handler in `engine.py`. A new Part with new kinds of step cannot reuse those handlers, but can reuse their lifecycle pieces: the one-CLI terminal (`terminal.py`), `_start_watcher` and `_watch_output` (capture `output.txt` when non-empty and unchanged across two one-second polls), the model-name box of `generate`, the editor pattern of `fix` (edit a file in the app), the yes or no grid of `readback`, the compare layout of `cli_compare`, step questions (`step_checks` in the lessons file), `kit:` sources and the glossary.
- Part 3's `generate` step already types the exact line Part 1 needs (`Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.`) into a folder holding only `prompt.md`. The stand-in `fake_cli.py` already handles it.
- Content rules enforced by tests: equal word count across the options of a choice; word caps; `kit:`-only citations; banned words; "Part, not session"; skills byte-identical (Part 1 bundles no skill).
- The source materials (October 2026 live session) are read-only on OneDrive; their tool, room and facilitator wording cannot be carried over (AGENTS.md rules 7 and 10).

## Goals / Non-Goals

**Goals:**
- A participant with no facilitator reaches the live session's outcomes: names the four benefits, explains why structure helps to a non-technical and a technical reader, has a before and after pair, and has rewritten one real prompt.
- Discovery before theory is enforced by structure and by tests, not by trust.
- Everything the app does in Part 1 decides from files and the participant's own answers.

**Non-Goals:** the proposal's "Out of scope" list, plus: no new route, no new storage mechanism, no change to Part 3.

## Decisions

**D1. Part 1 registry entry and ids.**
`part-1`; `mission = p1-mission`; course (in order): lesson `p1-mission`, step `cold`, step `score`, lesson `p1-gaps`, lesson `p1-frameworks`, step `rewrite`, step `rescore`, lesson `p1-benefits`, step `own`. Part 3's ids (`mission`, `generate`, `run`, ...) do not collide. Course list groups (content, in `part-1-lessons.json` `ui.course_groups`): "Start with your own words" (`p1-mission`, `cold`, `score`), "Name the gaps" (`p1-gaps`, `p1-frameworks`), "Try a framework" (`rewrite`, `rescore`), "Keep it and reuse it" (`p1-benefits`, `own`).

**D2. Lesson content outline** (the words are written in the apply tasks and reviewed by the user; this fixes the shape). Each lesson after the mission follows "In the method." (link: ask clearly, or know what you need), "The idea.", short passages, one "How this course does it".

| Lesson | One concept (win line) | Activities (none blocks Continue) | Retrieval | Minutes |
|---|---|---|---|---|
| `p1-mission` | purpose, why checking matters, the method, the six-Part map | none | none | 3 |
| `p1-gaps` | every gap was something the prompt never said | `gaps-sort` (sort typical gaps into five numbered kinds of missing information plus a set-aside group), `gaps-own` (reflection, 8 words), `gaps-known` (choice: why the AI could not have known) | `r-gaps-1`, `r-gaps-2` | 6 |
| `p1-frameworks` | people named kinds of information a prompt needs; those names are frameworks; our five are an example, and you build your own labels when none fits | `fw-map` (sort the labels of both samples, one label per item, into the kind each mainly covers; the feedback names the partial fits, and no full sample prompt is shown before the rewrite), `fw-partial` (choice: why kinds 4 and 5 map only partly), `fw-own` (choice: what to do when no framework fits) | `r-fw-1`, `r-fw-2` | 5 |
| `p1-benefits` | structure gives four benefits; it is the structure, not the letters | `ben-sort` (sort what you saw into the four benefits), `ben-structure` (choice: why both samples beat the cold prompt), `ben-explain-tech` (choice for a technical reader), `ben-explain-plain` (reflection, 20 words, for a non-technical colleague) | `r-ben-1` to `r-ben-3` | 7 |

Typical gaps (bundled file `kit/part1/typical-gaps.md`, from the facilitator guide's chat examples and bucket table): "Sounds like I'm bragging" (1), "Reads like a formal report, not a quick note" (1), "An email with a subject line, not a Teams message" (2), "Didn't know who the update was for" (3), "Left out that I work on two clients plus internal work" (3), "Way over 150 words" (4), "Went Monday to Friday instead of by client" (4), "Blocker buried and no clear ask" (5), "Never said what I need from my lead" (5), "Made up a detail about Contoso" (set aside), "Just felt boring" (set aside). Every item has one clearly best kind, with feedback that says why; the lesson says people will not always agree and the point is that every gap fits somewhere.
Step titles lead with the idea in tool-neutral words (no counts or file names): "Write it your way" (`cold`), "Score what you got" (`score`), "Try a framework" (`rewrite`), "Score it again" (`rescore`), "Use it on your own work" (`own`). Lesson titles say what the learner gets, never a teaching device: "What your first prompt left out" (`p1-gaps`), "Frameworks: ready-made labels for what a prompt needs" (`p1-frameworks`), "Four ways a structured prompt helps you" (`p1-benefits`). The sorting groups are "kinds of missing information"; the word "bucket" is not used in Part 1 text and is not a glossary term.

**D3. Three step kinds, content-driven, in one handler module.**
Each Part 1 step names a `kind` in `part-1-steps.json`; `part_steps.py` holds one handler per kind and the gates. Routes stay the existing `/api/step/*`.

| Kind | Steps | `submit` body | `check` gate | `GET /api/state?step=` data |
|---|---|---|---|---|
| `write_and_run` | `cold`, `rewrite` | `{"prompt","model_name","framework"?}`: saves the prompt file (the participant's explicit Save) and the model name | prompt non-empty (and, for `rewrite`, different from the cold prompt and a label set chosen); output saved; model name non-empty | saved prompt, notes preview, scenario, label choices (equal text), run copy preview, model name, `cli` block, output text once captured |
| `score_form` | `score`, `rescore` | `{"answers":{"r1":"yes"\|"no",...},"gap","in_prompt","reflections":{...}}` | five answers; required text fields non-empty | the output (plain text), the five requirements from content, saved answers, `score` (n of 5, from the answers), and for `rescore` the first run's prompt, output and score and the delta |
| `write_pair` | `own` | `{"before","after","labels"}` | all three non-empty and `before` differs from `after` | saved texts |

`score_form` fields are described by the step content (`rows`, `fields`, `reflections`), so Part 2 and Part 4 can reuse it. Nothing is graded: the score is the participant's, and no gate can fail because of what they answered, only because a field is empty.
*Alternative:* write Part 1 as ten hand-built step handlers like Part 3. Rejected: three kinds cover five steps with less code, and later Parts reuse them.

**D4. Run copy and the notes.**
The participant's saved prompt holds only their words (`prompt-cold.md`, `prompt-framework.md`). Start writes the folder's `prompt.md` as those words, a blank line, a plain divider line from content, and the rough notes from `kit/part1/rough-notes.txt` (the same notes as the scenario card and Northwind's). The preview on the page is the same text. *Alternative:* ask participants to paste the notes. Rejected: it adds a copy-paste chore for non-technical readers and makes the two runs differ by accident, while "same notes" is the control of the comparison.

**D5. Capture reuses the existing watcher.**
`_start_watcher(source, destination)` and `_watch_output` are reused with a destination under `<project>\part-1\` and a completion callback; the only edit to Part 3 code is making `_finish_run`'s "advance the run counter" part a parameter (Part 3 passes today's behavior). A done step has no Start control (one shot); Reset lesson progress is the way back.

**D6. Storage and reset inventory.**
`progress.json` `parts.part-1` = `{"done": [...], "steps": {"cold": {"model_name","prompt_hash","last_check"}, "score": {"answers","gap","in_prompt","last_check"}, "rewrite": {"framework","model_name","prompt_hash","last_check"}, "rescore": {"answers","reflections","last_check"}, "own": {"labels","last_check"}}}`. These hold only what the participant answered; no key exists. Reset inventory additions (`reset.py`; `tests/test_reset.py` fails when a file is on no list): project `part-1\output-cold.txt` and `output-framework.txt` are moved by both resets; `part-1\prompt-cold.md`, `prompt-framework.md`, `own-before.md`, `own-after.md` are kept by Reset lesson progress and moved by Reset app configuration (like `prompt-v0.md`); home `part1\` is moved by both.

**D7. Interface (authorized, rule 11).**
- U1 `app.part` (default `part-3`); `openPart(id)` sets it; state requests pass `part`; `course_text` (header sub-brand, route-map strings, course groups, finished screen) is the active Part's.
- U2 editor: a `<textarea>` with a visible label, Save, "Insert labels", character-count-free; the notes preview below it, read-only.
- U3 score form: a `<fieldset>` per requirement with two radios; text areas; "n of 5" as text.
- U4 compare: two columns (stacked in `mid` and `narrow` layouts) of plain text blocks, reusing the `cli_compare` result styles.
- U5 Part 1 row: the existing course-row component fed by `state.series`.
New code lives in `web/js/part-steps.js`; `app.js`, `views.js`, `series.js` and `panels.js` change only where they read the active Part. No new design tokens. Part 3's screens are not edited.

**D8. Kit files and glossary.**
`kit/part1/`: `rough-notes.txt`, `typical-gaps.md`, `frameworks-map.md` (the reveal table), `sample-rtcc.md`, `sample-rise.md` (the sample prompts from the live materials, re-checked for banned words and Teams-meeting wording). Each is cited by a lesson, step or test (the orphan check). Pre-reveal lessons cite only `rough-notes.txt` and `typical-gaps.md`; `frameworks-map.md` is cited from `p1-frameworks`; the sample prompts are cited from `p1-benefits` only. A content test asserts these citation boundaries. `content/glossary.json` gains entries: prompt, prompting framework, gap (kind `idea`); RTCC and RISE (kind `idea`, "a sample"); cold prompt and scenario card (kind `course`, begin "In this course,"). The reference card is unchanged.

**D9. Stage 3 note in Part 1.**
One optional note of at most 60 words at the end of `p1-benefits` (no activity): the Stage 3 Prompt is a structured prompt like this one; the program's own instructions decide what to submit; nothing here is needed to finish the Part. Requires the `learning-priority-order` change (one note per Part's last lesson). Tests: the note names the Prompt and appears nowhere else in Part 1.

**D10. Stand-in and tests.**
`fake_cli.py` already writes an `output.txt` from `prompt.md`; it gains one rule: if `prompt.md` has label lines (a word followed by a colon at the start of a line) it writes the better sample, otherwise the weaker one (harness only, in `e2e-work\harness\`). Harness stages for Part 1 run only with `E2E_PROFILE=standin`. Backend tests: `tests/test_part_1_content.py` (lesson shape, caps, option parity, citation boundaries, no framework names before the reveal, banned words, glossary, series names), `tests/test_part_1_steps.py` (the three kinds' submit, check, gates, capture with a fake terminal, files, reset inventory, setup gating, locking, old progress). Interface tests in `tests/frontend/ui.spec.js` with a Part 1 mock in `mock_api.py` and `mock_course.py`.

## Files and storage touched

| Location or key | Touched | Kept or cleared |
|---|---|---|
| `<project>\part-1\prompt-cold.md`, `prompt-framework.md`, `own-before.md`, `own-after.md` (new) | written by Save only | kept by Reset lesson progress; moved to backup by Reset app configuration |
| `<project>\part-1\output-cold.txt`, `output-framework.txt` (new) | written by the app from the CLI's file | moved by both resets |
| `<home>\part1\cold\`, `<home>\part1\rewrite\` (new scratch) | cleared before each Start; hold only `prompt.md` and the CLI's `output.txt` | moved by both resets |
| `<project>\.learning\progress.json` `parts.part-1` (new) | read and written | cleared by both resets (fresh file) |
| `<project>\.learning\progress.json` `lessons` | Part 1 lessons, activities, records, review items | as Part 3's |
| `<home>\pending-lessons.json` | may hold a `p1-mission` record before a project exists | merged on setup; cleared by both resets |
| `content/part-1-lessons.json`, `part-1-steps.json`, `series.json`, `glossary.json` | new or changed content | shipped in the archive |
| `kit/part1/*` | bundled, read-only | shipped; viewable in the kit viewer |
| Browser `localStorage` | none | unchanged |

## Risks / Trade-offs

- **[A participant's CLI cannot produce `output.txt` in the blind folder]** → Same troubleshooting entries as Part 3's `generate`; no example-output recovery path in this change (Open Question 8); the setup CLI working test has already shown the CLI can write a file.
- **[Pre-reveal text leaks a framework name]** → A content test scans the pre-reveal items and their sources.
- **[A self-scored form is noisy]** → That is the lesson: Part 1 teaches that gaps are visible without judgment, and Part 2 makes the judgment precise. The app records and never grades the score.
- **[A confidential real prompt in the `own` step]** → Step text says to leave out confidential details and that the text stays in the project folder; the files are on the reset lists and the project warning about OneDrive already exists.
- **[Part 1 and Part 3 content drift apart (names, outcomes)]** → The Series map name and outcome tests cover both mission maps.
- **[Time: about an hour of work against a 45-minute live session]** → Each item is a sitting that resumes; the minutes shown are the sum of the parts.

## Migration Plan

Ship after `generalize-parts` is archived. Existing projects have no Part 1 progress and load unchanged; Part 1 starts at `p1-mission`. Rollback: remove the registry entry and the `series.json` kind; `parts.part-1` in saved progress is ignored by the earlier build.

## Open Questions

Each has an assumed default (the user answered "yes" to the plan that stated them); change any before section 1 of tasks.md starts.

1. **Notes.** The app appends the rough notes under the participant's words. Default: yes.
2. **Label sets.** RTCC, RISE and "my own labels", none pre-selected. Default: yes.
3. **Stage 3 note in Part 1** (D9). Default: yes, at most 60 words.
4. **Handoff to Part 3.** Part 1's prompt does not seed `prompt-v0.md`. Default: no wiring.
5. **Setup.** All five steps need setup, including the two forms and `own`. Default: yes (same rule as Part 3).
6. **Skippable lessons.** None. Default: yes.
7. **Series map.** Parts 1 and 3 start expanded. Default: yes.
8. **Real CLI.** Stand-in only; two real sessions need the user's approval. Default: yes.
9. **`own` required.** The step must be done to finish Part 1. Default: yes.
10. **All five yes in `score`.** The text box changes to "what did your prompt include?". Default: yes.
11. **Second framework run.** Not offered; the other framework is a bundled sample after the rewrite. Default: yes.
