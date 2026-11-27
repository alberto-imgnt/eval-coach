# Spec Delta

## ADDED Requirements

### Requirement: Part 4 opens and expands like the other Parts with content
The Part 4 row SHALL show its outcome, its state and count, an open control and an expand control, and selecting its open control SHALL open Part 4 at its current item. Its first item SHALL be `p4-mission`. Source: issue #18.

#### Scenario: Part 4 is no longer coming soon
- **WHEN** the participant looks at the row for Part 4
- **THEN** it shows a state, a count and an open control, and no "Coming soon" label

#### Scenario: Expanding Part 4
- **WHEN** the participant uses the expand control on the Part 4 row
- **THEN** its lesson names appear in course order, each with its status

#### Scenario: Opening Part 4
- **GIVEN** Part 3 is Done and the participant has not started Part 4
- **WHEN** they select the Part 4 row
- **THEN** Part 4 opens on `p4-mission`, with Part 4's own course list and header

#### Scenario: Locked until Part 3
- **GIVEN** Part 3 is not Done or Skipped
- **WHEN** the Series map is shown
- **THEN** the Part 4 row says "Not started", shows the lock icon and its text, and has no count and no action

## MODIFIED Requirements

### Requirement: Parts without content show Coming soon
A Part with no content (Part 5) SHALL show its number, name, a one-line outcome and a "Coming soon" label. Its row SHALL have no expand control, SHALL NOT be a link or button, and SHALL NOT open anything or change any state when selected.

#### Scenario: Coming-soon row
- **WHEN** the participant looks at the row for Part 5
- **THEN** it shows the Part's number, name, outcome and the label "Coming soon"
- **AND** it has no expand icon

#### Scenario: Selecting a coming-soon row
- **WHEN** the participant clicks or presses a key on a coming-soon row
- **THEN** nothing opens and the Series map stays as it was

#### Scenario: Part 1 is no longer coming soon
- **WHEN** the participant looks at the row for Part 1
- **THEN** it shows a state, a count and an open control, and no "Coming soon" label

#### Scenario: Part 2 is no longer coming soon
- **WHEN** the participant looks at the row for Part 2
- **THEN** it shows a state, a count and an open control, and no "Coming soon" label

### Requirement: A Part with content shows its progress
The row for a Part with content (Parts 1, 2, 3 and 4) SHALL show where the participant stands: locked, not started, in progress, done or skipped. For a Part that is open it SHALL show the count of lessons and steps done out of the total, the same count that Part's sidebar shows, and while the Part is not finished it SHALL name the action that selecting it takes ("Start" or "Continue"). A locked Part SHALL show its state and the lock text from `course-locking`, with no count and no action; a skipped Part SHALL show its state and no count or action.

#### Scenario: Not started
- **GIVEN** Part 1 is open and no lesson or step of it is done
- **WHEN** the Series map is shown
- **THEN** the Part 1 row says it is not started and offers "Start"

#### Scenario: In progress
- **GIVEN** some lessons and steps of Part 1 are done
- **WHEN** the Series map is shown
- **THEN** the row shows the count done out of the total and offers "Continue"

#### Scenario: Locked
- **GIVEN** Part 1 is not Done or Skipped
- **WHEN** the Series map is shown
- **THEN** the Part 2, Part 3 and Part 4 rows say "Not started", show the lock icon and its text, and have no count and no action

#### Scenario: Skipped
- **GIVEN** Part 1 is Skipped
- **WHEN** the Series map is shown
- **THEN** the Part 1 row says Skipped, with no count and no action

#### Scenario: Count matches the sidebar
- **WHEN** the participant opens Part 1 and looks at the sidebar
- **THEN** the sidebar's progress count equals the count shown on the row

#### Scenario: Each Part counts its own items
- **GIVEN** the participant has finished three items of Part 1 and none of Part 2, Part 3 or Part 4
- **WHEN** the Series map is shown
- **THEN** the Part 1 row shows 3 of 9 done, and the other rows are "Not started" with the lock icon

### Requirement: A Part row expands to its lesson names
A Part with content SHALL have an expand control (its expanded state available to screen readers) separate from the control that opens the Part. Expanding SHALL show that Part's lesson names in order, each with its status in the same words the sidebar uses (done, skipped, now or locked), as plain text that does not open the lesson. Expanding or collapsing SHALL NOT open the Part or change progress, and SHALL work on a locked Part. When the Series map is shown after a launch or reload, only the active Part SHALL be expanded: the Part in progress, otherwise the first Part that is open and not started. When every Part with content is Done or Skipped, none SHALL be expanded. Source: series review item 3.

#### Scenario: Expanding
- **WHEN** the participant uses the expand control on a Part row
- **THEN** that Part's lesson names appear in course order, each with its status
- **AND** the participant stays on the Series map

#### Scenario: Expanding Part 1
- **WHEN** the participant uses the expand control on the Part 1 row
- **THEN** its four lesson names appear in course order, each with its status

#### Scenario: Expanding Part 2
- **WHEN** the participant uses the expand control on the Part 2 row
- **THEN** its four lesson names appear in course order, each with its status

#### Scenario: Collapsing
- **GIVEN** a Part row is expanded
- **WHEN** the participant uses the expand control again
- **THEN** the lesson names are hidden

#### Scenario: Expanding a locked Part
- **GIVEN** Part 3 is locked
- **WHEN** the participant uses the expand control on the Part 3 row
- **THEN** its lesson names appear with the status "Not started", and Part 3 does not open

#### Scenario: Keyboard
- **WHEN** the participant tabs through the Series map
- **THEN** the expand control and the open control of each row with content are each reachable and each works with Enter or Space, except that the open control of a locked row opens nothing

#### Scenario: Default state
- **GIVEN** nothing is done
- **WHEN** the Series map is shown after a launch or reload
- **THEN** only the Part 1 row is expanded

#### Scenario: Default state with a Part in progress
- **GIVEN** Part 1 is Done and Part 2 is in progress
- **WHEN** the Series map is shown after a launch or reload
- **THEN** only the Part 2 row is expanded

#### Scenario: Default state when everything is finished
- **GIVEN** Parts 1, 2, 3 and 4 are each Done or Skipped
- **WHEN** the Series map is shown after a launch or reload
- **THEN** no row is expanded
