# Spec Delta

## Purpose

Makes the course say what the whole series is for, why checking AI work matters, what a score can and cannot tell you, and where the method applies next, so Part 3 reads as one step of the series and not as a stand-alone tool.

## ADDED Requirements

### Requirement: The mission states the series purpose
The mission lesson SHALL state, in plain words, that the series teaches participants to judge the work AI gives them and to trust it because it was checked, not because it looked right. It SHALL say the series is not asking for blind trust or blind distrust. Source: `docs/SERIES-INTENT.md` "Intent".

#### Scenario: Purpose on the mission page
- **WHEN** the participant opens the mission lesson
- **THEN** the text says the goal is to judge AI work and trust it for the right reasons
- **AND** it says trust comes from checking, and that neither blind trust nor blind distrust is asked for

#### Scenario: Mission stays one page with no questions
- **WHEN** the mission lesson is loaded
- **THEN** it has no activities and no review questions
- **AND** its stated mission sentence is unchanged apart from "Part 2" replacing "Session 2"

### Requirement: The mission says why checking AI work matters
The mission lesson SHALL give a short "why it matters" covering three reasons: AI sounds sure of itself even when it is wrong, "better" is an opinion until it is measured, and answers change from one try to the next. Source: `docs/SERIES-INTENT.md` "Why it matters".

#### Scenario: The three reasons
- **WHEN** the participant reads the mission lesson
- **THEN** each of the three reasons is stated in plain words with no code

### Requirement: The course map uses the series' Part names
The course map in the mission lesson SHALL list all six Parts with the names used in the series intent (structured prompting, defining evaluation criteria, running evals and baseline, iterating with evaluation-driven development, load-bearing audit and packaging, your own task). Each row SHALL carry a one-line plain description in the participant's words, and exactly one row SHALL be marked as the current Part.

#### Scenario: Six rows, one current
- **WHEN** the course map is shown
- **THEN** it has six rows numbered 1 to 6
- **AND** Parts 1 and 2 are marked done, Part 3 is marked as where the participant is, and Parts 4 to 6 are marked next

#### Scenario: Wider series stays plain
- **WHEN** a row describes Part 4, 5 or 6
- **THEN** it says what the participant will be able to do, not what the app does

### Requirement: The baseline lesson says what a score does and does not tell you
The baseline lesson SHALL say that a score describes how one prompt did against one set of rules and does not guarantee every future answer, and that a rule that cannot judge something is marked NOT CHECKED instead of pretending. Source: `docs/SERIES-INTENT.md` "What to keep in mind".

#### Scenario: Limits stated
- **WHEN** the participant reads the baseline lesson
- **THEN** it says a good score is not a guarantee of future answers
- **AND** it says a rule that cannot judge a quality is reported as not checked

### Requirement: The baseline lesson says how a baseline is used next
The baseline lesson SHALL say that in Part 4 the participant changes the prompt, checks again with the same rules and compares, and that if the score did not move the change did not help. It SHALL keep what it already says about Parts 4 and 5.

#### Scenario: Score did not move
- **WHEN** the participant reads what comes next
- **THEN** the lesson says a change that does not move the score did not help

### Requirement: The baseline lesson points the method at the participant's own work
The baseline lesson SHALL name three kinds of everyday work the same method applies to (for example a message after a client call, a summary of a long thread, a job description) and SHALL say the participant picks a task of their own in Part 6 that repeats, has clear requirements and can be checked by rules. It SHALL say the Northwind update is practice only. The passage SHALL NOT add an activity and SHALL NOT block Continue.

#### Scenario: Own task fit
- **WHEN** the participant reads the baseline lesson
- **THEN** it names three kinds of repeating work
- **AND** it states the three things a task needs in order to fit

#### Scenario: No new blocking element
- **WHEN** the baseline lesson is loaded
- **THEN** the number of activities that hold back Continue is unchanged

### Requirement: The baseline lesson says Part 6 is live and where to bring ideas
The "Your own work" passage SHALL say that Part 6 is live and that task ideas can be brought to office hours or the AIR discussion (added 2026-11-15). This is the only place in the course that points a participant to people, an exception to AGENTS.md rule 10. It SHALL give no contact details, links, names or schedules and SHALL NOT use the word "session".

#### Scenario: Part 6 is live
- **WHEN** the participant reads "Your own work"
- **THEN** it says Part 6 is live
- **AND** it says ideas can be brought to office hours or the AIR discussion
- **AND** it says Northwind is practice only

#### Scenario: No other text points to people
- **WHEN** any other lesson, step or interface string is scanned
- **THEN** it contains none of the contact-instruction phrases the content tests ban

#### Scenario: No new blocking element
- **WHEN** the baseline lesson is loaded
- **THEN** the number of activities that hold back Continue is unchanged
