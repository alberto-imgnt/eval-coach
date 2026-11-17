# Design

## Context

Setup today is a full-page wizard (`web/js/preflight.js`, `renderWizard`) with one page per item in `ITEM_IDS` (`track`, `python`, `node`, `promptfoo`, `cli`, `signin`, `working_test`, `project`). Each page has its own Check button; "Check everything" is one button in the footer. The `cli` page asks for a typed command, offers recipes from `cli-recipes.json` (including `other`), and has a "Start my AI" button that opens a sign-in session (`PF_SIGNIN`). The participant then confirms sign-in (`signin`) and later runs the working test in a second AI process (`PF_TEST`) with Start, Send and Check buttons. The terminal shows on `cli`, `signin` and `working_test`.

Facts checked in the code:

- `Preflight.start_check_all` already runs python, node, promptfoo, cli, signin, working_test and project in one background job, and node/promptfoo checks are already offline (`npm_config_offline`).
- Installed tools can be found by `terminal.check_command(cli_command, env)` for each recipe with a `cli_command`; this only resolves the name.
- Sign-in cannot be detected without reading terminal output (rule 3). The working test already proves it by reading `output.txt` and `version.txt` in `<home>\cli-test`.
- The app cannot tell when the AI is ready for a line, so Send stays a participant action.
- `app.js` closes the wizard on the Series map after `/api/setup` succeeds (the project page is the last page today).

Rules that shape this: rules 2, 3 and 5 (no answering, no terminal parsing, consented downloads only), rule 6 (CLI-specific data only in `cli-recipes.json`), rule 10 (plain words, "your AI"/"AI window"), rule 11 (interface authorization, see proposal).

## Goals / Non-Goals

**Goals:**

- Checks run by themselves and the participant lands only on pages that need them.
- Choosing an AI is one click when one is installed; assisted install when none is.
- Sign-in and the working test are one step.
- A terminal appears only where the participant must act.
- A last page explains the AI window with an annotated screenshot per tool.

**Non-Goals:**

- Model choice (change 3), the Part 1 AI flow (change 4), locking (change 5).
- Any decision made from terminal text.
- Migrating old `preflight.json` content beyond ignoring what is no longer used.

## Decisions

### 1. Page model

The wizard page list is built on the client from the preflight view and two non-check pages:

`track` → `summary` (new, "Checking your computer") → `python` → `node`, `promptfoo` (promptfoo track) → `cli` ("Choose your AI") → `working_test` ("AI working test") → `project` → `ai_window` (new lesson page).

`summary` and `ai_window` are client page ids, not items in `ITEM_IDS`. They carry no status in `preflight.json`. `firstWizardItem` stays: first page whose check has not passed, Track on a fresh setup. Forward navigation (`wizardGo` from Next) goes to the first later page whose item is not `passed`, falling to `ai_window` when none is left; Back and the page dots go to any page. `summary`'s Next is enabled once a check run has finished in this wizard visit (`ran_once` and no running job); `ai_window`'s check counts as passed always. Alternative considered: hide passed pages from the list. Rejected because "n of total" then jumps around and Back cannot reach a passed page.

### 2. Items: `signin` is removed, `cli` means "chosen and found"

- `ITEM_IDS` loses `signin`. Old files keep `signin` and `signed_in_command` keys; `_load` ignores unknown item ids already, and the extra top-level key is left alone. Nothing is migrated (nothing is live).
- `cli` passes when a command is saved and `terminal.check_command` resolves it. The `launched_command` requirement is dropped. `cli_found` ("needs_you") becomes a pass; `cli_launched` is unused.
- `working_test` becomes available when `cli` passes (`require_test_ready` no longer needs `signin`). Passing it still stores `test_passed_command`. A changed command still clears `test_passed_command`.
- `PF_SIGNIN` and `preflight_cli_start`, `preflight_signin_confirm` and their routes are removed. `PF_TEST` is the only AI session in setup besides `PF_RECIPE` (install).

### 3. Automatic summary check

The `summary` page calls `POST /api/preflight/check` when it is shown (client guards against a second call while `job.running`) and on every arrival. `_job_check_all` runs python, node, promptfoo, a new `_detect_ais`, cli, working_test (re-read only) and project. `_detect_ais` stores nothing in `preflight.json`; it returns the found list in the view as `cli.found` (recipe ids whose `cli_command` resolves, deduplicated by `cli_command`). It never starts a tool. `working_test` re-read uses `check_test_result` only if the test was passed for the same command before; otherwise it stays "needs you".

The page shows one row per check with the existing status words and a Next that follows decision 1. Nothing is auto-advanced. If a check throws, `_guarded` already reports it as failed.

### 4. Choose your AI

View additions in `Preflight.view`: `cli.tools` (replaces the `recipes` list for participants): one entry per distinct `cli_command` among non-hidden recipes except `other`, each with `id`, `name`, `found` (bool), `preselect` (true when exactly one tool is found and none is chosen), `install` (the first recipe for that `cli_command`: plain text, size, consent view, requirement, `command`) and `other_installs` (further recipes for the same tool, for example Claude winget, shown behind "Another way to install"). `cli-recipes.json` gains a `plain` field per recipe (plain-words description) and `other` gets `"participant": false`; the PowerShell prerequisite recipe stays `hidden`.

The page lists the three tools. A found tool has "Use this AI"; a missing tool has "Install" (consent, then `POST /api/preflight/cli/recipe`, unchanged) and a "Show the command" disclosure (`<details>`, command text from the recipe). "Use this AI" calls the existing `POST /api/preflight/cli` with that tool's `cli_command`. After an install the page re-runs the checks (`POST /api/preflight/check`) when the install session ends, so the new tool is found. The terminal shows here only while the session owner is `PF_RECIPE`.

**Test-only free text.** `__main__.py` gets a `--custom-ai` flag (hidden from `--help`), passed to `Preflight`/`Engine` and exposed as `view["custom_ai"]`. The typed field and its "Check this command" button render only when `custom_ai` is true. The server route `/api/preflight/cli` already accepts any string and stays as is. `e2e-work/harness` and `tests/helpers.py` start the app with the flag.

### 5. Merged sign-in and working test

This visible page is what the participant reaches when the background test (decision 9) does not pass, and what Back or the page list opens at any time. The working test page offers, in order: Start my AI window (`POST /api/preflight/test/start`, clears and prepares the test folder, starts `PF_TEST`), the test line with a Send button (`/api/preflight/test/send`), and a Check button (`/api/preflight/test/check`). A short line says to sign in in the AI window if asked.

Quiet polling: after `session.sent` is true and the session is running, the client calls a new read-only route `POST /api/preflight/test/poll` every 3 seconds. It calls `Preflight.poll_test_result()`, which reads `output.txt` and `version.txt` and, only when both are right, records the pass (same as `check_test_result` success path) and returns `passed`. It never records a failure and never writes a failure message. Polling stops when the page is left, the session stops or the test passes. On a pass the engine stops the AI process (`_stop_cli`) exactly as `preflight_test_check` does today.

The existing failure message `cli_not_signed_in` ("also") stays and is shown by the Check button.

### 6. Terminal visibility

`wizardUsesTerminal` returns true for `working_test`, and for `cli` only while `state.terminal.owner === 'preflight:recipe'` and it is running. The background test (decision 9) never uses the terminal, so it never shows one. During an install, the participant can move to another page; the AI window then stays hidden except on `cli`/`working_test`, but the process keeps running (already true: moving pages does not stop it). The head of the terminal pane is framed as "Your AI window" (label strings in `preflight.json`; session labels already come from `session_labels`).

### 7. Mini lesson page and reopening

New content key `ai_window_lesson` in `content/preflight.json`:

```
{ "title": "Your AI window", "intro": "...", "legend_heading": "...",
  "tools": { "copilot": {"image": "img/ai-window/copilot.png", "alt": "...",
              "markers": [{"n": 1, "x": 12.5, "y": 8, "label": "...", "text": "..."}, ...]}, "claude": {...}, "devin": {...} },
  "generic": {"markers": [...]}, "reopen_label": "What am I looking at?", "close": "..." }
```

Markers are positioned in percent of the image so they scale with it. They are focusable buttons-as-text (`tabindex=0`, `role="img"` wrapper with an `aria-label`, `aria-describedby` on a tooltip) with the same description as the legend. The legend is an ordered list below the image. A shared `renderAiWindowLesson(ctx)` in `web/js/preflight.js` (or a new `web/js/ai-window.js`) is used by the wizard page, the Settings dialog and the AI window dialog, so the text lives once. The tool shown is found from the saved `cli_command` by matching it with `cli-recipes.json` `cli_command`; no match (stand-in) shows `generic` without an image.

The `ai_window` page is the wizard's last page. The existing `pfProject` path in `app.js` stops closing the wizard: it sets a client flag `wizardFinishing = true` that keeps the wizard open and moves to `ai_window`; its "Finish" button runs the old close logic (Series map, clear drafts). `screen` selection (`app.js` ~line 152) keeps showing the wizard while the flag is set even though `pf.passed` is now true.

Screenshots: `web/img/ai-window/{copilot,claude,devin}.png`, captured with Playwright from the app's own AI window after setup, one session per tool on a real CLI with explicit user approval. Account name and email are masked in the image (drawn over before saving) and the capture is checked by eye before use. Marker data and alt text are written after the capture.

Reopening: Settings gets a "What am I looking at?" button in the setup group (`web/js/settings.js`), and the AI window head (`renderPreflightTermHead` and the lesson/step AI window heads in `panels.js`) gets a link of the same label. Both open `web/js/dialog.js` with the same component and close back.

### 8. Settings summary

`settings.js` lists items from the same source as the wizard (the view's `items`, now without `signin`, plus the `cli` row reading "Your AI") and the two buttons.

### 9. Background AI test (added 2026-11-17)

**What the tools allow.** Per each vendor's documentation, GitHub Copilot CLI (`-p`), Claude Code (`-p`) and Devin CLI (`-p`) each have a one-shot mode that runs a prompt and exits. In that mode nobody can answer an approval prompt: without permission options, writes and shell commands are denied (Copilot says so explicitly; Devin's Normal mode prompts for writes and shell). The visible test (write `output.txt`, run `python --version`) therefore cannot run headless without permission flags, which rule 2 forbids. The background test is a different, weaker test by design.

**Trigger.** `Engine.preflight_cli` already runs when the participant presses "Use this AI" (and for the typed route under `--custom-ai`). After `set_cli_command` and only when the command resolves and `test_passed_command` is not already that command, it calls `Preflight.start_ai_test()`. No new client call is needed; the client sees the job in the view it already polls. A new command, a visible test start (`preflight_test_start`) or an install start cancels a running background test first.

**The run.** `start_ai_test` starts a thread (like `start_check_all`) that:

1. Looks up the tool's `headless` entry in `cli-recipes.json` by matching `cli_command` (rule 6: CLI-specific data only there). Shape: `"headless": {"args": ["-p", "{line}"], "timeout_seconds": 120}`. No entry (the stand-in, a custom command without data) means no background test, and the wizard goes straight to the visible page.
2. Fills `{line}` with `working_test.headless_line` from `content/preflight.json` ("Reply with the single word OK."). The prompt needs no tool, so no permission or folder-trust question arises.
3. Runs the command with `subprocess` (through the preflight runner) in `<home>\cli-test\` with no window (`CREATE_NO_WINDOW`) and stdin from `DEVNULL`. Its output is captured in memory by the runner and discarded; nothing reads it. It does not use `terminal`, `PF_TEST` or `_cli_step`, so no terminal appears and rule 4 is kept by refusing to start while any AI session runs. A visible test start and an install start cancel it. Other session starts cannot overlap it, because the lessons and steps stay locked until the working test has passed.
4. Waits up to `timeout_seconds` (default 120 s, overridable per tool). On the limit it kills the process tree. The value is a starting estimate: the docs give no timing, and a cold one-shot start plus one model reply is expected to take well under a minute. It is confirmed with one approved real run per tool during apply and can be changed in data without code. **Measured 2026-11-17** (real runs through `Preflight.start_ai_test()`, each exit status 0, output "OK", no window): GitHub Copilot CLI 22.7 s, Claude Code 5.1 s, Devin CLI 11.1 s. The 120 s limit stays: more than five times the slowest. Copilot's one-shot run uses model credits and leaves a resumable session on the participant's account; that is the price of the test and is not removed by the app. Sign-out behavior (what each tool does when not signed in, and whether any opens a browser) was not measured, because that needs the account signed out and the app never edits credentials; the design already sends any non-zero exit or timeout to the visible page.
5. Records the result: exit code 0 → `working_test` passed with `test_passed_command` set and message `working_test_passed_background`. Any non-zero exit, a timeout or a start error → `working_test` `needs_you` with message `ai_test_background_needs_you`. It never records `failed`.

**Rule 3 clarification.** The verdict is the exit status of a process the app started itself, not terminal text and not anything the tool printed. AGENTS.md rule 3 is clarified to say so; the log file is never read for a decision.

**Sign-in.** The hidden run cannot sign in: stdin is closed and there is no window, so a tool that is not signed in ends non-zero (or hits the time limit if it waits). That outcome is the fallback: the wizard goes to the visible AI working test page, whose text says the quiet test could not finish and that the participant may need to sign in in the AI window. There they start the AI window, sign in as the tool asks, press Send and the existing checks (quiet polling, Check button) decide from the test folder, as in decision 5. Because a non-zero exit cannot tell "not signed in" from "needs a trust or permission answer" or "no network", the text names all three in plain words.

**Client.** After "Use this AI" the Choose your AI page shows a "Testing your AI" line (no terminal; Use this AI, the installs and Next disabled) while the job runs. When it ends the wizard moves by itself to the first page whose item has not passed (decision 1): Project folder (or Your AI window when everything passes) after a pass, the AI working test page after "needs you". An AI with no quiet test leaves the page as it was. The typed `--custom-ai` route behaves the same when the command has `headless` data. The client learns the state from `working_test.background.state` (`idle`, `running`, `passed`, `needs_you`) in the preflight view, kept in memory only; a quiet pass is remembered in `preflight.json` as `test_passed_quietly`, so a later check of everything keeps it passed without test files to re-read.

**What it proves.** The AI starts, is signed in, and replies. The visible test additionally proved write and run ability. With the visible page skipped after a background pass, the first write or run request in a later Part appears as a normal approval prompt in the AI window, which the participant answers, as the series already teaches. Accepted trade-off for a smoother setup.

**Alternative considered: a hidden interactive session where the app types the test line.** Rejected: the app cannot tell when the AI is ready, so the line can be lost or land in a sign-in or trust prompt, which would be answering a prompt (rule 2).

### 10. Check everything only where it helps (added 2026-11-17)

The footer "Check everything" button (`#pf-check-all`) is rendered only on pages whose check can fail or change because of something the participant does outside the app: `python`, `node`, `promptfoo`, `cli` and `project`. It is not rendered on `track` (nothing is checked yet), `summary` (it runs the checks by itself on every arrival), `working_test` (it has its own "Check the test result" and a quiet re-read) and `ai_window` (a lesson). The label and the id stay, and the button still runs `POST /api/preflight/check`, so every message that says "choose Check everything again" stays true. Alternatives considered: removing it everywhere with a re-check on window focus (more logic and every message reworded), and leaving it on every page (noise on four pages, and a duplicate of what the summary page just did). The same `Preflight` code runs either way; only `renderWizard` changes.

## Files and storage touched

| Location | Kept or cleared |
|---|---|
| `<home>\preflight.json` | Kept. `signin` item and `signed_in_command` are ignored, not removed. `cli_command`, `test_passed_command`, `track`, `setup_skipped`, `ran_once` unchanged. `launched_command` is no longer written or read. |
| `<home>\cli-test\` | Cleared on each test start (as today); read by the quiet poll. The background test also runs here (as its working folder) and writes nothing. |
| `<home>\cli-signin\` | No longer created; an existing folder is left in place. |
| `<home>\cli-install\` | Cleared on each install start (as today). |
| `<home>\cli-recipes.json` override | Still read if present; entries without `plain` fall back to `note`. |
| `<home>\reset-backup\` | Unchanged. A configuration reset still moves `preflight.json` away. |
| `progress.json` | Not touched. The mini lesson writes nothing. |
| `app/eval_coach/content/preflight.json` | New text: summary page, choose-your-AI, merged test page, lesson, Settings buttons. Removes sign-in text and `cli_hint`, `recipe_*` wording that mentions typing. |
| `app/eval_coach/content/cli-recipes.json` | `plain` field per recipe; `other` marked not for participants; per-tool `headless` argv and `timeout_seconds`. |
| `app/eval_coach/content/settings.json` | "What am I looking at?" label. |
| `app/eval_coach/web/js/{preflight,app,settings,panels,dialog}.js`, `web/styles.css` | Wizard pages, quiet poll, lesson component, reopen entries. |
| `app/eval_coach/web/img/ai-window/` | New screenshots (masked). Shipped in the `.pyz`. |
| `app/eval_coach/{preflight,engine,server,__main__}.py` | Items, detection, merged test, poll route, `--custom-ai`, removal of the sign-in session and routes. |
| `docs/SPEC.md`, `docs/PHASE2.md`, `docs/IMPLEMENTATION-PLAN.md`, `AGENTS.md`, `docs/temp/series-review-pending-changes.md` | Updated in the same change. |
| `dist/eval-coach.pyz` | Rebuilt. |

## Risks / Trade-offs

- **Auto-running checks on arrival** reruns every time the participant visits the page; checks are cheap (offline, name resolution), but the promptfoo offline check can take a few seconds. The job is the same one the footer button runs today and shows progress.
- **Quiet polling uses files only**, so it never decides from terminal text. The Check button remains the only place a failure is reported.
- **Dropping the sign-in item** loses the "AI started" proof the old `launched_command` gave. The working test is a stronger proof, so this is accepted.
- **Two ways to install Claude** (installer script and winget): only the first is the main option; the second is behind "Another way to install" to keep the page to three tools.
- **Screenshots go stale** when a tool's window changes. Markers are percentages of a fixed image, so a new screenshot needs its marker data checked by hand. Each tool's entry in the content file records the date of its capture in a `captured` field.
- **Real-CLI sessions** (3) are needed for the screenshots, one per tool, each with explicit single-use approval. If a tool cannot be run, its page shows the generic legend until a capture exists.
- **Tests that start the app** must pass `--custom-ai`; forgetting it hides the typed field and the stand-in cannot be entered through the UI.
- **Devin's window** may need a different approach to mask personal data; its capture is reviewed before it is committed to the content.
- **Background test is weaker than the visible test** (decision 9): it does not prove write or run ability, and a pass skips the visible page. The first approval prompt in a later Part is the participant's first meeting with approvals.
- **Exit code is coarse.** A non-zero exit cannot say why. The visible fallback names the three likely causes. A tool that opens a browser for login in one-shot mode would be unwanted, so the real run per tool checks that none does; if one does, its `headless` entry is removed and it goes straight to the visible page.
- **One-shot flags may change** between tool versions. They live in data, and a wrong entry only sends the participant to the visible page (never a failure).
- **A hung tool** is bounded by the time limit and a process-tree kill; the background run never blocks the rest of setup.

## Open Questions

Confirm or change each; the assumed default is what the tasks implement.

1. **Interface authorization (rule 11).** Do you authorize the scope listed in the proposal? *Assumed: not yet. Apply must wait for your confirmation before touching `web/` or interface copy.*
2. **Test-only flag name.** `--custom-ai` on the command line. *Assumed: this name, off by default, hidden from `--help`.*
3. **Forward navigation skips passed pages.** *Assumed: yes (decision 1).*
4. **Claude Code install options.** Show only the installer script as the main option with winget behind "Another way to install". *Assumed: yes.*
5. **Quiet polling interval** for the test folder. *Assumed: every 3 seconds, only after Send, only while the page is open and the session runs.*
6. **Last page shows for everyone**, including participants who already completed setup earlier and reopen it from Settings: it is the last page of the wizard but "Finish" in Settings closes back to Settings. *Assumed: yes.*
7. **Reopen as a dialog** (not a wizard page) from Settings and the AI window. *Assumed: dialog via `dialog.js`.*
8. **Screenshot capture timing.** Capture after the page layout is built, so the three real sessions (one per tool, approved one by one) come at the end of apply. *Assumed: yes.*
9. **Background test decided by exit code** (rule 3 clarification), read-only prompt, no permission flags, 120 s limit per tool in data, automatic move on both outcomes, visible page as the sign-in fallback. *Confirmed by the user on 2026-11-17 (time limit to be checked in the approved real runs).*
