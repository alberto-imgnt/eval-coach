# Spec Delta

## MODIFIED Requirements

### Requirement: Setup is a full-page wizard
The setup wizard SHALL fill the whole window with one page per applicable check, in order: Track, Python, Your AI, Sign in and license, AI working test, Project folder (the promptfoo track adds Node and promptfoo pages). While it is open, the course sidebar, course list, tools and reminder banner SHALL NOT be shown. Page titles SHALL follow `participant-vocabulary`.

#### Scenario: Nothing beside the wizard
- **WHEN** the setup wizard is shown
- **THEN** it fills the window
- **AND** no course list, sidebar or reminder banner is shown beside it

#### Scenario: Last page
- **GIVEN** the participant is on the Project folder page and every earlier check has passed
- **WHEN** the participant sets up the project
- **THEN** setup is done and the wizard closes on the first lesson

#### Scenario: Page titles
- **WHEN** the participant reads the wizard's page titles
- **THEN** none says "CLI"

## ADDED Requirements

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
