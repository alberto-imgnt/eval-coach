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
3. Run the project's test and build commands named in the tasks and in AGENTS.md or the config guidance. Run them one at a time when the project says not to overlap them. Use stand-ins, never real external tools, unless the user approved them.
4. Walk the delta specs: for each `#### Scenario:` confirm the code or a test covers it. List any scenario with no coverage.
5. Check the docs the project requires to be updated with the change (for example its main spec or plan document).

If anything fails, fix it within the change's scope and re-verify, or pause (checkpoint B). Report a short verification table: check, result.

## Step 8 - Sync and archive (checkpoint C)

1. Run `openspec instructions archive --change "<name>" --json` (advisory; ignore failure) and apply its `context` and `operationGuidance`.
2. Show the user: change name, tasks complete, verification result, delta specs and whether the main specs need syncing, and what will move to `changes/archive/`. Ask to confirm. Wait for the answer.
3. On confirmation follow the `openspec-archive-change` skill, which assesses the sync, runs `openspec-sync-specs` inline, verifies the merged main specs, and moves the change. Do not sync in the background.
4. Afterwards run `openspec validate --all --strict --json` and `openspec list --json`; the change must no longer be active and the specs must be valid.
5. Follow any archive guidance from the config (for example summarising which existing docs are superseded) in the final report.

## Final report

```
## Lifecycle complete: <name>
Stages: explore (skipped|done) > propose > validate > approve > apply > verify > archive
Plan: <n> capabilities, <m> tasks, all complete
Verification: <checks and results>
Specs: <synced to main specs | no delta specs | skipped>
Archived to: <path>
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
