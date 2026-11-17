# Design

## Context

See `proposal.md` for the outcome, the live-session mapping and the authorizations. Built on `generalize-parts` (the Part registry, per-Part progress under `parts.<id>`, unique ids, the step `kind` hook), `add-part-1` (the first Part with its own steps) and `read-ahead-always` (locked items preview at any time). Observed in the repository on 2026-11-16:

- `state.PARTS` is `(PART_3, PART_1)`. A `Part` holds its course, content files, `progress_key` and `new_steps` (default step records). `STEP_KINDS` is filled by `part_steps.py` on import (`store.STEP_KINDS.setdefault`). The engine calls a kind's `detail`, `submit`, `check` and the like as `method(engine, step, ...)` (`engine._kind_call`).
- `part_steps.py` is Part 1's module: three kinds, `_base` (the shared step view), `_finish` (record a gate result, mark done) and `_body`/`_line` (input cleaning). Its panels are in `web/js/part-steps.js`, registered into `PANELS` in `panels.js` by step id.
- A locked step opens through `_step_preview`, which never calls a kind's `detail` and reads no participant file. A done step refuses `submit`.
- `import_checks.analyze(prompt_text, cases_text)` accepts no prompt (`None`) and returns findings with stable `code`s; its messages are import wording ("press Check my files again") and are formatted inside `analyze`. `parsers.parse_test_cases` and `import_checks.criterion_types`, `vague_words` and `is_content_criterion` are what Part 3's import already trusts.
- `kit/northwind/northwind-test-cases-reference.md` holds the six reference criteria and the Northwind lists. Part 3 cites it and the Northwind starter writes it into the project, so it cannot be hidden.
- Content rules enforced by tests: equal option word counts, word caps, `kit:`-only citations, banned words, "Part, not session", Stage 3 wording in one place, no retired ids (including `compare`), glossary kinds, Series map names and outcomes equal in every mission map.
- The live-session sources (Session 2 structure, worksheet, scenario card, template) are read-only on OneDrive; their facilitator and meeting-tool wording cannot be carried over (AGENTS.md rules 7, 10 and 12).

## Goals / Non-Goals

**Goals:**
- A participant with no presenter reaches the live session's outcomes: at least three distinct criteria traced to requirements and covering format and content, a threshold a script could decide for each, and a `test-cases.md` that Part 3 reads.
- The reference criteria stay out of reach until the participant has drafted their own, as far as the app can arrange it.
- Every decision is made from files and the participant's own answers. No CLI, checker or model is involved.

**Non-Goals:** the proposal's "Out of scope" list, plus: no new route, no new storage mechanism, no change to `import_checks.py` or to any Part 1 or Part 3 behavior, and no automatic judgment of the participant's wording beyond the checks in D5.

## Decisions

**D1. Part 2 registry entry and ids.**
`part-2`; `mission = p2-mission`; `progress_key = part-2`. Course, in order: lesson `p2-mission`, lesson `p2-criteria`, step `draft`, lesson `p2-thresholds`, step `thresholds`, lesson `p2-testfile`, step `test-file`, step `reference`. `PARTS` becomes `(PART_3, PART_1, PART_2)`; Part 3 stays first because its steps file holds the shared messages. None of these ids is used by Part 1 or Part 3 or is a retired id (`compare` is why the last step is `reference`). Activity and review ids use the prefixes `crit-`, `thr-`, `tf-` and `r-crit-`, `r-thr-`, `r-tf-`. Default step records (`new_part_2_steps`), which hold only what the participant answered:
`draft {"checks": {"traces": false, "distinct": false}, "last_check": null}`, `thresholds {"checks": {"script_test": false}, "last_check": null}`, `test-file {"last_check": null}`, `reference {"choices": {}, "last_check": null}`.
Course groups (in the Part's `series.json` `ui`): "Know what you need" (`p2-mission`, `p2-criteria`, `draft`), "Turn it into rules" (`p2-thresholds`, `thresholds`), "Write it down" (`p2-testfile`, `test-file`) and "Compare with an example" (`reference`).

**D2. Lesson content outline.**
The words are written in the apply tasks and reviewed by the user; this fixes the shape. Lessons after the mission open "In the method." (know what you need, or turn it into rules), "The idea.", short passages and one "How this course does it". No lesson is skippable, and none blocks Continue. Titles say what the lesson gives the participant: "From requirements to criteria", "Rules a script could check", "Writing your rules down".

| Lesson | Concept | Activities | Retrieval | Minutes |
|---|---|---|---|---|
| `p2-mission` | purpose, why checking matters, the method, the six-Part map, nothing is run here; answers Part 1's question | none | none | 3 |
| `p2-criteria` | a criterion is one thing a good answer must do; trace it; format and content; no duplicates; the polished-but-wrong test introduced | `crit-sort` (sort example criteria into format and content), `crit-trace` (choice: which criterion traces to no requirement), `crit-same` (choice: two criteria that check one thing) | `r-crit-1`, `r-crit-2` | 6 |
| `p2-thresholds` | the script test; vague word to number, term or label; structure and required-term patterns; a proxy and "Not checked" | `thr-sort` (sort thresholds into "a script can decide" and "tighten it"), `thr-lab` (a `rule_lab` over three samples: one good, one polished and wrong, one too long, with the length and label rules), `thr-pattern` (choice), `thr-explain-tech` (choice), `thr-explain-plain` (reflection, 20 words) | `r-thr-1` to `r-thr-3` | 8 |
| `p2-testfile` | the file's parts; supporting lists live in the file; the file is the input to Part 3; why rules come before judging | `tf-sort` (sort pieces into the file's sections), `tf-why` (choice), `tf-own` (optional reflection, 8 words: a task of your own that repeats) | `r-tf-1`, `r-tf-2` | 5 |

The worked examples (the length criterion and the blocker criterion, with a passing and a failing text each) and the blank template are bundled kit files (D8). Caps: 450 words for `p2-mission`, 400 for `p2-testfile` (it carries the lead-in to Part 3 and the optional Stage 3 note), 300 for the others. The `rule_lab` rule kinds are the fixed list (`word_count_under`, `all_labels`, and so on); no participant code runs.

**D3. Three step kinds, content-driven, in one new module.**
`criteria_steps.py` holds one handler per kind, registered the same way as Part 1's (the import sits beside `part_steps` in the engine). Routes stay the existing `/api/step/*`. Part 1's module is not edited.

| Kind | Steps | `submit` body | `check` gate | `detail` data |
|---|---|---|---|---|
| `criteria_table` | `draft`, `thresholds` | `{"rows"?:[{"requirement","criterion","type","threshold"}],"checks"?:{id:bool}}`. `rows` is the explicit Save and replaces `part-2\worksheet.json`; `checks` records the ticks as the participant works (stored under `checks` in the step's record, in both steps). In `thresholds` only `threshold` may change; adding, removing and editing the other fields is `draft`'s | `draft`: 3 or more rows, each with requirement, criterion and a type; one or more of type content; no two equal criteria (ignoring spacing and capitals); both ticks. `thresholds`: every row has a threshold (a "Not checked:" line counts); the script-test tick | `scenario` (draft), `rows`, `columns`, `requirements` (the card), `checks`, vague-word notes per row (`thresholds`), `part1` (draft, D6) |
| `test_file` | `test-file` | `{"text"?,"build"?:true,"replace"?:true}`. `text` is Save and writes `part-2\test-cases.md`; `build` composes the file from the worksheet (D4); a saved non-blank file is replaced only with `replace` (`confirm_replace`) | a saved file with a non-empty test input, 3 or more criteria and one or more about content (D5) | `text`, `saved`, `has_worksheet`, `findings` (`blocking`, `notes`), `criteria` |
| `reveal_compare` | `reference` | `{"choices"?:{reference id:option id},"text"?}`; `text` goes through the same file save as `test-file` | every reference criterion has one of the four options | `reference` (the criteria, types, thresholds and the Northwind lists), `mine`, `options`, `choices`, the same file fields as `test-file` |

Limits mirror Part 1's: text up to 50 000 characters, single-line fields cleaned to one plain line, at most 12 rows. A done step refuses `submit` (`step_done`), as in Part 1; the `reference` step's editor is the one place a file can still be saved after `test-file` is done. No handler starts a CLI or runs anything (`cli` is null; `start` and `send` are `not_supported`).
*Alternatives:* two kinds for the worksheet (`draft` and `thresholds`) were rejected because the source carries one worksheet through both blocks and the rows must be the same; ten bespoke handlers like Part 3 were rejected as in `add-part-1`.

**D4. The file the app builds.**
`build` writes the layout Part 3's parser reads: `# Test cases: Northwind end-of-week update`, `## Test input` (the seven Northwind rough notes, read from the existing `kit/part1/rough-notes.txt` so the notes exist once), `## Criteria` with `### C<n>: <criterion trimmed to a short name>` and `- Requirement:`, `- Type: Format|Content`, `- Threshold:` lines in row order, and an empty `## Supporting lists` with one placeholder line from the live template. Everything under a criterion is the participant's own text, unchanged. The file is written with LF line endings; the parser reads both. *Alternative:* ask the participant to paste the notes and type the layout. Rejected: it is a copy chore for non-technical readers and invites a layout the parser cannot read.

**D5. File checks reuse the detection, not the wording.**
`import_checks.analyze(None, text)` supplies the finding codes: `no_criteria`, `few_criteria` and `no_content_criterion` block; `missing_threshold` and `vague` are notes. Part 2 writes its own message for each code in `content/part-2-steps.json` (`test-file.findings`), filled from the parsed criteria and `import_checks.vague_words`, and each ends with what to do next. Added in `criteria_steps.py`, never in `import_checks`: an empty test input blocks; a criterion with no Requirement line is a note; a threshold that names a list ("banned", "required" or "list") with no entry under Supporting lists is a note. Notes never block. The tracing check that needs a prompt is not used. *Alternative:* parameterize the import messages. Rejected: it edits Part 3's import module and its content for a different screen's wording.

**D6. The optional read of Part 1.**
`draft.detail` reads the participant's Part 1 `score` record (the five yes or no marks and the gap) through `engine._progress_of(part_1, create=False)` and the saved answers, and returns them as plain text labelled as theirs; it returns nothing when Part 1 has no such record. It writes nothing and never gates. The five requirements are kept in Part 2's `draft` scenario with the same ids and text as Part 1's `cold` scenario (a content test asserts equality), so the marks line up without Part 2 reading Part 1's content at run time.

**D7. The reveal.**
`reveal_compare.detail` parses `kit/northwind/northwind-test-cases-reference.md` (`parse_test_cases`, `criterion_types`, the supporting lists section) and returns it only when `test-file` is in the Part's `done` list; before that it returns an empty `reference`, and a locked step never reaches `detail` at all. The four options (ids `had`, `missed`, `different`, `vague`) have equal-length labels. The kit file is not gated: Part 3 cites it and the Northwind starter writes it into the project, so Part 2 does not claim a seal. What is guaranteed is the discovery order inside Part 2, and a test that no Part 2 lesson, step text, glossary entry, interface string or API response before the gate holds a reference criterion beyond the two worked examples, a reference threshold or a Northwind list word. *Alternative:* hide a new copy under `HIDDEN_KIT_NAMES` or `GATED_KIT`. Rejected: a second copy can drift from the byte-identical Northwind file, and gating the original breaks Part 3.

**D8. Kit files, glossary and series.**
`kit/part2/`: `worked-examples.md` (the sample passing update, the length and blocker criteria with a passing and a failing text each; no other criterion) and `test-case-template.md` (the blank template). Each is cited by a lesson or step, and the content test lists them. `content/glossary.json` gains Test case, Format check, Content check, Supporting list and Script test (kind `idea`) and Worksheet (kind `course`, "In this course," first); the existing Criterion and Threshold entries keep pointing to `rules`. `series.json` flips Part 2 to `course` and adds its `ui`: `brand_sub` "Part 2 · Defining evaluation criteria", `map_title`, `map_aria`, `course_groups` (D1) and the finished text.

**D9. The Stage 3 note.**
One optional note of at most 60 words ends `p2-testfile`: the Stage 3 Evaluations need at least three distinct rules with clear pass or fail limits; scripts, promptfoo files and written test cases are all accepted; the program's own instructions decide what to submit; nothing here is needed to finish the Part. `tests/test_learning_priorities.py` gains the Part 2 case (names the Evaluations; appears nowhere else in Part 2).

**D10. Storage, resets and the project folder.**
`project.py` gains `PART2_DIR = "part-2"` and the two file names, with `Paths` helpers beside Part 1's. `reset.py` lists both files under `part-2\`: kept by Reset lesson progress, moved by Reset app configuration (like `prompt-v0.md` and Part 1's prompts); no outputs list, since Part 2 produces none and starts no CLI, so there is no `<home>` scratch folder. `tests/test_reset.py` fails on any unlisted file. After a progress reset the saved worksheet and file remain and `draft` shows them; the participant's work is never overwritten.

**D11. Interface (authorized in `proposal.md`).**
New code lives in `web/js/criteria-steps.js` and is spread into `PANELS` by step id (`draft`, `thresholds`, `test-file`, `reference`). The field helpers it shares with Part 1's panels (`textField`, `saveButton`, `savedLine`, draft handling) are exported from `part-steps.js` with no behavior change. U6: a worksheet of rows (requirement text box with a "Use a requirement from the card" menu, criterion box, a type choice, a threshold box in the second step), add and remove, two ticks, Save. U7: the file in an editor with Save, "Build my file from my worksheet" (a confirm before replacing text) and a findings list (blocking items first, notes after). U8: the reference criteria stacked beside the participant's own, a labelled group of four `radio-card` choices per criterion, and the same editor. Rows stack their fields in the `mid` and `narrow` layouts. Existing tokens only; free text goes into text nodes only. `app.js`'s default expansion list gains `part-2`. `part-steps.js`, `panels.js` and `app.js` change only where they register or read the active Part.

**D12. Tests and stand-in.**
Backend: `tests/test_part_2_content.py` (lesson shape, caps, option parity, kit files, citation boundaries, equal requirement text with Part 1, no reference leakage in content, banned words, glossary, series names in all three mission maps, the Stage 3 note) and `tests/test_part_2_steps.py` (course order and locking, the three kinds' submit, gates and findings, files, previews, setup gating, the reveal gate over the HTTP routes, the read of Part 1 with and without progress, old progress, resets). Existing content, series, parts and reset tests gain Part 2. Interface: `tests/frontend/part2.spec.js` against the real app (`real_server.py`) with Part 2 added to the mocks. Harness: a Part 2 stage in `e2e-work/harness/lesson-stages.js` and `run.js` that works the lessons, fills the worksheet, builds and saves the file, classifies the reference and finishes; it needs no CLI (the stand-in is not involved) but keeps the `E2E_PROFILE=standin` refusal like the other lesson stages.

## Files and storage touched

| Location or key | Touched | Kept or cleared |
|---|---|---|
| `<project>\part-2\worksheet.json` (new) | written by Save in `draft` and `thresholds` | kept by Reset lesson progress; moved to backup by Reset app configuration |
| `<project>\part-2\test-cases.md` (new) | written by Save or a confirmed Build in `test-file` and `reference` | kept by Reset lesson progress; moved to backup by Reset app configuration |
| `<project>\.learning\progress.json` `parts.part-2` (new) | ticks, reference choices, last gate results; never a reference text or worksheet text | cleared by both resets (a fresh file is written) |
| `<project>\.learning\progress.json` `lessons` | Part 2 lessons, activities, records, review items | as Parts 1 and 3 |
| `<project>\.learning\progress.json` `parts.part-1` | read only, by `draft` | untouched |
| `<project>\part-1\` files | not read or written | untouched |
| `<home>\pending-lessons.json` | may hold a `p2-mission` record before a project exists | merged on setup; cleared by both resets |
| `<home>\` scratch folders, `preflight.json`, sealed key | not used | untouched |
| `content/part-2-lessons.json`, `part-2-steps.json`, `series.json`, `glossary.json` | new or changed content | shipped in the archive |
| `kit/part2/*` | bundled, read-only | shipped; viewable in the kit viewer |
| `kit/northwind/northwind-test-cases-reference.md`, `kit/part1/rough-notes.txt` | read only | untouched |
| Browser `localStorage` | none | unchanged |

## Risks / Trade-offs

- **[The reference is readable outside the step]** The Northwind file is in Part 3's kit and, with the Northwind starter, in the project folder → Part 2 says only that the reference comes after the file, cites it nowhere, and guards its own content and responses with tests. It is a discovery order, not a seal, and the docs say so.
- **[The content heuristic rejects a good file]** `is_content_criterion` is deliberately generous but can miss unusual wording → the finding gives an example threshold and the participant's own `Type: Content` line is trusted, as in Part 3's import.
- **[A vague nudge discourages "Not checked"]** → The nudge offers "Not checked:" with a reason as a fourth choice, and the file keeps it, so the honest answer stays available.
- **[Part 1 progress changes shape]** The `draft` read depends on Part 1's `score` record → it reads defensively, and shows nothing when a key is missing.
- **[The participant edits the file outside the app]** The app rereads it at every check and never replaces it without Save or a confirmed Build.
- **[Word caps are tight for the last lesson]** `p2-testfile` carries a file layout, a hand-off and a note in 400 words → the layout example lives in the bundled template, and the lesson cites it.
- **[A second Part's panels share helpers with Part 1]** → Only exports are added to `part-steps.js`; `tests/frontend/part1.spec.js` must pass unchanged.

## Migration Plan

Ship after `add-part-1` and `read-ahead-always` (both archived). Existing projects have no Part 2 progress and load unchanged; Part 2 starts at `p2-mission`. Rollback: remove the registry entry and the `series.json` kind; `parts.part-2` in saved progress is ignored by the earlier build, and `part-2\` files are ordinary participant files.

## Open Questions

Each has an assumed default; change any before section 1 of `tasks.md` starts.

1. **Interface authorization.** U6 to U8 are recorded as authorized by the request to propose this change. Default: yes; say so if not.
2. **Editing in `reference`.** The same file editor appears after the reveal, and a saved change reruns the checks without affecting the gate. Default: yes.
3. **Reading Part 1.** `draft` shows the participant's Part 1 marks and gap when they exist. Default: yes, read-only and optional.
4. **Vague words.** A non-blocking nudge with "Not checked:" as an option. Default: yes.
5. **Missing supporting list.** A note, not a block. Default: yes.
6. **Series map.** Parts 1, 2 and 3 start expanded. Default: yes.
7. **Glossary.** "Criterion" and "Threshold" keep pointing to Part 3's `rules`. Default: yes.
8. **`thresholds` edits.** Only the threshold column is editable there; criteria are changed in `draft` before it, or in the file editor after. Default: yes.
9. **Wording review.** The lessons, steps and the finished screen are for you to review before the change is archived, as for Part 1. Default: yes.
10. **Step id.** The last step's id is `reference` and its title is "Compare with an example", so it is not confused with the reference card. Default: yes.
11. **Hand-off.** No Part 3 starter loads the Part 2 file; the finished screen says the file is in `part-2\` and that Part 3's "My own files" import accepts it for a new project. Default: yes.
12. **Real CLI.** None is involved, so no budget is used. Default: yes.
