# mission-lesson-shape Specification

## Purpose

Gives every Part's mission lesson the same short shape (goal, why it matters to you, what you will do, what you leave with) so a participant knows what a Part is for in a minute, without a repeated series pitch or a map of the series.

## Requirements

### Requirement: Every mission lesson has the same four passages
Each Part's mission lesson (`mission`, `p1-mission`, `p2-mission`) SHALL be one page with no activities and no review questions, with four labelled passages in this order: "The goal", "Why it matters to you", "What you will do" and "What you leave with". Each passage SHALL be specific to its Part. Source: series review item 13.

#### Scenario: Same order in every Part
- **WHEN** the content tests read each mission lesson body
- **THEN** each holds the four passages in that order, and no mission holds a fifth labelled passage except the series passage of Part 1

#### Scenario: Specific to the Part
- **WHEN** the participant reads "Why it matters to you" in Part 2 and in Part 3
- **THEN** the two passages differ and each says why that Part's work matters for the participant's own use of AI

#### Scenario: What you leave with
- **WHEN** the participant reads "What you leave with"
- **THEN** it names what they will hold when the Part is done (for example a saved prompt, a test case file, or a recorded baseline) in plain words

### Requirement: The series framing appears once, in Part 1
The series-level framing (the series teaches judging AI work and trusting it because it was checked, the three reasons checking matters, and the method) SHALL appear in Part 1's mission only, as one labelled passage before "The goal". The missions of Parts 2 and 3 SHALL NOT repeat it. Source: series review item 13.

#### Scenario: Part 1 carries it
- **WHEN** the participant opens `p1-mission`
- **THEN** a series passage says the series teaches judging AI work, that trust comes from checking, that neither blind trust nor blind distrust is asked for, and gives the three reasons and the method

#### Scenario: Other missions do not repeat it
- **WHEN** the content tests scan `p2-mission` and `mission`
- **THEN** neither contains the sentence "AI sounds sure of itself" or the three-reason list

#### Scenario: Later Parts link back
- **WHEN** the participant reads the mission of Part 2 or Part 3
- **THEN** its goal passage may point back to the previous Part's result in one sentence

### Requirement: No mission lesson shows a map of the series
No mission lesson SHALL contain a "you are here" map or any list of all six Parts. The Series map is the only place that lists the Parts. Source: series review item 12.

#### Scenario: Map removed
- **WHEN** the content tests scan the mission lesson bodies
- **THEN** none contains a `you-are-here` block or a numbered list of the six Part names

#### Scenario: Series map unchanged
- **WHEN** the participant opens the Series map
- **THEN** it still lists all six Parts with their states

### Requirement: Mission lessons keep their length and their plain words
Each mission lesson body SHALL stay within the word cap in `course-structure` and SHALL follow the app's plain-language rules (AGENTS.md rule 10). Each SHALL say the Practice task is for practice only where it names it. Source: `course-structure`, AGENTS.md rules 7 and 10.

#### Scenario: Word cap
- **WHEN** the content tests count each mission body
- **THEN** none exceeds 450 words

#### Scenario: Practice only
- **WHEN** a mission names the Practice task
- **THEN** it says the task is a ready-made example for practice and is never something to submit
