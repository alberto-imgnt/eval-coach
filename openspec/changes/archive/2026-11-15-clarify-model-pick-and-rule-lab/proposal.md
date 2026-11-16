# Proposal

## Why

Two participant-reported gaps (2026-11-15), both already fixed in the code and recorded here after the fact:

1. The "Collect your answers" step says "pick a mid-tier model, not the most powerful one offered" and "write the model name in the box", but never says how to see or change the model in the CLI, or what mid-tier means.
2. In the "From looks good to a rule" lesson, the two "Test what you know" rule labs ask the participant to predict PASS or FAIL for sample and rule pairs, but the rules were only a short name inside each case's small legend. The participant could not see what a rule really checks (strict "under", case, whole word or part of a word), so the prediction was a guess. The "Try your own text" box under the lab did not say what it is for.

## What Changes

- **Model pick (content only).** The generate step's second instruction now says how to open the CLI's model list (click the terminal, type `/model`, press Enter, choose with the arrow keys and Enter), what to do when `/model` does nothing (ask the CLI which model it uses and how to switch), what mid-tier means (the everyday model such as Sonnet, Mini or Standard, not the largest or newest flagship such as Opus), and to write the exact model name in the box.
- **Rule lab shows its rules.** Each rule in a rule lab can carry an `explain` sentence. The lab lists every rule with its explanation above the cases, so every prediction follows a stated rule. The two labs in the rules lesson get explanations for all four rules (word count under 20, both labels, none of "proud", the label "Risk:"), and both prompts tell the participant to read the rules first. The prediction hint points at the rules above.
- **"Try your own text" says what it is for.** A line under its heading says it is optional practice that is not scored, what to do (pick a rule, type or paste any text, press "Run this rule" to see the verdict and reason) and that the sample notes can be run there only after the exercise is passed.
- Docs: `docs/PHASE3.md` describes the `explain` field and the intro line.

**Interface authorization (rule 11).** On 2026-11-15 the user reported the two lesson problems above as defects in what participants see and asked for them to be fixed. Scope taken from that request: (a) two interface strings in `content/lesson-ui.json` (`rule_predict` reworded, `rule_rules_heading` and `rule_own_intro` added); (b) in `web/js/lessons.js`, one heading plus one list of the lab's rules and one hint line in the "Try your own text" block, using existing classes. Not touched: layout, styling, tokens, element ids, existing labels (`Your text`, `Rule`, `Run this rule`), the short hint in `web/js/panels.js`.

## Out of scope

- Per-CLI model instructions or any CLI-specific logic (rule 6); the text is generic and names no CLI.
- Verifying `/model` against each CLI recipe, and changing the hint in `web/js/panels.js`.
- Changing which cases a lab asks, their expected verdicts, or how the app grades them.
- Changing rule kinds, or any rule-lab behavior other than showing an optional `explain` per rule.
- Other lessons' activities and the Part 3 flow.

## Capabilities

### New Capabilities
- `model-selection-guidance`: the step that collects the five answers tells the participant how to find, choose and record a mid-tier model.
- `rule-lab-clarity`: a rule lab states each rule in plain words before asking for predictions, and its own-text box says what it is for.

### Modified Capabilities
<!-- None. No requirement in an existing OpenSpec spec changes. -->

## Impact

- Content: `app/eval_coach/content/steps.json` (generate step), `lessons.json` (the two rule labs), `lesson-ui.json` (`rule_predict`, `rule_rules_heading`, `rule_own_intro`).
- Backend: `app/eval_coach/lessons.py` (validate an optional non-empty `explain` on a rule; pass it into the public lab view).
- Interface: `app/eval_coach/web/js/lessons.js` (`renderRuleLab`, `renderRuleOwn`).
- Docs: `docs/PHASE3.md`. `docs/SPEC.md` has no wording to change (it already says the participant picks a mid-tier model in their CLI).
- Tests: a few focused cases for the new behavior (see tasks).
- Build output: `dist/eval-coach.pyz` rebuilt, not hand-edited.
- Storage: none. No progress field, no new key.
