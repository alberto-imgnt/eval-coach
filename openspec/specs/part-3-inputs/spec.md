# part-3-inputs Specification

## Purpose
Makes Part 3 start from inputs the participant has seen and chosen. It shows the prompt and test cases that will be scored, offers the Part 1 rewrite and the Part 2 file for the same task, and labels any fallback, so nothing is swapped silently and no original or in-use file is lost.

## Requirements

### Requirement: Part 3 opens with a Choose your inputs step
Part 3 SHALL have a step `inputs`, "Choose your inputs", after `several-runs` and before `generate`. It SHALL start no AI and no checker, behave the same on the Script and promptfoo tracks, and need setup like every hands-on step. `generate` SHALL open only once `inputs` is done.

#### Scenario: Order
- **WHEN** the participant has finished `several-runs`
- **THEN** `inputs` opens and `generate` stays locked with the usual lock message

#### Scenario: No AI
- **WHEN** the participant opens `inputs`
- **THEN** no AI window starts and no line to paste is shown

#### Scenario: Both tracks
- **WHEN** the participant is on the promptfoo track
- **THEN** `inputs` has the same behavior and the same words as on the Script track

### Requirement: The step shows which prompt and test cases are active
Before anything can change, `inputs` SHALL show the text of the prompt and the test cases Part 3 will use now, each with a plain label for where it came from: the Practice task, files the participant brought in setup, their Part 1 rewrite, their Part 2 file, or "a file in your project folder" when the app cannot tell. The label SHALL come from comparing the active file with the known sources. The project's recorded starter SHALL only tell the participant's own files apart from an unknown file.

#### Scenario: Practice task project
- **GIVEN** the project was set up with the Practice task
- **WHEN** the participant opens `inputs`
- **THEN** both files are labelled as the Practice task and are shown in full

#### Scenario: Participant's own files
- **GIVEN** the project was set up with files the participant brought
- **WHEN** the participant opens `inputs`
- **THEN** both files are labelled as the files they brought, not as the Practice task

#### Scenario: Source cannot be told
- **GIVEN** the active file matches no known source and the project was not set up with the participant's own files, for example after the participant edited it by hand
- **WHEN** the participant opens `inputs`
- **THEN** the label says it is a file in the project folder and does not guess

### Requirement: Using the Part 1 rewrite is an explicit choice
`inputs` SHALL offer the participant's Part 1 rewrite as a choice for the prompt. The prompt it carries SHALL be the rewrite followed by the task's rough notes, which is what Part 1's AI ran, without Part 1's closing instruction, so that Part 3 runs the same task. Nothing changes until the participant picks it, and a pick replaces only the active prompt.

#### Scenario: Offered after the rewrite is done
- **GIVEN** Part 1's `rewrite` step is done and its prompt file is not blank
- **WHEN** the participant opens `inputs`
- **THEN** the rewrite is offered with a label naming Part 1

#### Scenario: Carries the notes
- **WHEN** the participant picks the Part 1 rewrite
- **THEN** the active prompt holds the rewrite and the rough notes and does not hold Part 1's closing instruction

#### Scenario: Nothing changes without a pick
- **WHEN** the participant presses Continue without choosing anything
- **THEN** the active files are unchanged and the step records that they were kept

### Requirement: Using the Part 2 file is an explicit choice
`inputs` SHALL offer the participant's Part 2 test cases file as a choice for the test cases when it passes the same blocking checks as an imported file (three or more criteria, one about content, a non-empty test input). A pick replaces only the active test cases.

#### Scenario: Offered
- **GIVEN** Part 2's `test-file` step is done and the saved file passes the blocking checks
- **WHEN** the participant opens `inputs`
- **THEN** the file is offered with a label naming Part 2

#### Scenario: Pick both at once
- **WHEN** both the Part 1 rewrite and the Part 2 file are offered
- **THEN** one action uses both, and each can still be picked on its own

### Requirement: A source that cannot be used is labelled with the reason
When a Part 1 or Part 2 file is not offered, `inputs` SHALL say why in plain words: the Part was skipped, the step is not finished, the file is missing, blank or too large, or it fails a blocking check, named. A Part 1 prompt that changed after the answer saved for it was made SHALL be offered with a label saying so and SHALL NOT be preselected. The step SHALL never fill a gap with a file the participant did not choose.

#### Scenario: Part skipped
- **GIVEN** the participant skipped Part 2
- **WHEN** they open `inputs`
- **THEN** the Part 2 file is not offered and the step says Part 2 was skipped

#### Scenario: File unsuitable
- **GIVEN** the Part 2 file has only two criteria
- **WHEN** the participant opens `inputs`
- **THEN** the file is not offered and the message says how many criteria are missing

#### Scenario: Changed after its answer
- **GIVEN** the Part 1 prompt was edited after the saved answer was made
- **WHEN** the participant opens `inputs`
- **THEN** the rewrite is offered with a note that it changed, and is not preselected

### Requirement: The Practice task files are the labelled fallback
`inputs` SHALL always offer the Practice task prompt and test cases as a fallback, labelled as practice only and never as a submission. Choosing them SHALL be explicit like any other choice.

#### Scenario: Fallback offered
- **GIVEN** both the Part 1 and the Part 2 sources are unusable
- **WHEN** the participant opens `inputs`
- **THEN** the Practice task files are offered, labelled practice only

#### Scenario: Never a submission
- **WHEN** the participant reads the fallback
- **THEN** it says the Practice task cannot be their submission

### Requirement: A possible mismatch between prompt and test cases is shown
When the test input in the active test cases is not the rough notes in the active prompt (ignoring spacing), or when the participant picks a Practice task file into a project that holds their own task files, `inputs` SHALL show a plain note that the two files may be for different tasks. The note SHALL NOT block Continue.

#### Scenario: Different notes
- **GIVEN** the participant picks their Part 1 rewrite and keeps test cases whose input is another task
- **WHEN** the step shows the pair
- **THEN** a note says the prompt and the test cases may be for different tasks

#### Scenario: Own task project
- **GIVEN** the project holds the participant's own task files
- **WHEN** they pick the Part 1 rewrite
- **THEN** the note says Part 1 was written for the Practice task

### Requirement: No original or in-use file is lost
Before `inputs` replaces an active file it SHALL keep a copy under `part-3\replaced\` in the project, unless a copy with the same content is already there. It SHALL NOT delete a participant file, overwrite an existing copy, change the Part 1 or Part 2 file it copied from, or touch the participant's original files from setup.

#### Scenario: Original kept
- **WHEN** the participant picks their Part 1 rewrite over the Practice task prompt
- **THEN** the Practice task prompt is kept in `part-3\replaced\` and the active prompt is the rewrite

#### Scenario: Hand-edited file kept
- **GIVEN** the participant edited the active test cases by hand in the project folder
- **WHEN** they pick the Part 2 file
- **THEN** their edited file is kept in `part-3\replaced\` before it is replaced

#### Scenario: Sources unchanged
- **WHEN** a choice is applied
- **THEN** the Part 1 and Part 2 files are byte for byte what they were

#### Scenario: Switching back
- **GIVEN** the participant picked the Part 1 rewrite and has not continued
- **WHEN** they pick the Practice task prompt instead
- **THEN** the Practice task prompt is active and the rewrite is still saved in Part 1 and in `part-3\replaced\`

### Requirement: Continuing locks the chosen files as the evidence in use
Pressing Continue SHALL finish `inputs` when both active files are non-blank and the test cases pass the blocking checks. It SHALL record, for each file, where it came from and a hash of its content, and no file text. After that `inputs` SHALL refuse further choices, so the files Part 3 reads are the files the step showed.

#### Scenario: Finished
- **WHEN** the participant presses Continue with a valid pair
- **THEN** `generate` opens and the choice is recorded as sources and hashes only

#### Scenario: Choices after continuing
- **GIVEN** `inputs` is done
- **WHEN** a request to change a file arrives
- **THEN** it is refused and the files are unchanged

#### Scenario: Invalid pair
- **GIVEN** the active test cases have only two criteria
- **WHEN** the participant presses Continue
- **THEN** the step does not finish and says what is missing

### Requirement: A source that changed since the choice is reported
After `inputs` is done, opening it SHALL show whether each chosen source is unchanged, changed or gone since the choice, as information only. A later "Start this step again" in Part 1 or Part 2 SHALL NOT change the files Part 3 uses.

#### Scenario: Part 1 restarted later
- **GIVEN** the participant used their Part 1 rewrite and later restarted Part 1's `rewrite`
- **WHEN** they open `inputs`
- **THEN** it says the Part 1 file changed or is gone, and Part 3's active prompt is unchanged

### Requirement: Older progress and resets keep working
A saved project from before this step SHALL load with `inputs` done, recorded as the files already in the project, whenever Generate has already started or a later Part 3 step is done, and with `inputs` as the next step otherwise. A progress reset SHALL keep `part-3\replaced\` and a configuration reset SHALL move it, like the participant's other own words.

#### Scenario: Partway through Part 3
- **GIVEN** a saved project with `generate` done and no `inputs` record
- **WHEN** it loads
- **THEN** `inputs` is done, labelled as the files already in the project, and nothing on disk is rewritten

#### Scenario: Part 3 not started
- **GIVEN** a saved project with no Part 3 step done and no recorded Generate start or saved answer
- **WHEN** it loads
- **THEN** `inputs` is the next Part 3 step

#### Scenario: Generation underway on upgrade
- **GIVEN** an older project with a saved answer or a recorded Generate start but no finished Part 3 step
- **WHEN** it loads
- **THEN** `inputs` is done using the existing files, and Generate can resume on the selected track without changing the existing inputs or answers

#### Scenario: Reset inventory
- **WHEN** the reset tests list the files of a finished stand-in project
- **THEN** every file under `part-3\replaced\` is on a reset list
