# interface-alignment Specification

## Purpose
Makes the interface (course list, reference card, glossary, step titles and finished screen) present the method and the series first and this course's mechanics as one labelled way of working, in plain words that do not clash with the series' Part numbering.

## Requirements

### Requirement: The course list is grouped by what is being learned
The course list in the sidebar SHALL show group headings above the lessons and steps they cover, in the course order. The group names and membership SHALL come from `content/lesson-ui.json`, and every course item SHALL belong to exactly one group.

#### Scenario: Headings in order
- **WHEN** the course list is shown
- **THEN** it has these groups once each, above their items: "Why check AI work" (mission, hook), "Collect answers" (several-runs, generate), "Turn it into rules" (rules, build), "Test the checker" (trust, fixtures, fixtures-config, readback, predict, key), "Read results and improve" (surprise, run, fix) and "Keep a record" (baseline-why, baseline)
- **AND** items keep their existing status, order and numbering

#### Scenario: Optional step
- **WHEN** the optional live step is shown
- **THEN** it appears under "Keep a record" and is still marked optional

#### Scenario: Accessibility
- **WHEN** a screen reader reads the course list
- **THEN** each group is announced by its heading, and the heading is not a button

#### Scenario: Small screens
- **WHEN** the course list is a drop-down on a narrow screen
- **THEN** the same headings are shown in the drop-down

### Requirement: Interface words do not clash with Part numbers
Interface copy SHALL use "Part" only for the six series Parts. The overall progress label SHALL count "lessons and steps" and the lock messages SHALL say "lessons" or "steps", never "parts of the course".

#### Scenario: Progress label
- **WHEN** the sidebar shows overall progress
- **THEN** it reads "N of M lessons and steps done"

#### Scenario: Lock message
- **WHEN** a participant opens a locked lesson or step
- **THEN** the message names the lesson or step and does not use "part" for it

### Requirement: The reference card leads with the method
The reference card SHALL open with the method in one line (ask clearly, know what you need, turn it into rules, score the result, improve, keep a record). A section headed "How this course works" SHALL follow, describing this course's own chain of work and its three results as results of this course's checker. The glossary in two groups comes next, and the card SHALL close with the principles from `method-over-mechanics` instead of a "who does what" motto. It SHALL NOT mention exit codes.

#### Scenario: Method first
- **WHEN** the participant opens the reference card
- **THEN** the method line is the first content

#### Scenario: Course mechanics labelled
- **WHEN** the participant reads the section after the method
- **THEN** its heading says it is how this course works
- **AND** it describes PASS, FAIL and NOT CHECKED as the results this course's checker gives

#### Scenario: Printable
- **WHEN** the reference card is printed
- **THEN** it still fits one page

### Requirement: The glossary separates ideas from this course's terms
The glossary panel and the reference card SHALL show two groups, "Ideas" and "In this course". Each entry's group SHALL come from a `kind` field in `content/glossary.json` (`idea` or `course`), every entry SHALL have one, and entries of kind `course` SHALL begin "In this course,".

#### Scenario: Two groups
- **WHEN** the participant opens the glossary
- **THEN** the general ideas appear under "Ideas" and the course-specific terms under "In this course"

#### Scenario: Missing kind
- **WHEN** the content tests load the glossary
- **THEN** an entry without a `kind` fails validation

### Requirement: Step titles and goals lead with the idea
Step titles and goals SHALL state what the participant achieves in tool-neutral words, with counts, file names and tool names left to the step's own text. The `generate` step SHALL be titled "Collect your answers".

#### Scenario: Sidebar titles
- **WHEN** the course list shows the steps
- **THEN** no step title contains a number word or a file name

### Requirement: The finished screen says what comes next
The finished screen SHALL say what the participant can do now and that Part 4 changes the prompt and compares scores with the baseline.

#### Scenario: Finished
- **WHEN** the participant finishes the course
- **THEN** the screen names Part 4 and what it does in plain words

### Requirement: The interface change is limited
The change SHALL add only group headings in the course list (one heading element and one style rule using existing design tokens), the two groups and the method section in the glossary and reference card, and content-driven wording. It SHALL NOT change design tokens, colors, typography, component styles, element ids, the preflight, Settings or terminal screens, or the step panels. Source: AGENTS.md rule 11; authorized by the user on 2026-11-14 for items U1 to U6 and U8 of the UI audit.

#### Scenario: Interface tests
- **WHEN** the interface tests run
- **THEN** the only changed or added expectations are the group headings, the Part strings, the reference and glossary groups, the step titles and the finished text

#### Scenario: Both themes and text sizes
- **WHEN** the new headings are shown in the light and dark themes and at the largest text size
- **THEN** they meet normal text contrast and do not overlap or clip
