# Spec Delta

## Purpose

Defines what each Part 4 step does for the participant: choosing a starting point, checking the checker with a known-good answer, and in each round writing a hypothesis, editing the prompt, measuring five fresh answers, then deciding and logging, so a round leaves evidence a person can read and the app can check from files.

## ADDED Requirements

### Requirement: The starting-point step offers the participant's baseline or the Practice baseline
`starting-point` SHALL start no AI and offer two choices: "Your Part 3 baseline" and "Practice task baseline". Nothing SHALL be preselected and nothing SHALL change until a choice is submitted. The first is available when Part 3's baseline step is done and its saved results still match the files; otherwise the step says why in plain words. The Practice choice is always available and labelled practice only. Source: issue #15; `part-3-inputs` (the same habit).

#### Scenario: Own baseline unavailable
- **GIVEN** Part 3 was skipped or its baseline results no longer match its files
- **WHEN** the participant opens the step
- **THEN** the first choice is unavailable with a plain reason, and the Practice choice is available

#### Scenario: Little room to practice
- **GIVEN** the participant's Iteration 0 overall score is 95% or more
- **WHEN** the participant opens the step
- **THEN** a plain note says there is little room to improve, and the Practice choice is offered beside it

#### Scenario: Nothing chosen yet
- **WHEN** the participant opens the step without choosing
- **THEN** neither choice is selected and no file or record is created

#### Scenario: The choice is fixed once rounds start
- **GIVEN** attempt 1 exists
- **WHEN** the participant tries to change the starting point
- **THEN** it is refused with a plain sentence, and no file changes

### Requirement: The known-good step shows its score only after the answer is saved
`known-good` SHALL ask the participant to write or paste a known-good answer chosen from the written requirements. The score SHALL be shown only after the answer is saved, as passes out of checked results and whether it meets 95%, apart from the five-answer score. The step SHALL be done when the answer is saved, scored and meets 95%. Below 95% it SHALL give a next step that never offers to loosen a rule. Source: `part-4-attempts`; `docs/SPEC.md` "Evidence handoff".

#### Scenario: Score hidden first
- **WHEN** no known-good answer is saved
- **THEN** no known-good score is shown

#### Scenario: Meets 95%
- **WHEN** the saved answer passes 95% or more of checked results
- **THEN** the score and "meets the 95% mark" are shown and the step can be finished

#### Scenario: Below 95%
- **WHEN** the saved answer passes under 95% of checked results
- **THEN** the step says to check the checker or the written requirements, offers no way to loosen a rule, and cannot be finished

#### Scenario: A repair changes Iteration 0
- **GIVEN** the participant repaired the checker and its results on the original five answers differ
- **WHEN** they continue
- **THEN** the step asks them to rerun the original five answers and record the corrected Iteration 0 before any round

### Requirement: The hypothesis step saves a prediction before the edit and the run
`hypothesis-n` SHALL show the starting version's result for every rule, mark the rules that fail, and ask for a hypothesis that names the rule and what the participant expects. It SHALL save the text and lock the edit step until it exists. The text SHALL stay editable until the round has a saved answer and never after. Source: `part-4-attempts`.

#### Scenario: Edit stays locked
- **GIVEN** no hypothesis is saved for the round
- **WHEN** the participant tries to open `edit-n`
- **THEN** it is locked and the lock message is shown

#### Scenario: Changed after the run
- **GIVEN** the round has a saved answer
- **WHEN** the participant tries to change the hypothesis
- **THEN** it is refused with a plain sentence that says a hypothesis written after the result is not a prediction

#### Scenario: A failing rule is shown
- **WHEN** the participant opens the step
- **THEN** every rule of the starting version is listed with its pass count and the failing ones are marked in words as well as by color

### Requirement: The edit step changes only the round's own copy of the prompt
`edit-n` SHALL show the round's own copy of the kept version's prompt for editing. It SHALL be done when the saved prompt differs from the starting prompt. Saving SHALL never change the participant's earlier prompts, rules, checker, answers or log, and never replace a file that already holds the participant's work.

#### Scenario: No change made
- **WHEN** the saved prompt equals the starting prompt, ignoring spacing
- **THEN** the step says a change is needed and cannot be finished

#### Scenario: Earlier files untouched
- **WHEN** the participant saves an edit
- **THEN** Part 3's files and every earlier round's files have the same bytes as before

### Requirement: The measure step collects five fresh answers in new chats
`measure-n` SHALL open the participant's AI window by itself, show the line to paste with a Copy button, and save each answer as the next run of the round, each in a new chat, from the round's own prompt and the same input as the starting version. The app SHALL NOT answer a prompt in the AI window or read its output to decide anything. Source: `ai-window-paste-flow`; AGENTS.md rules 2 and 3.

#### Scenario: Five fresh chats
- **WHEN** the participant pastes the line
- **THEN** the AI saves an answer, the app files it as the next run and closes the AI window, and the next run needs a new chat

#### Scenario: Run without a hypothesis
- **GIVEN** no hypothesis is saved
- **WHEN** a request asks to run or score the round
- **THEN** it is refused with a plain sentence that names the hypothesis step

### Requirement: The measure step scores the five answers with no AI call and records the model
After five answers are saved, `measure-n` SHALL score them by running the round's own checker, with no AI call, on the Script track or the promptfoo track. It SHALL record the model and say when it differs from the previous attempt's.

#### Scenario: Model differs
- **GIVEN** this round's model differs from the previous attempt's
- **WHEN** the answers are scored
- **THEN** a plain note says the comparison used a different model, and the score is still shown

#### Scenario: Both tracks
- **WHEN** the participant is on the Script track or the promptfoo track
- **THEN** the round is scored on its own five answers with the checker or config copy of the round's folder, and the original config is unchanged

### Requirement: The results compare every rule and flag changed coverage
After scoring, `measure-n` SHALL show for every rule its pass count before and after, the overall score, and any NOT CHECKED rule in plain words. A set of rules different from Iteration 0 SHALL be flagged as a coverage change, a rule that became NOT CHECKED SHALL be shown as lost coverage, and neither SHALL be counted as a gain. The five-answer score SHALL be shown with its 95% target and a next step, never as a pass or fail, and apart from the known-good check.

#### Scenario: Every rule
- **WHEN** the results are shown
- **THEN** each rule lists its before and after counts, not only the rule the hypothesis named

#### Scenario: Coverage changed
- **WHEN** the round reports a different set of rules from Iteration 0
- **THEN** a plain note says it is flagged and not counted as a gain

#### Scenario: Below the target
- **WHEN** the overall score is under 95%
- **THEN** the step shows a suggested next step and the round can still be finished

#### Scenario: Evidence wording after the decision
- **GIVEN** the round is not decided
- **WHEN** the results are shown
- **THEN** no "measured gain" wording appears until the participant keeps or undoes the round

### Requirement: The decide step records an explicit decision before the log
`decide-n` SHALL ask the participant to keep or undo the round and SHALL NOT assume the latest round is kept. A round with stale results SHALL NOT be decided. Source: issue #15.

#### Scenario: Keep
- **GIVEN** the participant keeps the round
- **WHEN** the decision is saved
- **THEN** the round becomes the kept version, and a later round starts from its files

#### Scenario: Undo
- **GIVEN** round 2 is undone
- **WHEN** the next round or Part 5 starts
- **THEN** it starts from the last kept round, and round 2 stays in the log marked undone

#### Scenario: Stale results
- **GIVEN** a file changed after scoring
- **WHEN** the participant tries to decide
- **THEN** it is refused with a plain sentence that names what changed, and the round must be scored again

### Requirement: The log entry is written half by the AI and half by the participant
After the decision, `decide-n` SHALL show a line to paste that has the AI write the factual part of the log entry (counts, overall, NOT CHECKED and the saved Hypothesis) to the log file of the chosen starting point, and SHALL ask the participant to write Change, Result, Reasoning and the Decision line themselves. Source: the bundled skill's log mode; issue #15.

#### Scenario: Who writes what
- **WHEN** the step shows its instructions
- **THEN** they say the AI writes the numbers and the saved Hypothesis, and the participant writes Change, Result, Reasoning and Decision in their own words

#### Scenario: Before the decision
- **GIVEN** the round is not decided
- **WHEN** the participant opens the step
- **THEN** no line to paste is shown until they keep or undo the round

### Requirement: The decide step checks the log against the saved results and never edits it
The step SHALL be done when the log has one entry for the round, its Decision equals the saved one, its Hypothesis equals the saved text ignoring spacing, its counts and NOT CHECKED items equal the saved results, the round was scored on the files it has now, and its Change, Result and Reasoning are not empty. Each failure SHALL be a plain sentence with the difference named. The app SHALL NOT edit the log.

#### Scenario: A clean pass
- **WHEN** every check passes
- **THEN** the step is done and the AI window closes

#### Scenario: Empty reasoning
- **GIVEN** the log entry's Reasoning is empty
- **WHEN** the participant presses Check my work
- **THEN** the step is not done and says the Reasoning is missing

#### Scenario: Decision differs
- **GIVEN** the app has the round as kept and the log says undone
- **WHEN** the participant checks
- **THEN** the step names both values, and the log is not changed

#### Scenario: Counts differ
- **GIVEN** the log's pass counts differ from the saved results
- **WHEN** the participant checks
- **THEN** the step names the rule and both numbers, and the log is not changed

### Requirement: Finishing Part 4 needs two documented rounds and never a score
Part 4 SHALL be done when rounds 1 and 2 are decided, scored, fresh and documented in the log, whatever their decisions or scores. A below-target score SHALL give a suggested next step and SHALL NOT block. A flat or undone round SHALL be described as "no measured gain on these rules". Round 3 SHALL start from the kept version in the same way and SHALL stay optional.

#### Scenario: Below target, two rounds
- **GIVEN** two documented rounds whose latest score is under 95%
- **WHEN** the participant finishes `decide-2`
- **THEN** Part 4 is done and a next step is shown

#### Scenario: One round
- **GIVEN** only round 1 is documented
- **WHEN** the participant looks at Part 4
- **THEN** it is not done and round 2 is the next item

#### Scenario: Round 3 from the kept version
- **GIVEN** round 2 was undone
- **WHEN** the participant starts round 3
- **THEN** its prompt is a copy of round 1's kept prompt, and its parent is 1

### Requirement: Participant work is preserved and a finished step is not restarted
Every Part 4 step SHALL write only create-only copies into the round's own folder and SHALL never overwrite a participant file. A finished Part 4 step SHALL NOT offer "Start this step again", because a decision cannot be silently undone, and a request for it SHALL be refused with a plain sentence that changes nothing.

#### Scenario: Existing work
- **GIVEN** a round folder already holds the participant's files
- **WHEN** the round is resumed
- **THEN** no file in it is overwritten

#### Scenario: No restart
- **WHEN** the participant opens a finished Part 4 step
- **THEN** no "Start this step again" control is shown and a direct request is refused
