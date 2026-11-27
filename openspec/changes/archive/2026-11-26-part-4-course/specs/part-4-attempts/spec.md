# Spec Delta

## ADDED Requirements

### Requirement: Iteration 0 comes from the chosen starting point
The attempt engine SHALL read Iteration 0's prompt, test cases, checker, five answers and log from the project's own Part 3 files when the starting point is the participant's baseline, and from `part-4\practice\` when it is the Practice baseline. The chosen starting point SHALL be saved in `parts.part-4` as an id and never as text. A `progress.json` with no saved starting point SHALL mean the participant's own baseline.

#### Scenario: Own baseline
- **GIVEN** the starting point is the participant's baseline
- **WHEN** attempt 1 is created
- **THEN** its starting files are copies of the project's Part 3 files

#### Scenario: Practice baseline
- **GIVEN** the starting point is the Practice baseline
- **WHEN** attempt 1 is created
- **THEN** its starting files are copies of the files in `part-4\practice\`, and the project's own files are not read

#### Scenario: Older progress
- **GIVEN** a `progress.json` saved before this change, with attempts and no starting point
- **WHEN** it is loaded
- **THEN** it loads unchanged and the starting point is the participant's baseline

## MODIFIED Requirements

### Requirement: Each attempt is stored apart from Part 3
Each attempt `n` SHALL be stored under `part-4\attempts\<n>\` with its own prompt, test cases, checker, `runs\run-1` to `run-5`, `results.json` and `hypothesis.md`; when the Practice baseline is the starting point it SHALL be stored under `part-4\practice\attempts\<n>\` instead. Part 3's files SHALL never be edited. Source: `docs/SPEC.md` "Evidence handoff".

#### Scenario: Part 3 files untouched
- **WHEN** an attempt is created, run and scored
- **THEN** the project's `prompt-v0.md`, `test-cases.md`, `check.py`, `runs\` and `iteration-log.md` have the same bytes as before

#### Scenario: A second attempt starts from the kept version
- **GIVEN** attempt 1 is kept
- **WHEN** attempt 2 is created
- **THEN** its starting files are copies of attempt 1's, and its parent is 1

#### Scenario: A Practice attempt
- **GIVEN** the Practice baseline is the starting point
- **WHEN** attempt 1 is created and scored
- **THEN** its files are under `part-4\practice\attempts\1\` and no file under `part-4\attempts\` is created

### Requirement: The log carries a decision line and is only read
`parse_iteration_log` SHALL read a `Decision` field with the value `kept`, `undone` or `pending` and return it with the entry. The app SHALL check each Part 4 entry's decision against the manifest, each entry's counts and NOT CHECKED items against its saved results, and that its Change, Result and Reasoning are not empty. It SHALL read the log of the chosen starting point. The app SHALL never edit the log, read terminal output or call a model. Part 3's baseline gate SHALL behave as before.

#### Scenario: Decision matches
- **GIVEN** the manifest says attempt 2 is undone and its log entry says `Decision: undone`
- **WHEN** the log is checked
- **THEN** that item passes

#### Scenario: Decision differs
- **GIVEN** the manifest says kept and the log says undone
- **WHEN** the log is checked
- **THEN** the check fails and names both values

#### Scenario: Empty Reasoning
- **GIVEN** the entry's Reasoning has no text
- **WHEN** the log is checked
- **THEN** the check fails and says the Reasoning is missing, and the log is not changed

#### Scenario: Text is only checked for presence
- **GIVEN** the entry's Change, Result and Reasoning each hold any text
- **WHEN** the log is checked
- **THEN** the presence item passes whatever the text says

#### Scenario: Part 3 gate unchanged
- **GIVEN** a log with entries 0, 1 and 2
- **WHEN** the Part 3 baseline gate runs
- **THEN** it reads only Iteration 0 and gives the same result as before

### Requirement: Participant work is preserved
The app SHALL NOT overwrite or delete an existing participant file when creating or resuming an attempt, SHALL resume from `parts.part-4` when it exists, and SHALL show Part 4 on the Series map as a Part with content once its course ships.

#### Scenario: Existing attempt folder
- **GIVEN** `part-4\attempts\1\` already holds participant files
- **WHEN** the attempt is resumed
- **THEN** no file in it is overwritten

#### Scenario: Older progress
- **GIVEN** a `progress.json` saved before this change
- **WHEN** it is loaded
- **THEN** it loads unchanged and `parts.part-4` starts empty
