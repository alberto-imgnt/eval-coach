# Spec Delta

## MODIFIED Requirements

### Requirement: Part 3's gates and teaching are unchanged
Part 3 SHALL keep "Check my work", every gate item and its wording, every nudge, the answer-key deletion nudge, the predictions lock and the baseline mismatch messages. A step SHALL become done only through the same check as before. The step SHALL be judged only from files and by running the checker, never from the terminal. The model name SHALL still be recorded by the app at every start so the "Model name recorded" gate and the baseline line keep working. The `inputs` step is not an AI step: the paste flow does not apply to it, and it is finished by its own Continue. Source: AGENTS.md rules 3 and 9; series review item 10b.

#### Scenario: Check my work stays
- **WHEN** the participant opens any Part 3 step that had it
- **THEN** "Check my work" is shown and works as before

#### Scenario: Model recorded
- **WHEN** a window starts, by itself or by "Open a new AI chat"
- **THEN** the model that start used is recorded for Part 3, each model once, in the order first used

#### Scenario: Run files are still captured
- **GIVEN** the AI saves `output.txt` in the blind folder
- **WHEN** the file is complete and unchanged
- **THEN** the app saves it as the run's file and stops the window, as before

#### Scenario: A finished step closes its window
- **GIVEN** a step's AI window is still open
- **WHEN** "Check my work" passes for that step
- **THEN** that window is closed, so the next step can open its own by itself

#### Scenario: The inputs step is not an AI step
- **WHEN** the participant opens `inputs`
- **THEN** it shows no AI line, no Copy and no "Open a new AI chat"
- **AND** no AI window opens by itself
