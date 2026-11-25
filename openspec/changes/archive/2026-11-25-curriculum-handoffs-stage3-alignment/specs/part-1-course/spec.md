# Spec Delta

## MODIFIED Requirements

### Requirement: The benefits come from structure, in four named benefits
`p1-benefits` SHALL name four benefits and tie each to what the participant saw: completeness (the AI guesses less), better first results (fewer rounds), easier fixes (the labels show which part to change) and repeatability (the same structure works next time and teammates can follow it). It SHALL state the takeaway "Give the AI what it needs. Use a framework, or build your own." It SHALL describe the benefits as what structure tends to give, and SHALL NOT say the participant's own second prompt did better.

#### Scenario: Four benefits
- **WHEN** the participant reads the lesson
- **THEN** all four benefits are named, each with a sentence that points back to the cold and rewrite runs

#### Scenario: Structure, not letters
- **GIVEN** `rescore` is done
- **WHEN** the participant reads the two sample prompts for the same task side by side
- **THEN** the lesson says both hold the same information under different labels, so the benefit comes from structure and not from a particular framework

#### Scenario: No claim about the participant's score
- **GIVEN** the participant's second hand score was equal or lower
- **WHEN** they read the lesson
- **THEN** it does not say their second prompt did better
- **AND** it says one comparison is an observation and not proof

#### Scenario: Takeaway
- **WHEN** the participant reaches the takeaway
- **THEN** it is stated in those words

### Requirement: The lesson leads into Part 2
The closing passage of `p1-benefits`, before the optional note, SHALL say real work does not come with a card of requirements and ask how the participant knows the second answer is better, without answering it. It SHALL say the two prompts and outputs are saved in the project, that Part 2 builds on them, and that Part 3 lets the participant choose the rewrite to score. Source: the course context notes (local reference) "The question that leads into Part 2".

#### Scenario: Open question
- **WHEN** the participant reaches the end of `p1-benefits`
- **THEN** the question is asked and is not answered in the lesson
- **AND** the lesson says the before and after prompts and outputs are saved in the project for Part 2

#### Scenario: Part 3 named
- **WHEN** the participant reaches the end of `p1-benefits`
- **THEN** the lesson says they can choose their rewrite to score in Part 3

#### Scenario: Finished
- **WHEN** the participant finishes Part 1
- **THEN** the screen says what they can do now and that Part 2 turns "that looks good" into clear pass or fail rules
