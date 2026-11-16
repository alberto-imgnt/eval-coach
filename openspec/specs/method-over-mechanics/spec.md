# method-over-mechanics Specification

## Purpose
Keeps the course teaching the transferable method of judging AI work (tier 1) ahead of this series' own mechanics, and keeps those mechanics from reading as the recommended or only correct way to evaluate.

## Requirements

### Requirement: Each lesson leads with the transferable idea
Every lesson SHALL open its teaching with the idea a participant can take to any task, in tool-neutral plain words, before it describes how this course does the work. Source: `docs/SERIES-INTENT.md` "What to keep in mind" and the plan's tier 1.

#### Scenario: Idea first
- **WHEN** the participant reads a lesson that also describes this course's mechanics
- **THEN** the transferable idea appears before the mechanics
- **AND** the idea is stated without naming a file, command, folder or tool

### Requirement: This course's mechanics are labelled as this course's choices
Where a lesson describes a series-specific practice or artifact (five runs, a blind folder, the generator and builder roles, verdict lines, the checker file layout, exit codes, the four fixture steps, the answer-key timing, the skill file, file names), it SHALL introduce it under the label "How this course does it". Each such lesson SHALL say once that other approaches exist and that Stage 3 accepts scripts, promptfoo files and written test cases. Source: `docs/STAGE3-TASK-SPEC.md` section 2.

#### Scenario: Labelled mechanics
- **WHEN** the participant opens a lesson that still mentions a course-specific practice
- **THEN** the lesson marks it under "How this course does it"

#### Scenario: Steps carry the procedure
- **WHEN** the participant opens a step
- **THEN** the step's text states the procedure of this course, and the first step says once that it is this course's way of working

#### Scenario: Not the only way
- **WHEN** the participant reads a labelled passage
- **THEN** it says this is one way of working and that other approaches are accepted

### Requirement: Course mechanics never read as the one correct approach
Participant-facing text SHALL NOT describe a course-specific practice as the right, only, correct, proper or standard way, and SHALL NOT use "must" or "always" for one. A practice that exists for a reason SHALL give the reason in a clause (for example "so the model cannot read the tests") and not as a rule.

#### Scenario: Absolutes
- **WHEN** the content tests scan lessons, steps and the glossary
- **THEN** none of them contains "the right way", "the only way", "the correct way", "the proper way", "the standard way" or "this is how it is done"

#### Scenario: A reason, not a rule
- **WHEN** a lesson explains why the runs are separate, blind or counted as five
- **THEN** it gives the reason in plain words and says five is what this course uses and what Stage 3 asks for a baseline

### Requirement: True principles stay firm, with their reason
Three principles SHALL stay unconditional and SHALL each carry a one-clause reason: never edit the checker to make a failing answer pass, never hide a rule that could not be checked (it stays NOT CHECKED and visible), and write predictions before running the checker. Source: `docs/STAGE3-TASK-SPEC.md` sections 2 and 3, `docs/SERIES-INTENT.md` "What to keep in mind".

#### Scenario: Principle with reason
- **WHEN** the participant reads the lesson on surprises
- **THEN** it says never to edit the checker to make a failing answer pass, with the reason that a failing result is the information

### Requirement: Process-only topics are short and never tested in a lesson
Topics that matter only to this course's mechanics (the two roles, exit codes, the layout of the checker file, the answer-key timing, the order of the fixture steps) SHALL take no more than 60 words each in a lesson, and each lesson's "How this course does it" passages together SHALL take no more than 120 words. No lesson activity or review question SHALL test only such a mechanic. See `course-structure` for the activities removed.

#### Scenario: Word budget
- **WHEN** the content tests measure a labelled passage
- **THEN** no process-only topic exceeds 60 words and no lesson's labelled passages exceed 120 words together

#### Scenario: No mechanics-only question
- **WHEN** the content tests list every lesson activity and review question
- **THEN** none asks only for the order of steps, the roles, an exit code or the layout of a file

### Requirement: Glossary separates ideas from this course's terms
Glossary entries for course-specific terms (blind folder, generator, builder, verdict, first look, known-good output, run, fixtures folder, file names, check.py or promptfooconfig.yaml, agent skill) SHALL begin "In this course," and SHALL say what the idea behind the term is. Entries for general ideas (criterion, threshold, NOT CHECKED, deterministic, proxy, baseline) SHALL stay tool-neutral.

#### Scenario: Course terms marked
- **WHEN** the participant opens the glossary
- **THEN** each course-specific term's meaning begins with "In this course,"

### Requirement: The Stage 3 note does not present course files as the required format
The Stage 3 note SHALL say that file names and layout used in this course are this course's and that Stage 3 asks for three artifacts: the Prompt, the Evaluations and the Log. Source: `docs/STAGE3-TASK-SPEC.md` section 4 ("The layout is a suggestion").

#### Scenario: Layout is not a requirement
- **WHEN** the participant reads the Stage 3 note
- **THEN** it says the file layout in this course is one way to organize the work
