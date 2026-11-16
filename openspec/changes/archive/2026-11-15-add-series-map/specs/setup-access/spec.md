# Spec Delta

## MODIFIED Requirements

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
