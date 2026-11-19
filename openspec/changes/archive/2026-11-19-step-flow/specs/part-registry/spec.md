# Spec Delta

## ADDED Requirements

### Requirement: A Part may register a restart plan
A Part MAY register a restart plan naming, for each of its steps, the saved record and files the step owns. Parts 1 and 2 SHALL register one; Part 3 SHALL NOT, and the app SHALL offer no restart and refuse a request for it. Every file a restart moves SHALL be on the reset inventory, and the content tests SHALL fail when a file a restart can move is on no list. Source: series review item 11; `step-restart`.

#### Scenario: Part with a plan
- **WHEN** the participant opens a finished step of Part 1 or Part 2
- **THEN** the step's state says a restart is available

#### Scenario: Part without a plan
- **WHEN** the participant opens a finished Part 3 step
- **THEN** the step's state says no restart is available and a restart request is refused

#### Scenario: Inventory coverage
- **GIVEN** a restart plan names a file that is on no reset list
- **WHEN** the tests run
- **THEN** a test fails and names the file
