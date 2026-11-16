# Change: write the answer key after predictions lock

Read `docs/SPEC.md` first. Its non-negotiable rules still apply. Merge this change into SPEC.md when it is done, so SPEC.md stays the single source of truth.

## Why
A real Claude Code test showed the CLI writes `answer-key.md` with a shell command, and the approval prompt prints the whole command. The participant must approve it, so the key is on screen before they predict. Asking people not to read it is not a safeguard. The fix is structural: the key does not exist until predictions are locked.

## New step order
`generate, build, fixtures, readback, predict, key, run, fix`

| Step | CLI starts in | Line the app types (exact) |
|---|---|---|
| fixtures | `<home>\fixtures-work` | `Read skills/make-eval-fixtures/SKILL.md and follow it for test-cases.md and prompt-v0.md, with one change: write only the two fixture files. Do not write the answer key, and do not say what is wrong with either fixture.` |
| key (new) | `<home>\key-work` | `Read skills/make-eval-fixtures/SKILL.md. The two fixture files are already in fixtures/. Do not change them. Follow only the Answer key section, using test-cases.md, and write fixtures/answer-key.md. Do nothing else.` |

`skills/make-eval-fixtures/SKILL.md` stays byte-identical to the source. The typed line carries the change.

## Behavior

**fixtures**
- Gate: `fixture-bad.txt` and `fixture-polished-but-wrong.txt` are non-empty in `<home>\fixtures-work\fixtures\`, and `<project>\fixtures\answer-key.md` does not exist. A key is no longer required.
- On pass: copy the two outputs to `<project>\fixtures\`.
- If the CLI wrote `answer-key.md` under `fixtures-work` anyway, delete it when the gate passes and add this non-blocking nudge: `Your CLI wrote an answer key anyway. The app deleted it, and a new one will be written after you lock your predictions. If you saw what it said, predict as honestly as you can.`
- After a pass, no answer key exists anywhere: not in `fixtures-work`, not in `key-work`, not in sealed storage.

**key (new, follows predict)**
- Locked until predict is done, which requires locked predictions. `/api/step/start`, `/send` and `/check` for `key` are rejected before that, as for any locked step.
- Start clears `<home>\key-work\` and writes exactly: `test-cases.md` (the project's current copy), `prompt-v0.md`, `skills/make-eval-fixtures/SKILL.md`, `fixtures/fixture-bad.txt`, `fixtures/fixture-polished-but-wrong.txt` (from the project). It must not contain `check.py`, `runs/` or anything else.
- Gate: `<home>\key-work\fixtures\answer-key.md` is non-empty; both fixtures in `key-work` still hash the same as the project's copies; `<project>\fixtures\answer-key.md` does not exist.
- On pass: **move** the key to sealed storage (same path as today).
- `key.data = {"files":[{"name":"answer-key.md","present":bool}],"key_held":bool}`. Remove `key_held` from `fixtures.data` and drop the key from its `files`.

**run**
- Unchanged: requires locked predictions, and `answer_key_markdown` is returned only after the checker run succeeded on that state. Key text must never appear in any API response before that.

**Resuming older progress**
A `progress.json` without a `key` entry must load without error. If it has one, nothing changes. Treat `key` as done when the sealed key exists and predict is done, otherwise locked or active by the normal rules.

## Content (`content/steps.json`, exact text)

`fixtures`:
- `goal`: `Have a new chat write two test outputs, without seeing your checker.`
- Replace the `why` item that begins "The answer key is sealed" with: `The answer key comes later, after you lock your predictions. A prediction is only useful if you commit to it first.`
- Remove the instruction that begins "Your CLI may show the contents of answer-key.md".
- Replace the instruction that begins "It writes fixture-bad.txt" with: `It writes fixture-bad.txt and fixture-polished-but-wrong.txt. A long approval request may not fit in the terminal, so scroll up to read all of it before you answer.`
- Replace the last instruction with: `Press Check my work. The app copies the two fixtures into your project.`
- Remove the `key` gate entry.

`readback` and `fix`: add this instruction right after the one that mentions Send: `A long approval request may not fit in the terminal. Scroll up to read all of it before you answer.`

`predict`: replace the `why` item that begins "The answer key stays sealed" with: `The answer key does not exist yet. It is written after you lock, so nothing can influence your predictions.`

`run`: `why` and `instructions` stay as they are.

New `key` step (insert between `predict` and `run`):
```json
{
  "title": "Write the answer key",
  "goal": "Now that your predictions are locked, have a new chat write the answer key for your two fixtures.",
  "why": [
    "The key is written only after you lock, so it cannot influence your predictions, even if your CLI shows it on screen.",
    "This is a new chat in a folder with only your test cases, your prompt, one skill and the two fixtures. It cannot open check.py or your runs.",
    "The key judges each fixture against your requirements, not against what the checker happens to do."
  ],
  "instructions": [
    "Press Start. A new chat opens in the answer key folder.",
    "If your CLI asks whether to trust the folder, choose the yes option. The highlighted default may be No. If your CLI exits, use Start again.",
    "When the CLI is ready, press Send. If your CLI asks for approvals, they appear in the terminal. A long approval request may not fit, so scroll up to read all of it before you answer.",
    "Your CLI may show the key as it writes it. That is fine now, because your predictions are locked.",
    "Press Check my work. The app seals the key away from your project folder. You will read it in the next step, after the checker has run."
  ],
  "line": "<the exact key line above>",
  "folder_label": "Answer key folder (test cases, prompt, one skill and the two fixtures only)",
  "troubleshooting": [
    {"problem": "The agent cannot read the skill file.", "fix": "Paste the text of SKILL.md into the terminal and add \"Follow these instructions\" before the line."},
    {"problem": "The agent changed a fixture.", "fix": "Press Stop, then Start, and send the line again. The app restores both fixtures when you start."},
    {"problem": "The file is missing.", "fix": "Look at the terminal. If your CLI is set to ask for approval, it may be waiting for you. Answer it there, then press Check my work again."},
    {"problem": "Your CLI reports a temporary error.", "fix": "Wait a moment and ask it again in the terminal."}
  ],
  "gate": {
    "key": {"label": "Answer key written", "ok": "", "fail": "answer-key.md was not found, or it is empty."},
    "fixtures_unchanged": {"label": "Fixtures unchanged", "ok": "", "fail": "A fixture changed during this step. Press Stop, then Start, and send the line again."},
    "no_key_in_project": {"label": "No answer key in your project", "ok": "", "fail": "An answer-key.md is in your project's fixtures folder. Delete it, then press Check my work again."}
  }
}
```

## Tests
- Backend: fixtures gate passes with no key; stray key deleted with nudge; no key anywhere after fixtures; `key` locked before predictions lock; `key-work` holds exactly the five files; gate fails on missing key and on a changed fixture; key moves to sealed and leaves `key-work`; answer key withheld from every API response until the run succeeded; old `progress.json` without `key` loads, both with and without a sealed key.
- Frontend: the mock and specs cover the new step.
- Stand-in end-to-end: `e2e-work/harness` gains a `key` stage. Assert at the end of the fixtures stage that no answer key exists anywhere, and assert that the key-session stand-in is the first thing to create one.
