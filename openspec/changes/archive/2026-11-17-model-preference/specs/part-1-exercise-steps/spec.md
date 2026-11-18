# Spec Delta

## MODIFIED Requirements

### Requirement: The cold step's gate
The `cold` step SHALL pass when the saved prompt is non-empty, the run's output is saved and non-empty, and a model was recorded for the run. The model SHALL be recorded by the app when the AI starts (see `model-preference`), not typed. The participant SHALL be told that both runs use the model chosen with the toggle and that keeping it the same keeps the comparison fair, and the recorded model SHALL be saved for the `rewrite` step. A step that is done SHALL NOT offer a second run.

#### Scenario: Missing pieces
- **WHEN** the participant checks the step with no saved output
- **THEN** the gate fails with a plain message naming what is missing

#### Scenario: One shot
- **GIVEN** the step is done
- **WHEN** the participant opens it again
- **THEN** it shows their prompt and output and no Start control

#### Scenario: Model recorded without typing
- **GIVEN** the participant started the AI window and the run's output is saved
- **WHEN** the participant checks the step
- **THEN** the "Model name recorded" check passes and the participant typed no model name

### Requirement: The rewrite step's gate and fairness nudge
The `rewrite` step SHALL pass when a label set is chosen, the saved prompt is non-empty and differs from the cold prompt, the run's output is saved and non-empty, and a model was recorded for the run. If the recorded model differs from the cold run's, the step SHALL pass and show a plain, non-blocking note that a different model makes the comparison less fair.

#### Scenario: Unchanged prompt
- **WHEN** the saved prompt equals the cold prompt
- **THEN** the gate fails and says to change the prompt first

#### Scenario: Different model
- **WHEN** the recorded models differ because the toggle was changed between the runs
- **THEN** the gate can pass and the step shows the non-blocking note

#### Scenario: Same model by default
- **GIVEN** the toggle was not changed between the two runs
- **WHEN** the participant checks the `rewrite` step
- **THEN** the models match and no note is shown
