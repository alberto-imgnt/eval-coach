# Design

## Context

See proposal.md for why. Observed state of the code:

- **Terminal.** `terminal.py` builds sessions through `_real_factory`, which imports `ConPTY` late ("Windows only"). `ConPTY` exposes `write`, `type_line`, `read_new`, `snapshot`, `resize`, `alive`, `wait`, `pids`, `close`, plus `exit_code` and `pid`. `command_to_argv` is platform-neutral parsing; `resolve_command` is Windows-only (it routes `.cmd`, `.bat`, `.ps1` and extensionless shims). The Windows Terminal marker in `_with_terminal_hint` is Windows-flavoured.
- **Preflight.** `preflight.py` hard-codes `System32` tools (`curl.exe`, `tar.exe`, `taskkill.exe`, `cmd.exe`, PowerShell), a `win-x64` Node zip with its hash and `node.exe` layout, `CREATE_NO_WINDOW`, the registry PATH read (`read_registry_paths`) and recipe shells `cmd` and `powershell`. `Preflight.env()` prepends the private Python (`runtime\python\python.exe`) and Node folders. `_npx_argv` expects `node_modules\npm\bin\npx-cli.js` beside `node.exe`; on Mac the layout is `bin/node` and `lib/node_modules/npm/bin/npx-cli.js`.
- **Paths.** `project.py` already falls back from `USERPROFILE` to `expanduser("~")`, so the default folders work on a Mac.
- **Launcher.** `packaging/launcher.cmd` ends with a marker line, and `tools/build_pyz.py` appends the `.pyz` after it. Python reads a zip with leading bytes, so the same trick works for a shell script. The script must never read past its own `exit`.
- **Content.** Windows words are in `cli-recipes.json`, `steps.json`, `preflight.json`, `import-checks.json` (and possibly `lessons.json`, `lesson-ui.json`). Examples: `Ctrl+V`, `skills\\...`, `C:\\Users\\you\\...`, "File Explorer", "Copy as path", "use py instead of python".
- **Rules in play.** Rule 1 (stdlib only: `pty`, `os`, `signal`, `termios` are stdlib), rule 5 (network hosts), rule 8 (skills byte-identical), rule 11 (interface), rule 13 (OS-specific code location).
- **Pins found on 2026-11-20.** python-build-standalone release `20261110`: `cpython-3.13.18+20261110-aarch64-apple-darwin-install_only.tar.gz` (25,598,083 bytes, sha256 `1afd3983237c2a10277345f235be730e9cb49a123e0574ed252dbf3a841a24e4`) and `...-x86_64-apple-darwin-install_only.tar.gz` (25,349,864 bytes, sha256 `a46bcdeecd28ba253522b321dcb3806da1b0ff581479fc1d27e9613e3ac44764`). Node 26.13.0 from nodejs.org: `node-v26.13.0-darwin-arm64.tar.gz` (58,334,661 bytes, sha256 `d38bd5e5a2ddce6bbb5ce45e46e208337da4d51fffe611e567fd32073d6439f6`) and `node-v26.13.0-darwin-x64.tar.gz` (sha256 `525c9b29bb0263d687de60a4cec0e2a6db876a8eb032369e5795eca71e7c358e`). Node 26's own build notes say its macOS binaries target macOS 13.5. Windows pins Python 3.13.17; the Mac build is 3.13.18, which is what that release offers (to be rechecked when the pins are written).

## Goals / Non-Goals

**Goals:**
- Windows behavior, files and tests are unchanged.
- All OS-specific code sits in a short list of named modules (rule 13, amended).
- The Mac launcher mirrors the Windows launcher's guarantees: consent first, fixed hash, no stub opened, plain failures, window stays open.
- Platform wording is resolved in the server so `web/` is untouched.
- The Mac can be tested in CI for logic and the pty layer; only the signed-in AI check needs a physical Mac.

**Non-Goals:**
- Linux support, though the `pty` module should not assume macOS beyond what it must.
- Signing, notarization, installers, Homebrew.
- Rewriting `preflight.py` into a plugin system. Only the OS-specific seams move.

## Decisions

### D1. One zip, one `.command` file, built beside the Windows file
`packaging/launcher.sh` ends with a marker line; `build_pyz.py` appends the `.pyz` after it to produce `dist/eval-coach.command`, then writes `dist/eval-coach-mac.zip` with the file's Unix mode set to `0755` (`zipfile.ZipInfo.external_attr = 0o100755 << 16`). A browser-downloaded bare file loses the executable bit and Finder refuses it; a zip keeps it.
*Alternatives:* a bare `.command` (Finder refuses it); a `.app` bundle (needs signing for a good experience); `.dmg`/`.pkg` (admin prompts, more tooling). Rejected.
The user chose option 3 in exploration: zip with double-click as the main route plus a one-line Terminal fallback (`bash <path>/eval-coach.command`), which skips both the missing executable bit and Gatekeeper because Terminal runs `bash` directly.

### D2. Launcher is POSIX `sh`, with a marker line and an `exit` before the archive
The script runs under `/bin/bash` (always present on macOS, version 3.2), so it avoids newer bash features. Every path ends in `exit`, never reading the archive. It uses full paths for system tools (`/usr/bin/curl`, `/usr/bin/tar`, `/usr/bin/shasum`, `/usr/bin/uname`, `/usr/bin/sw_vers`, `/usr/sbin/sysctl`). Paths are always quoted; no `eval`. The app is started with `"$PY" -B "$0" --python "$PY" "$@"` using the file's own path (resolved with `cd -P` and `pwd -P`, so folders with spaces, `&`, `(`, `!` work).

### D3. Python discovery order on a Mac, without opening Apple's installer
1. `python3`, then `python` from PATH (`command -v` equivalents), skipping `/usr/bin/python3` unless `xcode-select -p` succeeds and the Command Line Tools folder exists.
2. Fixed locations: `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`, `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`.
3. The private copy `~/.eval-coach/runtime/python/bin/python3`.
Each candidate is run with stdin from `/dev/null`, a per-run random token, a hard timeout (a background `kill` after 10 seconds) and must print the token and `sys.version_info >= (3, 9)`. A candidate that prints something else, or hangs, is ignored. This is the Mac version of the Windows probe in `launcher.cmd`.
*Alternative:* trusting `/usr/bin/python3` always. Rejected: without the Command Line Tools it opens Apple's install dialog, which is the equivalent of the Microsoft Store stub.

### D4. Private Python from python-build-standalone, pinned per chip
The launcher carries two pins (arm64, x86_64) with URL, size, SHA-256 and the folder inside the archive. It chooses by `uname -m`, and when `sysctl -n sysctl.proc_translated` says it is under Rosetta, it chooses the chip the Python will run on (arm64). The `install_only` archive extracts to `python/` with `bin/python3`; it is downloaded to the runtime folder, hashed with `/usr/bin/shasum -a 256`, unpacked into `python.new`, run once (probe), then renamed to `python`. Same consent text, same three tries, same declined message as Windows. `EVAL_COACH_PYTHON_URL` may redirect the file for tests but never changes the hash.
Source host: GitHub release downloads (`github.com/astral-sh/python-build-standalone/releases/download/...`). AGENTS.md rule 5 gets this one host, used only after consent. A manifest, `packaging/runtime-manifest.json` (new), holds all Windows and Mac pins; `build_pyz.py` stamps them into each launcher so there is one source for each value, and a test fails if a launcher and the manifest disagree.
*Alternatives:* python.org `.pkg` (needs admin, or fragile `pkgutil --expand` relocation); Homebrew (not on Macs by default); asking the user to install Python (high friction). Rejected.

### D5. A `pty` terminal behind the same interface
New `app/eval_coach/ptyterm.py` defines `PosixPTY` with the same public surface as `ConPTY`. It uses `pty.openpty()`, `subprocess.Popen(..., start_new_session=True)` with the pty slave as stdin/stdout/stderr, a reader thread that fills the same ring buffer rules, `fcntl.ioctl(TIOCSWINSZ)` for resize, `os.killpg` for `close` and `pids` (listing the group via `ps -g` or `pgrep -g`). `close` sends `SIGHUP`, then `SIGTERM`, then `SIGKILL` after a short wait. `type_line` writes the text, waits, then writes `\r` as today. `terminal.py` chooses the class by `sys.platform` and no longer imports Windows code on a Mac; `resolve_command` for the POSIX class only needs `shutil.which` plus an executable check, with the shebang handled by the OS.
*Alternative:* `subprocess` with pipes. Rejected: AI tools need a real terminal (colors, cursor, resize, paste).

### D6. Platform seams live in one small module
New `app/eval_coach/hostos.py` holds: `IS_MAC`, `IS_WINDOWS`, `kill_tree(proc)` (taskkill vs `killpg`), `popen_flags()`, `download_argv(...)` and `extract_argv(...)` (curl and tar paths), `recipe_shell_argv(recipe)` (`cmd`, `powershell`, or `/bin/zsh -lc` on a Mac), `extra_path_dirs()` (registry PATH vs `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, the AIs' own folders), `node_pins()`, `node_exe_relative()` and `npx_cli_relative()`. `preflight.py` calls these instead of its constants; Windows return values are exactly today's. `conpty.py` is untouched except for being skipped on a Mac. Rule 13 is amended to name `conpty.py`, `ptyterm.py`, `hostos.py` and the launchers.
*Alternative:* sprinkling `sys.platform` checks in `preflight.py`. Rejected: the point of rule 13 is a short list of places.

### D7. Mac recipes come from data, with a platform key
`cli-recipes.json` gets a `platforms` structure so each recipe may carry `windows` and `mac` variants of `shell`, `command`, `needs_mb`, `plain`, `requires`. Windows variants are today's values verbatim. Mac variants for the three AIs are written from the vendors' own Mac docs and verified before pinning (tasks); Mac has no "PowerShell" recipe or requirement. The recipes run in the AI window through the user's shell with a login environment so PATH edits made by an installer apply for the next check. No CLI-specific logic enters code (rule 6).
*Alternative:* parallel `cli-recipes.mac.json`. Rejected: two files drift.

### D8. Platform tokens in content, resolved by the server
`content/*.json` strings may include tokens such as `{paste_key}`, `{file_manager}`, `{copy_path_hint}`, `{path_example}`, `{sep}`, `{python_cmd}`. A new platform table (`content/platform.json`) gives each token's text for `windows` and `mac`. The content loader resolves tokens when it serves content, based on the host OS (overridable by a test-only environment value so tests can render both). Windows output is byte-for-byte what it is today. Because the text is sent to the existing UI as plain strings, `web/` does not change.
Strings that hard-code a Windows path (for example `skills\\build-eval-script`) become `skills{sep}build-eval-script`. A content test fails on a leftover `Ctrl+V`, `File Explorer`, `C:\` or `py ` outside `platform.json`.
*Alternative:* two copies of `steps.json`. Rejected: doubles the review surface and drifts.
Interface authorization (rule 11) is required before the content tasks run; it is not yet given (see proposal).

### D9. Supported macOS versions and the promptfoo track
Launcher check: `sw_vers -productVersion` below 13 stops with a plain message (the floor matches Claude Code's macOS 13, decided 2026-11-23). Node 26's binaries target 13.5, so on macOS 13.0 to 13.4 the Node page and the track choice say the promptfoo track needs 13.5 or later and point to the Script track. Server detects the version with `platform.mac_ver()`; the message comes from content.
*Alternative:* pinning an older Node for Macs. Rejected for now: a second Node pin to keep working with promptfoo 0.125.1 and `NODE_MIN` (22.22.0); revisit if macOS 13.0 to 13.4 promptfoo users matter (Open Question 2).

### D10. Verification: CI on macOS, then a real Mac
A new `.github/workflows/ci.yml` runs `python -m unittest discover -s tests` on `windows-latest`, `macos-15` (arm64) and `macos-15-intel` (Intel) — runner labels to confirm when the workflow is written. Tests that need ConPTY, `setup.cmd`, the embedded Python or Windows tools skip on a Mac with a reason; new Mac tests (pty round trip, kill tree, launcher script against a local file URL, `sh` syntax with `sh -n`, hash check, zip mode bit) skip on Windows. Launcher tests that need real downloads use `EVAL_COACH_PYTHON_URL` pointing at a local archive. The signed-in AI check is a manual task (7.6) with one single-use approval per tool (AGENTS.md rules for real CLIs).

### Storage and locations touched

| Location | Windows | Mac | Kept or cleared |
|---|---|---|---|
| App home | `%USERPROFILE%\.eval-coach` | `~/.eval-coach` | kept; cleared only by "Reset app configuration" (with backup) |
| Private Python | `.eval-coach\runtime\python\python.exe` | `.eval-coach/runtime/python/bin/python3` | kept across runs; replaced by a newer launcher only if damaged |
| Private Node | `.eval-coach\runtime\node` | same, with `bin/node` and `lib/node_modules/npm` | kept |
| npm cache | `.eval-coach\npm-cache` | `.eval-coach/npm-cache` | kept |
| Reset backup | `.eval-coach\reset-backup\` | `.eval-coach/reset-backup/` | one folder, as today |
| Project | `%USERPROFILE%\eval-project` | `~/eval-project` | never overwritten |
| Download work folder | `%TEMP%\ec-setup-*` | `$TMPDIR` or `/tmp` `ec-setup-*` | deleted by the launcher on every exit |
| `progress.json` and sealed key storage | unchanged | unchanged | no new keys; no key or course answer is stored |
| New repo files | none | `packaging/launcher.sh`, `packaging/runtime-manifest.json`, `app/eval_coach/ptyterm.py`, `app/eval_coach/hostos.py`, `app/eval_coach/content/platform.json`, `.github/workflows/ci.yml` | tracked |
| Build output | `dist/eval-coach.cmd`, `.pyz` | `dist/eval-coach.command`, `dist/eval-coach-mac.zip` | generated, not hand-edited |

## Risks / Trade-offs

- **Gatekeeper still shows a one-time warning** → The instructions explain right-click Open and Open Anyway, with the Terminal fallback. Signing is out of scope; revisit if the warning blocks too many people.
- **Mac install commands for the three AIs may change or differ from my assumptions** → Each is checked against the vendor's own docs in the first task, and shown only through "Show the command". Wrong commands fail visibly in the AI window, which the participant can read.
- **`pty` behavior differs from ConPTY (echo, newline mapping, signals)** → Start with a round-trip test against a small Python child and the stand-in `fake_cli.py`, then the manual pass with each real AI (single-use approval each).
- **A new download host weakens rule 5** → One host, consent first, fixed hash per chip, no environment override of the hash; the rule text records exactly this.
- **Python 3.13.18 on Mac versus 3.13.17 on Windows** → Both are 3.13; the app needs only 3.9+. Pin both in the manifest so the difference is visible, not accidental.
- **Content tokens could leak into Windows text** → A test renders every string for both platforms and fails on an unresolved `{token}` and on any Windows difference from the stored baseline.
- **CI runner availability and labels change** → Pin by label in the workflow and note it in docs; the manual Mac pass remains the final gate.
- **macOS 13.0 to 13.4 and the promptfoo track** → Plain message and Script track; Open Question 2.
- **Windows regression** → Windows return values from `hostos.py` are today's literals; the existing Windows suites and the stand-in e2e run unchanged.

## Migration Plan

1. Land the platform seams (`hostos.py`, terminal chooser, content tokens) with Windows behavior unchanged and the full Windows suites green.
2. Add `ptyterm.py` and the Mac preflight paths; run them in macOS CI.
3. Add the launcher, manifest and the zip build; smoke-test on the CI Macs and on one real Mac.
4. Do the Mac content and recipes, after the user authorizes the interface copy changes.
5. Real-Mac pass with each AI (one approval each), then docs and rule amendments.
Rollback: the Windows path is untouched by default, so reverting this change removes the Mac files and the platform tokens. Participant data is never modified by the change.

## Open Questions

1. **Runner labels and Intel coverage.** Assumed: `macos-15` (arm64) and `macos-15-intel` (Intel) runners are used in CI, and the Intel runner is allowed to be retired later without blocking a release.
2. **promptfoo on macOS 13.0 to 13.4.** Assumed: the promptfoo track is declared unsupported there with a plain message; the Script track is offered. Say if you want an older Node pinned for those Macs instead.
3. **Mac AI install commands.** Assumed: the vendors' own Mac installers (script or package manager, as each vendor documents) are used, and each command is shown to you before it is pinned.
4. **Where the Gatekeeper steps live.** Nothing inside the launcher can be read before macOS lets it open, so the one-time approval and the Terminal fallback go in `docs/SETUP.md` and the text that accompanies the zip where it is shared. Assumed: you share the zip with that text; the launcher's own messages cover everything after the first open.
5. **Zip contents.** Assumed: the zip holds only `eval-coach.command`. If a short README inside the zip is wanted, say so; it would be the one exception to "one file".
6. **Python 3.13.18 versus 3.13.17.** Assumed: Mac pins 3.13.18 (the release's own version); Windows stays on 3.13.17.
7. **Interface authorization.** Assumed: not given yet; the content tasks wait for it (proposal, rule 11).
