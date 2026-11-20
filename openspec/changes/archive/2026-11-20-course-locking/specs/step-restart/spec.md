# Spec Delta

## MODIFIED Requirements

### Requirement: Later steps lock again until the chosen step is done
Once a restart finishes, each later step SHALL be locked by its Part's order until the steps before it are done again, as `part-registry` and `course-locking` set out. Lessons stay as they were.

#### Scenario: Next step locked
- **GIVEN** `score` was restarted
- **WHEN** the participant, or a request, asks for `rewrite`
- **THEN** it is refused with the lock message, and no step text is shown
