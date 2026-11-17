# series-map Specification

## Purpose

Gives the participant a home screen that shows every Part of the six-Part series, where they stand in the available Part, and which Parts are still coming, and a way to move between that screen and a Part's content.

## Requirements

### Requirement: The Series map is the home screen
The app SHALL open on the Series map whenever setup is not being shown: on every fresh launch and every page reload, after setup is completed or skipped. The app SHALL NOT remember which screen was open before.

#### Scenario: Launch after setup
- **GIVEN** setup has passed
- **WHEN** the participant opens the app
- **THEN** the Series map is shown, not a lesson or step

#### Scenario: Reload inside a Part
- **GIVEN** the participant is reading a lesson
- **WHEN** the page is reloaded
- **THEN** the Series map is shown
- **AND** no progress is lost

#### Scenario: First run
- **GIVEN** the app has never been set up and setup has not been skipped
- **WHEN** the participant opens the app
- **THEN** the setup wizard is shown first, not the Series map

### Requirement: One row per Part, in series order
The Series map SHALL list all six Parts in series order, each with its number and name: 1 Structured prompting, 2 Defining evaluation criteria, 3 Running evals and baseline, 4 Iterating with evaluation-driven development, 5 Load-bearing audit and packaging, 6 Your own task. Each row SHALL give its state in words as well as by color or icon.

#### Scenario: All six Parts are listed
- **WHEN** the Series map is shown
- **THEN** six rows appear in the order 1 to 6, each with its number and name

#### Scenario: State is not color alone
- **WHEN** a row shows a state (not started, in progress, done, coming soon or live meeting)
- **THEN** the state is written in text that a screen reader reads

### Requirement: Parts without content show Coming soon
A Part with no content (Parts 4 and 5) SHALL show its number, name, a one-line outcome and a "Coming soon" label. Its row SHALL have no expand control, SHALL NOT be a link or button, and SHALL NOT open anything or change any state when selected.

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

#### Scenario: Part 2 is no longer coming soon
- **WHEN** the participant looks at the row for Part 2
- **THEN** it shows a state, a count and an open control, and no "Coming soon" label

### Requirement: Part 6 explains that it is a live meeting
The Part 6 row SHALL show its number, name, a "Live meeting" label and a brief, plain explanation of what the Part is about (choosing a task of your own that repeats, has clear requirements and can be checked by rules) and that it takes place live, where participants talk their ideas through. Its row SHALL have no expand control and SHALL NOT be a link or button.

#### Scenario: Part 6 row
- **WHEN** the participant looks at the row for Part 6
- **THEN** it shows the number, name, the label "Live meeting" and the short explanation
- **AND** it has no expand icon and does not say "Coming soon"

#### Scenario: Selecting the Part 6 row
- **WHEN** the participant clicks or presses a key on the Part 6 row
- **THEN** nothing opens and the Series map stays as it was

### Requirement: The Part 6 row points to no people or places
The Part 6 row SHALL NOT mention office hours, the AIR discussion, or any person, place, contact detail, link or schedule. Source: user authorization recorded in the proposal, as a one-place exception to AGENTS.md rule 10; see `series-intent-framing`.

#### Scenario: No pointers to people
- **WHEN** the content tests scan the Part 6 row
- **THEN** it contains no contact-instruction phrase, "office hours", "AIR discussion" or the word "session"

### Requirement: A Part with content shows its progress
The row for a Part with content (Parts 1, 2 and 3) SHALL show where the participant stands: not started, in progress or done, with the count of lessons and steps done out of the total, the same count that Part's sidebar shows. While the Part is not finished, the row SHALL name the action that selecting it takes ("Start" or "Continue").

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
- **GIVEN** the participant has finished three items of Part 1 and none of Part 2 or Part 3
- **WHEN** the Series map is shown
- **THEN** the Part 1 row shows 3 of 9 done, the Part 2 row shows 0 of 8 and the Part 3 row shows 0 of 16

### Requirement: A Part row expands to its lesson names
A Part with content SHALL have an expand control (its expanded state available to screen readers) separate from the control that opens the Part. Expanding SHALL show that Part's lesson names in order, each with its status in the same words the sidebar uses (done, skipped, now or not started), as plain text that does not open the lesson. Expanding or collapsing SHALL NOT open the Part or change progress.

#### Scenario: Expanding
- **WHEN** the participant uses the expand control on the Part 3 row
- **THEN** the seven lesson names appear in course order, each with its status
- **AND** the participant stays on the Series map

#### Scenario: Expanding Part 1
- **WHEN** the participant uses the expand control on the Part 1 row
- **THEN** its four lesson names appear in course order, each with its status

#### Scenario: Expanding Part 2
- **WHEN** the participant uses the expand control on the Part 2 row
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
- **THEN** the rows of Part 1, Part 2 and Part 3 are expanded

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

#### Scenario: Opening Part 2
- **GIVEN** the participant has not started Part 2
- **WHEN** they select the Part 2 row
- **THEN** Part 2 opens on `p2-mission`, with Part 2's own course list and header

#### Scenario: Before setup has passed
- **GIVEN** setup was skipped and has not passed
- **WHEN** the participant selects Part 3
- **THEN** Part 3 opens with locked items still unavailable for work, and open as read-only previews for reading

### Requirement: Back to series map
Inside a Part, the sidebar SHALL keep its progress, course list and tools and SHALL add a "Back to series map" control above the progress. On narrow screens the control SHALL be in the top bar. Using it SHALL show the Series map and SHALL NOT change progress, lock or unlock an item, or stop a running CLI process.

#### Scenario: Return to the map
- **GIVEN** the participant is in a lesson of Part 3
- **WHEN** they select "Back to series map"
- **THEN** the Series map is shown
- **AND** the Part 3 row reflects the participant's current progress

#### Scenario: Narrow screen
- **GIVEN** the window is narrow
- **WHEN** the participant is inside a Part
- **THEN** "Back to series map" is reachable from the top bar

### Requirement: Sidebar tools are available on every screen
The sidebar's tools (glossary, reference card, theme toggle, Settings, Quit) SHALL be shown, in the same order and with the same behavior, on the Series map and inside a Part. The collapse control SHALL work on both, and its state SHALL be shared. The setup reminder and review banners SHALL show on the Series map as they do inside a Part. The map's sidebar SHALL NOT show the progress count or the course list. The full-page setup wizard still shows no sidebar.

#### Scenario: Tools on the map
- **WHEN** the Series map is shown
- **THEN** glossary, reference card, theme toggle, Settings and Quit are available and work

#### Scenario: Collapsed sidebar is shared
- **GIVEN** the sidebar is collapsed to icons inside Part 3
- **WHEN** the participant goes back to the Series map
- **THEN** the sidebar is still collapsed

#### Scenario: Banner on the map
- **GIVEN** setup has been skipped and has not passed
- **WHEN** the Series map is shown
- **THEN** the setup reminder banner is shown above the map

### Requirement: The map does not disturb the course
Showing the Series map, expanding a row, or returning from it SHALL NOT change progress, lock or unlock an item, write any participant file or stored progress, or start or stop a CLI process.

#### Scenario: Browsing the map
- **WHEN** the participant opens the Series map, expands and collapses a row, then opens Part 3
- **THEN** progress and stored files are unchanged

### Requirement: Series map words live in content and are the only list of the Parts
All text on the Series map, including Part names, outcomes, labels, the intro line and the Back control, SHALL come from the content files and follow the app's plain-language rules (the word "Part", no presenter or classroom words). No mission lesson lists the Parts, so the Series map holds the only copy of the names and outcomes.

#### Scenario: Banned words
- **WHEN** the content tests run
- **THEN** no Series map text contains a banned word

#### Scenario: One place for the names
- **WHEN** the content tests scan the mission lessons
- **THEN** none lists the Part names

### Requirement: The Series map intro is about doing the work yourself
The intro line of the Series map SHALL say there are six Parts and one method, and that the participant does each Part themselves because copying someone else's prompt or rules gives their answers, not the skill to check your own. It SHALL NOT say to look ahead and SHALL NOT mention Stage 3. Source: series review item 19.

#### Scenario: The intro
- **WHEN** the participant opens the Series map
- **THEN** the intro reads in plain words, in one or two sentences, that each Part is to be done by the participant

#### Scenario: No look ahead, no Stage 3
- **WHEN** the content tests scan the Series map intro
- **THEN** it contains neither "look ahead" nor "Stage 3"
