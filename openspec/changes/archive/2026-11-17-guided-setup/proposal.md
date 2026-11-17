# Proposal

## Why

In the series review of 2026-11-16 a reviewer walked through setup and it asked for too much. Every check has its own page and its own Check button. The participant has to read terminal text, type the command that starts their AI, sign in on one page and then run a working test on another. "Another AI tool" asks non-technical people to know a command name. Nothing explains what the AI window is, even though every later Part happens inside it.

Setup should do the checking itself, send the participant only to pages that need them, and make choosing and testing an AI as close to one click as it can be. This is change 2 of the five series-review changes and builds on the vocabulary from `content-clarity` ("your AI", "AI window", "Practice task").

Source: `docs/temp/series-review-pending-changes.md`, area B, items 5, 5b, 5c, 6, 9, 9c and 9d.

## What Changes

- **Automatic summary check (items 5, 5b).** A new page after Track runs by itself: Python, and for the promptfoo track Node and promptfoo (offline only), the project folder, and which of the three supported AIs are installed. No Check button is needed and nothing moves on its own. When it ends, "Next" goes to the first page that needs the participant. Pages whose check already passed are skipped when moving forward and can still be reached with Back and from the page list.
- **Sign-in and the working test become one page (item 5b).** The "Sign in and license" page and its "I signed in" button are removed. One page starts the AI window, the participant signs in if asked, presses Send for the test line, and the app reads the test folder. A passing test proves the sign-in.
- **Choose your AI (items 6, 9d).** One page replaces the command field and the install list. If AIs were found, it offers to use one (preselected when exactly one, a pick when several). If none was found, it shows the three supported tools (GitHub Copilot CLI, Claude Code, Devin CLI) and offers assisted install of the chosen one. "Another AI tool" is removed for participants. A free-text command route stays for the stand-in CLI and the tests only.
- **Background AI test (added 2026-11-17).** Pressing "Use this AI" saves the AI and, by itself, runs a hidden one-shot test with that tool's non-interactive mode: no window, no terminal, nothing typed, no permission flags. The result is the process exit code. On a pass the AI working test counts as passed and the wizard moves on by itself. If the hidden run cannot finish (typically because the participant is not signed in, or the tool needs a trust or permission answer), the wizard moves to the visible AI working test page with a plain "needs you" line, where the participant signs in in the AI window and runs the existing write-and-run test. The background test proves the AI starts, is signed in and replies; it cannot prove write and run ability, because the tools refuse both in one-shot mode without permission flags (rule 2).
- **Check everything only where it helps (added 2026-11-17).** The footer "Check everything" button is shown only on the pages where a participant can fix something outside the app and needs a way to look again: Python, Node.js, promptfoo, Choose your AI and Project folder. It is removed from Track, Checking your computer (which runs the checks by itself), AI working test (which has its own check) and Your AI window. Its label stays the same, so the messages that name it stay true.
- **Terminal only where the participant must act (item 5c).** The AI window shows on the sign-in and test page and while an install runs, framed as "your AI window". Every other page has no terminal. Installs are described in plain words with their size; the exact command sits behind a "Show the command" link.
- **AI window mini lesson (items 9, 9c).** A last wizard page, "Your AI window", explains what the participant is looking at with an annotated screenshot of the chosen tool (numbers over the image, a text legend, descriptions on hover and keyboard focus, real alt text). It can be reopened from Settings and from the AI window ("What am I looking at?"). It is not tracked as progress.
- **Skip for now stays** on every first-run page (item 18, already decided).

Out of scope:

- Model choice and the Sonnet/Haiku toggle (change 3). Setup still tells the participant nothing about models beyond what exists today.
- Course locking, the Skipped state, demo access (change 5).
- Part 1 AI flow (change 4).
- Detecting sign-in, or any other decision, by reading terminal output or any text a tool prints. Rule 3 stays whole except for one clarification: the background test decides from the exit code of its own one-shot process, never from its output. Everything else is decided from files in the test folder and from resolving command names.
- Permission flags (`--allow-all-tools`, `--permission-mode`, `--dangerously-skip-permissions` and the like) in the background test, and answering any prompt. A tool that needs an answer simply ends the background test as "needs you".
- Signing in without a window. Sign-in always happens in the visible AI window.
- Installing anything without consent, or answering a prompt in the AI window (rules 2 and 5). Install recipes are not run in tests (AGENTS "real CLI" rules).
- Removing "CLI" from code, ids, file names and `cli-recipes.json` keys.
- Technical or non-technical mode (item 0, deferred).

## Interface authorization (AGENTS.md rule 11)

This change reshapes the setup interface. The series review decisions (items 5 to 9d) call for it, but the explicit authorization required by rule 11 is **to be given by the user when this proposal is reviewed**. No file under `web/`, no `content/lesson-ui.json` or step `ui` block, and no interface copy may be edited by `/opsx-apply` until the user confirms the scope below:

- Wizard: the new automatic summary page, jumping to pages that need the participant (skipping passed pages going forward), the merged sign-in and test page, the choose-your-AI page, "Show the command" links, terminal shown only on the sign-in and test page and during an install, the "your AI window" framing, and the new last page.
- The annotated screenshot component (image, numbered markers, legend, hover and focus descriptions) and its reopen entries: a "What am I looking at?" control in the AI window head and an entry in the Settings setup group.
- Removal of the typed command field, the "Another AI tool" card and the "I signed in" button from the participant view. The typed command field stays visible only when the app is started with the test-only flag (see design).
- Copy in `content/preflight.json`, `content/settings.json` and the labels of the wizard in `web/js/`.
- New files: `web/img/ai-window/` screenshots and any new styles needed in `web/styles.css`, using the existing design system (`docs/DESIGN.md`).

Anything beyond this list needs a new authorization.

**Addition requested 2026-11-17 (Check everything):** the footer "Check everything" button is no longer rendered on Track, Checking your computer, AI working test and Your AI window. Nothing else in the interface changes. The user chose this option when asked.

**Addition requested 2026-11-17 (background AI test):** the Choose your AI page shows a "Testing your AI" progress line with no terminal after "Use this AI" and moves on by itself when the test ends; the AI working test page shows a plain line saying the quiet test could not finish and what to do in the AI window. Copy goes in `content/preflight.json`. Nothing else in the interface changes. The user asked for the behavior; the page text and automatic move are confirmed with the artifact edits.

**Authorization recorded (2026-11-16):** the user confirmed the full scope above when asking to apply this change, and accepted the assumed defaults for design open questions 2 to 8.

## Capabilities

### New Capabilities

- `ai-selection`: how setup finds the installed AIs, offers to use one, runs a hidden background test when one is chosen, offers assisted install of one of the three supported tools, and keeps a free-text command route for tests only.
- `ai-window-lesson`: the last-page mini lesson with the annotated screenshot, and where it can be reopened.

### Modified Capabilities

- `setup-access`: wizard page order and the automatic summary check, Next/Back behavior with skipped passed pages, terminal only where the participant must act, the merged sign-in and working test page, Settings summary and setup completion with the extra last page.
- `settings-page`: the setup group also offers "What am I looking at?".

## Impact

- Backend: `app/eval_coach/preflight.py` (items, check-all order, AI detection, merged test, recipe view, background test job), `engine.py` (session ownership, test start and polling, removal of the separate sign-in session, starting and cancelling the background test from `preflight_cli`), `server.py` (routes), `content/cli-recipes.json` (plain-words field, `other` hidden from participants, per-tool `headless` argv and time limit), `content/preflight.json` (all new wording and the lesson content, background test text), `e2e-work/harness/fake_cli.py` (one-shot mode for the stand-in).
- Frontend: `web/js/preflight.js`, `web/js/app.js`, `web/js/settings.js`, `web/js/panels.js`, `web/styles.css`, new `web/img/ai-window/`.
- Storage: `preflight.json` in the app home. `signin` item and `signed_in_command` become unused and are ignored on load, not migrated. Nothing in `progress.json` changes.
- Tests: `tests/test_preflight.py`, `tests/helpers.py`, `tests/frontend/ui.spec.js`, `e2e-work/harness/run.js`, content tests (banned words, "CLI" vocabulary, lesson content), new tests for AI detection, the merged test page and the lesson component.
- Docs: `docs/SPEC.md` (setup and preflight sections), `docs/PHASE2.md`, `docs/IMPLEMENTATION-PLAN.md` task table, `AGENTS.md` rule 6 (tool list fixed to three, test-only free-text route) and `docs/temp/series-review-pending-changes.md` (mark change 2 proposed).
- Real-CLI use: the three annotated screenshots need one real session per tool (3 sessions), each with explicit user approval and masked account data. The background test's per-tool argv and time limit are confirmed with one real one-shot run per tool, also with explicit single-use approval. All development and tests use `e2e-work/harness/fake_cli.py`.
- Sequencing: needs `content-clarity` (archived). Change 3 (model preference) puts its toggle on the merged test page afterwards.
