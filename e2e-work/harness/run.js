// End-to-end stages. Usage: node run.js <stage>
const L = require('./lib');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const { state } = L;
const BLIND = path.join(L.HOME, 'blind');
const FIX_WORK = path.join(L.HOME, 'fixtures-work');
const KEY_WORK = path.join(L.HOME, 'key-work');
const PROJECT = L.PROJECT;
const sha = (p) => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const exists = (p) => fs.existsSync(p);
const hasText = (p) => exists(p) && fs.readFileSync(p, 'utf8').trim().length > 0;

async function openApp(page) {
  await page.goto(state.url);
  await L.enterPart(page);
  await page.waitForFunction(() => document.querySelector('#step-heading') || document.querySelector('.setup'), null, { timeout: 15000 });
  await L.waitFor(async () => (await page.locator('#step-heading').count()) > 0, 15000, 'a heading');
  L.assertion('url has no token after load', page.url() === `http://127.0.0.1:${state.port}/`, page.url());
}

async function heading(page) { return (await page.locator('#step-heading').innerText()).trim(); }

async function expectPassed(page, stepLabel) {
  await L.clickAndWait(page, '#check-work', '/api/step/check');
  await page.locator('.check-head').waitFor({ timeout: 15000 });
  const text = await page.locator('.check-head').innerText();
  const items = await page.locator('.check-items li').allInnerTexts();
  L.assertion(`gate passes: ${stepLabel}`, /Passed/.test(text), `${text} | ${items.join(' / ')}`);
}

async function assertUiMatchesChecker(page, tableRoot, args, label) {
  const indep = L.independentRun(args);
  const uiFiles = await page.locator(`${tableRoot} .result-file`).evaluateAll((els) => els.map((el) => ({
    file: el.querySelector('h3').textContent,
    rows: Array.from(el.querySelectorAll('tbody tr')).map((tr) => ({
      id: tr.querySelector('.crit-id').textContent,
      verdict: tr.querySelector('.verdict').className.match(/v-(\S+)/)[1],
    })),
  })));
  const uiMap = {};
  for (const f of uiFiles) { uiMap[path.basename(f.file.replace(/\\/g, '/')).toLowerCase()] = Object.fromEntries(f.rows.map((r) => [r.id, r.verdict])); }
  const same = JSON.stringify(sorted(uiMap)) === JSON.stringify(sorted(indep));
  L.assertion(`UI verdicts equal independent check.py run (${label})`, same && Object.keys(indep).length > 0, `ui=${JSON.stringify(uiMap)} indep=${JSON.stringify(indep)}`);
  return indep;
}

function sorted(obj) {
  return Object.fromEntries(Object.keys(obj).sort().map((k) => [k, Object.fromEntries(Object.keys(obj[k]).sort().map((c) => [c, obj[k][c]]))]));
}

// ---- stages -----------------------------------------------------------------

const pfItem = (s, id) => s.preflight.items.find((i) => i.id === id);

// The setup wizard moves forward to the next page that still needs the participant, and Next waits for the page's
// check (on Checking your computer, until the checks it started have ended).
async function wizardTo(page, id) {
  for (let i = 0; i < 80; i += 1) {
    if (await page.locator(`#pf-item-${id}`).count()) return;
    if ((await page.locator('#wizard-next').getAttribute('aria-disabled')) !== 'true') await page.locator('#wizard-next').click();
    await L.sleep(500);
  }
  L.assertion(`the wizard reached the ${id} page`, (await page.locator(`#pf-item-${id}`).count()) > 0);
}

// Stand-in only. The real tools' recipes carry the one-shot data for the quiet background test; the stand-in's launch
// commands get the same through the recipes override file in the app home, so the real test code path runs.
const QUIET = { hang: `${L.CLI_COMMAND} --bg-hang`, fail: `${L.CLI_COMMAND} --bg-fail` };
const EVENTS_FILE = path.join(L.WORK, 'fake-cli-events.jsonl');

function writeQuietRecipes() {
  const recipe = (id, command, seconds) => ({ id, name: `Stand-in ${id}`, cli_command: command, shell: 'none', command: '', needs_mb: 0, headless: { args: ['-p', '{line}'], timeout_seconds: seconds } });
  fs.mkdirSync(L.HOME, { recursive: true });
  fs.writeFileSync(path.join(L.HOME, 'cli-recipes.json'), JSON.stringify({ recipes: [recipe('hang', QUIET.hang, 4), recipe('fail', QUIET.fail, 120), recipe('plain', L.CLI_COMMAND, 120)] }, null, 2));
}

let quietBase = 0;

function oneShotEvents() {
  if (!exists(EVENTS_FILE)) return [];
  return fs.readFileSync(EVENTS_FILE, 'utf8').split(/\r?\n/).filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter((e) => e && e.event === 'oneshot').slice(quietBase);
}

// Back with the Back button to a page that a passed check skipped going forward.
async function backTo(page, id) {
  for (let i = 0; i < 12 && !(await page.locator(`#pf-item-${id}`).count()); i += 1) {
    await page.locator('#wizard-back').click();
    await L.sleep(300);
  }
  L.assertion(`the wizard went back to the ${id} page`, (await page.locator(`#pf-item-${id}`).count()) > 0);
}

async function stageSetup() {
  quietBase = oneShotEvents().length;
  if (L.STANDIN) writeQuietRecipes();
  await L.startServer();
  const { browser, page } = await L.openBrowser({ tall: true });
  try {
    await openApp(page);
    L.assertion('preflight screen appears first', await page.getByRole('heading', { name: 'Before you begin' }).isVisible());
    L.assertion('setup is a full-page wizard with no sidebar beside it', (await page.locator('#topbar').isHidden()) && (await page.locator('.course-item').count()) === 0);
    L.assertion('the wizard opens on the first page', (await page.locator('#wizard-count').innerText()).startsWith('1 of '));
    const s0 = await L.apiState();
    L.assertion('steps locked before preflight', s0.preflight.passed === false && s0.step === null && s0.steps.every((x) => x.status === 'locked'));
    L.assertion('script track is the default', s0.preflight.track === 'script');
    if (L.PF) {
      await page.getByRole('radio', { name: /promptfoo track/ }).check();
      await L.waitFor(async () => (await L.apiState()).preflight.track === 'promptfoo', 10000, 'the promptfoo track to be saved');
      const picked = await L.apiState();
      L.assertion('the promptfoo track lists the Node.js and promptfoo items as applying', ['node', 'promptfoo'].every((id) => pfItem(picked, id).applies === true));
      L.assertion('the track screen explains the extra step', /one extra step/.test(picked.preflight.track_note || ''), picked.preflight.track_note);
    }
    // Next from Track opens Checking your computer, which starts the checks by itself.
    await L.clickAndWait(page, '#wizard-next', '/api/preflight/check');
    await L.waitFor(async () => !(await L.apiState()).preflight.job, L.PF ? 240000 : 60000, 'checks to finish');
    const afterCheck = await L.apiState();
    L.assertion('python item passed by running it', pfItem(afterCheck, 'python').status === 'passed', pfItem(afterCheck, 'python').detail);
    if (L.PF) {
      // Real Node and the real, pinned promptfoo from the private runtime and cache, found and run offline.
      L.assertion('Node.js item passed by running the private node', pfItem(afterCheck, 'node').status === 'passed', pfItem(afterCheck, 'node').detail);
      L.assertion('promptfoo item passed by running the cached promptfoo', pfItem(afterCheck, 'promptfoo').status === 'passed', pfItem(afterCheck, 'promptfoo').detail);
    }

    // A command that does not exist explains itself, and nothing crashes.
    await wizardTo(page, 'cli');
    await page.getByLabel('Command that starts your AI').fill('no-such-cli-e2e-xyz --flag');
    await L.clickAndWait(page, '#pf-cli-check', '/api/preflight/cli');
    await L.waitFor(async () => pfItem(await L.apiState(), 'cli').status === 'failed', 10000, 'bad command fails item 5');
    const message = pfItem(await L.apiState(), 'cli').detail;
    L.assertion('nonexistent CLI command gives a plain error', /could not be found/i.test(message), message);
    L.assertion('next action given for a missing command', pfItem(await L.apiState(), 'cli').next.length > 0);
    L.assertion('preflight screen still shown after bad command', await page.getByRole('heading', { name: 'Before you begin' }).isVisible());

    if (L.STANDIN) {
      // The quiet background test of the chosen AI, with the stand-in's one-shot mode. It never opens an AI window.
      // First it runs past its limit (the process is killed), then it exits non-zero (as when not signed in).
      // Both end as "needs you" and the wizard moves to the AI working test page, which is the visible fallback.
      for (const [label, command] of [['runs past its limit', QUIET.hang], ['exits non-zero', QUIET.fail]]) {
        await page.getByLabel('Command that starts your AI').fill(command);
        await L.clickAndWait(page, '#pf-cli-check', '/api/preflight/cli');
        await page.locator('#pf-ai-testing').waitFor({ timeout: 8000 });
        L.assertion(`no AI window while the quiet test runs (${label})`, (await page.locator('#col-right').isHidden()) && !(await L.apiState()).terminal.running);
        await L.waitFor(async () => (await page.locator('#pf-item-working_test').count()) > 0, 40000, `the wizard to move to the AI working test page (${label})`);
        const ended = await L.apiState();
        L.assertion(`the quiet test that ${label} needs the participant and is not a failure`, pfItem(ended, 'working_test').status === 'needs_you' && ended.preflight.working_test.background.state === 'needs_you', JSON.stringify(pfItem(ended, 'working_test')));
        L.assertion(`the page says the quiet test could not finish (${label})`, /could not finish/.test(await page.locator('#pf-item-working_test').innerText()));
        if (command !== QUIET.fail) await backTo(page, 'cli');
      }
      const ran = oneShotEvents();
      L.assertion('the quiet tests ran the one-shot mode with no input', ran.length === 2 && ran.every((e) => e.stdin_closed === true) && ran[0].flags.includes('--bg-hang') && ran[1].flags.includes('--bg-fail'), JSON.stringify(ran));
      L.assertion('the one-shot runs started in the test folder', ran.every((e) => path.resolve(e.cwd).toLowerCase() === path.join(L.HOME, 'cli-test').toLowerCase()), JSON.stringify(ran.map((e) => e.cwd)));
    } else {
      await page.getByLabel('Command that starts your AI').fill(L.CLI_COMMAND);
      await L.clickAndWait(page, '#pf-cli-check', '/api/preflight/cli');
      await L.waitFor(async () => pfItem(await L.apiState(), 'cli').status === 'passed', 10000, 'command found, so the AI is chosen');
    }
    L.assertion('no sign-in item exists', !(await L.apiState()).preflight.items.some((i) => i.id === 'signin'));
    await wizardTo(page, 'working_test');

    // One page starts the AI window and runs the working test: Start, sign in if asked, Send. A pass proves the sign-in.
    L.countSession('preflight working test');
    await L.clickAndWait(page, '#cli-start', '/api/preflight/test/start');
    const testDir = path.join(L.HOME, 'cli-test');
    const tree = L.listTree(testDir);
    L.assertion('test folder holds only input.txt', tree.length === 1 && tree[0] === 'input.txt', tree.join(','));
    await L.waitReady(page, 'preflight-test');
    await L.clickAndWait(page, '#cli-send', '/api/preflight/test/send');
    await L.driveCli(page, 'preflight-test', async ({ busy, idleMs }) => hasText(path.join(testDir, 'output.txt')) && hasText(path.join(testDir, 'version.txt')) && !busy && idleMs > 1500);
    // The page re-reads the test folder by itself after Send, so no Check press is needed.
    await L.waitFor(async () => pfItem(await L.apiState(), 'working_test').status === 'passed', 30000, 'working test passed by the quiet re-read');
    L.assertion('working test decided from the files', fs.readFileSync(path.join(testDir, 'output.txt'), 'utf8').trim() === 'HELLO FROM EVAL COACH');
    await L.waitFor(async () => !(await L.apiState()).terminal.running, 15000, 'CLI stopped after the working test');

    if (L.STANDIN) {
      // Choosing the plain stand-in command again runs the quiet test, which passes: the AI working test counts as
      // passed without any AI window, and the wizard moves on by itself.
      await backTo(page, 'cli');
      await page.getByLabel('Command that starts your AI').fill(L.CLI_COMMAND);
      await L.clickAndWait(page, '#pf-cli-check', '/api/preflight/cli');
      await L.waitFor(async () => (await page.locator('#pf-item-project').count()) > 0, 40000, 'the wizard to move past the AI working test after a quiet pass');
      const quiet = await L.apiState();
      L.assertion('a quiet pass counts as the AI working test', pfItem(quiet, 'working_test').status === 'passed' && quiet.preflight.working_test.background.state === 'passed', JSON.stringify(pfItem(quiet, 'working_test')));
      L.assertion('the quiet pass opened no AI window', !quiet.terminal.running && (await page.locator('#col-right').isHidden()));
      const all = oneShotEvents();
      L.assertion('the third quiet test ran the plain command', all.length === 3 && all[2].flags.length === 0, JSON.stringify(all));
    }

    // Project folder.
    await wizardTo(page, 'project');
    await page.getByLabel('Project folder').fill(PROJECT);
    await page.getByRole('radio', { name: /Practice task/ }).check();
    await page.getByRole('button', { name: 'Set up my project' }).click();
    await L.waitFor(async () => { const s = await L.apiState(); return s.configured && s.preflight.passed; }, 15000, 'preflight to finish');
    // The wizard ends on the Your AI window page; Finish closes it.
    await page.locator('#pf-item-ai_window').waitFor({ timeout: 15000 });
    L.assertion('the wizard ends on the Your AI window page', await page.locator('#pf-item-ai_window').isVisible());
    await page.locator('#wizard-finish').click();
    const afterSetup = await L.apiState();
    // With lessons, preflight leads to the hook lesson; the generate step comes after it.
    L.assertion('setup completes and the course continues with the first lesson after preflight',     afterSetup.course ? afterSetup.current_item && afterSetup.current_item.id === 'hook' : /collect your answers/i.test(await heading(page)), JSON.stringify(afterSetup.current_item));
    L.assertion('preflight results persisted', exists(path.join(L.HOME, 'preflight.json')));
    L.assertion('preflight passed in state', (await L.apiState()).preflight.passed === true);
    for (const f of ['prompt-v0.md', 'test-cases.md', 'skills/build-eval-script/SKILL.md', 'skills/make-eval-fixtures/SKILL.md', '.learning/progress.json']) {
      L.assertion(`project has ${f}`, exists(path.join(PROJECT, f)));
    }
  } finally { await browser.close(); }
}

// How many AI windows the stand-in has been launched as, read from its own event file (a harness-only record).
function launchCount() {
  if (!exists(EVENTS_FILE)) return 0;
  return fs.readFileSync(EVENTS_FILE, 'utf8').split(/\r?\n/).filter(Boolean).filter((l) => { try { return JSON.parse(l).event === 'launch'; } catch { return false; } }).length;
}

// "Open a new AI chat": the participant's own start, and the only way to open a window after the automatic first one.
async function startCli(page, label) {
  L.countSession(label);
  const resp = await L.clickAndWait(page, '#cli-start', '/api/step/start');
  if (!resp.ok()) throw new Error(`start failed: ${resp.status()}`);
}

// A Part 3 step opens its AI window by itself when the page shows it (the page calls /api/step/auto-start once).
// `base` is launchCount() taken before the page opened. The window is counted as one session.
async function awaitAutoStart(page, stepId, label, base) {
  await L.waitFor(async () => { const s = await L.apiState(stepId); return s.terminal.running && s.step && s.step.id === stepId && s.step.cli.started; }, 20000, `${label}: the AI window to open by itself`);
  await L.waitFor(async () => launchCount() > base, 20000, `${label}: the stand-in to be launched`);
  await L.sleep(500);
  L.countSession(label);
  const s = await L.apiState(stepId);
  L.assertion(`${label}: the AI window opened by itself, once`, s.terminal.running && launchCount() === base + 1, `launches ${launchCount() - base}`);
  L.assertion(`${label}: the step no longer offers an automatic start`, s.step.cli.can_auto_start === false && s.step.cli.mode === 'paste');
  await expectPasteView(page, stepId);
}

// The paste-mode head: the line to paste with a Copy button, "Open a new AI chat", and no Send or Start again.
async function expectPasteView(page, stepId) {
  const cli = (await L.apiState(stepId)).step.cli;
  await L.waitFor(async () => (await page.locator('#cli-line').count()) === 1 && (await page.locator('#cli-line').innerText()).trim() === cli.line.trim(), 15000, `${stepId}: the line to paste on the page`);
  L.assertion(`${stepId}: the line is shown in the page for the participant to copy`, (await page.locator('#copy-paste').count()) === 1, cli.line);
  L.assertion(`${stepId}: no Send to AI and no Start again button`, (await page.locator('#cli-send').count()) === 0 && (await page.locator('#cli-retry').count()) === 0);
  L.assertion(`${stepId}: the start button is Open a new AI chat`, (await page.locator('#cli-start').innerText()).trim() === 'Open a new AI chat');
}

// A step whose automatic start may or may not be left: it opens by itself when the page shows it and the step was
// never started; after that (a restart in between, or an earlier window), "Open a new AI chat" is the participant's way.
// A window that opened by itself on Continue in the stage before is adopted (it was counted there).
async function openAi(page, stepId, label, base) {
  if (state.carry === stepId) {
    state.carry = null;
    L.saveState(state);
    await L.waitFor(async () => { const s = await L.apiState(stepId); return s.terminal.running && s.step.cli.started; }, 10000, `${label}: the AI window opened on Continue`);
    await expectPasteView(page, stepId);
    L.assertion(`${label}: the window that opened by itself on Continue is still the only one`, launchCount() === base, String(launchCount() - base));
    return 'carried';
  }
  await L.sleep(800); // the page asks for the automatic start right after it draws the step
  const s = await L.apiState(stepId);
  if (s.terminal.running || s.step.cli.can_auto_start) { await awaitAutoStart(page, stepId, label, base); return 'auto'; }
  await expectPasteView(page, stepId);
  await startCli(page, label);
  return 'button';
}

// Continue into a step that uses the AI: the next step is shown, so its window opens by itself right there.
async function continueIntoAi(page, nextId, label) {
  const base = launchCount();
  await page.locator('#continue').click();
  await awaitAutoStart(page, nextId, label, base);
  state.carry = nextId;
  L.saveState(state);
}

// What the participant does with Copy: paste the step's line into the AI window and press Enter. The app types nothing.
async function pasteLine(stepId, label) {
  const line = (await L.apiState(stepId)).step.cli.line;
  const r = await postApi('/api/terminal/input', { data: Buffer.from(`${line}\r`).toString('base64') });
  L.assertion(`${label}: the participant's paste was accepted`, r.status === 200, JSON.stringify(r.body));
}

// The app no longer types a step's line: Send is refused and an automatic start with a window open does nothing.
async function expectSendRefused(stepId) {
  const before = launchCount();
  const send = await postApi('/api/step/send', { step: stepId });
  L.assertion(`${stepId}: Send is refused as not supported`, send.status === 400 && send.body.error.code === 'not_supported', JSON.stringify(send.body));
  const auto = await postApi('/api/step/auto-start', { step: stepId });
  L.assertion(`${stepId}: asking again for an automatic start is harmless and starts nothing`, auto.status === 200 && launchCount() === before, `${auto.status} ${launchCount() - before}`);
}

async function waitCliRunningFalse() {
  await L.waitFor(async () => !(await L.apiState()).terminal.running, 10000, 'CLI to stop');
}

// Part 3's first step: it shows the pair that will be scored and starts no AI. The participant keeps the Practice
// task files, and nothing in their project changes (no copy is made, because nothing was replaced).
async function stageInputs() {
  const base = launchCount();
  const files = ['prompt-v0.md', 'test-cases.md'].map((name) => path.join(PROJECT, name));
  const before = files.map(sha);
  const { browser, page } = await L.openBrowser();
  try {
    await openApp(page);
    L.assertion('on the inputs step', /choose your inputs/i.test(await heading(page)), await heading(page));
    L.assertion('inputs is the current step and generate is still locked', (await L.apiState()).current_step === 'inputs' && (await L.apiState()).steps.find((x) => x.id === 'generate').status === 'locked');
    for (const key of ['prompt', 'test_cases']) {
      L.assertion(`inputs: ${key} is shown in full and labelled as the Practice task`, /practice task/i.test(await page.locator(`#inputs-${key} > p.hint`).first().innerText()) && (await page.locator(`#inputs-${key}-text`).innerText()).trim().length > 0);
    }
    L.assertion('inputs: the Part 1 and Part 2 files are not offered yet, with a reason', (await page.locator('#inputs-prompt input[value="part1"]').isDisabled()) && (await page.locator('#inputs-test_cases input[value="part2"]').isDisabled()) && /finish/i.test(await page.locator('#inputs-prompt').innerText()));
    L.assertion('inputs: no AI window, no line to paste, no Send', (await page.locator('#cli-start, #cli-send, .paste-box').count()) === 0 && !(await L.apiState()).terminal.running && launchCount() === base);
    for (const [route, label] of [['/api/step/start', 'Start'], ['/api/step/send', 'Send'], ['/api/step/skip', 'Skip']]) {
      const r = await postApi(route, { step: 'inputs' });
      L.assertion(`inputs: ${label} is refused as not supported`, r.status === 400 && r.body.error.code === 'not_supported', JSON.stringify(r.body));
    }
    const locked = await postApi('/api/step/start', { step: 'generate' });
    L.assertion('inputs: generate cannot start before this step is done', locked.status === 400 && locked.body.error.code === 'step_locked', JSON.stringify(locked.body));
    // Choosing "Keep the active file" changes nothing, because the Practice task is already what the project holds.
    await L.clickAndWait(page, '#inputs-prompt input[value="keep"]', '/api/step/submit');
    L.assertion('inputs: choosing to keep the active file writes nothing', files.map(sha).join() === before.join() && !exists(path.join(PROJECT, 'part-3', 'replaced')));
    L.assertion('inputs: Continue is offered', await page.locator('#continue').isEnabled());
  } finally { await browser.close(); }

  // Continue is pressed through the API so the page does not move on to generate, which would open its AI window.
  const done = await postApi('/api/step/check', { step: 'inputs' });
  L.assertion('inputs: Continue finishes the step', done.status === 200 && done.body.state.step.status === 'done', JSON.stringify(done.body).slice(0, 300));
  const after = await L.apiState();
  L.assertion('inputs: generate is now the current step', after.current_step === 'generate' && after.steps.find((x) => x.id === 'inputs').status === 'done');
  L.assertion('inputs: the track did not change', after.preflight.track === (L.PF ? 'promptfoo' : 'script'), after.preflight.track);
  L.assertion('inputs: the files are byte for byte what they were and no copy was made', files.map(sha).join() === before.join() && !exists(path.join(PROJECT, 'part-3', 'replaced')));
  const progress = JSON.parse(fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8'));
  const choice = progress.steps.inputs.choice;
  L.assertion('inputs: only sources and hashes are recorded', ['prompt', 'test_cases'].every((k) => Object.keys(choice[k]).sort().join() === 'sha256,source' && choice[k].source === 'practice' && choice[k].sha256 === before[k === 'prompt' ? 0 : 1]), JSON.stringify(choice));
  L.assertion('inputs: progress.json holds no file text', !JSON.stringify(progress).includes('Test input') && !JSON.stringify(progress).includes('Mon: standup'));
  const again = await postApi('/api/step/submit', { step: 'inputs', data: { use: { prompt: 'practice' } } });
  L.assertion('inputs: a choice after Continue is refused', again.status === 400 && again.body.error.code === 'step_done', JSON.stringify(again.body));
  L.assertion('inputs: no AI window was started', launchCount() === base);
}

async function stageGenerate() {
  const { browser, page } = await L.openBrowser();
  try {
    const base = launchCount();
    await openApp(page);
    await L.sleep(0);
    L.assertion('on generate step', /collect your answers/i.test(await heading(page)), await heading(page));
    for (const f of ['prompt-v0.md', 'test-cases.md', 'skills/build-eval-script/SKILL.md', 'skills/make-eval-fixtures/SKILL.md', '.learning/progress.json']) {
      L.assertion(`project has ${f}`, exists(path.join(PROJECT, f)));
    }

    const firstRun = [1, 2, 3, 4, 5].find((k) => !hasText(path.join(PROJECT, 'runs', `run-${k}.txt`)));
    L.note('generate', `resuming at run ${firstRun}`);
    for (let n = firstRun; n <= 5; n += 1) {
      const tag = `generate-${n}`;
      if (n === 1) {
        // Run 1 opens by itself when the step is shown.
        await awaitAutoStart(page, 'generate', 'generate run 1', base);
      } else {
        // Runs 2 to 5: nothing opens by itself; the participant opens a new chat.
        const launches = launchCount();
        await L.sleep(1500);
        const idle = await L.apiState('generate');
        L.assertion(`no window opened by itself before run ${n}`, !idle.terminal.running && launchCount() === launches && idle.step.cli.can_auto_start === false, `launches ${launchCount() - launches}`);
        await page.locator('#cli-start').waitFor();
        await L.waitFor(async () => (await page.locator('#cli-start').getAttribute('aria-disabled')) !== 'true', 15000, 'Open a new AI chat button');
        await expectPasteView(page, 'generate');
        await startCli(page, `generate run ${n}`);
      }
      const tree = L.listTree(BLIND);
      L.assertion(`blind folder holds only prompt.md at start of run ${n}`, tree.length === 1 && tree[0] === 'prompt.md', tree.join(','));
      L.assertion('fixtures answer key absent', !exists(L.projectKeyPath()));
      await L.waitReady(page, tag);

      if (n === 1) {
        await expectSendRefused('generate');
        // Open a new AI chat asks first while the window runs; Cancel leaves the window alone.
        const launches = launchCount();
        await page.locator('#cli-start').click();
        await page.locator('dialog.confirm').waitFor({ timeout: 5000 });
        L.assertion('Open a new AI chat asks first while the AI window runs', /Open a new AI chat\?/.test(await page.locator('dialog.confirm').innerText()));
        await page.locator('dialog.confirm').getByRole('button', { name: 'Cancel' }).click();
        await L.sleep(800);
        L.assertion('Cancel left the AI window alone', (await L.apiState()).terminal.running === true && launchCount() === launches);
        // Stop, then come back to the step: nothing opens by itself a second time.
        await L.clickAndWait(page, '#cli-stop', '/api/step/stop');
        await waitCliRunningFalse();
        await page.reload();
        await L.enterPart(page);
        await page.locator('#cli-start').waitFor({ timeout: 15000 });
        await L.sleep(2000);
        const revisit = await L.apiState('generate');
        L.assertion('revisiting the step after Stop starts no second window', !revisit.terminal.running && launchCount() === launches && revisit.step.cli.can_auto_start === false, `launches ${launchCount() - launches}`);
        await L.waitFor(async () => (await page.locator('#cli-start').getAttribute('aria-disabled')) !== 'true', 10000, 'Open a new AI chat enabled');
        L.assertion('Open a new AI chat is enabled after the AI window was stopped', true);
        L.countSession('generate run 1 (Open a new AI chat after stop)');
        const r2 = await L.clickAndWait(page, '#cli-start', '/api/step/start');
        L.assertion('Open a new AI chat opens the AI window again', r2.ok(), String(r2.status()));
        await L.waitFor(async () => launchCount() > launches, 20000, 'the stand-in to be launched again');
        L.assertion('exactly one more window was opened', launchCount() === launches + 1, String(launchCount() - launches));
        const tree2 = L.listTree(BLIND);
        L.assertion('blind folder holds only prompt.md after Open a new AI chat', tree2.length === 1 && tree2[0] === 'prompt.md', tree2.join(','));
        await L.waitReady(page, `${tag}-retry`);
        await L.shot(page, 'generate-live.png');
      }

      await pasteLine('generate', `generate run ${n}`);
      const runFile = path.join(PROJECT, 'runs', `run-${n}.txt`);
      await L.driveCli(page, tag, async ({ busy, idleMs, screen }) => {
        if (hasText(runFile) && !(await L.apiState()).terminal.running) return true;
        if (!busy && idleMs > 120000) await L.stopRun(page, `run ${n} stalled`, screen);
        return false;
      });
      const prompt = fs.readFileSync(path.join(PROJECT, 'prompt-v0.md'), 'utf8').trim();
      const output = fs.readFileSync(runFile, 'utf8').trim();
      L.assertion(`run-${n}.txt non-empty and differs from prompt`, output.length > 0 && output !== prompt, `${output.split(/\s+/).length} words`);
      L.note('run', `run ${n} saved`);
    }

    L.assertion('generate has no model box', (await page.locator('#model-name').count()) === 0);
    const recorded = JSON.parse(fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8')).steps.generate;
    L.assertion('the app recorded the model at the start, with nothing typed', JSON.stringify(recorded.models_used) === JSON.stringify([L.MODEL]), JSON.stringify(recorded));
    await expectPassed(page, 'generate');
    await page.locator('#continue').click();
    await L.waitFor(async () => (await L.apiState()).steps.find((x) => x.id === 'generate').status === 'done', 5000, 'generate step done');
    L.note('current item', JSON.stringify((await L.apiState()).current_item || (await L.apiState()).current_step));
  } finally { await browser.close(); }
}

async function stageRestart() {
  const { browser, page } = await L.openBrowser();
  try {
    // Showing the build step opens its AI window by itself, once; the server's Quit then closes it.
    const base = launchCount();
    await openApp(page);
    L.assertion('before restart: current step is build', (await L.apiState()).current_step === 'build');
    await awaitAutoStart(page, 'build', 'restart: build opens its AI window by itself', base);
    await page.locator('#quit').click();
    await page.locator('dialog.confirm').getByRole('button', { name: 'Quit' }).click();
    await page.getByRole('heading', { name: 'eval-coach has stopped' }).waitFor({ timeout: 15000 });
    const stillUp = await L.waitFor(async () => !L.pidAlive(state.serverPid), 15000, 'server exit').catch(() => false);
    L.assertion('Quit stops the server process', Boolean(stillUp));
  } finally { await browser.close(); }

  await L.startServer();
  const b2 = await L.openBrowser();
  try {
    const afterQuit = launchCount();
    await openApp(b2.page);
    await L.sleep(2000);
    const s = await L.apiState();
    L.assertion('after restart: the step already started once, so no AI window opens by itself', !s.terminal.running && s.step.cli.can_auto_start === false && launchCount() === afterQuit, `launches ${launchCount() - afterQuit}`);
    L.assertion('after restart: configured and at build', s.configured === true && s.current_step === 'build', JSON.stringify({ c: s.configured, cur: s.current_step }));
    L.assertion('after restart: setup retained', s.setup.cli_command === L.CLI_COMMAND && /(eval|standin)-project/.test(s.setup.project_path), `${s.setup.cli_command} ${s.setup.project_path}`);
    const gen = await L.apiState('generate');
    const recordedAfter = JSON.parse(fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8')).steps.generate;
    L.assertion('after restart: generate shows 5 runs and the recorded model', gen.step.data.runs.every((r) => r.done) && recordedAfter.models_used.length === 1 && recordedAfter.models_used[0] === L.MODEL);
    L.assertion('after restart: UI shows build step', /build/i.test(await heading(b2.page)) || (await heading(b2.page)).length > 0, await heading(b2.page));
  } finally { await b2.browser.close(); }
}

async function ensureHeading(page, regex) {
  const h = await heading(page);
  L.assertion(`on expected step ${regex}`, regex.test(h), h);
}

async function reloadCheck(page, tag) {
  const before = await L.readScreen(page);
  L.note('reload', 'reloading page while CLI runs');
  await page.reload();
  await L.enterPart(page);
  await page.locator('.xterm-rows').waitFor({ timeout: 10000 });
  await L.waitFor(async () => (await L.readScreen(page)).trim().length > 0, 10000, 'terminal replay after reload');
  const after = await L.readScreen(page);
  L.logScreen(`${tag}-after-reload`, after);
  const url = page.url();
  L.assertion('reload: token not in URL', !url.includes('t='), url);
  const beforeLines = L.normLines(before).filter((l) => l.length > 12);
  const afterText = L.normLines(after).join('\n');
  L.assertion('reload: terminal stream replayed earlier output', beforeLines.length === 0 || beforeLines.some((l) => afterText.includes(l)), `${beforeLines.length} lines compared`);
  L.assertion('reload: app recovered at same step, CLI still running', (await L.apiState()).terminal.running === true);
  const changed = await L.waitFor(async () => { const now = await L.readScreen(page); return now !== after ? 'changed' : null; }, 40000, 'terminal update after reload').catch(() => null);
  L.assertion('reload: terminal output keeps streaming after reload', changed === 'changed');
}

async function stageBuild() {
  const { browser, page } = await L.openBrowser();
  try {
    const base = launchCount();
    await openApp(page);
    await ensureHeading(page, /build/i);
    await openAi(page, 'build', 'build', base);
    L.assertion('no answer key anywhere yet', !exists(L.projectKeyPath()) && !exists(L.sealedKeyPath()));
    await L.waitReady(page, 'build');
    await expectSendRefused('build');
    await pasteLine('build', 'build');
    const checker = path.join(PROJECT, L.PF ? 'promptfooconfig.yaml' : 'check.py');
    let reloaded = false;
    await L.driveCli(page, 'build', async ({ busy, idleMs, elapsedMs, screen }) => {
      if (!reloaded && busy && elapsedMs > 8000) {
        reloaded = true;
        await reloadCheck(page, 'build');
        return false;
      }
      if (exists(checker) && !busy && idleMs > 10000) return true;
      if (!exists(checker) && !busy && idleMs > 60000) await L.stopRun(page, 'build stalled with no check.py', screen);
      return false;
    });
    L.assertion('CLI stream reload exercised', reloaded);
    L.assertion('the reload did not open a second AI window', launchCount() === base + 1, String(launchCount() - base));
    L.assertion(`${path.basename(checker)} written`, exists(checker));
    await L.clickAndWait(page, '#cli-stop', '/api/step/stop');
    await waitCliRunningFalse();

    await page.getByRole('button', { name: 'Run the first look' }).click();
    await page.locator('.result-file').first().waitFor({ timeout: 40000 });
    await assertUiMatchesChecker(page, '#col-left', ['runs/run-1.txt'], 'first look');
    const boxes = page.getByRole('checkbox');
    const count = await boxes.count();
    for (let i = 0; i < count; i += 1) await boxes.nth(i).check();
    await L.sleep(800);
    await expectPassed(page, 'build');
    await page.locator('#continue').click();
    await L.sleep(800);
    L.assertNoProjectKey();
  } finally { await browser.close(); }
}

// A step that is not open is refused, so the answer key cannot be in its response; an open step must not hold it.
async function keyWithheld(step) {
  const s = await L.apiState(step);
  if (s.error) return s.error.code === 'step_locked' && !JSON.stringify(s).includes('answer_key_markdown":"');
  return (s.step.data.answer_key_markdown ?? null) === null;
}

async function postApi(route, body) {
  const res = await fetch(`http://127.0.0.1:${state.port}${route}`, {
    method: 'POST',
    headers: { 'X-Eval-Token': state.token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() };
}

// Script track: the fake CLI makes nothing usable, so the participant uses the Northwind example's own fixtures.
// Only the two fixture files are written, into the folder the CLI would have used, and the normal gate runs after.
async function fixturesRecovery(page, wf) {
  const MODE_FILE = path.join(L.WORK, 'fake-cli-mode.txt');
  const kit = path.join(L.ROOT, 'app', 'eval_coach', 'kit', 'northwind');
  const names = ['fixture-bad.txt', 'fixture-polished-but-wrong.txt'];
  fs.writeFileSync(MODE_FILE, 'no-fixtures');
  try {
    await pasteLine('fixtures', 'fixtures (nothing usable)');
    await L.driveCli(page, 'fixtures (nothing usable)', async ({ screen }) => /STAND-IN: no fixtures could be made/.test(screen));
  } finally { fs.rmSync(MODE_FILE, { force: true }); }
  L.assertion('recovery: the CLI made nothing usable', names.every((n) => !hasText(wf(n))), L.listTree(FIX_WORK).join(','));

  const note = await page.locator('#example-fixtures-note').innerText();
  L.assertion('recovery: the page says these are the Practice task\'s own fixtures', /Practice task's own fixtures/.test(note) && /test cases only/.test(note) && /No answer key is written now/.test(note), note);
  L.assertion('recovery: the button waits while the CLI runs', (await page.locator('#use-example-fixtures').getAttribute('aria-disabled')) === 'true');
  const refused = await postApi('/api/step/use-example-fixtures', { step: 'fixtures' });
  L.assertion('recovery: refused while the CLI runs', refused.status === 400 && refused.body.error.code === 'cli_running', JSON.stringify(refused.body.error));
  L.assertion('recovery: nothing was written while the CLI ran', names.every((n) => !exists(wf(n))));

  await L.clickAndWait(page, '#check-work', '/api/step/check');
  await page.locator('.check-head').waitFor({ timeout: 15000 });
  L.assertion('recovery: the normal gate fails with nothing usable', /Not done yet/.test(await page.locator('.check-head').innerText()));
  L.assertion('recovery: the failed gate copied nothing to the project', !exists(path.join(PROJECT, 'fixtures', names[0])));

  await L.clickAndWait(page, '#cli-stop', '/api/step/stop');
  await waitCliRunningFalse();
  await L.waitFor(async () => (await page.locator('#use-example-fixtures').getAttribute('aria-disabled')) !== 'true', 10000, 'the example button to be ready');
  const resp = await L.clickAndWait(page, '#use-example-fixtures', '/api/step/use-example-fixtures');
  L.assertion('recovery: the example fixtures were accepted', resp.ok(), String(resp.status()));
  L.assertion('recovery: exactly the two fixtures are in the CLI\'s fixtures folder', JSON.stringify(L.listTree(path.join(FIX_WORK, 'fixtures'))) === JSON.stringify(names), L.listTree(FIX_WORK).join(','));
  L.assertion('recovery: both are the example\'s own files, byte for byte', names.every((n) => sha(wf(n)) === sha(path.join(kit, n))));
  L.assertion('recovery: no answer key anywhere', L.answerKeyLocations().length === 0, L.answerKeyLocations().join(','));
  L.assertion('recovery: the project has no fixtures yet (the gate copies them)', !exists(path.join(PROJECT, 'fixtures', names[0])));
  const again = await postApi('/api/step/use-example-fixtures', { step: 'fixtures' });
  L.assertion('recovery: text is never replaced without confirmation', again.status === 400 && again.body.error.code === 'confirm_replace', JSON.stringify(again.body.error));
}

async function stageFixtures() {
  const { browser, page } = await L.openBrowser({ tall: true });
  let stream = null;
  try {
    L.setCliFolder(FIX_WORK);
    stream = L.watchStream();
    const base = launchCount();
    await openApp(page);
    await ensureHeading(page, /fixture/i);
    await openAi(page, 'fixtures', 'fixtures', base);
    const tree = L.listTree(FIX_WORK);
    L.assertion('fixtures-work holds only the 3 allowed files at start', JSON.stringify(tree) === JSON.stringify(['prompt-v0.md', 'skills/make-eval-fixtures/SKILL.md', 'test-cases.md']), tree.join(','));
    L.assertion('project has no fixtures answer key', !exists(L.projectKeyPath()));
    await L.waitReady(page, 'fixtures');
    await expectSendRefused('fixtures');
    const wf = (n) => path.join(FIX_WORK, 'fixtures', n);
    if (!L.PF) {
      await fixturesRecovery(page, wf);
    } else {
      await pasteLine('fixtures', 'fixtures');
      await L.driveCli(page, 'fixtures', async ({ busy, idleMs, screen }) => {
        if (hasText(wf('fixture-bad.txt')) && hasText(wf('fixture-polished-but-wrong.txt')) && !busy && idleMs > 8000) return true;
        if (!busy && idleMs > 60000) await L.stopRun(page, 'fixtures stalled', screen);
        return false;
      });
    }
    await L.assertNoProjectKey();
    await expectPassed(page, 'fixtures');
    L.assertion('no answer key anywhere after the fixtures step', L.answerKeyLocations().length === 0, L.answerKeyLocations().join(','));
    const fixturesData = (await L.apiState('fixtures')).step.data;
    L.assertion('fixtures step data has no key entry', !('key_held' in fixturesData) && !JSON.stringify(fixturesData).includes('answer-key'), JSON.stringify(fixturesData));
    L.assertion('project fixtures has both outputs and no key', hasText(path.join(PROJECT, 'fixtures', 'fixture-bad.txt')) && hasText(path.join(PROJECT, 'fixtures', 'fixture-polished-but-wrong.txt')) && !exists(L.projectKeyPath()), L.listTree(path.join(PROJECT, 'fixtures')).join(','));
    await L.waitFor(async () => !(await L.apiState()).terminal.running, 15000, 'CLI stopped after fixtures');
    L.assertion('progress.json holds no key or fixture text', (() => { const r = L.assertProgressClean(); return !r.keyHit && !r.fixtureHit; })());
    stream.check('fixtures session');
    await continueIntoAi(page, L.PF ? 'fixtures-config' : 'readback', `${L.PF ? 'fixtures-config' : 'readback'} (opens by itself on Continue)`);
  } finally { if (stream) stream.stop(); await browser.close(); }
}

async function stageReadback() {
  const { browser, page } = await L.openBrowser({ tall: true });
  let stream = null;
  try {
    L.setCliFolder(PROJECT);
    stream = L.watchStream();
    const base = launchCount();
    await openApp(page);
    await ensureHeading(page, /read/i);
    await openAi(page, 'readback', 'readback', base);
    await L.waitReady(page, 'readback');
    await expectSendRefused('readback');
    await pasteLine('readback', 'readback');
    const hasExample = () => fs.readdirSync(path.join(PROJECT, 'examples')).some((f) => /^c\d+-pass\.txt$/i.test(f));
    await L.driveCli(page, 'readback', async ({ busy, idleMs, screen }) => {
      if (hasExample() && !busy && idleMs > 12000) return true;
      if (!busy && idleMs > 60000) await L.stopRun(page, 'readback stalled', screen);
      return false;
    });
    L.assertion('readback produced example files', hasExample());
    await L.clickAndWait(page, '#cli-stop', '/api/step/stop');
    await waitCliRunningFalse();
    const criteria = (await L.apiState('readback')).step.data.criteria;
    L.assertion('readback lists parsed criteria', criteria.length === 6, criteria.map((c) => c.id).join(','));
    for (const c of criteria) {
      const group = page.getByRole('radiogroup', { name: new RegExp(`^${c.id} `) });
      const answer = c.id === 'C6' ? 'No' : 'Yes';
      await group.getByRole('radio', { name: answer, exact: true }).check();
    }
    await page.locator('#readback-note').fill('C6 checks keywords only; I would reword that threshold.');
    await page.locator('#readback-note').blur();
    await L.sleep(800);
    await expectPassed(page, 'readback');
    stream.check('readback session');
    await page.locator('#continue').click();
    await L.sleep(800);
  } finally { if (stream) stream.stop(); await browser.close(); }
}

async function stagePredict() {
  const { browser, page } = await L.openBrowser();
  try {
    await openApp(page);
    await ensureHeading(page, /predict/i);
    L.assertion('before lock: API withholds answer key', await keyWithheld('run'));
    const polished = await page.locator('.polished-text').innerText();
    L.assertion('polished fixture text is shown', polished.trim().length > 0);
    const criteria = (await L.apiState('predict')).step.data.criteria;
    const badGuess = { C1: 'F', C2: 'F', C3: 'F', C4: 'F', C5: 'F', C6: 'F' };
    const polGuess = { C1: 'P', C2: 'P', C3: 'P', C4: 'P', C5: 'P', C6: 'P' };
    const label = { P: 'PASS', F: 'FAIL', NC: 'NOT CHECKED' };
    for (const c of criteria) {
      await page.getByRole('radiogroup', { name: new RegExp(`^${c.id} .*Bad fixture`) }).getByRole('radio', { name: label[badGuess[c.id] || 'F'] }).check();
      await page.getByRole('radiogroup', { name: new RegExp(`^${c.id} .*Polished fixture`) }).getByRole('radio', { name: label[polGuess[c.id] || 'P'] }).check();
    }
    await page.locator('#predict-wrong').fill('It looks right but a fact does not match the notes.');
    await page.locator('#predict-catches').fill('The content criteria, probably C3 or C6.');
    await page.locator('#predict-worst_guess').fill('C2, the grouped-by-client labels.');
    await L.shot(page, 'predict.png');
    await page.evaluate(() => { document.getElementById('col-left').scrollTop = 1e6; });
    await L.shot(page, 'predict-bottom.png');
    await page.locator('#lock-predictions').click();
    const [resp] = await Promise.all([
      page.waitForResponse((r) => new URL(r.url()).pathname === '/api/step/submit' && r.request().postData().includes('"lock":true')),
      page.locator('dialog.confirm').getByRole('button', { name: 'Lock my predictions' }).click(),
    ]);
    L.assertion('predictions locked', resp.ok(), String(resp.status()));
    L.markPredictLocked();
    await L.sleep(500);
    L.assertion('after lock, before run: API withholds answer key', await keyWithheld('run'));
    await expectPassed(page, 'predict');
    await continueIntoAi(page, 'key', 'key (opens by itself on Continue)');
  } finally { await browser.close(); }
}

async function stageKey() {
  const { browser, page } = await L.openBrowser({ tall: true });
  try {
    L.setCliFolder(KEY_WORK);
    const base = launchCount();
    await openApp(page);
    await ensureHeading(page, /answer key/i);
    L.assertion('no answer key exists before the key session', L.answerKeyLocations().length === 0, L.answerKeyLocations().join(','));
    await openAi(page, 'key', 'key', base);
    const tree = L.listTree(KEY_WORK);
    L.assertion('key-work holds exactly the 5 allowed files', JSON.stringify(tree) === JSON.stringify(['fixtures/fixture-bad.txt', 'fixtures/fixture-polished-but-wrong.txt', 'prompt-v0.md', 'skills/make-eval-fixtures/SKILL.md', 'test-cases.md']), tree.join(','));
    L.assertion('no answer key exists right before the line is pasted', L.answerKeyLocations().length === 0, L.answerKeyLocations().join(','));
    await L.waitReady(page, 'key');
    L.assertion('key step: API has no key text before the session writes it', (await L.apiState('key')).step.data.key_held === false);
    await expectSendRefused('key');
    await pasteLine('key', 'key');
    const workKey = L.keyWorkKeyPath();
    await L.driveCli(page, 'key', async ({ busy, idleMs, screen }) => {
      if (hasText(workKey) && !busy && idleMs > 8000) return true;
      if (!busy && idleMs > 60000) await L.stopRun(page, 'key stalled', screen);
      return false;
    });
    L.assertion('the key session is the first thing to create a key, in key-work only', hasText(workKey) && JSON.stringify(L.answerKeyLocations().map((p) => p.toLowerCase())) === JSON.stringify([workKey.toLowerCase()]), L.answerKeyLocations().join(','));
    const fixturesBefore = ['fixture-bad.txt', 'fixture-polished-but-wrong.txt'].map((n) => sha(path.join(PROJECT, 'fixtures', n)));
    const keyWritten = fs.readFileSync(workKey, 'utf8');
    await L.assertNoProjectKey();
    await expectPassed(page, 'key');
    L.assertion('sealed: key moved to sealed storage', exists(L.sealedKeyPath()) && !exists(L.keyWorkKeyPath()));
    L.assertion('sealed key is the key that was written', fs.readFileSync(L.sealedKeyPath(), 'utf8') === keyWritten);
    L.assertion('project fixtures unchanged by the key step', JSON.stringify(fixturesBefore) === JSON.stringify(['fixture-bad.txt', 'fixture-polished-but-wrong.txt'].map((n) => sha(path.join(PROJECT, 'fixtures', n)))));
    L.assertion('project has no answer key', !exists(L.projectKeyPath()));
    await L.waitFor(async () => !(await L.apiState()).terminal.running, 15000, 'CLI stopped after key');
    L.assertion('after key: API withholds answer key from the run step', await keyWithheld('run'));
    L.assertion('key step reports the key held', (await L.apiState('key')).step.data.key_held === true);
    L.assertion('progress.json holds no key or fixture text', (() => { const r = L.assertProgressClean(); return !r.keyHit && !r.fixtureHit; })());
    await page.locator('#continue').click();
    await L.sleep(800);
  } finally { await browser.close(); }
}

async function stageRun() {
  const { browser, page } = await L.openBrowser();
  try {
    await openApp(page);
    await ensureHeading(page, /run/i);
    L.assertion('before run: answer key hidden in page', (await page.locator('#answer-key-body').count()) === 0);
    await L.clickAndWait(page, '#run-fixtures', '/api/step/run-checker');
    await page.locator('.run-grid').waitFor({ timeout: 40000 });
    const indep = L.independentRun(['fixtures/fixture-bad.txt', 'fixtures/fixture-polished-but-wrong.txt']);
    const gridRows = await page.locator('.run-grid tbody tr').evaluateAll((trs) => trs.map((tr) => {
      const verdicts = Array.from(tr.querySelectorAll('.verdict')).map((v) => v.className.match(/v-(\S+)/)[1]);
      return { id: tr.querySelector('.crit-id').textContent, cells: verdicts };
    }));
    const uiBad = Object.fromEntries(gridRows.map((r) => [r.id, r.cells[1]]));
    const uiPolished = Object.fromEntries(gridRows.map((r) => [r.id, r.cells[3]]));
    const indepBad = indep['fixture-bad.txt'];
    const indepPol = indep['fixture-polished-but-wrong.txt'];
    L.assertion('run grid verdicts equal independent check.py run', JSON.stringify(sorted({ a: uiBad, b: uiPolished })) === JSON.stringify(sorted({ a: indepBad, b: indepPol })), `ui bad ${JSON.stringify(uiBad)} indep bad ${JSON.stringify(indepBad)} ui pol ${JSON.stringify(uiPolished)} indep pol ${JSON.stringify(indepPol)}`);

    const key = page.locator('#answer-key-body');
    await key.waitFor({ timeout: 10000 });
    const keyText = await key.innerText();
    const sealed = fs.readFileSync(L.sealedKeyPath(), 'utf8');
    const firstHeading = sealed.split(/\r?\n/).find((l) => l.replace(/[#*\s]/g, '').length > 3);
    L.assertion('answer key revealed after run', keyText.trim().length > 50 && keyText.toLowerCase().includes(firstHeading.replace(/^[#\s*]+/, '').trim().slice(0, 12).toLowerCase()), keyText.slice(0, 120));

    const selects = page.locator('.surprise-row select');
    const n = await selects.count();
    L.note('surprises', String(n));
    for (let i = 0; i < n; i += 1) await selects.nth(i).selectOption(i % 2 === 0 ? 'reads_differently' : 'vague');
    await L.sleep(1000);
    await L.shot(page, 'run.png');
    await page.evaluate(() => { document.getElementById('col-left').scrollTop = 1e6; });
    await L.shot(page, 'run-bottom.png');
    await expectPassed(page, 'run');
    fs.writeFileSync(path.join(L.WORK, 'polished-before.json'), JSON.stringify(indepPol));
    fs.writeFileSync(path.join(L.WORK, 'key-copy.md'), L.redact(sealed));
    await continueIntoAi(page, 'fix', 'fix (opens by itself on Continue)');
    L.note('run-grid', JSON.stringify(gridRows));
  } finally { await browser.close(); }
}

function applyFixEdit(text) {
  const edit = JSON.parse(fs.readFileSync(path.join(L.WORK, 'fix-edit.json'), 'utf8'));
  if (!text.includes(edit.find)) throw new Error(`fix-edit find text not present: ${edit.find}`);
  return { text: text.replace(edit.find, edit.replace), edit };
}

async function stageFix() {
  const { browser, page } = await L.openBrowser({ tall: true });
  try {
    L.setCliFolder(PROJECT);
    const base = launchCount();
    await openApp(page);
    await ensureHeading(page, /fix/i);
    L.assertion('fix opens right after the run step, with no lesson between', (await L.apiState()).current_step === 'fix');
    await openAi(page, 'fix', 'fix', base);
    const checker = path.join(PROJECT, L.PF ? 'promptfooconfig.yaml' : 'check.py');
    const before = sha(checker);
    const tcPath = path.join(PROJECT, 'test-cases.md');
    const box = page.locator('#fix-test-cases');
    const original = await box.inputValue();
    const { text, edit } = applyFixEdit(original);
    L.note('fix-edit', JSON.stringify(edit));
    await box.fill(text);
    await box.blur();
    await L.clickAndWait(page, '#fix-save', '/api/step/submit');
    await L.waitFor(async () => (await L.apiState('fix')).step.data.test_cases_changed === true, 5000, 'test_cases_changed');
    const specSaved = fs.statSync(tcPath).mtimeMs;
    await L.waitReady(page, 'fix');
    await expectSendRefused('fix');
    await pasteLine('fix', 'fix');
    await L.driveCli(page, 'fix', async ({ busy, idleMs, screen }) => {
      if (sha(checker) !== before && !busy && idleMs > 12000) return true;
      if (!busy && idleMs > 60000) await L.stopRun(page, 'fix stalled', screen);
      return false;
    });
    L.assertion(`${path.basename(checker)} changed by the CLI`, sha(checker) !== before);
    L.assertion(`${path.basename(checker)} updated after the spec`, fs.statSync(checker).mtimeMs > specSaved, `${fs.statSync(checker).mtimeMs} > ${specSaved}`);
    await L.clickAndWait(page, '#cli-stop', '/api/step/stop');
    await waitCliRunningFalse();
    await L.clickAndWait(page, '#fix-rerun', '/api/step/run-checker');
    await page.locator('.result-file').first().waitFor({ timeout: 40000 });
    const s = (await L.apiState('fix')).step.data;
    L.assertion('fix: test_cases_changed and checker_changed_after', s.test_cases_changed && s.checker_changed_after, JSON.stringify({ t: s.test_cases_changed, c: s.checker_changed_after }));
    const indep = await assertUiMatchesChecker(page, '#col-left', ['fixtures/fixture-bad.txt', 'fixtures/fixture-polished-but-wrong.txt'], 'fix rerun');
    const polBefore = JSON.parse(fs.readFileSync(path.join(L.WORK, 'polished-before.json'), 'utf8'));
    const polAfter = indep['fixture-polished-but-wrong.txt'];
    L.assertion('fix: polished fixture result changed', JSON.stringify(sorted({ a: polBefore })) !== JSON.stringify(sorted({ a: polAfter })), `before ${JSON.stringify(polBefore)} after ${JSON.stringify(polAfter)}`);
    await expectPassed(page, 'fix');
    L.note('final', JSON.stringify((await L.apiState()).current_step));
    await L.shot(page, 'fix-done.png');
    L.assertion('all steps done', (await L.apiState()).current_step === null);
    L.assertNoProjectKey();
    L.assertion('progress.json clean at end', (() => { const r = L.assertProgressClean(); return !r.keyHit && !r.fixtureHit; })());
  } finally { await browser.close(); }
}

async function stageQuit() {
  const { browser, page } = await L.openBrowser();
  try {
    await openApp(page);
    await page.locator('#quit').click();
    await page.locator('dialog.confirm').getByRole('button', { name: 'Quit' }).click();
    await page.getByRole('heading', { name: 'eval-coach has stopped' }).waitFor({ timeout: 15000 });
  } finally { await browser.close(); }
  await L.waitFor(async () => !L.pidAlive(state.serverPid), 15000, 'server exit').catch(() => {});
}

// Restart the server after the earlier stop and save the authorized command through the app's API.
async function stageResume() {
  await L.startServer();
  const res = await fetch(`http://127.0.0.1:${state.port}/api/setup`, {
    method: 'POST',
    headers: { 'X-Eval-Token': state.token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_path: PROJECT, cli_command: L.CLI_COMMAND, starter: 'northwind' }),
  });
  const body = await res.json();
  L.assertion('resume: setup accepted', res.ok && body.ok === true, JSON.stringify(body.error || null));
  const s = await L.apiState();
  L.assertion('resume: CLI command saved', s.setup.cli_command === L.CLI_COMMAND, s.setup.cli_command);
  L.assertion('resume: progress kept (2 runs, on generate)', s.current_step === 'generate' && (await L.apiState('generate')).step.data.runs.filter((r) => r.done).length === 2);
}

// Bring the server back after a stop, without touching the saved setup.
async function stageServe() {
  await L.startServer();
  const s = await L.apiState();
  L.assertion('serve: command and progress kept', s.setup.cli_command === L.CLI_COMMAND && s.current_step === (process.argv[3] || 'build'), `${s.setup.cli_command} at ${s.current_step}`);
}

const LESSON_STAGES = require('./lesson-stages');
const STAGES = { serve: stageServe, resume: stageResume, setup: stageSetup, inputs: stageInputs, generate: stageGenerate, restart: stageRestart, build: stageBuild, fixtures: stageFixtures, readback: stageReadback, predict: stagePredict, key: stageKey, run: stageRun, fix: stageFix, quit: stageQuit, ...LESSON_STAGES };

(async () => {
  const name = process.argv[2];
  try {
    await STAGES[name]();
    L.note('stage-complete', name);
    L.saveState(state);
    if (state.violations.length) { console.log('VIOLATIONS', state.violations); process.exitCode = 4; }
  } catch (err) {
    L.note('stage-failed', `${name}: ${err && err.message}`);
    if (err instanceof L.StopRun) {
      L.killServer();
      process.exitCode = 3;
    } else {
      process.exitCode = 1;
      if (err && err.stack) console.error(L.redact(err.stack));
    }
    L.saveState(state);
  }
  process.exit();
})();
