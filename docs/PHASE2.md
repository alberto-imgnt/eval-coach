# Phase 2: preflight

Read `docs/SPEC.md` first; its non-negotiable rules apply. Preflight must install every necessary dependency. Real steps stay locked until it passes. There is no human support path, so every failure must explain itself and give the participant a next action.

Evidence from Phase 0 is in `spikes/phase0-preflight/` (`runtime-manifest.json`, `detect-python.cmd`) and `spikes/phase0-wrapper/`.

## Distribution
`eval-coach.zip` contains `setup.cmd` and `eval-coach.pyz`. Participants unzip it and run `setup.cmd`.

## Stage 1: `setup.cmd`
Uses only cmd.exe and `%SystemRoot%\System32` tools, called by full path (`curl.exe`, `tar.exe`, `certutil.exe`), because Git Bash and other tools can shadow them on PATH.
1. Detect a working Python 3.9 or later using the tested logic in `detect-python.cmd`. Skip anything under `\Microsoft\WindowsApps\` without running it.
2. If none is found, look for `%USERPROFILE%\.eval-coach\runtime\python\python.exe`.
3. If still none: show what will be installed, where, and the size (python.org embeddable 3.13.17, about 11 MB download, 22 MB installed, no admin rights, no system changes) and ask Y/N. On Y: download, verify SHA-256 against the value pinned in the script, extract, delete `python313._pth`. Hash mismatch stops with a clear message and deletes the file; it is never bypassed.
4. Launch `python eval-coach.pyz`, passing the path so the app knows which Python it runs on.
Must handle a user profile path containing spaces and `&`, `(`, `)`.
Pinned values come from `runtime-manifest.json`.

## Stage 2: preflight screen
Replaces the Phase 1 setup screen. Results persist in `<home>\preflight.json`. Each item shows status (not checked, passed, failed, needs you), detail, and an action. "Check everything again" reruns it. Items are verified by running them.

**Where it appears.** Setup ("Before you begin") is a global, full-page wizard, not a course item: one page per check (Track, Python, Your AI CLI, Sign in and license, CLI working test, Project folder; the promptfoo track adds Node.js and promptfoo), with Back, Next and a progress count, and no sidebar or course list beside it. Next is disabled until the page's check passes. The terminal shows inside the pages that use the CLI. It is shown first on first run, and again after "Reset app configuration". It has a "Skip for now" action: a skipped setup is remembered (`setup_skipped` in `preflight.json`) and the app then opens on the course with a reminder banner. Until every applicable item passes, steps and lesson exercises that start the CLI stay off (refused with `preflight_incomplete`, buttons disabled with a plain explanation), while every lesson, the glossary and the reference stay readable (locked lessons and steps open as read-only previews). The same wizard, with the same words, opens from the Settings panel ("Open setup") and from the reminder banner, so every check, install, CLI option, the track choice and the project folder can be used there at any time, whether or not setup has passed; closing it returns to where it was opened. See `docs/SPEC.md` "Setup is a skippable global gate".

| # | Item | Applies | Verified by | If missing |
|---|---|---|---|---|
| 1 | Track choice | all | Script (default) or promptfoo | |
| 2 | Python | all | the running interpreter, and `python --version` through the CLI's PATH | Stage 1 handled it |
| 3 | Node.js >= 22.22.0 | promptfoo | run `node --version`; existing install reused only if new enough | consent, then private install to `<home>\runtime\node` from nodejs.org 26.13.0 with SHA-256 verification (41 MB download, 113 MB installed) |
| 4 | promptfoo 0.125.1 | promptfoo | `npx --yes promptfoo@0.125.1 --version` prints 0.125.1 | consent stating about 1 GB of disk, then predownload with `npm_config_cache=<home>\npm-cache`, `PROMPTFOO_DISABLE_TELEMETRY=1`, `PROMPTFOO_CONFIG_DIR=<home>\promptfoo`; show progress, allow several minutes |
| 5 | AI CLI | all | participant enters or picks the command; launched in the terminal | offer the install recipes below, with consent, run visibly in the embedded terminal |
| 6 | Sign-in and license | all | participant starts the CLI, signs in, confirms | the app can't do this; plain explanation that an agentic tool license is required |
| 7 | CLI working test | all | see below | failure names which capability failed |
| 8 | Project folder | all | creation succeeded; not in OneDrive; `prompt-v0.md` and `test-cases.md` exist | Northwind starters or importing the participant's files |

Before any install, check free disk space and include the amount in the consent text.

### CLI environment
The wrapper starts every CLI and every checker with `<home>\runtime\python` and `<home>\runtime\node`, when present, prepended to PATH, or the found Python's folder otherwise, and with the npm cache and promptfoo variables above. It adds no permission settings.

### CLI working test (item 7)
In a cleared `<home>\cli-test\` containing `input.txt` with `hello from eval coach`, start the CLI and type:
`Read input.txt, write its contents in uppercase to output.txt, then run python --version and write what it prints to version.txt. Do nothing else.`
Pass when `output.txt` is `HELLO FROM EVAL COACH` (ignoring trailing whitespace) and `version.txt` contains `Python 3`. A chat-only tool can't pass, and no tool is named or blocked.

### CLI install recipes (`content/cli-recipes.json`)
Data, not code, so they can change without a rebuild. Show the exact command before it runs. Sources are the vendors' official docs, recorded in Phase 0:
- GitHub Copilot CLI: `winget install GitHub.Copilot`. Docs list PowerShell 6+ as a prerequisite and Windows 11 ships 5.1, so if the participant picks Copilot and `pwsh` is missing, say so and offer `winget install Microsoft.PowerShell`.
- Claude Code: `curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd`, or `winget install Anthropic.ClaudeCode`.
- Devin CLI: PowerShell `irm https://static.devin.ai/cli/setup.ps1 | iex`.
- Other CLI: the participant installs it and enters the command.

### Failure messages
Plain text for each: no network or proxy block, download timed out, hash mismatch, not enough disk, antivirus removed a file, CLI not found after install, CLI not signed in, working test incomplete, npm errors. Each ends with the action to take. For blocked downloads, the action is to install Python or Node from the company's software portal (Company Portal or Software Center) and choose "Check everything again". No "contact" instruction.

## Tests
- `setup.cmd` under a scrubbed PATH with a temporary profile: no Python, real Python, stub only, private Python already there, paths with spaces and `&`, hash mismatch (corrupted archive), declined consent.
- Unit tests for each preflight item with fake runners; real downloads in one end-to-end test against the temporary home, reusing `spikes/phase0-preflight/downloads` only as a comparison.
- Node version comparison around 22.22.0.
- CLI working test: passing, wrong file content, missing version file.
