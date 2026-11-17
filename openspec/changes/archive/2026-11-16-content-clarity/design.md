# Design

## Context

Everything participants read lives in `content/*.json` (AGENTS.md rule 1 of the working conventions), with a few hardcoded interface strings in `web/` that say "CLI". A scan of the current content finds about 365 uses of "CLI" in participant text (`steps.json` ~209, `preflight.json` ~64, `part-1-steps.json` ~45, `lesson-ui.json` ~27, `lessons.json` 12, `cli-recipes.json` 8, `settings.json` 7, `glossary.json` 2), 36 uses of "kind" in `part-1-lessons.json` for the five groups, and Northwind in `lessons.json`, `part-1-lessons.json`, `part-2-lessons.json`, `part-1-steps.json`, `part-2-steps.json`, `steps.json`, `preflight.json` and `series.json`. Each mission lesson is a Markdown body with a fenced `you-are-here` block that `web/js/markdown.js` renders. Tests read the same JSON, so most work is content plus test updates. See proposal.md for why.

Constraints that shape the approach: bundled skills are byte-identical (rule 8), `kit/northwind` files are unchanged and tested, lessons cite only bundled `kit:` files, progress stores ids and never text (rule 9 of the non-negotiables), and interface layout stays as it is (rule 11).

## Goals / Non-Goals

**Goals:**
- One shape for every mission lesson, written once and re-usable for Parts 4 and 5.
- A vocabulary participants can read without help: "your AI", "AI window", "Practice task", "My own task", "categories".
- Tests that keep the vocabulary from drifting back.

**Non-Goals:**
- No change to behavior, gates, ids, storage keys, file names or the course order.
- No new interface component and no change to `web/js/markdown.js`. The `you-are-here` renderer stays unused.
- No rename of "CLI" in code, specs, tests, docs, `cli-recipes.json` keys or ids.

## Decisions

### D1. Mission skeleton as labelled bold passages in the existing Markdown body
Each mission body uses bold lead-ins, the same device lessons already use ("In plain words.", "The method."): `**The goal.**`, `**Why it matters to you.**`, `**What you will do.**`, `**What you leave with.**`. Part 1 adds `**About this series.**` first, carrying the purpose, the three reasons and the method. The existing `**The goal: ...**` heading line becomes `**The goal.**` plus a sentence, and the lesson's `mission` field (the goal sentence) stays as it is.
Alternative considered: structured fields in JSON per mission. Rejected: it needs a renderer change, which rule 11 forbids without authorization, and the Markdown already renders.

Draft copy, to be refined in apply and checked against the 450-word cap.

Part 1 (`p1-mission`):
- About this series. This series teaches you to judge the work AI gives you, and to trust it because you checked it, not because it looked right. It does not ask for blind trust or blind distrust. Checking matters for three reasons: AI sounds sure of itself even when it is wrong; "better" is only an opinion until you measure it; and answers change from one try to the next, so one answer proves little. The method is: ask clearly, know what you need, turn it into rules, score the result, improve, keep a record.
- The goal. Understand why a structured prompt gets better results, and that you can use a ready-made structure or build your own.
- Why it matters to you. Every later Part builds on the prompt. When a prompt leaves something out, the AI guesses, and you cannot tell which guesses were wrong. You do not need any technical background.
- What you will do. Write a prompt in your own words, run it once and score the answer against five things you knew but never said. Then the ideas come in, as names for what you found. Rewrite the prompt, run it again and compare. The update you work with is the Practice task: a ready-made example, for practice only and never something to submit.
- What you leave with. Your first prompt and its answer, a rewritten prompt and its answer, your scores, and one real prompt from your own work in a structure.

Part 2 (`p2-mission`):
- The goal. Real work does not come with a card of requirements, so how do you know the second answer is better? You write down what good means before you look at any answer. In this Part you turn "that looks good" into clear rules that a script could check.
- Why it matters to you. Words like "clear" mean different things to different readers until each becomes a number, a term or a label. A rule written down before you see an answer cannot bend to fit the answer you see.
- What you will do. Turn what you know about a good answer into criteria, give each one a pass or fail rule, and write them down as test cases. Nothing is run in this Part. Running the rules starts in Part 3. The Practice task is for practice only.
- What you leave with. A worksheet and a test case file in your project folder (`part-2\test-cases.md`).

Part 3 (`mission`):
- The goal. Turn the test cases, criteria and thresholds you wrote in Part 2 into a checker you can trust, and record a starting score.
- Why it matters to you. A checker applies your rules the same way every time. Without one, a score depends on who looks and when. You do not need to code, because your AI writes the program. Your job is to decide what good means and to check that the program means the same.
- What you will do. Have your AI build the checker, test the checker on answers where you know the result, run it on five answers and record the baseline.
- What you leave with. A tested checker, results for five answers and a baseline score you can compare against in later Parts.

### D2. Framework section: categories list, then one table per framework
`p1-frameworks` opens its idea passage with a numbered list titled "The five categories of what a prompt needs" (1 Who the AI acts as, 2 What to produce, 3 Background, 4 Limits and format, 5 A good result) and the sentence "These are the five categories this course uses. Others exist." Then two tables, RTCC and RISE, each in spelling order:

| Letter | Label | What you write there | Covers category |
|---|---|---|---|
| R | Role | Who the AI acts as | 1. Who the AI acts as |
| T | Task | What you want produced | 2. What to produce |
| C | Context | The background it needs | 3. Background |
| C | Constraints | The limits and the format | 4. Limits and format (also touches 5) |

| Letter | Label | What you write there | Covers category |
|---|---|---|---|
| R | Role | Who the AI acts as | 1. Who the AI acts as |
| I | Input | The notes and background | 3. Background |
| S | Steps | What to do, in order | 2. What to produce |
| E | Expectation | What a good result looks like | 5. A good result (also touches 4) |

This replaces the single mapping table. The `fw-map` sort activity keeps its ids and answers; only the word "kind" in prompts and feedback becomes "category". Alternative considered: keep one table with a column per framework. Rejected by the review (hard to read).
"Kind" is replaced only where it means these five groups. Other uses stay: "what kind of thing to produce", "a different kind of problem", Part 2's "both kinds" (format and content), glossary `kind: idea|course` (a data field) and step `kind` ids. The tests in `test_part_1_content.py` that assert "other kinds exist", "five common kinds", "kind 5 fits only partly" change to the new words.

### D3. "CLI" replacement by rule, applied by a script, reviewed by hand
Replace by a fixed rule table rather than per-string judgement: "your CLI" to "your AI"; "the CLI" to "your AI" or "the AI window" depending on whether the sentence is about the tool or the window it runs in; "CLI window/terminal" to "AI window"; "Start my CLI" to "Start my AI"; "Send to CLI" to "Send to AI"; "CLI session" to "AI window chat" (Part terminology spec: "session" rules still apply). A one-off script lists every string that contains "CLI" so each change is reviewed in context; the script is not committed. Vendor names ("GitHub Copilot CLI", "Devin CLI") are kept. "Another CLI" in `cli-recipes.json` becomes "Another AI tool" as text only; its removal for participants is change 2 (guided setup).
The `web/` hardcoded strings are changed in place with the same words, text only.
Alternative considered: move the hardcoded strings into content now. Rejected: it is a code and interface refactor outside this change; it can follow in change 2.

### D4. "Practice task" replaces the example's name only where the example is named as an option or choice
Changes: the starter choice label and hint, `northwind_note`, the `project_files_missing` message, mission and finished-screen sentences, glossary and step text that call it "the Northwind example". Unchanged: `kit/northwind/*` files, kit file names and `kit:northwind/...` refs, the client name inside the example's own prompt, rough notes and test cases (including `r3` "Northwind, Contoso, Internal" in the step data), step ids and the starter's internal id. Source labels such as "Northwind test cases (learning example)" become "Practice task test cases (learning example)", because the label is participant text; the ref stays.
Existing tests that check "Northwind is a learning example where introduced" and "nothing offers Northwind as a submission" are rewritten for "Practice task" and "practice only".

### D5. Tests: one scan, explicit allow-list
Add `tests/test_participant_vocabulary.py`. It reads every string in `content/*.json`, the bundled non-skill kit files and the string literals in `web/`, and fails on a bare "CLI" and on "Northwind" as an option name. The allowed uses are a short list in the test: vendor product names (`GitHub Copilot CLI`, `Devin CLI`, `PowerShell` recipe names) and the glossary "AI window" entry, each with a reason. Mission tests in `test_series.py`, `test_part_1_content.py` and `test_part_2_content.py` that read the `you-are-here` block are replaced by tests for the four passages, the series passage in Part 1 only and the absence of a map. `test_every_mission_map_agrees_with_the_series_map` and its two siblings are removed with the spec requirement.

### D6. Series map intro and track words are content only
`series.json` `ui.intro` becomes "Six Parts, one method. Do each one yourself: copying someone else's prompt or rules gives you their answers, not the skill to check your own." `preflight.json` `ui.track_options` hints become the two level-based sentences; the "default" and "needs nothing extra" wording goes. The track radio has no preselection requirement beyond the current behavior; the apply step checks the Track page and records any preselected state as a finding, not a silent change (a preselection would be an interface change).

## Files and storage touched

| Location | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/content/lessons.json`, `part-1-lessons.json`, `part-2-lessons.json` | Mission bodies, vocabulary, categories, Practice task | Ids, activity ids, `win`, `minutes`, `related`, `sources` refs kept; labels and prose changed |
| `app/eval_coach/content/part-1-steps.json`, `part-2-steps.json`, `steps.json` | "CLI" and "Northwind" prose | Step ids, `kind`, gates, data keys kept |
| `app/eval_coach/content/preflight.json`, `settings.json`, `lesson-ui.json`, `series.json`, `glossary.json`, `cli-recipes.json` | Display text, track hints, starter labels, intro, new "AI window" entry, remove "CLI" entry | Keys, command data and recipes kept |
| `app/eval_coach/kit/part1/frameworks-map.md`, `typical-gaps.md` | "kinds" to "categories" | File names kept |
| `app/eval_coach/kit/northwind/`, `kit/skills/` | None | Unchanged, byte-identical |
| `app/eval_coach/web/index.html`, `js/app.js`, `js/lessons.js`, `js/panels.js`, `js/views.js` | Hardcoded "CLI" text only | No layout, id or style change |
| `tests/` | See D5 and tasks | New and updated |
| `docs/SPEC.md`, `docs/COURSE-CONTEXT.md`, `docs/IMPLEMENTATION-PLAN.md`, `AGENTS.md` (rule 10 and Status), `docs/temp/series-review-pending-changes.md` | Wording and status | Kept otherwise |
| `dist/eval-coach.pyz` | Rebuilt | Generated |
| Participant `progress.json`, `.learning\` files, reset-backup folder, `pending-lessons.json` | None | Kept. Only ids are stored, and no id changes. Saved reflections stay valid. |

## Risks / Trade-offs

- [A wrong "CLI" replacement changes the meaning, for example "CLI" meaning the tool versus the window] → Review each changed string in context (D3) and run the vocabulary test plus the step and Playwright tests.
- [Playwright tests match old text such as "Start my CLI"] → Search `tests/frontend` for each changed string and update in the same task.
- [Part 1 mission passes 450 words with the series passage] → Count in the tests; trim "What you will do" first, and raise the cap only with the user's go-ahead (Open Question Q4).
- [Removing the "Northwind" name makes the example harder to find in the kit] → Source labels still say "Practice task" and the ref keeps the file name; the glossary entry for the Practice task says what it is.
- [Series-level framing now lives only in Part 1, so a participant starting at Part 2 misses it] → Accepted by the review (item 13); Part 2 and 3 goal passages point back to the previous Part in one sentence. Course locking (change 5) later makes starting mid-series unusual.
- [Hardcoded `web/` strings are edited text-only but the interface rule is strict] → The user authorized wording-only edits on 2026-11-16 (Q1); nothing else in `web/` changes.

## Migration Plan

No data migration. Content ships with the next build. Rollback is restoring the previous content files. Existing progress files keep working because lesson, step and activity ids do not change, and a mission already marked done stays done.

## Open Questions

1. **Q1. Interface authorization (rule 11). Confirmed by the user:** wording-only edits to the hardcoded `web/` strings listed in the proposal, in addition to the content files. No layout, style, component or id change.
2. **Q2. Where the series passage sits in Part 1. Confirmed by the user:** first, as "About this series", before "The goal".
3. **Q3. "Another CLI" option text.** Assumed default: rename the display text to "Another AI tool" now, even though change 2 removes it for participants.
4. **Q4. Part 1 mission length.** Assumed default: keep within the existing 450-word cap by trimming prose. Alternative: raise the cap for `p1-mission` only.
5. **Q5. Practice task in source labels.** Assumed default: change participant-visible source labels (for example "Practice task test cases (learning example)") and keep refs. Alternative: leave labels that quote the kit file name.
6. **Q6. "Another" uses of "kind".** Assumed default: change "kind" to "category" only for the five groups; leave other uses (including Part 2's "both kinds" for format and content).
7. **Q7. Track preselection.** Assumed default: if the Track page currently preselects a track, record it and leave it, since removing it is an interface change not covered here.
8. **Q8. Unused `you-are-here` renderer.** Assumed default: leave `web/js/markdown.js` as is. Removing it is a later cleanup that needs its own authorization.
