# Design

## Context

The Series map heading and intro come from `title` and `ui.intro` in `app/eval_coach/content/series.json`. The engine passes them through unchanged in `state.series` (`engine._series_view`), and `web/js/series.js` draws them as the page `<h1 id="step-heading">` and one `<p class="lede">`. The intro is plain text in one paragraph, so a longer string needs no markup, no new element and no style. See proposal.md for the motivation and the interface authorization.

The sidebar brand line on the map (`ui.brand_sub`) is a separate string in the same file and is drawn by `views.js` from `state.series.ui.brand_sub`. It reads "Evaluated Systems (Stage 3)".

## Goals / Non-Goals

**Goals:**
- The page heading reads "Evaluated systems" and the intro reads as approved in the proposal.
- The intro stays one paragraph in the existing element; no code and no markup change.
- A content test pins the intro's rules (questions, principles in order, no count or step wording, length) so later edits cannot drift back to procedure.

**Non-Goals:**
- No change to `web/`, `lesson-ui.json`, element ids, styles or the Part rows.
- No rename of the "series map" concept anywhere else.
- No new place for the dropped "do each one yourself" message.

## Decisions

1. **Content only.** Both strings live in `series.json`, which the engine and the mock API already read, so the stand-in, the Playwright mock (`tests/frontend/mock_api.py` loads the real file) and the app agree without code changes. Alternative: a separate heading element above the intro; rejected because it is an interface change that the user did not ask for.

2. **Remove and add, not modify, the intro requirement.** The old requirement's name ("about doing the work yourself") no longer describes it, and OpenSpec matches modified requirements by header. The delta removes it with a reason and adds two requirements: what the intro says, and what it must not do. Alternative: rename; rejected as it would hide the behavior change in a header edit.

3. **Pin the intro by rules, not by exact string.** Tests assert the structure that matters (opens with the two questions, contains the four principle phrases in order, ends with "a task of your own", none of the banned words, at most four sentences and 80 words) and not the whole sentence, so a wording polish does not break them. Alternative: assert the full string; rejected as brittle.

4. **One home for the intro tests.** `tests/test_series.py` holds the intro tests. The duplicate in `tests/test_participant_vocabulary.py` is changed to the new banned-word check (no "look ahead", no "Stage 3", no count, no step wording) and does not repeat the structure assertions.

5. **Heading assertions follow the title.** The Playwright specs wait for `#step-heading` to have the text "Series map" after going back to the map. Those expectations change to "Evaluated systems". Tests that mean the control or the concept ("Back to series map", test names that say "Series map:") keep their words. Alternative: a shared constant for the heading; rejected as out of proportion for a one-line change, but the apply step may use a local constant per spec file to avoid repeating the string.

## Files and storage touched

| Location | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/content/series.json` `title`, `ui.intro` | New words | Read-only content, shipped in the app |
| `docs/SPEC.md` "Series map" (the sentence on `ui.intro`) | Describe the new intro | Doc |
| `docs/temp/series-review-pending-changes.md` item 19 | Note that the intro was superseded | Working note |
| `tests/test_series.py`, `tests/test_participant_vocabulary.py` | Intro assertions | Tests |
| `tests/frontend/ui.spec.js`, `locking.spec.js`, `part1.spec.js`, `part2.spec.js` | Heading expectation | Tests |
| `dist/eval-coach.pyz` | Rebuilt by the build check, not hand-edited | Generated |

No `progress.json` key, storage key, browser storage entry or participant file is touched. Nothing is cleared.

## Risks / Trade-offs

- [The heading and the sidebar brand line now both read "Evaluated Systems" on the map] → Left as is and flagged as an open question; changing the brand line needs separate interface authorization.
- [A heading that is not "Series map" may make the screen harder to name for someone who has used the app before, since the Back control still says "series map"] → The user asked to keep the Back wording; the row list directly below the intro makes the page recognizable.
- [The intro is longer and denser than the old line, which may wrap to many lines at the largest text size or on a narrow screen] → The existing Playwright checks on narrow width and largest text size already cover the map and are run for this change; apply records any wrapping finding without changing styles.
- [Dropping the "do each one yourself" warning removes the only place the app tells participants that copying does not build the skill] → Recorded as out of scope; a later change can place it in `p1-mission`.
- [The intro is abstract for someone who has never been caught by a wrong AI answer] → Accepted. The two opening questions are the reader's own and the rows underneath are concrete.

## Open Questions

1. **Sidebar brand line.** Should `ui.brand_sub` ("Evaluated Systems (Stage 3)") change now that the page heading says "Evaluated systems"? Assumed default: no, leave it, since it is outside the authorized scope and the Stage 3 link may be wanted there.
2. **Where the "do each one yourself" message goes.** Assumed default: nowhere in this change; decide separately.
