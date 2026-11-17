---
name: openspec-lifecycle
description: Run a whole OpenSpec change from idea to archive - explore, propose, validate, review, apply, verify, sync and archive - and guide the user through each state transition without them needing to know OpenSpec. Use when the user describes a feature or fix and wants it taken end to end, says "run the full lifecycle", "take this through OpenSpec", "openspec lifecycle", "opsx lifecycle", or asks to continue or resume a change without naming a stage.
license: MIT
compatibility: Requires openspec CLI 1.x and the generated openspec-* skills in this project.
metadata:
  version: "1.0"
---

Take one change from description to archive. You are a conductor: each stage is done by the existing OpenSpec skill or CLI command named below, so their guardrails stay in force. This skill adds stage detection, a validate-and-fix loop, a verify stage, and the checkpoints with the user. Read [references/lifecycle-map.md](references/lifecycle-map.md) for the CLI cheat-sheet and the state table.

**Input**: a change description (for example "add a dark-mode toggle"), or the name of an existing change to continue. If neither is clear, ask once: "What change do you want to take through the lifecycle? Describe what to build or fix."

**Speak plainly.** The user may not know OpenSpec. At every stage change, say in one or two sentences where you are, what you just did and what happens next. Say "plan" for the proposal, specs, design and tasks, and "archive" for finishing. Never ask the user to type an OpenSpec command; run it yourself. Use the CLI's `--json` output for decisions, not text scraping.

## Checkpoints

The user is consulted at these points. No others are needed.

- **A. Plan approval** (after the plan validates, before any code is written). Always.
- **B. Pause conditions** (any stage). Stop and ask when a task is unclear, implementation exposes a design problem, work beyond the specs is needed, a verification command fails and you cannot fix it within the task's scope, a CLI state is `blocked`, or ambiguity would change scope, behavior or compatibility.
- **C. Archive confirmation.** Always.

If the user asks for fewer stops (for example "don't wait for plan approval"), checkpoint A may be skipped for that run only, and only when they say so in this conversation. B and C can never be skipped. Their request to build something is never approval of the plan.

## Step 0 - Preflight (no writes)

1. Run `openspec list --json`. If `root` is `null`, stop: tell the user this project does not use OpenSpec and ask whether to set it up (`openspec init`), use a registered store, or continue without OpenSpec. Never run `init` or create `openspec/` yourself.
2. Run `openspec context --json`; use `root.path` as the root. Read `<root>/openspec/config.yaml` (`context`, `rules`, `operations`) and any AGENTS.md at the root. These are constraints for you: obey them, never copy them into artifacts.
3. If the user names a store, pass `--store <id>` on every store-aware command for the rest of the run.

## Step 1 - Find the stage

Pick the change: use the name given, else infer from the conversation, else take the only active change, else list changes from `openspec list --json` and ask. Announce "Using change: `<name>`".

For a new description with no matching change, the stage is **Explore or Propose**. For an existing change, run `openspec status --change "<name>" --json` and `openspec list --json` and use the state table in the reference file to pick the stage. Announce it: "This change is at the **<stage>** stage."

## Step 2 - Explore (only if needed)

Skip when the request names clear behavior and scope. Otherwise follow the `openspec-explore` skill: inspect the code, ask one focused question at a time, recommend an option, write nothing. Move on when scope, out-of-scope items and any interface or compatibility constraints are agreed. Derive a kebab-case change name (for example "add dark-mode toggle" -> `add-dark-mode-toggle`); if that change already exists, ask whether to continue it or pick a new name.

## Step 3 - Propose (planning only)

Follow the `openspec-propose` skill: `openspec new change "<name>"`, then create every artifact in `applyRequires` plus everything it transitively requires, in dependency order, using `openspec instructions <artifact> --json` for template and rules. Inspect the real code before drafting, and obey the project's `rules` and `context`.

Do not edit project code in this step. Re-run `openspec status --change "<name>" --json` until every required artifact is `done` or `skipped`.

## Step 4 - Validate and fix

Run `openspec validate "<name>" --strict --json`.

- Valid: continue to Step 5.
- Issues: read each issue's path and message, fix the artifact at that path (delta format rules are in the reference file), and re-validate. Allow three fix rounds. If it still fails, show the remaining issues and ask the user how to proceed (checkpoint B).
- Never weaken a spec just to make validation pass, and never use `--no-validate`.

## Step 5 - Review and plan approval (checkpoint A)

Present, briefly:
- what the change does and what is out of scope;
- the capabilities (spec files) and their key requirements;
- the design's decisions and its **Open Questions with their assumed defaults** (ask the user to confirm or correct them);
- the task count and the verification commands the tasks use;
- anything that needs the user's explicit authorization under the project rules (for example interface changes), confirming it is recorded in the proposal.

Then ask: approve and start implementing, revise the plan, or stop here. On "revise", follow the `openspec-update-change` skill (confirm each edit, keep artifacts consistent), re-run Step 4, and present again. On "stop", end with the change location and how to resume. Do not write code until the user approves.

## Step 6 - Apply

Follow the `openspec-apply-change` skill: `openspec instructions apply --change "<name>" --json`, read every `contextFiles` entry, apply `context` and `operationGuidance` as constraints, then implement tasks one at a time and tick each `- [ ]` at its `sourcePath` and `line` only when its specified behavior is fully done and its verification command has passed. Re-run the apply instructions after each tick to confirm progress.

Stop at checkpoint B when it applies. When the plan must change, update the artifacts through `openspec-update-change` (with the user's confirmation), re-validate, then resume. Continue until `state` is `all_done`.

## Step 7 - Verify (no code writes unless a defect is found)

OpenSpec's core profile has no verify command, so do it here:

1. `openspec list --json`: the change's `completedTasks` must equal `totalTasks`.
2. `openspec validate "<name>" --strict --json`: still valid (the plan may have been edited during apply).
3. Walk the delta specs: for each `#### Scenario:` confirm the code or a test covers it. List any scenario with no coverage.
4. Check the docs the project requires to be updated with the change (for example its main spec or plan document).

The test and build suites are not run here. They run once, in the archive gate (Step 8), so they are never run twice.

If anything fails, fix it within the change's scope, or pause (checkpoint B). Report a short verification table: check, result.

## Step 8 - Verification gate, sync and archive (checkpoint C)

1. **Verification gate** (before anything is synced or moved). Build the required labels as listed under "Required checks" below, then run `python tools\verify_receipt.py check --change "<name>" --require backend --require backend-embedded [--require <label> ...]`.
   - `valid`: skip the suites and say the receipt is current.
   - Otherwise run each missing check the change needs, one at a time, through the receipt tool: `python tools\verify_receipt.py write --change "<name>" --name <label> -- <command>`. Use stand-ins, never real external tools, unless the user approved them. If a check fails, fix it within the change's scope and rerun, or pause (checkpoint B); never archive on a failure. A fix invalidates earlier receipts, so rerun every required check after the last edit.
   - Never write or edit a receipt by hand.
   - **Required checks.** Build the list from the change's `tasks.md` verification tasks and AGENTS.md, and pass every label with its own `--require`. Never skip on a receipt that holds fewer. One label per command or runtime:

     | Label | Command | Required when |
     |---|---|---|
     | `backend` | `python -m unittest discover -s tests` | always |
     | `backend-embedded` | `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests` | always (the second runtime; run after `backend`, never at the same time) |
     | `interface` | `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` | `app/eval_coach/web/` or `tests/frontend/` changed, or a task names it |
     | `build` | `python tools\build_pyz.py --smoke` | `app/` changed, or a task names it |
     | `e2e` (and `e2e-promptfoo` for `--track promptfoo`) | `node e2e-work\harness\run-all.js --fresh` (add the track option) | a task names it, or `e2e-work/harness/` or setup behavior changed |
2. Run `openspec instructions archive --change "<name>" --json` (advisory; ignore failure) and apply its `context` and `operationGuidance`.
3. Show the user: change name, tasks complete, verification result (from the receipt), delta specs and whether the main specs need syncing, and what will move to `changes/archive/`. Ask to confirm. Wait for the answer.
4. On confirmation follow the `openspec-archive-change` skill, which assesses the sync, runs `openspec-sync-specs` inline, verifies the merged main specs, and moves the change. Do not sync in the background.
5. Afterwards run `openspec validate --all --strict --json` and `openspec list --json`; the change must no longer be active and the specs must be valid.
6. Follow any archive guidance from the config (for example summarising which existing docs are superseded) in the final report.
7. **Completion hook**: ask the user whether to open the branch and pull request now. On yes, follow the `post-archive-pr` skill; its Step 3 finds the receipt valid and does not run the tests again. On no, say they can ask for it later. Never start it without the yes.

## Final report

```
## Lifecycle complete: <name>
Stages: explore (skipped|done) > propose > validate > approve > apply > verify > archive
Plan: <n> capabilities, <m> tasks, all complete
Verification: <checks and results, from the receipt>
Specs: <synced to main specs | no delta specs | skipped>
Archived to: <path>
Pull request: <opened (url) | declined | later>
Follow-ups: <anything deferred, assumed defaults the user confirmed, docs to review>
```

If the run stops early, report the stage reached, the change path, and say "ask me to continue `<name>`" to resume.

## Guardrails

- Planning artifacts only until checkpoint A is approved; never edit code in Steps 2 to 5.
- One change at a time. Never touch another change's files.
- Do not run `openspec init`, git commands, or commit, unless the user asks.
- Use the CLI for scaffolding, status, validation and archive moves; do not hand-move change folders or hand-create `openspec/` files outside a change.
- Never copy `context`, `rules` or `operationGuidance` text into artifacts or code.
- Never tick a task that is partly done or deferred; never narrow specified behavior to make it fit.
- Re-read artifacts from disk before using them; the user may have edited them.
- Trust CLI state (`status`, `list`, `instructions`) over memory of earlier output.
