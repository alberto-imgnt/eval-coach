// The Settings panel, the setup reminder banner and the reset dialogs.
// Every word comes from content/settings.json, which the server sends as state.settings.text.

import { getTextSize, setTextSize, textRange, textSizeStep } from './chrome.js';
import { h } from './dom.js';
import { fmt } from './lessons.js';
import { actionButton } from './ui.js';

const words = (ctx) => ctx.state.settings.text;

// ---- the reminder banner ----------------------------------------------------

// A slim strip above the content while setup has not passed. It has no close control, and it is not shown
// on the setup screen itself. It never takes focus.
export function renderSetupBanner(ctx) {
  const { state } = ctx;
  if (!state || !state.settings || state.preflight.passed || ctx.view === 'wizard') return [];
  const b = words(ctx).banner;
  return [
    h(
      'section',
      { class: 'setup-banner', id: 'setup-reminder', key: 'setup-reminder', role: 'status', 'aria-label': b.label },
      h('p', null, b.text),
      actionButton(ctx, { label: b.button, id: 'setup-banner-go', onClick: () => ctx.actions.openSetup() }),
    ),
  ];
}

// ---- text size ----------------------------------------------------------------

function renderTextSize(ctx) {
  const s = words(ctx).settings;
  const range = textRange();
  const size = getTextSize();
  return h(
    'section',
    { class: 'settings-group', id: 'settings-text-size', key: 'text-size', 'aria-labelledby': 'settings-text-size-title' },
    h('h2', { id: 'settings-text-size-title' }, s.text_size_heading),
    h('p', null, s.text_size_intro),
    h(
      'div',
      { class: 'size-row' },
      h('label', { for: 'text-size-slider', class: 'field-label' }, s.text_size_label),
      h('input', {
        type: 'range',
        id: 'text-size-slider',
        min: String(range.min),
        max: String(range.max),
        step: String(textSizeStep()),
        value: String(size),
        'aria-valuetext': fmt(s.text_size_value, { value: size }),
        onInput: (event) => {
          setTextSize(Number(event.target.value));
        },
      }),
      h('output', { id: 'text-size-value', class: 'size-value', for: 'text-size-slider' }, fmt(s.text_size_value, { value: size })),
      actionButton(ctx, {
        label: s.text_size_default,
        id: 'text-size-default',
        disabled: size === 100,
        onClick: () => setTextSize(100),
      }),
    ),
    h('p', { class: 'hint', id: 'text-size-range' }, fmt(s.text_size_range, { min: range.min, max: range.max })),
  );
}

// ---- resets -------------------------------------------------------------------

// The confirmation dialog's body: what is cleared, what is kept, where the backup goes.
export function resetDialogBody(text, kind, backupFolder, hasProject) {
  const w = text.reset[kind];
  return [
    h(
      'div',
      { class: 'reset-dialog', id: `reset-dialog-${kind}` },
      h('p', null, w.lead),
      h('h3', null, w.clears_title),
      h('ul', { id: 'reset-clears' }, w.clears.map((item) => h('li', null, item))),
      h('h3', null, w.keeps_title),
      h('ul', { id: 'reset-keeps' }, w.keeps.map((item) => h('li', null, item))),
      h('p', { id: 'reset-backup-note' }, hasProject || kind === 'configuration' ? fmt(w.backup, { folder: backupFolder }) : w.no_project),
      kind === 'configuration' && !hasProject ? h('p', { id: 'reset-no-project' }, w.no_project) : null,
    ),
  ];
}

// The confirmation dialog's body for "Start this step again": the steps that start again, what is cleared and kept,
// and where the backup goes. `restart` is the step's own restart view from the server.
export function restartDialogBody(w, restart) {
  const values = { steps: restart.steps_text, folder: restart.backup_folder };
  return [
    h(
      'div',
      { class: 'reset-dialog', id: 'restart-dialog' },
      h('p', { id: 'restart-lead' }, fmt(w.lead, values)),
      h('h3', null, w.clears_title),
      h('ul', { id: 'restart-clears' }, w.clears.map((item) => h('li', null, fmt(item, values)))),
      h('h3', null, w.keeps_title),
      h('ul', { id: 'restart-keeps' }, w.keeps.map((item) => h('li', null, item))),
      h('p', { id: 'restart-backup-note' }, fmt(w.backup, values)),
    ),
  ];
}

function renderReset(ctx) {
  const s = words(ctx).settings;
  const t = words(ctx);
  const result = ctx.local('reset-result');
  const item = (kind, danger) =>
    h(
      'li',
      { class: `reset-item${danger ? ' is-strong' : ''}`, key: `reset-${kind}` },
      h('h3', null, t.reset[kind].button),
      h('p', null, t.reset[kind].summary),
      actionButton(ctx, {
        label: t.reset[kind].button,
        id: `reset-${kind}`,
        busyKey: `reset-${kind}`,
        busyLabel: '…',
        kind: danger ? 'danger' : null,
        onClick: () => ctx.actions.reset(kind),
      }),
    );
  return h(
    'section',
    { class: 'settings-group', id: 'settings-reset', key: 'reset', 'aria-labelledby': 'settings-reset-title' },
    h('h2', { id: 'settings-reset-title' }, s.reset_heading),
    h('p', null, s.reset_intro),
    h('ul', { class: 'reset-list' }, item('progress', false), item('configuration', true)),
    result ? h('p', { class: 'callout callout-good reset-result', id: 'reset-result', role: 'status' }, result.message) : null,
  );
}

// The setup group: the checks and their status, and a button that opens the setup wizard.
function renderSetupGroup(ctx) {
  const s = words(ctx).settings;
  const pf = ctx.state.preflight;
  return h(
    'section',
    { class: 'settings-group', id: 'settings-setup', key: 'setup', 'aria-labelledby': 'settings-setup-title' },
    h('h2', { id: 'settings-setup-title' }, s.setup_heading),
    h('p', null, s.setup_intro),
    h(
      'ul',
      { class: 'setup-summary', id: 'settings-setup-summary', 'aria-label': s.setup_summary_label },
      pf.items
        .filter((i) => i.applies)
        .map((i) =>
          h(
            'li',
            { key: `sum-${i.id}`, id: `settings-setup-${i.id}` },
            h('span', null, (s.summary_names && s.summary_names[i.id]) || i.title),
            h('span', { class: `pf-tag t-${i.status}` }, pf.text[`status_${i.status}`] || i.status),
          ),
        ),
    ),
    h(
      'div',
      { class: 'row' },
      actionButton(ctx, { label: s.setup_open, id: 'settings-setup-open', kind: 'primary', onClick: () => ctx.actions.openSetup() }),
      actionButton(ctx, { label: s.setup_ai_window, id: 'settings-ai-window', onClick: () => ctx.actions.openAiWindowLesson() }),
    ),
  );
}

// ---- the panel ----------------------------------------------------------------

export function renderSettings(ctx) {
  const s = words(ctx).settings;
  return h(
    'article',
    { class: 'settings-page', key: 'settings' },
    h('h1', { id: 'step-heading', tabindex: -1 }, s.heading),
    h('p', { class: 'lede' }, s.lede),
    h('div', { class: 'row' }, actionButton(ctx, { label: s.close, id: 'settings-close', onClick: () => ctx.actions.closeSettings() })),
    renderTextSize(ctx),
    renderSetupGroup(ctx),
    renderReset(ctx),
  );
}
