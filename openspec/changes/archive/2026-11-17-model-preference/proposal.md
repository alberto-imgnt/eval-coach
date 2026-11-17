# Proposal

## Why

Today the participant picks a model by hand: they open their AI window, type `/model`, choose from a list, and write the exact name into a box in every step that uses the AI (Part 1 cold and rewrite, Part 3 generate, baseline and live). The reviewers found this slow and easy to get wrong (a typo, a flagship model, a different model on the second run). It also asks a non-technical participant to read a picker they have never seen.

The series review (item 7, `docs/temp/series-review-pending-changes.md`, change 3) decided to replace this with one stored preference, a Sonnet or Haiku toggle wherever the AI is used, a launch option that starts the AI on that model, and the real model name recorded by the app instead of typed. Change 4 (`part-1-ai-flow`) needs this first: once the model is not typed, Part 1 can drop its model box.

## What Changes

- **One stored preference, default Sonnet.** Sonnet or Haiku, kept in `<home>\preflight.json`, applied the next time an AI window starts. Reset app configuration returns it to Sonnet; Reset lesson progress keeps it.
- **A Sonnet / Haiku toggle in every view that shows the AI window** (Part 1 and Part 3 steps, lesson AI activities, the setup working test page). Changing it while an AI window runs does not touch that window; the toggle says it applies the next time the AI starts.
- **The model is passed as a launch option.** `cli-recipes.json` gains per-tool `models` data (launch arguments, keyword, shipped fallback). Claude Code takes the alias (`--model sonnet` or `--model haiku`); GitHub Copilot CLI takes an exact ID (`--model=<id>`); Devin CLI takes `--model sonnet`, and for Haiku the exact ID the discovery finds. A command with no model data (the stand-in, the typed `--custom-ai` route) is started with no option and the toggle is not shown.
- **Model discovery by keyword.** For a tool that needs an exact ID, the app starts the tool once in a hidden window in its own empty folder, types `/model`, reads the list, takes the newest ID that contains "sonnet" (or "haiku"), and stops the process. If anything fails, the shipped fallback ID is used. The result is cached per tool and program version. This needs a scoped exception to AGENTS.md rule 3 (read the model list only to get a model ID, and read the text before it only to avoid typing into a prompt) and a matching note in rule 6.
- **The app records the model used.** At every AI start the app writes the model it passed (or "the AI's own default" when none) to the step record. The typed model box and the `/model` instruction go away from Part 1 and Part 3. The gates that need "a model name" now need "a recorded model". The existing "different model" nudge stays.
- **AGENTS.md** gets the rule 3 and rule 6 changes and the real-CLI budget wording is simplified (the 17-session budget is gone; every real run still needs explicit approval, single-use Yes only, no install recipes, no edits to CLI settings or credentials).

### Interface authorization (AGENTS.md rule 11)

Requested scope, **authorized by the user on 2026-11-17** (apply may touch `web/` and interface copy within this scope only):

- The Sonnet / Haiku toggle component, shown in the AI window header of every view that has one, including the wizard's AI working test page.
- Removal of the model box from the Part 1 `cold` and `rewrite` panels and the Part 3 `generate`, `baseline` and `live` panels, with the text that goes with it (`content/steps.json`, `content/part-1-steps.json`, step `ui` blocks).
- Interface copy in `content/lesson-ui.json` and `content/settings.json` for the toggle and its note.

No other layout, styling, element id or component changes.

## Capabilities

### New Capabilities
- `model-preference`: the stored Sonnet or Haiku preference, the toggle in every AI view, when it applies, what is recorded per AI start, and how reset treats it.
- `model-discovery`: how the app turns the preference into a launch option, the per-tool data, the hidden `/model` read for tools that need an exact ID, the fallback, the cache and the limits on what the app may read or type.

### Modified Capabilities
- `model-selection-guidance`: the three "type /model, choose, write the name in the box" requirements are replaced by text that says which model the app uses and why Sonnet or Haiku, and that the app records it.
- `part-1-exercise-steps`: the `cold` and `rewrite` gates need a recorded model instead of a typed one; the fairness nudge compares recorded models.

## Out of Scope

- Part 1 auto-start of the AI window, the Copy button and removing "Check my work" (change 4, `part-1-ai-flow`).
- Course locking, skipping and demo access (change 5).
- A technical or non-technical mode with different model defaults (deferred, item 0).
- More than two choices (no Opus or flagship model) and a model picker the participant can type into.
- Running any model for the participant, or listing models from the vendor's API (rules 2 and 5 stand).
- A migration of model names already typed in `progress.json`; the app is not live, and an old value stays until the next AI start overwrites it.
- Setting the model for the quiet background test of the chosen AI (it keeps its own defaults).
- Real-CLI runs during planning. Verification of the real tools is the 6 approved sessions in the series plan (per tool, one on Sonnet and one on Haiku); each needs the user's approval.

## Impact

- **Code:** `app/eval_coach/{engine,preflight,terminal,state,gates,part_steps,server}.py`; a new `app/eval_coach/models.py` for the data lookup, discovery and cache; `web/js/{app,panels,part-steps,lessons,preflight,settings}.js` and `web/styles.css` for the toggle and the removed box.
- **Content:** `content/cli-recipes.json` (per-tool `models` data), `content/steps.json`, `content/part-1-steps.json`, `content/lesson-ui.json`, `content/preflight.json`, `content/settings.json`.
- **Storage:** `<home>\preflight.json` (`model_preference`), new `<home>\model-cache.json`, new scratch folder `<home>\cli-models\`, step records in `progress.json` (`model_name` now written by the app).
- **Docs and rules:** `AGENTS.md` (rules 3 and 6, real-CLI paragraph), `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md`, `docs/temp/series-review-pending-changes.md`.
- **Tests:** unit tests for the data lookup, parse and cache; engine and HTTP tests for the preference and the recorded model; the stand-in gains `--model` handling; Playwright tests for the toggle.
