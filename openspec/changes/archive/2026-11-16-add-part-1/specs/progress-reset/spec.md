# Spec Delta

## MODIFIED Requirements

### Requirement: Reset lesson progress leaves no course files
After confirmation, no file that the app or the participant's CLI produced during the course SHALL remain in the project folder: the checker, fixtures, saved runs, saved results, the iteration log, the saved outputs of Part 1 and any other course output. The starting prompt and starting test cases, and the prompts the participant wrote in Part 1 (cold, framework, and the own-work before and after), SHALL stay in place, and every other file in the project folder SHALL be left untouched.

#### Scenario: Course outputs gone
- **GIVEN** the project folder holds a checker, fixtures, saved runs, an iteration log and Part 1 outputs
- **WHEN** the participant confirms the reset
- **THEN** none of them is in the project folder
- **AND** the starting prompt and test cases are still there, unchanged

#### Scenario: Part 1 prompts stay
- **GIVEN** the project folder holds the participant's Part 1 prompts and outputs
- **WHEN** the participant confirms the reset
- **THEN** the prompts and own-work files are still there, unchanged, and the outputs are in the backup

#### Scenario: Unknown files untouched
- **GIVEN** the project folder holds a file the app never created
- **WHEN** the participant confirms the reset
- **THEN** that file is still there, unchanged

#### Scenario: Steps start clean
- **WHEN** the participant starts the first step after the reset
- **THEN** no step check passes or fails because of a leftover from before the reset
