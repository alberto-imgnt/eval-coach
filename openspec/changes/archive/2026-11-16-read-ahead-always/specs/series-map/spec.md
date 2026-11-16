## MODIFIED Requirements

### Requirement: Selecting a Part opens its content
Selecting the open control of a Part with content SHALL open that Part at its current item: the active lesson or step, or its closing screen when everything is finished.

#### Scenario: Continue
- **GIVEN** the participant stopped on the third lesson of Part 3 and returned to the Series map
- **WHEN** they select the Part 3 row
- **THEN** Part 3 opens on that lesson

#### Scenario: Opening Part 1
- **GIVEN** the participant has not started Part 1
- **WHEN** they select the Part 1 row
- **THEN** Part 1 opens on `p1-mission`, with Part 1's own course list and header

#### Scenario: Before setup has passed
- **GIVEN** setup was skipped and has not passed
- **WHEN** the participant selects Part 3
- **THEN** Part 3 opens with locked items still unavailable for work, and open as read-only previews for reading
