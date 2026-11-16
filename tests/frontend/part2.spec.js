// Part 2's interface, tested against the real app (real_server.py): the real engine, course content and server.
// Part 2 starts no CLI, so nothing here needs a stand-in; a test only sets up where the participant is through the
// control port and reads the files the app wrote.
const { test: base, expect } = require('./.tmp/node_modules/@playwright/test');
const path = require('path');

const TOKEN = 'dev-token';
const PORT = Number(process.env.PART1_TEST_PORT) || 38927;
const CONTROL = `http://127.0.0.1:${PORT + 1}`;
const SHOTS = path.join(__dirname, '.tmp', 'screenshots');
const CSP_WORDS = /content security policy|refused to|csp/i;

const ROWS = [
  { requirement: 'It is under 150 words', criterion: 'The update is short', type: 'format', threshold: 'Word count under 100 passes' },
  { requirement: 'The work is grouped by client (Northwind, Contoso, Internal), not by day', criterion: 'Work is grouped by client', type: 'format', threshold: 'Passes if the labels Alpha and Beta both appear' },
  { requirement: 'It calls out the blocker and what you need to resolve it', criterion: 'The blocker is named', type: 'content', threshold: 'Passes if the word "stuck" appears' },
];
const REQUIREMENTS = [
  'It is sent as a Teams message, not an email',
  'It is under 150 words',
  'The work is grouped by client (Northwind, Contoso, Internal), not by day',
  'It calls out the blocker and what you need to resolve it',
  'The tone is factual, not self-promotional',
];

const test = base.extend({
  guarded: [
    async ({ page }, use) => {
      const problems = [];
      page.on('console', (msg) => {
        if (CSP_WORDS.test(msg.text())) problems.push(`console: ${msg.text()}`);
      });
      page.on('pageerror', (err) => problems.push(`pageerror: ${err.message}`));
      page.on('request', (req) => {
        const url = new URL(req.url());
        if (url.protocol !== 'data:' && url.host !== `127.0.0.1:${PORT}`) problems.push(`external request: ${req.url()}`);
      });
      await use(problems);
      expect(problems, problems.join('\n')).toEqual([]);
    },
    { auto: true },
  ],
});

async function control(request, route, data) {
  const res = await request.post(`${CONTROL}${route}`, { data: data || {} });
  expect(res.ok()).toBeTruthy();
}

async function readPart2(request, name) {
  return (await (await request.get(`${CONTROL}/control/read2?name=${name}`)).json()).text;
}

async function readRoot(request, name) {
  return (await (await request.get(`${CONTROL}/control/readroot?name=${name}`)).json()).text;
}

async function filesOf(request, route) {
  return (await request.get(`${CONTROL}${route}`)).json();
}

async function apiState(request, query) {
  const res = await request.get(`/api/state${query || ''}`, { headers: { 'X-Eval-Token': TOKEN } });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

// Starts a fresh app, optionally with everything before `reach` in Part 2 (and Part 1 up to `part1`) already done,
// and opens Part 2 from the Series map.
async function openPart2(page, request, opts = {}) {
  await control(request, '/control/reset', { scenario: opts.scenario || 'ready', part1_reach: opts.part1, reach2: opts.reach });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#series-list')).toHaveCount(0);
}

const sideways = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

const textContrast = (page, selector) =>
  page.evaluate((sel) => {
    const parse = (value) => value.match(/[\d.]+/g).map(Number);
    const lum = ([r, g, b]) => {
      const f = (c) => {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const el = document.querySelector(sel);
    const fg = parse(getComputedStyle(el).color);
    let node = el;
    let bg = [255, 255, 255];
    while (node) {
      const c = parse(getComputedStyle(node).backgroundColor);
      if (c.length === 3 || c[3] > 0) {
        bg = c.slice(0, 3);
        break;
      }
      node = node.parentElement;
    }
    const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
    return (hi + 0.05) / (lo + 0.05);
  }, selector);

async function saveShot(page, name, anchor) {
  await page.locator(anchor || '.step-page .panel').first().evaluate((el) => el.scrollIntoView({ block: 'start' }));
  await page.waitForTimeout(450);
  await page.screenshot({ path: path.join(SHOTS, `part2-${name}.png`) });
}

// ---- worksheet helpers ----------------------------------------------------------------

async function fillRow(page, n, row, withThreshold) {
  await page.locator(`#row-${n}-requirement`).fill(row.requirement);
  await page.locator(`#row-${n}-criterion`).fill(row.criterion);
  if (row.type) await page.locator(`#row-${n}-type input[value="${row.type}"]`).check();
  if (withThreshold) await page.locator(`#row-${n}-threshold`).fill(row.threshold);
}

// Adds a row for each of `rows` (starting at row `first`) and fills it in.
async function addRows(page, rows, first = 1) {
  for (const [i, row] of rows.entries()) {
    await page.locator('#ws-add').click();
    await expect(page.locator(`#ws-row-${first + i}`)).toBeVisible();
    await fillRow(page, first + i, row);
  }
}

async function saveWorksheet(page) {
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText(/ saved\.$/);
}

async function tickBoth(page) {
  await page.locator('#tick-traces').check();
  await page.locator('#tick-distinct').check();
  await expect(page.locator('#tick-distinct')).toBeChecked();
}

async function checkWork(page) {
  await page.locator('#check-work').click();
  await expect(page.locator('.check-result')).toBeVisible();
}

const gateItems = (page) => page.locator('.check-items li');
const gateText = (page, label) => gateItems(page).filter({ hasText: label });

// ---- the Series map ------------------------------------------------------------------

test('the Series map shows Part 2 with a state and an open control, Parts 4 and 5 still say Coming soon, and each Part counts its own items', async ({ page, request }) => {
  await control(request, '/control/reset', { scenario: 'ready', part1_reach: 'rewrite' });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  const row = page.locator('#series-part-2');
  await expect(row).toHaveClass(/k-course/);
  await expect(row.locator('.series-tag')).toHaveCount(0);
  await expect(row).not.toContainText('Coming soon');
  await expect(row).toContainText('Defining evaluation criteria');
  await expect(row).toContainText('Not started');
  await expect(row.locator('.series-action')).toHaveText('Start');
  await expect(row.locator('#series-open-part-2')).toBeVisible();
  await expect(row.locator('#series-toggle-part-2')).toBeVisible();
  const soon = page.locator('.series-row.k-soon');
  await expect(soon).toHaveCount(2);
  expect(await soon.locator('.series-title').allTextContents()).toEqual(['Part 4: Iterating with evaluation-driven development', 'Part 5: Load-bearing audit and packaging']);
  for (const one of await soon.all()) {
    await expect(one.locator('.series-tag')).toHaveText('Coming soon');
    await expect(one.locator('button, a, [tabindex], .series-chevron')).toHaveCount(0);
  }
  // Each Part counts its own items. The row shows a count once a Part is started; the state carries all three.
  const parts = Object.fromEntries((await apiState(request)).series.parts.map((p) => [p.id, p]));
  expect([parts['part-2'].done, parts['part-2'].total]).toEqual([0, 8]);
  expect(parts['part-1'].total).toBe(9);
  expect(parts['part-1'].done).toBeGreaterThan(0);
  expect(parts['part-3'].total).toBe(16);
  expect(parts['part-3'].done).toBe(0);
  await expect(page.locator('#series-part-1 .series-count')).toHaveText(`${parts['part-1'].done} of 9 done`);
  await expect(row.locator('.series-count')).toHaveCount(0);
});

test('the Part 2 row expands and collapses by mouse and keyboard without opening the Part, and starts expanded', async ({ page, request }) => {
  await control(request, '/control/reset', { scenario: 'ready' });
  await page.goto(`/?t=${TOKEN}`);
  const toggle = page.locator('#series-toggle-part-2');
  const lessons = page.locator('#series-lessons-part-2 li');
  for (const id of ['part-1', 'part-2', 'part-3']) await expect(page.locator(`#series-toggle-${id}`)).toHaveAttribute('aria-expanded', 'true');
  await expect(lessons).toHaveCount(4);
  expect(await page.locator('#series-lessons-part-2 .series-lesson-title').allTextContents()).toEqual([
    'Your mission',
    'From requirements to criteria',
    'Rules a script could check',
    'Writing your rules down',
  ]);
  await expect(lessons.first()).toContainText('Now');
  await expect(lessons.last()).toContainText('Not started');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('#series-lessons-part-2')).toBeHidden();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#series-lessons-part-2')).toBeVisible();
  await page.keyboard.press('Space');
  await expect(page.locator('#series-lessons-part-2')).toBeHidden();
  await page.keyboard.press('Space');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.activeElement.id)).toBe('series-open-part-2');
  await expect(page.locator('#step-heading')).toHaveText('Series map');
});

test('opening Part 2 lands on its mission page with its own header, route groups and course list; Back works', async ({ page, request }) => {
  await openPart2(page, request);
  await expect(page.locator('.brand-sub')).toHaveText('Part 2 · Defining evaluation criteria');
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  expect(await page.locator('.course-group').allTextContents()).toEqual(['Know what you need', 'Turn it into rules', 'Write it down', 'Compare with an example']);
  await expect(page.locator('.course-item')).toHaveCount(8);
  expect(await page.locator('.course-item-title').allTextContents()).toEqual([
    'Your mission',
    'From requirements to criteria',
    'Draft your criteria',
    'Rules a script could check',
    'Add a pass or fail rule',
    'Writing your rules down',
    'Write your test cases down',
    'Compare with an example',
  ]);
  await page.locator('#back-to-series').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-3').click();
  await expect(page.locator('.brand-sub')).toHaveText('Part 3 · Running evals and baseline');
});

test('selecting the Part 2 row continues at the current item', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'p2-thresholds' });
  await expect(page.locator('#step-heading')).toHaveText('Rules a script could check');
  await page.locator('#back-to-series').click();
  await expect(page.locator('#series-part-2')).toContainText('In progress');
  await expect(page.locator('#series-part-2 .series-action')).toHaveText('Continue');
  await expect(page.locator('#series-part-2 .series-count')).toHaveText(/^\d of 8 done$/);
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#step-heading')).toHaveText('Rules a script could check');
});

// ---- no CLI, setup and previews ----------------------------------------------------------

test('no Part 2 step offers Start or Send or a terminal, and none starts a CLI', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  for (const title of ['Draft your criteria', 'Add a pass or fail rule', 'Write your test cases down', 'Compare with an example']) {
    await page.locator('.course-btn', { hasText: title }).click();
    await expect(page.locator('#step-heading')).toHaveText(title);
    for (const id of ['#cli-start', '#cli-send', '#cli-stop', '#cli-retry']) await expect(page.locator(id)).toHaveCount(0);
    await expect(page.locator('#term-host')).toBeHidden();
    await expect(page.locator('#screen-main')).toHaveClass(/no-terminal/);
  }
  expect((await filesOf(request, '/control/files2')).started).toBe(0);
});

test('before setup the draft step can be read, nothing in it can be saved, and the server refuses a save', async ({ page, request }) => {
  await control(request, '/control/reset', { scenario: 'no-setup' });
  await page.goto(`/?t=${TOKEN}`);
  await page.locator('#pf-skip').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await page.locator('.course-btn', { hasText: 'Draft your criteria' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
  await expect(page.locator('#preview-note')).toBeVisible();
  await expect(page.locator('#preview-setup')).toBeVisible();
  await expect(page.locator('.step-page')).toContainText('Read the scenario and the five things you know');
  for (const id of ['#ws-add', '#part-save', '#check-work', '#ws-rows', '#scenario-card']) await expect(page.locator(id)).toHaveCount(0);
  const refused = await request.post('/api/step/submit', { headers: { 'X-Eval-Token': TOKEN }, data: { step: 'draft', data: { rows: ROWS } } });
  expect(refused.ok()).toBeFalsy();
  expect(['not_configured', 'preflight_incomplete']).toContain((await refused.json()).error.code);
});

test('a locked Part 2 step opens as a preview that writes nothing, and the reference stays hidden until the file is done', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'test-file' });
  await expect(page.locator('#step-heading')).toHaveText('Write your test cases down');
  await page.locator('.course-btn', { hasText: 'Compare with an example' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Compare with an example');
  await expect(page.locator('#preview-note')).toContainText('Write your test cases down');
  for (const id of ['#ref-C1', '#reference-lists', '#one-good-answer', '#part-save', '#check-work']) await expect(page.locator(id)).toHaveCount(0);
  expect((await filesOf(request, '/control/files2')).part2).toEqual(['worksheet.json']);
  const detail = await apiState(request, '?step=reference');
  expect(detail.step.preview).toBeTruthy();
  expect(detail.step.data).toEqual({});
});

// ---- the draft step -----------------------------------------------------------------------

test('the draft step shows the scenario card, the five requirements and the rough notes as plain text', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
  const card = page.locator('#scenario-card');
  await expect(card).toContainText('Friday afternoon');
  expect(await card.locator('li').allTextContents()).toEqual(REQUIREMENTS);
  await expect(page.locator('#scenario-notes')).toContainText('Northwind');
  await expect(page.locator('#scenario-notes')).toHaveAttribute('role', 'region');
  await expect(page.locator('#ws-empty')).toHaveText('Add at least three criteria to begin.');
  await expect(page.locator('.ws-row')).toHaveCount(0);
});

test('the worksheet adds and removes rows, fills a requirement from the card, and saves only when asked', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await page.locator('#ws-add').click();
  await page.locator('#ws-add').click();
  await expect(page.locator('.ws-row')).toHaveCount(2);
  await expect(page.locator('#ws-empty')).toHaveCount(0);
  await expect(page.locator('#part-save-status')).toHaveText('You have changes that are not saved yet.');
  await expect(page.locator('#ws-row-1 > legend')).toHaveText('Criterion 1');
  // The menu fills the box, and the box stays editable.
  await page.locator('#row-1-menu').selectOption({ label: REQUIREMENTS[1] });
  await expect(page.locator('#row-1-requirement')).toHaveValue(REQUIREMENTS[1]);
  await expect(page.locator('#row-1-menu')).toHaveValue('');
  await page.locator('#row-1-requirement').fill(`${REQUIREMENTS[1]} (my words)`);
  await expect(page.locator('#row-1-requirement')).toHaveValue(`${REQUIREMENTS[1]} (my words)`);
  await page.locator('#row-1-criterion').fill('First one');
  await page.locator('#row-2-criterion').fill('Second one');
  await page.locator('#row-1-type input[value="format"]').check();
  await expect(page.locator('#row-2-type .ws-type-none')).toHaveText('Not chosen');
  await page.locator('#row-2-remove').click();
  await expect(page.locator('.ws-row')).toHaveCount(1);
  expect(await readPart2(request, 'worksheet.json')).toBeNull();
  await saveWorksheet(page);
  const saved = JSON.parse(await readPart2(request, 'worksheet.json'));
  expect(saved.rows).toEqual([{ requirement: `${REQUIREMENTS[1]} (my words)`, criterion: 'First one', type: 'format', threshold: '' }]);
  await expect(page.locator('#part-save')).toHaveAttribute('aria-disabled', 'true');
});

test('the worksheet stops at the row limit and tells the participant why', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  for (let i = 0; i < 12; i += 1) await page.locator('#ws-add').click();
  await expect(page.locator('.ws-row')).toHaveCount(12);
  await expect(page.locator('#ws-add')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#ws-full')).toHaveText('The worksheet is full.');
  await page.locator('#ws-add').click({ force: true });
  await expect(page.locator('.ws-row')).toHaveCount(12);
});

test('a saved worksheet is shown again when the step is reopened, not a blank table', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await addRows(page, ROWS);
  await saveWorksheet(page);
  await page.reload();
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
  await expect(page.locator('.ws-row')).toHaveCount(3);
  await expect(page.locator('#row-3-criterion')).toHaveValue('The blocker is named');
  await expect(page.locator('#row-3-type input[value="content"]')).toBeChecked();
  await expect(page.locator('#part-save-status')).toHaveText('Your worksheet is saved.');
});

test('unsaved changes ask to Save first and check nothing', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await addRows(page, ROWS);
  await page.locator('#check-work').click();
  await expect(page.locator('.notice')).toContainText('Press Save my worksheet first');
  await expect(page.locator('.check-result')).toHaveCount(0);
  await saveWorksheet(page);
  await page.locator('#row-1-criterion').fill('Changed after saving');
  await page.locator('#check-work').click();
  await expect(page.locator('.notice')).toContainText('not saved yet');
  await expect(page.locator('.check-result')).toHaveCount(0);
});

test('the draft gate names what is missing: too few rows, no content row, a missing piece, a repeat and the self-checks', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await addRows(page, ROWS.slice(0, 2));
  await saveWorksheet(page);
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Not done yet');
  await expect(gateText(page, 'Three or more criteria')).toContainText('You have 2 saved. Add 1 more so there are at least 3.');
  await expect(gateText(page, 'One about content')).toContainText('At least one criterion must be about what the answer says');
  await expect(gateText(page, 'Self-check: each one traces')).toContainText('Tick the first self-check');
  await expect(gateText(page, 'Self-check: no two')).toContainText('Tick the second self-check');
  await expect(gateText(page, 'Three or more criteria').locator('.check-mark')).toHaveText('Not yet');
  // Three rows, one missing its criterion, one repeating another.
  await page.locator('#ws-add').click();
  await page.locator('#row-3-requirement').fill(ROWS[2].requirement);
  await page.locator('#row-3-type input[value="content"]').check();
  await saveWorksheet(page);
  await checkWork(page);
  await expect(gateText(page, 'Every row complete')).toContainText('Fill in the requirement, the criterion and the type for row 3.');
  await page.locator('#row-3-criterion').fill('  the UPDATE is   short ');
  await saveWorksheet(page);
  await checkWork(page);
  await expect(gateText(page, 'No repeated criterion')).toContainText('The criterion in rows 1 and 3 is the same.');
  await page.locator('#row-3-criterion').fill(ROWS[2].criterion);
  await tickBoth(page);
  await saveWorksheet(page);
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
  await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
});

test('the ticks save as the participant works and survive a reload without pressing Save', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await page.locator('#tick-traces').check();
  await expect(page.locator('#tick-traces')).toBeChecked();
  const record = async () => (await apiState(request, '?step=draft')).step.data.ticks.map((t) => [t.id, t.checked]);
  await expect.poll(record).toEqual([['traces', true], ['distinct', false]]);
  await page.reload();
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#tick-traces')).toBeChecked();
  await expect(page.locator('#tick-distinct')).not.toBeChecked();
});

test('the worksheet works by keyboard: boxes, the type choice, add, remove, Save and Check', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await page.locator('#ws-add').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#row-1-requirement')).toBeFocused();
  await page.keyboard.type('It is under 150 words');
  await page.keyboard.press('Tab');
  await expect(page.locator('#row-1-menu')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#row-1-criterion')).toBeFocused();
  await page.keyboard.type('The update is short');
  await page.keyboard.press('Tab');
  await expect(page.locator('#row-1-type input[value="format"]')).toBeFocused();
  await page.keyboard.press('Space');
  await expect(page.locator('#row-1-type input[value="format"]')).toBeChecked();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#row-1-type input[value="content"]')).toBeChecked();
  await page.keyboard.press('Tab');
  await expect(page.locator('#row-1-remove')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#ws-add')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('.ws-row')).toHaveCount(2);
  await page.locator('#row-2-remove').focus();
  await page.keyboard.press('Space');
  await expect(page.locator('.ws-row')).toHaveCount(1);
  await expect(page.locator('#ws-add')).toBeFocused();
  await page.locator('#part-save').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#part-save-status')).toHaveText('Your worksheet is saved.');
  await page.locator('#tick-traces').focus();
  await page.keyboard.press('Space');
  await expect(page.locator('#tick-traces')).toBeChecked();
  await page.locator('#check-work').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.check-result')).toBeVisible();
});

test('the optional Part 1 panel shows the participant\'s own marks and gap, and Part 1 stays unchanged', async ({ page, request }) => {
  await control(request, '/control/reset', { scenario: 'ready', part1_reach: 'rewrite', reach2: 'draft' });
  const before = await filesOf(request, '/control/files');
  await page.goto(`/?t=${TOKEN}`);
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
  const panel = page.locator('#part1-panel');
  await expect(panel).toBeVisible();
  await expect(page.locator('.step-page')).toContainText('Your own notes from Part 1');
  await expect(panel.locator('li')).toHaveCount(5);
  await expect(panel.locator('li').first()).toContainText(`${REQUIREMENTS[0]}: Yes`);
  await expect(panel.locator('li').last()).toContainText(`${REQUIREMENTS[4]}: No`);
  await expect(page.locator('#part1-gap')).toHaveText('No ask for my lead');
  await addRows(page, ROWS);
  await saveWorksheet(page);
  expect(await filesOf(request, '/control/files')).toEqual(before);
});

test('without Part 1 work there is no Part 1 panel and the step works the same', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'draft' });
  await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
  await expect(page.locator('#part1-panel')).toHaveCount(0);
  await expect(page.locator('.step-page')).not.toContainText('Your own notes from Part 1');
  await expect(page.locator('#ws-add')).toBeVisible();
});

// ---- the thresholds step ------------------------------------------------------------------

async function openThresholds(page, request) {
  await openPart2(page, request, { reach: 'thresholds' });
  await expect(page.locator('#step-heading')).toHaveText('Add a pass or fail rule');
}

test('the thresholds step shows the same rows, read-only, with an empty Threshold box for each', async ({ page, request }) => {
  await openThresholds(page, request);
  await expect(page.locator('.ws-row')).toHaveCount(3);
  await expect(page.locator('#criteria-locked')).toHaveText('The criteria are fixed in this step. Only the thresholds can change.');
  await expect(page.locator('#ws-row-1 .ref-fact').first()).toContainText(ROWS[0].requirement);
  await expect(page.locator('#ws-row-3')).toContainText('The blocker is named');
  await expect(page.locator('#ws-row-3')).toContainText('Content');
  for (const n of [1, 2, 3]) {
    await expect(page.locator(`#row-${n}-threshold`)).toHaveValue('');
    await expect(page.locator(`#row-${n}-criterion`)).toHaveCount(0);
  }
  for (const id of ['#ws-add', '#row-1-remove']) await expect(page.locator(id)).toHaveCount(0);
});

test('the thresholds gate names a missing threshold and the script test; "Not checked:" counts as written', async ({ page, request }) => {
  await openThresholds(page, request);
  await page.locator('#row-1-threshold').fill('Word count under 100 passes');
  await page.locator('#row-3-threshold').fill('Not checked: a person has to judge whether the ask is clear');
  await saveWorksheet(page);
  await checkWork(page);
  await expect(gateText(page, 'Every criterion has a threshold')).toContainText('Write a threshold for row 2.');
  await expect(gateText(page, 'Script test applied')).toContainText('Tick the script test');
  await page.locator('#row-2-threshold').fill('Passes if the labels Alpha and Beta both appear');
  await page.locator('#tick-script_test').check();
  await expect(page.locator('#tick-script_test')).toBeChecked();
  await saveWorksheet(page);
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
  const saved = JSON.parse(await readPart2(request, 'worksheet.json'));
  expect(saved.rows.map((r) => r.criterion)).toEqual(ROWS.map((r) => r.criterion));
  expect(saved.rows[2].threshold).toBe('Not checked: a person has to judge whether the ask is clear');
});

test('a vague threshold gets a note that names the word and never blocks; a quoted word is not flagged', async ({ page, request }) => {
  await openThresholds(page, request);
  await expect(page.locator('#threshold-notes')).toHaveText('No notes. Nothing here looks vague.');
  await page.locator('#row-1-threshold').fill('The update is clear');
  await page.locator('#row-2-threshold').fill('Passes if the word "clear" appears');
  await page.locator('#row-3-threshold').fill('Passes if the word "stuck" appears');
  await saveWorksheet(page);
  const notes = page.locator('#threshold-notes li');
  await expect(notes).toHaveCount(1);
  await expect(notes.first()).toContainText('Row 1 uses “clear”');
  await expect(notes.first()).toContainText('a number');
  await expect(notes.first()).toContainText('a list of terms you choose');
  await expect(notes.first()).toContainText('a label');
  await expect(notes.first()).toContainText('Not checked:');
  await page.locator('#tick-script_test').check();
  await expect(page.locator('#tick-script_test')).toBeChecked();
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
  await expect(page.locator('#threshold-notes li')).toHaveCount(1);
});

test('a finished step shows one Quick check that never stands in the way of the next item', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'test-file' });
  await page.locator('.course-btn', { hasText: 'Add a pass or fail rule' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Add a pass or fail rule');
  await expect(page.getByRole('heading', { name: 'Quick check' })).toBeVisible();
  await expect(page.locator('.step-page article.activity')).toHaveCount(1);
  await expect(page.locator('#continue')).toBeVisible();
  await expect(page.locator('#row-1-threshold')).toBeDisabled();
  await expect(page.locator('#part-save')).toHaveAttribute('aria-disabled', 'true');
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Writing your rules down');
});

// ---- the test-file step ------------------------------------------------------------------

async function openTestFile(page, request) {
  await openPart2(page, request, { reach: 'test-file' });
  await expect(page.locator('#step-heading')).toHaveText('Write your test cases down');
}

const editorText = (page) => page.locator('#file-editor').inputValue();

test('Build puts the participant\'s own criteria in the layout Part 3 reads, numbered C1, C2 and so on', async ({ page, request }) => {
  await openTestFile(page, request);
  await expect(page.locator('#file-editor')).toHaveValue('');
  await expect(page.locator('#file-build')).not.toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#findings-empty')).toHaveText('No file is saved yet.');
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  const text = await editorText(page);
  expect(text).toContain('## Test input');
  expect(text).toContain('## Criteria');
  expect(text).toContain('## Supporting lists');
  for (const [i, row] of ROWS.entries()) {
    expect(text).toContain(`### C${i + 1}: ${row.criterion}`);
    expect(text).toContain(`- Requirement: ${row.requirement}`);
    expect(text).toContain(`- Threshold: ${row.threshold}`);
  }
  expect(text).toContain('- Type: Content');
  expect(await readPart2(request, 'test-cases.md')).toBe(text);
  await expect(page.locator('#findings-none')).toHaveText('Nothing to fix.');
});

test('the supporting lists start empty of any example words, and the step says the participant writes their own list', async ({ page, request }) => {
  await openTestFile(page, request);
  await expect(page.locator('#lists-note')).toContainText('A banned or required list for your own task is something you write yourself');
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  const lists = (await editorText(page)).split('## Supporting lists')[1];
  expect(lists.trim()).toBe('- Example: Terms to avoid: word one, word two');
  await expect(page.locator('#findings-notes')).toHaveCount(0);
});

test('a threshold that names a list with no list entry gets a note that says where to add it', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  const text = (await editorText(page)).replace('Word count under 100 passes', 'No word from the banned list appears');
  await page.locator('#file-editor').fill(text);
  await page.locator('#part-save').click();
  await expect(page.locator('#findings-notes')).toContainText('C1 (The update is short) points to a list, but the file has no list under Supporting lists');
  await expect(page.locator('#findings-blocking')).toHaveCount(0);
});

test('Build asks before replacing saved text, keeps the old text when declined and replaces it when confirmed', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  await page.locator('#file-editor').fill('# My own file\n\nMy words.');
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  await page.locator('#file-build').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog).toContainText('Replace your saved file?');
  await expect(dialog).toContainText('Your worksheet is not changed.');
  await dialog.getByRole('button', { name: 'Keep my file' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('#file-editor')).toHaveValue('# My own file\n\nMy words.');
  expect(await readPart2(request, 'test-cases.md')).toBe('# My own file\n\nMy words.');
  await page.locator('#file-build').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Replace my file' }).click();
  await expect(page.locator('#file-editor')).toHaveValue(/### C1: The update is short/);
  expect(await readPart2(request, 'test-cases.md')).toContain('### C3: The blocker is named');
  await expect(page.locator('.notice')).toHaveCount(0);
});

test('Build also asks when the editor holds unsaved text, and when the server asks to confirm a blank editor', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  const built = await editorText(page);
  await page.locator('#file-editor').fill('Unsaved words.');
  await page.locator('#file-build').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Keep my file' }).click();
  await expect(page.locator('#file-editor')).toHaveValue('Unsaved words.');
  expect(await readPart2(request, 'test-cases.md')).toBe(built);
  // A blank editor over a saved file: the server's own refusal asks the same question.
  await page.locator('#file-editor').fill('');
  await page.locator('#file-build').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog).toContainText('Replace your saved file?');
  await dialog.getByRole('button', { name: 'Keep my file' }).click();
  expect(await readPart2(request, 'test-cases.md')).toBe(built);
  await expect(page.locator('.notice')).toHaveCount(0);
  await page.locator('#file-build').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Replace my file' }).click();
  await expect(page.locator('#file-editor')).toHaveValue(built);
  await expect(page.locator('.notice')).toHaveCount(0);
});

test('Build is off with a hint when the saved worksheet has no rows to build from', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'test-file' });
  await control(request, '/control/write2', { name: 'worksheet.json', text: '{"rows": []}' });
  await page.reload();
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#step-heading')).toHaveText('Write your test cases down');
  await expect(page.locator('#file-build')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#build-hint')).toHaveText('Save your worksheet in the earlier steps to build from it.');
  await page.locator('#file-build').click({ force: true });
  await expect(page.locator('#file-editor')).toHaveValue('');
  expect(await readPart2(request, 'test-cases.md')).toBeNull();
});

test('the file gate and its findings: too few criteria, no content criterion, then notes that never block', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  const full = await editorText(page);
  // Two criteria only.
  const two = full.slice(0, full.indexOf('### C3:')) + full.slice(full.indexOf('## Supporting lists'));
  await page.locator('#file-editor').fill(two);
  await page.locator('#part-save').click();
  await expect(page.locator('#findings-blocking h3')).toHaveText('Fix these first');
  await expect(page.locator('#findings-blocking')).toContainText('The file has 2 of the 3 criteria it needs. Add 1 more.');
  await expect(page.locator('#findings-blocking')).toContainText('### C3:');
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Not done yet');
  await expect(gateText(page, 'Three or more criteria')).toContainText('2 of the 3 criteria');
  // Three criteria, none about content.
  const noContent = full
    .replace('- Type: Content', '- Type: Format')
    .replace('Passes if the labels Alpha and Beta both appear', 'Word count over 5 passes')
    .replace('Passes if the word "stuck" appears', 'Word count over 20 passes');
  await page.locator('#file-editor').fill(noContent);
  await page.locator('#part-save').click();
  await expect(page.locator('#findings-blocking')).toContainText('No criterion checks what the answer says');
  await expect(page.locator('#findings-blocking')).toContainText('Passes if the update names every client in the notes');
  await checkWork(page);
  await expect(gateText(page, 'One about content')).toContainText('No criterion checks what the answer says');
  // A vague threshold is a note: the gate passes and the note stays on the page.
  const vague = full.replace('Word count under 100 passes', 'The update is clear');
  await page.locator('#file-editor').fill(vague);
  await page.locator('#part-save').click();
  await expect(page.locator('#findings-blocking')).toHaveCount(0);
  await expect(page.locator('#findings-notes h3')).toHaveText('Notes. These do not stop you.');
  await expect(page.locator('#findings-notes')).toContainText('C1 (The update is short) uses “clear” in its threshold');
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
  await expect(page.locator('#findings-notes')).toBeVisible();
});

test('missing blocks show before notes, a missing threshold and requirement are notes, and a test input is required', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  const full = await editorText(page);
  const broken = full
    .replace('## Test input', '## Notes')
    .replace('- Threshold: Word count under 100 passes', '- Threshold:')
    .replace('- Requirement: It is under 150 words\n', '')
    .replace('- Type: Content', '- Type: Format');
  await page.locator('#file-editor').fill(broken);
  await page.locator('#part-save').click();
  await expect(page.locator('#findings-blocking')).toContainText('The file has no test input');
  const order = await page.locator('#file-findings .callout').evaluateAll((els) => els.map((e) => e.id));
  expect(order).toEqual(['findings-blocking', 'findings-notes']);
  await expect(page.locator('#findings-notes')).toContainText('C1 (The update is short) has no threshold');
  await expect(page.locator('#findings-notes')).toContainText('C1 (The update is short) has no Requirement line');
});

test('the same file text checks the same way with Windows line endings', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  await control(request, '/control/write2', { name: 'test-cases.md', text: (await readPart2(request, 'test-cases.md')).replace(/\n/g, '\r\n') });
  await page.reload();
  await page.locator('#series-open-part-2').click();
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
});

test('saving a file only replaces it when the participant presses Save, and Part 3\'s own file is untouched', async ({ page, request }) => {
  await openTestFile(page, request);
  const root = await readRoot(request, 'test-cases.md');
  expect(root).not.toBeNull();
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  await page.locator('#file-editor').fill('# Draft only');
  expect(await readPart2(request, 'test-cases.md')).toContain('## Criteria');
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  expect(await readPart2(request, 'test-cases.md')).toBe('# Draft only');
  expect(await readRoot(request, 'test-cases.md')).toBe(root);
  expect((await filesOf(request, '/control/files2')).part2.sort()).toEqual(['test-cases.md', 'worksheet.json']);
});

test('the test-file step passes and opens the reference, which was not there before', async ({ page, request }) => {
  await openTestFile(page, request);
  await page.locator('#file-build').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Compare with an example');
  await expect(page.locator('.ref-card').first()).toBeVisible();
});

// ---- the reference step ------------------------------------------------------------------

async function openReference(page, request) {
  await openPart2(page, request, { reach: 'reference' });
  await expect(page.locator('#step-heading')).toHaveText('Compare with an example');
  await expect(page.locator('.ref-card').first()).toBeVisible();
}

test('the reference step shows each example criterion with four choices, beside the participant\'s own, and says it is not a score', async ({ page, request }) => {
  await openReference(page, request);
  const cards = page.locator('.ref-card');
  const count = await cards.count();
  expect(count).toBeGreaterThan(2);
  await expect(page.locator('#one-good-answer')).toContainText('one good answer, not the only one');
  await expect(page.locator('#one-good-answer')).toContainText('this is not a score');
  for (const card of await cards.all()) {
    await expect(card.locator('h3')).not.toHaveText('');
    expect(await card.locator('.ref-fact dt').allTextContents()).toEqual(['Requirement', 'Type', 'Threshold']);
    const group = card.locator('fieldset.ref-choices');
    await expect(group.locator('legend')).toContainText('How does yours compare with');
    expect(await group.locator('label.radio-card').allTextContents()).toEqual(['I had this one', 'I missed this one', 'Mine differs but works', 'Mine was too vague']);
    await expect(group.locator('input:checked')).toHaveCount(0);
  }
  await expect(page.locator('#mine-list li')).toHaveCount(3);
  await expect(page.locator('#mine-list')).toContainText('The blocker is named');
  await expect(page.locator('#ref-progress')).toHaveText(`0 of ${count} compared`);
});

test('the example\'s own list appears once, on this step, marked as the example\'s and not theirs to copy', async ({ page, request }) => {
  await openPart2(page, request, { reach: 'reference' });
  await page.locator('.course-btn', { hasText: 'Write your test cases down' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Write your test cases down');
  await expect(page.locator('#reference-lists')).toHaveCount(0);
  const mineText = await page.locator('#file-editor').inputValue();
  await page.locator('.course-btn', { hasText: 'Compare with an example' }).click();
  await expect(page.locator('#reference-lists')).toHaveCount(1);
  await expect(page.locator('#reference-lists-note')).toContainText('This list belongs to the example');
  await expect(page.locator('#reference-lists-note')).toContainText('you do not copy this one');
  await expect(page.locator('.step-page h2', { hasText: 'The example\'s own list' })).toHaveCount(1);
  const listText = await page.locator('#reference-lists').innerText();
  expect(listText.trim().length).toBeGreaterThan(0);
  for (const line of listText.split('\n').filter((l) => l.trim())) expect(mineText).not.toContain(line.trim());
});

test('choices save as the participant picks them, the gate names a missing one, and the app never judges the answers', async ({ page, request }) => {
  await openReference(page, request);
  const cards = page.locator('.ref-card');
  const count = await cards.count();
  const ids = await cards.evaluateAll((els) => els.map((e) => e.id.replace('ref-', '')));
  for (const id of ids.slice(0, count - 1)) await page.locator(`#ref-${id}-choices label.radio-card`).nth(3).click();
  await expect(page.locator('#ref-progress')).toHaveText(`${count - 1} of ${count} compared`);
  await expect.poll(async () => Object.keys((await apiState(request, '?step=reference')).step.data.choices).length).toBe(count - 1);
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Not done yet');
  await expect(gateText(page, 'Every example criterion compared')).toContainText(`Choose how yours compares for: `);
  await page.locator(`#ref-${ids[count - 1]}-choices label.radio-card`).nth(0).click();
  await expect(page.locator('#ref-progress')).toHaveText(`${count} of ${count} compared`);
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Passed');
  await page.locator('#back-to-series').click();
  await page.locator('#series-open-part-2').click();
  await expect(page.locator('#step-heading')).toHaveText('You have finished Part 2');
  await expect(page.locator('.finished-page')).toContainText('part-2\\test-cases.md');
});

test('a choice works by keyboard with the arrow keys, inside a labelled group', async ({ page, request }) => {
  await openReference(page, request);
  const first = page.locator('.ref-card').first();
  const id = (await first.getAttribute('id')).replace('ref-', '');
  const radios = page.locator(`#ref-${id}-choices input[type="radio"]`);
  await radios.first().focus();
  await page.keyboard.press('ArrowDown');
  await expect(radios.nth(1)).toBeChecked();
  await page.keyboard.press('ArrowRight');
  await expect(radios.nth(2)).toBeChecked();
  await expect(page.locator(`#ref-${id}-choices`)).toContainText('Mine differs but works');
  await expect.poll(async () => (await apiState(request, '?step=reference')).step.data.choices[id]).toBe('different');
});

test('the file editor is here again: editing and saving runs the file checks and leaves the step\'s gate alone', async ({ page, request }) => {
  await openReference(page, request);
  const text = (await editorText(page)).replace('Word count under 100 passes', 'The update is clear');
  await page.locator('#file-editor').fill(text);
  await page.locator('#check-work').click();
  await expect(page.locator('.notice')).toContainText('Press Save my file first');
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
  await expect(page.locator('#findings-notes')).toContainText('uses “clear”');
  expect(await readPart2(request, 'test-cases.md')).toBe(text);
  await checkWork(page);
  await expect(page.locator('.check-head')).toContainText('Not done yet');
  await expect(page.locator('.check-items li')).toHaveCount(1);
});

// ---- looks and layout --------------------------------------------------------------------

test('the scenario card, the Part 1 panel, the threshold notes and the ticks are readable and fit at every width in both themes', async ({ page, request }) => {
  test.setTimeout(240000);
  for (const theme of ['light', 'dark']) {
    for (const width of [1280, 900, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await control(request, '/control/reset', { scenario: 'ready', part1_reach: 'rewrite', reach2: 'draft' });
      await page.goto(`/?t=${TOKEN}`);
      await page.evaluate((value) => window.localStorage.setItem('eval-coach-theme', value), theme);
      await page.reload();
      await page.locator('#series-open-part-2').click();
      await expect(page.locator('#step-heading')).toHaveText('Draft your criteria');
      await expect(page.locator('#part1-panel')).toBeVisible();
      expect(await sideways(page), `draft ${theme} ${width}`).toBeLessThanOrEqual(0);
      for (const selector of ['#scenario-card', '#part1-panel', '#part1-panel li', '#part1-gap', '#scenario-notes']) {
        expect(await textContrast(page, selector), `${theme} ${width} ${selector}`).toBeGreaterThanOrEqual(4.5);
      }
      await saveShot(page, `top-${theme}-${width}`, '#part1-panel');
      await page.locator('.ws-ticks').evaluate((el) => el.scrollIntoView({ block: 'center' }));
      await expect(page.locator('#tick-traces')).toBeVisible();
      await page.waitForTimeout(450);
      await page.screenshot({ path: path.join(SHOTS, `part2-ticks-${theme}-${width}.png`) });
      await control(request, '/control/reset', { scenario: 'ready', reach2: 'thresholds' });
      await page.reload();
      await page.locator('#series-open-part-2').click();
      await expect(page.locator('#step-heading')).toHaveText('Add a pass or fail rule');
      await page.locator('#row-1-threshold').fill('The update is clear and good');
      await page.locator('#row-2-threshold').fill('Passes if the labels Alpha and Beta both appear');
      await saveWorksheet(page);
      await expect(page.locator('#threshold-notes li')).toHaveCount(1);
      expect(await sideways(page), `thresholds ${theme} ${width}`).toBeLessThanOrEqual(0);
      expect(await textContrast(page, '#threshold-notes li'), `${theme} ${width} notes`).toBeGreaterThanOrEqual(4.5);
      await saveShot(page, `notes-${theme}-${width}`, '#threshold-notes');
    }
  }
});

test('every panel fits at three widths in both themes and at the largest text size, stacks its rows, and its new text is readable', async ({ page, request }) => {
  test.setTimeout(480000);
  const stops = [
    ['draft', 'Draft your criteria', '#ws-row-1', true],
    ['thresholds', 'Add a pass or fail rule', '#ws-row-1', false],
    ['test-file', 'Write your test cases down', '#file-editor', false],
    ['reference', 'Compare with an example', '.ref-card', false],
  ];
  const prepare = async (reach) => {
    await control(request, '/control/reset', { scenario: 'ready', part1_reach: reach === 'draft' ? 'rewrite' : undefined, reach2: reach === 'reference' ? 'reference' : reach });
  };
  for (const theme of ['light', 'dark']) {
    for (const width of [1280, 900, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const [reach, heading, anchor, fills] of stops) {
        await prepare(reach);
        await page.goto(`/?t=${TOKEN}`);
        await page.evaluate((value) => window.localStorage.setItem('eval-coach-theme', value), theme);
        await page.reload();
        await page.locator('#series-open-part-2').click();
        await expect(page.locator('#step-heading')).toHaveText(heading);
        if (reach === 'test-file') await page.locator('#file-build').click();
        if (reach === 'draft') {
          await addRows(page, ROWS);
          await saveWorksheet(page);
        }
        if (reach === 'thresholds') {
          await page.locator('#row-1-threshold').fill('The update is clear');
          await saveWorksheet(page);
        }
        if (reach === 'test-file') {
          await expect(page.locator('#part-save-status')).toHaveText('Your file is saved.');
          const text = (await editorText(page)).replace('Word count under 100 passes', 'The update is clear').replace('### C3:', '### C3x:');
          await page.locator('#file-editor').fill(`${text}\n`);
          await page.locator('#part-save').click();
          await expect(page.locator('#findings-notes')).toBeVisible();
        }
        await expect(page.locator(anchor).first()).toBeVisible();
        expect(await sideways(page), `${reach} ${theme} ${width}`).toBeLessThanOrEqual(0);
        if (reach === 'draft' || reach === 'thresholds') {
          const boxes = await page.locator('#ws-row-1 .ws-cell, #ws-row-1 .ws-facts > div').evaluateAll((els) => els.map((e) => e.getBoundingClientRect().top));
          if (width < 1100) expect(new Set(boxes.map((t) => Math.round(t))).size, `${reach} ${width} stacks`).toBe(boxes.length);
        }
        if (reach === 'reference' && width < 1100) {
          const tops = await page.locator('.ref-card').first().locator('label.radio-card').evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
          expect(new Set(tops).size, `reference options stack at ${width}`).toBe(tops.length);
        }
        for (const selector of ['.step-page .lede', '.hint', '.field-label', '.ref-fact dt', '.ref-fact dd', '.ref-mine li', '.callout', '.callout h3', '#findings-blocking li', '#findings-notes li', '#threshold-notes li', '.ws-row legend', '.ws-ticks .check-row', '.radio-card']) {
          if ((await page.locator(selector).count()) === 0) continue;
          expect(await textContrast(page, selector), `${reach} ${theme} ${width} ${selector}`).toBeGreaterThanOrEqual(4.5);
        }
        if (fills || reach === 'reference') await expect(page.locator('.step-page')).toBeVisible();
        await saveShot(page, `${reach}-${theme}-${width}`, anchor);
      }
    }
  }
  for (const [reach, heading, anchor] of stops) {
    await page.setViewportSize({ width: 1280, height: 900 });
    await prepare(reach);
    await page.goto(`/?t=${TOKEN}`);
    await page.evaluate(() => window.localStorage.setItem('eval-coach-text-size', '150'));
    await page.reload();
    await page.locator('#series-open-part-2').click();
    await expect(page.locator('#step-heading')).toHaveText(heading);
    if (reach === 'test-file') await page.locator('#file-build').click();
    if (reach === 'draft') await addRows(page, ROWS);
    await expect(page.locator(anchor).first()).toBeVisible();
    expect(await sideways(page), `${reach} largest text`).toBeLessThanOrEqual(0);
    await saveShot(page, `${reach}-largest-text`, anchor);
  }
});
