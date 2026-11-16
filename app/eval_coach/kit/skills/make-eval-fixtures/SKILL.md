---
name: make-eval-fixtures
description: Write two test outputs for a prompt-evaluation checker, for any task, from a markdown test-case file and the prompt: a clearly bad output, and a polished-but-wrong output that meets the thresholds as written while breaking a requirement. Use when asked to make fixtures or test outputs that check whether a checker can be trusted.
argument-hint: "[path to test-cases.md] [path to prompt file]"
---

# Make eval fixtures

A checker is only as good as the thresholds behind it. Fixtures are outputs written on purpose to test those thresholds. This skill works for any task: assume nothing about the subject matter. Everything specific to the task comes from the user's files.

## Input

- A markdown test-case file: a test input section, criteria with requirement and threshold, and any supporting lists. Criteria can appear as blocks or as a table. If the user gives no path, look for a file whose title mentions "test cases".
- The prompt file (for example `prompt-v0.md`), to learn what kind of artifact the task produces. If there is none, rely on the requirements and the test input, and say so.

Do not read or open the checker (a script or a config), or any saved model output in `runs/` or similar. The fixtures must be written without knowing how the checker works.

## What to write

Write plain-text files in `fixtures/` next to the test-case file. Each one must look like a real output for this task: the same kind of artifact, the same rough length and format the prompt asks for. If the artifact is structured (for example JSON), write it in that format and keep the `.txt` extension. No meta commentary, and no mention of tests, fixtures or thresholds inside the files. If a criterion sets a length limit, count the words to confirm each fixture is on the side of the limit you intend.

1. **`fixture-bad.txt`**: a careless first attempt. It breaks most of the format, structure, length and tone requirements. It may still use facts from the test input.
2. **`fixture-polished-but-wrong.txt`**: it looks right, and it meets the thresholds as written, but it breaks a requirement in substance. To write it:
   1. For each criterion, put its Requirement next to its Threshold and note the gap: what the requirement asks for that the threshold does not actually check. Typical gaps: a threshold that checks a label exists but not what follows it; a keyword check that does not check meaning; a coverage check that a passing mention satisfies; a check that a number appears but not that it is used correctly; no check against invented facts.
   2. Pick the one or two biggest gaps.
   3. Write an output that satisfies the threshold wording for every criterion that can be checked by rule, and still violates the requirement. Typical moves: state something that contradicts the test input; invent a fact, number or name; mention the required keyword in a throwaway phrase while leaving out the real content; use the right structure with the wrong content.
   4. If every threshold is airtight, say so in the answer key. Do not force a gap.

Skip criteria whose threshold relies on judgment (words such as clear, good, professional): they cannot be checked by rule, so they do not count when deciding whether the polished fixture passes.

## Answer key

Write `fixtures/answer-key.md`, and do not show its contents in your reply. The user predicts first and reads the key afterwards. For each fixture list:

- For every criterion: whether a good checker should pass or fail it, judged against the requirement, and whether the threshold as written would likely let it through or wrongly reject it.
- Any thresholds that conflict with each other in this fixture or in a normal good output (for example one criterion that forbids what another requires). Note the conflict; do not resolve it.
- For the polished-but-wrong fixture: what is wrong with it, which requirement it breaks, and which threshold wording lets it through.

## Reply

Name the two fixture files and the answer key, and give one short line about the style of each fixture (for example its length and tone), without saying what is wrong with it. Then tell the user: "Fill in your predictions in your predict grid before opening the answer key." Nothing else.

## Guardrails

- Create files only in `fixtures/`. Do not modify the test-case file, the prompt, or any other file.
- Do not read the checker or the outputs.
- Do not use real personal or client data; use only what is in the test input, plus invented details where inventing is the point.
