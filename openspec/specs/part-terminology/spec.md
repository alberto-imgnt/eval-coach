# part-terminology Specification

## Purpose
Makes the words a participant reads match the series' own naming, so a part of the series is always called a Part and never a session, in lessons, steps, glossary, example files and interface text.

## Requirements

### Requirement: A series part is called a Part
Everything a participant can read SHALL call a part of the series a "Part" (for example "Part 4") and SHALL NOT use the word "session" for it. This covers lesson text, step text, the glossary, the Northwind catch-up files and the interface strings that show the Part number. Source: AGENTS.md rule 10 and `docs/COURSE-CONTEXT.md` "Open items".

#### Scenario: Lesson and step text
- **WHEN** the content tests scan the lessons, steps, glossary and Northwind catch-up files
- **THEN** none of them contains "Session" followed by a number, nor the word "session" meaning a part of the series

#### Scenario: Header
- **WHEN** the app header is shown
- **THEN** its sub-brand reads "Part 3 · Running evals and baseline"

#### Scenario: Course map labels
- **WHEN** the course map is shown
- **THEN** each row title starts with "Part" and its number
- **AND** the screen-reader label reads "You are at Part N of M."

### Requirement: Other meanings of session are left alone
The word "session" SHALL remain where it names something other than a series part: a running CLI session in setup text and code, and the source material's own file names. The rule SHALL NOT change any bundled skill file, which stays byte-identical to its source.

#### Scenario: CLI session wording
- **WHEN** the setup wizard describes a test run of the participant's CLI
- **THEN** the existing wording is unchanged

#### Scenario: Skills untouched
- **WHEN** the content tests compare the bundled skills with their source
- **THEN** they are still byte-identical

### Requirement: Part-number strings come from content
The interface strings that show a Part number (the header sub-brand, the course-map row title and the course-map screen-reader label) SHALL come from content, not from code: from `content/lesson-ui.json` for Part 3 and from the Part's own entry in `content/series.json` for any other Part. The wider interface scope is in `interface-alignment`. Source: AGENTS.md rules 10 and 11 and "every word participants see lives in `content/*.json`".

#### Scenario: Strings in content
- **WHEN** the content tests scan `web/js`
- **THEN** none of `views.js`, `markdown.js`, `part-steps.js` or `criteria-steps.js` contains the words "Session" or a hard-coded Part title, and the strings are read from the interface text

#### Scenario: Header in Part 1
- **WHEN** the participant is inside Part 1
- **THEN** the sub-brand reads "Part 1 · Structured prompting"

#### Scenario: Header in Part 2
- **WHEN** the participant is inside Part 2
- **THEN** the sub-brand reads "Part 2 · Defining evaluation criteria"
