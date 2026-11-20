# Spec Delta

## MODIFIED Requirements

### Requirement: Part 2 has four lessons and four steps in a fixed order
The Part 2 course SHALL be, in this order: lesson `p2-mission`, lesson `p2-criteria`, step `draft`, lesson `p2-thresholds`, step `thresholds`, lesson `p2-testfile`, step `test-file`, step `reference`. Locking follows `part-registry` and `course-locking`. Source: the course context notes (local reference) "Part 2: defining evaluation criteria".

#### Scenario: Order
- **WHEN** the Part 2 course list is read
- **THEN** it holds exactly those eight items in that order, with lessons and steps in the same list

#### Scenario: A step after a lesson
- **GIVEN** `p2-thresholds` is not done
- **WHEN** the participant tries to start the `thresholds` step
- **THEN** it is locked and the lock message is shown, and its text is not shown

#### Scenario: First lesson before setup
- **GIVEN** Part 2 is open and setup has not passed
- **WHEN** the participant opens `p2-mission`
- **THEN** it works as normal, because it has no hands-on exercise

#### Scenario: Part 2 waits for Part 1
- **GIVEN** Part 1 is not Done or Skipped
- **WHEN** the participant opens `p2-mission`
- **THEN** it does not open, and no other Part's items change

#### Scenario: Parts are independent
- **GIVEN** Part 1 is Done and the participant has done nothing in Part 3
- **WHEN** they open `p2-mission`
- **THEN** it opens, and no other Part's items change

### Requirement: The Northwind reference is held until the file is done
Everything the participant reads or does before the `reference` step SHALL NOT show the Northwind reference criteria beyond the two worked examples, their thresholds or the Northwind banned list. The `reference` step SHALL show them only after `test-file` is done, so the participant drafts their own criteria first. Source: facilitator reference tables in the live materials; AGENTS.md rule 9 (the same discovery-before-reveal habit).

#### Scenario: Before the reveal
- **WHEN** the content tests scan the `p2-` lessons, the steps' words, the glossary and the interface text
- **THEN** no reference criterion other than the two worked examples, no reference threshold and no banned word from the Northwind list appears

#### Scenario: The reveal
- **GIVEN** `test-file` is done
- **WHEN** the participant opens `reference`
- **THEN** the reference criteria are shown beside the participant's own

#### Scenario: Locked until then
- **GIVEN** `test-file` is not done
- **WHEN** the participant, or a request, asks for the `reference` step
- **THEN** it is refused with the lock message and no step text or reference criterion is returned

#### Scenario: Previews hide it
- **GIVEN** Part 2 is Skipped and `test-file` was never done
- **WHEN** the participant opens the `reference` step read-only
- **THEN** only the step's words are shown, and no reference criterion
