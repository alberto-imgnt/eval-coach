# Spec Delta

## MODIFIED Requirements

### Requirement: Configuration reset also moves the starting files
Confirming SHALL also move the starting prompt, the starting test cases, the bundled skill files and the prompts the participant wrote in Part 1 out of the project folder into the same backup, so that no file the app created is left in it. Every other file in the project folder SHALL be left untouched.

#### Scenario: Nothing from the app left
- **GIVEN** the project folder holds the starting files, course outputs, Part 1 prompts and an unrelated file
- **WHEN** the participant confirms Reset app configuration
- **THEN** only the unrelated file remains in the project folder
- **AND** the backup holds everything that was moved
