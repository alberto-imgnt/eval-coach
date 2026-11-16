# setup-banner Specification

## Purpose

Keeps participants who skipped setup aware, at all times and without being blocked, that hands-on exercises need setup, and gives them a one-click way back to it.

## Requirements

### Requirement: Reminder banner while setup is incomplete
While setup has not passed and the participant is not in the setup wizard, the app SHALL show a reminder banner on every screen (lessons, steps, Settings, glossary and reference views). It SHALL say in plain words that hands-on exercises are unavailable until setup is done, and SHALL contain a button that opens setup.

#### Scenario: Banner after skipping
- **GIVEN** the participant skipped setup
- **WHEN** any screen is shown
- **THEN** the banner is visible
- **AND** it states that hands-on exercises need setup

#### Scenario: Going to setup from the banner
- **WHEN** the participant presses the banner's setup button
- **THEN** the setup wizard is shown full page

#### Scenario: No banner in the wizard
- **WHEN** the setup wizard is shown
- **THEN** the banner is not shown

### Requirement: The banner cannot be dismissed and goes away only when setup passes
The banner SHALL have no close or hide control and SHALL stay in view while the content scrolls. It SHALL disappear as soon as setup passes and SHALL NOT return unless the app configuration is reset or a required setup check later fails.

#### Scenario: Scrolling
- **GIVEN** a long lesson is open and the banner is shown
- **WHEN** the participant scrolls the lesson
- **THEN** the banner stays in view

#### Scenario: Setup completed
- **GIVEN** the banner is shown
- **WHEN** setup passes
- **THEN** the banner is gone

### Requirement: Clearly visible but not obtrusive
The banner SHALL be a slim strip at the top of the content area that does not cover lesson text or controls, uses a calm attention color distinct from error styling, takes at most two lines at 100% text size on a desktop, and never opens a dialog or moves focus by itself. It SHALL meet normal text contrast in both themes.

#### Scenario: No overlap
- **WHEN** the banner is shown over a lesson
- **THEN** no lesson text or control is covered by it

#### Scenario: Focus
- **WHEN** the banner appears
- **THEN** keyboard focus does not move to it

### Requirement: The banner adapts to text size and phones
The banner SHALL stay readable and fully visible at every text size and on phones: its text wraps, its button stays reachable and at least 44 pixels high on a phone, and it SHALL NOT take more than a fifth of a 390 pixel wide phone screen's height at 100% text size.

#### Scenario: Largest size
- **GIVEN** the text size is the largest allowed for the device
- **WHEN** the banner is shown
- **THEN** its text and button are fully visible without sideways scrolling

### Requirement: Banner words live in content
All banner text SHALL come from the content files and follow the app's plain-language rules.

#### Scenario: Banned words
- **WHEN** the content tests run
- **THEN** the banner text contains no banned word
