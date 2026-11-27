# Spec Delta

## Purpose

Defines what the Part 4 course teaches and in what order, so a participant who never attended a live session learns to improve a prompt one change at a time, read every rule and not only the total, and keep a log of what changed, what the evidence said and why they kept or undid each change.

## ADDED Requirements

### Requirement: Part 4 has a fixed order of lessons and steps
The Part 4 course SHALL list its lessons and steps in one fixed order, set out in the Order scenario, with a round's four steps after the lesson that prepares it. Locking follows `part-registry` and `course-locking`. Source: issue #15 learner experience.

#### Scenario: Order
- **WHEN** the Part 4 course list is read
- **THEN** it holds exactly these items in this order: lesson `p4-mission`, step `starting-point`, lesson `p4-checker-first`, step `known-good`, lessons `p4-one-change` and `p4-worked-example`, steps `hypothesis-1`, `edit-1`, `measure-1` and `decide-1`, lesson `p4-read-results`, steps `hypothesis-2`, `edit-2`, `measure-2` and `decide-2`, lesson `p4-keep-and-log`, then the optional steps `hypothesis-3`, `edit-3`, `measure-3` and `decide-3`

#### Scenario: The known-good check comes before any comparison
- **GIVEN** `known-good` is not done
- **WHEN** the participant tries to open `hypothesis-1`
- **THEN** it is locked and the lock message is shown, and its text is not shown

#### Scenario: Part 4 waits for Part 3
- **GIVEN** Part 3 is not Done or Skipped
- **WHEN** the participant opens `p4-mission`
- **THEN** it does not open, and no other Part's items change

#### Scenario: Round 3 is optional
- **GIVEN** every item before round 3 is done
- **WHEN** the participant looks at the Part
- **THEN** Part 4 is Done, and round 3 is offered as optional and never required to finish

### Requirement: Each lesson teaches one concept and follows the lesson shape
Each Part 4 lesson after the mission SHALL open with "In the method." then "The idea.", then any short labelled passages, and keep this course's own mechanics to one "How this course does it" passage that says other approaches exist. Each SHALL have an activity, at least two retrieval questions, bundled `kit:` sources and a primary source. No lesson SHALL be skippable. Source: `method-over-mechanics`, `course-structure`.

#### Scenario: Shape
- **WHEN** the content tests scan the Part 4 lessons after the mission
- **THEN** each opens with "In the method." then "The idea.", none exceeds its cap, and each has an activity, two review questions and a primary source

#### Scenario: Not the only way
- **WHEN** a lesson names a course-specific practice (five answers, the attempt folder, the log file)
- **THEN** it sits under "How this course does it" and says other approaches work too

#### Scenario: Nothing blocks Continue
- **WHEN** a Part 4 lesson has questions or reflections
- **THEN** the participant can continue without answering them

### Requirement: The lessons teach checking the checker first
`p4-checker-first` SHALL teach that a known-good answer is chosen from the written requirements before its score is seen, never as the best of the five; that the checker should score it 95% or more; and that when it does not, the participant investigates the checker or the written requirements and never loosens a rule to make it pass. It SHALL say this check is separate from the five-answer score and is never merged with it. Source: `docs/SPEC.md` "Evidence handoff".

#### Scenario: Chosen before scored
- **WHEN** the participant reads the lesson
- **THEN** it says to choose the known-good answer before looking at its score, and never says to pick the best of the five answers

#### Scenario: Below 95%
- **WHEN** the participant reads what to do when the known-good answer scores under 95%
- **THEN** the lesson says to check the checker or the written requirements and not to loosen a rule

#### Scenario: Kept apart
- **WHEN** the participant reads the lesson
- **THEN** it names the known-good check and the five-answer score as two separate things

### Requirement: The lessons teach one change, one prediction and reading every rule
`p4-one-change` SHALL teach changing one thing at a time, writing a hypothesis before anything is scored, and using the same input, model and rules each time. `p4-read-results` SHALL teach reading each rule and not only the total, that one comparison is an observation, that a rule that becomes NOT CHECKED is lost coverage and never a gain, and that a simpler prompt at the same score can be worth keeping.

#### Scenario: One change
- **WHEN** the participant reads `p4-one-change`
- **THEN** it says to change one thing, write the hypothesis first, and keep the input, model and rules the same

#### Scenario: A total can hide a worse rule
- **WHEN** the participant reads `p4-read-results`
- **THEN** it says to read each rule, that a total can rise while a rule gets worse, and that a rule that moves to NOT CHECKED is lost coverage and not a gain

#### Scenario: One comparison
- **WHEN** the participant reads the lesson
- **THEN** it calls one comparison an observation that can suggest and never prove

### Requirement: The lessons use two phrases for a result and no others
Part 4 text SHALL call a higher score on the same rules a "measured gain on these rules" and an equal or lower score "no measured gain on these rules". It SHALL NOT say "did not help", "no benefit" or "did better" about a result, and SHALL NOT tell the participant to pick their best answer as the known-good one. Source: `docs/CONTENT-RULES.md` "Evidence wording and the three thresholds".

#### Scenario: Banned phrases
- **WHEN** the content tests scan the Part 4 lessons, steps, glossary and finished text
- **THEN** none contains "did not help", "no benefit" or "did better", or tells the participant to pick their best answer

#### Scenario: A flat attempt
- **WHEN** the participant reads how a flat or undone attempt is described
- **THEN** it says "no measured gain on these rules" and never calls the attempt an improvement

### Requirement: The five-answer score is a target and the Part never blocks on it
The course SHALL say the five-answer overall score of 95% is a coaching target and not a gate, that a verified result below it gets a suggested next step, and that completing Part 4 needs two documented rounds after Iteration 0, which is this course's convention. Source: issue #15; `docs/CONTENT-RULES.md`.

#### Scenario: Below the target
- **WHEN** the participant reads the passage
- **THEN** it says a score below 95% is not a failure and gives a next step

#### Scenario: Two rounds
- **WHEN** the participant reads what finishing needs
- **THEN** it says two documented rounds after Iteration 0, and that Iteration 0 is not one of them

### Requirement: The worked Practice task starts from Iteration 0 and compares every rule
`p4-worked-example` SHALL start from the Practice task's Iteration 0 (25 of 30 overall, with factual tone at 3 of 5) and show each round's results for every rule, before and after, with NOT CHECKED kept visible. Round 1 SHALL be a concrete tone line (26 of 30: tone up by 2, one other rule down by 1). Round 2 SHALL be a shorter tone line with the Role line removed (26 of 30, no measured gain, kept as simpler). It SHALL be called a worked example with saved answers, never a measurement.

#### Scenario: Every rule is compared
- **WHEN** the participant reads a round's result
- **THEN** every rule shows its before and after, not only the targeted one

#### Scenario: The side effect is named
- **WHEN** the participant reads round 1's result
- **THEN** the rule that got worse is named, the total is shown rising, and the lesson says the reason is a guess and not a fact

#### Scenario: A flat round
- **WHEN** the participant reads round 2's result
- **THEN** it says "no measured gain on these rules" and that a simpler prompt at the same score can be worth keeping

#### Scenario: A worked example, not a measurement
- **WHEN** the participant reads the introduction
- **THEN** it says the answers are saved examples and that only the participant's own rounds are measured, so their numbers may differ

### Requirement: The worked edits and results stay hidden until the prediction is locked
Before the participant answers the prediction activity, no response, page text or bundled file the participant can open SHALL contain round 1's exact edit, round 2's exact edit or either round's results. The participant SHALL see only Iteration 0, the vague tone line and the idea of a more concrete tone line, and SHALL predict for each rule whether it rises, stays or falls. Source: AGENTS.md rule 9 (the same habit); issue #18.

#### Scenario: Before the prediction
- **WHEN** a lesson, a kit file or an API response is read before the prediction is answered
- **THEN** it holds no worked edit and no worked result

#### Scenario: After the prediction
- **GIVEN** the participant answered the prediction
- **WHEN** they continue
- **THEN** the exact edits and the per-rule results are shown beside their prediction

#### Scenario: A wrong prediction
- **WHEN** the participant predicts a rule wrongly
- **THEN** only that rule's feedback is shown, retry is unlimited, and the full results are shown once every rule is predicted

### Requirement: Every step has one Quick check and the course ends with a reflection
Each Part 4 step SHALL have one question on its own page after the step is done (a Quick check), never a gate. The last Quick check, on `decide-2`, SHALL ask the participant to explain their decision and what the score cannot tell them, as a written reflection that is saved and never blocks Continue. Source: `docs/CONTENT-RULES.md` teaching rules; issue #15.

#### Scenario: A Quick check
- **GIVEN** a Part 4 step is done
- **WHEN** the participant opens it
- **THEN** one question is shown, and the participant can continue without answering it

#### Scenario: The closing reflection
- **WHEN** the participant reaches the Quick check of `decide-2`
- **THEN** it asks them to explain their decision and what the score cannot tell them, in their own words

### Requirement: The mission page follows the mission shape
`p4-mission` SHALL follow `mission-lesson-shape`: one page with four passages, "The goal", "Why it matters to you", "What you will do" and "What you leave with". "The goal" SHALL use the wording "Understand how to improve a prompt one change at a time, and how to tell from a rerun of the same rules whether a change was worth keeping." It SHALL NOT repeat the series framing or show a map of the Parts.

#### Scenario: The four passages
- **WHEN** the participant reads `p4-mission`
- **THEN** the four passages appear in that order and the page is at most 450 words

#### Scenario: What you leave with
- **WHEN** the participant reads "What you leave with"
- **THEN** it names an iteration log with two documented rounds and the kept version of their prompt, in plain words

### Requirement: Part 4 uses the app's plain-language rules
Part 4 text SHALL follow AGENTS.md rule 10 and `docs/CONTENT-RULES.md`: "Part", never session; no presenter, facilitator, room, handout, neighbor or clock; no Copilot Chat in Teams; "your AI" or "AI window", never a bare "CLI"; "Practice task" and "My own task"; every course-specific glossary entry beginning "In this course,". The Practice task SHALL always be called practice only and never a submission option.

#### Scenario: Banned words
- **WHEN** the content tests scan the Part 4 content, kit files and glossary entries
- **THEN** no banned word, session label or contact-instruction phrase is found

#### Scenario: Glossary
- **WHEN** the participant opens the glossary
- **THEN** hypothesis, iteration, red green refactor, known-good answer, kept version, measured gain on these rules and coverage change appear, ideas under "Ideas" and course terms under "In this course"

### Requirement: Part 4 names no certification wording
Part 4 lessons, steps, glossary entries, finished text and interface text SHALL NOT name Stage 3 or certification, and SHALL give no submission steps. Certification orientation stays in the notes of Parts 2 and 3 and never replaces or gates tier 1 or tier 2 content. Source: docs/CONTENT-RULES.md "Learning priorities".

#### Scenario: No Stage 3 wording
- **WHEN** the content tests scan the Part 4 content
- **THEN** none names Stage 3 or certification, or holds a link, upload or form instruction

### Requirement: Part 4 stands alone and the finished screen says what they hold
Everything a live group did together SHALL be carried by the app, and no Part 4 text SHALL ask the participant to share, swap or discuss with another person. When Part 4 is finished the screen SHALL say what the participant now holds (their iteration log and their kept version, or practice results marked practice only), what they can now do, and that Part 5 starts from the kept version.

#### Scenario: No group needed
- **WHEN** the content tests scan Part 4 text
- **THEN** no text asks the participant to share, swap or discuss with another person

#### Scenario: Finished
- **WHEN** the participant finishes Part 4
- **THEN** the screen names the log and the kept version, says what they can now do, and says Part 5 starts from the kept version

#### Scenario: Practice results
- **GIVEN** the participant worked on the Practice baseline
- **WHEN** they finish Part 4
- **THEN** the screen says the results are practice only and cannot be submitted
