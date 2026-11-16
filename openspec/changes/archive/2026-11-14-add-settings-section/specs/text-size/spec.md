## Purpose

Lets a participant scale all app text with a slider, with values suited to the device, and keeps the layout comfortable at every size.

## ADDED Requirements

### Requirement: Text size slider
Settings SHALL offer a slider that sets the app text size in steps of 5%, with 100% as the default. It SHALL show its current value as a percentage, work by keyboard and by touch, and have a control that returns it to 100%. On a desktop the range SHALL be 80% to 150%.

#### Scenario: First visit
- **GIVEN** the participant has never chosen a text size
- **WHEN** Settings is opened
- **THEN** the slider shows 100%

#### Scenario: Desktop limits
- **GIVEN** a desktop browser
- **WHEN** the participant drags the slider to either end
- **THEN** the value is 80% or 150% and cannot go beyond

#### Scenario: Back to default
- **GIVEN** the slider is at 125%
- **WHEN** the participant uses the control that returns to 100%
- **THEN** the slider and the app text return to 100%

### Requirement: Phone values
When a phone is detected, the slider SHALL use a range suited to phones, 90% to 130%, and the default SHALL stay 100%. A phone is a touch device whose shorter screen side is 600 pixels or less. A narrow desktop window SHALL NOT count as a phone.

#### Scenario: Phone limits
- **GIVEN** a phone is detected
- **WHEN** the participant drags the slider to either end
- **THEN** the value is 90% or 130% and cannot go beyond

#### Scenario: Narrow desktop window
- **GIVEN** a desktop browser window 390 pixels wide
- **WHEN** Settings is opened
- **THEN** the desktop range 80% to 150% is offered

### Requirement: Text size applies live to the whole app
Moving the slider SHALL change all app text, including lessons, steps, the sidebar, dialogs and the terminal, as it moves and without a page reload.

#### Scenario: Choosing 125%
- **WHEN** the participant sets the slider to 125%
- **THEN** body text, headings, controls and terminal text all become larger straight away
- **AND** no page reload happens

#### Scenario: Terminal keeps working
- **GIVEN** a CLI is running in the terminal
- **WHEN** the participant changes the text size
- **THEN** the terminal text changes size and the terminal refits its box
- **AND** the CLI session is not interrupted

### Requirement: Layout adapts to the text size
At every size in the active range, every screen SHALL stay usable: no sideways scrolling of the page, no overlapping or cut-off text or controls, and every button reachable. This SHALL hold on a 1280 pixel wide desktop window and on a 390 pixel wide phone. When a size no longer fits the current layout, the layout SHALL switch to its next more compact form instead of squeezing content.

#### Scenario: Largest size on desktop
- **GIVEN** a 1280 pixel wide desktop window
- **WHEN** the text size is 150%
- **THEN** every screen can be read and operated without sideways scrolling
- **AND** the layout has switched to a more compact form where needed

#### Scenario: Largest size on a phone
- **GIVEN** a 390 pixel wide phone
- **WHEN** the text size is 130%
- **THEN** every screen can be read and operated by scrolling down only

#### Scenario: Default look unchanged
- **WHEN** the text size is 100% on a wide window
- **THEN** the layout is the same as before this change

### Requirement: Text size is remembered in this browser only
The chosen size SHALL be stored in the browser with the theme and sidebar choices. It SHALL NOT be sent to the server or written to `progress.json`, and SHALL be applied before the page first paints.

#### Scenario: Remembered after reload
- **GIVEN** the participant chose 130%
- **WHEN** the app is reloaded
- **THEN** 130% is applied before the first paint
- **AND** no flash of 100% appears

#### Scenario: Browser storage is blocked
- **GIVEN** the browser blocks local storage
- **WHEN** the participant moves the slider
- **THEN** the size applies until the page reloads
- **AND** no error is shown

### Requirement: Bad stored values are handled
If the stored text size is not a number, the app SHALL use 100%. If it is a number outside the active range, the app SHALL use the nearest limit of that range.

#### Scenario: Corrupt value
- **GIVEN** the stored text size is "abc"
- **WHEN** the app loads
- **THEN** 100% is applied

#### Scenario: Out of range on a phone
- **GIVEN** a phone is detected and the stored text size is 150
- **WHEN** the app loads
- **THEN** 130% is applied
