// Records which CLI/console processes exist before the run, or compares at the end.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const WORK = 'C:\\Projects\\Improving\\eval-coach\\e2e-work';
const FILE = path.join(WORK, 'process-baseline.json');
const NAMES = ['claude.exe', 'conhost.exe', 'openconsole.exe'];

function snapshot() {
  const out = execFileSync('tasklist', ['/FO', 'CSV', '/NH'], { encoding: 'utf8' });
  const rows = out.split(/\r?\n/).filter(Boolean).map((l) => l.split('","').map((c) => c.replace(/"/g, '')));
  return rows.filter((r) => NAMES.includes(r[0].toLowerCase())).map((r) => ({ name: r[0], pid: r[1] }));
}

const mode = process.argv[2] || 'record';
if (mode === 'record') {
  fs.writeFileSync(FILE, JSON.stringify(snapshot(), null, 2));
  console.log('recorded baseline');
} else {
  const base = new Set(JSON.parse(fs.readFileSync(FILE, 'utf8')).map((p) => `${p.name}:${p.pid}`));
  const now = snapshot();
  const added = now.filter((p) => !base.has(`${p.name}:${p.pid}`));
  console.log(JSON.stringify({ baseline: base.size, now: now.length, new: added }, null, 2));
}
