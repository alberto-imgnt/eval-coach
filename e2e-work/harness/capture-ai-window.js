// Captures one masked screenshot of a real AI window, started from this app's own working test page.
// Usage: node e2e-work/harness/capture-ai-window.js <launch name> <output png>
// Nothing is sent to the AI: the window is started, looked at, and stopped. Account names, e-mail addresses and the
// user name are painted over with block characters in the page before the picture is taken, and the picture is
// refused if any of them is still in the window text. The words to paint over come from CAPTURE_MASKS ("|" separated,
// kept out of the repository); without it the script refuses to run. Set CAPTURE_TRUST=1 to send one single-use Yes to the
// folder-trust question of the scratch folder (only when the highlighted choice is a Yes); use it only with the
// user's approval. Real-CLI use needs the user's approval (AGENTS.md).
const { chromium } = require('../../tests/frontend/.tmp/node_modules/@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const tool = process.argv[2];
const out = path.resolve(process.argv[3]);
const HOME = `C:\\eval-coach-capture\\${tool}`;
// Personal text to paint over comes from the local environment, never from tracked source: names, account and
// organization words, separated by "|". Without it nothing is captured.
const MASKS = (process.env.CAPTURE_MASKS || '').split('|').map((s) => s.trim()).filter(Boolean);
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const EMAIL = '[\\w.+-]+@[\\w-]+(?:\\.[\\w-]+)+';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  if (!MASKS.length) {
    throw new Error('CAPTURE_MASKS is not set: list the account names and personal words to paint over, separated by "|". Nothing was started.');
  }
  fs.rmSync(HOME, { recursive: true, force: true });
  fs.mkdirSync(HOME, { recursive: true });
  // Choosing the tool would start a real background request. Without a one-shot mode in the scratch home's
  // recipes, the only run is the visible one this script starts from the working test page.
  const bundled = JSON.parse(fs.readFileSync(path.join(ROOT, 'app', 'eval_coach', 'content', 'cli-recipes.json'), 'utf8'));
  for (const recipe of bundled.recipes) delete recipe.headless;
  fs.writeFileSync(path.join(HOME, 'cli-recipes.json'), JSON.stringify(bundled, null, 2));
  // The window is captured as a participant would see it, so the editor this script runs in must not show through.
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !/^(VSCODE|TERM_PROGRAM|GIT_ASKPASS|ELECTRON)/i.test(k)));
  const server = spawn('python', ['-m', 'eval_coach', '--no-browser', '--home', HOME], { cwd: path.join(ROOT, 'app'), windowsHide: true, env });
  const url = await new Promise((resolve, reject) => {
    let buf = '';
    server.stdout.on('data', (d) => {
      buf += d.toString();
      const m = buf.match(/http:\/\/127\.0\.0\.1:\d+\/\?t=\S+/);
      if (m) resolve(m[0]);
    });
    server.on('exit', () => reject(new Error('server exited')));
    setTimeout(() => reject(new Error('no url')), 20000);
  });
  const origin = new URL(url).origin;
  const token = new URL(url).searchParams.get('t');
  const post = async (p, body) => {
    const r = await fetch(origin + p, { method: 'POST', headers: { 'X-Eval-Token': token, 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    return r.json();
  };
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    const chosen = await post('/api/preflight/cli', { cli_command: tool });
    const cli = chosen.state.preflight.items.find((i) => i.id === 'cli');
    if (cli.status !== 'passed') throw new Error(`the command ${tool} was not found`);
    await post('/api/preflight/check', {});
    for (let i = 0; i < 40; i += 1) {
      const s = await (await fetch(origin + '/api/state', { headers: { 'X-Eval-Token': token } })).json();
      if (!s.preflight.job) break;
      await sleep(500);
    }
    await page.goto(url);
    for (let i = 0; i < 40; i += 1) {
      if (await page.locator('#pf-item-working_test').count()) break;
      if ((await page.locator('#wizard-next').getAttribute('aria-disabled')) !== 'true') await page.locator('#wizard-next').click();
      await sleep(500);
    }
    const stable = async () => {
      let last = '';
      let stableSince = Date.now();
      for (let i = 0; i < 80; i += 1) {
        await sleep(500);
        const text = await page.locator('#term-host .xterm-rows').innerText();
        if (text !== last) {
          last = text;
          stableSince = Date.now();
        } else if (Date.now() - stableSince > 5000 && text.trim()) return text;
      }
      return last;
    };
    await page.locator('#cli-start').click();
    let first = await stable();
    // The folder-trust question for this scratch folder: one single-use Yes, only when the highlighted choice is a Yes.
    if (process.env.CAPTURE_TRUST === '1' && /trust/i.test(first)) {
      const selected = (text) => (text.split('\n').find((l) => /^[\s│]*[>❯❭]/.test(l)) || '').trim();
      await page.locator('#term-host').click();
      if (!/yes/i.test(selected(first))) {
        await page.keyboard.press('ArrowDown');
        await sleep(1500);
        first = await page.locator('#term-host .xterm-rows').innerText();
      }
      const row = selected(first);
      if (!/yes/i.test(row)) throw new Error(`the highlighted choice is not a Yes, nothing was sent: ${row}`);
      console.log(`sending one Enter on: ${row.replace(/\s+/g, ' ')}`);
      await page.keyboard.press('Enter');
      await stable();
    }
    // Paint over anything personal, row by row, across the styled pieces of each row.
    const masked = await page.evaluate(({ masks, email }) => {
      const rows = Array.from(document.querySelectorAll('#term-host .xterm-rows > div'));
      const re = new RegExp(`${email}|${masks.map((m) => m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')}`, 'gi');
      let count = 0;
      for (const row of rows) {
        const nodes = [];
        const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) nodes.push(walker.currentNode);
        const text = nodes.map((n) => n.nodeValue).join('');
        for (const m of text.matchAll(re)) {
          count += 1;
          let pos = 0;
          for (const node of nodes) {
            const len = node.nodeValue.length;
            const from = Math.max(m.index, pos);
            const to = Math.min(m.index + m[0].length, pos + len);
            if (from < to) {
              const chars = node.nodeValue.split('');
              for (let k = from - pos; k < to - pos; k += 1) chars[k] = '█';
              node.nodeValue = chars.join('');
            }
            pos += len;
          }
        }
      }
      return count;
    }, { masks: MASKS, email: EMAIL });
    const after = await page.locator('#term-host .xterm-rows').innerText();
    const residue = new RegExp(`${EMAIL}|${MASKS.map(escapeRe).join('|')}`, 'i').test(after);
    console.log(`masked ${masked} piece(s); personal text left: ${residue}`);
    console.log('--- window text (masked) ---');
    console.log(after.split('\n').map((l) => l.replace(/\s+$/, '')).filter((l) => l.length).join('\n'));
    if (!residue) {
      fs.mkdirSync(path.dirname(out), { recursive: true });
      await page.locator('#term-host').screenshot({ path: out });
      console.log(`saved ${out}`);
    }
    await page.locator('#cli-stop').click();
  } finally {
    await browser.close();
    server.kill();
    await sleep(500);
    fs.rmSync(HOME, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
