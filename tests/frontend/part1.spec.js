// Part 1's interface, tested against the real app (real_server.py): the real engine, course content and server,
// with a pseudo console that starts nothing. A test plays the part of the CLI by writing output.txt through the
// control port.
const { test: base, expect } = require('./.tmp/node_modules/@playwright/test');
const path = require('path');

const TOKEN = 'dev-token';
const PORT = Number(process.env.PART1_TEST_PORT) || 38927;
const CONTROL = `http://127.0.0.1:${PORT + 1}`;
const SHOTS = path.join(__dirname, '.tmp', 'screenshots');
const CSP_WORDS = /content security policy|refused to|csp/i;
const FRAMEWORK_WORDS = /framework|RTCC|RISE|CO-STAR|RISEN|bucket/i;

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

async function files(request) {
  return (await request.get(`${CONTROL}/control/files`)).json();
}

async function readFile(request, name) {
  return (await (await request.get(`${CONTROL}/control/read?name=${name}`)).json()).text;
}

// Starts a fresh app, optionally with everything before `reach` already done, and opens Part 1 from the Series map.
async function openPart1(page, request, opts = {}) {
  await control(request, '/control/reset', { scenario: opts.scenario || 'ready', reach: opts.reach, answer: opts.answer });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-1').click();
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
      if (c.length === 3 || c[3] === 1) {
        bg = c.slice(0, 3);
        break;
      }
      if (c[3] > 0) {
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
  await page.screenshot({ path: path.join(SHOTS, `part1-${name}.png`) });
}

// Types a prompt, saves it and checks the file the app wrote.
async function savePrompt(page, text) {
  await page.locator('#prompt-editor').fill(text);
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your prompt is saved.');
}

// ---- Part 1 in the app ----------------------------------------------------------------

test('opening Part 1 shows its own header, course list and groups, and Part 3 keeps its own; Back works from both', async ({ page, request }) => {
  await openPart1(page, request);
  await expect(page.locator('.brand-sub')).toHaveText('Part 1 · Structured prompting');
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  expect(await page.locator('.course-group').allTextContents()).toEqual([
    'Start with your own words',
    'Name the gaps',
    'Try a framework',
    'Keep it and reuse it',
  ]);
  await expect(page.locator('.course-item')).toHaveCount(9);
  expect(await page.locator('.course-item-title').allTextContents()).toEqual([
    'Your mission',
    'Write it your way',
    'Score what you got',
    'What your first prompt left out',
    'Frameworks: ready-made labels for what a prompt needs',
    'Try a framework',
    'Score it again',
    'Four ways a structured prompt helps you',
    'Use it on your own work',
  ]);
  await page.locator('#back-to-series').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-3').click();
  await expect(page.locator('.brand-sub')).toHaveText('Part 3 · Running evals and baseline');
  await expect(page.locator('.course-group').first()).toHaveText('Why check AI work');
  await expect(page.locator('.course-item')).toHaveCount(16);
  await page.locator('#back-to-series').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-1').click();
  await expect(page.locator('.brand-sub')).toHaveText('Part 1 · Structured prompting');
  await expect(page.locator('.course-item')).toHaveCount(9);
});

test('the mission page is one page with no map of the Parts, no questions and no framework names', async ({ page, request }) => {
  await openPart1(page, request);
  await expect(page.locator('.route-stop')).toHaveCount(0);
  const body = await page.locator('.lesson-body').innerText();
  expect(body).not.toMatch(FRAMEWORK_WORDS);
  expect(body).toContain('for practice only and never something to submit');
  await expect(page.getByRole('heading', { name: 'Test what you know' })).toHaveCount(0);
  await page.locator('#lesson-continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Write it your way');
});

test('the cold step shows the scenario card and no coaching, and cannot start before a prompt is saved', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'cold' });
  await expect(page.locator('#step-heading')).toHaveText('Write it your way');
  const card = page.locator('#scenario-card');
  await expect(card.locator('li')).toHaveCount(5);
  await expect(card).toContainText('Teams message');
  await expect(card).toContainText('under 150 words');
  await expect(card.locator('#scenario-notes')).toContainText('Mon: standup and two Northwind client meetings');
  await expect(page.locator('#prompt-editor')).toHaveValue('');
  await expect(page.locator('#part-save')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#cli-start')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#cli-start')).toHaveText('Open a new AI chat');
  await expect(page.locator('#cli-start-blocked')).toContainText('Save your prompt first');
  await expect(page.locator('#run-paste-empty')).toBeVisible();
  await expect(page.locator('#copy-paste')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#run-output-empty')).toBeVisible();
  await expect(page.locator('#cli-chat-note')).toContainText('Each step opens a new chat');
  for (const id of ['#cli-send', '#cli-retry', '.term-line', '#check-work']) await expect(page.locator(id)).toHaveCount(0);
  const text = await page.locator('.step-page').innerText();
  expect(text).not.toMatch(FRAMEWORK_WORDS);
  expect(text).not.toMatch(/Stage 3/);
});

test('the cold step: saving opens the AI window by itself, Copy gives the text to paste, and the captured answer finishes the step', async ({ page, request }) => {
  await page.addInitScript(() => {
    window.__copied = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: (text) => { window.__copied.push(text); return Promise.resolve(); } }, configurable: true });
  });
  await openPart1(page, request, { reach: 'cold' });
  const words = 'Please write my Friday update.';
  await page.locator('#prompt-editor').fill(words);
  await expect(page.locator('#part-save-status')).toHaveText('You have changes that are not saved yet.');
  await expect(page.locator('#part-save')).not.toHaveAttribute('aria-disabled', 'true');
  expect((await files(request)).launched).toEqual([]);
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your prompt is saved.');
  expect(await readFile(request, 'prompt-cold.md')).toBe(words);
  expect((await files(request)).part1).toEqual(['prompt-cold.md']);
  await expect.poll(async () => (await files(request)).launched.length).toBe(1);
  await expect(page.locator('.term-status')).toHaveText('Your AI is running.');
  expect((await files(request)).cold_work).toEqual(['prompt.md']);
  const paste = page.locator('#run-paste');
  await expect(paste).toContainText(words);
  await expect(paste).toContainText('Rough notes (added by the app)');
  await expect(paste).toContainText('Mon: standup and two Northwind client meetings');
  await expect(paste).toContainText('Save only your answer to output.txt. Do nothing else.');
  await expect(page.locator('#cli-start')).toHaveText('Open a new AI chat');
  await expect(page.locator('#cli-start')).not.toHaveAttribute('aria-disabled', 'true');
  for (const id of ['#cli-send', '#cli-retry', '#model-name', '#check-work']) await expect(page.locator(id)).toHaveCount(0);
  await expect(page.getByRole('radio', { name: 'Sonnet' })).toBeChecked();

  await page.locator('#copy-paste').click();
  await expect(page.locator('#copy-status')).toContainText('Copied');
  const [copied] = await page.evaluate(() => window.__copied);
  expect(copied).toBe(await paste.textContent());
  expect(copied.startsWith(words)).toBe(true);
  expect(copied.endsWith('Do nothing else.\n')).toBe(true);

  const html = '<b>bold</b> <script>window.__xss = 1</script>';
  await control(request, '/control/output', { step: 'cold', text: html });
  const output = page.locator('#run-output');
  await expect(output).toHaveText(html);
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
  await expect(output.locator('b')).toHaveCount(0);
  await expect(page.locator('#continue')).toHaveText('Continue to: Score what you got');
  await expect(page.locator('#check-work')).toHaveCount(0);
  expect((await files(request)).typed).toEqual([]);
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
});

test('a browser that refuses the clipboard leaves the text selected and says how to copy it', async ({ page, request }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('denied')) }, configurable: true });
  });
  await openPart1(page, request, { reach: 'cold' });
  await savePrompt(page, 'Please write my Friday update with <angle> brackets.');
  await expect(page.locator('#run-paste')).toContainText('<angle> brackets');
  await expect(page.locator('#run-paste').locator('angle')).toHaveCount(0);
  await page.locator('#copy-paste').click();
  await expect(page.locator('#copy-status')).toContainText('Ctrl+C');
  const selected = await page.evaluate(() => window.getSelection().toString());
  expect(selected).toContain('Please write my Friday update with <angle> brackets.');
});

test('the cold step lists what is missing as the participant works, with no Check button', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'cold' });
  const items = page.locator('.check-items li');
  await expect(items).toHaveCount(3);
  await expect(page.locator('#gate-heading')).toHaveText('What is still missing');
  await expect(items.nth(0).locator('.check-mark')).toHaveText('Not yet');
  await page.locator('#prompt-editor').fill('An unsaved prompt.');
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your prompt is saved.');
  await expect(items.nth(0).locator('.check-mark')).toHaveText('OK');
  await expect(items.nth(1).locator('.check-mark')).toHaveText('Not yet');
  await expect(items.nth(2).locator('.check-mark')).toHaveText('OK');
  await expect(page.locator('#check-work')).toHaveCount(0);
  await expect(page.locator('#continue')).toHaveCount(0);
});

test('a finished cold step shows its prompt and answer, offers no second run and offers to start the step again', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'score' });
  await page.locator('.course-btn', { hasText: 'Write it your way' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Write it your way');
  await expect(page.locator('#prompt-editor')).toHaveValue('Please turn my notes into a Friday update for my lead.');
  await expect(page.locator('#run-output')).toContainText('Update for Friday.');
  await expect(page.locator('#cli-start')).toHaveCount(0);
  await expect(page.locator('#part-save')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#prompt-editor')).toBeDisabled();
  await expect(page.locator('#step-restart')).toHaveText('Start this step again');
});

test('the score form works by keyboard, counts n of 5 from the answers, and changes its question when all five are yes', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'score' });
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
  await expect(page.locator('#score-output')).toContainText('Update for Friday.');
  await expect(page.locator('#score-row-r1 input')).toHaveCount(2);
  await expect(page.locator('#score-line')).toHaveText('Answer all five to see your score.');
  // Keyboard: focus the first radio, check it with Space, and move along the group with the arrow keys.
  await page.locator('#score-row-r1 input[value="yes"]').focus();
  await page.keyboard.press('Space');
  await expect(page.locator('#score-row-r1 input[value="yes"]')).toBeChecked();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#score-row-r1 input[value="no"]')).toBeChecked();
  for (const id of ['r2', 'r3', 'r4', 'r5']) {
    await page.locator(`#score-row-${id} input[value="yes"]`).focus();
    await page.keyboard.press('Space');
  }
  await expect(page.locator('#score-line')).toHaveText('Your score: 4 of 5');
  await expect(page.locator('#score-gap')).toHaveValue('');
  await expect(page.locator('label[for="score-gap"]')).toHaveText('One thing the answer got wrong or missed');
  await page.locator('#score-row-r1 input[value="yes"]').check();
  await expect(page.locator('#score-line')).toHaveText('Your score: 5 of 5');
  await expect(page.locator('label[for="score-gap"]')).toHaveText('What did your prompt include that helped the answer meet all five?');
  await page.locator('#score-row-r5 input[value="no"]').check();
  await expect(page.locator('label[for="score-gap"]')).toHaveText('One thing the answer got wrong or missed');
  await expect(page.locator('#score-line')).toHaveText('Your score: 4 of 5');
});

test('the score list shows what is missing, never judges the answers, and Continue finishes the step only when everything is in', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'score' });
  await expect(page.locator('#check-work')).toHaveCount(0);
  await expect(page.locator('.check-items li')).toHaveCount(3);
  await expect(page.locator('.check-items li').nth(0)).toContainText('0 of 5 are answered');
  await expect(page.locator('#continue')).toHaveText('Continue to: What your first prompt left out');
  await expect(page.locator('#continue')).toHaveAttribute('aria-disabled', 'true');
  for (const id of ['r1', 'r2', 'r3', 'r4', 'r5']) await page.locator(`#score-row-${id} input[value="no"]`).check();
  await expect(page.locator('.check-items li').nth(0)).toContainText('OK');
  await expect(page.locator('#continue')).toHaveAttribute('aria-disabled', 'true');
  await page.locator('#score-gap').fill('It never said what I need from my lead.');
  await page.locator('#in-prompt input[value="no"]').check();
  await expect(page.locator('#score-line')).toHaveText('Your score: 0 of 5');
  await expect(page.locator('.check-items li.is-missing')).toHaveCount(0);
  await expect(page.locator('#continue')).not.toHaveAttribute('aria-disabled', 'true');
  // Typing is never cut off: the answers autosave and the step stays open until the participant presses Continue.
  await page.locator('#score-gap').fill('It never said what I need from my lead, and it was too long.');
  await expect(page.locator('#continue-hint')).toBeVisible();
  await page.waitForTimeout(1500);
  await expect(page.locator('#score-gap')).toBeEnabled();
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
  await page.locator('#continue').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#step-heading')).toHaveText('What your first prompt left out');
  await page.locator('.course-btn', { hasText: 'Score what you got' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
  await expect(page.locator('#score-gap')).toHaveValue('It never said what I need from my lead, and it was too long.');
  await expect(page.locator('#score-gap')).toBeDisabled();
  await expect(page.locator('.step-question, #act-title-sc-score')).toBeVisible();
});

test('the gaps lesson sorts typical gaps into five numbered kinds with a set-aside group and unlimited retries', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'p1-gaps' });
  await expect(page.locator('#step-heading')).toHaveText('What your first prompt left out');
  const body = await page.locator('.lesson-body').innerText();
  expect(body).not.toMatch(/framework|RTCC|RISE/i);
  const rows = page.locator('.sort-row');
  await expect(rows).toHaveCount(11);
  const options = await rows.first().locator('select option').allTextContents();
  expect(options).toEqual([
    'Choose a group',
    '1. Who the AI should act as',
    '2. What exactly to produce',
    '3. Background it needs',
    '4. Limits and format',
    '5. What a good result looks like',
    'Set aside for later Parts',
  ]);
  for (const row of await rows.all()) await row.locator('select').selectOption({ index: 1 });
  await page.locator('#submit-gaps-sort').click();
  await expect(page.getByText(/of 11 are in the right group/)).toBeVisible();
  await page.locator('#lesson-continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Frameworks: ready-made labels for what a prompt needs');
});

test('the rewrite step offers three equal label sets with none chosen, inserts a skeleton, and confirms before replacing text', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'rewrite' });
  await expect(page.locator('#step-heading')).toHaveText('Try a framework');
  const cards = page.locator('#label-sets .radio-card');
  await expect(cards).toHaveCount(3);
  expect(await cards.locator('input:checked').count()).toBe(0);
  const descriptions = await cards.locator('.hint').allTextContents();
  expect(new Set(descriptions.map((d) => d.trim().split(/\s+/).length)).size).toBe(1);
  await expect(page.locator('#insert-labels')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#insert-hint')).toBeVisible();

  await cards.nth(0).locator('input').check();
  await expect(page.locator('#insert-labels')).not.toHaveAttribute('aria-disabled', 'true');
  await page.locator('#insert-labels').click();
  const editor = page.locator('#prompt-editor');
  await expect(editor).toHaveValue(/^Role: who the AI acts as\nTask: what to produce\nContext: the background it needs\nConstraints: limits and format$/);

  await editor.fill('Role: a consultant\nTask: my own words');
  await cards.nth(1).locator('input').check();
  await page.locator('#insert-labels').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog).toContainText('Replace your text?');
  await dialog.getByRole('button', { name: 'Keep my text' }).click();
  await expect(editor).toHaveValue('Role: a consultant\nTask: my own words');
  await page.locator('#insert-labels').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Replace with labels' }).click();
  await expect(editor).toHaveValue(/^Role: who the AI acts as\nInput:/);
  await expect(editor).toBeFocused();
  // The saved prompt changes only when the participant presses Save.
  expect(await files(request).then((f) => f.part1)).toEqual(['prompt-cold.md', 'output-cold.txt'].sort());
  await cards.nth(2).locator('input').check();
  await editor.fill('');
  await page.locator('#insert-labels').click();
  await expect(editor).toHaveValue(/^Who the AI acts as:/);
});

test('the rewrite step runs once in a new chat, fails an unchanged prompt, and notes a different model without blocking', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'rewrite' });
  const before = (await files(request)).launched.length;
  // The same words as the first prompt: saving opens the window, and the answer is captured but the list says why not.
  await page.locator('#label-sets .radio-card').nth(0).locator('input').check();
  await savePrompt(page, 'Please turn my notes into a Friday update for my lead.');
  await expect.poll(async () => (await files(request)).launched.length).toBe(before + 1);
  await control(request, '/control/output', { step: 'rewrite', text: 'A second answer.' });
  await expect(page.locator('#run-output')).toHaveText('A second answer.');
  await expect(page.locator('.check-items li').nth(2)).toContainText('same as your first one');
  await expect(page.locator('#gate-heading')).toHaveText('What is still missing');
  await expect(page.locator('#check-work')).toHaveCount(0);
  await expect(page.locator('#continue')).toHaveCount(0);
  await expect(page.locator('#model-note')).toHaveCount(0);

  // A new prompt is saved without opening another window. The toggle changes the model of the next chat, and the app
  // records it: a different model finishes the step with a note.
  await savePrompt(page, 'Role: a consultant\nTask: write the update\nContext: two clients\nConstraints: short');
  expect((await files(request)).launched.length).toBe(before + 1);
  await page.getByRole('radio', { name: 'Haiku' }).check();
  await expect.poll(async () => (await files(request)).model_preference).toBe('haiku');
  await page.locator('#cli-start').click();
  await expect.poll(async () => (await files(request)).launched.at(-1)).toEqual(['fake-cli', '--model', 'haiku']);
  await control(request, '/control/output', { step: 'rewrite', text: 'A third answer.' });
  await expect(page.locator('#run-output')).toHaveText('A third answer.');
  await expect(page.locator('#model-note')).toContainText('different model');
  await expect(page.locator('#model-note')).toContainText('less fair');
  await expect(page.locator('#continue')).toHaveText('Continue to: Score it again');
  expect(await readFile(request, 'prompt-framework.md')).toContain('Role: a consultant');
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Score it again');
});

test('a running AI window asks before a new chat replaces it, and keeping it changes nothing', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'cold' });
  await savePrompt(page, 'Please write my Friday update.');
  await expect.poll(async () => (await files(request)).launched.length).toBe(1);
  await expect(page.locator('.term-status')).toHaveText('Your AI is running.');
  await expect(page.locator('#cli-stop')).not.toHaveAttribute('aria-disabled', 'true');
  await page.locator('#cli-start').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog).toContainText('Open a new AI chat?');
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  expect((await files(request)).launched.length).toBe(1);
  await page.locator('#cli-start').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Open a new chat' }).click();
  await expect.poll(async () => (await files(request)).launched.length).toBe(2);
});

test('the compare puts both runs side by side on a wide screen and stacks them in the mid and narrow layouts', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openPart1(page, request, { reach: 'rescore' });
  await expect(page.locator('#step-heading')).toHaveText('Score it again');
  for (const id of ['r1', 'r2', 'r3', 'r4']) await page.locator(`#score-row-${id} input[value="yes"]`).check();
  await page.locator('#score-row-r5 input[value="no"]').check();
  await expect(page.locator('#compare-change')).toHaveText('Your score went up by 2.');
  await expect(page.locator('#compare-notes')).toContainText('One run each cannot show how much answers vary');
  await expect(page.locator('#compare-notes')).not.toContainText('A lower second score can happen');
  const first = page.locator('#compare-first');
  const second = page.locator('#compare-second');
  await expect(first).toContainText('Please turn my notes into a Friday update for my lead.');
  await expect(first).toContainText('Update for Friday.');
  await expect(first).toContainText('Score: 2 of 5');
  await expect(second).toContainText('Role: a consultant');
  await expect(second).toContainText('Score: 4 of 5');
  for (const [width, stacked] of [[1280, false], [900, true], [390, true]]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(200);
    const a = await first.boundingBox();
    const b = await second.boundingBox();
    if (stacked) {
      expect(b.y, `stacked at ${width}`).toBeGreaterThanOrEqual(a.y + a.height - 1);
      expect(Math.abs(a.x - b.x)).toBeLessThan(2);
    } else {
      expect(Math.abs(a.y - b.y), `side by side at ${width}`).toBeLessThan(2);
      expect(b.x).toBeGreaterThan(a.x + a.width - 2);
    }
    expect(await sideways(page), `sideways at ${width}`).toBeLessThanOrEqual(0);
  }
});

test('a lower second score is explained without blaming the labels, and the written answers are listed until they are in', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'rescore' });
  for (const id of ['r1', 'r2', 'r3', 'r4', 'r5']) await page.locator(`#score-row-${id} input[value="no"]`).check();
  await expect(page.locator('#compare-change')).toHaveText('Your score went down by 2.');
  await expect(page.locator('#compare-notes')).toContainText('A lower second score can happen');
  await expect(page.locator('#compare-notes')).toContainText('still missing');
  await expect(page.locator('#check-work')).toHaveCount(0);
  await expect(page.locator('.check-items li').nth(1)).toContainText('Write what your labels made you add');
  await expect(page.locator('#continue')).toHaveAttribute('aria-disabled', 'true');
  await page.locator('#reflection-added').fill('The reader and the length.');
  await page.locator('#reflection-better').fill('It is not better; the ask is still missing.');
  await expect(page.locator('.check-items li.is-missing')).toHaveCount(0);
  await expect(page.locator('#continue')).toHaveText('Continue to: Four ways a structured prompt helps you');
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Four ways a structured prompt helps you');
  await page.locator('.course-btn', { hasText: 'Score it again' }).click();
  await expect(page.locator('#act-title-sc-rescore')).toBeVisible();
  await expect(page.locator('#step-question, section[data-key="step-question"]').first()).toContainText('Quick check');
});

test('the benefits lesson shows the sample prompts only after the rescore step', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'p1-benefits' });
  await expect(page.locator('#step-heading')).toHaveText('Four ways a structured prompt helps you');
  const sources = page.locator('.source-list');
  await expect(sources).toContainText('Sample prompt with RTCC labels');
  await expect(sources).toContainText('Sample prompt with RISE labels');
  await expect(page.locator('.lesson-body')).toContainText('Give the AI what it needs. Use a framework, or build your own.');
  await expect(page.locator('.lesson-body')).toContainText('Stage 3 note (optional).');
  const open = sources.getByRole('button', { name: /Open/ }).first();
  await open.click();
  await expect(page.locator('dialog')).toContainText('Role:');
  await page.keyboard.press('Escape');
});

test('the own step has no Start control, says what is private, and saving everything finishes it and Part 1', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'own' });
  await expect(page.locator('#step-heading')).toHaveText('Use it on your own work');
  await expect(page.locator('#cli-start')).toHaveCount(0);
  await expect(page.locator('#cli-send')).toHaveCount(0);
  await expect(page.locator('#own-privacy')).toContainText('Leave out anything confidential');
  await expect(page.locator('#own-privacy')).toContainText('stays on this computer');
  await expect(page.locator('#check-work')).toHaveCount(0);
  await expect(page.locator('.check-items li.is-missing')).toHaveCount(3);
  await page.locator('#own-before').fill('Write my weekly report.');
  await page.locator('#own-after').fill('Role: analyst\nTask: write my weekly report');
  await page.locator('#own-labels').fill('RTCC');
  await page.locator('#part-save').click();
  await expect(page.locator('#part-save-status')).toHaveText('Your work is saved.');
  expect(await readFile(request, 'own-before.md')).toBe('Write my weekly report.');
  expect(await readFile(request, 'own-after.md')).toBe('Role: analyst\nTask: write my weekly report');
  await expect(page.locator('#own-before')).toBeDisabled();
  await expect(page.locator('#step-restart')).toBeVisible();
  await page.locator('#back-to-series').click();
  await expect(page.locator('#series-part-1')).toContainText('Done');
  await expect(page.locator('#series-part-1 .series-count')).toHaveText('9 of 9 done');
  await page.locator('#series-open-part-1').click();
  await expect(page.locator('#step-heading')).toHaveText('You have finished Part 1');
  await expect(page.locator('.finished-page')).toContainText('Part 2');
  await expect(page.locator('.finished-page')).toContainText('clear pass or fail rules');
});

test('a finished step offers Start this step again: keeping everything changes nothing and the keep action has focus', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'rescore' });
  await page.locator('.course-btn', { hasText: 'Score what you got' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
  await page.locator('#step-restart').focus();
  await page.keyboard.press('Enter');
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog).toContainText('Start this step again?');
  await expect(dialog.locator('#restart-lead')).toContainText('Score what you got, Try a framework, Score it again and Use it on your own work');
  await expect(dialog.locator('#restart-keeps')).toContainText('The steps before this one, your other Parts and your lesson progress');
  await expect(dialog.locator('#restart-backup-note')).toContainText('reset-backup');
  await expect(dialog.locator('#restart-backup-note')).toContainText('replaces the previous backup');
  await expect(dialog.getByRole('button', { name: 'Keep everything' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('dialog.confirm[open]')).toHaveCount(0);
  expect((await files(request)).part1).toEqual(['output-cold.txt', 'output-framework.txt', 'prompt-cold.md', 'prompt-framework.md']);
  await expect(page.locator('#step-restart')).toBeVisible();
  await expect(page.locator('#score-gap')).toHaveValue('No ask for my lead');
});

test('restarting a step clears it and the later steps, keeps the earlier ones, backs up the files and announces the result', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'own' });
  await page.locator('.course-btn', { hasText: 'Score what you got' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
  await page.locator('#step-restart').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Start again' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Score what you got');
  await expect(page.locator('#restart-result')).toContainText('Score what you got, Try a framework, Score it again and Use it on your own work will start again');
  await expect(page.locator('#restart-result')).toHaveAttribute('role', 'status');
  await expect(page.locator('#score-gap')).toBeEnabled();
  await expect(page.locator('#score-gap')).toHaveValue('');
  await expect(page.locator('#step-restart')).toHaveCount(0);
  await expect(page.locator('#continue')).toHaveAttribute('aria-disabled', 'true');
  const after = await files(request);
  expect(after.part1).toEqual(['output-cold.txt', 'prompt-cold.md']);
  expect(after.backup).toEqual(expect.arrayContaining(['project/part-1/prompt-framework.md', 'project/part-1/output-framework.txt']));
  expect(after.backup.some((name) => name.startsWith('project/part-1/prompt-cold'))).toBe(false);
  // The next step is locked again until this one is done, and the earlier step stays a finished record.
  const locked = page.locator('.course-btn', { hasText: 'Try a framework' });
  await expect(locked).toHaveAttribute('aria-disabled', 'true');
  await expect(locked).toContainText('Not started');
  await page.locator('.course-btn', { hasText: 'Write it your way' }).click();
  await expect(page.locator('#run-output')).toContainText('Update for Friday.');
  await expect(page.locator('#step-restart')).toBeVisible();
});

test('Start this step again is not offered on a step that is not finished, and a later step cannot be opened', async ({ page, request }) => {
  await openPart1(page, request, { reach: 'cold' });
  await expect(page.locator('#step-heading')).toHaveText('Write it your way');
  await expect(page.locator('#step-restart')).toHaveCount(0);
  await expect(page.locator('.course-btn', { hasText: 'Score what you got' })).toHaveAttribute('aria-disabled', 'true');
  await page.locator('.course-btn', { hasText: 'Score what you got' }).click({ force: true });
  await expect(page.locator('#step-heading')).toHaveText('Write it your way');
  await expect(page.locator('#step-restart')).toHaveCount(0);
});

test('before setup the next step can be read, and nothing in it can be saved or started', async ({ page, request }) => {
  await control(request, '/control/reset', { scenario: 'no-setup' });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await page.locator('#pf-skip').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#series-open-part-1').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await page.locator('#lesson-continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Write it your way');
  await expect(page.locator('#preview-note')).toBeVisible();
  await expect(page.locator('#preview-setup')).toBeVisible();
  for (const id of ['#part-save', '#prompt-editor', '#cli-start', '#cli-send', '#check-work']) await expect(page.locator(id)).toHaveCount(0);
  await expect(page.locator('.step-page')).toContainText('Write a prompt in your own words');
  await expect(page.locator('.course-btn', { hasText: 'Score what you got' })).toHaveAttribute('aria-disabled', 'true');
});

test('after setup a later Part 1 lesson and step are locked and cannot be opened', async ({ page, request }) => {
  await openPart1(page, request);
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  for (const title of ['Score what you got', 'What your first prompt left out']) {
    const button = page.locator('.course-btn', { hasText: title });
    await expect(button).toHaveAttribute('aria-disabled', 'true');
    await expect(button).toContainText('Not started');
    await button.click({ force: true });
    await expect(page.locator('#step-heading')).toHaveText('Your mission');
  }
  await expect(page.locator('#preview-note')).toHaveCount(0);
});

test('the new text styles are readable in both themes and every panel fits at three widths and the largest text size', async ({ page, request }) => {
  test.setTimeout(420000);
  const stops = [
    ['cold', 'Write it your way', '#scenario-card'],
    ['score', 'Score what you got', '#score-row-r1'],
    ['rewrite', 'Try a framework', '#label-sets'],
    ['rescore', 'Score it again', '#compare'],
    ['own', 'Use it on your own work', '#own-privacy'],
  ];
  for (const theme of ['light', 'dark']) {
    for (const width of [1280, 900, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const [reach, heading, anchor] of stops) {
        await control(request, '/control/reset', { scenario: 'ready', reach });
        await page.goto(`/?t=${TOKEN}`);
        await page.evaluate((value) => window.localStorage.setItem('eval-coach-theme', value), theme);
        await page.reload();
        await page.locator('#series-open-part-1').click();
        await expect(page.locator('#step-heading')).toHaveText(heading);
        if (reach === 'rescore') await page.locator('#score-row-r1 input[value="yes"]').check();
        await expect(page.locator(anchor)).toBeVisible();
        expect(await sideways(page), `${reach} ${theme} ${width}`).toBeLessThanOrEqual(0);
        for (const selector of ['.step-page .lede', '.hint', '.field-label', '.mono-block', '.score-line, .compare-score, .callout']) {
          if ((await page.locator(selector).count()) === 0) continue;
          expect(await textContrast(page, selector), `${reach} ${theme} ${width} ${selector}`).toBeGreaterThanOrEqual(4.5);
        }
        if (theme === 'light' || width === 390) await saveShot(page, `${reach}-${theme}-${width}`, anchor);
      }
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await control(request, '/control/reset', { scenario: 'ready', reach: 'rescore' });
  await page.goto(`/?t=${TOKEN}`);
  await page.evaluate(() => window.localStorage.setItem('eval-coach-text-size', '150'));
  await page.reload();
  await page.locator('#series-open-part-1').click();
  await expect(page.locator('#step-heading')).toHaveText('Score it again');
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  await saveShot(page, 'rescore-largest-text', '#compare');
});
