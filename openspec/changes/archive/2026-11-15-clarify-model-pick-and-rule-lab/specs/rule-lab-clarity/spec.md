# Spec Delta

## Purpose

Makes a rule lab fair to predict: the participant reads what each rule checks before predicting a verdict, and the optional own-text box says what it is for.

## ADDED Requirements

### Requirement: A rule lab lists its rules before the cases
A rule lab SHALL show every rule it uses, each with its name and, when the rule has one, a plain-language explanation, above the cases the participant must predict. An explanation SHALL be optional per rule and SHALL NOT reveal any case's expected verdict.

#### Scenario: Rules visible before predicting
- **WHEN** a participant opens a rule lab
- **THEN** every rule is listed with its explanation above the PASS or FAIL choices
- **AND** the hint under the list tells them to use those rules

#### Scenario: A rule without an explanation
- **WHEN** a rule has no explanation
- **THEN** the lab still lists its name and nothing else breaks

#### Scenario: Grading is unchanged
- **WHEN** the participant submits predictions
- **THEN** they are graded against the same expected verdicts as before, and a failed attempt still reports only a count

### Requirement: Explanations state the details that decide a verdict
An explanation SHALL state what decides a verdict, such as whether the limit itself passes, whether capital letters matter, and whether a match can sit inside a longer word.

#### Scenario: Word count rule
- **WHEN** the participant reads "Word count under 20"
- **THEN** the explanation says that fewer than 20 words passes and exactly 20 words fails
- **AND** says that every piece of text between spaces counts as one word

#### Scenario: List term rule
- **WHEN** the participant reads "Contains none of: proud"
- **THEN** the explanation says that capital letters are ignored and that the word is also found inside a longer word such as "proudly"

#### Scenario: Label rules
- **WHEN** the participant reads a label rule ("Blocker: and Need:" or "Risk:")
- **THEN** the explanation says the label must appear with its colon and the same capital letters, and that it can appear anywhere in the note

### Requirement: The lab prompts point at the rules
The prompt of each rule lab SHALL tell the participant to read the rules and the notes before predicting, and SHALL NOT repeat rule details that the rule list now carries.

#### Scenario: First lab
- **WHEN** the first lab is shown
- **THEN** its prompt asks the participant to read the two rules and three notes, then predict every pair

### Requirement: The own-text box says what it is for
The "Try your own text" box SHALL carry a line saying it is optional practice that is not scored, what to do in it, and when the sample notes become usable in it.

#### Scenario: Reading the box
- **WHEN** the participant reaches "Try your own text"
- **THEN** a line says it is optional and not scored
- **AND** says to pick a rule, type or paste any text and press "Run this rule" to see the verdict and the reason

#### Scenario: Sample text before passing
- **WHEN** the participant has not yet passed the exercise
- **THEN** the line says the sample notes can be run there only after the exercise is passed
- **AND** running a sample's text before then is still refused

### Requirement: Interface additions stay within the authorization
The additions to the rule lab interface SHALL be limited to the rule list and the own-text intro line, using existing design classes and tokens, with no change to element ids or existing labels. Source: AGENTS.md rule 11.

#### Scenario: Existing controls
- **WHEN** the rule lab is shown
- **THEN** the labels "Rule", "Your text" and "Run this rule" and every existing element id are unchanged
