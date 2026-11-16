// The preflight screen: every item's status, detail, next action and controls.
// All words come from the server (content/preflight.json).

import { h } from './dom.js';
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

function recipeCard(ctx, pf, recipe) {
  const t = pf.text;
  return h(
    'li',
    { key: `recipe-${recipe.id}`, class: 'pf-recipe', id: `pf-recipe-card-${recipe.id}` },
    h('strong', { class: 'block' }, recipe.name),
    recipe.note ? h('p', { class: 'hint' }, recipe.note) : null,
    recipe.command
      ? h(
          'div',
          { key: 'cmd' },
          h('span', { class: 'hint block' }, t.recipe_exact),
          h('code', { class: 'pf-command', id: `pf-recipe-command-${recipe.id}` }, recipe.command),
        )
      : null,
    recipe.requirement
      ? h(
          'div',
          { class: 'callout callout-attn', key: 'req' },
          h('strong', null, `${t.recipe_requirement_missing} ${recipe.requirement.name}. `),
          recipe.requirement.detail,
        )
      : null,
    h(
      'div',
      { class: 'row', key: 'buttons' },
      recipe.cli_command
        ? actionButton(ctx, {
            label: t.recipe_use,
            id: `pf-recipe-use-${recipe.id}`,
            onClick: () => {
              ctx.setDraft('pf.cli_command', recipe.cli_command);
              ctx.rerender();
            },
          })
        : null,
      recipe.requirement
        ? actionButton(ctx, {
            label: `${t.recipe_install}: ${recipe.requirement.name}`,
            id: `pf-recipe-install-${recipe.requirement.recipe}`,
            busyKey: `pf-recipe-${recipe.requirement.recipe}`,
            disabled: jobBusy(pf),
            onClick: () => ctx.actions.pfRecipe(recipe.requirement.recipe),
          })
        : null,
      recipe.command
        ? actionButton(ctx, {
            label: t.recipe_install,
            id: `pf-recipe-install-${recipe.id}`,
            busyKey: `pf-recipe-${recipe.id}`,
            disabled: jobBusy(pf),
            onClick: () => ctx.actions.pfRecipe(recipe.id),
          })
        : null,
    ),
  );
}

function cliControls(ctx, pf, item) {
  const t = pf.text;
  const found = item.status === 'passed' || (pf.cli.command && item.status === 'needs_you' && !ctx.hasDraft('pf.cli_command'));
  return h(
    'div',
    { key: 'cli-controls' },
    textField(ctx, { id: 'pf-cli-command', label: t.cli_label, hint: t.cli_hint, draftKey: 'pf.cli_command', value: pf.cli.command, mono: true }),
    h(
      'div',
      { class: 'row', key: 'cli-buttons' },
      actionButton(ctx, { label: t.cli_check, id: 'pf-cli-check', busyKey: 'pf-cli-check', busyLabel: t.cli_checking, onClick: () => ctx.actions.pfCliCheck() }),
      actionButton(ctx, {
        label: t.cli_start,
        id: 'pf-cli-start',
        busyKey: 'pf-cli-start',
        busyLabel: t.cli_starting,
        kind: 'primary',
        disabled: !found,
        onClick: () => ctx.actions.pfCliStart(),
      }),
    ),
    h(
      'details',
      { class: 'pf-recipes', key: 'recipes', open: item.status !== 'passed' },
      h('summary', null, t.recipe_heading),
      h('p', { class: 'hint' }, t.recipe_hint),
      h('ul', { class: 'pf-recipe-list' }, pf.cli.recipes.filter((r) => !r.hidden).map((r) => recipeCard(ctx, pf, r))),
    ),
  );
}

function signinControls(ctx, pf, item) {
  const t = pf.text;
  const cliReady = isPassed(pf, 'cli');
  return h(
    'div',
    { class: 'row', key: 'signin-row' },
    item.status !== 'passed'
      ? actionButton(ctx, {
          label: t.signin_confirm,
          id: 'pf-signin-confirm',
          busyKey: 'pf-signin',
          kind: 'primary',
          disabled: !cliReady,
          onClick: () => ctx.actions.pfSignin(),
        })
      : null,
  );
}

function workingTestControls(ctx, pf, item) {
  const t = pf.text;
  const ready = isPassed(pf, 'cli') && isPassed(pf, 'signin');
  if (!ready || item.status === 'passed') return null;
  return h(
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
  else if (item.install) controls = installControls(ctx, pf, item);
  else if (item.id === 'cli') controls = cliControls(ctx, pf, item);
  else if (item.id === 'signin') controls = signinControls(ctx, pf, item);
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
      h('span', { class: `pf-tag t-${item.status}`, id: `pf-status-${item.id}` }, statusWord(pf, item.status)),
    ),
    item.detail ? h('p', { class: 'pf-detail', key: 'detail' }, item.detail) : null,
    item.next ? h('p', { class: 'pf-next', key: 'next' }, item.next) : null,
    controls,
  );
}

// Setup is a full-page wizard: one page per applicable check, with the same controls and ids as before.
// The pages that use the participant's CLI show the terminal beside (or below) the page.
const TERMINAL_ITEMS = ['cli', 'signin', 'working_test'];

export function wizardPages(pf) {
  return pf.items.filter((i) => i.applies);
}

// The page the wizard opens on: the first check that has not passed. A fresh setup starts on the Track page,
// which carries the welcome text and the track choice even though its check passes by default.
export function firstWizardItem(pf) {
  const pages = wizardPages(pf);
  if (!pages.slice(1).some((i) => i.status === 'passed')) return pages[0].id;
  const open = pages.find((i) => i.status !== 'passed');
  return (open || pages[0]).id;
}

export function wizardIndex(ctx) {
  const pf = ctx.state.preflight;
  const pages = wizardPages(pf);
  const index = pages.findIndex((p) => p.id === (ctx.wizard.item || firstWizardItem(pf)));
  return index < 0 ? 0 : index;
}

export function wizardUsesTerminal(ctx) {
  const pages = wizardPages(ctx.state.preflight);
  return TERMINAL_ITEMS.includes(pages[wizardIndex(ctx)].id);
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

export function renderWizard(ctx) {
  const pf = ctx.state.preflight;
  const t = pf.text;
  const pages = wizardPages(pf);
  const index = wizardIndex(ctx);
  const page = pages[index];
  const last = index === pages.length - 1;
  const passed = page.status === 'passed';
  const busy = jobBusy(pf);
  const unfinished = pages.filter((i) => i.status !== 'passed').map((i) => i.title);
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
        actionButton(ctx, {
          label: pf.ran_once ? t.check_all_again : t.check_all,
          id: 'pf-check-all',
          busyKey: 'pf-check',
          busyLabel: t.checking,
          disabled: busy,
          onClick: () => ctx.actions.pfCheckAll(),
        }),
        last ? null : actionButton(ctx, { label: t.wizard_next, id: 'wizard-next', kind: 'primary', disabled: !passed, onClick: () => goTo(pages[index + 1]) }),
      ),
      !last && !passed ? h('p', { class: 'hint', id: 'wizard-needed', key: 'needed' }, t.wizard_needed) : null,
      unfinished.length ? h('p', { class: 'hint', id: 'wizard-unfinished', key: 'unfinished' }, t.still_to_finish.replace('{items}', unfinished.join(', '))) : null,
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
  const testReady = isPassed(pf, 'cli') && isPassed(pf, 'signin') && testItem && testItem.status !== 'passed';
  const statusLine =
    running ? t.term_running : terminal.exit_code !== null && terminal.exit_code !== undefined ? t.term_stopped.replace('{code}', terminal.exit_code) : t.term_not_running;
  return [
    h(
      'div',
      { class: 'term-title-row', key: 'title' },
      h('h2', { class: 'term-label' }, terminal.label || t.term_title),
      h('span', { class: `term-status${running ? ' is-on' : ''}`, role: 'status' }, statusLine),
    ),
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
