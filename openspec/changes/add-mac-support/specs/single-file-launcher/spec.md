# Spec Delta

## MODIFIED Requirements

### Requirement: One file starts the app
Everything a participant needs to start eval-coach on Windows SHALL be in one file, `eval-coach.cmd`. Double-clicking it SHALL check for Python, then start the app and open it in the browser, with no other file beside it and no earlier step. The Mac equivalent is `eval-coach.command` (see `mac-launcher`). Source: this replaces the Phase 5 plan item "Build `eval-coach.zip` with exactly two files".

#### Scenario: Python is already installed
- **GIVEN** the participant has a working Python 3.9 or later
- **WHEN** the participant double-clicks `eval-coach.cmd`
- **THEN** the app starts and opens in the browser
- **AND** the participant is not asked a question

#### Scenario: The file is alone in its folder
- **GIVEN** `eval-coach.cmd` is the only file in its folder
- **WHEN** the participant double-clicks it
- **THEN** the app starts

#### Scenario: Opened straight from the zip
- **GIVEN** the file was opened from inside a zip file, so Windows extracted only that file
- **WHEN** the participant double-clicks it
- **THEN** the app starts
- **AND** no "missing file" message is shown

### Requirement: Messages tell participants to start eval-coach again
Setup messages that send a participant back to the launcher SHALL say to start eval-coach again, and SHALL NOT name `setup.cmd`, `eval-coach.cmd`, `eval-coach.command` or any other file. The launchers' own messages SHALL call the file `eval-coach`. Wording follows `participant-vocabulary` (AGENTS.md rule 10). This holds on Windows and on a Mac.

#### Scenario: Python missing in the wizard
- **WHEN** the wizard's Python page reports that Python could not be run
- **THEN** its next step says to close the window and start eval-coach again
- **AND** it names no file

#### Scenario: Launcher messages
- **WHEN** a launcher shows a failure or a decline message
- **THEN** it refers to "eval-coach" and not to "setup.cmd" or a file extension

#### Scenario: Mac launcher messages
- **WHEN** the Mac launcher shows a failure or a decline message
- **THEN** it refers to "eval-coach" and not to "eval-coach.command"
