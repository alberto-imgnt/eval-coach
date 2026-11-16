# OpenSpec lifecycle map

## Stages and what they produce

| Stage | Delegates to | Key commands | Writes |
|---|---|---|---|
| Preflight | - | `openspec list --json`, `openspec context --json` | nothing |
| Explore | `openspec-explore` | read-only | nothing (until confirmed) |
| Propose | `openspec-propose` | `openspec new change`, `status --json`, `instructions <artifact> --json` | `openspec/changes/<name>/` |
| Validate | - | `openspec validate <name> --strict --json`, `openspec show <name>` | artifact fixes |
| Review | `openspec-update-change` | - | artifact edits the user confirms |
| Apply | `openspec-apply-change` | `openspec instructions apply --change <name> --json` | code, `tasks.md` checkboxes |
| Verify | - | `openspec list --json`, validate, project tests | nothing |
| Archive | `openspec-archive-change`, `openspec-sync-specs` | `openspec instructions archive --json`, `openspec validate --all --strict --json` | `openspec/specs/`, `changes/archive/` |

## Directory layout

```
openspec/
  config.yaml              schema, context, per-artifact rules, operations guidance
  specs/<capability>/spec.md        main specs (source of truth after archive)
  changes/<name>/
    .openspec.yaml         schema, created date, optional skip_specs / retire_capabilities
    proposal.md            why, what changes, capabilities, out of scope
    specs/<capability>/spec.md      delta specs
    design.md              how; decisions, risks, open questions
    tasks.md               checkbox list: "- [ ] 1.1 ..."
  changes/archive/YYYY-MM-DD-<name>/   finished changes
```

Artifact graph (spec-driven): proposal -> specs and design -> tasks. `applyRequires` is `["tasks"]`, so apply needs `tasks.md`, and tasks need specs and design, which need the proposal. `status` only checks that files exist; it says nothing about quality, so always validate.

## State table (pick the stage for an existing change)

Inputs: `openspec status --change <name> --json` (`artifacts[].status`, `isPlanningComplete`), `openspec list --json` (`completedTasks`, `totalTasks`), `openspec validate <name> --strict --json` (`valid`, `issues`), `openspec instructions apply --change <name> --json` (`state`).

| Observed | Stage |
|---|---|
| No change with that name | Explore or Propose |
| Any required artifact not `done` or `skipped` | Propose (continue with the next `ready` artifact) |
| All artifacts done, validation has issues | Validate and fix |
| All artifacts done and valid, `completedTasks` is 0, user has not approved in this conversation | Review (checkpoint A) |
| `0 < completedTasks < totalTasks`, or approved and starting | Apply |
| apply `state` is `blocked` | Resolve the blocker named in `missingArtifacts` or the message, then re-detect |
| `completedTasks == totalTasks` (apply `all_done`) | Verify |
| Verified, change still active | Archive (checkpoint C) |
| Change is under `changes/archive/` | Finished; nothing to do |

A change with work already ticked was approved earlier, so skip checkpoint A on resume unless the plan was edited since.

## Delta spec format (what `--strict` checks)

- Sections: `## ADDED Requirements`, `## MODIFIED Requirements`, `## REMOVED Requirements`, `## RENAMED Requirements`.
- A new capability starts with `## Purpose` (50 or more characters). Do not add Purpose to a delta for an existing capability.
- `### Requirement: <name>` followed by text using SHALL or MUST, 500 characters or fewer before the first scenario.
- Every requirement has at least one `#### Scenario: <name>` (exactly four `#`) with a WHEN or GIVEN line and a THEN line.
- MODIFIED must repeat the whole existing requirement block, header text matching exactly. Use ADDED to add new concerns.
- REMOVED needs **Reason** and **Migration**. RENAMED uses `FROM:` and `TO:`.
- Specs describe observable behavior, not class names or implementation steps.

## Reading validation output

`validate --json` returns `items[]` with `valid` and `issues[]` (`level`, `path`, `message`). Issue `path` is relative to the change's `specs/` folder (for example `greeting/spec.md`). With `--strict` a WARNING makes `valid` false and the command exit non-zero; without it the same warning still reports `valid: true`. Always use `--strict`.

## Common validation fixes

| Issue | Fix |
|---|---|
| Requirement has no scenario | Add a `#### Scenario:` with WHEN and THEN |
| Scenario flagged (strict) | Add the missing WHEN/GIVEN or THEN line |
| Description over 500 characters | Move examples to scenarios or split into several requirements |
| Purpose too brief (strict, reported on the main spec after sync) | Write 50 or more characters of purpose in the delta up front |
| MODIFIED requirement not found | Header must match the main spec's header; copy it from `openspec/specs/` |
| Zero deltas | Add a delta spec, or set `skip_specs: true` in `.openspec.yaml` for a doc-only or tooling change |

## Archive notes

- `openspec archive <name> --yes` validates, merges deltas and moves the change non-interactively. The skill path (`openspec-archive-change`) is preferred because it shows the sync summary and verifies the merge first.
- `--skip-specs` is only for changes with no spec-level behavior.
- Target folder name is `YYYY-MM-DD-<name>`; an existing target is an error, not an overwrite.
- Windows: use backslash paths in shell commands and the CLI instead of `mkdir -p` or `mv`.
