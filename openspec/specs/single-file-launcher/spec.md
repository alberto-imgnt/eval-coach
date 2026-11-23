# single-file-launcher Specification

## Purpose

Lets a participant start eval-coach by double-clicking one file, with Python found or installed for them on the way, so there is no second file or separate setup step to run first.

## Requirements

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

### Requirement: Python is found without asking when it exists
The launcher SHALL look for a working Python 3.9 or later first on the computer, then in the private copy from an earlier run, and SHALL ask a question only when neither is found. A Python that is not a real installation (such as the Microsoft Store placeholder) SHALL NOT be run or counted. Having the app inside the launcher file SHALL NOT change what is found.

#### Scenario: Python on the computer
- **GIVEN** a working Python 3.9 or later is installed
- **WHEN** the launcher runs
- **THEN** that Python starts the app and no download is offered

#### Scenario: Private copy from an earlier run
- **GIVEN** no Python is installed and the private copy from an earlier run works
- **WHEN** the launcher runs
- **THEN** the private copy starts the app and no download is offered

#### Scenario: Store placeholder only
- **GIVEN** the only `python` on the computer is the Microsoft Store placeholder
- **WHEN** the launcher runs
- **THEN** the placeholder is not opened
- **AND** the launcher offers the private copy

### Requirement: A private Python is installed only after consent
When no working Python is found, the launcher SHALL say what it would install, where, its download and installed size, the download address, and the free disk space, and SHALL say that no administrator rights are needed and nothing else on the computer changes. It SHALL download only after the participant answers yes. An unclear answer SHALL be asked again, up to three times in all, and no answer at all or "no" SHALL count as declining. Source: AGENTS.md rule 5 and `docs/SETUP.md` Stage 1.

#### Scenario: Consent shown before anything downloads
- **GIVEN** no working Python is found
- **WHEN** the launcher reaches the install question
- **THEN** it shows what, size, where, address and free space
- **AND** nothing has been downloaded yet

#### Scenario: Participant agrees
- **WHEN** the participant types Y
- **THEN** Python is downloaded, checked, unpacked and tried before it is put in place
- **AND** the app then starts with it

#### Scenario: Participant declines
- **WHEN** the participant types N, or gives no answer
- **THEN** nothing is installed and nothing on the computer changes
- **AND** the launcher says what to do next, either start it again and answer Y or install Python from the company's software portal

#### Scenario: Unclear answers
- **WHEN** the participant types something that is neither yes nor no, three times
- **THEN** the launcher treats it as declining

### Requirement: The download must match its fixed fingerprint
The launcher SHALL accept the downloaded Python only if its SHA-256 fingerprint equals the value built into the launcher. A mismatch, or a download that cannot be checked, SHALL delete the file, install nothing, and say so. No setting or environment value SHALL change the fingerprint that is required. Source: `docs/SETUP.md` Stage 1.

#### Scenario: Damaged or altered download
- **WHEN** the downloaded file's fingerprint does not match
- **THEN** the file is deleted and nothing is installed
- **AND** the message says the file failed its safety check and what to do next

#### Scenario: No way to skip the check
- **GIVEN** a participant or program sets an environment value naming a different fingerprint
- **WHEN** the launcher checks a download
- **THEN** the built-in fingerprint is still the one required

### Requirement: Every failure says what happened and what to do next
Every failure the launcher can report (blocked download, timeout, damaged download, unreadable archive, file removed by security software, low disk space, a Python copy in use, missing Windows tools, no temporary folder, the app stopping with an error) SHALL say in plain words what happened and give a next action that is not "contact someone". After a failure or a decline the window SHALL stay open until a key is pressed, and an app error SHALL show its exit code.

#### Scenario: Blocked download
- **WHEN** the Python download fails because the network or a proxy blocks it
- **THEN** the message says nothing was installed
- **AND** it tells the participant to check the connection and start it again, or install Python from the company's software portal

#### Scenario: Window stays open after a failure
- **WHEN** any failure message is shown
- **THEN** the window waits for a key press before closing

#### Scenario: App stops with an error
- **WHEN** the app exits with a non-zero code
- **THEN** the launcher shows that code
- **AND** it says to close the window and start eval-coach again

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

### Requirement: The launcher works wherever the file is
The launcher SHALL work when the folder holding the file, or the participant's profile folder, has spaces, ampersands, parentheses or exclamation marks in its path.

#### Scenario: Unusual folder name
- **GIVEN** the file is in a folder named `My Files & (Old)!`
- **WHEN** the participant double-clicks it
- **THEN** the app starts

### Requirement: Replacing the file updates the app
Replacing `eval-coach.cmd` with a newer one SHALL be the whole update: the new file SHALL start the newer app, and the private Python and the participant's saved progress and files SHALL be left as they are.

#### Scenario: Newer file, same computer
- **GIVEN** the participant has run an earlier `eval-coach.cmd` and has progress saved
- **WHEN** they replace it with a newer one and double-click it
- **THEN** the newer app starts and the saved progress is still there
