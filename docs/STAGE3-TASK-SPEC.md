# Evaluated Systems (Stage 3): Intent and Task Spec

Audience: practitioners already fluent with AI tooling. This is a spec of what to deliver and prove. Official requirements: [Stage 3 Certification](https://improving.sharepoint.com/sites/GrowthLearning/SitePages/Stage-3-Certification.aspx). If this spec and that page differ, the page governs.

## 1. Intent

**Objective.** Submit a Stage 3 package for one task of your own: a structured prompt, an executable eval suite, and an iteration log showing measured improvement.

**Principle.** Trust in AI output comes from a rerunnable check, not from reading the output. Fluent output reads as correct whether or not it is, so "it looks fine" is not evidence, and "better" without a measurement is an opinion. Every claim ("better", "reliable") must resolve to a score from rules defined before the run. Output varies run to run, so one good answer proves little. Judge a prompt across several runs. The goal is neither blind trust nor blind distrust: state what good looks like, check for it, and keep a record (baseline, change, new score) that lets you show someone else why the result is reliable enough to use.

**Outcome.** You can:
1. State "good" as at least 3 pass/fail rules.
2. Show the checker itself is trustworthy.
3. Baseline a prompt across 5 outputs.
4. Improve it with before/after scores.
5. Show every instruction in the prompt earns its place.
6. Explain the result to a technical and a non-technical reader.

## 2. Constraints
- **Task:** your own; it repeats, has clear requirements, and its output is checkable by rules.
- **Eval approach (your choice):** Stage 3 accepts scripts, promptfoo files, or written test cases. Script-plus-markdown (e.g. a Python `check.py`) and promptfoo are two options among many. Research the available approaches and choose the one that best fits your task's output type, your skills, and what must be rerunnable. Whatever you choose, it must meet every requirement in this spec, and you should record your choice and why in the log or README.
- **Model:** evals must work with a mid-tier model (e.g. Sonnet or GPT-4). No top-end model may be required.
- **Agent:** any agentic tool that can run code and edit files. Chat-only tools do not qualify.
- **Rule:** never edit the checker to make a failing output pass. If the result is wrong, fix the spec.

## 3. Tasks (in order)

| # | Task | Done when |
|---|---|---|
| 1 | Write `prompt-v0` in a structured format (RTCC or equivalent). State the context you would otherwise leave implicit. | Every instruction is deliberate |
| 2 | Write ≥3 **distinct** rules as markdown test cases, each tied to a stated requirement and covering both format and content. Each rule gets a runnable pass/fail threshold or scoring guide. | Rules are not rewordings of one check |
| 3 | Build the checker from the test cases using your chosen eval approach (an agent may build it). | The checker runs end to end |
| 4 | **Verify the checker.** Make two fixtures: one clearly bad output and one polished-but-wrong output. Predict per-rule results for both **before** running. Run them, then reconcile every surprise by fixing the spec. | The bad fixture fails more than half the checked rules. The polished fixture fails at least one. |
| 5 | **Baseline.** Generate 5 outputs from `prompt-v0` on a mid-tier model and run the checker on all 5. Log it as `Iteration 0`. | Per-rule counts and the overall score are recorded |
| 6 | **Iterate test-first,** at least 2 rounds. Write or adjust the checks, see them fail, change the prompt until they pass, then tidy up. Rerun the same rules each time. | Each round has a score delta. A change that does not move the score did not help. |
| 7 | Confirm the checker scores ≥95% on a known-good output. | Score recorded |
| 8 | **Load-bearing audit.** Map each prompt instruction to the rule(s) it serves. Cut or rework the rest and any filler. | ≥90% of instructions map to a rule |
| 9 | Package for someone else to run. | The ZIP below is complete |

## 4. Deliverables (ZIP)

```
prompt.md          the final prompt (text file)
evals/             test cases + your runnable checker (script, promptfoo config, or other)
iteration-log.md   Iteration 0 plus ≥2 improvement rounds
README.md          optional: file layout and how to run
```

The layout is a suggestion. Stage 3 requires three artifacts: Prompt, Evaluations, Log.

Each log entry (`Iteration N`) records:
- **Prompt** and **Model** used.
- **Runs:** the number of outputs scored.
- A per-rule table of `passes / checked runs`.
- **Overall** score and a **Not checked** line.
- **Hypothesis**, **change made**, **new score** and **reasoning**, so each round leads causally to the next.

## 5. Proof

| Requirement | Threshold | Evidence |
|---|---|---|
| Rule quality | ≥3 distinct rules, each with an explicit pass/fail limit or scoring guide | Test cases or config |
| Checker trust | Bad fixture fails more than half the checked rules; polished-but-wrong fixture fails ≥1 | Fixture runs, with predictions made before running |
| Baseline | 5 outputs, per-rule counts | `Iteration 0` |
| Improvement | ≥2 rounds, test-first, score moves | Log with starting score, hypothesis, change, new score, reasoning |
| Ceiling | ≥95% on a known-good output | Recorded run |
| Load-bearing | ≥90% of instructions map to a rule; no filler | Instruction → rule map |
| Model fit | Passes on a mid-tier model | Model named in the log |

**Scoring.** `Overall = passes / checked results`. A NOT CHECKED rule is excluded from the denominator and must be listed explicitly, never silently dropped.

## 6. Suggested checks before submission
Self-check against these before you submit. They do not replace the [official Stage 3 requirements](https://improving.sharepoint.com/sites/GrowthLearning/SitePages/Stage-3-Certification.aspx).
- [ ] The task is your own.
- [ ] Every row of the proof table has evidence.
- [ ] The ZIP contains the Prompt, Evaluations and Log.
- [ ] Anyone can rerun the evals and get the same scoring.

