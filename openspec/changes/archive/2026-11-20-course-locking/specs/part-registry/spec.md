# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Locking stays inside a Part`
- TO: `### Requirement: Items lock in order inside a Part, and Parts lock in series order`

## MODIFIED Requirements

### Requirement: Items lock in order inside a Part, and Parts lock in series order
A lesson SHALL open when every item before it in its own Part is done or skipped, and a step SHALL open when the previous step in its own Part is done and the lesson immediately before it, if any, is done or skipped. Every item of a Part SHALL also be locked while an earlier Part is not Done or Skipped, as `course-locking` sets out. A locked item of any Part SHALL be refused for reading as well as for doing. Hands-on work in any Part SHALL follow the setup rules in `setup-access`.

#### Scenario: Parts are independent
- **GIVEN** Part 1 is Done and the participant has done nothing in Part 3
- **WHEN** they open the first lesson of Part 2
- **THEN** it opens, and Part 3's items are unchanged

#### Scenario: A later Part is locked as a whole
- **GIVEN** the participant has done nothing in Part 1
- **WHEN** they try to open the first lesson of Part 2
- **THEN** it does not open and the lock message is shown, and Part 1's items are unchanged

#### Scenario: A Part opens when the earlier ones are finished
- **GIVEN** Part 1 is Done and Part 2 is Skipped
- **WHEN** the participant opens the first lesson of Part 3
- **THEN** it opens

#### Scenario: Hands-on work before setup
- **GIVEN** setup has not passed
- **WHEN** the participant tries a step of any Part
- **THEN** it is refused the same way a Part 3 step is

#### Scenario: Reading ahead in another Part
- **GIVEN** the participant is part-way through Part 3 and has done nothing in Part 1
- **WHEN** they open a lesson or step of Part 1 that its own order still keeps locked
- **THEN** it is refused with the lock message, and no progress of either Part changes

#### Scenario: Reading ahead in the same Part
- **GIVEN** the participant is part-way through Part 3
- **WHEN** they try to open a lesson or step of Part 3 that its own order still keeps locked
- **THEN** it is refused with the lock message, and no progress changes

#### Scenario: Doing a locked item is still refused
- **GIVEN** a lesson or step is locked by its Part's order, or because an earlier Part is not finished
- **WHEN** the participant, or a direct request to the server, tries to answer, start, check, submit or complete it
- **THEN** it is refused with the plain lock message and nothing is recorded

### Requirement: Resets cover every Part's progress
Both resets SHALL clear the progress of every Part together, including every Skipped Part, and SHALL leave a fresh progress file with no step done and no Part skipped. Which files a Part keeps or moves SHALL be listed in the reset inventory for that Part.

#### Scenario: Reset lesson progress
- **GIVEN** progress exists in two Parts
- **WHEN** the participant resets lesson progress and confirms
- **THEN** both Parts show nothing done and the one backup folder holds what was moved

#### Scenario: A skipped Part is cleared
- **GIVEN** Part 1 is Skipped
- **WHEN** the participant resets lesson progress and confirms
- **THEN** Part 1 is no longer Skipped, and Part 2 is locked again
