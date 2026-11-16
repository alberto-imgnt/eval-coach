#!/usr/bin/env node
// promptfoo `exec:` provider that runs the attendee's own agent CLI (Copilot, Claude Code or Devin),
// so no API key is needed. Usage in a config:
//   providers:
//     - id: 'exec: node ./agent-provider.js'
//       label: my-agent
//       config:
//         cli: copilot        # optional: copilot | claude | devin (default: AGENT_CLI env var, then auto-detect)
//         model: <model name> # optional: omit to use the CLI's default model
// The prompt is sent as one non-interactive request from an empty temp folder, so the agent
// cannot read test-cases.md or any other project file.
const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const prompt = process.argv[2];
let config = {};
try {
  config = (JSON.parse(process.argv[3] || '{}').config) || {};
} catch (e) {
  // no usable options: fall back to defaults
}

function onPath(cmd) {
  const probe = spawnSync(process.platform === 'win32' ? 'where' : 'which', [cmd], { encoding: 'utf8' });
  return probe.status === 0;
}

const cli = config.cli || process.env.AGENT_CLI || ['copilot', 'claude', 'devin'].find(onPath);
if (!cli) {
  console.error('No agent CLI found. Install copilot, claude or devin, or set AGENT_CLI.');
  process.exit(1);
}
const model = config.model || process.env.AGENT_MODEL;

// Each CLI is called in its non-interactive "print the answer and exit" mode.
const builders = {
  copilot: () => ({ args: ['-p', prompt, '-s', ...(model ? ['--model', model] : [])], input: undefined }),
  claude: () => ({ args: ['-p', ...(model ? ['--model', model] : [])], input: prompt }),
  devin: () => ({
    args: ['-p', '--permission-mode', 'auto', ...(model ? ['--model', model] : []), '--', prompt],
    input: undefined,
  }),
};
if (!builders[cli]) {
  console.error(`Unsupported cli "${cli}". Use copilot, claude or devin.`);
  process.exit(1);
}

const { args, input } = builders[cli]();
const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-provider-'));
const result = spawnSync(cli, args, {
  encoding: 'utf8',
  cwd,
  input,
  // npm installs on Windows are .cmd shims, which need a shell to launch
  shell: process.platform === 'win32' && !onExe(cli),
});

function onExe(cmd) {
  const probe = spawnSync('where', [cmd], { encoding: 'utf8' });
  return probe.status === 0 && /\.exe\s*$/im.test(probe.stdout);
}

fs.rmSync(cwd, { recursive: true, force: true });
if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
if (result.status !== 0) {
  console.error(result.stderr || result.stdout);
  process.exit(result.status || 1);
}
process.stdout.write(result.stdout.trim());
