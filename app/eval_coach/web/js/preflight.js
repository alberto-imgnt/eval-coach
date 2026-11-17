// The preflight screen: every item's status, detail, next action and controls.
// All words come from the server (content/preflight.json).

import { h } from './dom.js';
import { aiWindowLink, renderAiWindowLesson } from './ai-window.js';
import { actionButton, textField } from './ui.js';

function statusWord(pf, status) {
  return pf.text[`status_${status}`] || status;
}

function jobBusy(pf) {
  return Boolean(pf.job && pf.job.running);
}

function itemById(pf, id) {
  return pf.items.find((i) => i.id === id);
}

function isPassed(pf, id) {
  const item = itemById(pf, id);
  return Boolean(item && item.status === 'passed');
}

// The quiet background test of the chosen AI is running. Nothing is shown of the AI itself while it does.
export function aiTesting(pf) {
  return Boolean(pf.working_test && pf.working_test.background && pf.working_test.background.state === 'running');
}

function renderProgress(pf) {
  const { job } = pf;
  if (!job || !job.running) return null;
  return h(
    'div',
    { class: 'pf-progress', key: 'progress', role: 'status', 'aria-live': 'polite' },
    h('span', { class: 'pf-progress-label' }, job.label, job.detail ? `: ${job.detail}` : ''),
    job.percent !== null && job.percent !== undefined
      ? h('progress', { max: 100, value: job.percent, class: 'pf-bar' })
      : h('progress', { class: 'pf-bar' }),
    job.progress_text ? h('span', { class: 'hint' }, job.progress_text) : null,
  );
}

function trackControls(ctx, pf) {
  const options = Object.entries(pf.track_options);
  return h(
    'fieldset',
    { class: 'field', key: 'track-field' },
    h('legend', { class: 'field-label' }, pf.text.track_legend),
    options.map(([value, option]) =>
      h(
        'label',
        { class: 'radio-card', key: `track-${value}` },
        h('input', {
          type: 'radio',
          name: 'track',
          value,
          disabled: Boolean(pf.track_locked),
          checked: ctx.draft('pf.track', pf.track) === value,
          onChange: () => {
            ctx.setDraft('pf.track', value);
            ctx.actions.pfTrack(value);
          },
        }),
        h('span', null, h('strong', null, option.label), h('span', { class: 'hint block' }, option.hint)),
      ),
    ),
    pf.track_note ? h('p', { class: 'callout callout-attn', key: 'track-note', id: 'pf-track-note' }, pf.track_note) : null,
    pf.track_locked_note ? h('p', { class: 'callout', key: 'track-locked', id: 'pf-track-locked' }, pf.track_locked_note) : null,
  );
}

function installControls(ctx, pf, item) {
  if (!item.install) return null;
  return h(
    'div',
    { class: 'row', key: 'install-row' },
    actionButton(ctx, {
      label: pf.text.install_button,
      id: `pf-install-${item.id}`,
      busyKey: `pf-install-${item.id}`,
      kind: 'primary',
      disabled: !item.install.available,
      onClick: () => ctx.actions.pfInstall(item),
    }),
  );
}

function fmt(template, vars) {
  return String(template || '').replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] !== undefined ? vars[k] : m));
}

// One way to install a tool: its plain-words description, an install button and the exact command behind a link.
function installOption(ctx, pf, tool, option, { primary }) {
  const t = pf.text;
  return h(
    'div',
    { class: 'pf-install-option', key: `opt-${option.id}`, id: `pf-install-option-${option.id}` },
    h('p', { class: 'hint', key: 'plain' }, option.plain),
    option.requirement
      ? h(
          'div',
          { class: 'callout callout-attn', key: 'req', id: `pf-requirement-${option.id}` },
          h('strong', null, `${t.ai_requirement_missing} ${option.requirement.name}. `),
          option.requirement.detail,
          h(
            'div',
            { class: 'row' },
            actionButton(ctx, {
              label: fmt(t.ai_install_requirement, { name: option.requirement.name }),
              id: `pf-install-${option.requirement.recipe}`,
              busyKey: `pf-recipe-${option.requirement.recipe}`,
              disabled: jobBusy(pf) || aiTesting(pf),
              onClick: () => ctx.actions.pfRecipe(option.requirement.recipe),
            }),
          ),
        )
      : null,
    h(
      'div',
      { class: 'row', key: 'buttons' },
      actionButton(ctx, {
        label: fmt(t.ai_install, { name: tool.name }),
        id: `pf-install-${option.id}`,
        busyKey: `pf-recipe-${option.id}`,
        kind: primary ? 'primary' : null,
        disabled: jobBusy(pf) || aiTesting(pf),
        onClick: () => ctx.actions.pfRecipe(option.id),
      }),
    ),
    h(
      'details',
      { class: 'pf-show-command', key: 'command', id: `pf-show-command-${option.id}` },
      h('summary', null, t.ai_show_command),
      h('span', { class: 'hint block' }, t.ai_exact),
      h('code', { class: 'pf-command', id: `pf-command-${option.id}` }, option.command),
    ),
  );
}

function missingToolCard(ctx, pf, tool) {
  const t = pf.text;
  return h(
    'li',
    { key: `tool-${tool.cli_command}`, class: 'pf-tool', id: `pf-tool-${tool.cli_command}` },
    h('div', { class: 'pf-tool-head' }, h('strong', null, tool.name), h('span', { class: 'pf-tag t-not_checked' }, t.ai_missing_tag)),
    installOption(ctx, pf, tool, tool.install, { primary: false }),
    tool.other_installs.length
      ? h(
          'details',
          { class: 'pf-other-way', key: 'other', id: `pf-other-way-${tool.cli_command}` },
          h('summary', null, t.ai_other_way),
          tool.other_installs.map((option) => installOption(ctx, pf, tool, option, { primary: false })),
        )
      : null,
  );
}

function cliControls(ctx, pf, item) {
  const t = pf.text;
  const tools = pf.cli.tools;
  const found = tools.filter((tool) => tool.found);
  const missing = tools.filter((tool) => !tool.found);
  const defaultChoice = (found.find((tool) => tool.chosen) || found.find((tool) => tool.preselect) || {}).cli_command || '';
  const selected = ctx.draft('pf.ai', defaultChoice);
  const chosen = tools.find((tool) => tool.chosen);
  return h(
    'div',
    { key: 'cli-controls' },
    h('p', { class: 'hint', key: 'intro' }, t.ai_intro),
    item.status === 'passed' && chosen ? h('p', { class: 'callout callout-good', id: 'pf-ai-chosen', key: 'chosen' }, fmt(t.ai_chosen, { name: chosen.name })) : null,
    pf.session.kind === 'recipe' ? h('p', { class: 'callout callout-attn', id: 'pf-ai-installing', key: 'installing', role: 'status' }, t.ai_installing) : null,
    aiTesting(pf)
      ? h(
          'p',
          { class: 'callout callout-attn pf-testing', id: 'pf-ai-testing', key: 'testing', role: 'status' },
          h('span', { class: 'pf-spinner', id: 'pf-ai-spinner', 'aria-hidden': 'true' }),
          h('span', null, t.ai_testing),
        )
      : null,
    found.length
      ? h(
          'fieldset',
          { class: 'field', key: 'found' },
          h('legend', { class: 'field-label' }, t.ai_found_legend),
          found.map((tool) =>
            h(
              'label',
              { class: 'radio-card', key: `found-${tool.cli_command}`, id: `pf-ai-card-${tool.cli_command}` },
              h('input', {
                type: 'radio',
                name: 'ai',
                value: tool.cli_command,
                id: `pf-ai-${tool.cli_command}`,
                checked: selected === tool.cli_command,
                onChange: () => {
                  ctx.setDraft('pf.ai', tool.cli_command);
                  ctx.rerender();
                },
              }),
              h('span', null, h('strong', null, tool.name), h('span', { class: 'hint block' }, t.ai_found_tag)),
            ),
          ),
          h(
            'div',
            { class: 'row', key: 'use-row' },
            actionButton(ctx, {
              label: t.ai_use,
              id: 'pf-use-ai',
              busyKey: 'pf-use-ai',
              kind: 'primary',
              disabled: !selected || aiTesting(pf),
              onClick: () => ctx.actions.pfUseAi(selected),
            }),
          ),
        )
      : null,
    missing.length
      ? h(
          'div',
          { class: 'pf-missing', key: 'missing' },
          h('h3', { class: 'pf-missing-title' }, t.ai_missing_legend),
          h('ul', { class: 'pf-tool-list', id: 'pf-tool-list' }, missing.map((tool) => missingToolCard(ctx, pf, tool))),
        )
      : null,
    pf.custom_ai
      ? h(
          'div',
          { class: 'pf-test-only', key: 'test-only', id: 'pf-test-only' },
          textField(ctx, { id: 'pf-cli-command', label: pf.test_only.cli_label, hint: pf.test_only.cli_hint, draftKey: 'pf.cli_command', value: pf.cli.command, mono: true }),
          h(
            'div',
            { class: 'row', key: 'cli-buttons' },
            actionButton(ctx, { label: pf.test_only.cli_check, id: 'pf-cli-check', busyKey: 'pf-cli-check', busyLabel: pf.test_only.cli_checking, disabled: aiTesting(pf), onClick: () => ctx.actions.pfCliCheck() }),
          ),
        )
      : null,
  );
}

function workingTestControls(ctx, pf, item) {
  const t = pf.text;
  const ready = isPassed(pf, 'cli');
  if (!ready || item.status === 'passed') return null;
  return h(
    'div',
    { key: 'test-controls' },
    h('p', { class: 'hint', key: 'signin-note', id: 'pf-test-signin-note' }, t.test_signin_note),
    h('p', { class: 'hint', key: 'waiting', id: 'pf-test-waiting' }, t.test_waiting),
    h(
      'div',
      { class: 'row', key: 'test-row' },
      actionButton(ctx, {
        label: t.test_check,
        id: 'pf-test-check',
        busyKey: 'pf-test-check',
        busyLabel: t.test_checking,
        kind: 'primary',
        onClick: () => ctx.actions.pfTestCheck(),
      }),
    ),
  );
}

// The Checking your computer page: one row per check, and the AIs that were found. The checks run by themselves.
function summaryControls(ctx, pf) {
  const t = pf.text;
  const rows = pf.items.filter((i) => i.applies && i.id !== 'track');
  const names = pf.cli.tools.filter((tool) => tool.found).map((tool) => tool.name);
  const cliDetail = (row) => (row.status === 'passed' ? row.detail : names.length ? fmt(t.summary_ai_found, { names: names.join(', ') }) : t.summary_ai_none);
  return h(
    'div',
    { key: 'summary-controls' },
    h('p', { class: 'hint', key: 'lede' }, t.summary_lede),
    h(
      'ul',
      { class: 'setup-summary pf-summary', id: 'pf-summary', key: 'rows' },
      rows.map((row) =>
        h(
          'li',
          { key: `sum-${row.id}`, id: `pf-summary-${row.id}`, class: 'pf-summary-row' },
          h('span', { class: 'pf-summary-title' }, row.title),
          h('span', { class: `pf-tag t-${row.status}`, id: `pf-summary-status-${row.id}` }, statusWord(pf, row.status)),
          (row.id === 'cli' ? cliDetail(row) : row.detail) ? h('p', { class: 'hint pf-summary-detail' }, row.id === 'cli' ? cliDetail(row) : row.detail) : null,
        ),
      ),
    ),
    ctx.wizard.summaryDone
      ? h('p', { class: 'callout callout-good', id: 'pf-summary-done', key: 'done', role: 'status' }, pf.items.filter((i) => i.applies).every((i) => i.status === 'passed') ? t.summary_all_passed : t.summary_done)
      : h('p', { class: 'hint', id: 'pf-summary-wait', key: 'wait', role: 'status' }, t.summary_running),
  );
}

function importResult(t, result) {
  const kind = !result.ready ? 'bad' : result.warnings.length ? 'attn' : 'good';
  const status = !result.ready ? t.import_blocked : result.warnings.length ? t.import_ready_notes : t.import_ready;
  const list = (items, prefix) => h('ul', { class: 'import-list' }, items.map((f, i) => h('li', { key: `${prefix}-${i}` }, f.message)));
  return h(
    'div',
    { class: `callout callout-${kind} import-result`, id: 'import-result', key: 'import-result' },
    h('p', { role: 'status', id: 'import-status' }, status),
    result.blocking.length ? [h('h3', { key: 'bt' }, t.import_blocking_title), h('div', { id: 'import-blocking', key: 'bl' }, list(result.blocking, 'b'))] : null,
    result.warnings.length ? [h('h3', { key: 'wt' }, t.import_warnings_title), h('div', { id: 'import-warnings', key: 'wl' }, list(result.warnings, 'w'))] : null,
    result.criteria.length
      ? [
          h('h3', { key: 'ct' }, t.import_criteria_title),
          h('ul', { class: 'import-criteria', id: 'import-criteria', key: 'cl' }, result.criteria.map((c) => h('li', { key: c.id }, `${c.id} ${c.name}`))),
        ]
      : null,
  );
}

function projectControls(ctx, pf) {
  const t = pf.text;
  const setup = ctx.state.setup || {};
  const defaults = setup.defaults || {};
  const starter = ctx.draft('setup.starter', setup.starter || 'northwind');
  const projectPath = ctx.draft('setup.project_path', setup.project_path || defaults.project_path || '');
  const warnings = setup.warnings || [];
  const pathWarning = /onedrive/i.test(projectPath) && !warnings.some((w) => /onedrive/i.test(w)) ? t.project_onedrive_warning : null;
  const cliReady = isPassed(pf, 'cli');
  // A check only counts for the exact paths it was run on.
  const importKey = [ctx.draft('setup.prompt_path', ''), ctx.draft('setup.test_cases_path', ''), projectPath].map((s) => s.trim()).join('\n');
  const saved = ctx.local('import-check');
  const importCurrent = saved && saved.key === importKey ? saved.result : null;
  const importReady = starter !== 'own' || Boolean(importCurrent && importCurrent.ready);
  const starterOption = (value, label, detail) =>
    h(
      'label',
      { class: 'radio-card', key: `starter-${value}` },
      h('input', {
        type: 'radio',
        name: 'starter',
        value,
        checked: starter === value,
        onChange: () => {
          ctx.setDraft('setup.starter', value);
          ctx.rerender();
        },
      }),
      h('span', null, h('strong', null, label), h('span', { class: 'hint block' }, detail)),
    );
  return h(
    'form',
    {
      class: 'pf-project',
      key: 'project-form',
      onSubmit: (e) => {
        e.preventDefault();
        if (!cliReady) return;
        if (importReady) ctx.actions.pfProject();
        else ctx.actions.pfImportCheck();
      },
    },
    textField(ctx, { id: 'setup-project', label: t.project_label, hint: t.project_hint, draftKey: 'setup.project_path', value: setup.project_path || defaults.project_path, mono: true }),
    warnings.length || pathWarning
      ? h('ul', { class: 'warnings', key: 'warnings' }, warnings.map((w, i) => h('li', { key: `w-${i}` }, w)), pathWarning ? h('li', { key: 'w-local' }, pathWarning) : null)
      : null,
    h(
      'fieldset',
      { class: 'field', key: 'starter' },
      h('legend', { class: 'field-label' }, t.starter_legend),
      starterOption('northwind', t.starter_northwind_label, t.starter_northwind_hint),
      h('p', { class: 'hint northwind-note', id: 'northwind-note' }, t.northwind_note),
      starterOption('own', t.starter_own_label, t.starter_own_hint),
      starter === 'own'
        ? h(
            'div',
            { class: 'own-paths', key: 'own-paths' },
            h('h3', { key: 'import-heading' }, t.import_heading),
            h('p', { class: 'hint', key: 'import-intro' }, t.import_intro),
            h('p', { class: 'hint', id: 'import-copies', key: 'import-copies' }, t.import_copies),
            textField(ctx, { id: 'setup-prompt', label: t.prompt_label, draftKey: 'setup.prompt_path', value: '', mono: true, placeholder: t.prompt_placeholder }),
            textField(ctx, { id: 'setup-test-cases', label: t.test_cases_label, draftKey: 'setup.test_cases_path', value: '', mono: true, placeholder: t.test_cases_placeholder }),
            h(
              'div',
              { class: 'row', key: 'import-row' },
              actionButton(ctx, {
                label: t.import_check,
                id: 'pf-import-check',
                busyKey: 'pf-import-check',
                busyLabel: t.import_checking,
                onClick: () => ctx.actions.pfImportCheck(),
              }),
            ),
            saved && !importCurrent ? h('p', { class: 'hint', id: 'import-stale', key: 'import-stale' }, t.import_stale) : null,
            importCurrent ? importResult(t, importCurrent) : null,
          )
        : null,
    ),
    h(
      'div',
      { class: 'row', key: 'submit' },
      h(
        'button',
        {
          type: 'submit',
          id: 'pf-project-submit',
          class: 'btn btn-primary',
          'aria-busy': ctx.busy('setup') ? 'true' : null,
          'aria-disabled': ctx.busy('setup') || !cliReady || !importReady ? 'true' : null,
        },
        ctx.busy('setup') ? t.project_submitting : t.project_submit,
      ),
      cliReady ? null : h('span', { class: 'hint' }, t.project_blocked),
      cliReady && !importReady && !saved ? h('span', { class: 'hint', id: 'import-first', key: 'import-first' }, t.import_check_first) : null,
    ),
  );
}

function renderItem(ctx, pf, item) {
  let controls = null;
  if (item.id === 'track') controls = trackControls(ctx, pf);
  else if (item.id === 'summary') controls = summaryControls(ctx, pf);
  else if (item.id === 'ai_window') controls = renderAiWindowLesson(ctx);
  else if (item.install) controls = installControls(ctx, pf, item);
  else if (item.id === 'cli') controls = cliControls(ctx, pf, item);
  else if (item.id === 'working_test') controls = workingTestControls(ctx, pf, item);
  else if (item.id === 'project') controls = projectControls(ctx, pf);
  return h(
    'li',
    { key: `pf-${item.id}`, id: `pf-item-${item.id}`, class: `pf-item pf-${item.status}` },
    h(
      'div',
      { class: 'pf-head' },
      h('span', { class: 'pf-num' }, String(item.number)),
      h('h2', { class: 'pf-title' }, item.title),
      item.virtual ? null : h('span', { class: `pf-tag t-${item.status}`, id: `pf-status-${item.id}` }, statusWord(pf, item.status)),
    ),
    item.detail ? h('p', { class: 'pf-detail', key: 'detail' }, item.detail) : null,
    item.next ? h('p', { class: 'pf-next', key: 'next' }, item.next) : null,
    controls,
  );
}

// Setup is a full-page wizard: one page per applicable check, with the same controls and ids as before, and two
// pages that are not checks: Checking your computer (after Track) runs the checks by itself, and Your AI window
// (last) is a lesson that is never recorded as progress.
export function wizardPages(pf) {
  const pages = pf.items.filter((i) => i.applies).map((i) => ({ ...i }));
  const checked = pf.ran_once && !jobBusy(pf);
  pages.splice(1, 0, { id: 'summary', virtual: true, title: pf.pages.summary.title, status: checked ? 'passed' : 'not_checked', detail: '', next: '' });
  pages.push({ id: 'ai_window', virtual: true, title: pf.pages.ai_window.title, status: 'passed', detail: '', next: '' });
  return pages;
}

// The page the wizard opens on: the first check that has not passed. A fresh setup starts on the Track page,
// which carries the welcome text and the track choice even though its check passes by default.
export function firstWizardItem(pf) {
  const pages = wizardPages(pf).filter((p) => !p.virtual);
  if (!pages.slice(1).some((i) => i.status === 'passed')) return pages[0].id;
  const open = pages.find((i) => i.status !== 'passed');
  return (open || pages[0]).id;
}

// Moving forward goes to the next page that still needs the participant. Passed checks are skipped; Back and
// the page list still reach them. The two pages that are not checks are never skipped.
export function nextWizardPage(pages, index) {
  for (let i = index + 1; i < pages.length; i += 1) {
    if (pages[i].virtual || pages[i].status !== 'passed') return pages[i];
  }
  return pages[pages.length - 1];
}

export function wizardIndex(ctx) {
  const pf = ctx.state.preflight;
  const pages = wizardPages(pf);
  const index = pages.findIndex((p) => p.id === (ctx.wizard.item || firstWizardItem(pf)));
  return index < 0 ? 0 : index;
}

export function wizardPageId(ctx) {
  return wizardPages(ctx.state.preflight)[wizardIndex(ctx)].id;
}

// The AI window shows on the working test page, and on Choose your AI only while an install runs.
export function wizardUsesTerminal(ctx) {
  const id = wizardPageId(ctx);
  if (id === 'working_test') return true;
  return id === 'cli' && ctx.state.preflight.session.kind === 'recipe';
}

function wizardHead(ctx, pf, canSkip) {
  const t = pf.text;
  return h(
    'header',
    { class: 'wizard-head', key: 'head' },
    h('span', { class: 'wizard-mark' }, h('span', { class: 'wm-a' }, 'eval'), h('span', { class: 'wm-sep' }, '-'), h('span', { class: 'wm-b' }, 'coach')),
    canSkip
      ? actionButton(ctx, { label: t.skip_button, id: 'pf-skip', busyKey: 'pf-skip', onClick: () => ctx.actions.pfSkip() })
      : ctx.wizard.byChoice
        ? actionButton(ctx, { label: t.wizard_close, id: 'wizard-close', onClick: () => ctx.actions.closeSetup() })
        : null,
  );
}

function wizardProgress(pf, pages, index) {
  const t = pf.text;
  return h(
    'nav',
    { class: 'wizard-steps', key: 'steps', 'aria-label': t.wizard_nav_label },
    h('p', { class: 'wizard-count', id: 'wizard-count' }, t.wizard_progress.replace('{n}', String(index + 1)).replace('{total}', String(pages.length))),
    h(
      'ol',
      { class: 'wizard-list' },
      pages.map((page, i) =>
        h(
          'li',
          { key: `wiz-${page.id}`, class: `wizard-dot t-${page.status}${i === index ? ' is-here' : ''}`, 'aria-current': i === index ? 'step' : null },
          h('span', { class: 'wizard-dot-num' }, String(i + 1)),
          h('span', { class: 'wizard-dot-name' }, page.title),
        ),
      ),
    ),
  );
}

// Check everything is offered only where the participant can fix something outside the app and look again.
const RECHECK_PAGES = ['python', 'node', 'promptfoo', 'cli', 'project'];

export function renderWizard(ctx) {
  const pf = ctx.state.preflight;
  const t = pf.text;
  const pages = wizardPages(pf);
  const index = wizardIndex(ctx);
  const page = pages[index];
  const last = index === pages.length - 1;
  const passed = page.id === 'summary' ? Boolean(ctx.wizard.summaryDone) : page.status === 'passed';
  const busy = jobBusy(pf);
  const unfinished = pages.filter((i) => !i.virtual && i.status !== 'passed').map((i) => i.title);
  // First run offers to skip. Opened from Settings or the reminder, it offers to close instead.
  const canSkip = !ctx.wizard.byChoice && !pf.passed && !pf.skipped;
  const result = ctx.wizard.byChoice ? null : ctx.local('reset-result');
  const goTo = (target) => ctx.actions.wizardGo(target.id);
  return h(
    'article',
    { class: 'setup preflight wizard', key: 'wizard' },
    wizardHead(ctx, pf, canSkip),
    h('h1', { id: 'step-heading', tabindex: -1, key: 'heading' }, t.heading),
    wizardProgress(pf, pages, index),
    index === 0
      ? [
          result ? h('p', { class: 'callout callout-good reset-result', id: 'reset-result', role: 'status', key: 'reset-result' }, result.message) : null,
          h('p', { class: 'lede', key: 'lede' }, t.lede),
          h('p', { key: 'intro' }, t.intro),
          canSkip ? h('p', { class: 'hint', id: 'pf-skip-hint', key: 'skip-hint' }, t.skip_hint) : null,
        ]
      : null,
    renderProgress(pf),
    h('ol', { class: 'pf-list', key: `page-${page.id}` }, renderItem(ctx, pf, { ...page, number: index + 1 })),
    h(
      'div',
      { class: 'wizard-foot', key: 'foot' },
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, { label: t.wizard_back, id: 'wizard-back', disabled: index === 0, onClick: () => goTo(pages[index - 1]) }),
        RECHECK_PAGES.includes(page.id)
          ? actionButton(ctx, {
              label: pf.ran_once ? t.check_all_again : t.check_all,
              id: 'pf-check-all',
              busyKey: 'pf-check',
              busyLabel: t.checking,
              disabled: busy,
              onClick: () => ctx.actions.pfCheckAll(),
            })
          : null,
        last
          ? actionButton(ctx, { label: t.wizard_finish, id: 'wizard-finish', kind: 'primary', onClick: () => ctx.actions.wizardFinish() })
          : actionButton(ctx, { label: t.wizard_next, id: 'wizard-next', kind: 'primary', disabled: !passed || (page.id === 'cli' && aiTesting(pf)), onClick: () => goTo(nextWizardPage(pages, index)) }),
      ),
      !last && !passed ? h('p', { class: 'hint', id: 'wizard-needed', key: 'needed' }, page.id === 'summary' ? t.summary_wait : t.wizard_needed) : null,
      unfinished.length && !last ? h('p', { class: 'hint', id: 'wizard-unfinished', key: 'unfinished' }, t.still_to_finish.replace('{items}', unfinished.join(', '))) : null,
    ),
  );
}

export function renderPreflightTermHead(ctx) {
  const { state } = ctx;
  const pf = state.preflight;
  const t = pf.text;
  const { terminal } = state;
  const running = terminal.running;
  const testItem = itemById(pf, 'working_test');
  const testReady = ctx.wizard.item === 'working_test' && isPassed(pf, 'cli') && testItem && testItem.status !== 'passed';
  const statusLine =
    running ? t.term_running : terminal.exit_code !== null && terminal.exit_code !== undefined ? t.term_stopped.replace('{code}', terminal.exit_code) : t.term_not_running;
  return [
    h(
      'div',
      { class: 'term-title-row', key: 'title' },
      h('h2', { class: 'term-label' }, terminal.label || t.term_title),
      h('span', { class: `term-status${running ? ' is-on' : ''}`, role: 'status' }, statusLine),
    ),
    h('div', { class: 'row term-ai-link', key: 'ai-window-link' }, aiWindowLink(ctx)),
    testReady
      ? h(
          'div',
          { class: 'term-line-block', key: 'line' },
          h('span', { class: 'hint block' }, t.term_line_intro),
          h('code', { class: 'term-line' }, pf.working_test.line),
          h('span', { class: 'hint block' }, t.term_folder, ' ', pf.working_test.folder_label),
        )
      : null,
    h(
      'div',
      { class: 'row term-actions', key: 'actions' },
      testReady
        ? actionButton(ctx, { label: t.term_start, id: 'cli-start', busyKey: 'pf-test-start', busyLabel: t.cli_starting, kind: running ? null : 'primary', onClick: () => ctx.actions.pfTestStart() })
        : null,
      testReady
        ? actionButton(ctx, { label: t.term_send, id: 'cli-send', busyKey: 'pf-test-send', disabled: !running || pf.session.kind !== 'test', kind: running ? 'primary' : null, onClick: () => ctx.actions.pfTestSend() })
        : null,
      actionButton(ctx, { label: t.term_stop, id: 'cli-stop', busyKey: 'pf-stop', disabled: !running, onClick: () => ctx.actions.pfStop() }),
    ),
    pf.session.kind === 'test' && pf.session.sent
      ? h('p', { class: 'hint', key: 'sent' }, t.term_sent)
      : pf.session.kind === 'test' && running
        ? h('p', { class: 'hint', key: 'ready' }, t.term_ready)
        : null,
  ];
}

export function renderPreflightTermFoot(ctx) {
  return [h('p', { class: 'term-note', key: 'approvals' }, ctx.state.preflight.text.term_foot)];
}
