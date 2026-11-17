# participant-vocabulary Specification

## Purpose

Keeps the words participants read for the AI tool and the ready-made example plain and consistent: "your AI" and "AI window" instead of "CLI", "Practice task" instead of "Northwind", so a non-technical reader never meets a term they have not been told.

## Requirements

### Requirement: Participants read "your AI" and "AI window", not "CLI"
Every text a participant reads (lessons, steps, glossary, setup and Settings text, interface labels, messages and tooltips) SHALL say "your AI" or "AI window" where it would otherwise say "CLI". Vendor product names (GitHub Copilot CLI, Devin CLI) SHALL stay as they are. Code, specs, ids, file names and `cli-recipes.json` keys MAY keep "CLI". Source: series review item 15, AGENTS.md rule 10.

#### Scenario: No bare CLI
- **WHEN** the content tests scan every string in `content/*.json`, the interface strings in `web/` and the bundled kit files
- **THEN** the word "CLI" appears only inside a vendor product name or in the glossary entry for "AI window"

#### Scenario: Product names stay
- **WHEN** the participant reads the list of supported tools
- **THEN** it shows "GitHub Copilot CLI" and "Devin CLI" unchanged

#### Scenario: Buttons and labels
- **WHEN** the participant reads a button, status line or hint that used to say "CLI"
- **THEN** it says "AI window" or "your AI" with the same meaning, for example "Start my AI" and "Send to AI"

### Requirement: The glossary explains the AI window
The glossary SHALL have an entry "AI window" under "In this course". It SHALL say the AI window is the terminal inside the app where the participant's own AI tool runs, that each new chat starts a new AI window process, and that the participant stays in control of what the AI tool does. It SHALL NOT use the word "CLI" except in a product name. Source: series review item 15.

#### Scenario: Entry exists
- **WHEN** the participant opens the glossary
- **THEN** "AI window" is listed with a plain meaning and no "CLI" outside a product name

#### Scenario: Old entry gone
- **WHEN** the content tests load the glossary
- **THEN** no entry is titled "CLI"

### Requirement: The ready-made example is called the Practice task
What a participant reads SHALL call the ready-made example the "Practice task" and SHALL say once, where it is first offered, that it is a ready-made example used for practice and is never something to submit. The other option SHALL be called "My own task". The scenario's own client name inside example text, ids, folders and kit files SHALL stay unchanged. Source: series review item 16, AGENTS.md rule 7.

#### Scenario: No Northwind outside the scenario
- **WHEN** the content tests scan lesson text, step text, glossary, setup text and interface labels
- **THEN** "Northwind" appears only inside example data or sources that quote the example itself, and nowhere as the name of an option or choice

#### Scenario: The explanation
- **WHEN** the participant is offered the Practice task
- **THEN** the text says everything is provided, so there is nothing to bring, and that it is for practice only

#### Scenario: Never a submission
- **WHEN** the content tests scan the content
- **THEN** nothing offers the Practice task as a submission

### Requirement: The two words are covered by tests that cannot be skipped
The content tests SHALL fail when "CLI" appears outside a vendor product name or the glossary entry, and when "Northwind" appears as an option name in participant-visible text. The list of allowed places SHALL live in the test, not in the content. Source: series review items 15 and 16.

#### Scenario: A new bare CLI is caught
- **WHEN** a content string is changed to include "your CLI"
- **THEN** the content tests fail and name the file and the string

#### Scenario: Allowed uses are explicit
- **WHEN** the tests run
- **THEN** each allowed use is a named exception with a reason
