# AGENTS.md

Instructions for AI agents working on eval-coach. Read this first, then the docs it points to. If this file and a doc disagree, the doc wins; fix this file.

## What this project is

eval-coach is a standalone Windows learning app for the **whole "Evaluated Systems (Stage 3)" series** (WPG AIR). The series goal: every participant, technical or not, can submit a Stage 3-ready task with documented, runnable test cases. There is no presenter and there are no handouts. The app is a local web server (Python standard library) that wraps the **participant's own AI CLI** in an embedded terminal. The shared example across the series is the Northwind weekly update.

The series has six parts (the per-Part detail is in the local course-context notes, see "Local working papers" below): 1 structured prompting, 2 defining evaluation criteria, 3 running evals and baseline, 4 iterating with evaluation-driven development, 5 load-bearing audit and packaging, 6 the participant's own task. Parts 1, 2 and 3 are built. In Part 3 the participant has an agent build a checker, checks the checker can be trusted, runs it on five outputs and records a baseline. Do not scope new work, naming or content to one Part alone; design so the other parts can be added.

Two tracks: **Script** (default; markdown test cases and a Python `check.py`) and **promptfoo** (pinned promptfoo 0.125.1 on a private Node).

## Where to look

| Need | File |
|---|---|
| Build spec, layout, storage, HTTP contract, course model | [docs/SPEC.md](docs/SPEC.md) |
| Preflight and setup wizard (setup checks, installs; global, not a Part) | [docs/SETUP.md](docs/SETUP.md) |
| Teaching, activity, wording and learning-priority rules for every Part's course | [docs/CONTENT-RULES.md](docs/CONTENT-RULES.md) |
| Part 3 course (lesson list, AI-window activities); Parts 1 and 2 are in `docs/SPEC.md` "Part 1" and "Part 2" | [docs/RUNNING-EVALS-COURSE.md](docs/RUNNING-EVALS-COURSE.md) |
| Interface design system ("Graphite and Lime", light/dark) | [docs/DESIGN.md](docs/DESIGN.md) |
| Stand-in end-to-end harness | [e2e-work/harness/README.md](e2e-work/harness/README.md) |
| Spec-driven pilot: OpenSpec specs and in-flight changes (`/opsx-propose`, `/opsx-apply`, `/opsx-archive`) | [openspec/](openspec/); project context in [openspec/config.yaml](openspec/config.yaml) |
| Change history and the record of each decision | `openspec/changes/archive/` (proposal, design, tasks and `verification.json` per change) and `git log` |

OpenSpec pilot: use it for changes that touch about three or more files or have unclear behavior; small fixes and content edits skip it. Where an OpenSpec spec exists for an area, it wins over `docs/SPEC.md` for that area. Keep `OPENSPEC_TELEMETRY=0` (telemetry is also turned off in the global config).

### Local working papers (not in git)

`docs/local/` and `docs/temp/` are git-ignored, so a fresh clone does not have them. They hold the implementation plan and its history (task tables, phase status, decisions, risks), the series intent and Stage 3 task notes, the course context for Parts 1 and 2, the Part 3 answer-key change record and the design preview page. If they are on this machine, read them for background and keep the plan's master task table in step with each change, but never stage them, quote them into tracked files, or copy their text into content, tests or specs. Tracked files must stand on their own: the OpenSpec specs and `docs/SPEC.md` carry what the code and content need.

## Status

Parts 1, 2 and 3 of the series are built and verified on the stand-in, and the app opens on a Series map of all six Parts: Parts 1, 2 and 3 open their courses, Parts 4 and 5 show "Coming soon", and Part 6 shows "Live meeting". Real-CLI confirmation (the two real Part 1 sessions and the real-tool runs of the quiet background AI test) waits for the user's approval. Setup is a global, skippable first-run wizard, not a course item. Every shipped change is an archived OpenSpec change under `openspec/changes/archive/`, and the current behavior is in `openspec/specs/` and `docs/SPEC.md`. Open work: the change `course-locking` is applied on the stand-in and waits for the archive gate, the user's wording review of the per-Part skip texts and the real `demo_hash.json` (made by the user with `tools\make_demo_hash.py`): it makes the series strictly sequential for participants (a lesson, step or Part opens only when it is done, skipped or the next to do; a Part opens only when every earlier Part is Done or Skipped; a locked item is refused with one lock message and no read-ahead preview, which reverses `read-ahead-always`; "Skip this Part" marks a whole Part Skipped after a plain confirm; the Series map opens on the active Part), and adds a hidden demo access (the app version in Settings, five selections, a password) that opens every Part for the current run only, one item at a time. Also open: the change `part-3-ai-flow` is applied on the stand-in and waits for the archive gate and the user's review (the nine Part 3 AI steps open the AI window by themselves the first time a step is opened, show the line to paste with a Copy button, offer "Open a new AI chat" in place of Start my AI, Send to AI and Start again, and close the window when the step passes; "Check my work" and every gate stay), so one AI window now behaves the same in Parts 1 and 3; its real-tool confirmation (one `generate` run and one `build` start per tool) needs the user's approval. The earlier change `step-flow` is archived (Part 1's `cold` and `rewrite` open the AI window by themselves on the first prompt save, no Part 1 step has "Check my work", and finished steps of Parts 1 and 2 offer "Start this step again"; the paste flow was confirmed on the three real tools on 2026-11-19). Packaging the release and a pilot with real users need the user's go-ahead before starting; the Mac port is deferred and starts only on request. Phase and task status (the plan's Phase 5, 6 and 7) is in the local plan (`docs/local/IMPLEMENTATION-PLAN.md`) when it is on this machine; otherwise rely on the OpenSpec archive and `git log`.

## Repository layout

```
app/eval_coach/        the app (stdlib only); module roles are listed in SPEC.md "Layout"
  content/*.json       all user-facing words (steps, preflight, lessons, glossary, lesson-ui, import-checks)
  kit/                 bundled skills/, northwind/, lessons/ files
  web/                 static UI, no build step
tests/                 unittest suite; tests/frontend holds the Playwright interface tests
tools/build_pyz.py     builds dist/eval-coach.pyz
tools/verify_receipt.py  records and checks verification receipts for OpenSpec changes
packaging/setup.cmd    participant entry point
dist/                  build output (generated)
e2e-work/              stand-in harness and its scratch homes, logs and screenshots (generated, except harness/)
spikes/                Phase 0 experiments; hold the private Python 3.13 and Node 26 runtimes and npm cache used by tests
```

Do not hand-edit `dist/`, or the scratch output under `e2e-work/` (everything except `e2e-work/harness/`; `e2e-work/eval-project/` is a working project folder the harness and tests use).

## Non-negotiable rules

1. **Python standard library only at runtime**, Python 3.9-compatible syntax, `from __future__ import annotations`. No pip packages. The browser UI has no build step.
2. **No permission flags** on the participant's CLI, and the app **never answers a CLI prompt**.
3. **Never parse terminal output to decide anything.** Decide by reading files and by running the checker directly. Two scoped exceptions. (a) Guided-setup, 2026-11-17: a process the app started itself, with no terminal, may be judged by its exit status alone, never by what it printed. Only the quiet background test of the chosen AI does this. (b) OpenSpec change `model-preference`: a tool's own `/model` list may be read in memory only to get a model ID, and the text before it only to avoid typing into a question; never for a result. The text is never written to a file.
4. "New chat" means a new CLI process; only one CLI process runs at a time.
5. Network use by the app is limited to consented preflight downloads (python.org, nodejs.org, the npm registry). No telemetry, no API keys, the app never calls a model.
6. The participant chooses the CLI from a fixed list of three tools (GitHub Copilot CLI, Claude Code, Devin CLI) that lives in `cli-recipes.json`. The only model choice is Sonnet or Haiku, a stored preference with a toggle in every AI window; the launch option for each tool (alias or exact ID, with a shipped fallback and the keyword used to find the ID) is `models` data in `cli-recipes.json`. No CLI-specific logic outside that data. A free-text command route stays only so the stand-in and the tests can run: the server accepts any command, and the interface shows the typed field only when the app is started with the hidden `--custom-ai` flag (OpenSpec change `guided-setup`). A command with no `models` data (the stand-in, a typed command) starts with no model option and shows no toggle.
7. Never suggest Copilot Chat in Teams. Northwind is a learning example and never a submission option.
8. Bundled skills stay **byte-identical** to their source files (the Part 3 skills come from the Session 3 materials); changes go in the line to paste.
9. No answer key exists until predictions are locked (`key` step, `key-work` folder, sealed storage outside the project). `progress.json` never holds answer keys, fixture text or course answers.
10. **Plain language** for non-technical readers. Never mention a presenter, facilitator, room, breakout, handout, neighbor, clock, or tell people to contact someone. Use "Script track" and "promptfoo track". Part, not session, is the app's word. Say "your AI" or "AI window", never a bare "CLI" (vendor names such as GitHub Copilot CLI stay), and "Practice task" and "My own task", never "Northwind" as an option name (OpenSpec change `content-clarity`; `tests/test_participant_vocabulary.py` enforces both). One exception (authorized 2026-11-15): Part 6 is a live troubleshooting meeting, so the app may say, as information only, that it happens live and that people can bring their task ideas to office hours or the AIR discussion. It is stated once, in `baseline-why` "Your own work", and nowhere else. The one other place is the Series map's Part 6 row (authorized 2026-11-15), which may say, as information only, that Part 6 is a live meeting and what it is about; it never mentions office hours, the AIR discussion, or any person, place, contact detail, link or schedule.
11. **Do not change the interface without the user's explicit authorization**: layout, styling, components, element ids, and interface copy (`web/`, `content/lesson-ui.json`, step `ui` blocks). Prefer changing content or server behavior so the existing interface shows it unchanged.
12. **Never modify the OneDrive source materials** (read-only; the location is in the local note `docs/local/SOURCE-MATERIALS.md`, not in git).
13. Keep OS-specific code in `conpty.py` and the setup scripts.

## Working conventions

- Add or update tests in the same task as the code. Update [docs/SPEC.md](docs/SPEC.md) when behavior or an API changes, and keep the local plan's master task table (`docs/local/`, not in git) in step when it exists.
- A task is finished only when its "Done when" check has been run and passed.
- Every word participants see lives in `content/*.json`, not in code.
- Lessons cite only bundled `kit:` files (enforced by a test). No external reading.
- The repo is under git, with `origin` on GitHub and `main` as the default branch. Do not commit, branch or push unless the user asks. After an archived OpenSpec change, the `post-archive-pr` skill (`.github/skills/post-archive-pr/`) does the branch, commit, push and PR, and runs only on request.
- Be careful with files in participant-facing storage: never overwrite an existing participant file when creating a project; resume if `.learning\progress.json` exists.

## Verification commands

Run from the repo root on Windows.

| Check | Command |
|---|---|
| Backend tests | `python -m unittest discover -s tests` |
| Backend on embedded 3.13 | `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests` |
| Interface tests | `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` |
| Build and smoke test | `python tools\build_pyz.py --smoke` |
| Stand-in end-to-end | `node e2e-work\harness\run-all.js --fresh` (add `--track promptfoo` or `--both`); write output to a file, not a pipe |
| Approval rule checks | `node e2e-work\harness\classifier-check.js` |

Notes:
- Verification receipts: the archive gate records each passed check with `python tools\verify_receipt.py write --change <name> --name <label> -- <command>` (labels `backend`, `backend-embedded`, `interface`, `build`, `e2e`; the lifecycle's Step 8 and `operations.archive.guidance` in `openspec/config.yaml` say which are required for a change). `post-archive-pr` skips its own test run only when `python tools\verify_receipt.py check --change <name> --staged --require <label> ...` (every required label) says `valid`: the staged snapshot, minus `openspec/` and ignored files, is exactly the tree that was tested.
- Run the two backend suites one after the other, never at the same time: the `setup.cmd` integration test fails when runs overlap.
- `test_conpty.RealConsole.test_type_line_sends_enter_separately` is timing-sensitive; rerun it once before treating a failure as real.
- Two tests are skipped by design. `test_promptfoo_real.py` skips when the spike's private Node and npm cache are absent. The tests that compare bundled files with their source (byte-identical skills, reference results) skip unless `EVAL_COACH_SOURCE_MATERIALS` points to the read-only source folder (its location is in `docs/local/SOURCE-MATERIALS.md`); set it when running the suites for an archive gate, so those checks run.
- Rebuild `dist/eval-coach.pyz` after app changes that affect the shipped archive.
- On Windows use backslash paths; PowerShell does not support heredocs.

## Rules for anything that touches a real CLI

- Use the stand-in `e2e-work/harness/fake_cli.py` unless the user has approved a real-CLI run. Lesson harness stages refuse to run unless `E2E_PROFILE=standin`.
- Real approvals are single-use "Yes" only, after the full command text is verified. Never choose "switch to auto mode" or "don't ask again".
- If a command is refused, bring it to the user. Do not widen the verifier on your own judgment.
- Each real-CLI run needs the user's approval. There is no session budget (the user lifted it on 2026-11-16). Folder-trust questions are answered only with the user's explicit approval, one single-use Yes per tool, and never for any other prompt.
- `e2e-work/harness/real-paste.js <claude|copilot|devin>` is the approved real-tool check of the Part 1 paste flow (one cold step per tool, on a throwaway home under `e2e-work\real-paste\`). The approval checker in `lib.js` knows each tool's trust and write-approval shapes (trust: `❯`, `›`, `>` or `❭` marker; Devin's `Writing <file>` approval with `❭ 1 Yes  (Approve once)`); anything else still stops the run and is brought to the user. Claude Code now starts in auto mode by default on every computer (the app passes no flag), so only `real-paste.js` may set `ALLOW_CLI_DEFAULT_AUTO_MODE=1` to accept that start; every other run still stops on auto mode (user decision, 2026-11-19).
- Never run a real CLI install recipe in a test. Never edit CLI settings or credentials.

## Sensitive items

- Four Phase 0 transcripts contain the account email (housekeeping item H2, waiting on the user). Do not copy or quote them, and do not delete them without the user's go-ahead.
- Never add secrets, tokens or personal data to content, tests or docs.
- The demo access password is never written anywhere in the repository, specs, tests, docs, logs or the shipped app: only a salted hash is kept (`app/eval_coach/demo_hash.json`, made by `python tools\make_demo_hash.py`, which reads the password at a prompt). Tests and the harness use their own throwaway password and hash. Do not create or commit a real `demo_hash.json`; the user runs the tool.
