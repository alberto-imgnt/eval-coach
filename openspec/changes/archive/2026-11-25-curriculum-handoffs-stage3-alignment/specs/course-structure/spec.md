# Spec Delta

## MODIFIED Requirements

### Requirement: Lessons and steps interleave in a fixed order
The course order SHALL be: `mission`, `hook`, `several-runs`, step `inputs`, step `generate`, `rules`, step `build`, `trust`, steps `fixtures` (and `fixtures-config` on the promptfoo track), `readback`, `predict`, `key`, then `surprise`, steps `run`, `fix`, then `baseline-why` and step `baseline`. A step SHALL unlock when the previous step is done and the lesson immediately before it, if any, is done or skipped. The gates and results of the nine steps that existed before `inputs` SHALL NOT change.

#### Scenario: Step after lesson
- **GIVEN** `several-runs` is not done or skipped
- **WHEN** the participant tries to open the `inputs` step
- **THEN** it is locked and the message names that lesson

#### Scenario: Generate after inputs
- **GIVEN** `inputs` is not done
- **WHEN** the participant tries to open the `generate` step
- **THEN** it is locked with the usual lock message

#### Scenario: Steps with no lesson before them
- **GIVEN** the `run` step is done
- **WHEN** the participant opens the `fix` step
- **THEN** it unlocks without a lesson in between

#### Scenario: Existing steps unchanged
- **WHEN** the participant works through `generate` to `baseline`
- **THEN** each of those nine steps has the same gate items, nudges and results as before
