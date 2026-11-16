# Spec Delta

## MODIFIED Requirements

### Requirement: Lessons follow the method, one concept each
The Part 3 course SHALL have seven lessons, each teaching one concept, in the order of the series method (ask clearly, know what you need, turn it into rules, score the result, improve, keep a record). Other Parts list their own lessons in their own specs (Part 1: `part-1-course`). Source: `docs/SERIES-INTENT.md` "What you will learn".

#### Scenario: Seven lessons
- **WHEN** the Part 3 course content is loaded
- **THEN** it holds exactly these lessons in this order: `mission` (purpose and map), `hook` (a fixed rule beats an AI opinion), `several-runs` (one answer proves little), `rules` (turn "looks good" into a rule, and what a rule cannot check), `trust` (test the checker before trusting it), `surprise` (read a surprise, fix the spec and not the checker) and `baseline-why` (the baseline, what a score means, what comes next)
- **AND** each has one stated concept in its `win` line

#### Scenario: Method position
- **WHEN** the participant opens a lesson after the mission
- **THEN** its opening line says which link of the method it covers

### Requirement: Lessons stay short
Each lesson SHALL have a body of no more than 300 words, except a Part's first lesson (`mission`, `p1-mission`), which SHALL have no more than 450 words, and a Part's last lesson that also carries a closing orientation passage (`baseline-why`, `p1-benefits`), which SHALL have no more than 400 words. Lessons are in plain language with no code.

#### Scenario: Word cap
- **WHEN** the content tests count each lesson body
- **THEN** none exceeds its cap
