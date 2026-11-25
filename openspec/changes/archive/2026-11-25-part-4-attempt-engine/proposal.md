# Proposal

## Why

Issue #15 asks for Part 4, where the participant improves their prompt one change at a time and leaves a log that Part 5 can audit. Today every Part 3 file lives at the project root and the log gate expects a single Iteration 0 entry, so nothing can hold several attempts side by side. The handoff contract agreed in `curriculum-handoffs-stage3-alignment` (`docs/SPEC.md` "Evidence handoff") needs per-attempt storage, a manifest and a kept pointer before any course content is written. This is slice A of three (A attempt engine, B course content, C harness coverage). It builds and tests the engine on the stand-in with no participant-facing course, so the contract risk is settled before content depends on it.

## What Changes

- **Attempt storage.** Each attempt `n` lives under `part-4\attempts\<n>\`: its own prompt, test cases, checker (the script, or a copied promptfoo config), `runs\run-1` to `run-5`, `results.json` and `hypothesis.md`. Part 3's files are never edited.
- **Manifest in `parts.part-4`.** Chronological `{n, parent, log_entry, model, hashes, results, decision}` records, hashes and counts only, never text. The kept version is the last attempt whose decision is `kept` (Iteration 0 if none), set only by an explicit keep or undo.
- **Hypothesis before scoring.** A locked step saves the hypothesis to the attempt folder and its hash to the manifest before the edit and the run steps open. The log entry's Hypothesis must match it, ignoring spacing.
- **Checker runs per attempt.** The existing script and promptfoo runners are pointed at an attempt folder. On the promptfoo track each attempt copies the config and the `known-good` test is added at the known-good step, with assertions copied from existing tests. The checker hash ignores it.
- **Known-good check, reported apart from the five-answer score.** The participant chooses the known-good answer before its score is shown. A score under 95% gives a next step and never loosens a rule. The five-answer score is a coaching target and never a gate.
- **Log parser and gate.** `parse_iteration_log` reads a `Decision` field (`kept`, `undone`, `pending`). A Part 4 gate compares each attempt's log entry with its saved results by reusing the Part 3 count and NOT CHECKED checks, rejects stale or mismatched evidence and flags a changed criterion set. It never edits the log.
- **Part registration kept dark.** The Part and its step kinds are registered and tested, with placeholder-free engine content only. The Series map row for Part 4 stays "Coming soon" until slice B.

## Capabilities

### New Capabilities
- `part-4-attempts`: how a Part 4 attempt is stored, scored and recorded, how the kept pointer and manifest work, how the hypothesis and known-good steps are ordered, and how the log is checked against saved results.

### Modified Capabilities
<!-- None. The part-registry and series-map requirements are met as they stand; the Series row flips in slice B. -->

## Impact

- Code: new attempt module and step kinds; `state.py` (Part 4 entry and default step records); `parsers.py` (`Decision` field); `baseline.py` and `gates.py` (reuse of count checks and a folder-based run and hash); `promptfoo.py` (attempt config copy).
- Storage: `part-4\attempts\<n>\...` in the project folder and `parts.part-4` in `progress.json` (hashes and counts only).
- Docs: `docs/SPEC.md` "Evidence handoff" moves from "Not yet built" to built for the attempt side. Tests land with each task group.
- Out of scope: course lessons, glossary, the worked Practice task and its content, the Series map row, harness stages, any Part 5 behavior, any `web/` or interface change (AGENTS.md rule 11), and any real AI run.
