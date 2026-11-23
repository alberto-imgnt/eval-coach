// Runs the complete stand-in sequence, one stage per process, and prints the totals.
// Usage: node run-all.js [--fresh] [--from <stage>] [--only <stage>] [--track script|promptfoo] [--both]
//   --fresh  build a private archive of the current app, delete the stand-in home, project and state, then run everything
//   --track  which track to run (default script); the promptfoo pass uses its own home, project, state and logs
//   --both   run the Script pass and then the promptfoo pass
// Always E2E_PROFILE=standin: these stages use only the stand-in fake_cli.py, never a real CLI.
// The promptfoo pass runs the REAL pinned promptfoo from the spike's private Node and npm cache, which are
// linked (junctions, never copied or deleted) into the stand-in home as runtime\node and npm-cache.
if (process.platform !== 'win32') { console.log('SKIP: the stand-in harness runs on Windows only.'); process.exit(0); }
const { spawnSync, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const WORK = path.resolve(__dirname, '..');
const ROOT = path.resolve(WORK, '..');
const SPIKE = path.join(ROOT, 'spikes', 'phase0-preflight');
const PYTHON = path.join(SPIKE, 'runtime', 'python-embed-3.13.17-nopth', 'python.exe');
const PYZ = process.env.E2E_PYZ || path.join(WORK, 'eval-coach-e2e.pyz');

const SCRIPT_SEQUENCE = ['mission', 'setup', 'hook', 'several-runs', 'generate', 'rules', 'restart', 'build', 'trust',
  'fixtures', 'readback', 'predict', 'key', 'surprise', 'run', 'fix', 'baseline-why', 'baseline', 'part1', 'part2', 'migrate', 'model', 'quit'];
const PF_SEQUENCE = ['mission', 'setup', 'hook', 'several-runs', 'generate', 'rules', 'restart', 'build', 'trust',
  'fixtures', 'fixtures-config', 'readback', 'predict', 'key', 'surprise', 'run', 'fix', 'baseline-why', 'baseline', 'live', 'part1', 'part2', 'migrate', 'model', 'quit'];

const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };

function linkRuntime(home) {
  fs.mkdirSync(path.join(home, 'runtime'), { recursive: true });
  const links = [[path.join(home, 'runtime', 'node'), path.join(SPIKE, 'runtime', 'node-v26.13.0-win-x64')], [path.join(home, 'npm-cache'), path.join(SPIKE, 'npm-cache')]];
  for (const [link, target] of links) {
    if (!fs.existsSync(target)) throw new Error(`the spike's private runtime is missing: ${target}`);
    if (!fs.existsSync(link)) fs.symlinkSync(target, link, 'junction');
  }
}

// A junction is removed on its own, never recursively, so the spike's files are never touched.
function unlinkRuntime(home) {
  for (const link of [path.join(home, 'runtime', 'node'), path.join(home, 'npm-cache')]) {
    let st = null;
    try { st = fs.lstatSync(link); } catch { continue; }
    if (st.isSymbolicLink()) fs.rmdirSync(link);
  }
}

function runPass(trackName, fresh) {
  const pf = trackName === 'promptfoo';
  const suffix = pf ? '-standin-pf' : '-standin';
  const homeName = pf ? 'standin-home-pf' : 'standin-home';
  const projectName = pf ? 'standin-project-pf' : 'standin-project';
  const STATE = path.join(WORK, `harness-state${suffix}.json`);
  const LOGS = path.join(WORK, `logs${suffix}`);
  const env = { ...process.env, E2E_PROFILE: 'standin', E2E_PYZ: PYZ, E2E_TRACK: trackName };
  const home = path.join(WORK, homeName);

  if (fresh) {
    unlinkRuntime(home);
    for (const p of [homeName, projectName, `logs${suffix}`, `screenshots${suffix}`, 'migrate-tmp', 'model-tmp']) fs.rmSync(path.join(WORK, p), { recursive: true, force: true });
    for (const f of [`harness-state${suffix}.json`, 'fake-cli-events.jsonl', 'fake-cli-mode.txt']) fs.rmSync(path.join(WORK, f), { force: true });
  }
  if (pf) linkRuntime(home);

  const sequence = pf ? PF_SEQUENCE : SCRIPT_SEQUENCE;
  let stages = sequence;
  if (opt('--only')) stages = [opt('--only')];
  else if (opt('--from')) stages = sequence.slice(sequence.indexOf(opt('--from')));

  console.log(`== ${trackName} track ==`);
  fs.mkdirSync(LOGS, { recursive: true });
  let failedStage = null;
  try {
    for (const stage of stages) {
      const log = path.join(LOGS, `stage-${stage}.out`);
      const fd = fs.openSync(log, 'w');
      const started = Date.now();
      const res = spawnSync(process.execPath, [path.join(__dirname, 'run.js'), stage], { env, cwd: ROOT, stdio: ['ignore', fd, fd] });
      fs.closeSync(fd);
      const text = fs.readFileSync(log, 'utf8');
      const fails = (text.match(/ASSERT-FAIL/g) || []).length;
      console.log(`${res.status === 0 ? 'ok  ' : 'FAIL'} ${stage.padEnd(15)} exit ${res.status} ${(Date.now() - started) / 1000}s ${fails ? `${fails} failed checks` : ''}`);
      if (res.status !== 0) { failedStage = stage; break; }
    }
  } finally {
    if (pf) unlinkRuntime(home);
  }

  const s = JSON.parse(fs.readFileSync(STATE, 'utf8'));
  const failed = s.assertions.filter((a) => !a.ok);
  console.log(`checks: ${s.assertions.length - failed.length} passed, ${failed.length} failed; violations: ${s.violations.length}; CLI sessions: ${s.sessions.length}`);
  for (const f of failed) console.log(`  FAILED: ${f.name} :: ${f.detail}`);
  for (const v of s.violations) console.log(`  VIOLATION: ${v}`);
  return !(failedStage || failed.length || s.violations.length);
}

const fresh = args.includes('--fresh');
if (fresh) execFileSync(PYTHON, [path.join(__dirname, 'build-private-pyz.py')], { stdio: 'inherit' });
const tracks = args.includes('--both') ? ['script', 'promptfoo'] : [opt('--track') === 'promptfoo' ? 'promptfoo' : 'script'];
let allOk = true;
for (const t of tracks) {
  if (!runPass(t, fresh)) { allOk = false; if (tracks.length > 1) console.log(`the ${t} pass failed`); }
}
process.exit(allOk ? 0 : 1);
