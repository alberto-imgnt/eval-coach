## RENAMED Requirements

- FROM: `### Requirement: Learning content is readable before setup`
- TO: `### Requirement: Learning content is always readable`

## MODIFIED Requirements

### Requirement: Learning content is always readable
Every lesson and step SHALL be openable for reading at any time, in any order, whether or not setup has passed, together with the glossary, the reference and the files lessons cite. An item that normal course order keeps locked SHALL open as a read-only preview: its text and exercises are shown, but exercises cannot be answered, steps cannot be started or checked, nothing can be completed, and nothing about it is recorded in progress.

#### Scenario: Reading ahead
- **GIVEN** setup has not passed
- **WHEN** the participant opens a lesson that normal order would still keep locked
- **THEN** its text is shown
- **AND** its exercises cannot be answered and nothing is recorded

#### Scenario: Reading ahead after setup
- **GIVEN** setup has passed and the participant is on the third lesson of a Part
- **WHEN** they open a later lesson or step of that Part from the course list
- **THEN** it opens as a read-only preview instead of being greyed out or refused
- **AND** its status still reads "Locked" and nothing is recorded

#### Scenario: Reading the current lesson
- **GIVEN** setup has not passed and the mission lesson is the current item
- **WHEN** the participant opens it
- **THEN** it works as normal, because it has no hands-on exercise

#### Scenario: Question exercises
- **GIVEN** setup has not passed and a lesson is open by normal order
- **WHEN** the lesson has exercises that do not use the CLI
- **THEN** those exercises work as normal
- **AND** the lesson cannot be completed while a required CLI exercise is undone

#### Scenario: Previews never do work
- **GIVEN** a step is shown as a preview
- **WHEN** the participant looks at it
- **THEN** it shows only the step's words, with no controls that start the CLI, run the checker or save anything
- **AND** no participant file is read to build it

#### Scenario: The answer key stays sealed
- **GIVEN** the participant's predictions are not locked
- **WHEN** they read the `key` step ahead of time
- **THEN** the preview holds the step's instructions only, and no answer key text is shown

## ADDED Requirements

### Requirement: A preview says what holds it back
A preview SHALL carry a plain note saying that the participant is reading ahead and that nothing done there is saved. When setup has not passed, the note SHALL say setup is not finished and offer the way to open setup. When setup has passed, the note SHALL name the earlier lesson or step still to do and offer a button that returns to the participant's current item in the same Part.

#### Scenario: Note before setup
- **GIVEN** setup has not passed
- **WHEN** a preview is shown
- **THEN** the note says setup is not finished and offers to open setup

#### Scenario: Note after setup
- **GIVEN** setup has passed and the participant's current item is `several-runs`
- **WHEN** they read the `rules` lesson ahead
- **THEN** the note names the lesson still to do and offers a button back to `several-runs`

#### Scenario: Back to where I am
- **GIVEN** a preview is shown after setup
- **WHEN** the participant presses the button in its note
- **THEN** their current item opens, and progress is unchanged

### Requirement: Locked items can be reached from every list and link
The course list, the step list, the glossary and a lesson's related-lessons list SHALL open a locked lesson or step as a preview, with its status shown in words as "Locked". They SHALL NOT show it as unavailable text or leave it out. The "Continue" control after finishing an item SHALL still lead to the next item to do.

#### Scenario: Course list after setup
- **GIVEN** setup has passed
- **WHEN** the participant looks at the course list
- **THEN** every item is a control that opens it, and a locked one is labelled "Locked"

#### Scenario: Glossary link to a locked lesson
- **GIVEN** a glossary entry points to a lesson that is still locked
- **WHEN** the participant opens the entry
- **THEN** a link to the lesson is shown and opens it as a preview

#### Scenario: Continue is unchanged
- **GIVEN** the participant has just finished a step
- **WHEN** the next item is locked by a lesson that is still to do
- **THEN** "Continue" does not open the locked item as if it were next to do
