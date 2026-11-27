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
- **WHEN** a row shows a state (not started, in progress, done, skipped, locked, coming soon or live meeting)
- **THEN** the state is written in text that a screen reader reads

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

### Requirement: The Series map page is titled "Evaluated systems"
The heading of the Series map page SHALL read "Evaluated systems". Every other reference to the map by name (the "Back to series map" control and its tooltip, the sidebar, Settings, the setup wizard and its messages) SHALL keep its current words. Source: user decision 2026-11-20.

#### Scenario: The heading
- **WHEN** the participant opens the Series map
- **THEN** the page heading reads "Evaluated systems"
- **AND** the heading is still the element that receives focus when the page opens

#### Scenario: Other references are unchanged
- **GIVEN** the participant is inside a Part
- **WHEN** they look at the control that returns to the map
- **THEN** it still reads "Back to series map"

### Requirement: The Series map intro says what the series is for
The intro under the Series map heading SHALL state the series outcome in plain words, as the questions a participant already asks (is AI work good enough to use, and how do you know) and an answer made of principles: work that is asked for clearly, judged against rules you can test, measured so that a better prompt is a fact and not an opinion, and kept to what earns its place. It SHALL end by pointing down at the rows, ending with a task of the participant's own.

#### Scenario: Outcome and principles
- **WHEN** the participant opens the Series map
- **THEN** the intro opens with the two questions "Is it good enough to use?" and "How do you know?"
- **AND** it defines an evaluated system through the four principles above, in that order
- **AND** its last clause points at the rows and at a task of the participant's own

#### Scenario: Each clause echoes a row
- **WHEN** the intro is read beside the six rows
- **THEN** its clauses follow the order of the Parts' outcomes (asking clearly, rules, measuring, proof of improvement, keeping what earns its place, a task of your own)
- **AND** no Part is named in it

### Requirement: The Series map intro is not procedural
The intro SHALL NOT count or name the Parts, SHALL NOT use sequence or step wording, SHALL NOT say to look ahead and SHALL NOT mention Stage 3. It SHALL be at most four short sentences and at most 80 words. It SHALL follow the plain-language rules of AGENTS.md rule 10.

#### Scenario: No count and no sequence
- **WHEN** the content tests scan the Series map intro
- **THEN** it contains none of "six", "Part", "step", "first", "then", "look ahead" or "Stage 3"

#### Scenario: Length
- **WHEN** the content tests measure the intro
- **THEN** it has at most four sentences and at most 80 words

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
