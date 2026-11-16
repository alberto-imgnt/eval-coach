# Answer key: Northwind example fixtures

Use this only if you are working with the Northwind example (the reference test cases and prompt). Everyone else gets their own answer key from the fixtures skill.

Verdicts are judged against the requirement. "Threshold" says whether the reference threshold as written lets the output through. The reference thresholds are the six in `northwind-test-cases-reference.md`.

## fixture-bad.txt

| Criterion | A good checker should | Reference threshold |
| --- | --- | --- |
| C1 Length | Fail (154 words, limit is under 150) | Catches it |
| C2 Grouped by client | Fail (organized by day, no client labels) | Catches it |
| C3 Blocker and ask | Fail (the wait for access is hinted at; no blocker or need is called out) | Catches it (no "Blocker:" or "Need:") |
| C4 Teams, not email | Fail (subject line, "Dear", "Regards") | Catches it |
| C5 Factual tone | Fail (boastful, exclamation marks) | Catches it |
| C6 Uses the rough notes | Pass (every note is covered) | Passes: all keywords are present |

## fixture-polished-but-wrong.txt

| Criterion | A good checker should | Reference threshold |
| --- | --- | --- |
| C1 Length | Pass (58 words) | Passes |
| C2 Grouped by client | Pass | Passes |
| C3 Blocker and ask | **Fail**: it says "Blocker: none this week", but the real blocker was half a day lost waiting on client test data access | **Lets it through**: both labels appear, and the check never looks at what follows them |
| C4 Teams, not email | Pass | Passes |
| C5 Factual tone | Pass | Passes |
| C6 Uses the rough notes | Pass in substance | Passes |

### What is wrong with it

- It reports no blocker when there was one, and says nothing is needed.
- It invents a $50k estimate and a budget confirmation. No criterion checks for invented facts.

### The fix

Tighten C3, for example: `Passes if a "Blocker:" label and a "Need:" label both appear, the text after "Blocker:" mentions "test data", and the text after "Need:" mentions "access"`. The polished fixture then fails C3 and nothing else changes.

That is still a proxy. A fixture that writes "Blocker: test data is fine. Need: access is not needed" would pass it. Tightening a keyword check is an arms race; deterministic checks narrow the gap, they do not close it. A criterion such as "every number in the output also appears in the test input" would catch the invented $50k.
