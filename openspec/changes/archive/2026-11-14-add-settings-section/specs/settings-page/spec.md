## Purpose

Defines the Settings entry and panel: where it is, what it shows, and how it behaves on desktop and on phones.

## ADDED Requirements

### Requirement: Settings entry sits before Quit
The sidebar's tool list SHALL contain a Settings entry placed directly before the Quit entry, with the same look and behavior as the other tools. When the sidebar is collapsed to icons or laid out as a top bar on narrow screens, Settings SHALL stay directly before Quit and keep its name available to screen readers.

#### Scenario: Position in the tool list
- **WHEN** the sidebar is shown
- **THEN** Settings appears immediately before Quit

#### Scenario: Collapsed or narrow layout
- **GIVEN** the sidebar is collapsed, or the window is narrow
- **WHEN** the tool list is shown
- **THEN** Settings is still immediately before Quit
- **AND** it is reachable by keyboard and has an accessible name

### Requirement: Selecting Settings shows the Settings panel
Selecting Settings SHALL show a Settings panel containing every option at once, with no tabs or hidden sections, in this order: text size, setup (a status summary and an "Open setup" button), then reset with its two actions (reset lesson progress and reset app configuration).

#### Scenario: Panel contents
- **WHEN** the participant selects Settings
- **THEN** the panel shows the text size control, the setup summary with its button and both reset actions
- **AND** they appear in that order

### Requirement: Settings is reachable at any time
The participant SHALL be able to open Settings from any screen of the course, including on first run after skipping setup and while a step or lesson is in progress. The only exception is the full-page setup wizard, which has no tools; closing it returns to where the participant was.

#### Scenario: Opening Settings before setup passes
- **GIVEN** setup has been skipped and has not passed
- **WHEN** the participant opens Settings
- **THEN** the Settings panel is shown
- **AND** course items that are locked stay locked

#### Scenario: Leaving Settings
- **WHEN** the participant leaves Settings
- **THEN** the screen they were on before, or the current course item, is shown

### Requirement: Settings does not disturb the course
Opening Settings or changing the text size SHALL NOT change progress, lock or unlock a course item, or start or stop a CLI process.

#### Scenario: Changing text size mid-step
- **GIVEN** a CLI process is running for a step
- **WHEN** the participant opens Settings and moves the text size slider
- **THEN** the CLI process keeps running
- **AND** progress is unchanged

### Requirement: Settings works on phones
On a phone, Settings SHALL be fully usable at 390 pixels wide: every control reachable by scrolling down only, no sideways scrolling, no cut-off text, and touch targets at least 44 pixels high. The desktop layout SHALL NOT be reduced to fit phones.

#### Scenario: Phone
- **GIVEN** a phone-sized touch screen
- **WHEN** the Settings panel is open
- **THEN** all options can be reached by scrolling down only
- **AND** the page does not scroll sideways

### Requirement: Settings words live in content
All text shown in Settings SHALL come from the content files, not from code, and SHALL follow the app's plain-language rules (the word "Part", no presenter or classroom words, "Script track" and "promptfoo track").

#### Scenario: Banned words
- **WHEN** the content tests run
- **THEN** no Settings text contains a banned word
