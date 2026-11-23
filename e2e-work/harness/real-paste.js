// Real-tool confirmation of the Part 1 paste flow (OpenSpec change step-flow), one real session for one tool.
// Usage: node e2e-work/harness/real-paste.js <claude|copilot|devin>
//
// It starts the real app on a throwaway home and project under e2e-work\real-paste\<tool>, saves a cold prompt in the page
// (the AI window opens by itself), presses the page's own Copy button, pastes the copied text into the real terminal the
// way a participant does (a paste event on the terminal, then Enter), and answers only what the approval checker in
// lib.js allows, one single-use Yes at a time (never "don't ask again", never auto mode). It decides only from files and
// the step's state, never from what the terminal shows. Real-CLI use needs the user's approval (AGENTS.md); this was
// approved on 2026-11-19 for the cold step, one session per tool, with the harness answering the trust question and
// the create-output.txt question.
if (process.platform !== 'win32') { console.log('SKIP: this runs on Windows only.'); process.exit(0); }
const { chromium } = require('../../tests/frontend/.tmp/node_modules/@playwright/test');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const L = require('./lib.js');

const ROOT = path.resolve(__dirname, '..', '..');
const WORK = path.join(ROOT, 'e2e-work');
const tool = process.argv[2];
if (!['claude', 'copilot', 'devin'].includes(tool)) throw new Error('usage: node real-paste.js <claude|copilot|devin>');
const BASE = path.join(WORK, 'real-paste', tool);
const HOME = path.join(BASE, 'home');
const PROJECT = path.join(BASE, 'project');
const LOG = path.join(BASE, 'server.out');
const PYTHON = path.join(ROOT, 'spikes', 'phase0-preflight', 'runtime', 'python-embed-3.13.17-nopth', 'python.exe');
const PYZ = path.join(ROOT, 'dist', 'eval-coach.pyz');
const PROMPT = 'Please turn my rough notes into a short Friday update for my project lead.';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: L.redact ? L.redact(detail || '') : detail || '' });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` :: ${detail}` : ''}`);
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
  const server = await startServer();
  const api = async (method, p, body) => {
    const r = await fetch(server.origin + p, { method, headers: { 'X-Eval-Token': server.token, 'Content-Type': 'application/json' }, body: method === 'POST' ? JSON.stringify(body || {}) : undefined });
    return r.json();
  };
  const stepState = async () => (await api('GET', '/api/state?step=cold')).step;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  let stopped = null;
  try {
    const setup = await api('POST', '/api/setup', { project_path: PROJECT, cli_command: tool, starter: 'northwind' });
    check('the project was set up', setup.ok, JSON.stringify(setup.error || ''));
    const mission = await api('POST', '/api/lesson/complete', { lesson: 'p1-mission', part: 'part-1' });
    check('the Part 1 mission is done, so cold is open', mission.ok, JSON.stringify(mission.error || ''));

    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: server.origin });
    const page = await context.newPage();
    page.on('pageerror', (e) => console.log(`pageerror: ${e.message}`));
    await page.goto(server.url);
    await page.locator('#series-open-part-1').click();
    await page.locator('#step-heading', { hasText: 'Write it your way' }).waitFor({ timeout: 15000 });
    check('the cold step is open', (await page.locator('#step-heading').innerText()) === 'Write it your way');
    for (const id of ['#cli-send', '#check-work']) check(`no ${id} on the page`, (await page.locator(id).count()) === 0);

    // Saving the prompt opens the AI window by itself.
    L.setCliFolder(path.join(HOME, 'part1', 'cold'));
    await page.locator('#prompt-editor').fill(PROMPT);
    await page.locator('#part-save').click();
    await page.locator('.term-status.is-on').waitFor({ timeout: 60000 });
    check('saving the prompt opened the AI window by itself', true);
    const started = await stepState();
    check('the app recorded the model it passed', Boolean(started.cli && started.cli.started), '');
    await L.waitReady(page, `${tool}-ready`);
    const before = await L.readScreen(page);
    check('the app typed nothing into the AI before the paste', !/Save only your answer|Rough notes|Friday update/i.test(before));
    check('the AI folder holds only prompt.md', JSON.stringify(fs.readdirSync(path.join(HOME, 'part1', 'cold'))) === JSON.stringify(['prompt.md']), fs.readdirSync(path.join(HOME, 'part1', 'cold')).join(','));

    // Copy with the page's own button, then paste into the real terminal the way a participant does.
    await page.locator('#copy-paste').click();
    await page.locator('#copy-status').filter({ hasText: 'Copied' }).waitFor({ timeout: 10000 });
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    const shown = (await stepState()).data.paste_text;
    const norm = (s) => s.replace(/\r\n/g, '\n');
    check('Copy put the text to paste on the clipboard', norm(copied) === shown && copied.includes(PROMPT), `${copied.length} chars copied, ${shown.length} shown`);
    check('the text equals prompt.md', fs.readFileSync(path.join(HOME, 'part1', 'cold', 'prompt.md'), 'utf8') === shown);
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

    // The participant's part is done; answer only what the checker allows, until the step finishes by itself.
    await L.driveCli(page, `${tool}-paste`, async () => (await stepState()).status === 'done', { timeoutMs: 300000 });
    await sleep(1500);
    const done = await stepState();
    const out = path.join(PROJECT, 'part-1', 'output-cold.txt');
    check('the AI saved output.txt and the app filed it', fs.existsSync(out) && fs.readFileSync(out, 'utf8').trim().length > 0);
    check('the step finished by itself, with no Check press', done.status === 'done' && done.last_check && done.last_check.ok === true);
    const progress = JSON.parse(fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8')).parts['part-1'];
    check('the recorded model came from the app, not from typing', Boolean(progress.steps.cold.model_name), progress.steps.cold.model_name);
    check('the AI window was closed by the app', !(await api('GET', '/api/state')).terminal.running);
    await page.locator('#continue').waitFor({ timeout: 15000 });
    check('Continue to the next step is offered', (await page.locator('#continue').innerText()).startsWith('Continue to:'));
    check('the page stayed on the finished step', (await page.locator('#step-heading').innerText()) === 'Write it your way');
    await page.screenshot({ path: path.join(BASE, 'finished.png') });
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
