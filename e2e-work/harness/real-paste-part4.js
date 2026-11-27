// Real-tool confirmation of Part 4 (OpenSpec change part-4-harness follow-up), one real session per step and tool.
// Usage: node e2e-work/harness/real-paste-part4.js <claude|copilot|devin> [script|promptfoo]
//
// It starts the real app on a throwaway home and project under e2e-work\real-paste4\<tool>-<track>, skips Parts 1 to 3 (no
// demo password is used), chooses the bundled Practice baseline, saves the known-good answer, a hypothesis and an edited
// prompt, then:
//   measure-1: the AI window opens by itself, the harness pastes the step's line the way a participant does, and the real AI
//              saves answer 1. Answers 2 to 5 are copied from the bundled Northwind samples so the round can be scored.
//   decide-1:  the round is scored and undone, the decide window opens by itself, the harness pastes its line, and the real AI
//              appends the Iteration 1 entry to the Practice log. The participant's words are then written by the harness and
//              the step's own check must accept the AI's counts.
// On the promptfoo track the Practice config is the checker, so scoring runs the real pinned promptfoo.
// It answers only what the approval checker in lib.js allows, one single-use Yes at a time (never "don't ask again", never
// auto mode), and it decides only from files and the steps' state, never from the terminal. Real-CLI use needs the user's
// approval (AGENTS.md); approved on 2026-11-27: one measure answer and one decide line per tool, Script and promptfoo tracks.
if (process.platform !== 'win32') { console.log('SKIP: this runs on Windows only.'); process.exit(0); }
// User decision 2026-11-27: this approved real-tool run may accept Claude Code's default auto mode start (as real-paste.js does).
process.env.ALLOW_CLI_DEFAULT_AUTO_MODE = '1';
const { chromium } = require('../../tests/frontend/.tmp/node_modules/@playwright/test');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const L = require('./lib.js');

const ROOT = path.resolve(__dirname, '..', '..');
const WORK = path.join(ROOT, 'e2e-work');
const tool = process.argv[2];
const track = process.argv[3] || 'script';
const MANUAL = process.argv.includes('--manual-decide');
if (!['claude', 'copilot', 'devin'].includes(tool) || !['script', 'promptfoo'].includes(track)) throw new Error('usage: node real-paste-part4.js <claude|copilot|devin> [script|promptfoo]');
const PF = track === 'promptfoo';
const BASE = path.join(WORK, 'real-paste4', `${tool}-${track}`);
const HOME = path.join(BASE, 'home');
const PROJECT = path.join(BASE, 'project');
const PRACTICE = path.join(PROJECT, 'part-4', 'practice');
const ATTEMPT = path.join(PRACTICE, 'attempts', '1');
const LOG = path.join(BASE, 'server.out');
const PYTHON = path.join(ROOT, 'spikes', 'phase0-preflight', 'runtime', 'python-embed-3.13.17-nopth', 'python.exe');
const PYZ = path.join(ROOT, 'dist', 'eval-coach.pyz');
const SAMPLES = path.join(ROOT, 'app', 'eval_coach', 'kit', 'northwind');
const SPIKE = path.join(ROOT, 'spikes', 'phase0-preflight');
const MEASURE_LINE = 'Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.';
const HYPOTHESIS = 'A friendlier tone should make the update warmer and change nothing else.';
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
    if (u.startsWith('CLAUDE') || u.startsWith('ANTHROPIC_') || (u.startsWith('COPILOT_') && u !== 'COPILOT_HOME') || u.startsWith('VSCODE_') || u.startsWith('ELECTRON_') || u === 'TERM_PROGRAM' || u === 'GIT_ASKPASS') continue;
    env[k] = v;
  }
  env.DISABLE_AUTOUPDATER = '1';
  return env;
}

function writePreflight() {
  const items = Object.fromEntries(['track', 'python', 'node', 'promptfoo', 'cli', 'working_test'].map((i) => [i, { status: 'passed', detail: 'ok', next: '' }]));
  fs.mkdirSync(HOME, { recursive: true });
  fs.writeFileSync(path.join(HOME, 'preflight.json'), JSON.stringify({ version: 1, track, cli_command: tool, test_passed_command: tool, recipe_ran: false, ran_once: true, items }));
  if (PF) {
    fs.mkdirSync(path.join(HOME, 'runtime'), { recursive: true });
    for (const [link, target] of [[path.join(HOME, 'runtime', 'node'), path.join(SPIKE, 'runtime', 'node-v26.13.0-win-x64')], [path.join(HOME, 'npm-cache'), path.join(SPIKE, 'npm-cache')]]) {
      if (!fs.existsSync(target)) throw new Error(`the spike's private runtime is missing: ${target}`);
      fs.symlinkSync(target, link, 'junction');
    }
  }
}

// A junction is removed on its own, never recursively, so the spike's files are never touched.
function unlinkPf() {
  for (const link of [path.join(HOME, 'runtime', 'node'), path.join(HOME, 'npm-cache')]) {
    let st = null;
    try { st = fs.lstatSync(link); } catch { continue; }
    if (st.isSymbolicLink()) fs.rmdirSync(link);
  }
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

const hasText = (file) => fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0;

async function main() {
  try { unlinkPf(); } catch { /* none */ }
  fs.rmSync(BASE, { recursive: true, force: true });
  fs.mkdirSync(BASE, { recursive: true });
  writePreflight();
  let server = await startServer();
  const api = async (method, p, body) => {
    const r = await fetch(server.origin + p, { method, headers: { 'X-Eval-Token': server.token, 'Content-Type': 'application/json' }, body: method === 'POST' ? JSON.stringify(body || {}) : undefined });
    return r.json();
  };
  const stepState = async (step) => (await api('GET', `/api/state?step=${step}`)).step;
  const submit = (step, data) => api('POST', '/api/step/submit', { step, data });
  const must = (name, r) => { check(name, r && r.ok, JSON.stringify((r && (r.error || r.code)) || '')); if (!r || !r.ok) throw new Error(`${name} failed`); return r; };
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  let stopped = null;
  try {
    must('the project was set up', await api('POST', '/api/setup', { project_path: PROJECT, cli_command: tool, starter: 'northwind' }));
    // Parts 1 to 3 are skipped in the throwaway progress file and the Part 4 reading lessons are marked done, then the app
    // starts again so it reads them. This run is about the AI steps.
    try { execFileSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    await sleep(800);
    const progressFile = path.join(PROJECT, '.learning', 'progress.json');
    const saved = JSON.parse(fs.readFileSync(progressFile, 'utf8'));
    for (const lesson of ['p4-mission', 'p4-checker-first', 'p4-one-change', 'p4-worked-example']) saved.lessons.per_lesson[lesson] = { status: 'done', activities: {} };
    saved.lessons.skipped_parts = ['part-1', 'part-2', 'part-3'];
    fs.writeFileSync(progressFile, JSON.stringify(saved));
    server = await startServer();

    must('the Practice baseline was chosen', await submit('starting-point', { action: 'choose', choice: 'practice' }));
    check('the bundled Practice files were copied and the checker for this track is there', hasText(path.join(PRACTICE, 'prompt-v0.md')) && hasText(path.join(PRACTICE, PF ? 'promptfooconfig.yaml' : 'check.py')));
    must('the known-good answer was saved and accepted', await submit('known-good', { action: 'save', text: fs.readFileSync(path.join(SAMPLES, 'sample-run-1.txt'), 'utf8') }));
    check('known-good is done', (await stepState('known-good')).status === 'done');
    must('the hypothesis was saved', await submit('hypothesis-1', { action: 'save', text: HYPOTHESIS }));
    const start = fs.readFileSync(path.join(PRACTICE, 'prompt-v0.md'), 'utf8');
    must('the changed prompt was saved', await submit('edit-1', { action: 'save', prompt: `${start.replace(/\s+$/, '')}\n\n- Tone: friendly and upbeat.\n` }));
    check('measure-1 is open and waiting for its answers', (await stepState('measure-1')).status === 'active');

    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: server.origin });
    const page = await context.newPage();
    page.on('pageerror', (e) => console.log(`pageerror: ${e.message}`));
    const requests = [];
    page.on('request', (r) => { if (r.method() === 'POST') requests.push(new URL(r.url()).pathname); });
    const openPartFour = async () => {
      await page.goto(server.url);
      await page.waitForFunction(() => document.querySelector('#series-open-part-4') || document.querySelector('.wizard'), null, { timeout: 15000 });
      if (await page.locator('#series-open-part-4').count()) {
        await page.locator('#series-open-part-4').click();
        await page.locator('#series-list').waitFor({ state: 'detached', timeout: 15000 });
      }
    };
    const paste = async (line) => {
      await page.evaluate(async (text) => {
        const box = document.querySelector('.xterm-helper-textarea');
        box.focus();
        const data = new DataTransfer();
        data.setData('text/plain', text);
        box.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
      }, line);
      await sleep(1500);
      await page.locator('.xterm-helper-textarea').focus();
      await page.keyboard.press('Enter');
    };

    // ---- measure-1: one real answer ----
    L.setCliFolder(path.join(HOME, 'part4', 'blind'));
    await openPartFour();
    await page.locator('.term-status.is-on').waitFor({ timeout: 90000 });
    check('opening measure-1 started the AI window by itself', requests.includes('/api/step/auto-start') && !requests.includes('/api/step/start'), requests.join(','));
    const m0 = await stepState('measure-1');
    check('the measure step shows the line and the window as started', m0.cli.line === MEASURE_LINE && m0.cli.started && m0.cli.mode === 'paste', JSON.stringify(m0.cli));
    await L.waitReady(page, `${tool}-${track}-measure-ready`);
    check('the app typed nothing into the AI before the paste', !/save only your answer/i.test(await L.readScreen(page)));
    const blind = path.join(HOME, 'part4', 'blind');
    check('the blind folder holds only this round\'s prompt.md', JSON.stringify(fs.readdirSync(blind)) === '["prompt.md"]' && fs.readFileSync(path.join(blind, 'prompt.md'), 'utf8').replace(/\r\n/g, '\n') === fs.readFileSync(path.join(ATTEMPT, 'prompt.md'), 'utf8').replace(/\r\n/g, '\n'), fs.readdirSync(blind).join(','));
    await page.locator('#copy-paste').click();
    await page.locator('#copy-status').filter({ hasText: 'Copied' }).waitFor({ timeout: 10000 });
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    check('Copy put the measure line on the clipboard', copied === MEASURE_LINE, `${copied.length} chars`);
    await paste(copied);
    const run1 = path.join(ATTEMPT, 'runs', 'run-1.txt');
    await L.driveCli(page, `${tool}-${track}-measure`, async () => hasText(run1) && !(await api('GET', '/api/state')).terminal.running, { timeoutMs: 300000 });
    await sleep(1000);
    check('the real AI saved output.txt and the app filed it as answer 1', hasText(run1));
    check('the AI window was closed by the app after the answer', !(await api('GET', '/api/state')).terminal.running);
    check('the measure line was never sent by the app', !requests.includes('/api/step/send'));
    await page.screenshot({ path: path.join(BASE, 'measure-1.png') });

    for (let n = 2; n <= 5; n += 1) fs.copyFileSync(path.join(SAMPLES, `sample-run-${n}.txt`), path.join(ATTEMPT, 'runs', `run-${n}.txt`));
    const m1 = await stepState('measure-1');
    check('all five answers are saved and nothing is scored yet', m1.data.all_saved === true && m1.data.attempt.scored === false, JSON.stringify(m1.data.runs));
    must('the round was scored', await submit('measure-1', { action: 'score' }));
    const scored = await stepState('measure-1');
    check('the scored round shows every rule before and after', scored.data.attempt.compare.rules.length > 0 && scored.data.attempt.compare.rules.every((r) => r.before && r.after), JSON.stringify(scored.data.attempt.compare.before));
    must('the round was undone', await submit('decide-1', { action: 'decide', choice: 'undo' }));

    // ---- decide-1: the real AI writes the log entry ----
    const d = await stepState('decide-1');
    check('decide-1 shows a line naming the Practice round and log', d.cli.can_auto_start === true && d.cli.line.includes('part-4/practice') && d.cli.line.includes('iteration-log.md'), d.cli.line);
    L.setCliFolder(PROJECT);
    requests.length = 0;
    const logFile = path.join(PRACTICE, 'iteration-log.md');
    const entryDone = () => fs.existsSync(logFile) && /^## Iteration 1\b/m.test(fs.readFileSync(logFile, 'utf8'));
    if (MANUAL) {
      // The AI window is started and the line pasted through the app, then you open the printed URL in your own browser,
      // read each command the AI asks to run and press Yes (or No) yourself. Nothing is approved by this script.
      const started = await api('POST', '/api/step/auto-start', { step: 'decide-1' });
      check('decide-1 started the AI window by itself', started.ok, JSON.stringify(started.error || ''));
      await sleep(15000);
      const pasted = await api('POST', '/api/terminal/input', { data: Buffer.from(`${d.cli.line}\r`).toString('base64') });
      check('the participant\'s paste of the decide line was accepted', pasted.ok, JSON.stringify(pasted.error || ''));
      console.log(`\n>>> MANUAL: open this URL in your own browser, then read each prompt in the AI window and press Yes (or No) yourself:\n>>> ${server.url}\n>>> Waiting up to 15 minutes for the Iteration 1 entry in ${logFile}\n`);
      const until = Date.now() + 900000;
      while (!entryDone() && Date.now() < until) await sleep(2000);
      await sleep(10000);
    } else {
      await openPartFour();
      await page.locator('.term-status.is-on').waitFor({ timeout: 90000 });
      check('opening decide-1 started the AI window by itself', requests.includes('/api/step/auto-start') && !requests.includes('/api/step/start'), requests.join(','));
      await L.waitReady(page, `${tool}-${track}-decide-ready`);
      check('the app typed nothing into the decide window', !/iteration-log/i.test(await L.readScreen(page)));
      await page.locator('#copy-paste').click();
      await page.locator('#copy-status').filter({ hasText: 'Copied' }).waitFor({ timeout: 10000 });
      const line = await page.evaluate(() => navigator.clipboard.readText());
      check('Copy put the decide line on the clipboard', line === d.cli.line, `${line.length} chars`);
      await paste(line);
      await L.driveCli(page, `${tool}-${track}-decide`, async (s) => entryDone() && !s.busy && s.idleMs > 6000, { timeoutMs: 420000 });
    }
    check('the real AI appended an Iteration 1 entry to the Practice log', entryDone());
    await page.screenshot({ path: path.join(BASE, 'decide-1.png') });
    await api('POST', '/api/step/stop', { step: 'decide-1' });
    const text = fs.readFileSync(logFile, 'utf8');
    const section = text.slice(text.search(/^## Iteration 1\b/m));
    check('the entry copies the saved hypothesis word for word', section.includes(HYPOTHESIS));
    check('the participant\'s own log in the project folder was not touched', !fs.existsSync(path.join(PROJECT, 'iteration-log.md')));

    // The participant writes their own words; the step's own check must then agree with the AI's counts.
    fs.writeFileSync(logFile, text.slice(0, text.length - section.length) + section
      .replace(/^- Hypothesis:/m, '- Decision: undone\n- Hypothesis:')
      .replace(/^- Change:.*$/m, '- Change: Added a friendly-tone line (real-tool run).')
      .replace(/^- Result:.*$/m, '- Result: See the table (real-tool run).')
      .replace(/^- Reasoning:.*$/m, '- Reasoning: Checked the counts (real-tool run).'));
    const gate = await api('POST', '/api/step/check', { step: 'decide-1' });
    const items = (await stepState('decide-1')).last_check.items;
    check('the step\'s own check accepted the real AI\'s log entry', gate.ok && (await stepState('decide-1')).status === 'done', JSON.stringify(items.filter((i) => !i.ok)));
    check('no AI window is left running', !(await api('GET', '/api/state')).terminal.running);
    const part4 = JSON.parse(fs.readFileSync(progressFile, 'utf8')).parts['part-4'];
    check('progress.json holds the decision, hashes and counts only', !JSON.stringify(part4).includes(HYPOTHESIS) && part4.attempts.some((a) => a.n === 1 && a.decision === 'undone'));
  } catch (e) {
    stopped = e.message || String(e);
    console.log(`STOPPED: ${stopped}`);
    if (e.screen) console.log(`SCREEN:\n${L.redact(e.screen)}`);
  } finally {
    await browser.close();
    try { execFileSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    await sleep(800);
    unlinkPf();
  }
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${tool} (${track}): ${results.length - failed.length} passed, ${failed.length} failed${stopped ? `; stopped: ${stopped}` : ''}`);
  process.exit(failed.length || stopped ? 1 : 0);
}

main().catch((e) => {
  console.error(e.stack || e.message);
  process.exit(1);
});
