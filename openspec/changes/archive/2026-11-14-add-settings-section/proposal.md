# Proposal

## Why

Participants cannot change how the app looks, cannot start over without deleting files by hand, and can only reach setup through a course-list entry. Setup is global (one time per install), yet it currently sits in the middle of the course as if it belonged to a lesson. The app is desktop first but must also work on a phone, and larger text is the most common need. A Settings panel gives these controls one home, and setup becomes a global screen instead of a course item. This is the first change run through the spec-driven pilot.

## What Changes

- Add a **Settings** entry to the sidebar's tool list, directly before **Quit**. It opens a **Settings panel** that shows every option at once: text size, setup, and the two resets.
- **Text size**: a slider that scales all app text. On desktop it runs from 80% to 150% (default 100%). When a phone is detected it uses values suited to phones (90% to 130%). The layout adapts at every size, desktop first and phone second.
- **Setup is global**: it is shown first, once, on first run and again after the app configuration is reset, and is never repeated per lesson or Part. The "Before you begin" entry is **removed from the course list** and no lesson or step has its own setup screen. Everything setup does stays available from Settings at any time.
- **Setup is a full-page wizard**: "Before you begin" is no longer shown next to the course sidebar and terminal, which was confusing. It takes over the whole window, one check per page (Track, Python, AI CLI, Sign in and license, CLI working test, Project folder), with a progress indicator, Back and Next. Next stays disabled until the page's check passes. "Skip for now" is always available on first run. The same wizard opens from the Settings setup group and from the reminder banner, and the terminal appears inside the pages that use the CLI.
- **Setup can be skipped.** A participant who skips it can still read all learning content, but hands-on work (steps and exercises that start their CLI) stays unavailable until setup passes. A slim, always-visible **reminder banner** says so and has a button back to setup.
- **Two resets**, both leaving no leftovers in the app:
  - **Reset lesson progress**: clears course progress and everything the app and the participant's CLI produced during the course. Setup and the starting prompt and test cases stay.
  - **Reset app configuration**: does all of that, and also clears setup, the remembered project, the starting files and the display choices, so the app behaves like a first run.
  - Nothing is hard-deleted from the project folder: what is cleared is moved to **one backup folder** that is replaced at the next reset. Answer keys are never backed up.
- Interface changes are authorized by the user for this task (AGENTS.md rule 11), limited to Settings, the removal of the setup course-list entry, and the layout work needed for text size. The user also authorized, in the amendment of this change, the setup wizard: a full-page screen that hides the sidebar and tools while open, per-page layout with Back, Next and progress, the Settings setup group becoming a summary with an "Open setup" button, and the banner button opening the wizard. Nothing else in the interface is covered.

## Capabilities

### New Capabilities
- `settings-page`: the sidebar entry and the Settings panel, on desktop and on phones.
- `text-size`: the slider, phone-aware values, live apply, memory and adaptive layout.
- `setup-access`: setup as a one-time global first-run screen that can be skipped, available in Settings, gating hands-on work, and not part of the course.
- `setup-banner`: the always-visible, unobtrusive reminder while setup is incomplete.
- `progress-reset`: "Reset lesson progress".
- `configuration-reset`: "Reset app configuration".

### Modified Capabilities
<!-- None. The app has no OpenSpec specs yet; existing behavior is described in docs/SPEC.md and is not re-specified here. -->

## Impact

- Web UI (`app/eval_coach/web/`): Settings tool and panel, text-size slider, size-aware breakpoints, viewport setting, terminal font scaling, removal of the setup course-list entry and the "view finished setup" path, a skip action on the setup screen, the reminder banner, read-only previews of lessons before setup, and the setup wizard (a full-page screen with its own layout and navigation, replacing the two-column setup screen and the embedded setup list in Settings).
- Content (`content/lesson-ui.json` or a new settings block): every word shown in Settings and in the reset dialogs. Wording that points to "the Before you begin screen" is reviewed.
- Server: two reset operations and a backup routine; the engine clears in-memory state.
- Storage: a new browser display choice; a new `<home>\reset-backup\` folder. `docs/SPEC.md` (Storage, HTTP contract, course model, Settings) and `docs/DESIGN.md` need updating.
- Tests: backend tests for both resets and the backup; interface tests for Settings, the slider, phone emulation, and layout at several sizes and widths.
- Out of scope: changing setup rules, checks or setup endpoints (the wizard only changes how they are presented); per-Part resets; restoring from the backup inside the app (it is a plain folder); progress export; server-side display settings; deleting downloaded runtimes; Mac.
