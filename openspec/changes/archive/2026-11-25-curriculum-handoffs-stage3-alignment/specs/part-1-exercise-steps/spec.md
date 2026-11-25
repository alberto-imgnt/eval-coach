# Spec Delta

## MODIFIED Requirements

### Requirement: Compare puts both runs side by side
The `rescore` step SHALL score the second output on the same five requirements, then show both prompts, outputs and scores side by side as plain text with the change between the scores. It SHALL ask in writing what the labels made the participant add, and what differed between the two answers, and if the second was not better, which part of the prompt is still missing. It SHALL call the comparison one observation and not proof, and SHALL NOT say the second answer is better unless the participant's own scores show a higher score. Source: facilitator guide, segment 6.

#### Scenario: Side by side
- **WHEN** the participant opens `rescore`
- **THEN** the two prompts, outputs and scores are shown next to each other, stacked on a narrow screen

#### Scenario: One run each
- **WHEN** the participant reads the compare
- **THEN** it says one run each cannot show how much answers vary, which Part 3 measures
- **AND** it says the comparison is an observation and not proof

#### Scenario: A worse second answer
- **GIVEN** the second score is lower than the first
- **WHEN** the participant opens the compare
- **THEN** the text says this can happen and points them to ask which part of the prompt is still missing, without blaming the framework

#### Scenario: An equal second score
- **GIVEN** the second score equals the first
- **WHEN** the participant opens the compare
- **THEN** the text says the hand score did not change and does not say the rewrite did better

#### Scenario: Questions do not assume a gain
- **WHEN** the participant reads the step's written questions and gate wording
- **THEN** none assumes the second answer was better

#### Scenario: Gate
- **WHEN** the five rows and both written answers are filled
- **THEN** the step can pass
