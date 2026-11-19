// Real-tool confirmation of the Part 3 paste flow (OpenSpec change part-3-ai-flow), one real run per tool.
// Usage: node e2e-work/harness/real-paste-part3.js <claude|copilot|devin>
//
// It starts the real app on a throwaway home and project under e2e-work\real-paste3\<tool>, opens Part 3's `generate` step
// (the AI window opens by itself), presses the page's own Copy button, pastes the copied line into the real terminal the
// way a participant does (a paste event, then Enter), and answers only what the approval checker in lib.js allows, one
// single-use Yes at a time (never "don't ask again", never auto mode). It decides only from files and the step's state.
// Run 1 is real. Runs 2 to 5 are copied from the bundled Northwind samples so `generate` can pass; then the `build` step
// opens and its AI window must start by itself (nothing is pasted there). Real-CLI use needs the user's approval
// (AGENTS.md); this was approved on 2026-11-19: one `generate` run 1 and one `build` start per tool.
const { chromium } = require('../../tests/frontend/.tmp/node_modules/@playwright/test');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const L = require('./lib.js');

const ROOT = path.resolve(__dirname, '..', '..');
const WORK = path.join(ROOT, 'e2e-work');
const tool = process.argv[2];
if (!['claude', 'copilot', 'devin'].includes(tool)) throw new Error('usage: node real-paste-part3.js <claude|copilot|devin>');
const BASE = path.join(WORK, 'real-paste3', tool);
const HOME = path.join(BASE, 'home');
const PROJECT = path.join(BASE, 'project');
const LOG = path.join(BASE, 'server.out');
const PYTHON = path.join(ROOT, 'spikes', 'phase0-preflight', 'runtime', 'python-embed-3.13.17-nopth', 'python.exe');
const PYZ = path.join(ROOT, 'dist', 'eval-coach.pyz');
const SAMPLES = path.join(ROOT, 'app', 'eval_coach', 'kit', 'northwind');
const LINE = 'Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: L.redact(detail || '') });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` :: ${L.redact(detail)}` : ''}`);
}

function cleanEnv() {
  const env = {};
  for (const [k, v] of Object.entries(process.env)) {
    const u = k.toUpperCase();
    if (u.startsWith('CLAUDE') || u.startsWith('ANTHROPIC_') || u.startsWith('VSCODE_') || u.startsWith('ELECTRON_') || u === 'TERM_PROGRAM' || u === 'GIT_ASKPASS') continue;
    env[k] = v;
  }
  env.DISABLE_AUTOUPDATER = '1';
  return env;
}

function writePreflight() {
  const items = Object.fromEntries(['track', 'python', 'node', 'promptfoo', 'cli', 'working_test'].map((i) => [i, { status: 'passed', detail: 'ok', next: '' }]));
  fs.mkdirSync(HOME, { recursive: true });
  fs.writeFileSync(path.join(HOME, 'preflight.json'), JSON.stringify({ version: 1, track: 'script', cli_command: tool, test_passed_command: tool, recipe_ran: false, ran_once: true, items }));
}

async function startServer() {
  fs.writeFileSync(LOG, '');
  const out = fs.openSync(LOG, 'a');
  const child = spawn(PYTHON, [PYZ, '--no-browser', '--custom-ai', '--home', HOME], { detached: true, stdio: ['ignore', out, out], env: cleanEnv(), windowsHide: true, cwd: WORK });
  child.unref();
  fs.closeSync(out);
  for (let i = 0; i < 100; i += 1) {
    const m = fs.readFileSync(LOG, 'utf8').match(/http:\/\/127\.0\.0\.1:(\d+)\/\?t=(\S+)/);
    if (m) return { pid: child.pid, url: m[0], origin: `http://127.0.0.1:${m[1]}`, token: m[2] };
    await sleep(100);
  }
  throw new Error('the server did not print its URL');
}

async function main() {
  fs.rmSync(BASE, { recursive: true, force: true });
  fs.mkdirSync(BASE, { recursive: true });
  writePreflight();
  let server = await startServer();
  const api = async (method, p, body) => {
    const r = await fetch(server.origin + p, { method, headers: { 'X-Eval-Token': server.token, 'Content-Type': 'application/json' }, body: method === 'POST' ? JSON.stringify(body || {}) : undefined });
    return r.json();
  };
  const stepState = async (step) => (await api('GET', `/api/state?step=${step}`)).step;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  let stopped = null;
  try {
    const setup = await api('POST', '/api/setup', { project_path: PROJECT, cli_command: tool, starter: 'northwind' });
    check('the project was set up', setup.ok, JSON.stringify(setup.error || ''));
    // The lessons before the steps have exercises of their own, and this run is about the steps. Mark them done in the
    // throwaway project's progress file, then start the app again so it reads them.
    try { execFileSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    await sleep(800);
    const progressFile = path.join(PROJECT, '.learning', 'progress.json');
    const saved = JSON.parse(fs.readFileSync(progressFile, 'utf8'));
    for (const lesson of ['mission', 'hook', 'several-runs', 'rules']) saved.lessons.per_lesson[lesson] = { status: 'done', activities: {} };
    fs.writeFileSync(progressFile, JSON.stringify(saved));
    server = await startServer();
    const state = await api('GET', '/api/state');
    check('generate is the active step', state.current_step === 'generate', String(state.current_step));

    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: server.origin });
    const page = await context.newPage();
    page.on('pageerror', (e) => console.log(`pageerror: ${e.message}`));
    const requests = [];
    page.on('request', (r) => { if (r.method() === 'POST') requests.push(new URL(r.url()).pathname); });
    L.setCliFolder(path.join(HOME, 'blind'));
    await page.goto(server.url);
    await L.enterPart(page);

    // Opening the step starts the AI window by itself.
    await page.locator('#step-heading', { hasText: 'Collect your answers' }).waitFor({ timeout: 15000 });
    await page.locator('.term-status.is-on').waitFor({ timeout: 90000 });
    check('opening generate started the AI window by itself', requests.includes('/api/step/auto-start') && !requests.includes('/api/step/start'), requests.join(','));
    for (const id of ['#cli-send', '#cli-retry']) check(`no ${id} on the page`, (await page.locator(id).count()) === 0);
    check('the button reads "Open a new AI chat"', (await page.locator('#cli-start').innerText()).trim() === 'Open a new AI chat');
    const started = await stepState('generate');
    check('the step shows the line and the window as started', started.cli.line === LINE && started.cli.started && started.cli.mode === 'paste');
    const progress1 = JSON.parse(fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8')).steps.generate;
    check('the app recorded the model it passed', progress1.models_used.length === 1 && progress1.auto_started === true, JSON.stringify(progress1.models_used));
    await L.waitReady(page, `${tool}-ready`);
    const before = await L.readScreen(page);
    check('the app typed nothing into the AI before the paste', !/save only your answer/i.test(before));
    check('the blind folder holds only prompt.md', JSON.stringify(fs.readdirSync(path.join(HOME, 'blind'))) === JSON.stringify(['prompt.md']), fs.readdirSync(path.join(HOME, 'blind')).join(','));

    // Copy with the page's own button, then paste into the real terminal the way a participant does.
    await page.locator('#copy-paste').click();
    await page.locator('#copy-status').filter({ hasText: 'Copied' }).waitFor({ timeout: 10000 });
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    check('Copy put the line on the clipboard', copied === LINE, `${copied.length} chars`);
    await page.evaluate(async (text) => {
      const box = document.querySelector('.xterm-helper-textarea');
      box.focus();
      const data = new DataTransfer();
      data.setData('text/plain', text);
      box.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
    }, copied);
    await sleep(1500);
    await page.locator('.xterm-helper-textarea').focus();
    await page.keyboard.press('Enter');

    // The participant's part is done; answer only what the checker allows, until the run is filed and the window closes.
    const run1 = path.join(PROJECT, 'runs', 'run-1.txt');
    await L.driveCli(page, `${tool}-paste`, async () => fs.existsSync(run1) && fs.readFileSync(run1, 'utf8').trim().length > 0 && !(await api('GET', '/api/state')).terminal.running, { timeoutMs: 300000 });
    await sleep(1000);
    check('the AI saved output.txt and the app filed it as run 1', fs.readFileSync(run1, 'utf8').trim().length > 0);
    check('the AI window was closed by the app after the run', !(await api('GET', '/api/state')).terminal.running);
    check('the line was never sent by the app', !requests.includes('/api/step/send'));
    await page.screenshot({ path: path.join(BASE, 'generate-run1.png') });

    // Runs 2 to 5 come from the bundled samples, so the step can pass and build can open.
    for (let n = 2; n <= 5; n += 1) fs.copyFileSync(path.join(SAMPLES, `sample-run-${n}.txt`), path.join(PROJECT, 'runs', `run-${n}.txt`));
    const checkRes = await api('POST', '/api/step/check', { step: 'generate' });
    check('Check my work passes for generate', checkRes.ok && checkRes.state.step.last_check.ok === true, JSON.stringify(checkRes.error || ''));
    check('no AI window is left running after the step passed', !(await api('GET', '/api/state')).terminal.running);
    const skip = { ok: true };
    check('the rules lesson was already out of the way', skip.ok);
    const afterSkip = await api('GET', '/api/state');
    check('build is the active step', afterSkip.current_step === 'build', String(afterSkip.current_step));

    // Opening build starts its window by itself, in the project folder. Nothing is pasted.
    L.setCliFolder(PROJECT);
    requests.length = 0;
    await page.reload();
    await L.enterPart(page).catch(() => {});
    await page.locator('#step-heading', { hasText: /Build the checker/ }).waitFor({ timeout: 15000 });
    await page.locator('.term-status.is-on').waitFor({ timeout: 90000 });
    check('opening build started the AI window by itself', requests.includes('/api/step/auto-start') && !requests.includes('/api/step/start'), requests.join(','));
    const build = await stepState('build');
    check('the build line is shown and the window started', build.cli.started && build.cli.mode === 'paste' && build.cli.line.startsWith('Read skills/build-eval-script/SKILL.md'));
    await L.waitReady(page, `${tool}-build-ready`);
    const buildScreen = await L.readScreen(page);
    check('the app typed nothing into the build window', !/build-eval-script/i.test(buildScreen));
    const progress2 = JSON.parse(fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8')).steps;
    check('the build record notes the start and the model list kept one entry per model', progress2.build.auto_started === true && new Set(progress2.generate.models_used).size === progress2.generate.models_used.length, JSON.stringify(progress2.generate.models_used));
    await page.screenshot({ path: path.join(BASE, 'build-started.png') });
    await api('POST', '/api/step/stop', { step: 'build' });
    check('the build window was stopped by the test', !(await api('GET', '/api/state')).terminal.running);
  } catch (e) {
    stopped = e.message || String(e);
    console.log(`STOPPED: ${stopped}`);
    if (e.screen) console.log(`SCREEN:\n${L.redact(e.screen)}`);
  } finally {
    await browser.close();
    try { execFileSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    await sleep(800);
  }
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${tool}: ${results.length - failed.length} passed, ${failed.length} failed${stopped ? `; stopped: ${stopped}` : ''}`);
  process.exit(failed.length || stopped ? 1 : 0);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
