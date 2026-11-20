# Proposal

## Why

Today a participant receives two files, `setup.cmd` and `eval-coach.pyz`, and must know to run the `.cmd` and leave the `.pyz` beside it. The `.pyz` does nothing on a computer without Python, and double-clicking `setup.cmd` from inside the zip stops with a "missing file" message because Windows extracts only that one file. A first launch should be one double-click on one file: it finds or installs Python, then opens the app.

A spike (2026-11-20, throwaway folders, nothing kept) showed this is feasible: Python runs a `.cmd` file that has the app archive appended to it, and the real launcher started the app and served the page from such a file. It also found one cmd quirk that decides the design: once the file contains binary data, any backward `goto` silently fails. That broke the Python search in the real script, so the three loops that use one must be rewritten.

## What Changes

- Build one participant file, `dist\eval-coach.cmd`: the launcher script followed by the app archive. Double-clicking it runs the launcher, and the launcher runs the app from its own file.
- Rename the source `packaging\setup.cmd` to `packaging\launcher.cmd` and make it start the app from itself (`%~f0`) instead of from a sibling `eval-coach.pyz`. It passes any command-line arguments through to the app so tests and the smoke check can use `--no-browser --port 0 --home`.
- Remove the "missing sibling file" stop (`fail_no_pyz`): a single file has nothing to be separated from.
- Rewrite the three loops that use a backward `goto` (`:ask`, `:probe_wait`, `:rename_runtime`) so they only move forward, with the same visible behavior: up to three asks, a 10-second probe timeout, and up to 15 rename retries.
- Change `tools\build_pyz.py` to build the archive as before and then assemble `dist\eval-coach.cmd` (launcher text, a marker line, then the archive bytes). `dist\eval-coach.pyz` is still produced, because the end-to-end harness and the smoke check use it.
- Reword the four setup messages in `preflight.json` that tell participants to "run setup.cmd again", so they say to start eval-coach again, without a file name.
- Update the tests that run the launcher, add a test that fails if the launcher script uses a backward `goto` or `call`, and update `README.md`, `docs/SETUP.md`, `docs/SPEC.md` and `AGENTS.md`.
- Replace the planned `eval-coach.zip` with two files (Phase 5 task 5.1) by the single `eval-coach.cmd`. How participants receive that one file stays with the user.

## Capabilities

### New Capabilities
- `single-file-launcher`: what a participant sees when they double-click the one eval-coach file: how it finds Python, asks before installing a private copy, starts the app from itself, and explains each failure with a next action.

### Modified Capabilities
<!-- None. No existing openspec/specs capability covers the launcher. The wizard's Python page is unchanged apart from four sentences of wording. -->

## Impact

- **Code and build:** `packaging\setup.cmd` (renamed to `launcher.cmd`), `tools\build_pyz.py`, `dist\` output (generated).
- **Content:** four strings in `app\eval_coach\content\preflight.json` (`python_missing`, `python_too_old`, `check_error`, `cli_not_found_after_install`). This is setup failure wording, not layout or styling. AGENTS.md rule 11 lists `web/`, `lesson-ui.json` and step `ui` blocks, not `preflight.json`; the wording change is treated as covered by this request and is listed as an open question in the design for confirmation.
- **Tests:** `tests\test_setup_cmd.py`, `tests\test_integration_setup.py`, and a fixture string in `tests\frontend\ui.spec.js`.
- **Docs:** `README.md`, `docs\SETUP.md`, `docs\SPEC.md`, `AGENTS.md`.
- **Unchanged:** the app's behavior and API, the pinned Python version and SHA-256, the private runtime location, and the in-app setup wizard.
- **Rules kept:** the launcher stays cmd-only with full-path Windows tools, plain ASCII and CRLF for its script part, no administrator rights, and consent before any download (AGENTS.md "Non-negotiable rules" 4 and 5, `docs/SETUP.md` Stage 1).

## Out of scope

- A Mac or Linux launcher (Phase 7 stays deferred).
- Code signing, antivirus or SmartScreen exemptions, and removing the Windows "downloaded file" warning.
- Checking or installing Node.js, promptfoo or the AI tool from the launcher. The in-app setup wizard keeps those.
- Building the participant zip, deciding how the file is shared, and the live-console run (Phase 5 tasks 5.2 to 5.7 and Phase 6.2), which need the user's go-ahead.
- Changing the interface, the wizard pages, or any other participant text.
- Changing the pinned Python version, its download address or its hash.
