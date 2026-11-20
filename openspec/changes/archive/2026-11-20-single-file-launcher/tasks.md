# Tasks

## 1. Launcher script and build

- [x] 1.1 Rename `packaging\setup.cmd` to `packaging\launcher.cmd` with `git mv`. Set `EC_PYZ` to `%~f0`, remove the `fail_no_pyz` check and its message, pass `%*` and `-B` on the launch line, end the script with the marker line `rem ===== eval-coach.pyz follows =====`, and reword every message to say "eval-coach" (never `setup.cmd`). Verify: `python -m unittest tests.test_setup_cmd.ScriptShapeTests` passes after task 1.4 updates it.
- [x] 1.2 Rewrite `:probe_wait` and `:rename_runtime` as forward-only `for /l` loops with the same limits (10 probe polls, 15 rename tries) and the same messages. Verify: `DetectionTests` and `test_no_python_installs_private_copy_and_launches` in `tests\test_setup_cmd.py` pass on the assembled file.
- [x] 1.3 Rewrite `:ask` as a forward-only form that still asks at most three times and treats no answer as "no". Verify: `test_unclear_answer_asks_again`, `test_no_answer_at_all_counts_as_declined` and `test_declined_consent_exits_cleanly_with_next_step` pass.
- [x] 1.4 Add `assemble_launcher(script_bytes, pyz_bytes)` to `tools\build_pyz.py` (script, marker line, archive bytes), make `build()` also write `dist\eval-coach.cmd`, and make `--smoke` start both the `.pyz` and the `.cmd` on the embedded Python (static files and kit load). Verify: `python tools\build_pyz.py --smoke` prints both checks passing and `dist\eval-coach.cmd` exists.

## 2. Tests

- [x] 2.1 Update `tests\test_setup_cmd.py`: `put_package` writes one file by assembling `packaging\launcher.cmd` with the stub archive through `assemble_launcher`; `ScriptShapeTests` check CRLF and ASCII on the script part only (split on the marker) and that the part after the marker opens as a zip; drop `test_missing_pyz_explains_how_to_extract`; change "run setup.cmd again" assertions to the new wording. Verify: `python -m unittest tests.test_setup_cmd` passes.
- [x] 2.2 Add a script-shape test that fails when the script part has a `goto` or `call :label` whose label is defined earlier in the script part, plus a test that a launcher alone in an empty folder, and one in a folder named `My Files & (Old)!`, starts the stub app. Verify: `python -m unittest tests.test_setup_cmd` passes, and temporarily adding a backward `goto` to a copy makes the new test fail.
- [x] 2.3 Update `tests\test_integration_setup.py` to run the built `dist\eval-coach.cmd` alone in its folder with no sibling file, and still check `/api/state`, the quit call and that the real profile is untouched. Verify: `python -m unittest tests.test_integration_setup` passes.

## 3. Participant wording

- [x] 3.1 In `app\eval_coach\content\preflight.json`, change `python_missing`, `python_too_old`, `check_error` and `cli_not_found_after_install` so the next step says to close the window and start eval-coach again, with no file name; change the `--python` help text in `app\eval_coach\__main__.py`; change the fixture string in `tests\frontend\ui.spec.js`. Verify: `python -m unittest tests.test_participant_vocabulary` and the preflight content tests pass, and `grep -ri "setup\.cmd" app tests` finds nothing outside this change's own test names.
- [x] 3.2 Run the interface tests for the preflight pages. Verify: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` passes.

## 4. Documentation

- [x] 4.1 Update `README.md` (packaging row, layout list, "Participants start the app by..." line), `docs\SETUP.md` (Distribution, Stage 1, Tests: one file, appended archive, no backward jumps rule), `docs\SPEC.md` (layout lines for `packaging/` and `tools/build_pyz.py`) and `AGENTS.md` (layout line, the `setup.cmd` integration test note, and the plain-ASCII and CRLF rule restated for the script part only). Verify: `grep -rn "setup\.cmd" README.md docs AGENTS.md` shows only deliberate history mentions.
- [x] 4.2 If `docs\local\IMPLEMENTATION-PLAN.md` exists on this machine, update Phase 5 items 5.1 and 5.4 and Phase 6.2 to name `eval-coach.cmd`; never stage it. Verify: the file reads consistently, or skip with a note if absent.

## 5. Integration checks

- [x] 5.1 Build with `python tools\build_pyz.py --smoke`, then double-click-equivalent run: start `dist\eval-coach.cmd` alone from a folder with spaces and `&` under a normal PATH, and once with a scrubbed PATH and the private runtime present, checking the page answers and the launcher exits cleanly after quit. Verify: both runs reach `/api/state` with status 200.
- [x] 5.2 Run the two backend suites one after the other (`python -m unittest discover -s tests`, then the embedded 3.13 run from AGENTS.md) and the stand-in end-to-end (`node e2e-work\harness\run-all.js --fresh > e2e-work\receipt-e2e.txt`). Verify: all pass; record receipts with `tools\verify_receipt.py` as the archive gate says.

## Workflow follow-up

- Ask the user to run `dist\eval-coach.cmd` once on a company-managed computer and report whether security software blocks it (design Risks); if it does, switch to option B.
- Phase 5 tasks 5.2 to 5.7 (distribution, pinned values recheck) and Phase 6.2 (live console run) wait for the user's go-ahead.
- Archive the change after the verification gate, then offer the post-archive PR.
