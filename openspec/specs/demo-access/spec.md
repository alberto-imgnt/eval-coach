# demo-access Specification

## Purpose

Gives the maintainer a hidden, password-protected way to open any Part for a demo or a test, for the current run only. It is a deterrent against casual use, not a security feature. Source: series review items 1 and 1e, decisions O3.

## Requirements

### Requirement: Demo access is revealed by clicking the app version five times
Settings SHALL show the app version. Selecting it five times in a row (by mouse, or by Enter or Space) SHALL reveal a demo access group with a password box. Nothing else in the app, in its words or in its help SHALL mention demo access before then.

#### Scenario: Five selections
- **WHEN** the participant selects the version line five times in a row in Settings
- **THEN** a demo access group with a password box appears

#### Scenario: Fewer than five
- **WHEN** the participant selects the version line four times and then leaves Settings
- **THEN** nothing is revealed

#### Scenario: No early mention
- **WHEN** the content tests scan every participant-visible text
- **THEN** none mentions demo access before the group is revealed, except the group's own words

### Requirement: The right password opens every Part, one item at a time
Entering the right password SHALL turn demo access on. While it is on, every Part with content SHALL open as if the Parts before it were Done or Skipped, so any Part can be started. Inside a Part the order SHALL stay strict: items are read and done one after another, with no reading ahead. It SHALL NOT mark any Part Done or Skipped, SHALL NOT change the setup rules, and SHALL NOT open the sealed answer key (AGENTS.md rule 9). What the participant does while it is on is saved like any other work.

#### Scenario: Opening Part 3 directly
- **GIVEN** nothing is done in Parts 1 and 2 and demo access is on
- **WHEN** the participant opens Part 3
- **THEN** it opens at its first item, and its later items are still locked

#### Scenario: Order inside a Part
- **GIVEN** demo access is on
- **WHEN** the participant tries a later item of a Part before the one before it is done
- **THEN** it is locked, as for any participant

#### Scenario: Setup and the key
- **GIVEN** demo access is on and setup has not passed, or predictions are not locked
- **WHEN** the participant tries hands-on work, or asks for the answer key
- **THEN** they are refused as for any participant

#### Scenario: Turning it off
- **GIVEN** demo access is on and Part 3 was started with Parts 1 and 2 untouched
- **WHEN** the participant turns demo access off
- **THEN** Part 3 is locked again by the normal rule, and nothing they saved there is deleted

### Requirement: A wrong password changes nothing
A wrong or empty password SHALL leave demo access off, say in plain words that the password was not accepted, and give no hint. It SHALL NOT show whether demo access exists in this build.

#### Scenario: Wrong password
- **WHEN** the participant enters a wrong password
- **THEN** demo access stays off and a plain message says the password was not accepted

### Requirement: Demo access lasts only for the current run
Demo access SHALL be held only while the app is running. Closing the app, or quitting it, SHALL turn it off, and it SHALL NOT be written to `progress.json`, the settings file or any other file. Reloading the page SHALL keep it on. "Reset lesson progress" and "Reset app configuration" SHALL NOT change it.

#### Scenario: Close and reopen
- **GIVEN** demo access is on
- **WHEN** the app is closed and opened again
- **THEN** demo access is off and the locks apply

#### Scenario: Reload
- **GIVEN** demo access is on
- **WHEN** the page is reloaded
- **THEN** demo access is still on

#### Scenario: Nothing stored
- **WHEN** demo access has been on and the project files are read
- **THEN** none records that it was on

### Requirement: A visible notice shows while demo access is on
While demo access is on, a notice SHALL show on the Series map, inside every Part and in Settings, saying that demo access is on, that every Part is open and that what is done is saved. Settings SHALL offer "Turn off demo access". The notice SHALL be read by a screen reader and SHALL NOT take focus.

#### Scenario: Notice on every screen
- **GIVEN** demo access is on
- **WHEN** the participant moves between the Series map, a Part and Settings
- **THEN** the notice is shown on each

#### Scenario: Turning off
- **WHEN** the participant selects "Turn off demo access"
- **THEN** the notice goes and the locks apply again

### Requirement: The password is checked against a salted hash kept in the app
The app SHALL check the password against a salted, slow hash shipped inside the app, compared in constant time. The password itself SHALL NOT appear in the repository, specs, tests, docs, logs or the shipped app. A small tool SHALL create the hash from a password typed at a prompt, and tests SHALL inject their own hash. When no hash is shipped, demo access SHALL be unavailable and the version line SHALL do nothing. Source: series review item 1e.

#### Scenario: The tool
- **WHEN** the maintainer runs the tool and types a password
- **THEN** it writes a salt and a hash, never the password

#### Scenario: Tests use their own hash
- **WHEN** a test turns demo access on
- **THEN** it does so with a hash the test supplied, not the shipped one

#### Scenario: No hash shipped
- **GIVEN** the app has no hash file
- **WHEN** the participant selects the version line five times
- **THEN** nothing is revealed
