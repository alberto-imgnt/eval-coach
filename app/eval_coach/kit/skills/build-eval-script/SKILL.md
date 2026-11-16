---
name: build-eval-script
description: Turn a markdown test-case file (criteria with pass/fail thresholds, for any task) into a deterministic Python checker that scores saved AI outputs, explain the checker with runnable examples, and log baseline pass rates. Use when asked to build, explain, run, or log results for a prompt-evaluation script from test cases.
argument-hint: "[path to test-cases.md] [build | explain | run + log]"
---

# Build an eval script

The test-case file is the spec. The script is an implementation of it. This skill works for any task: assume nothing about the subject matter. Everything specific to the task comes from the user's files. Translate faithfully; do not improve, loosen, or tighten any threshold.

## Input

A markdown test-case file. If the user gives no path, look for a file whose title mentions "test cases"; if there are several, ask which one.

Expected shape: a test input section, a list of criteria, and supporting lists. Criteria usually appear as `### C<n>: name` blocks with Requirement, Type and Threshold lines, but accept any layout that carries the same information, such as a criteria table (columns like #, Requirement, Criterion, Format or content, Threshold) or a numbered list. For each criterion capture:

- **ID**: `C<n>` from the file's number.
- **Name**: the short name or Criterion column; if absent, the Requirement text.
- **Requirement and threshold**: as written. Decide what to build from the threshold wording; Type is only a label.

Lists may sit in a supporting-lists section or inside a threshold. Never edit the file. If something is missing, carry on and say what you assumed.

Pick the mode from the request: **build** (default), **explain**, or **run + log**.

## Threshold patterns

Map every threshold to exactly one of these, or to NOT CHECKED. The same patterns work for any subject.

| The threshold says | The check |
| --- | --- |
| Under, over, at most, at least or exactly N words, characters, lines or sentences | Count and compare. |
| Contains all of a list, any of a list, or at least k of a list | Count the terms found and compare. |
| Contains none of a list (banned words, banned symbols) | No term is found. |
| A label ending in a colon appears | The label is found. |
| A heading-style label appears (a name that introduces a group of items) | A line starts with the name. |
| No line uses a given heading pattern | No line matches the pattern. |
| Starts or ends with exact text | Compare after trimming. |
| Matches a format (date, id, email or another pattern) | Regular expression. |
| Is valid JSON, or the top level has certain keys or N elements | Parse it, then check the structure. |
| Every item (or every value of a field) has certain keys, matches a pattern, or is one of a list | Parse it, then check each item. "One of a list" is a whole-value match, not a substring. |
| Has N list items or sections in text | Count matching lines. |
| Every number in the output also appears in the test input | Extract the numbers and compare with the test input. |
| Every item in the test input is covered | A keyword for each item is found. |
| The text after a label mentions a term | Look in the text after the label. |

**NOT CHECKED** applies when the threshold relies on judgment or meaning: words such as clear, good, concise, professional, relevant, accurate, helpful, natural, appropriate, or anything that needs the text to be understood. Do not guess, do not turn it into a word list on your own, and do not call an AI model from inside the script. Suggest a rewrite that names the pattern and leaves the terms to the user, for example `Passes if at least 1 of <your terms> appears`, and name the proxy's weak point in a few words. Do not invent the terms.

## Defaults

Apply these unless the threshold says otherwise, and list each one you relied on under Interpretation choices.

- **Limits:** "under" and "over" are strict; "at most" and "at least" are inclusive. Words are whitespace-separated tokens.
- **Terms and lists:** case-insensitive substring match.
- **Exact wording:** text given as the exact start, end or label (for example `starts with "..."`, or a label ending in a colon) is matched exactly, including case.
- **Labels:** a label ending in a colon counts wherever it appears. A heading-style label must start its own line, ignoring bullets, `#` and bold markers, followed by a colon or the end of the line; its name is matched case-insensitively, and a name inside a sentence is not a heading label. If a label appears more than once, any occurrence may satisfy the threshold. A missing label fails.
- **Text after a label:** the rest of that label's line, up to the next label on that line. The next label is one of the labels named in the test-case file; if there are none, a single word ending in a colon.
- **Numbers:** a run of digits with optional `.` or `,` between digits, compared as whole tokens. Ignore the numerals that begin numbered-list lines; they are formatting, not claims.
- **List items:** a line that starts with a bullet marker, or with digits followed by `.` or `)` and a space.
- **Decoration:** ignore `**`, `_` and backticks when matching labels and prefixes.
- **Structured output:** do not strip code fences, prose or other wrapping before parsing unless the threshold says so. If several criteria depend on the same parse, each one fails with the parse reason; say so.
- **Missing parts:** a criterion about the items that have a field applies only to items that have it; the criterion that requires the field catches the missing ones. An "every" check passes on an empty collection; say so.

## Mode 1: Build

1. Read the test-case file and list each criterion with its ID, name and threshold.
2. Assign each criterion one pattern from the table, or NOT CHECKED.
3. Write `check.py` next to the test-case file:
   - Python 3, standard library only, one file. No network, no model calls, no randomness. The same input always gives the same result.
   - Constants at the top for every list and limit, whether it sits in a supporting-lists section or inside a threshold. Copy values from the test-case file without surrounding quotation marks. If a check needs a helper list or pattern that is not in the file, mark it `# not in the test case file` and name it under Interpretation choices.
   - If a check compares against the test input, copy the test input into a constant with the comment `# copied from the test input in <file>; update if it changes`.
   - One function per criterion, in file order, named `check_c<n>_<short_name>(text)`. A comment directly above it starts with the criterion ID and quotes the threshold verbatim.
   - Each function returns `(result, reason)`: `True` or `False`, or `None` for NOT CHECKED. Reasons say what was found, for example `154 words (limit: under 150)` or `missing: <term>`. Give every NOT CHECKED criterion a function that returns `(None, "needs judgment: <suggested rewrite>")` for every file, so it shows up in every report.
   - Read files as UTF-8 and accept a BOM (`utf-8-sig`). Handle Windows line endings. Do not crash on non-ASCII text when printing.
   - The runner, not the criterion functions, handles empty input: if the file is empty or only whitespace, every checked criterion fails with the reason `empty output`.
   - Usage: `python check.py output1.txt [output2.txt ...]`. For each file print `== <file>`, then one line per criterion in the form `<ID> PASS|FAIL|NOT CHECKED  <name>: <reason>`, then `-> <p> passed, <f> failed, <n> NOT CHECKED`, then a blank line. With two or more files, finish with `== Pass rate per criterion` and one line per criterion (`C1 <name>: 2/3`, or `C3 <name>: NOT CHECKED`).
   - Exit code 0 only if every criterion is checked and passes for every file. Exit 1 if any criterion fails or is NOT CHECKED. Exit 2 for a usage error or an unreadable file.
   - Do not add criteria that are not in the file.
4. Self-test: create `examples/empty.txt` next to the test-case file and run the script on it. Every checked criterion must fail with `empty output` and nothing may crash. Do not run the user's outputs yet unless asked.
5. Report, in this order:
   - Where `check.py` is and the exact command to run it.
   - **NOT CHECKED**: each criterion, why, and the suggested rewrite. Say plainly that these criteria are not covered yet.
   - **Interpretation choices**: every place a threshold left room and what you chose, one line each (the defaults you relied on, substring or whole word, how list items and numbers are detected, helper lists you added).

## Mode 2: Explain (read-back)

For every checked criterion, produce evidence, not just a description:

1. Write two tiny files in `examples/` next to the test-case file: `c<n>-pass.txt` (text that should pass this criterion) and `c<n>-fail.txt` (text that should fail it). Other criteria may fail on them; that is fine.
2. Run `check.py` on them and compare the verdict for that criterion with what you expected. Report every mismatch as a finding. Do not quietly fix it.
3. For each criterion, in plain language and without code, say: the threshold as written, exactly what the script does, and anything the script does that the threshold does not say or fails to do that it does say.

For NOT CHECKED criteria, restate the suggested rewrite. End with: "If this is not what you meant, which threshold in the markdown would you change?"

## Mode 3: Run and log

1. Run `check.py` on the files the user names and show the output as printed.
2. Ask for the prompt file name and the model if you do not know them; use today's date. Append an entry to the user's log (default `iteration-log.md` next to the test-case file, create it if missing): `Iteration 0: baseline` if the log has none, otherwise the next number. Log the baseline after the thresholds are settled. If they change afterwards, ask whether to replace Iteration 0 or add a new entry, and say that the logged numbers used the earlier thresholds. Format:

```markdown
## Iteration 0: baseline
- Date:
- Prompt: <prompt file name>
- Model:
- Runs: <N>
- Overall: <sum of criterion passes across runs> / <checked criteria x runs>
- Not checked: <count, with IDs>

| Criterion | Passed | Rate | Notes |
| --- | --- | --- | --- |
| C1 <name> | 4/5 | 80% | fails: run-3 |
| C3 <name> | not checked | n/a | needs a rewrite |

- Hypothesis:
- Change:
- Result:
- Reasoning:
```

   Fill Date, Prompt, Model, Runs, Overall, Not checked and the table. Round rates to whole percents. In Notes, list failing file names without the extension, and write "needs a rewrite" for NOT CHECKED criteria. Leave Hypothesis, Change, Result and Reasoning empty. Log only real model outputs, never fixtures or examples.
3. Never edit the checker to make a failing output pass. A failing result is the information. If a result looks wrong (a known-bad output passes, or a good output fails), say which threshold wording caused it and propose a change to the markdown threshold. Once the markdown is updated, update `check.py` to match: change only the functions whose threshold changed.

## Guardrails

- Do not modify the test-case file or any output file unless asked; propose edits instead.
- Do not use an AI model to judge anything inside the script.
- Run only the checker, Python, and basic file and folder commands.
