# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Learning content is always readable`
- TO: `### Requirement: Open items are readable before setup`

## MODIFIED Requirements

### Requirement: Setup comes first and can be skipped
The app SHALL present setup ("Before you begin"), as the setup wizard, as the first thing a participant sees on first run and again after the app configuration is reset. The wizard SHALL offer a clear way to skip it for now on every page. Once setup has passed, no lesson, Part or step SHALL present setup again or show an automatic setup screen.

#### Scenario: First run
- **GIVEN** the app has never been set up
- **WHEN** the participant opens the app
- **THEN** the setup wizard is shown first
- **AND** it offers a way to skip setup for now

#### Scenario: Completing setup
- **GIVEN** the participant is in the setup wizard on first run
- **WHEN** every applicable check passes and the project is set up
- **THEN** hands-on work is open to the participant and the Series map is shown
- **AND** opening Part 1 from the map starts at its mission lesson

#### Scenario: Skipping setup
- **GIVEN** the participant is in the setup wizard on first run
- **WHEN** the participant skips setup
- **THEN** the Series map is shown, and the mission lesson of Part 1 can be opened from it
- **AND** the setup reminder banner is shown

#### Scenario: Skip is remembered
- **GIVEN** the participant skipped setup and then closed and reopened the app
- **WHEN** the app opens
- **THEN** it opens on the Series map with the reminder banner and does not show the setup wizard again by itself

#### Scenario: Moving through the course after setup
- **GIVEN** setup has passed
- **WHEN** the participant moves from any lesson or step to the next
- **THEN** no setup screen appears

#### Scenario: After resetting app configuration
- **GIVEN** setup had passed, or had been skipped
- **WHEN** the participant resets the app configuration
- **THEN** the app behaves exactly as on first run and shows the setup wizard first
- **AND** the earlier skip is forgotten

#### Scenario: After resetting lesson progress only
- **GIVEN** setup had passed
- **WHEN** the participant resets lesson progress
- **THEN** setup is still passed and is not presented again

### Requirement: Open items are readable before setup
Before setup has passed, the item that is next to do and every item that is done or skipped SHALL be readable, together with the glossary, the reference and the files lessons cite. Which items are open is decided by `course-locking`; setup does not open any other item and does not lock any item that order has opened. Hands-on work SHALL stay refused until setup has passed, and an item that normal order keeps locked SHALL NOT open as a preview, with or without setup.

#### Scenario: Reading ahead
- **GIVEN** setup has not passed
- **WHEN** the participant tries to open a lesson that normal order would still keep locked
- **THEN** it does not open and the lock message is shown, and nothing is recorded

#### Scenario: Reading ahead after setup
- **GIVEN** setup has passed and the participant is on the third lesson of a Part
- **WHEN** they look at a later lesson or step of that Part in the course list, or a request asks for it
- **THEN** it is shown as "Not started" with the lock icon and does not open, and the request is refused

#### Scenario: Reading the current lesson
- **GIVEN** setup has not passed and a mission lesson is the current item
- **WHEN** the participant opens it
- **THEN** it works as normal, because it has no hands-on exercise

#### Scenario: Question exercises
- **GIVEN** setup has not passed and a lesson is open by normal order
- **WHEN** the lesson has exercises that do not use the CLI
- **THEN** those exercises work as normal
- **AND** the lesson cannot be completed while a required CLI exercise is undone

#### Scenario: Previews never do work
- **GIVEN** setup has not passed and a step is the next item to do
- **WHEN** the participant opens it
- **THEN** it shows only the step's words, with no controls that start the CLI, run the checker or save anything, and there is a way to open setup
- **AND** no participant file is read to build it

#### Scenario: The answer key stays sealed
- **GIVEN** the participant's predictions are not locked
- **WHEN** a request asks for the `key` step ahead of time
- **THEN** it is refused and no answer key text is shown

## REMOVED Requirements

### Requirement: A preview says what holds it back
**Reason**: There are no read-only previews of locked items any more; a locked item cannot be opened (`course-locking`). Only a skipped Part opens read-only, and `part-skip` gives it its own note.
**Migration**: The two preview note wordings and the "Back to where I am" button are removed from the content files and the interface.

### Requirement: Locked items can be reached from every list and link
**Reason**: Locked items are now greyed, not clickable and shown with the status "Locked", and links to locked lessons are plain text (`course-locking`). This reverses the archived change `read-ahead-always` for participants.
**Migration**: The course list, step list, glossary and related-lessons list follow `course-locking`; "Continue" is unchanged.
