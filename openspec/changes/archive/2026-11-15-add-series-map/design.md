# Design

## Context

See proposal.md for motivation. Current state that shapes the approach, observed in the code:

- `render()` in `web/js/app.js` picks one of three views from `currentView(state)`: `wizard`, `settings` or `lesson`/`course`. `app.screen` is `'settings'`, `'setup'` or `null`; `null` means Part 3 content. `app.setupFrom` remembers where the wizard was opened from (`'settings'` or `null`). Several actions end by setting `app.screen = null` to "show the course": `pfSkip`, the setup submit, `closeSettings`, `closeSetup`, `navigate`, `openCourseItem`, and the configuration reset.
- The sidebar is `renderTopbar` in `web/js/views.js`: brand, `#nav-toggle`, a progress ring, the course list (`renderCourseNav` in `web/js/lessons.js`) and `renderTopbarTools`. The tools renderer does not depend on the course, so it can be reused as is. The wizard empties `#topbar`.
- `engine.get_state` returns `course` (lessons and steps with status `done`, `skipped`, `active` or `locked`), `current_item` and `course_text` (all of `content/lesson-ui.json` `ui`). Progress counts in the sidebar are computed in the browser from `state.course`.
- Settings and the map-less views start no terminal and leave a running CLI alone (`viewedTerminalOwner` returns `null` for settings, so `isForeignTerminal` is false).
- The `mission` lesson holds a static "you are here" block (fence `you-are-here`, parsed in `web/js/markdown.js`) with stops tagged `done`, `here`, `next`. The `series-intent-framing` spec pins it (Parts 1 and 2 `done`, Part 3 `here`, Parts 4 to 6 `next`), and this change leaves it alone.
- Governing files updated since the first draft of this change: the archived change `align-series-content-with-intent` added the specs `series-intent-framing`, `course-structure`, `interface-alignment`, `part-terminology`, `method-over-mechanics` and `learning-priority-order`; AGENTS.md rule 10 now has a Part 6 exception (the live note, stated once in `baseline-why`); `docs/COURSE-CONTEXT.md` describes Part 6 as informational only; the design system is "Graphite and Lime".
- An `Engine` built without lessons (the step tests) has no course; `hasLessons(state)` is false and the old step list is shown.

## Goals / Non-Goals

**Goals:**
- A Series map screen that is the home of the app, with one row per Part, built so a new Part is added with content and a flag, not new code.
- Reuse the existing sidebar, tools, collapse state, banners and Settings/wizard return logic.
- No new HTTP route, no new stored state.

**Non-Goals:**
- Per-Part courses or per-Part progress. `state.course` stays the Part 3 list, and the map derives Part 3's row from it. Generalizing to many courses is a later change that this design must not block.
- Deep links, history entries or restoring the last screen.

## Decisions

### D1. Screen state: `app.screen = 'series'` is the default
`app.screen` gains the value `'series'`, and its initial value is `'series'` (it is `null` today). `null` keeps meaning "Part 3 content". `currentView` returns `'series'` for it after the wizard test, so first run still opens on the wizard (the wizard test comes first, as today).
- Every action that means "go into the Part" sets `app.screen = null` (`navigate`, `openCourseItem`, and the new `openPart`). `openPart('part-3')` sets `app.screen = null` and clears `viewLesson` and `viewStep`, so the Part opens at `current_item`.
- Every action that today ends with `app.screen = null` meaning "land on the course" now sets `'series'`: `pfSkip`, the setup submit ("Set up my project") and the configuration reset (which then hits the wizard first because setup is not passed).
- New `backToSeries` action sets `app.screen = 'series'` after `saver.flush()`.
- A page reload recreates `app` with `screen: 'series'`, which gives "every launch and reload opens on the map" with no storage.

Alternative considered: a separate `app.home` flag next to `app.screen`. Rejected: it creates two sources of truth for "which screen", and the existing `setupFrom` logic already works on one value.

### D2. Returning from Settings and the wizard
`closeSettings` currently sets `screen = null`. It now returns to `app.settingsFrom`, set by `openSettings` to the screen that was open (`'series'` or `null`). `setupFrom` widens from `'settings'`/`null` to `'settings'`/`'series'`/`null`; `closeSetup` restores it. When setup is opened from Settings and Settings was opened from the map, closing the wizard returns to Settings and closing Settings returns to the map (chain preserved with two fields).

### D3. Where the map's data comes from: `content/series.json` and `state.series`
`content/series.json` holds `{"title", "parts": [{"n", "id", "title", "kind", "outcome"}], "ui": {...words...}}`. `kind` is `course` (Part 3, has content), `soon` (Parts 1, 2, 4, 5) or `live` (Part 6). For `live`, `outcome` holds the brief Part 6 explanation. The engine loads it once next to `lesson-ui.json` and `get_state` adds:

```
"series": {
  "title": "...", "ui": {...},
  "parts": [
    {"n":1, "title":"...", "kind":"soon", "outcome":"..."},
    ...
    {"n":3, "title":"...", "kind":"course", "outcome":"...",
     "state":"not_started|in_progress|done",
     "done": <int>, "total": <int>,
     "lessons": [{"id","title","status"}]},   // from state.course, kind == "lesson"
    ...
    {"n":6, "title":"...", "kind":"live", "outcome":"..."}
  ]
}
```
`done` and `total` count lessons and steps in `state.course` with the same rule the sidebar uses (`done` or `skipped`), so the row and the sidebar always agree. A state with no lessons (engine without a course) returns `series: null` and the UI keeps the old step list.

Alternative considered: put the Part list in `lesson-ui.json`. Rejected: that file is Part 3 interface text; the series list belongs to the whole series and will grow with each Part. Alternative: compute everything in the browser from `course_text`. Rejected: the server already owns status, and a test can pin the shape.

### D4. The view: `web/js/series.js`
A new module exports `renderSeries(ctx)` (the `#col-left` content) and `renderSeriesNav(ctx)` (the sidebar middle). `main` gets the `no-terminal` class, as for Settings.
- Row structure: an `li` per Part inside an `ol`. For an available Part: an expand `button` (`aria-expanded`, `aria-controls`) holding the chevron, and a separate open `button` holding the number, name, state text and the "Start" or "Continue" action. Not nested buttons: they are siblings in the row. Expanded content is an `ol` of lesson names with status words from `ui.status_*`.
- A coming-soon or live row is a plain `li` with text and its label ("Coming soon" or "Live meeting") and the outcome or explanation line; no button, no tabindex, no handler. The two kinds differ only by label and class.
- Expansion is in memory: `app.seriesOpen` (a Set of Part ids), initialized with Part 3, never saved.
- Pure rendering helpers use the existing `h`/`morph` pipeline; no new dependency.

### D5. Sidebar composition
`renderTopbar` branches on `ctx.view`:
- `series`: brand (sub-brand text from `series.ui`, not "Part 3 · …"), `#nav-toggle`, no ring, no course list, then `renderTopbarTools`.
- inside the Part: unchanged, plus a `Back to series map` button (`#back-to-series`) as the first block after the brand, in the same markup the narrow layout already turns into the top bar. The label comes from `lesson-ui.json` `ui.back_to_series`.
`syncCourseNav` and the narrow drop-down code in `chrome.js` handle a missing `details.course-nav` already (it queries for it); this is verified in the tasks. The wizard continues to empty `#topbar`.
The collapse state (`eval-coach-nav`) is shared because it is read by the same `navCollapsed()` call on both branches.

### D6. Terminal and running CLI
`viewedTerminalOwner` returns `null` for `series`, like `settings`. A running CLI keeps running while the map is shown and the terminal pane is hidden; returning to the Part shows it again. This matches the requirement that the map and Back do not start or stop a CLI.

### D7. Mission map and Part 6 wording
The mission map block, its `markdown.js` renderer and `series-intent-framing`'s map requirement are untouched (user decision). The two maps answer different questions: the mission map is the series as the participant has lived it, the Series map is what the app holds. A content test checks they use the same Part names and, for Parts 1 to 5, the same one-line outcomes, so the wording cannot drift.

Part 6 is a live meeting (SERIES-INTENT.md, COURSE-CONTEXT.md). The user asked for a brief, clear explanation of it on the map, an exception to AGENTS.md rule 10's "stated once, in `baseline-why`". The exception is widened by exactly one place: the Part 6 row says it is a live meeting and what it is about. It does not say office hours or the AIR discussion (those stay in `baseline-why` only) and gives no person, place, link or schedule. A content test pins both halves. AGENTS.md rule 10, the `docs/SPEC.md` rule line, `openspec/config.yaml` context and the `series-intent-framing` requirement are amended to match (task 4.2).

### D8. Reset behavior
Reset of lesson progress: no map state to clear; the map re-renders from fresh state and Part 3 shows "Not started". Reset of app configuration: goes to the wizard first (setup not passed), then the map after skip or completion, as in D1.

## Files and storage touched

| Location | Change | Kept or cleared |
|---|---|---|
| `app/eval_coach/content/series.json` | new | n/a |
| `app/eval_coach/content/lesson-ui.json` | add `back_to_series` | n/a |
| `app/eval_coach/engine.py` | load `series.json`; `series` in `get_state` | n/a |
| `app/eval_coach/web/js/app.js`, `views.js`, new `series.js` | screen state, actions, rendering | n/a |
| `app/eval_coach/web/styles.css` | map rows, chevron, labels, Back control (existing tokens) | n/a |
| `content/lessons.json`, `web/js/markdown.js` | untouched | kept |
| `progress.json`, `pending-lessons.json`, `preflight.json`, `<home>\reset-backup\` | untouched | kept (neither reset changes) |
| `localStorage` `eval-coach-nav`, `eval-coach-theme`, `eval-coach-text-size` | read as before; shared between map and Part | cleared by configuration reset as before |
| Row expansion (`app.seriesOpen`) | memory only | gone on reload |
| `tests/frontend/mock_api.py`, `mock_course.py`, `ui.spec.js`, `e2e-work/harness/*.js` | return `series`; enter Part 3 through the map | n/a |
| `AGENTS.md`, `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md`, `docs/COURSE-CONTEXT.md`, `openspec/config.yaml` | updated (rule 10 wording, state shape, status, coverage) | n/a |
| `dist/eval-coach.pyz` | rebuilt | generated |

## Risks / Trade-offs

- [Many tests assume the page opens on the course] -> The Playwright openers (`openApp`, `openCourse`, `openWithStorage`) and the harness gain one helper that enters Part 3 from the map; suites are rerun in full and the helper is the only change to most tests.
- [An extra click every launch while only one Part exists] -> The row offers a labelled "Continue" and is the first thing on screen; accepted by the user.
- [Action code that sets `app.screen = null` and was missed would land inside the Part] -> Tasks list every assignment found today (`app.js` lines near `pfSkip`, setup submit, `closeSettings`, `closeSetup`, reset) and a test per landing.
- [A reload loses the participant's place] -> `Continue` resumes at the current item; accepted by the user.
- [Part rows can drift from the mission map] -> Content test compares names and the Part 1 to 5 outcomes (D7).
- [The Series map says Parts 1 and 2 are "Coming soon" while the mission map says they are done] -> They answer different questions (what the app holds vs the series the participant has lived); accepted by the user. Wording on the map says "coming soon" about app content, not about the participant's progress.
- [The Part 6 live note appears in a second place, against AGENTS.md rule 10] -> Authorized by the user; the rule, SPEC line, config context and spec are amended in the same change, and a test limits the map to "live meeting" wording with no pointers to people.
- [`interface-alignment` "The interface change is limited" says the earlier change may not alter Settings screens, element ids or step panels] -> Read as the scope of that change, which it names (items U1 to U6 and U8 authorized 2026-11-14). This change adds a new view, one sidebar control and return logic, and changes no design token, existing element id, terminal screen or step panel. It has its own authorization in the proposal.
- [`part-terminology` requires Part strings to come from content and scans `web/js`] -> `series.js` holds no Part title or number word; everything comes from `series.json` and `lesson-ui.json`. The scan is extended to include it.
- [The Part 3 row's count differs from the sidebar] -> Both use the same rule; a test compares them.
- [Coming-soon label read as a promise for Parts 4 and 5] -> Accepted by the user; the `COURSE-CONTEXT.md` coverage column is updated so it no longer says "Not planned".
- The lessons still speak as if Parts 1 and 2 were done by the participant; that wording is outside this change.

## Migration Plan

No data migration: no stored state changes. Ship by rebuilding `dist/eval-coach.pyz`. Rollback is removing `series.json`, the `series` state key and `series.js`, and restoring `app.screen = null` as the default; stored progress is unaffected either way.

## Open Questions

Confirm each; the assumed default is used if no answer is given.

1. **Count on the Part 3 row**: lessons and steps done out of total (same as the sidebar ring), while the expanded list names lessons only. Default: yes. Alternative: lessons only on the row, which would not match the ring.
2. **Part 6 label and text**: the label is "Live meeting" (not "Coming soon"), and the explanation reads along the lines of "A live working meeting. You pick a task of your own that repeats, has clear requirements and can be checked by rules, and talk your ideas through." Final wording is set in `series.json` and checked by the content tests. Default: yes.
3. **Part 6 and office hours**: the map never mentions office hours or the AIR discussion; those stay in `baseline-why`. Default: yes.
4. **CLI while on the map**: a running CLI keeps running, pane hidden, as with Settings. Default: yes.
5. **Map sub-brand text**: the sidebar's sub-brand on the map reads "Evaluated Systems (Stage 3)" (from `series.json`). Default: yes.
6. **Finished Part 3**: the row says "Done" and its action reads "Review" and opens the closing screen. Default: yes.
7. **Back control label**: "Back to series map". Default: yes.
8. **`interface-alignment` limit requirement**: left as written and read as the scope of the earlier change (see Risks), with no delta spec. Default: yes. Alternative: a delta spec rewording it.
