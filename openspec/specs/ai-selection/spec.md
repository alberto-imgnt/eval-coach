# ai-selection Specification

## Purpose
How setup finds, offers and installs one of the three supported AI tools, with as few clicks as possible.

## Requirements

### Requirement: The supported AIs are fixed to three
For participants the app SHALL offer exactly three AI tools: GitHub Copilot CLI, Claude Code and Devin CLI. There SHALL be no "Another AI tool" option and no typed command field in the participant interface. The list SHALL come from `cli-recipes.json` data (AGENTS.md rule 6 allows CLI-specific data only there). Source: series review item 9d.

#### Scenario: Three tools only
- **WHEN** the participant reaches the Choose your AI page
- **THEN** only GitHub Copilot CLI, Claude Code and Devin CLI can be chosen
- **AND** there is no "Another AI tool" option and no field to type a command

#### Scenario: Plain-language words
- **WHEN** the participant reads the page
- **THEN** the page says "AI", not "CLI", except in the vendor product names

### Requirement: Installed AIs are found automatically
The checks SHALL find which of the three tools are installed by resolving each tool's launch command from `cli-recipes.json` on this computer, without starting any of them and without reading terminal text. The result SHALL be shown on the Choose your AI page.

#### Scenario: One AI found
- **GIVEN** only Claude Code is installed
- **WHEN** the participant reaches the Choose your AI page
- **THEN** Claude Code is shown as found and is preselected
- **AND** one press of "Use this AI" chooses it

#### Scenario: Several AIs found
- **GIVEN** Claude Code and GitHub Copilot CLI are installed
- **WHEN** the participant reaches the page
- **THEN** both are shown as found and none is preselected
- **AND** the participant picks one and presses "Use this AI"

#### Scenario: Choice is remembered
- **GIVEN** the participant chose an AI and closed the app
- **WHEN** the app opens again and setup is run again
- **THEN** the same AI is still chosen and the Choose your AI check passes if it is still found

#### Scenario: Chosen AI disappears
- **GIVEN** the chosen AI is no longer found
- **WHEN** the checks run
- **THEN** the Choose your AI check fails with a plain message and the page offers the found or installable tools again

### Requirement: None found offers an assisted install
When no supported AI is found, the page SHALL show the three tools and offer to install the one the participant picks. Each tool SHALL be described in plain words with the download size and what it needs (for example, GitHub Copilot CLI needs PowerShell 6 or later, installed first with the option provided). The exact command SHALL be behind a "Show the command" link. Nothing SHALL be installed without the participant's consent, and the install SHALL run in the AI window so the participant can watch and answer what it asks (AGENTS.md rule 5; the app never answers a prompt, rule 2).

#### Scenario: Plain words
- **GIVEN** no supported AI is found
- **WHEN** the participant reads the Claude Code option
- **THEN** it says in plain words what is installed and about how large it is
- **AND** the exact command is not shown until the participant opens "Show the command"

#### Scenario: Show the command
- **WHEN** the participant opens "Show the command"
- **THEN** the exact command that will run is shown

#### Scenario: Consent before install
- **WHEN** the participant presses the install button
- **THEN** a consent step names the tool, the size and the free disk space, and nothing runs until it is confirmed

#### Scenario: Requirement missing
- **GIVEN** PowerShell 6 or later is missing and the participant picked GitHub Copilot CLI
- **WHEN** the page shows that option
- **THEN** it says PowerShell is missing and offers to install it first

#### Scenario: After the install
- **GIVEN** the install finished
- **WHEN** the participant checks again
- **THEN** the new tool is found and the page offers to use it

### Requirement: The typed command route is for tests only
A free-text command route SHALL remain only so the stand-in CLI and tests can run: the server SHALL keep accepting an arbitrary command on the existing preflight CLI route, and the interface SHALL show the typed command field only when the app was started with a test-only flag. The flag SHALL NOT appear in any participant-facing text or setting.

#### Scenario: Default launch
- **WHEN** the app is started normally
- **THEN** no typed command field is shown anywhere

#### Scenario: Test launch
- **GIVEN** the app was started with the test-only flag
- **WHEN** the Choose your AI page is shown
- **THEN** the typed command field and its Check button are available so tests can enter `fake_cli.py`

#### Scenario: Real tools unaffected
- **GIVEN** the app was started with the test-only flag
- **WHEN** a real tool is found
- **THEN** it is still offered like any other

### Requirement: Choosing an AI runs a quiet background test
Pressing "Use this AI" SHALL save the AI and immediately start a test of it in the background, with no further action from the participant. The test SHALL run the tool's one-shot non-interactive mode, using a launch recipe from `cli-recipes.json` and a prompt that needs no file or shell access. It SHALL run with no window, no terminal and no AI window, nothing SHALL be typed into it, no permission flag SHALL be used, and it SHALL NOT answer any prompt (AGENTS.md rules 2 and 4). The result SHALL be decided only from the exit status of the process the app started, never from anything it printed (rule 3). The test SHALL end within a time limit set per tool in `cli-recipes.json`, and the process SHALL be stopped when the limit is reached. The test SHALL never record a failure: it ends as passed or as "needs you".

#### Scenario: Starts at once
- **GIVEN** the participant is on the Choose your AI page with a found tool
- **WHEN** the participant presses "Use this AI"
- **THEN** the AI is saved and the background test starts without another button
- **AND** the page shows that the AI is being tested

#### Scenario: Nothing visible
- **WHEN** the background test runs
- **THEN** no terminal, AI window or other tool interface is shown
- **AND** nothing is typed into the tool and no permission flag is used

#### Scenario: Passes
- **GIVEN** the tool starts, is signed in and replies, and the process ends with exit status 0 within the limit
- **WHEN** the test ends
- **THEN** the AI working test counts as passed for this AI
- **AND** the wizard moves by itself to the next page that still needs the participant

#### Scenario: Needs the participant
- **GIVEN** the process ends with a non-zero status, runs into the time limit, or cannot be started (for example, the participant is not signed in)
- **WHEN** the test ends
- **THEN** the wizard moves by itself to the AI working test page, where the visible AI window is available
- **AND** the page says in plain words that the quiet test could not finish and that the participant may need to sign in, or answer a question, in the AI window
- **AND** no failure is recorded

#### Scenario: Sign-in happens in the AI window
- **GIVEN** the background test ended as "needs you" because the participant is not signed in
- **WHEN** the participant uses the AI working test page
- **THEN** they sign in in the AI window and run the visible test, and the result is decided from the test folder as before

#### Scenario: Tool without one-shot data
- **GIVEN** the chosen command has no one-shot launch data (for example the stand-in)
- **WHEN** the participant presses "Use this AI"
- **THEN** no background test runs and the page stays as it is
- **AND** Next goes to the AI working test page, where the visible AI window is available

#### Scenario: Changed or interrupted
- **GIVEN** a background test is running
- **WHEN** the participant chooses another AI, starts the visible test or starts an install
- **THEN** the running background test is stopped first and only one AI process runs at a time
