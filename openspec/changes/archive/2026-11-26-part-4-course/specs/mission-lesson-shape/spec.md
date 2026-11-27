# Spec Delta

## MODIFIED Requirements

### Requirement: Every mission lesson has the same four passages
Each Part's mission lesson (`mission`, `p1-mission`, `p2-mission`, `p4-mission`) SHALL be one page with no activities and no review questions, with four labelled passages in this order: "The goal", "Why it matters to you", "What you will do" and "What you leave with". Each passage SHALL be specific to its Part. Source: series review item 13.

#### Scenario: Same order in every Part
- **WHEN** the content tests read each mission lesson body
- **THEN** each holds the four passages in that order, and no mission holds a fifth labelled passage except the series passage of Part 1

#### Scenario: Specific to the Part
- **WHEN** the participant reads "Why it matters to you" in Part 2 and in Part 3
- **THEN** the two passages differ and each says why that Part's work matters for the participant's own use of AI

#### Scenario: What you leave with
- **WHEN** the participant reads "What you leave with"
- **THEN** it names what they will hold when the Part is done (for example a saved prompt, a test case file, or a recorded baseline) in plain words
