# platform-wording Specification

## Purpose

Makes the words a participant reads match the computer they use: the paste shortcut, the file manager, path examples and the Python command, without changing the interface and without a second copy of the course.

## Requirements

### Requirement: Platform words come from one place
Every participant-visible word that depends on the computer (paste and copy shortcut, the file manager's name, how to copy a file's path, what a full path looks like, the key that opens a menu, the Python command, the AI install notes) SHALL come from platform entries in the content files, chosen by the computer the app runs on, and SHALL NOT be written into the course text twice. The interface SHALL show the chosen words with no change to its layout, styling, components or element ids (AGENTS.md rule 11).

#### Scenario: Paste shortcut on a Mac
- **GIVEN** the app runs on a Mac
- **WHEN** a step tells the participant to paste into the AI window
- **THEN** it says ⌘V (Command-V)

#### Scenario: Paste shortcut on Windows
- **GIVEN** the app runs on Windows
- **WHEN** the same step is shown
- **THEN** it says Ctrl+V, exactly as before this change

#### Scenario: One source
- **WHEN** the content tests scan the course text
- **THEN** no step or lesson contains a hard-coded `Ctrl+V`, `File Explorer`, `C:\` example or `py` command outside the platform entries

### Requirement: Paths and file names read naturally on each platform
Path examples SHALL use the participant's own style: a drive letter and backslashes on Windows, a home folder and forward slashes on a Mac. Folder names the course uses inside the project (for example `skills/build-eval-script`) SHALL be written with the separator of the computer in use. Where the participant is asked to give the full path of a file, the text SHALL say how to copy it in the file manager they have (Copy as path in File Explorer, Option-Command-C in Finder).

#### Scenario: Full path request on a Mac
- **GIVEN** a participant on a Mac is asked for the full path of their prompt file
- **WHEN** they read the page
- **THEN** the example looks like `/Users/you/Documents/prompt-v0.md`
- **AND** the page says to select the file in Finder and press Option-Command-C

#### Scenario: Not a full path on a Mac
- **GIVEN** a participant on a Mac enters `Documents/prompt-v0.md`
- **WHEN** the file check runs
- **THEN** the message says the path must start from the root or the home folder, not from a drive letter

#### Scenario: Skill folder names
- **WHEN** a step on a Mac names the skill folder
- **THEN** it reads `skills/build-eval-script`, with forward slashes

### Requirement: The Python command is the one that exists
Text that tells the participant, or their AI, how to run Python SHALL name the command that exists on the computer: `python3` on a Mac, and on Windows what it says now. A Mac step SHALL NOT tell the participant to try `py`. The bundled skill files stay byte-identical (AGENTS.md rule 8); the platform's command goes in the typed line.

#### Scenario: Troubleshooting entry on a Mac
- **GIVEN** the checker is run by the participant's AI on a Mac
- **WHEN** the participant's AI says python was not found
- **THEN** the troubleshooting text says to ask it to run the checker with `python3`

#### Scenario: Skill files unchanged
- **WHEN** the tests compare the bundled skills to their source files
- **THEN** every skill file is byte-identical

### Requirement: Vocabulary and tone rules apply on every platform
Text for every platform SHALL follow the same vocabulary rules: "your AI" and "AI window" (never a bare "CLI"), "Practice task" and "My own task", "Part" (never session), "Script track" and "promptfoo track", and no mention of a presenter, facilitator, room, handout or "contact someone" (AGENTS.md rule 10). Mac-only words SHALL be plain: "Finder", "Terminal", "Command key" or ⌘.

#### Scenario: Content tests per platform
- **WHEN** the content tests run
- **THEN** they check the Windows text and the Mac text, and fail on a banned word in either

#### Scenario: No gaps
- **WHEN** the content tests run
- **THEN** every platform entry exists for both Windows and Mac, and a missing one fails the test naming the file and key
