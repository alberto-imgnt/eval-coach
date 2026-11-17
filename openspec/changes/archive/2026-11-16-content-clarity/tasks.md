# Tasks

Commands run from the repo root on Windows. Run the two backend suites one after the other, never together. Use the stand-in CLI only (`e2e-work\harness\fake_cli.py`); no real CLI run is needed.

## 1. Vocabulary tests first

- [x] 1.1 Add `tests/test_participant_vocabulary.py`: scan every string in `app/eval_coach/content/*.json`, the non-skill files in `app/eval_coach/kit/` and the string literals in `app/eval_coach/web/`; fail on a bare "CLI" outside the named allow-list (vendor names `GitHub Copilot CLI`, `Devin CLI`, and the glossary "AI window" entry) and on "Northwind" as an option or choice name. Verify: `python -m unittest tests.test_participant_vocabulary` fails and lists the current offenders.
- [x] 1.2 Add a test that the glossary has "AI window" under "In this course" with no bare "CLI", and no entry titled "CLI". Verify: same command, fails until group 3 is done.

## 2. Mission lessons (items 12, 13)

- [x] 2.1 Rewrite `p1-mission` in `part-1-lessons.json` to "About this series", "The goal", "Why it matters to you", "What you will do", "What you leave with", with no `you-are-here` block, using the draft copy in design D1. Verify: body is at most 450 words and `python -m unittest tests.test_part_1_content` mission tests pass after they are updated in 2.4.
- [x] 2.2 Rewrite `p2-mission` in `part-2-lessons.json` to the four passages, opening on Part 1's question, with no series passage and no map. Verify: `python -m unittest tests.test_part_2_content` mission tests pass after 2.4.
- [x] 2.3 Rewrite `mission` in `lessons.json` (Part 3) to the four passages with no series passage and no map; leave the `mission` goal sentence, sources, `primary_source` and `related` as they are except for Practice task labels (group 5). Verify: `python -m unittest tests.test_lessons tests.test_course`.
- [x] 2.4 Replace the mission-map tests with tests for the four passages in order, the series passage in Part 1 only, "AI sounds sure of itself" absent from Parts 2 and 3, no `you-are-here` block and no six-Part list in any mission, and the word cap; remove the three mission-map agreement tests in `tests/test_series.py` (`test_part_names_and_the_outcomes_of_parts_one_to_five_match_all_three_mission_maps`, `test_the_part_six_row_is_the_same_in_all_three_mission_maps`, the Part 1 and Part 2 "marks ... here" tests) and `test_every_mission_map_agrees_with_the_series_map` in `tests/test_part_2_content.py`. Verify: `python -m unittest tests.test_series tests.test_part_1_content tests.test_part_2_content` passes.
- [x] 2.5 Update `docs/SPEC.md` and `docs/COURSE-CONTEXT.md` where they describe the mission maps or the repeated series framing. Verify: search both for "you are here" and "mission map" finds no stale statement.

## 3. Glossary and "AI window" (item 15)

- [x] 3.1 In `content/glossary.json`, replace the "CLI" entry with "AI window" (kind `course`, begins "In this course,") per the participant-vocabulary spec, and fix the "run" entry text that says "a new CLI process". Verify: `python -m unittest tests.test_lessons tests.test_part_1_content tests.test_part_2_content` (glossary checks) and the test from 1.2 pass.

## 4. "CLI" to "your AI" across participant text (item 15)

- [x] 4.1 List every string with "CLI" in `content/*.json` with a throwaway script (not committed); apply the D3 rule table file by file in context: `steps.json`, `part-1-steps.json`, `preflight.json`, `lesson-ui.json`, `lessons.json`, `settings.json`, `cli-recipes.json` (display text only: "Another CLI" to "Another AI tool"; keep "GitHub Copilot CLI" and "Devin CLI"). Verify: `python -m unittest tests.test_participant_vocabulary` shows no offender in `content/`.
- [x] 4.2 Change the hardcoded "CLI" strings in `web/index.html` (aria-label), `web/js/app.js`, `web/js/lessons.js`, `web/js/panels.js` and `web/js/views.js` to the same words, text only (authorized scope, rule 11). Do not change layout, styles, components or ids. Verify: the vocabulary test shows no offender in `web/` and `git`-free diff review of those files shows only string changes.
- [x] 4.3 Update tests and the stand-in harness that assert old text ("Start my CLI", "Send to CLI", "Your CLI", step and preflight messages): search `tests/`, `tests/frontend/` and `e2e-work/harness/` for each changed string. Verify: `python -m unittest discover -s tests`, then the interface tests (`node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`).
- [x] 4.4 Update `AGENTS.md` rule 10 to name "your AI" and "AI window" and "Practice task", and `docs/SPEC.md` where it quotes interface text. Verify: search `docs/SPEC.md` for the changed strings finds none stale.

## 5. Practice task and My own task (item 16)

- [x] 5.1 In `content/preflight.json` change `starter_northwind_label`, `starter_northwind_hint`, `northwind_note`, `starter_own_label`, its hint and `project_files_missing` to the Practice task and My own task wording in the spec (keep the keys). Verify: `python -m unittest tests.test_preflight tests.test_example_fixtures` pass after test updates in 5.3.
- [x] 5.2 Replace participant-visible "Northwind" in `lessons.json`, `part-1-lessons.json`, `part-2-lessons.json`, `part-1-steps.json` (not the `r3` client-group data), `part-2-steps.json`, `steps.json`, `series.json` and source labels, with "Practice task" and the practice-only sentence where the example is first introduced. Keep `kit:` refs, kit files, ids and the in-scenario client name. Verify: the 1.1 test shows no offender and `python -m unittest tests.test_content_banned_words` passes after 5.3.
- [x] 5.3 Rewrite the Northwind tests in `tests/test_content_banned_words.py` (learning example where introduced, never a submission, never used in place of own work) for "Practice task" and "practice only"; keep `test_the_northwind_examples_are_unchanged` and the skill byte-identity tests as they are. Verify: `python -m unittest tests.test_content_banned_words`.

## 6. Framework section and categories (item 14a)

- [x] 6.1 Rebuild the `p1-frameworks` idea passage: numbered five categories with the "five used in this course, more exist" statement, then one table each for RTCC and RISE (Letter, Label, What you write there, Covers category) per design D2. Keep the `fw-map` activity ids and answers. Verify: `python -m unittest tests.test_part_1_content` after 6.4.
- [x] 6.2 Replace "kind(s)" with "category/categories" where it means the five groups in `part-1-lessons.json` (about 36 uses, including `win`, activity prompts, feedback, source labels and `why`), `part-1-steps.json` (`rewrite.why`), `glossary.json` (prompting framework entry), and `kit/part1/frameworks-map.md` and `kit/part1/typical-gaps.md`; leave other senses of "kind" and Part 2's "both kinds". Verify: a test scans those files for "kind" with an explicit allow-list of the other senses.
- [x] 6.3 Keep CRISP out of Part 1: add a test that no Part 1 lesson, step, kit file or glossary entry names CRISP. Verify: `python -m unittest tests.test_part_1_content`.
- [x] 6.4 Update `tests/test_part_1_content.py` assertions that use "other kinds exist", "five common kinds", "Our five are an example, not a full list", "add the kinds your task needs" and "kind 4/5 fits only partly" to the new wording, and the table-shape test to expect two tables with a row per letter. Verify: `python -m unittest tests.test_part_1_content`.

## 7. Tracks and Series map intro (items 17, 19)

- [x] 7.1 In `content/preflight.json` set `ui.track_options` hints to the level-based sentences from design D6, remove "default" and "needs nothing extra" wording from the track messages (`track_script`, `track_promptfoo`) and keep the names "Script track" and "promptfoo track". Verify: a content test finds no "default", "recommended" or "best" about a track, and `python -m unittest tests.test_preflight`.
- [x] 7.2 Check whether the Track page preselects a track; if it does, record it in `docs/IMPLEMENTATION-PLAN.md` as a finding and leave it (design Q7). Verify: Playwright interface tests still pass.
- [x] 7.3 Set `content/series.json` `ui.intro` to the doing-it-yourself line (no "look ahead", no "Stage 3"). Verify: `python -m unittest tests.test_series` with a new intro test.

## 8. Docs, build and end-to-end

- [x] 8.1 Update `docs/IMPLEMENTATION-PLAN.md` (task table and a section for this change) and mark change 1 as proposed and applied in `docs/temp/series-review-pending-changes.md`; update `docs/PHASE3.md` content rules for the new words. Verify: the master task table matches the phase sections.
- [x] 8.2 Run the full checks one after the other: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests`, then the Playwright command from `AGENTS.md`. Verify: all pass; rerun `test_conpty.RealConsole.test_type_line_sends_enter_separately` once if it alone fails.
- [x] 8.3 Rebuild and smoke test: `python tools\build_pyz.py --smoke`. Verify: it exits 0.
- [x] 8.4 Run the stand-in end-to-end: `node e2e-work\harness\run-all.js --fresh` for the Script track, writing output to a file, then `--track promptfoo`. Verify: both pass and the harness text checks for changed wording are updated.

## Workflow follow-up

- Archive the change after review; the archive summary lists which `docs/SPEC.md` sections are superseded.
- Next in the series review order: guided-setup (change 2) builds on this vocabulary.
