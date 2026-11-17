# ai-window-lesson Specification

## Purpose

A short, untracked mini lesson that tells the participant what they are looking at in the AI window.

## ADDED Requirements

### Requirement: The wizard ends with a mini lesson about the AI window
The setup wizard SHALL have a last page, "Your AI window", after the Project folder page. It SHALL show the annotated screenshot for the AI the participant chose, a short intro and the legend. It SHALL NOT count as a lesson, a step or progress, SHALL NOT be a check, and SHALL NOT gate setup. Finishing it closes the wizard on the first lesson. Source: series review item 9.

#### Scenario: Last page
- **GIVEN** the participant set up the project
- **WHEN** the wizard moves on
- **THEN** the Your AI window page is shown with the chosen tool's annotated screenshot

#### Scenario: Not tracked
- **WHEN** the participant finishes or leaves the page
- **THEN** no progress, step or lesson status changes and nothing is added to `progress.json`

#### Scenario: Setup passes without it
- **GIVEN** every check has passed and the participant left the wizard before the last page
- **WHEN** the app reads setup status
- **THEN** setup has passed

### Requirement: One annotated screenshot per tool
There SHALL be one screenshot per supported tool (GitHub Copilot CLI, Claude Code, Devin CLI), each captured from the AI window of this app so it matches what the participant sees. Numbers SHALL be overlaid on the image as real elements, not drawn into it, with a text legend, a description available on hover and on keyboard focus, and real alt text. Any account name or email in a screenshot SHALL be masked before it is stored. Source: series review item 9c.

#### Scenario: Matches the chosen tool
- **GIVEN** the participant chose Claude Code
- **WHEN** the Your AI window page is shown
- **THEN** the Claude Code screenshot is shown, not another tool's

#### Scenario: Numbers and legend
- **WHEN** the participant reads the page
- **THEN** numbered markers sit over the image and a legend lists each number with its plain-words meaning

#### Scenario: Hover and focus
- **WHEN** the participant hovers over or tabs to a marker
- **THEN** its description is shown

#### Scenario: Accessible
- **WHEN** the screenshot is read by a screen reader
- **THEN** it has alt text, and the legend gives every number's meaning as text

#### Scenario: Nothing personal
- **WHEN** the content tests scan the screenshot data files
- **THEN** no account name or email is present

#### Scenario: No screenshot for a test command
- **GIVEN** the chosen command is the test-only stand-in
- **WHEN** the page is shown
- **THEN** it shows the legend text without a screenshot

### Requirement: The lesson can be reopened
The lesson SHALL be reopenable from the Settings setup group and from the AI window ("What am I looking at?"), showing the same content in a dialog that closes back to where the participant was. Reopening it SHALL NOT stop a running AI process or change progress.

#### Scenario: From Settings
- **WHEN** the participant presses "What am I looking at?" in Settings
- **THEN** the lesson is shown in a dialog and closing it returns to Settings

#### Scenario: From the AI window
- **GIVEN** an AI window is shown in a lesson or step
- **WHEN** the participant presses "What am I looking at?"
- **THEN** the lesson is shown and the AI process keeps running

#### Scenario: Words from content
- **WHEN** the lesson text is edited in its content file
- **THEN** the wizard page and the dialog show the edited text
