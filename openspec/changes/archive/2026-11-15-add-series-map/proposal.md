# Proposal

## Why

The app is built for the whole six-Part series, but the interface only knows Part 3: the sidebar is one flat list of Part 3 lessons and steps, and the other Parts appear only as a static sketch inside the `mission` lesson. A participant has no place that shows the whole series, where they are in it, or what the other Parts are. Adding those Parts later needs a home for them first.

## What Changes

- **New home screen, the Series map.** After setup is completed or skipped, the app opens on a map of all six Parts. It opens on the map on every fresh launch and every page reload (no memory of the last screen).
- **One row per Part**, in series order, with the Part number and name:
  - Part 3 (the only Part with app content) shows its progress and a chevron that expands the row to list its lesson names with each lesson's status. Selecting the row opens the Part's content, resuming at the current item. Expanding and opening are two separate controls.
  - Parts 1, 2, 4 and 5 show the number, name, a one-line outcome and a "Coming soon" label. They have no chevron and do nothing when selected.
  - Part 6 shows the number, name and a "Live meeting" label with a brief, clear explanation of what the Part is about and that it takes place live. It has no chevron and does nothing when selected (user decision, recorded below).
- **Back to series map.** Inside a Part, the sidebar keeps its progress ring, groups, lesson and step names, and gains a "Back to series map" control at the top (also in the narrow-screen bar).
- **Sidebar tools stay everywhere.** Glossary, Reference, theme toggle, Settings and Quit are available on the map and inside a Part, with the same ids, order and collapsed-to-icons behavior. The sidebar collapse control and its saved state apply on both screens.
- **Existing exits land on the map.** The setup wizard's last page ("Set up my project"), "Skip for now" and the end of first-run after a configuration reset go to the map instead of the current course item. Closing Settings or the setup wizard returns to the screen it was opened from, which may be the map.
- **Series content in one place.** A new `content/series.json` holds the six Parts (number, name, kind, one-line outcome or Part 6 explanation) and the map's words. The server adds `state.series` (each Part with its kind and, for Part 3, its status, progress and lesson list, built from the existing course list). No new endpoint.
- **Mission map left alone.** The "you are here" block in the `mission` lesson and the `series-intent-framing` requirement about it are not changed. The Series map describes what is in the app; the mission map describes the series as the participant has lived it. A test checks that both use the same Part names.
- **Part 6 wording rule widened by one place.** AGENTS.md rule 10, the matching line in `docs/SPEC.md`, the `openspec/config.yaml` context and the `series-intent-framing` requirement "The baseline lesson says Part 6 is live and where to bring ideas" say the live note is stated once, in `baseline-why`, and nowhere else. They are amended so the Series map's Part 6 row may also say, as information only, that Part 6 is a live meeting and what it is about. Office hours and the AIR discussion stay in `baseline-why` only, and the map names no people, contact details, links or schedules.
- **Docs and tests.** `docs/SPEC.md` (setup wizard, Settings, state shape, new Series map section), `docs/IMPLEMENTATION-PLAN.md`, `docs/COURSE-CONTEXT.md` (coverage column) and AGENTS.md (Status, rule 10) are updated. Playwright tests, their mock API and the stand-in harness that assume the page opens on the course go through the map.

Authorizations (both given by the user in the conversation that led to this proposal, 2026-11-15):
- **Interface change** (AGENTS.md rule 11): a Series map home screen, a Back to series map control, Part rows with an expandable lesson list, and "Coming soon" and "Live meeting" labels. Scope: the new view and its styles in `web/`, the sidebar's top section, and interface text in `content/series.json` and `content/lesson-ui.json`, using the existing design tokens ("Graphite and Lime"). Not authorized: any other layout, styling or copy change.
- **Part 6 wording** (AGENTS.md rule 10 exception): "Include part 6 with a brief clear explanation of what it is about and how will/can be done (live setting)". Scope: one short passage in the Part 6 row of the Series map. Not authorized: pointers to people or places anywhere else.

## Capabilities

### New Capabilities
- `series-map`: the home screen listing all six Parts, the expand and open behavior of a Part row, "Coming soon" and "Live meeting" rows, Part progress, the Back to series map control, and which screen the app opens on.

### Modified Capabilities
- `setup-access`: the setup wizard and "Skip for now" finish on the Series map; closing the wizard returns to the screen it was opened from, which may be the map.
- `settings-page`: Settings is reachable from the map, and leaving it returns to the map when that is where it was opened.
- `series-intent-framing`: the requirement that the live note on Part 6 appears only in `baseline-why` is widened so the Series map's Part 6 row may also say Part 6 is a live meeting.

## Impact

- `app/eval_coach/engine.py`: `get_state` adds `series`. A new reader loads `content/series.json`.
- `app/eval_coach/content/series.json` (new); `content/lesson-ui.json` (Back control label).
- `app/eval_coach/web/js/app.js` (screen state, render, actions), `js/views.js` (sidebar top section, tools on the map), a new `js/series.js` for the map view, `styles.css`.
- Tests: new `tests/test_series.py`; `tests/frontend/ui.spec.js` openers, `tests/frontend/mock_api.py`, `tests/frontend/mock_course.py` and the stand-in harness in `e2e-work/harness/` go through the map; `tests/test_part_terminology.py` and `tests/test_content_banned_words.py` cover the new content.
- Docs and governing files: AGENTS.md, `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md`, `docs/COURSE-CONTEXT.md`, `openspec/config.yaml` (context line for rule 10).
- `dist/eval-coach.pyz` must be rebuilt.
- No change to `progress.json`, the reset inventory or any HTTP route. Row expansion lives in memory only.

## Out of scope

- Content, lessons or steps for Parts 1, 2, 4 or 5, and per-Part courses or per-Part progress storage. The map is built so a Part can be switched on by adding content and changing its kind in `series.json`.
- Any Part 6 content, exercise, scheduling, link or contact detail, and any mention of office hours or the AIR discussion on the map.
- Opening a coming-soon or live Part, previews of it, or notifying participants when it ships.
- Changing the mission lesson, its map or its tests.
- Remembering the last screen, URLs or deep links, or browser Back/Forward behavior.
- Changing the Part 3 sidebar (groups, ring, items) other than adding the Back control, and renaming the header text "Part 3 · Running evals and baseline" inside the Part.
- Any change to CLI handling, setup checks, lessons, steps, grading or the answer key.
