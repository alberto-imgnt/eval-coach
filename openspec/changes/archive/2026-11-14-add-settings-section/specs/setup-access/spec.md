## Purpose

Makes setup a one-time, global screen instead of a course item, and keeps all of its functions available from Settings.

## ADDED Requirements

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
- **THEN** the participant gains full access to the course, starting with the mission lesson

#### Scenario: Skipping setup
- **GIVEN** the participant is in the setup wizard on first run
- **WHEN** the participant skips setup
- **THEN** the course is shown with learning content available
- **AND** the setup reminder banner is shown

#### Scenario: Skip is remembered
- **GIVEN** the participant skipped setup and then closed and reopened the app
- **WHEN** the app opens
- **THEN** it opens on the course with the reminder banner and does not show the setup wizard again by itself

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

### Requirement: Setup is a full-page wizard
The setup wizard SHALL fill the whole window with one page per applicable check, in order: Track, Python, AI CLI, Sign in and license, CLI working test, Project folder (the promptfoo track adds Node and promptfoo pages). While it is open, the course sidebar, course list, tools and reminder banner SHALL NOT be shown.

#### Scenario: Nothing beside the wizard
- **WHEN** the setup wizard is shown
- **THEN** it fills the window
- **AND** no course list, sidebar or reminder banner is shown beside it

#### Scenario: Last page
- **GIVEN** the participant is on the Project folder page and every earlier check has passed
- **WHEN** the participant sets up the project
- **THEN** setup is done and the wizard closes on the first lesson

### Requirement: The wizard guides the participant page by page
The wizard SHALL show which page the participant is on and how many there are, without course words ("Part", "step"), with Back and Next controls. Next SHALL be disabled until the current page's check has passed. It SHALL open on the first page whose check has not passed, or on the Track page when no check after it has passed.

#### Scenario: Progress and order
- **WHEN** the participant is on the third of six pages
- **THEN** the wizard shows "3 of 6" and the page names
- **AND** Back returns to the second page

#### Scenario: Next waits for the check
- **GIVEN** the current page's check has not passed
- **WHEN** the participant looks at Next
- **THEN** it is disabled and a plain line says what is still needed

#### Scenario: Next after the check passes
- **GIVEN** the current page's check passes
- **WHEN** the participant presses Next
- **THEN** the next page is shown

#### Scenario: Opening position
- **GIVEN** the Track and Python checks have passed and the AI CLI check has not
- **WHEN** the wizard opens
- **THEN** it shows the AI CLI page

#### Scenario: Fresh setup
- **GIVEN** no check after the Track check has passed
- **WHEN** the wizard opens
- **THEN** it shows the Track page, with the welcome text

### Requirement: The wizard keeps the terminal and the CLI working
The pages that use the participant's CLI (AI CLI, Sign in and license, CLI working test) SHALL show the terminal inside the wizard, beside the page on a wide window and below it on a narrow one. Pages that do not use it SHALL NOT show a terminal. Moving between pages SHALL NOT stop a running CLI process.

#### Scenario: Terminal on a CLI page
- **WHEN** the participant is on the AI CLI page
- **THEN** the terminal is shown inside the wizard

#### Scenario: Running CLI while moving
- **GIVEN** the participant started their CLI on the AI CLI page
- **WHEN** the participant moves to the Sign in and license page
- **THEN** the same CLI process is still running in the terminal

#### Scenario: No terminal elsewhere
- **WHEN** the participant is on the Python page
- **THEN** no terminal is shown

### Requirement: Leaving the wizard
On first run the wizard SHALL offer "Skip for now" on every page. When it was opened from Settings or from the reminder banner, it SHALL instead offer a close action that returns to the screen the participant came from, and SHALL NOT offer to skip. Closing or skipping SHALL NOT change any check's result or stop a running CLI process.

#### Scenario: Closing from Settings
- **GIVEN** the participant opened setup from Settings
- **WHEN** the participant closes the wizard
- **THEN** Settings is shown again with the same sidebar layout

#### Scenario: Closing from the banner
- **GIVEN** the participant opened setup from the reminder banner on a lesson
- **WHEN** the participant closes the wizard
- **THEN** the same lesson is shown with the banner

### Requirement: Hands-on work needs setup
Until setup has passed, the participant SHALL NOT be able to do hands-on work: every step, and every lesson exercise that starts the participant's CLI. Those controls SHALL be disabled with a plain explanation and a way to open setup, and the server SHALL refuse them with the existing setup-incomplete error.

#### Scenario: Starting a CLI exercise without setup
- **GIVEN** setup has not passed
- **WHEN** the participant tries to start a lesson exercise that uses the CLI
- **THEN** the control is disabled and says setup is needed
- **AND** a direct request to the server is refused

#### Scenario: Steps without setup
- **GIVEN** setup has not passed
- **WHEN** the participant opens a step
- **THEN** its instructions can be read
- **AND** nothing in it starts the CLI

### Requirement: Learning content is readable before setup
Until setup has passed, every lesson SHALL be openable for reading in any order, together with the glossary, the reference and the files lessons cite. Items that normal course order would still keep locked SHALL open as read-only previews: their exercises are shown but cannot be answered or completed, and nothing about them is recorded in progress.

#### Scenario: Reading ahead
- **GIVEN** setup has not passed
- **WHEN** the participant opens a lesson that normal order would still keep locked
- **THEN** its text is shown
- **AND** its exercises cannot be answered and nothing is recorded

#### Scenario: Reading the current lesson
- **GIVEN** setup has not passed and the mission lesson is the current item
- **WHEN** the participant opens it
- **THEN** it works as normal, because it has no hands-on exercise

#### Scenario: Question exercises
- **GIVEN** setup has not passed and a lesson is open by normal order
- **WHEN** the lesson has exercises that do not use the CLI
- **THEN** those exercises work as normal
- **AND** the lesson cannot be completed while a required CLI exercise is undone

### Requirement: Setup is not a course item
The course list SHALL NOT contain a "Before you begin" or other setup entry, and no lesson or step SHALL have its own setup screen. The course progress shown by the app SHALL count only lessons and steps.

#### Scenario: Course list
- **WHEN** the course list is shown at any time
- **THEN** it lists only lessons and steps

### Requirement: Full setup is available in Settings
The setup group in the Settings panel SHALL show a short summary of the setup checks and their status and an "Open setup" button that opens the same setup wizard, full page. Everything setup provides SHALL be reachable through it: running or re-running checks, installs, choosing and testing the CLI command, the track choice, the project folder, and importing your own files. It SHALL be the same capability, not a reduced copy, and SHALL work whether or not setup has passed.

#### Scenario: Opening setup from Settings
- **WHEN** the participant presses "Open setup" in Settings
- **THEN** the setup wizard fills the window
- **AND** it offers to close back to Settings

#### Scenario: Re-running a check from Settings
- **GIVEN** every check has passed
- **WHEN** the participant opens setup from Settings and runs the checks again
- **THEN** the checks run and their statuses update

#### Scenario: Changing the CLI command from Settings
- **WHEN** the participant opens setup from Settings, enters a new CLI command and checks it
- **THEN** the result is the same as doing so on first run

#### Scenario: Completing setup from Settings
- **GIVEN** setup has never passed
- **WHEN** the participant uses setup opened from Settings
- **THEN** they can complete setup there

### Requirement: Existing setup rules still apply
Using setup from Settings or from the wizard SHALL follow the same rules everywhere: the track is locked once a step is done, a project inside OneDrive is refused, only one CLI process runs at a time, and nothing is installed without consent. Steps SHALL stay locked while any applicable check has not passed.

#### Scenario: Track locked
- **GIVEN** a step is done
- **WHEN** the participant tries to change the track in the setup wizard
- **THEN** the change is refused with the same plain-language reason as before

### Requirement: One source for the text
Text in the setup wizard and in the Settings setup group SHALL come from the content files, with the same wording for the same thing wherever it appears, so a wording change appears everywhere.

#### Scenario: Wording change
- **WHEN** the setup intro text is edited in its content file
- **THEN** the wizard and Settings show the edited text
