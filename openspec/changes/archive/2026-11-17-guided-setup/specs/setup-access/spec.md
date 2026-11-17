# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: The wizard keeps the terminal and the CLI working
**Reason**: Replaced by "The wizard shows the terminal only where the participant must act". The terminal is no longer shown on every page that uses the AI, and the separate sign-in page is gone.
**Migration**: None. The rule that moving between pages keeps a running AI process alive moves into the new requirement.
