# learning-priority-order Specification

## Purpose
Keeps every piece of course content ranked by the project's learning priorities, with core knowledge first, context second and certification last, and keeps the Stage 3 note an orientation that follows the series' Stage 3 structure.

## Requirements

### Requirement: Content is ranked by learning tier
Content decisions SHALL follow the order in `docs/CONTENT-RULES.md` "Learning priorities": tier 1 core knowledge (understand evaluation concepts, run an evaluation, explain both to a technical and a non-technical reader), tier 2 context (the end-to-end workflow and where an evaluation fits), tier 3 certification (how the work lines up with Stage 3). When two items compete for time or screen space the higher tier SHALL win.

#### Scenario: Competing items
- **GIVEN** a lesson has room for one more passage and both a tier 1 and a tier 3 passage are candidates
- **WHEN** the lesson content is decided
- **THEN** the tier 1 passage is kept and the tier 3 passage is shortened or dropped

#### Scenario: Tier 1 outcomes still covered
- **WHEN** the content tests run
- **THEN** the plain-words explanation activities for a non-technical reader and the technical-audience item are still present and unchanged

### Requirement: Certification content never gates or replaces higher tiers
Stage 3 content SHALL be orientation only. It SHALL NOT block Continue, SHALL NOT replace or delay tier 1 or tier 2 content, SHALL NOT score a submission, and SHALL NOT give submission steps (no links, addresses, upload or form instructions). It SHALL appear only in the last lesson of a Part that carries a note (today `baseline-why` in Part 3, `p1-benefits` in Part 1 and `p2-testfile` in Part 2).

#### Scenario: Stage 3 reflection is optional
- **WHEN** the participant reaches a Stage 3 reflection or note in a Part's last lesson
- **THEN** it is marked optional
- **AND** the participant can continue without answering it

#### Scenario: Stage 3 stays in one place
- **WHEN** the content tests scan every other lesson, the glossary, the steps and the interface text
- **THEN** none of them names Stage 3 or certification, except the last lesson of a Part that carries a note (today `baseline-why` in Part 3, `p1-benefits` in Part 1 and `p2-testfile` in Part 2)

#### Scenario: No submission steps
- **WHEN** a Stage 3 note is scanned
- **THEN** it contains no link, address, upload instruction or form instruction

### Requirement: The Stage 3 note follows the Prompt, Evaluations and Log structure
The Stage 3 note SHALL describe Stage 3 as three submitted artifacts: the Prompt, the Evaluations and the Log. For each it SHALL say what the participant already holds after Part 3 and what a later Part adds. Source: the series intent notes (local reference) "How this connects to Stage 3 certification" and the Stage 3 task notes (local reference) sections 4 and 5.

#### Scenario: Three artifacts named
- **WHEN** the participant reads the Stage 3 note
- **THEN** it names the Prompt, the Evaluations and the Log

#### Scenario: What Part 3 produced
- **WHEN** the participant reads the note
- **THEN** it ties the prompt file to the Prompt, the test cases, checker and tested fixtures to the Evaluations, and Iteration 0 to the Log
- **AND** it says the Log needs at least two improvement rounds, which Part 4 adds

#### Scenario: Later Parts named
- **WHEN** the participant reads the note
- **THEN** it says the 95% known-good check and the improvement rounds come in Part 4, and the instruction-by-instruction audit comes in Part 5

### Requirement: The note says the evaluation approach is the participant's choice
The Stage 3 note SHALL say that scripts, promptfoo files and written test cases are all accepted forms of evaluation, so that the Script track and the promptfoo track are shown as two options and not the only ones. It SHALL say that the program's own instructions decide what to submit and that nothing in the note is needed to finish the course, and SHALL NOT carry a publication date for the criteria.

#### Scenario: Not the only options
- **WHEN** the participant reads the note
- **THEN** it says scripts, promptfoo files and written test cases are all accepted

#### Scenario: The program decides
- **WHEN** the participant reads the note
- **THEN** it says the program's own instructions decide what to submit
- **AND** it says nothing there is needed to finish the course

### Requirement: Alignment is guarded by a test
A test SHALL fail when the Part 3 Stage 3 note stops naming the Prompt, the Evaluations and the Log, when the Part 1 note stops naming the Prompt, when the Part 2 note stops naming the Evaluations, when Stage 3 wording appears outside a Part's last lesson, or when the local plan's Stage 3 alignment map (checked only where the plan is present) and the notes name different artifacts. Source: the Stage 3 tier in `docs/CONTENT-RULES.md` "Learning priorities".

#### Scenario: A criterion removed
- **GIVEN** the Part 3 note no longer names the Log
- **WHEN** the content tests run
- **THEN** the guard test fails

#### Scenario: Part 1 note
- **GIVEN** the Part 1 note no longer names the Prompt
- **WHEN** the content tests run
- **THEN** the guard test fails

#### Scenario: Part 2 note
- **GIVEN** the Part 2 note no longer names the Evaluations
- **WHEN** the content tests run
- **THEN** the guard test fails
