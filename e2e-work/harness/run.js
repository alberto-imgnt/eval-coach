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

async function startCli(page, label) {
  L.countSession(label);
  const resp = await L.clickAndWait(page, '#cli-start', '/api/step/start');
  if (!resp.ok()) throw new Error(`start failed: ${resp.status()}`);
}

async function waitCliRunningFalse() {
  await L.waitFor(async () => !(await L.apiState()).terminal.running, 10000, 'CLI to stop');
}

async function stageGenerate() {
  const { browser, page } = await L.openBrowser();
  try {
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
      await page.locator('#cli-start').waitFor();
      await L.waitFor(async () => (await page.locator('#cli-start').getAttribute('aria-disabled')) !== 'true', 15000, 'start button');
      await startCli(page, `generate run ${n}`);
      const tree = L.listTree(BLIND);
      L.assertion(`blind folder holds only prompt.md at start of run ${n}`, tree.length === 1 && tree[0] === 'prompt.md', tree.join(','));
      L.assertion('fixtures answer key absent', !exists(L.projectKeyPath()));
      await L.waitReady(page, tag);

      if (n === 1) {
        // Stop, then Start again, before running: start-again-after-stop check.
        await L.clickAndWait(page, '#cli-stop', '/api/step/stop');
        await waitCliRunningFalse();
        await L.waitFor(async () => (await page.locator('#cli-retry').getAttribute('aria-disabled')) !== 'true', 10000, 'Start again enabled');
        L.assertion('Start again is enabled after the CLI was stopped', true);
        L.countSession('generate run 1 (Start again after stop)');
        const r2 = await L.clickAndWait(page, '#cli-retry', '/api/step/start');
        L.assertion('Start again restarts the CLI', r2.ok(), String(r2.status()));
        const tree2 = L.listTree(BLIND);
        L.assertion('blind folder holds only prompt.md after Start again', tree2.length === 1 && tree2[0] === 'prompt.md', tree2.join(','));
        await L.waitReady(page, `${tag}-retry`);
        await L.shot(page, 'generate-live.png');
      }

      const sendResp = await L.clickAndWait(page, '#cli-send', '/api/step/send');
      L.assertion(`send ok run ${n}`, sendResp.ok(), String(sendResp.status()));
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
    await openApp(page);
    L.assertion('before restart: current step is build', (await L.apiState()).current_step === 'build');
    await page.locator('#quit').click();
    await page.locator('dialog.confirm').getByRole('button', { name: 'Quit' }).click();
    await page.getByRole('heading', { name: 'eval-coach has stopped' }).waitFor({ timeout: 15000 });
    const stillUp = await L.waitFor(async () => !L.pidAlive(state.serverPid), 15000, 'server exit').catch(() => false);
    L.assertion('Quit stops the server process', Boolean(stillUp));
  } finally { await browser.close(); }

  await L.startServer();
  const b2 = await L.openBrowser();
  try {
    await openApp(b2.page);
    const s = await L.apiState();
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
    await openApp(page);
    await ensureHeading(page, /build/i);
    await startCli(page, 'build');
    L.assertion('no answer key anywhere yet', !exists(L.projectKeyPath()) && !exists(L.sealedKeyPath()));
    await L.waitReady(page, 'build');
    await L.clickAndWait(page, '#cli-send', '/api/step/send');
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
    await L.clickAndWait(page, '#cli-send', '/api/step/send');
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
    await openApp(page);
    await ensureHeading(page, /fixture/i);
    L.setCliFolder(FIX_WORK);
    stream = L.watchStream();
    await startCli(page, 'fixtures');
    const tree = L.listTree(FIX_WORK);
    L.assertion('fixtures-work holds only the 3 allowed files at start', JSON.stringify(tree) === JSON.stringify(['prompt-v0.md', 'skills/make-eval-fixtures/SKILL.md', 'test-cases.md']), tree.join(','));
    L.assertion('project has no fixtures answer key', !exists(L.projectKeyPath()));
    await L.waitReady(page, 'fixtures');
    const wf = (n) => path.join(FIX_WORK, 'fixtures', n);
    if (!L.PF) {
      await fixturesRecovery(page, wf);
    } else {
      await L.clickAndWait(page, '#cli-send', '/api/step/send');
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
    await page.locator('#continue').click();
    await L.sleep(800);
  } finally { if (stream) stream.stop(); await browser.close(); }
}

async function stageReadback() {
  const { browser, page } = await L.openBrowser({ tall: true });
  let stream = null;
  try {
    await openApp(page);
    await ensureHeading(page, /read/i);
    L.setCliFolder(PROJECT);
    stream = L.watchStream();
    await startCli(page, 'readback');
    await L.waitReady(page, 'readback');
    await L.clickAndWait(page, '#cli-send', '/api/step/send');
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
    L.assertion('before lock: API withholds answer key', ((await L.apiState('run')).step.data.answer_key_markdown ?? null) === null);
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
    L.assertion('after lock, before run: API withholds answer key', ((await L.apiState('run')).step.data.answer_key_markdown ?? null) === null);
    await expectPassed(page, 'predict');
    await page.locator('#continue').click();
    await L.sleep(800);
  } finally { await browser.close(); }
}

async function stageKey() {
  const { browser, page } = await L.openBrowser({ tall: true });
  try {
    await openApp(page);
    await ensureHeading(page, /answer key/i);
    L.assertion('no answer key exists before the key session', L.answerKeyLocations().length === 0, L.answerKeyLocations().join(','));
    L.setCliFolder(KEY_WORK);
    await startCli(page, 'key');
    const tree = L.listTree(KEY_WORK);
    L.assertion('key-work holds exactly the 5 allowed files', JSON.stringify(tree) === JSON.stringify(['fixtures/fixture-bad.txt', 'fixtures/fixture-polished-but-wrong.txt', 'prompt-v0.md', 'skills/make-eval-fixtures/SKILL.md', 'test-cases.md']), tree.join(','));
    L.assertion('no answer key exists right before the line is sent', L.answerKeyLocations().length === 0, L.answerKeyLocations().join(','));
    await L.waitReady(page, 'key');
    L.assertion('key step: API has no key text before the session writes it', (await L.apiState('key')).step.data.key_held === false);
    await L.clickAndWait(page, '#cli-send', '/api/step/send');
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
    L.assertion('after key: API withholds answer key from the run step', ((await L.apiState('run')).step.data.answer_key_markdown ?? null) === null);
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
    await page.locator('#continue').click();
    await L.sleep(800);
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
    await openApp(page);
    await ensureHeading(page, /fix/i);
    L.assertion('fix opens right after the run step, with no lesson between', (await L.apiState()).current_step === 'fix');
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
    L.setCliFolder(PROJECT);
    await startCli(page, 'fix');
    await L.waitReady(page, 'fix');
    await L.clickAndWait(page, '#cli-send', '/api/step/send');
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
const STAGES = { serve: stageServe, resume: stageResume, setup: stageSetup, generate: stageGenerate, restart: stageRestart, build: stageBuild, fixtures: stageFixtures, readback: stageReadback, predict: stagePredict, key: stageKey, run: stageRun, fix: stageFix, quit: stageQuit, ...LESSON_STAGES };

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
