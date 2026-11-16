## MODIFIED Requirements

### Requirement: Locking stays inside a Part
A lesson SHALL open for work when every item before it in its own Part is done or skipped, and a step SHALL open for work when the previous step in its own Part is done and the lesson immediately before it, if any, is done or skipped. A Part SHALL NOT lock or unlock another Part's items. A locked item of any Part SHALL still open as a read-only preview, as set out in `setup-access`. Hands-on work in any Part SHALL follow the setup rules in `setup-access`.

#### Scenario: Parts are independent
- **GIVEN** the participant has done nothing in Part 3
- **WHEN** they open the first lesson of another Part
- **THEN** it opens, and Part 3's items are unchanged

#### Scenario: Hands-on work before setup
- **GIVEN** setup has not passed
- **WHEN** the participant tries a step of any Part
- **THEN** it is refused the same way a Part 3 step is

#### Scenario: Reading ahead in another Part
- **GIVEN** the participant is part-way through Part 3 and has done nothing in Part 1
- **WHEN** they open a lesson or step of Part 1 that its own order still keeps locked
- **THEN** its text is shown as a read-only preview, and no progress of either Part changes

#### Scenario: Doing a locked item is still refused
- **GIVEN** a lesson or step is locked by its Part's order
- **WHEN** the participant, or a direct request to the server, tries to answer, start, check, submit or complete it
- **THEN** it is refused with the plain lock message and nothing is recorded
