# Spec Delta

## REMOVED Requirements

### Requirement: The mission page states the purpose and where Part 1 sits
**Reason**: Part 1's mission now follows the shared mission shape and has no map of the Parts (series review items 12 and 13). Replaced by "The Part 1 mission page follows the mission shape".
**Migration**: Remove the `you-are-here` block from `p1-mission` and the Part 1 map tests; restate the purpose in the "About this series" passage.

### Requirement: Every gap is something the AI could not have known
**Reason**: The five groups are called categories, not kinds (series review item 14a). Replaced by "Every gap is a missing category the AI could not have known".
**Migration**: Update `p1-gaps`, its activities, the typical-gaps kit file and the tests to say "categories".

### Requirement: The reveal names the example kinds and keeps frameworks as samples
**Reason**: The framework section is rebuilt as a numbered list of five categories and one table per framework (series review item 14a). Replaced by "The reveal names the five categories and keeps frameworks as samples".
**Migration**: Rebuild the `p1-frameworks` mapping and update the framework tests and the frameworks kit file.

## MODIFIED Requirements

### Requirement: Part 1 uses the app's plain-language rules
Part 1 text SHALL follow AGENTS.md rule 10 and the content rules in `docs/PHASE3.md`: "Part", never session; no mention of a presenter, facilitator, room, breakout, handout, neighbor or clock; "Script track" and "promptfoo track" where tracks are named; no suggestion of Copilot Chat in Teams; the ready-made example called the Practice task and never a submission option; "your AI" or "AI window", never a bare "CLI"; every glossary entry for a course-specific term begins "In this course,".

#### Scenario: Banned words
- **WHEN** the content tests scan the Part 1 content, kit files and glossary entries
- **THEN** no banned word, session label or contact-instruction phrase is found

#### Scenario: Glossary
- **WHEN** the participant opens the glossary after Part 1 is added
- **THEN** the ideas (prompt, prompting framework, gap) appear under "Ideas" and the course terms (cold prompt, scenario card) under "In this course"

## ADDED Requirements

### Requirement: The Part 1 mission page follows the mission shape
`p1-mission` SHALL follow `mission-lesson-shape`, with the series passage "About this series" first. That passage SHALL state the series purpose, the three reasons checking matters and the method. "The goal" SHALL say why a structured prompt gets better results and that you can use or build a framework. "What you will do" SHALL say you write a prompt in your own words first and that the Practice task is for practice only. Source: `docs/SERIES-INTENT.md`, series review items 12 and 13.

#### Scenario: No map
- **WHEN** the participant reads `p1-mission`
- **THEN** no map of the six Parts is shown

#### Scenario: The series passage and the four passages
- **WHEN** the participant reads the page
- **THEN** "About this series" comes first, then "The goal", "Why it matters to you", "What you will do" and "What you leave with"

#### Scenario: No theory yet
- **WHEN** the participant reads the page
- **THEN** it says they will write a prompt in their own words first and it names no framework

### Requirement: Every gap is a missing category the AI could not have known
`p1-gaps` SHALL teach that each gap the participant found was something the prompt never said, so the AI had no way to know it. A sort activity SHALL place typical gaps from the bundled examples under five numbered categories of missing information with feedback, and a reflection SHALL ask which category their own gap is. Source: facilitator guide "The gap buckets", series review item 14a.

#### Scenario: The sorting device is not a term
- **WHEN** the content tests scan the Part 1 lessons, steps, kit files and glossary
- **THEN** the word "bucket" appears nowhere, and no lesson title or glossary entry uses it

#### Scenario: Categories of missing information
- **WHEN** the participant opens `p1-gaps`
- **THEN** five numbered categories are shown in plain words: who the AI should act as, what exactly to produce, background it needs, limits and format, and what a good result looks like
- **AND** no framework name appears

#### Scenario: Categories, not kinds
- **WHEN** the content tests scan the Part 1 lessons, steps, kit files and glossary
- **THEN** the five groups are called "categories" wherever the text means them, and the word "kind" is not used for them

#### Scenario: Lesson titles
- **WHEN** the participant reads the course list
- **THEN** each lesson title says what the lesson gives them, in words they already understand: "What your first prompt left out", "Frameworks: ready-made labels for what a prompt needs", "Four ways a structured prompt helps you"

#### Scenario: Sorting typical gaps
- **WHEN** the participant sorts the typical gaps
- **THEN** a wrong placement shows how many are right and feedback for that item, never the full answer, and retry is unlimited

#### Scenario: Their own gap
- **WHEN** the participant writes where their own gap belongs
- **THEN** it is saved as a reflection that does not block Continue

### Requirement: The reveal names the five categories and keeps frameworks as samples
`p1-frameworks` SHALL say people have named categories of what a prompt needs and that the names are prompting frameworks. It SHALL open with a numbered list "the five categories of what a prompt needs", saying these are the five used in this course and that more exist. It SHALL then show one table per sample framework, RTCC and RISE, one row per letter in spelling order. Source: `docs/COURSE-CONTEXT.md` "Part 1", series review items 14a and 14b.

#### Scenario: The five categories
- **WHEN** the participant reads the framework section
- **THEN** a numbered list of the five categories comes first, and says they are the five this course uses and more exist

#### Scenario: One table per framework
- **WHEN** the participant reads the mapping
- **THEN** RTCC (Role, Task, Context, Constraints) and RISE (Role, Input, Steps, Expectation) each have their own table with the columns Letter, Label, What you write there and Covers category
- **AND** a letter that fits two categories shows "also touches" for the second

#### Scenario: The categories are an example
- **WHEN** the participant reads `p1-gaps` or `p1-frameworks`
- **THEN** each says the five categories are common but not a complete list, names at least one other category, and `p1-frameworks` says to build your own labels by adding the categories the task needs

#### Scenario: Samples, not rules
- **WHEN** the participant reads the lesson
- **THEN** it says the letters use common expansions that other sources define differently, that others exist (CO-STAR and RISEN are named), and that covering what the task needs matters more than the letters

#### Scenario: A skeleton, not a recommendation
- **WHEN** the lesson shows how to fill in labels
- **THEN** it shows a skeleton for each sample and says to use whichever reads clearest

#### Scenario: No CRISP
- **WHEN** the content tests scan the Part 1 lessons, steps, kit files and glossary
- **THEN** none names CRISP
