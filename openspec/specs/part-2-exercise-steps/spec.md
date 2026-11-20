# part-2-exercise-steps Specification

## Purpose
Defines the four hands-on steps of Part 2 (draft, thresholds, test-file, reference): what the participant does, what each step checks, which files it keeps, what the file checks say, and how the worksheet, file and reference panels behave. No step runs a CLI or any checker.

## Requirements

### Requirement: The steps run nothing
No Part 2 step SHALL start the participant's CLI, run a checker or call a model, and none SHALL need a network. Every gate SHALL decide from the participant's own saved words and files, never from terminal output. Source: AGENTS.md rules 3 and 5; the course context notes (local reference) ("Nothing is run in Part 2").

#### Scenario: No CLI
- **WHEN** the participant opens any Part 2 step
- **THEN** it offers no Start or Send control and no terminal

#### Scenario: Judged by files
- **WHEN** a Part 2 step is checked
- **THEN** the result depends only on the participant's saved worksheet, file and answers

### Requirement: Hands-on steps need setup and stay in order
Every Part 2 step SHALL be refused until setup has passed (as in `setup-access`) and SHALL open only in order. A step that order has not opened SHALL be refused with the lock message and SHALL NOT be readable as a preview (`course-locking`). Done steps SHALL stay viewable.

#### Scenario: Before setup
- **GIVEN** setup has not passed, Part 2 is open and the lesson before `draft` is done
- **WHEN** the participant opens the `draft` step
- **THEN** the instructions can be read, and the worksheet, Save and Check are disabled with a way to open setup

#### Scenario: Server refusal
- **GIVEN** setup has not passed
- **WHEN** a request tries to save the worksheet
- **THEN** the server refuses it with the setup-incomplete error

#### Scenario: Preview writes nothing
- **WHEN** a request asks for a locked step, or the participant opens a step of a Skipped Part read-only
- **THEN** no file or saved progress changes

### Requirement: The draft step starts from the scenario card
The `draft` step SHALL show the scenario card (a Friday end-of-week update, the five things the participant knows that are not in the notes, and the rough notes) and ask the participant to turn those requirements into criteria. Source: scenario card and criteria worksheet in the live materials.

#### Scenario: Card shown
- **WHEN** the participant opens `draft`
- **THEN** the five requirements and the rough notes are shown as plain text

#### Scenario: Not the answer
- **WHEN** the content tests scan the step's words
- **THEN** no criterion, threshold or banned word from the Northwind reference appears

### Requirement: The participant's own Part 1 notes are shown when they exist
When the participant has done Part 1, the `draft` step SHALL show, read-only and as plain text, their own yes or no marks on the five requirements and the gap they named, so hand scoring leads to criteria. When they have not, the step SHALL omit this panel without error. It SHALL never gate the step or change any Part 1 file.

#### Scenario: Part 1 done
- **GIVEN** the participant scored an answer in Part 1
- **WHEN** they open `draft`
- **THEN** their marks and their gap are shown next to the requirements, and labelled as their own

#### Scenario: Part 1 not done
- **GIVEN** the participant has not done Part 1
- **WHEN** they open `draft`
- **THEN** no Part 1 panel is shown and the step works the same

#### Scenario: Read only
- **WHEN** the participant uses the step
- **THEN** no Part 1 file or Part 1 saved progress changes

### Requirement: The worksheet holds criteria with a type
The worksheet SHALL have one row per criterion with the requirement it traces to, the criterion in the participant's words, and a type (format or content). The participant SHALL be able to add and remove rows and to fill a requirement from the card or type their own. Rows SHALL be saved only when the participant presses Save, and an existing saved worksheet SHALL be shown, never replaced, when the step is reopened.

#### Scenario: Add and remove
- **WHEN** the participant adds a row and removes another
- **THEN** the table shows the change and nothing is saved until they press Save

#### Scenario: Requirement from the card
- **WHEN** the participant chooses a requirement from the card for a row
- **THEN** its text fills the requirement box, and they can still edit it

#### Scenario: Reopening
- **GIVEN** a worksheet was saved
- **WHEN** the participant opens the step again
- **THEN** their rows are shown, not a blank table

#### Scenario: Unsaved changes
- **GIVEN** the table has changes that are not saved
- **WHEN** the participant presses Check my work
- **THEN** the step asks them to Save first and checks nothing

### Requirement: The draft step's gate
The `draft` step SHALL pass when the worksheet has at least three rows, each with a requirement, a criterion and a type, at least one row is of type content, no two rows have the same criterion text, and the participant has ticked both self-checks (each criterion traces to a requirement, and no two check the same thing). Source: the live session's rules and self-check.

#### Scenario: Too few criteria
- **WHEN** the worksheet has two complete rows
- **THEN** the gate fails and says how many more are needed

#### Scenario: No content criterion
- **WHEN** every row is of type format
- **THEN** the gate fails and says at least one criterion must be about what the answer says

#### Scenario: Missing piece
- **WHEN** a row has no requirement or no criterion
- **THEN** the gate fails and names the row

#### Scenario: Repeated criterion
- **WHEN** two rows have the same criterion text, ignoring spacing and capitals
- **THEN** the gate fails and names both rows

#### Scenario: Self-check
- **WHEN** a self-check tick is missing
- **THEN** the gate fails and says which

### Requirement: The thresholds step adds a pass or fail rule to every criterion
The `thresholds` step SHALL show the same worksheet with a Threshold column added and SHALL pass when every row has a threshold and the participant has ticked that they applied the script test to every threshold. A threshold that begins "Not checked:" with a reason SHALL count as written. Source: the live session's second block.

#### Scenario: Same rows
- **WHEN** the participant opens `thresholds` after `draft`
- **THEN** their rows from the first step are shown with an empty Threshold box for each

#### Scenario: Missing threshold
- **WHEN** a row has no threshold
- **THEN** the gate fails and names the row

#### Scenario: Not checked is honest
- **WHEN** a threshold reads "Not checked:" followed by a reason
- **THEN** the gate treats it as written and the file keeps it

#### Scenario: Script test tick
- **WHEN** the participant has not ticked the script test
- **THEN** the gate fails and says so

### Requirement: Vague thresholds get a nudge, never a block
When a threshold contains a vague word, the `thresholds` step SHALL show a non-blocking note for that row that names the word and offers three ways to fix it (a number, a list of terms the participant chooses, a label), and says a rule that cannot be made checkable can be written as "Not checked:" with a reason. Words in quotation marks or backticks SHALL NOT be flagged.

#### Scenario: Vague word
- **WHEN** a threshold says "the update is clear"
- **THEN** a note names "clear" and offers the three rewrites
- **AND** the gate can still pass

#### Scenario: Chosen term
- **WHEN** a threshold has the word inside quotation marks
- **THEN** it is not flagged

### Requirement: The test-file step builds the file and checks it
The `test-file` step SHALL offer to build `test-cases.md` from the worksheet in the layout Part 3 reads: a title, a test input holding the rough notes, the criteria with ID, requirement, type and threshold, and a supporting-lists section. The participant SHALL edit it in the step, and the file SHALL be written only when they press Save or Build. Building SHALL ask before replacing text the participant has already saved.

#### Scenario: Build
- **GIVEN** the worksheet has thresholds
- **WHEN** the participant presses Build my file
- **THEN** the editor holds a file with their criteria numbered C1, C2 and so on, in that layout

#### Scenario: Existing text
- **GIVEN** the participant already saved a file
- **WHEN** they press Build my file
- **THEN** the step asks before replacing it, and keeps the old text if they decline

#### Scenario: Own words kept
- **WHEN** the file is built
- **THEN** the criterion, requirement, type and threshold are the participant's own text, unchanged

### Requirement: The participant writes their own supporting lists
The built file SHALL hold an empty supporting-lists section with a plain example line (not the Northwind list), and the step SHALL tell the participant that a banned or required list for their own task is written by them and stored in the file. The Northwind banned list SHALL NOT be pre-filled.

#### Scenario: Empty list section
- **WHEN** the file is built
- **THEN** the supporting-lists section holds no Northwind words

#### Scenario: Missing list
- **WHEN** a threshold refers to a list (banned words, required labels) and the file has no list entry for it
- **THEN** the step shows a non-blocking note naming the criterion and saying where to add the list

### Requirement: The test-file gate uses the checks for a usable file
The `test-file` step SHALL pass when a saved file has a test input, at least three criteria and at least one about content. It SHALL show other findings as non-blocking notes: a criterion with no threshold, a criterion with no requirement, and a vague threshold. Every finding SHALL be worded for this step (never "press Check my files") and SHALL say what to do next. Source: the checks Part 3's import already applies.

#### Scenario: Too few criteria
- **WHEN** the saved file has two criteria
- **THEN** the gate fails and the finding says how many are missing and shows the heading layout

#### Scenario: No content criterion
- **WHEN** no criterion's threshold names the terms, labels or facts the answer must include
- **THEN** the gate fails and the finding gives an example of a content threshold

#### Scenario: Notes do not block
- **WHEN** the file has a vague threshold but meets the three requirements
- **THEN** the gate passes and the note is still shown

#### Scenario: Same layout as Part 3
- **GIVEN** the file passes
- **WHEN** Part 3's file check reads it
- **THEN** it finds the same criteria

### Requirement: The reference step shows the example after the file is done
The `reference` step SHALL show the Northwind reference criteria (requirement, type and threshold, as the live session's reference table) beside the participant's own, only once `test-file` is done. For each reference criterion the participant SHALL choose one of: "I had this", "I missed this", "I wrote it differently and mine works", or "Mine was vague". The step SHALL say the reference is one good answer, not the only one. Source: presenter reference tables in the live materials.

#### Scenario: Reveal
- **GIVEN** `test-file` is done
- **WHEN** the participant opens `reference`
- **THEN** each reference criterion is shown with four choices and the participant's own criteria are listed beside them

#### Scenario: One good answer
- **WHEN** the participant reads the step
- **THEN** it says different criteria can also be right, and that the reference is not a score

#### Scenario: Banned list shown only here
- **WHEN** the participant opens `reference`
- **THEN** the Northwind banned list appears once, marked as the example's own and not theirs to copy for their own task

### Requirement: The reference step's gate and optional repair
The `reference` step SHALL pass when every reference criterion has a choice. The app SHALL NOT judge whether the choices are right. The step SHALL offer the same file editor as `test-file` so the participant can improve their file after comparing, and a saved change SHALL pass through the same file checks, never blocking the step.

#### Scenario: Classified
- **WHEN** every reference criterion has a choice
- **THEN** the step can pass

#### Scenario: Missing choice
- **WHEN** a reference criterion has no choice
- **THEN** the gate fails and names it

#### Scenario: Edit after comparing
- **WHEN** the participant edits and saves their file in this step
- **THEN** the file checks run again and show any notes, and the step's gate is unchanged

### Requirement: Part 2 files and progress keep only the participant's own work
Part 2 SHALL save the worksheet and `test-cases.md` in `<project>\part-2\`. Step records in saved progress SHALL hold the participant's own answers (ticks, choices, file hashes) and SHALL hold no reference text, no worksheet content and no course answer. A saved file SHALL be replaced only by the participant pressing Save or confirming Build. Source: AGENTS.md rule 9 and "never overwrite a participant file".

#### Scenario: Files
- **WHEN** the participant finishes `test-file`
- **THEN** `test-cases.md` exists under `part-2` in the project

#### Scenario: Saving
- **GIVEN** a saved file exists
- **WHEN** the participant edits and presses Save
- **THEN** the file is replaced, and nothing else changes it

#### Scenario: No reference in progress
- **WHEN** the content tests read the saved progress after `reference` is done
- **THEN** no field holds a reference criterion, threshold or banned word

#### Scenario: Not touched by Part 3 files
- **GIVEN** the project has its own `test-cases.md` from Part 3's setup
- **WHEN** the participant works in Part 2
- **THEN** that file is unchanged

### Requirement: Each step has one short check that never blocks
Each Part 2 step SHALL have one question on its own page after the step is done, under the heading "Quick check", in the same form as Part 3's step questions. Answering SHALL never be required to continue.

#### Scenario: Quick check
- **GIVEN** the `thresholds` step is done
- **WHEN** the participant opens its page
- **THEN** one question is shown, and the next item opens whether or not it is answered

### Requirement: The worksheet, file and reference panels are accessible and follow the design
The worksheet, test-file and reference panels (authorized in the proposal) SHALL use the existing design tokens, work in both themes, at every text size and in the wide, mid and narrow layouts, and SHALL be usable by keyboard. Type and classification choices SHALL be labelled groups whose meaning is in text, not color. Saving and checking SHALL announce their result to a screen reader. Source: `docs/DESIGN.md`.

#### Scenario: Keyboard
- **WHEN** the participant tabs through the worksheet
- **THEN** each row's boxes, the type choice, add and remove, Save and Check are reachable and work with Enter or Space

#### Scenario: Narrow screen
- **GIVEN** the window is narrow
- **WHEN** the worksheet or the reference comparison is shown
- **THEN** each row stacks its fields and nothing scrolls sideways

#### Scenario: Not color alone
- **WHEN** a classification or a finding is shown
- **THEN** its meaning is written in text
