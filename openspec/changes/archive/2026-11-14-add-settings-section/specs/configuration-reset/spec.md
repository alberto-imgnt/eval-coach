## Purpose

Lets a participant return the app to its first-run state with "Reset app configuration", which also does everything "Reset lesson progress" does, with the same single backup.

## ADDED Requirements

### Requirement: Reset app configuration needs a stronger confirmation
Reset app configuration SHALL NOT run until the participant confirms in a dialog that names everything it clears (setup results, CLI command, track, remembered project, starting prompt and test cases, text size and other display choices, and all lesson progress), everything it keeps, where the backup will be, and that it replaces the previous backup. The dialog's default action SHALL keep everything, and it SHALL be visibly different from the lesson progress dialog.

#### Scenario: Cancelling
- **WHEN** the participant chooses Reset app configuration and then keeps everything
- **THEN** nothing is cleared or moved

#### Scenario: Dialog mentions progress
- **WHEN** the confirmation dialog opens
- **THEN** it states that lesson progress is also cleared

### Requirement: Configuration reset includes the lesson progress reset
Confirming SHALL do everything Reset lesson progress does: the same progress clearing, removal of course files into the same single backup, no answer key anywhere, stopping of a running CLI, and the same all-or-nothing outcome.

#### Scenario: Progress and files cleared too
- **GIVEN** the participant has progress, a baseline and course files
- **WHEN** the participant confirms Reset app configuration
- **THEN** every lesson and step shows as not started
- **AND** no course output remains in the project folder

### Requirement: Configuration reset also moves the starting files
Confirming SHALL also move the starting prompt, the starting test cases and the bundled skill files out of the project folder into the same backup, so that no file the app created is left in it. Every other file in the project folder SHALL be left untouched.

#### Scenario: Nothing from the app left
- **GIVEN** the project folder holds the starting files, course outputs and an unrelated file
- **WHEN** the participant confirms Reset app configuration
- **THEN** only the unrelated file remains in the project folder
- **AND** the backup holds everything that was moved

### Requirement: Configuration reset clears setup
Confirming SHALL clear the setup results, the track choice, the CLI command and the remembered project, so the app no longer knows which project was in use.

#### Scenario: Setup is needed again
- **GIVEN** every setup check had passed
- **WHEN** the participant confirms Reset app configuration
- **THEN** no check shows as passed
- **AND** the CLI command is empty and no project is selected
- **AND** steps are locked

### Requirement: Configuration reset returns display choices to defaults
Confirming SHALL return the text size to 100% and the theme and sidebar choices to their defaults in this browser as soon as the reset succeeds.

#### Scenario: Display back to defaults
- **GIVEN** the text size is 140% and the theme is dark
- **WHEN** the participant confirms Reset app configuration
- **THEN** the text size is 100% and the theme is light

### Requirement: Configuration reset keeps downloads
It SHALL keep the private runtimes and package cache downloaded with consent, so setup checks can pass again without downloading.

#### Scenario: Runtimes kept
- **GIVEN** the private runtimes were downloaded earlier
- **WHEN** the participant confirms Reset app configuration and runs setup again
- **THEN** the runtime check passes without a new download

### Requirement: The app then behaves as on first run
After the reset, the app SHALL behave exactly as on first run: setup is shown first and every lesson and step is locked until setup passes, after which the course starts at its first item.

#### Scenario: Restart of the experience
- **WHEN** the reset finishes
- **THEN** the setup screen is shown first
- **AND** every lesson and step is locked

#### Scenario: Course after setup
- **GIVEN** the reset has finished
- **WHEN** the participant completes setup again
- **THEN** the course starts at its first item with no progress
