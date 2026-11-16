# Design

## Context

See proposal.md. This change was implemented first and recorded afterwards, so the decisions below describe what was built.

- The generate step's `instructions` are a list in `content/steps.json`; a step's text is content, not interface.
- A rule lab (`rule_lab` activity) comes from `content/lessons.json`. The public view built by `lessons.py` passes only whitelisted fields (`id`, `label`) for each rule, and the browser renders the rule only as part of each case's legend.
- `lesson-ui.json` `ui` holds the lab's interface strings. The browser reads them with `tx(ctx, key)`.

## Decisions

**D1. One longer instruction, not new instruction items.** The model advice extends the existing second instruction of the generate step. Nothing else in the step (gates, troubleshooting, `ui`) changes, so item counts and the gate stay as they were.

**D2. Generic wording.** Typing `/model` is stated as what "most CLIs" do, with a fallback of asking the CLI. No CLI is named and no code or `cli-recipes.json` entry changes (rule 6). Not verified per CLI recipe (see Open Questions).

**D3. An optional `explain` per rule rather than computed text.** The lab's rules are fixed kinds (word count, list terms, labels). Generating prose from the kind and params would hide the interpretation choices the lesson teaches. Authors write one sentence per rule in `lessons.json`; the validator requires it to be non-empty text when present, and the public view includes it only when present. Existing labs and test fixtures without it keep working.

**D4. Explanations state semantics, not answers.** They say what counts (strict "under", case, substring, exact label) and never name a sample or an expected verdict. Grading, expected verdicts and the "count only" feedback are untouched.

**D5. Smallest interface addition.** In `renderRuleLab`: one `h4` heading and one list reusing the `samples` list class, placed between the samples and the hint. In `renderRuleOwn`: one `hint` paragraph under the heading. Strings come from `lesson-ui.json` (`rule_rules_heading`, `rule_own_intro`; `rule_predict` reworded). No CSS, no ids, no label changes.

**D6. Own-text intro mentions the sample lock.** The engine refuses sample text before the exercise is passed (`sample_before_answer`). The intro says so, so the refusal is not a surprise.

## Files and storage

| Location | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/content/steps.json` | generate step, instruction 2 | content, shipped in the archive |
| `app/eval_coach/content/lessons.json` | `explain` on four rules; two lab prompts | content |
| `app/eval_coach/content/lesson-ui.json` | `rule_predict`, `rule_rules_heading`, `rule_own_intro` | content |
| `app/eval_coach/lessons.py` | validate and pass through `explain` | code |
| `app/eval_coach/web/js/lessons.js` | rules list, intro line | code |
| `docs/PHASE3.md` | one sentence on `explain` and the intro | docs |
| `dist/eval-coach.pyz` | rebuilt | generated |
| `progress.json`, settings, sealed storage | none | unchanged |

## Risks

- A rule's `explain` can drift from the real rule behavior. `tests/test_lessons.py` already checks every lab's expected verdicts against the real rules; the explanations are prose and are guarded only by review.
- The model advice can age as CLIs change their menus.

## Open Questions

1. Is `/model` the right command for every CLI in `cli-recipes.json` (Copilot CLI, Claude Code, Devin)? Assumed default: yes for most, and the "ask the CLI" fallback covers the rest. Not yet checked.
2. Should the short hint in `web/js/panels.js` ("Pick a mid-tier model, not the most powerful one offered.") be aligned with the new wording? Assumed default: no, left as is, because it is interface copy outside the authorized scope.
3. Should other rule labs added in later Parts be required to carry an `explain`? Assumed default: no, it stays optional.
