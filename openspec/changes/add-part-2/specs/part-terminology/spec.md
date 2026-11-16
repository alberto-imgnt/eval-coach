# Spec Delta

## MODIFIED Requirements

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
