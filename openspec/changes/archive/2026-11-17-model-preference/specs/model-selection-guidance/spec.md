# Spec Delta

## MODIFIED Requirements

### Requirement: The step says what mid-tier means
The step SHALL say that the two models the app offers are everyday models, Sonnet (the default) and Haiku (the lighter and faster one), and that the most capable or newest flagship model, with Opus as an example, is not offered because the course compares prompts, not models. The step SHALL NOT recommend one over the other beyond saying which is the default.

#### Scenario: Choosing from a list
- **WHEN** the participant reads the step that first uses the AI
- **THEN** it says what Sonnet and Haiku are and that a flagship model is not part of the choice

## REMOVED Requirements

### Requirement: The step says how to open the model list
**Reason**: The participant no longer opens a model list or types `/model`; the app starts the AI on the model chosen with the toggle (see `model-preference`).
**Migration**: The step text points to the Sonnet / Haiku toggle instead. The fallback text for a CLI where `/model` does nothing is no longer needed.

### Requirement: The step says what to write in the box
**Reason**: The participant no longer types a model name; the app records the model it started the AI on (see `model-preference`).
**Migration**: The "Model name recorded" check stays and is met by the recorded model.

## ADDED Requirements

### Requirement: The step says which model the app uses and records it
The step that first uses the AI SHALL tell the participant that the app starts their AI on the model chosen with the toggle (Sonnet unless changed), that the app records that model for them, that a change applies the next time the AI starts, and that using the same model for both Part 1 runs keeps the comparison fair. It SHALL NOT tell them to type `/model` or to write a model name.

#### Scenario: Step text
- **WHEN** the participant reads the step
- **THEN** it names the toggle, says the app records the model and says a change applies at the next start
- **AND** it does not mention typing `/model` or a model box

#### Scenario: Content test
- **WHEN** the content tests scan the step texts of Parts 1 and 3
- **THEN** none contains "/model" or asks for a model name to be written
