# Spec Delta

## MODIFIED Requirements

### Requirement: Hands-on steps need setup and stay in order
Every Part 2 step SHALL be refused until setup has passed (as in `setup-access`) and SHALL open only in order. A step that order has not opened SHALL be refused with the lock message and SHALL NOT be readable as a preview (`course-locking`). Done steps SHALL stay viewable.

#### Scenario: Before setup
- **GIVEN** setup has not passed, Part 2 is open and the lesson before `draft` is done
- **WHEN** the participant opens the `draft` step
- **THEN** the instructions can be read, and the worksheet, Save and Check are disabled with a way to open setup

#### Scenario: Server refusal
- **GIVEN** setup has not passed
- **WHEN** a request tries to save the worksheet
- **THEN** the server refuses it with the setup-incomplete error

#### Scenario: Preview writes nothing
- **WHEN** a request asks for a locked step, or the participant opens a step of a Skipped Part read-only
- **THEN** no file or saved progress changes
