# part-registry Specification

## Purpose

Lets the app hold the course, content and saved progress of more than one Part of the series, so a new Part is added by content and a registry entry, and Part 3 and the participant's saved progress are never disturbed.

## Requirements

### Requirement: Each Part with content has its own course
Each Part with content SHALL have one ordered list of lessons and steps, its own lesson content and its own step content, and its own saved step progress. Part 3's list, content and progress SHALL stay exactly as they are. Source: `docs/SPEC.md` "Series map" ("a Part is switched on by adding its content").

#### Scenario: Part 3 is unchanged
- **WHEN** the course of Part 3 is read after this change
- **THEN** it holds the same lessons and steps in the same order, with the same statuses, gates, routes and files as before

#### Scenario: A second Part
- **GIVEN** a Part is registered with its own lessons and steps
- **WHEN** the participant opens that Part
- **THEN** its lessons and steps are listed in its own order, and its progress counts only its own items

### Requirement: An id belongs to exactly one Part
A lesson or step id SHALL name one item in one Part. Two Parts SHALL NOT share an id, and the app SHALL refuse to start when they do. Every route that takes a lesson or step id SHALL find the Part from the id.

#### Scenario: Duplicate id
- **GIVEN** two Parts both contain a lesson or step with the same id
- **WHEN** the app loads its content
- **THEN** it prints the duplicate and exits instead of starting

#### Scenario: No selector needed
- **WHEN** the page asks for a lesson, an activity answer or a step by id
- **THEN** the right Part's item is returned without the request naming the Part

### Requirement: State can be read for a chosen Part
`GET /api/state` SHALL accept an optional Part selector and, when it is absent, SHALL describe Part 3. When the request names a step, the Part SHALL be the step's. For the chosen Part, the lists of steps, the course list, the current step, the current item and the step detail SHALL describe that Part. The Series state SHALL describe every Part with content.

#### Scenario: Default Part
- **WHEN** the page asks for state with no selector and no step
- **THEN** the response describes Part 3 exactly as before

#### Scenario: Chosen Part
- **WHEN** the page asks for state with a registered Part selector
- **THEN** the course list, steps and current item are that Part's

#### Scenario: Unknown Part
- **WHEN** the selector names a Part that is not registered
- **THEN** the request is refused with a plain message and nothing changes

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

### Requirement: Earlier saved progress loads unchanged
A `progress.json` or `pending-lessons.json` written before this change SHALL load without error and without being rewritten until something changes. Part 3's keys SHALL keep their places. A Part with no saved progress SHALL start from its defaults the first time it is used.

#### Scenario: Old progress
- **GIVEN** a `progress.json` with no record for any other Part
- **WHEN** the project is opened
- **THEN** it loads, Part 3 shows the same progress, and the file is byte-identical until the participant does something

#### Scenario: First use of another Part
- **WHEN** the participant first saves progress in another Part
- **THEN** that Part's progress is saved under its own key and Part 3's keys are untouched

#### Scenario: Corrupt Part block
- **GIVEN** a Part's saved block has the wrong shape
- **WHEN** the project is opened
- **THEN** the participant sees the same plain "progress cannot be read" message as for any corrupt progress file, and no file is changed

### Requirement: Lesson progress, review and early progress are shared
Lesson progress, learning records, the shuffle seed, placement answers and the review queue SHALL be kept once for the whole participant. A review sitting SHALL mix due items from every Part. Course progress made before a project exists SHALL be kept in one `pending-lessons.json` and merged into the project when it is set up. Saved progress that names a lesson id no longer in any Part SHALL be dropped as before.

#### Scenario: Review across Parts
- **GIVEN** retrieval items from lessons in two Parts are due
- **WHEN** the review sitting is built
- **THEN** items from both Parts can appear, and consecutive items come from different lessons when possible

#### Scenario: Pending progress
- **GIVEN** the participant read a first lesson before a project existed
- **WHEN** the project is set up
- **THEN** that lesson's record is merged as before, whatever Part it belongs to

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

### Requirement: A Part on the Series map must be registered
Every Part the Series map marks as having content SHALL be registered, and every registered Part SHALL appear on the Series map. Its name and lesson list SHALL come from its own content.

#### Scenario: Mismatch
- **GIVEN** the Series map marks a Part as having content but no Part is registered for it, or the reverse
- **WHEN** the content tests run
- **THEN** a test fails and names the Part

### Requirement: A Part may register a restart plan
A Part MAY register a restart plan naming, for each of its steps, the saved record and files the step owns. Parts 1 and 2 SHALL register one; Part 3 SHALL NOT, and the app SHALL offer no restart and refuse a request for it. Every file a restart moves SHALL be on the reset inventory, and the content tests SHALL fail when a file a restart can move is on no list. Source: series review item 11; `step-restart`.

#### Scenario: Part with a plan
- **WHEN** the participant opens a finished step of Part 1 or Part 2
- **THEN** the step's state says a restart is available

#### Scenario: Part without a plan
- **WHEN** the participant opens a finished Part 3 step
- **THEN** the step's state says no restart is available and a restart request is refused

#### Scenario: Inventory coverage
- **GIVEN** a restart plan names a file that is on no reset list
- **WHEN** the tests run
- **THEN** a test fails and names the file
