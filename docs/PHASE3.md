# Phase 3: course content

Read `docs/SPEC.md` first; its non-negotiable rules apply. Task IDs refer to `docs/IMPLEMENTATION-PLAN.md`. The API and storage parts of this file are merged into `SPEC.md` (section "Course and lessons (Phase 3)"), which is the contract the code follows. This file keeps the teaching rules, the lesson list and the content rules. It describes Part 3's course. Part 1 (structured prompting) has its own course, in `docs/SPEC.md` "Part 1" and the OpenSpec specs `part-1-course` and `part-1-exercise-steps`; it follows the same teaching and content rules below (the mission is `p1-mission`, the same shape applies to `p1-gaps`, `p1-frameworks` and `p1-benefits`, and "discovery before theory" holds until `p1-frameworks`). Part 2 (defining evaluation criteria) likewise has its own course, in `docs/SPEC.md` "Part 2" and the OpenSpec specs `part-2-course` and `part-2-exercise-steps`; it follows the same teaching and content rules (the mission is `p2-mission`, the same shape applies to `p2-criteria`, `p2-thresholds` and `p2-testfile`, and the Northwind reference criteria stay held back until the `reference` step).

## Teaching rules (from the /teach guidance at aihero.dev/skills-teach)
- Mission first. Every lesson ties to the mission and gives one tangible win, and can be finished in one sitting.
- Knowledge comes first and is kept easy. Practice comes next, with a tight feedback loop, and is meant to be hard.
- **Every answer option in a question has the same number of words.** This is a content rule enforced by a test.
- Answer order is shuffled. A participant's order is stable across reloads.
- Every lesson after the mission opens with `**In the method.**` (one line that names the link of the method the lesson covers: ask clearly, know what you need, turn it into rules, score the result, improve, keep a record), then `**The idea.**` (the transferable concept, in plain words), then any short labelled passages. Lessons keep this course's own mechanics (roles, blind folder, number of runs, file layout) to one short passage labelled `**How this course does it.**` that comes after the idea and says other approaches exist; the full procedure is explained in the step that does it. The mission opens with the goal sentence and uses `**In plain words.**`, `**Why it matters.**`, `**The method.**` and `**Where this course fits.**` (the six-Part map, with the intent's Part names). The recap is never longer than a few sentences and names only things the course itself produced.
- No question ever blocks Continue (decision 2026-11-10, replacing the earlier "quizzes cannot be skipped" rule from the /teach guidance). Only the exercises do: the demo, and the output a CLI exercise must save. Each lesson body says so in plain words ("It is for you, so answer it or move on"). A passed question still creates a learning record, and every lesson's `retrieval` items still come back in the review queue, so retrieval and spacing are kept without gating.
- A short check follows every hands-on exercise, and each step has one question on its own page after the step is done (`step_checks` in `content/lessons.json`, shown under the heading "Quick check"). Step questions are never a gate.
- Every lesson cites its sources and names one primary source to read. "A lesson with no citations is the skill teaching from memory."
- Claims come from the session materials. Do not add facts from general knowledge. Any external citation must be a page that was actually opened and read.
- Learning records hold only what the participant demonstrated. Viewing a page creates no record.
- Real-world judgment becomes written reflection, because the app has no community channel.
- The short form of each idea goes in the reference, not only in a lesson.

**Mission (use this wording):** `Understand how to turn the test cases, criteria and thresholds from Part 2 into reusable parts, and how those parts fit into an evaluated AI process.` The mission states the learning outcome, not the files the participant produces. The series intent and the Stage 3 task are described in `docs/SERIES-INTENT.md` and `docs/STAGE3-TASK-SPEC.md`; the course is built from them in the priority order tier 1 core knowledge, tier 2 context, tier 3 certification (see "Learning priorities" in `docs/IMPLEMENTATION-PLAN.md`).

## Course order
`mission` comes before preflight. Everything else comes after preflight passes. There are seven lessons, one concept each, in the order of the method; the steps carry the procedure. The ids below equal `state.COURSE`.

| Item | Kind | Method link |
|---|---|---|
| `mission` | lesson, one page, no activities | purpose, why checking matters, the six-Part map |
| preflight | existing screen | |
| `hook` | lesson, CLI (`hook-compare`) | turn it into rules: a fixed rule beats an AI opinion |
| `several-runs` | lesson (skippable) | score the result: one answer proves little |
| `generate` | step | |
| `rules` | lesson, rule labs, practice run (`build-try`) | turn it into rules: from "looks good" to a rule, and what a rule cannot check |
| `build` | step | |
| `trust` | lesson (skippable) | score the result: test the checker before trusting it |
| `fixtures`, `readback`, `predict`, `key` | steps | |
| `surprise` | lesson, practice run (`fix-try`) | improve: read a surprise, fix the spec and not the checker |
| `run`, `fix` | steps | |
| `baseline-why` | lesson | keep a record: the baseline, what a score means, what comes next, the Stage 3 note |
| `baseline` | step | |

On the promptfoo track `fixtures-config` follows `fixtures`. A step stays locked until the lesson immediately before it is done or skipped. Earlier versions of the course had eleven lessons (loop, generate-why, build-why, choices, verify, compare and fix-why were merged into the seven above) and ten mechanics-only activities that were removed; the full disposition is in `openspec/changes/align-series-content-with-intent/design.md` (D8) and `docs/SPEC.md` ("Course and lessons"). Word caps: 300 per lesson, 450 for `mission`, 400 for `baseline-why`.

## Content file: `content/lessons.json`
```json
{
  "version": 1,
  "mission": "<mission text>",
  "placement": [
    {"id": "p-rules", "lesson": "several-runs", "prompt": "...", "options": [
      {"id": "a", "text": "...", "correct": true, "feedback": "..."},
      {"id": "b", "text": "...", "correct": false, "feedback": "..."}
    ]}
  ],
  "lessons": [{
    "id": "several-runs",
    "title": "...",
    "win": "One sentence: what the participant can do after this lesson.",
    "minutes": 4,
    "skippable": true,
    "body": "Markdown. Short. Rendered with the app's existing safe markdown renderer.",
    "activities": [ ... ],
    "retrieval": [ ... at least 2 items, choice shape only, different from the activities ... ],
    "sources": [{"label": "...", "ref": "kit:skills/build-eval-script/SKILL.md"}],
    "primary_source": {"label": "...", "ref": "kit:...", "why": "One sentence on why to read it."},
    "related": {"lessons": ["..."], "glossary": ["..."]}
  }]
}
```
`ref` is either `kit:<path inside app/eval_coach/kit>` (the app opens the bundled file in a read-only viewer) or an `https://` URL. Participants cannot see the session plan, so never cite it to them: use `kit:` files, or plain teaching statements backed by a kit file. Knowledge-only lessons may be `skippable`; practice lessons and CLI lessons never are.

### Activity types
| `type` | Fields | Pass when |
|---|---|---|
| `choice` | `id, prompt, options[{id,text,correct,feedback}]` with exactly one correct option | The correct option is chosen |
| `order` | `id, prompt, items[{id,text}]` listed in the correct order, `feedback_right`, `feedback_wrong` | The submitted order matches |
| `sort` | `id, prompt, buckets[{id,label}], items[{id,text,bucket,feedback}]` | Every item is in its bucket |
| `rule_lab` | `id, prompt, samples[{id,label,text}], cases[{sample,rule,expected}]`, `rules[{id,label,kind,params}]` | The participant predicted every case correctly |
| `reflection` | `id, prompt, min_words` | At least `min_words` words saved |
| `cli_compare` | `id, runs, line, files, question` | `runs` non-empty outputs saved and `question` (a choice) passed |
| `cli_demo` | `id, line, files, run_args` | `check.py` exists, the scan passes, and two app-run checks gave identical verdicts |
| `cli_practice` | `id, line, folder_label, files[{name,source}], question` | The CLI saved `output.txt` in the practice folder and `question` (a choice) passed |

`rule_lab` rule kinds are a fixed list implemented in Python: `word_count_under {limit}`, `all_present {terms}`, `none_present {terms}`, `all_labels {labels}`. No activity type blocks Continue except `cli_demo` and the saved output of `cli_compare` and `cli_practice` (see the teaching rules above and `SPEC.md`). The app never executes participant-supplied code. The lab shows the verdict, the reason, and a "Run again" button so the participant sees the same verdict twice. It also has a "Try your own text" box, introduced by a line that says it is optional, unscored practice. Each rule may carry an `explain` sentence; the lab lists every rule with it above the cases so predictions follow stated rules.

### Grading
- Correct answers, buckets, expected verdicts and order stay on the server until the activity is answered. No API response may contain them earlier.
- A wrong choice shows only that option's feedback, not the right answer. Retry is unlimited. Record whether the first attempt passed.
- Word-count parity counts whitespace-separated tokens. All options in a `choice`, placement or retrieval item must match.

## CLI activities
All three use the existing terminal, Start and Send pattern. The app decides only from files.

**Practice runs (`build-try` in `rules`, `fix-try` in `surprise`).** A lesson that talks about running something in the CLI may have a `cli_practice` activity, so the participant sees the same Start, Send, Stop and Start again panel as in the hook lesson. Folder `<home>\practice\<activity id>\`, cleared before each start. It holds only the `files` the activity lists, each copied from a `kit:` source and never from the participant's project. The folder never holds an answer key. The app types the activity's exact `line`, which must tell the CLI to save its answer to `output.txt`. When `output.txt` is non-empty and stable, the app copies it to `<project>\.learning\practice\<activity id>.txt`, stops the CLI, and shows the text as plain text. The question unlocks only after that, and the lesson cannot be completed without it. A lesson that has only a practice run of this kind may stay `skippable`, because the placement question already proves the knowledge.

A terminal marker for CLIs that print "Unsupported terminal" in the page terminal is listed in `content/terminal-hints.json`. Code never names a CLI.

**Hook (`hook`, 3 runs).** Folder `<home>\hook\`, cleared before each run. It holds only `update.txt` (from `kit/northwind/fixture-polished-but-wrong.txt`) and `requirements.md` (from `kit/lessons/hook/requirements.md`). Exact line:
`Read update.txt and requirements.md. Score the update from 1 to 10 against the requirements, say pass or fail, and give one sentence of reasoning. Save only that to output.txt. Do nothing else.`
Capture `output.txt` the way the generate step does, stop the CLI, and save to `<project>\.learning\hook\run-n.txt`. Each run is a new process. Show the three results side by side as plain text, never as HTML.

`kit/lessons/hook/requirements.md` content: the six Northwind requirements (under 150 words; group by client, not by day; call out the blocker and what you need; sent as a Teams message, not an email; factual, not self-promotional; turn the rough notes into the update), followed by the rough notes list from `kit/northwind/northwind-test-cases-reference.md`.

**Anatomy demo (`cli_demo`, not used by the current course).** The seven-lesson course has no lesson with a `cli_demo`: the earlier `rules-demo` and `rules-anatomy` activities were removed because they taught only this course's file layout, and the checker is now built in the `build` step. The activity type stays supported (a `cli_demo` sits only in lesson `rules`). When used, the folder is `<home>\demo\`, cleared before start, holding the activity's `files`; the app runs `check.py output.txt` twice from that folder and shows both verdict lists.

## Placement
Shown inside `mission`, at most 6 questions, in `choice` shape. A correct answer offers to skip that question's `skippable` lesson; the participant accepts or declines. A wrong answer changes nothing. Practice steps and non-skippable lessons are never skipped. A placement pass creates a learning record with source `placement`.

## Review queue
- Every completed lesson schedules each of its `retrieval` items, first due 1 day after completion.
- Correct moves the item through 1, 3 and 7 days, then retires it. Wrong moves it back to 1 day.
- At most 5 items per sitting, mixed so consecutive items come from different lessons when possible. A sitting is fixed once chosen; items still due wait for the next time the app opens.
- Shown when the app reopens and items are due. The participant can postpone it, and it never blocks the course. It also works after the course is finished.
- The clock is injected so tests can control it.

## State and routes
Now specified in `SPEC.md`: the `lessons` block in `progress.json`, the migration of older progress, the new `State` fields (`course`, `current_item`, `review`, `course_text`), and the routes under `/api/lesson`, `/api/placement`, `/api/kit` and `/api/review`. Engine tests that are not about lessons construct the engine with no lessons, so the existing step tests keep working without changes to their flow.

## Reference
`content/glossary.json`: `{"terms":[{"term","kind","meaning","lesson"}]}`, covering the series glossary, reworded to drop "today" and any live-session wording. Every term has a `kind`: `idea` (a general idea, tool-neutral) or `course` (a term for how this course does it, whose meaning begins "In this course,"). An in-app glossary panel is reachable from every screen and, like the printable reference, shows two groups: "Ideas" and "In this course". The printable one-page reference is a separate page (`web/reference.html`); it opens with the method in one line, then "How this course works" and what this course's checker says (PASS, FAIL, NOT CHECKED), the glossary in its two groups and the principles, and it must fit one page when printed.

## Content quality rules
- Plain language for non-technical readers. Short paragraphs.
- Never mention a presenter, facilitator, room, breakout, chat waterfall, handout, neighbor or clock. Say "Script track" and "promptfoo track", not Room A and Room B.
- Copilot Chat in Teams is never suggested. Northwind is a learning example and never a submission option.
- Lessons must not give away what is wrong with a participant's own fixture. `verify` must not reveal Northwind's answer key.
