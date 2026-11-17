# Spec Delta

## REMOVED Requirements

### Requirement: The mission states the series purpose
**Reason**: The series purpose appears once, in Part 1's mission, not in every mission (series review item 13). Replaced by "Part 1's mission states the series purpose".
**Migration**: Keep the purpose in the `p1-mission` series passage; remove it from `p2-mission` and `mission`.

### Requirement: The course map uses the series' Part names
**Reason**: No mission lesson shows a map of the series any more (series review item 12). The Series map is the one place that lists the Parts, and `series-map` still holds their names.
**Migration**: Remove the `you-are-here` block from `mission`, `p1-mission` and `p2-mission`, and the content tests that compare mission-map names with the Series map.

## MODIFIED Requirements

### Requirement: The mission says why checking AI work matters
Part 1's mission lesson SHALL give a short "why it matters" covering three reasons: AI sounds sure of itself even when it is wrong, "better" is an opinion until it is measured, and answers change from one try to the next. Source: `docs/SERIES-INTENT.md` "Why it matters", series review item 13.

#### Scenario: The three reasons
- **WHEN** the participant reads `p1-mission`
- **THEN** each of the three reasons is stated in plain words with no code

## ADDED Requirements

### Requirement: Part 1's mission states the series purpose
`p1-mission` SHALL state, in plain words, that the series teaches participants to judge the work AI gives them and to trust it because it was checked, not because it looked right, and that it is not asking for blind trust or blind distrust. The other mission lessons SHALL NOT repeat it (`mission-lesson-shape`). Source: `docs/SERIES-INTENT.md` "Intent", series review item 13.

#### Scenario: Purpose on the Part 1 mission page
- **WHEN** the participant opens `p1-mission`
- **THEN** the text says the goal is to judge AI work and trust it for the right reasons
- **AND** it says trust comes from checking, and that neither blind trust nor blind distrust is asked for

#### Scenario: A mission stays one page with no questions
- **WHEN** a mission lesson is loaded
- **THEN** it has no activities and no review questions
