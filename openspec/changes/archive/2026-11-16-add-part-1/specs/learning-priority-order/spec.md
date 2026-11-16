# Spec Delta

## MODIFIED Requirements

### Requirement: Certification content never gates or replaces higher tiers
Stage 3 content SHALL be orientation only. It SHALL NOT block Continue, SHALL NOT replace or delay tier 1 or tier 2 content, SHALL NOT score a submission, and SHALL NOT give submission steps (no links, addresses, upload or form instructions). It SHALL appear only in the last lesson of a Part that carries a note (today `baseline-why` in Part 3 and `p1-benefits` in Part 1).

#### Scenario: Stage 3 reflection is optional
- **WHEN** the participant reaches a Stage 3 reflection or note in a Part's last lesson
- **THEN** it is marked optional
- **AND** the participant can continue without answering it

#### Scenario: Stage 3 stays in one place
- **WHEN** the content tests scan every other lesson, the glossary, the steps and the interface text
- **THEN** none of them names Stage 3 or certification, except the last lesson of a Part that carries a note (today `baseline-why` in Part 3 and `p1-benefits` in Part 1)

#### Scenario: No submission steps
- **WHEN** a Stage 3 note is scanned
- **THEN** it contains no link, address, upload instruction or form instruction

### Requirement: Alignment is guarded by a test
A test SHALL fail when the Part 3 Stage 3 note stops naming the Prompt, the Evaluations and the Log, when the Part 1 note stops naming the Prompt, when Stage 3 wording appears outside a Part's last lesson, or when the plan's Stage 3 alignment map and the notes name different artifacts. Source: plan task 3.40.

#### Scenario: A criterion removed
- **GIVEN** the Part 3 note no longer names the Log
- **WHEN** the content tests run
- **THEN** the guard test fails

#### Scenario: Part 1 note
- **GIVEN** the Part 1 note no longer names the Prompt
- **WHEN** the content tests run
- **THEN** the guard test fails
