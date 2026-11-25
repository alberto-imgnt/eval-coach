# part-3-paste-flow Specification

## Purpose

Defines how Part 3's AI steps use the shared paste flow (`ai-window-paste-flow`): when the AI window starts by itself, what text the participant pastes, what "nothing to lose" means in each kind of folder, and what stays as it was. Source: series review items 8 and 8a, change 4b.

## Requirements

### Requirement: Part 3's AI steps use the paste flow
The steps `generate`, `build`, `fixtures`, `fixtures-config`, `readback`, `key`, `fix`, `baseline` and `live` SHALL use the paste flow. `predict` and `run` start no AI and SHALL NOT change. In a paste-flow step the app SHALL NOT type any line into the AI window, SHALL NOT answer any prompt the AI shows and SHALL set no permission flag. The request that used to type the step's line SHALL be refused as not supported. Source: AGENTS.md rules 2 and 3.

#### Scenario: Nothing typed
- **WHEN** a Part 3 AI window starts, runs and ends
- **THEN** no keystroke reaches the AI except what the participant typed or pasted

#### Scenario: Send is refused
- **WHEN** a request asks the app to type a Part 3 AI step's line
- **THEN** it is refused as not supported and nothing is typed

#### Scenario: Steps without an AI
- **WHEN** the participant opens `predict` or `run`
- **THEN** the step looks and behaves exactly as before and shows no AI window controls

### Requirement: The text to paste is the step's line
Each paste-flow step SHALL show, with a Copy button, the one text the participant pastes: the step's line, with the recorded model name filled in where the line has one. The text SHALL be the same words the app used to type, so the step's folder, skills and gates do not change. Copy SHALL be off, and the page SHALL say why, while a part of the text is not yet known (the AI choice for `live`).

#### Scenario: Copy
- **WHEN** the participant presses Copy
- **THEN** the text is placed on the clipboard and a status line that a screen reader announces says it was copied

#### Scenario: The browser refuses
- **GIVEN** the browser refuses clipboard access
- **WHEN** the participant presses Copy
- **THEN** the text is selected and the page says to press Ctrl+C

#### Scenario: Model filled in
- **GIVEN** the runs recorded one model name
- **WHEN** the participant opens `baseline`
- **THEN** the text to paste names that model and Copy is on

#### Scenario: Live mode before its choices
- **GIVEN** the warning is not acknowledged or no AI is chosen
- **WHEN** the participant opens `live`
- **THEN** Copy and "Open a new AI chat" are off and the page names what is missing

### Requirement: Opening an open step starts the AI window once
When the page shows a Part 3 paste-flow step that is active, it SHALL ask the server to apply the start rule once for that visit. The server SHALL start a new AI window, in the step's own folder and on the chosen model, only when all of these hold: the step is active and not done, setup has passed, no AI window is running, the AI has not been started by itself for this step before, the step is not `live`, and starting would not lose anything (see the next requirement). It SHALL record the model and that the start happened. A read-ahead view, a locked or finished step, a step opened before setup and a second visit SHALL start nothing, and the request SHALL succeed without effect in those cases.

#### Scenario: First visit starts the window
- **GIVEN** `build` is active and no window is running
- **WHEN** the participant opens it for the first time
- **THEN** a new AI window starts in the project folder on the chosen model and the step records that it started

#### Scenario: Second visit does not restart it
- **GIVEN** the window started by itself for the step
- **WHEN** the participant leaves and opens the step again
- **THEN** no window starts and a running window keeps running

#### Scenario: Stop then revisit
- **GIVEN** the window started and the participant pressed Stop
- **WHEN** the participant opens the step again
- **THEN** no window starts

#### Scenario: Reading ahead
- **GIVEN** the step is locked
- **WHEN** the participant reads it
- **THEN** no window starts, no folder is prepared and nothing is recorded

#### Scenario: Finished step
- **GIVEN** the step is done
- **WHEN** the participant opens it
- **THEN** no window starts

#### Scenario: Another window is running
- **GIVEN** an AI window for something else is running
- **WHEN** the participant opens the step
- **THEN** no second window starts

#### Scenario: Live mode is never started by itself
- **GIVEN** the warning is acknowledged and an AI is chosen
- **WHEN** the participant opens `live`
- **THEN** no window starts until the participant presses "Open a new AI chat"

#### Scenario: A start that fails
- **GIVEN** the AI cannot be started
- **WHEN** the participant opens the step
- **THEN** the page names the problem, the step stays open, and "Open a new AI chat" remains the way to try again

### Requirement: Nothing is lost by an automatic start
An automatic start SHALL NOT run when it would replace a saved result or a file in the step's scratch folder. In `generate` this means the next run's file is empty and the blind folder holds nothing but `prompt.md`; in `fixtures` the fixtures work folder holds no fixture text and the project holds no fixtures yet; in `key` the key work folder holds no answer key and no sealed key exists. The steps that work in the project folder (`build`, `fixtures-config`, `readback`, `fix`, `baseline`) clear nothing when a window starts, so they have no extra condition. The automatic start SHALL never read, quote or open the sealed answer key.

#### Scenario: A file the AI made blocks the start
- **GIVEN** the blind folder holds a file other than `prompt.md`
- **WHEN** the participant opens `generate`
- **THEN** no window starts and the file is kept

#### Scenario: Fixture text blocks the start
- **GIVEN** the fixtures work folder holds fixture text
- **WHEN** the participant opens `fixtures`
- **THEN** no window starts and the fixture text is kept

#### Scenario: Sealed key
- **GIVEN** a sealed answer key exists
- **WHEN** the participant opens `key`
- **THEN** no window starts and nothing is read from the key

### Requirement: Open a new AI chat replaces Start my AI and Start again
Each paste-flow step SHALL offer "Open a new AI chat". It SHALL start a new AI process on the chosen model and prepare the step's folder exactly as "Start my AI" did. When a window is running, or the step's scratch folder holds a result the new start would clear, it SHALL ask first and name what is lost. `generate` SHALL use it for runs 2 to 5, one new chat per run. Only one AI window SHALL run at a time. Source: AGENTS.md rule 4.

#### Scenario: No window running
- **GIVEN** no window is running and the folder holds nothing to lose
- **WHEN** the participant presses "Open a new AI chat"
- **THEN** a new window starts at once on the chosen model

#### Scenario: Window running
- **GIVEN** a window is running
- **WHEN** the participant presses "Open a new AI chat"
- **THEN** a confirm names what is lost and the window is replaced only after the participant agrees

#### Scenario: Run 2 of 5
- **GIVEN** run 1 is saved and the first window has stopped by itself
- **WHEN** the participant presses "Open a new AI chat"
- **THEN** a new window starts for run 2 and the label says run 2 of 5

#### Scenario: Old buttons are gone
- **WHEN** the participant opens any Part 3 paste-flow step
- **THEN** the page shows no "Send to AI", "Start my AI" or "Start again"

### Requirement: Part 3's gates and teaching are unchanged
Part 3 SHALL keep "Check my work", every gate item and its wording, every nudge, the answer-key deletion nudge, the predictions lock and the baseline mismatch messages. A step SHALL become done only through the same check as before. The step SHALL be judged only from files and by running the checker, never from the terminal. The model name SHALL still be recorded by the app at every start so the "Model name recorded" gate and the baseline line keep working. The `inputs` step is not an AI step: the paste flow does not apply to it, and it is finished by its own Continue. Source: AGENTS.md rules 3 and 9; series review item 10b.

#### Scenario: Check my work stays
- **WHEN** the participant opens any Part 3 step that had it
- **THEN** "Check my work" is shown and works as before

#### Scenario: Model recorded
- **WHEN** a window starts, by itself or by "Open a new AI chat"
- **THEN** the model that start used is recorded for Part 3, each model once, in the order first used

#### Scenario: Run files are still captured
- **GIVEN** the AI saves `output.txt` in the blind folder
- **WHEN** the file is complete and unchanged
- **THEN** the app saves it as the run's file and stops the window, as before

#### Scenario: A finished step closes its window
- **GIVEN** a step's AI window is still open
- **WHEN** "Check my work" passes for that step
- **THEN** that window is closed, so the next step can open its own by itself

#### Scenario: The inputs step is not an AI step
- **WHEN** the participant opens `inputs`
- **THEN** it shows no AI line, no Copy and no "Open a new AI chat"
- **AND** no AI window opens by itself

### Requirement: Part 3 words are plain and match the new flow
Every Part 3 step's instructions, troubleshooting and gate failure lines SHALL describe the paste flow: the AI window opens by itself, wait until it is ready, copy, paste, then press Check my work. No Part 3 step SHALL name "Send to AI", "Start my AI", "Start again", "Press Send" or "Press Start", and none SHALL use a bare "CLI". Every word SHALL come from the content files. Source: AGENTS.md rule 10; `participant-vocabulary`.

#### Scenario: Content scan
- **WHEN** the content tests scan the Part 3 AI steps
- **THEN** none names the old buttons

#### Scenario: Note shown
- **WHEN** the participant opens a paste-flow step
- **THEN** the AI window head says each step opens a new chat and that the window starts by itself

### Requirement: Part 3 offers no restart
Part 3 SHALL NOT offer "Start this step again" and SHALL refuse a restart request, as `part-registry` already says. Source: series review section 7.

#### Scenario: Finished Part 3 step
- **WHEN** the participant opens a finished Part 3 step
- **THEN** no restart is offered and a restart request is refused
