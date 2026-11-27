# Tasks

## 1. Authored worked answers and the Practice checker

- [x] 1.1 Add the ten authored worked answers (five per round) under `tests/golden/part4-worked/` and `tests/test_part_4_worked.py`, which scores them with `tests/golden/reference-check.py` and asserts Iteration 0 is 25 of 30 (C5 3 of 5), round 1 is 26 of 30 (C5 5 of 5, C6 4 of 5, C1 to C4 unchanged) and round 2 is 26 of 30 with the same per-rule counts. Every answer keeps the six C6 keywords except the one meant to lose "lunch". Verify: `python -m unittest tests.test_part_4_worked`.
- [x] 1.2 Add `kit/part4/practice/check.py` (the reference checker's logic with practice wording), `promptfooconfig.yaml` (from `tests/golden/promptfoo/promptfooconfig.yaml`) and `iteration-log.md` (Iteration 0 already filled in). Test that the script gives the reference checker's per-rule counts on the five sample answers, that the config gives the same counts when the private Node is present (skip otherwise), and that the log entry's counts and NOT CHECKED items equal the checker's, using `gates.baseline_count_problems`. Verify: `python -m unittest tests.test_part_4_practice` (new file, the checker and log cases).

## 2. Engine: baseline object, presence check, optional steps

- [x] 2.1 Add the baseline object (`OwnBaseline`, `PracticeBaseline`), `PracticePaths` and the `AttemptPaths` base folder, and make `Attempts` read Iteration 0 through it. Save `parts.part-4.start` (absent means `"own"`; set once; refused after attempt 1 exists). Verify: `python -m unittest tests.test_part_4_attempts tests.test_baseline_step tests.test_engine_gates` still pass, plus new cases in `tests/test_part_4_practice.py` for attempt 1 from the Practice files, the participant's own bytes unchanged, an existing Practice file never overwritten and the switch refused after round 1.
- [x] 2.2 Add the seventh log gate item (Change, Result and Reasoning present, presence only) with messages in `content/part-4-attempts.json`. Verify: new cases in `tests/test_part_4_attempts.py` for empty Reasoning, any text passing, and Part 3's baseline gate unchanged with entries 0, 1 and 2.
- [x] 2.3 Add `optional_steps` to `state.Part`, excluded from the Part's done count and Done state, unlocking in their own order after the last required item. Leave `OPTIONAL_STEP = "live"` untouched. Verify: `python -m unittest tests.test_parts tests.test_series tests.test_course_locking` unchanged, plus a new case that a Part with optional steps is Done without them and counts only required items.
- [x] 2.4 Register Part 4 in `PARTS` with the new round-suffixed ids and `restart=None`, remove it from `DARK_PARTS`, add `part4` to `reset.HOME_SCRATCH` and keep the Practice folder on the reset inventory. Verify: `python -m unittest tests.test_parts tests.test_reset tests.test_course tests.test_http_course` pass, a new test in `tests/test_parts.py` shows no duplicate ids across Parts, and the Part 4 restart request is refused.

## 3. Step kinds

- [x] 3.1 Add `attempt_steps.py` with the `choose_start`, `known_good` and `hypothesis` kinds, registered through `state.register_step_kind`, actions through `/api/step/submit`. Verify: `python -m unittest tests.test_part_4_steps` covers the starting-point choices and refusals, the known-good score hidden until saved and blocked under 95%, and the hypothesis lock and the edit step staying locked without one.
- [x] 3.2 Add the `edit` and `decide` kinds: the edit step saves only the round's own copy and needs a changed prompt; the decide step records keep or undo, shows the log line only after a decision, and runs the log gate. Verify: new cases in `tests/test_part_4_steps.py` for no change made, stale refusal, keep and undo moving the kept version, the undone-second-edit case, and every gate message including the presence item, with `iteration-log.md` bytes unchanged.
- [x] 3.3 Add the `measure` kind: the blind folder under `<home>\part4\blind\`, one fresh AI window per run, the output watcher saving into the attempt's next empty run, the model recorded in the step's own record, and an explicit score action. Verify: stand-in tests with `e2e-work/harness/fake_cli.py` for five runs on both tracks, the model note, run without a hypothesis refused, the original config bytes unchanged and no answer typed by the app.

## 4. Course content and the reveal

- [x] 4.1 Add the activity `reveal` (returned only on pass) to `lessons.py` and the validator, keeping existing activity views unchanged. Verify: `python -m unittest tests.test_lessons` plus new cases that no response before the pass holds the reveal and that it is returned after.
- [x] 4.2 Write `content/part-4-lessons.json`: `p4-mission` (four passages, at most 450 words), the five lessons with activities, retrieval, `kit:` sources, glossary links and step Quick checks, including the six-rule prediction `sort` with the worked reveal and the closing reflection on `decide-2`. Verify: `lessons.validate_course` passes for Part 4, `python -m unittest tests.test_part_4_content` covers the order, word caps (300, 450, 400), equal-length options, the lesson shape, no early reveal and that the lesson's per-rule table equals the numbers task 1.1 computes.
- [x] 4.3 Write `content/part-4-steps.json` (step words, line templates, gates, troubleshooting, messages) and the glossary terms (hypothesis, iteration, red green refactor, known-good answer, kept version, measured gain on these rules, coverage change). Verify: `python -m unittest tests.test_part_4_content tests.test_participant_vocabulary tests.test_learning_priorities tests.test_content_banned_words tests.test_part_terminology` pass, including no "did not help", "no benefit" or "did better", no Stage 3 or certification wording, and "Practice task" never offered as a submission.
- [x] 4.4 Activate the Series map row in `series.json` (`kind: "course"`, `skip` text, `ui` block with course groups and finished text; Part 5 stays "Coming soon"). Verify: `python -m unittest tests.test_series tests.test_course tests.test_http_course` and a new case that the Part 4 row shows state, count and an open control, with the Part 5 and Part 6 rows unchanged.

## 5. Interface (authorized, additive panels only)

- [x] 5.1 Add `web/js/attempt-steps.js` with a panel for each Part 4 step id, built from existing components and styles, and one import and spread in `panels.js`. No existing panel, layout, style, id or copy changes. Verify: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` for the existing specs unchanged.
- [x] 5.2 Add `tests/frontend/part4.spec.js` covering the starting-point choice, the hypothesis lock, the five-run list and per-rule table, keep or undo with the log gate, the prediction and reveal, the Series row and locking, on both tracks. Verify: the Playwright command above passes the new spec.

## 6. Docs and integration

- [x] 6.1 Update `docs/SPEC.md` (a Part 4 section; "Evidence handoff" attempt side with the Practice baseline, the presence item and the step ids), `docs/CONTENT-RULES.md` (the Parts table row and the Stage 3 map rows that say "Part 4, not built") and `docs/RUNNING-EVALS-COURSE.md` (its note that Parts 4 and 5 are not built); keep `docs/local/IMPLEMENTATION-PLAN.md` in step if present, never staged. Verify: read each section against the code and tests, and `python -m unittest tests.test_participant_vocabulary` still passes.
- [x] 6.2 Run the backend suites one after the other, then the interface suite and the build smoke test, and record them for the archive gate with `tools\verify_receipt.py`. Verify: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests`, then the Playwright command, then `python tools\build_pyz.py --smoke`, all pass.

## Workflow follow-up

- Slice C (issue #19) adds the harness stages and end-to-end coverage for Part 4; it is a separate change.
- One real run per tool of the `decide` log line and, on the promptfoo track, the Practice config needs the user's approval; the stand-in covers the app's side.
- Archive this change after the verification gate, then ask about the branch and pull request.
