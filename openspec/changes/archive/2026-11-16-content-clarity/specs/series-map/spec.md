# Spec Delta

## REMOVED Requirements

### Requirement: Series map words live in content
**Reason**: The requirement tied the Series map to the maps inside the mission lessons, which are removed (series review item 12). Replaced by "Series map words live in content and are the only list of the Parts".
**Migration**: Remove the content tests that compare Series map names and outcomes with the mission maps.

## ADDED Requirements

### Requirement: Series map words live in content and are the only list of the Parts
All text on the Series map, including Part names, outcomes, labels, the intro line and the Back control, SHALL come from the content files and follow the app's plain-language rules (the word "Part", no presenter or classroom words). No mission lesson lists the Parts, so the Series map holds the only copy of the names and outcomes.

#### Scenario: Banned words
- **WHEN** the content tests run
- **THEN** no Series map text contains a banned word

#### Scenario: One place for the names
- **WHEN** the content tests scan the mission lessons
- **THEN** none lists the Part names

### Requirement: The Series map intro is about doing the work yourself
The intro line of the Series map SHALL say there are six Parts and one method, and that the participant does each Part themselves because copying someone else's prompt or rules gives their answers, not the skill to check your own. It SHALL NOT say to look ahead and SHALL NOT mention Stage 3. Source: series review item 19.

#### Scenario: The intro
- **WHEN** the participant opens the Series map
- **THEN** the intro reads in plain words, in one or two sentences, that each Part is to be done by the participant

#### Scenario: No look ahead, no Stage 3
- **WHEN** the content tests scan the Series map intro
- **THEN** it contains neither "look ahead" nor "Stage 3"
