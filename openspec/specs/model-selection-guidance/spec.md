# model-selection-guidance Specification

## Purpose
Tells a participant which model the app starts their AI on (Sonnet by default, or Haiku), why no flagship model is offered, and that the app records the model, so the model name in the baseline log is real and the choice is not a guess.

## Requirements

### Requirement: The step says what mid-tier means
The step SHALL say that the two models the app offers are everyday models, Sonnet (the default) and Haiku (the lighter and faster one), and that the most capable or newest flagship model, with Opus as an example, is not offered because the course compares prompts, not models. The step SHALL NOT recommend one over the other beyond saying which is the default.

#### Scenario: Choosing from a list
- **WHEN** the participant reads the step that first uses the AI
- **THEN** it says what Sonnet and Haiku are and that a flagship model is not part of the choice

### Requirement: The step says which model the app uses and records it
The step that first uses the AI SHALL tell the participant that the app starts their AI on the model chosen with the toggle (Sonnet unless changed), that the app records that model for them, that a change applies the next time the AI starts, and that using the same model for both Part 1 runs keeps the comparison fair. It SHALL NOT tell them to type `/model` or to write a model name.

#### Scenario: Step text
- **WHEN** the participant reads the step
- **THEN** it names the toggle, says the app records the model and says a change applies at the next start
- **AND** it does not mention typing `/model` or a model box

#### Scenario: Content test
- **WHEN** the content tests scan the step texts of Parts 1 and 3
- **THEN** none contains "/model" or asks for a model name to be written
