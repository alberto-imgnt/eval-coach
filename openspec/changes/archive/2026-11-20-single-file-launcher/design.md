# Design

## Context

Today `packaging\setup.cmd` (CRLF, ASCII, cmd.exe and `%SystemRoot%\System32` tools only) finds or installs Python and then runs `eval-coach.pyz` from its own folder with `--python <path>`. The app, the in-app setup wizard and the test seams are described in `docs/SETUP.md` Stage 1. See proposal.md for why one file is wanted.

A spike on 2026-11-20 (throwaway folders, since deleted) established four facts this design relies on:

1. `python eval-coach.cmd` runs a zip archive that has text in front of it; the extension does not matter. Checked on Python 3.12 and the embedded 3.13.17.
2. cmd.exe runs the text part, stops at an `exit /b`, and never reads the bytes after it. The real server started from such a file in a folder named `ec-spike & (test)` and answered HTTP 200. Windows Defender found nothing in the combined file.
3. cmd searches for a label from the current line to the end of the file before it wraps to the start. If a NUL byte is reached, that search ends silently, so a backward `goto :label` falls through. With the real script this made the Python search report "not found" on a computer that has Python: `:probe_wait` was the first backward jump, and the probe returned after one loop. One NUL byte after the script was enough; a Ctrl-Z marker did not help. Forward `goto` and `call :label` to labels later in the file were not affected, and a large text-only tail (8,000 lines) was not affected.
4. With `:probe_wait` rewritten as a forward-only `for /l` loop, the real launcher plus the real app launched and served HTTP 200 in about 2 seconds.

## Goals / Non-Goals

**Goals:**
- One shipped file, `dist\eval-coach.cmd`, that behaves as `setup.cmd` does today, except that it starts the app from itself.
- The launcher's behavior (detection order, consent, SHA-256 pin, messages, exit codes) stays the same, apart from the file name in messages.
- A guard that stops the backward-jump problem returning silently.

**Non-Goals:**
- Any change to the app, the wizard pages, the pinned Python, or the private runtime location.
- Distribution (zip, share location), signing, or a Mac launcher (see proposal Out of scope).

## Decisions

**D1. The shipped file is the launcher text followed by the app archive.** The build writes `launcher text` + marker line + `.pyz bytes`. The launcher ends with `exit /b` before the marker, so cmd never reads the archive; Python ignores the text because a zip is found from its end-of-file directory.
- *Alternatives:* (B) keep two files and rename `setup.cmd` to something clearer. Smaller change, but the "alone in a zip" failure and the two-file confusion remain. (C) embed the archive as base64 text and decode it with `certutil -decode`. This avoids the NUL quirk, but endpoint-protection tools often flag `certutil -decode` of an embedded payload, and the file grows by a third. A is chosen; B is the fallback if the user's security software rejects the combined file (see Risks).

**D2. The marker line is the boundary between the script and the archive.** The last script line is `exit /b %EC_RC%` style code, followed by one marker line `rem ===== eval-coach.pyz follows =====` and a CRLF. Tests split the file on the marker to check the script part (CRLF only, ASCII only, no backward jumps) and to check that the rest is a valid zip. `build_pyz.py` exposes one function, `assemble_launcher(script_bytes, pyz_bytes)`, and the tests call it so they build the file the same way the build does.

**D3. The app is started from the launcher file itself.** `EC_PYZ` becomes `%~f0`. The launch line becomes `"%EC_PY%" -B "%EC_PYZ%" --python "%EC_PY%" %*`. `%*` is new and passes `--no-browser`, `--port` and `--home` for tests and the smoke check; a double-click passes nothing. The `fail_no_pyz` check and its message are removed, since the file always contains the app. `-B` stops Python writing `__pycache__` next to the participant's file.

**D4. The three backward loops become forward-only, with the same behavior.**
- `:probe_wait` (10 polls of `ping -n 2`): replace with `for /l %%I in (1,1,%EC_PROBE_TIMEOUT%) do if not exist "%EC_DONE%" "%EC_SYS%\ping.exe" -n 2 127.0.0.1 >nul`, then `if exist "%EC_DONE%" goto probe_finished` and `goto probe_hung`. This is the version the spike ran.
- `:rename_runtime` (up to 15 tries, one second apart): the same `for /l` form around the `ren` and `if exist` check.
- `:ask` (up to three tries): unrolled into three forward blocks, or a `for /l` over `set /p`, whichever the tests show keeps `set /p` reading from a redirected file correctly. This one has no spike evidence yet, so it is the riskiest edit; `test_unclear_answer_asks_again` covers it.
- A new test fails if the script part contains a `goto` or `call` whose target label appears earlier in the script part. This turns the silent failure found in the spike into a loud one.

**D5. Names.** The source is renamed `packaging\launcher.cmd`; the product is `dist\eval-coach.cmd`. "setup" stays the word for the in-app wizard only, so the participant does not meet two different things called setup. Launcher messages say "eval-coach" (for example "start eval-coach again"), never a file name, so a rename later changes no text.

**D6. `dist\eval-coach.pyz` is still built.** The end-to-end harness (`e2e-work\harness\lib.js`, `real-paste*.js`) and `--smoke` use it. `build_pyz.py` builds the archive, then assembles `dist\eval-coach.cmd` from it, and `--smoke` runs both: the `.pyz` as today, and the `.cmd` started with the embedded Python and the same file and kit checks.

**D7. No change to detection or install code.** Only the file name in messages, `EC_PYZ`, the dropped sibling check, `%*`, and the three loops change. Probe, consent text, download, SHA-256 check and unpack are copied as they are.

## Files and storage touched

| Location | Change | Kept or cleared |
|---|---|---|
| `packaging\setup.cmd` | renamed to `packaging\launcher.cmd`, edited per D3 to D5 | source, kept in git |
| `dist\eval-coach.cmd` | new generated file | generated, rebuilt each build |
| `dist\eval-coach.pyz` | unchanged | generated, kept |
| `tools\build_pyz.py` | adds `assemble_launcher` and the smoke run on the `.cmd` | kept |
| `app\eval_coach\content\preflight.json` | four strings: `python_missing`, `python_too_old`, `check_error`, `cli_not_found_after_install` | kept |
| `app\eval_coach\__main__.py` | help text of `--python` only ("setup.cmd sets this") | kept |
| `tests\test_setup_cmd.py`, `tests\test_integration_setup.py`, `tests\frontend\ui.spec.js` | updated for the single file and new wording | kept |
| `README.md`, `docs\SETUP.md`, `docs\SPEC.md`, `AGENTS.md` | file name, packaging and layout lines | kept |
| `.gitattributes` | no change needed: `* -text` already keeps bytes as written | kept |
| `%USERPROFILE%\.eval-coach\runtime\python` | unchanged: still the only thing the launcher installs | kept across updates |
| `<home>\progress.json`, `preflight.json` and project folders | untouched by the launcher | kept |
| `%TEMP%\ec-setup-*` | per-run work folder, as today | cleared at launch or exit |

## Risks / Trade-offs

- **[Security software rejects a script with an appended binary]** The spike only tested Windows Defender on this machine. → Keep option B ready (same launcher, `.pyz` shipped beside it as one folder); the build can emit both because D6 keeps the `.pyz`. Ask the user to try the built file on a managed work laptop before Phase 5.
- **[A future edit adds a backward `goto` and the Python search breaks silently]** → The D4 test fails the build; the rule is added to the header comment of `launcher.cmd` and to `docs\SETUP.md`.
- **[The `:ask` rewrite changes how `set /p` reads redirected input]** → `test_unclear_answer_asks_again` and `test_no_answer_at_all_counts_as_declined` run the real script; if neither can be made to pass with a forward-only form, fall back to reading the answers in one `for /f` over the redirected input.
- **[Update with a running app]** Replacing the file while the app runs may fail because Windows locks it. → The existing "close every window" wording stays; no code change.
- **[Mark of the Web]** A downloaded `.cmd` shows the Windows "Open File – Security Warning" prompt, as `setup.cmd` does today. → Out of scope; mention in the release note.
- **[Larger file]** About 590 KB instead of 18 KB plus 570 KB: no net change.
- **[Python 3.9 reading a prefixed zip]** The spike ran 3.12 and 3.13. → The two backend suites and the integration test run on both; Python 3.9 uses the same pure-Python zip reader, and any 3.9 machine is checked in the Phase 6 run.

## Migration Plan

1. Land the change; `dist\eval-coach.cmd` is built by the same command as today.
2. Docs and the Phase 5 plan now name one file; Phase 5 tasks 5.2 to 5.7 and Phase 6.2 stay with the user's go-ahead and apply to `eval-coach.cmd`.
3. Rollback: revert the commit. The old `setup.cmd` plus `.pyz` pair can be rebuilt from git history; nothing on participant computers needs undoing, because the launcher writes only to the same private runtime folder as before.

## Open Questions

- **Final file name.** Assumed `eval-coach.cmd`. Confirm, or name another (for example `Start eval-coach.cmd`).
- **Setup failure wording.** Four strings in `preflight.json` change from "run setup.cmd again" to "start eval-coach again". AGENTS.md rule 11 does not list this file, so it is assumed covered by this request. Confirm.
- **Phase 5 item 5.1.** Assumed that "build `eval-coach.zip` with exactly two files" is replaced by this single file, and that whether it is also zipped is decided later with the distribution choice (D3 in the plan). Confirm.
- **Managed-laptop check.** Assumed the user will try `dist\eval-coach.cmd` on a company-managed computer after the build and say if security software blocks it; if it does, the fallback is option B.
