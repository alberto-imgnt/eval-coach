# Spec Delta

## MODIFIED Requirements

### Requirement: Parts without content show Coming soon
A Part with no content (Parts 2, 4 and 5) SHALL show its number, name, a one-line outcome and a "Coming soon" label. Its row SHALL have no expand control, SHALL NOT be a link or button, and SHALL NOT open anything or change any state when selected.

#### Scenario: Coming-soon row
- **WHEN** the participant looks at the row for Part 4
- **THEN** it shows the Part's number, name, outcome and the label "Coming soon"
- **AND** it has no expand icon

#### Scenario: Selecting a coming-soon row
- **WHEN** the participant clicks or presses a key on a coming-soon row
- **THEN** nothing opens and the Series map stays as it was

#### Scenario: Part 1 is no longer coming soon
- **WHEN** the participant looks at the row for Part 1
- **THEN** it shows a state, a count and an open control, and no "Coming soon" label

### Requirement: A Part with content shows its progress
The row for a Part with content (Parts 1 and 3) SHALL show where the participant stands: not started, in progress or done, with the count of lessons and steps done out of the total, the same count that Part's sidebar shows. While the Part is not finished, the row SHALL name the action that selecting it takes ("Start" or "Continue").

#### Scenario: Not started
- **GIVEN** no lesson or step of Part 3 is done
- **WHEN** the Series map is shown
- **THEN** the Part 3 row says it is not started and offers "Start"

#### Scenario: In progress
- **GIVEN** some lessons and steps of Part 3 are done
- **WHEN** the Series map is shown
- **THEN** the row shows the count done out of the total and offers "Continue"

#### Scenario: Count matches the sidebar
- **WHEN** the participant opens Part 3
- **THEN** the sidebar's progress count equals the count shown on the row

#### Scenario: Each Part counts its own items
- **GIVEN** the participant has finished three items of Part 1 and none of Part 3
- **WHEN** the Series map is shown
- **THEN** the Part 1 row shows 3 of 9 done and the Part 3 row shows 0 of 16

### Requirement: A Part row expands to its lesson names
A Part with content SHALL have an expand control (its expanded state available to screen readers) separate from the control that opens the Part. Expanding SHALL show that Part's lesson names in order, each with its status in the same words the sidebar uses (done, skipped, now or locked), as plain text that does not open the lesson. Expanding or collapsing SHALL NOT open the Part or change progress.

#### Scenario: Expanding
- **WHEN** the participant uses the expand control on the Part 3 row
- **THEN** the seven lesson names appear in course order, each with its status
- **AND** the participant stays on the Series map

#### Scenario: Expanding Part 1
- **WHEN** the participant uses the expand control on the Part 1 row
- **THEN** its four lesson names appear in course order, each with its status

#### Scenario: Collapsing
- **GIVEN** the Part 3 row is expanded
- **WHEN** the participant uses the expand control again
- **THEN** the lesson names are hidden

#### Scenario: Keyboard
- **WHEN** the participant tabs through the Series map
- **THEN** the expand control and the open control of each row with content are each reachable and each works with Enter or Space

#### Scenario: Default state
- **WHEN** the Series map is shown after a launch or reload
- **THEN** the rows of Part 1 and Part 3 are expanded

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
- **THEN** Part 3 opens with locked items still locked, as before

### Requirement: Series map words live in content
All text on the Series map, including Part names, outcomes, labels and the Back control, SHALL come from the content files and follow the app's plain-language rules (the word "Part", no presenter or classroom words). Each Part's name SHALL match its name in the mission lesson's map of the Parts in every mission lesson that has one, and the outcome lines of Parts 1 to 5 SHALL match too. The mission maps themselves are not changed by this capability.

#### Scenario: Banned words
- **WHEN** the content tests run
- **THEN** no Series map text contains a banned word

#### Scenario: Names agree with the mission map
- **WHEN** the content tests run
- **THEN** each Part's name in the Series map matches its name in the mission map of Part 3 and in the mission map of Part 1
- **AND** the outcome of each of Parts 1 to 5 matches its line in both
