# Spec Delta

## MODIFIED Requirements

### Requirement: The baseline lesson says Part 6 is live and where to bring ideas
The "Your own work" passage SHALL say that Part 6 is live and that task ideas can be brought to office hours or the AIR discussion (added 2026-11-15). This is the only place in the course that points a participant to people, an exception to AGENTS.md rule 10. It SHALL give no contact details, links, names or schedules and SHALL NOT use the word "session". The Series map's Part 6 row MAY also say, as information only, that Part 6 is a live meeting and what it is about (added 2026-11-15, authorized by the user); it SHALL NOT mention office hours, the AIR discussion, or any person, place, contact detail, link or schedule.

#### Scenario: Part 6 is live
- **WHEN** the participant reads "Your own work"
- **THEN** it says Part 6 is live
- **AND** it says ideas can be brought to office hours or the AIR discussion
- **AND** it says Northwind is practice only

#### Scenario: No other text points to people
- **WHEN** any other lesson, step or interface string, including the Series map's Part 6 row, is scanned
- **THEN** it contains none of the contact-instruction phrases the content tests ban
- **AND** only `baseline-why` contains "office hours" or "AIR discussion"

#### Scenario: Part 6 on the Series map
- **WHEN** the participant reads the Part 6 row of the Series map
- **THEN** it says Part 6 is a live meeting and what it is about, in a few plain words
- **AND** it gives no person, place, contact detail, link or schedule

#### Scenario: No new blocking element
- **WHEN** the baseline lesson is loaded
- **THEN** the number of activities that hold back Continue is unchanged
