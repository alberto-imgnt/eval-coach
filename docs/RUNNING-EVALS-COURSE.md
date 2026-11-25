# Part 3: running evals and baseline (course content)

Read `docs/SPEC.md` first; its non-negotiable rules apply. The teaching rules, the content-file schema, the activity types, grading, the review queue, the glossary and the wording rules that every Part follows are in [CONTENT-RULES.md](CONTENT-RULES.md). This file holds only what is specific to Part 3: its mission wording, lesson list and order, and its AI-window activities. Task IDs and phase names in older archived changes refer to a local implementation plan that is not in the repository. The API and storage contract is in `docs/SPEC.md` ("Course and lessons").

Part 1 (structured prompting) and Part 2 (defining evaluation criteria) have their own courses, in `docs/SPEC.md` "Part 1" and "Part 2" and the OpenSpec specs `part-1-course`, `part-1-exercise-steps`, `part-2-course` and `part-2-exercise-steps`. Parts 4 and 5 are not built.

**Mission (use this wording):** `Understand how to turn the test cases, criteria and thresholds from Part 2 into reusable parts, and how those parts fit into an evaluated AI process.` The mission states the learning outcome, not the files the participant produces. The mission page has the four-passage shape every Part uses (`mission-lesson-shape`) and no map of the Parts. The course follows the series intent in the priority order tier 1 core knowledge, tier 2 context, tier 3 certification (see "Learning priorities" in [CONTENT-RULES.md](CONTENT-RULES.md)).

## Course order
`mission` is readable before setup. Everything else opens after setup passes (setup is a global screen, not a course item). There are seven lessons, one concept each, in the order of the method; the steps carry the procedure. The ids below equal `state.COURSE`.

| Item | Kind | Method link |
|---|---|---|
| `mission` | lesson, one page, no activities | the goal, why it matters to you, what you will do, what you leave with (no map of the Parts; the series framing is in Part 1's `p1-mission` only) |
| `hook` | lesson, AI window (`hook-compare`) | turn it into rules: a fixed rule beats an AI opinion |
| `several-runs` | lesson (skippable) | score the result: one answer proves little |
| `inputs` | step, no AI | choose which prompt and test cases Part 3 will score: the active pair with where each came from, the Part 1 rewrite and the Part 2 file as explicit choices, and the Practice task as the labelled fallback (never a submission) |
| `generate` | step | |
| `rules` | lesson, rule labs, practice run (`build-try`) | turn it into rules: from "looks good" to a rule, and what a rule cannot check |
| `build` | step | |
| `trust` | lesson (skippable) | score the result: test the checker before trusting it |
| `fixtures`, `readback`, `predict`, `key` | steps | |
| `surprise` | lesson, practice run (`fix-try`) | improve: read a surprise, fix the spec and not the checker |
| `run`, `fix` | steps | |
| `baseline-why` | lesson | keep a record: the baseline, what a score means, what comes next, the Stage 3 note |
| `baseline` | step | |

On the promptfoo track `fixtures-config` follows `fixtures`. A step stays locked until the lesson immediately before it is done or skipped. Earlier versions of the course had eleven lessons (loop, generate-why, build-why, choices, verify, compare and fix-why were merged into the seven above) and ten mechanics-only activities that were removed; the full disposition is in `openspec/changes/archive/2026-11-15-align-series-content-with-intent/design.md` (D8) and `docs/SPEC.md` ("Course and lessons"). Word caps: 300 per lesson, 450 for `mission`, 400 for `baseline-why`.

The Part 3 lessons are in `content/lessons.json`, its steps in `content/steps.json`. Their schema is the one in [CONTENT-RULES.md](CONTENT-RULES.md).

## AI-window activities
All use the existing terminal, Start and Send pattern. The app decides only from files.

**Practice runs (`build-try` in `rules`, `fix-try` in `surprise`).** A lesson that talks about running something in the AI window may have a `cli_practice` activity, so the participant sees the same Start, Send, Stop and Start again panel as in the hook lesson. Folder `<home>\practice\<activity id>\`, cleared before each start. It holds only the `files` the activity lists, each copied from a `kit:` source and never from the participant's project. The folder never holds an answer key. The app types the activity's exact `line`, which must tell the AI to save its answer to `output.txt`. When `output.txt` is non-empty and stable, the app copies it to `<project>\.learning\practice\<activity id>.txt`, stops the AI, and shows the text as plain text. The question unlocks only after that, and the lesson cannot be completed without it. A lesson that has only a practice run of this kind may stay `skippable`, because the placement question already proves the knowledge.

A terminal marker for AI tools that print "Unsupported terminal" in the page terminal is listed in `content/terminal-hints.json`. Code never names a tool.

**Hook (`hook`, 3 runs).** Folder `<home>\hook\`, cleared before each run. It holds only `update.txt` (from `kit/northwind/fixture-polished-but-wrong.txt`) and `requirements.md` (from `kit/lessons/hook/requirements.md`). Exact line:
`Read update.txt and requirements.md. Score the update from 1 to 10 against the requirements, say pass or fail, and give one sentence of reasoning. Save only that to output.txt. Do nothing else.`
Capture `output.txt` the way the generate step does, stop the AI, and save to `<project>\.learning\hook\run-n.txt`. Each run is a new process. Show the three results side by side as plain text, never as HTML.

`kit/lessons/hook/requirements.md` content: the six Northwind requirements (under 150 words; group by client, not by day; call out the blocker and what you need; sent as a Teams message, not an email; factual, not self-promotional; turn the rough notes into the update), followed by the rough notes list from `kit/northwind/northwind-test-cases-reference.md`.

**Anatomy demo (`cli_demo`, not used by the current course).** The seven-lesson course has no lesson with a `cli_demo`: the earlier `rules-demo` and `rules-anatomy` activities were removed because they taught only this course's file layout, and the checker is now built in the `build` step. The activity type stays supported (a `cli_demo` sits only in lesson `rules`). When used, the folder is `<home>\demo\`, cleared before start, holding the activity's `files`; the app runs `check.py output.txt` twice from that folder and shows both verdict lists.

## Part 3 content rules
- The Part 3 content rules are the series-wide ones in [CONTENT-RULES.md](CONTENT-RULES.md), plus: `trust` must not reveal Northwind's answer key, and nothing before the `key` step may show fixture answers (SPEC.md "Steps in this slice" and AGENTS.md rule 9).
