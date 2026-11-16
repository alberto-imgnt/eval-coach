# AGENTS.md

Instructions for AI agents working on eval-coach. Read this first, then the docs it points to. If this file and a doc disagree, the doc wins; fix this file.

## What this project is

eval-coach is a standalone Windows learning app for the **whole "Evaluated Systems (Stage 3)" series** (WPG AIR). The series goal: every participant, technical or not, can submit a Stage 3-ready task with documented, runnable test cases. There is no presenter and there are no handouts. The app is a local web server (Python standard library) that wraps the **participant's own AI CLI** in an embedded terminal. The shared example across the series is the Northwind weekly update.

The series has six parts (details in [docs/COURSE-CONTEXT.md](docs/COURSE-CONTEXT.md)): 1 structured prompting, 2 defining evaluation criteria, 3 running evals and baseline, 4 iterating with evaluation-driven development, 5 load-bearing audit and packaging, 6 the participant's own task. Part 3 is the part built so far: the participant has an agent build a checker, checks the checker can be trusted, runs it on five outputs and records a baseline. Do not scope new work, naming or content to Part 3 alone; design so the other parts can be added.

Two tracks: **Script** (default; markdown test cases and a Python `check.py`) and **promptfoo** (pinned promptfoo 0.125.1 on a private Node).

## Where to look

| Need | File |
|---|---|
| Build spec, layout, storage, HTTP contract, course model | [docs/SPEC.md](docs/SPEC.md) |
| Task list, phase status, decisions, verification commands | [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) |
| Preflight (setup checks, installs) | [docs/PHASE2.md](docs/PHASE2.md) |
| Lessons and course content | [docs/PHASE3.md](docs/PHASE3.md) |
| Answer key is sealed until predictions are locked | [docs/KEY-AFTER-LOCK.md](docs/KEY-AFTER-LOCK.md) |
| Interface design system ("Graphite and Lime", light/dark) | [docs/DESIGN.md](docs/DESIGN.md) |
| What the whole series is for: the method, the six Parts, why it matters, the Stage 3 link (source of intent) | [docs/SERIES-INTENT.md](docs/SERIES-INTENT.md) |
| What the Stage 3 task is: the Prompt, the Evaluations and the Log, and what is checked in each | [docs/STAGE3-TASK-SPEC.md](docs/STAGE3-TASK-SPEC.md) |
| What participants learned in earlier parts; Northwind details | [docs/COURSE-CONTEXT.md](docs/COURSE-CONTEXT.md) |
| Stand-in end-to-end harness | [e2e-work/harness/README.md](e2e-work/harness/README.md) |
| Spec-driven pilot: OpenSpec specs and in-flight changes (`/opsx-propose`, `/opsx-apply`, `/opsx-archive`) | [openspec/](openspec/); project context in [openspec/config.yaml](openspec/config.yaml) |

OpenSpec pilot: use it for changes that touch about three or more files or have unclear behavior; small fixes and content edits skip it. Where an OpenSpec spec exists for an area, it wins over `docs/SPEC.md` for that area. Keep `OPENSPEC_TELEMETRY=0` (telemetry is also turned off in the global config).

## Status

The build covers Part 3, Part 1 and Part 2 of the series, and the app opens on a Series map (OpenSpec change `add-series-map`, archived; its specs are in `openspec/specs/`) that lists all six Parts: Parts 1, 2 and 3 open their courses, Parts 4 and 5 show "Coming soon", and Part 6 shows "Live meeting". Part 1 (structured prompting, OpenSpec change `add-part-1`) is built and verified on the stand-in: four lessons and five steps, with three step kinds in `app/eval_coach/part_steps.py` and panels in `web/js/part-steps.js`; its real-CLI runs (two real sessions, the cold run and the rewrite run) wait for the user's approval. Part 2 (defining evaluation criteria, OpenSpec change `add-part-2`) is built on the stand-in: four lessons and four steps, with three step kinds in `app/eval_coach/criteria_steps.py` and panels in `web/js/criteria-steps.js`; it runs nothing (no CLI, checker or model), so it uses no real-CLI budget, and its final integration check and the user's wording review before archive are pending. Phases 0 to 4 of the current plan are done (on the stand-in; real-CLI confirmation is in Phase 6). Setup is now a global, skippable first-run screen (not a course item) presented as a full-page wizard with one check per page and no sidebar beside it, and a Settings panel (before Quit in the sidebar) holds the text size slider, a setup summary with an "Open setup" button that opens the same wizard, and the two resets ("Reset lesson progress" and "Reset app configuration"; one backup folder, `<home>\reset-backup\`); this came from the OpenSpec change `add-settings-section` (archived; its specs are in `openspec/specs/`). The plan and specs otherwise still describe the content as Part 3 (with the Part 1 and Part 2 additions in `docs/SPEC.md` "Part 1" and "Part 2"); they predate the whole-series scope and need updating when the user asks for series work on the other Parts. Phase 5 (package) and Phase 6 (pilot) need the user's go-ahead before starting. Phase 7 (Mac) is deferred and starts only on request. Check [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) for current state before picking up work.

## Repository layout

```
app/eval_coach/        the app (stdlib only); module roles are listed in SPEC.md "Layout"
  content/*.json       all user-facing words (steps, preflight, lessons, glossary, lesson-ui, import-checks)
  kit/                 bundled skills/, northwind/, lessons/ files
  web/                 static UI, no build step
tests/                 unittest suite; tests/frontend holds the Playwright interface tests
tools/build_pyz.py     builds dist/eval-coach.pyz
packaging/setup.cmd    participant entry point
dist/                  build output (generated)
e2e-work/              stand-in harness and its scratch homes, logs and screenshots (generated, except harness/)
spikes/                Phase 0 experiments; hold the private Python 3.13 and Node 26 runtimes and npm cache used by tests
```

Do not hand-edit `dist/`, or the scratch output under `e2e-work/` (everything except `e2e-work/harness/`; `e2e-work/eval-project/` is a working project folder the harness and tests use).

## Non-negotiable rules

1. **Python standard library only at runtime**, Python 3.9-compatible syntax, `from __future__ import annotations`. No pip packages. The browser UI has no build step.
2. **No permission flags** on the participant's CLI, and the app **never answers a CLI prompt**.
3. **Never parse terminal output to decide anything.** Decide by reading files and by running the checker directly.
4. "New chat" means a new CLI process; only one CLI process runs at a time.
5. Network use by the app is limited to consented preflight downloads (python.org, nodejs.org, the npm registry). No telemetry, no API keys, the app never calls a model.
6. The participant chooses the CLI and model. No allowlist and no CLI-specific logic, except data in `cli-recipes.json`.
7. Never suggest Copilot Chat in Teams. Northwind is a learning example and never a submission option.
8. Bundled skills stay **byte-identical** to their source files (the Part 3 skills come from the Session 3 materials); changes go in the typed line.
9. No answer key exists until predictions are locked (`key` step, `key-work` folder, sealed storage outside the project). `progress.json` never holds answer keys, fixture text or course answers.
10. **Plain language** for non-technical readers. Never mention a presenter, facilitator, room, breakout, handout, neighbor, clock, or tell people to contact someone. Use "Script track" and "promptfoo track". Part, not session, is the app's word. One exception (authorized 2026-11-15): Part 6 is a live troubleshooting meeting, so the app may say, as information only, that it happens live and that people can bring their task ideas to office hours or the AIR discussion. It is stated once, in `baseline-why` "Your own work", and nowhere else. The one other place is the Series map's Part 6 row (authorized 2026-11-15), which may say, as information only, that Part 6 is a live meeting and what it is about; it never mentions office hours, the AIR discussion, or any person, place, contact detail, link or schedule.
11. **Do not change the interface without the user's explicit authorization**: layout, styling, components, element ids, and interface copy (`web/`, `content/lesson-ui.json`, step `ui` blocks). Prefer changing content or server behavior so the existing interface shows it unchanged.
12. **Never modify the OneDrive source materials** (read-only; path is in SPEC.md).
13. Keep OS-specific code in `conpty.py` and the setup scripts.

## Working conventions

- Add or update tests in the same task as the code. Update [docs/SPEC.md](docs/SPEC.md) when behavior or an API changes, and keep the master task table in [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) in step with the phase sections.
- A task is finished only when its "Done when" check has been run and passed.
- Every word participants see lives in `content/*.json`, not in code.
- Lessons cite only bundled `kit:` files (enforced by a test). No external reading.
- The repo is not under git. Do not initialize one or commit unless the user asks.
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
- Run the two backend suites one after the other, never at the same time: the `setup.cmd` integration test fails when runs overlap.
- `test_conpty.RealConsole.test_type_line_sends_enter_separately` is timing-sensitive; rerun it once before treating a failure as real.
- Two tests are skipped by design. `test_promptfoo_real.py` skips when the spike's private Node and npm cache are absent.
- Rebuild `dist/eval-coach.pyz` after app changes that affect the shipped archive.
- On Windows use backslash paths; PowerShell does not support heredocs.

## Rules for anything that touches a real CLI

- Use the stand-in `e2e-work/harness/fake_cli.py` unless the user has approved a real-CLI run. Lesson harness stages refuse to run unless `E2E_PROFILE=standin`.
- Real approvals are single-use "Yes" only, after the full command text is verified. Never choose "switch to auto mode" or "don't ask again".
- If a command is refused, bring it to the user. Do not widen the verifier on your own judgment.
- The real-CLI test budget is 17 sessions (15 used) unless the user changes it.
- Never run a real CLI install recipe in a test. Never edit CLI settings or credentials.

## Sensitive items

- Four Phase 0 transcripts contain the account email (housekeeping item H2, waiting on the user). Do not copy or quote them, and do not delete them without the user's go-ahead.
- Never add secrets, tokens or personal data to content, tests or docs.
