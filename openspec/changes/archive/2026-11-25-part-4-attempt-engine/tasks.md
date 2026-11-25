# Tasks

## 1. Log parser and shared check helpers

- [x] 1.1 Add the `Decision` field to `parse_iteration_log` (`parsers.py`) with tests in `tests/test_iteration_log.py` for `kept`, `undone`, `pending`, a missing field and an unknown value. Verify: `python -m unittest tests.test_iteration_log tests.test_parsers`.
- [x] 1.2 Add a test that a log with entries 0, 1 and 2 gives the same Part 3 baseline gate result as one with entry 0 only. Verify: `python -m unittest tests.test_baseline_step`.
- [x] 1.3 Make `baseline.run_checks`, `summarize` and `runs_hash` accept any object with the accessors they use, and add `AttemptPaths` (`project.py`) rooted at `part-4\attempts\<n>\`. Verify: Part 3 tests unchanged (`python -m unittest tests.test_baseline_step tests.test_engine_gates`) and a new test that runs both on an attempt folder.

## 2. Attempt storage and manifest

- [x] 2.1 Register Part 4 in `state.py` (own `progress_key`, default step records, no shared ids) with `series.json` left at "soon". Verify: `tests/test_parts.py` and `tests/test_series.py` pass and a new test shows no duplicate ids and an unchanged Series map.
- [x] 2.2 Create an attempt from the kept version with create-only copies and a recorded parent. Verify: new `tests/test_part_4_attempts.py` covers attempt 1 from Iteration 0, attempt 2 from attempt 1, Part 3 file bytes unchanged and an existing file never overwritten.
- [x] 2.3 Store the manifest in `parts.part-4` with hashes and counts only, and load older progress with it empty. Verify: tests that the manifest holds no text and that earlier `progress.json` files load unchanged.
- [x] 2.4 Derive the kept pointer and apply explicit keep and undo. Verify: tests for the undone-second-edit case, a pending latest attempt and refusing a decision on an unscored or stale attempt.

## 3. Hypothesis and scoring on both tracks

- [x] 3.1 Add the hypothesis step handler: save `hypothesis.md`, record its hash, refuse run and score without it, refuse edits after the run. Verify: tests for each refusal with plain messages.
- [x] 3.2 Score an attempt on the Script track with `check.py` in the attempt folder and save `results.json`. Verify: a stand-in based test checks per-criterion counts, a stale result after a changed run file and a flagged coverage change.
- [x] 3.3 Score an attempt on the promptfoo track from the copied config without editing the original. Verify: `tests/test_promptfoo_track.py` style test with the stand-in config checks the original bytes are unchanged and results match the Script-style summary.

## 4. Known-good check

- [x] 4.1 Save the known-good answer and score it only after it exists (Script track on the file; promptfoo track by adding the `known-good` test with copied assertions to the attempt's config). Verify: tests that no score is returned before the file exists and the checker hash is unchanged by the added test but changes for any other edit.
- [x] 4.2 Report the known-good result apart from the five-answer score, with a next step below 95% that never loosens a rule, and require a rerun of the original five answers when a repair changes Iteration 0's verdicts. Verify: tests for 95% or more, below 95%, and the repair case.

## 5. Log gate and completion

- [x] 5.1 Add the Part 4 log gate: one entry per attempt, decision matches the manifest, Hypothesis matches the saved text, and counts and NOT CHECKED items match `results.json` by reusing the Part 3 helpers. Verify: tests for each mismatch message and a clean pass.
- [x] 5.2 Add completion (two fresh, documented rounds after Iteration 0, five-answer score a target only) with the evidence wording "measured gain" and "no measured gain on these rules". Verify: tests for two rounds below target passing, one round not passing, and flat and reverted attempts never described as gains; `tests/test_participant_vocabulary.py` still passes.

## 6. Docs and integration

- [x] 6.1 Update `docs/SPEC.md` "Evidence handoff" to mark the attempt side built and add the manifest, attempt folder and gate behavior; keep `docs/local` in step if present, never staged. Verify: read the section against the code and tests.
- [x] 6.2 Run the backend suites one after the other and the build smoke test. Verify: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests`, then `python tools\build_pyz.py --smoke` all pass. Record them with `tools\verify_receipt.py` at the archive gate.

## Workflow follow-up

- Slice B (Part 4 course content and the worked Practice task) and slice C (harness stages) are separate changes. Slice B needs the user's authorization for any interface change and a source for the worked edits and results.
- Archive this change after the verification gate, then ask about the branch and pull request.
