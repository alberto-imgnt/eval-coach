# eval-coach

eval-coach is a self-guided learning app for the **Evaluated Systems (Stage 3)** series. It helps anyone, technical or not, learn to submit a Stage 3-ready task with documented, runnable test cases.

Everything a participant needs is inside the app: lessons, activities, step-by-step guidance, checks and a reference card. The app runs on the participant's own computer and wraps **their own AI tool** in an embedded terminal (the "AI window"). The shared worked example across the series is the Northwind weekly update.

## What it teaches

The series has six parts:

1. Structured prompting
2. Defining evaluation criteria
3. Running evals and a baseline
4. Iterating with evaluation-driven development
5. Load-bearing audit and packaging
6. The participant's own task

The app opens on a Series map of all six Parts. Parts 1, 2 and 3 are built; Parts 4 and 5 show "Coming soon" and Part 6 is a live meeting.

- **Part 1:** the participant writes a prompt in their own words, scores the answer, learns what prompts usually leave out, rewrites the prompt with a framework (RTCC or RISE) and rewrites one real prompt of their own.
- **Part 2:** the participant turns requirements into criteria with pass/fail thresholds and builds a markdown test case file. Nothing is run.
- **Part 3:** the participant has an agent build a checker, confirms the checker can be trusted, runs it on five outputs and records a baseline.

Part 3 offers two tracks:

- **Script track** (default): markdown test cases and a Python `check.py`.
- **promptfoo track**: promptfoo 0.125.1 running on a private copy of Node.js.

## How it works

- A small local web server starts on the participant's machine and opens the app in the browser.
- The participant picks one of three supported AI tools (GitHub Copilot CLI, Claude Code, Devin CLI) and a Sonnet or Haiku model preference. The launch options for each tool are data in `cli-recipes.json`; the app has no tool-specific logic.
- The app never answers a CLI prompt, sets no permission flags, holds no API keys and never calls a model.
- Progress is decided by reading files and running the checker directly, never by reading terminal output.
- Nothing is sent anywhere by the app. Its only network use is consented setup downloads from python.org, nodejs.org and the npm registry.
- Progress and answers are saved locally, and the answer key stays sealed until the participant locks their predictions.

## Tech stack

| Area | Technology |
|---|---|
| Language | Python 3.9+ syntax, **standard library only** at runtime (no pip packages) |
| Web server | `http.server`-based local HTTP server with Server-Sent Events (SSE) for live terminal output |
| Terminal | Windows ConPTY pseudo console (`conpty.py`) shown in the browser with [xterm.js](https://xtermjs.org/) and its fit addon |
| Frontend | Plain HTML, CSS and JavaScript modules. No framework and no build step |
| Design | "Graphite and Lime" design system with light and dark themes |
| Content | JSON files under `app/eval_coach/content/` hold every word participants see |
| Storage | Local JSON files written atomically (`%USERPROFILE%\.eval-coach` and the participant's project folder) |
| Packaging | A single `eval-coach.pyz` built with `zipapp`, started by `packaging\setup.cmd` |
| Setup runtime | Private Python 3.13 (embedded) installed after consent when no suitable Python is found |
| promptfoo track | promptfoo 0.125.1 on a private Node.js, installed after consent |
| Spec-driven changes | [OpenSpec](openspec/) |

## Testing

| Layer | Technology |
|---|---|
| Backend | `unittest` |
| Interface | Playwright |
| End-to-end | A stand-in CLI harness (`e2e-work/harness/`) driven by Node.js |

## Repository layout

```
app/eval_coach/    the app (modules, content/*.json, kit/ bundled files, web/ static UI)
tests/             unittest suite; tests/frontend holds the Playwright tests
tools/build_pyz.py builds dist/eval-coach.pyz
packaging/         setup.cmd, the participant entry point
docs/              spec, plan, design and course context
openspec/          specs and in-flight changes
e2e-work/harness/  stand-in end-to-end harness
spikes/            early experiments and the private runtimes used by tests
```

## Run, build and test

Run from the repo root on Windows.

```powershell
# Start the app from source
$env:PYTHONPATH = "app"; python -m eval_coach --no-browser    # options: --port, --home

# Build dist\eval-coach.pyz and smoke test it
python tools\build_pyz.py --smoke

# Backend tests
python -m unittest discover -s tests

# Interface tests
node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js

# Stand-in end-to-end run
node e2e-work\harness\run-all.js --fresh
```

Participants start the app by running `setup.cmd` next to `eval-coach.pyz`.

## Documentation

| Need | File |
|---|---|
| Build spec, layout, storage, HTTP contract | [docs/SPEC.md](docs/SPEC.md) |
| Setup checks and installs | [docs/SETUP.md](docs/SETUP.md) |
| Teaching, activity and wording rules for every Part | [docs/CONTENT-RULES.md](docs/CONTENT-RULES.md) |
| Part 3 course (lesson list, AI-window activities) | [docs/RUNNING-EVALS-COURSE.md](docs/RUNNING-EVALS-COURSE.md) |
| Interface design system | [docs/DESIGN.md](docs/DESIGN.md) |
| Current behavior, per area | [openspec/specs/](openspec/specs/) |
| What shipped and why (proposal, design, tasks and verification per change) | [openspec/changes/archive/](openspec/changes/archive/) |
| Contributor and agent rules | [AGENTS.md](AGENTS.md) |

The implementation plan and other working papers are kept locally and are not part of the repository.
