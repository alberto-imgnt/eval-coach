# Spec Delta

## MODIFIED Requirements

### Requirement: Reset lesson progress clears progress
After confirmation, all course progress SHALL be cleared: lessons and activities, placement, step records, the baseline, the review schedule, saved hook and practice runs, and every Part skipped. The course SHALL start again at its first item, and every Part after Part 1 SHALL be locked again until the Parts before it are Done or Skipped.

#### Scenario: Full fresh start
- **GIVEN** the participant has finished lessons and steps and has a baseline
- **WHEN** the participant confirms the reset
- **THEN** every lesson and step shows as not started
- **AND** no baseline and no review items exist
- **AND** the current course item is the first one

#### Scenario: Skipped Parts are cleared
- **GIVEN** the participant skipped Part 1
- **WHEN** the participant confirms the reset
- **THEN** no Part shows Skipped, and Parts 2 and 3 are locked

#### Scenario: Track can be chosen again
- **GIVEN** the track was locked because a step was done
- **WHEN** the participant confirms the reset
- **THEN** the track can be changed again before the first step is done
