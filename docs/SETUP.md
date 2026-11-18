# Setup and preflight

Read `docs/SPEC.md` first; its non-negotiable rules apply. Setup and preflight are global: they apply to every Part, and Part 2 is the only part that needs no AI window. Preflight must install every necessary dependency. Real steps stay locked until it passes. There is no human support path, so every failure must explain itself and give the participant a next action.

Evidence from the early experiments is in `spikes/phase0-preflight/` (`runtime-manifest.json`, `detect-python.cmd`) and `spikes/phase0-wrapper/`.

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
Replaces the earlier single-page setup screen. Results persist in `<home>\preflight.json`. Each item shows status (not checked, passed, failed, needs you), detail, and an action. "Check everything again" reruns it. Items are verified by running them.

**Where it appears.** Setup ("Before you begin") is a global, full-page wizard, not a course item: Track, Checking your computer, Python, Choose your AI, AI working test, Project folder, Your AI window (the promptfoo track adds Node.js and promptfoo after Python), with Back, Next and a progress count, and no sidebar or course list beside it. Next is disabled until the page's check passes and moves to the next page that still needs the participant (passed pages are skipped going forward; Back reaches them). Checking your computer and Your AI window are pages, not checks (OpenSpec change `guided-setup`, whose specs win over this section): the first runs the checks by itself when it is shown, the second is a mini lesson with an annotated screenshot of the chosen AI that is never recorded as progress. "Check everything" is offered only on the Python, Node.js, promptfoo, Choose your AI and Project folder pages, where something can be fixed outside the app. The AI window shows only on the AI working test page and while an install runs. It is shown first on first run, and again after "Reset app configuration". It has a "Skip for now" action: a skipped setup is remembered (`setup_skipped` in `preflight.json`) and the app then opens on the course with a reminder banner. Until every applicable item passes, steps and lesson exercises that start the CLI stay off (refused with `preflight_incomplete`, buttons disabled with a plain explanation), while every lesson, the glossary and the reference stay readable (locked lessons and steps open as read-only previews). The same wizard, with the same words, opens from the Settings panel ("Open setup") and from the reminder banner, so every check, install, AI choice, the track choice and the project folder can be used there at any time, whether or not setup has passed; closing it returns to where it was opened. See `docs/SPEC.md` "Setup is a skippable global gate".

| # | Item | Applies | Verified by | If missing |
|---|---|---|---|---|
| 1 | Track choice | all | Script (default) or promptfoo | |
| 2 | Python | all | the running interpreter, and `python --version` through the CLI's PATH | Stage 1 handled it |
| 3 | Node.js >= 22.22.0 | promptfoo | run `node --version`; existing install reused only if new enough | consent, then private install to `<home>\runtime\node` from nodejs.org 26.13.0 with SHA-256 verification (41 MB download, 113 MB installed) |
| 4 | promptfoo 0.125.1 | promptfoo | `npx --yes promptfoo@0.125.1 --version` prints 0.125.1 | consent stating about 1 GB of disk, then predownload with `npm_config_cache=<home>\npm-cache`, `PROMPTFOO_DISABLE_TELEMETRY=1`, `PROMPTFOO_CONFIG_DIR=<home>\promptfoo`; show progress, allow several minutes |
| 5 | Choose your AI (`cli`) | all | one of GitHub Copilot CLI, Claude Code or Devin CLI is chosen and its command resolves (the checks find installed ones by resolving each tool's command from the recipes; nothing is started) | offer the install recipes below, with consent, run visibly in the AI window |
| 6 | AI working test | all | first a quiet background test starts when the AI is chosen (the tool's one-shot mode, no window, no typing, no permission flags; only its exit status decides, so it proves start, sign-in and a reply). If it passes, this item passes and the page is skipped. If it cannot finish, see below: the participant starts the AI window, signs in there if asked, presses Send. A pass proves the sign-in: there is no separate sign-in item | failure names which capability failed; a quiet test that cannot finish is "needs you", never a failure |
| 7 | Project folder | all | creation succeeded; not in OneDrive; `prompt-v0.md` and `test-cases.md` exist | Northwind starters or importing the participant's files |

Before any install, check free disk space and include the amount in the consent text.

### CLI environment
The wrapper starts every CLI and every checker with `<home>\runtime\python` and `<home>\runtime\node`, when present, prepended to PATH, or the found Python's folder otherwise, and with the npm cache and promptfoo variables above. It adds no permission settings.

### CLI working test (item 6)
In a cleared `<home>\cli-test\` containing `input.txt` with `hello from eval coach`, start the CLI and type:
`Read input.txt, write its contents in uppercase to output.txt, then run python --version and write what it prints to version.txt. Do nothing else.`
Pass when `output.txt` is `HELLO FROM EVAL COACH` (ignoring trailing whitespace) and `version.txt` contains `Python 3`. A chat-only tool can't pass, and no tool is named or blocked. After Send the page re-reads the folder every 3 seconds (`POST /api/preflight/test/poll`) and records a pass only, never a failure; the Check button (`POST /api/preflight/test/check`) is the only place a failure is reported.

### CLI install recipes (`content/cli-recipes.json`)
Data, not code, so they can change without a rebuild. Show the exact command behind a "Show the command" link, and describe each recipe in plain words and size in its `plain` field. Sources are the vendors' official docs, recorded in the early experiments:
- GitHub Copilot CLI: `winget install GitHub.Copilot`. Docs list PowerShell 6+ as a prerequisite and Windows 11 ships 5.1, so if the participant picks Copilot and `pwsh` is missing, say so and offer `winget install Microsoft.PowerShell`.
- Claude Code: `curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd`, or `winget install Anthropic.ClaudeCode` (shown behind "Another way to install").
- Devin CLI: PowerShell `irm https://static.devin.ai/cli/setup.ps1 | iex`.
- Other: the free-text recipe is marked `"participant": false` and is not offered. A typed command field exists only when the app is started with the hidden `--custom-ai` flag, so the stand-in CLI and the tests can run.

### Failure messages
Plain text for each: no network or proxy block, download timed out, hash mismatch, not enough disk, antivirus removed a file, CLI not found after install, CLI not signed in, working test incomplete, npm errors. Each ends with the action to take. For blocked downloads, the action is to install Python or Node from the company's software portal (Company Portal or Software Center) and choose "Check everything again". No "contact" instruction.

## Tests
- `setup.cmd` under a scrubbed PATH with a temporary profile: no Python, real Python, stub only, private Python already there, paths with spaces and `&`, hash mismatch (corrupted archive), declined consent.
- Unit tests for each preflight item with fake runners; real downloads in one end-to-end test against the temporary home, reusing `spikes/phase0-preflight/downloads` only as a comparison.
- Node version comparison around 22.22.0.
- CLI working test: passing, wrong file content, missing version file.
