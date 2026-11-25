# Spec Delta

## MODIFIED Requirements

### Requirement: The Stage 3 note follows the Prompt, Evaluations and Log structure
The Stage 3 note SHALL describe Stage 3 as three submitted artifacts: the Prompt, the Evaluations and the Log. For each it SHALL say what the participant already holds after Part 3 and what a later Part adds. Source: the series intent notes (local reference) "How this connects to Stage 3 certification" and the Stage 3 task notes (local reference) sections 4 and 5.

#### Scenario: Three artifacts named
- **WHEN** the participant reads the Stage 3 note
- **THEN** it names the Prompt, the Evaluations and the Log

#### Scenario: What Part 3 produced
- **WHEN** the participant reads the note
- **THEN** it ties the prompt file to the Prompt, the test cases, checker and tested fixtures to the Evaluations, and Iteration 0 to the Log
- **AND** it says Stage 3 asks for at least two documented iterations, and that this course has the participant log two improvement rounds after Iteration 0, which Part 4 adds
- **AND** it says Iteration 0 is the starting point and not one of those two rounds

#### Scenario: Later Parts named
- **WHEN** the participant reads the note
- **THEN** it says the known-good check of the checker and the improvement rounds come in Part 4, and the instruction-by-instruction audit comes in Part 5
- **AND** it names the 95% known-good check, the five-answer coaching target and the 90% load-bearing audit as separate things

## ADDED Requirements

### Requirement: Every Stage 3 criterion maps to an exercise and its evidence
`docs/CONTENT-RULES.md` SHALL hold a traceability map with one row per examiner criterion for the Prompt, the Evaluations and the Log. Each row SHALL name the hands-on exercise (Part and step) that teaches it, the evidence the exercise produces, and whether the row is an examiner requirement or a course convention. A row SHALL be marked an examiner requirement only after it was checked against the official program wording, and the map SHALL record when and from what it was checked.

#### Scenario: Every criterion has a row
- **WHEN** the content tests read the map
- **THEN** each of the Prompt, Evaluations and Log has at least one row and no row is without an exercise and an evidence entry

#### Scenario: Stricter than the program
- **GIVEN** the course asks for more than the program page states, such as two rounds after Iteration 0 where the page says at least two documented iterations
- **WHEN** the map lists that row
- **THEN** it marks the course's figure as a convention and names the program's own figure beside it

#### Scenario: Conventions are not requirements
- **WHEN** the map lists a course choice such as the file layout, the five answers, the Script track or the 95% known-good figure
- **THEN** the row says it is a course convention unless the official wording was checked and says otherwise

### Requirement: Certification orientation stays in the closing lessons
Content that orients a participant to Stage 3 SHALL stay optional and in the last lesson of a Part, as `Certification content never gates or replaces higher tiers` already says. The traceability map is for contributors and SHALL NOT appear in any participant-facing text.

#### Scenario: Map not shown to participants
- **WHEN** the content tests scan lessons, steps, the glossary and interface strings
- **THEN** none contains the traceability map or its row labels
