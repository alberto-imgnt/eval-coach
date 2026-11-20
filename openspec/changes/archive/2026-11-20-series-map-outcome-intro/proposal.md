# Proposal

## Why

The text under the Series map title tells participants how to take the course ("Six Parts, one method. Do each one yourself…"). It does not say what the series is for or what they will be able to do afterwards, so a participant meets six rows without knowing why they should care. The title, "Series map", names the page's form, not its subject, and is generic. The series is about Evaluated Systems: AI work that has been checked, not just judged by how it looks. The opening of the home screen should say that in terms of what the participant gains, without listing steps and without a count of Parts.

## What Changes

- The Series map page title becomes **"Evaluated systems"** (was "Series map").
- The intro becomes an outcome-oriented, principle-led text, replacing the "do each one yourself" intro (series review item 19):
  > Is it good enough to use? How do you know? An evaluated system answers both: it is asked for clearly, judged against rules you can test, measured so that a better prompt is a fact and not an opinion, and kept to what earns its place. Below is where you learn to do each of these, ending with a task of your own.
- The intro covers the series' principles (trust from checking, good defined before it is judged, better measured and not argued, only what earns its place) and echoes the Parts 1 to 6 outcomes in order, without naming a Part, a count or a step.
- The intro no longer says there are six Parts and no longer carries the "copying someone else's prompt or rules" warning. **BREAKING** for the `series-map` requirement "The Series map intro is about doing the work yourself", which is replaced.
- The tests that assert the old intro and the old heading are updated.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `series-map`: the requirement "The Series map intro is about doing the work yourself" is replaced by an outcome-oriented intro requirement; a new requirement fixes the page title.

## Impact

- **Content:** `app/eval_coach/content/series.json` (`title`, `ui.intro`).
- **Docs:** `docs/SPEC.md` "Series map" (the sentence on `ui.intro`); the item 19 note in `docs/temp/series-review-pending-changes.md`; `docs/CONTENT-RULES.md` if it describes the intro.
- **Tests:** `tests/test_series.py` and `tests/test_participant_vocabulary.py` (intro assertions); the Playwright specs in `tests/frontend/` that wait for the heading text "Series map" (`ui.spec.js`, `locking.spec.js`, `part1.spec.js`, `part2.spec.js`).
- **Not touched:** Python code, `web/` code, element ids, styling, layout.

### Interface authorization (AGENTS.md rule 11)

The user asked for this wording change on 2026-11-20 and chose the title "Evaluated systems" and the intro text above. The authorization covers **only** the text of the Series map page title and intro line in `content/series.json`. It does not cover layout, styling, components, element ids, the sidebar brand line, or any other interface copy.

## Out of Scope

- "Back to series map" (`lesson-ui.json` `ui.back_to_series`), the top-bar Back control, and every other reference to "series map" in the interface, specs, docs and tests. They keep their names; the user asked for them to stay.
- The sidebar brand line on the map (`ui.brand_sub`, "Evaluated Systems (Stage 3)"). It will now sit beside a page title of the same words. Whether to change it is left to the user (see the design's Open Questions).
- The Part rows: names, outcomes, labels, states, Skip text, the Part 6 live-meeting row.
- Any new visible element, such as a heading above the list, a subtitle or a callout. The layout is unchanged; the intro stays one paragraph.
- Re-adding the "do each one yourself" message elsewhere (for example in `p1-mission`). Not decided here.
- The other Parts' lesson content, `docs/local/` working papers, and a real-CLI run.
