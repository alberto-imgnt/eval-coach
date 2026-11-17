# part-1-course Specification

## Purpose

Defines what the Part 1 course (structured prompting) teaches and in what order, so a participant who never attended a live session still reaches the same knowledge and outcomes: why structure gets better results, what a framework is, and how to use or build one.

## Requirements

### Requirement: Part 1 has four lessons and five steps in a fixed order
The Part 1 course SHALL be, in this order: lesson `p1-mission`, step `cold`, step `score`, lesson `p1-gaps`, lesson `p1-frameworks`, step `rewrite`, step `rescore`, lesson `p1-benefits`, step `own`. Locking follows `part-registry`: a step opens when the previous step is done and the lesson immediately before it, if any, is done or skipped. Source: `docs/COURSE-CONTEXT.md` "Part 1: structured prompting".

#### Scenario: Order
- **WHEN** the Part 1 course list is read
- **THEN** it holds exactly those nine items in that order, with lessons and steps in the same list

#### Scenario: A step after a lesson
- **GIVEN** `p1-frameworks` is not done
- **WHEN** the participant tries to open the `rewrite` step
- **THEN** it is locked and the message names that lesson

#### Scenario: First lesson before setup
- **GIVEN** setup has not passed
- **WHEN** the participant opens `p1-mission`
- **THEN** it works as normal, because it has no hands-on exercise

### Requirement: Part 1 teaches the why, not a recommended framework
Part 1 SHALL teach why structure gets better results and that the participant can use an existing framework or build their own. It SHALL NOT recommend one framework, choose one for the participant, teach what every letter means in depth, or measure prompt quality. Source: facilitator guide "Purpose and expected outcomes".

#### Scenario: No recommendation
- **WHEN** the content tests scan Part 1 lessons, steps and glossary entries
- **THEN** none says one framework is best, better, recommended or the one to use

#### Scenario: Neutral choice
- **WHEN** the participant reaches the rewrite
- **THEN** every framework option is offered with the same amount of text and none is pre-selected

### Requirement: Discovery comes before theory
Everything the participant reads or does before the reveal (`p1-mission`, `cold`, `score`, `p1-gaps`) SHALL NOT name a prompting framework or use the word "framework". The names RTCC, RISE, CO-STAR and RISEN SHALL first appear in `p1-frameworks`. The sample framework prompts SHALL be reachable only after the `rescore` step is done, because seeing them earlier would replace the participant's own discovery.

#### Scenario: Before the reveal
- **WHEN** the content tests scan `p1-mission`, `cold`, `score` and `p1-gaps`, including their sources
- **THEN** none contains a framework name or the word "framework"

#### Scenario: Samples held back
- **GIVEN** the participant has not finished `rescore`
- **WHEN** they open the lessons and files that are open to them
- **THEN** no lesson source, activity or glossary entry shows a sample framework prompt

#### Scenario: Samples after
- **GIVEN** `rescore` is done
- **WHEN** the participant reads `p1-benefits`
- **THEN** it cites the two sample prompts for the same task

### Requirement: Gaps that are not missing input are set aside
`p1-gaps` SHALL say that invented details, judging overall quality and answers that change from one try to the next are real, but belong to evaluation in later Parts, and SHALL offer a "set aside" group in the sort for such items. Source: facilitator guide "If a gap isn't missing context".

#### Scenario: Set-aside group
- **WHEN** the typical gaps are shown
- **THEN** at least one is an invented detail or a quality judgment, and the right place for it is the set-aside group

#### Scenario: Plain reason
- **WHEN** the participant reads the set-aside passage
- **THEN** it says these are held for later Parts and gives no answer to them here

### Requirement: The benefits come from structure, in four named benefits
`p1-benefits` SHALL name four benefits and tie each to what the participant saw: completeness (the AI guesses less), better first results (fewer rounds), easier fixes (the labels show which part to change) and repeatability (the same structure works next time and teammates can follow it). It SHALL state the takeaway "Give the AI what it needs. Use a framework, or build your own."

#### Scenario: Four benefits
- **WHEN** the participant reads the lesson
- **THEN** all four benefits are named, each with a sentence that points back to the cold and rewrite runs

#### Scenario: Structure, not letters
- **GIVEN** `rescore` is done
- **WHEN** the participant reads the two sample prompts for the same task side by side
- **THEN** the lesson says both hold the same information under different labels, so the benefit comes from structure and not from a particular framework

#### Scenario: Takeaway
- **WHEN** the participant reaches the takeaway
- **THEN** it is stated in those words

### Requirement: Explain-it activities for two audiences
`p1-benefits` SHALL include a written explanation of why a framework helps, addressed to a colleague who is not technical (a reflection of at least 20 words), and a question for a technical reader (for example why the same structure works whichever labels are used). Neither SHALL block Continue. Source: `docs/IMPLEMENTATION-PLAN.md` "Learning priorities", tier 1.

#### Scenario: Plain-words explanation
- **WHEN** the participant writes the explanation
- **THEN** it is saved, and Continue is never held back by it

### Requirement: The lesson leads into Part 2
The closing passage of `p1-benefits`, before the optional note, SHALL say real work does not come with a card of requirements and ask how the participant knows the second answer is better, without answering it. Source: `docs/COURSE-CONTEXT.md` "The question that leads into Part 2".

#### Scenario: Open question
- **WHEN** the participant reaches the end of `p1-benefits`
- **THEN** the question is asked and is not answered in the lesson
- **AND** the lesson says the before and after prompts and outputs are saved in the project for Part 2

#### Scenario: Finished
- **WHEN** the participant finishes Part 1
- **THEN** the screen says what they can do now and that Part 2 turns "that looks good" into clear pass or fail rules

### Requirement: Part 1 lessons follow the same shape as Part 3's
Each Part 1 lesson after the mission SHALL open with "In the method." then "The idea.", then any short labelled passages, and keep this course's own mechanics to one "How this course does it" passage of at most 120 words that says other approaches exist. Bodies SHALL stay within the caps in `course-structure`. Source: `method-over-mechanics`.

#### Scenario: Shape
- **WHEN** the content tests scan the Part 1 lessons after the mission
- **THEN** each opens with "In the method." then "The idea.", and none exceeds its cap
- **AND** each has an activity, two review questions, bundled sources and a primary source

#### Scenario: Not the only way
- **WHEN** a lesson names a course-specific practice (a separate chat per run, a folder holding only the prompt, the file names)
- **THEN** it is under "How this course does it" and says other approaches work too

#### Scenario: Nothing blocks Continue
- **WHEN** a Part 1 lesson has questions or reflections
- **THEN** the participant can continue without answering them

### Requirement: Part 1 gives one optional Stage 3 note
`p1-benefits` SHALL end with one optional note of at most 60 words that says the Prompt Stage 3 asks for is a structured prompt like the one built here, that the program's own instructions decide what to submit, and that nothing in the note is needed to finish the Part. It SHALL NOT block Continue, score a submission, give submission steps, or carry a link, address or date. Source: `docs/SERIES-INTENT.md` "How this connects to Stage 3 certification".

#### Scenario: The note
- **WHEN** the participant reads the note
- **THEN** it names the Prompt, says the program decides what to submit, and is marked optional

#### Scenario: No other Stage 3 wording
- **WHEN** the content tests scan the other Part 1 lessons, steps, glossary entries and interface text
- **THEN** none names Stage 3 or certification

### Requirement: Part 1 uses the app's plain-language rules
Part 1 text SHALL follow AGENTS.md rule 10 and the content rules in `docs/PHASE3.md`: "Part", never session; no mention of a presenter, facilitator, room, breakout, handout, neighbor or clock; "Script track" and "promptfoo track" where tracks are named; no suggestion of Copilot Chat in Teams; the ready-made example called the Practice task and never a submission option; "your AI" or "AI window", never a bare "CLI"; every glossary entry for a course-specific term begins "In this course,".

#### Scenario: Banned words
- **WHEN** the content tests scan the Part 1 content, kit files and glossary entries
- **THEN** no banned word, session label or contact-instruction phrase is found

#### Scenario: Glossary
- **WHEN** the participant opens the glossary after Part 1 is added
- **THEN** the ideas (prompt, prompting framework, gap) appear under "Ideas" and the course terms (cold prompt, scenario card) under "In this course"

### Requirement: Part 1 stands alone as a self-paced course
Everything a live group did together SHALL be carried by the app: what other people typically notice is shown from bundled examples, the other framework is shown as a bundled sample after the rewrite, and the compare questions are answered in writing. No Part 1 text SHALL depend on another person being present.

#### Scenario: Typical gaps
- **WHEN** the participant is in `p1-gaps`
- **THEN** the typical gaps shown come from a bundled file and are labelled as typical, not as other participants' data

#### Scenario: Compare questions
- **WHEN** the participant reaches `rescore`
- **THEN** the two compare questions are asked in the form and answered in writing

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
