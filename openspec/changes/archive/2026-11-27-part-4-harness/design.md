# Design

## Context

See proposal.md for the motivation. What exists today:

- Slices A and B give Part 4 an attempt engine (`attempts.py`), step kinds (`attempt_steps.py`), content (`part-4-lessons.json`, `part-4-steps.json`), a Practice baseline under `kit/part4/practice/` and an interface panel set. Unit tests (`test_part_4_*.py`, 2189 backend tests in the last receipt) and `tests/frontend/part4.spec.js` cover them, but the unit tests drive the engine with a fake terminal.
- The stand-in harness runs one stage per process (`run.js <stage>`), sequenced by `run-all.js`, against a private archive (`build-private-pyz.py`) and the stand-in AI `fake_cli.py`. State and assertions persist in `e2e-work/harness-state-standin*.json`. `lesson-stages.js` holds the Part 1 and Part 2 stages and the second-app pattern (`spawnApp`, used by `migrate` and `model`). Stages refuse to run unless `E2E_PROFILE=standin`.
- Part 4 course order: `p4-mission`, `starting-point`, `p4-checker-first`, `known-good`, `p4-one-change`, `p4-worked-example`, then rounds 1 and 2 (`hypothesis-n`, `edit-n`, `measure-n`, `decide-n`) and the lessons around them. Round 3 is an optional step list after the course.
- The measure step opens one AI window per run in `<home>\part4\blind\` and shows the paste line `Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.`; the output watcher saves `output.txt` as the attempt's next run. The decide step shows a `run + log mode` line after the decision. Today `fake_cli.py` would answer the measure line with a random Northwind sample (the generic `output.txt` branch) and would not answer the decide line at all.
- Rule 3 (never parse terminal output to decide anything) and rule 2 (the app never answers a CLI prompt) apply to the harness too: the harness may type the participant's paste, and it never reads the screen to decide a result.

## Goals / Non-Goals

**Goals:**
- Run Part 4 end to end on the stand-in on the Script and promptfoo tracks, through the same HTTP routes the interface uses, and cover every case in #19.
- Make the stand-in's answers deterministic and tied to the round's prompt, so a test can produce a gain, a flat result, a worse result and a lost-coverage result on purpose.
- Keep the harness independent of the app: it reads files and API responses, and never imports app code to compute an expected result (`pf-independent-check.py` is the precedent).

**Non-Goals:**
- Real-tool confirmation (separate approval).
- Re-testing engine rules already pinned by unit tests. A stage checks each case once, end to end, and does not copy the unit assertions.
- Any change to the app, content or interface.

## Decisions

**1. Two stages, not one.** `part4` continues the main home after `part2` and uses the Part 3 baseline the harness already built (own baseline path). `part4-practice` runs on a second app with a temporary home where Part 3 is untouched (catch-up path). Why: the Practice path must start with Part 3 unfinished, which the main home can no longer be after `baseline`; the second-app pattern already exists. Alternative: one stage that resets state midway (rejected: it fights the stage-per-process model and risks hiding order bugs).

**2. The stand-in picks answers from the round's prompt, not from a mode file alone.** In the Part 4 blind folder (`part4` in the path, no `part1`), `fake_cli.py` reads `prompt.md` and writes one of five fixed answer sets chosen by a marker the harness puts in its own edits (for example a tone sentence for the gain, none for flat, a sentence that drops a keyword for lost coverage). Answer texts come from `tests/golden/part4-worked/` (the authored worked answers) and the Northwind samples, which are read-only fixtures. Why: this matches how the Part 1 branch decides, keeps the five answers per round unique and repeatable, and needs no extra per-run signalling. Alternative: a mode file per run (rejected: five modes per round, easy to desynchronize). The existing `fake-cli-mode.txt` is reused only for the decide branch's wrong-entry mode (`wrong-count`-style), the way `baseline_log` does.

**3. The decide line is answered by writing the log entry the way the real skill would, from files.** The branch matches `run + log mode` with a `/attempts/<n>/` path, runs the project's (or Practice) checker on the attempt's runs through the existing `parse_checker` helper, and appends an `Iteration n` entry with the saved Hypothesis copied word for word and Change, Result and Reasoning left empty; the stage then has the harness write the participant's three fields into the log file (the participant's work, not the app's). The app never edits the log. Why: the existing `baseline_log` already does this for Iteration 0. Alternative: the harness writes the whole entry (rejected: it would not exercise the line the app shows).

**4. Both tracks share one stage body.** The stage uses `L.TRACK` to pick the score route, the Part 4 config path and the line template. The promptfoo pass uses the real pinned promptfoo against each attempt's copy, so a stage's wall time is dominated by scoring runs; the stages score only where a case needs a score, and the five runs are saved through the same watcher path as everywhere else.

**5. What each stage asserts** (each case once, end to end):
- `part4`: the lock message before the Part 3 baseline is done; the starting-point choice with nothing preselected; own baseline chosen; Part 3's files byte-identical before and after (hash compare, including the original promptfoo config); the known-good answer chosen and saved before any score is shown, an under-95% answer blocked with a next step and no way to loosen a rule, then a passing one; round 1 gain kept (measured gain wording, per-rule before and after, `NOT CHECKED` visible); round 2 flat or worse and undone (no gain wording, kept version stays round 1, round 3 starts from round 1: the undone-second-edit case); a stale result after a run file is edited (decide refused until scored again); a checker or config edit flagged as a coverage change and never counted as a gain; the log gate failing with the wrong-entry mode and passing when the entry matches; `progress.json` holding hashes, counts and decisions only, with no prompt, answer or log text; Part 4 done after two decided rounds even when the overall score is below 95%, with a suggested next step and the known-good result reported separately.
- `part4-practice`: own baseline refused with a reason when Part 3 is skipped; Practice chosen; the files copied under `part-4\practice\` with an existing Practice file never overwritten; the participant's project files and log never read or changed; the choice fixed once round 1 exists; a Practice round documented in the Practice log only.
- Both: the early reveal. Over `/api/lesson` the worked edits and results are absent from every response until the prediction passes, then returned (no key or reveal text in `progress.json`; rule 9).

**6. Session budget.** `MAX_SESSIONS` is a harness guard, not an app rule. Each measure run is one AI process, so two rounds add 12 (10 runs plus 2 decide windows) and round 3 adds 6 more, per track. Replace the stand-in constant with the measured total after the stages run, and record the new count in the README.

**7. Playwright.** Slice B's `part4.spec.js` already covers 13 cases. Compare it with the #19 list; add a case only where one is missing (candidates: a flat attempt shown without gain wording, completion below the target). Do not add interface panels.

## File locations and storage keys

| Location | Touched by | Kept or cleared |
|---|---|---|
| `e2e-work/harness/fake_cli.py` | new Part 4 measure and decide branches, wrong-entry mode | source, kept |
| `e2e-work/harness/lesson-stages.js`, `run.js` | the two stages and their registration; a `P4_CONTENT` load | source, kept |
| `e2e-work/harness/lib.js` | `MAX_SESSIONS` | source, kept |
| `e2e-work/harness/run-all.js` | `SCRIPT_SEQUENCE`, `PF_SEQUENCE`; `--fresh` also removes the new temp homes | source, kept |
| `e2e-work/harness/README.md`, `docs/SPEC.md` | stage table, session notes, "Not built here" line | docs, kept |
| `e2e-work/standin-home*`, `standin-project*`, `part4-tmp`, `logs-standin*`, `harness-state-standin*.json` | stage output (generated, git-ignored) | cleared by `--fresh` |
| `<home>\part4\blind\`, `<project>\part-4\attempts\<n>\`, `<project>\part-4\practice\` | written by the app during the stages | kept for assertions; cleared with the stand-in home |
| `progress.json` `parts.part-4` | read by the stages (`start`, manifest, decisions, hashes) | read only; the harness never edits it |
| Participant's real home and files | never touched | n/a |

No `app/`, `web/`, `content/*.json` or `lesson-ui.json` file changes. Participant-facing wording is unchanged.

## Risks / Trade-offs

- [The stage exposes an app defect] -> Fix it as a tightly coupled bug with a unit test in the same change; if it is a design question, stop and bring it to the user.
- [Promptfoo scoring makes the promptfoo pass slow] -> Score only where a case needs it; run the pass with output to a file as the README requires; allow a long timeout.
- [Stand-in answers drift from the real checker's idea of a gain] -> Answers come from the authored worked answers that `test_part_4_worked.py` already scores, and the stage computes expected counts from the harness's own independent checker, never from app code.
- [Stage order depends on the Part 3 baseline state] -> `part4` runs only after `baseline`, `part1` and `part2`, and `--only part4` on a fresh home fails fast with a message naming the missing stages.
- [Slice B is not yet committed] -> The stages need its working-tree files; the branch and pull request wait for the user's go-ahead.
- [Timing-sensitive terminal tests] -> The known flaky `RealConsole` test is unrelated; rerun once before treating a failure as real.

## Migration Plan

Add the stages and fake-CLI branches, run `node e2e-work\harness\run-all.js --fresh` for the Script pass and again with `--track promptfoo`, writing output to a file. No data migration and nothing to roll back: removing the stages leaves the app unchanged.

## Open Questions

1. Where does `part4` sit in the sequence? Assumed: after `part2` and before `migrate`, so `migrate` and `model` still run on a home that has been through every Part. Confirm.
2. Should the optional round 3 be in the end-to-end run? Assumed: yes, once, on the Script track only, to show it starts from the kept version and never counts toward Done; the promptfoo pass skips it to save six real-promptfoo runs. Confirm.
3. Should `fake_cli.py` read the worked answers from `tests/golden/part4-worked/` (a test folder) or from a copy under `e2e-work/harness/`? Assumed: read the existing folder, as it already reads `tests/golden/reference-check.py`, to avoid a second copy of the answers. Confirm.
4. The new session total is unknown until the stages run. Assumed: the constant is set to the measured total plus no extra headroom, and the README records the breakdown. Confirm.
