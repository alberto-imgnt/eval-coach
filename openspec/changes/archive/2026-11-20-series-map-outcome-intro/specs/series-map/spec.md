## ADDED Requirements

### Requirement: The Series map page is titled "Evaluated systems"
The heading of the Series map page SHALL read "Evaluated systems". Every other reference to the map by name (the "Back to series map" control and its tooltip, the sidebar, Settings, the setup wizard and its messages) SHALL keep its current words. Source: user decision 2026-11-20.

#### Scenario: The heading
- **WHEN** the participant opens the Series map
- **THEN** the page heading reads "Evaluated systems"
- **AND** the heading is still the element that receives focus when the page opens

#### Scenario: Other references are unchanged
- **GIVEN** the participant is inside a Part
- **WHEN** they look at the control that returns to the map
- **THEN** it still reads "Back to series map"

### Requirement: The Series map intro says what the series is for
The intro under the Series map heading SHALL state the series outcome in plain words, as the questions a participant already asks (is AI work good enough to use, and how do you know) and an answer made of principles: work that is asked for clearly, judged against rules you can test, measured so that a better prompt is a fact and not an opinion, and kept to what earns its place. It SHALL end by pointing down at the rows, ending with a task of the participant's own.

#### Scenario: Outcome and principles
- **WHEN** the participant opens the Series map
- **THEN** the intro opens with the two questions "Is it good enough to use?" and "How do you know?"
- **AND** it defines an evaluated system through the four principles above, in that order
- **AND** its last clause points at the rows and at a task of the participant's own

#### Scenario: Each clause echoes a row
- **WHEN** the intro is read beside the six rows
- **THEN** its clauses follow the order of the Parts' outcomes (asking clearly, rules, measuring, proof of improvement, keeping what earns its place, a task of your own)
- **AND** no Part is named in it

### Requirement: The Series map intro is not procedural
The intro SHALL NOT count or name the Parts, SHALL NOT use sequence or step wording, SHALL NOT say to look ahead and SHALL NOT mention Stage 3. It SHALL be at most four short sentences and at most 80 words. It SHALL follow the plain-language rules of AGENTS.md rule 10.

#### Scenario: No count and no sequence
- **WHEN** the content tests scan the Series map intro
- **THEN** it contains none of "six", "Part", "step", "first", "then", "look ahead" or "Stage 3"

#### Scenario: Length
- **WHEN** the content tests measure the intro
- **THEN** it has at most four sentences and at most 80 words

## REMOVED Requirements

### Requirement: The Series map intro is about doing the work yourself
**Reason**: The intro now says what the series is for and what the participant will be able to do, not how to take the course; the "six Parts, one method" count and the "copying someone else's prompt or rules" warning are no longer on the Series map. Replaced by "The Series map intro says what the series is for" and "The Series map intro is not procedural".
**Migration**: The tests that assert "Six Parts, one method." and "Do each one yourself" move to the new requirements. The "do each one yourself" message is not carried elsewhere in this change.
