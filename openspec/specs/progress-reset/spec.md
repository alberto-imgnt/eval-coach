# progress-reset Specification

## Purpose

Lets a participant restart the course with "Reset lesson progress": a confirmed action that leaves no progress or course files behind in the app, keeps a single backup, and keeps setup, display choices and the starting files.

## Requirements

### Requirement: Reset lesson progress needs explicit confirmation
Reset lesson progress SHALL NOT run until the participant confirms in a dialog that says in plain words what will be cleared, what will be kept, where the backup will be, and that it replaces the previous backup. The dialog's default action SHALL keep everything.

#### Scenario: Cancelling
- **WHEN** the participant chooses Reset lesson progress and then chooses to keep everything
- **THEN** nothing is cleared or moved

#### Scenario: Confirmation text
- **WHEN** the confirmation dialog opens
- **THEN** it lists what is cleared, what is kept, the backup folder and that the previous backup is replaced, in the words defined by the content files

### Requirement: Reset lesson progress clears progress
After confirmation, all course progress SHALL be cleared: lessons and activities, placement, step records, the baseline, the review schedule, saved hook and practice runs, and every Part skipped. The course SHALL start again at its first item, and every Part after Part 1 SHALL be locked again until the Parts before it are Done or Skipped.

#### Scenario: Full fresh start
- **GIVEN** the participant has finished lessons and steps and has a baseline
- **WHEN** the participant confirms the reset
- **THEN** every lesson and step shows as not started
- **AND** no baseline and no review items exist
- **AND** the current course item is the first one

#### Scenario: Skipped Parts are cleared
- **GIVEN** the participant skipped Part 1
- **WHEN** the participant confirms the reset
- **THEN** no Part shows Skipped, and Parts 2 and 3 are locked

#### Scenario: Track can be chosen again
- **GIVEN** the track was locked because a step was done
- **WHEN** the participant confirms the reset
- **THEN** the track can be changed again before the first step is done

### Requirement: Reset lesson progress leaves no course files
After confirmation, no file that the app or the participant's CLI produced during the course SHALL remain in the project folder: the checker, fixtures, saved runs, saved results, the iteration log, the saved outputs of Part 1 and any other course output. The starting prompt and starting test cases, the prompts the participant wrote in Part 1 (cold, framework, and the own-work before and after) and the worksheet and test cases the participant wrote in Part 2 SHALL stay in place, and every other file in the project folder SHALL be left untouched.

#### Scenario: Course outputs gone
- **GIVEN** the project folder holds a checker, fixtures, saved runs, an iteration log and Part 1 outputs
- **WHEN** the participant confirms the reset
- **THEN** none of them is in the project folder
- **AND** the starting prompt and test cases are still there, unchanged

#### Scenario: Part 1 prompts stay
- **GIVEN** the project folder holds the participant's Part 1 prompts and outputs
- **WHEN** the participant confirms the reset
- **THEN** the prompts and own-work files are still there, unchanged, and the outputs are in the backup

#### Scenario: Part 2 files stay
- **GIVEN** the project folder holds the participant's Part 2 worksheet and test cases
- **WHEN** the participant confirms the reset
- **THEN** both files are still there, unchanged, and the Part 2 steps show as not started

#### Scenario: Unknown files untouched
- **GIVEN** the project folder holds a file the app never created
- **WHEN** the participant confirms the reset
- **THEN** that file is still there, unchanged

#### Scenario: Steps start clean
- **WHEN** the participant starts the first step after the reset
- **THEN** no step check passes or fails because of a leftover from before the reset

### Requirement: Cleared files go to one backup
Before anything is cleared, everything the reset removes from the project folder SHALL be moved to a single backup folder outside the project, and the previous backup SHALL be replaced only after the new one is complete. Nothing SHALL be permanently deleted except the previous backup and the answer key. The answer key, if any, SHALL NOT be backed up.

#### Scenario: Backup contents
- **GIVEN** the project folder holds course outputs
- **WHEN** the participant confirms the reset
- **THEN** the backup folder holds those files with their names and contents unchanged

#### Scenario: Second reset
- **GIVEN** a backup from an earlier reset exists
- **WHEN** the participant confirms another reset
- **THEN** only the newest backup exists afterwards

#### Scenario: Answer key
- **GIVEN** the answer key step was done
- **WHEN** the participant confirms the reset
- **THEN** no answer key exists anywhere in the app or the backup
- **AND** none exists until predictions are locked again

### Requirement: Reset lesson progress keeps setup and display choices
It SHALL keep the setup results, the chosen CLI command, the track choice, the project folder and the private runtimes, and SHALL keep the text size, theme and sidebar choices.

#### Scenario: No second setup
- **GIVEN** every setup check had passed
- **WHEN** the participant confirms the reset
- **THEN** the checks still show as passed
- **AND** the CLI command and project folder are unchanged

#### Scenario: Text size survives
- **GIVEN** the text size is 130%
- **WHEN** the participant confirms the reset
- **THEN** the text size is still 130%

### Requirement: Reset stops any running CLI
If a CLI process is running, the app SHALL stop it before clearing anything and SHALL NOT answer any prompt in it.

#### Scenario: Reset during a step
- **GIVEN** a CLI is running for a step
- **WHEN** the participant confirms the reset
- **THEN** the CLI process is stopped
- **AND** progress is then cleared

### Requirement: Reset before a project exists
If no project has been set up, the reset SHALL clear only any course progress held outside a project (kept by earlier versions of the app) and the dialog SHALL say so. No backup is made.

#### Scenario: Nothing to clear
- **GIVEN** setup has not passed and no project exists
- **WHEN** the participant confirms the reset
- **THEN** the app is unchanged except for any earlier course progress, which is cleared

### Requirement: Reset is all or nothing and reports the outcome
If the backup cannot be completed or anything cannot be moved or cleared, the app SHALL change nothing, SHALL say so in plain words, and SHALL leave progress and files as they were. On success it SHALL tell the participant what was cleared and where the backup is.

#### Scenario: Backup fails
- **GIVEN** the backup folder cannot be written
- **WHEN** the participant confirms the reset
- **THEN** a plain-language error is shown
- **AND** progress and project files are exactly as before

#### Scenario: Success message
- **WHEN** the reset finishes
- **THEN** the app says that progress was cleared and names the backup folder
