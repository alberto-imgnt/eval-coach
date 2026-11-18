# course-structure Specification

## Purpose
Organizes the course around the method of judging AI work, one transferable concept per lesson, with the procedure of this course carried by the steps, so the lessons follow the series intent and not the app's own workflow.

## Requirements

### Requirement: Lessons follow the method, one concept each
The Part 3 course SHALL have seven lessons, each teaching one concept, in the order of the series method (ask clearly, know what you need, turn it into rules, score the result, improve, keep a record). Other Parts list their own lessons in their own specs (Part 1: `part-1-course`). Source: the series intent notes (local reference) "What you will learn".

#### Scenario: Seven lessons
- **WHEN** the Part 3 course content is loaded
- **THEN** it holds exactly these lessons in this order: `mission` (purpose and map), `hook` (a fixed rule beats an AI opinion), `several-runs` (one answer proves little), `rules` (turn "looks good" into a rule, and what a rule cannot check), `trust` (test the checker before trusting it), `surprise` (read a surprise, fix the spec and not the checker) and `baseline-why` (the baseline, what a score means, what comes next)
- **AND** each has one stated concept in its `win` line

#### Scenario: Method position
- **WHEN** the participant opens a lesson after the mission
- **THEN** its opening line says which link of the method it covers

### Requirement: Lessons and steps interleave in a fixed order
The course order SHALL be: `mission`, `hook`, `several-runs`, step `generate`, `rules`, step `build`, `trust`, steps `fixtures` (and `fixtures-config` on the promptfoo track), `readback`, `predict`, `key`, then `surprise`, steps `run`, `fix`, then `baseline-why` and step `baseline`. A step SHALL unlock when the previous step is done and the lesson immediately before it, if any, is done or skipped. The nine steps, their gates and their results SHALL NOT change.

#### Scenario: Step after lesson
- **GIVEN** `several-runs` is not done or skipped
- **WHEN** the participant tries to open the `generate` step
- **THEN** it is locked and the message names that lesson

#### Scenario: Steps with no lesson before them
- **GIVEN** the `run` step is done
- **WHEN** the participant opens the `fix` step
- **THEN** it unlocks without a lesson in between

### Requirement: The procedure lives in the steps
The roles of the two chats, the blind folder, the number of runs, the checker file layout, the order of the fixture steps, the answer-key timing and exit codes SHALL be explained in the text of the step that does them, with the reason in a clause, and SHALL NOT be taught in a lesson beyond the budget in `method-over-mechanics`.

#### Scenario: Blind folder in the generate step
- **WHEN** the participant opens the `generate` step
- **THEN** its text says the folder holds only the prompt, with the reason that a model that can read the tests could write to them

#### Scenario: Not in the lesson
- **WHEN** the participant reads `several-runs`
- **THEN** it teaches that several answers beat one and does not describe the two chat roles

### Requirement: Mechanics-only activities are removed, concept activities stay
Activities that test only this course's mechanics, and the review questions that only test them, SHALL be removed. Every explain-it activity and every concept activity SHALL stay, moved under its new lesson (the full list is in design D8).

#### Scenario: Removed activity
- **WHEN** the content tests list the activity ids
- **THEN** none of `loop-order`, `loop-actors`, `generate-fair`, `generate-try`, `rules-demo`, `rules-anatomy`, `build-first-look`, `verify-order`, `verify-try` and `compare-exit` is present

#### Scenario: Tier 1 explain-it kept
- **WHEN** the content tests list the activity ids
- **THEN** `hook-explain`, `build-explain`, `choices-explain-tech`, `baseline-explain` and `baseline-explain-write` are present, each under a lesson that teaches the idea it asks about

#### Scenario: Concept activities kept
- **WHEN** the content tests list the activity ids
- **THEN** every other activity id from the earlier course is present under its new lesson

#### Scenario: Continue
- **WHEN** a lesson loses an activity
- **THEN** it still has at least one activity or review question, and no activity holds back Continue that did not before

### Requirement: Saved progress survives the restructure
Saved progress that names a lesson no longer in the course SHALL load without error. The removed lesson's record SHALL be dropped, completed steps SHALL be kept, and a new lesson that comes before the participant's furthest completed step SHALL be recorded as skipped and migrated, so it blocks nothing and schedules no review. Review items whose question left the content SHALL be ignored.

#### Scenario: Old progress
- **GIVEN** a `progress.json` with records for `loop` and `generate-why` and the `generate` step done
- **WHEN** the project is opened
- **THEN** it loads without error, the `generate` step is still done and `several-runs` is skipped and migrated

#### Scenario: Pending mission progress
- **GIVEN** `pending-lessons.json` holds only the `mission` lesson
- **WHEN** the project is set up
- **THEN** the mission record is merged as before

### Requirement: No dangling references
Every glossary `lesson` reference, every lesson `related` entry and every `sources` or `primary_source` reference SHALL name a lesson or bundled file that exists after the restructure, and no bundled course file SHALL be left that no lesson, step or test uses.

#### Scenario: Glossary links
- **WHEN** the content tests resolve every glossary lesson reference
- **THEN** each names one of the seven lessons

#### Scenario: Orphan files
- **WHEN** the content tests list the bundled lesson files
- **THEN** each is cited by a lesson, a step or a test

### Requirement: Lessons stay short
Each lesson SHALL have a body of no more than 300 words, except a Part's first lesson (`mission`, `p1-mission`, `p2-mission`), which SHALL have no more than 450 words, and a Part's last lesson that also carries a closing orientation passage (`baseline-why`, `p1-benefits`, `p2-testfile`), which SHALL have no more than 400 words. Lessons are in plain language with no code.

#### Scenario: Word cap
- **WHEN** the content tests count each lesson body
- **THEN** none exceeds its cap
