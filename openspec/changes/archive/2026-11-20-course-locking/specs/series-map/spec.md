# Spec Delta

## MODIFIED Requirements

### Requirement: One row per Part, in series order
The Series map SHALL list all six Parts in series order, each with its number and name: 1 Structured prompting, 2 Defining evaluation criteria, 3 Running evals and baseline, 4 Iterating with evaluation-driven development, 5 Load-bearing audit and packaging, 6 Your own task. Each row SHALL give its state in words as well as by color or icon.

#### Scenario: All six Parts are listed
- **WHEN** the Series map is shown
- **THEN** six rows appear in the order 1 to 6, each with its number and name

#### Scenario: State is not color alone
- **WHEN** a row shows a state (not started, in progress, done, skipped, locked, coming soon or live meeting)
- **THEN** the state is written in text that a screen reader reads

### Requirement: A Part with content shows its progress
The row for a Part with content (Parts 1, 2 and 3) SHALL show where the participant stands: locked, not started, in progress, done or skipped. For a Part that is open it SHALL show the count of lessons and steps done out of the total, the same count that Part's sidebar shows, and while the Part is not finished it SHALL name the action that selecting it takes ("Start" or "Continue"). A locked Part SHALL show its state and the lock text from `course-locking`, with no count and no action; a skipped Part SHALL show its state and no count or action.

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
- **THEN** the Part 2 and Part 3 rows say "Not started", show the lock icon and its text, and have no count and no action

#### Scenario: Skipped
- **GIVEN** Part 1 is Skipped
- **WHEN** the Series map is shown
- **THEN** the Part 1 row says Skipped, with no count and no action

#### Scenario: Count matches the sidebar
- **WHEN** the participant opens Part 1 and looks at the sidebar
- **THEN** the sidebar's progress count equals the count shown on the row

#### Scenario: Each Part counts its own items
- **GIVEN** the participant has finished three items of Part 1 and none of Part 2 or Part 3
- **WHEN** the Series map is shown
- **THEN** the Part 1 row shows 3 of 9 done, and the Part 2 and Part 3 rows are "Not started" with the lock icon

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
- **GIVEN** Parts 1, 2 and 3 are each Done or Skipped
- **WHEN** the Series map is shown after a launch or reload
- **THEN** no row is expanded

### Requirement: Selecting a Part opens its content
Selecting the open control of a Part that is open SHALL open that Part at its current item: the active lesson or step, or its closing screen when everything is finished. Selecting the open control of a locked Part SHALL open nothing and change nothing. Selecting a Skipped Part SHALL open it at its first lesson, read-only, as `part-skip` sets out.

#### Scenario: Continue
- **GIVEN** the participant stopped on the third lesson of Part 3 and returned to the Series map
- **WHEN** they select the Part 3 row
- **THEN** Part 3 opens on that lesson

#### Scenario: Opening Part 1
- **GIVEN** the participant has not started Part 1
- **WHEN** they select the Part 1 row
- **THEN** Part 1 opens on `p1-mission`, with Part 1's own course list and header

#### Scenario: Opening Part 2
- **GIVEN** Part 1 is Done and the participant has not started Part 2
- **WHEN** they select the Part 2 row
- **THEN** Part 2 opens on `p2-mission`, with Part 2's own course list and header

#### Scenario: Selecting a locked Part
- **GIVEN** Part 3 is locked
- **WHEN** the participant clicks or presses a key on its open control
- **THEN** nothing opens and the Series map stays as it was

#### Scenario: Before setup has passed
- **GIVEN** setup was skipped and has not passed
- **WHEN** the participant selects Part 1
- **THEN** Part 1 opens with only its current item available, and hands-on work is refused
