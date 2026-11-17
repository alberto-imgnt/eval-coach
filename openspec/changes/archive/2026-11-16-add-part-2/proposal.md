# Proposal

## Why

Part 2 ("Defining evaluation criteria") is the bridge between the prompt a participant wrote in Part 1 and the checker they build in Part 3, but the app shows it only as a "Coming soon" row. Part 1 already ends by asking "how do you know the second answer is better?" and promises "Part 2 builds on them" (the saved prompts and outputs). Part 3 starts from a `test-cases.md` file that, until now, only the Northwind starter or an import can supply. A participant who did not attend the live Part 2 cannot learn from the app how to turn "that looks good" into criteria and pass or fail thresholds, or how to write them down. The live session (October 2026 materials: session structure, criteria worksheet, scenario card, test case template) was designed for a facilitated group in a meeting tool, with a presenter reference table shown at each block. The app has no group, presenter or shared screen, so the content is re-authored for self-paced work while keeping the knowledge, techniques and outcomes. Part 1 now proves the format for a Part with its own lessons and steps, and `generalize-parts` makes a new Part a content and registry change.

## What Changes

**The learning outcome (kept from the live session).** The participant can turn the task's requirements into at least three distinct criteria, each traced to a stated requirement and together covering both format and content; give each criterion a pass or fail threshold that a script could decide; and record them as markdown test cases. Nothing is run in Part 2 (running starts in Part 3). The participant leaves with a `test-cases.md` file for the Northwind example. The takeaway is that vague words such as "clear", "good" and "concise" become a number, a keyword or a label.

**A Part 2 course of four lessons and four steps**, in Part 3's and Part 1's format (ids in `design.md`):

| Order | Item | Kind | Carries |
|---|---|---|---|
| 1 | `p2-mission` | lesson, one page | goal, why it matters, the method, the six-Part map; answers Part 1's closing question |
| 2 | `p2-criteria` | lesson | one criterion is one thing a good answer must do; trace it to a requirement; cover format and content; no two check the same thing |
| 3 | `draft` | step, a worksheet | pick requirements, draft 3 or more criteria with a type; self-check |
| 4 | `p2-thresholds` | lesson | the script test; vague words become a number, a term or a label; two patterns (structure, required term); a proxy and what a rule cannot check; explain-it for two audiences |
| 5 | `thresholds` | step, the same worksheet | add a threshold to every criterion |
| 6 | `p2-testfile` | lesson | the test case file format; supporting lists; where the file goes next (Part 3); one optional Stage 3 note naming the Evaluations |
| 7 | `test-file` | step, an editor | build `test-cases.md` from the worksheet, edit it, and pass the file checks |
| 8 | `reference` | step, a comparison | after the file is done, see the Northwind reference criteria and classify each difference; fix the file if wanted |

**How the live session maps to the app** (what is kept, what changes because delivery changed):

| Live session | In the app |
|---|---|
| Presenter-led recap of Part 1 | The `p2-mission` page, which opens on Part 1's question; the participant's own Part 1 notes appear in `draft` when they exist, and the scenario card carries the rest |
| Scenario card handed out | The scenario card shown inside `draft` (a Friday end-of-week update, the five things you know, the rough notes) |
| Presenter demo of two criteria (one format, one content) with passing and failing samples | Worked examples in `p2-criteria` and `p2-thresholds` for those two criteria only, with a `rule_lab` to predict verdicts; the other criteria are left for the participant to find |
| Blank criteria worksheet carried through two blocks, Threshold column empty until the second | One worksheet shared by `draft` and `thresholds`: the Threshold column is introduced by the second step |
| Self-check (does each criterion trace to a requirement, do any two check the same thing) | Two required self-check ticks in `draft` |
| Script test (could a script decide this with no human judgment) | A lesson passage, a sort activity, and a required tick in `thresholds`, with non-blocking nudges that name vague words and offer three rewrites |
| Presenter reference tables (criteria, thresholds, banned list) shown during the blocks | Held until after the file is done: the `reference` step shows the Northwind reference, and the participant classifies each criterion against their own |
| Blank markdown template filled in solo, saved as the input for Part 3 | The `test-file` step builds the template from the worksheet; the participant edits and saves it in the project folder |
| Partner review (swap criteria, flag vague, duplicate or format-only) | The `reference` classification ("had it", "missed it", "different but works", "mine was vague") and the file checks |
| Banned list written by the presenter | The participant writes their own list; none is pre-filled. The Northwind list is shown only in `reference` |
| Open discussion, timing, slides, room and logistics | Not carried over (AGENTS.md rule 10) |

**Engine and interface support (builds on `generalize-parts`, `add-part-1` and `read-ahead-always`, all archived).**
- Three new content-driven step kinds in a new module, registered in `state.STEP_KINDS` the way Part 1's are: `criteria_table` (the shared worksheet for `draft` and `thresholds`), `test_file` (assemble, edit and check `test-cases.md`) and `reveal_compare` (the `reference` step).
- Part 2 content files, bundled kit files, glossary entries, a `series.json` change from `soon` to `course` for Part 2, and a Part 2 `ui` block (header, route map, course groups, finished screen).
- Project files under `<project>\part-2\` and the reset inventory updated. No scratch folder under `<home>`: Part 2 starts no CLI.
- The checks reuse the existing `import_checks` detection (3 or more criteria, a content criterion, missing threshold, vague words) with Part 2's own wording, because the import messages tell the participant to "press Check my files". `import_checks` and Part 3 stay unchanged.

**Authorizations.**
- Interface change (AGENTS.md rule 11). Recorded as given: the user asked to propose this change on 2026-11-16, in reply to a plan that listed items U6 to U8 and said they would be treated as authorized. If that reading is wrong, say so before the apply workflow starts. Scope: (U6) a criteria worksheet panel: rows of Requirement, Criterion, Type (and Threshold in the second step) with add and remove, a "Use a requirement from the card" menu, and the two self-check ticks; (U7) a test-file panel: the file in an editor with Save, "Build my file from my worksheet" with a confirm before replacing text, and a findings list; (U8) a reference panel: the reference criteria beside the participant's own, one classification radio group per criterion, and the file editor again. Existing design tokens and components (`radio-card`, `seg`, `mono-block`) only. The Part 2 row on the Series map reuses the existing course-row component and the per-Part `ui` mechanism that Part 1 introduced (no new component). Not authorized: any other layout, styling, component or copy change, and any change to Part 1's or Part 3's screens.
- Stage 3 wording (AGENTS.md "Stage 3 note in one place", `learning-priority-order`): one short optional note in the last lesson of Part 2 (design D9). If not wanted, drop D9 and the matching requirement.

## Capabilities

### New Capabilities
- `part-2-course`: what Part 2 teaches and in what order: the mission page, the criteria, thresholds and test-file lessons; the discovery-before-reveal rule for the reference criteria; the format and content rule, the script test and the two threshold patterns; the explain-it activities; the Stage 3 note; what carries over from the live session.
- `part-2-exercise-steps`: the four steps (draft, thresholds, test-file, reference): what the participant does, the gates, the files, the file checks and their wording, the optional read of the participant's own Part 1 work, and how the worksheet, file and reference panels look and behave.

### Modified Capabilities
- `series-map`: Part 2 becomes a Part with content; only Parts 4 and 5 stay "Coming soon"; Parts 1, 2 and 3 start expanded; names and outcomes agree across all three mission maps.
- `course-structure`: the length caps cover `p2-mission` (first lesson) and `p2-testfile` (last lesson).
- `learning-priority-order`: the Stage 3 note may also sit in the last lesson of Part 2, where it names the Evaluations, and the guard test covers it.
- `part-terminology`: Part strings in `part-steps.js` and the new panels come from content (the Part 2 header reads "Part 2 · Defining evaluation criteria").
- `progress-reset`: the participant's worksheet and test cases in `part-2\` stay when only lesson progress is reset.
- `configuration-reset`: the same files move with the starting files.

## Impact

- New: `content/part-2-lessons.json`, `content/part-2-steps.json`, `kit/part2/*` (the scenario card and the file template), `app/eval_coach/criteria_steps.py` (handlers and gates for the three kinds), `web/js/criteria-steps.js`, tests `tests/test_part_2_content.py`, `tests/test_part_2_steps.py`, `tests/frontend/part2.spec.js`.
- Changed: `content/series.json` (Part 2 `kind` and `ui`), `content/glossary.json` (Part 2 entries), `state.py` (the Part 2 registry entry and default step records), `engine.py` (kind registration and the read of Part 1 progress, nothing else), `project.py` and `reset.py` (the `part-2\` files), `web/js/panels.js` and `app.js` (register the new panels only), `web/styles.css`, `tests/frontend/mock_api.py` and `mock_course.py`, `e2e-work/harness/` (a Part 2 stage; stand-in only).
- Docs and governing files: `docs/SPEC.md` (layout, storage, reset inventory, a "Part 2" section), `docs/IMPLEMENTATION-PLAN.md` (phase P2 and its task table, the coverage and Stage 3 alignment tables), `docs/COURSE-CONTEXT.md` (the Part 2 coverage row and the banned-words open item), `docs/PHASE3.md` (a pointer), `AGENTS.md` Status (including the stale "wording for review before archive" note for Part 1).
- `dist/eval-coach.pyz` must be rebuilt.
- No new route, no new dependency, no network use, no CLI use, and no real-CLI budget needed.

## Out of scope

- Parts 4, 5 and 6; any change to Part 1's or Part 3's lessons, steps, gates or screens.
- Running, scoring or grading a criterion against any output (that is Part 3), and any automatic judgment of the participant's wording beyond the file checks listed in `design.md`.
- Wiring the Part 2 file into Part 3's setup (a starter that loads it). The file is a normal file in the project; Part 3's existing "My own files" import accepts it for a new project.
- Teaching the checker, fixtures, baseline or the load-bearing audit; the bad-output test is introduced here and developed in Part 3.
- A task of the participant's own as the working example. Northwind is the only example and is never a submission option; one optional reflection points to the participant's own repeating work.
- Changes to setup, preflight, tracks, the reference card or Settings; changing the glossary entries "Criterion" and "Threshold" that point to Part 3's `rules` lesson.
- Slide, timing, partner-swap and facilitation logistics from the live materials.
