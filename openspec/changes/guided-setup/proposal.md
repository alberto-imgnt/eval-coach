# Proposal

## Why

In the series review of 2026-11-16 a reviewer walked through setup and it asked for too much. Every check has its own page and its own Check button. The participant has to read terminal text, type the command that starts their AI, sign in on one page and then run a working test on another. "Another AI tool" asks non-technical people to know a command name. Nothing explains what the AI window is, even though every later Part happens inside it.

Setup should do the checking itself, send the participant only to pages that need them, and make choosing and testing an AI as close to one click as it can be. This is change 2 of the five series-review changes and builds on the vocabulary from `content-clarity` ("your AI", "AI window", "Practice task").

Source: `docs/temp/series-review-pending-changes.md`, area B, items 5, 5b, 5c, 6, 9, 9c and 9d.

## What Changes

- **Automatic summary check (items 5, 5b).** A new page after Track runs by itself: Python, and for the promptfoo track Node and promptfoo (offline only), the project folder, and which of the three supported AIs are installed. No Check button is needed and nothing moves on its own. When it ends, "Next" goes to the first page that needs the participant. Pages whose check already passed are skipped when moving forward and can still be reached with Back and from the page list.
- **Sign-in and the working test become one page (item 5b).** The "Sign in and license" page and its "I signed in" button are removed. One page starts the AI window, the participant signs in if asked, presses Send for the test line, and the app reads the test folder. A passing test proves the sign-in.
- **Choose your AI (items 6, 9d).** One page replaces the command field and the install list. If AIs were found, it offers to use one (preselected when exactly one, a pick when several). If none was found, it shows the three supported tools (GitHub Copilot CLI, Claude Code, Devin CLI) and offers assisted install of the chosen one. "Another AI tool" is removed for participants. A free-text command route stays for the stand-in CLI and the tests only.
- **Terminal only where the participant must act (item 5c).** The AI window shows on the sign-in and test page and while an install runs, framed as "your AI window". Every other page has no terminal. Installs are described in plain words with their size; the exact command sits behind a "Show the command" link.
- **AI window mini lesson (items 9, 9c).** A last wizard page, "Your AI window", explains what the participant is looking at with an annotated screenshot of the chosen tool (numbers over the image, a text legend, descriptions on hover and keyboard focus, real alt text). It can be reopened from Settings and from the AI window ("What am I looking at?"). It is not tracked as progress.
- **Skip for now stays** on every first-run page (item 18, already decided).

Out of scope:

- Model choice and the Sonnet/Haiku toggle (change 3). Setup still tells the participant nothing about models beyond what exists today.
- Course locking, the Skipped state, demo access (change 5).
- Part 1 AI flow (change 4).
- Detecting sign-in, or any other decision, by reading terminal output. Rule 3 stays whole: the app decides from files in the test folder and from resolving command names.
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

## Capabilities

### New Capabilities

- `ai-selection`: how setup finds the installed AIs, offers to use one, offers assisted install of one of the three supported tools, and keeps a free-text command route for tests only.
- `ai-window-lesson`: the last-page mini lesson with the annotated screenshot, and where it can be reopened.

### Modified Capabilities

- `setup-access`: wizard page order and the automatic summary check, Next/Back behavior with skipped passed pages, terminal only where the participant must act, the merged sign-in and working test page, Settings summary and setup completion with the extra last page.
- `settings-page`: the setup group also offers "What am I looking at?".

## Impact

- Backend: `app/eval_coach/preflight.py` (items, check-all order, AI detection, merged test, recipe view), `engine.py` (session ownership, test start and polling, removal of the separate sign-in session), `server.py` (routes), `content/cli-recipes.json` (plain-words field, `other` hidden from participants), `content/preflight.json` (all new wording and the lesson content).
- Frontend: `web/js/preflight.js`, `web/js/app.js`, `web/js/settings.js`, `web/js/panels.js`, `web/styles.css`, new `web/img/ai-window/`.
- Storage: `preflight.json` in the app home. `signin` item and `signed_in_command` become unused and are ignored on load, not migrated. Nothing in `progress.json` changes.
- Tests: `tests/test_preflight.py`, `tests/helpers.py`, `tests/frontend/ui.spec.js`, `e2e-work/harness/run.js`, content tests (banned words, "CLI" vocabulary, lesson content), new tests for AI detection, the merged test page and the lesson component.
- Docs: `docs/SPEC.md` (setup and preflight sections), `docs/PHASE2.md`, `docs/IMPLEMENTATION-PLAN.md` task table, `AGENTS.md` rule 6 (tool list fixed to three, test-only free-text route) and `docs/temp/series-review-pending-changes.md` (mark change 2 proposed).
- Real-CLI use: the three annotated screenshots need one real session per tool (3 sessions), each with explicit user approval and masked account data. All development and tests use `e2e-work/harness/fake_cli.py`.
- Sequencing: needs `content-clarity` (archived). Change 3 (model preference) puts its toggle on the merged test page afterwards.
