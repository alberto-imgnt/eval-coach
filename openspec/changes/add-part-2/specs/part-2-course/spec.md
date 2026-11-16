# Spec Delta

## Purpose

Defines what the Part 2 course (defining evaluation criteria) teaches and in what order, so a participant who never attended a live session still reaches the same knowledge and outcomes: turning requirements into distinct criteria, giving each a pass or fail threshold a script could decide, and writing them down as test cases.

## ADDED Requirements

### Requirement: Part 2 has four lessons and four steps in a fixed order
The Part 2 course SHALL be, in this order: lesson `p2-mission`, lesson `p2-criteria`, step `draft`, lesson `p2-thresholds`, step `thresholds`, lesson `p2-testfile`, step `test-file`, step `reference`. Locking follows `part-registry`. Source: `docs/COURSE-CONTEXT.md` "Part 2: defining evaluation criteria".

#### Scenario: Order
- **WHEN** the Part 2 course list is read
- **THEN** it holds exactly those eight items in that order, with lessons and steps in the same list

#### Scenario: A step after a lesson
- **GIVEN** `p2-thresholds` is not done
- **WHEN** the participant tries to start the `thresholds` step
- **THEN** it is locked and the message names that lesson, though its text can still be read as a preview

#### Scenario: First lesson before setup
- **GIVEN** setup has not passed
- **WHEN** the participant opens `p2-mission`
- **THEN** it works as normal, because it has no hands-on exercise

#### Scenario: Parts are independent
- **GIVEN** the participant has done nothing in Part 1 or Part 3
- **WHEN** they open `p2-mission`
- **THEN** it opens, and no other Part's items change

### Requirement: The mission page states the purpose and where Part 2 sits
`p2-mission` SHALL be one page with no activities and no review questions. It SHALL state the Part's goal (turn "that looks good" into rules a script could check), that nothing is run in this Part, the series purpose, why checking matters, the method and the Northwind update as practice only. It SHALL open on Part 1's question, how you know the second answer is better, and answer it: by writing down what good means. Source: `docs/SERIES-INTENT.md`.

#### Scenario: Map
- **WHEN** the participant reads the map on `p2-mission`
- **THEN** six rows are numbered 1 to 6, Part 2 is marked as where they are, Part 1 as before, and Parts 3 to 6 as next

#### Scenario: Names agree with the Series map
- **WHEN** the content tests run
- **THEN** each Part's name on this map equals its name on the Series map, and the outcomes of Parts 1 to 5 equal its lines

#### Scenario: The question from Part 1
- **WHEN** the participant reads the opening of the page
- **THEN** it asks how you know the second answer is better, and says the answer is rules written down before looking

#### Scenario: Nothing is run
- **WHEN** the participant reads the page
- **THEN** it says Part 2 runs nothing, and that running the rules on real answers starts in Part 3

### Requirement: A criterion traces to a requirement, and the set covers format and content
`p2-criteria` SHALL teach that a criterion is one thing a good answer must do, that each one traces to a stated requirement, that the set covers both format (how it looks) and content (what it says), and that no two criteria check the same thing. It SHALL ask for at least three criteria with at least one on content. Source: `docs/COURSE-CONTEXT.md` "Part 2" rules.

#### Scenario: Format and content named
- **WHEN** the participant reads the lesson
- **THEN** format and content are defined in plain words with one example of each from the Northwind update

#### Scenario: Worked examples
- **WHEN** the participant reads the worked examples
- **THEN** exactly two criteria are modelled, one format (the length) and one content (the blocker and the ask), each with a passing and a failing sample text
- **AND** no other Northwind criterion appears in the lesson

#### Scenario: Sorting requirements
- **WHEN** the participant sorts example criteria into format and content
- **THEN** a wrong placement shows how many are right and feedback for that item, never the full answer, and retry is unlimited

#### Scenario: Two checks of one thing
- **WHEN** the participant reads the duplicate passage
- **THEN** it shows two criteria that check the same thing worded differently and says to keep one

### Requirement: A threshold is a rule a script could decide
`p2-thresholds` SHALL teach the script test (could a script decide this with no human judgment; if not, tighten it), that vague words such as "clear", "good" and "concise" become a number, a keyword or a label, and the two patterns that carry to any task: the structure pattern (the prompt asks for fixed labels and the threshold checks they exist) and the required-term pattern (a key fact from the input appears). Source: `docs/COURSE-CONTEXT.md` "Thresholds".

#### Scenario: Vague to checkable
- **WHEN** the participant reads the lesson
- **THEN** at least three vague words are each turned into a number, a term or a label, in plain examples

#### Scenario: Predict the verdict
- **WHEN** the participant uses the practice lab
- **THEN** they predict whether sample texts pass or fail the model thresholds, and the lab shows each verdict and the reason
- **AND** the lab includes a polished text that passes the format rules and fails the content rule

#### Scenario: Patterns
- **WHEN** the participant reads the patterns
- **THEN** the structure pattern is named as the one that works for any task and links an instruction in the prompt to a criterion, and the required-term pattern is named second

### Requirement: Rules cannot check everything, and the lesson says so
`p2-thresholds` SHALL say that some qualities, such as tone, can only be roughly checked with a proxy (a list of words to avoid), that a proxy can pass an answer that misses the point, and that a rule which cannot judge a quality is marked "Not checked" and not pretended. Source: `docs/SERIES-INTENT.md` "What to keep in mind".

#### Scenario: Tone as a proxy
- **WHEN** the participant reads the passage
- **THEN** it uses tone as the example of a proxy, says the list is the participant's own to write for their own task, and does not print the Northwind banned list

#### Scenario: Not checked
- **WHEN** the participant reads the passage
- **THEN** it says that when a rule cannot judge something the honest answer is "Not checked", with a plain reason

### Requirement: The Northwind reference is held until the file is done
Everything the participant reads or does before the `reference` step SHALL NOT show the Northwind reference criteria beyond the two worked examples, their thresholds or the Northwind banned list. The `reference` step SHALL show them only after `test-file` is done, so the participant drafts their own criteria first. Source: facilitator reference tables in the live materials; AGENTS.md rule 9 (the same discovery-before-reveal habit).

#### Scenario: Before the reveal
- **WHEN** the content tests scan the `p2-` lessons, the steps' words, the glossary and the interface text
- **THEN** no reference criterion other than the two worked examples, no reference threshold and no banned word from the Northwind list appears

#### Scenario: The reveal
- **GIVEN** `test-file` is done
- **WHEN** the participant opens `reference`
- **THEN** the reference criteria are shown beside the participant's own

#### Scenario: Previews hide it
- **GIVEN** `test-file` is not done
- **WHEN** the participant opens the `reference` step as a read-only preview
- **THEN** the preview shows the step's words and no reference criterion

### Requirement: Explain-it activities for two audiences
`p2-thresholds` SHALL include a written explanation, addressed to a colleague who is not technical, of why a word like "clear" cannot be checked and what to write instead (a reflection of at least 20 words), and a question for a technical reader (for example why a keyword check is only a proxy, or why a label threshold links the prompt to the rules). Neither SHALL block Continue. Source: `docs/IMPLEMENTATION-PLAN.md` "Learning priorities", tier 1.

#### Scenario: Plain-words explanation
- **WHEN** the participant writes the explanation
- **THEN** it is saved, and Continue is never held back by it

#### Scenario: Technical reader
- **WHEN** the participant reaches the technical question
- **THEN** every option has the same number of words

### Requirement: The test case file lesson says why the file matters
`p2-testfile` SHALL show the test case file's parts (test input, criteria with ID, requirement, type and threshold, supporting lists), say that a threshold points at a list that lives in the same file, and say that the file is the input to Part 3, where an agent turns it into a checker. It SHALL say writing the rules down before any answer is judged keeps a score honest, and that other file formats can hold the same rules.

#### Scenario: File parts
- **WHEN** the participant reads the lesson
- **THEN** the parts of the file are shown with one short example criterion

#### Scenario: Lists live in the file
- **WHEN** the participant reads the supporting-list passage
- **THEN** it says a banned or required list is written by them for their own task and stored in the same file so the check stays runnable

#### Scenario: Hand-off to Part 3
- **WHEN** the participant reaches the end of the lesson
- **THEN** it says Part 3 turns a file like this into a checker and runs it on real answers, and that the file is saved in the project folder

### Requirement: Part 2 lessons follow the same shape as Parts 1 and 3
Each Part 2 lesson after the mission SHALL open with "In the method." then "The idea.", then any short labelled passages, and keep this course's own mechanics to one "How this course does it" passage of at most 120 words that says other approaches exist. Bodies SHALL stay within the caps in `course-structure`. No lesson SHALL be skippable. Source: `method-over-mechanics`.

#### Scenario: Shape
- **WHEN** the content tests scan the Part 2 lessons after the mission
- **THEN** each opens with "In the method." then "The idea.", and none exceeds its cap
- **AND** each has an activity, two review questions, bundled sources and a primary source

#### Scenario: Not the only way
- **WHEN** a lesson names a course-specific practice (the worksheet, the file name, the project folder)
- **THEN** it is under "How this course does it" and says other approaches work too

#### Scenario: Nothing blocks Continue
- **WHEN** a Part 2 lesson has questions or reflections
- **THEN** the participant can continue without answering them

### Requirement: Part 2 gives one optional Stage 3 note
`p2-testfile` SHALL end with one optional note of at most 60 words that says the Evaluations Stage 3 asks for need at least three distinct rules with clear pass or fail limits, and that scripts, promptfoo files and written test cases are all accepted. Source: `docs/STAGE3-TASK-SPEC.md` section 5.

#### Scenario: The note
- **WHEN** the participant reads the note
- **THEN** it names the Evaluations, says the program decides what to submit, and is marked optional

#### Scenario: Accepted forms
- **WHEN** the participant reads the note
- **THEN** it says scripts, promptfoo files and written test cases are all accepted

### Requirement: The Stage 3 note is orientation only
The `p2-testfile` note SHALL say that the program's own instructions decide what to submit and that nothing in it is needed to finish the Part. It SHALL NOT block Continue, score a submission, give submission steps, or carry a link, address or date.

#### Scenario: Nothing needed
- **WHEN** the participant skips the note
- **THEN** Continue is available and nothing is recorded as missing

#### Scenario: No submission steps
- **WHEN** the content tests scan the note
- **THEN** it holds no link, address, upload or form instruction and no date

#### Scenario: No other Stage 3 wording
- **WHEN** the content tests scan the other Part 2 lessons, steps, glossary entries and interface text
- **THEN** none names Stage 3 or certification

### Requirement: Part 2 points to the participant's own repeating work without a task of their own
`p2-testfile` SHALL include one optional reflection asking which task of their own repeats, has clear requirements and could be checked by rules, and SHALL say Northwind is practice only and cannot be submitted. The reflection SHALL NOT block Continue and SHALL NOT mention office hours, discussions, people or places.

#### Scenario: Optional reflection
- **WHEN** the participant reads the lesson's activities
- **THEN** the own-work reflection is marked optional and is saved if answered

#### Scenario: Northwind is practice
- **WHEN** the participant reads the lesson or the finished screen
- **THEN** it says the Northwind update is a learning example and not something to submit

### Requirement: Part 2 uses the app's plain-language rules
Part 2 text SHALL follow AGENTS.md rule 10 and the content rules in `docs/PHASE3.md`: "Part", never session; no mention of a presenter, facilitator, room, breakout, handout, neighbor or clock; no suggestion of Copilot Chat in Teams; Northwind introduced as a learning example and never a submission option; every glossary entry for a course-specific term begins "In this course,".

#### Scenario: Banned words
- **WHEN** the content tests scan the Part 2 content, kit files and glossary entries
- **THEN** no banned word, session label or contact-instruction phrase is found

#### Scenario: Glossary
- **WHEN** the participant opens the glossary after Part 2 is added
- **THEN** the ideas (test case, format check, content check, supporting list, script test) appear under "Ideas" and the course term (worksheet) under "In this course"

### Requirement: Part 2 stands alone as a self-paced course
Everything a live group did together SHALL be carried by the app: the presenter's reference tables are shown only in the `reference` step, the partner review becomes a classification against the reference, and the scenario card is inside the first step. No Part 2 text SHALL depend on another person being present, and no Part 2 item SHALL need Part 1 or Part 3 to be done.

#### Scenario: No Part 1 needed
- **GIVEN** the participant has done nothing in Part 1
- **WHEN** they work through Part 2
- **THEN** every step can pass, with the scenario card standing in for their Part 1 notes

#### Scenario: No group needed
- **WHEN** the content tests scan Part 2 text
- **THEN** no text asks the participant to share, swap or discuss with another person

### Requirement: The finished screen says what they hold and what comes next
When Part 2 is finished the screen SHALL say what the participant can now do (turn requirements into distinct criteria, give each a threshold a script could decide, and record them as test cases), where their file is in the project folder, and that Part 3 turns a file like this into a checker. It SHALL say the Northwind file is practice and is not something to submit.

#### Scenario: Finished
- **WHEN** the participant finishes Part 2
- **THEN** the screen names the file, says what they can now do and what Part 3 does with it
