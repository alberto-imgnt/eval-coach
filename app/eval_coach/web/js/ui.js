// Shared form and display helpers used by the step views.

import { h } from './dom.js';

export const VERDICTS = { P: 'PASS', F: 'FAIL', NC: 'NOT CHECKED' };

// The optional live-mode step, while it is on offer (promptfoo track, after the baseline step).
export function optionalLive(state) {
  return ((state && state.optional_steps) || []).find((i) => i.id === 'live' && i.status === 'optional') || null;
}

export function verdictTag(v) {
  const label = VERDICTS[v];
  if (!label) return h('span', { class: 'verdict v-none' }, 'none');
  return h('span', { class: `verdict v-${v}` }, label);
}

// A button that stays focusable while busy or unavailable (aria-disabled), so
// keyboard users do not lose their place when its state changes.
export function actionButton(ctx, { label, busyKey, busyLabel, onClick, kind, disabled, id }) {
  const busy = Boolean(busyKey && ctx.busy(busyKey));
  const off = busy || Boolean(disabled);
  return h(
    'button',
    {
      type: 'button',
      id,
      class: `btn${kind ? ` btn-${kind}` : ''}`,
      'aria-disabled': off ? 'true' : null,
      'aria-busy': busy ? 'true' : null,
      onClick: () => {
        if (!off) onClick();
      },
    },
    busy ? busyLabel || 'Working…' : label,
  );
}

export function textField(ctx, opts) {
  const { id, label, hint, draftKey, value, saveStep, multiline, rows, disabled, placeholder, mono } = opts;
  const current = ctx.draft(draftKey, value === null || value === undefined ? '' : value);
  const props = {
    id,
    disabled,
    placeholder,
    value: current,
    class: mono ? 'input mono' : 'input',
    'aria-describedby': hint ? `${id}-hint` : null,
    autocomplete: 'off',
    spellcheck: mono ? 'false' : null,
    onInput: (e) => {
      ctx.setDraft(draftKey, e.target.value);
      if (saveStep) ctx.queueSave(saveStep);
      ctx.rerender();
    },
    onBlur: saveStep ? () => ctx.flushSave(saveStep) : null,
  };
  const control = multiline ? h('textarea', { ...props, rows: rows || 3 }) : h('input', { ...props, type: 'text' });
  return h(
    'div',
    { class: 'field', key: `field-${id}` },
    h('label', { for: id, class: 'field-label' }, label),
    hint ? h('p', { class: 'hint', id: `${id}-hint` }, hint) : null,
    control,
  );
}

export function section(key, title, ...children) {
  return h('section', { key, class: 'block' }, title ? h('h2', null, title) : null, ...children);
}

export function runSummary(rows) {
  const count = { P: 0, F: 0, NC: 0 };
  for (const row of rows || []) if (count[row.verdict] !== undefined) count[row.verdict] += 1;
  return `${count.P} PASS, ${count.F} FAIL, ${count.NC} NOT CHECKED`;
}

export function runErrorBox(result) {
  if (!result || result.ok) return null;
  return h(
    'div',
    { class: 'callout callout-bad', key: 'run-error' },
    h('strong', null, 'The checker could not finish. '),
    result.error || 'It stopped with an unexpected error.',
    result.exit_code !== null && result.exit_code !== undefined ? ` (exit code ${result.exit_code})` : null,
  );
}

export function rawOutput(result) {
  if (!result || !result.raw) return null;
  return h(
    'details',
    { class: 'raw', key: 'raw' },
    h('summary', null, 'Show the checker’s full text output'),
    h('pre', { class: 'mono-block' }, result.raw),
  );
}

export function resultTables(result) {
  if (!result) return null;
  const { files } = result;
  return h(
    'div',
    { class: 'results', key: 'results' },
    runErrorBox(result),
    result.ok && result.exit_code === 1
      ? h('p', { class: 'hint' }, 'Exit code 1 is normal. It only means at least one check failed.')
      : result.ok && result.exit_code
        ? h('p', { class: 'hint' }, 'A non-zero exit code is normal here. It only means at least one check failed.')
        : null,
    (files || []).map((f) =>
      h(
        'div',
        { class: 'result-file', key: `file-${f.file}` },
        h('h3', null, f.file),
        h('p', { class: 'hint' }, runSummary(f.rows)),
        h(
          'div',
          { class: 'table-scroll' },
          h(
            'table',
            { class: 'grid' },
            h(
              'thead',
              null,
              h('tr', null, h('th', { scope: 'col' }, 'Criterion'), h('th', { scope: 'col' }, 'Result'), h('th', { scope: 'col' }, 'What the checker said')),
            ),
            h(
              'tbody',
              null,
              (f.rows || []).map((r) =>
                h(
                  'tr',
                  { key: r.id },
                  h('td', null, h('span', { class: 'crit-id' }, r.id), ' ', r.name),
                  h('td', null, verdictTag(r.verdict)),
                  h('td', null, r.reason),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
    rawOutput(result),
  );
}
