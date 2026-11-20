# course-locking Specification

## Purpose

Makes the course strictly sequential for participants: a lesson, step or Part opens only after what comes before it is done or skipped, and what is locked can be neither read nor done. Source: series review items 1, 1d, 4 and 18.

## Requirements

### Requirement: An item opens only when what is before it is finished
A lesson or step SHALL open, for reading and for doing, only when it is done, skipped, or the next item to do in its own Part. An item is the next to do when every lesson and step before it in the course order of its Part is done or skipped. The same order SHALL apply whether or not setup has passed; hands-on work still follows `setup-access`.

#### Scenario: The next item opens
- **GIVEN** Part 1 is open and `p1-mission` is done
- **WHEN** the participant opens the next item in the list
- **THEN** it opens and works as normal

#### Scenario: A later item stays closed
- **GIVEN** the participant is on the second lesson of a Part
- **WHEN** they try to open the fourth item of that Part
- **THEN** it does not open, and the lock message is shown instead

#### Scenario: A finished item can be read again
- **GIVEN** the participant finished a lesson
- **WHEN** they open it from the course list
- **THEN** it opens, as it did before

### Requirement: A Part opens only when every earlier Part is Done or Skipped
Part 2 SHALL open only when Part 1 is Done or Skipped, and Part 3 only when Parts 1 and 2 are each Done or Skipped. A Part that is not open SHALL show its state as "Not started" with the lock icon, SHALL NOT open from the Series map, and SHALL refuse every one of its lessons and steps. Selecting it SHALL NOT start it or change any progress.

#### Scenario: Part 3 before Parts 1 and 2
- **GIVEN** Parts 1 and 2 are not done and not skipped
- **WHEN** the participant tries to open Part 3, by the map or by a direct request
- **THEN** it does not open and nothing is recorded or started

#### Scenario: Part 3 after Part 1 skipped and Part 2 done
- **GIVEN** Part 1 is Skipped and Part 2 is Done
- **WHEN** the participant opens Part 3
- **THEN** it opens at its first item

#### Scenario: Part 2 while Part 1 is in progress
- **GIVEN** Part 1 is in progress
- **WHEN** the participant looks at the Series map
- **THEN** the Part 2 row is Locked, and Part 1's row offers Continue

#### Scenario: The Part 3 Start button
- **GIVEN** Part 1 has an unfinished item
- **WHEN** the participant selects the Part 3 row
- **THEN** Part 3 is not started and is not marked in progress

### Requirement: A locked item can neither be read nor done
A locked lesson, step or Part SHALL NOT open as a read-only view or preview. Every request that names it (open, answer, start, check, submit, complete, skip or restart) SHALL be refused with one plain message saying it opens when the previous ones are done, and nothing SHALL be read from or written to participant files or saved progress. The sealed answer key SHALL stay sealed (AGENTS.md rule 9).

#### Scenario: Opening a locked lesson
- **GIVEN** a lesson is locked
- **WHEN** a request asks for it
- **THEN** it is refused with the lock message and no text of the lesson is returned

#### Scenario: Opening a locked step
- **GIVEN** a step is locked
- **WHEN** the page or a direct request asks for it
- **THEN** it is refused with the lock message and no step text is returned

#### Scenario: Doing a locked item
- **GIVEN** a lesson or step is locked
- **WHEN** a request tries to answer, start, check, submit or complete it
- **THEN** it is refused with the lock message and nothing is recorded

#### Scenario: The key step stays sealed
- **GIVEN** the participant's predictions are not locked
- **WHEN** a request asks for the `key` step
- **THEN** it is refused and no answer key text is returned

### Requirement: With setup skipped, only the current and finished items can be read
When setup has not passed, the participant SHALL be able to read the item that is next to do and every item that is done or skipped, and nothing else. Hands-on work SHALL stay refused as `setup-access` sets out. "Skip for now" in setup SHALL stay available. Source: series review item 18.

#### Scenario: Skipped setup
- **GIVEN** the participant skipped setup and is at the start of Part 1
- **WHEN** they look at the course list
- **THEN** `p1-mission` opens and works, and every other item is locked

#### Scenario: The first step after a lesson
- **GIVEN** setup was skipped and `p1-mission` is done
- **WHEN** the participant opens the `cold` step
- **THEN** it opens as the next item, its hands-on controls are off, and there is a way to open setup

### Requirement: A locked item looks locked and cannot be selected
In the Series map, the course list and the step list, a locked item SHALL be greyed, SHALL show a lock icon and the status word "Not started", and SHALL NOT open anything or change any state when clicked or activated by keyboard. It SHALL show the tooltip "opens when the previous ones are done" on hover and on keyboard focus. The icon SHALL have an accessible name, and the item SHALL stay reachable by keyboard so the text can be read.

#### Scenario: Locked row in the course list
- **GIVEN** the participant is on the second lesson of a Part
- **WHEN** they look at the course list
- **THEN** each later item is greyed with a lock icon and the word "Not started"

#### Scenario: Selecting a locked row
- **WHEN** the participant clicks a locked item, or presses Enter or Space on it
- **THEN** nothing opens and nothing changes

#### Scenario: Tooltip on focus
- **WHEN** the participant tabs to a locked item
- **THEN** the text "opens when the previous ones are done" is shown and is read by a screen reader

#### Scenario: Not colour alone
- **WHEN** a locked item is shown in either theme
- **THEN** the lock icon and the word "Not started" tell it apart, not the grey alone

### Requirement: Links to a locked lesson are plain text
The glossary and a lesson's "related lessons" list SHALL show a lesson that is locked as plain text with the word "Not started", not as a link or button, and SHALL link to a lesson that is open. The "Continue" control after finishing an item SHALL still lead to the next item to do.

#### Scenario: Glossary entry for a locked lesson
- **GIVEN** a glossary entry points to a lesson that is locked
- **WHEN** the participant opens the entry
- **THEN** the lesson's title is plain text with the word "Not started", and nothing opens when it is clicked

#### Scenario: Related lesson that is open
- **GIVEN** a lesson lists a related lesson the participant has finished
- **WHEN** it is shown
- **THEN** the related lesson is a link that opens it

#### Scenario: Continue
- **GIVEN** the participant just finished an item
- **WHEN** they select "Continue"
- **THEN** the next item to do opens

### Requirement: The lock does not touch the reference material
The glossary, the reference card, Settings and the bundled files that lessons cite SHALL stay readable at any time, in any order. They are not lessons or steps.

#### Scenario: Reference card early
- **GIVEN** the participant has just started Part 1
- **WHEN** they open the reference card or the glossary
- **THEN** it opens

### Requirement: The lock words live in content
Every word of the lock (the tooltip, the status word, the refusal message) SHALL come from the content files and follow `participant-vocabulary`.

#### Scenario: Words scan
- **WHEN** the content tests scan the lock words
- **THEN** none contains a banned word, and the tooltip text is the same wherever it appears
