# Spec Delta

## Purpose

Tells a participant how to see, change and record a mid-tier model in their own CLI, so the model name in the baseline log is real and the choice is not a guess.

## ADDED Requirements

### Requirement: The step says how to open the model list
The step that collects the five answers SHALL tell the participant how to open their CLI's model list from the terminal, and what to do when that does not work. The text SHALL be generic and SHALL NOT depend on which CLI the participant chose (AGENTS.md rule 6).

#### Scenario: A CLI with a model command
- **WHEN** the participant reads the step's instructions
- **THEN** they are told to click the terminal, type /model and press Enter, and to choose from the list with the arrow keys and Enter

#### Scenario: The command does nothing
- **WHEN** typing /model has no effect in the participant's CLI
- **THEN** the step tells them to ask the CLI which model it is using and how to switch to a different one, and to follow the answer

### Requirement: The step says what mid-tier means
The step SHALL say that a mid-tier model is the everyday model, such as one called Sonnet, Mini or Standard, and not the model described as the most capable, the largest or the newest flagship, with Opus as an example.

#### Scenario: Choosing from a list
- **WHEN** the participant sees several models in their CLI
- **THEN** the step has told them which kind to choose and which kind to avoid

### Requirement: The step says what to write in the box
The step SHALL tell the participant to write the exact model name shown into the model box, and that it is needed later. The step's gate on the model name is unchanged.

#### Scenario: Recording the name
- **WHEN** the participant has chosen a model
- **THEN** the step tells them to write the exact name shown into the box
- **AND** the "Model name recorded" check still fails while the box is empty
