# eval-coach implementation plan

Status as of 2026-11-10. Phases 0, 1 and 2 are closed. Phase 3 is closed, and Phase 3F (learning-priority alignment, added and built 2026-11-10) has added content tasks to it. Decision D5 settled 3.28 as not applicable. Decision D1 approved Phases 3 and 4 on 2026-11-09. Phase 4 is built and verified on the stand-in. Decision D2 (2026-11-09) put live mode in as an optional step. Decision D6 (2026-11-10) allows one Stage 3 note. Phases 5 and 6 have not been approved yet. Phase 7 (Mac) is deferred. On 2026-11-14 the OpenSpec change `align-series-content-with-intent` (task 3.46, in progress) restructures the course into seven concept lessons and aligns the content and interface with `SERIES-INTENT.md` and `STAGE3-TASK-SPEC.md`; text below that names the earlier eleven lessons (lesson numbers 0 to 10) records the original build and is superseded by 3.46.

eval-coach turns Part 3 of the "Evaluated Systems (Stage 3)" series, "Running evals and baseline" (WPG AIR Session 3 in the source materials), into a standalone Windows learning app. There is no presenter and there are no handouts. The app wraps the participant's own AI CLI.

Related documents: [SERIES-INTENT.md](SERIES-INTENT.md) says what the whole series is for, [STAGE3-TASK-SPEC.md](STAGE3-TASK-SPEC.md) says what the Stage 3 task is (the Prompt, the Evaluations and the Log), [SPEC.md](SPEC.md) is the build spec and HTTP contract, [PHASE2.md](PHASE2.md) is the preflight spec, [KEY-AFTER-LOCK.md](KEY-AFTER-LOCK.md) is the answer-key change, and [DESIGN.md](DESIGN.md) is the interface design system ("Graphite and Lime": light and dark themes, course sidebar) and the research behind it (2026-11-10).

## Progress at a glance

Legend: ✅ **Done** (the "Done when" check was run and passed) · ⏳ **To do** (not started, waiting on a go-ahead) · ⏸ **Deferred** (starts only on request) · ➖ **Not applicable or not authorized** (a decision closed it; see the task).

| Phase | Tasks | Status | Left to do |
|---|---|---|---|
| 0. Wrapper test | 0.1 to 0.4 | ✅ Done | None |
| 1. Working slice | 1.1 to 1.13 | ✅ Done (stand-in coverage gap accepted) | Real-CLI runs, in 6.5 to 6.7 |
| 1K. Answer key after lock | 1K.1 to 1K.7 | ✅ Done | None |
| 2. Preflight | 2.1 to 2.21 | ✅ Done | Live-console, clean-account and proxy checks, in 6.2 to 6.4 |
| 3A to 3E. Course content | 3.1 to 3.35 | ✅ Done (3.28 ➖ not applicable, D5) | None |
| 3F. Learning-priority alignment | 3.36 to 3.46 | 3.36 to 3.45 ✅ Done (3.41 ➖ not authorized); 3.46 🔄 Running (OpenSpec change `align-series-content-with-intent`) | 3.46 verification; pilot checks 6.14 to 6.16 |
| 4. Baseline, promptfoo, import | 4.1 to 4.28 | ✅ Done on the stand-in (4.18 built under D2) | Real-CLI runs, in 6.5 to 6.7 |
| S. Settings and global setup | S.1 to S.5 (OpenSpec change `add-settings-section`) | ✅ Done on the stand-in; the change is archived and its specs are in `openspec/specs/` | Real-browser check on a phone |
| M. Series map | M.1 to M.5 (OpenSpec change `add-series-map`) | ✅ Done on the stand-in; the change is archived and its specs are in `openspec/specs/` | None |
| G. Generalize Parts | G.1 to G.5 (OpenSpec change `generalize-parts`) | ✅ Done on the stand-in; the change is archived and its spec is in `openspec/specs/` | None; `add-part-1` builds on it |
| P1. Part 1: structured prompting | P1.1 to P1.9 (OpenSpec change `add-part-1`) | ✅ Built and verified on the stand-in; the change is archived and its specs are in `openspec/specs/` | Two real-CLI sessions (the cold run and the rewrite run) after the user approves them, in Phase 6 |
| C. Content clarity | C.1 to C.8 (OpenSpec change `content-clarity`) | ✅ Done on the stand-in; the change is archived (2026-11-16) and its specs are in `openspec/specs/` | None; guided setup (change 2) builds on this vocabulary |
| P2. Part 2: defining evaluation criteria | P2.1 to P2.9 (OpenSpec change `add-part-2`) | 🔄 Built on the stand-in; the final integration check (P2.9) and the user's wording review before archive are pending | P2.9; no real CLI is involved, so no real-CLI budget is used |
| R. Read ahead always | R.1 to R.4 (OpenSpec change `read-ahead-always`) | ✅ Done on the stand-in; the change is archived and its specs are in `openspec/specs/` | None |
| 5. Package | 5.1 to 5.8 | ⏳ To do, needs go-ahead | All 8 tasks |
| 6. Pilot | 6.1 to 6.16 | ⏳ To do, needs go-ahead and D4 | All 16 tasks |
| 7. Mac | 7.1 to 7.6 | ⏸ Deferred | All 6 tasks |

Open decisions: D1 (go-ahead for Phases 5 and 6), D3 (zip delivery) and D4 (pilot users and CLIs). D2, D5 and D6 are decided.

## Master task table

One line per task. The detailed table, files and "Done when" check for each task are in the phase sections below. Keep this table in step with them: change the status here whenever a task's status changes.

| ID | Task (short) | Status |
|---|---|---|
| **Phase 0** | **Wrapper test** | ✅ Done |
| 0.1 | Host three real CLIs in ConPTY via `ctypes` | ✅ Done |
| 0.2 | Type one line, wait about 400 ms, send Enter separately | ✅ Done |
| 0.3 | Verify no-admin Python 3.13.17 embeddable install by hash | ✅ Done |
| 0.4 | Verify private Node 26.13.0 and a promptfoo 0.125.1 eval | ✅ Done |
| **Phase 1** | **Working slice** | ✅ Done |
| 1.1 | Local server: token, Host and Origin checks, CSP, 2 MB limit | ✅ Done |
| 1.2 | Terminal session, output replay, SSE stream | ✅ Done |
| 1.3 | Step state machine and resumable progress | ✅ Done |
| 1.4 | Project creation, blind and isolated folders | ✅ Done |
| 1.5 | File-based gates | ✅ Done |
| 1.6 | Test-case and checker-output parsers | ✅ Done |
| 1.7 | Direct checker runner and no-AI-calls scan | ✅ Done |
| 1.8 | Browser interface with embedded terminal | ✅ Done |
| 1.9 | Step guidance content | ✅ Done |
| 1.10 | Zipapp build | ✅ Done |
| 1.11 | Real Claude Code through setup, generate, restart, build | ✅ Done |
| 1.12 | Real Claude Code through fixtures | ✅ Done |
| 1.13 | Readback, predict, run and fix on the stand-in | ✅ Done |
| **Phase 1K** | **Answer key after lock** | ✅ Done |
| 1K.1 | Add the `key` step between `predict` and `run` | ✅ Done |
| 1K.2 | Fixtures step writes two files only; delete a stray key | ✅ Done |
| 1K.3 | `key-work` folder, gate, move to sealed storage | ✅ Done |
| 1K.4 | Exact step text and typed lines for the key | ✅ Done |
| 1K.5 | Key panel in the interface | ✅ Done |
| 1K.6 | Resume older progress with no `key` entry | ✅ Done |
| 1K.7 | Stand-in key stage | ✅ Done |
| **Phase 2** | **Preflight** | ✅ Done |
| 2.1 | Detect Python 3.9+, skip WindowsApps stubs | ✅ Done |
| 2.2 | Consent, download, pinned SHA-256, extract | ✅ Done |
| 2.3 | Launch `eval-coach.pyz --python <path>` | ✅ Done |
| 2.4 | Paths with spaces, `&`, `(`, `)`, accents | ✅ Done |
| 2.5 | Plain failure messages with a next action | ✅ Done |
| 2.6 | Preflight state file and HTTP routes | ✅ Done |
| 2.7 | Lock real steps until preflight passes | ✅ Done |
| 2.8 | Track choice, Script by default | ✅ Done |
| 2.9 | Python item (running interpreter and CLI PATH) | ✅ Done |
| 2.10 | Node item: reuse 22.22.0+ or consented private install | ✅ Done |
| 2.11 | promptfoo 0.125.1 predownload with progress | ✅ Done |
| 2.12 | CLI item and install recipes from data | ✅ Done |
| 2.13 | Sign-in and license confirmation | ✅ Done |
| 2.14 | CLI working test from `output.txt` and `version.txt` | ✅ Done |
| 2.15 | Project folder item: not in OneDrive, files exist | ✅ Done |
| 2.16 | CLI and checker environment: no permission flags | ✅ Done |
| 2.17 | Background work: progress, timeout, single-run guard | ✅ Done |
| 2.18 | Disk check and failure messages | ✅ Done |
| 2.19 | Integration: real `setup.cmd` launches real `.pyz` | ✅ Done |
| 2.20 | Stand-in end-to-end through preflight | ✅ Done |
| 2.21 | Orchestrator verifies agent results independently | ✅ Done |
| **Phase 3A** | **Lesson engine** | ✅ Done |
| 3.1 | Lesson schema | ✅ Done |
| 3.2 | Load and validate lessons from the bundle | ✅ Done |
| 3.3 | Lessons in the course order, gating steps | ✅ Done |
| 3.4 | Migrate existing progress | ✅ Done |
| 3.5 | Lesson view | ✅ Done |
| 3.6 | Single-choice question with feedback | ✅ Done |
| 3.7 | Shuffle answers, enforce equal answer length | ✅ Done |
| 3.8 | Practice activity: run a rule on sample text | ✅ Done |
| 3.9 | Written reflection activity | ✅ Done |
| 3.10 | Learning record only for demonstrated understanding | ✅ Done |
| 3.10a | Ordering and sorting activities | ✅ Done |
| 3.10b | CLI activities: three-run hook and anatomy demo | ✅ Done |
| 3.10c | Read-only viewer for bundled source files | ✅ Done |
| **Phase 3B** | **Placement and review** | ✅ Done |
| 3.11 | Placement questions | ✅ Done |
| 3.12 | Review scheduler at 1, 3 and 7 days | ✅ Done |
| 3.13 | Review queue shown on reopen | ✅ Done |
| 3.14 | Mix topics within a review session | ✅ Done |
| **Phase 3C** | **Lessons** | ✅ Done |
| 3.15 | Lesson 0: mission (a one-page introduction with no questions; placement removed, to be replaced by separate tracks) | ✅ Done |
| 3.16 | Lesson 1: hook (now `hook`) | ✅ Done |
| 3.17 | Lesson 2: the loop and two actors (merged into `several-runs` by 3.46) | ✅ Done |
| 3.18 | Lesson 3: generate (merged into `several-runs` by 3.46) | ✅ Done |
| 3.19 | Lesson 4: from threshold to rule (now `rules`) | ✅ Done |
| 3.20 | Lesson 5: build and first look (merged into `rules` by 3.46) | ✅ Done |
| 3.21 | Lesson 6: interpretation choices (merged into `rules` by 3.46) | ✅ Done |
| 3.22 | Lesson 7: fixtures, read back, predict (now `trust`) | ✅ Done |
| 3.23 | Lesson 8: run and compare (merged into `surprise` by 3.46) | ✅ Done |
| 3.24 | Lesson 9: fix the spec (merged into `surprise` by 3.46) | ✅ Done |
| 3.25 | Lesson 10: baseline and bridge (now `baseline-why`) | ✅ Done |
| **Phase 3D** | **Reference and quality** | ✅ Done |
| 3.26 | In-app glossary | ✅ Done |
| 3.27 | Printable one-page reference | ✅ Done |
| 3.28 | External primary source and citations | ➖ Not applicable (D5) |
| 3.29 | Banned-word content test | ✅ Done |
| 3.30 | Plain-language review | ✅ Done |
| 3.31 | Stand-in end-to-end through the lessons | ✅ Done |
| **Phase 3E** | **Guided coaching refinement** | ✅ Done |
| 3.32 | Every lesson opens with a recap and plain explanation | ✅ Done |
| 3.33 | No question blocks Continue | ✅ Done |
| 3.34 | Short check after each CLI exercise | ✅ Done |
| 3.35 | "Quick check" question on each step page | ✅ Done |
| **Phase 3F** | **Learning-priority alignment** | 🔄 Running (3.46) |
| 3.36 | "Say it in plain words" activities (tier 1) | ✅ Done |
| 3.37 | State what a rule cannot check (tier 1) | ✅ Done |
| 3.38 | Series workflow in lesson 0 (tier 2): taught by the series table; the ordering activity was removed with the lesson's questions | ✅ Done |
| 3.39 | Stage 3 note at end of the last lesson (tier 3; reworked by 3.46 to the Prompt, Evaluations and Log structure) | ✅ Done |
| 3.40 | `test_learning_priorities.py` guard test | ✅ Done |
| 3.41 | "Evidence you hold" panel (new interface element) | ➖ Not authorized |
| 3.42 | Re-run all checks after 3.36 to 3.40 | ✅ Done |
| 3.43 | Correct the six-session series wording | ✅ Done |
| 3.44 | Bring the stand-in harness up to date | ✅ Done |
| 3.45 | Lesson 0 as a question-free introduction with an outcome-based mission | ✅ Done |
| 3.46 | Align the series content and interface with `SERIES-INTENT.md` and `STAGE3-TASK-SPEC.md`: seven concept lessons, the procedure in the steps, Prompt/Evaluations/Log Stage 3 note, "Part" wording, grouped course list, reference card and glossary, and the Part 6 note (OpenSpec change `align-series-content-with-intent`) | 🔄 Running |
| **Phase 4A** | **Baseline step** | ✅ Done |
| 4.1 | Add `baseline` step after `fix` | ✅ Done |
| 4.2 | Script-track typed line for run and log mode | ✅ Done |
| 4.3 | Iteration log parser | ✅ Done |
| 4.4 | App runs the checker on all five runs | ✅ Done |
| 4.5 | Gate: log totals match; NOT CHECKED listed | ✅ Done |
| 4.6 | Baseline view: pass rate per criterion | ✅ Done |
| 4.7 | Step content and bridge to Part 4 | ✅ Done |
| **Phase 4B** | **promptfoo track** | ✅ Done |
| 4.8 | Track-specific lines and content | ✅ Done |
| 4.9 | Build line naming `run-1` to `run-5` as tests | ✅ Done |
| 4.10 | `fixtures-config` step after fixtures | ✅ Done |
| 4.11 | App runs the promptfoo eval | ✅ Done |
| 4.12 | App runs `summarize_results.py` | ✅ Done |
| 4.13 | Parser for the summary output | ✅ Done |
| 4.14 | Config scan rejects `llm-rubric` and non-`echo` providers | ✅ Done |
| 4.15 | Gates for build, run, fix and baseline on the config | ✅ Done |
| 4.16 | Explain "all failed while anything is NOT CHECKED" | ✅ Done |
| 4.17 | Stand-in end-to-end on the promptfoo track | ✅ Done |
| 4.18 | Optional live mode `live` step (D2) | ✅ Done |
| **Phase 4C** | **Import the participant's own work** | ✅ Done |
| 4.19 | Import screen for prompt and test cases | ✅ Done |
| 4.20 | Rename guidance for `prompt-v0.md`, `test-cases.md` | ✅ Done |
| 4.21 | Check: three or more criteria | ✅ Done |
| 4.22 | Check: at least one content criterion | ✅ Done |
| 4.23 | Check: criteria trace to requirements | ✅ Done |
| 4.24 | Check: flag vague words in thresholds | ✅ Done |
| 4.25 | Offer Northwind only as a learning starter | ✅ Done |
| **Phase 4D** | **Troubleshooting** | ✅ Done |
| 4.26 | Move "If something breaks" items into steps | ✅ Done |
| 4.27 | Windows line-ending guidance | ✅ Done |
| 4.28 | Northwind fixtures as a recovery path | ✅ Done |
| **Phase S** | **Settings and global setup** (OpenSpec change `add-settings-section`) | ✅ Done on the stand-in |
| S.1 | Resets: the inventory, "Reset lesson progress" and "Reset app configuration" with one backup | ✅ Done |
| S.2 | Setup as a skippable global first-run gate, hands-on gating, read-only previews, reminder banner | ✅ Done |
| S.3 | Text size slider (80 to 150, phones 90 to 130) and a layout that follows it | ✅ Done |
| S.4 | Settings panel before Quit: text size, setup, reset | ✅ Done |
| S.5 | Integration: backend, interface and stand-in runs; docs | ✅ Done |
| S.6 | Setup wizard (amendment): full-page, one check per page, Back and Next, terminal inside the CLI pages, opened from first run, Settings and the banner | ✅ Done on the stand-in |
| **Phase M** | **Series map** (OpenSpec change `add-series-map`) | ✅ Done on the stand-in |
| M.1 | `content/series.json` and `state.series`; the Part names and Part 1 to 5 outcomes agree with the mission map | ✅ Done |
| M.2 | The Series map as the home screen, with a Part 3 row that expands and opens, "Coming soon" rows and the Part 6 "Live meeting" row | ✅ Done |
| M.3 | "Back to series map" in the sidebar and the narrow-screen bar; Settings and the setup wizard return to the screen they came from | ✅ Done |
| M.4 | Interface tests, mock API and stand-in harness go through the map | ✅ Done |
| M.5 | Docs: Part 6 wording exception, `SPEC.md` Series map section, coverage column | ✅ Done |
| **Phase G** | **Generalize Parts** (OpenSpec change `generalize-parts`) | ✅ Done on the stand-in |
| G.1 | The Part registry in `state.py` (`Part`, `PARTS`, `part_of`, step kinds, `register_part`) and per-Part saved progress (`parts.<id>`, validation, migration) | ✅ Done |
| G.2 | The content loader per Part (`load_bundled`, `load_step_content`, unique ids, step kinds) and the content tests over every Part | ✅ Done |
| G.3 | The engine resolves the Part from an id; the step kind hook; the `part` selector on `GET /api/state`; the Series map built per registered Part | ✅ Done |
| G.4 | Shared pieces checked with two Parts (review, pending progress, both resets) and the Series map cross-check | ✅ Done |
| G.5 | Docs and integration: `SPEC.md` "Parts", backend suites, interface suite, build smoke test, stand-in harness | ✅ Done |
| **Phase P1** | **Part 1: structured prompting** (OpenSpec change `add-part-1`) | ✅ Built on the stand-in |
| P1.1 | Bundled kit files `kit/part1/` (rough notes, typical gaps, reveal table, two sample prompts) | ✅ Done |
| P1.2 | `content/part-1-lessons.json`, `part-1-steps.json`, glossary entries and the Part 1 row on the Series map (`kind: course`, per-Part `ui`) | ✅ Done |
| P1.3 | Content tests: discovery before theory, citation boundaries, equal choice lengths, banned words, the Stage 3 note | ✅ Done |
| P1.4 | The Part 1 registry entry, `part_steps.py` (the `write_and_run`, `score_form` and `write_pair` kinds) with gates and views, setup gating and locking | ✅ Done |
| P1.5 | Reset inventory for `part-1\` and `<home>\part1\`; the `part` field on every route's returned state | ✅ Done |
| P1.6 | Interface (authorized 2026-11-15, U1 to U5): `app.part`, `js/part-steps.js` (prompt editor, score form, compare, own form), Part 1's row and groups | ✅ Done |
| P1.7 | Interface tests: the mock API's Part 1 row, `tests/frontend/part1.spec.js` against the real app (`real_server.py`) | ✅ Done |
| P1.8 | Stand-in harness: `fake_cli.py` answers a labelled prompt better; stage `part1` | ✅ Done |
| P1.9 | Docs and integration: `SPEC.md` "Part 1", this plan, `COURSE-CONTEXT.md`, `PHASE3.md`, `AGENTS.md` Status; both backend suites, the interface suite, build smoke test, the harness on both tracks | ✅ Done |
| **Phase P2** | **Part 2: defining evaluation criteria** (OpenSpec change `add-part-2`) | 🔄 Built on the stand-in; P2.9 pending |
| P2.1 | Bundled kit files `kit/part2/` (the worked examples, the blank test case template) | ✅ Done on the stand-in |
| P2.2 | `content/part-2-lessons.json`, `part-2-steps.json`, glossary entries and the Part 2 row on the Series map (`kind: course`, per-Part `ui`, groups) | ✅ Done on the stand-in |
| P2.3 | Content tests: no reference leak, discovery before the reveal, equal option lengths, banned words, the Stage 3 note naming the Evaluations | ✅ Done on the stand-in |
| P2.4 | The Part 2 registry entry, `criteria_steps.py` (the `criteria_table`, `test_file` and `reveal_compare` kinds) with gates, findings and the reveal, setup gating and locking | ✅ Done on the stand-in |
| P2.5 | Reset inventory for `part-2\` and the project helpers (`PART2_DIR`, `Paths.part2_file`) | ✅ Done on the stand-in |
| P2.6 | Interface (authorized in the change's proposal, U6 to U8): `js/criteria-steps.js` (worksheet, test-file and reference panels), `part-2` in the default Series map expansion | ✅ Done on the stand-in (screenshots at 1280, 900 and 390 pixels, both themes and the largest text size, to be viewed in P2.9) |
| P2.7 | Interface tests: the mock API's Part 2 row, `tests/frontend/part2.spec.js` against the real app | 🔄 Running (`part2.spec.js` is not in place yet) |
| P2.8 | Stand-in harness: stage `part2` (works the lessons, fills and saves the worksheet, adds thresholds, builds and saves the file, classifies the reference) | ✅ Written; its run is part of P2.9 |
| P2.9 | Docs and final integration check: both backend suites, the whole interface suite, `python tools\build_pyz.py --smoke` (`part-2-*.json`, `kit/part2` and `criteria_steps.py` inside the archive), the stand-in harness on both tracks, `openspec validate add-part-2 --strict` | ⏳ Pending verification (docs are done) |
| **Phase C** | **Content clarity** (OpenSpec change `content-clarity`) | ✅ Done on the stand-in |
| C.1 | Vocabulary tests `tests/test_participant_vocabulary.py`: no bare "CLI", no "Northwind" as an option name, glossary "AI window", track words, series intro, categories, no CRISP in Part 1 | ✅ Done |
| C.2 | Mission lessons share one shape (goal, why it matters to you, what you will do, what you leave with); no map; the series framing in `p1-mission` only | ✅ Done |
| C.3 | "AI window" glossary entry and "your AI" across content, interface strings and participant-visible server messages | ✅ Done |
| C.4 | "Practice task" and "My own task" for the ready-made example and the other starter | ✅ Done |
| C.5 | `p1-frameworks` rebuilt: numbered five categories and one table per framework; "categories" instead of "kinds" in Part 1 | ✅ Done (finding: the lesson body is 400 words, so its test cap is 420) |
| C.6 | Track descriptions by technical level, no default wording; Series map intro | ✅ Done (finding: the Track page still preselects the Script track, because `preflight.py` stores `"script"` as the initial track; removing that is an interface change that needs authorization) |
| C.7 | Docs: `docs/SPEC.md`, `COURSE-CONTEXT.md`, `PHASE3.md`, `AGENTS.md` rule 10, `docs/temp/series-review-pending-changes.md` | ✅ Done |
| C.8 | Verification: both backend suites, the interface suite, `python tools\build_pyz.py --smoke`, the stand-in harness on both tracks | ✅ Done |
| **Phase 5** | **Package** | ⏳ To do (needs go-ahead) |
| 5.1 | Build `eval-coach.zip` with exactly two files | ⏳ To do |
| 5.2 | Version number in the app and in progress | ⏳ To do |
| 5.3 | Test the zip after a download mark (Mark of the Web) | ⏳ To do |
| 5.4 | Confirm message for running from inside the zip | ⏳ To do |
| 5.5 | SmartScreen guidance (D3) | ⏳ To do |
| 5.6 | Confirm test seams cannot bypass the pinned hash | ⏳ To do |
| 5.7 | Recheck pinned versions and hashes | ⏳ To do |
| 5.8 | Write `docs/RELEASE.md` | ⏳ To do |
| **Phase 6** | **Pilot** | ⏳ To do (needs go-ahead and D4) |
| 6.1 | Choose 3 to 5 Windows users | ⏳ To do |
| 6.2 | Double-click `setup.cmd` at a live console | ⏳ To do |
| 6.3 | Run on a clean Windows account | ⏳ To do |
| 6.4 | Run behind the company proxy | ⏳ To do |
| 6.5 | Real CLI: fixtures line writes no key | ⏳ To do |
| 6.6 | Real CLI: key line writes only the key | ⏳ To do |
| 6.7 | Real CLI: readback, run, fix, baseline | ⏳ To do |
| 6.8 | Test install recipes on a pilot machine | ⏳ To do |
| 6.9 | Observe approval prompts and auto-mode menu | ⏳ To do |
| 6.10 | Record where people got stuck and timings | ⏳ To do |
| 6.11 | Sort findings into must-fix and later | ⏳ To do |
| 6.12 | Fix and retest must-fix items | ⏳ To do |
| 6.13 | Release decision | ⏳ To do |
| 6.14 | Tier 1 check: explain and run an evaluation | ⏳ To do |
| 6.15 | Tier 2 check: place the evaluation in the series | ⏳ To do |
| 6.16 | Tier 3 check: name the Stage 3 artifacts | ⏳ To do |
| **Phase 7** | **Mac** | ⏸ Deferred |
| 7.1 | Terminal layer on `pty` | ⏸ Deferred |
| 7.2 | `setup.sh` matching `setup.cmd` | ⏸ Deferred |
| 7.3 | Private Node install for Mac | ⏸ Deferred |
| 7.4 | Mac commands in recipes and step text | ⏸ Deferred |
| 7.5 | Quit, process-tree stop, path handling | ⏸ Deferred |
| 7.6 | Test on a real Mac | ⏸ Deferred |

## Learning priorities

Every content, activity and pilot decision is ranked by this hierarchy (set by the user, 2026-11-10):

| Tier | Priority | What a participant can do at the end |
|---|---|---|
| 1 | **Core knowledge (top)** | Understand evaluation concepts and run an evaluation, and explain both to a technical and to a non-technical audience |
| 2 | **Context (secondary)** | Describe the end-to-end workflow and where an evaluation fits in the broader process |
| 3 | **Certification (tertiary)** | See how the work they produced lines up with the Stage 3 certification requirements |

Rules for using the hierarchy:
- When two tasks compete for time or screen space, the higher tier wins.
- Certification content never replaces, delays or gates tier 1 or tier 2 content. It never blocks Continue.
- The app teaches and shows alignment. It never certifies, never scores a submission and never gives submission steps.
- "Explain it" is part of tier 1: knowing the concept and running it is not enough unless the participant can also say it in plain words to a non-technical reader.

**Reading of "priority order"** (stated 2026-11-14; the order is tier 1 core knowledge > tier 2 context > tier 3 certification). When two items compete for time or screen space, the higher tier wins: a tier 1 idea is placed, worded and sized before a tier 2 or tier 3 item, and a lower-tier item is the one that is shortened or cut. The order ranks content; it does not make lower tiers optional to the point of omission, so each tier still gets its place, in proportion (for example the Stage 3 note is at most 150 words and optional, the mission is at most 450 and a lesson at most 300).

**Audit 2026-11-14** (against `docs/SERIES-INTENT.md` and `docs/STAGE3-TASK-SPEC.md`; task 3.46, OpenSpec change `align-series-content-with-intent`, proposal "Audit findings"). Findings, in priority order:
- Tier 1: the series purpose (judge AI work and trust it because it was checked, neither blind trust nor blind distrust) was never stated. "Why it matters" was missing: AI sounds sure of itself when it is wrong, "better" is an opinion until measured, answers change from one try to the next (the last two were taught by activities, the first was not said). The limits of a score (one prompt against one set of rules, no guarantee for future answers) were not said in plain words. The last lesson said what comes next but not the Part 4 rule that makes a baseline useful: if the score did not move, the change did not help.
- Tier 2: the course map labelled Parts 4 to 6 with wording that differs from the intent's table, and its Part names were not the series names. There was no bridge from the Northwind practice case to the participant's own repeating work (Part 6: repeats, clear requirements, checkable by rules).
- Tier 3: the Stage 3 note named three criteria ("written evaluation framework", "before and after numbers", "reusable library of prompt templates") dated "as of June 2026", which differs from the intent and the task spec (three submitted artifacts: Prompt, Evaluations, Log). The note did not say that scripts, promptfoo files and written test cases are all accepted.
- Terminology (rule 10, "Part, not session"): participant-facing content said "Session N" about 25 times, with no test to enforce the rule, plus three hard-coded interface strings.
- Structure and framing: the 11 lessons followed the app's procedure, not the series method; about 7 taught this course's own mechanics in absolute wording, and 10 of 33 activities tested only those mechanics, so tier 3-style procedure sat on top of tier 1 ideas and nothing said other approaches exist (the task spec says the approach is the participant's choice and the file layout a suggestion). The fix is structural (seven lessons, procedure in the steps), not wording alone.
- Interface (authorized 2026-11-14, items U1 to U6 and U8): a flat sidebar list mixing lessons and steps; "parts" used for lessons and steps, clashing with the six Parts; hard-coded Part strings in `views.js` and `markdown.js`; a reference card that presented this course's loop, verdicts, exit code and "who does what" as the method; one flat glossary mixing ideas and course terms; step titles carrying course choices; a finished screen that did not say what comes next.
- Checked and already aligned (no change): the Northwind requirements and criteria, the iteration-log fields against the task spec, the fixture thresholds, NOT CHECKED outside the denominator, "never edit the checker to make a failing output pass", the explain-it activities, the mid-tier model in the log, and no submission steps.

### Coverage (audit 2026-11-10, updated after Phase 3F and by 3.46)

Current course: seven concept lessons in the order of the series method (`mission`, `hook`, `several-runs`, `rules`, `trust`, `surprise`, `baseline-why`) with the nine steps between them; see `docs/SPEC.md` "Course and lessons".

| Tier | Outcome | Status | Where | Remaining gap |
|---|---|---|---|---|
| 1 | Series purpose and why checking AI work matters (judge it, trust it because it was checked; sure-sounding mistakes, "better" as an opinion, answers that change) | Covered (3.46), restated in Part 1 (P1) | `mission` and `p1-mission` ("In plain words", "Why it matters") | None |
| 1 | Part 1's why: a structured prompt gives the AI what it needs; frameworks are ready-made labels for kinds of information a prompt needs (our five are an example; build your own when none fits); use one or build your own; the four benefits; one real prompt rewritten | Built on the stand-in (P1) | The Part 1 course: `p1-mission`, `cold`, `score`, `p1-gaps`, `p1-frameworks`, `rewrite`, `rescore`, `p1-benefits`, `own` | Two real-CLI sessions in Phase 6 |
| 1 | Part 2's why: a criterion is one thing a good answer must do and traces to a requirement; the set covers format and content; no two check the same thing; a threshold is a rule a script could decide (vague words become a number, a term or a label); what a rule cannot check is "Not checked"; the rules are written down as test cases before any answer is judged | Built on the stand-in (P2) | The Part 2 course: `p2-mission`, `p2-criteria`, `draft`, `p2-thresholds`, `thresholds`, `p2-testfile`, `test-file`, `reference` | Final integration check (P2.9); the user's review of the wording before archive |
| 1 | Concepts: what an eval is, why a checker beats an AI grader, several runs, thresholds as rules, NOT CHECKED, pass rate, baseline, what a score does and does not tell you | Covered (3.16 to 3.25, reworked by 3.46) | `hook`, `several-runs`, `rules`, `trust`, `surprise`, `baseline-why` | None |
| 1 | Run an eval end to end on the participant's own prompt | Covered | Steps, Phases 1 and 4 | Real-CLI runs wait for Phase 6 |
| 1 | Explain evals to a **non-technical** audience | Covered (3.36) | `hook-explain`, `build-explain`, `baseline-explain`, and a written explanation `baseline-explain-write` | Pilot check 6.14 |
| 1 | Explain evals to a **technical** audience (for example, why a rule is whole-word or part-of-word) | Covered (3.36) | `choices-explain-tech`, plus the lab `choices-lab`, both in `rules` | Pilot check 6.14 |
| 1 | Judgment criteria that a rule cannot check | Covered (3.37) | "What a rule cannot check" in `rules`; the NOT CHECKED glossary entry | None |
| 2 | Where this Part fits in the series and what comes next | Covered (3.38, 3.43, 3.46) | `mission` (six-row map with the intent's Part names) and `baseline-why` ("What comes next": the Part 4 rule that if the score did not move the change did not help) | Pilot check 6.15 |
| 2 | The method (ask clearly, know what you need, turn it into rules, score the result, improve, keep a record) and which link each lesson covers | Covered (3.46) | Each lesson opens "In the method."; the course list groups; the reference card opens with the method | None |
| 2 | Where an evaluation fits in the whole workflow, and how to use the method on the participant's own repeating work (Part 6) | Covered (3.38, 3.45, 3.46) | The mission page (prompt, AI answer, checker and recorded score; the six-Part map) and "Your own work" in `baseline-why` | A team or release process beyond the series has no source (D5) and is out of scope |
| 3 | Stage 3 alignment: the Prompt, the Evaluations and the Log | Covered, in one short optional note (3.39, 3.40, 3.46, D6) | "How this fits the Stage 3 certification" at the end of `baseline-why` (at most 150 words), the optional reflection `baseline-stage3`, and `tests/test_learning_priorities.py` | Pilot check 6.16 |

### Stage 3 alignment map

Sources: [SERIES-INTENT.md](SERIES-INTENT.md) ("How this connects to Stage 3 certification") and [STAGE3-TASK-SPEC.md](STAGE3-TASK-SPEC.md) (sections 3 to 5), both added 2026-11-14. They replace the earlier "three headline criteria" from the June 2026 program page, which differed from them. The official Stage 3 page governs if it differs; submission steps are the program's own, and nothing here replaces them. The app teaches and shows alignment only (tier 3): it never certifies, never scores a submission and never gives submission steps. Stage 3 asks for three submitted artifacts: the **Prompt**, the **Evaluations** and the **Log**. Scripts, promptfoo files and written test cases are all accepted forms of evaluation; the Script and promptfoo tracks are two options among many, and the file names and layout in this course are this course's, a suggestion in the task spec.

| Artifact | What Stage 3 looks for (task spec sections 4 and 5) | What the participant holds after Part 3, and where | Alignment |
|---|---|---|---|
| **Prompt** | A structured prompt; deliberate instructions; at least 90% of instructions each help meet a rule; no filler (Parts 1 and 5) | `prompt-v0.md` from Part 1, used for the five runs. The load-bearing audit is Part 5 | Starting point only |
| **Evaluations** | At least 3 distinct rules; real quality checks; clear pass/fail limits (Part 2); works with a mid-tier model (Part 3); 95% or higher on a known-good output (Part 4) | `test-cases.md` turned into a tested checker (`check.py` or `promptfooconfig.yaml`); the bad and polished-but-wrong fixtures with predictions made before the run; five runs from a mid-tier model; import check 4.21 requires three or more criteria. The 95% confirmation is Part 4 | Covered for rules, checker trust and model fit; ceiling previewed. "At least 3 distinct rules" with clear pass/fail limits is covered by Part 2, built on the stand-in (a worksheet of three or more criteria with format and content covered, a threshold for each, and a `test-cases.md` that passes the file checks) |
| **Log** | At least 2 recorded rounds of improvement; each round has the starting score, hypothesis, change, new score and reasoning; test-first; a clear order of events (Parts 3 to 5) | `iteration-log.md` with Iteration 0 (Prompt, Model, Runs, per-rule table, Overall, Not checked). The improvement rounds come in Part 4 | Partial: Iteration 0 only |

Where each lives in the course: the Stage 3 note is in `baseline-why` only (never elsewhere, never blocking Continue). The wider series outcomes, placed against this course (Part 3):

| Requirement (task spec section 5) | Part | This course |
|---|---|---|
| Structured prompting; 3+ distinct rules; substantive checks; clear pass/fail limits | 1 and 2 | Starting inputs, not taught here. The polished-but-wrong fixture (`trust`, then the `fixtures` step) tests the "not window dressing" point |
| Mid-tier models | 3 | Covered: `several-runs` and the `generate` step |
| Order of events, each change leading to the next | 3 to 5 | Started: Iteration 0 is the first log entry |
| 95% or higher on a known-good output | 4 | Previewed: the known-good output at the end of `baseline-why` |
| 2 or more documented iterations, test-first | 4 | Previewed only: "what comes next" in `baseline-why` |
| 90% or more load-bearing, no filler; deliberate instruction design | 5 | Previewed only: one sentence in `baseline-why` |

Anything beyond these tables belongs to a later Part and is out of scope here.

## How to use this plan

Each task has one outcome and one check that proves it, and should take half a day or less. A task is finished only when its "Done when" check has been run and passed.

Status values are **Done**, **Running** (an agent is working on it now), **To do**, and **Not applicable** or **Not authorized** (closed by a decision). Phase and sub-phase headings carry the same status, and a completed section starts with a status line. Task tables with a Status column show it per task; tables without one are covered by the status line above them.

Rules for every task:
- Follow the non-negotiable rules below.
- Add or update tests in the same task as the code.
- After any app change, run the checks in "Verification commands".
- When behavior or an API changes, update `SPEC.md` in the same task.
- Commit only when the user asks. The repo is under git with `origin` on GitHub; the `post-archive-pr` skill handles the branch, commit, push and PR after an archived change.

### Non-negotiable rules
1. Python standard library only at runtime, with Python 3.9-compatible syntax. The browser UI has no build step.
2. The app sets no permission flags on the CLI and never answers a CLI prompt.
3. The app never reads terminal output to make a decision. It decides by reading files and running the checker itself.
4. "New chat" means a new CLI process, and only one CLI process runs at a time.
5. The only network use by the app itself is consented preflight downloads. There is no telemetry and the app holds no API keys.
6. The participant chooses the CLI and model. There is no allowlist and no CLI-specific logic, except data in `cli-recipes.json`.
7. Copilot Chat in Teams is not approved and is never suggested.
8. Northwind is a learning example and never a submission option.
9. The bundled skills stay byte-identical to the Session 3 source. Changes go in the typed line.
10. No answer key exists until predictions are locked.
11. All guidance lives in the app. Never mention a presenter, room, handout or clock, and never tell people to contact someone. One exception (authorized 2026-11-15): `baseline-why` "Your own work" says, as information only, that Part 6 happens live and that task ideas can be brought to office hours or the AIR discussion. The only other mention is the Series map's Part 6 row (authorized 2026-11-15), which says, as information only, that Part 6 is a live meeting and what it is about, and never names office hours, the AIR discussion, or any person, place, contact detail, link or schedule.
12. Never modify the OneDrive source materials.
13. The interface is not changed without the user's explicit authorization. That covers layout, styling, components, element ids and interface copy (`web/`, `content/lesson-ui.json`, the step `ui` blocks). Where possible, content and server behavior change so that the existing interface shows them unchanged. The 2026-11-10 authorization (task 3.35) covers only the step-page question and the lesson progress and Continue-hint wording. The 2026-11-14 authorization (task 3.46) covers only the course-list group headings, the Part strings and "lessons and steps" wording, the reference card and its method section, the two glossary groups, step titles and goals, and the finished-screen text.

### Rules for tests that touch a real CLI
- Use the stand-in `e2e-work/harness/fake_cli.py` unless the user has approved a real-CLI run.
- Real approvals are single-use "Yes" only, after the full command text is verified, and never "switch to auto mode" or "don't ask again".
- A refused command is brought to the user. The verifier is not widened on an agent's own judgment.
- The real test has used 15 sessions. Its budget of 17 stands unless the user changes it.
- Never run a real CLI install recipe in a test. Never edit CLI settings or credentials.

### Verification commands
Run from `C:\Projects\Improving\eval-coach`.

| Check | Command |
|---|---|
| Backend tests | `python -m unittest discover -s tests` |
| Backend on embedded 3.13 | `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests` |
| Interface tests | `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js` |
| Build and smoke test | `python tools\build_pyz.py --smoke` |
| Stand-in end-to-end | Set `E2E_PROFILE=standin`, then run `node e2e-work\harness\run.js <stage>` for each stage in order |
| Approval rule checks | `node e2e-work\harness\classifier-check.js` |

Backend test count as of 2026-11-10: 1052 tests with 2 skipped by design, all passing on Python 3.12 and on embedded 3.13 (Phase 2 closed at 343; Phase 3 at 668; Phase 4 at 1001; Phase 3F added `test_learning_priorities.py`). `test_conpty.RealConsole.test_type_line_sends_enter_separately` failed once under load and passed on rerun, so treat it as timing-sensitive. Run the two backend suites one after the other, not at the same time: the `setup.cmd` integration test fails when two runs overlap.

---

## Phase 0: Wrapper test — ✅ DONE

**Status: ✅ Done. All 4 tasks (0.1 to 0.4) are complete.**

| ID | Task | Evidence |
|---|---|---|
| 0.1 | Host three real CLIs in ConPTY through Python `ctypes` | `spikes/phase0-wrapper/`; Copilot CLI, Claude Code and Devin CLI hosted |
| 0.2 | Type one line, wait about 400 ms, send Enter separately | Same spike |
| 0.3 | Verify a no-admin Python 3.13.17 embeddable install by hash | `spikes/phase0-preflight/runtime-manifest.json` |
| 0.4 | Verify a private Node 26.13.0 install and a promptfoo 0.125.1 eval | Same folder |

Limit: this was not tested on a clean Windows account. Task 6.3 covers that.

---

## Phase 1: Working slice — ✅ DONE (with a known coverage gap)

**Status: ✅ Done. All 13 tasks (1.1 to 1.13) are complete.** The coverage gap below is accepted and is closed by Phase 6.

| ID | Task | Files | Evidence |
|---|---|---|---|
| 1.1 | Local server on 127.0.0.1 with token, Host and Origin checks, CSP and 2 MB limit | `server.py` | Backend tests |
| 1.2 | Terminal session, output replay, SSE stream | `conpty.py`, `terminal.py` | Backend tests |
| 1.3 | Step state machine and resumable progress | `engine.py`, `state.py` | Backend tests |
| 1.4 | Project creation, blind and isolated folders | `project.py` | Backend tests |
| 1.5 | File-based gates | `gates.py` | Backend tests |
| 1.6 | Test-case and checker-output parsers | `parsers.py`, `tests/golden/` | Golden tests |
| 1.7 | Direct checker runner and no-AI-calls scan | `runner.py`, `scan.py` | Backend tests |
| 1.8 | Browser interface with embedded terminal | `web/` | Interface tests |
| 1.9 | Step guidance | `content/steps.json` | Content tests |
| 1.10 | Zipapp build | `tools/build_pyz.py` | Smoke test |
| 1.11 | Real Claude Code through setup, generate, restart, build | `e2e-work/harness-state.json` | Gates passed, 0 violations |
| 1.12 | Real Claude Code through fixtures | Same | Gate passed under the old typed line, before the key moved |
| 1.13 | Readback, predict, run and fix with a stand-in | `harness-state-standin.json` | Passed |

**Known gap, accepted by the user:** readback, predict, key, run and fix have not run on a real CLI. The two new typed lines have not either. Tasks 6.5 to 6.7 close this.

### Answer key after lock — ✅ DONE

**Status: ✅ Done. All 7 tasks (1K.1 to 1K.7) are complete.**

A real run showed the approval prompt prints the whole key before the participant predicts, so the key now gets written after predictions lock.

| ID | Task | Files | Evidence |
|---|---|---|---|
| 1K.1 | Add the `key` step between `predict` and `run` | `state.py`, `engine.py` | Backend tests |
| 1K.2 | Fixtures step writes two files only; delete a stray key and show a nudge | `project.py`, `gates.py` | Backend tests |
| 1K.3 | `key-work` folder with exactly five files; gate; move to sealed storage | `project.py`, `gates.py` | Backend tests |
| 1K.4 | Exact step text and typed lines | `content/steps.json` | Content tests |
| 1K.5 | Key panel in the interface | `web/js/panels.js` | 33 interface tests |
| 1K.6 | Resume older progress that has no `key` entry | `state.py` | Backend tests |
| 1K.7 | Stand-in key stage | `e2e-work/harness/` | 114 of 114 checks, 0 violations |

---

## Phase 2: Preflight — ✅ DONE

**Status: ✅ Done. Both stages and all 21 tasks (2.1 to 2.21) are complete; exit criteria met.**

### Stage 1: `setup.cmd` — ✅ DONE

**Status: ✅ Done. Tasks 2.1 to 2.5 are complete.**

| ID | Task | Files | Evidence |
|---|---|---|---|
| 2.1 | Detect Python 3.9+, skipping WindowsApps stubs | `packaging/setup.cmd` | `test_setup_cmd.py` |
| 2.2 | Consent, download, pinned SHA-256, extract, delete `python313._pth` | Same | Same; real python.org download passed |
| 2.3 | Launch `eval-coach.pyz --python <path>` | Same, `__main__.py` | Same |
| 2.4 | Paths with spaces, `&`, `(`, `)` and accented names | Same | Same |
| 2.5 | Plain failure messages with a next action | Same | 31 tests: 30 passed, 1 skipped by design |

Limit: prompts were answered through redirected input, not a double-clicked console. Task 6.2 covers that.

### Stage 2: Preflight screen — ✅ DONE

**Status: ✅ Done. Tasks 2.6 to 2.21 are complete.**

| ID | Task | Files | Done when |
|---|---|---|---|
| 2.6 | Preflight state in `<home>\preflight.json` and routes in the HTTP contract | `engine.py`, `server.py`, `SPEC.md` | State survives a restart; routes documented |
| 2.7 | Lock real steps until preflight passes; keep project resume | `engine.py` | Tests cover locked steps and a resumed project |
| 2.8 | Track choice, Script by default | `web/`, `content/preflight.json` | A promptfoo choice shows that steps follow the Script track for now |
| 2.9 | Python item through the running interpreter and the CLI's PATH | preflight code | Unit tests pass |
| 2.10 | Node item: reuse if at least 22.22.0, otherwise consented private install | preflight code | Tests around 22.22.0; hash mismatch deletes the file |
| 2.11 | promptfoo 0.125.1 predownload with consent and progress | preflight code | Prints 0.125.1 in the real-download test |
| 2.12 | CLI item and install recipes from data, shown and consented | `content/cli-recipes.json` | Exact command shown; fake commands in tests |
| 2.13 | Sign-in and license confirmation | `web/`, content | Item needs a participant confirmation |
| 2.14 | CLI working test, decided from `output.txt` and `version.txt` | preflight code | Pass, wrong content and missing version file tested |
| 2.15 | Project folder item: not in OneDrive, required files exist | preflight code | Unit tests pass |
| 2.16 | CLI and checker environment: PATH, npm and promptfoo variables only | `terminal.py`, `runner.py` | Test confirms no permission settings are added |
| 2.17 | Background work with progress, timeout and single-run guard | preflight code | Survives a page reload; cannot run twice |
| 2.18 | Disk check and failure messages | `content/preflight.json` | Each failure ends with an action |
| 2.19 | Integration: real `setup.cmd` launches the real `.pyz` | tests | `/api/state` answers and no browser opens |
| 2.20 | Stand-in end-to-end through preflight | `e2e-work/harness/` | All stages pass |
| 2.21 | Orchestrator verifies the agent's results independently | none | Backend rerun, totals read from saved results |

**Phase 2 exit (met):** every task above is done and `dist/eval-coach.pyz` is rebuilt.

Evidence: 343 backend tests with 2 skipped by design on Python 3.12 and embedded 3.13, 40 interface tests, the `setup.cmd` integration test, one real Node and promptfoo download, and a stand-in run of 123 checks with 0 failed and 0 violations.

Decisions made during the build:
- A new project inside OneDrive is refused. An existing one keeps its progress but fails the project item until it is moved.
- The CLI environment also reads PATH entries from the registry, read only, so a CLI installed during preflight is found without a restart.
- An optional `<home>\cli-recipes.json` replaces the bundled recipes, so they can change without a rebuild.

Limits:
- No real CLI or real install recipe ran. Tasks 6.5 to 6.8 cover that.
- Saved preflight results are trusted after a restart until "Check everything again" is pressed.
- The CLI item passes when the CLI launches, so a CLI that exits straight away is caught only by the working test.
- Disk minimums (Node 200 MB, promptfoo 1.2 GB, recipes 400 MB) are estimates.

---

## Phase 3: Course content — ✅ DONE (approved 2026-11-09)

**Status: ✅ Done. 43 of 44 tasks (3.1 to 3.44, plus 3.10a to 3.10c) are done. 3.28 is ➖ not applicable (D5) and 3.41 is ➖ not authorized (rule 13). No task is outstanding.**

Goal: turn the working steps into a complete course, using the /teach guidance: mission first, one skill and one tangible win, easy knowledge and hard practice, tight automatic feedback, and retrieval, spacing and interleaving.

Decision D1 approved Phase 3 on 2026-11-09. The spec is [PHASE3.md](PHASE3.md) (teaching and content rules) and the "Course and lessons" section of [SPEC.md](SPEC.md) (API and storage).

How to read the status column: **Done** means the "Done when" check was run and passed.

### 3A. Lesson engine — ✅ DONE (3.1 to 3.10c)

| ID | Task | Files | Depends on | Done when | Status |
|---|---|---|---|---|---|
| 3.1 | Define the lesson schema: mission, explanation, activities, source references | `docs/SPEC.md`, `content/lessons.json` | Phase 2 | Schema documented; invalid lessons fail a content test | Done |
| 3.2 | Load and validate lessons from the bundle | `resources.py`, new `lessons.py` | 3.1 | Works from disk and inside the zipapp | Done |
| 3.3 | Add lessons to the course order, before their matching steps | `state.py`, `engine.py` | 3.2 | A step stays locked until its lesson is complete | Done |
| 3.4 | Migrate existing progress into the new order | `state.py` | 3.3 | Old progress loads and keeps completed steps | Done |
| 3.5 | Lesson view | `web/js/views.js`, `web/js/panels.js` | 3.2 | Renders at normal and narrow widths | Done |
| 3.6 | Single-choice question with immediate feedback explaining each option | `web/`, `engine.py` | 3.5 | Interface test covers right and wrong answers | Done |
| 3.7 | Shuffle answer order per participant, and enforce equal answer length | `lessons.py`, content tests | 3.6 | Validation rejects any question whose options differ in word count; order is stable across reloads | Done |
| 3.8 | Practice activity: run a rule against sample text and see the verdict | `web/`, `engine.py` | 3.5 | Same input always gives the same verdict | Done |
| 3.9 | Written reflection activity, replacing practitioner wisdom | `web/`, `state.py` | 3.5 | Saved in progress and resumes | Done |
| 3.10 | Learning record only for demonstrated understanding | `state.py` | 3.6, 3.8 | Viewing a page creates no record; passing an activity does | Done |
| 3.10a | Ordering and sorting activities | `web/`, `engine.py` | 3.5 | Graded on the server; answers absent from responses until submitted | Done |
| 3.10b | CLI activities: three-run hook and anatomy demo, decided from files only | `engine.py`, `project.py`, `kit/lessons/` | 3.5 | Stand-in passes; outputs shown as plain text | Done |
| 3.10c | Read-only viewer for bundled source files | `server.py`, `web/` | 3.5 | Rejects path traversal | Done |

### 3B. Placement and review — ✅ DONE (3.11 to 3.14)

Placement (3.11) is no longer used: the bundled placement list is empty and its tests were removed in 3.45. The code stays until a later change replaces placement with separate tracks for advanced users and the regular course.

| ID | Task | Files | Depends on | Done when | Status |
|---|---|---|---|---|---|
| 3.11 | Placement questions that recommend where to start | `content/lessons.json`, `engine.py` | 3.6 | Strong answers can skip knowledge lessons, never practice steps | Done |
| 3.12 | Review scheduler at 1, 3 and 7 days | new `review.py` | 3.10 | Tests use a fake clock | Done |
| 3.13 | Review queue shown when the app reopens | `web/` | 3.12 | Due items appear; none are shown early | Done |
| 3.14 | Mix topics within a review session | `review.py` | 3.12 | Consecutive items come from different lessons when possible | Done |

The app sends no reminders, because it has no notification channel. Reviews appear when the participant reopens it. A sitting holds at most 5 items and is fixed once chosen, so any other due items wait for the next time the app opens.

### 3C. Lessons — ✅ DONE (3.15 to 3.25)

Every lesson draws from the session plan and names its source section. Each one needs a mission, a short explanation, at least one activity, and a retrieval question. The one exception is lesson 0 (the mission page), which is a plain introduction with no questions (3.45). In this table **Done** means the lesson's content is written, passes the schema and content tests, and its server behavior is tested; the interface check for display is 3.5, and the end-to-end run is 3.31.

**Superseded by 3.46.** The rows below record the original eleven-lesson build (lessons 0 to 10). Task 3.46 merged them into seven concept lessons in the order of the series method: `mission`, `hook`, `several-runs` (from the loop and generate lessons), `rules` (from the rules, build and choices lessons), `trust` (from the verify lesson), `surprise` (from the compare and fix lessons) and `baseline-why`. Ten mechanics-only activities were removed. The present lesson list is in `docs/PHASE3.md` and `docs/SPEC.md`.

| ID | Lesson | Content and activity | Source | Done when | Status |
|---|---|---|---|---|---|
| 3.15 | 0. Mission | Learning outcome: understand how Part 2 test cases, criteria and thresholds become reusable parts and how they fit into an evaluated AI process; the series table. No questions, no placement (3.45) | Series outcomes map, `docs/SERIES-INTENT.md` | Mission visible before any task | Done |
| 3.16 | 1. Hook | The CLI grades the Northwind polished fixture three times in blind folders; compare side by side | Block 0 | Three grades displayed, and reasons compared if the scores match | Done |
| 3.17 | 2. The loop and two actors | Order the steps "prompt, answer, file, checker, verdict"; sort tasks between generator and builder | The loop, Two actors | Ordering activity gives immediate feedback | Done |
| 3.18 | 3. Generate | Why blind runs, why five, why a mid-tier model | Block 1 | Question passed before the generate step | Done |
| 3.19 | 4. From threshold to rule | Same threshold in three notations; anatomy demo builds and runs a 2-criterion checker in a demo folder | Block 2, `presenter/demo-test-cases.md` | Same file gives the same verdict twice | Done |
| 3.20 | 5. Build and first look | What a skill is; reading NOT CHECKED; first look is not the baseline | How the checker is built | Practice classifies thresholds as checkable or not | Done |
| 3.21 | 6. Interpretation choices | Pick the choice hidden in a rule, such as whole word or part of a word | Handback section | Practice finds at least one choice | Done |
| 3.22 | 7. Fixtures, read back, predict | Why fixtures avoid the checker; polished but wrong; why you commit first | Steps 2 to 4 | Question passed before predict | Done |
| 3.23 | 8. Run and compare | Exit code 1 is normal; three kinds of surprise | Step 5 | Practice classifies three sample surprises | Done |
| 3.24 | 9. Fix the spec | Why the markdown changes rather than the checker | Step 6 | Practice picks the right fix for a scenario | Done |
| 3.25 | 10. Baseline and bridge | Pass rate across runs; what Part 4 does next | Step 7, Coverage | Reflection saved | Done |

### 3D. Reference and quality — ✅ DONE (3.26 to 3.31; 3.28 ➖ not applicable)

| ID | Task | Files | Depends on | Done when | Status |
|---|---|---|---|---|---|
| 3.26 | In-app glossary from the session glossary, without "today" and presenter wording | `content/glossary.json`, `web/` | 3.5 | Every term in the session glossary is present | Done |
| 3.27 | Printable one-page reference | `web/` print styles | 3.26 | Prints on one page from the browser | Done |
| 3.28 | One primary source and lesson citations (decision D5) | `content/lessons.json` | D5 | Every external claim links to a page that was opened and checked | Not applicable (D5: bundled files only) |
| 3.29 | Banned-word content test: presenter, facilitator, room, breakout, waterfall, handout, neighbor, clock, Copilot Chat | content tests | 3.25 | Test scans all content files | Done |
| 3.30 | Plain-language review with a non-technical reader in mind | content files | 3.25 | No unexplained term remains on any screen | Done |
| 3.31 | Stand-in end-to-end through the lessons | `e2e-work/harness/` | 3.25 | All stages pass | Done |

### 3E. Guided coaching refinement (2026-11-10) — ✅ DONE (3.32 to 3.35)

Source: the /teach guidance (aihero.dev/skills-teach) plus a check of the retrieval-practice research. On 2026-11-10 the user authorized the interface changes listed in 3.35 and decided that no quiz may block Continue. Interface changes outside 3.35 still need authorization (rule 13).

| ID | Task | Files | Done when | Status |
|---|---|---|---|---|
| 3.32 | Every lesson opens with a recap (`Where you are.`) and a plain explanation (`What this part is.`); 3.46 replaced this with `In the method.` and `The idea.` | `content/lessons.json` | Content test checks every lesson | Done |
| 3.33 | No question blocks Continue; only the demo and the saved output of a CLI exercise do | `engine.py`, `SPEC.md`, `PHASE3.md` | Engine, HTTP and interface tests pass | Done |
| 3.34 | A short check after each CLI exercise (`rules-anatomy`, the question inside each `cli_*` activity, `choices-find`) | `content/lessons.json` | Content tests pass; options match in word count | Done |
| 3.35 | Step pages: a "Quick check" question under the gate result once a step is done, for all nine steps (`step_checks`, `POST /api/step/question`); the lesson progress text now reads "Done so far: x of y", and the Continue hint says only exercises hold it back | `lessons.py`, `engine.py`, `server.py`, `web/js/lessons.js`, `views.js`, `app.js`, `content/lesson-ui.json`, `content/lessons.json` | Backend, interface and smoke tests pass | Done |

The last step, `baseline`, has its own question, so the course ends with a check. Unanswered questions are not added to the review queue; the lesson's `retrieval` items still are. Reflections no longer block, because they are not exercises.

Notes on 3.26 and 3.27: the glossary has every session-glossary term plus CLI, agent, markdown and proxy; the in-app panel is reachable from every screen, and the reference page prints on one page in Letter and A4. 3.28 waits for decision D5; until then every lesson cites only bundled `kit:` files, which a content test enforces. 3.29 also records the SHA-256 of the bundled skills and Northwind files, so any change to them fails a test.

**Phase 3 exit (met; 3.28 not applicable under D5):** a participant can go from mission to the end of the course with only the app, and all checks pass.

Evidence (2026-11-09): 668 backend tests with 2 skipped by design on Python 3.12 and embedded 3.13, 62 interface tests, a rebuilt `dist/eval-coach.pyz` that passes the smoke test, and a fresh stand-in run of 1017 checks with 0 failed, 0 violations and 18 CLI sessions (stand-in budget raised from 13 to 18). The review queue was tested against a mock and a fake clock, not by waiting days. No real CLI ran, so the lessons' CLI activities and the new typed lines still need Phase 6.

Evidence so far: backend tests in `test_lessons.py`, `test_course.py`, `test_review.py`, `test_http_course.py` and `test_content_banned_words.py` (see the test count under Verification).

Decisions made during the build:
- A review sitting holds at most 5 items and is fixed until it is answered. Anything else that is due waits for the next time the app opens.
- Course progress made before a project exists (the mission) is kept in `<home>\pending-lessons.json` and merged into the project's progress when it is set up.
- Lessons before the furthest completed step in older progress are recorded as skipped, so they do not block and schedule no reviews.
- The glossary adds four words the lessons rely on and the session glossary lacks: CLI, agent, markdown, proxy.

Limits:
- The `baseline-why` lesson (originally lesson 10) teaches the baseline and the iteration log. Phase 4 added the `baseline` step that records one, and the lesson now comes before it.
- The hook lesson depends on the participant's own CLI giving three gradings; its comparison question holds whatever the three results show.

### 3F. Learning-priority alignment (added 2026-11-10; Phase 3 content, in scope of D1) — 🔄 RUNNING (3.46; 3.36 to 3.45 ✅ done, 3.41 ➖ not authorized)

Goal: close the gaps in "Coverage today" in tier order. Tasks 3.36 to 3.38 use activity types that already exist and edit only `content/lessons.json`, `content/glossary.json` and tests, so they change no layout, component or element id (rule 13). Anything that needs a new screen or new interface copy is listed as 3.41 and waits for the user's explicit authorization.

| ID | Tier | Task | Files | Depends on | Done when | Status |
|---|---|---|---|---|---|---|
| 3.36 | 1 | "Say it in plain words": one activity in each of three lessons (the hook, build and first look, and baseline), where the participant picks the best explanation for a non-technical reader and, in the baseline lesson, writes one. The three topics are why a rule beats an AI grader, what NOT CHECKED means, and what a baseline pass rate tells you. Wrong options sound plausible and match in word count. Include one technical-audience item, such as the whole-word choice, in lesson 6 | `content/lessons.json`, content tests | 3.25 | Content tests pass; options match in word count; the reflection saves and resumes; no new Continue block | Done |
| 3.37 | 1 | State the boundary of what a rule can check: a short passage in lesson 5 and a glossary entry saying that judgment criteria stay NOT CHECKED here, and that a person or a later session covers them. Describe the concept only; the app still rejects `llm-rubric` (4.14) and makes no AI calls (rule 3) | `content/lessons.json`, `content/glossary.json` | 3.25 | Every glossary term still present; content tests pass | Done |
| 3.38 | 2 | Place the evaluation in the series workflow in lesson 0, covering the six pieces of work in the series, from the series outcomes map (D6 source). It was an ordering activity (`mission-series`); 3.45 removed the activity and the series table now carries it. A wider team workflow has no source and is out of scope (D5) | `content/lessons.json` | 3.25 | Cites bundled `kit:` files only | Done |
| 3.39 | 3 | Stage 3 note at the end of the last lesson (lesson 10 when built; `baseline-why` now): a short, plain passage and one optional reflection that names the Stage 3 criteria (3.46 reworked this to the three artifacts, Prompt, Evaluations and Log), shows which files the participant now holds, and says what comes next. It says the program's own instructions decide what to submit. It must not block Continue, and must not mention a presenter, room, handout or clock | `content/lessons.json`, content tests | D6, 3.36 | A content test checks that the note names the criteria (now the three artifacts) and gives no submission steps | Done (D6 approved) |
| 3.40 | 3 | `tests/test_learning_priorities.py` reads this plan's Stage 3 map and fails if the last lesson stops naming the Stage 3 items (now Prompt, Evaluations and Log), or if any Stage 3 wording appears outside that lesson | `tests/test_learning_priorities.py` | 3.39 | Test passes and fails correctly on a changed lesson | Done (D6 approved) |
| 3.41 | 3 | Optional: an "evidence you hold" panel listing `test-cases.md`, the baseline numbers and the iteration log. Needs a new interface element | `web/`, `lesson-ui.json` | D6, user authorization | Interface test passes | Not authorized (user answered "No, not now" on 2026-11-10; rule 13) |
| 3.42 | all | Re-run the checks after 3.36 to 3.40: backend suites on 3.12 and embedded 3.13, interface tests, build and smoke test, and the stand-in end-to-end through the lessons | `e2e-work/harness/` | 3.36 to 3.40, 3.43 | All pass; plan and `SPEC.md` updated where behavior changed | Done: backend 1052 tests (2 skipped by design) on 3.12 and embedded 3.13, 103 interface tests, the build smoke test, and the stand-in run on both tracks (Script 1268 checks over 24 CLI sessions, promptfoo 1323 over 26; 0 failed, 0 violations) |
| 3.43 | 2 | Correct the series wording: the mission lesson said "four-part series" and listed four sessions; the series outcomes map has six (4 iterate, 5 trim and package, 6 your own task). The baseline lesson now also says what Part 5 does | `content/lessons.json`, content tests | 3.38 | Content test rejects "four-part"; all six sessions are in the mission table | Done |
| 3.44 | all | Bring the stand-in harness up to date. It predates the 2026-11-10 refinement (3.33 to 3.35): it still expected questions to hold Continue back, and it has no driver for the `cli_practice` activity used by `generate-why`, `build-why`, `verify` and `fix-why`. Already fixed: the mission and hook expectations, `expectIncomplete`, a `runPractice` driver (the generic stand-in output branch already answers the four practice lines), and the session budget (22 to 26). The step-page "Quick check" is covered by the interface tests and is not driven by the harness | `e2e-work/harness/` | 3.42 | `run-all.js --fresh` passes every stage on both tracks | Done |
| 3.45 | 0 | Make lesson 0 a one-page, plain-language introduction. The mission states the learning outcome, not the files produced: "Understand how to turn the test cases, criteria and thresholds from Part 2 into reusable parts, and how those parts fit into an evaluated AI process." All lesson 0 questions (3 activities, 2 review items) and the placement questions are removed; the validator lets only `mission` have no activities or retrieval; placement tests are removed (placement is to be replaced by separate tracks); `dist/eval-coach.pyz` rebuilt | `content/lessons.json`, `lessons.py`, `web/js/lessons.js`, tests, `docs/PHASE3.md`, `e2e-work/harness/` | 3.15, 3.38 | Python suite passes (1039 tests, 2 skipped by design); the mission text is asserted in `tests/test_lessons.py` | Done |
| 3.46 | all | Align the series content and interface with `docs/SERIES-INTENT.md` and `docs/STAGE3-TASK-SPEC.md` (OpenSpec change `align-series-content-with-intent`, authorized 2026-11-14; audit in "Learning priorities"). Restructure the 11 lessons into 7 concept lessons in the order of the method (`mission`, `hook`, `several-runs`, `rules`, `trust`, `surprise`, `baseline-why`) and remove 10 mechanics-only activities; move the procedure into the step text; state the series purpose, why it matters, the limits of a score and the own-work bridge; rewrite the Stage 3 note around the Prompt, Evaluations and Log; replace "Session N" with "Part N" and guard it with a test; accept old saved progress; group the course list under headings, use "lessons and steps" wording, read the Part strings from content, rewrite the reference card (method first) and split the glossary into Ideas and In this course (`kind`), reword step titles and the finished screen; add one Part 6 note to `baseline-why` "Your own work" (Part 6 is a live meeting; ideas can be brought to office hours or the AIR discussion; the only exception to rule 10's "contact someone" ban, authorized 2026-11-15; the work task is recommended, not required, said in `SERIES-INTENT.md` and `COURSE-CONTEXT.md` only; `baseline-why` kept at 400 words or fewer); update the docs and rebuild `dist/eval-coach.pyz` | `content/*.json`, `state.py`, `lessons.py`, `web/` (authorized items only), `kit/northwind/` comment lines, tests, `e2e-work/harness/`, `docs/`, `AGENTS.md` | 3.45 | Backend suites (system Python and embedded 3.13), interface tests, build smoke test and the stand-in end-to-end on both tracks pass; every audit finding maps to a changed line or a "checked, no change" entry | Running |

Order inside 3F: 3.36, 3.37, 3.38 and 3.43, then 3.39 and 3.40, then 3.42, then 3.44. Tiers 1 and 2 are complete without 3.39. Task 3.46 comes last and supersedes the lesson numbers and the "three criteria" wording used in the rows above (3.15 to 3.45 describe the original eleven-lesson build and its three-criteria Stage 3 note, which 3.46 replaced with the seven-lesson course and the Prompt, Evaluations and Log structure; rows that say "lesson 10" now mean `baseline-why`, "lesson 5" and "lesson 6" now mean `rules`, and the activities `rules-anatomy` and the other removed ids no longer exist).

---

## Phase 4: Baseline, promptfoo track and import — ✅ DONE on the stand-in (approved 2026-11-09)

**Status: ✅ Done. All 28 tasks (4.1 to 4.28) are complete; 4A (4.1 to 4.7), 4B (4.8 to 4.18), 4C (4.19 to 4.25) and 4D (4.26 to 4.28) are each done. Real-CLI confirmation is pending in Phase 6.**

Tasks 4.1 to 4.28 are done. 4.18 is built under decision D2 (2026-11-09: build it now, with a warning about auto mode): an optional promptfoo-track side step `live` after the baseline. It is outside `STEP_IDS`, `COURSE` and `progress.done`, so it never gates the course. The app only types the Room B step 8 line into the participant's own CLI. It never runs `agent-provider.js` or promptfoo live, and a required acknowledgement states that the helper turns on Devin's auto mode. A content test cross-checks that warning against `agent-provider.js`. The "Done when" checks were run and passed. Where the build differs from the tables below:
- 4.4 and 4.11 to 4.12: the track-agnostic runner lives in new `baseline.py` and `promptfoo.py`, not `runner.py`. The promptfoo eval runs with `npm_config_offline=true`, the update, sharing and telemetry switches off, and a dead local proxy, because npx and promptfoo otherwise contact the network at run time (rule 5).
- 4.10: the new promptfoo-only step is `fixtures-config`. The track is stored in `progress.json` and fixed once any step is done.
- 4.19 to 4.24: new `import_checks.py` and `content/import-checks.json`. Blocking: fewer than 3 criteria, no content criterion, unreadable or empty files, a different file already in the project. Warnings: untraced criteria, vague words, missing threshold, non-UTF-8, existing progress.
- 4.28: `POST /api/step/use-example-fixtures` writes only the two Northwind fixtures, never a key, and needs `"replace": true` to overwrite text.

### 4A. Baseline step (both tracks need this; it is a core session outcome) — ✅ DONE (4.1 to 4.7)

| ID | Task | Files | Depends on | Done when |
|---|---|---|---|---|
| 4.1 | Add `baseline` after `fix` | `state.py`, `engine.py` | Phase 3 | Locked until fix is done or skipped |
| 4.2 | Script-track typed line: `Read skills/build-eval-script/SKILL.md and follow it in run + log mode. The runs are runs/run-1.txt to runs/run-5.txt. The prompt file is prompt-v0.md. The model was <model>.` | `content/steps.json`, `engine.py` | 4.1 | Model name is forced to a single line before typing |
| 4.3 | Iteration log parser | `parsers.py`, `tests/golden/` | 4.1 | Golden tests cover the skill's format |
| 4.4 | App runs the checker independently on all five runs | `runner.py`, `engine.py` | 4.1 | Results stored per criterion |
| 4.5 | Gate: log totals match the app's own run, and NOT CHECKED is listed | `gates.py` | 4.3, 4.4 | Fails on any mismatch and names the criterion |
| 4.6 | Baseline view: pass rate per criterion | `web/` | 4.4 | Interface test passes |
| 4.7 | Content for the step, including the bridge to Part 4 | `content/steps.json` | 4.1 | Content tests pass |

### 4B. promptfoo track — ✅ DONE (4.8 to 4.18)

Steps match the Script track. Lines come from the Session 3 Room B material, rewritten as one line each.

| ID | Task | Files | Depends on | Done when |
|---|---|---|---|---|
| 4.8 | Track-specific lines and content | `content/steps.json` | 2.8 | Each step has text for both tracks |
| 4.9 | Build line naming `run-1` to `run-5` as tests | `content/steps.json` | 4.8 | Content test checks the exact line |
| 4.10 | New typed step after fixtures: add both fixtures to the config as tests | `engine.py`, content | 4.8 | Gate reads the config and finds both test names |
| 4.11 | App runs `npx --yes promptfoo@0.125.1 eval -c promptfooconfig.yaml --no-cache --no-table --no-write -o results.json` | `runner.py` | 2.16 | Non-zero exit from failed checks is treated as normal |
| 4.12 | App runs `summarize_results.py` as a separate command | `runner.py` | 4.11 | Run fails clearly if `results.json` is missing |
| 4.13 | Parser for the summary output | `parsers.py`, `tests/golden/` | 4.12 | Same result shape as the Script track |
| 4.14 | Config scan: reject `llm-rubric` and any provider other than `echo` | `scan.py` | 4.8 | Plain message names the problem |
| 4.15 | Gates for build, run, fix and baseline on the config | `gates.py` | 4.11 to 4.14 | Each gate tested on both tracks |
| 4.16 | Explain "every test shows failed while anything is NOT CHECKED" | content | 4.8 | Present in run and troubleshooting text |
| 4.17 | Stand-in end-to-end on the promptfoo track | `e2e-work/harness/` | 4.15 | All stages pass, with real promptfoo on stand-in files |
| 4.18 | Live mode: apply decision D2 | depends on D2 | D2 | Excluded from the app, or built under that decision |

### 4C. Importing the participant's own work — ✅ DONE (4.19 to 4.25)

| ID | Task | Files | Depends on | Done when |
|---|---|---|---|---|
| 4.19 | Import screen for prompt and test cases | `web/`, `engine.py` | 2.15 | Source files are copied and never changed |
| 4.20 | Rename guidance for `prompt-v0.md` and `test-cases.md` | content | 4.19 | Files have the expected names after import |
| 4.21 | Check: three or more criteria | `parsers.py`, new `import_checks.py` | 4.19 | Failure tells the participant what to add |
| 4.22 | Check: at least one content criterion | `import_checks.py` | 4.21 | Tested on good and bad files |
| 4.23 | Check: criteria trace to requirements | `import_checks.py` | 4.21 | Tested on good and bad files |
| 4.24 | Check: flag vague words in thresholds | `import_checks.py` | 4.21 | A flag is a warning that leads to NOT CHECKED guidance |
| 4.25 | Offer Northwind only as a learning starter | content, `web/` | 4.19 | Screen says it cannot be a submission |

### 4D. Troubleshooting — ✅ DONE (4.26 to 4.28)

| ID | Task | Files | Depends on | Done when |
|---|---|---|---|---|
| 4.26 | Move the Room A and B "If something breaks" items into the matching steps | content | 4.8 | Every item is placed or recorded as not applicable |
| 4.27 | Windows line-ending guidance for label checks | content | 4.26 | Present where label checks fail |
| 4.28 | Northwind fixtures as a recovery path when generated fixtures are unusable | `project.py`, content | 4.26 | Works only with the Northwind starter |

**Phase 4 exit (met on the stand-in):** both tracks reach a verified Iteration 0 entry.

Evidence (2026-11-09): 1001 backend tests with 2 skipped by design on Python 3.12 and embedded 3.13, 93 interface tests, a rebuilt `dist/eval-coach.pyz` that passes the smoke test, `classifier-check.js` all ok, and a stand-in run of both tracks (Script 1093 checks over 20 CLI sessions, promptfoo 1128 checks over 22; 0 failed and 0 violations on both) with the stand-in session budget at 22. The promptfoo track ran real promptfoo 0.125.1 offline on stand-in files.

Limits:
- No real CLI ran. The new typed lines (baseline, `fixtures-config`, live mode, promptfoo build, readback and fix) still need Phase 6, and the live-mode warning is verified against the helper's source only.
- The lessons are shared by both tracks, so the `rules` lesson demo still builds a Python `check.py` for promptfoo-track participants.
- The dead-proxy and offline settings depend on how promptfoo 0.125.1 behaves; recheck them whenever the pin changes.

---

## Phase S: Settings and global setup — ✅ DONE on the stand-in (OpenSpec change `add-settings-section`)

The first change run through the OpenSpec pilot. The change was archived on 2026-11-14 to `openspec/changes/archive/2026-11-14-add-settings-section/` (proposal, six delta specs, design, tasks); its six specs now live in `openspec/specs/` and win over `docs/SPEC.md` for their areas. The interface changes were authorized by the user for this change only (Settings, removing the setup course-list entry, and the layout work for text size). A later amendment, also authorized by the user, made setup a full-page wizard (S.6).

| ID | Task | Files | Done when |
|---|---|---|---|
| S.1 | Resets: inventory, the shared move-with-rollback routine, `POST /api/reset/progress` and `/api/reset/configuration`, one backup folder `<home>\reset-backup\` | `reset.py`, `engine.py`, `server.py`, `content/settings.json` | `tests/test_reset.py` covers both resets, the backup, the answer key, rollback and the first-run state |
| S.2 | Setup is a skippable global first-run screen, not a course item; hands-on work needs setup; locked lessons and steps open as read-only previews (before setup; extended to after setup by Phase R); reminder banner | `preflight.py`, `engine.py`, `web/js/*`, `content/*` | `tests/test_setup_gate.py` and the interface tests for first run, skip, gating, previews and the banner |
| S.3 | Text size slider with phone-aware range, `data-layout` breakpoints that follow the size, terminal font scaling | `web/js/theme.js`, `web/js/chrome.js`, `web/js/terminal.js`, `web/styles.css` | Interface tests at 80 to 150 on 1280px and 90 to 130 on a 390px phone find no sideways scroll or covered controls; a screenshot comparison at 100% shows only the sidebar changes |
| S.4 | Settings panel: text size, setup (a status summary and an "Open setup" button), both resets with confirmation | `web/js/settings.js`, `web/js/views.js`, `content/settings.json` | Interface tests for position before Quit, group order, cancel and confirm for both resets |
| S.5 | Integration and docs | `docs/SPEC.md`, `docs/DESIGN.md`, `docs/PHASE2.md`, `AGENTS.md` | The verification commands below pass |
| S.6 | Amendment: setup is a full-page wizard (no sidebar beside it), one check per page with progress, Back and Next (Next waits for the check), "Skip for now" on first run or a close action when opened from Settings or the banner, terminal inside the CLI pages | `web/js/preflight.js`, `web/js/app.js`, `web/js/settings.js`, `web/styles.css`, `content/preflight.json`, `content/settings.json`, `tests/frontend/ui.spec.js`, `e2e-work/harness/run.js` | Interface tests for the wizard on desktop and phone, `tests.test_content_and_resources`, the stand-in harness on both tracks |

Evidence (2026-11-11): 1094 backend tests on Python 3.12 and embedded 3.13 (2 skipped by design); the only failures are six `test_setup_cmd` tests (they run `setup.cmd`, which this change does not touch, and it could not find or install Python in the test profile on this machine) and `test_conpty.RealConsole.test_type_line_sends_enter_separately`, which is timing-sensitive and passed on rerun. 132 interface tests, a rebuilt `dist/eval-coach.pyz` that passes the smoke test, and a stand-in run of both tracks (Script 1243 checks over 24 CLI sessions, promptfoo 1293 over 26; 0 failed and 0 violations on both).

Limits:
- Checked in Edge with touch emulation only; no real phone was used.
- The printable reference page has no setup banner, because it is a separate static page that does not talk to the server.
- Lesson bodies still say "Your setup is ready" or "Setup is done"; a preview of such a lesson before setup shows a note that setup is not finished.

---

## Phase R: Read ahead always — ✅ DONE on the stand-in (OpenSpec change `read-ahead-always`)

Locked lessons and steps open as read-only previews at any time, in every Part, not only before setup. Locking still governs doing and recording. The interface changes (locked items as buttons in the course list, step list, glossary and related lessons; a second preview-note wording and its button) were authorized by the user in the change's proposal. The change was archived on 2026-11-16 to `openspec/changes/archive/2026-11-16-read-ahead-always/`; its specs (`setup-access`, `part-registry`, `series-map`) are synced into `openspec/specs/` and win over `docs/SPEC.md` for their areas.

| ID | Task | Files | Done when |
|---|---|---|---|
| R.1 | A locked lesson or step returns a preview whatever the setup state; a locked step never runs `_detail`; previews carry `held_by` and read no participant file | `engine.py`, `tests/test_course.py`, `tests/test_http_course.py`, `tests/test_part_1_steps.py` | The backend tests for previews after setup, `held_by`, unchanged `progress.json` and refused write routes pass |
| R.2 | Second preview wording and the back button text | `content/settings.json`, `tests/test_content_and_resources.py` | The content tests pass |
| R.3 | Locked entries are buttons; glossary and related-lesson links to locked lessons; the preview note and `#preview-back` | `web/js/lessons.js`, `web/js/views.js`, `web/js/app.js`, `tests/frontend/*` | The whole interface suite passes |
| R.4 | Docs and final checks | `docs/SPEC.md`, `docs/IMPLEMENTATION-PLAN.md` | Both backend suites, the build smoke test and the stand-in run pass |

---

## Phase M: Series map — ✅ DONE on the stand-in (OpenSpec change `add-series-map`)

The app opens on a Series map of all six Parts instead of on the Part 3 course. The interface change and the Part 6 wording exception were authorized by the user on 2026-11-15 (see the change's proposal). Its specs (`series-map`, and changes to `setup-access`, `settings-page` and `series-intent-framing`) are in `openspec/specs/` (change archived 2026-11-15) and win over `docs/SPEC.md` for their areas.

| ID | Task | Files | Done when |
|---|---|---|---|
| M.1 | `content/series.json` (six Parts, kinds `course`, `soon`, `live`, and the map's words) and `series` in `get_state` (Part 3's state, count and lesson list built from the course list; `None` without a course) | `content/series.json`, `engine.py`, `tests/test_series.py` | `tests/test_series.py`: shape, progress rules, count equals the sidebar's, names and outcomes equal the mission map, Part 6 has no pointers to people, the live note stays in `baseline-why` |
| M.2 | Series map view: `app.screen` starts on `'series'`; Part rows with separate expand and open controls; text-only "Coming soon" and "Live meeting" rows | `web/js/series.js`, `web/js/app.js`, `web/styles.css` | Interface tests for rows, states, expand and collapse by mouse and keyboard, Start, Continue and Review |
| M.3 | "Back to series map" control; the sidebar tools on the map; Settings and the setup wizard return to where they were opened from; skip, finish and configuration reset land on the map | `web/js/views.js`, `web/js/app.js`, `content/lesson-ui.json` | Interface tests for the return paths, the collapsed sidebar, the banner on the map and the narrow-layout control |
| M.4 | The mock API returns `series`; the interface tests and the stand-in harness enter Part 3 from the map | `tests/frontend/mock_api.py`, `tests/frontend/ui.spec.js`, `e2e-work/harness/lib.js`, `run.js`, `lesson-stages.js` | Whole interface suite and the stand-in harness on both tracks pass |
| M.5 | Docs and governing text: rule 10 exception, `SPEC.md` Series map section, `COURSE-CONTEXT.md` coverage column, `AGENTS.md` Status | `AGENTS.md`, `docs/*.md`, `openspec/config.yaml` | Read against the change's specs |

---

## Phase G: Generalize Parts — ✅ DONE on the stand-in (OpenSpec change `generalize-parts`)

The engine, the saved progress and the content loader now hold more than one Part's course, so Part 1 (change `add-part-1`) and later Parts can be added by content and a registry entry. No participant-visible change: no interface change, no new route, no content change, and Part 3's order, steps, gates, files and saved keys are unchanged. Its spec (`part-registry`) wins over `docs/SPEC.md` for its area; the contract is in `docs/SPEC.md` "Parts".

| ID | Task | Files | Done when |
|---|---|---|---|
| G.1 | `Part`, `PARTS`, `part_by_id`, `part_of`, `all_lesson_ids`, `all_step_ids`, `duplicate_ids`, `register_part` and `register_step_kind` in `state.py` (Part 3's lists kept as aliases); `parts` in `new_progress`, `new_part_progress`, per-Part validation, pruning and migration | `state.py`, `tests/test_parts.py` | Part 3's lists equal the earlier ones; old progress loads byte-identical; a wrong-shaped block raises the corrupt-progress message; the full backend suite has the same outcome as before |
| G.2 | `validate_course` and `load_bundled` take a Part; `load_step_content` merges every Part's steps and `ui`; a shared id or an unknown step `kind` stops the start; the content tests read every registered Part | `lessons.py`, `engine.py`, `__main__.py`, `tests/test_parts.py`, `tests/test_lessons.py`, `tests/course_helpers.py` | A duplicate id, an out-of-list lesson and an unknown kind are reported with a synthetic Part; Part 3's merged step text equals `steps.json` |
| G.3 | `_part_of`, `_progress_of`, per-Part `_walk`, `_status`, `_lesson_status`, `_mark_done`, `_step`; the step `kind` hook; `part` on `get_state` and `GET /api/state`; `series` for every registered Part | `engine.py`, `server.py`, `content/steps.json` (`unknown_part`), `tests/test_parts.py`, `tests/test_http_course.py` | A synthetic Part's first lesson opens before setup, its step only after its lesson, Part 3 never moves; no selector gives Part 3's state as before; an unknown selector is refused |
| G.4 | Review across Parts, pending progress, both resets, and the cross-check that the Series map and the registry name the same Parts | `tests/test_parts.py`, `tests/test_series.py` | All pass |
| G.5 | `docs/SPEC.md` (layout, storage, state shape, "Parts"), this plan, and the final integration check | `docs/` | The backend suites on both interpreters, the interface suite, `python tools\build_pyz.py --smoke`, the stand-in harness and `openspec validate generalize-parts --strict` pass |

---

## Phase P1: Part 1, structured prompting — ✅ BUILT on the stand-in (OpenSpec change `add-part-1`)

Part 1 is the first Part after Part 3 to get content. The participant writes a prompt in their own words and runs it once, scores the answer against five things they knew but never said, sorts the gaps into five common kinds of missing information (an example, not a complete list), learns that frameworks are ready-made labels for those kinds, rewrites the prompt with a set of labels in a new chat, scores again and compares, and rewrites one real prompt of their own. The four-lesson, five-step course is in `docs/SPEC.md` "Part 1"; its specs (`part-1-course`, `part-1-exercise-steps` and changes to `series-map`, `course-structure`, `learning-priority-order`, `part-terminology`, `progress-reset` and `configuration-reset`) win over this plan for their areas. The interface change (U1 to U5) was authorized by the user on 2026-11-15; no other interface or Part 3 screen changed. Verified on the stand-in only: the real-CLI budget (15 of 17 sessions used) is unchanged, and a real pass needs two real sessions (the cold run and the rewrite run) and the user's approval, in Phase 6. The change was archived on 2026-11-16 to `openspec/changes/archive/2026-11-16-add-part-1/`.

| ID | Task | Files | Done when |
|---|---|---|---|
| P1.1 | `kit/part1/` | `rough-notes.txt`, `typical-gaps.md`, `frameworks-map.md`, `sample-rtcc.md`, `sample-rise.md` | `tests/test_part_1_content.py`: the notes equal Northwind's, no meeting-tool wording, every file cited |
| P1.2 | Part 1 content | `content/part-1-lessons.json`, `part-1-steps.json`, `glossary.json`, `series.json` | The loader starts; word caps, equal option lengths, kit-only sources; names and outcomes equal both mission maps |
| P1.3 | Content tests | `tests/test_part_1_content.py`, `test_content_banned_words.py`, `test_part_terminology.py`, `test_learning_priorities.py`, `test_series.py` | No framework name before the reveal; the samples cited only by `p1-benefits`; the Stage 3 note names the Prompt |
| P1.4 | Registry entry and step kinds | `state.py`, `part_steps.py`, `engine.py`, `project.py` | `tests/test_part_1_steps.py`: order, locking, gates, one-shot runs, files, setup gating |
| P1.5 | Resets and the `part` field | `reset.py`, `server.py`, `tests/test_reset.py` | Outputs and `part1\` moved by both resets; prompts and own work kept by Reset lesson progress; a POST returns the Part the page is in |
| P1.6 | Interface (U1 to U5) | `web/js/app.js`, `api.js`, `panels.js`, `part-steps.js`, `reference.js`, `web/styles.css` | Interface tests; screenshots at 1280, 900 and 390 pixels, both themes and the largest text size, viewed |
| P1.7 | Interface tests | `tests/frontend/part1.spec.js`, `real_server.py`, `mock_api.py`, `ui.spec.js`, `playwright.config.js` | The whole interface suite passes |
| P1.8 | Stand-in harness | `e2e-work/harness/fake_cli.py`, `lesson-stages.js`, `run-all.js`, `lib.js` | `run-all.js --fresh` and `--both`: 0 failed checks, 0 violations; `classifier-check.js` |
| P1.9 | Docs and integration | `docs/*.md`, `AGENTS.md` | Both backend suites, the interface suite, `python tools\build_pyz.py --smoke`, the harness, `openspec validate add-part-1 --strict` |

---

## Phase P2: Part 2, defining evaluation criteria — 🔄 BUILT on the stand-in (OpenSpec change `add-part-2`; final integration check P2.9 pending)

Part 2 is the bridge between the prompt written in Part 1 and the checker built in Part 3. The participant turns five requirements into at least three distinct criteria (each traced to a requirement, together covering format and content), gives each a threshold a script could decide, builds a `test-cases.md` from the worksheet in the layout Part 3 reads and passes the file checks, and then compares their file with the Northwind reference criteria. Nothing is run: no CLI, checker or model, no network, and no real-CLI budget. The four-lesson, four-step course is in `docs/SPEC.md` "Part 2"; its specs (`part-2-course`, `part-2-exercise-steps` and changes to `series-map`, `course-structure`, `learning-priority-order`, `part-terminology`, `progress-reset` and `configuration-reset`) win over this plan for their areas. The interface change (U6 to U8) was authorized in the change's proposal; no other interface or Part 1 or Part 3 screen changed. The Northwind reference is shown only in the `reference` step, after `test-file` is done: this is a discovery order inside Part 2, not a seal, because the Northwind kit file is Part 3's and is not gated. The Part 2 wording (lessons, steps, findings, reference options and the finished screen) is for the user to review before the change is archived.

| ID | Task | Files | Done when |
|---|---|---|---|
| P2.1 | `kit/part2/` | `worked-examples.md`, `test-case-template.md` | `tests/test_part_2_content.py`: both files are readable through the kit viewer, hold no meeting-tool, room or facilitator wording, the examples model only the length and blocker criteria, and every file is cited |
| P2.2 | Part 2 content | `content/part-2-lessons.json`, `part-2-steps.json`, `glossary.json`, `series.json` | The loader starts; word caps, equal option lengths, kit-only sources; names and outcomes equal all three mission maps |
| P2.3 | Content tests | `tests/test_part_2_content.py`, `test_content_banned_words.py`, `test_part_terminology.py`, `test_learning_priorities.py`, `test_series.py` | No reference criterion beyond the two worked examples, no reference threshold and no Northwind list word before the reveal; the Stage 3 note names the Evaluations and appears nowhere else in Part 2 |
| P2.4 | Registry entry and step kinds | `state.py`, `criteria_steps.py`, `engine.py` | `tests/test_part_2_steps.py`: order, locking, every gate and finding, the vague-word notes, files, `confirm_replace` and `no_worksheet`, the reveal over the HTTP routes, the optional read of Part 1, setup gating, previews, no CLI started |
| P2.5 | Resets and project files | `project.py`, `reset.py`, `tests/test_reset.py` | Both files kept by Reset lesson progress and moved by Reset app configuration; an unrelated file in `part-2\` untouched; the inventory test fails on any unlisted file |
| P2.6 | Interface (U6 to U8) | `web/js/criteria-steps.js`, `part-steps.js`, `panels.js`, `app.js`, `web/styles.css` | Interface tests; screenshots at 1280, 900 and 390 pixels, both themes and the largest text size, viewed |
| P2.7 | Interface tests | `tests/frontend/part2.spec.js`, `mock_api.py`, `mock_course.py`, `ui.spec.js` | The whole interface suite passes, `part1.spec.js` unchanged |
| P2.8 | Stand-in harness | `e2e-work/harness/lesson-stages.js`, `run-all.js`, `README.md` | `run-all.js --fresh` and `--both`: 0 failed checks, 0 violations; `classifier-check.js` |
| P2.9 | Docs and integration | `docs/*.md`, `AGENTS.md`, `openspec/changes/add-part-2/` | Both backend suites (one after the other), the interface suite, `python tools\build_pyz.py --smoke`, the harness on both tracks, `openspec validate add-part-2 --strict`; no real-CLI session used (15 of 17 remain). **Pending verification.** |

---

## Phase C: Content clarity — ✅ DONE on the stand-in (OpenSpec change `content-clarity`)

The words participants read were made plain: one mission shape for Parts 1 to 3 (no map of the Parts; the series framing only in `p1-mission`), "your AI" and "AI window" instead of "CLI" (vendor names stay), "Practice task" and "My own task" instead of "Northwind", "categories" for the five groups of what a prompt needs, a framework section with one table per framework, track descriptions by technical level and a Series map intro about doing each Part yourself. The change's specs (`mission-lesson-shape`, `participant-vocabulary` and changes to `part-1-course`, `part-2-course`, `series-intent-framing`, `series-map`, `setup-access`) win over this plan for their areas. Interface copy edits (`web/` strings, `lesson-ui.json`, `preflight.json`, `settings.json`, `series.json`) were authorized in the change's proposal; no layout, style, component or id changed. `tests/test_participant_vocabulary.py` keeps the words from drifting back. Participant-visible messages built in Python (`engine.py`, `gates.py`, `scan.py`, `baseline.py`, `promptfoo.py`, `part_steps.py`, `conpty.py`, `terminal.py`) were reworded the same way. Findings: the Track page preselects the Script track (see C.6), and the `p1-frameworks` word cap is 420. No real CLI was used.

---

## Phase 5: Package — ⏳ TO DO (needs go-ahead, D1)

**Status: ⏳ To do. None of the 8 tasks (5.1 to 5.8) is started.**

| ID | Task | Files | Depends on | Done when |
|---|---|---|---|---|
| 5.1 | Build `eval-coach.zip` with `setup.cmd` and `eval-coach.pyz` | `tools/build_pyz.py` | Phase 4 | Zip holds exactly the two files |
| 5.2 | Version number shown in the app and stored in progress | `__main__.py`, `state.py` | 5.1 | Visible in the interface |
| 5.3 | Test the zip after a download mark (Mark of the Web) | tests | 5.1 | Behavior recorded for File Explorer unzip and for SmartScreen |
| 5.4 | Message for running from inside the zip | `packaging/setup.cmd` | 5.1 | Already tested at script level; confirm from the built zip |
| 5.5 | SmartScreen guidance, given that signing is not available | delivery message (D3) | 5.3 | Accurate to the test in 5.3 |
| 5.6 | Remove test seams from the shipped behavior, or confirm they are safe | `packaging/setup.cmd` | 5.1 | `EVAL_COACH_PYTHON_URL` cannot bypass the pinned hash |
| 5.7 | Confirm pinned versions and hashes are still correct | manifest, `setup.cmd` | 5.1 | Real download test passes |
| 5.8 | Record the release checks | `docs/RELEASE.md` | 5.1 to 5.7 | Another person could repeat them |

---

## Phase 6: Pilot — ⏳ TO DO (needs go-ahead and D4)

**Status: ⏳ To do. None of the 16 tasks (6.1 to 6.16) is started.**

| ID | Task | Depends on | Done when |
|---|---|---|---|
| 6.1 | Choose 3 to 5 Windows users, including a non-developer | D4 | Names and CLIs recorded |
| 6.2 | Double-click `setup.cmd` at a live console | Phase 5 | Prompts and failure pauses work |
| 6.3 | Run on a clean Windows account with no Python or Node | Phase 5 | Preflight installs everything without admin rights |
| 6.4 | Run behind the company proxy | Phase 5 | Downloads succeed, or the message gives a workable action |
| 6.5 | Real CLI: new fixtures line writes no key | Phase 5 | No key before predictions lock, on each pilot CLI |
| 6.6 | Real CLI: new key line writes only the key | 6.5 | Gate passes and fixtures are unchanged |
| 6.7 | Real CLI: readback, run, fix, baseline | 6.6 | Full course completed by at least one person per CLI |
| 6.8 | Test the install recipes for real on a pilot machine | Phase 5 | Each recipe works, or is corrected in `cli-recipes.json` |
| 6.9 | Observe long approval prompts and the "switch to auto mode" menu | 6.7 | Guidance matches what people actually see |
| 6.10 | Record where people got stuck and how long each part took | 6.7 | One findings table |
| 6.11 | Sort findings into must-fix and later | 6.10 | User agrees with the list |
| 6.12 | Fix the must-fix items, and retest each one | 6.11 | Every must-fix verified |
| 6.13 | Release decision | 6.12 | User approves distribution |
| 6.14 | Tier 1 check: ask the non-developer to explain a pass rate and NOT CHECKED to an imaginary manager, and ask each pilot user to run an evaluation on their own prompt unaided | 6.7, 3.36 | One findings row per person: could explain, could run, where they stalled |
| 6.15 | Tier 2 check: ask each pilot user to say where the evaluation sits in the series and what Part 4 does with the baseline | 6.7, 3.38 | Findings row per person |
| 6.16 | Tier 3 check, only if 3.39 is built: ask each pilot user to name the three Stage 3 artifacts (Prompt, Evaluations, Log) and which of their files matches each | 6.7, 3.39 | Findings row per person; no one thinks the app submits or certifies |

---

## Phase 7: Mac — ⏸ DEFERRED (about 3 to 4 days)

**Status: ⏸ Deferred. None of the 6 tasks (7.1 to 7.6) is started.**

Start only when the user asks. Keep OS-specific code in `conpty.py` and the setup scripts until then.

| ID | Task | Done when |
|---|---|---|
| 7.1 | Terminal layer on `pty` behind the same interface as `conpty.py` | Existing terminal tests pass on Mac |
| 7.2 | `setup.sh` with the Python and hash behavior of `setup.cmd` | Same scenarios tested |
| 7.3 | Private Node install routine for Mac | Pinned hash verified |
| 7.4 | Mac commands in `cli-recipes.json` and step text | Content tests pass per platform |
| 7.5 | Quit, process-tree stop and path handling | No orphan processes remain |
| 7.6 | Test on a real Mac with at least one signed-in CLI | Full course completed |

---

## Open decisions

| ID | Decision | Needed by | Recommendation |
|---|---|---|---|
| D1 | Approve Phases 3 to 6 | Before 3.1 | Approve one phase at a time. **Phases 3 and 4 approved 2026-11-09.** Phases 5 and 6 still need a go-ahead |
| D2 | Include promptfoo live mode (Room B step 8)? | Before 4.18 | Decided 2026-11-09: build it now as an optional step with an explicit auto-mode warning (the app types one line; the participant's own CLI runs the helper). `agent-provider.js` runs the CLI non-interactively and passes `--permission-mode auto` for Devin, which conflicts with rule 2 |
| D3 | How do participants receive the zip? | Before 5.5 | SharePoint or Teams file, with one short message saying to unzip and run `setup.cmd` |
| D4 | Who pilots it, and on which CLIs? | Before 6.1 | At least one non-developer and at least two different CLIs |
| D5 | Add external reading to the lessons? | Before 3.28 | Lessons cite the bundled skills and Northwind files as their sources and primary reading. Any external page would be optional and must be opened and checked first. **Decided 2026-11-09: bundled files only.** Every lesson cites only `kit:` files, enforced by a test |
| D6 | May the app name the Stage 3 criteria (tasks 3.39 and 3.40)? | Before 3.39 | **Decided 2026-11-10: yes, as recommended.** One short note at the end of the last lesson, worded as the program's published criteria as of June 2026 (reworked by 3.46 on 2026-11-14 to the Prompt, Evaluations and Log structure of `docs/STAGE3-TASK-SPEC.md`, with the date dropped). The lesson cites no document, so D5 still holds. The note is never required, never blocks Continue, gives no submission steps, and is rechecked against the program's current wording before release (task 6.16). The user also named the series outcomes map as the source for the wider workflow |

## Housekeeping

These items are outside the phases and are waiting on the user.

| ID | Item | Status |
|---|---|---|
| H1 | Remove Copilot Chat in Teams from the Session 3 materials and attendee kit | Done outside this project; confirmed absent from the Markdown files and the zip on 2026-11-09 |
| H2 | Delete the 4 Phase 0 transcripts that contain the account email | Offered, not answered |
| H3 | Remove `e2e-work` and the Phase 0 runtimes and npm cache once they are no longer needed | After the pilot |
| H4 | Put the repo under git | Done; repo is under git with `origin` on GitHub |

## Known risks

| Risk | Effect | Handling |
|---|---|---|
| A real CLI ignores "write only the two fixture files" | A key appears before predictions | App deletes it and tells the participant; 6.5 measures how often this happens |
| Real CLIs produce long approval prompts | Participants may approve what they have not read | Scroll guidance is in the steps; 6.9 checks whether it is enough |
| CLI menus offer "switch to auto mode" | Participants may turn off their own approvals | The app can't prevent this; the guidance needs a decision after 6.9 |
| Install recipes change or fail | Preflight can't finish | Recipes are data, and "Other CLI" always remains available |
| Corporate policy blocks the local service or an unsigned script | App can't launch | Only the pilot can show this; 5.3 and 6.4 test it |
| promptfoo needs about 1 GB | Slow or failed setup | Consent states the size; only promptfoo-track participants download it |

## Order of work

1. ✅ Done: finish Phase 2.
2. ✅ Done: Phase 3A, then 3B and 3C together, then 3D (and 3E).
3. ✅ Done: Phase 4A first because it is a core outcome, then 4B, 4C and 4D.
4. ✅ Done: Phase 3F (3.36 to 3.44) before Phase 5, including tier 3 under D6.
5. ⏳ Next: Phase 5, then Phase 6.
6. ⏸ Phase 7 only on request.
