---
name: post-archive-pr
description: After an OpenSpec change has been applied and archived, create a branch named for the change, commit only the files that belong to it with a Conventional Commits message, push, and open a ready-for-review GitHub PR to main with delete-branch-after-merge enabled. Use only when the user asks for it, for example "open a PR for the archived change", "post-archive PR", "commit and push the change", or "ship the change".
license: MIT
compatibility: Requires git, the GitHub CLI (gh) logged in with push rights, and the openspec CLI. Windows and PowerShell commands.
metadata:
  version: "1.0"
---

Take an archived OpenSpec change from a dirty working tree to an open pull request on `main`. Run it only when the user asks. This skill never merges a PR, never force-pushes, and never edits code.

The user asking for this skill is the explicit go-ahead to branch, commit and push that AGENTS.md and `openspec/config.yaml` require ("do not commit unless the user asks"). It covers only the steps below.

**Input**: the change name, optional. If omitted, take it from the conversation or from the newest folder under `openspec/changes/archive/`. If more than one is plausible, ask which one.

Announce: "Using change: `<name>`".

## Step 1 - Preconditions (no writes)

Stop and tell the user what to fix if any of these fails.

1. **The change is archived.** Find `openspec/changes/archive/<YYYY-MM-DD>-<name>/`. If the change is still under `openspec/changes/<name>/`, stop and say: "Archive the change first (`/opsx-archive`), then ask me again." Never archive it from here.
2. `git rev-parse --is-inside-work-tree` succeeds, and `git remote get-url origin` points at GitHub.
3. `gh auth status` is logged in, and `gh repo view --json viewerPermission` shows `WRITE`, `MAINTAIN` or `ADMIN`.
4. `git branch --show-current` is `main`. If not, ask whether to branch from the current branch anyway; do not switch silently.
5. `git fetch origin main`, then `git rev-list --count HEAD..origin/main`. If main is behind, tell the user and ask whether to continue or stop so they can update first. Do not pull or rebase.
6. `git status --porcelain` shows something to commit.

## Step 2 - Pick the files that belong to the change

The working tree can hold unrelated edits. Never use `git add -A`, `git add .` or `git commit -a`.

1. Read the archived `proposal.md` (Impact section) and `tasks.md` for the paths the change touches. Read `git status --porcelain` for what actually changed.
2. Mark a changed path as **belongs** when any of these is true:
   - it is listed in the proposal's Impact section or in a task, directly or through a listed folder or glob;
   - it is the archived change folder, or the matching deletion of `openspec/changes/<name>/` when that folder was tracked;
   - it is a main spec under `openspec/specs/<capability>/` for a capability in the archived `specs/` folder;
   - it is a test for a belonging source file, or `docs/SPEC.md` when the tasks required updating it.
3. Everything else is **unrelated**. Show the user the two lists (belongs, unrelated), then ask which unrelated files, if any, to add. The default is none. Do not stage a path that is unclear without asking.
4. Never stage ignored or generated output: `docs/local/` (working papers), `dist/`, `e2e-work/` scratch (everything but `e2e-work/harness/`), `spikes/*/transcripts/`, `__pycache__/`, `node_modules/`. Never stage anything that looks like a secret, token or personal data (AGENTS.md "Sensitive items"). Warn and leave it out.

## Step 3 - Preflight tests (receipt first, then ask)

`/opsx-apply` does not run the full suites at completion. The archive gate (the lifecycle's Step 8, or the `operations.archive.guidance` in `openspec/config.yaml`) records the runs in a verification receipt (`verification.json` in the change folder, which moves to the archive with it), one check per command or runtime (`backend`, `backend-embedded`, `interface`, `build`, `e2e`). The receipt is tied to a git tree hash of the working tree (everything except `openspec/` and ignored files). Because Step 2 can leave unrelated edits unstaged, the working tree alone does not prove what a commit holds, so this step stages the approved paths first and compares the receipt with the **staged snapshot** (`--staged`). Never write or edit a receipt by hand; only `tools\verify_receipt.py` writes one.

### 3a - Stage, then check the receipt (no prompt)

Stage only the approved paths, by name (never `git add -A`), and review them:

```powershell
git add -- <path> <path> ...
git diff --cached --stat
```

If staging shows anything not approved, run `git restore --staged -- <path>` for it. Then build the required labels the way the archive gate did (the lifecycle's Step 8 "Required checks": always `backend` and `backend-embedded`, plus `interface`, `build` and `e2e` when they apply to this change) and check:

```powershell
python tools\verify_receipt.py check --change <change-name> --staged --require backend --require backend-embedded [--require <label> ...]
```

It prints JSON and exits 0 (`valid`), 1 (`stale`), 2 (`missing`) or 3 (`incomplete`).

| Status | Do this |
|---|---|
| `valid` | The staged snapshot is exactly the tree that passed. Skip the run without asking. Tell the user once: "Tests already passed on exactly the files being committed (receipt from `<finished>`); skipping." Go to Step 4. |
| `stale` | Show the `changed` list (paths where the staged snapshot differs from what was verified; a `D` path was tested but is not staged, so the commit would leave it out) and go to 3b. |
| `incomplete` | Name the missing checks and go to 3b. |
| `missing` | Go to 3b. |

Record for the PR body and final report, for `valid`: "Tests: `<command>` passed (`<n>` tests) at `<finished>`; verified by receipt against the staged snapshot (tree `<first 10 characters of recorded_tree>`)". Use the receipt's `checks` for every check it holds, not only `backend`.

### 3b - Ask whether to run (receipt not valid)

Ask the user, with the ask-user tool, whether to run the required suites before branching. Use a single yes/no choice, default yes, and say in the question that it can take a few minutes and why the receipt did not apply (for example "3 staged files differ from the last verification"). Do not decide for them and do not skip the question.

- **Yes**: run each required check through the receipt tool, one at a time, so the results are recorded. Stop on any failure:

  ```powershell
  python tools\verify_receipt.py write --change <change-name> --name backend -- python -m unittest discover -s tests
  ```

  (use the commands and labels from the lifecycle's Step 8 for the others). `write` fingerprints the working tree, so afterwards run the `--staged` check from 3a again. If it is still not `valid`, files outside the staged set (unrelated edits or untracked files) were present while the tests ran, and the commit does not hold exactly what passed. Say so, and ask whether to stage them too, to set them aside and rerun, or to continue with the tests reported as run on a different tree than the commit. Never call the committed files verified in that case.

- **No** (or the question is declined): skip the run. Record one of these for the PR body and the final report, and never claim a result you did not see:
  - stale receipt: "Tests: not run now (skipped at the user's request). Earlier round: `<checks>` passed at `<finished>`, but the files being committed differ from what was tested: `<changed list>`."
  - missing or incomplete receipt: "Tests: not run (skipped at the user's request). No valid verification receipt for these changes."

  Then continue to Step 4. As a secondary hint only, the archived `tasks.md`, the local plan (`docs/local/`, git-ignored, so it may not exist) or the conversation may mention an earlier run; cite it as "reported earlier, not machine-checked", never as verified.

When the suites run:

- Do not run it at the same time as another backend suite.
- `test_conpty.RealConsole.test_type_line_sends_enter_separately` is timing-sensitive: rerun it once before treating that single failure as real.
- If it fails, show the failing tests and stop. Do not branch, commit or push. Do not fix code from this skill; hand the failure back to the user.
- `write` refuses to record a pass if files changed while the suite ran (exit 5); rerun it.
- Running anything that edits files (formatters, builds that write outside `dist/`) after a receipt is written makes it stale; do not do that between Step 3 and the commit.

## Step 4 - Create the branch

Branch name: `<type>/<change-name>`, where `<change-name>` is the archived folder name without its date prefix, for example `feat/add-settings-section`.

Choose `<type>` from what the change does (the same type as the commit in Step 5):

| Type | Use for |
|---|---|
| `feat` | new behavior participants or the app gains |
| `fix` | a defect corrected |
| `docs` | documentation or participant content wording only |
| `refactor` | restructuring with no behavior change |
| `test` | tests only |
| `perf` | faster or lighter, same behavior |
| `build` / `ci` | packaging, build tooling, workflows |
| `chore` | upkeep that fits none of the above |

Then:

1. Check for a clash: `git branch --list <branch>` and `git ls-remote --heads origin <branch>`. If either exists, stop and ask the user for another name or whether to reuse it. Do not reuse or overwrite silently.
2. `git switch -c <branch>`. Uncommitted work carries over; nothing is lost.

## Step 5 - Commit

Staging was done in Step 3. Re-read `git status --porcelain` and `git diff --cached --stat`; if anything changed since (the user may have edited files), stage or unstage by name, and redo the Step 3a check before committing.

Write the message with the file-creation tool to `<session-folder>\files\commit-msg.txt` (never from a PowerShell here-string, never inside the repo), commit from it, then delete the file:

```powershell
git commit -F "<session-folder>\files\commit-msg.txt"
```

**Message rules** (Conventional Commits 1.0.0 plus the Git project's guidance):

- Header: `<type>(<scope>)!: <description>`. Type is from the table above. Scope is optional, one lowercase word for the area touched (for example `settings`, `engine`, `content`, `parts`). The `!` appears only for a breaking change.
- Description: imperative mood ("add", not "added"), lowercase start, no trailing period. Aim for 50 characters or fewer in the header and never more than 72. Say what the change does, not how.
- A blank line, then a body wrapped at 72 characters. Explain what changed and why, and name anything the reader needs to know that the diff does not show. Use short paragraphs or `-` bullets. Take the why from the proposal; do not paste it.
- Footers after a blank line, in this order:
  - `BREAKING CHANGE: <what breaks and what to do>` only when the change breaks compatibility (also mark the header with `!`).
  - `OpenSpec-Change: <archived-folder-name>` so the commit points at its archived plan.
  - `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` as the last line.
- One logical change per commit. If the staged set is clearly two unrelated changes, tell the user and offer to split.
- Do not use `--no-verify`, `--amend` on a pushed commit, or `--allow-empty`.

Example:

```
feat(parts): let locked lessons open as read-only previews

Locked lessons and steps were unreadable once setup had passed, so a
participant part-way through a Part could not see what came next.
Locking now governs doing and recording only; reading is always open.

- show the same text-only preview after setup as before it
- keep every write route refusing a locked item

OpenSpec-Change: 2026-11-16-read-ahead-always
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## Step 6 - Push

```powershell
git push -u origin <branch>
```

Never use `--force` or `--force-with-lease`. If the push is rejected, show the error and stop.

## Step 7 - Open the pull request

Write the PR body with the file-creation tool to `<session-folder>\files\pr-body.md`, then:

```powershell
gh pr create --base main --head <branch> --title "<commit header>" --body-file "<session-folder>\files\pr-body.md" --assignee "@me"
```

- Title: the commit header, unchanged.
- Ready for review: no `--draft`. No `--reviewer` and no `--label`.
- If a PR for this branch already exists (`gh pr list --head <branch> --state open --json url`), report its URL instead of creating another.
- Body, generated from the archived proposal, in plain language and under about 40 lines:

```markdown
## Why
<one to three sentences from the proposal's Why>

## What changes
<bullets from the proposal's What Changes, trimmed>

## Out of scope
<bullets from the proposal, or "Nothing noted.">

## Verification
- Verification, from Step 3: the receipt's passed checks with test counts and time ("verified by receipt against the staged snapshot"), or "passed (<n> tests)" from a run just made, or the skipped wording (with the changed files, or "no valid verification receipt")
<other checks the tasks ran and that passed, if known>

## OpenSpec
Archived change: `openspec/changes/archive/<archived-folder-name>/`
Main specs updated: <capability list, or "none">
```

Do not paste the whole proposal or design, or any secret or personal data. Delete both temporary files afterwards.

## Step 8 - Delete the branch after merge

GitHub has no per-PR "delete source branch" checkbox. Use the repo setting `delete_branch_on_merge`, or leave deletion to the user after merge. Do not run `gh pr merge`, including with `--auto`, from this skill: it can merge immediately even on a protected branch when the requirements are already satisfied.

In PowerShell, single-quote every `gh api` path and `--jq` expression that contains braces (`'repos/{owner}/{repo}'`), or PowerShell splits them.

1. Read the repo: `gh api 'repos/{owner}/{repo}' --jq '{del: .delete_branch_on_merge, admin: .permissions.admin}'`.
2. **Use the repo setting.** If `del` is already true, there is nothing to do. If false and `admin` is true, ask the user to confirm, then run `gh api -X PATCH 'repos/{owner}/{repo}' -F delete_branch_on_merge=true`. If the user declines or is not an admin, leave the setting unchanged.
3. **Report exactly what happened**: repo setting already on, repo setting turned on, or setting left unchanged and why. If automatic deletion is not enabled, tell the user that GitHub's "Delete branch" button on the merged PR does it.

Changing the repo setting affects every future PR in the repo. Say that when asking for confirmation.

## Final report

```
## Pull request ready: <name>
Branch: <branch> (from main)
Commit: <short sha> <header>
Files: <n> committed; <m> left out (<list or "none">)
Tests: passed via valid receipt (staged snapshot matches) | passed (run now) | not run (skipped at the user's request); <files that differ from the earlier round, or "no valid receipt">
PR: <url>
Delete branch after merge: <what happened in step 8>
```

If it stops early, report the step reached, what is already done (branch, commit, push), and what remains, so the user can resume.

## Guardrails

- Only after the change is archived, and only when the user asks.
- Stage by explicit path. Never `git add -A`, `-a`, `--force`, `--no-verify`, or `git reset --hard`.
- Never merge the PR, and never change repo settings, protection or rulesets without the user's confirmation in this conversation.
- Never write or change code, specs or docs from this skill. A failing test stops it.
- Trust a verification receipt only when `verify_receipt.py check --staged` with every required label says `valid`; never write or edit one by hand. With a valid receipt, do not ask and do not rerun. Otherwise always ask whether to run the tests (Step 3); never run them or skip them without the user's answer, and never report tests as passed when they were skipped, or call the committed files verified when the tests ran on a tree that held unstaged files. Report an earlier round as earlier, never as a result of this run.
- Do not initialize a repo, add remotes, or change git config.
- Run `git` and `gh` only against `origin` for this repo. Do not touch other repos or forks.
- Re-read `git status` from disk before each stage; the user may have edited files.
- Keep secrets, tokens, the account email and personal data out of commits, PR bodies and reports.
