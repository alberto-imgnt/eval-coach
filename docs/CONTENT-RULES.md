# Content rules: teaching, activities and wording for every Part

Read `docs/SPEC.md` first; its non-negotiable rules apply. These rules apply to **every Part's course** (Part 1 `part-1-course`, Part 2 `part-2-course`, Part 3 [RUNNING-EVALS-COURSE.md](RUNNING-EVALS-COURSE.md), and Parts 4 and 5 when they are built). They were first written for Part 3 and moved here when the app became a series of six Parts. The API and storage contract is in `docs/SPEC.md` ("Course and lessons", "Parts", "Part 1", "Part 2"). The OpenSpec specs `mission-lesson-shape`, `method-over-mechanics`, `course-structure`, `participant-vocabulary` and `part-terminology` win over this file for their areas.

Where each Part's own course is described:

| Part | Course | Mission lesson | Specs |
|---|---|---|---|
| 1. Structured prompting | `docs/SPEC.md` "Part 1" | `p1-mission` | `part-1-course`, `part-1-exercise-steps` |
| 2. Defining evaluation criteria | `docs/SPEC.md` "Part 2" | `p2-mission` | `part-2-course`, `part-2-exercise-steps` |
| 3. Running evals and baseline | [RUNNING-EVALS-COURSE.md](RUNNING-EVALS-COURSE.md) | `mission` | `course-structure` |
| 4, 5 | not built (Series map shows "Coming soon") | | |
| 6 | live meeting (Series map row only) | | |

Part-specific rules that sit on top of these: Part 1 keeps "discovery before theory" until `p1-frameworks` (no framework is named before it); Part 2 holds the Northwind reference criteria back until the `reference` step. Part 3's rules are in its own file.

## Teaching rules
- Mission first. Every lesson ties to its Part's mission and gives one tangible win, and can be finished in one sitting.
- Knowledge comes first and is kept easy. Practice comes next, with a tight feedback loop, and is meant to be hard.
- **Every answer option in a question has the same number of words.** This is a content rule enforced by a test.
- Answer order is shuffled. A participant's order is stable across reloads.
- Every lesson after the mission opens with `**In the method.**` (one line that names the link of the method the lesson covers: ask clearly, know what you need, turn it into rules, score the result, improve, keep a record), then `**The idea.**` (the transferable concept, in plain words), then any short labelled passages. Lessons keep this course's own mechanics (roles, blind folder, number of runs, file layout) to one short passage labelled `**How this course does it.**` that comes after the idea and says other approaches exist; the full procedure is explained in the step that does it.
- Every Part's mission lesson has the same shape: one page, no activities, four passages in this order: `The goal`, `Why it matters to you`, `What you will do` and `What you leave with`, each specific to its Part (spec `mission-lesson-shape`). The series framing ("AI sounds sure of itself…", the three reasons, the method) appears once, as a passage before "The goal" in Part 1's mission only. No mission shows a map of the Parts; the Series map is the only place that lists them. A mission body is at most 450 words.
- No question ever blocks Continue (decision 2026-11-10, replacing an earlier rule that quizzes cannot be skipped). Only the exercises do: the demo, and the output an AI-window exercise must save. Each lesson body says so in plain words ("It is for you, so answer it or move on"). A passed question still creates a learning record, and every lesson's `retrieval` items still come back in the review queue, so retrieval and spacing are kept without gating.
- A short check follows every hands-on exercise, and each step has one question on its own page after the step is done (`step_checks` in the Part's lessons file, shown under the heading "Quick check"). Step questions are never a gate.
- Every lesson cites its sources and names one primary source to read. A lesson with no citations is teaching from memory.
- Claims come from the source materials. Do not add facts from general knowledge. Any external citation must be a page that was actually opened and read.
- Learning records hold only what the participant demonstrated. Viewing a page creates no record.
- Real-world judgment becomes written reflection, because the app has no community channel.
- The short form of each idea goes in the reference, not only in a lesson.
- Content is ranked tier 1 core knowledge, tier 2 context, tier 3 certification (see "Learning priorities" below). The series intent and the Stage 3 task are kept in local reference notes (not in the repository); the specs `series-intent-framing`, `method-over-mechanics` and `learning-priority-order` carry what the content needs from them.

## Content files: `content/lessons.json` and `content/part-<n>-lessons.json`
Part 3's lessons are in `content/lessons.json`; every other Part keeps its own in `content/part-<n>-lessons.json`. All use one schema and one validator (`lessons.validate_course`), checked against that Part's lesson and step ids.
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
`ref` is either `kit:<path inside app/eval_coach/kit>` (the app opens the bundled file in a read-only viewer) or an `https://` URL. Participants cannot see the source session plans, so never cite them to them: use `kit:` files, or plain teaching statements backed by a kit file. Knowledge-only lessons may be `skippable`; practice lessons and AI-window lessons never are. A Part's mission is the one lesson allowed to have no activities or retrieval.

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
| `cli_practice` | `id, line, folder_label, files[{name,source}], question` | The AI saved `output.txt` in the practice folder and `question` (a choice) passed |

`rule_lab` rule kinds are a fixed list implemented in Python: `word_count_under {limit}`, `all_present {terms}`, `none_present {terms}`, `all_labels {labels}`. No activity type blocks Continue except `cli_demo` and the saved output of `cli_compare` and `cli_practice` (see the teaching rules above and `SPEC.md`). The app never executes participant-supplied code. The lab shows the verdict, the reason, and a "Run again" button so the participant sees the same verdict twice. It also has a "Try your own text" box, introduced by a line that says it is optional, unscored practice. Each rule may carry an `explain` sentence; the lab lists every rule with it above the cases so predictions follow stated rules.

### Grading
- Correct answers, buckets, expected verdicts and order stay on the server until the activity is answered. No API response may contain them earlier.
- A wrong choice shows only that option's feedback, not the right answer. Retry is unlimited. Record whether the first attempt passed.
- Word-count parity counts whitespace-separated tokens. All options in a `choice`, placement or retrieval item must match.

## Placement
Shown inside a Part's mission, at most 6 questions, in `choice` shape. A correct answer offers to skip that question's `skippable` lesson; the participant accepts or declines. A wrong answer changes nothing. Practice steps and non-skippable lessons are never skipped. A placement pass creates a learning record with source `placement`. No Part has placement questions today (`placement` is empty); the engine feature stays.

## Review queue
One queue serves every Part (a sitting mixes lessons from all of them).
- Every completed lesson schedules each of its `retrieval` items, first due 1 day after completion.
- Correct moves the item through 1, 3 and 7 days, then retires it. Wrong moves it back to 1 day.
- At most 5 items per sitting, mixed so consecutive items come from different lessons when possible. A sitting is fixed once chosen; items still due wait for the next time the app opens.
- Shown when the app reopens and items are due. The participant can postpone it, and it never blocks the course. It also works after the course is finished.
- The clock is injected so tests can control it.

## State and routes
Specified in `SPEC.md`: the `lessons` block in `progress.json`, the migration of older progress, the `State` fields (`course`, `current_item`, `review`, `course_text`, `series`), and the routes under `/api/lesson`, `/api/placement`, `/api/kit` and `/api/review`. Engine tests that are not about lessons construct the engine with no lessons, so the existing step tests keep working without changes to their flow.

## Reference
`content/glossary.json`: `{"terms":[{"term","kind","meaning","lesson"}]}`, covering the series glossary, reworded to drop "today" and any live-session wording. Every term has a `kind`: `idea` (a general idea, tool-neutral) or `course` (a term for how this course does it, whose meaning begins "In this course,"). An in-app glossary panel is reachable from every screen and, like the printable reference, shows two groups: "Ideas" and "In this course". The printable one-page reference is a separate page (`web/reference.html`); it opens with the method in one line, then "How this course works" and what this course's checker says (PASS, FAIL, NOT CHECKED), the glossary in its two groups and the principles, and it must fit one page when printed.

## Content quality rules
- Plain language for non-technical readers. Short paragraphs.
- Never mention a presenter, facilitator, room, breakout, chat waterfall, handout, neighbor or clock. Say "Script track" and "promptfoo track", not Room A and Room B. Say "Part", never "session".
- Copilot Chat in Teams is never suggested. The ready-made example is called the "Practice task" (the other starter is "My own task") and is never a submission option; "Northwind" stays only inside the example's own text.
- Say "your AI" or "AI window", never a bare "CLI" (vendor names such as GitHub Copilot CLI stay). The five groups of what a prompt needs are "categories", not "kinds".
- Lessons must not give away what is wrong with a participant's own fixture. In Part 3, `trust` must not reveal Northwind's answer key.

## Learning priorities
Every content, activity and pilot decision is ranked by this hierarchy (set by the user, 2026-11-10; the order restated 2026-11-14):

| Tier | Priority | What a participant can do at the end |
|---|---|---|
| 1 | **Core knowledge (top)** | Understand evaluation concepts and run an evaluation, and explain both to a technical and to a non-technical audience |
| 2 | **Context (secondary)** | Describe the end-to-end workflow and where an evaluation fits in the broader process |
| 3 | **Certification (tertiary)** | See how the work they produced lines up with the Stage 3 certification requirements |

Rules for using the hierarchy:
- When two tasks compete for time or screen space, the higher tier wins.
- Certification content never replaces, delays or gates tier 1 or tier 2 content. It never blocks Continue.
- The app teaches and shows alignment. It never certifies, never scores a submission and never gives submission steps.
- "Explain it" is part of tier 1: knowing the concept and running it is not enough unless the participant can also say it in plain words to a non-technical reader.

**Reading of "priority order".** The order is tier 1 core knowledge > tier 2 context > tier 3 certification. A tier 1 idea is placed, worded and sized before a tier 2 or tier 3 item, and a lower-tier item is the one that is shortened or cut. The order ranks content; it does not make lower tiers optional to the point of omission, so each tier still gets its place, in proportion (for example a Stage 3 note is short and optional, a mission is at most 450 words and a lesson at most 300).
