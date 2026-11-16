# Tasks

Commands run from the repo root on Windows (see AGENTS.md "Verification commands"). This change was implemented first and recorded afterwards, so each task was checked when it landed and is re-verified in the verify stage.

## 1. Model pick guidance (content)

- [x] 1.1 In `app/eval_coach/content/steps.json`, extend the generate step's second instruction with how to open the model list (`/model`), the fallback of asking the CLI, what mid-tier means, and to write the exact model name in the box. Leave the gate, other instructions and troubleshooting unchanged. Verify: `python -m unittest discover -s tests -p "test_content*.py"`.
- [x] 1.2 Add `test_generate_step_says_how_to_pick_and_record_a_model` to `tests/test_content_and_resources.py`. Verify: `python -m unittest discover -s tests -p "test_content_and_resources.py"`.

## 2. Rule lab explains its rules

- [x] 2.1 In `app/eval_coach/lessons.py`, validate an optional non-empty `explain` on each rule and include it in the public rule-lab view only when present. Verify: `python -m unittest discover -s tests -p "test_lessons.py"`.
- [x] 2.2 In `app/eval_coach/content/lessons.json`, add an `explain` to the four rules of the two labs in the rules lesson and reword both lab prompts to point at the rules. Verify: `python -m unittest discover -s tests -p "test_lessons.py"`.
- [x] 2.3 In `app/eval_coach/content/lesson-ui.json`, reword `rule_predict` and add `rule_rules_heading` and `rule_own_intro`. In `app/eval_coach/web/js/lessons.js`, render the rule list in `renderRuleLab` and the intro line in `renderRuleOwn`, using existing classes only. Verify: the Playwright suite in 3.2.
- [x] 2.4 Add tests: bundled labs have an `explain` on every rule, the validator rejects a blank `explain`, the view carries `explain` only when present (`tests/test_lessons.py`); the mock course and the rule-lab Playwright test check the heading, an explanation and the intro line (`tests/frontend/mock_course.py`, `tests/frontend/ui.spec.js`). Verify: tasks 3.1 and 3.2.

## 3. Verify, docs and build

- [x] 3.1 Run the backend suite: `python -m unittest discover -s tests`. All pass (2 skipped by design).
- [x] 3.2 Run the interface suite: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`. All pass.
- [x] 3.3 Update `docs/PHASE3.md` (rule lab `explain` and the intro line). `docs/SPEC.md` needs no change: it already says the participant picks a mid-tier model in their CLI. Verify: read both files.
- [x] 3.4 Rebuild the archive: `python tools\build_pyz.py --smoke`. Verify: the smoke test passes and `dist\eval-coach.pyz` is newer than the content files.
