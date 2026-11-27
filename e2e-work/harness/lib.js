// Shared harness code: server control, xterm reader, strict approval classifier,
// logging with email redaction, and the assertions that run during the flow.
if (process.platform !== 'win32') { console.log('SKIP: the stand-in harness runs on Windows only.'); process.exit(0); }
const { chromium } = require('../../tests/frontend/.tmp/node_modules/@playwright/test');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn, execFileSync } = require('child_process');

const ROOT = 'C:\\Projects\\Improving\\eval-coach';
const WORK = path.join(ROOT, 'e2e-work');
const STANDIN = process.env.E2E_PROFILE === 'standin';
const TRACK = process.env.E2E_TRACK === 'promptfoo' ? 'promptfoo' : 'script'; // the second full pass uses the promptfoo track
const PF = TRACK === 'promptfoo';
const SUFFIX = STANDIN ? (PF ? '-standin-pf' : '-standin') : '';
const HOME = path.join(WORK, STANDIN ? (PF ? 'standin-home-pf' : 'standin-home') : 'home');
const PROJECT = path.join(WORK, STANDIN ? (PF ? 'standin-project-pf' : 'standin-project') : 'eval-project');
const STATE_FILE = path.join(WORK, `harness-state${SUFFIX}.json`);
const SERVER_LOG = path.join(WORK, `server${SUFFIX}.out`);
const LOG_DIR = path.join(WORK, `logs${SUFFIX}`);
const SHOTS = path.join(WORK, `screenshots${SUFFIX}`);
const PYTHON = path.join(ROOT, 'spikes', 'phase0-preflight', 'runtime', 'python-embed-3.13.17-nopth', 'python.exe');
const PYZ = process.env.E2E_PYZ || path.join(ROOT, 'dist', 'eval-coach.pyz'); // E2E_PYZ: a private build, see build-private-pyz.py
const CLI_COMMAND = STANDIN ? `${PYTHON} ${path.join(WORK, 'harness', 'fake_cli.py')}` : 'claude --model sonnet --permission-mode default';
// The model the app records at each AI start: the stand-in has no model data, so no option is passed; a real command names its own.
const MODEL = STANDIN ? "the AI's own default model" : 'sonnet';
const CLI_TIMEOUT_MS = 240000;
// stand-in: 27 before Part 4 on the Script pass (the promptfoo pass adds 2, for its extra step and its optional live step) + 18 for Part 4 (the `part4` stage's two rounds and the `part4-practice` stage's one round, each five answers and one log window) = 45 on the Script pass and 47 on the promptfoo pass. real: 13 used + fixtures, readback, fix + 1 retry (user-approved option A); Part 1 needs two more real sessions only after the user approves them
const MAX_SESSIONS = STANDIN ? 47 : 17;
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+/g;
// Demo access for the stand-in runs: Part 3 is reached directly, so the app starts with a throwaway hash (made here,
// for a throwaway password) and the harness turns demo access on. The real password and hash are never used here.
const DEMO_PASSWORD = 'throwaway-harness-password';
const DEMO_HASH_FILE = path.join(WORK, 'harness-demo-hash.json');

for (const d of [WORK, HOME, LOG_DIR, SHOTS]) fs.mkdirSync(d, { recursive: true });

function redact(s) { return String(s).replace(EMAIL_RE, '[redacted-email]'); }
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
function loadState() { try { return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch { return { sessions: [], assertions: [], violations: [], prompts: [] }; } }
function saveState(s) { fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2)); }

const state = loadState();
function note(kind, detail) {
  const line = `${new Date().toISOString()} ${kind}: ${redact(detail)}`;
  fs.appendFileSync(path.join(LOG_DIR, 'harness.log'), line + '\n');
  console.log(line);
}
function assertion(name, ok, detail) {
  state.assertions.push({ name, ok: Boolean(ok), detail: redact(detail || '') });
  saveState(state);
  note(ok ? 'ASSERT-PASS' : 'ASSERT-FAIL', `${name}${detail ? ' :: ' + detail : ''}`);
  if (!ok) throw new Error(`assertion failed: ${name} ${detail || ''}`);
}
function softAssertion(name, ok, detail) {
  state.assertions.push({ name, ok: Boolean(ok), detail: redact(detail || '') });
  saveState(state);
  note(ok ? 'ASSERT-PASS' : 'ASSERT-FAIL', `${name}${detail ? ' :: ' + detail : ''}`);
}
function violation(detail) {
  state.violations.push(redact(detail));
  saveState(state);
  note('VIOLATION', detail);
}

class StopRun extends Error { constructor(reason, screen) { super(reason); this.reason = reason; this.screen = screen; } }

// ---- server control -------------------------------------------------------
function filteredEnv() {
  const env = {};
  for (const [k, v] of Object.entries(process.env)) {
    const u = k.toUpperCase();
    if (u.startsWith('CLAUDE') || u.startsWith('ANTHROPIC_') || u.startsWith('VSCODE_') || u.startsWith('ELECTRON_')) continue;
    env[k] = v;
  }
  env.DISABLE_AUTOUPDATER = '1'; // harness only: the CLI must not update itself during the test
  return env;
}

function demoArgs() {
  if (!STANDIN) return [];
  const salt = crypto.randomBytes(16);
  const iterations = 1000;
  const hash = crypto.pbkdf2Sync(DEMO_PASSWORD, salt, iterations, 32, 'sha256');
  fs.writeFileSync(DEMO_HASH_FILE, JSON.stringify({ salt: salt.toString('hex'), hash: hash.toString('hex'), iterations }));
  return ['--demo-hash-file', DEMO_HASH_FILE];
}

// The first request after a start: turn demo access on for the stand-in run (a real run is unlocked by hand).
async function unlockDemo(port, token) {
  if (!STANDIN) return;
  const res = await fetch(`http://127.0.0.1:${port}/api/demo/unlock`, {
    method: 'POST', headers: { 'X-Eval-Token': token, 'Content-Type': 'application/json' }, body: JSON.stringify({ password: DEMO_PASSWORD }),
  });
  if (!res.ok) throw new Error(`demo access did not turn on: ${res.status}`);
}

async function startServer() {
  fs.writeFileSync(SERVER_LOG, '');
  const out = fs.openSync(SERVER_LOG, 'a');
  const child = spawn(PYTHON, [PYZ, '--no-browser', '--custom-ai', ...demoArgs(), '--home', HOME], {
    detached: true, stdio: ['ignore', out, out], env: filteredEnv(), windowsHide: true, cwd: WORK,
  });
  child.unref();
  fs.closeSync(out);
  state.serverPid = child.pid;
  for (let i = 0; i < 100; i += 1) {
    const text = fs.readFileSync(SERVER_LOG, 'utf8');
    const m = text.match(/http:\/\/127\.0\.0\.1:(\d+)\/\?t=(\S+)/);
    if (m) {
      state.url = m[0];
      state.port = m[1];
      state.token = m[2];
      saveState(state);
      await unlockDemo(state.port, state.token);
      note('server', `started pid ${child.pid} port ${state.port}`);
      return;
    }
    await sleep(100);
  }
  throw new Error('server did not print its URL');
}

function pidAlive(pid) {
  try { return execFileSync('tasklist', ['/FI', `PID eq ${pid}`, '/NH'], { encoding: 'utf8' }).includes(String(pid)); } catch { return false; }
}

function killServer() {
  if (state.serverPid && pidAlive(state.serverPid)) {
    try { execFileSync('taskkill', ['/PID', String(state.serverPid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    note('server', `killed pid ${state.serverPid}`);
  }
  state.serverPid = null;
  saveState(state);
}

// ---- browser --------------------------------------------------------------
async function openBrowser(opts = {}) {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: opts.tall ? { width: 2600, height: 3400 } : { width: 1280, height: 800 } });
  const page = await context.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  installGuards(page);
  page.on('pageerror', (err) => note('pageerror', err.message));
  page.on('console', (msg) => { if (msg.type() === 'error') note('console-error', msg.text()); });
  return { browser, context, page };
}

// The app opens on the Series map (or on setup, the first time). This goes into Part 3 from the map.
async function enterPart(page) {
  await page.waitForFunction(() => document.querySelector('#series-open-part-3') || document.querySelector('.wizard'), null, { timeout: 15000 });
  if (await page.locator('#series-open-part-3').count()) {
    await page.locator('#series-open-part-3').click();
    await page.locator('#series-list').waitFor({ state: 'detached', timeout: 15000 });
  }
}

// ---- key secrecy guards -----------------------------------------------------
function sealedKeyDir() {
  const norm = path.resolve(PROJECT).toLowerCase();
  const id = crypto.createHash('sha256').update(norm).digest('hex').slice(0, 16);
  return path.join(HOME, 'sealed', id);
}
function sealedKeyPath() { return path.join(sealedKeyDir(), 'answer-key.md'); }
function workKeyPath() { return path.join(HOME, 'fixtures-work', 'fixtures', 'answer-key.md'); }
function keyWorkKeyPath() { return path.join(HOME, 'key-work', 'fixtures', 'answer-key.md'); }
function projectKeyPath() { return path.join(PROJECT, 'fixtures', 'answer-key.md'); }

// Every place an answer key could be. Before the key step, none of these exists.
function answerKeyLocations() {
  const roots = [path.join(HOME, 'fixtures-work'), path.join(HOME, 'key-work'), path.join(HOME, 'sealed'), path.join(PROJECT, 'fixtures')];
  const found = [];
  const walk = (d) => {
    if (!fs.existsSync(d)) return;
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name.toLowerCase() === 'answer-key.md') found.push(p);
    }
  };
  roots.forEach(walk);
  return found;
}

function keyLines() {
  const lines = new Set();
  for (const p of [sealedKeyPath(), workKeyPath(), keyWorkKeyPath()]) {
    if (!fs.existsSync(p)) continue;
    for (const raw of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
      const line = raw.trim();
      if (line.length >= 40) lines.add(line);
    }
  }
  return lines;
}

function bodyContainsKey(body, lines) {
  for (const line of lines) {
    if (body.includes(line) || body.includes(JSON.stringify(line).slice(1, -1))) return line;
  }
  return null;
}

function markPredictLocked() { state.predictLocked = true; saveState(state); }

// The key text may appear only in the run step's own body, after a locked
// prediction and a successful run of the checker on both fixtures.
function bodyMayRevealKey(body) {
  if (!state.predictLocked) return false;
  let parsed;
  try { parsed = JSON.parse(body); } catch { return false; }
  const s = parsed && parsed.state ? parsed.state : parsed;
  const step = s && s.step;
  return Boolean(step && step.id === 'run' && step.data && step.data.result && step.data.result.ok === true);
}

function installGuards(page) {
  page.on('response', async (resp) => {
    let url;
    try { url = new URL(resp.url()); } catch { return; }
    if (!url.pathname.startsWith('/api/') || url.pathname.startsWith('/api/terminal/stream')) return;
    let body;
    try { body = await resp.text(); } catch { return; }
    state.responsesSeen = (state.responsesSeen || 0) + 1;
    const lines = keyLines();
    if (lines.size > 0) state.responsesCheckedAgainstKey = (state.responsesCheckedAgainstKey || 0) + 1;
    if (bodyMayRevealKey(body)) {
      if (lines.size > 0 && bodyContainsKey(body, lines)) state.keyRevealsSeen = (state.keyRevealsSeen || 0) + 1;
      return;
    }
    const hit = bodyContainsKey(body, lines);
    if (hit) violation(`answer key text leaked via ${url.pathname}${url.search}: ${hit.slice(0, 80)}`);
    if (/"answer_key_markdown":\s*"/.test(body)) violation(`answer_key_markdown set via ${url.pathname}${url.search}`);
  });
}

// ---- SSE terminal stream watcher ------------------------------------------
const ANSI_RE = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])/g;
const compact = (t) => t.replace(ANSI_RE, '').replace(/[\s\u00a0│┃║╭╮╰╯┌┐└┘─━═⎿]/g, '').toLowerCase();

function watchStream() {
  const chunks = [];
  const controller = new AbortController();
  let events = 0;
  (async () => {
    const res = await fetch(`http://127.0.0.1:${state.port}/api/terminal/stream?t=${encodeURIComponent(state.token)}`, { signal: controller.signal });
    const decoder = new TextDecoder();
    let buffer = '';
    for await (const part of res.body) {
      buffer += decoder.decode(part, { stream: true });
      let at;
      while ((at = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, at);
        buffer = buffer.slice(at + 2);
        if (!block.startsWith('event: output')) continue;
        const data = block.split('\n').find((l) => l.startsWith('data: '));
        if (data) { chunks.push(Buffer.from(JSON.parse(data.slice(6)).data, 'base64')); events += 1; }
      }
    }
  })().catch(() => {});
  return {
    // Raw terminal bytes stay in memory only. Only the verdict is kept.
    // Used only for sessions before the key step; the key session may print the key.
    check(label) {
      const keyPath = [sealedKeyPath(), workKeyPath()].find((p) => fs.existsSync(p));
      if (!keyPath) return softAssertion(`SSE stream vs answer key (${label})`, true, `no key exists yet; ${events} output events`);
      const stream = compact(Buffer.concat(chunks).toString('utf8'));
      const publicFiles = ['test-cases.md', 'prompt-v0.md', 'check.py', 'promptfooconfig.yaml', 'skills/make-eval-fixtures/SKILL.md', 'skills/build-eval-script/SKILL.md', 'skills/build-promptfoo-config/SKILL.md', 'fixtures/fixture-bad.txt', 'fixtures/fixture-polished-but-wrong.txt'];
      const publicText = compact(publicFiles.map((f) => path.join(PROJECT, f)).filter((p) => fs.existsSync(p)).map((p) => fs.readFileSync(p, 'utf8')).join('\n'));
      const SIZE = 40;
      let keyOnlyFragments = 0;
      const hits = [];
      for (const raw of fs.readFileSync(keyPath, 'utf8').split(/\r?\n/)) {
        const line = compact(raw);
        for (let i = 0; i + SIZE <= line.length; i += SIZE) {
          const frag = line.slice(i, i + SIZE);
          if (publicText.includes(frag)) continue;
          keyOnlyFragments += 1;
          if (stream.includes(frag)) hits.push(frag);
        }
      }
      const detail = `${events} output events, ${keyOnlyFragments} key-only fragments compared, ${hits.length} found in terminal stream`;
      softAssertion(`sealed key text absent from SSE terminal stream (${label})`, hits.length === 0, hits.length ? `${detail}. Printed by the CLI; the app does not write to this stream. First: ${hits[0]}` : detail);
      return hits.length;
    },
    stop() { controller.abort(); },
  };
}

function assertNoProjectKey() {
  if (fs.existsSync(projectKeyPath())) violation('<project>/fixtures/answer-key.md exists');
}

function assertProgressClean() {
  const progress = fs.readFileSync(path.join(PROJECT, '.learning', 'progress.json'), 'utf8');
  const hit = bodyContainsKey(progress, keyLines());
  const fixtureLines = [];
  for (const name of ['fixture-bad.txt', 'fixture-polished-but-wrong.txt']) {
    const p = path.join(PROJECT, 'fixtures', name);
    if (fs.existsSync(p)) {
      for (const raw of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
        const line = raw.trim();
        if (line.length >= 25) fixtureLines.push(line);
      }
    }
  }
  const fixtureHit = fixtureLines.find((l) => progress.includes(l) || progress.includes(JSON.stringify(l).slice(1, -1)));
  return { keyHit: hit, fixtureHit };
}

// ---- terminal screen and approvals -----------------------------------------
async function readScreen(page) {
  const text = await page.evaluate(() => {
    const rows = document.querySelector('.xterm-rows');
    return rows ? Array.from(rows.children).map((r) => r.textContent).join('\n') : '';
  });
  return text.replace(/\u00a0/g, ' ');
}

const BOX_RE = /[│┃║╭╮╰╯┌┐└┘─━═]/g;
function normLines(screen) {
  return screen.split('\n').map((l) => l.replace(BOX_RE, ' ').replace(/\s+/g, ' ').trim());
}

// Basic file and folder commands, approved only when their paths stay in e2e-work.
const BASIC_COMMANDS = new Set(['mkdir', 'ls', 'dir', 'cat', 'type', 'head', 'tail', 'wc', 'touch', 'cp', 'mv', 'copy', 'move',
  'new-item', 'get-childitem', 'get-content', 'copy-item', 'move-item', 'test-path']);

const WORK_NORM = WORK.toLowerCase().replace(/\\/g, '/');
function pathAllowed(p) {
  let norm = p.trim().replace(/^["']|["']$/g, '').replace(/\\/g, '/');
  if (!norm) return false;
  if (norm.split('/').includes('..')) return false;
  const gitBash = norm.match(/^\/([a-zA-Z])\/(.*)$/);
  if (gitBash) norm = `${gitBash[1]}:/${gitBash[2]}`;
  if (/^[a-zA-Z]:/.test(norm) || norm.startsWith('/')) return norm.toLowerCase().startsWith(WORK_NORM + '/');
  return true;
}

function lastIndex(items, test) {
  for (let i = items.length - 1; i >= 0; i -= 1) if (test(items[i])) return i;
  return -1;
}

// Splits on && and ; outside quotes. Returns null when quotes are unbalanced.
function splitSegments(text) {
  const out = [];
  let cur = '';
  let quote = null;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quote) { if (ch === quote) quote = null; cur += ch; continue; }
    if (ch === '"' || ch === "'") { quote = ch; cur += ch; continue; }
    if (ch === ';') { out.push(cur); cur = ''; continue; }
    if (ch === '&' && text[i + 1] === '&') { out.push(cur); cur = ''; i += 1; continue; }
    cur += ch;
  }
  if (quote) return null;
  out.push(cur);
  return out.map((p) => p.trim()).filter(Boolean);
}

function tokenize(segment) {
  return (segment.match(/"[^"]*"|'[^']*'|\S+/g) || []).map((t) => t.replace(/^["']|["']$/g, ''));
}

const SEGMENT_HEADS = new Set(['mkdir', 'touch', ':', 'cat', 'ls', 'echo', 'python', 'py', 'wc', 'grep', 'head', 'tail', 'sort', 'printf', 'sed']);
const READ_ONLY = new Set(['wc', 'grep', 'head', 'tail', 'sort', 'printf', 'sed']);
const COMMAND_WORD = /^(rm|rmdir|del|curl|wget|bash|sh|cmd|powershell|pwsh|python|python3|py|npm|pip|git|cd)(\.exe)?$/i;
const unquote = (t) => t.replace(/^["']|["']$/g, '');
// The folder the current step's CLI started in. `cd` is allowed only to this folder or a subfolder of it.
let cliFolder = null;
function setCliFolder(folder) { cliFolder = folder; }
function normFolder(p) {
  let norm = unquote(String(p).trim()).replace(/\\/g, '/').replace(/\/+$/, '');
  const gitBash = norm.match(/^\/([a-zA-Z])\/(.*)$/);
  if (gitBash) norm = `${gitBash[1]}:/${gitBash[2]}`;
  return norm.toLowerCase();
}
const isAbsolute = (p) => /^[a-zA-Z]:/.test(p) || /^[\\/]/.test(p);
// Every allowed cd stays inside the start folder and none may contain "..", so a relative
// target can't escape no matter which allowed cd ran before it.
function cdAllowed(target) {
  if (!cliFolder) return false;
  const norm = normFolder(target);
  const root = normFolder(cliFolder);
  if (!norm || norm.split('/').includes('..')) return false;
  if (isAbsolute(norm)) return norm === root || norm.startsWith(`${root}/`);
  return norm.split('/').every((seg) => /^[\w.-]+$/.test(seg) && !seg.startsWith('-'));
}

function toRows(input) {
  return typeof input === 'string' ? input.split('\n').map((text) => ({ text: text.trim(), nearFull: false })) : input;
}

// A soft-wrapped row continues only if the next row starts like a path, never like a command.
function continues(nextText) {
  const first = nextText.split(/\s+/)[0] || '';
  return /[./\\]/.test(first) && !COMMAND_WORD.test(first);
}

// Turns display rows into logical shell lines, dropping heredoc bodies. Returns {lines} or {reason}.
function parseCommand(input) {
  const rows = toRows(input).filter((r) => r.text !== '');
  if (!rows.length) return { reason: 'empty command' };
  const whole = rows.map((r) => r.text).join('\n');
  if (/…|\+\s*\d+\s+lines|ctrl\+\w+ to expand/i.test(whole)) return { reason: 'command text is truncated' };
  const lines = [];
  const problems = [];
  let i = 0;
  while (i < rows.length) {
    let line = rows[i].text;
    while (rows[i].nearFull && i + 1 < rows.length && continues(rows[i + 1].text)) { i += 1; line += ` ${rows[i].text}`; }
    i += 1;
    const open = line.match(/(?:^|&&|;)\s*cat\s*>\s*("[^"]*"|'[^']*'|[^\s<>&;|]+)\s*<<(-?)\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\3\s*$/);
    if (open) {
      if (open[2] === '-') problems.push('heredoc form <<- is not allowed');
      const target = unquote(open[1]);
      if (isAbsolute(target) || !pathAllowed(target)) problems.push(`heredoc target not allowed: ${target}`);
      const prefix = line.slice(0, open.index).trim();
      if (prefix) lines.push(prefix);
      const quoted = open[3] !== '';
      const delim = open[4];
      const body = [];
      let closed = false;
      while (i < rows.length) {
        const text = rows[i].text;
        i += 1;
        if (text === delim) { closed = true; break; }
        body.push(text);
      }
      if (!closed) problems.push(`heredoc is not closed, so the text is incomplete (delimiter ${delim})`);
      if (!quoted && /\$\(|`/.test(body.join('\n'))) problems.push(`heredoc body has $( or a backtick under an unquoted delimiter (${target})`);
      continue;
    }
    if (/<</.test(line)) { problems.push(`unsupported heredoc: ${line}`); continue; }
    if (/\\\s*$/.test(line)) { problems.push(`line continuation is not allowed: ${line}`); continue; }
    lines.push(line);
  }
  return { lines, problems };
}

function verifySubstitution(inner, loopVar) {
  const m = inner.trim().match(/^wc(\s+-[a-z]+)?\s*<?\s*("?)(\$\{?[A-Za-z_]\w*\}?|[^\s"$<>|&;`]+)\2$/);
  if (!m) return `$( ) is allowed only around wc: ${inner}`;
  const v = m[3].match(/^\$\{?([A-Za-z_]\w*)\}?$/);
  if (v) return v[1] === loopVar ? null : `unknown variable in $( ): ${m[3]}`;
  return pathAllowed(m[3]) && !isAbsolute(m[3]) ? null : `path not allowed in $( ): ${m[3]}`;
}

function verifySimple(part, loopVar, single) {
  const redirects = [];
  const body = part.replace(/(\d?>>?)\s*("[^"]*"|'[^']*'|[^\s>]+)/g, (_, op, target) => { redirects.push(unquote(target)); return ' '; });
  if (body.includes('>')) return `malformed redirect: ${part}`;
  for (const target of redirects) if (!pathAllowed(target) || /^(nul|con|prn|aux)$/i.test(target)) return `redirect not allowed: ${target}`;
  const tokens = tokenize(body);
  if (!tokens.length) return `empty segment: ${part}`;
  const head = tokens[0].replace(/\.exe$/i, '').toLowerCase();
  if (head === 'cd') {
    if (redirects.length || tokens.length !== 2) return `cd must have exactly one folder: ${part}`;
    if (!cdAllowed(tokens[1])) return `cd is allowed only to the folder this CLI started in or its subfolders: ${tokens[1]}`;
    return null;
  }
  const basicSingle = single && BASIC_COMMANDS.has(head);
  if (!SEGMENT_HEADS.has(head) && !basicSingle) return `command not allowed: ${tokens[0]}`;
  if (head !== 'printf' && /%/.test(body)) return `% is not allowed here: ${part}`;
  const args = tokens.slice(1);
  if (head === ':') {
    if (args.length || redirects.length !== 1) return `": " is allowed only as ": > <file>": ${part}`;
    return null;
  }
  if (head === 'python' || head === 'py') {
    if (!args[0] || args[0].startsWith('-') || !/\.py$/i.test(args[0])) return `python must run a .py file: ${part}`;
    for (const arg of args) if (arg.startsWith('-')) return `python flag not allowed: ${arg}`;
  }
  let scan = args;
  if (head === 'sed') {
    if (args[0] !== '-n' || args.some((a) => a.startsWith('-i') || a.startsWith('--in-place'))) return `only sed -n is allowed: ${part}`;
    if (!args[1] || !/^(\d*(,\d*)?|\/[^/]*\/)p$/.test(args[1])) return `sed script not allowed: ${args[1]}`;
    scan = args.slice(2);
  }
  if (head === 'grep') {
    const at = args.findIndex((a) => !a.startsWith('-'));
    scan = args.filter((_, i) => i !== at);
  }
  for (const arg of scan) {
    if (arg.startsWith('-')) continue;
    if ((head === 'echo' || head === 'printf') && !/[/\\]/.test(arg)) continue;
    if (arg === 'SUBST') continue;
    if (!pathAllowed(arg)) return `path not allowed: ${arg}`;
  }
  return null;
}

function verifyStatement(statement, loopVar, single) {
  let text = statement.replace(/2>&1/g, ' ');
  let at;
  while ((at = text.indexOf('$(')) >= 0) {
    const close = text.indexOf(')', at);
    if (close < 0) return `unterminated $( ): ${statement}`;
    const inner = text.slice(at + 2, close);
    if (inner.includes('(')) return `nested $( ): ${statement}`;
    const reason = verifySubstitution(inner, loopVar);
    if (reason) return reason;
    text = `${text.slice(0, at)}SUBST${text.slice(close + 1)}`;
  }
  if (/`/.test(text)) return `backtick: ${statement}`;
  if (/~/.test(text)) return `home path: ${statement}`;
  if (/</.test(text)) return `input redirect: ${statement}`;
  const withoutStatus = text.replace(/\$\?/g, '');
  for (const m of withoutStatus.matchAll(/\$\{?([A-Za-z_]\w*)\}?/g)) if (m[1] !== loopVar) return `variable not allowed: ${m[0]}`;
  if (withoutStatus.replace(/\$\{?[A-Za-z_]\w*\}?/g, '').includes('$')) return `variable not allowed: ${statement}`;
  if (/\|\|/.test(text)) return `|| is not allowed: ${statement}`;
  if (/&/.test(text)) return `background or unknown & operator: ${statement}`;
  const parts = text.split('|').map((p) => p.trim());
  const failures = [];
  for (const part of parts) {
    if (parts.length > 1) {
      const head = (tokenize(part)[0] || '').replace(/\.exe$/i, '').toLowerCase();
      if (!READ_ONLY.has(head)) failures.push(`pipes are allowed only between read-only commands: ${part}`);
    }
    const reason = verifySimple(part, loopVar, single && parts.length === 1);
    if (reason) failures.push(reason);
  }
  return failures.length ? failures.join(' | ') : null;
}

// Verifies the full command text against the approval rule. Returns null if allowed, else the reason.
function verifyShell(input) {
  const parsed = parseCommand(input);
  if (parsed.reason) return parsed.reason;
  const failures = [...parsed.problems];
  const text = parsed.lines.join('\n');
  if (/[%]\w+%/.test(text)) failures.push('uses a Windows environment variable');
  const statements = [];
  for (const line of parsed.lines) {
    const segments = splitSegments(line);
    if (!segments) failures.push(`unbalanced quotes: ${line}`);
    else statements.push(...segments);
  }
  const single = statements.length === 1 && !/[>|]/.test(text);
  let loopVar = null;
  let awaitingDo = false;
  for (const statement of statements) {
    if (/^for\s/.test(statement)) {
      if (loopVar) failures.push('nested for loops are not allowed');
      const m = statement.match(/^for\s+([A-Za-z_]\w*)\s+in\s+(\S+)$/);
      if (!m) {
        failures.push(`for loop must be: for <var> in <glob>: ${statement}`);
        loopVar = loopVar || '__invalid__';
      } else {
        const glob = unquote(m[2]);
        if (isAbsolute(glob) || !pathAllowed(glob) || /\$/.test(glob)) failures.push(`glob not allowed: ${glob}`);
        loopVar = m[1];
      }
      awaitingDo = true;
      continue;
    }
    if (statement === 'done') {
      if (!loopVar || awaitingDo) failures.push('done without a loop body');
      loopVar = null;
      awaitingDo = false;
      continue;
    }
    let body = statement;
    if (/^do(\s|$)/.test(statement)) {
      if (!awaitingDo) failures.push(`unexpected do: ${statement}`);
      awaitingDo = false;
      body = statement.replace(/^do\s*/, '');
      if (!body) continue;
    } else if (awaitingDo) {
      failures.push(`for loop must be followed by do: ${statement}`);
      awaitingDo = false;
    }
    const reason = verifyStatement(body, loopVar, single);
    if (reason) failures.push(reason);
  }
  if (loopVar) failures.push('for loop is not closed, so the text is incomplete');
  return failures.length ? failures.join(' || ') : null;
}

// Returns {kind:'none'} | {kind:'allow', ...} | {kind:'stop', reason}
function classify(screen) {
  const lines = normLines(screen);
  const selected = lastIndex(lines, (l) => /^[❯›>]\s*\d+\.\s/.test(l));
  const plainYesNo = lines.some((l) => /^\d+\.\s+(Yes|No)\b/.test(l));
  const flat = lines.join(' ');
  const promptSignals = /Enter to confirm|Enter to select|Press Enter to continue|Esc to (cancel|exit|go back)|\(y\/n\)|\[y\/N\]|\[Y\/n\]/i.test(flat);
  // Devin CLI's folder-trust question has its own shape: the question line, then "❭ 1 Yes, trust <folder>" and "· 2 No, exit".
  const devinTrust = lines.some((l) => /^Do you trust the authors of this directory\?/.test(l));
  // Devin CLI's file-write approval: a "● Writing <file>" heading and a menu whose first choice is "❭ 1 Yes  (Approve once)".
  const devinMenu = lines.some((l) => /^[❭·]\s*\d\s+(Yes|No)\b/.test(l));
  const devinOnce = lines.some((l) => /^❭\s*1\s+Yes\s+\(Approve once\)$/.test(l));
  if (selected < 0 && !plainYesNo && !promptSignals && !devinTrust && !devinMenu) return { kind: 'none' };

  const stop = (reason) => ({ kind: 'stop', reason });

  // (a) Trusting a folder under e2e-work.
  if (lastIndex(lines, (l) => /^Do you want to /.test(l)) < 0 && /trust the files|trust this folder|project you created or one you trust|trust the authors of this directory/i.test(flat)) {
    const compact = screen.replace(/[\s│┃║╭╮╰╯┌┐└┘─━═]/g, '').toLowerCase();
    // GitHub Copilot CLI's trust dialog names no folder at all. It is accepted only when nothing on screen names another
    // folder and the harness itself started that AI in a folder under e2e-work (setCliFolder), so the question can only be
    // about that folder.
    const nameless = /Confirm folder trust/.test(flat) && !/[a-zA-Z]:[\\/]/.test(flat) && Boolean(cliFolder)
      && normFolder(cliFolder).startsWith(`${normFolder(WORK)}/`);
    if (!compact.includes(WORK.replace(/\s/g, '').toLowerCase()) && !nameless) return stop('trust prompt for a folder not under e2e-work');
    const marked = lines.find((l) => /^[❯›>❭]\s*(\d+\.?\s*)?(Yes|No)\b/i.test(l));
    if (marked && /^[❯›>❭]\s*(\d+\.?\s*)?Yes\b/i.test(marked)) return { kind: 'allow', what: 'trust', sig: 'trust' };
    if (marked && lines.some((l) => /^(\d+\.\s*)?Yes, I trust this folder/i.test(l))) {
      return { kind: 'allow', what: 'trust (move selection from No to Yes)', sig: 'trust-move', keys: ['ArrowDown'] };
    }
    return stop('trust prompt without a Yes option that can be selected');
  }

  // (a2) Devin CLI's write approval: only a plain relative file, with its first choice highlighted. Never choice 2 or 3.
  if (devinMenu && !devinTrust) {
    if (!devinOnce) return stop('Devin menu without a highlighted "Yes (Approve once)"');
    const head = lines.map((l) => l.match(/^● Writing\s+(\S+)$/)).filter(Boolean).pop();
    if (!head) return stop('Devin approval without a "Writing <file>" heading');
    if (/^[a-zA-Z]:|^[\\/]/.test(head[1]) || !pathAllowed(head[1])) return stop(`Devin write outside the scratch folder: ${head[1]}`);
    return { kind: 'allow', what: `write ${head[1]}`, sig: `devin write ${head[1]}` };
  }

  // (b) Permission prompts.
  const q = lastIndex(lines, (l) => /^Do you want to /.test(l));
  if (q < 0 || selected < 0) return stop('menu that is not a recognized approval prompt');
  if (!/^[❯›>]\s*1\.\s*Yes$/.test(lines[selected])) return stop(`option 1 is not a plain Yes: ${lines[selected]}`);
  let question = lines[q];
  for (let i = q + 1; i < Math.min(q + 4, lines.length) && !question.includes('?'); i += 1) question = `${question}${question.endsWith('-') ? '' : ' '}${lines[i]}`.trim();

  const fileQ = question.match(/^Do you want to (create|make this edit to|overwrite|write to|edit)\s+(.+?)\?$/);
  if (fileQ) {
    if (!pathAllowed(fileQ[2])) return stop(`file prompt outside e2e-work: ${fileQ[2]}`);
    return { kind: 'allow', what: `${fileQ[1]} ${fileQ[2]}`, sig: question };
  }
  if (/^Do you want to proceed\?/.test(question)) {
    const before = lines.slice(0, q);
    const bashAt = (() => { for (let i = before.length - 1; i >= 0; i -= 1) if (/^(Bash|PowerShell)( command)?$/i.test(before[i])) return i; return -1; })();
    if (bashAt >= 0) {
      const after = before.slice(bashAt + 1);
      const rules = after.reduce((acc, l, i) => (/^╌+$/.test(l) ? [...acc, i] : acc), []);
      if (rules.length >= 2) {
        // This CLI shows the exact command between two dashed rules, so both rules prove it is complete.
        const raw = screen.split('\n');
        const cols = Math.max(...raw.map((l) => l.length));
        const offset = bashAt + 1;
        const rows = [];
        for (let i = rules[0] + 1; i < rules[rules.length - 1]; i += 1) {
          if (after[i]) rows.push({ text: after[i], nearFull: (raw[offset + i] || '').trimEnd().length >= cols - 3 });
        }
        const chars = rows.reduce((n, r) => n + r.text.length, 0);
        const size = `${rows.length} rows, ${chars} chars`;
        const first = rows.length ? rows[0].text.slice(0, 120) : '';
        const reason = verifyShell(rows);
        if (reason) return stop(`${reason} [${size}; first row: ${first}]`);
        const digest = crypto.createHash('sha256').update(rows.map((r) => r.text).join('\n')).digest('hex').slice(0, 16);
        return { kind: 'allow', what: `shell [${size}] ${first}`, sig: `shell ${digest}` };
      }
      const cmdLines = after.filter(Boolean);
      const candidate = cmdLines.join(' ');
      if (/[|&;<>`$%~]/.test(candidate)) return stop(`shell prompt with metacharacters: ${candidate}`);
      const tokens = candidate.split(/\s+/);
      const head = tokens[0].replace(/\.exe$/i, '').toLowerCase();
      if (head === 'python') {
        if (!tokens[1] || tokens[1].startsWith('-') || !/\.py$/.test(tokens[1]) || !pathAllowed(tokens[1])) return stop(`python target not allowed: ${candidate}`);
        for (const t of tokens.slice(2)) {
          if (!/[./\\]/.test(t)) break; // description words follow the command
          if (t.startsWith('-') || !pathAllowed(t)) return stop(`python argument not allowed: ${candidate}`);
        }
        return { kind: 'allow', what: `shell ${candidate}`, sig: `shell ${candidate}` };
      }
      if (BASIC_COMMANDS.has(head)) {
        for (const t of tokens.slice(1)) {
          if (t.startsWith('-')) continue;
          if (/[./\\]/.test(t) && !pathAllowed(t)) return stop(`file command outside e2e-work: ${candidate}`);
        }
        return { kind: 'allow', what: `shell ${candidate}`, sig: `shell ${candidate}` };
      }
      return stop(`command not allowed: ${candidate}`);
    }
    const readAt = (() => { for (let i = before.length - 1; i >= 0; i -= 1) if (/^Read (file|files?)\b/i.test(before[i])) return i; return -1; })();
    if (readAt >= 0) {
      const target = before.slice(readAt + 1).find(Boolean);
      if (target && pathAllowed(target)) return { kind: 'allow', what: `read ${target}`, sig: `read ${target}` };
    }
    return stop(`unrecognized proceed prompt: ${flat.slice(-400)}`);
  }
  return stop(`unrecognized question: ${question}`);
}

async function answerYes(page, keys) {
  await page.locator('.xterm-helper-textarea').focus();
  for (const key of keys || ['Enter']) await page.keyboard.press(key);
}

// Auto or bypass mode means the CLI handles approvals itself: never continue. One opt-in exists for the real-tool
// paste-flow check (real-paste.js, set by the user's 2026-11-19 decision): Claude Code now starts in auto mode by default on
// every computer, with no flag from this app, so that start alone is not stopped. Nothing else changes in the checker.
function modeViolation(screen) {
  if (process.env.ALLOW_CLI_DEFAULT_AUTO_MODE === '1') return null;
  return normLines(screen).find((l) => /\b(auto|bypass\w*)\s+(mode|permissions)\b.*\bon\b/i.test(l)) || null;
}

function logScreen(tag, screen) {
  fs.appendFileSync(path.join(LOG_DIR, `${tag}.screens.log`), `\n----- ${new Date().toISOString()} -----\n${redact(screen)}\n`);
}

async function stopRun(page, reason, screen) {
  note('STOP', reason);
  if (screen) note('STOP-SCREEN', screen);
  state.stopped = { reason: redact(reason), screen: screen ? redact(screen) : '' };
  saveState(state);
  throw new StopRun(reason, screen);
}

// Answer allowed prompts until doneCheck says the CLI is finished.
async function driveCli(page, tag, doneCheck, opts = {}) {
  const started = Date.now();
  const timeout = opts.timeoutMs || CLI_TIMEOUT_MS;
  let lastScreen = '';
  let lastChange = Date.now();
  let answeredSig = null;
  let answeredAt = 0;
  for (;;) {
    if (Date.now() - started > timeout) {
      const scr = await readScreen(page);
      logScreen(tag, scr);
      await stopRun(page, `CLI run exceeded ${timeout / 1000}s (${tag})`, scr);
    }
    assertNoProjectKey();
    const scr = await readScreen(page);
    if (scr !== lastScreen) { lastScreen = scr; lastChange = Date.now(); logScreen(tag, scr); }
    if (modeViolation(scr)) await stopRun(page, `CLI is in a mode that handles approvals itself (${tag}): ${modeViolation(scr)}`, scr);
    const c = classify(scr);
    if (c.kind === 'stop') { await stopRun(page, `prompt not allowed (${tag}): ${c.reason}`, scr); }
    if (c.kind === 'allow') {
      if (c.sig === answeredSig && Date.now() - answeredAt < 8000) { await sleep(500); continue; }
      state.prompts.push({ tag, what: redact(c.what), when: new Date().toISOString() });
      saveState(state);
      note('APPROVE', `${tag}: ${c.what}`);
      await answerYes(page, c.keys);
      answeredSig = c.sig;
      answeredAt = Date.now();
      await sleep(800);
      continue;
    }
    const idleMs = Date.now() - lastChange;
    const busy = /esc to interrupt/i.test(scr.replace(BOX_RE, ' '));
    if (await doneCheck({ idleMs, busy, screen: scr, elapsedMs: Date.now() - started })) return;
    await sleep(700);
  }
}

// Wait until the CLI shows its input line (handles the trust prompt first).
async function waitReady(page, tag) {
  const started = Date.now();
  let readySince = 0;
  let lastScreen = '';
  for (;;) {
    if (Date.now() - started > 90000) {
      const scr = await readScreen(page);
      logScreen(tag, scr);
      await stopRun(page, `CLI never became ready (${tag})`, scr);
    }
    const scr = await readScreen(page);
    if (scr !== lastScreen) { lastScreen = scr; logScreen(tag, scr); readySince = 0; }
    const c = classify(scr);
    if (c.kind === 'stop') await stopRun(page, `prompt not allowed at start (${tag}): ${c.reason}`, scr);
    if (c.kind === 'allow') {
      state.prompts.push({ tag, what: redact(c.what), when: new Date().toISOString() });
      saveState(state);
      note('APPROVE', `${tag}: ${c.what}`);
      await answerYes(page, c.keys);
      await sleep(1500);
      readySince = 0;
      continue;
    }
    const lines = normLines(scr);
    if (modeViolation(scr)) await stopRun(page, `CLI is in a mode that handles approvals itself (${tag}): ${modeViolation(scr)}`, scr);
    const ready = lines.some((l) => /^[>❯❭](\s|$)/.test(l) || /\? for shortcuts/.test(l) || /manual mode on/.test(l));
    if (ready) {
      if (!readySince) readySince = Date.now();
      if (Date.now() - readySince > 2000) return;
    } else {
      readySince = 0;
    }
    await sleep(400);
  }
}

function countSession(label) {
  state.sessions.push({ label, when: new Date().toISOString() });
  saveState(state);
  note('session', `#${state.sessions.length}: ${label}`);
  if (state.sessions.length > MAX_SESSIONS) throw new Error('CLI session budget exceeded');
}

async function clickAndWait(page, selector, routeSuffix) {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === routeSuffix, { timeout: 45000 }),
    page.locator(selector).click(),
  ]);
  return resp;
}

async function apiState(step) {
  const url = `http://127.0.0.1:${state.port}/api/state${step ? `?step=${step}` : ''}`;
  const res = await fetch(url, { headers: { 'X-Eval-Token': state.token } });
  return res.json();
}

async function waitFor(fn, ms, label) {
  const start = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - start > ms) throw new Error(`timed out waiting for ${label}`);
    await sleep(400);
  }
}

function listTree(dir) {
  const out = [];
  const walk = (d, rel) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const r = rel ? `${rel}/${e.name}` : e.name;
      if (e.isDirectory()) walk(path.join(d, e.name), r); else out.push(r);
    }
  };
  walk(dir, '');
  return out.sort();
}

async function redactDomEmails(page) {
  await page.evaluate((src) => {
    const re = new RegExp(src, 'g');
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (re.test(node.nodeValue)) { node.nodeValue = node.nodeValue.replace(re, '[redacted]'); }
      re.lastIndex = 0;
    }
  }, EMAIL_RE.source);
}

async function shot(page, name) {
  await redactDomEmails(page);
  const file = path.join(SHOTS, name);
  await page.screenshot({ path: file });
  note('screenshot', file);
  return file;
}

// The checker the harness trusts, independent of the app: the project's own check.py on the Script track. On the
// promptfoo track there is no check.py, so the Northwind reference checker stands in (tightened the same way the
// stand-in tightens the config once the config says so), which also cross-checks promptfoo against plain Python.
const TIGHTEN_FIND = "return True, 'found \"Blocker:\" and \"Need:\"'";
function independentChecker() {
  if (!PF) return path.join(PROJECT, 'check.py');
  const reference = fs.readFileSync(path.join(ROOT, 'tests', 'golden', 'reference-check.py'), 'utf8');
  const configPath = path.join(PROJECT, 'promptfooconfig.yaml');
  const tightened = fs.existsSync(configPath) && fs.readFileSync(configPath, 'utf8').includes('test data');
  const text = tightened
    ? reference.replace(TIGHTEN_FIND, "if 'test data' not in text.split('Blocker:', 1)[1].splitlines()[0]:\n        return False, 'blocker does not mention test data'\n    " + TIGHTEN_FIND)
    : reference;
  const target = path.join(WORK, 'pf-independent-check.py');
  fs.writeFileSync(target, text);
  return target;
}

function runCheckerIndependently(args) {
  const out = execFileSync(PYTHON, [independentChecker(), ...args], { cwd: PROJECT, encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1' }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  return out;
}

function parseCheckerText(text) {
  const files = {};
  let current = null;
  for (const line of text.split(/\r?\n/)) {
    const h = line.match(/^== (.+)$/);
    if (h) { current = h[1] === 'Pass rate per criterion' ? null : path.basename(h[1].replace(/\\/g, '/')).toLowerCase(); if (current) files[current] = {}; continue; }
    const m = line.match(/^(C\d+)\s+(PASS|FAIL|NOT CHECKED)\s/);
    if (m && current) files[current][m[1]] = { PASS: 'P', FAIL: 'F', 'NOT CHECKED': 'NC' }[m[2]];
  }
  return files;
}

function independentRun(args) {
  let stdout;
  try {
    stdout = runCheckerIndependently(args);
  } catch (e) {
    if (e.status === 0 || e.status === 1) stdout = e.stdout.toString();
    else throw new Error(`check.py failed: ${e.status} ${e.stderr}`);
  }
  return parseCheckerText(stdout);
}

function independentRunIn(cwd, args) {
  let stdout;
  const checker = cwd === PROJECT ? independentChecker() : 'check.py'; // other folders (the demo) always hold a check.py
  try {
    stdout = execFileSync(PYTHON, [checker, ...args], { cwd, encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1' }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    if (e.status === 0 || e.status === 1) stdout = e.stdout.toString();
    else throw new Error(`check.py failed: ${e.status} ${e.stderr}`);
  }
  return parseCheckerText(stdout);
}

module.exports = {
  ROOT, WORK, HOME, PROJECT, STATE_FILE, PYTHON, PYZ, CLI_COMMAND, MODEL, STANDIN, TRACK, PF, independentChecker, CLI_TIMEOUT_MS, SHOTS, LOG_DIR, SERVER_LOG, demoArgs, unlockDemo,
  state, saveState, loadState, note, assertion, violation, redact, sleep, StopRun,
  startServer, killServer, pidAlive, filteredEnv,
  openBrowser, enterPart, readScreen, classify, driveCli, waitReady, answerYes, countSession, clickAndWait,
  apiState, waitFor, listTree, shot, logScreen, stopRun, markPredictLocked,
  assertNoProjectKey, assertProgressClean, sealedKeyPath, projectKeyPath, workKeyPath, keyWorkKeyPath, answerKeyLocations, keyLines,
  softAssertion, watchStream, verifyShell, setCliFolder, independentRun, independentRunIn, parseCheckerText, runCheckerIndependently, normLines,
};
