# Tasks

## 1. Content and its tests

- [x] 1.1 In `app/eval_coach/content/series.json` set `title` to "Evaluated systems" and `ui.intro` to the text in the proposal. Leave every other string, including `ui.brand_sub`, as it is. Verify: `python -m unittest tests.test_series tests.test_participant_vocabulary` passes after 1.2 and 1.3.
- [x] 1.2 In `tests/test_series.py` replace `test_the_intro_is_about_doing_the_work_yourself` with tests for the new requirements: the intro opens with "Is it good enough to use? How do you know?", contains the four principle phrases in order and ends with a task of the participant's own, contains none of "six", "Part", "step", "first", "then", "look ahead" or "Stage 3" (whole words, case-insensitive), has at most four sentences and 80 words; and the page `title` is "Evaluated systems". Verify: `python -m unittest tests.test_series`.
- [x] 1.3 In `tests/test_participant_vocabulary.py` change `test_the_series_map_intro_is_about_doing_the_work_yourself` to the banned-word check only (no "look ahead", no "Stage 3", no count or step wording), without repeating the structure assertions from 1.2. Verify: `python -m unittest tests.test_participant_vocabulary`.

## 2. Interface tests

- [x] 2.1 In `tests/frontend/ui.spec.js`, `locking.spec.js`, `part1.spec.js` and `part2.spec.js` change each `toHaveText('Series map')` on `#step-heading` to "Evaluated systems". Leave test names, the "Back to series map" control and every other use of the phrase as it is. Verify: `rg "toHaveText\('Series map'\)" tests/frontend` returns nothing.
- [x] 2.2 Add one Playwright check in `ui.spec.js` that the Series map shows the heading "Evaluated systems" and an intro that starts with "Is it good enough to use?", and that "Back to series map" is still the control's name inside a Part. Verify: `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js -g "Series map"`.
- [x] 2.3 Run the map's narrow-width and largest-text-size checks (`Series map: on a narrow screen…` and `Series map: labels are readable…` in `ui.spec.js`) and record in the apply notes whether the longer intro wraps without sideways scrolling. Do not change styles; report a problem as a finding for the user. Verify: the same Playwright command with `-g "narrow screen|labels are readable"`.

## 3. Docs

- [x] 3.1 In `docs/SPEC.md` "Series map" replace the sentence that says `ui.intro` "says there are six Parts, one method, and that you do each one yourself" with a description of the new intro and the page title, and cite this change. Verify: read the section and grep `docs/SPEC.md` for "do each one yourself" (no match left).
- [x] 3.2 In `docs/temp/series-review-pending-changes.md` mark item 19's draft as superseded by this change. Do not stage this file if it is ignored by git. Verify: read item 19.

## 4. Final check

- [ ] 4.1 Run the backend suite, then the embedded 3.13 suite one after the other, the interface suite and the build smoke test through the archive gate, as the project config says, and confirm `openspec validate series-map-outcome-intro --strict` passes. Verify: `python -m unittest discover -s tests`, then `spikes\phase0-preflight\runtime\python-embed-3.13.17-nopth\python.exe -m unittest discover -s tests`, then `node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js`, then `python tools\build_pyz.py --smoke`.
