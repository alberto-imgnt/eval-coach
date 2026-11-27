# part-4-attempts Specification

## Purpose
Defines how a Part 4 attempt is stored, scored and recorded, how the kept version is chosen, and how the log is checked against saved results, so Part 5 can start from the kept version without guessing.

## Requirements

### Requirement: Each attempt is stored apart from Part 3
Each attempt `n` SHALL be stored under `part-4\attempts\<n>\` with its own prompt, test cases, checker, `runs\run-1` to `run-5`, `results.json` and `hypothesis.md`; when the Practice baseline is the starting point it SHALL be stored under `part-4\practice\attempts\<n>\` instead. Part 3's files SHALL never be edited. Source: `docs/SPEC.md` "Evidence handoff".

#### Scenario: Part 3 files untouched
- **WHEN** an attempt is created, run and scored
- **THEN** the project's `prompt-v0.md`, `test-cases.md`, `check.py`, `runs\` and `iteration-log.md` have the same bytes as before

#### Scenario: A second attempt starts from the kept version
- **GIVEN** attempt 1 is kept
- **WHEN** attempt 2 is created
- **THEN** its starting files are copies of attempt 1's, and its parent is 1

#### Scenario: A Practice attempt
- **GIVEN** the Practice baseline is the starting point
- **WHEN** attempt 1 is created and scored
- **THEN** its files are under `part-4\practice\attempts\1\` and no file under `part-4\attempts\` is created

### Requirement: The manifest holds hashes and counts only
`parts.part-4` in `progress.json` SHALL list the attempts in chronological order, each with `n`, `parent`, `log_entry`, `model`, `hashes` (prompt, test cases, checker, runs), per-criterion `passes` and `checked_runs`, the NOT CHECKED criteria, and a `decision` of `kept`, `undone` or `pending`. It SHALL never hold prompt, answer, hypothesis or log text.

#### Scenario: No text in progress
- **WHEN** an attempt is scored and the manifest is read
- **THEN** it contains hashes, counts and ids only

### Requirement: The kept version is set only by an explicit decision
The kept version SHALL be the last attempt whose decision is `kept`, or Iteration 0 if none. An attempt SHALL stay `pending` until the participant chooses keep or undo. A rejected attempt SHALL remain in the manifest and the log.

#### Scenario: Undone second edit
- **GIVEN** attempts 1 and 2 where 1 is kept and 2 is undone
- **WHEN** the kept version is read
- **THEN** it is attempt 1, and attempt 2 is still listed as undone

#### Scenario: The latest attempt is not assumed kept
- **GIVEN** attempt 2 is pending
- **WHEN** the kept version is read
- **THEN** it is the last kept attempt or Iteration 0, never attempt 2

### Requirement: The hypothesis is saved before the edit and the run
The hypothesis step SHALL save `hypothesis.md` in the attempt folder and record its hash before the edit and run steps of that attempt open. The attempt's log entry SHALL carry a Hypothesis equal to the saved text, ignoring spacing.

#### Scenario: Run is locked until a hypothesis exists
- **WHEN** a participant tries to run an attempt that has no saved hypothesis
- **THEN** the app refuses with a plain sentence that names the hypothesis step

#### Scenario: Log hypothesis differs
- **GIVEN** the log entry's Hypothesis differs from the saved text
- **WHEN** the attempt is checked
- **THEN** the check fails with the difference named and the log is not changed

### Requirement: Each attempt is scored on five fresh answers with the same rules
An attempt SHALL be scored by running the checker on its own five saved answers, with no AI call. Results SHALL be saved per criterion. Evidence SHALL be rejected as stale when the prompt, rules or answers changed after scoring, and a criterion set different from Iteration 0 SHALL be flagged as a coverage change, never counted as a gain.

#### Scenario: Script track
- **WHEN** five answers are saved in an attempt's `runs\`
- **THEN** `check.py` runs in the attempt folder and `results.json` holds per-criterion counts

#### Scenario: promptfoo track
- **GIVEN** the attempt folder holds a copy of the config and its local files
- **WHEN** the attempt is scored
- **THEN** the original config is unchanged and the results come from the copy

#### Scenario: Answers changed after scoring
- **WHEN** a run file differs from the hash recorded at scoring
- **THEN** the result is shown as out of date and the attempt cannot be kept until it is run again

#### Scenario: Coverage changed
- **WHEN** an attempt reports a different set of criteria from Iteration 0
- **THEN** the change is flagged in plain words, and a criterion that became NOT CHECKED is shown as lost coverage

### Requirement: The known-good check is chosen first and reported apart
The participant SHALL save a known-good answer before its score is shown. The result SHALL be reported as passing at 95% or more of checked results or as below that, with a next step that never loosens a rule. It SHALL be kept separate from the five-answer score, and neither SHALL be merged into one pass or fail. On the promptfoo track a `known-good` test SHALL be added to the attempt's copied config using assertions copied from existing tests, and the checker hash SHALL ignore it.

#### Scenario: Below 95%
- **WHEN** the known-good answer scores under 95%
- **THEN** the app suggests checking the checker or the written requirements and offers no way to loosen a rule

#### Scenario: Score not shown early
- **WHEN** no known-good answer is saved
- **THEN** no known-good score is returned

#### Scenario: A repair changes verdicts
- **GIVEN** a corrected checker changes Iteration 0's verdicts
- **WHEN** the participant continues
- **THEN** the app asks for the original five answers to be rerun before any attempt is compared

### Requirement: The five-answer score is a target, not a gate
A five-answer overall score below 95% SHALL give a suggested next step and SHALL NOT block completion. Completion SHALL require verified evidence of two documented rounds after Iteration 0. Flat or reverted attempts SHALL be recorded as such and described as "no measured gain on these rules", never as improvements.

#### Scenario: Below target, two rounds documented
- **GIVEN** two documented rounds whose latest score is under 95%
- **WHEN** completion is checked
- **THEN** it passes and shows a next step

#### Scenario: Only one round
- **GIVEN** one documented round
- **WHEN** completion is checked
- **THEN** it does not pass and says one more round is needed

### Requirement: The log carries a decision line and is only read
`parse_iteration_log` SHALL read a `Decision` field with the value `kept`, `undone` or `pending` and return it with the entry. The app SHALL check each Part 4 entry's decision against the manifest, each entry's counts and NOT CHECKED items against its saved results, and that its Change, Result and Reasoning are not empty. It SHALL read the log of the chosen starting point. The app SHALL never edit the log, read terminal output or call a model. Part 3's baseline gate SHALL behave as before.

#### Scenario: Decision matches
- **GIVEN** the manifest says attempt 2 is undone and its log entry says `Decision: undone`
- **WHEN** the log is checked
- **THEN** that item passes

#### Scenario: Decision differs
- **GIVEN** the manifest says kept and the log says undone
- **WHEN** the log is checked
- **THEN** the check fails and names both values

#### Scenario: Empty Reasoning
- **GIVEN** the entry's Reasoning has no text
- **WHEN** the log is checked
- **THEN** the check fails and says the Reasoning is missing, and the log is not changed

#### Scenario: Text is only checked for presence
- **GIVEN** the entry's Change, Result and Reasoning each hold any text
- **WHEN** the log is checked
- **THEN** the presence item passes whatever the text says

#### Scenario: Part 3 gate unchanged
- **GIVEN** a log with entries 0, 1 and 2
- **WHEN** the Part 3 baseline gate runs
- **THEN** it reads only Iteration 0 and gives the same result as before

### Requirement: Participant work is preserved
The app SHALL NOT overwrite or delete an existing participant file when creating or resuming an attempt, SHALL resume from `parts.part-4` when it exists, and SHALL show Part 4 on the Series map as a Part with content once its course ships.

#### Scenario: Existing attempt folder
- **GIVEN** `part-4\attempts\1\` already holds participant files
- **WHEN** the attempt is resumed
- **THEN** no file in it is overwritten

#### Scenario: Older progress
- **GIVEN** a `progress.json` saved before this change
- **WHEN** it is loaded
- **THEN** it loads unchanged and `parts.part-4` starts empty

### Requirement: Iteration 0 comes from the chosen starting point
The attempt engine SHALL read Iteration 0's prompt, test cases, checker, five answers and log from the project's own Part 3 files when the starting point is the participant's baseline, and from `part-4\practice\` when it is the Practice baseline. The chosen starting point SHALL be saved in `parts.part-4` as an id and never as text. A `progress.json` with no saved starting point SHALL mean the participant's own baseline.

#### Scenario: Own baseline
- **GIVEN** the starting point is the participant's baseline
- **WHEN** attempt 1 is created
- **THEN** its starting files are copies of the project's Part 3 files

#### Scenario: Practice baseline
- **GIVEN** the starting point is the Practice baseline
- **WHEN** attempt 1 is created
- **THEN** its starting files are copies of the files in `part-4\practice\`, and the project's own files are not read

#### Scenario: Older progress
- **GIVEN** a `progress.json` saved before this change, with attempts and no starting point
- **WHEN** it is loaded
- **THEN** it loads unchanged and the starting point is the participant's baseline
