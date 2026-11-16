---
name: build-promptfoo-config
description: Turn a markdown test-case file (criteria with pass/fail thresholds, for any task) into a deterministic promptfoo config that scores saved AI outputs without calling a model, explain the config with runnable examples, and log baseline pass rates. Use when asked to build, explain, run, or log results for a promptfoo evaluation from test cases.
argument-hint: "[path to test-cases.md] [build | explain | run + log]"
---

# Build a promptfoo config

The test-case file is the spec. The promptfoo config is an implementation of it. This skill works for any task: assume nothing about the subject matter. Everything specific to the task comes from the user's files. Translate faithfully; do not improve, loosen, or tighten any threshold. Requires Node.js (`node --version`) and Python 3 for the summary helper.

## Input

A markdown test-case file. If the user gives no path, look for a file whose title mentions "test cases"; if there are several, ask which one.

Expected shape: a test input section, a list of criteria, and supporting lists. Criteria usually appear as `### C<n>: name` blocks with Requirement, Type and Threshold lines, but accept any layout that carries the same information, such as a criteria table (columns like #, Requirement, Criterion, Format or content, Threshold) or a numbered list. For each criterion capture:

- **ID**: `C<n>` from the file's number.
- **Name**: the short name or Criterion column; if absent, the Requirement text.
- **Requirement and threshold**: as written. Decide what to build from the threshold wording; Type is only a label.

Lists may sit in a supporting-lists section or inside a threshold. Never edit the file. If something is missing, carry on and say what you assumed.

Saved model outputs live in any folder the user names (for example `runs/`), one file per run (`run-1.txt`, `run-2.txt`, ...). If none is named, use `runs/`. Fixture files can be referenced from wherever they are. Example files for Mode 2 live in `examples/` next to the test-case file.

Pick the mode from the request: **build** (default), **explain**, **run + log**, or **live** (promptfoo generates the outputs through the user's own agent CLI, no API key).

## Threshold patterns

Map every threshold to exactly one of these, or to NOT CHECKED. The same patterns work for any subject.

| The threshold says | The assertion |
| --- | --- |
| Under, over, at most, at least or exactly N words | `word-count` with `min` and/or `max` (both inclusive, so "under 150" is `max: 149`) |
| Characters, lines or sentences | `javascript` |
| Contains all of a list | `icontains-all` |
| Contains any of a list | `icontains-any` |
| At least k of a list | `javascript` |
| Contains none of a list (banned words, banned symbols) | `not-icontains-any` |
| A label ending in a colon appears | `contains-all` (exact text, anywhere) |
| A heading-style label appears (a name that introduces a group of items) | `regex`: a line starts with the name, ignoring bullets, `#` and bold markers, then a colon or the end of the line |
| No line uses a given heading pattern | `not-regex` with the pattern |
| Starts with exact text | `starts-with` |
| Ends with exact text | `javascript` |
| Matches a format (date, id, email or another pattern) | `regex` |
| Is valid JSON, or the top level has certain keys or N elements | `is-json` with a schema (`type`, `required`, `minItems`, `maxItems`) |
| Every item (or every value of a field) has certain keys, matches a pattern, or is one of a list | `is-json` with a schema (`items`, `required`, `pattern`, `enum`). "One of a list" is a whole-value match; `enum` is case-sensitive, so use `pattern` with character classes when case should be ignored. |
| Has N list items or sections in text | `javascript` counting matching lines |
| Every number in the output also appears in the test input | `javascript` with the test input inlined |
| Every item in the test input is covered | `icontains-all` with a keyword per item |
| The text after a label mentions a term | `regex` or `javascript` |

**NOT CHECKED** applies when the threshold relies on judgment or meaning: words such as clear, good, concise, professional, relevant, accurate, helpful, natural, appropriate, or anything that needs the text to be understood. Do not guess, do not turn it into a word list on your own, and never use `llm-rubric`, `similar`, `model-graded-*`, `factuality`, `select-best`, or any assertion that needs a model or an API key. Suggest a rewrite that names the pattern and leaves the terms to the user, for example `Passes if at least 1 of <your terms> appears`, and name the proxy's weak point in a few words. Do not invent the terms.

## Defaults

Apply these unless the threshold says otherwise, and list each one you relied on under Interpretation choices.

- **Limits:** "under" and "over" are strict; "at most" and "at least" are inclusive. Words are whitespace-separated tokens.
- **Terms and lists:** case-insensitive substring match (use the `icontains-*` assertions).
- **Exact wording:** text given as the exact start, end or label (for example `starts with "..."`, or a label ending in a colon) is matched exactly, including case.
- **Labels:** a label ending in a colon counts wherever it appears. A heading-style label must start its own line, ignoring bullets, `#` and bold markers, followed by a colon or the end of the line; its name is matched case-insensitively, and a name inside a sentence is not a heading label. If a label appears more than once, any occurrence may satisfy the threshold. A missing label fails.
- **Text after a label:** the rest of that label's line, up to the next label on that line. The next label is one of the labels named in the test-case file; if there are none, a single word ending in a colon.
- **Numbers:** a run of digits with optional `.` or `,` between digits, compared as whole tokens. Ignore the numerals that begin numbered-list lines; they are formatting, not claims.
- **List items:** a line that starts with a bullet marker, or with digits followed by `.` or `)` and a space.
- **Structured output:** do not strip code fences, prose or other wrapping before parsing unless the threshold says so. If several criteria depend on the same parse, each one fails with the parse reason; say so.
- **Missing parts:** a criterion about the items that have a field applies only to items that have it; the criterion that requires the field catches the missing ones. An "every" check passes on an empty collection; say so.

## Mode 1: Build

1. Read the test-case file and list each criterion with its ID, name and threshold.
2. Assign each criterion one pattern from the table, or NOT CHECKED.
3. Write `promptfooconfig.yaml` next to the test-case file using this shape:

```yaml
description: <task name> checks
prompts:
  - "{{output}}"
providers:
  - echo
defaultTest:
  assert:
    # C1: <threshold quoted verbatim>
    - type: word-count
      metric: C1_<short_name>
      value:
        max: 149
    # C2: <threshold quoted verbatim> (NOT CHECKED: needs judgment; suggested rewrite: <rewrite>)
    - type: javascript
      metric: C2_<short_name>
      value: "({ pass: false, score: 0, reason: 'NOT CHECKED: needs judgment' })"
    # Empty outputs must not pass "must not contain" checks
    - type: javascript
      metric: non_empty
      value: output.trim().length > 0
tests:
  - description: run-1
    vars:
      output: file://runs/run-1.txt
```

   - The `echo` provider returns the prompt unchanged, so each saved output is checked as-is. No model and no API key are involved.
   - Put assertions in `defaultTest.assert` so every test gets the same checks. Add one `tests` entry per output file. Name saved model outputs `run-<n>`, known fixtures `fixture-<name>` and Mode 2 examples `example-<name>` so they can be summarized separately.
   - Use built-in deterministic assertions first. Use `javascript` only when no built-in can express the threshold; keep it under 10 lines and add a comment saying why. Prefix any assertion with `not-` to negate it.
   - A `javascript` value on a single line is an expression: write `output.trim().length > 0`, with no `return`. A multi-line value is a function body: it needs an explicit `return`. The NOT CHECKED stub must stay a single-line expression, as shown.
   - Every assertion carries `metric: C<n>_<short_name>`. A criterion that needs several assertions repeats the same metric on each; it passes only if all of them pass.
   - Add a comment above each criterion quoting its threshold verbatim.
   - Quote YAML values that contain special characters such as `!`, `:` or `#`.
   - `regex` has no flags. Use `(?:^|\n)` for "start of a line" and `(?::|\r?\n|$)` for "end of a label"; output files from Windows contain `\r\n`. For case-insensitive regex, use character classes such as `[Aa]`.
   - A `javascript` assertion that needs the test input gets it inlined as a constant with the comment `// copied from the test input in <file>; update if it changes`.
4. Run the command from Mode 3, step 1, and fix config errors until it runs. A failing assertion is a result, not an error. Because every NOT CHECKED stub fails, promptfoo reports every test as failed and exits non-zero while any criterion is NOT CHECKED; that is intended.
5. Report, in this order:
   - Where `promptfooconfig.yaml` is and the exact command to run it.
   - **NOT CHECKED**: each criterion, why, and the suggested rewrite. Say plainly that these criteria are not covered yet.
   - **Interpretation choices**: every place a threshold left room and what you chose, one line each (the defaults you relied on, substring or whole word, how list items and numbers are detected).

## Mode 2: Explain (read-back)

For every checked criterion, produce evidence, not just a description:

1. Write two tiny files in `examples/`: `c<n>-pass.txt` (text that should pass this criterion) and `c<n>-fail.txt` (text that should fail it). Other criteria may fail on them; that is fine.
2. Add them to the config as tests named `example-c<n>-pass` and `example-c<n>-fail`, run it, and compare the verdict for that criterion with what you expected. Report every mismatch as a finding. Do not quietly fix it.
3. For each criterion, in plain language and without YAML, say: the threshold as written, exactly what the assertion(s) check, and anything the config does that the threshold does not say or fails to do that it does say.

For NOT CHECKED criteria, restate the suggested rewrite. End with: "If this is not what you meant, which threshold in the markdown would you change?"

## Mode 3: Run and log

1. Set `PROMPTFOO_DISABLE_TELEMETRY=1` (PowerShell: `$env:PROMPTFOO_DISABLE_TELEMETRY='1'`; bash: `export PROMPTFOO_DISABLE_TELEMETRY=1`), then run: `npx --yes promptfoo@0.125.1 eval -c promptfooconfig.yaml --no-cache --no-table --no-write -o results.json` (`--no-write` keeps promptfoo from saving run history on the machine; `results.json` is still written). A non-zero exit code only means at least one check failed, so run the summary as a separate command (do not chain it with `&&`).
2. Summarize with [summarize_results.py](./summarize_results.py): copy it next to the config and run `python summarize_results.py results.json`. To summarize only some tests, add a name prefix: `python summarize_results.py results.json run-` covers only the `run-<n>` tests. Show the output as printed.
3. Ask for the prompt file name and the model if you do not know them; use today's date. Append an entry to the user's log (default `iteration-log.md` next to the test-case file, create it if missing): `Iteration 0: baseline` if the log has none, otherwise the next number. Log only the `run-<n>` tests and only the `C<n>` metrics (not `non_empty`); never log fixtures or examples. Log the baseline after the thresholds are settled; if they change afterwards, ask whether to replace Iteration 0 or add a new entry, and say that the logged numbers used the earlier thresholds. Format:

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

   Fill Date, Prompt, Model, Runs, Overall, Not checked and the table. Round rates to whole percents. In Notes, list failing test names, and write "needs a rewrite" for NOT CHECKED criteria. Leave Hypothesis, Change, Result and Reasoning empty.
4. Never edit the config to make a failing output pass. A failing result is the information. If a result looks wrong (a known-bad output passes, or a good output fails), say which threshold wording caused it and propose a change to the markdown threshold. Once the markdown is updated, update `promptfooconfig.yaml` to match: change only the assertions whose threshold changed.

## Mode 4: Live (generate the outputs through the user's own agent)

Use when the user wants promptfoo to produce the outputs itself instead of pasting saved runs. The provider is the user's own agent CLI (GitHub Copilot CLI, Claude Code or Devin CLI), launched by [agent-provider.js](./agent-provider.js) through promptfoo's `exec:` provider. It signs in with the CLI's own login, so there is no API key. It runs the CLI from an empty temp folder, so the agent cannot read `test-cases.md`.

1. Copy `agent-provider.js` next to `promptfooconfig.yaml`. Do not edit it. Find which CLI to use: ask the user, or check `copilot --version`, `claude --version` and `devin --version`. Write the answer in `cli:` below. Ask for the model (mid-tier) and write it in `model:`; if they do not know, omit `model:`.
2. Write `promptfooconfig.live.yaml` next to the main config. Copy the `defaultTest.assert` block from `promptfooconfig.yaml` unchanged, including the comments, and use this shape:

```yaml
description: <task name> live runs
prompts:
  - file://prompt-v0.md
providers:
  - id: 'exec: node ./agent-provider.js'
    label: my-agent
    config:
      cli: <copilot | claude | devin>
      model: <model name>
defaultTest:
  assert:
    # same assertions as promptfooconfig.yaml
tests:
  - description: run-1
  - description: run-2
  - description: run-3
  - description: run-4
  - description: run-5
```

   - One test per run, named `run-<n>`, so `summarize_results.py` and the log work as in Mode 3.
   - Keep the two configs' assertions identical. When a threshold changes, change both files.
   - If `prompt-v0.md` contains `{{` or `{%`, tell the user; promptfoo reads those as template syntax.
3. Run: `npx --yes promptfoo@0.125.1 eval -c promptfooconfig.live.yaml --no-cache --no-table --no-write -o results-live.json`, then `python summarize_results.py results-live.json run-`. Each live run is a new answer, so scores can differ from run to run; say so.
4. Provider errors (the CLI is not signed in, or is not found) are not results. Report the error text and have the user fix the login or the `cli:` value. Do not switch to an API key.
5. To log the baseline from live runs, follow Mode 3 steps 2 to 4 using `results-live.json`.

## Guardrails

- Do not modify the test-case file or any output file unless asked; propose edits instead.
- Do not set provider API keys. The only model provider allowed is `agent-provider.js` in Mode 4, which uses the user's own signed-in agent CLI. Everything else stays on `echo`.
- Never use a model-graded assertion, in any mode: the model generates the outputs, never the grades.
- Run only promptfoo, `summarize_results.py`, `agent-provider.js`, Python, Node and basic file and folder commands.
