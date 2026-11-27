// Part 4's step panels in the interface, tested against the real app (real_server.py): the real engine, course content
// and server, with a pseudo console that never starts a program. A test sets up where the participant is through the
// app's own API and writes the files the AI would write (the five answers, the participant's log entry) straight into
// the project folder, as the stand-in tests do. The app is run on the Script track: this server has no private Node, so
// the promptfoo checker of Part 4 is covered by the Python tests, and the panels read the same data on either track.
const { test: base, expect } = require('./.tmp/node_modules/@playwright/test');
const fs = require('fs');
const path = require('path');

const TOKEN = 'dev-token';
const PORT = Number(process.env.PART1_TEST_PORT) || 38927;
const CONTROL = `http://127.0.0.1:${PORT + 1}`;
const SHOTS = path.join(__dirname, '.tmp', 'screenshots');
const ROOT = path.join(__dirname, '..', '..');
const CONTENT = path.join(ROOT, 'app', 'eval_coach', 'content');
const CSP_WORDS = /content security policy|refused to|csp/i;

const readJson = (file) => JSON.parse(fs.readFileSync(path.join(CONTENT, file), 'utf8'));
const LESSONS = Object.fromEntries(readJson('part-4-lessons.json').lessons.map((l) => [l.id, l]));
const STEPS = readJson('part-4-steps.json').steps;
const KNOWN_GOOD = fs.readFileSync(path.join(ROOT, 'app', 'eval_coach', 'kit', 'northwind', 'sample-run-1.txt'), 'utf8');
const goldenRun = (round, n) => fs.readFileSync(path.join(ROOT, 'tests', 'golden', 'part4-worked', `round-${round}`, `run-${n}.txt`), 'utf8');
const HYPOTHESIS = 'Factual tone should rise, because a concrete line names what to avoid.';

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

// ---- the app's own API, used to set up where the participant is ----------------------------------------

const headers = { 'X-Eval-Token': TOKEN };

async function control(request, data) {
  const res = await request.post(`${CONTROL}/control/reset`, { data });
  expect(res.ok()).toBeTruthy();
}

async function getState(request, query) {
  const res = await request.get(`/api/state${query || ''}`, { headers });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function post(request, route, data) {
  const res = await request.post(route, { headers, data });
  const body = await res.json();
  expect(body.ok, JSON.stringify(body.error || body).slice(0, 300)).toBe(true);
}

const submit = (request, step, data) => post(request, '/api/step/submit', { step, data });
const stepView = async (request, id) => (await getState(request, `?part=part-4&step=${id}`)).step;
const projectOf = async (request) => (await getState(request)).setup.project_path;

function lessonAnswer(activity) {
  if (activity.type === 'choice') return { option: activity.options.find((o) => o.correct).id };
  if (activity.type === 'order') return { order: activity.items.map((i) => i.id) };
  if (activity.type === 'sort') return { placements: Object.fromEntries(activity.items.map((i) => [i.id, i.bucket])) };
  return { text: Array(activity.min_words).fill('thinking').join(' ') };
}

async function finishLesson(request, id) {
  for (const activity of LESSONS[id] ? LESSONS[id].activities : []) {
    await post(request, '/api/lesson/answer', { lesson: id, activity: activity.id, answer: lessonAnswer(activity) });
  }
  await post(request, '/api/lesson/complete', { lesson: id });
}

// Finishes every Part 4 lesson before `target`. The steps before it are the caller's.
async function lessonsBefore(request, target) {
  const { course } = await getState(request, '?part=part-4');
  for (const item of course) {
    if (item.id === target) return;
    if (item.kind === 'lesson' && item.status !== 'done') await finishLesson(request, item.id);
  }
}

async function reachStep(request, target) {
  await lessonsBefore(request, target);
}

const attemptDir = (project, n) => path.join(project, 'part-4', 'practice', 'attempts', String(n));
const practiceLog = (project) => path.join(project, 'part-4', 'practice', 'iteration-log.md');

async function startPractice(request) {
  await reachStep(request, 'starting-point');
  await submit(request, 'starting-point', { action: 'choose', choice: 'practice' });
  await reachStep(request, 'known-good');
  await submit(request, 'known-good', { action: 'save', text: KNOWN_GOOD });
}

async function writeRound(request, n, hypothesis = HYPOTHESIS) {
  await reachStep(request, `hypothesis-${n}`);
  await submit(request, `hypothesis-${n}`, { action: 'save', text: hypothesis });
  await editRound(request, n);
}

async function editRound(request, n) {
  const dir = attemptDir(await projectOf(request), n);
  const prompt = fs.readFileSync(path.join(dir, 'prompt.md'), 'utf8');
  await submit(request, `edit-${n}`, { action: 'save', prompt: `${prompt.trimEnd()}\n- Tone: factual. Do not use praise words.\n` });
}

function writeRuns(project, n, round) {
  const dir = path.join(attemptDir(project, n), 'runs');
  fs.mkdirSync(dir, { recursive: true });
  for (let k = 1; k <= 5; k += 1) fs.writeFileSync(path.join(dir, `run-${k}.txt`), goldenRun(round, k), 'utf8');
}

async function scoreRound(request, n, round) {
  writeRuns(await projectOf(request), n, round);
  await reachStep(request, `measure-${n}`);
  await submit(request, `measure-${n}`, { action: 'score' });
}

// The entry the participant writes to the log, from the numbers the app saved.
function logEntry(attempt, n, decision, hypothesis, reasoning = 'The numbers moved.') {
  const rows = attempt.compare.rules.map((rule) => {
    const cell = rule.after;
    return cell.not_checked
      ? `| ${rule.id} ${rule.name} | not checked | n/a | needs a rewrite |`
      : `| ${rule.id} ${rule.name} | ${cell.passes}/${cell.checked} | ${Math.round((100 * cell.passes) / cell.checked)}% |  |`;
  });
  const notChecked = attempt.compare.rules.filter((rule) => rule.after.not_checked).map((rule) => rule.id);
  return [
    '',
    `## Iteration ${n}: tone line`,
    '- Date: 2026-11-26',
    '- Prompt: prompt.md',
    '- Model: sonnet',
    '- Runs: 5',
    `- Overall: ${attempt.compare.after.passes} / ${attempt.compare.after.total}`,
    `- Not checked: ${notChecked.length}${notChecked.length ? ` (${notChecked.join(', ')})` : ''}`,
    `- Decision: ${decision}`,
    `- Hypothesis: ${hypothesis}`,
    '',
    '| Criterion | Passed | Rate | Notes |',
    '| --- | --- | --- | --- |',
    ...rows,
    '',
    '- Change: one change to the tone line',
    '- Result: counted',
    `- Reasoning: ${reasoning}`,
    '',
  ].join('\n');
}

async function decideRound(request, n, choice) {
  await reachStep(request, `decide-${n}`);
  await submit(request, `decide-${n}`, { action: 'decide', choice });
}

async function documentRound(request, n) {
  const view = await stepView(request, `decide-${n}`);
  const project = await projectOf(request);
  const { attempt, decision } = view.data;
  fs.appendFileSync(practiceLog(project), logEntry(attempt, n, decision, attempt.hypothesis), 'utf8');
  await post(request, '/api/step/check', { step: `decide-${n}` });
  expect((await stepView(request, `decide-${n}`)).status).toBe('done');
}

// A whole round through the API: hypothesis, edit, answers, score, decision and a matching log entry.
async function playRound(request, n, round, choice) {
  await writeRound(request, n);
  await scoreRound(request, n, round);
  await decideRound(request, n, choice);
  await documentRound(request, n);
}

// ---- the page --------------------------------------------------------------------------------------------

async function openPart4(page, request, demo, extra) {
  await control(request, { scenario: 'ready', demo, ...(extra || {}) });
  await page.goto(`/?t=${TOKEN}`);
  await expect(page.locator('#step-heading')).toHaveText('Evaluated systems');
}

async function openStep(page, id) {
  await page.locator('#series-open-part-4').click();
  const title = STEPS[id].title;
  const current = page.locator('#step-heading');
  if ((await current.textContent()) !== title) await page.locator('.course-item', { hasText: title }).first().click();
  await expect(current).toHaveText(title);
}

// Opens a step from the course list, for a step the page has already moved past.
async function reopen(page, id) {
  await page.locator('.course-item', { hasText: STEPS[id].title }).first().click();
  await expect(page.locator('#step-heading')).toHaveText(STEPS[id].title);
}

// A demo run set up as far as `prepare` takes it, with the lessons before `id` finished, opened on `id`.
async function demoAt(page, request, prepare, id) {
  await openPart4(page, request, true);
  await prepare(request);
  await reachStep(request, id);
  await page.reload();
  await openStep(page, id);
}

const noGainWords = /measured gain/i;

// ---- tests ---------------------------------------------------------------------------------------------

test.describe('the Series row and locking', () => {
  test('Part 4 is locked until Part 3 is done or skipped, and Part 5 is still coming soon', async ({ page, request }) => {
    await openPart4(page, request, false);
    const row = page.locator('#series-part-4');
    await expect(row).toHaveClass(/k-course/);
    await expect(page.locator('#series-open-part-4')).toHaveAttribute('aria-disabled', 'true');
    await expect(row.locator('.series-action')).toHaveCount(0);
    await expect(row.locator('.series-count')).toHaveCount(0);
    await expect(row.locator('.lock-tip')).toHaveCount(1);
    await expect(page.locator('#series-part-5')).toContainText('Coming soon');
    await expect(page.locator('#series-part-5')).toHaveClass(/k-soon/);
    await expect(page.locator('#series-open-part-5')).toHaveCount(0);

    for (const part of ['part-1', 'part-2', 'part-3']) await post(request, '/api/part/skip', { part, confirm: true });
    await page.reload();
    await expect(page.locator('#series-open-part-4')).not.toHaveAttribute('aria-disabled', 'true');
    await expect(row.locator('.series-state')).toHaveText('Not started');
    await expect(row.locator('.series-action')).toHaveText('Start');
    await expect(page.locator('#series-part-5')).toContainText('Coming soon');
    await expect(page.locator('#series-part-6')).toContainText('Live meeting');

    // The mission lesson is done: the row shows its state and count and keeps the open control.
    await finishLesson(request, 'p4-mission');
    await page.reload();
    await expect(row.locator('.series-state')).toHaveText('In progress');
    await expect(row.locator('.series-count')).toHaveText('1 of 16 done');
    await expect(row.locator('.series-action')).toHaveText('Continue');
    await expect(page.locator('#series-skip-part-4')).toBeVisible();
    await page.locator('#series-open-part-4').click();
    await expect(page.locator('#step-heading')).toHaveText(STEPS['starting-point'].title);
  });
});

test.describe('the starting point', () => {
  test('nothing is preselected, Part 3 skipped makes your own baseline unavailable, and Practice says practice only', async ({ page, request }) => {
    await openPart4(page, request, false);
    for (const part of ['part-1', 'part-2', 'part-3']) await post(request, '/api/part/skip', { part, confirm: true });
    await reachStep(request, 'starting-point');
    await page.reload();
    await openStep(page, 'starting-point');
    const ui = STEPS['starting-point'].ui;

    await expect(page.locator('#p4-start-own')).not.toBeChecked();
    await expect(page.locator('#p4-start-practice')).not.toBeChecked();
    await expect(page.locator('#p4-start-use')).toHaveCount(0);
    await expect(page.locator('#p4-start-own')).toBeDisabled();
    await expect(page.locator('#p4-start-own-reason')).toContainText(ui.unavailable);
    await expect(page.locator('#p4-start-own-reason')).toContainText('skipped');
    await expect(page.locator('#p4-start-practice')).toBeEnabled();
    await expect(page.locator('#p4-start-practice-note')).toHaveText(ui.practice_only);
    await expect(page.locator('#p4-practice-only')).toHaveText(ui.practice_only);
    expect(fs.existsSync(path.join(await projectOf(request), 'part-4', 'practice'))).toBe(false);
    await expect(page.locator('#check-work')).toHaveCount(0);

    await page.locator('#p4-start-practice').check();
    await expect(page.locator('#p4-start-use')).toHaveText(ui.use_practice);
    await page.locator('#p4-start-use').click();
    // The step is done, so the page moves on to the next item. Opening the step again shows what was chosen.
    await expect(page.locator('#step-heading')).toHaveText(LESSONS['p4-checker-first'].title, { timeout: 20000 });
    expect((await stepView(request, 'starting-point')).status).toBe('done');
    expect(fs.existsSync(path.join(await projectOf(request), 'part-4', 'practice', 'iteration-log.md'))).toBe(true);
    await reopen(page, 'starting-point');
    await expect(page.locator('#p4-start-practice-chosen')).toHaveText(ui.chosen);
    await expect(page.locator('#p4-start-practice')).toBeChecked();
    await expect(page.locator('#p4-start-own')).not.toBeChecked();
    await expect(page.locator('#p4-start-use')).toHaveCount(0);
  });

  test('a Part 3 baseline that is not finished is unavailable with its own reason', async ({ page, request }) => {
    await demoAt(page, request, (r) => reachStep(r, 'starting-point'), 'starting-point');
    await expect(page.locator('#p4-start-own')).toBeDisabled();
    await expect(page.locator('#p4-start-own-reason')).toContainText('not finished');
    await expect(page.locator('#p4-start-practice-card')).toBeVisible();
  });
});

test.describe('the known-good answer', () => {
  test('the score shows only after the answer is saved', async ({ page, request }) => {
    await openPart4(page, request, true);
    await reachStep(request, 'starting-point');
    await submit(request, 'starting-point', { action: 'choose', choice: 'practice' });
    await reachStep(request, 'known-good');
    await page.reload();
    await openStep(page, 'known-good');
    const ui = STEPS['known-good'].ui;
    await expect(page.locator('#p4-practice-only')).toBeVisible();
    await expect(page.locator('#p4-rules')).toContainText('C1');
    await expect(page.locator('#p4-result')).toHaveCount(0);
    await expect(page.locator('#p4-answer-save')).toHaveAttribute('aria-disabled', 'true');

    await page.locator('#p4-answer').fill(KNOWN_GOOD);
    await page.locator('#p4-answer-save').click();
    await expect(page.locator('#step-heading')).toHaveText(LESSONS['p4-one-change'].title, { timeout: 20000 });
    expect((await stepView(request, 'known-good')).status).toBe('done');
    await reopen(page, 'known-good');
    await expect(page.locator('#p4-result')).toContainText('6 of 6');
    await expect(page.locator('#p4-result')).toContainText('meets the 95% mark');
    await expect(page.locator('#p4-result-next')).toHaveCount(0);
    await expect(page.locator('#p4-answer')).toBeDisabled();
    expect(ui.save).toBeTruthy();
  });

  test('a known-good answer under 95% gives a next step and cannot be finished', async ({ page, request }) => {
    await openPart4(page, request, true);
    await reachStep(request, 'starting-point');
    await submit(request, 'starting-point', { action: 'choose', choice: 'practice' });
    await reachStep(request, 'known-good');
    await page.reload();
    await openStep(page, 'known-good');
    const second = fs.readFileSync(path.join(ROOT, 'app', 'eval_coach', 'kit', 'northwind', 'sample-run-2.txt'), 'utf8');
    await page.locator('#p4-answer').fill(second);
    await page.locator('#p4-answer-save').click();
    await expect(page.locator('#p4-result')).toContainText('under the 95% mark', { timeout: 20000 });
    await expect(page.locator('#p4-result-next')).toContainText('Do not loosen a rule');
    expect((await stepView(request, 'known-good')).status).toBe('active');
  });
});

test.describe('the hypothesis and the edit', () => {
  test('the edit step is locked until a hypothesis is saved, and failing rules are marked in words', async ({ page, request }) => {
    await demoAt(page, request, startPractice, 'hypothesis-1');
    const ui = STEPS['hypothesis-1'].ui;
    await expect(page.locator('#p4-practice-only')).toBeVisible();
    await expect(page.locator('#p4-start-note')).toHaveText(ui.start_iteration_0);
    await expect(page.locator('#p4-start-overall')).toHaveText('Overall: 25 of 30');
    await expect(page.locator('#p4-start-rules li')).toHaveCount(6);
    const c5 = page.locator('#p4-start-rule-C5');
    await expect(c5).toHaveAttribute('data-failing', 'true');
    await expect(c5).toContainText(ui.needs_work);
    await expect(c5).toContainText('3 of 5 answers pass');
    const c4 = page.locator('#p4-start-rule-C4');
    await expect(c4).toHaveAttribute('data-failing', 'false');
    await expect(c4).toContainText(ui.passes_all);
    await expect(c4).not.toContainText(ui.needs_work);

    // The next item is locked, and a locked item is refused.
    const editButton = page.getByRole('button', { name: new RegExp(STEPS['edit-1'].title) });
    await expect(editButton).toBeDisabled();
    await expect(editButton).toContainText('Not started');
    const refused = await request.post('/api/step/submit', { headers, data: { step: 'edit-1', data: { action: 'save', prompt: 'x' } } });
    expect((await refused.json()).ok).toBe(false);
    expect((await stepView(request, 'hypothesis-1')).status).toBe('active');

    await expect(page.locator('#p4-hypothesis-save')).toHaveAttribute('aria-disabled', 'true');
    await page.locator('#p4-hypothesis').fill(HYPOTHESIS);
    await expect(page.locator('#p4-save-status')).toHaveText(ui.unsaved);
    await page.locator('#p4-hypothesis-save').click();
    await expect.poll(async () => (await stepView(request, 'hypothesis-1')).status).toBe('done');
    expect((await stepView(request, 'hypothesis-1')).status).toBe('done');
    await reopen(page, 'hypothesis-1');
    await expect(page.locator('#p4-hypothesis')).toHaveValue(HYPOTHESIS);
    await expect(page.locator('#p4-hypothesis')).toBeEnabled();

    // The edit step shows the hypothesis, the starting prompt and an editor.
    await reopen(page, 'edit-1');
    const editUi = STEPS['edit-1'].ui;
    await expect(page.locator('#p4-edit-hypothesis')).toHaveText(HYPOTHESIS);
    await expect(page.locator('#p4-start-prompt')).not.toBeEmpty();
    await expect(page.locator('#p4-edit-state')).toHaveText(editUi.same_note);
    await expect(page.locator('#p4-prompt-save')).toHaveAttribute('aria-disabled', 'true');
    const prompt = await page.locator('#p4-prompt').inputValue();
    await page.locator('#p4-prompt').fill(`${prompt.trimEnd()}\n- Tone: factual. Do not use praise words.\n`);
    await page.locator('#p4-prompt-save').click();
    await expect.poll(async () => (await stepView(request, 'edit-1')).status).toBe('done');
    await reopen(page, 'edit-1');
    await expect(page.locator('#p4-edit-state')).toHaveText(editUi.changed_note);
    // Only the round's own copy changed.
    const project = await projectOf(request);
    expect(fs.readFileSync(path.join(attemptDir(project, 1), 'prompt.md'), 'utf8')).toContain('Do not use praise words');
    expect(fs.readFileSync(path.join(project, 'part-4', 'practice', 'prompt-v0.md'), 'utf8')).not.toContain('Do not use praise words');
  });

  test('the hypothesis cannot be changed once an answer is saved, and the page says why', async ({ page, request }) => {
    await demoAt(page, request, (r) => startPractice(r).then(() => writeRound(r, 1)), 'hypothesis-1');
    await expect(page.locator('#p4-hypothesis')).toBeEnabled();
    writeRuns(await projectOf(request), 1, 1);
    await page.reload();
    await openStep(page, 'hypothesis-1');
    await expect(page.locator('#p4-hypothesis')).toBeDisabled();
    await expect(page.locator('#p4-locked-note')).toContainText('not a prediction');
    await expect(page.locator('#p4-hypothesis-save')).toHaveAttribute('aria-disabled', 'true');
    await page.locator('.course-item', { hasText: STEPS['edit-1'].title }).click();
    await expect(page.locator('#p4-prompt')).toBeDisabled();
    await expect(page.locator('#p4-locked-note')).toBeVisible();
  });
});

test.describe('five answers and the per-rule table', () => {
  test('the run list fills as answers are saved, and the table shows every rule before and after', async ({ page, request }) => {
    await demoAt(page, request, (r) => startPractice(r).then(() => writeRound(r, 1)), 'measure-1');
    const ui = STEPS['measure-1'].ui;
    await expect(page.locator('#p4-practice-only')).toBeVisible();
    await expect(page.locator('#p4-runs li')).toHaveCount(5);
    for (let n = 1; n <= 5; n += 1) {
      await expect(page.locator(`#p4-run-${n}`)).toContainText(ui.run_empty);
      await expect(page.locator(`#p4-run-${n}`)).toHaveAttribute('data-done', 'false');
    }
    await expect(page.locator('#p4-score')).toHaveAttribute('aria-disabled', 'true');
    await expect(page.locator('#p4-results')).toHaveCount(0);

    const project = await projectOf(request);
    writeRuns(project, 1, 1);
    await page.reload();
    await openStep(page, 'measure-1');
    for (let n = 1; n <= 5; n += 1) {
      await expect(page.locator(`#p4-run-${n}`)).toContainText('Saved (');
      await expect(page.locator(`#p4-run-${n}`)).toHaveAttribute('data-done', 'true');
    }
    await expect(page.locator('#p4-score')).not.toHaveAttribute('aria-disabled', 'true');
    await page.locator('#p4-score').click();
    await expect(page.locator('#p4-results')).toBeVisible({ timeout: 30000 });

    await expect(page.locator('#p4-results tbody tr')).toHaveCount(6);
    const cell = (rule, part) => page.locator(`#p4-rule-${rule}-${part}`);
    await expect(cell('C5', 'before')).toHaveText('3 of 5');
    await expect(cell('C5', 'after')).toHaveText('5 of 5');
    await expect(cell('C5', 'change')).toHaveText(ui.up);
    await expect(cell('C6', 'before')).toHaveText('5 of 5');
    await expect(cell('C6', 'after')).toHaveText('4 of 5');
    await expect(cell('C6', 'change')).toHaveText(ui.down);
    await expect(cell('C6', 'change')).toHaveClass(/surprise/);
    for (const rule of ['C1', 'C2', 'C3', 'C4']) await expect(cell(rule, 'change')).toHaveText(ui.same);
    await expect(page.locator('#p4-overall-before')).toHaveText('Before: 25 of 30');
    await expect(page.locator('#p4-overall-after')).toHaveText('After: 26 of 30');
    await expect(page.locator('#p4-five')).toContainText('26 of 30');
    await expect(page.locator('#p4-five')).toContainText('goal and not a gate');
    await expect(page.locator('#p4-five-next')).not.toBeEmpty();
    await expect(page.locator('#p4-coverage')).toHaveCount(0);
    await expect(page.locator('.panel')).not.toContainText(noGainWords);
    expect((await stepView(request, 'measure-1')).status).toBe('done');
  });

  test('a rule that became NOT CHECKED is shown in words as lost coverage and flagged', async ({ page, request }) => {
    await demoAt(page, request, (r) => startPractice(r).then(() => writeRound(r, 1)), 'measure-1');
    const ui = STEPS['measure-1'].ui;
    const project = await projectOf(request);
    const checker = path.join(attemptDir(project, 1), 'check.py');
    const text = fs.readFileSync(checker, 'utf8');
    const marker = /^( +)ok, reason = fn\(text\)(\r?\n)/m;
    expect(text).toMatch(marker);
    fs.writeFileSync(
      checker,
      text.replace(marker, (line, pad, eol) => `${line}${pad}if cid == "C5":${eol}${pad}    print(f"{cid} NOT CHECKED  {name}: needs judgment")${eol}${pad}    continue${eol}`),
      'utf8',
    );
    writeRuns(project, 1, 1);
    await page.reload();
    await openStep(page, 'measure-1');
    await page.locator('#p4-score').click();
    await expect(page.locator('#p4-results')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('#p4-rule-C5-after')).toHaveText(ui.not_checked);
    await expect(page.locator('#p4-rule-C5-change')).toContainText(ui.lost);
    await expect(page.locator('#p4-rule-C5-change')).toHaveClass(/surprise/);
    await expect(page.locator('#p4-rule-C5-before')).toHaveText('3 of 5');
    await expect(page.locator('#p4-coverage')).toContainText('C5');
    await expect(page.locator('.panel')).not.toContainText(noGainWords);
  });
});

test.describe('keep or undo, and the log', () => {
  async function toDecide(page, request) {
    await demoAt(page, request, async (r) => {
      await startPractice(r);
      await writeRound(r, 1);
      await scoreRound(r, 1, 1);
    }, 'decide-1');
  }

  test('no line to paste until the decision, then the log gate fails until the log matches', async ({ page, request }) => {
    await toDecide(page, request);
    const ui = STEPS['decide-1'].ui;
    await expect(page.locator('#p4-practice-only')).toBeVisible();
    await expect(page.locator('#p4-results tbody tr')).toHaveCount(6);
    await expect(page.locator('#p4-pending-note')).toHaveText(ui.pending_note);
    await expect(page.locator('#cli-line')).toHaveCount(0);
    await expect(page.locator('#p4-evidence')).toHaveCount(0);
    await expect(page.locator('.panel')).not.toContainText(noGainWords);
    await expect(page.locator('#p4-keep')).not.toHaveAttribute('aria-disabled', 'true');

    await page.locator('#p4-keep').click();
    await expect(page.locator('#p4-decision-note')).toHaveText(ui.kept_note);
    await expect(page.locator('#p4-keep')).toHaveCount(0);
    await expect(page.locator('#p4-evidence')).toContainText('measured gain on these rules');
    await expect(page.locator('#p4-log-note')).toContainText('part-4/practice/iteration-log.md');
    await expect(page.locator('#cli-line')).toContainText('iteration-log.md');

    // Check my work fails while the log has no entry for the round, and names what is missing.
    const check = page.locator('#check-work, #check-log, button:has-text("Check my work")').first();
    await check.click();
    await expect(page.locator('.step-page')).toContainText('The log has no entry for attempt 1', { timeout: 15000 });
    expect((await stepView(request, 'decide-1')).status).toBe('active');

    // The participant's entry with the Reasoning left empty is not enough either.
    const project = await projectOf(request);
    const view = await stepView(request, 'decide-1');
    const entry = logEntry(view.data.attempt, 1, 'kept', HYPOTHESIS, '');
    fs.appendFileSync(practiceLog(project), entry, 'utf8');
    await check.click();
    await expect(page.locator('.step-page')).toContainText(/Reasoning/, { timeout: 15000 });
    expect((await stepView(request, 'decide-1')).status).toBe('active');

    // The complete entry passes.
    fs.writeFileSync(practiceLog(project), fs.readFileSync(practiceLog(project), 'utf8').replace(entry, logEntry(view.data.attempt, 1, 'kept', HYPOTHESIS)), 'utf8');
    await check.click();
    await expect.poll(async () => (await stepView(request, 'decide-1')).status, { timeout: 15000 }).toBe('done');
    await expect(page.locator('#continue')).toBeVisible();
    await expect(page.locator('#step-restart')).toHaveCount(0);
  });

  test('undoing a round records "no measured gain" wording and keeps the earlier version', async ({ page, request }) => {
    await toDecide(page, request);
    await page.locator('#p4-undo').click();
    await expect(page.locator('#p4-decision-note')).toHaveText(STEPS['decide-1'].ui.undone_note);
    await expect(page.locator('#p4-evidence')).toContainText('no measured gain on these rules');
    await expect(page.locator('#p4-evidence')).not.toContainText('did not help');
  });
});

test.describe('the round after a decision and the reflection', () => {
  test('round 2 starts from the kept version, and decide-2 keeps a reflection that never blocks', async ({ page, request }) => {
    await openPart4(page, request, true);
    await startPractice(request);
    await playRound(request, 1, 1, 'keep');
    await writeRound(request, 2, 'Shortening the tone line should keep Factual tone and cut length.');
    await scoreRound(request, 2, 2);
    await decideRound(request, 2, 'keep');
    await documentRound(request, 2);
    await page.reload();
    await openStep(page, 'decide-2');
    const ui = STEPS['decide-2'].ui;
    await expect(page.locator('#step-restart')).toHaveCount(0);
    await expect(page.locator('#p4-decision-note')).toHaveText(ui.kept_note);
    await expect(page.locator('#p4-results tbody tr')).toHaveCount(6);
    await expect(page.locator('#p4-overall-before')).toHaveText('Before: 26 of 30');
    await expect(page.locator('#p4-overall-after')).toHaveText('After: 26 of 30');

    await expect(page.locator('#p4-reflection')).toBeEnabled();
    await page.locator('#p4-reflection').fill('I kept it because it was simpler and the score did not move.');
    await page.locator('#p4-reflection').blur();
    await expect.poll(async () => (await stepView(request, 'decide-2')).data.reflection.text).toContain('simpler');
    await page.reload();
    await openStep(page, 'decide-2');
    await expect(page.locator('#p4-reflection')).toHaveValue(/simpler/);
    expect((await stepView(request, 'decide-2')).status).toBe('done');
  });
});

test.describe('finishing', () => {
  test('a flat round is shown without gain wording, and two documented rounds finish Part 4 under the 95% target', async ({ page, request }) => {
    await openPart4(page, request, true);
    await startPractice(request);
    await playRound(request, 1, 1, 'keep');
    await writeRound(request, 2, 'A shorter tone line should change nothing.');
    await scoreRound(request, 2, 2);
    await decideRound(request, 2, 'keep');
    await page.reload();
    await openStep(page, 'decide-2');
    // Round 2's answers score the same as round 1's, so keeping it is not a gain.
    await expect(page.locator('#p4-evidence')).toContainText('Attempt 2: no measured gain on these rules');
    await expect(page.locator('#p4-evidence')).not.toContainText(/Attempt 2: measured gain/);
    await expect(page.locator('#p4-overall-before')).toHaveText('Before: 26 of 30');
    await expect(page.locator('#p4-overall-after')).toHaveText('After: 26 of 30');

    await documentRound(request, 2);
    const measured = (await stepView(request, 'measure-2')).data.attempt.five_answers;
    expect(measured.meets_target).toBe(false);
    expect(measured.next_step).toBeTruthy();
    await lessonsBefore(request, 'none');
    await page.reload();
    await page.locator('#series-open-part-4').click();
    await expect(page.locator('#step-heading')).toHaveText('You have finished Part 4');
    await expect(page.locator('.finished-page')).toContainText('two documented rounds');
    await expect(page.locator('.finished-page')).toContainText('practice only');
  });
});

test.describe('the worked example', () => {
  test('the exact edits and results stay hidden until the prediction passes', async ({ page, request }) => {
    await openPart4(page, request, true);
    await startPractice(request);
    await lessonsBefore(request, 'p4-worked-example');
    await page.reload();
    await page.locator('#series-open-part-4').click();
    await page.locator('.course-item', { hasText: LESSONS['p4-worked-example'].title }).first().click();
    await expect(page.locator('#step-heading')).toHaveText(LESSONS['p4-worked-example'].title);
    const activity = LESSONS['p4-worked-example'].activities.find((a) => a.id === 'wx-predict');
    const reveal = /saved answers, not a measurement/;
    await expect(page.locator('.lesson-body')).not.toContainText(reveal);
    await expect(page.locator('.lesson-body')).not.toContainText('26 of 30');

    // A wrong placement shows no reveal.
    const wrong = Object.fromEntries(activity.items.map((i) => [i.id, i.bucket === 'rises' ? 'falls' : 'rises']));
    for (const item of activity.items) await page.locator(`#sort-${activity.id}-${item.id}`).selectOption(wrong[item.id]);
    await page.locator(`#submit-${activity.id}`).click();
    await expect(page.locator(`#submit-${activity.id}`)).toBeVisible();
    await expect(page.locator('.lesson-body')).not.toContainText(reveal);
    await expect(page.locator('.lesson-body')).not.toContainText('26 of 30');

    // The right placement reveals the edit and the results.
    for (const item of activity.items) await page.locator(`#sort-${activity.id}-${item.id}`).selectOption(item.bucket);
    await page.locator(`#submit-${activity.id}`).click();
    await expect(page.locator('.lesson-body')).toContainText(reveal, { timeout: 15000 });
    await expect(page.locator('.lesson-body')).toContainText('26 of 30');
    await expect(page.locator('.lesson-body')).toContainText('measured gain on these rules');
  });
});
