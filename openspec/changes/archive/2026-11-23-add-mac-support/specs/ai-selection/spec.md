# Spec Delta

## MODIFIED Requirements

### Requirement: None found offers an assisted install
When no supported AI is found, the page SHALL show the three tools and offer to install the one the participant picks. Each tool SHALL be described in plain words with the download size and what it needs (for example, on Windows GitHub Copilot CLI needs PowerShell 6 or later, installed first with the option provided). The install option, its command and its requirements SHALL be those of the computer the app runs on (Windows or Mac). The exact command SHALL be behind a "Show the command" link. Nothing SHALL be installed without the participant's consent, and the install SHALL run in the AI window so the participant can watch and answer what it asks (AGENTS.md rule 5; the app never answers a prompt, rule 2).

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
- **GIVEN** PowerShell 6 or later is missing on Windows and the participant picked GitHub Copilot CLI
- **WHEN** the page shows that option
- **THEN** it says PowerShell is missing and offers to install it first

#### Scenario: After the install
- **GIVEN** the install finished
- **WHEN** the participant checks again
- **THEN** the new tool is found and the page offers to use it

#### Scenario: Install options on a Mac
- **GIVEN** the app runs on a Mac and no supported AI is found
- **WHEN** the participant reads the page
- **THEN** each tool shows its Mac install option, its size and its "Show the command" link
- **AND** no option mentions winget, PowerShell or an `.exe`
