// Course locking in the interface, tested against the real app (real_server.py) as a participant's own run:
// demo access is off, so the Part rule, the lock refusals, "Skip this Part" and the hidden demo entry are the real ones.
const { test: base, expect } = require('./.tmp/node_modules/@playwright/test');

const TOKEN = 'dev-token';
const PORT = Number(process.env.PART1_TEST_PORT) || 38927;
const CONTROL = `http://127.0.0.1:${PORT + 1}`;
const CSP_WORDS = /content security policy|refused to|csp/i;
const TIP = 'Opens when the previous ones are done';
const DEMO_PASSWORD = 'throwaway-test-password';

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

async function api(request, method, path, data) {
  const res = await request.fetch(path, {
    method,
    data,
    headers: { 'X-Eval-Token': TOKEN, ...(data ? { 'Content-Type': 'application/json' } : {}) },
  });
  return { status: res.status(), body: await res.json() };
}

// A participant's own run: setup passed, demo access off.
async function openMap(page, request, extra) {
  await control(request, '/control/reset', { scenario: 'ready', demo: false, ...(extra || {}) });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Series map');
}

test('the map opens on the active Part only, and the later Parts are locked and do nothing', async ({ page, request }) => {
  await openMap(page, request);
  await expect(page.locator('#series-toggle-part-1')).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#series-toggle-part-2')).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('#series-toggle-part-3')).toHaveAttribute('aria-expanded', 'false');
  for (const id of ['part-2', 'part-3']) {
    const row = page.locator(`#series-${id}`);
    const open = page.locator(`#series-open-${id}`);
    await expect(row).toContainText('Not started');
    await expect(row.getByRole('img', { name: 'Not open yet' })).toBeVisible();
    await expect(row.locator('.series-action')).toHaveCount(0);
    await expect(row.locator('.series-count')).toHaveCount(0);
    await expect(open).toHaveAttribute('aria-disabled', 'true');
    await open.click({ force: true });
    await expect(page.locator('#step-heading')).toHaveText('Series map');
    await open.focus();
    await expect(row.locator('.lock-tip')).toBeVisible();
    await expect(row.locator('.lock-tip')).toHaveText(TIP);
    await expect(open).toHaveAccessibleDescription(TIP);
    await page.keyboard.press('Enter');
    await page.keyboard.press('Space');
    await expect(page.locator('#step-heading')).toHaveText('Series map');
  }
  await expect(page.locator('#series-open-part-1')).not.toHaveAttribute('aria-disabled', 'true');
  await expect(page.locator('#series-part-1 .series-action')).toHaveText('Start');
  // A locked Part still expands, and shows its lessons as Locked.
  await page.locator('#series-toggle-part-3').click();
  await expect(page.locator('#series-lessons-part-3 li').first()).toContainText('Not started');
  await expect(page.locator('#step-heading')).toHaveText('Series map');
});

test('"Skip this Part" is on the open Part only, and its confirm says what is given up', async ({ page, request }) => {
  await openMap(page, request);
  await expect(page.locator('#series-skip-part-1')).toBeVisible();
  await expect(page.locator('#series-skip-part-2')).toHaveCount(0);
  await expect(page.locator('#series-skip-part-3')).toHaveCount(0);
  await page.locator('#series-skip-part-1').click();
  const dialog = page.locator('dialog.confirm[open]');
  await expect(dialog.getByRole('heading', { name: 'Skip Part 1: Structured prompting?' })).toBeVisible();
  await expect(dialog.locator('#skip-teaches')).toContainText('tell your AI clearly');
  await expect(dialog.locator('#skip-matters')).toContainText('steadier');
  await expect(dialog.locator('#skip-cost')).toContainText('no artifact and no evaluator');
  await dialog.getByRole('button', { name: 'Keep the Part' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('#series-part-1')).not.toContainText('Skipped');
  expect((await api(request, 'GET', '/api/state')).body.series.parts[0].state).toBe('not_started');
  expect((await api(request, 'GET', '/api/state')).body.series.parts[1].state).toBe('locked');
});

test('a confirmed skip marks the Part Skipped, opens the next Part, and its lessons read as read-only', async ({ page, request }) => {
  await openMap(page, request);
  await page.locator('#series-skip-part-1').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Skip the Part' }).click();
  const part1 = page.locator('#series-part-1');
  await expect(part1).toContainText('Skipped');
  await expect(part1.locator('.skip-icon')).toBeVisible();
  await expect(part1.locator('.series-action')).toHaveCount(0);
  await expect(part1.locator('.series-count')).toHaveCount(0);
  await expect(page.locator('#series-skip-part-1')).toHaveCount(0);
  await expect(page.locator('#series-part-2')).toContainText('Not started');
  await expect(page.locator('#series-part-2 .series-action')).toHaveText('Start');
  await expect(page.locator('#series-skip-part-2')).toBeVisible();
  await expect(page.locator('#series-part-3')).toContainText('Not started');
  await expect(page.locator('#series-open-part-3')).toHaveAttribute('aria-disabled', 'true');
  // Its lessons list Skipped in the expanded list.
  await page.locator('#series-toggle-part-1').click();
  await expect(page.locator('#series-lessons-part-1 li').first()).toContainText('Skipped');
  // Opening it reads: the lesson text with a note, and nothing to do.
  await page.locator('#series-open-part-1').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await expect(page.locator('#skipped-part-note')).toContainText('You skipped this Part');
  await expect(page.locator('#lesson-continue')).toHaveCount(0);
  await expect(page.locator('.course-item.s-skipped').first()).toBeVisible();
  // The skip is remembered after a reload.
  await page.reload();
  await expect(page.locator('#series-part-1')).toContainText('Skipped');
});

test('a locked lesson or step is refused by the server and carries no text', async ({ page, request }) => {
  await openMap(page, request);
  const lesson = await api(request, 'GET', '/api/lesson?id=hook');
  expect(lesson.status).toBe(400);
  expect(lesson.body.error.code).toBe('lesson_locked');
  expect(lesson.body.error.message).toBe(TIP);
  expect(JSON.stringify(lesson.body)).not.toContain('"body"');
  const step = await api(request, 'GET', '/api/state?step=cold');
  expect(step.status).toBe(400);
  expect(step.body.error.code).toBe('step_locked');
  const key = await api(request, 'GET', '/api/state?step=key');
  expect(key.body.error.code).toBe('step_locked');
  const part2 = await api(request, 'GET', '/api/lesson?id=p2-mission');
  expect(part2.body.error.code).toBe('lesson_locked');
});

test('inside an open Part the later lessons and steps are greyed, with the tooltip, and pressing one opens nothing', async ({ page, request }) => {
  await openMap(page, request);
  await page.locator('#series-open-part-1').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await page.locator('.course-summary').click();
  const items = page.locator('.course-item.s-locked');
  expect(await items.count()).toBeGreaterThan(0);
  const locked = items.first();
  await expect(locked).toContainText('Not started');
  await expect(locked.getByRole('img', { name: 'Not open yet' })).toBeVisible();
  const button = locked.getByRole('button');
  await expect(button).toHaveAttribute('aria-disabled', 'true');
  await button.click({ force: true });
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await button.focus();
  await expect(locked.locator('.lock-tip')).toBeVisible();
  await expect(locked.locator('.lock-tip')).toHaveText(TIP);
});

test('a locked lesson in the related list is plain text, and an open one is a link', async ({ page, request }) => {
  await openMap(page, request, { demo: true });
  await page.locator('#series-open-part-3').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  const related = page.locator('.related-list');
  await expect(related.getByRole('button')).toHaveCount(0);
  await expect(related.locator('.related-locked').first()).toContainText('Not started');
});

test('demo access: four selections of the version reveal nothing, five reveal the group, and a wrong password changes nothing', async ({ page, request }) => {
  await openMap(page, request);
  await page.locator('#settings-open').click();
  await expect(page.locator('#settings-version')).toHaveText(/^Version \d/);
  await expect(page.locator('#settings-demo')).toHaveCount(0);
  for (let i = 0; i < 4; i += 1) await page.locator('#settings-version').click();
  await expect(page.locator('#settings-demo')).toHaveCount(0);
  await page.locator('#settings-close').click();
  await page.locator('#settings-open').click();
  for (let i = 0; i < 4; i += 1) await page.locator('#settings-version').click();
  await expect(page.locator('#settings-demo')).toHaveCount(0); // the count restarts when Settings is left
  await page.locator('#settings-version').click();
  await expect(page.locator('#settings-demo')).toBeVisible();
  await page.locator('#demo-password').fill('not the password');
  await page.locator('#demo-unlock').click();
  await expect(page.locator('#demo-error')).toHaveText('That password was not accepted.');
  await expect(page.locator('#demo-notice')).toHaveCount(0);
  expect((await api(request, 'GET', '/api/state')).body.demo.on).toBe(false);
  expect((await api(request, 'GET', '/api/state')).body.series.parts[2].state).toBe('locked');
});

test('demo access: the right password opens every Part with a notice on every screen, and turning it off locks them again', async ({ page, request }) => {
  await openMap(page, request);
  await page.locator('#settings-open').click();
  for (let i = 0; i < 5; i += 1) await page.locator('#settings-version').click();
  await page.locator('#demo-password').fill(DEMO_PASSWORD);
  await page.locator('#demo-unlock').click();
  const notice = page.locator('#demo-notice');
  await expect(notice).toBeVisible();
  await expect(notice).toHaveAttribute('role', 'status');
  await expect(notice).toContainText('Demo access is on');
  await expect(page.locator('#demo-lock')).toBeVisible();
  await expect(page.locator('#demo-password')).toHaveCount(0);
  expect(await page.evaluate(() => document.querySelector('#demo-notice').contains(document.activeElement))).toBe(false);
  await page.locator('#settings-close').click();
  await expect(notice).toBeVisible();
  await expect(page.locator('#series-part-3')).toContainText('Not started');
  await expect(page.locator('#series-open-part-3')).not.toHaveAttribute('aria-disabled', 'true');
  // Part 3 opens at its first item only.
  await page.locator('#series-open-part-3').click();
  await expect(page.locator('#step-heading')).toHaveText('Your mission');
  await expect(notice).toBeVisible();
  expect((await api(request, 'GET', '/api/lesson?id=hook')).body.error.code).toBe('lesson_locked');
  // A reload keeps it, because the run is the same.
  await page.reload();
  await expect(notice).toBeVisible();
  // Turning it off locks Part 3 again.
  await page.locator('#settings-open').click();
  await page.locator('#demo-lock').click();
  await expect(notice).toHaveCount(0);
  await page.locator('#settings-close').click();
  const state = (await api(request, 'GET', '/api/state')).body;
  expect(state.demo.on).toBe(false);
  expect(state.series.parts[2].state).toBe('locked');
});

test('demo access: nothing about it shows before it is revealed', async ({ page, request }) => {
  await openMap(page, request);
  const everything = async () => (await page.locator('body').innerText()).toLowerCase();
  expect(await everything()).not.toContain('demo');
  await page.locator('#settings-open').click();
  expect(await everything()).not.toContain('demo');
  await page.locator('#glossary-open').click();
  expect(await everything()).not.toContain('demo access');
});

test('without a hash in the build, selecting the version five times reveals nothing', async ({ page, request }) => {
  await openMap(page, request);
  await page.route('**/api/state*', async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    json.demo = { available: false, on: false };
    await route.fulfill({ response, json });
  });
  await page.reload();
  await page.locator('#settings-open').click();
  for (let i = 0; i < 6; i += 1) await page.locator('#settings-version').click();
  await expect(page.locator('#settings-demo')).toHaveCount(0);
});

// Locked rows, the Skipped row, the lock tooltip and the demo notice stay readable and inside the window, in both
// themes, at the default and the largest text size, on a desktop and a phone-wide window.
async function sidewaysOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test('the lock, the Skipped state and the demo notice fit at the largest text size in both themes', async ({ page, request }) => {
  await openMap(page, request);
  await page.locator('#series-skip-part-1').click();
  await page.locator('dialog.confirm[open]').getByRole('button', { name: 'Skip the Part' }).click();
  await expect(page.locator('#series-part-1')).toContainText('Skipped');
  await page.locator('#settings-open').click();
  for (let i = 0; i < 5; i += 1) await page.locator('#settings-version').click();
  await page.locator('#demo-password').fill(DEMO_PASSWORD);
  await page.locator('#demo-unlock').click();
  await expect(page.locator('#demo-notice')).toBeVisible();
  await page.locator('#settings-close').click();
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ['light', 'dark']) {
      for (const size of [100, 150]) {
        await page.evaluate(([t, n]) => {
          window.EvalCoachDisplay.setSize(n);
          document.documentElement.setAttribute('data-theme', t);
        }, [theme, size]);
        await page.waitForTimeout(250);
        expect(await sidewaysOverflow(page), `map at ${width}px, ${theme}, ${size}%`).toBeLessThanOrEqual(0);
        for (const id of ['#series-part-1', '#series-part-3']) await expect(page.locator(id)).toBeVisible();
        await expect(page.locator('#demo-notice')).toBeVisible();
      }
    }
  }
});
