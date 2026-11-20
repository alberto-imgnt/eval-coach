# Spec Delta

## Purpose

Lets a participant skip a whole Part on purpose, after a plain warning of what they give up, so a Part they cannot or will not do does not block the Parts after it. Source: series review item 2.

## ADDED Requirements

### Requirement: The open Part offers "Skip this Part"
The Series map row of a Part SHALL offer "Skip this Part" only while that Part is open and not yet Done or Skipped. Locked, Done and Skipped Parts, and Parts that are coming soon or live, SHALL NOT offer it, and a direct request to skip them SHALL be refused with a plain message that changes nothing.

#### Scenario: The open Part
- **GIVEN** Part 1 is in progress
- **WHEN** the participant looks at the Series map
- **THEN** the Part 1 row offers "Skip this Part"

#### Scenario: A locked Part
- **GIVEN** Part 2 is locked
- **WHEN** the participant looks at its row, or a request asks to skip it
- **THEN** no skip control is shown, and the request is refused and changes nothing

#### Scenario: A finished Part
- **GIVEN** Part 1 is Done
- **WHEN** the participant looks at its row
- **THEN** there is no skip control

### Requirement: A skip needs a plain confirm that says what is given up
Selecting "Skip this Part" SHALL open a confirm that says what the Part teaches, why it matters, and that skipping means no artifact and no evaluator from it. It SHALL offer Cancel and a confirm button, be reachable by keyboard, and name no person, place or Stage 3. Cancel SHALL change nothing. The words for each Part SHALL come from the content files and follow `participant-vocabulary`.

#### Scenario: The confirm
- **WHEN** the participant selects "Skip this Part" on the Part 2 row
- **THEN** the confirm names what Part 2 teaches and why it matters, and says there will be no artifact and no evaluator from it

#### Scenario: Cancelling
- **WHEN** the participant cancels the confirm
- **THEN** the Part is not skipped and nothing is saved

### Requirement: A confirmed skip marks the Part Skipped and counts as done for the lock
Confirming SHALL mark the Part Skipped and save that. A Skipped Part SHALL count as Done for the rule that opens the next Part. The skip SHALL NOT delete, move or change any participant file or saved step or lesson record, and SHALL stop a running AI window of that Part first. It SHALL work whether or not setup has passed.

#### Scenario: Skipping Part 1
- **GIVEN** Part 1 is in progress
- **WHEN** the participant confirms the skip
- **THEN** the Part 1 row says Skipped, and the Part 2 row opens

#### Scenario: Work already saved stays
- **GIVEN** the participant had finished `cold` in Part 1
- **WHEN** they skip Part 1
- **THEN** their saved `cold` files and record are unchanged

#### Scenario: Skipping with setup skipped
- **GIVEN** setup has not passed
- **WHEN** the participant skips Part 1
- **THEN** it is saved and Part 2's mission lesson opens

#### Scenario: Remembered
- **GIVEN** a Part is skipped
- **WHEN** the app is closed and opened again
- **THEN** the Part is still Skipped

### Requirement: A skipped Part shows Skipped and opens read-only
A Skipped Part SHALL show the state word Skipped, with an icon, on its Series map row, on each of its lessons and steps in the expanded list, in the sidebar and in the course list. Its items SHALL open read-only: lesson text and a step's words are shown, nothing can be answered, started, checked, submitted or completed, no AI window starts, and no participant file is read or written. A note SHALL say the Part was skipped. There SHALL be no control in the app to undo a skip.

#### Scenario: The map
- **GIVEN** Part 1 is Skipped
- **WHEN** the Series map is shown
- **THEN** the row says Skipped in words and shows no skip control

#### Scenario: Opening a skipped lesson
- **GIVEN** Part 1 is Skipped
- **WHEN** the participant opens one of its lessons
- **THEN** the text is shown with a note that the Part was skipped, and its exercises are off

#### Scenario: A skipped step
- **WHEN** the participant opens a step of a Skipped Part
- **THEN** only the step's words are shown, with no control that starts an AI window, runs the checker or saves anything

#### Scenario: Doing is refused
- **GIVEN** a Part is Skipped
- **WHEN** a request tries to answer, start, check, submit or complete any of its items
- **THEN** it is refused with a plain message and nothing is recorded

#### Scenario: No undo
- **WHEN** the participant looks for a way to undo a skip
- **THEN** the app offers none; "Reset lesson progress" in Settings clears it with the rest of the progress

### Requirement: Skip words live in content and the Skipped state is not colour alone
Each Part's skip texts, the Skipped label, the note on a skipped item and the confirm's buttons SHALL come from the content files. The Skipped state SHALL be written in text that a screen reader reads, not shown by colour or icon alone.

#### Scenario: Words scan
- **WHEN** the content tests scan the skip texts
- **THEN** none contains a banned word, "Stage 3", office hours or a person or place
