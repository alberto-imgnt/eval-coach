# Proposal

## Why

The series review of 2026-11-16 found that the words participants read get in the way. Every mission lesson carries the same series-level paragraph and a "you are here" map that adds nothing once you are inside a Part. "CLI" and "Northwind" mean nothing to a non-technical reader. The two tracks look like a quiet recommendation ("the default") instead of a choice made by technical level. The framework section of Part 1 mixes "kinds" and frameworks in one table that is hard to read. This is mostly a content change, and it sets the vocabulary every later change builds on (guided setup, model preference, the Part 1 AI flow and course locking).

Source: `docs/temp/series-review-pending-changes.md`, area E, items 12, 13, 14a, 15, 16, 17 and 19.

## What Changes

- **Mission lessons (items 12, 13).** Remove the "you are here" map from every mission lesson (`mission`, `p1-mission`, `p2-mission`). Give every mission the same four passages in this order: the goal, why it matters to you (specific to the Part), what you will do, what you leave with. The series-level framing ("AI sounds sure of itself...", the three reasons, the method) appears once, in Part 1, and is removed from the other missions.
- **Framework section (item 14a).** Rebuild the framework passage of `p1-frameworks`: a numbered list of "the five categories of what a prompt needs" with a note that these are the five used in this course and more exist, then one table per framework (RTCC, RISE) with one row per letter in spelling order: Letter, Label, What you write there, Covers category. Use the word "categories", not "kinds", wherever the text means these five groups (`part-1-lessons.json`, `part-1-steps.json`, the glossary and the bundled `part1` kit files). CRISP stays out of Part 1 (item 14b).
- **"AI window" instead of "CLI" (item 15).** Everything participants read says "your AI" or "AI window" where it now says "CLI". Vendor product names (GitHub Copilot CLI, Devin CLI) stay. Add a glossary entry "AI window" and a content test that flags "CLI" outside product names and the glossary.
- **"Practice task" instead of "Northwind" (item 16).** What participants read calls the ready-made example the "Practice task", with a short explanation that it is a ready-made example, and the other option "My own task". Internal ids, folders, kit files, bundled skills and the client name inside the scenario (Northwind in the update itself) stay.
- **Track descriptions by tech level (item 17).** Script: no technical experience needed, your AI builds the checker, nothing extra to install. promptfoo: for technical users, needs Node.js and about 1 GB. No default or recommendation wording or badge. Names stay "Script track" and "promptfoo track".
- **Series map intro (item 19).** Replace "or look ahead at what comes next" with a line about doing the work yourself.
- **Part 2 re-check.** `add-part-2` is complete and archived, so its mission and wording are brought in line with items 12, 13 and 15 in this change.

Out of scope:

- Technical or non-technical mode (item 0, deferred), model choice (change 3), guided setup and its pages (change 2), the Part 1 AI flow (change 4) and course locking (change 5).
- Missions for Parts 4 and 5, which do not exist yet; they follow the skeleton when they are written.
- Renaming "CLI" in code, specs, tests, docs, ids, file names, `cli-recipes.json` keys or the "Another CLI" option. Only what participants read changes. Removing the free-text "Another AI tool" option belongs to change 2.
- Any bundled skill file (rule 8, byte-identical) and the Northwind kit files (`kit/northwind`), which stay unchanged.
- Removing the `you-are-here` renderer from `web/js/markdown.js`. It stays unused in this change.
- Recommending a framework or adding CRISP.

## Interface authorization (AGENTS.md rule 11)

This change edits interface copy only. The user explicitly authorized this scope on 2026-11-16 (rule 11):

- Wording in `content/lesson-ui.json`, step `ui` blocks, `content/preflight.json`, `content/settings.json` and `content/series.json`.
- Wording of hardcoded strings in `web/` (`index.html` aria label, `js/app.js`, `js/lessons.js`, `js/panels.js`, `js/views.js`) that say "CLI". Text only. No change to layout, styling, components or element ids.
- No new interface components. The framework tables are Markdown inside a lesson body, which the lesson renderer already shows.

## Capabilities

### New Capabilities

- `mission-lesson-shape`: every Part's mission lesson has the same four passages in a fixed order, no "you are here" map and no repeated series framing.
- `participant-vocabulary`: the words participants read for the AI tool ("your AI", "AI window") and the ready-made example ("Practice task"), and the content tests that keep them consistent.

### Modified Capabilities

- `part-1-course`: the mission requirement (new shape, no map), the gaps and reveal requirements (categories, one table per framework) and the plain-language rule (Practice task).
- `part-2-course`: the mission requirement (new shape, no map), the Practice task wording and the plain-language rule.
- `series-intent-framing`: the series purpose and the three reasons live in Part 1 only; the course map requirement is removed.
- `series-map`: the intro line, and the Series map no longer has to match a mission map.
- `setup-access`: page names without "CLI", track descriptions by tech level with no default wording, and the starter choice words (Practice task, My own task).

## Impact

- Content: `app/eval_coach/content/` (`lessons.json`, `part-1-lessons.json`, `part-2-lessons.json`, `part-1-steps.json`, `part-2-steps.json`, `steps.json`, `preflight.json`, `lesson-ui.json`, `settings.json`, `glossary.json`, `series.json`, `cli-recipes.json` display text only) and `app/eval_coach/kit/part1/` (`frameworks-map.md`, `typical-gaps.md`).
- Interface copy: the five `web/` files listed above, text only.
- Tests: `tests/test_series.py`, `test_part_1_content.py`, `test_part_2_content.py`, `test_content_banned_words.py`, the frontend Playwright tests that match "CLI" text, plus new vocabulary tests.
- Docs: `docs/SPEC.md`, `docs/COURSE-CONTEXT.md` (wording), `docs/IMPLEMENTATION-PLAN.md` task table, `AGENTS.md` (rule 10 gains the two words), and `docs/temp/series-review-pending-changes.md` (mark change 1 proposed).
- Sequencing: `add-part-2` is already archived, so the `part-2-course` and `series-map` deltas apply on top of it. This change comes before guided setup, model preference, the Part 1 AI flow and course locking.
- No change to behavior, gates, progress storage or the 17-session real-CLI budget. Verification uses the stand-in CLI only.
