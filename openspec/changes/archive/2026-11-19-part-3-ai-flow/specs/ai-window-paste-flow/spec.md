# Spec Delta

## MODIFIED Requirements

### Requirement: The rule is shared by every step that pastes
The start rule, the pasted text, the folder contents and the refusals of this capability SHALL be defined once and SHALL apply to any step whose content opts in to the paste flow. Each Part SHALL state only what differs for it: what moment starts the window (Part 1: the first save of a prompt; Part 3: the first time an open step is shown), what text is pasted (Part 1: the saved prompt, a divider, the rough notes and a closing line; Part 3: the step's own line), and its own check for what a start would lose. A later change can therefore switch another Part's step to the flow by content, with only those three parts defined.

#### Scenario: A step opts in
- **GIVEN** a step's content says it uses the paste flow
- **WHEN** the participant uses it
- **THEN** the same refusals apply, the app types nothing, and the Part's own start moment, text and "nothing to lose" check apply

#### Scenario: A step that does not opt in
- **GIVEN** a step's content does not say so
- **WHEN** the participant uses it
- **THEN** it behaves exactly as before, with its typed line and its Send button

#### Scenario: Two Parts, two start moments
- **GIVEN** Part 1's `cold` step and Part 3's `build` step both use the flow
- **WHEN** the participant saves a prompt in `cold` and opens `build`
- **THEN** each window starts by itself once, under its own Part's rule, and neither Part's trigger starts the other's window
