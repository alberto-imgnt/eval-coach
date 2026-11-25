# Spec Delta

## MODIFIED Requirements

### Requirement: The baseline lesson says how a baseline is used next
The baseline lesson SHALL say that in Part 4 the participant changes the prompt, checks again with the same rules and compares. It SHALL say that a score that did not move is "no measured gain on these rules", which is not the same as "no benefit": a simpler prompt can be worth keeping at the same score, and the score does not cover qualities no rule checks. It SHALL keep what it already says about Parts 4 and 5.

#### Scenario: Score did not move
- **WHEN** the participant reads what comes next
- **THEN** the lesson says an unchanged score means no measured gain on these rules
- **AND** it says this does not mean the change had no benefit

#### Scenario: Not the old wording
- **WHEN** the content tests scan lessons, steps and the glossary
- **THEN** none says that a change that does not move the score "did not help"

## ADDED Requirements

### Requirement: One comparison is a learning observation, not proof
Wherever the course compares two prompts, two scores or two runs, it SHALL call a single comparison an observation and SHALL NOT say it proves the later prompt did better. When the later score is equal or lower, the text SHALL say so plainly and SHALL NOT claim a gain. This applies to Part 1's hand-scored compare, to `p1-benefits` and to Part 3.

#### Scenario: Equal or lower score
- **GIVEN** the participant's second hand score in Part 1 equals or is below the first
- **WHEN** the participant reads the compare, the step's questions and `p1-benefits`
- **THEN** none says the rewrite did better
- **AND** the compare says one run each is an observation and not proof

#### Scenario: Higher score
- **GIVEN** the second score is higher
- **WHEN** the participant reads the compare
- **THEN** it reports the change and still calls it one observation, not proof

### Requirement: A measured result is reported per criterion, with NOT CHECKED visible
Where the course describes a score for the participant, it SHALL say the result is per rule, that a total can hide a rule that got worse, and that a rule that could not be judged stays NOT CHECKED and outside the total. It SHALL NOT present reduced coverage as a gain.

#### Scenario: Total hides a drop
- **WHEN** the participant reads how to compare two scores
- **THEN** the text says to compare every rule, not only the total

#### Scenario: Coverage change
- **WHEN** the participant reads how to compare two scores
- **THEN** the text says a rule that moved to NOT CHECKED is lost coverage, not a gain

### Requirement: Three thresholds are kept apart
The course SHALL keep three different numbers apart. First, a known-good answer is chosen by checking it against the written requirements before its score is seen, and the checker should score it 95% or more. Second, the overall score across five answers is a coaching target, not a gate. Third, an instruction-by-instruction audit meets the Stage 3 load-bearing criterion only at 90% or more, reported exactly. Iteration 0 SHALL NOT count as one of the two documented improvement rounds.

#### Scenario: Known-good answer
- **WHEN** the participant reads how the checker is trusted
- **THEN** the text says to choose the known-good answer from the written requirements before seeing its score
- **AND** it does not say to pick the best-scoring answer

#### Scenario: Iteration 0
- **WHEN** the participant reads the Stage 3 note or the baseline lesson
- **THEN** the text says Iteration 0 is the starting point and not one of the two improvement rounds this course asks for

#### Scenario: Three numbers
- **WHEN** the participant reads about the 95% check, the five-answer target and the 90% audit
- **THEN** each is described as a separate thing and none is said to replace another
