# Spec Delta

## MODIFIED Requirements

### Requirement: Selecting Settings shows the Settings panel
Selecting Settings SHALL show a Settings panel containing every option at once, with no tabs or hidden sections, in this order: text size, setup (a status summary, an "Open setup" button and a "What am I looking at?" button), then reset with its two actions (reset lesson progress and reset app configuration), then the app version line. The version line is the entry to the hidden demo access group described in `demo-access`, which appears after the version line only once revealed.

#### Scenario: Panel contents
- **WHEN** the participant selects Settings
- **THEN** the panel shows the text size control, the setup summary with its two buttons, both reset actions and the app version, and no demo access group
- **AND** they appear in that order

#### Scenario: Summary matches the wizard
- **WHEN** the participant reads the setup summary
- **THEN** it lists the same checks as the wizard (Python, Node.js and promptfoo on the promptfoo track, your AI, the AI working test, the project folder) and no separate sign-in line

#### Scenario: Version line
- **WHEN** the participant reads the end of the Settings panel
- **THEN** it shows the app version in plain words, for example "Version 0.1.0"
