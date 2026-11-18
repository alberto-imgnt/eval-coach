# model-discovery Specification

## Purpose

Turns the Sonnet or Haiku preference into the right launch option for each supported AI, finds an exact model ID by keyword where a tool needs one, and keeps that to a narrow, safe reading of the tool's own model list.

## Requirements

### Requirement: Launch options come from per-tool data
For each of the three supported AIs the app SHALL build the model launch option from `cli-recipes.json` data (the Sonnet and Haiku keyword, the launch arguments and a shipped fallback). There SHALL be no tool-specific logic outside that data. A command with no model data SHALL be started with no model option. Source: AGENTS.md rule 6; series review item 7.

#### Scenario: A tool that accepts an alias
- **GIVEN** the chosen AI is Claude Code and the preference is Haiku
- **WHEN** the AI window starts
- **THEN** it is started with the Haiku alias and no discovery is run

#### Scenario: A tool that needs an exact ID
- **GIVEN** the chosen AI is GitHub Copilot CLI and the preference is Sonnet
- **WHEN** the AI window starts
- **THEN** it is started with the exact Sonnet model ID the app resolved

#### Scenario: Data changes without code
- **WHEN** a keyword or fallback ID in `cli-recipes.json` is edited
- **THEN** the next AI start uses it and no code changes

#### Scenario: No permission flags
- **WHEN** the app builds any model launch option
- **THEN** it adds no permission or approval option (AGENTS.md rule 2)

### Requirement: An exact ID is found by keyword from the AI's own model list
Where a tool needs an exact ID, the app SHALL find it by keyword ("sonnet" or "haiku") in the list the tool shows for its `/model` command, taking the newest match, so IDs do not go stale and the participant never edits files. Source: series review item 7; AGENTS.md rule 3 (scoped exception).

#### Scenario: Newest match wins
- **GIVEN** the model list holds two Sonnet IDs
- **WHEN** discovery reads the list
- **THEN** the ID with the higher version is used

#### Scenario: Nothing is chosen in the list
- **WHEN** discovery has read the list
- **THEN** the process is stopped and no item was selected

#### Scenario: Not while an AI runs
- **GIVEN** an AI window is running
- **WHEN** a discovery would be needed
- **THEN** it does not start, and the shipped fallback or the saved result is used for the next start

### Requirement: Discovery runs hidden and changes nothing
Discovery SHALL run in a hidden window in its own empty folder, only when no AI window runs (AGENTS.md rule 4), and SHALL stop the process when done. It SHALL NOT select an item, answer any prompt or change any setting.

#### Scenario: Hidden and empty
- **WHEN** discovery runs
- **THEN** the participant sees no window and the folder it uses holds none of their files

#### Scenario: Settings untouched
- **WHEN** discovery has finished
- **THEN** the tool's settings and sign-in are as they were

### Requirement: The read is limited to getting an ID
The app SHALL use the text of the model list only to get a model ID. It SHALL use the text shown before the app types only to avoid typing into a question: if that text holds a word the data lists as a sign-in, trust or approval question, the app SHALL type nothing and fall back. It SHALL NOT use the text for any pass or fail, for any gate or for any check. Source: AGENTS.md rules 2 and 3.

#### Scenario: A question is on screen
- **GIVEN** the tool shows a sign-in or folder-trust question when it starts
- **WHEN** discovery looks at the screen
- **THEN** it types nothing, stops the process and uses the fallback

#### Scenario: Never a verdict
- **WHEN** discovery fails or finds nothing
- **THEN** no check, gate or step result changes

### Requirement: Failure never blocks the participant
If discovery cannot finish, is skipped, finds no match or the tool shows a layout the app does not recognize, the app SHALL use the saved result for that tool and version if there is one, otherwise the shipped fallback, and the AI SHALL still start. The participant SHALL NOT see an error for this. Source: series review item 7 ("a layout change never blocks a participant").

#### Scenario: Layout changed
- **GIVEN** the model list no longer holds a recognizable Sonnet ID
- **WHEN** the participant starts the AI
- **THEN** the AI starts with the shipped fallback

#### Scenario: Not signed in
- **GIVEN** the tool is not signed in and shows no model list
- **WHEN** the participant starts the AI
- **THEN** the AI starts with the fallback and no error is shown about the model

### Requirement: Results are saved per tool and version
The app SHALL save each discovered ID with the tool and the version of its program, and SHALL NOT run discovery again until that program changes or the participant resets the app configuration. Saved results SHALL hold only model IDs and nothing the tool printed otherwise. Source: series review item 7.

#### Scenario: Reused
- **GIVEN** an ID was found for the installed Copilot program
- **WHEN** the participant starts the AI again
- **THEN** no discovery runs and the saved ID is used

#### Scenario: Program updated
- **GIVEN** the tool's program changed since the ID was saved
- **WHEN** the participant starts the AI
- **THEN** discovery runs again

#### Scenario: Only IDs are kept
- **WHEN** the participant opens the saved results
- **THEN** they hold model IDs, the tool name and a version marker, and no screen text, account name or email

### Requirement: The hidden window does not show or keep account details
Discovery SHALL NOT show the hidden window to the participant, SHALL NOT write the tool's screen text to any file, and SHALL NOT send it anywhere. Source: AGENTS.md rule 5 and the sensitive-items section.

#### Scenario: Nothing written
- **WHEN** discovery has finished
- **THEN** the only file it wrote is the saved result with the model ID, and its scratch folder holds no screen text
