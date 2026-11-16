# Spec Delta

## MODIFIED Requirements

### Requirement: Settings is reachable at any time
The participant SHALL be able to open Settings from any screen of the course, including the Series map, on first run after skipping setup and while a step or lesson is in progress. The only exception is the full-page setup wizard, which has no tools; closing it returns to where the participant was.

#### Scenario: Opening Settings before setup passes
- **GIVEN** setup has been skipped and has not passed
- **WHEN** the participant opens Settings
- **THEN** the Settings panel is shown
- **AND** course items that are locked stay locked

#### Scenario: Opening Settings from the Series map
- **GIVEN** the Series map is shown
- **WHEN** the participant opens Settings
- **THEN** the Settings panel is shown

#### Scenario: Leaving Settings
- **WHEN** the participant leaves Settings
- **THEN** the screen they were on before is shown: the Series map if that is where they opened it, otherwise the lesson or step they were on
