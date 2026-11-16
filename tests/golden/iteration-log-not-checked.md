## Iteration 0: baseline
- Date: 2026-11-09
- Prompt: prompt-v0.md
- Model: mid-tier-model
- Runs: 5
- Overall: 9 / 10
- Not checked: 1 (C3)

| Criterion | Passed | Rate | Notes |
| --- | --- | --- | --- |
| C1 Length | 4/5 | 80% | fails: run-3 |
| C2 Mentions the order number | 5/5 | 100% |  |
| C3 Tone is professional | not checked | n/a | needs a rewrite |

- Hypothesis: The first criterion fails when the model adds an apology.
- Change:
- Result:
- Reasoning:

## Iteration 1: shorter prompt
- Date: 2026-11-10
- Prompt: prompt-v1.md
- Model: mid-tier-model
- Runs: 5
- Overall: 10 / 10
- Not checked: 1 (C3)

| Criterion | Passed | Rate | Notes |
| --- | --- | --- | --- |
| C1 Length | 5/5 | 100% |  |
| C2 Mentions the order number | 5/5 | 100% |  |
| C3 Tone is professional | not checked | n/a | needs a rewrite |

- Hypothesis: A shorter prompt keeps every answer under the limit.
- Change: Cut the prompt to three sentences.
- Result: C1 now passes in every run.
- Reasoning: The limit was being exceeded by the extra sentences.
