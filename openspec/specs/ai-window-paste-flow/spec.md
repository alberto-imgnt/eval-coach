# ai-window-paste-flow Specification

## Purpose

Defines how a step that uses the participant's own AI starts the AI window by itself, what text the participant copies and pastes into it, and that the app types nothing into the AI. Written once so Part 1 uses it now and Part 3 can reuse it.

## Requirements

### Requirement: The AI window starts by itself on the first save of a prompt
In a step that uses the paste flow, saving a non-empty prompt SHALL start a new AI window when the step is active, no AI window is running, the AI has not been started for this step before, and starting would not replace a saved answer or any file in the step's AI folder. The start SHALL use the model the Sonnet / Haiku toggle chose and SHALL record that model. Source: series review items 8 and 8a.

#### Scenario: First save starts the window
- **GIVEN** the step is active and no AI window is running
- **WHEN** the participant saves a non-empty prompt for the first time
- **THEN** a new AI window starts in the step's own folder, on the chosen model, and the model is recorded for the step

#### Scenario: Second save does not restart it
- **GIVEN** the AI window started by itself and is still running
- **WHEN** the participant saves the prompt again
- **THEN** the window keeps running and is not restarted

#### Scenario: Stop then save does not start it again
- **GIVEN** the AI window started and the participant pressed Stop
- **WHEN** the participant saves the prompt again
- **THEN** no AI window starts

#### Scenario: Opening the step again starts nothing
- **WHEN** the participant opens, leaves and reopens the step without saving
- **THEN** no AI window starts

#### Scenario: A blank prompt starts nothing
- **WHEN** the participant saves a prompt that is empty or only spaces
- **THEN** no AI window starts

### Requirement: Nothing is lost by an automatic start
The AI window SHALL NOT start by itself when the step already has a saved answer, when its AI folder holds any file other than `prompt.md`, or when any other AI window is running. In those cases the save SHALL still succeed.

#### Scenario: A saved answer blocks the start
- **GIVEN** the step has a saved answer
- **WHEN** the participant saves a prompt
- **THEN** the prompt is saved and no AI window starts

#### Scenario: A file in the folder blocks the start
- **GIVEN** the step's AI folder holds a file the AI made
- **WHEN** the participant saves a prompt
- **THEN** the prompt is saved, the file is kept and no AI window starts

#### Scenario: Another AI window is running
- **GIVEN** an AI window for something else is running
- **WHEN** the participant saves a prompt
- **THEN** the prompt is saved and no second window starts

### Requirement: A step that is not open never starts the AI
A step that is finished, locked, or opened before setup has passed SHALL NOT start an AI window and SHALL refuse a save with the usual plain message. Source: `setup-access`; AGENTS.md rule 4.

#### Scenario: Finished step
- **GIVEN** the step is done
- **WHEN** a save is requested
- **THEN** it is refused as finished and no AI window starts

#### Scenario: Locked step
- **GIVEN** the step comes after an unfinished item
- **WHEN** a save is requested
- **THEN** it is refused as locked and no AI window starts

#### Scenario: Before setup
- **GIVEN** setup has not passed
- **WHEN** a save is requested
- **THEN** it is refused with the setup-incomplete message and no AI window starts

### Requirement: A window that will not start never loses the save
If the AI window cannot start by itself, the prompt SHALL still be saved, the page SHALL say in plain words why, and "Open a new AI chat" SHALL remain the way to try again. The automatic start SHALL count as not yet done until a window has started.

#### Scenario: Start fails
- **GIVEN** the AI cannot be started
- **WHEN** the participant saves a prompt
- **THEN** the prompt is saved and the page names the problem

#### Scenario: Try again by hand
- **GIVEN** the automatic start failed
- **WHEN** the participant presses "Open a new AI chat"
- **THEN** a window starts, the message goes away, and later saves do not start another

### Requirement: Open a new AI chat replaces the window
The step SHALL offer "Open a new AI chat" once a prompt is saved. It SHALL start a new AI process and clear the step's AI folder and any earlier answer. While a window is running it SHALL ask first, because anything the AI has not saved is lost. Only one AI window SHALL run at a time. Source: AGENTS.md rule 4.

#### Scenario: No window running
- **GIVEN** a prompt is saved and no window is running
- **WHEN** the participant presses "Open a new AI chat"
- **THEN** a new window starts at once on the chosen model

#### Scenario: Window running
- **GIVEN** a window is running
- **WHEN** the participant presses "Open a new AI chat"
- **THEN** a confirm names what is lost, and the window is replaced only after the participant agrees

#### Scenario: No prompt yet
- **GIVEN** no prompt is saved
- **WHEN** the participant looks at the control
- **THEN** it is off and the page says to save a prompt first

### Requirement: The participant pastes one text, and it is also saved
The step SHALL show the text to paste: the participant's prompt, a plain divider, the rough notes and the closing instruction, with a Copy button. The same text SHALL be saved as `prompt.md` in the step's AI folder, and a later prompt save while the window runs SHALL update that file without restarting the window.

#### Scenario: Text matches the file
- **GIVEN** a prompt is saved and the window has started
- **WHEN** the participant reads the text to paste
- **THEN** it equals the content of `prompt.md` in the AI folder and ends with the closing instruction

#### Scenario: Prompt changed while running
- **GIVEN** the window is running
- **WHEN** the participant saves a changed prompt
- **THEN** the text to paste and `prompt.md` show the new prompt and the window is not restarted

#### Scenario: Copy
- **WHEN** the participant presses Copy
- **THEN** the text is placed on the clipboard and a status line that a screen reader announces says it was copied

#### Scenario: The browser refuses
- **GIVEN** the browser refuses clipboard access
- **WHEN** the participant presses Copy
- **THEN** the text is selected and the page says to press Ctrl+C

#### Scenario: Nothing to copy yet
- **GIVEN** no prompt is saved
- **WHEN** the participant looks at the step
- **THEN** Copy is off and the page says to save a prompt first

### Requirement: The app types nothing into the AI
In a paste-flow step the app SHALL NOT type any line into the AI window, SHALL NOT answer any prompt the AI shows, and SHALL set no permission flag. The request that used to type the step's line SHALL be refused. The step SHALL be judged only from the saved answer file. Source: AGENTS.md rules 2 and 3.

#### Scenario: Nothing typed
- **WHEN** the window starts, runs and ends
- **THEN** no keystroke reaches the AI except what the participant typed or pasted

#### Scenario: Send is refused
- **WHEN** a request asks the app to type the step's line
- **THEN** it is refused as not supported and nothing is typed

### Requirement: The AI window note and words are plain
The step SHALL say that each step opens a new chat and that the window starts by itself on the first save. Every word SHALL come from the content files and follow `participant-vocabulary`: "AI window" and "your AI", never a bare "CLI", and no "Send to AI" or "Start my AI". Source: AGENTS.md rule 10.

#### Scenario: Note shown
- **WHEN** the participant opens a paste-flow step
- **THEN** the AI window head says each step opens a new chat

#### Scenario: No old buttons
- **WHEN** the content tests scan the paste-flow steps
- **THEN** none names "Send to AI", "Start my AI" or "Check my work"

### Requirement: The rule is shared by every step that pastes
The start rule, the pasted text, the folder contents and the refusals of this capability SHALL be defined once and SHALL apply to any step whose content opts in to the paste flow. Each Part SHALL state only what differs for it: what moment starts the window (Part 1: the first save of a prompt; Part 3: the first time an open step is shown), what text is pasted (Part 1: the saved prompt, a divider, the rough notes and a closing line; Part 3: the step's own line), and its own check for what a start would lose. A later change can therefore switch another Part's step to the flow by content, with only those three parts defined.

#### Scenario: A step opts in
- **GIVEN** a step's content says it uses the paste flow
- **WHEN** the participant uses it
- **THEN** the same refusals apply, the app types nothing, and the Part's own start moment, text and "nothing to lose" check apply

#### Scenario: A step that does not opt in
- **GIVEN** a step's content does not say so
- **WHEN** the participant uses it
- **THEN** it behaves exactly as before, with its typed line and its Send button

#### Scenario: Two Parts, two start moments
- **GIVEN** Part 1's `cold` step and Part 3's `build` step both use the flow
- **WHEN** the participant saves a prompt in `cold` and opens `build`
- **THEN** each window starts by itself once, under its own Part's rule, and neither Part's trigger starts the other's window
