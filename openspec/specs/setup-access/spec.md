# setup-access Specification

## Purpose

Makes setup a one-time, global screen instead of a course item, and keeps all of its functions available from Settings.

## Requirements

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
- **THEN** the participant gains full access to the course and the Series map is shown
- **AND** opening Part 3 from the map starts at the mission lesson

#### Scenario: Skipping setup
- **GIVEN** the participant is in the setup wizard on first run
- **WHEN** the participant skips setup
- **THEN** the Series map is shown, and Part 3's learning content is available from it
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

### Requirement: Setup is a full-page wizard
The setup wizard SHALL fill the whole window with one page per step, in order: Track, Checking your computer, Python, Choose your AI, AI working test, Project folder, Your AI window (the promptfoo track adds Node.js and promptfoo pages after Python). While it is open, the course sidebar, course list, tools and reminder banner SHALL NOT be shown. Page titles SHALL follow `participant-vocabulary`. The "Checking your computer" page and the "Your AI window" page are not checks of their own: the first runs the checks and the second is a lesson that is never recorded as progress.

#### Scenario: Nothing beside the wizard
- **WHEN** the setup wizard is shown
- **THEN** it fills the window
- **AND** no course list, sidebar or reminder banner is shown beside it

#### Scenario: Page order
- **GIVEN** the Script track is chosen
- **WHEN** the participant looks at the page list
- **THEN** it reads Track, Checking your computer, Python, Choose your AI, AI working test, Project folder, Your AI window
- **AND** with the promptfoo track, Node.js and promptfoo pages follow Python

#### Scenario: Last page
- **GIVEN** the participant is on the Project folder page and every earlier check has passed
- **WHEN** the participant sets up the project
- **THEN** setup has passed and the wizard moves on to the Your AI window page
- **AND** the wizard closes on the first lesson only when the participant finishes that page

#### Scenario: Page titles
- **WHEN** the participant reads the wizard's page titles
- **THEN** none says "CLI"

### Requirement: The wizard guides the participant page by page
The wizard SHALL show which page the participant is on and how many there are, without course words ("Part", "step"), with Back and Next controls. Next SHALL be disabled until the current page's check has passed. Moving forward SHALL go to the next page that still needs the participant and skip pages whose check has already passed; Back and the page list SHALL still reach every page. It SHALL open on the Track page on a fresh setup, and otherwise on the first page whose check has not passed.

#### Scenario: Progress and order
- **WHEN** the participant is on the third of seven pages
- **THEN** the wizard shows "3 of 7" and the page names
- **AND** Back returns to the second page

#### Scenario: Next waits for the check
- **GIVEN** the current page's check has not passed
- **WHEN** the participant looks at Next
- **THEN** it is disabled and a plain line says what is still needed

#### Scenario: Next after the check passes
- **GIVEN** the current page's check passes and the next page's check has not
- **WHEN** the participant presses Next
- **THEN** the next page is shown

#### Scenario: Next skips passed pages
- **GIVEN** the Python check has passed and the participant is on the Checking your computer page
- **WHEN** the participant presses Next and the next check that has not passed is Choose your AI
- **THEN** the Choose your AI page is shown, not the Python page

#### Scenario: Back reaches a passed page
- **GIVEN** the participant is on the Choose your AI page
- **WHEN** the participant presses Back
- **THEN** the previous page is shown even though its check passed

#### Scenario: Opening position
- **GIVEN** the Track and Python checks have passed and the Choose your AI check has not
- **WHEN** the wizard opens
- **THEN** it shows the Choose your AI page

#### Scenario: Fresh setup
- **GIVEN** no check after the Track check has passed
- **WHEN** the wizard opens
- **THEN** it shows the Track page, with the welcome text

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

#### Scenario: Closing from the banner on the Series map
- **GIVEN** the participant opened setup from the reminder banner on the Series map
- **WHEN** the participant closes the wizard
- **THEN** the Series map is shown with the banner

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
- **AND** its status still reads "Not started" and nothing is recorded

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

### Requirement: Setup is not a course item
The course list SHALL NOT contain a "Before you begin" or other setup entry, and no lesson or step SHALL have its own setup screen. The course progress shown by the app SHALL count only lessons and steps.

#### Scenario: Course list
- **WHEN** the course list is shown at any time
- **THEN** it lists only lessons and steps

### Requirement: Full setup is available in Settings
The setup group in the Settings panel SHALL show a short summary of the setup checks and their status and an "Open setup" button that opens the same setup wizard, full page. Everything setup provides SHALL be reachable through it: running or re-running the checks, installs, choosing and testing the AI, the track choice, the project folder, and importing your own files. It SHALL be the same capability, not a reduced copy, and SHALL work whether or not setup has passed.

#### Scenario: Opening setup from Settings
- **WHEN** the participant presses "Open setup" in Settings
- **THEN** the setup wizard fills the window
- **AND** it offers to close back to Settings

#### Scenario: Re-running a check from Settings
- **GIVEN** every check has passed
- **WHEN** the participant opens setup from Settings and reaches the Checking your computer page
- **THEN** the checks run and their statuses update

#### Scenario: Changing the CLI command from Settings
- **WHEN** the participant opens setup from Settings, chooses a different AI on the Choose your AI page and runs the working test
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
The course list, the step list, the glossary and a lesson's related-lessons list SHALL open a locked lesson or step as a preview, with its status shown in words as "Not started" (never "Locked"). They SHALL NOT show it as unavailable text or leave it out. The "Continue" control after finishing an item SHALL still lead to the next item to do.

#### Scenario: Course list after setup
- **GIVEN** setup has passed
- **WHEN** the participant looks at the course list
- **THEN** every item is a control that opens it, and one that is not yet open is labelled "Not started"

#### Scenario: Glossary link to a locked lesson
- **GIVEN** a glossary entry points to a lesson that is still locked
- **WHEN** the participant opens the entry
- **THEN** a link to the lesson is shown and opens it as a preview

#### Scenario: Continue is unchanged
- **GIVEN** the participant has just finished a step
- **WHEN** the next item is locked by a lesson that is still to do
- **THEN** "Continue" does not open the locked item as if it were next to do

### Requirement: The Track page describes each track by technical level
The Track page SHALL describe the Script track as needing no technical experience, with your AI building the checker and nothing extra to install, and the promptfoo track as for technical users, needing Node.js and about 1 GB of downloads. Neither track SHALL be called the default, recommended or best, and neither SHALL carry a badge or be preselected. The names stay "Script track" and "promptfoo track". Source: series review item 17, AGENTS.md rule 10.

#### Scenario: Script track words
- **WHEN** the participant reads the Script track option
- **THEN** it says no technical experience is needed, that their AI builds the checker, and that nothing extra needs to be installed

#### Scenario: promptfoo track words
- **WHEN** the participant reads the promptfoo track option
- **THEN** it says it is for technical users and needs Node.js and about 1 GB of downloads

#### Scenario: No recommendation
- **WHEN** the content tests scan the Track page, the track messages and the Settings summary
- **THEN** none contains "default", "recommended" or "best" about a track, and neither option is preselected

### Requirement: The project page offers a Practice task or My own task
The project folder page SHALL offer the ready-made example as "Practice task" with a short explanation that everything is provided, so there is nothing to bring, and that it is for practice only. The other option SHALL be "My own task": your own prompt and test cases, which you provide. The note that the Practice task cannot be a submission SHALL stay. Source: series review item 16.

#### Scenario: Practice task words
- **WHEN** the participant reads the project page
- **THEN** the option reads "Practice task", with a ready-made example and practice-only explanation

#### Scenario: My own task words
- **WHEN** the participant reads the other option
- **THEN** it reads "My own task" and says they provide their own prompt and test cases

#### Scenario: Messages agree
- **WHEN** the participant is told that project files are missing
- **THEN** the message names "Practice task" and "My own task", not "Northwind" or "My own files"

### Requirement: The wizard shows the terminal only where the participant must act
The wizard SHALL show the terminal, framed as "your AI window", only on the AI working test page, and on the Choose your AI page while an install is running. It SHALL be beside the page on a wide window and below it on a narrow one. Every other page SHALL NOT show a terminal. Moving between pages SHALL NOT stop a running AI process. Source: series review item 5c.

#### Scenario: Terminal on the test page
- **WHEN** the participant is on the AI working test page
- **THEN** the terminal is shown inside the wizard, framed as "your AI window"

#### Scenario: Terminal during an install
- **GIVEN** the participant chose to install an AI tool
- **WHEN** the install runs
- **THEN** the terminal shows it inside the Choose your AI page

#### Scenario: No terminal elsewhere
- **WHEN** the participant is on the Python, Choose your AI (with no install running), Project folder or Your AI window page
- **THEN** no terminal is shown

#### Scenario: No terminal during the background test
- **GIVEN** the participant pressed "Use this AI" and the background test is running
- **WHEN** the Choose your AI page is shown
- **THEN** no terminal or AI window is shown

#### Scenario: Running AI while moving
- **GIVEN** the participant started their AI on the AI working test page
- **WHEN** the participant moves to the Project folder page
- **THEN** the same AI process is still running

### Requirement: Check everything is offered only where the participant can act on it
The wizard footer SHALL offer "Check everything" only on the Python, Node.js, promptfoo, Choose your AI and Project folder pages, where a participant can fix something outside the app and look again. It SHALL NOT be offered on Track, Checking your computer, AI working test or Your AI window. Its label and its effect (running the applicable checks again) SHALL be unchanged.

#### Scenario: Offered where a check can be fixed outside the app
- **WHEN** the participant is on the Python, Node.js, promptfoo, Choose your AI or Project folder page
- **THEN** the footer offers Check everything and pressing it runs the checks again

#### Scenario: Not offered where it adds nothing
- **WHEN** the participant is on the Track, Checking your computer, AI working test or Your AI window page
- **THEN** the footer shows no Check everything button

### Requirement: Checking your computer runs by itself
The Checking your computer page SHALL start the checks as soon as it is shown, with no Check button needed: Python, for the promptfoo track Node.js and promptfoo (offline only, nothing downloaded), the project folder, and which supported AIs are installed. While it runs it SHALL show progress and SHALL NOT move to another page by itself. When it ends it SHALL show the result of each check in plain words and a Next control that goes to the first page that needs the participant, or to the Your AI window page when every check has passed. Checks SHALL read only files and resolve command names, never terminal text (AGENTS.md rule 3). Source: series review items 5 and 5b.

#### Scenario: Checks start on arrival
- **GIVEN** the participant reaches the Checking your computer page
- **WHEN** the page is shown
- **THEN** the checks start without any button being pressed
- **AND** the page stays until the participant presses Next

#### Scenario: Next goes to what needs the participant
- **GIVEN** the checks ended with Python passed and no AI found
- **WHEN** the participant presses Next
- **THEN** the Choose your AI page is shown

#### Scenario: Everything already passes
- **GIVEN** every check and the working test already passed
- **WHEN** the checks end and the participant presses Next
- **THEN** the Your AI window page is shown

#### Scenario: Nothing is downloaded
- **GIVEN** the promptfoo track is chosen and promptfoo is not installed
- **WHEN** the checks run
- **THEN** the promptfoo check reports that it needs the participant and nothing is downloaded

#### Scenario: Re-running
- **GIVEN** the participant leaves the page and comes back
- **WHEN** the page is shown again
- **THEN** the checks run again

### Requirement: Sign-in and the AI working test are one page
The AI working test page SHALL replace the separate "Sign in and license" page. It is where the participant goes when the background test (see `ai-selection`) did not pass, and it stays reachable with Back and the page list. The participant starts their AI window there, signs in if the AI asks, and presses Send for the test line. When the participant arrives because the background test could not finish, the page SHALL say so in plain words. The app SHALL decide the result from the files in the test folder, never from terminal text. A passing test SHALL count as proof of sign-in, and no "I signed in" confirmation SHALL be asked. While the participant has pressed Send and the AI window is running, the page SHALL re-read the test folder every few seconds and show success when the files are right, without reporting a failure until the participant presses the Check button. When the background test has already passed for the chosen AI, the page counts as passed and is skipped going forward. Source: series review item 5b.

#### Scenario: One page for both
- **WHEN** the participant reaches the working test page
- **THEN** it offers to start the AI window, the test line to send and a Check button
- **AND** it has no separate sign-in confirmation

#### Scenario: Passing the test
- **GIVEN** the participant signed in, sent the test line and the AI wrote the right files
- **WHEN** the test folder is read
- **THEN** the page shows the test passed and Next is enabled

#### Scenario: Not signed in
- **GIVEN** the AI did not write the files because the participant is not signed in
- **WHEN** the participant presses the Check button
- **THEN** the page says the output is missing and that the participant may need to sign in in the AI window, and the test stays not passed

#### Scenario: Quiet re-reading
- **GIVEN** the participant pressed Send and the files are not there yet
- **WHEN** the page re-reads the test folder
- **THEN** no failure message appears until the participant presses the Check button

#### Scenario: Arriving after the quiet test
- **GIVEN** the background test ended as "needs you"
- **WHEN** the wizard shows the AI working test page
- **THEN** a plain line says the quiet test could not finish and that the participant may need to sign in in the AI window

#### Scenario: Skipped after a background pass
- **GIVEN** the background test passed for the chosen AI
- **WHEN** the participant moves forward
- **THEN** the AI working test page is skipped, and it is still reachable with Back and the page list

#### Scenario: The participant sends the line
- **GIVEN** the AI window is running
- **WHEN** the participant has not pressed Send
- **THEN** the app does not send the test line by itself (AGENTS.md rules 2 and 3)
