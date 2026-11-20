# Proposal

## Why

The series is meant to be done by the participant, in order, and the app should not let them read or open their way around that. Today a locked lesson or step opens as a read-only preview at any time (archived `read-ahead-always`), and the Series map lets a participant open Part 3 with Parts 1 and 2 untouched (the Part 3 Start button starts it and marks it in progress). Both reviewers of 2026-11-16 asked for a full lock (series review items 1 and 4), a way to skip a whole Part with a clear warning (item 2), a map that opens on the Part the participant is in (item 3), and a way for the maintainer to open any Part for a demo (items 1, 1e). `add-part-2` is archived, so the strict rule no longer leaves Part 3 unreachable.

## What Changes

- **Full lock for participants (items 1, 4, 18).** A lesson or step opens, for reading or doing, only when it is done, skipped, or the next item to do in an open Part. A locked item can no longer be read: no read-only preview, and the server refuses it with a plain lock message. This **reverses `read-ahead-always` for participants**. A participant who skipped setup reads the current item and finished ones only ("Skip for now" stays).
- **Strict Part rule (item 4).** A Part opens only when every earlier Part is Done or Skipped. Parts 1 and 2 must be done or skipped before Part 3. This also ends the Part 3 Start bug. The rule lives in the server; the Series map and sidebar only show it.
- **Locked items look locked (item 1d).** In the Series map, the course list, the step list and links, a locked item is greyed and not clickable, with a **lock icon and the tooltip** "opens when the previous ones are done". The icon has an accessible name, and the same text shows on keyboard focus. The glossary and a lesson's "related lessons" show a locked lesson as plain text, not a link. The status word is "Not started" (as under `read-ahead-always`), shown with the lock icon, and the app never writes the word "locked" for a participant.
- **Skip a whole Part (item 2).** The open Part's row has "Skip this Part". A plain confirm says what the Part teaches, why it matters, and that you will have no artifact and no evaluator from it. A skipped Part counts as done for the rule above, and shows **Skipped** on the map and in the sidebar. A skipped Part's items open read-only and nothing in them can be done.
- **Series map default (item 3).** Only the active Part is expanded: the Part in progress, else the next to start. The rest are collapsed. When every Part with content is done or skipped, all are collapsed.
- **Demo access (items 1, 1e, O3).** A hidden way to open every Part: in Settings, click the app version five times, enter a password, and every Part opens, so a Part can be started without finishing the Parts before it. Inside a Part the order stays strict: items are still read and done one after another, with no reading ahead (you confirmed this on 2026-11-19). It is valid for the current run only (the app forgets it when it closes) and a visible notice shows while it is on. The password check is a **salted hash stored in the app**; the password itself is never in the repo, specs, tests or docs, and a small tool makes the hash. Demo access **does not open the sealed answer key**.
- **Docs and rules.** `docs/SPEC.md`, `AGENTS.md` (Status, and the password rule under Sensitive items) and the series review file are updated.

### Interface authorization (AGENTS.md rule 11)

**Requested, not yet granted**: apply starts only after you confirm this scope (it may touch `web/`, `content/lesson-ui.json`, `content/series.json`, `content/settings.json` and interface copy within it, and nothing else).

- Lock icon, "Not started" status, tooltip and focus text on locked items in the Series map, the course list and the step list; locked rows not clickable; locked glossary and related-lesson links shown as plain text.
- A locked Part row on the Series map (open control greyed, not clickable) and a **Skipped** state word and icon on Part rows, expanded lesson names and course lists.
- "Skip this Part" on the open Part's row, and its confirm dialog (text per Part).
- Series map default expansion (active Part open, others closed).
- A small app version line in Settings, the hidden five-click entry on it, the password prompt, a "Turn off demo access" button, and the "Demo access is on" notice shown on every screen while it is on.
- Removal of the two read-ahead preview notes (and their "Back to where I am" button) for participants. The read-only view stays only for the items of a skipped Part, with its own short note.

No other layout, styling, element id or component changes.

## Capabilities

### New Capabilities
- `course-locking`: when a lesson, step or Part opens for participants, what a locked item shows and refuses, and what is readable with setup skipped.
- `part-skip`: skipping a whole Part, its confirm, its stored state and how a skipped Part counts.
- `demo-access`: the hidden, run-only, password-protected way to open everything, its notice, and what it never opens.

### Modified Capabilities
- `setup-access`: "Learning content is always readable", "A preview says what holds it back" and "Locked items can be reached from every list and link" are replaced by the lock; the Part 3 and mission wording around reading before setup changes.
- `part-registry`: "Locking stays inside a Part" becomes locking across Parts; the "reading ahead" scenarios go; resets also clear skipped Parts.
- `series-map`: default expansion, locked Part rows, the Skipped state and the Part-open scenarios.
- `progress-reset`: "Reset lesson progress" also clears skipped Parts.
- `settings-page`: the version line and the hidden demo group.
- `part-1-exercise-steps`, `part-2-exercise-steps`, `part-2-course`, `step-restart`: the "readable as a read-only preview" wording and scenarios become "refused with the lock message".

## Out of Scope

- Technical mode (item 0), "Start this step again" for Part 3, and any change to what completes a step or a lesson.
- Migrating existing progress (decision O2): the app is not live. If it ships mid-course, a participant who is already ahead is held by the new rule until they finish what is before them.
- Locking the glossary, the reference card, the bundled kit files lessons cite, or Settings. They stay readable at any time.
- Parts 4, 5 and 6 (they stay "Coming soon" and "Live meeting") and any new Part content.
- Un-skipping a Part from the interface (decided 2026-11-19: no undo; "Reset lesson progress" is the way back).
- Running or approving any real AI tool. Everything is verified on the stand-in.
- Any change to the answer-key timing or sealed storage (AGENTS rule 9).

## Impact

- **Code:** `app/eval_coach/{engine,server,state,__main__}.py`; a new `app/eval_coach/demo_access.py`; `web/js/{series,lessons,views,app,settings,panels}.js` and `web/styles.css` for the lock, skip, notice and demo entry; `tools/make_demo_hash.py` (new); `tools/build_pyz.py` only if it does not already ship the hash file.
- **Content:** `content/series.json` (skip texts, locked and skipped words, intro unchanged), `content/settings.json` (demo and version words; the read-ahead gate texts go), `content/lesson-ui.json` (status word "Not started", tooltip), `content/steps.json` and `lessons.json` error messages for the lock.
- **Storage:** `progress.json` and `pending-lessons.json` lessons block gain `skipped_parts`; a new `app/eval_coach/demo_hash.json` holds only a salt and a hash; demo access itself is never stored.
- **Docs:** `docs/SPEC.md`, `AGENTS.md`, `docs/temp/series-review-pending-changes.md`, the local plan (`docs/local/`, not in git).
- **Tests and harness:** `tests/test_course.py`, `test_http_course.py`, `test_parts.py`, `test_part_1_steps.py`, the Part 2 and reset tests, `tests/frontend/*.spec.js` and its mock servers, `e2e-work/harness/run.js` and `lesson-stages.js` (they start Part 3 directly, so they unlock through demo access with a test hash), plus new tests for the hash and the content scan.
