# step-restart Specification

## Purpose

Lets a participant start a finished step again without resetting the whole course: it clears that step and every later step of the same Part, keeps a backup, and leaves earlier steps and other Parts alone.

## Requirements

### Requirement: A finished step of a Part with a restart plan offers "Start this step again"
A finished step of Part 1 or Part 2 SHALL offer a "Start this step again" control. A step that is not finished, a locked step, a read-only preview and every Part 3 step SHALL NOT offer it, and a direct request for them SHALL be refused with a plain message that changes nothing. Setup SHALL have passed, as for any hands-on action. Source: series review item 11; `setup-access`.

#### Scenario: Offered on a finished step
- **GIVEN** the Part 1 `score` step is done
- **WHEN** the participant opens it
- **THEN** a "Start this step again" control is shown

#### Scenario: Not offered
- **WHEN** the participant opens an unfinished step, a locked step or any Part 3 step
- **THEN** no "Start this step again" control is shown

#### Scenario: Refused request
- **WHEN** a request asks to restart a step that is not done, or a Part 3 step
- **THEN** the server refuses it with a plain message and nothing is cleared

### Requirement: A confirm says what changes before anything is cleared
Restarting SHALL NOT run until the participant confirms in a dialog that lists, in plain words, the step and the later steps of the same Part that will start again, what is cleared from them, that earlier steps and other Parts stay, the backup folder, and that it replaces the previous backup. The dialog's default action SHALL keep everything.

#### Scenario: Cancelling
- **WHEN** the participant opens the dialog and chooses to keep everything
- **THEN** nothing is cleared or moved

#### Scenario: Confirmation text
- **WHEN** the dialog opens
- **THEN** it names the step and each later step of that Part, the backup folder and that the previous backup is replaced, in the words defined by the content files

### Requirement: Restarting clears the step and every later step of its Part
After confirmation the app SHALL stop any running AI window, then clear the chosen step and every later step in the same Part: each step's saved record, answers, ticks, choices and Quick check answer, and the files that step owns. Those steps SHALL show as not started and the chosen step SHALL be the Part's active step. Earlier steps, every other Part, lesson progress, setup and the Sonnet / Haiku preference SHALL be untouched. Source: series review item 11.

#### Scenario: Later steps cleared
- **GIVEN** Part 1 `cold`, `score` and `rewrite` are done
- **WHEN** the participant restarts `score` and confirms
- **THEN** `score` and `rewrite` show as not started, `cold` stays done with its prompt and answer, and `score` is the active step

#### Scenario: Other Parts untouched
- **GIVEN** Part 2 steps are done
- **WHEN** the participant restarts a Part 1 step
- **THEN** Part 2's progress and files are unchanged

#### Scenario: Quick check answers cleared
- **GIVEN** the participant answered the Quick check of a step that restarts
- **WHEN** the restart finishes
- **THEN** that step shows its Quick check as unanswered

#### Scenario: Running AI window
- **GIVEN** an AI window is running
- **WHEN** the participant confirms a restart
- **THEN** the AI window is stopped before anything is cleared, and no AI prompt is answered

### Requirement: Part 1 restarts clear the files each step made
A Part 1 restart SHALL move the files of the chosen step and later steps to the backup: `cold` owns `prompt-cold.md` and `output-cold.txt`, `rewrite` owns `prompt-framework.md` and `output-framework.txt`, `own` owns `own-before.md` and `own-after.md`, and `score` and `rescore` own saved answers only. The step's scratch folder SHALL be cleared too.

#### Scenario: Restart cold
- **WHEN** the participant restarts `cold` and confirms
- **THEN** all four prompt and answer files of `cold` and `rewrite` and both own-work files are in the backup and none is left in `part-1`

#### Scenario: Restart rewrite
- **WHEN** the participant restarts `rewrite` and confirms
- **THEN** `prompt-cold.md` and `output-cold.txt` are still in place, and the rewrite and own-work files are in the backup

#### Scenario: Restart score
- **WHEN** the participant restarts `score` and confirms
- **THEN** their yes or no marks and written answers are cleared, and the saved prompts and answers of `cold` stay

### Requirement: Part 2 restarts clear the files each step made
A Part 2 restart SHALL clear the chain draft, thresholds, test-file, reference. `draft` owns the worksheet and `test-cases.md` under `part-2`; `thresholds` owns the worksheet's thresholds; `test-file` owns `test-cases.md`; `reference` owns its choices only. The `test-cases.md` under Part 3's project root SHALL never be touched.

#### Scenario: Restart draft
- **WHEN** the participant restarts `draft` and confirms
- **THEN** the worksheet and `test-cases.md` under `part-2` are in the backup and all four steps show as not started

#### Scenario: Restart thresholds
- **WHEN** the participant restarts `thresholds` and confirms
- **THEN** the backup holds the worksheet as it was, the worksheet in place has the same criteria, requirements and types with no thresholds, and `draft` stays done

#### Scenario: Restart reference
- **WHEN** the participant restarts `reference` and confirms
- **THEN** their choices are cleared and `test-cases.md` stays in place

#### Scenario: Part 3 file untouched
- **GIVEN** the project has Part 3's own `test-cases.md`
- **WHEN** the participant restarts any Part 2 step
- **THEN** that file is unchanged

### Requirement: Cleared files go to the one backup and nothing else is deleted
Before anything is cleared, everything a restart removes SHALL be moved to the one backup folder outside the project, and the previous backup SHALL be replaced only after the new one is complete. Nothing SHALL be permanently deleted except the previous backup. Source: `progress-reset` "Cleared files go to one backup"; AGENTS.md "never overwrite or delete participant files".

#### Scenario: Backup contents
- **WHEN** a restart finishes
- **THEN** the backup folder holds the moved files with their names and contents unchanged

#### Scenario: Replaces the earlier backup
- **GIVEN** a backup from an earlier reset or restart exists
- **WHEN** the participant confirms a restart
- **THEN** only the newest backup exists afterwards

#### Scenario: Backup fails
- **GIVEN** the backup folder cannot be written
- **WHEN** the participant confirms a restart
- **THEN** a plain-language error is shown and progress and files are exactly as before

#### Scenario: Success message
- **WHEN** a restart finishes
- **THEN** the page says which steps start again and names the backup folder

### Requirement: A restart is all or nothing
If the backup cannot be completed or anything cannot be moved or cleared, the app SHALL change nothing, say so in plain words, and leave progress and files as they were.

#### Scenario: Move fails part-way
- **GIVEN** one file cannot be moved
- **WHEN** the participant confirms a restart
- **THEN** every file already moved is put back, progress is unchanged and a plain message says so

### Requirement: Later steps lock again until the chosen step is done
Once a restart finishes, each later step SHALL be locked by its Part's order until the steps before it are done again, as `part-registry` and `course-locking` set out. Lessons stay as they were.

#### Scenario: Next step locked
- **GIVEN** `score` was restarted
- **WHEN** the participant, or a request, asks for `rewrite`
- **THEN** it is refused with the lock message, and no step text is shown

### Requirement: The control and its words are accessible and plain
The control and its dialog SHALL be reachable by keyboard, follow the design tokens in both themes, announce their outcome to a screen reader, and get every word from `content/*.json` following `participant-vocabulary`. The restart control SHALL NOT share a name with the control that starts a new AI chat. Source: `docs/DESIGN.md`; AGENTS.md rule 10.

#### Scenario: Keyboard
- **WHEN** the participant tabs to the control and presses Enter
- **THEN** the dialog opens with the keep-everything action focused

#### Scenario: Result announced
- **WHEN** a restart finishes
- **THEN** a screen reader announces the result message
