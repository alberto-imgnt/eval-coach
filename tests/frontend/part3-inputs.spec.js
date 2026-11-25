// Part 3's "Choose your inputs" step in the interface, tested against the real app (real_server.py): the real engine,
// course content and server. The step starts no AI, so a test only sets up where the participant is through the
// control port and reads the files the app wrote.
const { test: base, expect } = require('./.tmp/node_modules/@playwright/test');
const path = require('path');

const TOKEN = 'dev-token';
const PORT = Number(process.env.PART1_TEST_PORT) || 38927;
const CONTROL = `http://127.0.0.1:${PORT + 1}`;
const SHOTS = path.join(__dirname, '.tmp', 'screenshots');
const CSP_WORDS = /content security policy|refused to|csp/i;
const TITLE = 'Choose your inputs';

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

async function readRoot(request, name) {
  return (await (await request.get(`${CONTROL}/control/readroot?name=${name}`)).json()).text;
}

async function readPart2(request, name) {
  return (await (await request.get(`${CONTROL}/control/read2?name=${name}`)).json()).text;
}

async function apiState(request, query) {
  const res = await request.get(`/api/state${query || ''}`, { headers: { 'X-Eval-Token': TOKEN } });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

// Starts a fresh app (demo access on, so every Part is open), optionally with Parts 1 and 2 finished, and opens the
// step from Part 3's course list.
async function gotoInputs(page) {
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Evaluated systems');
  await page.locator('#series-open-part-3').click();
  await page.locator('.course-item', { hasText: TITLE }).click();
  await expect(page.locator('#step-heading')).toHaveText(TITLE);
  // The step sits in the "Collect answers" group with its neighbours, so that heading is not repeated.
  const headings = await page.locator('.course-group').allTextContents();
  expect(new Set(headings).size).toBe(headings.length);
}

async function openInputs(page, request, earlier) {
  const body = { scenario: 'ready', reach3: 'inputs' };
  if (earlier) Object.assign(body, { part1_reach: 'own', reach2: null });
  await control(request, '/control/reset', body);
  await gotoInputs(page);
}

const sideways = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function saveShot(page, name) {
  await page.locator('.step-page .panel').first().evaluate((el) => el.scrollIntoView({ block: 'start' }));
  await page.waitForTimeout(450);
  await page.screenshot({ path: path.join(SHOTS, `part3-inputs-${name}.png`) });
}

const active = (page, key) => page.locator(`#inputs-${key} > p.hint`).first();
const choice = (page, key, id) => page.locator(`#inputs-${key} input[value="${id}"]`);

test('a Practice task project shows both files in full, labelled, with nothing to start and no lock-in yet', async ({ page, request }) => {
  await openInputs(page, request, false);
  await expect(page.locator('.course-item', { hasText: TITLE })).toHaveCount(1);
  for (const key of ['prompt', 'test_cases']) {
    await expect(active(page, key)).toContainText('Practice task');
    await expect(page.locator(`#inputs-${key}-text`)).not.toHaveText('');
    await expect(choice(page, key, 'practice')).toBeChecked();
    await expect(choice(page, key, 'practice')).toBeEnabled();
    await expect(choice(page, key, key === 'prompt' ? 'part1' : 'part2')).toBeDisabled();
  }
  // The earlier Parts are not finished, so the reasons are shown beside the choices.
  await expect(page.locator('#inputs-prompt')).toContainText('Finish the Part 1 step');
  await expect(page.locator('#inputs-test_cases')).toContainText('Finish the Part 2 step');
  await expect(page.locator('#continue')).toBeEnabled();
  await expect(page.locator('#inputs-prompt')).not.toContainText('Use both of my files');
  await expect(page.getByRole('button', { name: 'Use both of my files' })).toHaveCount(0);
  await expect(page.locator('#terminal-pane, .paste-box, #paste-line')).toHaveCount(0);
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  await saveShot(page, 'practice');
});

test('picking the Part 1 rewrite changes only the prompt, keeps a copy, and can be switched back', async ({ page, request }) => {
  await openInputs(page, request, true);
  const original = await readRoot(request, 'prompt-v0.md');
  const cases = await readRoot(request, 'test-cases.md');
  await expect(choice(page, 'prompt', 'part1')).toBeEnabled();
  await choice(page, 'prompt', 'part1').click();
  await expect(active(page, 'prompt')).toContainText('Your Part 1 rewrite');
  await expect(choice(page, 'prompt', 'part1')).toBeChecked();
  await expect(page.locator('#inputs-prompt-text')).toContainText('Role: a consultant');
  await expect(page.locator('#inputs-prompt-text')).toContainText('Rough notes');
  await expect(page.locator('#inputs-prompt-text')).not.toContainText('Save only your answer');
  expect(await readRoot(request, 'prompt-v0.md')).toContain('Role: a consultant');
  expect(await readRoot(request, 'test-cases.md')).toBe(cases);
  await choice(page, 'prompt', 'practice').click();
  await expect(choice(page, 'prompt', 'practice')).toBeChecked();
  expect(await readRoot(request, 'prompt-v0.md')).toBe(original);
  await saveShot(page, 'picked');
});

test('"Use both of my files" carries Part 1 and Part 2 forward, Continue opens the next step and the choice locks', async ({ page, request }) => {
  await openInputs(page, request, true);
  const part2 = await readPart2(request, 'test-cases.md');
  await page.getByRole('button', { name: 'Use both of my files' }).click();
  await expect(active(page, 'test_cases')).toContainText('Your Part 2 test cases');
  await expect(active(page, 'prompt')).toContainText('Your Part 1 rewrite');
  expect(await readRoot(request, 'test-cases.md')).toBe(part2);
  await expect(page.locator('#continue')).toBeEnabled();
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect((await apiState(request)).current_step).toBe('generate');
  // Reopening the finished step shows what was chosen, as information, and offers no change.
  await page.locator('.course-item', { hasText: TITLE }).click();
  await expect(page.locator('#step-heading')).toHaveText(TITLE);
  await expect(active(page, 'prompt')).toContainText('Your Part 1 rewrite');
  await expect(page.locator('#inputs-prompt')).toContainText('The chosen source is unchanged.');
  await expect(page.locator('#inputs-prompt input[type="radio"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Use both of my files' })).toHaveCount(0);
  const refused = await request.post('/api/step/submit', {
    headers: { 'X-Eval-Token': TOKEN, 'Content-Type': 'application/json' },
    data: { step: 'inputs', data: { use: { prompt: 'practice' } } },
  });
  expect(refused.ok()).toBeFalsy();
  expect(await readRoot(request, 'prompt-v0.md')).toContain('Role: a consultant');
});

test('a note appears when the prompt and test cases may be for different tasks, and it does not block Continue', async ({ page, request }) => {
  await openInputs(page, request, true);
  await choice(page, 'prompt', 'part1').click();
  await expect(choice(page, 'prompt', 'part1')).toBeChecked();
  const mismatch = page.locator('.callout-attn', { hasText: 'may be for different tasks' });
  await expect(mismatch).toHaveCount(0);
  await control(request, '/control/write2', {
    name: 'test-cases.md',
    text: (await readPart2(request, 'test-cases.md')).replace(/(## Test input\s*)[\s\S]*?(?=\n## )/, '$1- Something else entirely.\n'),
  });
  await gotoInputs(page);
  await choice(page, 'test_cases', 'part2').click();
  await expect(choice(page, 'test_cases', 'part2')).toBeChecked();
  await expect(mismatch).toBeVisible();
  await expect(page.locator('#continue')).toBeEnabled();
  await saveShot(page, 'mismatch');
});

test('text from a file is shown as text, never as markup', async ({ page, request }) => {
  await openInputs(page, request, true);
  await control(request, '/control/write2', {
    name: 'test-cases.md',
    text: `${await readPart2(request, 'test-cases.md')}\n<img src=x onerror="window.__inputs_xss = 1"><b id="inputs-injected">bold</b>\n`,
  });
  await gotoInputs(page);
  await choice(page, 'test_cases', 'part2').click();
  await expect(page.locator('#inputs-test_cases-text')).toContainText('<b id="inputs-injected">bold</b>');
  await expect(page.locator('#inputs-injected')).toHaveCount(0);
  expect(await page.evaluate(() => window.__inputs_xss)).toBeUndefined();
});

test('an unsuitable Part 2 file is not offered and the reason says why, while the Practice task stays available', async ({ page, request }) => {
  await openInputs(page, request, true);
  const full = await readPart2(request, 'test-cases.md');
  await control(request, '/control/write2', { name: 'test-cases.md', text: full.split('### C3:')[0] });
  await gotoInputs(page);
  await expect(choice(page, 'test_cases', 'part2')).toBeDisabled();
  await expect(page.locator('#inputs-test_cases')).toContainText('more');
  await expect(choice(page, 'test_cases', 'practice')).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Use both of my files' })).toHaveCount(0);
  await expect(page.locator('.step-page')).toContainText('cannot be your submission');
  await expect(page.locator('#inputs-test_cases')).not.toContainText('Check my files');
});

test('the step is readable on a narrow screen and in dark mode', async ({ page, request }) => {
  await openInputs(page, request, true);
  await page.setViewportSize({ width: 390, height: 800 });
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('#inputs-prompt-text')).toBeVisible();
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  await saveShot(page, 'narrow-dark');
});
