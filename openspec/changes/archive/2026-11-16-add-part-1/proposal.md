# Proposal

## Why

Part 1 ("Structured prompting") is the start of the series and the source of the prompt every later Part builds on, but the app shows it only as a "Coming soon" row. A participant who has not attended a live Part 1 cannot get its knowledge or its outcomes from the app. The live session (October 2026 materials: agenda, facilitator guide, materials and deck) was designed for a facilitated group in a meeting tool; the app has no group, no facilitator and no shared screen, so the content must be re-authored for self-paced, hands-on work with the participant's own AI CLI while keeping the knowledge, techniques and learning outcomes. Part 3 already proves the format (concept lessons plus procedural steps, discovery before theory, tier-ranked content), so Part 1 follows it.

## What Changes

**The learning outcome (kept from the live session).** The participant understands why a framework gets better results, knows existing frameworks are samples and that they can build their own, and can name four benefits: completeness, better first results, easier fixes and repeatability. They leave with a before and after prompt pair with both outputs, and one real prompt from their own work rewritten with a framework. The takeaway is "Give the AI what it needs. Use a framework, or build your own." It does not recommend a framework, teach every letter, or measure quality.

**The method (kept): discovery before theory.** Write a cold prompt in your own words, score the output against five things you knew but never said, notice every gap was something the AI could not have known, sort the gaps into five plain-language kinds of missing information, then learn that those kinds have names (frameworks). Rewrite with a framework's labels in a new chat, run once, score again, compare.

**A Part 1 course of four lessons and five steps**, in Part 3's format (ids in `design.md`):

| Order | Item | Kind | Carries |
|---|---|---|---|
| 1 | `p1-mission` | lesson, one page | goal, why it matters, the method, the six-Part map |
| 2 | `cold` | step, runs the CLI | write a prompt in your own words; one run, no coaching |
| 3 | `score` | step, a form | hand-score against five requirements; name one gap; was it in my prompt? |
| 4 | `p1-gaps` | lesson | what your first prompt left out: every gap was something the AI could not know; five common kinds of missing information |
| 5 | `p1-frameworks` | lesson | the reveal: frameworks are ready-made labels for kinds of information; our five are an example, so build your own when needed; samples, not recommendations |
| 6 | `rewrite` | step, runs the CLI | rewrite with a framework's labels (or your own), new chat, one run |
| 7 | `rescore` | step, a form | score again, compare, say what the labels made you add |
| 8 | `p1-benefits` | lesson | four benefits, the takeaway, explain-it activities, what comes next |
| 9 | `own` | step, a form | the homework: one real prompt of your own, before and after |

**How the live session maps to the app** (what is kept, what changes because delivery changed):

| Live session | In the app |
|---|---|
| Facilitator frames the session, says "no right answers yet" | `p1-mission` and the `cold` step text, with no hints about frameworks or kinds of information |
| Scenario card pasted in meeting chat | The scenario card shown inside the `cold` step; the rough notes are added by the app under the participant's words |
| Copilot Chat in Teams, base licence | The participant's own CLI, in a folder that holds only the prompt, so the answer depends only on the prompt (the same reason the live session used a tool with no access to work data) |
| "Run it once, no second tries"; "reply: go ahead with your best guess" | Start, Send, one captured run per step; the best-guess line is a troubleshooting entry |
| Score out of five by typing a number; one-gap chat waterfall; facilitator reads gaps aloud and asks "was any of that in your prompt?" | The `score` form (five yes or no answers, one gap, "was it in my prompt?") and typical gaps from the bundled examples, sorted in `p1-gaps`, so the participant still sees what other people typically notice |
| Gaps that are not missing context are set aside for Part 2 | A set-aside group in the sort, with a plain line that invented details, quality and run-to-run variation belong to evaluation |
| Bucket slide, typing a number to sort | A sort activity with feedback; the five kinds are numbered |
| Reveal slide: RTCC and RISE mapped on, "others exist" | `p1-frameworks`: the mapping, the partial fits of kinds 4 and 5, other frameworks (CO-STAR, RISEN), and "or build your own" |
| Two breakout groups, one per framework; groups compare overlap | The participant picks one of two sample frameworks or their own labels; after `rescore`, `p1-benefits` shows the other framework's prompt for the same task (bundled samples, shown only after the rewrite) so the overlap, and that the benefit comes from structure, is still seen |
| Volunteers share both prompts; compare questions | `rescore` shows both prompts, outputs and scores side by side and asks the two compare questions in writing |
| Benefits named as they come up; benefits slide | `p1-benefits` ties each benefit to what the participant saw, with activities |
| Homework: bring one real prompt rewritten | The `own` step |
| Open question leading to the next session | The close of `p1-benefits`: how do you know the second answer is better? |
| Slide, timing, room and Q&A logistics | Not carried over (AGENTS.md rule 10) |

**Engine and interface support (builds on change `generalize-parts`).**
- Three new content-driven step kinds: `write_and_run` (a prompt editor plus a blind CLI run, for `cold` and `rewrite`), `score_form` (yes or no rows plus text fields, with a side-by-side compare for `rescore`) and `write_pair` (two text boxes plus a note, for `own`). Gates read files and the participant's own answers; the app never parses the CLI's output.
- Part 1 content files, bundled kit files (scenario notes, typical gaps, the reveal table, two sample framework prompts), glossary entries, and a `series.json` change from `soon` to `course` for Part 1.
- Per-Part interface strings (header sub-brand, route-map title, course groups, finished screen) read from the active Part's content.
- Project files under `<project>\part-1\`, scratch folders under `<home>\part1\`, and the reset inventory updated.

**Authorizations.**
- Interface change (AGENTS.md rule 11), authorized by the user on 2026-11-15 ("yes" to the plan that listed items U1 to U5, with the instruction to use the live session documents as reference and to account for the different delivery method). Scope: (U1) the page reads and sends the active Part, and the header, route map, course groups and finished screen take their words from that Part's content; (U2) a prompt editor panel with Save and an "Insert labels" button; (U3) a score form panel (five yes or no rows, text fields, a computed score); (U4) a side-by-side compare view of two prompts, two outputs and two scores, reusing the compare view's pattern; (U5) the Part 1 row on the Series map using the existing course-row component. Existing design tokens only. Not authorized: any other layout, styling, component or copy change, and any change to Part 3's screens.
- Stage 3 wording (AGENTS.md "Stage 3 note in one place"): one short optional note in the last lesson of Part 1 (design D9). The user's "yes" accepted the default; if not wanted, drop D9 and the matching requirement.

## Capabilities

### New Capabilities
- `part-1-course`: what Part 1 teaches and in what order: the mission page, the gaps and frameworks lessons, the benefits lesson and the Stage 3 note; the discovery-before-theory rule; the five example kinds of information, the sample frameworks and their partial fit; the four benefits; what carries over from the live session.
- `part-1-exercise-steps`: the five steps (cold run, score, rewrite, score again and compare, own prompt): what the participant does, the gates, the files, privacy, and how the three step kinds look and behave.

### Modified Capabilities
- `series-map`: Part 1 becomes a Part with content; Parts 2, 4 and 5 stay "Coming soon"; the expand, open and progress rows apply to every Part with content.
- `course-structure`: the "seven lessons" requirement names Part 3's course, and the length caps cover each Part's first and last lesson.
- `learning-priority-order`: Stage 3 content appears in the last lesson of a Part that has a note, no longer "the last lesson" of the app.
- `part-terminology`: Part-number strings may come from a Part's own content as well as `lesson-ui.json`.
- `progress-reset`: Part 1's prompts and own-work files stay when only lesson progress is reset; its outputs move.
- `configuration-reset`: Part 1's prompts and own-work files move with the starting files.

## Impact

- New: `content/part-1-lessons.json`, `content/part-1-steps.json`, `kit/part1/*` (scenario notes, typical gaps, reveal table, two sample prompts), `web/js/part-steps.js`, `app/eval_coach/part_steps.py` (handlers and gates for the three kinds), tests `tests/test_part_1_content.py`, `tests/test_part_1_steps.py`, interface tests in `tests/frontend/ui.spec.js`.
- Changed: `content/series.json` (Part 1 `kind`, per-Part `ui`), `content/glossary.json` (Part 1 entries), `state.py` registry (Part 1 entry), `engine.py` (kind dispatch only), `reset.py` (inventory), `web/js/app.js`, `web/js/views.js`, `web/js/series.js`, `web/js/panels.js` (active Part), `web/styles.css`, `tests/frontend/mock_api.py`, `e2e-work/harness/` (`fake_cli.py` and stages for Part 1, stand-in only).
- Docs and governing files: `docs/SPEC.md` (a Part 1 section, layout, storage, reset inventory), `docs/IMPLEMENTATION-PLAN.md` (phase P1), `docs/COURSE-CONTEXT.md` (coverage column: Part 1 built; Part 1 section notes how the app delivers it), `docs/PHASE3.md` pointer, AGENTS.md Status.
- `dist/eval-coach.pyz` must be rebuilt.
- Depends on `generalize-parts` being applied first.

## Out of scope

- Parts 2, 4, 5 and 6; any change to Part 3's lessons, steps, gates or screens (apart from Part 3's text that now says Part 1 exists: none is needed).
- Recommending, choosing for the participant, or grading a framework; teaching what each letter means in depth; measuring prompt quality or any automatic judging of prompt or output (that is Part 2 onward).
- Wiring Part 1's prompt into Part 3's `prompt-v0.md` or the import flow (they stay separate files; a later change may connect them).
- A second framework rewrite run (the other framework is shown as a bundled sample after the rewrite, not run).
- Real-CLI runs: Part 1 is verified on the stand-in. A real pass needs two real sessions (the cold run and the rewrite run) and the user's approval; 15 of 17 budgeted sessions are used.
- Slide-deck accessibility rules, timing and facilitation logistics from the live materials.
- Changes to setup, preflight, tracks, the reference card or the Settings panel.
