const { test: base, expect } = require('./.tmp/node_modules/@playwright/test');
const path = require('path');

const TOKEN = 'dev-token';
const SHOTS = path.join(__dirname, '.tmp', 'screenshots');
const CSP_WORDS = /content security policy|refused to|csp/i;
const PORT = process.env.UI_TEST_PORT || '38917';
const ORIGIN = `http://127.0.0.1:${PORT}`;

async function mock(request, route, data) {
  const res = await request.post(`/__mock/${route}`, {
    data: data || {},
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBeTruthy();
}

async function mockLog(request) {
  const res = await request.get('/__mock/log');
  return res.json();
}

const b64 = (bytes) => Buffer.from(bytes).toString('base64');

// Every test: fail on CSP errors or any request that leaves the app.
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

// The app opens on the Series map; this goes into Part 3 from there, as a participant does.
async function enterPart(page) {
  await page.locator('#series-open-part-3').click();
  await expect(page.locator('#series-list')).toHaveCount(0);
}

const opensOnMap = (scenario) => /^(pf-)?course/.test(scenario) && scenario !== 'course-first-run';

async function openApp(page, request, scenario, data) {
  await mock(request, 'reset', { scenario });
  if (data) await mock(request, 'set_data', data);
  await page.goto(`/?t=${TOKEN}`);
  if (opensOnMap(scenario)) await enterPart(page);
}

// Applies item changes before the page loads, so nothing depends on SSE timing.
async function openPreflight(page, request, changes, set, cli) {
  await mock(request, 'reset', { scenario: 'preflight' });
  if (set) await mock(request, 'pf_set', set);
  if (cli) await mock(request, 'pf_cli', cli);
  for (const [id, change] of Object.entries(changes || {})) await mock(request, 'pf_item', { id, changes: change });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
}

async function termText(page) {
  return page.locator('.xterm-rows').innerText();
}

// Moves the setup wizard to the page for an item: back to the first page, forward until at or past it, then back.
// Forward only goes to pages that still need the participant, so going back is what lands on a passed page.
async function wizardTo(page, id) {
  const enabled = async (button) => (await page.locator(button).getAttribute('aria-disabled')) !== 'true';
  const order = ['track', 'summary', 'python', 'node', 'promptfoo', 'cli', 'working_test', 'project', 'ai_window'];
  const rank = async () => {
    for (const name of order) if ((await page.locator(`#pf-item-${name}`).count()) > 0) return order.indexOf(name);
    return -1;
  };
  for (let i = 0; i < 10 && (await enabled('#wizard-back')); i += 1) await page.locator('#wizard-back').click();
  const target = order.indexOf(id);
  for (let i = 0; i < 10 && (await rank()) < target && (await enabled('#wizard-next')); i += 1) {
    await page.locator('#wizard-next').click();
    await page.waitForTimeout(50);
  }
  for (let i = 0; i < 10 && (await rank()) > target && (await enabled('#wizard-back')); i += 1) await page.locator('#wizard-back').click();
  await expect(page.locator(`#pf-item-${id}`)).toBeVisible();
}

// The last wizard page, Your AI window, ends setup. Finish goes to the first screen after setup.
async function finishWizard(page) {
  await expect(page.locator('#pf-item-ai_window')).toBeVisible();
  await page.locator('#wizard-finish').click();
}

test('token is removed from the URL and sent only as a header', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect(page.url()).toBe(ORIGIN + '/');
  const { log } = await mockLog(request);
  const stream = log.find((e) => e.path.startsWith('/api/terminal/stream'));
  expect(stream.path).toContain(`t=${TOKEN}`);
  const api = log.filter((e) => !e.path.startsWith('/api/terminal/stream'));
  expect(api.length).toBeGreaterThan(0);
  for (const entry of api) {
    expect(entry.path).not.toContain('t=');
    expect(entry.token_header).toBe(true);
  }
});

test('a reload keeps the token from sessionStorage and keeps it out of the URL', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect(await page.evaluate(() => sessionStorage.getItem('eval-coach-token'))).toBe(TOKEN);
  await page.reload();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect(page.url()).toBe(ORIGIN + '/');
  const { log } = await mockLog(request);
  const api = log.filter((e) => !e.path.startsWith('/api/terminal/stream'));
  expect(api.length).toBeGreaterThan(1);
  for (const entry of api) expect(entry.token_header).toBe(true);
});

test('if sessionStorage is blocked the app still works from the URL token', async ({ page, request }) => {
  await page.addInitScript(() => {
    const deny = () => {
      throw new DOMException('blocked', 'SecurityError');
    };
    Storage.prototype.setItem = deny;
    Storage.prototype.getItem = deny;
  });
  await openApp(page, request, 'generate');
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect(page.url()).toBe(ORIGIN + '/');
});

test('Start again works after the CLI was stopped', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
  await page.locator('#cli-stop').click();
  await expect(page.getByText('Your AI has stopped')).toBeVisible();
  await expect(page.locator('#cli-retry')).not.toHaveAttribute('aria-disabled', 'true');
  await page.locator('#cli-retry').click();
  await expect(page.getByText('Your AI is running.')).toBeVisible();
});

test('model toggle: shown in the step AI window head with the stored value, a plain note and an accessible name', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  const group = page.getByRole('radiogroup', { name: 'Model for your AI' });
  await expect(group).toBeVisible();
  await expect(group.getByRole('radio', { name: 'Sonnet' })).toBeChecked();
  await expect(group.getByRole('radio', { name: 'Haiku' })).not.toBeChecked();
  await expect(page.locator('#term-head')).toContainText('A change applies the next time your AI starts.');
  await expect(page.locator('#term-head')).not.toContainText('CLI');
  await page.screenshot({ path: path.join(SHOTS, 'model-toggle-step.png') });

  await group.getByRole('radio', { name: 'Haiku' }).check();
  await expect.poll(async () => (await postsTo(request, '/api/model')).map((e) => e.body)).toEqual([{ preference: 'haiku' }]);
  await expect(group.getByRole('radio', { name: 'Haiku' })).toBeChecked();
});

test('model toggle: reachable and changeable by keyboard alone', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  const sonnet = page.getByRole('radio', { name: 'Sonnet' });
  await sonnet.focus();
  await expect(sonnet).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect.poll(async () => (await postsTo(request, '/api/model')).map((e) => e.body)).toEqual([{ preference: 'haiku' }]);
  await expect(page.getByRole('radio', { name: 'Haiku' })).toBeChecked();
});

test('model toggle: a change while the AI runs does not touch the running window, and the other views show the same value', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  const before = (await mockLog(request)).log.filter((e) => e.path === '/api/step/start' || e.path === '/api/step/stop').length;
  await page.getByRole('radio', { name: 'Haiku' }).check();
  await expect.poll(async () => (await postsTo(request, '/api/model')).length).toBe(1);
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  expect((await mockLog(request)).log.filter((e) => e.path === '/api/step/start' || e.path === '/api/step/stop').length).toBe(before);
  await expect(page.locator('#ai-model-note')).toContainText('applies the next time your AI starts');

  await openCourse(page, request, 'course-main');
  await mock(request, 'ai_model', { preference: 'haiku' });
  await page.reload();
  await enterPart(page);
  await lessonReady(page);
  await expect(page.getByRole('radio', { name: 'Haiku' })).toBeChecked();
});

test('model toggle: shown beside the AI window on a lesson activity and on the setup working test page', async ({ page, request }) => {
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  await expect(page.locator('#term-head').getByRole('radiogroup', { name: 'Model for your AI' })).toBeVisible();
  await expect(page.locator('#term-head').getByRole('radio', { name: 'Sonnet' })).toBeChecked();

  await openPreflight(page, request, {
    cli: { status: 'passed', detail: 'Your AI started.', next: '' },
    signin: { status: 'passed', detail: 'Signed in.', next: '' },
    working_test: { status: 'needs_you', detail: 'Ready.', next: 'Press Start the test.' },
  });
  await wizardTo(page, 'working_test');
  await expect(page.locator('#term-head').getByRole('radiogroup', { name: 'Model for your AI' })).toBeVisible();
  await page.locator('#term-head').getByRole('radio', { name: 'Haiku' }).check();
  await expect.poll(async () => (await postsTo(request, '/api/model')).map((e) => e.body)).toEqual([{ preference: 'haiku' }]);
});

test('model toggle: hidden when the chosen AI has no model choice', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.getByRole('radiogroup', { name: 'Model for your AI' })).toBeVisible();
  await mock(request, 'ai_model', { available: false });
  await mock(request, 'emit_state');
  await expect(page.getByRole('radiogroup', { name: 'Model for your AI' })).toHaveCount(0);
  await expect(page.locator('#cli-start')).toBeVisible();
});

test('model toggle: fits a 390 pixel wide screen', async ({ browser, request }) => {
  const { context, page, errors } = await phonePage(browser);
  await openApp(page, request, 'generate');
  await expect(page.getByRole('radiogroup', { name: 'Model for your AI' })).toBeVisible();
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  expect(await layoutProblems(page)).toEqual([]);
  await page.screenshot({ path: path.join(SHOTS, 'model-toggle-phone.png') });
  expect(errors).toEqual([]);
  await context.close();
});

test('without a token the page shows a plain message and makes no API calls', async ({ page, request }) => {
  await mock(request, 'reset', { scenario: 'generate' });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Open eval-coach from its own link' })).toBeVisible();
  const { log } = await mockLog(request);
  expect(log.length).toBe(0);
});

test('preflight project item: prefills defaults, shows warnings, posts the contract', async ({ page, request }) => {
  await openApp(page, request, 'setup');
  await expect(page.getByLabel('Project folder')).toHaveValue('C:\\Users\\tester\\eval-project');
  await expect(page.getByText('Heads up: this folder has limited disk space.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();

  await page.getByLabel('Project folder').fill('C:\\Users\\tester\\OneDrive\\x');
  await expect(page.getByText('inside OneDrive')).toBeVisible();
  await page.getByLabel('Project folder').fill('C:\\work\\project');

  await page.getByRole('radio', { name: /My own task/ }).check();
  await expect(page.getByLabel('Path to your prompt file')).toBeVisible();
  await page.getByLabel('Path to your prompt file').fill('C:\\a\\prompt.md');
  await page.getByLabel('Path to your test cases file').fill('C:\\a\\tests.md');
  await page.getByRole('button', { name: 'Check my files' }).click();
  await expect(page.locator('#import-status')).toContainText('Your files look ready to import');
  await page.getByRole('button', { name: 'Set up my project' }).click();
  await finishWizard(page);

  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  const { log } = await mockLog(request);
  const setup = log.find((e) => e.path === '/api/setup');
  expect(setup.body).toEqual({
    project_path: 'C:\\work\\project',
    starter: 'own',
    prompt_path: 'C:\\a\\prompt.md',
    test_cases_path: 'C:\\a\\tests.md',
  });
  await expect(page.locator('.step-item')).toHaveCount(9);
  await expect(page.locator('.step-item.s-active')).toContainText('Now');
  await expect(page.locator('.step-item').nth(1)).toContainText('Not started');
  await expect(page.locator('.step-item').nth(1)).not.toContainText('Locked');
});

async function openImportScreen(page, request) {
  await openApp(page, request, 'setup');
  await page.getByLabel('Project folder').fill('C:\\work\\project');
  await page.getByRole('radio', { name: /My own task/ }).check();
}

test('import screen: the Practice task is only a ready-made example, and the copies are named in plain words', async ({ page, request }) => {
  await openApp(page, request, 'setup');
  await expect(page.locator('#northwind-note')).toContainText('The Practice task is a ready-made example');
  await expect(page.locator('#northwind-note')).toContainText('cannot be your submission');
  await expect(page.locator('#northwind-note')).toContainText('no way to submit it as your own work');
  await expect(page.locator('#import-copies')).toHaveCount(0);
  await page.getByRole('radio', { name: /My own task/ }).check();
  await expect(page.locator('#northwind-note')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Bring your own prompt and test cases' })).toBeVisible();
  await expect(page.locator('#import-copies')).toContainText('Your original files are not touched');
  await expect(page.locator('#import-copies')).toContainText('prompt-v0.md');
  await expect(page.locator('#import-copies')).toContainText('test-cases.md');
  await expect(page.locator('#import-copies')).toContainText('do not need to rename');
  await expect(page.locator('#import-first')).toContainText('Press Check my files before you set up your project.');
});

test('import screen: blocking problems stop setup, a changed path makes the result stale, a fixed file passes', async ({ page, request }) => {
  await openImportScreen(page, request);
  await page.getByLabel('Path to your prompt file').fill('C:\\nope\\prompt.md');
  await page.getByLabel('Path to your test cases file').fill('C:\\a\\few.md');
  await page.getByRole('button', { name: 'Check my files' }).click();
  await expect(page.locator('#import-status')).toContainText('cannot be imported yet');
  await expect(page.locator('#import-result')).toHaveClass(/callout-bad/);
  await expect(page.locator('#import-blocking')).toContainText('was not found at C:\\nope\\prompt.md');
  await expect(page.locator('#import-blocking')).toContainText('2 of the 3 criteria');
  await expect(page.locator('#import-blocking')).toContainText('press Check my files again');
  await expect(page.locator('#pf-project-submit')).toHaveAttribute('aria-disabled', 'true');

  // Pressing Enter in a path box while blocked checks again and never calls /api/setup.
  await page.getByLabel('Path to your test cases file').press('Enter');
  await expect(page.locator('#import-blocking')).toBeVisible();
  let { log } = await mockLog(request);
  expect(log.filter((e) => e.path === '/api/setup')).toHaveLength(0);
  expect(log.filter((e) => e.path === '/api/setup/import-check').length).toBeGreaterThanOrEqual(2);

  await page.getByLabel('Path to your prompt file').fill('C:\\a\\prompt.md');
  await expect(page.locator('#import-stale')).toContainText('You changed a path');
  await expect(page.locator('#import-result')).toHaveCount(0);
  await page.getByLabel('Path to your test cases file').fill('C:\\a\\tests.md');
  await page.getByRole('button', { name: 'Check my files' }).click();
  await expect(page.locator('#import-result')).toHaveClass(/callout-good/);
  await expect(page.locator('#import-status')).toContainText('Your files look ready to import');
  await expect(page.locator('#import-criteria li')).toHaveText(['C1 Length', 'C2 Order number', 'C3 Offer']);
  await expect(page.locator('#pf-project-submit')).not.toHaveAttribute('aria-disabled', 'true');

  await page.getByRole('button', { name: 'Set up my project' }).click();
  await finishWizard(page);
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  ({ log } = await mockLog(request));
  const check = log.filter((e) => e.path === '/api/setup/import-check').pop();
  expect(check.body).toEqual({ prompt_path: 'C:\\a\\prompt.md', test_cases_path: 'C:\\a\\tests.md', project_path: 'C:\\work\\project' });
  expect(log.filter((e) => e.path === '/api/setup')).toHaveLength(1);
});

test('import screen: warnings are shown with the NOT CHECKED guidance and do not stop setup', async ({ page, request }) => {
  await openImportScreen(page, request);
  await page.getByLabel('Path to your prompt file').fill('C:\\a\\prompt.md');
  await page.getByLabel('Path to your test cases file').fill('C:\\a\\vague.md');
  await page.getByRole('button', { name: 'Check my files' }).click();
  await expect(page.locator('#import-result')).toHaveClass(/callout-attn/);
  await expect(page.locator('#import-status')).toContainText('Read the notes below first');
  await expect(page.locator('#import-warnings li')).toHaveCount(2);
  await expect(page.locator('#import-warnings')).toContainText('will show as NOT CHECKED and count as not covered');
  await expect(page.locator('#import-warnings')).toContainText('a number, a list of terms you choose, or a label');
  await expect(page.locator('#import-blocking')).toHaveCount(0);
  await page.getByRole('button', { name: 'Set up my project' }).click();
  await finishWizard(page);
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
});

test('import screen at a narrow width: nothing overflows and every control stays reachable', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await openImportScreen(page, request);
  await page.getByLabel('Path to your prompt file').fill('C:\\Users\\someone\\Documents\\a-very-long-folder-name\\another-long-folder-name\\nope\\prompt.md');
  await page.getByLabel('Path to your test cases file').fill('C:\\Users\\someone\\Documents\\a-very-long-folder-name\\few.md');
  await page.locator('#pf-import-check').scrollIntoViewIfNeeded();
  await page.locator('#pf-import-check').click();
  await expect(page.locator('#import-blocking')).toBeVisible();
  const overflow = () => page.evaluate(() => ({
    doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    main: document.getElementById('screen-main').scrollWidth - document.getElementById('screen-main').clientWidth,
  }));
  expect(await overflow()).toEqual({ doc: 0, main: 0 });
  const box = await page.locator('#import-result').boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: path.join(SHOTS, 'import-narrow-blocked.png') });

  await page.getByLabel('Path to your prompt file').fill('C:\\a\\prompt.md');
  await page.getByLabel('Path to your test cases file').fill('C:\\a\\vague.md');
  await page.locator('#pf-import-check').click();
  await expect(page.locator('#import-warnings')).toBeVisible();
  expect(await overflow()).toEqual({ doc: 0, main: 0 });
  await page.locator('#pf-project-submit').scrollIntoViewIfNeeded();
  await expect(page.locator('#pf-project-submit')).toBeInViewport();
  await expect(page.locator('#pf-project-submit')).not.toHaveAttribute('aria-disabled', 'true');
  await page.screenshot({ path: path.join(SHOTS, 'import-narrow-ready.png') });
});

test('import screen screenshot at 1280x800', async ({ page, request }) => {
  await openImportScreen(page, request);
  await page.getByLabel('Path to your prompt file').fill('C:\\a\\prompt.md');
  await page.getByLabel('Path to your test cases file').fill('C:\\a\\vague.md');
  await page.locator('#pf-import-check').click();
  await expect(page.locator('#import-warnings')).toBeVisible();
  await page.locator('#import-result').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SHOTS, 'import-wide.png') });
});

test('preflight shows each status on its own page, with detail and next action, and Next waits for the check', async ({ page, request }) => {
  await openPreflight(page, request, {
    python: { status: 'failed', detail: 'Python could not run.', next: 'Run setup.cmd again.' },
    cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' },
  });
  // The wizard opens on the first check that has not passed.
  await expect(page.locator('#wizard-count')).toHaveText('3 of 7');
  await expect(page.locator('#pf-status-python')).toHaveText('Failed');
  await expect(page.locator('#pf-item-python .pf-detail')).toHaveText('Python could not run.');
  await expect(page.locator('#pf-item-python .pf-next')).toHaveText('Run setup.cmd again.');
  await expect(page.locator('#pf-item-cli')).toHaveCount(0);
  await expect(page.locator('#wizard-next')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#wizard-needed')).toContainText('Finish this check');
  await page.locator('#wizard-back').click();
  await expect(page.locator('#pf-item-summary')).toBeVisible();
  await page.locator('#wizard-back').click();
  await expect(page.locator('#pf-status-track')).toHaveText('Passed');
  await expect(page.locator('#pf-item-track .pf-tag')).toHaveClass(/t-passed/);
  await expect(page.locator('#wizard-next')).not.toHaveAttribute('aria-disabled', 'true');

  await mock(request, 'pf_item', { id: 'python', changes: { status: 'passed', detail: 'Python 3.13.', next: '' } });
  await mock(request, 'emit_state');
  await wizardTo(page, 'cli');
  await expect(page.locator('#wizard-count')).toHaveText('4 of 7');
  await expect(page.locator('#pf-status-cli')).toHaveText('Needs you');
  await expect(page.locator('#wizard-next')).toHaveAttribute('aria-disabled', 'true');
  await mock(request, 'pf_item', { id: 'cli', changes: { status: 'passed', detail: 'Found.', next: '' } });
  await mock(request, 'pf_item', { id: 'working_test', changes: { status: 'not_checked', detail: 'Not checked yet.', next: 'Press Check everything.' } });
  await mock(request, 'emit_state');
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-status-working_test')).toHaveText('Not checked');
  // Steps stay locked: there is no step list.
  await expect(page.locator('#step-heading')).toHaveText('Before you begin');
  await expect(page.locator('.step-item')).toHaveCount(0);
});

test('preflight: the first page has the welcome text and the track choice; promptfoo adds two pages', async ({ page, request }) => {
  await openApp(page, request, 'preflight');
  await wizardTo(page, 'track');
  await expect(page.locator('#wizard-count')).toHaveText('1 of 7');
  await expect(page.getByText('It only needs to be able to read files, write files and run commands.')).toBeVisible();
  await expect(page.locator('#pf-item-node')).toHaveCount(0);
  await expect(page.getByRole('radio', { name: /Script track/ })).toBeChecked();
  await page.getByRole('radio', { name: /promptfoo track/ }).check();
  await expect(page.locator('#pf-track-note')).toContainText('one extra step where your AI adds your two fixtures');
  await expect(page.locator('#wizard-count')).toHaveText('1 of 9');
  await wizardTo(page, 'node');
  await expect(page.locator('#pf-item-node')).toBeVisible();
  await wizardTo(page, 'promptfoo');
  await expect(page.locator('#pf-item-promptfoo')).toBeVisible();
  const { log } = await mockLog(request);
  expect(log.some((e) => e.path === '/api/preflight/track' && e.body.track === 'promptfoo')).toBe(true);
});

test('preflight: an install asks for consent showing the disk amount, and cancel sends nothing', async ({ page, request }) => {
  await openPreflight(page, request, { node: { applies: true, status: 'needs_you', detail: 'Node.js was not found.', next: 'Press Install.', install: { available: true, consent: { title: 'Install Node.js?', body: 'Size: about 41 MB.\nFree space on this drive: 500.0 GB.', confirm_label: 'Install Node.js', cancel_label: 'Cancel' } } } }, { track: 'promptfoo' });
  await page.locator('#pf-install-node').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Install Node.js?');
  await expect(dialog).toContainText('Free space on this drive: 500.0 GB.');
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect((await mockLog(request)).log.some((e) => e.path === '/api/preflight/install')).toBe(false);

  await page.locator('#pf-install-node').click();
  await page.getByRole('dialog').getByRole('button', { name: 'Install Node.js' }).click();
  await expect.poll(async () => (await mockLog(request)).log.some((e) => e.path === '/api/preflight/install' && e.body.item === 'node' && e.body.consent === true)).toBe(true);

  // Progress is shown and survives a page reload.
  await expect(page.locator('.pf-bar')).toBeVisible();
  await expect(page.locator('.pf-progress')).toContainText('10 MB of about 41 MB');
  await page.reload();
  await expect(page.locator('.pf-progress')).toContainText('Downloading node');
  await expect(page.locator('#pf-install-node')).toHaveAttribute('aria-disabled', 'true');
});

test('preflight: with no AI found the three tools are offered with plain words, and the exact command sits behind a link', async ({ page, request }) => {
  await openPreflight(page, request, { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' } });
  await expect(page.locator('#pf-tool-list .pf-tool-head strong')).toHaveText(['GitHub Copilot CLI', 'Claude Code', 'Devin CLI']);
  await expect(page.getByText('Another AI tool')).toHaveCount(0);
  await expect(page.getByText('Copilot Chat', { exact: false })).toHaveCount(0);
  await expect(page.locator('#pf-install-option-claude-installer')).toContainText('about 400 MB of disk');
  await expect(page.locator('#pf-install-option-devin')).toContainText('Installs Devin CLI');
  // The exact command is not shown until the link is opened.
  await expect(page.locator('#pf-command-copilot')).toBeHidden();
  await page.locator('#pf-show-command-copilot summary').click();
  await expect(page.locator('#pf-command-copilot')).toHaveText('winget install GitHub.Copilot');
  await page.locator('#pf-show-command-devin summary').click();
  await expect(page.locator('#pf-command-devin')).toHaveText('irm https://static.devin.ai/cli/setup.ps1 | iex');
  await expect(page.locator('#pf-requirement-copilot')).toContainText('PowerShell 6 or later');
  // Claude's second way to install is behind "Another way to install".
  await expect(page.locator('#pf-install-claude-winget')).toBeHidden();
  await page.locator('#pf-other-way-claude > summary').click();
  await page.locator('#pf-install-claude-winget').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('winget install Anthropic.ClaudeCode');
  await expect(dialog).toContainText('Free space on this drive: 500.0 GB');
  await dialog.getByRole('button', { name: 'Run it in my AI window' }).click();
  await expect.poll(async () => (await mockLog(request)).log.some((e) => e.path === '/api/preflight/cli/recipe' && e.body.recipe === 'claude-winget' && e.body.consent === true)).toBe(true);
  // The AI window shows on this page while the install runs.
  await expect(page.locator('#col-right')).toBeVisible();
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
});

test('preflight: one AI found is preselected and one press of Use this AI chooses it', async ({ page, request }) => {
  await openPreflight(page, request, { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' } }, null, { command: '', found: ['claude'] });
  await expect(page.locator('#pf-ai-claude')).toBeChecked();
  await expect(page.locator('#pf-use-ai')).not.toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#col-right')).toBeHidden();
  await page.locator('#pf-use-ai').click();
  await expect(page.locator('#pf-ai-chosen')).toContainText('You chose Claude Code.');
  expect((await postsTo(request, '/api/preflight/cli')).pop().body).toEqual({ cli_command: 'claude' });
  await expect(page.locator('#wizard-next')).not.toHaveAttribute('aria-disabled', 'true');
});

test('preflight: Use this AI starts a quiet test with no AI window, and a pass moves on by itself', async ({ page, request }) => {
  await openPreflight(
    page,
    request,
    { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' }, working_test: { status: 'not_checked', detail: 'Not checked yet.', next: '' } },
    { mock_bg: true },
    { command: '', found: ['claude'] },
  );
  await page.locator('#pf-use-ai').click();
  await expect(page.locator('#pf-ai-testing')).toContainText('Testing your AI');
  await expect(page.locator('#pf-ai-testing')).not.toContainText('Nothing opens');
  await expect(page.locator('#pf-ai-spinner')).toBeVisible();
  await expect(page.locator('#pf-ai-spinner')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#pf-ai-spinner')).toHaveCSS('animation-name', 'spin');
  await expect(page.locator('#col-right')).toBeHidden();
  await expect(page.locator('#pf-use-ai')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#wizard-next')).toHaveAttribute('aria-disabled', 'true');
  await page.waitForTimeout(400);
  await expect(page.locator('#pf-item-cli')).toBeVisible();
  await mock(request, 'pf_bg_end', { result: 'passed' });
  // The AI working test counts as passed, so the wizard goes straight to the first page that needs the participant.
  await expect(page.locator('#pf-item-project')).toBeVisible();
  await expect(page.locator('#col-right')).toBeHidden();
  expect((await postsTo(request, '/api/preflight/test/start')).length).toBe(0);
  await page.locator('#wizard-back').click();
  await expect(page.locator('#pf-status-working_test')).toHaveText('Passed');
  await expect(page.locator('#pf-item-working_test')).toContainText('answered a quiet test');
});

test('preflight: a quiet test that cannot finish moves to the AI working test page with a plain line', async ({ page, request }) => {
  await openPreflight(
    page,
    request,
    { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' }, working_test: { status: 'not_checked', detail: 'Not checked yet.', next: '' } },
    { mock_bg: true },
    { command: '', found: ['claude'] },
  );
  await page.locator('#pf-use-ai').click();
  await expect(page.locator('#pf-ai-testing')).toBeVisible();
  await mock(request, 'pf_bg_end', { result: 'needs_you' });
  await expect(page.locator('#pf-item-working_test')).toBeVisible();
  await expect(page.locator('#pf-status-working_test')).toHaveText('Needs you');
  await expect(page.locator('#pf-item-working_test')).toContainText('The quiet test could not finish by itself');
  await expect(page.locator('#pf-item-working_test')).toContainText('sign in');
  // The visible AI window is where the participant signs in, and nothing was started for them.
  await expect(page.locator('#cli-start')).toBeVisible();
  expect((await postsTo(request, '/api/preflight/test/start')).length).toBe(0);
});

test('preflight: a quiet test that finishes setup keeps the wizard open on the page after it, then Your AI window ends setup', async ({ page, request }) => {
  await openPreflight(
    page,
    request,
    {
      cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' },
      working_test: { status: 'not_checked', detail: 'Not checked yet.', next: '' },
      project: { status: 'passed', detail: 'Ready.', next: '' },
    },
    { mock_bg: true },
    { command: '', found: ['claude'] },
  );
  await page.locator('#pf-use-ai').click();
  await expect(page.locator('#pf-ai-testing')).toBeVisible();
  await mock(request, 'pf_bg_end', { result: 'passed' });
  await expect(page.locator('#pf-item-ai_window')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
});

test('preflight: an AI with no quiet test leaves the page as it was', async ({ page, request }) => {
  await openPreflight(page, request, { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' } }, null, { command: '', found: ['claude'] });
  await page.locator('#pf-use-ai').click();
  await expect(page.locator('#pf-ai-chosen')).toBeVisible();
  await expect(page.locator('#pf-ai-testing')).toHaveCount(0);
  await page.waitForTimeout(500);
  await expect(page.locator('#pf-item-cli')).toBeVisible();
});

test('preflight: several AIs found preselect none, and the participant picks one', async ({ page, request }) => {
  await openPreflight(page, request, { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' } }, null, { command: '', found: ['claude', 'copilot'] });
  await expect(page.locator('input[name="ai"]')).toHaveCount(2);
  await expect(page.locator('input[name="ai"]:checked')).toHaveCount(0);
  await expect(page.locator('#pf-use-ai')).toHaveAttribute('aria-disabled', 'true');
  await page.getByRole('radio', { name: /GitHub Copilot CLI/ }).check();
  await page.locator('#pf-use-ai').click();
  expect((await postsTo(request, '/api/preflight/cli')).pop().body).toEqual({ cli_command: 'copilot' });
});

test('preflight: the typed command field exists only for the test launch', async ({ page, request }) => {
  await openPreflight(page, request, { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' } }, { custom_ai: false });
  await expect(page.locator('#pf-tool-list')).toBeVisible();
  await expect(page.locator('#pf-cli-command')).toHaveCount(0);
  await expect(page.locator('#pf-cli-check')).toHaveCount(0);
});

test('preflight: choosing an AI, then one page starts the AI window and the test, with no sign-in button', async ({ page, request }) => {
  await openPreflight(page, request, {
    cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' },
    working_test: { status: 'needs_you', detail: 'Ready.', next: 'Press Start my AI window.' },
  });
  await page.getByLabel('Command that starts your AI').fill('mycli --model mid');
  await page.locator('#pf-cli-check').click();
  await expect.poll(async () => (await mockLog(request)).log.some((e) => e.path === '/api/preflight/cli' && e.body.cli_command === 'mycli --model mid')).toBe(true);
  await expect(page.locator('#wizard-next')).not.toHaveAttribute('aria-disabled', 'true');
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-item-working_test')).toBeVisible();
  await expect(page.locator('#pf-signin-confirm')).toHaveCount(0);
  await expect(page.locator('#pf-test-signin-note')).toContainText('sign in');
  await expect(page.locator('.term-line')).toContainText('Read input.txt, write its contents in uppercase to output.txt');
  await expect(page.locator('#cli-send')).toHaveAttribute('aria-disabled', 'true');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await expect(page.locator('#term-head h2')).toHaveText('Your AI window');
  await page.locator('#cli-send').click();
  await expect(page.getByText('Sent. Watch the AI window')).toBeVisible();
  await page.locator('#pf-test-check').click();
  await expect(page.locator('#pf-status-working_test')).toHaveText('Passed');
  const { log } = await mockLog(request);
  expect(log.some((e) => e.path === '/api/preflight/test/send')).toBe(true);
  expect(log.some((e) => e.path === '/api/preflight/signin' || e.path === '/api/preflight/cli/start')).toBe(false);
});

test('preflight: after Send the page quietly re-reads the test folder and shows the pass without a Check press', async ({ page, request }) => {
  await openPreflight(page, request, { working_test: { status: 'needs_you', detail: 'Ready.', next: 'Press Start my AI window.' } }, { mock_poll_passes: true });
  await expect(page.locator('#pf-item-working_test')).toBeVisible();
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  // Nothing is polled before Send.
  await page.waitForTimeout(3500);
  expect((await postsTo(request, '/api/preflight/test/poll')).length).toBe(0);
  await page.locator('#cli-send').click();
  await expect(page.locator('#pf-status-working_test')).toHaveText('Passed', { timeout: 10000 });
  expect((await postsTo(request, '/api/preflight/test/poll')).length).toBeGreaterThan(0);
  expect((await postsTo(request, '/api/preflight/test/check')).length).toBe(0);
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI has stopped (exit code 0).');
});

test('preflight: Checking your computer starts the checks by itself, shows a row per check, and Next goes to what needs the participant', async ({ page, request }) => {
  await openPreflight(page, request, {
    python: { status: 'passed', detail: 'Python 3.13.', next: '' },
    cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one below.' },
  });
  await wizardTo(page, 'track');
  const before = (await postsTo(request, '/api/preflight/check')).length;
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-item-summary')).toBeVisible();
  await expect.poll(async () => (await postsTo(request, '/api/preflight/check')).length).toBe(before + 1);
  await expect(page.locator('#pf-summary li')).toHaveCount(4);
  await expect(page.locator('#pf-summary-status-python')).toHaveText('Passed');
  await expect(page.locator('#pf-summary-cli')).toContainText('No supported AI was found');
  await expect(page.locator('#pf-summary-done')).toContainText('Press Next');
  // The page stays until Next is pressed, which skips the passed Python page.
  await expect(page.locator('#pf-item-summary')).toBeVisible();
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-item-cli')).toBeVisible();
  // Back reaches the passed Python page, and coming back to the summary runs the checks again.
  await page.locator('#wizard-back').click();
  await expect(page.locator('#pf-item-python')).toBeVisible();
  await page.locator('#wizard-back').click();
  await expect(page.locator('#pf-item-summary')).toBeVisible();
  await expect.poll(async () => (await postsTo(request, '/api/preflight/check')).length).toBe(before + 2);
  await wizardTo(page, 'python');
  await expect(page.locator('#pf-status-python')).toHaveText('Passed');
});

test('preflight: when every check passed, Next on Checking your computer goes to the Your AI window page', async ({ page, request }) => {
  await openApp(page, request, 'build');
  await openSettings(page);
  await page.locator('#settings-setup-open').click();
  await expect(page.locator('#pf-item-track')).toBeVisible();
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-item-summary')).toBeVisible();
  await expect(page.locator('#pf-summary-done')).toContainText('Everything passed');
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-item-ai_window')).toBeVisible();
  await expect(page.locator('#wizard-next')).toHaveCount(0);
  await expect(page.locator('#pf-check-all')).toHaveCount(0);
});

test('preflight: Check everything posts and updates the button label', async ({ page, request }) => {
  await openApp(page, request, 'preflight');
  await wizardTo(page, 'python');
  await expect(page.locator('#pf-check-all')).toHaveText('Check everything again');
  const before = (await postsTo(request, '/api/preflight/check')).length; // the Checking your computer page ran it
  await page.locator('#pf-check-all').click();
  await expect.poll(async () => (await postsTo(request, '/api/preflight/check')).length).toBe(before + 1);
});

test('preflight: Check everything shows only on the pages where something can be fixed outside the app', async ({ page, request }) => {
  await openApp(page, request, 'preflight');
  for (const id of ['track', 'summary', 'working_test']) {
    await wizardTo(page, id);
    await expect(page.locator('#pf-check-all'), id).toHaveCount(0);
  }
  for (const id of ['python', 'cli', 'project']) {
    await wizardTo(page, id);
    await expect(page.locator('#pf-check-all'), id).toBeVisible();
  }
});

test('preflight: the Project folder page waits for the AI page, and Next is off until a check passes', async ({ page, request }) => {
  await openPreflight(page, request, { cli: { status: 'needs_you', detail: 'Choose your AI.', next: 'Pick one.' } });
  await expect(page.locator('#pf-item-cli')).toBeVisible();
  await expect(page.locator('#wizard-next')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#pf-project-submit')).toHaveCount(0);
  await page.locator('#wizard-next').click({ force: true });
  await expect(page.locator('#pf-item-cli')).toBeVisible();
});

test('generate: tracker, no model box, automatic advance statement, SSE update', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('.run').nth(0)).toContainText('Saved, 58 words');
  await expect(page.locator('.run').nth(2)).toContainText('Current run');
  await expect(page.getByText('You do not need to press anything to move on.')).toBeVisible();
  await expect(page.locator('#model-name')).toHaveCount(0);
  await expect(page.getByLabel('The name of the model you chose in your AI')).toHaveCount(0);

  await mock(request, 'set_data', { step: 'generate', data: { current_run: 4, runs: [
    { n: 1, done: true, words: 58 }, { n: 2, done: true, words: 61 }, { n: 3, done: true, words: 70 },
    { n: 4, done: false, words: 0 }, { n: 5, done: false, words: 0 } ] } });
  await mock(request, 'emit_state');
  await expect(page.locator('.run').nth(2)).toContainText('Saved, 70 words');
  await expect(page.locator('.run').nth(3)).toContainText('Current run');
});

test('terminal header shows label, exact line, buttons; send focuses the terminal', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('#term-head h2')).toHaveText('Your AI');
  await expect(page.locator('.term-line')).toHaveText('Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.');
  await expect(page.locator('#term-foot')).toContainText('Any approval requests appear here in the terminal');
  await expect(page.locator('#cli-send')).toHaveAttribute('aria-disabled', 'true');

  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
  await expect(page.locator('#cli-start')).toHaveAttribute('aria-disabled', 'true');

  await page.locator('#cli-send').click();
  await expect(page.locator('#cli-send')).not.toHaveAttribute('aria-busy', 'true');
  await expect.poll(() => page.evaluate(() => document.activeElement && document.activeElement.className)).toContain('xterm-helper-textarea');
  await expect(page.getByText('Sent. If your AI reports a temporary error')).toBeVisible();

  await page.locator('#cli-stop').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI has stopped (exit code 0).');
});

test('terminal renders UTF-8 split across chunks and ANSI color', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('.xterm')).toBeVisible();
  await expect.poll(async () => (await mockLog(request)).log.some((e) => e.path.startsWith('/api/terminal/stream'))).toBe(true);
  const text = '日本語 ✓ café 🙂 end\r\n';
  const bytes = Buffer.from(text, 'utf8');
  const chunks = [];
  for (let i = 0; i < bytes.length; i += 1) chunks.push(b64(bytes.subarray(i, i + 1)));
  await mock(request, 'emit_output', { chunks_b64: chunks });
  await expect.poll(() => termText(page)).toContain('日本語 ✓ café 🙂 end');
  const replacement = await page.locator('.xterm-rows').innerText();
  expect(replacement).not.toContain('\ufffd');

  await mock(request, 'emit_output', { chunks_b64: [b64(Buffer.from('\x1b[31mred words\x1b[0m\r\n', 'utf8'))] });
  await expect.poll(() => termText(page)).toContain('red words');
  const span = page.locator('.xterm-rows span', { hasText: 'red words' }).first();
  await expect(span).toHaveClass(/xterm-fg-1/);
});

test('SSE reconnects with after= and does not duplicate output', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('.xterm')).toBeVisible();
  await expect.poll(async () => (await mockLog(request)).log.some((e) => e.path.startsWith('/api/terminal/stream'))).toBe(true);
  await mock(request, 'emit_output', { chunks_b64: [b64(Buffer.from('first-chunk\r\n'))] });
  await expect.poll(() => termText(page)).toContain('first-chunk');
  await mock(request, 'drop_streams');
  await expect
    .poll(async () => (await mockLog(request)).log.filter((e) => e.path.startsWith('/api/terminal/stream')).length, { timeout: 10000 })
    .toBeGreaterThan(1);
  await mock(request, 'emit_output', { chunks_b64: [b64(Buffer.from('second-chunk\r\n'))] });
  await expect.poll(() => termText(page), { timeout: 10000 }).toContain('second-chunk');

  const { log } = await mockLog(request);
  const reconnect = log.filter((e) => e.path.startsWith('/api/terminal/stream'))[1];
  expect(reconnect.path).toMatch(/after=101/);
  const text = await termText(page);
  expect(text.split('first-chunk').length - 1).toBe(1);
});

test('keystrokes arrive in order', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await expect.poll(() => page.evaluate(() => document.activeElement && document.activeElement.className)).toContain('xterm-helper-textarea');
  const message = 'The quick brown fox é ✓ jumps 0123456789';
  await page.keyboard.type(message, { delay: 2 });
  await expect.poll(async () => (await mockLog(request)).inputs_text).toBe(message);
  const { inputs_b64: batches } = await mockLog(request);
  expect(batches.length).toBeGreaterThan(0);
  expect(batches.length).toBeLessThan(message.length); // proves batching happened
});

test('typing survives an SSE state refetch and keeps focus', async ({ page, request }) => {
  await openApp(page, request, 'predict');
  const answer = page.getByLabel('What is wrong with the polished fixture?');
  await answer.click();
  await page.keyboard.type('Half a sen');
  await page.keyboard.press('Home');
  await page.keyboard.press('ArrowRight');

  // A refetch while typing: server value is still empty.
  await page.evaluate(() => {
    window.__sameNode = document.activeElement;
  });
  await mock(request, 'emit_state');
  await expect.poll(async () => (await mockLog(request)).log.filter((e) => e.path === '/api/state').length).toBeGreaterThan(1);
  await page.waitForTimeout(100);

  await expect(answer).toHaveValue('Half a sen');
  const focusKept = await page.evaluate(() => document.activeElement === window.__sameNode);
  expect(focusKept).toBe(true);
  const caret = await page.evaluate(() => document.activeElement.selectionStart);
  expect(caret).toBe(1);
  await page.keyboard.type('X');
  await expect(answer).toHaveValue('HXalf a sen');
});

test('a server value arriving while another field is unsaved does not wipe it', async ({ page, request }) => {
  await openApp(page, request, 'readback');
  await page.getByLabel('Note (optional)').click();
  await page.keyboard.type('draft note');
  await mock(request, 'set_data', { step: 'readback', data: { note: '' } });
  await mock(request, 'emit_state');
  await page.waitForTimeout(100);
  await expect(page.getByLabel('Note (optional)')).toHaveValue('draft note');
});

test('build: first look, scan messages, checklist, nudges', async ({ page, request }) => {
  await openApp(page, request, 'build');
  await expect(page.getByText('check.py imports requests')).toBeVisible();
  await page.getByRole('button', { name: 'Run the first look' }).click();
  await expect(page.locator('.result-file table tbody tr')).toHaveCount(4);
  await expect(page.locator('.result-file').getByText('PASS', { exact: true })).toHaveCount(1);
  await expect(page.locator('.result-file').getByText('FAIL', { exact: true })).toHaveCount(2);
  await expect(page.locator('.result-file').getByText('NOT CHECKED', { exact: true })).toHaveCount(1);

  await page.getByLabel('I read the NOT CHECKED list').check();
  await expect
    .poll(async () => (await mockLog(request)).log.some((e) => e.path === '/api/step/submit' && e.body.data.checklist && e.body.data.checklist.read_nc === true))
    .toBe(true);

  await mock(request, 'check_passes', { value: false });
  await page.getByRole('button', { name: 'Check my work' }).click();
  await expect(page.getByText('Not done yet.')).toBeVisible();
  await expect(page.getByText('Fix the spec, not the checker.')).toBeVisible();
  await expect(page.locator('.is-missing')).toContainText('First look was run');
});

test('fixtures: file status shows only the two fixtures', async ({ page, request }) => {
  await openApp(page, request, 'fixtures');
  await expect(page.locator('.file-list li')).toHaveCount(2);
  await expect(page.locator('.file-list li').nth(0)).toContainText('Present');
  await expect(page.locator('.file-list li').nth(1)).toContainText('Not there yet');
  await expect(page.getByRole('heading', { name: 'Answer key held back' })).toHaveCount(0);
  await expect(page.locator('.term-line')).toContainText('write only the two fixture files');
});

// ---- Task 4.28: the Northwind example's fixtures as a recovery path ----------------

const EXAMPLE_ROUTE = '/api/step/use-example-fixtures';

test('fixtures recovery: the page says whose fixtures these are, on both tracks', async ({ page, request }) => {
  for (const scenario of ['fixtures', 'pf-fixtures']) {
    await openApp(page, request, scenario);
    await expect(page.getByRole('heading', { name: 'If your AI cannot make usable fixtures' })).toBeVisible();
    const note = page.locator('#example-fixtures-note');
    await expect(note).toContainText("These two files are the Practice task's own fixtures.");
    await expect(note).toContainText("They fit its test cases only");
    await expect(note).toContainText('No answer key is written now');
    await expect(note).toContainText('Pressing Start again clears them.');
    await expect(page.locator('#use-example-fixtures')).toHaveText("Use the example's fixtures");
    await expect(page.locator('#use-example-fixtures')).not.toHaveAttribute('aria-disabled', 'true');
  }
});

test('fixtures recovery: pressing the button sends only the step, shows both files present, and the normal check follows', async ({ page, request }) => {
  await openApp(page, request, 'fixtures');
  await expect(page.locator('.file-list li').nth(1)).toContainText('Not there yet');
  await page.locator('#use-example-fixtures').click();
  await expect(page.locator('.file-list li').nth(1)).toContainText('Present');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const posts = (await mockLog(request)).log.filter((e) => e.path === EXAMPLE_ROUTE);
  expect(posts.map((p) => p.body)).toEqual([{ step: 'fixtures' }]);
  await expect(page.getByText('answer-key')).toHaveCount(0);
  await page.getByRole('button', { name: 'Check my work' }).click();
  await expect(page.getByText('Passed. This step is done.')).toBeVisible();
  const paths = (await mockLog(request)).log.map((e) => e.path);
  expect(paths.indexOf('/api/step/check')).toBeGreaterThan(paths.indexOf(EXAMPLE_ROUTE));
});

test('fixtures recovery: replacing text asks first, and Cancel sends nothing', async ({ page, request }) => {
  await openApp(page, request, 'fixtures', { step: 'fixtures', data: { example: { offered: true, would_replace: true } } });
  await page.locator('#use-example-fixtures').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Replace the fixtures?');
  await expect(dialog).toContainText("replaces it with the Practice task's two fixtures");
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect((await mockLog(request)).log.filter((e) => e.path === EXAMPLE_ROUTE)).toHaveLength(0);

  await page.locator('#use-example-fixtures').click();
  await page.getByRole('dialog').getByRole('button', { name: 'Replace them' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect.poll(async () => (await mockLog(request)).log.filter((e) => e.path === EXAMPLE_ROUTE).map((e) => e.body))
    .toEqual([{ step: 'fixtures', replace: true }]);
});

test('fixtures recovery: nothing is offered with your own files', async ({ page, request }) => {
  await openApp(page, request, 'fixtures');
  await mock(request, 'set_starter', { starter: 'own' });
  await page.reload();
  await expect(page.locator('.file-list li')).toHaveCount(2);
  await expect(page.locator('#use-example-fixtures')).toHaveCount(0);
  await expect(page.locator('#example-fixtures-note')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'If your AI cannot make usable fixtures' })).toHaveCount(0);
});

test('fixtures recovery: the button waits while the CLI is running, and a server refusal shows as plain text', async ({ page, request }) => {
  await openApp(page, request, 'fixtures');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await expect(page.locator('#use-example-fixtures')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#example-fixtures-stop')).toContainText('Press Stop first.');
  await page.locator('#use-example-fixtures').click({ force: true });
  expect((await mockLog(request)).log.filter((e) => e.path === EXAMPLE_ROUTE)).toHaveLength(0);
  await page.locator('#cli-stop').click();
  await expect(page.locator('#use-example-fixtures')).not.toHaveAttribute('aria-disabled', 'true');
  await mock(request, 'fail', { path: EXAMPLE_ROUTE, code: 'confirm_replace', message: 'The fixtures folder already has text in it. Confirm that you want to replace it <b>now</b>.' });
  await page.locator('#use-example-fixtures').click();
  const alert = page.getByRole('alert');
  await expect(alert).toContainText('The fixtures folder already has text in it.');
  await expect(alert.locator('b')).toHaveCount(0);
});

test('key: step sits after predict, shows the file, the line and the held back note', async ({ page, request }) => {
  await openApp(page, request, 'key');
  await expect(page.locator('#step-heading')).toHaveText('Write the answer key');
  await expect(page.locator('.step-item').nth(4)).toContainText('Done');
  await expect(page.locator('.step-item').nth(5)).toContainText('Now');
  await expect(page.locator('.step-item').nth(6)).toContainText('Not started');
  await expect(page.locator('.file-list li')).toHaveCount(1);
  await expect(page.locator('.file-list li').first()).toContainText('answer-key.md');
  await expect(page.locator('.file-list li').first()).toContainText('Not there yet');
  await expect(page.getByRole('heading', { name: 'Answer key held back' })).toBeVisible();
  await expect(page.getByText('When this step passes, the app seals the answer key')).toBeVisible();
  await expect(page.locator('.term-line')).toContainText('Follow only the Answer key section');
  await expect(page.locator('#cli-start')).toBeVisible();

  await page.locator('#check-work').click();
  await expect(page.getByText('Passed. This step is done.')).toBeVisible();
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Run and compare');
});

test('key: held back note after the key is sealed', async ({ page, request }) => {
  await openApp(page, request, 'key', { step: 'key', data: { files: [{ name: 'answer-key.md', present: true }], key_held: true } });
  await expect(page.locator('.file-list li').first()).toContainText('Present');
  await expect(page.getByText('The answer key is sealed away from your project folder.')).toBeVisible();
});

test('predict is followed by the locked key step, which opens to read', async ({ page, request }) => {
  await openApp(page, request, 'predict');
  await expect(page.locator('.step-item').nth(5)).toContainText('Write the answer key');
  await expect(page.locator('.step-item').nth(5)).toContainText('Not started');
  await expect(page.locator('.step-item').nth(5).getByRole('button')).toHaveCount(1);
});

test('readback: yes/no per criterion and note are saved', async ({ page, request }) => {
  await openApp(page, request, 'readback');
  await page.getByRole('radiogroup', { name: /C1/ }).getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('radiogroup', { name: /C2/ }).getByRole('radio', { name: 'No' }).check();
  await page.getByLabel('Note (optional)').fill('Reword C2.');
  await page.getByLabel('Note (optional)').blur();
  await expect
    .poll(async () => {
      const { log } = await mockLog(request);
      return log.some((e) => e.path === '/api/step/submit' && e.body.data.answers.C1 === 'yes' && e.body.data.answers.C2 === 'no' && e.body.data.note === 'Reword C2.');
    })
    .toBe(true);
});

test('steps without a CLI hide the terminal and use the full width', async ({ page, request }) => {
  await openApp(page, request, 'predict');
  await expect(page.locator('#col-right')).toBeHidden();
  const box = await page.locator('#col-left').boundingBox();
  expect(box.width).toBeGreaterThan(1200);
});

test('predict: grid, polished text, lock confirm, then permanent lock', async ({ page, request }) => {
  await openApp(page, request, 'predict');
  await expect(page.locator('.polished-text')).toContainText('Dear customer');
  await expect(page.locator('.polished-text')).toContainText('<b>Thanks</b>');
  await expect(page.locator('.predict-grid tbody tr')).toHaveCount(4);
  await expect(page.locator('.predict-grid tbody tr').first().getByText('PASS')).toHaveCount(2);
  await expect(page.locator('.predict-grid tbody tr').first().getByText('NOT CHECKED')).toHaveCount(2);

  const lock = page.locator('#lock-predictions');
  await expect(lock).toHaveAttribute('aria-disabled', 'true');
  await expect(page.getByText('Still to fill: 8 grid choices and 3 questions.')).toBeVisible();

  for (const c of ['C1', 'C2', 'C3', 'C4']) {
    await page.getByRole('radiogroup', { name: new RegExp(`^${c} .*Bad fixture`) }).getByRole('radio', { name: 'PASS' }).check();
    await page.getByRole('radiogroup', { name: new RegExp(`^${c} .*Polished fixture`) }).getByRole('radio', { name: 'NOT CHECKED' }).check();
  }
  await page.getByLabel('What is wrong with the polished fixture?').fill('It invents a refund.');
  await page.getByLabel('Which of your criteria should catch that?').fill('C2');
  await page.getByLabel('Across your five runs').fill('C3');
  await expect(lock).not.toHaveAttribute('aria-disabled', 'true');

  // Cancel keeps it unlocked.
  await lock.click();
  await expect(page.getByRole('dialog')).toContainText('Locking is permanent');
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  let { log } = await mockLog(request);
  expect(log.some((e) => e.path === '/api/step/submit' && e.body.data.lock === true)).toBe(false);

  await lock.click();
  await page.getByRole('dialog').getByRole('button', { name: 'Lock my predictions' }).click();
  await expect(page.getByText('Your predictions are locked.')).toBeVisible();
  ({ log } = await mockLog(request));
  const locked = log.find((e) => e.path === '/api/step/submit' && e.body.data.lock === true);
  expect(locked.body.data.bad).toEqual({ C1: 'P', C2: 'P', C3: 'P', C4: 'P' });
  expect(locked.body.data.polished.C3).toBe('NC');
  expect(locked.body.data.answers.wrong).toBe('It invents a refund.');

  await expect(page.locator('#lock-predictions')).toHaveCount(0);
  await expect(page.getByRole('radiogroup', { name: /^C1 .*Bad fixture/ }).getByRole('radio', { name: 'FAIL' })).toBeDisabled();
  await expect(page.getByLabel('Which of your criteria should catch that?')).toBeDisabled();
});

test('predict: manual rows can be added', async ({ page, request }) => {
  await mock(request, 'reset', { scenario: 'predict' });
  await mock(request, 'set_data', { step: 'predict', data: { manual_rows: true, criteria: [] } });
  await page.goto(`/?t=${TOKEN}`);
  await page.getByLabel('Add a criterion').fill('Mentions the order number');
  await page.getByRole('button', { name: 'Add row' }).click();
  await expect(page.locator('.predict-grid tbody tr')).toHaveCount(1);
  await expect(page.locator('.predict-grid tbody tr')).toContainText('C1 Mentions the order number');
  await expect(page.getByLabel('Add a criterion')).toHaveValue('');
  await expect
    .poll(async () => {
      const { log } = await mockLog(request);
      return log.some((e) => e.path === '/api/step/submit' && e.body.data.criteria && e.body.data.criteria.length === 1 && e.body.data.criteria[0].id === 'C1');
    })
    .toBe(true);
});

test('run: surprises highlighted with text, classification saved, answer key safe', async ({ page, request }) => {
  await openApp(page, request, 'run');
  await expect(page.getByText('The answer key stays hidden')).toBeVisible();
  await expect(page.locator('#answer-key-body')).toHaveCount(0);

  await page.locator('#run-fixtures').click();
  await expect(page.locator('.run-grid tbody tr')).toHaveCount(4);
  const surprises = page.locator('td.surprise');
  await expect(surprises).toHaveCount(3);
  await expect(surprises.first()).toContainText('Surprise');
  await expect(surprises.first()).toContainText('FAIL');
  await expect(page.locator('.run-grid').getByText('NOT CHECKED').first()).toBeVisible();

  await page.getByLabel(/C2 Mentions the order number, Bad fixture/).selectOption('vague');
  await expect
    .poll(async () => {
      const { log } = await mockLog(request);
      return log.some((e) => e.path === '/api/step/submit' && e.body.data.classifications && e.body.data.classifications['C2:bad'] === 'vague');
    })
    .toBe(true);

  // Markdown is rendered, and HTML in it stays as visible text.
  const key = page.locator('#answer-key-body');
  await expect(key.locator('h4').first()).toHaveText('Answer key');
  await expect(key.locator('strong').first()).toHaveText('passes the length rule');
  await expect(key.locator('table tbody tr')).toHaveCount(2);
  await expect(key.locator('ul li')).toHaveCount(2);
  await expect(key.locator('code')).toHaveText('code');
  await expect(key).toContainText('<script>window.__xss = 1</script>');
  await expect(key).toContainText('<img src=x onerror=');
  await expect(key.locator('script')).toHaveCount(0);
  await expect(key.locator('img')).toHaveCount(0);
  await expect(key.locator('a')).toHaveCount(0);
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
});

test('fix: textarea save, flags, rerun, skip when allowed', async ({ page, request }) => {
  await openApp(page, request, 'fix');
  const textarea = page.getByLabel('test-cases.md');
  await expect(textarea).toHaveValue('# Test cases\nC1: under 150 words\n');
  await expect(page.locator('#fix-skip')).toHaveCount(0);
  await expect(page.getByRole('listitem').filter({ hasText: 'test-cases.md changed' })).toContainText('Not yet');

  await textarea.fill('# Test cases\nC1: under 120 words\n');
  await expect(page.getByText('You have unsaved changes.')).toBeVisible();
  await page.locator('#check-work').click();
  await expect(page.getByRole('alert')).toContainText('Save them first');

  await page.locator('#fix-save').click();
  await expect(page.getByRole('listitem').filter({ hasText: 'test-cases.md changed' })).toContainText('Yes');
  const { log } = await mockLog(request);
  expect(log.some((e) => e.path === '/api/step/submit' && e.body.data.test_cases_text === '# Test cases\nC1: under 120 words\n')).toBe(true);

  await page.locator('#fix-rerun').click();
  await expect(page.locator('.result-file')).toHaveCount(2);
  await expect(page.getByRole('listitem').filter({ hasText: 'check.py updated after that change' })).toContainText('Yes');
  await expect(page.locator('.is-missing')).toHaveCount(0);

  await mock(request, 'set_data', { step: 'fix', data: { can_skip: true } });
  await mock(request, 'emit_state');
  await page.locator('#fix-skip').click();
  await page.getByRole('dialog').getByRole('button', { name: 'Skip this step' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Log your baseline');
});

test('baseline: the line names the recorded model, there is no model box, and the count shows each criterion', async ({ page, request }) => {
  await openApp(page, request, 'baseline');
  await expect(page.locator('#step-heading')).toHaveText('Log your baseline');
  await expect(page.locator('.step-item').nth(8)).toContainText('Now');
  await expect(page.locator('.term-line')).toHaveText(
    'Read skills/build-eval-script/SKILL.md and follow it in run + log mode. The runs are runs/run-1.txt to runs/run-5.txt. The prompt file is prompt-v0.md. The model was mid-tier-model.',
  );
  await expect(page.locator('#cli-blocked')).toHaveCount(0);
  await expect(page.locator('#baseline-model')).toHaveCount(0);
  await expect(page.getByLabel('The model you used for your five runs')).toHaveCount(0);

  await page.locator('#cli-start').click();
  await expect(page.locator('#cli-send')).not.toHaveAttribute('aria-disabled', 'true');
  await page.locator('#cli-send').click();
  await expect.poll(async () => (await mockLog(request)).log.filter((e) => e.path === '/api/step/send').length).toBe(1);
  expect((await mockLog(request)).log.filter((e) => e.path === '/api/step/submit' && e.body.step === 'baseline').length).toBe(0);
});

test('baseline: the app’s own count shows pass rate per criterion, NOT CHECKED as not covered, and the overall', async ({ page, request }) => {
  await openApp(page, request, 'baseline');
  await expect(page.locator('#baseline-overall')).toHaveCount(0);
  await expect(page.getByRole('listitem').filter({ hasText: 'iteration-log.md' })).toContainText('Not there yet');
  await page.locator('#baseline-run').click();
  await expect(page.locator('#baseline-overall')).toHaveText('Overall: 12 of 15 checks passed (80%).');
  const rows = page.locator('.baseline-grid tbody tr');
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0)).toContainText('Length under 150 words');
  await expect(rows.nth(0)).toContainText('4 of 5');
  await expect(rows.nth(0)).toContainText('80%');
  await expect(rows.nth(0)).toContainText('run-3');
  await expect(rows.nth(1)).toContainText('5 of 5');
  await expect(rows.nth(1)).toContainText('None');
  await expect(rows.nth(2)).toContainText('NOT CHECKED');
  await expect(rows.nth(2)).toContainText('Not covered');
  await expect(rows.nth(2)).not.toContainText('%');
  await expect(rows.nth(3)).toContainText('3 of 5');
  await expect(rows.nth(3)).toContainText('run-4, run-5');
  await expect(page.locator('.baseline-grid .rate-meter')).toHaveCount(3);
  await expect(page.locator('#baseline-not-covered')).toContainText('Not covered: C3.');
  await expect(page.locator('#baseline-stale')).toHaveCount(0);
  await expect(page.locator('#baseline-run')).toHaveText('Run my checker on the five runs again');
  const posts = (await mockLog(request)).log.filter((e) => e.path === '/api/step/run-checker');
  expect(posts.map((e) => e.body)).toEqual([{ step: 'baseline', which: 'baseline' }]);
  await page.getByText('Show the checker’s full results').click();
  await expect(page.locator('details.raw .result-file')).toHaveCount(5);

  await mock(request, 'set_data', { step: 'baseline', data: { fresh: false, log_exists: true } });
  await mock(request, 'emit_state');
  await expect(page.locator('#baseline-stale')).toContainText('changed after this count');
  await expect(page.getByRole('listitem').filter({ hasText: 'iteration-log.md' })).toContainText('Present');
});

test('baseline: Run is off until check.py and all five runs exist, and a failed run shows the error and no numbers', async ({ page, request }) => {
  await openApp(page, request, 'baseline', { step: 'baseline', data: { runs_ready: false } });
  await expect(page.locator('#baseline-run')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.getByText('All five runs must be saved first.')).toBeVisible();
  await mock(request, 'set_data', { step: 'baseline', data: { runs_ready: true, checker_exists: false } });
  await mock(request, 'emit_state');
  await expect(page.getByText('There is no check.py to run.')).toBeVisible();

  await mock(request, 'set_data', {
    step: 'baseline',
    data: { checker_exists: true, summary: null, result: { ok: false, exit_code: 2, error: 'check.py stopped with exit code 2, so its result cannot be trusted. Exit codes 0 and 1 are the normal ones.', raw: '', files: [] } },
  });
  await mock(request, 'emit_state');
  await expect(page.locator('.callout-bad')).toContainText('check.py stopped with exit code 2');
  await expect(page.locator('#baseline-overall')).toHaveCount(0);
});

test('baseline: Check my work shows what does not match, and passing finishes the course with the bridge text', async ({ page, request }) => {
  await openApp(page, request, 'baseline');
  await mock(request, 'check_passes', { value: false });
  await page.locator('#check-work').click();
  await expect(page.getByText('Not done yet.')).toBeVisible();
  await mock(request, 'check_passes', { value: true });
  await page.locator('#check-work').click();
  await expect(page.getByText('Passed. This step is done.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'You have finished every step' })).toBeVisible();
});

test('baseline: usable at narrow widths with no sideways scrolling', async ({ page, request }) => {
  for (const width of [1024, 700, 480]) {
    await page.setViewportSize({ width, height: 800 });
    await openApp(page, request, 'baseline');
    await page.locator('#baseline-run').click();
    await expect(page.locator('#baseline-overall')).toBeVisible();
    await expect(page.locator('.baseline-grid')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `page overflow at ${width}px`).toBeLessThanOrEqual(0);
    await expect(page.locator('#baseline-run')).toBeVisible();
    await expect(page.locator('#check-work')).toBeAttached();
  }
});

test('done steps are viewable and read-only, and passing a check stays on the results', async ({ page, request }) => {
  await openApp(page, request, 'fixtures');
  await page.locator('.step-item').nth(0).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(page.getByText('You finished this step.')).toBeVisible();
  await expect(page.locator('#model-name')).toHaveCount(0);
  await expect(page.locator('#cli-start')).toHaveCount(0);
  await expect(page.locator('#continue')).toHaveText('Continue to: Build the checker');
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Build the checker');
  await page.locator('.step-item').nth(2).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Make the fixtures');

  await page.locator('#check-work').click();
  await expect(page.getByText('Passed. This step is done.')).toBeVisible();
  await expect(page.locator('#step-heading')).toHaveText('Make the fixtures');
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Read back the checks');
});

test('the terminal starts clear in every section it enters', async ({ page, request }) => {
  await openApp(page, request, 'fixtures');
  const status = page.locator('#term-head .term-status');
  await page.locator('#cli-start').click();
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
  await mock(request, 'emit_exit', { code: 1 });
  await expect(status).toHaveText('Your AI has stopped (exit code 1).');
  await expect(page.locator('#term-head .term-label')).toHaveText('Your AI');

  // Another section: no output, label or exit code from the fixtures session.
  await page.locator('.step-item').nth(0).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(status).toHaveText('Your AI is not running.');
  await expect.poll(() => termText(page)).not.toContain('Fake CLI ready');
  await expect.poll(async () => (await postsTo(request, '/api/terminal/release')).length).toBe(1);

  // Coming back does not bring the old session back.
  await page.locator('.step-item').nth(2).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Make the fixtures');
  await expect(status).toHaveText('Your AI is not running.');
  expect(await termText(page)).not.toContain('Fake CLI ready');
  expect((await postsTo(request, '/api/terminal/release')).length).toBe(1);
  await page.locator('#cli-start').click();
  await expect(status).toHaveText('Your AI is running.');
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
});

test('locked steps open as previews, with nothing that starts the CLI', async ({ page, request }) => {
  await openApp(page, request, 'build');
  const locked = page.locator('.step-item').nth(3);
  await expect(locked).toContainText('Not started');
  await locked.getByRole('button').click();
  await expect(page.locator('#preview-note')).toContainText('nothing in it can be started');
  await expect(page.locator('#cli-start')).toBeHidden();
  await page.locator('#preview-back').click();
  await expect(page.locator('#preview-note')).toHaveCount(0);
});

test('API errors appear as plain messages and server strings are not parsed as HTML', async ({ page, request }) => {
  await openApp(page, request, 'run');
  await mock(request, 'fail', { path: '/api/step/run-checker', message: 'Predictions must be locked <b>first</b>.' });
  await page.locator('#run-fixtures').click();
  const alert = page.getByRole('alert');
  await expect(alert).toContainText('Predictions must be locked <b>first</b>.');
  await expect(alert.locator('b')).toHaveCount(0);
  await alert.getByRole('button', { name: 'Dismiss' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('Quit asks first, then stops and shows a closing message', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#quit').click();
  await page.getByRole('dialog').getByRole('button', { name: 'Quit' }).click();
  await expect(page.getByRole('heading', { name: 'eval-coach has stopped' })).toBeVisible();
  expect((await mockLog(request)).quit_called).toBe(true);
});

test('exit event updates terminal status without a state refetch', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await mock(request, 'emit_exit', { code: 3 });
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI has stopped (exit code 3).');
});

test('resize sends new terminal dimensions, debounced', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('.xterm')).toBeVisible();
  await expect.poll(async () => (await mockLog(request)).resizes.length).toBeGreaterThan(0);
  const before = (await mockLog(request)).resizes.length;
  await page.setViewportSize({ width: 1100, height: 700 });
  await page.setViewportSize({ width: 1090, height: 700 });
  await page.setViewportSize({ width: 1080, height: 700 });
  await expect.poll(async () => (await mockLog(request)).resizes.length).toBeGreaterThan(before);
  await page.waitForTimeout(300);
  const after = (await mockLog(request)).resizes;
  expect(after.length - before).toBeLessThanOrEqual(2);
  expect(after[after.length - 1].cols).toBeGreaterThan(20);
});

test('usable at 1024 wide with no horizontal overflow', async ({ page, request }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await openApp(page, request, 'predict');
  await expect(page.locator('#step-heading')).toHaveText('Predict the results');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await openApp(page, request, 'generate');
  await expect(page.locator('.xterm')).toBeVisible();
  const overflow2 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow2).toBeLessThanOrEqual(0);
});

test('keyboard focus is visible and F6 leaves the terminal', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect.poll(() => page.evaluate(() => document.activeElement && document.activeElement.className)).toContain('xterm-helper-textarea');
  await page.keyboard.press('F6');
  const tag = await page.evaluate(() => document.activeElement.tagName);
  expect(tag).toBe('BUTTON');
  await page.keyboard.press('Tab');
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
  expect(outline).toBe('solid');
});

test('screenshots at 1280x800', async ({ page, request }) => {
  await openApp(page, request, 'setup');
  await page.getByLabel('Project folder').waitFor();
  await page.screenshot({ path: path.join(SHOTS, 'setup.png') });

  await openApp(page, request, 'predict');
  await page.getByRole('radiogroup', { name: /^C1 .*Bad fixture/ }).getByRole('radio', { name: 'PASS' }).check();
  await page.getByRole('radiogroup', { name: /^C1 .*Polished fixture/ }).getByRole('radio', { name: 'NOT CHECKED' }).check();
  await page.screenshot({ path: path.join(SHOTS, 'predict.png') });
  await page.evaluate(() => { document.getElementById('col-left').scrollTop = 1e6; });
  await page.screenshot({ path: path.join(SHOTS, 'predict-bottom.png') });

  await openApp(page, request, 'run');
  await page.locator('#run-fixtures').click();
  await expect(page.locator('.run-grid')).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, 'run.png') });
  await page.evaluate(() => { document.getElementById('col-left').scrollTop = 1e6; });
  await page.screenshot({ path: path.join(SHOTS, 'run-bottom.png') });

  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
  await page.screenshot({ path: path.join(SHOTS, 'generate.png') });

  await page.locator('#cli-stop').click();
});

// ---- Phase 4B: the promptfoo track ------------------------------------------------

const PF_BUILD_LINE = 'Read skills/build-promptfoo-config/SKILL.md and follow it in build mode on test-cases.md. Add runs/run-1.txt to runs/run-5.txt as tests named run-1 to run-5.';
const PF_CONFIG_LINE = 'Read skills/build-promptfoo-config/SKILL.md. Add fixtures/fixture-bad.txt and fixtures/fixture-polished-but-wrong.txt to promptfooconfig.yaml as tests named fixture-bad and fixture-polished-but-wrong. Change nothing else.';

test('promptfoo track: the extra step comes after fixtures, and the build text names the config, not check.py', async ({ page, request }) => {
  await openApp(page, request, 'pf-build');
  await expect(page.locator('#step-heading')).toHaveText('Build the config');
  await expect(page.locator('.step-item')).toHaveCount(10);
  await expect(page.locator('.step-item').nth(2)).toContainText('Make the fixtures');
  await expect(page.locator('.step-item').nth(3)).toContainText('Add the fixtures to the config');
  await expect(page.locator('.step-item').nth(3)).toContainText('Not started');
  await expect(page.locator('.step-item').nth(4)).toContainText('Read back the checks');
  await expect(page.locator('.term-line')).toHaveText(PF_BUILD_LINE);
  await expect(page.getByText('The first look runs your config on your saved answers')).toBeVisible();
  await expect(page.getByText('uses a check that needs an AI model, or any provider other than echo')).toBeVisible();
  await expect(page.getByText('promptfooconfig.yaml uses the "llm-rubric" check')).toBeVisible();
  await expect(page.locator('#col-left')).not.toContainText('check.py');
  await page.getByRole('button', { name: 'Run the first look' }).click();
  await expect(page.locator('.result-file table tbody tr')).toHaveCount(4);
  await expect(page.getByText('A non-zero exit code is normal here.')).toBeVisible();
  await expect(page.getByText('Exit code 1 is normal.')).toHaveCount(0);
});

test('script track: the step list and the build text are unchanged', async ({ page, request }) => {
  await openApp(page, request, 'build');
  await expect(page.locator('#step-heading')).toHaveText('Build the checker');
  await expect(page.locator('.step-item')).toHaveCount(9);
  await expect(page.locator('.step-item').nth(3)).toContainText('Read back the checks');
  await expect(page.locator('.term-line')).toContainText('build-eval-script');
  await expect(page.getByText('The first look runs your checker on your first saved answer.')).toBeVisible();
  await expect(page.locator('#col-left')).not.toContainText('promptfoo');
});

test('promptfoo track: the fixtures step shows the config, each test name and whether it is in the config', async ({ page, request }) => {
  await openApp(page, request, 'pf-fixtures-config');
  await expect(page.locator('#step-heading')).toHaveText('Add the fixtures to the config');
  await expect(page.locator('.kicker')).toHaveText('Step 4 of 10');
  await expect(page.locator('.term-line')).toHaveText(PF_CONFIG_LINE);
  await expect(page.locator('#cli-start')).toBeVisible();
  await expect(page.locator('#fixture-tests li')).toHaveCount(2);
  await expect(page.locator('#fixture-tests li').nth(0)).toContainText('fixture-bad');
  await expect(page.locator('#fixture-tests li').nth(0)).toContainText('In the config');
  await expect(page.locator('#fixture-tests li').nth(1)).toContainText('fixture-polished-but-wrong');
  await expect(page.locator('#fixture-tests li').nth(1)).toContainText('Not in the config yet');
  await expect(page.getByText('The names must match exactly.')).toBeVisible();
  await expect(page.getByText('No warnings. promptfooconfig.yaml uses rules only')).toBeVisible();

  await mock(request, 'set_data', { step: 'fixtures-config', data: { tests: [{ name: 'fixture-bad', present: true }, { name: 'fixture-polished-but-wrong', present: true }], scan: [{ message: 'promptfooconfig.yaml uses the provider "openai:gpt-4o". Only the "echo" provider is allowed.' }] } });
  await mock(request, 'emit_state');
  await expect(page.locator('#fixture-tests li').nth(1)).toContainText('In the config');
  await expect(page.getByText('Only the "echo" provider is allowed.')).toBeVisible();

  await page.locator('#check-work').click();
  await expect(page.getByText('Passed. This step is done.')).toBeVisible();
  await page.locator('#continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Read back the checks');
});

test('promptfoo track: the fixtures step says when the config or the fixtures are missing', async ({ page, request }) => {
  await openApp(page, request, 'pf-fixtures-config', { step: 'fixtures-config', data: { config_exists: false, fixtures_ready: false, tests: [{ name: 'fixture-bad', present: false }, { name: 'fixture-polished-but-wrong', present: false }] } });
  await expect(page.getByText('There is no promptfooconfig.yaml in your project folder yet.')).toBeVisible();
  await expect(page.locator('#fixtures-not-ready')).toContainText('Your two fixtures are not saved in your project yet.');
  await expect(page.locator('#fixture-tests li').nth(0)).toContainText('Not in the config yet');
});

test('promptfoo track: the fix step says config, and the baseline step counts the config', async ({ page, request }) => {
  await openApp(page, request, 'pf-fix');
  await expect(page.locator('#step-heading')).toHaveText('Fix the spec');
  await expect(page.getByText('Fix the spec, not the config.')).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'promptfooconfig.yaml updated after that change' })).toContainText('Not yet');
  await expect(page.locator('.term-line')).toContainText('Update promptfooconfig.yaml to match');
  await expect(page.locator('#col-left')).not.toContainText('check.py');

  await openApp(page, request, 'pf-baseline');
  await expect(page.locator('.term-line')).toHaveText(
    'Read skills/build-promptfoo-config/SKILL.md and follow it in run + log mode. The runs are the tests named run-1 to run-5. The prompt file is prompt-v0.md. The model was mid-tier-model.',
  );
  await expect(page.getByText('The app runs your promptfoo config on all five runs itself, with no AI.')).toBeVisible();
  await page.locator('#baseline-run').click();
  await expect(page.locator('#baseline-overall')).toHaveText('Overall: 12 of 15 checks passed (80%).');
  await expect(page.locator('.baseline-grid tbody tr').nth(2)).toContainText('Not covered');
  await mock(request, 'set_data', { step: 'baseline', data: { fresh: false } });
  await mock(request, 'emit_state');
  await expect(page.locator('#baseline-stale')).toContainText('promptfooconfig.yaml or one of your runs changed after this count.');
  await mock(request, 'set_data', { step: 'baseline', data: { checker_exists: false, summary: null, result: null } });
  await mock(request, 'emit_state');
  await expect(page.getByText('There is no promptfooconfig.yaml to run.')).toBeVisible();
  await expect(page.locator('#col-left')).not.toContainText('check.py');
});

test('promptfoo track: the baseline step has no model box and Send is not blocked by a model', async ({ page, request }) => {
  await openApp(page, request, 'pf-baseline');
  await page.locator('#cli-start').click();
  await expect(page.getByLabel('The model you used for your five runs')).toHaveCount(0);
  await expect(page.locator('#cli-blocked')).toHaveCount(0);
  await expect(page.locator('#cli-send')).not.toHaveAttribute('aria-disabled', 'true');
});

test('promptfoo track: the step pages fit at narrow widths', async ({ page, request }) => {
  for (const width of [1024, 480]) {
    await page.setViewportSize({ width, height: 800 });
    for (const scenario of ['pf-fixtures-config', 'pf-baseline']) {
      await openApp(page, request, scenario);
      await expect(page.locator('#step-heading')).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `${scenario} at ${width}px`).toBeLessThanOrEqual(0);
    }
  }
});

test('preflight: the track cannot change once a step is done, and the screen says so', async ({ page, request }) => {
  await openApp(page, request, 'pf-fix');
  await mock(request, 'pf_set', { passed: false });
  await mock(request, 'pf_item', { id: 'project', changes: { status: 'failed' } });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await wizardTo(page, 'track');
  await expect(page.locator('#pf-track-locked')).toContainText('so its track is fixed');
  await expect(page.locator('#pf-track-locked')).toContainText('start a new project in a different folder');
  await expect(page.getByRole('radio', { name: /Script track/ })).toBeDisabled();
  await expect(page.getByRole('radio', { name: /promptfoo track/ })).toBeDisabled();
  await expect(page.getByRole('radio', { name: /promptfoo track/ })).toBeChecked();
  await expect(page.locator('#pf-track-note')).toContainText('one extra step');
});

test('preflight: before any step is done the track can still be changed', async ({ page, request }) => {
  await openPreflight(page, request, {});
  await wizardTo(page, 'track');
  await expect(page.locator('#pf-track-locked')).toHaveCount(0);
  await expect(page.getByRole('radio', { name: /promptfoo track/ })).toBeEnabled();
  await page.getByRole('radio', { name: /promptfoo track/ }).check();
  await expect(page.locator('#pf-track-note')).toContainText('one extra step where your AI adds your two fixtures');
});

// ---- Task 4.18: optional live mode (promptfoo track) -------------------------------

const LIVE_LINE = (cli, model) => `Read skills/build-promptfoo-config/SKILL.md and follow it in live mode. I use ${cli} with the model ${model}.`;

test('live mode: the course is finished without it, and it is offered as an optional extra', async ({ page, request }) => {
  await openApp(page, request, 'pf-live');
  await expect(page.locator('#step-heading')).toHaveText('You have finished every step');
  await expect(page.locator('#optional-live-note')).toContainText('Optional: you can have promptfoo write fresh outputs through your own signed-in AI tool.');
  await expect(page.locator('#optional-live-note')).toContainText('the course is complete without it');
  const items = page.locator('.step-item');
  await expect(items).toHaveCount(11);
  for (let i = 0; i < 10; i += 1) await expect(items.nth(i)).toContainText('Done');
  await expect(items.nth(10)).toContainText('Optional: live mode');
  await expect(items.nth(10)).toContainText('Optional');
  await page.locator('#open-live').click();
  await expect(page.locator('#step-heading')).toHaveText('Optional: live mode');
  await expect(page.locator('.kicker')).toHaveText('Optional step');
});

test('live mode: the Script track never offers it', async ({ page, request }) => {
  await openApp(page, request, 'done');
  await expect(page.locator('#step-heading')).toHaveText('You have finished every step');
  await expect(page.locator('#open-live')).toHaveCount(0);
  await expect(page.locator('.step-item')).toHaveCount(9);
});

test('live mode: the warning is shown first and nothing can start until it is acknowledged and a CLI is chosen', async ({ page, request }) => {
  await openApp(page, request, 'pf-live');
  await page.locator('#open-live').click();
  const warning = page.locator('#live-warning');
  await expect(warning).toContainText('Live mode is optional. The course is complete without it, so you can skip this step.');
  await expect(warning).toContainText('Live mode makes promptfoo call your own signed-in AI tool to write fresh outputs. No API key is involved');
  await expect(warning).toContainText('For Devin CLI the helper adds --permission-mode auto, which turns on Devin\'s auto mode for that run, so Devin may act without asking you.');
  await expect(warning).toContainText('For GitHub Copilot CLI and Claude Code the helper adds no permission flag.');
  await expect(warning).toContainText('empty temporary folder, so it cannot see test-cases.md');
  await expect(warning).toContainText('Results change from run to run');
  await expect(warning).toContainText('never changes your baseline');
  await expect(warning.locator('li')).toHaveCount(6);
  await expect(page.locator('#live-ack')).not.toBeChecked();
  await expect(page.locator('#live-ack-row')).toContainText('for Devin CLI the helper turns on auto mode so it may act without asking me');
  for (const id of ['#cli-start', '#cli-send', '#cli-retry']) await expect(page.locator(id)).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#cli-start-blocked')).toContainText('Read the warning and tick the box');
  await page.locator('#cli-start').click({ force: true });
  expect((await mockLog(request)).log.filter((e) => e.path === '/api/step/start')).toHaveLength(0);

  await page.locator('#live-ack').check();
  await expect(page.locator('#cli-start-blocked')).toContainText('Choose the AI tool you use from the list');
  await expect(page.locator('#cli-start')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('.term-line')).toContainText(LIVE_LINE('<copilot | claude | devin>', 'mid-tier-model'));
});

test('live mode: choosing a CLI shows what the helper does for it and puts it in the line', async ({ page, request }) => {
  await openApp(page, request, 'pf-live');
  await page.locator('#open-live').click();
  await page.locator('#live-ack').check();
  const radios = page.locator('#live-cli-choice input[type=radio]');
  await expect(radios).toHaveCount(3);
  await expect(page.locator('#live-cli-choice')).toContainText('GitHub Copilot CLI');
  await expect(page.locator('#live-cli-choice')).toContainText('Claude Code');
  await expect(page.locator('#live-cli-choice')).toContainText('Devin CLI');
  await expect(page.locator('#live-cli-note')).toHaveCount(0);

  await page.getByRole('radio', { name: 'Devin CLI' }).check();
  await expect(page.locator('#live-cli-note')).toContainText('--permission-mode auto');
  await expect(page.locator('#live-cli-note')).toContainText('may act without asking you');
  await expect(page.locator('.term-line')).toContainText(LIVE_LINE('devin', 'mid-tier-model'));
  await expect(page.locator('#cli-start-blocked')).toHaveCount(0);
  await page.getByRole('radio', { name: 'Claude Code' }).check();
  await expect(page.locator('#live-cli-note')).toContainText('adds no permission flag');
  await expect(page.locator('#live-cli-note')).not.toContainText('auto mode');
  await expect(page.locator('.term-line')).toContainText(LIVE_LINE('claude', 'mid-tier-model'));

  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await page.locator('#cli-send').click();
  const log = (await mockLog(request)).log;
  expect(log.filter((e) => e.path === '/api/step/send').map((e) => e.body)).toEqual([{ step: 'live' }]);
  expect(log.filter((e) => e.path === '/api/step/start').map((e) => e.body)).toEqual([{ step: 'live' }]);
  const submitted = log.filter((e) => e.path === '/api/step/submit').map((e) => e.body.data);
  expect(submitted.some((d) => d.acknowledged === true)).toBe(true);
  expect(submitted.some((d) => d.cli === 'claude')).toBe(true);
});

test('live mode: Check my work reads files only, says what is missing, and finishes the optional step', async ({ page, request }) => {
  await openApp(page, request, 'pf-live');
  await page.locator('#open-live').click();
  await page.locator('#live-ack').check();
  await page.getByRole('radio', { name: 'GitHub Copilot CLI' }).check();
  await page.locator('#check-work').click();
  await expect(page.getByText('Not done yet.')).toBeVisible();
  await expect(page.locator('.is-missing')).toContainText('promptfooconfig.live.yaml exists');
  await expect(page.locator('.is-missing')).toContainText('Press Start my AI, then Send to AI, so your AI writes it.');
  await expect(page.locator('#live-files')).toContainText('Not there yet');
  await mock(request, 'set_data', { step: 'live', data: { config_exists: true, provider_exists: true, provider_ok: true, started: true } });
  await page.reload();
  await page.locator('.step-item').nth(10).getByRole('button').click();
  await expect(page.locator('#live-started')).toContainText('The app noted your promptfooconfig.yaml and iteration-log.md');
  await page.locator('#check-work').click();
  await expect(page.getByText('Passed. This step is done.')).toBeVisible();
  await expect(page.locator('.step-item').nth(10)).toContainText('Done');
  const paths = (await mockLog(request)).log.map((e) => e.path);
  expect(paths.filter((p) => p === '/api/step/run-checker')).toHaveLength(0);
});

test('live mode: scan problems and a changed provider file are shown in plain text', async ({ page, request }) => {
  await openApp(page, request, 'pf-live');
  await mock(request, 'set_data', { step: 'live', data: {
    config_exists: true, provider_exists: true, provider_ok: false,
    scan: [{ message: 'promptfooconfig.live.yaml uses the "llm-rubric" check, which needs an AI model or the network. Ask your AI to copy the checks from promptfooconfig.yaml unchanged, then check again.' }],
  } });
  await page.reload();
  await page.locator('#open-live').click();
  await expect(page.locator('#live-scan')).toContainText('llm-rubric');
  await expect(page.locator('#live-provider-changed')).toContainText('not the copy that came with the course');
});

test('live mode: the page fits at normal and narrow widths and the controls stay reachable', async ({ page, request }) => {
  for (const width of [1280, 1024, 480]) {
    await page.setViewportSize({ width, height: 800 });
    await openApp(page, request, 'pf-live');
    await page.locator('#open-live').click();
    await expect(page.locator('#live-warning')).toBeVisible();
    await expect(page.locator('#live-ack')).toBeVisible();
    await page.locator('#live-ack').check();
    await expect(page.getByRole('radio', { name: 'Devin CLI' })).toBeVisible();
    await page.getByRole('radio', { name: 'Devin CLI' }).check();
    await expect(page.locator('#live-cli-note')).toBeVisible();
    await expect(page.locator('#cli-start')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `live step at ${width}px`).toBeLessThanOrEqual(0);
    await page.screenshot({ path: path.join(SHOTS, `live-${width}.png`), fullPage: false });
  }
});

// ---- Phase 3: lessons, review, glossary, reference ------------------------------

async function openCourse(page, request, scenario, done, stepIndex) {
  await mock(request, 'reset', { scenario });
  for (const id of done || []) await mock(request, 'lesson_status', { id, status: 'done' });
  if (stepIndex !== undefined) await mock(request, 'step_index', { index: stepIndex });
  await page.goto(`/?t=${TOKEN}`);
  if (opensOnMap(scenario)) await enterPart(page);
}

const lessonReady = (page) => expect(page.locator('.lesson-page .activity').first()).toBeVisible();
const activity = (page, type) => page.locator(`article.activity.a-${type}`);

async function postsTo(request, route) {
  return (await mockLog(request)).log.filter((e) => e.method === 'POST' && e.path === route);
}

test('the course list holds only lessons and steps, and locked items can be read ahead before setup', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await lessonReady(page);
  await expect(page.locator('.mission-box')).toContainText('Leave with a checker you can trust.');
  await expect(page.locator('.win-box')).toContainText('What you can do after this');
  await expect(page.locator('.kicker')).toContainText('Lesson 1 of 7');
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toHaveCount(0);
  await expect(page.locator('.step-item')).toHaveCount(0);
  await page.locator('.course-summary').click();
  const items = page.locator('.course-item');
  await expect(items).toHaveCount(16);
  await expect(items.nth(0)).toContainText('Your mission');
  await expect(items.nth(0)).toContainText('Now');
  await expect(page.locator('.course-item', { hasText: 'Before you begin' })).toHaveCount(0);
  await expect(items.nth(1)).toContainText('One update, three grades');
  await expect(items.nth(1)).toContainText('Not started');
  await expect(items.nth(1).locator('button')).toHaveCount(1);
  await expect(items.nth(3)).toContainText('Collect your answers');
});

test('the series map pins the current Part and shows the others as done or ahead', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const stops = page.locator('.route-map .route-stop');
  await expect(stops).toHaveCount(6);
  await expect(page.locator('.route-map table')).toHaveCount(0);
  const here = page.locator('.route-stop.is-here');
  await expect(here).toHaveCount(1);
  await expect(here).toHaveAttribute('aria-current', 'step');
  await expect(here).toContainText('You are here');
  await expect(here).toContainText('Part 3: Running evals and baseline');
  await expect(page.locator('.route-map ol')).toHaveAttribute('aria-label', 'Course map. You are at Part 3 of 6.');
  await expect(page.locator('.route-stop.is-done')).toHaveCount(2);
  await expect(page.locator('.route-stop.is-next')).toHaveCount(3);
  await expect(page.locator('.route-stop.is-next').first()).toContainText('Ahead');
  await expect(page.locator('.route-title').first()).toHaveText(/^Part 1: /);
  await expect(page.locator('.brand-sub')).toHaveText('Part 3 · Running evals and baseline');
  expect(await page.locator('body').innerText()).not.toMatch(/session/i);
});

test('choice: a wrong answer shows only its own feedback, a right one explains every option', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const box = activity(page, 'choice');
  await expect(box.locator('.feedback[role="status"][aria-live="polite"]')).toBeAttached();
  await expect(box.getByRole('radiogroup', { name: 'Which describes a checker you can trust?' })).toBeVisible();

  await box.getByRole('radio', { name: 'Different verdicts each run' }).check();
  await box.locator('#submit-m-choice').click();
  const feedback = box.locator('.feedback');
  await expect(feedback).toContainText('Not quite');
  await expect(feedback).toContainText('A checker that changes its mind cannot be trusted.');
  await expect(box).not.toContainText('Right. The same input gives the same verdict.');
  await expect(box).not.toContainText('Mood is what a checker must not depend on.');
  await expect(box.locator('.pass-tag')).toHaveCount(0);
  await expect(box.getByRole('radio', { name: 'The same verdict always' })).toBeEnabled();

  await box.getByRole('radio', { name: 'The same verdict always' }).check();
  await box.locator('#submit-m-choice').click();
  await expect(feedback).toContainText('Correct.');
  await expect(box.locator('.pass-tag')).toBeVisible();
  await expect(box).toContainText('Right. The same input gives the same verdict.');
  await expect(box).toContainText('Mood is what a checker must not depend on.');
  await expect(box.locator('#submit-m-choice')).toHaveCount(0);
  await expect(box.getByRole('radio', { name: 'The same verdict always' })).toBeDisabled();

  const answers = (await postsTo(request, '/api/lesson/answer')).map((e) => e.body);
  expect(answers).toEqual([
    { lesson: 'mission', activity: 'm-choice', answer: { option: 'a' } },
    { lesson: 'mission', activity: 'm-choice', answer: { option: 'b' } },
  ]);
});

test('no correct answer or feedback is in the page or in the lesson response before answering', async ({ page, request }) => {
  const bodies = [];
  page.on('response', async (res) => {
    if (res.url().includes('/api/lesson?')) bodies.push(await res.text());
  });
  await openCourse(page, request, 'course');
  await lessonReady(page);
  await expect.poll(() => bodies.length).toBeGreaterThan(0);
  const html = await page.locator('.lesson-page').innerHTML();
  const secrets = ['Right. The same input', 'cannot be trusted', 'Mood is what', 'The generator writes the answer', 'The checker applies the threshold', 'Right. The prompt comes first.', 'It can change between runs.'];
  for (const secret of secrets) {
    expect(html).not.toContain(secret);
    for (const body of bodies) expect(body).not.toContain(secret);
  }
  expect(html).not.toMatch(/data-correct|correct=|data-bucket/);
  for (const body of bodies) {
    expect(body).not.toMatch(/"correct"|"expected"|"bucket"|"feedback"/);
  }
});

test('sort: Check is off until every item has a bucket, a wrong sort shows a count only, then passes', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const box = activity(page, 'sort');
  await expect(box.locator('#submit-m-sort')).toHaveAttribute('aria-disabled', 'true');
  await box.getByLabel('Writes the answer').selectOption({ label: 'Generator' });
  await box.getByLabel('Applies the threshold').selectOption({ label: 'Generator' });
  await expect(box.locator('#submit-m-sort')).toHaveAttribute('aria-disabled', 'true');
  await box.getByLabel('Varies run to run').selectOption({ label: 'Generator' });
  await expect(box.locator('#submit-m-sort')).not.toHaveAttribute('aria-disabled', 'true');
  await box.locator('#submit-m-sort').click();
  await expect(box.locator('.feedback')).toContainText('2 of 3 are in the right group.');
  await expect(box).not.toContainText('The checker applies the threshold.');
  await box.getByLabel('Applies the threshold').selectOption({ label: 'Checker' });
  await box.locator('#submit-m-sort').click();
  await expect(box.locator('.pass-tag')).toBeVisible();
  await expect(box).toContainText('The checker applies the threshold.');
  await expect(box.getByLabel('Applies the threshold')).toBeDisabled();
});

test('Continue is never held back by a question, then the next lesson opens to read while setup is not done', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const next = page.locator('#lesson-continue');
  await expect(next).not.toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#continue-hint')).toHaveCount(0);
  await expect(page.locator('.lesson-progress-text')).toHaveText(/^Done so far: 0 of \d+$/);
  await next.click();
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await expect(page.locator('#preview-note')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toHaveCount(0);
  expect((await postsTo(request, '/api/lesson/complete'))[0].body).toEqual({ lesson: 'mission' });
  expect((await postsTo(request, '/api/lesson/answer')).length).toBe(0);
  await page.locator('.course-summary').click();
  await expect(page.locator('.course-item').nth(0)).toContainText('Done');
  await expect(page.locator('.course-item')  .nth(1)).toContainText('Not started');
});

test('an exercise still holds Continue back, and the hint says questions never do', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['mission']);
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await lessonReady(page);
  const next = page.locator('#lesson-continue');
  await expect(next).toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#continue-hint')).toHaveText('Finish the exercise above to continue. The questions never stop you.');
  await next.click({ force: true });
  expect((await postsTo(request, '/api/lesson/complete')).length).toBe(0);
});

test('step question: shown on a finished step, answered freely, and never in the way of Continue', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['mission', 'hook', 'several-runs']);
  await mock(request, 'step_index', { index: 1 });
  await page.reload();
  await enterPart(page);
  await page.locator('.course-summary').click();
  await page.locator('.course-item', { hasText: 'Collect your answers' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  const box = page.locator('.step-page article.activity.a-choice');
  await expect(page.getByRole('heading', { name: 'Quick check' })).toBeVisible();
  await expect(page.locator('#continue')).toBeVisible();
  await expect(box.locator('.activity-title')).toContainText('What made your five answers fair to score?');
  await expect(box.locator('[id^="submit-"]')).toHaveAttribute('aria-disabled', 'true');
  await box.getByRole('radio', { name: 'Each came from a retry that replaced a weaker answer' }).check();
  await box.locator('[id^="submit-"]').click();
  await expect(box.locator('.feedback')).toContainText('Not quite');
  await expect(box.locator('.feedback')).toContainText('A retry hides the variation you are measuring.');
  await expect(box).not.toContainText('Right. Each run was blind and separate.');
  await expect(page.locator('#continue')).toBeVisible();
  await box.getByRole('radio', { name: 'Each came from a new chat that never saw your tests' }).check();
  await box.locator('[id^="submit-"]').click();
  await expect(box.locator('.pass-tag')).toBeVisible();
  await expect(box).toContainText('Right. Each run was blind and separate.');
  await page.screenshot({ path: path.join(SHOTS, 'step-question.png'), fullPage: true });
  const sent = await postsTo(request, '/api/step/question');
  expect(sent.map((e) => e.body.step)).toEqual(['generate', 'generate']);
  expect(sent[1].body.option).toBe('a');
});

test('step question: an unfinished step shows none', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['mission', 'hook', 'several-runs']);
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(page.getByRole('heading', { name: 'Quick check' })).toHaveCount(0);
});

test('placement: a wrong answer changes nothing and a correct one for a practice lesson offers no skip', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  await expect(page.getByRole('heading', { name: 'Already know some of this?' })).toBeVisible();
  const runs = page.locator('.placement-item').nth(0);
  const hook = page.locator('.placement-item').nth(1);
  await runs.getByRole('radio', { name: 'The checker' }).check();
  await runs.getByRole('button', { name: 'Check my answer' }).click();
  await expect(runs).toContainText('No change. You will cover this in the course.');
  await expect(runs.getByRole('button', { name: 'Skip it' })).toHaveCount(0);
  await expect(runs.getByRole('radio', { name: 'The prompt' })).toBeDisabled();

  await hook.getByRole('radio', { name: 'Yes it can' }).check();
  await hook.getByRole('button', { name: 'Check my answer' }).click();
  await expect(hook).toContainText('Right. It can change between runs.');
  await expect(hook.getByRole('button', { name: 'Skip it' })).toHaveCount(0);
  await expect(page.locator('#lesson-skip')).toHaveCount(0);
});

test('placement: a correct answer offers to skip that lesson, and the participant accepts', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const runs = page.locator('.placement-item').nth(0);
  await runs.getByRole('radio', { name: 'The prompt' }).check();
  await runs.getByRole('button', { name: 'Check my answer' }).click();
  await expect(runs).toContainText('You know this one. Skip the lesson Why several answers?');
  await runs.getByRole('button', { name: 'Skip it' }).click();
  await expect(runs).toContainText('Lesson skipped.');
  const posts = await postsTo(request, '/api/placement/answer');
  expect(posts.map((e) => e.body)).toEqual([{ id: 'p-runs', option: 'b' }, { id: 'p-runs', accept_skip: true }]);
  await page.locator('.course-summary').click();
  await expect(page.locator('.course-item', { hasText: 'Why several answers' })).toContainText('Skipped');
});

test('placement: the participant can decline the skip and keep the lesson', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const runs = page.locator('.placement-item').nth(0);
  await runs.getByRole('radio', { name: 'The prompt' }).check();
  await runs.getByRole('button', { name: 'Check my answer' }).click();
  await runs.getByRole('button', { name: 'Take the lesson' }).click();
  await expect(runs).toContainText('You kept this lesson.');
  await page.locator('.course-summary').click();
  await expect(page.locator('.course-item', { hasText: 'Why several answers' })).toContainText('Not started');
});

test('order: the arrows reorder with the keyboard, wrong shows feedback only, the right order passes', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['hook']);
  await expect(page.locator('#step-heading')).toHaveText('Why several answers');
  await lessonReady(page);
  const box = activity(page, 'order');
  const texts = () => box.locator('.order-text').allInnerTexts();
  const wanted = ['Prompt', 'Answer', 'File', 'Checker', 'Verdict'];
  expect(await texts()).not.toEqual(wanted);

  await box.locator('#submit-runs-order').click();
  await expect(box.locator('.feedback')).toContainText('Not the right order yet.');
  await expect(box).not.toContainText('That is the order.');

  const first = (await texts())[0];
  const down = box.getByRole('button', { name: `Move down: ${first}` });
  await down.focus();
  await page.keyboard.press('Enter');
  expect((await texts())[1]).toBe(first);
  await expect(box.getByRole('button', { name: `Move down: ${first}` })).toBeFocused();

  for (let target = 0; target < wanted.length; target += 1) {
    for (let guard = 0; guard < 8 && (await texts())[target] !== wanted[target]; guard += 1) {
      const at = (await texts()).indexOf(wanted[target]);
      await box.getByRole('button', { name: `Move up: ${wanted[target]}` }).click();
      await expect.poll(async () => (await texts()).indexOf(wanted[target])).toBe(at - 1);
    }
  }
  expect(await texts()).toEqual(wanted);
  await box.locator('#submit-runs-order').click();
  await expect(box.locator('.pass-tag')).toBeVisible();
  await expect(box.locator('.feedback')).toContainText('That is the order.');
  const sent = (await postsTo(request, '/api/lesson/answer')).map((e) => e.body.answer.order);
  expect(sent[0]).not.toEqual(wanted);
  expect(sent[sent.length - 1]).toEqual(['a', 'b', 'c', 'd', 'e']);
  await expect(page.locator('#lesson-skip')).toHaveCount(0);
  await page.locator('#lesson-continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
});

test('a skippable lesson offers Skip only after its placement answer was right, and asks first', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['hook']);
  await expect(page.locator('#step-heading')).toHaveText('Why several answers');
  await lessonReady(page);
  await expect(page.locator('#lesson-skip')).toHaveCount(0);
  await mock(request, 'placement_pass', { id: 'p-runs' });
  await page.reload();
  await enterPart(page);
  await lessonReady(page);
  await page.locator('#lesson-skip').click();
  await expect(page.getByRole('dialog')).toContainText('You will not be asked to review it later.');
  await page.getByRole('dialog').getByRole('button', { name: 'Keep the lesson' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Why several answers');
  expect((await postsTo(request, '/api/lesson/skip')).length).toBe(0);
  await page.locator('#lesson-skip').click();
  await page.getByRole('dialog').getByRole('button', { name: 'Skip the lesson' }).click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect((await postsTo(request, '/api/lesson/skip'))[0].body).toEqual({ lesson: 'several-runs' });
});

test('rule lab: predictions, the verdict and reason, the same verdict twice, and your own text', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['hook', 'several-runs'], 1);
  await expect(page.locator('#step-heading')).toHaveText('From threshold to rule');
  await lessonReady(page);
  const lab = activity(page, 'rule_lab');
  await expect(lab.locator('.sample-text')).toHaveCount(2);
  await expect(lab.locator('.case-row')).toHaveCount(4);
  await expect(lab.locator('.rule-defs-heading')).toHaveText('The rules');
  await expect(lab.getByText('Passes with fewer than 10 words.')).toBeVisible();
  await expect(lab.locator('.rule-own .hint').first()).toContainText('Optional practice, not scored.');
  const group = (name) => lab.getByRole('group', { name });
  await expect(lab.locator('#submit-rules-lab')).toHaveAttribute('aria-disabled', 'true');
  for (const name of ['Short update · Under 10 words', 'Short update · Mentions the blocker', 'Long update · Under 10 words', 'Long update · Mentions the blocker']) {
    await group(name).getByLabel('PASS').check();
  }
  await lab.locator('#submit-rules-lab').click();
  await expect(lab.locator('.feedback').first()).toContainText('2 of 4 predictions are right.');
  await expect(lab).not.toContainText('words (limit: under 10)');

  // Sample text cannot be used to peek before the predictions are right.
  await lab.getByLabel('Your text', { exact: true }).fill('Shipped the report. Blocker: none.');
  await lab.locator('#rule-run-rules-lab').click();
  await expect(lab.locator('.rule-own .bad-text')).toContainText('Make your predictions for the samples first.');

  // Your own words work at any time. The same input gives the same verdict every time.
  await lab.getByLabel('Rule', { exact: true }).selectOption({ label: 'Mentions the blocker' });
  await lab.getByLabel('Your text', { exact: true }).fill('The blocker is cleared.');
  await lab.locator('#rule-run-rules-lab').click();
  const runs = lab.locator('.rule-runs li');
  await expect(runs).toHaveCount(1);
  await expect(runs.first()).toContainText('PASS');
  await expect(runs.first()).toContainText('All found: blocker');
  await lab.locator('#rule-again-rules-lab').click();
  await expect(runs).toHaveCount(2);
  const texts = await runs.allInnerTexts();
  expect(texts[1].replace('Run 2', '')).toBe(texts[0].replace('Run 1', ''));
  await expect(lab).toContainText('Same text, same rule: the verdict is the same every time.');
  const runPosts = await postsTo(request, '/api/lesson/rule-run');
  expect(runPosts[runPosts.length - 1].body).toEqual({ lesson: 'rules', activity: 'rules-lab', rule: 'r2', text: 'The blocker is cleared.' });

  for (const name of ['Long update · Under 10 words', 'Long update · Mentions the blocker']) {
    await group(name).getByLabel('FAIL').check();
  }
  await lab.locator('#submit-rules-lab').click();
  await expect(lab.locator('.pass-tag')).toBeVisible();
  await expect(group('Short update · Under 10 words')).toContainText('PASS');
  await expect(group('Short update · Under 10 words')).toContainText('5 words (limit: under 10)');
  await expect(group('Long update · Under 10 words')).toContainText('FAIL');
  await expect(group('Long update · Mentions the blocker')).toContainText('Missing: blocker');
});

test('reflection: live word count, saved to the server, and it resumes after a reload', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['hook', 'several-runs'], 1);
  await lessonReady(page);
  const box = activity(page, 'reflection');
  const field = box.getByRole('textbox', { name: 'Which threshold in your prompt is hardest to check?' });
  await expect(box.locator('.reflection-count')).toHaveText('0 of at least 5 words');
  await field.fill('two words');
  await expect(box.locator('.reflection-count')).toHaveText('2 of at least 5 words');
  await box.getByRole('button', { name: 'Save my answer' }).click();
  await expect(box.getByText('Saved.')).toBeVisible();
  await expect(box.locator('.pass-tag')).toHaveCount(0);
  await field.fill('the tone threshold is hardest to check');
  await expect(box.locator('.reflection-count')).toHaveText('7 of at least 5 words');
  await box.getByRole('button', { name: 'Save my answer' }).click();
  await expect(box.locator('.pass-tag')).toBeVisible();
  const saved = (await postsTo(request, '/api/lesson/answer')).map((e) => e.body.answer);
  expect(saved).toEqual([{ text: 'two words' }, { text: 'the tone threshold is hardest to check' }]);

  await page.reload();
  await enterPart(page);
  await lessonReady(page);
  await expect(page.getByRole('textbox', { name: 'Which threshold in your prompt is hardest to check?' })).toHaveValue('the tone threshold is hardest to check');
  await expect(activity(page, 'reflection').locator('.pass-tag')).toBeVisible();
});

test('hook: three runs side by side as plain text, the question opens when all three are saved', async ({ page, request }) => {
  await openCourse(page, request, 'course-main');
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await lessonReady(page);
  await expect(page.locator('.term-line')).toHaveText('Read update.txt and requirements.md. Score the update from 1 to 10 against the requirements, say pass or fail, and give one sentence of reasoning. Save only that to output.txt. Do nothing else.');
  await expect(page.locator('#term-head')).toContainText('A clean folder that holds only the update and its requirements');
  await expect(page.locator('.compare-col')).toHaveCount(3);
  await expect(page.locator('.compare-col').first()).toContainText('Not run yet');
  const question = activity(page, 'cli_compare');
  await expect(question.getByRole('radio').first()).toBeDisabled();

  await page.locator('#cli-start').click();
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
  await page.locator('#cli-send').click();
  await expect(page.getByText('Sent. If your AI reports a temporary error, press Send to AI again.')).toBeVisible();
  const starts = await postsTo(request, '/api/lesson/cli/start');
  expect(starts[0].body).toEqual({ lesson: 'hook', activity: 'hook-compare' });
  expect((await postsTo(request, '/api/lesson/cli/send'))[0].body).toEqual({ lesson: 'hook', activity: 'hook-compare' });

  await mock(request, 'hook_run', { n: 1, text: '7/10 pass. <b>Looks fine</b>' });
  await expect(page.locator('.compare-col').first().locator('pre')).toHaveText('7/10 pass. <b>Looks fine</b>');
  await expect(page.locator('.compare-text b')).toHaveCount(0);
  await expect(question.getByRole('radio').first()).toBeDisabled();
  await mock(request, 'hook_run', { n: 2, text: '6/10 fail. Missing the blocker.' });
  await mock(request, 'hook_run', { n: 3, text: '8/10 pass. Short and clear.' });
  await expect(page.locator('.compare-col.is-done')).toHaveCount(3);
  await expect(page.getByText('All three runs are saved. Compare them, then answer the question below.')).toBeVisible();
  await expect(page.locator('#term-head')).toContainText('Your AI has stopped');

  await question.getByRole('radio', { name: 'Three matching scores prove it' }).check();
  await question.locator('#submit-hook-compare').click();
  await expect(question.locator('.feedback')).toContainText('Three agreeing runs are a small sample.');
  await expect(question).not.toContainText('A checker gives the same verdict every time.');
  await question.getByRole('radio', { name: 'One grade cannot promise next' }).check();
  await question.locator('#submit-hook-compare').click();
  await expect(question.locator('.pass-tag')).toBeVisible();
  await page.locator('#lesson-continue').click();
  await expect(page.locator('#step-heading')).toHaveText('Why several answers');
});

test('anatomy demo: the checker runs twice from the app and both verdict lists are shown', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['hook', 'several-runs'], 1);
  await lessonReady(page);
  const demo = activity(page, 'cli_demo');
  await expect(demo.locator('#submit-rules-demo')).toHaveAttribute('aria-disabled', 'true');
  await expect(demo).toContainText('When your AI has written check.py, run it twice from here.');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head')).toContainText('Your AI is running.');
  await mock(request, 'demo_checker', { exists: true });
  await expect(demo.locator('#submit-rules-demo')).not.toHaveAttribute('aria-disabled', 'true');
  await expect(demo).toContainText('No warnings. check.py does not import any network or AI libraries.');
  await demo.locator('#submit-rules-demo').click();
  await expect(demo.getByRole('heading', { name: 'First run' })).toBeVisible();
  await expect(demo.getByRole('heading', { name: 'Second run' })).toBeVisible();
  await expect(demo.locator('.demo-run')).toHaveCount(2);
  await expect(demo).toContainText('Both runs gave the same verdicts.');
  await expect(demo.locator('.pass-tag')).toBeVisible();
  // The activity is finished, but a CLI that is still running can always be stopped.
  await expect(page.locator('#term-head')).toContainText('This activity is finished, so the controls are off here.');
  await expect(page.locator('#cli-start')).toHaveCount(0);
  await page.locator('#cli-stop').click();
  await expect(page.locator('#term-head')).toContainText('Your AI has stopped');
  expect((await postsTo(request, '/api/lesson/cli/stop'))[0].body).toEqual({ lesson: 'rules', activity: 'rules-demo' });
});

test('review: due questions show a banner that never blocks the course, one sitting, then it clears', async ({ page, request }) => {
  await mock(request, 'reset', { scenario: 'course-main' });
  await mock(request, 'review_items', { keys: ['several-runs:r-runs-1', 'rules:r-rules-1'] });
  await page.goto(`/?t=${TOKEN}`);
  await enterPart(page);
  await lessonReady(page);
  const banner = page.locator('.review-banner');
  await expect(banner).toContainText('2 review questions are due.');
  await activity(page, 'cli_compare').scrollIntoViewIfNeeded();
  await expect(page.locator('#lesson-continue')).toBeVisible();

  await page.locator('#review-start').click();
  const dialog = page.getByRole('dialog', { name: 'Quick review' });
  await expect(dialog).toContainText('2 left in this sitting');
  await expect(dialog.getByRole('radio')).toHaveCount(2);
  await dialog.getByRole('radio', { name: 'The prompt' }).check();
  await dialog.getByRole('button', { name: 'Check my answer' }).click();
  await expect(dialog).toContainText('Not quite. This question will come back tomorrow.');
  await expect(dialog).toContainText('The prompt starts the work.');
  await dialog.getByRole('button', { name: 'Next' }).click();
  await expect(dialog).toContainText('Same rule, same text: what verdict?');
  await expect(dialog).toContainText('1 left in this sitting');
  await dialog.getByRole('radio', { name: 'The same one' }).check();
  await dialog.getByRole('button', { name: 'Check my answer' }).click();
  await expect(dialog).toContainText('Correct. This question will come back later.');
  await dialog.getByRole('button', { name: 'Next' }).click();
  await expect(dialog).toContainText('0 left in this sitting');
  await dialog.getByRole('button', { name: 'Done for now' }).first().click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(banner).toHaveCount(0);
  const answers = (await postsTo(request, '/api/review/answer')).map((e) => e.body);
  expect(answers).toEqual([{ item: 'several-runs:r-runs-1', option: 'a' }, { item: 'rules:r-rules-1', option: 'a' }]);
});

test('review: it can be postponed, nothing shows early, and it still shows after the course is finished', async ({ page, request }) => {
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  await expect(page.locator('.review-banner')).toHaveCount(0);

  await mock(request, 'reset', { scenario: 'course-main' });
  await mock(request, 'review_items', { keys: ['several-runs:r-runs-1'] });
  await page.reload();
  await expect(page.locator('.review-banner')).toContainText('1 review question is due.');
  await page.locator('#review-postpone').click();
  await expect(page.locator('.review-banner')).toContainText('Review postponed. It will come back the next time you open the app.');
  expect((await postsTo(request, '/api/review/postpone')).length).toBe(1);
  await page.locator('.review-banner').getByRole('button', { name: 'Close' }).click();
  await expect(page.locator('.review-banner')).toHaveCount(0);
  await page.reload();
  await enterPart(page);
  await lessonReady(page);
  await expect(page.locator('.review-banner')).toHaveCount(0);

  await mock(request, 'reset', { scenario: 'course-main' });
  for (const id of ['mission', 'hook', 'several-runs', 'rules', 'trust', 'surprise', 'baseline-why']) await mock(request, 'lesson_status', { id, status: 'done' });
  await mock(request, 'step_index', { index: 9 });
  await mock(request, 'review_items', { keys: ['rules:r-rules-1'] });
  await page.reload();
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('You have finished the course');
  await expect(page.locator('.review-banner')).toContainText('1 review question is due.');
  await expect(page.locator('#review-start')).toBeVisible();
});

test('the glossary opens from every screen, lists every term, and returns focus', async ({ page, request }) => {
  const data = await (await request.get('/reference-data.json')).json();
  expect(data.glossary.length).toBeGreaterThan(20);
  for (const scenario of ['generate', 'done', 'course']) {
    await openApp(page, request, scenario);
    await expect(page.locator('#glossary-open')).toBeVisible();
  }
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await page.locator('#glossary-open').click();
  const dialog = page.getByRole('dialog', { name: 'Glossary' });
  await expect(dialog.locator('dt')).toHaveCount(data.glossary.length);
  await expect(dialog.getByRole('heading', { level: 3 })).toHaveText(['Ideas', 'In this course']);
  const ideaCount = data.glossary.filter((e) => e.kind === 'idea').length;
  await expect(dialog.locator('dl').nth(0).locator('dt')).toHaveCount(ideaCount);
  await expect(dialog.locator('dl').nth(1).locator('dt')).toHaveCount(data.glossary.length - ideaCount);
  for (const entry of data.glossary.filter((e) => e.kind === 'course')) expect(entry.meaning.startsWith('In this course,')).toBe(true);
  for (const entry of data.glossary) await expect(dialog.locator('dt', { hasText: new RegExp(`^${entry.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) })).toHaveCount(1);
  const link = dialog.getByRole('link', { name: 'Open the printable one-page reference' });
  await expect(link).toHaveAttribute('href', 'reference.html');
  await expect(link).toHaveAttribute('target', '_blank');
  await expect(link).toHaveAttribute('rel', /noopener/);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('#glossary-open')).toBeFocused();
  await expect(page.locator('#reference-link')).toHaveAttribute('href', 'reference.html');
});

test('related glossary terms open the panel at that term, and a lesson link opens the lesson', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['mission', 'hook', 'several-runs', 'rules'], 1);
  await expect(page.locator('#step-heading')).toHaveText('Build the checker');
  await page.locator('.course-summary').click();
  await page.locator('.course-item', { hasText: 'Your mission' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await expect(page.locator('.lesson-actions')).toContainText('You finished this lesson. It stays here for reference.');
  await page.locator('.related-terms').getByRole('button', { name: 'Checker' }).click();
  const dialog = page.getByRole('dialog', { name: 'Glossary' });
  await expect(dialog.locator('dt.is-wanted')).toHaveText('Checker');
  await expect(dialog.locator('dt.is-wanted')).toBeFocused();
  await dialog.getByRole('button', { name: 'Open the lesson From threshold to rule' }).first().click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('#step-heading')).toHaveText('From threshold to rule');
  await expect(page.locator('#lesson-continue')).toHaveCount(0);
});

test('sources: kit files open as plain text in a read-only viewer, web links open safely', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  await page.getByRole('button', { name: 'Open: The requirements file' }).click();
  const dialog = page.getByRole('dialog', { name: 'File: The requirements file' });
  await expect(dialog.locator('pre')).toContainText('<b>group by client</b>');
  await expect(dialog.locator('pre b')).toHaveCount(0);
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
  await expect(dialog.locator('textarea, input')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const kitCalls = (await mockLog(request)).log.filter((e) => e.path.startsWith('/api/kit?'));
  expect(kitCalls.length).toBeGreaterThan(0);
  expect(kitCalls[0].path).toBe('/api/kit?ref=kit%3Alessons%2Fhook%2Frequirements.md');
  expect(kitCalls[0].token_header).toBe(true);
  await expect(page.getByRole('heading', { name: 'One thing to read' })).toBeVisible();
  await expect(page.locator('.primary-source')).toContainText('Read how the checker gets built.');

  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  const web = page.getByRole('link', { name: 'Open: An outside article' });
  await expect(web).toHaveAttribute('href', 'https://example.com/article');
  await expect(web).toHaveAttribute('target', '_blank');
  await expect(web).toHaveAttribute('rel', 'noopener noreferrer');
});

test('narrow screens: the lesson stacks, nothing overflows sideways, and the actions stay reachable', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const overflow = () => page.evaluate(() => {
    const main = document.getElementById('screen-main');
    return { doc: document.documentElement.scrollWidth - document.documentElement.clientWidth, main: main.scrollWidth - main.clientWidth };
  });
  expect(await overflow()).toEqual({ doc: 0, main: 0 });
  await expect(page.locator('#glossary-open')).toBeVisible();
  await page.locator('.course-summary').click();
  await expect(page.locator('.course-panel')).toBeVisible();
  const panel = await page.locator('.course-panel').boundingBox();
  expect(panel.x).toBeGreaterThanOrEqual(0);
  expect(panel.x + panel.width).toBeLessThanOrEqual(390);
  await page.keyboard.press('Escape');
  await page.locator('#lesson-continue').scrollIntoViewIfNeeded();
  await expect(page.locator('#lesson-continue')).toBeInViewport();
  await page.screenshot({ path: path.join(SHOTS, 'lesson-narrow.png') });

  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  await expect(page.locator('#cli-start')).toBeVisible();
  await page.locator('#cli-start').scrollIntoViewIfNeeded();
  expect(await overflow()).toEqual({ doc: 0, main: 0 });
  const left = await page.locator('#col-left').boundingBox();
  const right = await page.locator('#col-right').boundingBox();
  expect(right.y).toBeGreaterThanOrEqual(left.y + left.height - 2);
});

test('lesson screenshots at 1280x800', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  await page.screenshot({ path: path.join(SHOTS, 'lesson-mission.png') });
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  await page.screenshot({ path: path.join(SHOTS, 'lesson-hook.png') });
  await openCourse(page, request, 'course-main', ['hook', 'several-runs'], 1);
  await lessonReady(page);
  await page.screenshot({ path: path.join(SHOTS, 'lesson-rules.png'), fullPage: false });
});

test('the reference page leads with the method, then how this course works, the glossary in two groups and the principles, and prints on one page', async ({ page, request }) => {
  const data = await (await request.get('/reference-data.json')).json();
  const html = await (await request.get('/reference.html')).text();
  expect(html).not.toMatch(/<script(?![^>]*\bsrc=)/i);
  expect(html).not.toMatch(/\sstyle=/i);
  expect(html).not.toMatch(/\son[a-z]+=/i);

  await page.goto('/reference.html');
  await expect(page.getByRole('heading', { name: 'Reference card' })).toBeVisible();
  await expect(page.locator('#reference h2')).toHaveText(['The method', 'How this course works', "What this course's checker says", 'Glossary', 'Principles that always hold']);
  await expect(page.locator('.ref-method .ref-loop-line')).toHaveText('Ask clearly, know what you need, turn it into rules, score the result, improve, keep a record.');
  await expect(page.locator('.ref-loop')).toContainText('In this course');
  for (const verdict of ['PASS', 'FAIL', 'NOT CHECKED']) await expect(page.locator('.ref-verdict strong', { hasText: new RegExp(`^${verdict}$`) })).toBeVisible();
  await expect(page.locator('.ref-principle-list li')).toHaveCount(3);
  expect((await page.locator('.ref-method, .ref-loop, .ref-verdicts, .ref-principles').allInnerTexts()).join(' ')).not.toMatch(/exit code/i);
  await expect(page.locator('.ref-group')).toHaveText(['Ideas', 'In this course']);
  // A term marked card: false (Part 1's) is in the in-app glossary only, so the printed card stays one page.
  const onCard = data.glossary.filter((e) => e.card !== false);
  expect(onCard.length).toBeLessThan(data.glossary.length);
  await expect(page.locator('.ref-term')).toHaveCount(onCard.length);
  const ideas = onCard.filter((e) => e.kind === 'idea').length;
  await expect(page.locator('.ref-glossary dl').nth(0).locator('.ref-term')).toHaveCount(ideas);
  await expect(page.locator('.ref-glossary dl').nth(1).locator('.ref-term')).toHaveCount(onCard.length - ideas);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
  const inline = await page.evaluate(() => document.querySelectorAll('[style]').length);
  expect(inline).toBe(0);

  for (const format of ['Letter', 'A4']) {
    const pdf = await page.pdf({ format, printBackground: true });
    const pages = (pdf.toString('latin1').match(/\/Type\s*\/Page(?![s\w])/g) || []).length;
    expect(pages, `${format} prints on one page`).toBe(1);
  }
  await page.screenshot({ path: path.join(SHOTS, 'reference.png'), fullPage: true });
});

// ---- Design system: themes, sidebar, progress ------------------------------

const rootAttr = (page, name) => page.evaluate((n) => document.documentElement.getAttribute(n), name);
const bodyBackground = (page) => page.evaluate(() => getComputedStyle(document.body).backgroundColor);

test('theme: light is the default, the toggle switches to dark, and the choice survives a reload', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await expect(page.locator('#theme-toggle')).toBeVisible();
  expect(await rootAttr(page, 'data-theme')).toBe('light');
  const light = await bodyBackground(page);
  await expect(page.locator('#theme-toggle')).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('#theme-toggle')).toContainText('Dark theme');

  await page.locator('#theme-toggle').click();
  expect(await rootAttr(page, 'data-theme')).toBe('dark');
  await expect(page.locator('#theme-toggle')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#theme-toggle')).toContainText('Light theme');
  await expect.poll(() => bodyBackground(page)).not.toBe(light);

  await page.reload();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  expect(await rootAttr(page, 'data-theme')).toBe('dark');
  await page.locator('#theme-toggle').click();
  expect(await rootAttr(page, 'data-theme')).toBe('light');
});

test('theme: the dark theme keeps text readable against its background', async ({ page, request }) => {
  await openApp(page, request, 'predict');
  await page.locator('#theme-toggle').click();
  const pair = await page.evaluate(() => {
    const lum = (rgb) => {
      const [r, g, b] = rgb.match(/[\d.]+/g).slice(0, 3).map((v) => {
        const c = Number(v) / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const text = lum(getComputedStyle(document.getElementById('step-heading')).color);
    const back = lum(getComputedStyle(document.body).backgroundColor);
    return (Math.max(text, back) + 0.05) / (Math.min(text, back) + 0.05);
  });
  expect(pair).toBeGreaterThan(7);
});

test('sidebar: wide windows start expanded, the toggle collapses it to a rail, and the choice is kept', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  expect(await rootAttr(page, 'data-nav')).toBe('expanded');
  await expect(page.locator('.course-panel')).toBeVisible();
  await expect(page.locator('.course-item-title').first()).toBeInViewport();
  await expect(page.locator('.journey .ring')).toHaveAttribute('aria-label', /% complete$/);
  const wide = (await page.locator('#topbar').boundingBox()).width;

  await page.locator('#nav-toggle').click();
  expect(await rootAttr(page, 'data-nav')).toBe('collapsed');
  await expect(page.locator('#nav-toggle')).toHaveAttribute('aria-expanded', 'false');
  await expect.poll(async () => (await page.locator('#topbar').boundingBox()).width).toBeLessThan(wide / 2);
  await expect(page.locator('.course-item').first().getByRole('button')).toBeVisible();
  await expect(page.locator('#glossary-open')).toBeVisible();

  await page.reload();
  await enterPart(page);
  await lessonReady(page);
  expect(await rootAttr(page, 'data-nav')).toBe('collapsed');
});

test('sidebar: the course list stays open on wide screens and opens a lesson in one click', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission', 'hook', 'several-runs']);
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await page.locator('.course-item', { hasText: 'Your mission' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await expect(page.locator('.course-panel')).toBeVisible();
  await expect(page.locator('.course-item.is-viewed')).toContainText('Your mission');
});

test('sidebar: the course list has no setup entry, and the course items still open their own screens', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission', 'hook', 'several-runs']);
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(page.locator('.course-item', { hasText: 'Before you begin' })).toHaveCount(0);
  await expect(page.locator('.course-item')).toHaveCount(16);
  await page.locator('.course-item', { hasText: 'Your mission' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await expect(page.locator('.course-item.is-viewed')).toContainText('Your mission');
  await page.locator('.course-item', { hasText: 'Collect your answers' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
});

test('sidebar: overall progress counts lessons and steps', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission', 'hook']);
  await lessonReady(page);
  await expect(page.locator('.journey-text')).toContainText('2 of 16 lessons and steps done');
  expect(await page.locator('.journey-text').innerText()).not.toMatch(/parts/i);
});

// ---- Course list groups --------------------------------------------------------------------

const GROUPS = [
  ['Why check AI work', ['Your mission', 'One update, three grades']],
  ['Collect answers', ['Why several answers', 'Collect your answers']],
  ['Turn it into rules', ['From threshold to rule', 'Build the checker']],
  ['Test the checker', ['Test the checker before you trust it', 'Make the fixtures', 'Read back the checks', 'Predict the results', 'Write the answer key']],
  ['Read results and improve', ['Reading a surprise', 'Run and compare', 'Fix the spec']],
  ['Keep a record', ['Your baseline, and what comes next', 'Log your baseline']],
];

// Each heading with the item titles that follow it, in list order.
const readGroups = (page) =>
  page.evaluate(() => {
    const out = [];
    for (const li of document.querySelectorAll('.course-list > li')) {
      const heading = li.querySelector('.course-group');
      if (heading) out.push([heading.textContent, []]);
      else out[out.length - 1][1].push(li.querySelector('.course-item-title').textContent);
    }
    return out;
  });

test('course list: group headings come once each, in order, above their lessons and steps', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  expect(await readGroups(page)).toEqual(GROUPS);
  await expect(page.locator('.course-item')).toHaveCount(16);
  const marks = await page.locator('.course-item-mark').allInnerTexts();
  expect(marks).toEqual(Array.from({ length: 16 }, (_, i) => String(i + 1)));
});

test('course list: a heading is text for a screen reader, not a button, and the tab order skips it', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission', 'hook']);
  await lessonReady(page);
  const headings = page.getByRole('heading', { level: 2, name: 'Why check AI work' });
  await expect(headings).toHaveCount(1);
  await expect(page.locator('.course-group')).toHaveCount(6);
  expect(await page.locator('.course-group').evaluateAll((els) => els.map((e) => e.closest('button, a, [tabindex]') !== null || e.tabIndex >= 0))).toEqual([false, false, false, false, false, false]);
  await expect(page.getByRole('button', { name: /Why check AI work/ })).toHaveCount(0);
  const nav = page.locator('.course-panel');
  await expect(nav.getByRole('heading')).toHaveText(GROUPS.map(([label]) => label));
  // Tab order inside the list follows the items, with no stop on a heading.
  const first = nav.getByRole('button').first();
  await first.focus();
  const stops = [];
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press('Tab');
    stops.push(await page.evaluate(() => (document.activeElement.closest('.course-item') ? 'item' : document.activeElement.className)));
  }
  expect(stops.filter((s) => s === 'item').length).toBeGreaterThanOrEqual(1);
  expect(stops).not.toContain('course-group');
  // Locked items are buttons too, so they can be read ahead; the connector still joins items within a group.
  const connector = await page.locator('.course-item').nth(1).evaluate((el) => getComputedStyle(el, '::before').content);
  expect(connector).toBe('""');
  const groupStart = await page.locator('.course-item').nth(2).evaluate((el) => getComputedStyle(el, '::before').content);
  expect(groupStart).not.toBe('""');
});

test('course list: the optional live step sits under Keep a record and stays marked optional', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'pf-course-main', ['mission', 'hook', 'several-runs', 'rules', 'trust', 'surprise', 'baseline-why'], 10);
  await expect(page.locator('#step-heading')).toHaveText('You have finished the course');
  await expect(page.locator('.finished-page .lede')).toContainText('In Part 4 you change the prompt and compare each new score with this baseline');
  await expect(page.locator('.course-item.k-step').last()).toContainText('Optional');
  const groups = await readGroups(page);
  const record = groups[groups.length - 1];
  expect(record[0]).toBe('Keep a record');
  expect(record[1][record[1].length - 1]).toBe('Optional: live mode');
  expect(groups.flatMap(([, titles]) => titles)).toHaveLength(18);
});

test('course list: headings meet text contrast and do not clip in the light and dark themes at the smallest and largest text size', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  const measure = () =>
    page.evaluate(() => {
      const lum = (rgb) => {
        const [r, g, b] = rgb.match(/[\d.]+/g).slice(0, 3).map((v) => {
          const c = Number(v) / 255;
          return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };
      const panel = document.querySelector('.course-panel').getBoundingClientRect();
      return [...document.querySelectorAll('.course-group')].map((el) => {
        let back = el;
        while (back && /rgba\(0, 0, 0, 0\)|transparent/.test(getComputedStyle(back).backgroundColor)) back = back.parentElement;
        const fore = lum(getComputedStyle(el).color);
        const ground = lum(getComputedStyle(back || document.body).backgroundColor);
        const box = el.getBoundingClientRect();
        const next = el.closest('li').nextElementSibling.getBoundingClientRect();
        return {
          shown: box.height > 0,
          contrast: (Math.max(fore, ground) + 0.05) / (Math.min(fore, ground) + 0.05),
          clipped: el.scrollWidth > el.clientWidth + 1 || box.right > panel.right + 1,
          overlaps: box.bottom > next.top + 1,
        };
      });
    });
  for (const theme of ['light', 'dark']) {
    for (const size of ['80', '150']) {
      await openWithStorage(page, request, 'course-main', { 'eval-coach-text-size': size, 'eval-coach-theme': theme });
      await lessonReady(page);
      if (!(await page.locator('details.course-nav').evaluate((el) => el.open))) await page.locator('.course-summary').click();
      const rows = await measure();
      expect(rows).toHaveLength(6);
      for (const row of rows) {
        expect(row.shown, `${theme} ${size} shown`).toBe(true);
        expect(row.contrast, `${theme} ${size} contrast`).toBeGreaterThanOrEqual(4.5);
        expect(row.clipped, `${theme} ${size} clipped`).toBe(false);
        expect(row.overlaps, `${theme} ${size} overlap`).toBe(false);
      }
    }
  }
});

test('course list: the narrow drop-down shows the same headings', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  await expect(page.locator('.course-group').first()).toBeHidden();
  await page.locator('.course-summary').click();
  await expect(page.locator('.course-panel')).toBeVisible();
  await expect(page.locator('.course-panel').getByRole('heading')).toHaveText(GROUPS.map(([label]) => label));
  expect(await readGroups(page)).toEqual(GROUPS);
  const panel = await page.locator('.course-panel').boundingBox();
  for (const box of await page.locator('.course-group').evaluateAll((els) => els.map((e) => JSON.parse(JSON.stringify(e.getBoundingClientRect()))))) {
    expect(box.left).toBeGreaterThanOrEqual(panel.x);
    expect(box.right).toBeLessThanOrEqual(panel.x + panel.width + 1);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
});

test('lesson progress: a pip fills for each activity passed', async ({ page, request }) => {
  await openCourse(page, request, 'course');
  await lessonReady(page);
  const total = await page.locator('.lesson-progress .pip').count();
  expect(total).toBeGreaterThan(0);
  await expect(page.locator('.lesson-progress .pip.is-on')).toHaveCount(0);
  await expect(page.locator('.lesson-progress-text')).toHaveText(`Done so far: 0 of ${total}`);
  const box = activity(page, 'choice');
  await box.getByRole('radio', { name: 'The same verdict always' }).check();
  await box.locator('#submit-m-choice').click();
  await expect(box.locator('.pass-tag')).toBeVisible();
  await expect(page.locator('.lesson-progress .pip.is-on')).toHaveCount(1);
  await expect(page.locator('.lesson-progress-text')).toHaveText(`Done so far: 1 of ${total}`);
});

test('design screenshots: wide and dark', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main');
  await lessonReady(page);
  await page.screenshot({ path: path.join(SHOTS, 'wide-lesson-light.png') });
  await page.locator('#theme-toggle').click();
  await page.waitForTimeout(450);
  await page.screenshot({ path: path.join(SHOTS, 'wide-lesson-dark.png') });
  await openCourse(page, request, 'course');
  await lessonReady(page);
  await page.screenshot({ path: path.join(SHOTS, 'wide-mission-dark.png') });
  await openApp(page, request, 'run');
  await page.locator('#run-fixtures').click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(SHOTS, 'wide-run-dark.png'), fullPage: false });
  await page.locator('#theme-toggle').click();
  await openApp(page, request, 'generate');
  await expect(page.locator('.xterm')).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, 'wide-generate-light.png') });
  await openApp(page, request, 'setup');
  await page.getByLabel('Project folder').waitFor();
  await page.screenshot({ path: path.join(SHOTS, 'wide-setup-light.png') });
});

// ---- Settings, setup as a global gate, and text size ----------------------------------

const PHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 };

async function phonePage(browser) {
  const context = await browser.newContext({ baseURL: ORIGIN, ...PHONE });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));
  return { context, page, errors };
}

// Sets browser storage for this origin, then reloads so the page starts with it (the way a returning visit does).
async function openWithStorage(page, request, scenario, items) {
  await openApp(page, request, scenario);
  await page.evaluate((entries) => {
    for (const [key, value] of Object.entries(entries)) window.localStorage.setItem(key, value);
  }, items);
  await page.reload();
  if (opensOnMap(scenario)) await enterPart(page);
}

const textSizeAttr = (page) => rootAttr(page, 'data-text-size');
const rootFontPx = (page) => page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
const sideways = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function openSettings(page) {
  await page.locator('#settings-open').click();
  await expect(page.locator('#step-heading')).toHaveText('Settings');
}

// Contrast ratio of the banner's text on its own background.
async function bannerContrast(page) {
  return page.evaluate(() => {
    const parse = (value) => value.match(/[\d.]+/g).slice(0, 3).map(Number);
    const lum = ([r, g, b]) => {
      const f = (c) => {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const banner = document.querySelector('#setup-reminder');
    const fg = lum(parse(getComputedStyle(banner.querySelector('p')).color));
    const bg = lum(parse(getComputedStyle(banner).backgroundColor));
    return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
  });
}

test('first run: setup comes first as a full-page wizard with a way to skip, no banner, and nothing of the course beside it', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await expect(page.locator('#pf-skip')).toBeVisible();
  await expect(page.locator('#setup-reminder')).toHaveCount(0);
  await expect(page.locator('.course-item', { hasText: 'Before you begin' })).toHaveCount(0);
  // The wizard fills the window: no sidebar, course list, tools or banner beside it.
  await expect(page.locator('#topbar')).toBeHidden();
  await expect(page.locator('.course-item')).toHaveCount(0);
  await expect(page.locator('#settings-open')).toHaveCount(0);
  await expect(page.locator('#glossary-open')).toHaveCount(0);
  await expect(page.locator('#quit')).toHaveCount(0);
  await expect(page.locator('#wizard-close')).toHaveCount(0);
  const box = await page.locator('#main-area').boundingBox();
  expect(box.x).toBe(0);
  expect(box.width).toBe(page.viewportSize().width);
  await page.screenshot({ path: path.join(SHOTS, 'wizard-first-run.png') });
});

test('the wizard shows the AI window only where the participant acts, and a running AI survives moving between pages', async ({ page, request }) => {
  await openPreflight(page, request, { working_test: { status: 'needs_you', detail: 'Ready.', next: 'Press Start my AI window.' } });
  await expect(page.locator('#pf-item-working_test')).toBeVisible();
  await expect(page.locator('#col-right')).toBeVisible();
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await expect(page.locator('#term-head h2')).toHaveText('Your AI window');
  await page.screenshot({ path: path.join(SHOTS, 'wizard-test-page.png') });
  // No AI window on the pages before it, even though the AI is still running.
  for (const id of ['cli', 'python', 'summary']) {
    await page.locator('#wizard-back').click();
    await expect(page.locator(`#pf-item-${id}`)).toBeVisible();
    await expect(page.locator('#col-right')).toBeHidden();
  }
  await wizardTo(page, 'working_test');
  await expect(page.locator('#col-right')).toBeVisible();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  // None on the Project folder and Your AI window pages either.
  await mock(request, 'pf_item', { id: 'working_test', changes: { status: 'passed', detail: 'Done.', next: '' } });
  await mock(request, 'emit_state');
  await page.locator('#wizard-next').click();
  await expect(page.locator('#pf-item-project')).toBeVisible();
  await expect(page.locator('#col-right')).toBeHidden();
  expect((await postsTo(request, '/api/preflight/stop')).length).toBe(0);
});

test('completing setup from the first-run screen ends on the Your AI window page, then the Series map, and Part 3 starts at the mission', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-project-submit').click();
  await expect(page.locator('#pf-item-ai_window')).toBeVisible();
  // Setup has passed, but the wizard stays on its last page until Finish.
  await expect(page.locator('#wizard-count')).toHaveText('7 of 7');
  await expect(page.locator('#pf-skip')).toHaveCount(0);
  await expect(page.locator('#topbar')).toBeHidden();
  await page.locator('#wizard-finish').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(page.locator('#setup-reminder')).toHaveCount(0);
  await expect(page.locator('#pf-skip')).toHaveCount(0);
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
});

test('skipping setup opens the Series map with the banner, and the skip is remembered after a reload', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(page.locator('#series-list')).toBeVisible();
  await expect(page.locator('#setup-reminder')).toBeVisible();
  expect((await postsTo(request, '/api/preflight/skip')).length).toBe(1);
  await page.reload();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(page.locator('#setup-reminder')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toHaveCount(0);
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
});

test('after setup no screen asks for setup again while moving through the course', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission']);
  for (const title of ['Your mission', 'Collect your answers', 'One update, three grades']) {
    const item = page.locator('.course-item', { hasText: title });
    if (await item.getByRole('button').count()) await item.getByRole('button').click();
    await expect(page.getByRole('heading', { name: 'Before you begin' })).toHaveCount(0);
    await expect(page.locator('#setup-reminder')).toHaveCount(0);
  }
});

test('before setup a CLI exercise and a step cannot be started, and the server refuses a direct request', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  await enterPart(page);
  await page.locator('.course-item', { hasText: 'One update, three grades' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await expect(page.locator('#preview-note')).toBeVisible();
  await expect(page.locator('#cli-needs-setup')).toContainText('needs setup first');
  await expect(page.locator('#cli-start')).toHaveCount(0);
  await expect(page.locator('.lesson-page input[type="radio"]').first()).toBeDisabled();
  await expect(page.locator('#lesson-continue')).toHaveCount(0);
  await page.locator('#cli-setup-go').click();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  const res = await request.post('/api/lesson/cli/start', {
    data: { lesson: 'hook', activity: 'hook-compare' },
    headers: { 'Content-Type': 'application/json', 'X-Eval-Token': TOKEN },
  });
  expect(res.status()).toBe(400);
  expect((await res.json()).error.code).toBe('preflight_incomplete');
});

test('before setup a step opens to read, with its instructions and nothing that starts the CLI', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  await enterPart(page);
  await page.locator('.course-summary').click();
  await page.locator('.course-item', { hasText: 'Collect your answers' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(page.locator('#preview-note')).toContainText('nothing in this step can be started');
  await expect(page.locator('.prose-list li').first()).toBeVisible();
  await expect(page.locator('#cli-start')).toHaveCount(0);
  await expect(page.locator('#check-work')).toHaveCount(0);
  await expect(page.locator('#setup-reminder')).toBeVisible();
});

test('after setup a later lesson opens as a preview that names what is still to do and leads back', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission']);
  const later = page.locator('.course-item', { hasText: 'From threshold to rule' });
  await expect(later).toContainText('Not started');
  await later.getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('From threshold to rule');
  await expect(page.locator('#preview-note')).toContainText('One update, three grades');
  await expect(page.locator('#preview-setup')).toHaveCount(0);
  await expect(page.locator('#cli-start')).toBeHidden();
  await expect(page.locator('#lesson-continue')).toHaveCount(0);
  await page.locator('[id^="rule-text-"]').first().fill('Keep it under 100 words.');
  await expect(page.locator('[id^="rule-run-"]').first()).toHaveAttribute('aria-disabled', 'true');
  expect((await postsTo(request, '/api/lesson/answer')).length).toBe(0);
  await page.locator('#preview-back').click();
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await expect(page.locator('#preview-note')).toHaveCount(0);
});

test('after setup a later step opens as a preview with nothing that starts the CLI', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission']);
  await page.locator('.course-item', { hasText: 'Collect your answers' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(page.locator('#preview-note')).toContainText('One update, three grades');
  await expect(page.locator('#preview-note')).toContainText('nothing in it can be started');
  await expect(page.locator('#cli-start')).toBeHidden();
  await expect(page.locator('#check-work')).toHaveCount(0);
  await page.locator('#preview-back').click();
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
});

test('after setup a glossary link opens a lesson that is still locked, as a preview', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['mission']);
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await page.locator('.course-summary').click();
  await page.locator('.course-item', { hasText: 'Your mission' }).getByRole('button').click();
  await page.locator('.related-terms').getByRole('button', { name: 'Checker' }).click();
  const dialog = page.getByRole('dialog', { name: 'Glossary' });
  await dialog.getByRole('button', { name: 'Open the lesson From threshold to rule' }).first().click();
  await expect(page.locator('#step-heading')).toHaveText('From threshold to rule');
  await expect(page.locator('#preview-note')).toBeVisible();
  await expect(page.locator('#lesson-continue')).toHaveCount(0);
});

test('banner: on every screen, not on setup, no close control, button opens setup, focus stays put', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  const banner = page.locator('#setup-reminder');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('exercises that use your AI are off');
  await expect(banner.getByRole('button')).toHaveCount(1);
  expect(await page.evaluate(() => document.querySelector('#setup-reminder').contains(document.activeElement))).toBe(false);
  await enterPart(page);
  await page.locator('.course-summary').click();
  await page.locator('.course-item', { hasText: 'Collect your answers' }).getByRole('button').click();
  await expect(banner).toBeVisible();
  await openSettings(page);
  await expect(banner).toBeVisible();
  await page.locator('#settings-close').click();
  await page.locator('#glossary-open').click();
  await expect(page.locator('dialog[open]')).toBeVisible();
  await expect(banner).toBeVisible();
  await page.keyboard.press('Escape');
  await page.locator('#setup-banner-go').click();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await expect(banner).toHaveCount(0);
  await expect(page.locator('#pf-skip')).toHaveCount(0);
  await expect(page.locator('#topbar')).toBeHidden();
  // Closing returns to the screen it was opened from, with the banner again.
  await page.locator('#wizard-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(banner).toBeVisible();
});

test('banner: stays in view while the lesson scrolls, covers nothing, is calm and readable in both themes', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 520 });
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  await enterPart(page);
  await lessonReady(page);
  const banner = page.locator('#setup-reminder');
  const before = await banner.boundingBox();
  await page.evaluate(() => {
    document.getElementById('col-left').scrollTop = 100000;
  });
  const after = await banner.boundingBox();
  expect(after.y).toBe(before.y);
  expect(after.y).toBeGreaterThanOrEqual(0);
  expect(after.y + after.height).toBeLessThanOrEqual(520);
  const main = await page.locator('#screen-main').boundingBox();
  expect(after.y + after.height).toBeLessThanOrEqual(main.y + 1);
  const lines = await page.evaluate(() => {
    const p = document.querySelector('#setup-reminder p');
    return p.getBoundingClientRect().height / parseFloat(getComputedStyle(p).lineHeight);
  });
  expect(lines).toBeLessThanOrEqual(2.05);
  expect(await bannerContrast(page)).toBeGreaterThanOrEqual(4.5);
  await page.locator('#theme-toggle').click();
  await page.waitForTimeout(450);
  expect(await bannerContrast(page)).toBeGreaterThanOrEqual(4.5);
  const colors = await page.evaluate(() => ({
    banner: getComputedStyle(document.querySelector('#setup-reminder')).backgroundColor,
    error: getComputedStyle(document.documentElement).getPropertyValue('--fail-tint').trim(),
  }));
  expect(colors.banner).not.toBe(colors.error);
});

test('banner: the largest size on a desktop and on a phone keeps the text and the button fully visible', async ({ page, request, browser }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openWithStorage(page, request, 'course-first-run', { 'eval-coach-text-size': '150' });
  await page.locator('#pf-skip').click();
  let banner = page.locator('#setup-reminder');
  await expect(banner).toBeVisible();
  const desktop = await page.evaluate(() => {
    const el = document.querySelector('#setup-reminder');
    const p = el.querySelector('p');
    const b = el.querySelector('button').getBoundingClientRect();
    return { textFits: p.scrollWidth <= p.clientWidth + 1, buttonRight: b.right, width: window.innerWidth };
  });
  expect(desktop.textFits).toBe(true);
  expect(desktop.buttonRight).toBeLessThanOrEqual(desktop.width);
  expect(await sideways(page)).toBeLessThanOrEqual(0);

  const phone = await phonePage(browser);
  await openWithStorage(phone.page, request, 'course-first-run', { 'eval-coach-text-size': '130' });
  await phone.page.locator('#pf-skip').click();
  banner = phone.page.locator('#setup-reminder');
  await expect(banner).toBeVisible();
  const small = await phone.page.evaluate(() => {
    const el = document.querySelector('#setup-reminder');
    const p = el.querySelector('p');
    const b = el.querySelector('button').getBoundingClientRect();
    return { textFits: p.scrollWidth <= p.clientWidth + 1, buttonRight: b.right, buttonHeight: b.height, width: window.innerWidth };
  });
  expect(small.textFits).toBe(true);
  expect(small.buttonRight).toBeLessThanOrEqual(small.width);
  expect(small.buttonHeight).toBeGreaterThanOrEqual(44);
  expect(await sideways(phone.page)).toBeLessThanOrEqual(0);
  await phone.page.evaluate(() => window.localStorage.setItem('eval-coach-text-size', '100'));
  await phone.page.reload();
  const box = await phone.page.locator('#setup-reminder').boundingBox();
  expect(box.height).toBeLessThanOrEqual(844 / 5);
  expect(phone.errors).toEqual([]);
  await phone.context.close();
});

test('Settings: the entry is directly before Quit in the wide, collapsed and narrow layouts and works by keyboard', async ({ page, request }) => {
  const order = () => page.evaluate(() => Array.from(document.querySelectorAll('.topbar-tools .tool')).map((e) => e.id));
  for (const [width, nav] of [[1600, 'expanded'], [1280, 'collapsed'], [500, 'collapsed']]) {
    await page.setViewportSize({ width, height: 800 });
    await openApp(page, request, 'generate');
    const ids = await order();
    expect(ids.slice(-2), `${width}px`).toEqual(['settings-open', 'quit']);
    expect(await rootAttr(page, 'data-nav')).toBe(nav);
    await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible();
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  await openApp(page, request, 'generate');
  await page.locator('#settings-open').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#step-heading')).toHaveText('Settings');
});

test('Settings: one panel with the text size, setup and both resets in that order, open before setup passes', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  await enterPart(page);
  await page.locator('.course-summary').click();
  const statuses = () => page.locator('.course-item').evaluateAll((els) => els.map((e) => e.className.match(/s-(\w+)/)[1]));
  const before = await statuses();
  await page.keyboard.press('Escape');
  await openSettings(page);
  await expect(page.locator('.settings-group > h2')).toHaveText(['Text size', 'Setup', 'Reset']);
  await expect(page.locator('#text-size-slider')).toBeVisible();
  await expect(page.locator('#pf-check-all')).toHaveCount(0);
  await expect(page.locator('#settings-setup-summary li')).toHaveCount(5);
  await expect(page.locator('#settings-setup-open')).toBeVisible();
  await expect(page.locator('#reset-progress')).toBeVisible();
  await expect(page.locator('#reset-configuration')).toBeVisible();
  await page.locator('.course-summary').click();
  expect(await statuses()).toEqual(before);
  expect(before.slice(1).every((s) => s === 'locked')).toBe(true);
});

test('Settings: leaving returns to the screen that was open, and opening it changes no progress or CLI', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect(page.getByText('Your AI is running.')).toBeVisible();
  await openSettings(page);
  await page.locator('#text-size-slider').focus();
  await page.keyboard.press('ArrowRight');
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Collect your answers');
  await expect(page.getByText('Your AI is running.')).toBeVisible();
  const posts = (await mockLog(request)).log.filter((e) => e.method === 'POST').map((e) => e.path);
  expect(posts.filter((p) => /stop|reset|submit|check|complete/.test(p))).toEqual([]);
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission']);
  await page.locator('.course-item', { hasText: 'Your mission' }).getByRole('button').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await openSettings(page);
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
});

test('text size: the slider shows 100%, stops at 80% and 150%, steps by 5 from the keyboard and returns to 100%', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await openSettings(page);
  const slider = page.locator('#text-size-slider');
  await expect(slider).toHaveAttribute('min', '80');
  await expect(slider).toHaveAttribute('max', '150');
  await expect(slider).toHaveAttribute('step', '5');
  await expect(page.locator('#text-size-value')).toHaveText('100%');
  await slider.focus();
  await page.keyboard.press('End');
  await expect(page.locator('#text-size-value')).toHaveText('150%');
  expect(await rootFontPx(page)).toBe(24);
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#text-size-value')).toHaveText('150%');
  await page.keyboard.press('Home');
  await expect(page.locator('#text-size-value')).toHaveText('80%');
  expect(await rootFontPx(page)).toBeCloseTo(12.8, 1);
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#text-size-value')).toHaveText('85%');
  await page.locator('#text-size-default').click();
  await expect(page.locator('#text-size-value')).toHaveText('100%');
  expect(await rootFontPx(page)).toBe(16);
  expect(await textSizeAttr(page)).toBe('100');
});

test('text size: it applies live to the whole app without a reload and is remembered after one', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await openSettings(page);
  const navigations = [];
  page.on('framenavigated', (frame) => navigations.push(frame.url()));
  const heading = page.locator('#step-heading');
  const before = await heading.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  const bodyBefore = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
  await page.locator('#text-size-slider').focus();
  for (let i = 0; i < 5; i += 1) await page.keyboard.press('ArrowRight');
  await expect(page.locator('#text-size-value')).toHaveText('125%');
  expect(await heading.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThan(before);
  expect(await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))).toBe(bodyBefore * 1.25);
  const tool = await page.locator('.tool-label').first().evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(tool).toBeGreaterThan(13.7);
  expect(navigations).toEqual([]);
  expect(await page.evaluate(() => window.localStorage.getItem('eval-coach-text-size'))).toBe('125');
  await page.reload();
  expect(await textSizeAttr(page)).toBe('125');
  expect(await rootFontPx(page)).toBe(20);
});

test('text size: computed sizes follow 80, 100 and 150 from the first paint', async ({ page, request }) => {
  for (const [value, px] of [['80', 12.8], ['100', 16], ['150', 24]]) {
    await openWithStorage(page, request, 'generate', { 'eval-coach-text-size': value });
    expect(await textSizeAttr(page)).toBe(value);
    expect(await rootFontPx(page)).toBeCloseTo(px, 1);
    expect(await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))).toBeCloseTo(px, 1);
  }
});

test('text size: bad and out-of-range stored values fall back to 100 or the nearest limit', async ({ page, request }) => {
  for (const [stored, expected] of [['abc', '100'], ['', '100'], ['NaN', '100'], ['500', '150'], ['10', '80'], ['-20', '80'], ['123', '125']]) {
    await openWithStorage(page, request, 'generate', { 'eval-coach-text-size': stored });
    expect(await textSizeAttr(page), `stored ${JSON.stringify(stored)}`).toBe(expected);
  }
});

test('text size: blocked browser storage still lets the size apply, with no error', async ({ page, request }) => {
  await page.addInitScript(() => {
    const deny = () => {
      throw new DOMException('blocked', 'SecurityError');
    };
    Storage.prototype.setItem = deny;
    Storage.prototype.getItem = deny;
    Storage.prototype.removeItem = deny;
  });
  await openApp(page, request, 'generate');
  await openSettings(page);
  await page.locator('#text-size-slider').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#text-size-value')).toHaveText('105%');
  expect(await textSizeAttr(page)).toBe('105');
});

test('text size on a phone: the range is 90 to 130, a stored 150 becomes 130, the controls are at least 44 pixels tall', async ({ browser, request }) => {
  const { context, page, errors } = await phonePage(browser);
  expect(await page.evaluate(() => window.matchMedia('(pointer: coarse)').matches)).toBe(true);
  await openWithStorage(page, request, 'generate', { 'eval-coach-text-size': '150' });
  expect(await textSizeAttr(page)).toBe('130');
  expect(await rootAttr(page, 'data-phone')).toBe('');
  await openSettings(page);
  const slider = page.locator('#text-size-slider');
  await expect(slider).toHaveAttribute('min', '90');
  await expect(slider).toHaveAttribute('max', '130');
  await expect(page.locator('#text-size-value')).toHaveText('130%');
  await slider.focus();
  await page.keyboard.press('Home');
  await expect(page.locator('#text-size-value')).toHaveText('90%');
  await page.locator('#text-size-default').click();
  await expect(page.locator('#text-size-value')).toHaveText('100%');
  for (const selector of ['#text-size-slider', '#text-size-default', '#reset-progress', '#reset-configuration', '#settings-close']) {
    const box = await page.locator(selector).boundingBox();
    expect(box.height, selector).toBeGreaterThanOrEqual(44);
  }
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  expect(errors).toEqual([]);
  await context.close();
});

test('text size on a narrow desktop window keeps the desktop range', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openApp(page, request, 'generate');
  expect(await rootAttr(page, 'data-phone')).toBeNull();
  await openSettings(page);
  await expect(page.locator('#text-size-slider')).toHaveAttribute('min', '80');
  await expect(page.locator('#text-size-slider')).toHaveAttribute('max', '150');
});

test('layout: data-layout follows the window width divided by the text size', async ({ page, request }) => {
  const layout = () => rootAttr(page, 'data-layout');
  await openApp(page, request, 'generate');
  for (const [width, expected] of [[1280, 'wide'], [1101, 'wide'], [1100, 'mid'], [821, 'mid'], [820, 'narrow'], [390, 'narrow']]) {
    await page.setViewportSize({ width, height: 800 });
    await expect.poll(layout, { message: `${width}px at 100%` }).toBe(expected);
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.evaluate(() => window.EvalCoachDisplay.setSize(150));
  await expect.poll(layout).toBe('mid');
  await page.evaluate(() => window.EvalCoachDisplay.setSize(80));
  await expect.poll(layout).toBe('wide');
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.evaluate(() => window.EvalCoachDisplay.setSize(100));
  await expect.poll(layout).toBe('mid');
  await page.evaluate(() => window.EvalCoachDisplay.setSize(140));
  await expect.poll(layout).toBe('narrow');
});

test('layout: at 100% the wide layout keeps its columns, and a larger size switches to a compact form', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openApp(page, request, 'generate');
  const columns = () => page.locator('#screen-main').evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').map(parseFloat));
  const wide = await columns();
  expect(wide).toHaveLength(2);
  expect(wide[0]).toBeGreaterThan(420);
  expect(await page.locator('#topbar').evaluate((el) => getComputedStyle(el).flexDirection)).toBe('column');
  await page.evaluate(() => window.EvalCoachDisplay.setSize(150));
  await page.setViewportSize({ width: 1200, height: 800 });
  await expect.poll(() => rootAttr(page, 'data-layout')).toBe('narrow');
  expect(await page.locator('#topbar').evaluate((el) => getComputedStyle(el).flexDirection)).toBe('row');
  expect(await sideways(page)).toBeLessThanOrEqual(0);
});

test('terminal: the text follows the text size, the terminal refits, and the CLI session keeps running', async ({ page, request }) => {
  // Tall enough that the AI window head (with its model switch) still leaves the terminal some height at 150%.
  await page.setViewportSize({ width: 1280, height: 1000 });
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect.poll(() => termText(page)).toContain('Fake CLI ready');
  const fontPx = () => page.locator('.xterm-rows').evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(await fontPx()).toBe(14);
  const resizes = async () => (await postsTo(request, '/api/terminal/resize')).map((e) => e.body);
  await expect.poll(async () => (await resizes()).length).toBeGreaterThan(0);
  const first = (await resizes()).pop();
  await page.evaluate(() => window.EvalCoachDisplay.setSize(150));
  await expect.poll(fontPx).toBe(21);
  await expect.poll(async () => (await resizes()).pop().cols).toBeLessThan(first.cols);
  await expect(page.getByText('Your AI is running.')).toBeVisible();
  expect((await postsTo(request, '/api/step/stop')).length).toBe(0);
  const state = await (await request.get('/api/state', { headers: { 'X-Eval-Token': TOKEN } })).json();
  expect(state.terminal.running).toBe(true);
});

// Every visible control must be reachable: inside the window sideways, not covered by another element, and with its text not cut off.
async function layoutProblems(page) {
  return page.evaluate(() => {
    const problems = [];
    const scrollers = (el) => {
      const out = [];
      for (let p = el.parentElement; p; p = p.parentElement) {
        const s = getComputedStyle(p);
        if (s.overflowX !== 'visible' || s.overflowY !== 'visible') out.push(p);
      }
      return out;
    };
    for (const el of document.querySelectorAll('button, input, select, textarea, a[href], summary')) {
      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0 || getComputedStyle(el).visibility === 'hidden') continue;
      if (el.closest('dialog:not([open])') || el.closest('[hidden]') || el.closest('.visually-hidden')) continue;
      const details = el.closest('details');
      if (details && !details.open && !el.closest('summary')) continue; // closed: not on screen
      const cx = box.left + box.width / 2;
      const cy = box.top + box.height / 2;
      const clipped = scrollers(el).some((s) => {
        const r = s.getBoundingClientRect();
        return cx < r.left || cx > r.right || cy < r.top || cy > r.bottom;
      });
      if (clipped || cy < 0 || cy > window.innerHeight) continue; // scrolled out of its box: reached by scrolling
      const label = (el.id || el.className || el.tagName).toString().slice(0, 40);
      if (box.right > window.innerWidth + 1 || box.left < -1) problems.push(`${label}: outside the window sideways`);
      const hit = document.elementFromPoint(cx, cy);
      if (hit && !(el.contains(hit) || hit.contains(el))) problems.push(`${label}: covered by ${(hit.id || hit.className || hit.tagName).toString().slice(0, 40)}`);
      if (el.tagName === 'BUTTON' && el.scrollWidth > el.clientWidth + 1) problems.push(`${label}: text cut off`);
    }
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth) problems.push('the page scrolls sideways');
    for (const id of ['screen-main', 'col-left', 'topbar']) {
      const el = document.getElementById(id);
      if (el && el.scrollWidth > el.clientWidth + 1) problems.push(`#${id} scrolls sideways`);
    }
    return problems;
  });
}

test('layout: every main screen stays usable from 80% to 150% on a desktop window', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const screens = [
    ['step', async () => openApp(page, request, 'generate')],
    ['lesson', async () => openCourse(page, request, 'course-main', ['mission'])],
    ['setup', async () => openApp(page, request, 'preflight')],
    ['settings', async () => {
      await openApp(page, request, 'generate');
      await openSettings(page);
    }],
    ['banner', async () => {
      await openApp(page, request, 'course-first-run');
      await page.locator('#pf-skip').click();
    }],
  ];
  for (const [name, open] of screens) {
    for (const size of [80, 100, 125, 150]) {
      await open();
      await page.evaluate((n) => window.EvalCoachDisplay.setSize(n), size);
      await page.waitForTimeout(250);
      expect(await layoutProblems(page), `${name} at ${size}%`).toEqual([]);
    }
  }
});

test('layout: every main screen stays usable from 90% to 130% on a phone', async ({ browser, request }) => {
  const { context, page, errors } = await phonePage(browser);
  const screens = [
    ['step', async () => openApp(page, request, 'generate')],
    ['lesson', async () => openCourse(page, request, 'course-main', ['mission'])],
    ['setup', async () => openApp(page, request, 'preflight')],
    ['settings', async () => {
      await openApp(page, request, 'generate');
      await openSettings(page);
    }],
    ['banner', async () => {
      await openApp(page, request, 'course-first-run');
      await page.locator('#pf-skip').click();
    }],
  ];
  for (const [name, open] of screens) {
    for (const size of [90, 100, 130]) {
      await open();
      await page.evaluate((n) => window.EvalCoachDisplay.setSize(n), size);
      await page.waitForTimeout(250);
      expect(await layoutProblems(page), `${name} at ${size}%`).toEqual([]);
    }
  }
  expect(errors).toEqual([]);
  await context.close();
});

test('the wizard on a phone: one column, nothing sideways, 44 pixel buttons, the AI window below the working test page', async ({ browser, request }) => {
  const { context, page, errors } = await phonePage(browser);
  await openApp(page, request, 'course-first-run');
  await wizardTo(page, 'track');
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  for (const selector of ['#pf-skip', '#wizard-back', '#wizard-next']) {
    const box = await page.locator(selector).boundingBox();
    expect(box.height, selector).toBeGreaterThanOrEqual(44);
  }
  await page.screenshot({ path: path.join(SHOTS, 'wizard-phone-track.png') });
  await wizardTo(page, 'python');
  expect((await page.locator('#pf-check-all').boundingBox()).height).toBeGreaterThanOrEqual(44);
  await mock(request, 'pf_item', { id: 'working_test', changes: { status: 'needs_you', detail: 'Ready.', next: 'Press Start my AI window.' } });
  await mock(request, 'emit_state');
  await wizardTo(page, 'working_test');
  const form = await page.locator('#pf-item-working_test').boundingBox();
  const terminal = await page.locator('#col-right').boundingBox();
  expect(terminal.y).toBeGreaterThan(form.y + form.height - 1);
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  expect(await layoutProblems(page)).toEqual([]);
  expect(errors).toEqual([]);
  await context.close();
});

test('Settings setup group: setup opens as the full-page wizard, the checks run again, the CLI command can change, and the track stays locked once a step is done', async ({ page, request }) => {
  await openApp(page, request, 'build');
  await openSettings(page);
  await expect(page.locator('#pf-check-all')).toHaveCount(0);
  await page.locator('#settings-setup-open').click();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await expect(page.locator('#topbar')).toBeHidden();
  await expect(page.locator('#pf-skip')).toHaveCount(0);
  await expect(page.locator('#wizard-count')).toHaveText('1 of 7');
  await expect(page.locator('#pf-check-all')).toHaveCount(0);
  await expect(page.locator('input[name="track"]').first()).toBeDisabled();
  await expect(page.locator('#pf-track-locked')).toBeVisible();
  // The Checking your computer page runs the checks by itself, so no button is pressed.
  await page.locator('#wizard-next').click();
  await expect.poll(async () => (await postsTo(request, '/api/preflight/check')).length).toBe(1);
  await wizardTo(page, 'cli');
  await page.locator('#pf-cli-command').fill('other-cli --fast');
  await page.locator('#pf-cli-check').click();
  expect((await postsTo(request, '/api/preflight/cli')).pop().body).toEqual({ cli_command: 'other-cli --fast' });
  await page.locator('#wizard-close').click();
  await expect(page.locator('.settings-page #step-heading')).toHaveText('Settings');
  await expect(page.locator('#settings-open')).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toHaveCount(0);
});

test('Settings setup group: setup can be completed from Settings on a fresh app, and Finish closes back to Settings', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  await openSettings(page);
  await expect(page.locator('#setup-reminder')).toBeVisible();
  await page.locator('#settings-setup-open').click();
  await expect(page.locator('#wizard-close')).toBeVisible();
  await expect(page.locator('#pf-skip')).toHaveCount(0);
  await page.locator('#pf-project-submit').click();
  await expect(page.locator('#pf-item-ai_window')).toBeVisible();
  await page.locator('#wizard-finish').click();
  await expect(page.locator('.settings-page #step-heading')).toHaveText('Settings');
  await expect(page.locator('#setup-reminder')).toHaveCount(0);
  await expect(page.locator('#topbar')).toBeVisible();
  expect((await postsTo(request, '/api/setup')).length).toBe(1);
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
});

const LESSON_WITH_SHOT = {
  title: 'Your AI window',
  intro: 'This is where your AI works for you.',
  legend_heading: 'What is on the screen',
  alt_generic: 'No picture is shown for this AI.',
  reopen_label: 'What am I looking at?',
  close: 'Close',
  captured_label: 'Picture taken on {date}.',
  tools: {
    mycli: {
      image: 'img/icon-glossary.svg',
      alt: 'The AI window with the conversation at the top and the message box at the bottom',
      captured: '2026-11-17',
      markers: [
        { n: 1, x: 20, y: 15, box: { x: 5, y: 5, w: 50, h: 20 }, label: 'The conversation', text: 'Your messages and the answers appear here.' },
        { n: 2, x: 60, y: 80, box: { x: 5, y: 70, w: 80, h: 15 }, label: 'The message box', text: 'Type to your AI here.' },
      ],
    },
  },
  generic: { markers: [{ n: 1, label: 'The conversation', text: 'Generic text.' }] },
};

test('Your AI window page: a screenshot with numbered markers, a text legend, and descriptions on hover and on keyboard focus', async ({ page, request }) => {
  await openPreflight(page, request, { project: { status: 'passed', detail: 'Ready.', next: '' } }, { ai_window_lesson: LESSON_WITH_SHOT });
  await wizardTo(page, 'ai_window');
  await expect(page.locator('.ai-shot-img')).toHaveAttribute('alt', /conversation at the top/);
  await expect(page.locator('.ai-shot figcaption')).toHaveText('Picture taken on 2026-11-17.');
  await expect(page.locator('.ai-marker')).toHaveCount(2);
  await expect(page.locator('#ai-lesson-legend li')).toHaveText([/The conversation Your messages and the answers appear here\./, /The message box Type to your AI here\./]);
  const first = page.locator('#ai-lesson-marker-1');
  await expect(first).toHaveAttribute('aria-describedby', 'ai-lesson-tip-1');
  await expect(first).toHaveAttribute('tabindex', '0');
  await expect(page.locator('#ai-lesson-tip-1')).toBeHidden();
  await first.hover();
  await expect(page.locator('#ai-lesson-tip-1')).toBeVisible();
  await expect(page.locator('#ai-lesson-tip-1')).toContainText('Your messages and the answers appear here.');
  await page.mouse.move(0, 0);
  await expect(page.locator('#ai-lesson-tip-1')).toBeHidden();
  await page.locator('#ai-lesson-marker-2').focus();
  await expect(page.locator('#ai-lesson-tip-2')).toBeVisible();
  await expect(page.locator('#ai-lesson-tip-2')).toContainText('Type to your AI here.');
  await page.screenshot({ path: path.join(SHOTS, 'wizard-ai-window.png') });
  // The part of the picture a marker describes is highlighted while it is hovered or focused, and only then.
  const region = (n) => page.locator(`.ai-region[data-n="${n}"]`);
  await expect(region(1)).toBeHidden();
  await expect(region(2)).toBeVisible();
  await page.mouse.move(0, 0);
  await page.evaluate(() => document.activeElement.blur());
  await page.locator('#ai-lesson-marker-1').hover();
  await expect(region(2)).toBeHidden();
  const frame = await page.locator('.ai-shot-frame').boundingBox();
  const box = await region(1).boundingBox();
  expect(Math.abs(box.x - (frame.x + frame.width * 0.05))).toBeLessThan(3);
  expect(Math.abs(box.width - frame.width * 0.5)).toBeLessThan(3);
  await page.mouse.move(0, 0);
  await page.locator('#ai-lesson-legend li').nth(1).hover();
  await expect(region(2)).toBeVisible();
  await page.mouse.move(0, 0);
  await expect(region(2)).toBeHidden();
  // Nothing about this page is saved as progress.
  const posts = (await mockLog(request)).log.filter((e) => e.method === 'POST').map((e) => e.path);
  expect(posts.filter((p) => /setup|lesson|step/.test(p))).toEqual([]);
});

test('Your AI window page: with no screenshot (the stand-in) it shows the legend text only', async ({ page, request }) => {
  await openPreflight(page, request, { project: { status: 'passed', detail: 'Ready.', next: '' } });
  await wizardTo(page, 'ai_window');
  await expect(page.locator('.ai-shot-img')).toHaveCount(0);
  await expect(page.locator('#ai-lesson-generic')).toBeVisible();
  await expect(page.locator('#ai-lesson-legend li')).toHaveCount(5);
  await expect(page.locator('#ai-lesson-legend')).toContainText('Approval requests');
  await expect(page.locator('#wizard-finish')).toBeVisible();
});

test('Your AI window page at a narrow width: nothing overflows and the markers stay inside the picture', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await openPreflight(page, request, { project: { status: 'passed', detail: 'Ready.', next: '' } }, { ai_window_lesson: LESSON_WITH_SHOT });
  await wizardTo(page, 'ai_window');
  await expect(page.locator('.ai-marker')).toHaveCount(2);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const frame = await page.locator('.ai-shot-frame').boundingBox();
  for (const n of [1, 2]) {
    const box = await page.locator(`#ai-lesson-marker-${n}`).boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(frame.x - 1);
    expect(box.x + box.width).toBeLessThanOrEqual(frame.x + frame.width + 1);
  }
  await page.screenshot({ path: path.join(SHOTS, 'wizard-ai-window-narrow.png') });
});

test('What am I looking at? opens the lesson from Settings and closes back to Settings', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await openSettings(page);
  await page.locator('#settings-ai-window').click();
  const dialog = page.locator('dialog.overlay-ai-window[open]');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('h2')).toHaveText('Your AI window');
  await expect(dialog.locator('#ai-lesson-dialog-legend li')).toHaveCount(5);
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('.settings-page #step-heading')).toHaveText('Settings');
  const posts = (await mockLog(request)).log.filter((e) => e.method === 'POST').map((e) => e.path);
  expect(posts.filter((p) => /stop|reset|submit|check|complete/.test(p))).toEqual([]);
});

test('What am I looking at? in the AI window opens the lesson and the AI keeps running', async ({ page, request }) => {
  await openApp(page, request, 'generate');
  await page.locator('#cli-start').click();
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  await page.locator('#ai-window-open').click();
  const dialog = page.locator('dialog.overlay-ai-window[open]');
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('#term-head .term-status')).toHaveText('Your AI is running.');
  expect((await postsTo(request, '/api/step/stop')).length).toBe(0);
});

test('Settings reset: Reset lesson progress asks first, defaults to keeping everything, then clears and names the backup', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openWithStorage(page, request, 'course-main', { 'eval-coach-text-size': '130', 'eval-coach-theme': 'dark' });
  await mock(request, 'lesson_status', { id: 'mission', status: 'done' });
  await page.reload();
  await enterPart(page);
  await openSettings(page);
  await page.locator('#reset-progress').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('h2')).toHaveText('Reset lesson progress?');
  await expect(dialog.locator('#reset-clears li')).not.toHaveCount(0);
  await expect(dialog.locator('#reset-keeps li')).not.toHaveCount(0);
  await expect(dialog.locator('#reset-backup-note')).toContainText('reset-backup');
  await expect(dialog.locator('#reset-backup-note')).toContainText('replaces the previous backup');
  expect(await page.evaluate(() => document.activeElement.textContent)).toBe('Keep everything');
  await dialog.getByRole('button', { name: 'Keep everything' }).click();
  expect((await postsTo(request, '/api/reset/progress')).length).toBe(0);
  await page.locator('#reset-progress').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Reset lesson progress' }).click();
  await expect(page.locator('#reset-result')).toContainText('reset-backup');
  expect((await postsTo(request, '/api/reset/progress'))[0].body).toEqual({ confirm: true });
  expect(await textSizeAttr(page)).toBe('130');
  expect(await rootAttr(page, 'data-theme')).toBe('dark');
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await expect(page.locator('.course-item', { hasText: 'Your mission' })).toContainText('Now');
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toHaveCount(0);
});

test('Settings reset: Reset app configuration says progress is cleared too, then returns to first run and the default look', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openWithStorage(page, request, 'course-main', { 'eval-coach-text-size': '140', 'eval-coach-theme': 'dark' });
  await openSettings(page);
  await page.locator('#reset-configuration').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog.locator('h2')).toHaveText('Reset app configuration?');
  await expect(dialog).toContainText('lesson progress');
  await expect(dialog.locator('.btn-danger')).toHaveText('Reset app configuration');
  expect(await page.evaluate(() => document.activeElement.textContent)).toBe('Keep everything');
  await dialog.getByRole('button', { name: 'Keep everything' }).click();
  expect((await postsTo(request, '/api/reset/configuration')).length).toBe(0);
  expect(await textSizeAttr(page)).toBe('140');
  await page.locator('#reset-configuration').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Reset app configuration' }).click();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await expect(page.locator('#pf-skip')).toBeVisible();
  await expect(page.locator('#wizard-count')).toHaveText('1 of 7');
  await expect(page.locator('#reset-result')).toContainText('reset-backup');
  expect(await textSizeAttr(page)).toBe('100');
  expect(await rootAttr(page, 'data-theme')).toBe('light');
  expect(await page.evaluate(() => window.localStorage.getItem('eval-coach-text-size'))).toBeNull();
  expect(await page.evaluate(() => window.localStorage.getItem('eval-coach-theme'))).toBeNull();
  await expect(page.locator('#setup-reminder')).toHaveCount(0);
  // Finishing setup again lands on the Series map, not inside the Part.
  await page.locator('#pf-skip').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
});

// ---- The Series map ----------------------------------------------------------------

const PART_TITLES = [
  'Part 1: Structured prompting',
  'Part 2: Defining evaluation criteria',
  'Part 3: Running evals and baseline',
  'Part 4: Iterating with evaluation-driven development',
  'Part 5: Load-bearing audit and packaging',
  'Part 6: Your own task',
];
const LESSON_IDS = ['mission', 'hook', 'several-runs', 'rules', 'trust', 'surprise', 'baseline-why'];

async function openMap(page, request, scenario, done) {
  await mock(request, 'reset', { scenario });
  for (const id of done || []) await mock(request, 'lesson_status', { id, status: 'done' });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Series map');
}

const postsLog = async (request) => (await mockLog(request)).log.filter((e) => e.method === 'POST').map((e) => e.path);

test('Series map: the app opens on it after a launch and after a reload, with six Parts in order', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  await expect(page.locator('#series-list > li')).toHaveCount(6);
  expect(await page.locator('.series-title').allTextContents()).toEqual(PART_TITLES);
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await page.reload();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(page.locator('#series-list > li')).toHaveCount(6);
  await expect(page.locator('.lesson-page')).toHaveCount(0);
});

test('Series map: Parts 4 and 5 say Coming soon and do nothing, Part 6 says Live meeting and explains itself', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  const soon = page.locator('.series-row.k-soon');
  await expect(soon).toHaveCount(2);
  await expect(page.locator('#series-part-1')).toHaveClass(/k-course/);
  await expect(page.locator('#series-part-2')).toHaveClass(/k-course/);
  expect(await soon.locator('.series-title').allTextContents()).toEqual([PART_TITLES[3], PART_TITLES[4]]);
  for (const row of await soon.all()) {
    await expect(row.locator('.series-tag')).toHaveText('Coming soon');
    await expect(row.locator('.series-outcome')).not.toHaveText('');
    await expect(row.locator('button, a, [tabindex], .series-chevron')).toHaveCount(0);
    await row.click();
    await page.keyboard.press('Enter');
  }
  const live = page.locator('.series-row.k-live');
  await expect(live).toHaveCount(1);
  await expect(live).toContainText('Part 6');
  await expect(live.locator('.series-tag')).toHaveText('Live meeting');
  await expect(live).not.toContainText('Coming soon');
  await expect(live.locator('.series-outcome')).toContainText('live');
  await expect(live.locator('.series-outcome')).toContainText('checked by rules');
  await expect(live).not.toContainText(/office hours|AIR discussion|session/i);
  await expect(live.locator('button, a, [tabindex], .series-chevron')).toHaveCount(0);
  await live.click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  expect(await postsLog(request)).toEqual([]);
});

test('Series map: Part 1 is no longer coming soon; its row shows its state, its count and an open control', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  const row = page.locator('#series-part-1');
  await expect(row.locator('.series-tag')).toHaveCount(0);
  await expect(row).not.toContainText('Coming soon');
  await expect(row).toContainText('Not started');
  await expect(row.locator('.series-action')).toHaveText('Start');
  await expect(row.locator('.series-count')).toHaveCount(0);
  await expect(row.locator('#series-open-part-1')).toBeVisible();
  await expect(row.locator('#series-toggle-part-1')).toBeVisible();
  await mock(request, 'part1', { done: 3, statuses: { 'p1-mission': 'done', 'p1-gaps': 'active' } });
  await page.reload();
  await expect(row).toContainText('In progress');
  await expect(row.locator('.series-action')).toHaveText('Continue');
  await expect(row.locator('.series-count')).toHaveText('3 of 9 done');
  await expect(page.locator('#series-part-3 .series-count')).not.toHaveText('3 of 9 done');
});

test('Series map: Parts 1, 2 and 3 start expanded and each lists its own lessons', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  await expect(page.locator('#series-toggle-part-1')).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#series-toggle-part-2')).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#series-toggle-part-3')).toHaveAttribute('aria-expanded', 'true');
  const part1 = page.locator('#series-lessons-part-1 li');
  await expect(part1).toHaveCount(4);
  await expect(part1.first()).toContainText('Your mission');
  await expect(part1.first()).toContainText('Now');
  await expect(part1.last()).toContainText('Not started');
  await expect(page.locator('#series-lessons-part-2 li')).toHaveCount(4);
  await expect(page.locator('#series-lessons-part-3 li')).toHaveCount(7);
  await page.locator('#series-toggle-part-1').click();
  await expect(page.locator('#series-lessons-part-1')).toBeHidden();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  expect(await postsLog(request)).toEqual([]);
});

test('Series map: the Part 3 row expands and collapses by mouse and keyboard without opening the Part', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  const toggle = page.locator('#series-toggle-part-3');
  const lessons = page.locator('#series-lessons-part-3');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(lessons.locator('li')).toHaveCount(7);
  await expect(lessons.locator('li').first()).toContainText('Your mission');
  await expect(lessons.locator('li').first()).toContainText('Done');
  await expect(lessons.locator('li').nth(1)).toContainText('Now');
  await expect(lessons.locator('li').last()).toContainText('Not started');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(lessons).toBeHidden();
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(lessons).toBeVisible();
  await page.keyboard.press('Space');
  await expect(lessons).toBeHidden();
  await page.keyboard.press('Space');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.activeElement.id)).toBe('series-open-part-3');
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  expect(await postsLog(request)).toEqual([]);
});

test('Series map: the Part 3 row says Start, Continue or Review, shows the same count as the sidebar, and opens the current item', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  const row = page.locator('#series-part-3');
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(row).toContainText('Not started');
  await expect(row.locator('.series-action')).toHaveText('Start');
  await expect(row.locator('.series-count')).toHaveCount(0);

  await openMap(page, request, 'course-main', ['mission']);
  await expect(row).toContainText('In progress');
  await expect(row.locator('.series-action')).toHaveText('Continue');
  const count = (await row.locator('.series-count').innerText()).match(/^(\d+) of (\d+) done$/);
  expect(count).not.toBeNull();
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
  await expect(page.locator('.journey-text')).toContainText(`${count[1]} of ${count[2]}`);

  await mock(request, 'reset', { scenario: 'course-main' });
  for (const id of LESSON_IDS) await mock(request, 'lesson_status', { id, status: 'done' });
  await mock(request, 'step_index', { index: 9 });
  await page.reload();
  await expect(row).toContainText('Done');
  await expect(row.locator('.series-action')).toHaveText('Review');
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('You have finished the course');
});

test('Series map: Back to series map keeps progress and the map shows it; Continue resumes where the participant stopped', async ({ page, request }) => {
  await openCourse(page, request, 'course-main', ['mission', 'hook']);
  await expect(page.locator('#step-heading')).toHaveText('Why several answers');
  const back = page.locator('#back-to-series');
  await expect(back).toBeVisible();
  await expect(back).toContainText('Back to series map');
  const before = await page.locator('.journey-text').innerText();
  await page.screenshot({ path: path.join(SHOTS, 'series-back-wide.png') });
  await back.click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(page.locator('#back-to-series')).toHaveCount(0);
  const count = (await page.locator('#series-part-3 .series-count').innerText()).match(/^(\d+) of (\d+)/);
  expect(before).toContain(`${count[1]} of ${count[2]}`);
  await enterPart(page);
  await expect(page.locator('#step-heading')).toHaveText('Why several answers');
  expect((await postsLog(request)).filter((p) => /complete|skip|reset|stop|release/.test(p))).toEqual([]);
});

test('Series map: the sidebar tools work on the map, it shows no progress or course list, and the collapsed state is shared', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await openCourse(page, request, 'course-main', ['mission']);
  await page.locator('#nav-toggle').click();
  expect(await rootAttr(page, 'data-nav')).toBe('collapsed');
  await page.locator('#back-to-series').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  expect(await rootAttr(page, 'data-nav')).toBe('collapsed');
  await page.locator('#nav-toggle').click();
  expect(await rootAttr(page, 'data-nav')).toBe('expanded');
  await expect(page.locator('.journey')).toHaveCount(0);
  await expect(page.locator('.course-nav')).toHaveCount(0);
  await expect(page.locator('.brand-sub')).toHaveText('Evaluated Systems (Stage 3)');
  for (const id of ['#glossary-open', '#reference-link', '#theme-toggle', '#settings-open', '#quit']) await expect(page.locator(id)).toBeVisible();
  const ids = await page.locator('.topbar-tools > *').evaluateAll((els) => els.map((e) => e.id));
  expect(ids).toEqual(['glossary-open', 'reference-link', 'theme-toggle', 'settings-open', 'quit']);
  await page.locator('#theme-toggle').click();
  expect(await rootAttr(page, 'data-theme')).toBe('dark');
  await page.locator('#glossary-open').click();
  await expect(page.locator('dialog[open]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#quit').click();
  await expect(page.locator('dialog.confirm[open]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('dialog.confirm[open]')).toHaveCount(0);
  expect((await postsLog(request)).filter((p) => p.includes('quit'))).toEqual([]);
});

test('Series map: Settings opened from the map or from a Part returns to where it started', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  await page.locator('#settings-open').click();
  await expect(page.locator('.settings-page #step-heading')).toHaveText('Settings');
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await page.locator('#settings-open').click();
  await page.locator('#settings-setup-open').click();
  await page.locator('#wizard-close').click();
  await expect(page.locator('.settings-page #step-heading')).toHaveText('Settings');
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await enterPart(page);
  await openSettings(page);
  await page.locator('#settings-close').click();
  await expect(page.locator('#step-heading')).toHaveText('One update, three grades');
});

test('Series map: the setup banner shows on the map, and closing setup from it returns to the map', async ({ page, request }) => {
  await openApp(page, request, 'course-first-run');
  await page.locator('#pf-skip').click();
  const banner = page.locator('#setup-reminder');
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(banner).toBeVisible();
  await page.locator('#setup-banner-go').click();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await page.locator('#wizard-close').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(banner).toBeVisible();
  await enterPart(page);
  await expect(page.locator('.lesson-page')).toBeVisible();
  await expect(page.locator('.series-list')).toHaveCount(0);
  const locked = await page.locator('.course-item.s-locked').count();
  expect(locked).toBeGreaterThan(0);
});

test('Series map: on a narrow screen the Back control is in the top bar and the map fits without sideways scrolling', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMap(page, request, 'course-main', ['mission']);
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  await enterPart(page);
  const back = page.locator('#back-to-series');
  await expect(back).toBeVisible();
  const bar = await page.locator('#topbar').boundingBox();
  const box = await back.boundingBox();
  expect(box.y).toBeGreaterThanOrEqual(bar.y);
  expect(box.y + box.height).toBeLessThanOrEqual(bar.y + bar.height + 1);
  await page.screenshot({ path: path.join(SHOTS, 'series-back-narrow.png') });
  await back.click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
});

// Contrast of an element's text on the nearest opaque background behind it.
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
        bg = c;
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

test('Series map: labels are readable in both themes, and the map fits at three widths and the largest text size', async ({ page, request }) => {
  for (const theme of ['light', 'dark']) {
    for (const width of [1280, 900, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await openWithStorage(page, request, 'course-main', { 'eval-coach-theme': theme });
      await page.goto(`/?t=${TOKEN}`);
      await expect(page.locator('#step-heading')).toHaveText('Series map');
      expect(await sideways(page), `${theme} ${width}`).toBeLessThanOrEqual(0);
      for (const selector of ['.series-tag', '.series-state', '.series-action', '.series-outcome', '.series-count', '.series-lesson-status']) {
        expect(await textContrast(page, selector), `${theme} ${width} ${selector}`).toBeGreaterThanOrEqual(4.5);
      }
      await page.waitForTimeout(450);
      await page.screenshot({ path: path.join(SHOTS, `series-map-${theme}-${width}.png`), fullPage: true });
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await openWithStorage(page, request, 'course-main', { 'eval-coach-text-size': '150' });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  expect(await sideways(page)).toBeLessThanOrEqual(0);
  await page.locator('#nav-toggle').click();
  expect(await sideways(page)).toBeLessThanOrEqual(0);
});

test('Series map: resetting the app configuration ends on setup first and then on the map', async ({ page, request }) => {
  await openMap(page, request, 'course-main', ['mission']);
  await page.locator('#settings-open').click();
  await page.locator('#reset-configuration').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Reset app configuration' }).click();
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible();
  await page.locator('#pf-skip').click();
  await expect(page.locator('#step-heading')).toHaveText('Series map');
  await expect(page.locator('#series-toggle-part-3')).toHaveAttribute('aria-expanded', 'true');
});
