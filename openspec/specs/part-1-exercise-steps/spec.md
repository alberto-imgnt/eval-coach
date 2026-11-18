# part-1-exercise-steps Specification

## Purpose

Defines the five hands-on steps of Part 1 (cold run, score, rewrite, score again and compare, own prompt): what the participant does, what each step checks, which files it keeps, and how the prompt editor, score form and compare view behave.

## Requirements

### Requirement: The steps use the participant's own CLI, one run at a time
The `cold` and `rewrite` steps SHALL run the participant's own CLI in a folder that holds only the prompt, so the answer depends only on what the prompt says. Each run SHALL be a new CLI process, only one CLI process SHALL run at a time, and the app SHALL set no permission flags and never answer a CLI prompt. The line the app types SHALL be: `Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.` Source: AGENTS.md rules 2 to 4; `docs/SPEC.md` "Steps in this slice".

#### Scenario: Folder holds only the prompt
- **WHEN** the participant presses Start in `cold` or `rewrite`
- **THEN** the scratch folder is cleared and holds only `prompt.md`

#### Scenario: Output captured from a file
- **WHEN** the CLI saves a non-empty `output.txt` that stays unchanged across two one-second checks
- **THEN** the app saves it as the run's output, stops the CLI and moves the step forward
- **AND** the app decides nothing from what the terminal shows

#### Scenario: Reason in the step
- **WHEN** the participant reads the step
- **THEN** it gives the reason for a folder holding only the prompt, and says this is this course's way of working and that other approaches work too

### Requirement: The cold step captures an unguided starting point
The `cold` step SHALL show the scenario card (a Friday end-of-week update, the five things the participant knows but that are not in the notes, and the rough notes) and ask for a prompt in the participant's own words, run once, with no second tries. Its text SHALL give no hint about structure, kinds of information or frameworks. Source: facilitator guide, segment 2.

#### Scenario: Notes visible before writing
- **WHEN** the participant opens the `cold` step, before saving anything
- **THEN** the scenario card shows the full rough notes as plain text, so they can see what the AI will work from

#### Scenario: Saved words only
- **WHEN** the participant saves a prompt
- **THEN** the saved file holds only their words, and the run copy adds the rough notes under them

#### Scenario: No coaching
- **WHEN** the content tests scan the `cold` step text
- **THEN** it names no kind of information, label set or framework, and does not suggest what to include

#### Scenario: Notes added
- **GIVEN** the participant saved a prompt
- **WHEN** they press Start
- **THEN** the folder's `prompt.md` is their words followed by the rough notes under a plain divider, and the page shows the same preview

#### Scenario: Asked a question
- **WHEN** the CLI asks a clarifying question
- **THEN** the troubleshooting text tells the participant to reply "go ahead with your best guess"

### Requirement: The cold step's gate
The `cold` step SHALL pass when the saved prompt is non-empty, the run's output is saved and non-empty, and a model was recorded for the run. The model SHALL be recorded by the app when the AI starts (see `model-preference`), not typed. The participant SHALL be told that both runs use the model chosen with the toggle and that keeping it the same keeps the comparison fair, and the recorded model SHALL be saved for the `rewrite` step. A step that is done SHALL NOT offer a second run.

#### Scenario: Missing pieces
- **WHEN** the participant checks the step with no saved output
- **THEN** the gate fails with a plain message naming what is missing

#### Scenario: One shot
- **GIVEN** the step is done
- **WHEN** the participant opens it again
- **THEN** it shows their prompt and output and no Start control

#### Scenario: Model recorded without typing
- **GIVEN** the participant started the AI window and the run's output is saved
- **WHEN** the participant checks the step
- **THEN** the "Model name recorded" check passes and the participant typed no model name

### Requirement: Scoring is the participant's own judgment
The `score` step SHALL show the saved output as plain text beside the scenario card's five requirements and ask for a yes or no on each, one thing the output missed, and whether that was in the prompt (yes, no or not sure). It SHALL show "n of 5" computed from the participant's answers. The app SHALL NOT read the output text to decide, score it, or say whether the participant is right. Source: facilitator guide, segment 3; AGENTS.md rule 3.

#### Scenario: Form
- **WHEN** the participant opens `score`
- **THEN** five rows each offer a yes and a no with text labels, a text box for the gap and three answers for "was that in my prompt?"

#### Scenario: All five yes
- **GIVEN** the participant answered yes to all five rows
- **WHEN** the form is shown
- **THEN** the text box asks what their prompt included instead of what the output missed

#### Scenario: Computed score
- **WHEN** the participant answers the five rows
- **THEN** the page shows how many were yes out of five, from those answers only

#### Scenario: Gate
- **WHEN** every row, the gap text and the "in my prompt?" answer are filled
- **THEN** the step can pass; nothing about the answers can make it fail

#### Scenario: Plain text only
- **WHEN** the output is shown
- **THEN** it is rendered as plain text, never as HTML

### Requirement: The rewrite step lets the participant choose labels without a recommendation
The `rewrite` step SHALL offer three label sets with equal text, none pre-selected and none recommended: RTCC, RISE, and the participant's own labels for what their task needs. "Insert labels" SHALL put the chosen skeleton in the editor; the participant writes the prompt, and the app adds the same rough notes under it. A new CLI process SHALL be used, so nothing is carried over from the cold run. Source: facilitator guide, segment 5.

#### Scenario: Choice
- **WHEN** the participant opens `rewrite`
- **THEN** three options with equal-length descriptions are shown and none is selected

#### Scenario: Skeleton
- **WHEN** the participant chooses RTCC and presses "Insert labels"
- **THEN** the editor holds the four RTCC labels with a one-line meaning each, and an existing text is not replaced without confirmation

#### Scenario: Same notes
- **WHEN** the participant presses Start
- **THEN** the run copy ends with the same rough notes as the cold run

### Requirement: The rewrite step's gate and fairness nudge
The `rewrite` step SHALL pass when a label set is chosen, the saved prompt is non-empty and differs from the cold prompt, the run's output is saved and non-empty, and a model was recorded for the run. If the recorded model differs from the cold run's, the step SHALL pass and show a plain, non-blocking note that a different model makes the comparison less fair.

#### Scenario: Unchanged prompt
- **WHEN** the saved prompt equals the cold prompt
- **THEN** the gate fails and says to change the prompt first

#### Scenario: Different model
- **WHEN** the recorded models differ because the toggle was changed between the runs
- **THEN** the gate can pass and the step shows the non-blocking note

#### Scenario: Same model by default
- **GIVEN** the toggle was not changed between the two runs
- **WHEN** the participant checks the `rewrite` step
- **THEN** the models match and no note is shown

### Requirement: Compare puts both runs side by side
The `rescore` step SHALL score the second output on the same five requirements, then show both prompts, outputs and scores side by side as plain text with the change between the scores. It SHALL ask in writing what the labels made the participant add, and what made the second answer better or, if it was not, which part of the prompt is still missing. Source: facilitator guide, segment 6.

#### Scenario: Side by side
- **WHEN** the participant opens `rescore`
- **THEN** the two prompts, outputs and scores are shown next to each other, stacked on a narrow screen

#### Scenario: One run each
- **WHEN** the participant reads the compare
- **THEN** it says one run each cannot show how much answers vary, which Part 3 measures

#### Scenario: A worse second answer
- **GIVEN** the second score is lower than the first
- **WHEN** the participant opens the compare
- **THEN** the text says this can happen and points them to ask which part of the prompt is still missing, without blaming the framework

#### Scenario: Gate
- **WHEN** the five rows and both written answers are filled
- **THEN** the step can pass

### Requirement: The own step moves the skill to the participant's real work
The `own` step SHALL ask the participant to paste one real prompt from their own work (or, if they have none, a task they repeat), rewrite it with a framework's labels or labels of their own, and say which labels they used. It SHALL tell them to leave out anything confidential, and say the text stays on this computer. It SHALL start no CLI. It SHALL pass when both texts and the label note are non-empty and the two texts differ.

#### Scenario: Privacy note
- **WHEN** the participant opens the step
- **THEN** it says to leave out confidential details and that the text is kept only in the project folder

#### Scenario: No CLI
- **WHEN** the step is shown
- **THEN** it offers no Start or Send control

#### Scenario: Gate
- **WHEN** the before text, the after text and the label note are saved and the texts differ
- **THEN** the step passes

### Requirement: Part 1 files and progress keep only the participant's own work
Part 1 SHALL save prompts and outputs in `<project>\part-1\` (`prompt-cold.md`, `output-cold.txt`, `prompt-framework.md`, `output-framework.txt`, `own-before.md`, `own-after.md`) and scratch folders under `<home>\part1\`. The step records in `progress.json` SHALL hold the participant's own answers (yes or no marks, short texts, model names, the chosen label set) and SHALL hold no answer key, since Part 1 has none. A saved text SHALL be replaced only by the participant pressing Save.

#### Scenario: Files
- **WHEN** the participant finishes the cold and rewrite runs
- **THEN** the four prompt and output files exist under `part-1` in the project

#### Scenario: Saving
- **GIVEN** a saved prompt exists
- **WHEN** the participant edits it and presses Save
- **THEN** the file is replaced with the new text, and nothing else changes it

#### Scenario: No key
- **WHEN** the content tests read the progress shape for Part 1
- **THEN** no field holds a course answer, fixture text or key

### Requirement: Hands-on steps need setup and stay in order
Every Part 1 step SHALL be refused until setup has passed (as in `setup-access`), SHALL open only in order, and until then SHALL be readable as a read-only preview that writes nothing. Done steps SHALL stay viewable.

#### Scenario: Before setup
- **GIVEN** setup has not passed
- **WHEN** the participant opens the `cold` step
- **THEN** the instructions can be read and the editor, Save and Start are disabled with a way to open setup

#### Scenario: Server refusal
- **GIVEN** setup has not passed
- **WHEN** a request tries to save or start in a Part 1 step
- **THEN** the server refuses it with the setup-incomplete error

### Requirement: Each step has one short check that never blocks
Each Part 1 step SHALL have one question on its own page after the step is done, under the heading "Quick check", in the same form as Part 3's step questions. Answering SHALL never be required to continue.

#### Scenario: Quick check
- **GIVEN** the `score` step is done
- **WHEN** the participant opens its page
- **THEN** one question is shown, and the next item opens whether or not it is answered

### Requirement: The editor, score form and compare view are accessible and follow the design
The prompt editor, score form and compare view (authorized in the proposal) SHALL use the existing design tokens, work in both themes, at every text size and in the wide, mid and narrow layouts, and SHALL be usable by keyboard. Each yes or no row SHALL be a labelled group of two radio buttons whose meaning is in text, not color. Saving or scoring SHALL announce its result to a screen reader. Source: `docs/DESIGN.md`.

#### Scenario: Keyboard
- **WHEN** the participant tabs through the score form
- **THEN** each row's radios, the text boxes and the check button are reachable and work with Enter or Space

#### Scenario: Narrow screen
- **GIVEN** the window is narrow
- **WHEN** the compare view is shown
- **THEN** the two sides are stacked and nothing scrolls sideways

#### Scenario: Not color alone
- **WHEN** the score is shown
- **THEN** it is written as "n of 5" in text
