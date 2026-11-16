# Design

## Context

See proposal.md for why. Current state that shapes the approach:

- All participant-facing words live in `content/*.json` (project rule). The course order is hard-coded in `state.COURSE`, and `lessons.py` requires the content's lesson ids to equal `LESSON_IDS` (derived from `COURSE`), so a lesson change is a content change plus a one-tuple change in `state.py`.
- Each of the 11 lessons is a pre-lesson for an app step. A step unlocks when the lesson immediately before it is done or skipped. Saved progress keeps per-lesson records in `progress.json` `lessons`, and review items point at question ids; a review item whose question left the content is already ignored (`docs/SPEC.md` "Review").
- The mission lesson is a one-page, no-questions lesson (task 3.45). Its mission sentence was set by the user; `tests/test_lessons.py` and `e2e-work/harness/lesson-stages.js` assert it word for word.
- The course map is a fenced `you-are-here` block in the mission body, rendered by `renderRouteMap` in `markdown.js`. Each row is `done|here|next | number | title | one line`; the renderer prepends "Session N: ".
- `tests/test_learning_priorities.py` already guards the three tiers and reads phrases from the lesson 10 Stage 3 note. Those phrases come from the old "three headline criteria".
- Steps already carry the procedure text (`why`, `instructions`, `troubleshooting`) for the blind folder, runs, fixtures and baseline in `steps.json`, so most mechanics in the lessons duplicate step text.
- Priority order used for every decision below: tier 1 (core knowledge) > tier 2 (context) > tier 3 (certification).

## Goals / Non-Goals

**Goals:**
- Lessons are organized by transferable concept in the order of the series method, with the procedure carried by the steps.
- Content states the series purpose and limits (tier 1), places the method in the series and in the participant's own work (tier 2), and aligns the Stage 3 note with the Prompt, Evaluations and Log structure (tier 3).
- This course's mechanics are labelled as this course's way and never read as the only way.
- "Part" is the only word for a series part, and a test keeps it that way.

**Non-Goals:**
- No new activity type, step, storage key or API. The nine steps and their gates are unchanged.
- No change to the skills, the checker, the baseline gates, setup, Settings or reset behavior.
- No change to design tokens, colors, typography or component styles, no change to the preflight, Settings, terminal or step panels, and no removal of the Script or promptfoo track. Step `ui` blocks are not touched.

## Decisions

**D1. Restructure by concept, not by app step.** Replace the 11 lessons with seven, in the method's order (see `specs/course-structure`). Alternative A: keep all lessons and reword (rejected by the user: the structure carries the emphasis). Alternative B: six lessons, also folding `hook` into `several-runs` (declined by the user: the hook is the hands-on proof that an AI grader is unsteady and belongs first).

**D2. Space follows the tiers.** Word caps: lesson 300, `baseline-why` 400, mission 450, labelled mechanics at most 120 words per lesson and 60 per topic. The Stage 3 note is at most 150 words, so the certification passage never outgrows the passages above it. The mission shrinks from about 540 words by dropping "How you will work" and "What to bring", which restate the steps. A content test asserts every cap.

**D3. Course map titles and lines follow the intent's Part table.** Titles: Structured prompting; Defining evaluation criteria; Running evals and baseline; Iterating with evaluation-driven development; Load-bearing audit and packaging; Your own task. Lines stay in the first person and say what the participant can do, taken from the intent's "In simple words" column. Alternative: keep the current outcome-style titles. Rejected: the intent names the Parts, and the renderer already adds "Part N:" in front, so the two read as "Part 3: Running evals and baseline".

**D4. Stage 3 note text** (heading kept so the existing test split still works): "**How this fits the Stage 3 certification.** Stage 3 asks you to hand in three things: the Prompt, the Evaluations and the Log. After this Part you hold the start of each. Your prompt file is the Prompt. Your test cases and your tested checker are the Evaluations; the polished-but-wrong test and the model name in your log show the checks are real. Iteration 0 is the first entry of the Log. The Log needs at least two rounds of improvement, and Part 4 adds them. Part 4 also confirms a score of 95% on a known-good output, and Part 5 checks that every instruction in your prompt earns its place. Scripts, promptfoo files and written test cases are all accepted forms of evaluation. This note is for orientation only. The program's own instructions decide what to submit, and nothing here is needed to finish this course." The phrase "as of June 2026" is dropped because the intent gives no date and the program's own page governs.

**D5. The term guard is a test, not a review habit.** Add one test that scans every string in `content/*.json`, the two Northwind catch-up files and the `web/js` strings that render a Part number, and fails on `\bsession\b` unless it is on a short allow list (CLI session wording in `preflight.json` and `WT_SESSION`, and the quoted "chat's history ... session ends" feedback in `lessons.json`). Alternative: extend `BANNED` in `test_content_banned_words.py`. Rejected: that pattern also scans code strings and skill files, and `session` is a legitimate word there.

**D6. Part strings read from content.** The header sub-brand and the course-map title template and `aria-label` become keys in `lesson-ui.json` (`ui.brand_sub`, `ui.map_title`, `ui.map_aria`), read through the interface text that `views.js` already receives. `renderMarkdown` has no context object, so `markdown.js` receives the two map labels as an argument or a small module setter called once when the text loads. No layout, class, id or style change. `tests/frontend/ui.spec.js` expectations on "Session 3: ..." change to match.

**D7. Source documents.** Where `docs/IMPLEMENTATION-PLAN.md`, `docs/COURSE-CONTEXT.md`, `docs/SPEC.md` or `docs/PHASE3.md` quote old wording or the old three headline criteria, they are updated in the same task group as the content. `AGENTS.md` "Where to look" gains `docs/SERIES-INTENT.md` and `docs/STAGE3-TASK-SPEC.md`. Its Status paragraph keeps saying the plan and specs still describe the app as Part 3 only, because this change does not rescope them.

**D8. Concept lessons, with a disposition for every old lesson and activity.**

| New lesson (id) | Concept and method link | Built from | Activities kept |
|---|---|---|---|
| `mission` | purpose, why it matters, the six-Part map | `mission` | none (one page) |
| `hook` | a fixed rule is steadier than an AI opinion (turn it into rules) | `hook` | `hook-compare`, `hook-explain` |
| `several-runs` | one answer proves little, so score several (score the result) | `loop` concept, `generate-why` concept | `generate-spot` |
| `rules` | turn "looks good" into a pass/fail rule; a sentence can be read two ways; what a rule cannot check (turn it into rules) | `rules`, `build-why`, `choices` | `rules-lab`, `build-sort`, `build-explain`, `build-try`, `choices-lab`, `choices-find`, `choices-explain-tech`, `choices-own` |
| `trust` | test the checker before trusting it; polished but wrong; predict before you run (score the result) | `verify` | `verify-polished`, `verify-unsure` |
| `surprise` | read a surprise; fix the spec, never the checker (improve) | `compare`, `fix-why` | `compare-sort`, `fix-scenario`, `fix-sort`, `fix-try` |
| `baseline-why` | the baseline, what a score does and does not tell you, own work, Stage 3 note (keep a record) | `baseline-why` | all six, unchanged |

Removed activities (mechanics only): `loop-order`, `loop-actors`, `generate-fair`, `generate-try`, `rules-demo`, `rules-anatomy`, `build-first-look`, `verify-order`, `verify-try`, `compare-exit`. Their review questions that test only roles, exit codes, file layout or step order are removed; the rest are re-homed. Where a removed activity carried a concept (for example "first look is not the baseline"), one sentence of it moves to the step text.

**D9. The procedure moves to the steps, with a label.** The roles, blind folder, five runs, checker layout, fixture order, answer-key timing and exit codes are written once in the step that does them, each with its reason ("so the model cannot read the tests"). The `generate` step says once that this is this course's way of working and that Stage 3 accepts scripts, promptfoo files and written test cases. Step `ui` blocks are not touched. Lessons keep at most one "How this course does it" passage. Alternative: keep the mechanics in lessons and label them. Rejected: the lessons would stay procedure-shaped.

**D10. State and validator.** `state.COURSE` becomes the new order, so `LESSON_IDS` follows. `lessons.py` keeps its activity-type rules (`cli_compare` only in `hook`); the `cli_demo` type stays supported but unused, so no activity-type code is removed. Saved progress: when `progress.json` or `pending-lessons.json` names a lesson id not in the course, that record is dropped on load. The existing migration marks lessons before the furthest completed step as skipped and migrated; it works on the new `COURSE`. A test covers a progress file written with the old ids.

**D11. Guards.** One test file (`tests/test_learning_priorities.py`, plus lesson-shape tests in `test_lessons.py`) enforces: the seven ids and order; the removed activity ids are absent; word caps; the label "How this course does it" appears only after a lesson's first concept paragraph; the absolutist phrases "the right way", "the only way", "the correct way", "the proper way", "the standard way", "this is how it is done" are absent from lessons, steps and glossary; glossary course terms start "In this course,"; no dangling glossary, `related` or `sources` reference; every bundled lesson file is cited.

**D12. Course-list groups, content-driven.** `lesson-ui.json` gets `ui.course_groups`: an ordered list of `{id, label, items: [ids]}` (items are lesson and step ids). `renderCourseNav` walks the entries in course order and inserts a heading element whenever the group changes, using the item id to find the group. No backend change: `state.course` is untouched. A test asserts every `COURSE` item (and the optional `live` step) belongs to exactly one group and that groups are contiguous in course order. The heading is a non-interactive element inside the existing list structure (a `li` with `role="presentation"` holding a heading-styled `span`, or a nested list, decided at implementation by what the Playwright accessibility check accepts); item numbering stays global. Existing CSS draws a connector between consecutive `.course-item` siblings (`.course-item + .course-item::before`) and prefixes steps with "Step · " via `::before` content; the new heading style must not break the connector and the hard-coded "Step · " string moves to a content-driven attribute only if it can be done without changing appearance, otherwise it is left (see Open Questions).

**D13. No "parts" for lessons and steps.** `lesson-ui.json` keys `locked_message`, `lesson_locked` and the sidebar progress label (`ui.journey_done`: "{done} of {total} lessons and steps done") use "lessons" and "steps". The two hard-coded `'parts complete'` and `'steps complete'` literals in `views.js` become content keys.

**D14. Reference card and glossary.** `reference` in `lesson-ui.json` gets `method_heading` and `method_line` (the six-link method), `loop_heading` becomes "How this course works" with `loop_lines` rewritten as this course's chain, `verdicts_heading` becomes "What this course's checker says", the exit-code sentence is removed, and `motto` becomes the principles from `method-over-mechanics`. `reference.js` renders the method section above the course section (a heading and a paragraph, using existing styles). `glossary.json` terms gain `kind` (`idea` or `course`); `lessons.validate_glossary` requires it; the glossary panel in `overlays.js` and the reference page render "Ideas" then "In this course", with group labels from `lesson-ui.json`. The one-page print fit is checked by the existing reference test.

**D15. Step titles and goals.** `steps.json` titles and goals drop counts, file names and tool names: `generate` becomes "Collect your answers"; other titles are reviewed one by one and changed only where they carry a course choice. Step ids and `ui` blocks are unchanged. Tests and harness code that look titles up by text are updated.

**D16. Finished screen.** `finished_body` in `lesson-ui.json` says what the participant can now do and that Part 4 changes the prompt and compares scores with the baseline.

**D17. Part 6 note (added 2026-11-15).** Part 6 is a live troubleshooting meeting where people share and discuss ideas for their submission, so the app only informs. The "Your own work" passage in `baseline-why` ends with one sentence: "In Part 6 you pick your own. It is live: bring ideas to office hours or the AIR discussion. Northwind is practice only." No activity, no Continue gate, no interface change. It is the one exception to rule 10's "never tell people to contact someone", recorded in `AGENTS.md` rule 10, `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md` (rule 11) and `openspec/config.yaml`. The contact-instruction test is unchanged (the wording avoids its phrases) and the text avoids "session" (D11 term guard). `tests/test_learning_priorities.py` asserts the sentence, so a later edit cannot drop it silently. A task from the participant's own work is recommended, not required; that is said in `docs/SERIES-INTENT.md` and `docs/COURSE-CONTEXT.md` only, because the lesson cap leaves no room for it. `baseline-why` was at 397 of 400 words, so two sentences were shortened with the same meaning (the baseline-record sentence and the known-good-output paragraph); no test asserts either sentence.

**Files touched, and whether kept or cleared**

| Location | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/content/lessons.json` | seven lessons; mission body and `win`; merged bodies; ten activities and their mechanics-only review items removed; `related` and `sources` re-pointed; "Session" to "Part" | lesson ids `mission`, `hook`, `rules`, `baseline-why` kept; `loop`, `generate-why`, `build-why`, `choices`, `verify`, `compare`, `fix-why` removed; `several-runs`, `trust`, `surprise` added |
| `app/eval_coach/content/steps.json` | procedure text per step with reasons and the one "this course's way" sentence; "Session 4" to "Part 4" (7 places) | step ids and `ui` blocks kept |
| `app/eval_coach/content/glossary.json` | "In this course," on course terms; "Session N" to "Part N" (4); `lesson` refs re-pointed | terms kept |
| `app/eval_coach/state.py` | `COURSE` order; load drops unknown lesson ids | `STEP_IDS` kept |
| `app/eval_coach/lessons.py`, `engine.py` | only where they name a removed lesson id | activity types kept |
| `app/eval_coach/kit/northwind/northwind-prompt-v0.md`, `northwind-test-cases-reference.md` | comment line wording only | bodies byte-identical |
| `app/eval_coach/kit/lessons/*` | files no lesson, step or test cites after the restructure (for example `generate/prompt.md`, `demo/*`) are listed in the tasks and removed only if unused | skills and Northwind files untouched |
| `app/eval_coach/web/js/views.js`, `markdown.js`, `lessons.js`, `overlays.js`, `reference.js` | Part strings from content; group headings; glossary groups; method section | no other behavior; element ids kept |
| `app/eval_coach/web/styles.css` | one rule for the group heading, existing tokens only | no token, color or component change |
| `app/eval_coach/content/lesson-ui.json` | `ui.course_groups`, `ui.brand_sub`, `ui.map_title`, `ui.map_aria`, `ui.journey_done`, lock messages, `reference` block, group labels, `finished_body` | other keys kept |
| `tests/test_course.py`, `test_lessons.py`, `test_http_course.py`, `test_review.py`, `test_setup_gate.py`, `test_learning_priorities.py`, `tests/frontend/mock_course.py`, `ui.spec.js`, `e2e-work/harness/lesson-stages.js`, `run-all.js` | lesson ids and wording follow the new course; new guard tests | n/a |
| `docs/*.md`, `AGENTS.md` | wording, course table, alignment map | n/a |
| `dist/eval-coach.pyz` | rebuilt, not edited | regenerated |
| `<project>\.learning\progress.json` `lessons` block, `<home>\pending-lessons.json` | records for removed lesson ids dropped on load; other keys untouched | step progress, `track`, `runs`, `results\`, `iteration-log.md`, `<home>\settings`, sealed key storage kept as is |

No storage key is added or renamed. A participant who is mid-course sees the new lessons on the next load and keeps step progress.

## Risks / Trade-offs

- [The mission is one page and may grow too long] -> Cap at 450 words (down from about 540) by dropping text that restates the steps.
- [Merged lessons exceed the word caps] -> The caps are tested; mechanics move to the steps, which have no cap but already hold that text.
- [Group headings break the sidebar's connector line, spacing or keyboard order] -> The Playwright tests cover tab order, the connector between items, both themes, the largest text size and the narrow drop-down before the change is accepted.
- [The reference card no longer fits one printed page after the method section] -> The method section is one line plus a heading; the existing one-page test runs and the card drops the exit-code sentence to make room.
- [Tests and the harness look up step titles by text] -> They are updated in the same group as the title change.
- [Glossary `kind` missing on a term] -> `validate_glossary` rejects it, so the content tests fail instead of the panel rendering an ungrouped term.
- [Old saved progress names removed lessons and blocks the course] -> Load drops unknown ids; a test loads a progress file written with the old ids; review items of removed questions are already ignored.
- [Removing activities breaks tests and the stand-in harness] -> The task groups update tests and `lesson-stages.js` in the same group as the content, and the full stand-in run is the last check.
- [Hands-on practice shrinks and "run an evaluation" (tier 1) is weakened] -> The steps are the hands-on run and are unchanged; `hook-compare`, `build-try`, `fix-try` and the labs stay.
- [Bundled skills or kit files drift from their source] -> Only comment lines in the two Northwind files change; the byte-identical test for skills runs unchanged and a new check asserts the Northwind bodies still match the golden fixtures.
- [Allow list for "session" hides a real miss] -> Keep it to named, exact strings and assert its size, so a new entry shows in review.
- [Old Stage 3 wording lives on in the plan and a stale test passes] -> The guard test reads the plan's alignment map and fails if its artifact names differ from the note's.
- [The intent changes again] -> The note defers to the program's own instructions and carries no date, so only the three artifact names are coupled to the documents.
- [The Part 6 rule 10 exception widens to other lessons] -> Every doc that states rule 10 limits the exception to the one `baseline-why` sentence, and the contact-instruction test still scans every lesson and interface string; nothing fails if a new pointer avoids the banned phrases, so review must catch it. Office hours or the AIR discussion may be renamed; the text names no dates or places.

## Open Questions

1. "Priority order set for this project" is read as the plan's learning tiers (core knowledge, then context, then certification). Assumed: yes.
2. The mission sentence was user-set wording. Assumed: only "Session 2" becomes "Part 2" (rule 10), and the tests that assert it change with it.
3. The `minutes` fields shrink with the lessons. Assumed: set each from its new word count (about 1 minute per 150 words plus activities), mission 3, `baseline-why` 6.
4. The intent's role-by-role table (five job families) is not copied in full. Assumed: `baseline-why` names three examples (client follow-up, thread summary, job description) and the Part 6 fit rule, to keep tier 2 short.
5. `STAGE3-TASK-SPEC.md` and the intent replace the June 2026 three-headline list as the reference for the note. Assumed: yes; the program's own page still governs, and the plan's alignment map is rewritten to match.
6. `tests/golden/*` and `e2e-work/harness` text that says "Session 2" is test material, not participant-facing. Assumed: update only what a test compares against the new wording; leave the rest.
7. `kit/lessons/generate/prompt.md` and `kit/lessons/demo/*` served removed activities. Assumed: delete them if no step or test uses them after the restructure; otherwise keep and cite.
8. Reviews already due for removed questions are dropped silently (existing behavior). Assumed: acceptable, because the pilot has not started and no real participant data exists.
9. The course list prefixes steps with "Step · " from CSS `content`, which is a hard-coded word outside `content/*.json`. Assumed: left as is, because moving it changes how the list is built and it carries no course mechanics; flagged for a later cleanup.
10. Group labels ("Why check AI work", "Collect answers", "Turn it into rules", "Test the checker", "Read results and improve", "Keep a record") are drafted by me. Assumed: accepted as written; they live in `lesson-ui.json` so wording changes need no code.
11. The design system is "Graphite and Lime" (confirmed by the user 2026-11-14; `DESIGN.md`, `styles.css`, `reference.css` and the preview already say so). Decision: correct the stale "Graphite and Iris" in `AGENTS.md` line 22 and `docs/IMPLEMENTATION-PLAN.md` line 7 in the docs task. No design token changes.
