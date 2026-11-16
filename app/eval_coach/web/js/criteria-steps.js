// The panels of the criteria Part's three step kinds: the criteria worksheet (criteria_table, the `draft` and
// `thresholds` steps), the test case file (test_file, `test-file`) and the reference comparison (reveal_compare,
// `reference`). No step starts a CLI. Every word comes from the step's content (step.ui and step.data), and
// everything the participant wrote or a file holds is placed in text nodes, never as markup.

import { confirmDialog } from './dialog.js';
import { h } from './dom.js';
import { fmt } from './lessons.js';
import { plainText, renderScenario, saveButton, savedLine } from './part-steps.js';
import { actionButton, section, textField } from './ui.js';

const BLANK_ROW = { requirement: '', criterion: '', type: '', threshold: '' };
const MAX_CELL = 400;

const draftKey = (step, name) => `${step.id}.${name}`;
const rowsKey = (step) => draftKey(step, 'rows');
const tickKey = (step, id) => draftKey(step, `tick.${id}`);
const textKey = (step) => draftKey(step, 'text');
const choiceKey = (step, id) => draftKey(step, `choice.${id}`);

// Which of a step's texts have changes that are not saved. The Check button asks to Save first.
export function unsavedCriteria(step, drafts) {
  if (step.kind === 'criteria_table') return drafts.has(rowsKey(step));
  if (step.kind === 'test_file' || step.kind === 'reveal_compare') return drafts.has(textKey(step));
  return false;
}

const focusSoon = (id) =>
  window.requestAnimationFrame(() => {
    const el = document.getElementById(id);
    if (el) el.focus();
  });

function fact(label, value, key) {
  return h('div', { class: 'ref-fact', key }, h('dt', null, label), h('dd', null, value));
}

// ---- the worksheet: draft and thresholds ---------------------------------

const currentRows = (ctx, step) => ctx.draft(rowsKey(step), step.data.rows);

function changeRows(ctx, step, rows) {
  ctx.setDraft(rowsKey(step), rows);
  ctx.rerender();
}

function changeRow(ctx, step, index, field, value) {
  changeRows(
    ctx,
    step,
    currentRows(ctx, step).map((row, i) => (i === index ? { ...row, [field]: value } : row)),
  );
}

function cell(ctx, step, index, field, { label, hint }) {
  const id = `row-${index + 1}-${field}`;
  const row = currentRows(ctx, step)[index];
  return h(
    'div',
    { class: 'field', key: `field-${id}` },
    h('label', { for: id, class: 'field-label' }, label),
    hint ? h('p', { class: 'hint', id: `${id}-hint` }, hint) : null,
    h('textarea', {
      id,
      rows: 2,
      maxlength: MAX_CELL,
      class: 'input',
      value: row[field],
      disabled: ctx.readOnly,
      autocomplete: 'off',
      'aria-describedby': hint ? `${id}-hint` : null,
      onInput: (e) => changeRow(ctx, step, index, field, e.target.value),
    }),
  );
}

function requirementMenu(ctx, step, index) {
  const { data, ui } = step;
  const id = `row-${index + 1}-menu`;
  return h(
    'div',
    { class: 'field', key: `field-${id}` },
    h('label', { for: id, class: 'field-label' }, ui.requirement_menu_label),
    h(
      'select',
      {
        id,
        class: 'input',
        value: '',
        disabled: ctx.readOnly,
        onChange: (e) => {
          const picked = data.requirements.find((r) => r.id === e.target.value);
          e.target.value = '';
          if (picked) changeRow(ctx, step, index, 'requirement', picked.label);
        },
      },
      h('option', { value: '' }, ui.requirement_menu_none),
      data.requirements.map((r) => h('option', { value: r.id, key: r.id }, r.label)),
    ),
  );
}

function typeChoice(ctx, step, index, row) {
  const { data, ui } = step;
  const n = index + 1;
  return h(
    'fieldset',
    { class: 'field', id: `row-${n}-type`, key: `type-${n}` },
    h('legend', { class: 'field-label' }, ui.type_label),
    h(
      'div',
      { class: 'seg' },
      data.types.map((t) =>
        h(
          'label',
          { class: 'seg-opt', key: t.id },
          h('input', {
            type: 'radio',
            name: `${step.id}-row-${n}-type`,
            value: t.id,
            checked: row.type === t.id,
            disabled: ctx.readOnly,
            onChange: () => changeRow(ctx, step, index, 'type', t.id),
          }),
          h('span', null, t.label),
        ),
      ),
    ),
    row.type ? null : h('p', { class: 'hint ws-type-none' }, ui.type_none),
  );
}

function editableRow(ctx, step, row, index) {
  const { ui } = step;
  const n = index + 1;
  return h(
    'fieldset',
    { class: 'ws-row', id: `ws-row-${n}`, key: `ws-row-${n}` },
    h('legend', null, fmt(ui.row_label, { n })),
    h(
      'div',
      { class: 'ws-grid' },
      h('div', { class: 'ws-cell', key: 'requirement' }, cell(ctx, step, index, 'requirement', { label: ui.requirement_label }), requirementMenu(ctx, step, index)),
      h('div', { class: 'ws-cell', key: 'criterion' }, cell(ctx, step, index, 'criterion', { label: ui.criterion_label }), typeChoice(ctx, step, index, row)),
    ),
    h(
      'div',
      { class: 'row' },
      actionButton(ctx, {
        label: fmt(ui.remove_row, { n }),
        id: `row-${n}-remove`,
        disabled: ctx.readOnly,
        onClick: () => {
          changeRows(
            ctx,
            step,
            currentRows(ctx, step).filter((_, i) => i !== index),
          );
          focusSoon('ws-add');
        },
      }),
    ),
  );
}

function thresholdRow(ctx, step, row, index) {
  const { data, ui } = step;
  const n = index + 1;
  const type = data.types.find((t) => t.id === row.type);
  return h(
    'fieldset',
    { class: 'ws-row', id: `ws-row-${n}`, key: `ws-row-${n}` },
    h('legend', null, fmt(ui.row_label, { n })),
    h(
      'dl',
      { class: 'ws-grid ws-facts' },
      fact(ui.requirement_label, row.requirement, 'requirement'),
      fact(ui.criterion_label, row.criterion, 'criterion'),
      fact(ui.type_label, type ? type.label : '', 'type'),
    ),
    cell(ctx, step, index, 'threshold', { label: ui.threshold_label, hint: ui.threshold_hint }),
  );
}

function renderRows(ctx, step) {
  const { data, ui } = step;
  const rows = currentRows(ctx, step);
  const unsaved = ctx.hasDraft(rowsKey(step));
  const full = rows.length >= data.max_rows;
  return section(
    'worksheet',
    ui.worksheet_heading,
    data.thresholds_only ? h('p', { class: 'hint', id: 'criteria-locked' }, ui.criteria_locked_hint) : null,
    rows.length === 0 ? h('p', { class: 'hint', id: 'ws-empty' }, ui.empty_hint) : null,
    h('div', { id: 'ws-rows' }, rows.map((row, i) => (data.thresholds_only ? thresholdRow(ctx, step, row, i) : editableRow(ctx, step, row, i)))),
    data.thresholds_only
      ? null
      : h(
          'div',
          { class: 'row' },
          actionButton(ctx, {
            label: ui.add_row,
            id: 'ws-add',
            disabled: full || ctx.readOnly,
            onClick: () => {
              changeRows(ctx, step, [...rows, { ...BLANK_ROW }]);
              focusSoon(`row-${rows.length + 1}-requirement`);
            },
          }),
          full ? h('span', { class: 'hint', id: 'ws-full' }, ui.add_row_full) : null,
        ),
    h('div', { class: 'row' }, saveButton(ctx, step, ui, [['rows', rowsKey(step), data.rows]], unsaved), savedLine(ui, unsaved, data.saved)),
  );
}

function renderNotes(step) {
  const { data, ui } = step;
  if (!data.thresholds_only) return null;
  return section(
    'notes',
    ui.notes_heading,
    data.notes.length
      ? h('div', { class: 'callout callout-attn', id: 'threshold-notes', role: 'status' }, h('ul', { class: 'plain-list' }, data.notes.map((n) => h('li', { key: `note-${n.row}` }, n.text))))
      : h('p', { class: 'hint', id: 'threshold-notes', role: 'status' }, ui.notes_none),
  );
}

function renderTicks(ctx, step) {
  const { data, ui } = step;
  return section(
    'ticks',
    ui.ticks_heading,
    h(
      'div',
      { class: 'ws-ticks', role: 'group', 'aria-label': ui.ticks_heading },
      data.ticks.map((t) =>
        h(
          'label',
          { class: 'check-row', key: t.id },
          h('input', {
            type: 'checkbox',
            id: `tick-${t.id}`,
            checked: ctx.draft(tickKey(step, t.id), t.checked),
            disabled: ctx.readOnly,
            onChange: (e) => {
              ctx.setDraft(tickKey(step, t.id), e.target.checked);
              ctx.queueSave(step.id);
              ctx.flushSave(step.id);
              ctx.rerender();
            },
          }),
          h('span', null, t.label),
        ),
      ),
    ),
  );
}

function renderPart1(data, ui) {
  const mine = data.part1;
  if (!mine) return null;
  const words = { yes: ui.part1_yes, no: ui.part1_no };
  return section(
    'part1',
    ui.part1_heading,
    h('p', { class: 'hint' }, ui.part1_note),
    h(
      'div',
      { class: 'callout', id: 'part1-panel' },
      h('strong', { class: 'block' }, ui.part1_marks_label),
      h(
        'ul',
        { class: 'plain-list' },
        mine.marks.map((m) => h('li', { key: m.id }, `${m.label}: `, h('strong', null, words[m.answer] || ui.part1_unmarked))),
      ),
      mine.gap.trim() ? [h('strong', { class: 'block', key: 'gap-label' }, ui.part1_gap_label), h('p', { id: 'part1-gap', key: 'gap' }, mine.gap)] : null,
    ),
  );
}

function renderTable(ctx, step) {
  const { data, ui } = step;
  return [
    data.scenario ? renderScenario({ scenario: data.scenario, notes: data.rough_notes }, ui) : null,
    renderPart1(data, ui),
    renderRows(ctx, step),
    renderNotes(step),
    renderTicks(ctx, step),
  ];
}

function collectTable(step, drafts) {
  const checks = {};
  const keys = [];
  for (const tick of step.data.ticks) {
    const key = tickKey(step, tick.id);
    if (drafts.has(key)) {
      checks[tick.id] = drafts.get(key);
      keys.push(key);
    }
  }
  return keys.length ? { data: { checks }, keys } : { data: {}, keys: [] };
}

// ---- the test case file: test-file and reference -----------------------------

function buildRow(ctx, step) {
  const { data, ui } = step;
  const key = textKey(step);
  return [
    h(
      'div',
      { class: 'row', key: 'build-row' },
      actionButton(ctx, {
        label: ui.build,
        id: 'file-build',
        busyKey: `part-build-${step.id}`,
        busyLabel: ui.building,
        disabled: !data.has_worksheet || ctx.readOnly,
        onClick: () =>
          ctx.actions.buildFile(step.id, {
            hasText: Boolean(ctx.draft(key, data.text).trim()),
            clear: [key],
            ask: () => confirmDialog({ title: ui.confirm_title, body: ui.confirm_body, confirmLabel: ui.confirm_confirm, cancelLabel: ui.confirm_cancel }),
          }),
      }),
    ),
    h('p', { class: 'hint', id: 'build-hint', key: 'build-hint' }, data.has_worksheet ? ui.build_hint : ui.build_empty_hint),
  ];
}

function renderFileEditor(ctx, step, withBuild) {
  const { data, ui } = step;
  const key = textKey(step);
  const unsaved = ctx.hasDraft(key);
  return section(
    'editor',
    ui.editor_heading,
    withBuild ? buildRow(ctx, step) : null,
    textField(ctx, {
      id: 'file-editor',
      label: ui.editor_label,
      hint: ui.editor_hint,
      draftKey: key,
      value: data.text,
      multiline: true,
      rows: 18,
      mono: true,
      disabled: ctx.readOnly,
    }),
    h('div', { class: 'row' }, saveButton(ctx, step, ui, [['text', key, data.text]], unsaved), savedLine(ui, unsaved, data.saved)),
  );
}

function findingList(id, tone, heading, items) {
  return h(
    'div',
    { class: `callout callout-${tone}`, id, key: id },
    h('h3', null, heading),
    h('ul', { class: 'plain-list' }, items.map((f, i) => h('li', { key: `${f.code}-${f.criterion || ''}-${i}` }, f.message))),
  );
}

function renderFindings(step) {
  const { data, ui } = step;
  const { blocking, notes } = data.findings;
  let body;
  if (!data.saved) body = h('p', { class: 'hint', id: 'findings-empty' }, ui.file_empty);
  else if (!blocking.length && !notes.length) body = h('p', { class: 'hint', id: 'findings-none' }, ui.findings_none);
  else {
    body = [
      blocking.length ? findingList('findings-blocking', 'bad', ui.blocking_heading, blocking) : null,
      notes.length ? findingList('findings-notes', 'attn', ui.notes_heading, notes) : null,
    ];
  }
  return section('findings', ui.findings_heading, h('div', { id: 'file-findings', role: 'status' }, body));
}

function renderTestFile(ctx, step) {
  const { ui } = step;
  return [renderFileEditor(ctx, step, true), h('p', { class: 'callout', id: 'lists-note', key: 'lists-note' }, ui.lists_note), renderFindings(step)];
}

// ---- the reference comparison -------------------------------------------------

const chosenOf = (ctx, step, id) => ctx.draft(choiceKey(step, id), step.data.choices[id] || '');

function referenceCard(ctx, step, criterion) {
  const { data, ui } = step;
  const current = chosenOf(ctx, step, criterion.id);
  return h(
    'article',
    { class: 'ref-card', id: `ref-${criterion.id}`, key: `ref-${criterion.id}` },
    h('h3', null, h('span', { class: 'crit-id' }, criterion.id), ' ', criterion.name),
    h('dl', { class: 'ref-facts' }, fact(ui.requirement_label, criterion.requirement, 'requirement'), fact(ui.type_label, criterion.type, 'type'), fact(ui.threshold_label, criterion.threshold, 'threshold')),
    h(
      'fieldset',
      { class: 'field ref-choices', id: `ref-${criterion.id}-choices` },
      h('legend', { class: 'field-label' }, fmt(ui.choice_legend, { name: criterion.name })),
      h(
        'div',
        { class: 'ref-options' },
        data.options.map((option) =>
          h(
            'label',
            { class: 'radio-card', key: option.id },
            h('input', {
              type: 'radio',
              name: `${step.id}-${criterion.id}`,
              value: option.id,
              checked: current === option.id,
              disabled: ctx.readOnly,
              onChange: () => {
                ctx.setDraft(choiceKey(step, criterion.id), option.id);
                ctx.queueSave(step.id);
                ctx.flushSave(step.id);
                ctx.rerender();
              },
            }),
            h('span', null, option.label),
          ),
        ),
      ),
    ),
  );
}

function renderReference(ctx, step) {
  const { data, ui } = step;
  if (!data.revealed) return h('p', { class: 'callout callout-attn', id: 'reference-locked' }, ui.locked_note);
  const done = data.reference.filter((r) => chosenOf(ctx, step, r.id)).length;
  return [
    h('p', { class: 'callout', id: 'one-good-answer', key: 'one-good-answer' }, ui.one_good_answer),
    section(
      'mine',
      ui.mine_heading,
      data.mine.length
        ? h(
            'ul',
            { class: 'ref-mine', id: 'mine-list' },
            data.mine.map((c) =>
              h('li', { key: c.id }, h('span', { class: 'crit-id' }, c.id), ' ', h('strong', null, c.name), c.threshold ? h('span', { class: 'hint block' }, `${ui.threshold_label}: ${c.threshold}`) : null),
            ),
          )
        : h('p', { class: 'hint', id: 'mine-empty' }, ui.mine_empty),
    ),
    section(
      'reference',
      ui.reference_heading,
      h('p', { class: 'hint', id: 'ref-progress', role: 'status' }, fmt(ui.chosen, { done, total: data.reference.length })),
      data.reference.map((r) => referenceCard(ctx, step, r)),
    ),
    data.lists.length
      ? section('lists', ui.lists_heading, h('p', { class: 'hint', id: 'reference-lists-note' }, ui.lists_note), plainText('reference-lists', data.lists.join('\n'), ui.lists_heading))
      : null,
    renderFileEditor(ctx, step, false),
    renderFindings(step),
  ];
}

function collectReference(step, drafts) {
  const choices = {};
  const keys = [];
  for (const criterion of step.data.reference) {
    const key = choiceKey(step, criterion.id);
    if (drafts.has(key)) {
      choices[criterion.id] = drafts.get(key);
      keys.push(key);
    }
  }
  return keys.length ? { data: { choices }, keys } : { data: {}, keys: [] };
}

export const CRITERIA_STEP_PANELS = {
  draft: { render: renderTable, collect: collectTable },
  thresholds: { render: renderTable, collect: collectTable },
  'test-file': { render: renderTestFile },
  reference: { render: renderReference, collect: collectReference },
};
