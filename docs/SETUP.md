# Setup and preflight

Read `docs/SPEC.md` first; its non-negotiable rules apply. Setup and preflight are global: they apply to every Part, and Part 2 is the only part that needs no AI window. Preflight must install every necessary dependency. Real steps stay locked until it passes. There is no human support path, so every failure must explain itself and give the participant a next action.

Evidence from the early experiments is in `spikes/phase0-preflight/` (`runtime-manifest.json`, `detect-python.cmd`) and `spikes/phase0-wrapper/`.

## Distribution
One file, `eval-coach.cmd`, is all a participant needs; they double-click it. `python tools\build_pyz.py` builds it as `dist\eval-coach.cmd`: the launcher script `packaging\launcher.cmd`, which ends with the marker line `rem ===== eval-coach.pyz follows =====`, followed by the bytes of `dist\eval-coach.pyz`. cmd runs the script part and stops at its last `exit /b`, never reading the archive; Python ignores the text in front of a zip archive, so the app runs from the same file. `dist\eval-coach.pyz` is still built for the smoke check and the end-to-end harness. Replacing the file with a newer one is the whole update.

Rules for the script part: plain ASCII with CRLF line endings, and no backward jump. Once binary data follows, cmd ends a label search silently at it, so a `goto` or `call` to a label defined earlier in the file does nothing (this once made the Python search report "not found" on a computer that has Python). Loops use `for /l` or are unrolled; `tests\test_setup_cmd.py` fails when a backward jump appears. Every path must end in `exit /b`.

## Stage 1: the launcher (`packaging\launcher.cmd`)
Uses only cmd.exe and `%SystemRoot%\System32` tools, called by full path (`curl.exe`, `tar.exe`, `certutil.exe`), because Git Bash and other tools can shadow them on PATH.
1. Detect a working Python 3.9 or later using the tested logic in `detect-python.cmd`. Skip anything under `\Microsoft\WindowsApps\` without running it.
2. If none is found, look for `%USERPROFILE%\.eval-coach\runtime\python\python.exe`.
3. If still none: show what will be installed, where, and the size (python.org embeddable 3.13.17, about 11 MB download, 22 MB installed, no admin rights, no system changes) and ask Y/N. On Y: download, verify SHA-256 against the value pinned in the script, extract, delete `python313._pth`. Hash mismatch stops with a clear message and deletes the file; it is never bypassed.
4. Start the app from the launcher file itself (`python -B eval-coach.cmd --python <path>`, with any arguments the launcher received passed on), so the app knows which Python it runs on.
Must handle a user profile path containing spaces and `&`, `(`, `)`.
Pinned values come from `packaging\runtime-manifest.json` (see "Pinned runtimes" below): `tools\build_pyz.py` stamps them into the launcher, and `tests\test_launcher_manifest.py` fails when a launcher or `hostos.py` disagrees.

## Mac: distribution and the launcher (`packaging/launcher.sh`)
OpenSpec change `add-mac-support`; its specs `mac-launcher`, `mac-runtime` and `platform-wording` win over this section. The Mac download is `dist/eval-coach-mac.zip`, which holds only `eval-coach.command` (mode 0755 inside the zip, so a double-click runs it). It is `packaging/launcher.sh` (LF endings, plain ASCII, bash 3.2 features only) followed by the marker line `# ===== eval-coach.pyz follows =====` and the app archive; every path of the script ends in `exit` before the marker, and Python reads the same file as a zip. `packaging/mac-start.txt` is the text that goes with the zip (it is not inside the zip, which stays one file). `python tools\build_pyz.py` builds the file and the zip; `--smoke` checks the launcher's shape and the zip on Windows and starts the launcher on a Mac.
1. Check macOS: below 13 stops with a plain message and nothing is downloaded.
2. Pick the chip the Python will run on: `uname -m`, and Rosetta (`sysctl sysctl.proc_translated` is 1) counts as Apple Silicon.
3. Find a working Python 3.9 or later: `python3` then `python` on PATH, then `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`, `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`. `/usr/bin/python3` is Apple's stub and is never run unless `xcode-select -p` succeeds, because running it otherwise opens Apple's installer. A candidate counts only when it prints a per-run token and reports Python 3.9 or later (stdin from `/dev/null`, an empty working folder, a 10 second limit).
4. Then the private copy at `~/.eval-coach/runtime/python/bin/python3`.
5. If none: show what, size (python-build-standalone 3.13.18, about 25 MB download, about 70 MB installed), where, the download address and the free space; ask Y or N up to three times (no answer or N declines). On Y: download with `/usr/bin/curl`, check the SHA-256 with `/usr/bin/shasum -a 256` against the value built into the script for this chip, unpack into `python.new`, run it once, then put it in place. A wrong or unverifiable file is deleted and nothing is installed; no environment value changes the hash (`EVAL_COACH_PYTHON_URL` only changes where the file comes from).
6. Start the app: `python -B <the file itself> --python <path> <arguments>`. The window stays open after a failure or a decline until a key is pressed, and an app error shows its exit code.
Messages call the file "eval-coach" and tell the participant to start eval-coach again. The launcher works from a folder with spaces, quotes, `&`, `(`, `)` or `!` in its path, from a read-only folder, and does not touch progress or the private Python when it is replaced by a newer file. Two test hooks exist and only narrow or inspect: `EC_SOURCE_ONLY=1` loads the functions without running anything, and `EVAL_COACH_PATH_ONLY=1` leaves the usual install folders out of the Python search.

### Starting it for the first time on a Mac (Gatekeeper)
The file is not signed or notarized (out of scope for this change), so macOS may refuse the first open. The text that goes with the zip (`packaging/mac-start.txt`, and this section) says, in this order:
1. Double-click `eval-coach-mac.zip`, then double-click `eval-coach.command`.
2. If macOS refuses: right-click the file, choose Open, then Open in the box.
3. On macOS 15 and later, if there is no Open button: System Settings, Privacy & Security, Security, "Open Anyway" next to the message about `eval-coach.command`.
4. If double-clicking still does nothing, in Terminal: `bash ~/Downloads/eval-coach.command` (or `bash `, a space, and the file dragged in from Finder).
The instructions give no way around macOS's protections; `tests/test_launcher_mac.py` scans both texts for advice that would.

## Mac: setup in the app (`hostos.py`, `ptyterm.py`)
- **AI window.** `terminal.py` picks `PosixPTY` (`ptyterm.py`) on a Mac: a `pty` with the child in its own session and process group and the pty as its controlling terminal. Same surface as `ConPTY`. Closing, "Open a new AI chat", Quit and a time-limited quiet test end the whole process group (hang-up, then terminate, then kill after a short wait). `TERM` is set to `xterm-256color` when it is missing or `dumb`; a tool listed in `terminal-hints.json` also gets `TERM_PROGRAM=Apple_Terminal` unless one is already set.
- **Python page.** Finds `python3`, then `python` (never Apple's stub); shows the path and version; below 3.9, or none, says to close the window and start eval-coach again. The private Python is first on the AI's PATH when it exists.
- **Node.js (promptfoo track).** A private copy from nodejs.org, the `darwin-arm64` or `darwin-x64` tarball for the app's chip, fixed SHA-256 per chip, `tar -xzf`, run `node --version`, moved to `~/.eval-coach/runtime/node`; npx runs `lib/node_modules/npm/bin/npx-cli.js` with that Node. Node 26 needs macOS 13.5 or later: below that the track page and the Node.js page say so, offer the Script track, and nothing is downloaded. Everything else works on macOS 13 and later.
- **AIs.** The Mac install commands are in the table above (recipe shell `zsh`, run as `/bin/zsh -lc`). A newly installed AI is found without restarting the app: the search adds `~/.local/bin`, `~/.npm-global/bin`, `/opt/homebrew/bin`, `/opt/homebrew/sbin`, `/usr/local/bin` and any folders a recipe lists in `path_dirs`, when they exist, and only resolves the command (it never starts the AI).
- **Recipes.** `content/cli-recipes.json` keeps the Windows values at the top level of each recipe and adds a `platforms` block with `windows` and `mac` entries; the Mac entry holds only what differs (`null` removes a field, `"available": false` hides the recipe on that platform). `tests/test_preflight.py` compares the Windows values with `tests/golden/cli-recipes-windows.json`.
- **Words.** `content/preflight.json` has `platform_overrides.mac` (messages and consent text that differ) and `platform_text.mac` (phrases removed from every string, such as the Windows software portal names).
- **Files.** The home folder `~/.eval-coach`, the project `~/eval-project` and the reset backup `~/.eval-coach/reset-backup/` behave as on Windows.

### Pinned runtimes
`packaging/runtime-manifest.json` is the only place a pin is written by hand (Windows Python 3.13.17 and Node 26.13.0; Mac Python 3.13.18 from python-build-standalone release `20261110`, and Node 26.13.0 for both chips). The Mac Python is a different patch version from the Windows one because that is what the release offers; the app needs only 3.9 or later.

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

#### Mac install commands (OpenSpec change `add-mac-support`, checked against each vendor's own documentation on 2026-11-20)
Run on a Mac through `/bin/zsh -lc "<command>"` in the AI window (recipe shell `zsh`). None needs administrator rights. The vendors state no download or disk size, so the recipes keep the 400 MB free-space check the Windows recipes use. Approved by the user on 2026-11-20 (task 1.1).

| AI | Mac command | Sign-in | Notes | Source |
|---|---|---|---|---|
| GitHub Copilot CLI | `curl -fsSL https://gh.io/copilot-install \| bash` (installs to `~/.local/bin` when not run as root) | GitHub account with a Copilot license; `/login` on first start | No PowerShell requirement on a Mac. Alternatives the vendor lists: `brew install --cask copilot-cli`, `npm install -g @github/copilot` (needs Node.js 22 or later) | docs.github.com, "Installing GitHub Copilot CLI" |
| Claude Code | `curl -fsSL https://claude.ai/install.sh \| bash` | Claude account that includes Claude Code | Vendor lists macOS 13.0 or later (the Mac floor of this app is the same, macOS 13); an installer-script alternative is `brew install --cask claude-code` | code.claude.com, "Advanced setup" |
| Devin CLI | `curl -fsSL https://cli.devin.ai/install.sh \| bash` | Devin account | Alternative: `brew install --cask devin-cli`. The vendor tells you to restart the terminal after install | docs.devin.ai, "Quickstart" |

### Failure messages
Plain text for each: no network or proxy block, download timed out, hash mismatch, not enough disk, antivirus removed a file, CLI not found after install, CLI not signed in, working test incomplete, npm errors. Each ends with the action to take. For blocked downloads, the action is to install Python or Node from the company's software portal (Company Portal or Software Center) and choose "Check everything again". No "contact" instruction.

## Tests
- The launcher (`packaging\launcher.cmd` assembled with a stub app) under a scrubbed PATH with a temporary profile: no Python, real Python, stub only, private Python already there, the file alone in a folder, paths with spaces and `&`, hash mismatch (corrupted archive), declined consent. Shape checks: CRLF and ASCII in the script part, a valid archive after the marker, no backward `goto` or `call`.
- `tests\test_integration_setup.py` runs the built `dist\eval-coach.cmd`, alone in its folder, against the real app.
- Unit tests for each preflight item with fake runners; real downloads in one end-to-end test against the temporary home, reusing `spikes/phase0-preflight/downloads` only as a comparison.
- Node version comparison around 22.22.0.
- CLI working test: passing, wrong file content, missing version file.
