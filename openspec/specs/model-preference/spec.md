# model-preference Specification

## Purpose

Lets the participant choose once whether their AI works on a Sonnet or a Haiku model, shows that choice wherever the AI window is used, and records which model each AI start used.

## Requirements

### Requirement: One stored preference, Sonnet by default
The app SHALL keep one model preference with two values, Sonnet and Haiku. A fresh setup SHALL have Sonnet. The preference SHALL be kept across restarts and SHALL NOT be a course item or progress. Source: series review item 7.

#### Scenario: Fresh setup
- **WHEN** the participant opens the app for the first time
- **THEN** the preference reads Sonnet

#### Scenario: Kept across restarts
- **GIVEN** the participant chose Haiku
- **WHEN** the app is closed and opened again
- **THEN** the preference still reads Haiku

### Requirement: A toggle in every view that shows the AI window
Every view that shows the AI window SHALL show a Sonnet / Haiku toggle, showing the current preference, with plain words saying a change applies the next time the AI starts. This covers the Part 1 and Part 3 steps, the lesson activities that use the AI, and the setup AI working test page. The toggle SHALL be reachable by keyboard and have an accessible name. Source: series review item 7; AGENTS.md rule 11 (interface authorization requested in the proposal).

#### Scenario: Toggle in a step
- **WHEN** the participant opens a step that uses the AI window
- **THEN** the toggle shows Sonnet or Haiku, whichever is stored

#### Scenario: Toggle on the setup test page
- **WHEN** the participant is on the AI working test page of the wizard
- **THEN** the same toggle is shown beside the AI window

#### Scenario: Changing while the AI runs
- **GIVEN** an AI window is running
- **WHEN** the participant changes the toggle
- **THEN** the running window is not touched or restarted
- **AND** the toggle says the change applies the next time the AI starts

#### Scenario: Same value everywhere
- **WHEN** the participant changes the toggle in one view and opens another
- **THEN** the other view shows the same value

#### Scenario: A tool with no model choice
- **GIVEN** the chosen AI command has no model data (the test-only typed route)
- **WHEN** a view shows the AI window
- **THEN** no toggle is shown and the AI starts with no model option

### Requirement: The preference is applied at the next AI start
Each time the app starts an AI window, it SHALL start the AI on the model that matches the stored preference at that moment. A change SHALL NOT affect a window that already runs, and the app SHALL NOT type a model command into a running AI. Source: AGENTS.md rules 2 and 4.

#### Scenario: Next start uses the new choice
- **GIVEN** the participant changed Sonnet to Haiku
- **WHEN** they start the AI window in any step
- **THEN** that AI starts on a Haiku model

### Requirement: Each AI start records the model it used
At every AI start the app SHALL record which model it asked for in the step's record, as a plain name. When no model option was passed, it SHALL record "the AI's own default model". The participant SHALL NOT type a model name, and no model box SHALL be shown. A step's gate that needs a model SHALL be met by the recorded model. Source: series review item 7.

#### Scenario: Recorded at start
- **WHEN** the participant starts the AI window in the Part 1 `cold` step on Sonnet
- **THEN** the step's record holds the Sonnet model the AI was started with
- **AND** the participant typed nothing

#### Scenario: No box
- **WHEN** the participant reads the Part 1 `cold` and `rewrite` steps and the Part 3 generate, baseline and live steps
- **THEN** none shows a box for a model name

#### Scenario: Several runs on different models
- **GIVEN** the participant did one of the five Part 3 runs on Sonnet and another on Haiku
- **WHEN** the step records its models
- **THEN** it holds each model used, in the order first used
- **AND** the line the app types into the log step names every model used

#### Scenario: Gate met by the record
- **GIVEN** an AI start recorded a model
- **WHEN** the participant checks the step
- **THEN** the "Model name recorded" check passes without any typed text

#### Scenario: Default model recorded
- **GIVEN** the AI command has no model data
- **WHEN** the participant starts the AI window
- **THEN** the step records "the AI's own default model" and its gate on a recorded model passes

### Requirement: Reset treats the preference as setup
Reset app configuration SHALL return the preference to Sonnet and remove the saved model results (see `model-discovery`). Reset lesson progress SHALL keep the preference. Source: `configuration-reset`, `progress-reset`.

#### Scenario: Reset configuration
- **GIVEN** the preference is Haiku
- **WHEN** the participant resets the app configuration
- **THEN** the preference reads Sonnet

#### Scenario: Reset progress
- **GIVEN** the preference is Haiku
- **WHEN** the participant resets lesson progress
- **THEN** the preference still reads Haiku

### Requirement: The words live in content
Every word of the toggle and its note SHALL come from `content/*.json`, follow `participant-vocabulary` ("your AI", "AI window", never a bare "CLI"), and not say that Sonnet or Haiku is recommended beyond that Sonnet is the default. Source: AGENTS.md rule 10.

#### Scenario: Plain words
- **WHEN** the content tests scan the toggle text
- **THEN** it contains no bare "CLI" and no presenter wording
