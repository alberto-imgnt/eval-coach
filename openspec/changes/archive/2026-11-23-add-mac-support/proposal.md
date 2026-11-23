# Proposal

## Why

eval-coach runs only on Windows, so a participant on a Mac cannot take the series (GitHub issue #7, "Add macOS compatibility"; Phase 7 of the local plan). Windows now starts from one file, `eval-coach.cmd` (`single-file-launcher`), so the Mac needs the same: one thing to open that finds or installs Python and starts the app, followed by an app that actually works on macOS. Doing the launcher, the terminal, setup and the wording as one change keeps Mac usable end to end rather than shipping a launcher that opens an app that cannot run an AI window.

## What Changes

- **Mac launcher.** New `packaging/launcher.sh`, shipped as `eval-coach.command` inside `eval-coach-mac.zip`: a shell script with the app archive appended after a marker line, the same shape as `eval-coach.cmd`. It finds a working Python 3.9 or later without ever opening Apple's Command Line Tools installer, and otherwise offers a private Python after consent, with a pinned SHA-256 per chip (Apple Silicon and Intel). The zip carries the executable bit so a double-click works. Instructions give the one-time Gatekeeper approval (right-click, Open) and a one-line Terminal fallback (`bash <path>/eval-coach.command`) for people who are blocked. `tools/build_pyz.py` builds both launchers.
- **Terminal on macOS.** A `pty`-based terminal with the same interface as `ConPTY` (`write`, `type_line`, `read_new`, `snapshot`, `resize`, `alive`, `wait`, `pids`, `close`), started in its own session so Quit and "New chat" stop the whole process tree. The terminal manager picks the right one by platform.
- **Setup on macOS.** The Python page, the private Node install for the promptfoo track (`darwin-arm64` or `darwin-x64`, pinned hash), the three AIs' Mac install commands, finding a newly installed AI (the Mac replacement for the Windows registry PATH read), and the quiet background AI test all work with Mac commands.
- **Wording per platform.** Paste shortcut (⌘V on a Mac), file manager (Finder), path examples and "Copy as path", `python3` in place of `python` or `py`, and `/` paths show on a Mac and stay as they are on Windows. This is done server side, from content tokens, so `web/` does not change.
- **Rules and docs.** AGENTS.md rule 5 allows one more download host (GitHub release downloads, for the private Mac Python). Rule 13 names the new OS-specific modules. `docs/SPEC.md`, `docs/SETUP.md` and `openspec/config.yaml` stop calling the app a Windows-only app.
- **Verification.** Backend tests run on Windows and, in CI, on macOS (Apple Silicon and Intel runners); Windows-only tests skip on a Mac and the reverse. A manual check on a real Mac with a signed-in AI finishes the change.

Not a breaking change for Windows: every Windows file, path and command stays as it is.

## Out of scope

- Linux, and the hosted no-install option (issue #6). The `pty` layer is written so a Linux build can reuse it, but nothing here ships or tests Linux.
- Code signing, notarization or an Apple developer account. The one-time Gatekeeper approval stays, and the instructions explain it.
- A `.pkg` or `.dmg` installer, and Homebrew-based installs of Python or Node.
- macOS 11 and earlier.
- Changes to the course lessons, the checks, the baseline or the answer-key rules. Course logic is identical on both platforms.
- Changing the bundled skill files: they stay byte-identical (rule 8). Mac wording lives in the typed lines, not in the skills.
- Real-AI runs on a Mac without the user's approval for each run (AGENTS.md, rules for anything that touches a real CLI).

## Interface authorization (AGENTS.md rule 11)

- **Needed and authorized.** The Mac wording changes interface copy in `content/steps.json`, `content/preflight.json`, `content/import-checks.json`, `content/lessons.json` and `content/lesson-ui.json` (paste shortcut, file manager, path examples, `python3`, Mac install wording, the macOS 13.5 promptfoo message, the Python page showing the Mac path). The user authorized this on 2026-11-20: "copy=Authorized as described" (answer to "Authorize the Mac interface copy changes (rule 11)?", the same answer approved the Mac install commands table of task 1.1: "recipes=Approve as shown").
- **Not needed.** No change to `web/` layout, styling, components or element ids is planned. Platform words are resolved on the server, so the existing interface shows them unchanged.

## Capabilities

### New Capabilities
- `mac-launcher`: the one-file Mac start (`eval-coach.command` in a zip), Python discovery, the private Python with a hash per chip, consent, failure messages and Gatekeeper guidance.
- `mac-runtime`: the app on macOS: the terminal, stopping process trees, Mac setup (Python and Node pins per chip, AI install commands, finding a newly installed AI), supported macOS versions and a plain message where a feature needs a newer one.
- `platform-wording`: what a participant reads adapts to the computer they are on (shortcuts, file manager, paths, the Python command) without changing the interface.

### Modified Capabilities
- `single-file-launcher`: the Purpose and first requirement say "on Windows"; they become a statement for Windows, with the Mac in `mac-launcher`, and the messages rule "Messages tell participants to start eval-coach again" applies to both launchers.
- `ai-selection`: the install options come from the computer's platform; "PowerShell 6 or later" applies to Windows only; the install command and size shown come from the Mac recipe on a Mac.
- `participant-vocabulary`: the content tests also run per platform, and the word rules (no bare "CLI", "Practice task") apply to every platform's wording.

## Impact

- **New files:** `packaging/launcher.sh`, a `pty` terminal module, a small OS helper module, a Mac runtime manifest (pinned versions, URLs and hashes), tests, and docs.
- **Changed code:** `terminal.py`, `preflight.py` (Windows constants, kill tree, shells, Node install, PATH discovery), `project.py` and `__main__.py` (home folder help text), `tools/build_pyz.py` (second launcher and the zip), the content loader (platform tokens).
- **Changed content:** `cli-recipes.json` (Mac recipes), `steps.json`, `preflight.json`, `import-checks.json`, `lessons.json` and `lesson-ui.json` where they name Windows keys, tools or paths.
- **Changed tests:** platform skips on `test_conpty.py`, `test_setup_cmd.py`, the integration tests and the Node harness; new Mac tests; a CI workflow (`.github/workflows/`) for macOS.
- **Docs and rules:** AGENTS.md rules 5 and 13 and its status text, `docs/SPEC.md`, `docs/SETUP.md`, `openspec/config.yaml` context.
- **Network:** one new host, GitHub release downloads, used only for the private Mac Python and only after consent, with a fixed hash.
