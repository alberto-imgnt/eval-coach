# Proposal

## Why

`docs/SERIES-INTENT.md` and `docs/STAGE3-TASK-SPEC.md` (both added 2026-11-14) now state what the whole "Evaluated Systems" series is for: a participant can judge AI work, trust it for the right reasons, and explain why. The Part 3 content built so far predates them. An audit against both documents and against the project's learning-priority order (tier 1 core knowledge, tier 2 context, tier 3 certification; `docs/IMPLEMENTATION-PLAN.md` "Learning priorities") found content that no longer matches, so it is reworked now, before more Parts are added on top of it.

## Audit findings

Gaps, in priority order.

**Tier 1, core knowledge**
- The series purpose is never stated. Nothing in the course says that the point is to judge AI work and trust it because it was checked, neither blindly trusting nor blindly distrusting it. The word "trust" appears only as "before you trust it" in the checker lessons.
- "Why it matters" is missing: AI sounds sure of itself when it is wrong, "better" is an opinion until measured, and answers change from one try to the next. The last two are taught by activities; the first is not said anywhere.
- The limits of a score are not said in plain words: a good score describes one prompt against one set of rules and does not guarantee future answers. Lesson 10 explains the pass rate but not this limit.
- Lesson 10 says what comes next, but not the Part 4 rule that makes a baseline useful: if the score did not move, the change did not help.

**Tier 2, context**
- The course map labels Parts 4 to 6 with wording that differs from the series intent table ("Better prompt versions", "A trimmed, packaged task"), and the Part names are not the series names.
- There is no bridge from the Northwind practice case to the participant's own repeating work (Part 6), although the intent says the method applies to any task that repeats, has clear requirements and can be checked by rules.

**Tier 3, certification**
- The Stage 3 note at the end of lesson 10 names three criteria ("written evaluation framework", "before and after numbers", "reusable library of prompt templates") dated "as of June 2026". `docs/STAGE3-TASK-SPEC.md` and the intent describe Stage 3 as three submitted artifacts (Prompt, Evaluations, Log) with the criteria listed under each. The note is out of line with both and is rewritten.
- The note does not say that scripts, promptfoo files and written test cases are all accepted, so the two tracks read as the only options.

**Terminology (project rule 10: "Part, not session")**
- Participant-facing content says "Session N" about 25 times: `lessons.json` (12), `steps.json` (7), `glossary.json` (4), the Northwind catch-up files (2), and three hard-coded interface strings. No test enforces the rule, which is why it drifted.

**Structure and framing (raised by the user 2026-11-14)**
- The 11 lessons follow the app's procedure (loop, runs, rules, build, choices, verify, compare, fix, baseline), each a pre-lesson for a step, not the series method (ask clearly, know what you need, turn it into rules, score, improve, keep a record). `state.COURSE` hard-codes that order.
- About 7 of the 11 lessons teach this series' own mechanics (the two chat roles, blind folder, five runs, verdict lines, checker file layout, exit codes, the four-step fixture protocol, answer-key timing, the skill file) in absolute wording ("do not", "on purpose", "this course splits"). Ten of the 33 activities test only those mechanics. This pushes tier 1 concepts underneath tier 3-style procedure, and nothing says other approaches exist, so participants can read the series' artifacts as the recommended or only correct way. `STAGE3-TASK-SPEC.md` section 2 says the approach is the participant's choice, and section 4 says the file layout is a suggestion.
- Rewording alone cannot fix this because the structure itself carries the emphasis, so the fix is structural.

**Interface audit (raised by the user 2026-11-14: "full audit and analysis of UI")**
- The sidebar is one flat numbered list that mixes concept lessons and procedure steps; nothing shows which part of the method an item covers (`renderCourseNav`).
- Interface copy uses "parts" for lessons and steps ("N of M parts complete", "Finish the earlier parts of the course first", "This part of the course is locked"), which now collides with the six series Parts.
- The header sub-brand "Session 3 · …" and the course-map title and label are hard-coded in `views.js` and `markdown.js`, against the rule that every word lives in `content/*.json`.
- The reference card (`lesson-ui.json` `reference`) presents "The loop", "The three verdicts", exit code 1 and a "Who does what" motto as the method, unlabelled.
- The glossary panel and the reference page are one flat list that mixes general ideas with this course's terms.
- Step titles carry course choices ("Generate five outputs", "Write the answer key").
- The finished screen does not say what comes next.
- Checked, no change: step panel labels and gates ("five runs" is the app's real gate and its reason moves into step text), placement UI (empty; to be replaced by separate tracks), review banner, terminal, preflight, Settings, design tokens. `docs/DESIGN.md`, the stylesheet and the design preview all name the design system "Graphite and Lime" (confirmed by the user 2026-11-14); `AGENTS.md` and `docs/IMPLEMENTATION-PLAN.md` still say "Graphite and Iris", so both are corrected in the docs task.

**Audit result (task 9.5, re-read 2026-11-14)**: every finding above maps to a changed line or a "checked, no change" entry.
- [x] Series purpose, why it matters, method line: mission body (`**The goal`, `In plain words`, `Why it matters`, `The method`).
- [x] Limits of a score, "score did not move", own-work bridge: `baseline-why` ("What a score tells you", "What comes next", "Your own work").
- [x] Part 6 is a live meeting and ideas can be brought to office hours or the AIR discussion (added 2026-11-15): `baseline-why` "Your own work".
- [x] Course map names: mission `you-are-here` block uses the intent's six Part names.
- [x] Stage 3 note and "scripts, promptfoo files and written test cases are all accepted": `baseline-why` note (Prompt, Evaluations, Log; 132 words).
- [x] "Session N": none left in `content/*.json`, the two Northwind files or `web/js` (guard test `test_part_terminology.py`).
- [x] Structure and framing: seven concept lessons; ten mechanics-only activities removed; procedure and reasons in step text; labelled "How this course does it" passages; steps outside the last lesson say "other approaches work too" without naming Stage 3, because the learning-priority spec keeps Stage 3 in the last lesson only (decided with the user 2026-11-14).
- [x] Interface: group headings, "lessons and steps" wording, Part strings from content, method-first reference card, Ideas / In this course glossary groups, step title "Collect your answers", finished screen naming Part 4. Checked, no change: step panels, placement, review banner, terminal, preflight, Settings, design tokens.
- [x] "Graphite and Iris" corrected to "Graphite and Lime" in `AGENTS.md` and the plan.
No course practice reads as the only way: the absolutist-phrase test passes for lessons, steps and glossary.

**Checked and already aligned (no change)**: the five requirements and six criteria of the Northwind example; the iteration-log fields (Prompt, Model, Runs, per-rule table, Overall, Not checked) against `STAGE3-TASK-SPEC.md` section 4; the fixture thresholds (bad fixture fails more than half of checked rules, polished fixture fails at least one); NOT CHECKED excluded from the denominator; "never edit the checker to make a failing output pass"; explain-it activities for a non-technical and a technical reader; mid-tier model recorded in the log; no Stage 3 text outside the last lesson, the glossary, steps or interface; no submission steps.

## What Changes

- **Restructure the course (11 lessons to 7), one concept per lesson in the order of the method.** New order: `mission`, `hook`, `several-runs`, step `generate`, `rules`, step `build`, `trust`, steps `fixtures` to `key`, `surprise`, steps `run`, `fix`, `baseline-why`, step `baseline`. Merges: `loop` and `generate-why` into `several-runs`; `rules`, `build-why` and `choices` into `rules`; `verify` into `trust`; `compare` and `fix-why` into `surprise`; `baseline-why` kept. The nine steps, their gates and results do not change.
- **Move the procedure into the steps.** The roles, blind folder, number of runs, checker layout, fixture order, answer-key timing and exit codes are explained in the step that does them, with the reason; lessons keep at most a short, labelled "How this course does it" passage and say other approaches exist and that Stage 3 accepts scripts, promptfoo files and written test cases. No course practice is described as the right or only way.
- **Remove ten mechanics-only activities** (and the review questions that only test them): `loop-order`, `loop-actors`, `generate-fair`, `generate-try`, `rules-demo`, `rules-anatomy`, `build-first-look`, `verify-order`, `verify-try`, `compare-exit`. All explain-it and concept activities stay under their new lesson.
- **Tolerate old saved progress** that names removed lesson ids; update the glossary, `related` and `sources` references; cap lesson length (300 words, `baseline-why` 400, mission 450).
- **Align the interface (authorized, see below).** Group headings in the course list; "lessons and steps" wording instead of "parts"; the header sub-brand and route-map strings read from content; a reference card that leads with the method and labels this course's mechanics; glossary and reference page in two groups (Ideas, In this course); concept-first step titles; a finished screen that names Part 4.
- Rewrite the mission text (no activities or questions, to keep the one-page rule from 3.45): add the series purpose, a short "why it matters", and a six-row course map that uses the intent's Part names and plain descriptions. The mission sentence keeps its user-set wording except "Session 2" becomes "Part 2".
- Add two short passages to `baseline-why`: what a score does and does not tell you, and how to use the method on your own repeating work (Part 6 fit: repeats, clear requirements, checkable by rules). Extend its "what comes next" with the "score did not move" rule.
- Rewrite the Stage 3 note in `baseline-why` around the three artifacts (Prompt, Evaluations, Log): what the participant holds after Part 3, what later Parts add, that scripts, promptfoo files and written test cases are all accepted, that file names and layout here are this course's, and that the program's own instructions decide what to submit. Drop "as of June 2026". It stays in the last lesson only, stays optional, and never gates Continue.
- Replace every "Session N" with "Part N" in `content/*.json` and in the two Northwind catch-up files. Change the three hard-coded interface strings (wording only), authorized below.
- Glossary: entries for course-specific terms begin "In this course,".
- Update `state.py` (`COURSE`), the lesson validator and the tests and harness that name lesson ids; update `tests/test_learning_priorities.py`; add guard tests for the term rule, the purpose statement, the Stage 3 structure, the absolutist-phrase ban, the labels and word budgets, and old-progress loading.
- Update `docs/IMPLEMENTATION-PLAN.md` (Stage 3 alignment map, coverage table, 3F tasks), `docs/COURSE-CONTEXT.md`, `AGENTS.md`, `docs/SPEC.md` ("Course and lessons") and `docs/PHASE3.md` so they agree with the new structure and point at the two new documents.
- Rebuild `dist/eval-coach.pyz`.

**Part 6 note (added 2026-11-15, user decision).** Part 6 is a live troubleshooting meeting where people share and discuss ideas for their submission, so the app cannot teach it. The "Your own work" passage in `baseline-why` now ends: "In Part 6 you pick your own. It is live: bring ideas to office hours or the AIR discussion. Northwind is practice only." It is information only: no activity, no Continue gate, no interface change. This is the one exception to rule 10's ban on telling people to contact someone; it is recorded in `AGENTS.md`, `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md` and `openspec/config.yaml`. A task from the participant's own work is recommended, not required; that is recorded in `docs/SERIES-INTENT.md` and `docs/COURSE-CONTEXT.md`, not in the lesson. To keep `baseline-why` within 400 words, two sentences in it were shortened with the same meaning. On 2026-11-14 the user asked for a full UI audit and authorized aligning the interface, items U1 to U6 and U8 of the audit, with this scope: (U1) group headings in the course list, one new heading element and one style rule that uses existing design tokens; (U2, U3) interface wording and the Part strings in `views.js` and `markdown.js` moved to `lesson-ui.json`; (U4) the `reference` copy in `lesson-ui.json` plus a method section in `reference.js`; (U5) two groups in the glossary panel and the reference page driven by a `kind` field; (U6) step titles and goals in `steps.json`; (U8) the finished-screen copy. Not authorized, and not touched: design tokens, colors, typography, component styles, element ids, the preflight, Settings, terminal and step panels, and every step `ui` block.

## Out of scope

- Building Parts 1, 2, 4, 5 or 6, or changing the number, order or gates of the nine steps.
- New activity types or screens, and interface elements beyond the course-list group headings and the glossary and reference groups; the evidence panel (3.41) stays not authorized.
- Any change to bundled skills (byte-identical rule 8), the answer key flow, preflight, setup, Settings, step panels or the promptfoo/Script track mechanics.
- Real-CLI runs (Phase 6 pilot) and the Mac work.
- Linking to the official Stage 3 page or any external reading (lessons cite only bundled `kit:` files).
- Teaching certification as a requirement, scoring a submission, or giving submission steps.
- The explain-it activities: they already meet tier 1 and stay as they are.

## Capabilities

### New Capabilities
- `series-intent-framing`: the course states the series purpose, why checking AI work matters, the limits of a score, and where the method applies next, using the series' Part names.
- `learning-priority-order`: content is ranked tier 1 core knowledge, tier 2 context, tier 3 certification, and the Stage 3 note follows the Prompt, Evaluations and Log structure without ever gating or replacing higher tiers.
- `part-terminology`: everything a participant reads uses "Part" for a series part and never "session".
- `method-over-mechanics`: lessons teach the transferable idea first; this course's mechanics are labelled as its own choices, never the only way, and kept short.
- `course-structure`: seven concept lessons in the order of the method, the procedure carried by the steps, mechanics-only activities removed, old progress tolerated, no dangling references.
- `interface-alignment`: the course list, reference card, glossary, step titles and finished screen present the method first and this course's mechanics as one labelled way, without clashing with Part numbers.

### Modified Capabilities
<!-- None. The existing specs cover Settings, setup and reset; no requirement in them changes. -->

## Impact

- Content: `app/eval_coach/content/lessons.json`, `steps.json`, `glossary.json`; `app/eval_coach/kit/northwind/northwind-prompt-v0.md` and `northwind-test-cases-reference.md` (comment lines only); bundled lesson files under `kit/lessons/` that no lesson or step cites after the restructure.
- Backend: `app/eval_coach/state.py` (`COURSE`, progress load and migration), `lessons.py` (validator expectations, plus `kind` on glossary terms and the group data in interface text), `engine.py` and the reference-data route only where they name a removed lesson id or pass glossary fields through.
- Interface: `app/eval_coach/web/js/views.js`, `markdown.js`, `lessons.js` (`renderCourseNav` group headings), `overlays.js` and `reference.js` (glossary groups, method section), `app.js` only if it builds the finished screen, and one new heading style rule in the existing stylesheet. Copy moves to `content/lesson-ui.json`.
- Tests: `tests/test_course.py`, `test_lessons.py`, `test_http_course.py`, `test_review.py`, `test_setup_gate.py`, `test_learning_priorities.py`, `test_content_banned_words.py`, `tests/frontend/mock_course.py`, `tests/frontend/ui.spec.js`, `e2e-work/harness/lesson-stages.js` and `run-all.js`, `tests/golden/*` where they name lesson ids or quote old wording.
- Docs: `AGENTS.md`, `docs/IMPLEMENTATION-PLAN.md`, `docs/COURSE-CONTEXT.md`, `docs/SPEC.md`, `docs/PHASE3.md`.
- Build output: `dist/eval-coach.pyz` (rebuilt, not hand-edited).
- Storage: no new key or progress field. Saved progress that names removed lesson ids is dropped on load; steps are untouched.
