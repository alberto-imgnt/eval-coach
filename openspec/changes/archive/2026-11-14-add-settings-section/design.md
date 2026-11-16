## Context

The app is a stdlib-only Python server with a no-build static UI. Facts that shape this change:

- **Sidebar tools.** `renderTopbarTools` in `web/js/views.js` renders the tool list (glossary, reference, theme toggle, Quit) through one `tool()` helper. On narrow screens the same pieces become a top bar.
- **Display choices.** `eval-coach-theme` and `eval-coach-nav` live in `localStorage`; `web/js/theme.js` applies them before first paint and `web/js/chrome.js` changes them.
- **Sizing.** The layout is mostly `rem` (about 550 values), but `body` sets `font-size: 16px`, the terminal uses `fontSize: 14`, and layout breakpoints are fixed pixels: 1100px, 820px (`@media` in `styles.css`) and `WIDE_QUERY` (821px) in `chrome.js`. `#screen-main` also uses `minmax(400px, 46%)`. `index.html` has no viewport meta tag, so phones render it at desktop width.
- **Setup today.** There is one setup screen, `renderPreflight` with terminal head and foot. It is not in `state.course`; `courseEntries` in `web/js/lessons.js` inserts a "Before you begin" entry after the mission lesson, and `app.viewPreflight` lets the finished screen be reopened from that entry. The main view shows setup when `!state.preflight.passed || app.viewPreflight`. Gates refuse steps with `preflight_incomplete` until setup passes.
- **State.** Progress is `<project>\.learning\progress.json` plus `results\`, `hook\`, `practice\`; `<home>\pending-lessons.json` before a project exists; the sealed key under `<home>\sealed\<id>\`; setup results in `<home>\preflight.json`; the last project in `<home>\app.json`. The engine caches setup and progress in memory.
- **Project folder** (from `project.Paths` and a finished stand-in run): `prompt-v0.md` and `test-cases.md` (starting files, copied from Northwind or from the participant's own files), `skills\` (bundled, byte-identical), and the course outputs `check.py`, `promptfooconfig*.yaml`, `agent-provider.js`, `results.json`, `iteration-log.md`, `runs\`, `fixtures\`, `examples\`, `.learning\`.
- **Rule 11** (no interface changes without authorization) is lifted by the user for Settings, the removal of the setup course-list entry, and the layout work for text size.

## Goals / Non-Goals

**Goals:**
- A Settings entry before Quit that opens one panel with every option: text size, setup, two resets.
- Setup as a one-time global full-page wizard, not a course item; its full function reachable from Settings.
- A text size slider with device-aware values and a layout that adapts at every size.
- Two resets that leave nothing from the app behind, move rather than delete, and are all-or-nothing.

**Non-Goals:**
- Changing setup checks or rules; per-Part reset; restoring from the backup in the app; theme or sidebar controls in Settings; deleting downloaded runtimes; Mac.

## Decisions

### 1. Settings is one panel, not a course item
Add a `settings` view opened from a new `tool()` placed immediately before the Quit tool, so it follows the collapsed and top-bar layouts for free. The panel stacks the three groups in order (text size, setup, reset) with no tabs. It uses the single-column layout with no terminal (setup runs in its own full-page wizard, decision 9); on narrow screens it is the same column. Settings is never "current", never gates anything and has no entry in `progress.json`. Alternative rejected: a separate `settings.html` (loses in-app state, needs a reload).

### 2. Setup becomes one global screen
- **Setup is a first-run gate that can be skipped.** Setup is a global, one-time process and a prerequisite for hands-on work. Today the mission lesson is open before setup and the setup screen is inserted after it; that changes. On first run (and after a configuration reset) the main view shows the setup screen first, with a "Skip for now" action. Skipping stores `setup_skipped` in `<home>\preflight.json` (cleared by a configuration reset, so it is forgotten with the rest of setup) and the app then opens on the course on later runs. Setup also creates the project, so the app no longer needs course progress to exist before a project does. `pending-lessons.json` stays readable and clearable for older installs but is no longer written for new ones.
- **Hands-on versus reading.** Hands-on means every step and the lesson activities that start the participant's CLI (types `cli_compare`, `cli_practice`, `cli_demo`). Those are refused with the existing `preflight_incomplete` error until setup passes (`_require_preflight` already guards steps; the lesson CLI start path gets the same guard), and their buttons are disabled with an explanation and a link to setup. Question-type activities (`choice`, `order`, `sort`, `reflection`) and the in-app `rule_lab` keep working for lessons open by normal order.
- **Reading ahead.** While setup has not passed, `lesson_view` and the step views serve read-only previews for items normal order would keep locked: text and cited kit files are returned, activity endpoints refuse (`lesson_locked`), and the UI renders exercises disabled. Nothing is written to progress for previews. This is the only place the engine's open/locked rules differ before and after setup.
- Remove the `preflight` entry from `courseEntries`, the `openCourseItem('preflight')` path and `app.viewPreflight`. The course list and progress ring then count only lessons and steps (they already do; the entry was display-only). Before setup passes, the course list shows every item locked.
- Setup is shown first on first run and after a configuration reset, because the stored results are cleared and the same first-run path applies. Once passed it never shows by itself again.
- The Settings panel's setup group is a short summary of the checks and their status plus an "Open setup" button that opens the same wizard (decision 9). Setup works whether or not it has passed. All preflight endpoints and rules stay as they are (track lock, OneDrive refusal, consent for installs).
- Audit `content/*.json` and views for wording that points to "the Before you begin screen/page" (for example `preflight_first`, the glossary entry for CLI) and point it to "setup" or Settings. I found no other per-lesson or per-step setup screens in the code; the audit task confirms this.

### 3. Text size is a root scale driven by one number
Store `eval-coach-text-size` as a number (percent). `theme.js` sets `html { font-size: <n>% }` and `--text-scale` before first paint. Change `body` from `16px` to `1rem`, convert fixed-px sizes and widths that must scale (such as `minmax(400px, 46%)`) to `rem`, and scale the terminal font by `round(14 * scale)` followed by its debounced fit. The slider is a native `<input type="range" step=5>` so keyboard and touch work out of the box; a 100% button resets it. Alternatives rejected: browser zoom (not controllable from the page) and CSS `zoom` (non-standard, breaks terminal measurement).

### 4. Phone detection decides the range
A phone is `matchMedia('(pointer: coarse)')` plus `min(screen.width, screen.height) <= 600`. It is based on the device, not the window, so a narrow desktop window is not a phone and a phone in landscape still is. Range is 80 to 150 on desktop and 90 to 130 on phones, default 100 in both. The stored value is clamped to the active range when read. The same flag turns on 44px touch targets in Settings. Alternative rejected: user-agent sniffing (brittle).

### 5. Layout breakpoints follow the scale
Media queries use CSS pixels and do not follow the root font size, so at 150% the desktop layout would not switch to a compact form in time. Replace the three width tests (1100px, 820px, `WIDE_QUERY`) with a `data-layout` attribute (`wide`, `mid`, `narrow`) computed as `innerWidth / scale` against the same thresholds, set in `theme.js` before first paint and updated on resize and on slider change. CSS `@media` blocks become `:root[data-layout="mid"] ...` selectors. At 100% the result is identical to today. Add `<meta name="viewport" content="width=device-width, initial-scale=1">`. Alternative rejected: duplicating `@media` blocks per scale bucket (many copies, still stepwise).

### 6. Resets move, then clear, all or nothing
Two operations share one routine: `POST /api/reset/progress` and `POST /api/reset/configuration`, each refused without `{"confirm": true}`. Under the engine lock:
1. Stop any running CLI (`_stop_cli`).
2. **Plan**: build the list of items to move from an explicit inventory (below), so unknown files are never touched.
3. **Back up**: move the planned items into `<home>\reset-backup.new\<timestamp>`; if any move fails, move back what was moved and return a plain-language error with nothing changed.
4. Delete the sealed answer key directory (never backed up), reset the in-memory state, recreate the empty scaffold the app needs, and write a fresh default `progress.json` when a project is kept.
5. Replace `<home>\reset-backup` with the new backup, then delete the old one.

Moves are renames on the same volume where possible, falling back to copy-then-verify-then-delete across volumes. With no project (nothing to back up) only state is cleared.

**Inventory.** Recorded from the finished stand-in runs on both tracks (`e2e-work\standin-project`, `standin-project-pf` and their homes) and kept in `reset.py` and in `docs/SPEC.md` ("Reset inventory"). Progress reset moves `.learning\`, `check.py`, `promptfooconfig.yaml`, `promptfooconfig.live.yaml`, `agent-provider.js`, `results.json`, `iteration-log.md`, the contents of `runs\`, `fixtures\`, `examples\`, the home scratch folders (`blind`, `fixtures-work`, `key-work`, `hook`, `demo`, `practice`), `pending-lessons.json` and the sealed answer key folder (its key is then deleted from the backup); it keeps `prompt-v0.md`, `test-cases.md` and the bundled `skills\` files. Configuration reset moves all of that plus `prompt-v0.md`, `test-cases.md`, the bundled `skills\` files (not other files a participant put in `skills\`), `<home>\preflight.json`, `<home>\app.json`, `cli-test`, `cli-signin` and `cli-install`. Display choices are cleared in the browser after success (the server cannot do this). Never touched: other project files, `<home>\runtime`, `npm-cache`, `promptfoo`, `promptfoo-work`, CLI recipes. The backup holds `project\` and `app\` subfolders and has no timestamp folder, because only one backup exists. A reset that moves nothing keeps the earlier backup; a reset always moves `.learning\`, so after a reset the backup is replaced even when little was produced.

### 7. The reminder banner is a slim strip in the content area
Render it from state (`!preflight.passed` and not on the setup screen) in a new region directly above the scrolling content column, outside the scroller so it stays in view, in the same family as the existing `#notices` and `review-banner` regions. Calm attention styling from the design tokens (not the error color), one or two lines, a "Go to setup" button, no close control, no focus movement, `role="status"` rather than an alert so screen readers are not interrupted. It uses `rem` so it scales with the text size, wraps at large sizes, and on phones collapses to a compact two-row form with a 44px button. It also shows inside the Settings panel.

### 8. Dialogs use the existing confirm dialog
`web/js/dialog.js` already has the pattern (as in "Start again?" and "Quit"). Default focus is the keep action. The configuration dialog uses the destructive style and a different title, and names progress as also cleared. Both name the backup folder and say it replaces the previous one.

### 9. Setup is a full-page wizard
Added by amendment: showing setup beside the course sidebar and the terminal confused participants (the sidebar lists a course they cannot yet use). `currentView` returns a new `wizard` view whose layout hides `#topbar` (sidebar and tools), `#setup-banner`, `#review-banner` and the two-column main area, and renders one full-width card.
- **Pages.** One page per applicable item in `pf.items` (`applies`), in server order: Track, Python, AI CLI, Sign in and license, CLI working test, Project folder; the promptfoo track adds Node and promptfoo after Python. Each page renders the existing per-item controls (`trackControls`, `installControls`, `cliControls`, `signinControls`, `workingTestControls`, `projectControls`), so every id, endpoint and rule is unchanged. `renderPreflight` is split into per-page renderers plus the wizard frame; the old single-list rendering and its embedded use in Settings are removed.
- **Frame.** A header with the app name only (no tools, no Quit), a progress indicator ("3 of 6" and page names; no "step" or "Part" words), the page title, status and detail, the controls, and a footer with Back, Next, "Check everything" and the leave action. Next is disabled until the page's item is `passed`, with a plain line saying what is needed; the last page's submit is the project form's own button.
- **Position.** The page index lives in memory only (`app.wizardItem`), not in storage. On open it is the first applicable item not `passed`; because the Track check passes by default, a fresh setup (no later check passed) opens on the Track page, which carries the welcome text, the skip hint and the track choice. When everything has passed it opens on the first page. Back and Next move it; a passed earlier page can be revisited.
- **Leaving.** First run (not passed, not skipped) shows "Skip for now" on every page (the existing `pfSkip`). When opened from Settings or the banner (`openSetup`), it shows a close action instead and returns to the screen recorded when it was opened (`app.screen` or the viewed lesson or step). Neither changes check results or stops a CLI.
- **Terminal.** `#col-right` becomes part of the wizard card for pages whose item is `cli`, `signin` or `working_test`: beside the page on a wide window, below it on a narrow one. Other pages hide it. The terminal host element is hidden, not recreated, so the CLI process and its output survive moving between pages.
- **Entry points.** First run opens the wizard; the banner button and the Settings "Open setup" button call `openSetup`. Settings shows the summary (items and statuses, from `state.preflight.items`) and the button; it no longer embeds the setup list. Words come from `content/preflight.json` (wizard progress, Back, Next, close, finish) and `content/settings` words for the summary.
- **Phones.** One column, 44px Back, Next and skip buttons, terminal below the controls.
- **Files and keys.** No new storage: no new `localStorage` key, no change to `preflight.json`, `progress.json` or any server file. `setup_skipped` is unchanged.
- **Alternatives rejected.** A modal over the app (still shows the sidebar behind it); a route/page outside the app (loses terminal and state).

## Risks / Trade-offs

- **Wizard rewrite touches the setup screen's every control.** Tests and the stand-in harness drive setup by element id. → Keep every existing id (`pf-check-all`, `pf-cli-command`, `pf-cli-check`, `pf-test-check`, `setup-project`, `pf-project-submit`, ...) and only change where they sit; the harness and Playwright setup tests are updated for the page-by-page flow.
- **The terminal moves between pages.** Re-parenting xterm could drop output or restart the CLI. → The terminal host is kept in one element that is shown or hidden, not recreated, and a test moves between pages with the stand-in CLI running.
- **Next gating can strand someone.** A check that cannot pass (for example no network for an install) would block Next. → "Skip for now" (first run) or Close is always available, and each page states what is needed.

- **Inventory drift.** If a later step writes a new file that is not in the inventory, reset would leave it behind. → A test drives the stand-in through both tracks and fails if any file in the project folder or home is unaccounted for by the inventory or by the kept list; the inventory is also listed in `docs/SPEC.md`.
- **Unknown files in a chosen folder.** "No leftovers" cannot cover files the app did not create. → They are left alone by design and the spec says so.
- **Backup uses disk space and holds participant work.** One slot only, replaced at the next reset; it holds no answer key. → The dialog says where it is.
- **Moves across volumes.** Copy-verify-delete can be interrupted. → The old files are deleted only after the copy is verified, and a failure leaves the original in place.
- **In-memory state out of step with disk.** → Both resets rebuild the cached state, and a test asserts `/api/state` after each reset equals a fresh start.
- **Removing the setup course-list entry** touches navigation and a few messages. → Interface tests cover first run, skip, after setup, and after a configuration reset.
- **Previews bypass sequential locking.** A bug there could record progress out of order. → Previews never call a write path; tests assert `progress.json` is byte-identical after reading ahead.
- **A banner on every screen can crowd small screens.** → Height cap tested on a 390px phone and at the largest text size.
- **Breakpoint rewrite touches the whole stylesheet.** → Screenshot comparison at 100% before and after, at 1280, 1100, 820 and 390px wide, must show no change.
- **Terminal refit while a CLI runs.** → The existing resize path is reused and verified with a running stand-in CLI.

## Migration Plan

No data migration. Existing `progress.json` files stay valid. `docs/SPEC.md` (Storage, HTTP contract, course model, a Settings section) and `docs/DESIGN.md` are updated in the same tasks as the code. Rollback removes the Settings tool and endpoints and restores the course-list entry; a stored `eval-coach-text-size` is then ignored.

## Implementation Notes

Recorded while applying the tasks.

- **`rule_lab` needs no CLI** (task 2.2). `lesson_rule_run` runs the fixed rules inside the app on the participant's text and uses neither the terminal nor the private runtime, so it counts as reading, not hands-on. Question activities (`choice`, `order`, `sort`, `reflection`) and `rule_lab` work in any lesson that is open by normal order; a locked lesson only opens as a preview.
- **Audit result** (task 2.5). The only per-lesson or per-step setup screens in the code were the `preflight` course-list entry and `app.viewPreflight`, both removed. Wording that pointed to "the Before you begin screen/page" was changed in `content/lesson-ui.json` (`preflight_first`), `content/preflight.json` (`errors.preflight_incomplete`), `content/glossary.json` (CLI) and two troubleshooting lines in `content/steps.json`. The setup screen keeps its own heading "Before you begin". Lesson bodies in `content/lessons.json` say "Your setup is ready" and "Setup is done"; they are course text outside this change and were left alone, and a preview of those lessons before setup shows a note that says setup is not finished.
- **`pending-lessons.json` is still written** when a participant skips setup and works the mission before a project exists, because the setup-access spec says the mission works as normal then. It is cleared by both resets. This differs from the task wording "stop writing pending-lessons.json for new installs".
- **The mission stays open before setup** (it is the one lesson with no hands-on exercise), so a lesson-level status of `active` for the mission is the one exception to "every lesson is locked" after a configuration reset. Everything else, and every step, is locked.
- **Before setup, with the open lessons finished,** the page shows the next locked lesson as a preview instead of an empty course.
- **The reminder banner** is part of the app page (lessons, steps, previews, Settings, and the glossary panel over them). The printable reference page is a separate static page that never talks to the server, so it has no banner.
- **Text size** is applied through a `data-text-size` attribute and one CSS rule per step, not an inline style, so the reference page's "no inline styles" check still holds and the printable card is unaffected.
- **The viewport meta tag** already existed in `index.html`.
- **Reset and the backup:** `.learning\` is always moved, so a reset replaces the earlier backup even when little was produced. The backup has `project\` and `app\` subfolders and no timestamp folder.

## Open Questions

Assumed defaults, confirmed or changed in review:

1. **Setup is a first-run gate that can be skipped, presented as a full-page wizard.** Setup is shown first. Skipping opens the course with the banner; the skip is remembered across launches (no nagging screen) until a configuration reset. This replaces the earlier assumption that a multi-page wizard was not required; confirmed by the user in the amendment: one check per page, Next disabled until the page's check passes, no sidebar beside it, "Skip for now" always available on first run, and the same wizard from Settings and the banner.
2. **Reading ahead before setup.** Assumed: all lessons are readable as read-only previews in any order. Simpler alternative: only lessons open by normal order are readable, which would stop at the first CLI exercise (the second lesson).
3. **`rule_lab` counts as reading, not hands-on.** It runs inside the app. Confirm while applying task 2.2 that it needs no CLI or private runtime.
4. **Phone range.** 90% to 130%, default 100%, phone defined as a touch device with a shorter screen side of 600px or less.
5. **Backup location.** `<home>\reset-backup\`, one slot, named in the dialogs.
6. **Kept after "Reset lesson progress".** Starting prompt and test cases, bundled skills, setup, runtimes and display choices.
7. **No Quit inside the wizard.** The wizard has no tools, so Quit is not offered while it is open (skip or close first). Assumed.
8. **Opening with everything passed.** A wizard opened from Settings with all checks passed starts on the first page. Assumed.
9. **"Check everything" stays.** It remains as a button in the wizard footer in addition to each page's own controls. Assumed.
