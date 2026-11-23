# Tasks

Verification commands are from AGENTS.md. Run the two backend suites one after the other. Never run a real AI without the user's approval (single-use Yes per tool). Groups 2 to 7 leave Windows behavior unchanged: after each, the Windows backend suite must still pass.

## 1. Facts and rules first

- [x] 1.1 Verify the three AIs' Mac install commands, sizes and sign-in needs against each vendor's own documentation, and write them (command, shell, size, plain description, source) into a short table in `docs/SETUP.md`. Verify by showing the table to the user before any recipe is written.
- [x] 1.2 Re-fetch the pinned Mac values (python-build-standalone release asset names, sizes and SHA-256; Node 26.13.0 `darwin-arm64` and `darwin-x64` tarballs and their `SHASUMS256.txt` hashes) and confirm each matches the design's values or update the design. Verify by running `curl.exe -sL https://nodejs.org/dist/v26.13.0/SHASUMS256.txt` and `gh api repos/astral-sh/python-build-standalone/releases/latest` and comparing.
- [x] 1.3 Amend AGENTS.md rule 5 (add GitHub release downloads for the private Mac Python, consent first, fixed hash), rule 13 (name `conpty.py`, `ptyterm.py`, `hostos.py` and the launchers), the status text, and the `openspec/config.yaml` context line that says "Windows learning app". Verify with `rg -n "Windows learning app|Mac is deferred" AGENTS.md openspec/config.yaml docs` showing no stale wording.

## 2. Platform seams (Windows unchanged)

- [x] 2.1 Add `app/eval_coach/hostos.py` with `IS_MAC`, `IS_WINDOWS`, `kill_tree`, `popen_flags`, download and extract argv, recipe shell argv, extra PATH directories, Node pin and layout helpers; Windows returns exactly today's literals. Add `tests/test_hostos.py` covering both platforms with the platform value injected. Verify: `python -m unittest tests.test_hostos`.
- [x] 2.2 Switch `preflight.py` (CURL, TAR, TASKKILL, CMD, POWERSHELL, `CREATE_NO_WINDOW`, `read_registry_paths`, Node constants, `node.exe` and npx paths, `_recipe_shells`) to `hostos`, plus `promptfoo.py` and `runner.py` flags. Verify: `python -m unittest tests.test_preflight tests.test_promptfoo_track tests.test_setup_gate` unchanged and green on Windows.
- [x] 2.3 Make `terminal.py` choose the terminal class by platform and stop importing Windows code on a Mac; make `_with_terminal_hint` use `hostos` for the marker. Verify: `python -m unittest tests.test_http tests.test_live_mode` green on Windows.
- [x] 2.4 Fix the `--home` help text in `__main__.py` and the default-folder comments to be platform-neutral. Verify: `python -m app.eval_coach --help` text (run as `python -m eval_coach --help` from `app`) names no `%USERPROFILE%` on a Mac and the same text on Windows.

## 3. Mac terminal

- [x] 3.1 Add `app/eval_coach/ptyterm.py` (`PosixPTY` with the `ConPTY` public surface, new session and process group, `TIOCSWINSZ` resize, group `pids`, escalating `close`). Add `tests/test_ptyterm.py` (skipped on Windows): round trip with a small Python child, resize seen by the child, exit code, `close` ends a child and a grandchild, output ring buffer limit. Verify: `python -m unittest tests.test_ptyterm` on a Mac or macOS CI.
- [x] 3.2 Add POSIX command resolution (executable check, `shutil.which`, shebang left to the OS) and make `test_conpty.py` and other Windows-only tests skip on a Mac with a reason. Verify: `python -m unittest tests.test_conpty` is skipped on macOS and unchanged on Windows.
- [x] 3.3 Run the stand-in `fake_cli.py` through `PosixPTY` and the quiet background test with its time limit and process-group stop. Verify: a new test in `tests/test_ptyterm.py` and `tests/test_preflight.py` (Mac branch), run on macOS CI.

## 4. Mac setup and installs

- [x] 4.1 Mac Node install in `preflight.py`: `darwin-arm64` or `darwin-x64` tarball, `tar -xzf`, hash check, run `node --version`, move to `runtime/node`; `_npx_argv` uses `lib/node_modules/npm/bin/npx-cli.js`; macOS 13.5 floor message. Verify: `tests/test_preflight.py` Mac cases with a fake runner, including wrong hash and old macOS.
- [x] 4.2 Mac PATH discovery for AIs installed while the app is open (`~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, the AIs' own folders) without starting any AI. Verify: Mac cases in `tests/test_preflight.py` using a temporary home.
- [x] 4.3 Mac Python check on the wizard's Python page: path shown, version rule, message to start eval-coach again, private Python at `runtime/python/bin/python3` in `Preflight.env()`. Verify: Mac cases in `tests/test_preflight.py`.
- [x] 4.4 Add `platforms` (windows and mac) to `cli-recipes.json` from the table in 1.1, keeping every Windows value verbatim, and no CLI logic in code (rule 6). Verify: `python -m unittest tests.test_preflight tests.test_models` and a new test that every recipe has both platforms and that Windows values equal the committed baseline.
- [x] 4.5 Document the Mac setup in `docs/SPEC.md` and `docs/SETUP.md` (setup flow, pins, supported macOS versions). Verify by reading the sections against the spec requirements of `mac-runtime`.

## 5. Mac launcher and build

- [x] 5.1 Add `packaging/runtime-manifest.json` with the Windows and Mac pins, and make `build_pyz.py` stamp them into both launchers; add a test that a launcher and the manifest agree. Verify: `python -m unittest tests.test_launcher_manifest` (new) and `python tools\build_pyz.py` succeeds.
- [x] 5.2 Write `packaging/launcher.sh`: macOS version check, chip detection (including Rosetta), Python discovery with the Apple stub rule and per-run token probe, consent text, three tries, download with `curl`, SHA-256 with `shasum -a 256`, unpack to `python.new`, probe, rename, start the app, plain failure messages, hold the window on failure, `exit` before the archive. Use only bash 3.2 features and quoted paths. Verify: `sh -n packaging/launcher.sh` (or `bash -n`) and the tests in 5.4.
- [x] 5.3 Extend `tools/build_pyz.py` to write `dist/eval-coach.command` (script, marker line, archive) and `dist/eval-coach-mac.zip` with mode `0755` on the command file; `--smoke` starts the app from each launcher on the platform it can. Verify: `python tools\build_pyz.py --smoke` passes on Windows (Mac launcher structure checked) and on macOS CI (launcher started).
- [x] 5.4 Launcher tests (`tests/test_launcher_mac.py`, skipped on Windows): Python found, Apple stub skipped, private copy used, consent yes and no and unclear x3, wrong hash deletes the file, hash cannot be overridden by `EVAL_COACH_PYTHON_URL`, unusual folder name, read-only folder, newer file keeps progress, message wording has no file names. Verify: `python -m unittest tests.test_launcher_mac` on macOS CI.
- [x] 5.5 Write the Mac start instructions (zip, double-click, right-click Open, Open Anyway on macOS 15 and later, Terminal fallback line, no Gatekeeper bypass) into `docs/SETUP.md` and the text that accompanies the zip, and a test that scans them for forbidden advice. Verify: `python -m unittest tests.test_launcher_mac.InstructionsTest` (name to match the test written).

## 6. Platform wording (waits for interface authorization, rule 11)

- [x] 6.1 Ask the user to authorize the interface copy changes described in the proposal. Verify: the authorization is quoted in the proposal before 6.2 starts.
- [x] 6.2 Add `content/platform.json` and the server-side token resolver (`{paste_key}`, `{file_manager}`, `{copy_path_hint}`, `{path_example}`, `{sep}`, `{python_cmd}`), with a test-only platform override. Verify: new unit tests render each string for both platforms; Windows output equals the committed baseline byte for byte.
- [x] 6.3 Replace the hard-coded Windows words in `steps.json`, `preflight.json`, `import-checks.json`, `lessons.json` and `lesson-ui.json` with tokens; adapt the absolute-path check (`/`-rooted paths on a Mac) in `import_checks.py` and its messages. Verify: `python -m unittest tests.test_import_checks tests.test_content_and_resources tests.test_content_banned_words` for both platforms.
- [x] 6.4 Content tests per platform: no leftover `Ctrl+V`, `File Explorer`, `C:\`, `py ` or unresolved tokens outside `platform.json`; vocabulary rules on Mac text; bundled skills byte-identical (rule 8). Verify: `python -m unittest tests.test_participant_vocabulary tests.test_troubleshooting_coverage tests.test_content_banned_words tests.test_part_1_content tests.test_part_2_content tests.test_part_3_content`.
- [x] 6.5 Confirm the interface shows the Mac words unchanged and `web/` has no diff. Verify: `git diff --stat -- app/eval_coach/web` is empty, and `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` passes.

## 7. CI and cross-platform tests

- [x] 7.1 Add `.github/workflows/ci.yml` running the backend suite on Windows and on macOS (Apple Silicon and Intel runner labels as available), with Mac-only and Windows-only tests skipping by reason. Verify: the workflow runs green on the pull request.
- [x] 7.2 Add platform skips to `test_setup_cmd.py`, `test_integration_setup.py`, `test_preflight_real_download.py`, `test_promptfoo_real.py` and the Node harness entry points so each suite is green on each platform. Verify: `python -m unittest discover -s tests` on Windows and in macOS CI.

## 8. Integration checks

- [x] 8.1 Windows regression: run both backend suites one after the other, the interface tests, the build smoke test and the stand-in end to end. Verify: `python -m unittest discover -s tests`, then the embedded 3.13 command, then `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`, `python tools\build_pyz.py --smoke`, and `node e2e-work\harness\run-all.js --fresh` (output to a file), all as in AGENTS.md.
- [ ] 8.2 Real Mac pass (issue task 7.6): unzip, approve once, double-click, setup wizard, AI window, one quiet test and one visible run for each of the three AIs, then Quit leaves no process behind. Verify: a checklist of the above with results written into `docs/SETUP.md` or the pull request. Each real-AI run needs the user's single-use approval after the full command text is verified.

## Workflow follow-up

- Archive the change after the verification gate in `openspec/config.yaml` passes (labels backend, backend-embedded, interface, build, e2e).
- After archive, the `post-archive-pr` skill opens the branch and pull request, only on request.
- Summarize which `docs/SPEC.md` sections the archived specs supersede.
