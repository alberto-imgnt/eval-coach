# Spec Delta

## MODIFIED Requirements

### Requirement: The steps use the participant's own CLI, one run at a time
The `cold` and `rewrite` steps SHALL run the participant's own CLI in a folder that holds only `prompt.md`, so the answer depends only on what the prompt says. Each run SHALL be a new CLI process, only one CLI process SHALL run at a time, and the app SHALL set no permission flags and never answer a CLI prompt. The AI window SHALL start by itself and the participant SHALL paste the text the step shows, as set out in `ai-window-paste-flow`; the app SHALL type no line. Source: AGENTS.md rules 2 to 4; `docs/SPEC.md` "Steps in this slice".

#### Scenario: Folder holds only the prompt
- **WHEN** the AI window starts in `cold` or `rewrite`
- **THEN** the scratch folder is cleared and holds only `prompt.md`, with the full text the participant pastes

#### Scenario: Output captured from a file
- **WHEN** the CLI saves a non-empty `output.txt` that stays unchanged across two one-second checks
- **THEN** the app saves it as the run's output, stops the CLI and, when the step's gate is met, finishes the step
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
- **THEN** the saved file holds only their words, and the text to paste adds the rough notes and the closing instruction under them

#### Scenario: No coaching
- **WHEN** the content tests scan the `cold` step text
- **THEN** it names no kind of information, label set or framework, and does not suggest what to include

#### Scenario: Notes added
- **GIVEN** the participant saved a prompt
- **WHEN** the AI window starts
- **THEN** the folder's `prompt.md` is their words followed by the rough notes under a plain divider and the closing instruction, and the page shows the same text with a Copy button

#### Scenario: Asked a question
- **WHEN** the CLI asks a clarifying question
- **THEN** the troubleshooting text tells the participant to reply "go ahead with your best guess"

### Requirement: The cold step's gate
The `cold` step SHALL be done when the saved prompt is non-empty, the run's output is saved and non-empty, and a model was recorded for the run. The model SHALL be recorded by the app when the AI starts (see `model-preference`), not typed. The participant SHALL be told that both runs use the model chosen with the toggle and that keeping it the same keeps the comparison fair, and the recorded model SHALL be saved for the `rewrite` step. A step that is done SHALL NOT offer a second run.

#### Scenario: Missing pieces
- **WHEN** the step's output is not saved yet
- **THEN** the step is not done and the inline list names what is missing in plain words

#### Scenario: One shot
- **GIVEN** the step is done
- **WHEN** the participant opens it again
- **THEN** it shows their prompt and output and no way to start a run

#### Scenario: Model recorded without typing
- **GIVEN** the AI window started and the run's output is saved
- **WHEN** the output is captured
- **THEN** the "Model name recorded" item is met, the participant typed no model name, and the step is done

### Requirement: The rewrite step's gate and fairness nudge
The `rewrite` step SHALL be done when a label set is chosen, the saved prompt is non-empty and differs from the cold prompt, the run's output is saved and non-empty, and a model was recorded for the run. If the recorded model differs from the cold run's, the step SHALL be done and show a plain, non-blocking note that a different model makes the comparison less fair.

#### Scenario: Unchanged prompt
- **WHEN** the saved prompt equals the cold prompt
- **THEN** the step is not done and the inline list says to change the prompt first

#### Scenario: Different model
- **WHEN** the recorded models differ because the toggle was changed between the runs
- **THEN** the step can be done and shows the non-blocking note

#### Scenario: Same model by default
- **GIVEN** the toggle was not changed between the two runs
- **WHEN** the `rewrite` step is done
- **THEN** the models match and no note is shown

### Requirement: Hands-on steps need setup and stay in order
Every Part 1 step SHALL be refused until setup has passed (as in `setup-access`), SHALL open only in order, and until then SHALL be readable as a read-only preview that writes nothing. Done steps SHALL stay viewable.

#### Scenario: Before setup
- **GIVEN** setup has not passed
- **WHEN** the participant opens the `cold` step
- **THEN** the instructions can be read, the editor, Save and Copy are disabled, no AI window starts, and there is a way to open setup

#### Scenario: Server refusal
- **GIVEN** setup has not passed
- **WHEN** a request tries to save or start in a Part 1 step
- **THEN** the server refuses it with the setup-incomplete error

### Requirement: The editor, score form and compare view are accessible and follow the design
The prompt editor, score form and compare view (authorized in the proposal) SHALL use the existing design tokens, work in both themes, at every text size and in the wide, mid and narrow layouts, and SHALL be usable by keyboard. Each yes or no row SHALL be a labelled group of two radio buttons whose meaning is in text, not color. Saving or scoring SHALL announce its result to a screen reader. Source: `docs/DESIGN.md`.

#### Scenario: Keyboard
- **WHEN** the participant tabs through the score form
- **THEN** each row's radios, the text boxes and the Continue button are reachable and work with Enter or Space

#### Scenario: Narrow screen
- **GIVEN** the window is narrow
- **WHEN** the compare view is shown
- **THEN** the two sides are stacked and nothing scrolls sideways

#### Scenario: Not color alone
- **WHEN** the score is shown
- **THEN** it is written as "n of 5" in text

## ADDED Requirements

### Requirement: Part 1 steps finish without a Check button
No Part 1 step SHALL offer "Check my work". A step SHALL be done when its own gate is met, at the moment its work is committed: the AI's output is captured (`cold`, `rewrite`), a Save leaves the gate met (`own`), or the participant presses "Continue to: <next step>", enabled only while the gate is met (`score`, `rescore`). Source: series review item 10b.

#### Scenario: Run step finishes by itself
- **GIVEN** the `cold` step has a saved prompt and a started AI window
- **WHEN** the output is captured
- **THEN** the step is done, the AI window closes and "Continue to: <next step>" appears

#### Scenario: Late label choice
- **GIVEN** the `rewrite` output was captured before a label set was chosen, and the prompt has not changed since
- **WHEN** the participant chooses a label set
- **THEN** the gate is met and the step is done

#### Scenario: Not done until the gate is met
- **GIVEN** any gate item of a Part 1 step is not met
- **WHEN** the participant saves, captures output or presses Continue
- **THEN** the step is not done

#### Scenario: Prompt changed after the run
- **GIVEN** the `rewrite` output was captured, but the gate failed because the prompt matched the cold prompt
- **WHEN** the participant edits the prompt and saves
- **THEN** the step is not done, because the output no longer matches the prompt, and the step says a new run is needed

#### Scenario: Own step
- **GIVEN** the before text, the after text and the label note are filled and differ
- **WHEN** the participant presses Save
- **THEN** the step is done

#### Scenario: Score form completes on Continue
- **GIVEN** every row, the gap text and the "was that in my prompt?" answer are filled
- **WHEN** the participant presses "Continue to: <next step>"
- **THEN** the step is done and the next step opens

#### Scenario: Continue not enabled early
- **GIVEN** one row of the score form is unanswered
- **WHEN** the participant looks at the Continue button
- **THEN** it is not enabled and the inline list names the missing row

#### Scenario: Typing is never cut off
- **GIVEN** the participant is typing the gap text of the score form
- **WHEN** the text autosaves
- **THEN** the step stays open and editable until they press Continue

### Requirement: What is still missing shows inline and never blocks
Until a Part 1 step is done, it SHALL show in plain words which items of its gate are not met yet, in the same form the check used, with any non-blocking notes under them. The list SHALL need no button, SHALL update as the participant works, and SHALL never stop the participant from editing, saving or opening a Quick check.

#### Scenario: List updates
- **GIVEN** the `score` form has two rows unanswered
- **WHEN** the participant answers one
- **THEN** the list shows one row missing

#### Scenario: Notes shown
- **WHEN** the recorded models differ between the two runs
- **THEN** the fairness note shows inline and does not stop the step

#### Scenario: Gate unchanged
- **WHEN** the content tests compare the Part 1 gate items with the ones before this change
- **THEN** each gate item is the same
