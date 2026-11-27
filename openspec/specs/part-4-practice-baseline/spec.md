# part-4-practice-baseline Specification

## Purpose
Defines the isolated Practice baseline for Part 4: a bundled Iteration 0, its checker and its log for the Practice task, which lets a participant whose own baseline is missing, unusable or already near the target practice the rounds without touching their own files, and which is never a submission.

## Requirements

### Requirement: The Practice baseline is a bundled Iteration 0 for the Practice task
The app SHALL bundle, for the Practice task, its prompt, test cases, five saved sample answers, a ready-made checker for each track and an `iteration-log.md` that already holds its Iteration 0 entry. On the checker, Iteration 0 SHALL score 25 of 30 overall.

#### Scenario: Script track score
- **WHEN** the bundled script runs on the five sample answers
- **THEN** the pass counts are Length 4 of 5, Grouped by client 4 of 5, Blocker and ask 4 of 5, Teams not email 5 of 5, Factual tone 3 of 5 and Uses the rough notes 5 of 5, and the overall score is 25 of 30

#### Scenario: promptfoo track score
- **WHEN** the bundled config runs on the same five answers
- **THEN** it gives the same per-rule counts as the script

#### Scenario: The log entry matches
- **WHEN** the Practice log's Iteration 0 entry is compared with the checker's result
- **THEN** the counts and the NOT CHECKED items are equal

### Requirement: Choosing it copies the files into an isolated Part 4 folder
Choosing the Practice baseline SHALL copy the bundled files, create-only, into `part-4\practice\` in the project folder, with the checker for the participant's track only. It SHALL NOT read, copy, change or replace any of the participant's own prompt, test cases, checker, answers or log, and an existing file in the folder SHALL never be overwritten. The folder is the participant's own work: a progress reset keeps it and a configuration reset moves it with the project.

#### Scenario: Own files untouched
- **GIVEN** the participant has their own Part 3 files
- **WHEN** they choose the Practice baseline
- **THEN** their prompt, test cases, checker, answers and log have the same bytes as before

#### Scenario: Existing file
- **GIVEN** `part-4\practice\` already holds a file with the participant's edits
- **WHEN** the choice is resumed
- **THEN** that file is not overwritten

#### Scenario: Resets
- **WHEN** the participant resets lesson progress
- **THEN** `part-4\practice\` is kept, and a configuration reset moves it to the backup with the rest of the project

### Requirement: Rounds on the Practice baseline use its own files and log
Every round started from the Practice baseline SHALL take its starting prompt, rules and checker from `part-4\practice\` and write to `part-4\practice\attempts\<n>\`. The line the participant pastes to write the log SHALL name `part-4\practice\iteration-log.md`, and the decide step SHALL check that file. The participant's own log SHALL NOT be read or written.

#### Scenario: Round 1
- **GIVEN** the participant chose the Practice baseline
- **WHEN** round 1 is created
- **THEN** its prompt, rules and checker are copies of the Practice files, and its parent is Iteration 0

#### Scenario: The log file
- **GIVEN** the Practice baseline is chosen
- **WHEN** the decide step shows its line to paste
- **THEN** the line names the Practice log, and the check reads that file

### Requirement: The Practice baseline has no recorded model
The bundled sample answers SHALL have no recorded model. The first round's recorded model SHALL be the first model of the Practice baseline, and the model note SHALL compare rounds only with each other. The lesson text SHALL say the sample answers have no recorded model.

#### Scenario: First round
- **WHEN** the first Practice round is scored
- **THEN** its model is recorded and no "different model" note is shown

#### Scenario: Second round
- **GIVEN** round 2 used a different model from round 1
- **WHEN** it is scored
- **THEN** the model note is shown

### Requirement: The Practice baseline is practice only and never a submission
Every screen that shows the Practice baseline, its rounds, its log or its results SHALL say it is for practice only and cannot be submitted. No route or setting SHALL offer it as a submission or into a package. Part 4 SHALL count two documented Practice rounds as finishing the Part, and the finished screen SHALL say the results are practice only. Source: AGENTS.md rule 7; `docs/SPEC.md` "Evidence handoff".

#### Scenario: Labelled
- **WHEN** the participant opens the starting-point step, a Practice round or the finished screen
- **THEN** each says the Practice baseline is practice only and cannot be submitted

#### Scenario: Part 5 hand-off
- **GIVEN** the participant finished Part 4 on the Practice baseline
- **WHEN** Part 5 reads the kept version
- **THEN** it is marked practice and Part 5 offers its labelled Practice path

### Requirement: The Practice baseline is chosen once
Once round 1 exists, the starting point SHALL stay as chosen. A participant who wants the other starting point SHALL need to reset lesson progress, which keeps the files.

#### Scenario: Changing after round 1
- **GIVEN** round 1 exists
- **WHEN** a request asks to switch the starting point
- **THEN** it is refused with a plain sentence that says what to do, and nothing changes
