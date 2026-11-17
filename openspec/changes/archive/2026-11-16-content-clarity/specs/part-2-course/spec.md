# Spec Delta

## REMOVED Requirements

### Requirement: The mission page states the purpose and where Part 2 sits
**Reason**: Part 2's mission now follows the shared mission shape and has no map of the Parts (series review items 12 and 13). Replaced by "The Part 2 mission page follows the mission shape".
**Migration**: Remove the `you-are-here` block from `p2-mission` and the Part 2 map and agreement tests.

### Requirement: Part 2 points to the participant's own repeating work without a task of their own
**Reason**: The ready-made example is called the Practice task in participant text (series review item 16). Replaced by the requirement of the same meaning under a new name.
**Migration**: Update the `p2-testfile` reflection text and the finished screen to say "Practice task".

## MODIFIED Requirements

### Requirement: Part 2 uses the app's plain-language rules
Part 2 text SHALL follow AGENTS.md rule 10 and the content rules in `docs/PHASE3.md`: "Part", never session; no mention of a presenter, facilitator, room, breakout, handout, neighbor or clock; no suggestion of Copilot Chat in Teams; the ready-made example called the Practice task and never a submission option; "your AI" or "AI window", never a bare "CLI"; every glossary entry for a course-specific term begins "In this course,".

#### Scenario: Banned words
- **WHEN** the content tests scan the Part 2 content, kit files and glossary entries
- **THEN** no banned word, session label or contact-instruction phrase is found

#### Scenario: Glossary
- **WHEN** the participant opens the glossary after Part 2 is added
- **THEN** the ideas (test case, format check, content check, supporting list, script test) appear under "Ideas" and the course term (worksheet) under "In this course"

### Requirement: The finished screen says what they hold and what comes next
When Part 2 is finished the screen SHALL say what the participant can now do (turn requirements into distinct criteria, give each a threshold a script could decide, and record them as test cases), where their file is in the project folder, and that Part 3 turns a file like this into a checker. It SHALL say the Practice task file is practice and is not something to submit.

#### Scenario: Finished
- **WHEN** the participant finishes Part 2
- **THEN** the screen names the file, says what they can now do and what Part 3 does with it

## ADDED Requirements

### Requirement: The Part 2 mission page follows the mission shape
`p2-mission` SHALL follow `mission-lesson-shape`. "The goal" SHALL open on Part 1's question (how do you know the second answer is better?), answer it, and state the goal. "What you will do" SHALL say nothing is run in this Part and that the Practice task is for practice only. It SHALL NOT repeat the series framing. Source: `docs/SERIES-INTENT.md`, series review items 12 and 13.

#### Scenario: No map
- **WHEN** the participant reads `p2-mission`
- **THEN** no map of the six Parts is shown

#### Scenario: The four passages
- **WHEN** the participant reads the page
- **THEN** "The goal", "Why it matters to you", "What you will do" and "What you leave with" appear in that order, and "Why it matters to you" is about writing rules down before judging an answer

#### Scenario: The question from Part 1
- **WHEN** the participant reads the opening of the page
- **THEN** it asks how you know the second answer is better, and says the answer is rules written down before looking

#### Scenario: Nothing is run
- **WHEN** the participant reads the page
- **THEN** it says Part 2 runs nothing, and that running the rules on real answers starts in Part 3

### Requirement: Part 2 points to the participant's own repeating work and says the Practice task is practice
`p2-testfile` SHALL include one optional reflection asking which task of their own repeats, has clear requirements and could be checked by rules, and SHALL say the Practice task is for practice only and cannot be submitted. The reflection SHALL NOT block Continue and SHALL NOT mention office hours, discussions, people or places.

#### Scenario: Optional reflection
- **WHEN** the participant reads the lesson's activities
- **THEN** the own-work reflection is marked optional and is saved if answered

#### Scenario: The Practice task is practice
- **WHEN** the participant reads the lesson or the finished screen
- **THEN** it says the Practice task is a ready-made example and not something to submit
