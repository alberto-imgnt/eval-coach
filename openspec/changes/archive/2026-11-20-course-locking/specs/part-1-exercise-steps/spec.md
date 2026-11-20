# Spec Delta

## MODIFIED Requirements

### Requirement: Hands-on steps need setup and stay in order
Every Part 1 step SHALL be refused until setup has passed (as in `setup-access`) and SHALL open only in order. A step that order has not opened SHALL be refused with the lock message and SHALL NOT be readable as a preview (`course-locking`). Done steps SHALL stay viewable.

#### Scenario: Before setup
- **GIVEN** setup has not passed and `p1-mission` is done
- **WHEN** the participant opens the `cold` step
- **THEN** the instructions can be read, the editor, Save and Copy are disabled, no AI window starts, and there is a way to open setup

#### Scenario: Not yet open
- **GIVEN** `cold` is not done
- **WHEN** the participant, or a request, asks for the `score` step
- **THEN** it is refused with the lock message and no step text is returned

#### Scenario: Server refusal
- **GIVEN** setup has not passed
- **WHEN** a request tries to save or start in a Part 1 step
- **THEN** the server refuses it with the setup-incomplete error
