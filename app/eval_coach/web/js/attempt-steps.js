// The panels of Part 4's steps: the starting-point choice, the known-good answer, and for each round the
// hypothesis, the prompt edit, the five-answer measure and the keep-or-undo decision.
// Every word comes from the step's content (step.ui and step.data), and everything the participant or the AI wrote
// is placed in text nodes, never as markup. The panels use the existing components and styles only.

import { h } from './dom.js';
import { fmt } from './lessons.js';
import { plainText } from './part-steps.js';
import { actionButton, section, textField } from './ui.js';

const ROUNDS = [1, 2, 3];
const NONE = '—';

const draftKey = (step, name) => `${step.id}.${name}`;
const saveBusyKey = (step) => `part-save-${step.id}`;

function practiceNote(data) {
  return data.practice_only
    ? h('p', { class: 'callout callout-attn', id: 'p4-practice-only', key: 'practice-only', role: 'status' }, data.practice_only)
    : null;
}

function tag(kind, text, id) {
  return h('span', { class: `verdict v-${kind}`, id }, text);
}

function savedStatus(ui, unsaved, saved) {
  return h('span', { class: 'hint', id: 'p4-save-status', role: 'status' }, unsaved ? ui.unsaved : saved ? ui.saved : '');
}

// A text box with its own Save button. `field` is the name the server reads the text under.
function saveRow(ctx, step, { id, field, label, hint, value, rows, mono, disabled, canSave, saved }) {
  const key = draftKey(step, field);
  const unsaved = ctx.hasDraft(key);
  const ui = step.ui;
  return [
    textField(ctx, { id, label, hint, draftKey: key, value, multiline: true, rows, mono, disabled }),
    h(
      'div',
      { class: 'row', key: `${id}-row` },
      actionButton(ctx, {
        label: ui.save,
        id: `${id}-save`,
        busyKey: saveBusyKey(step),
        busyLabel: ui.saving,
        kind: 'primary',
        disabled: disabled || !canSave(unsaved, ctx.draft(key, value || '')),
        onClick: () => {
          const text = ctx.draft(key, value || '');
          ctx.actions.partSave(step.id, { action: 'save', [field]: text }, [[key, text]]);
        },
      }),
      ui.saved ? savedStatus(ui, unsaved, saved) : null,
    ),
  ];
}

function rerunBlock(ctx, step, data) {
  if (!data.rerun_needed) return null;
  const ui = step.ui;
  return h(
    'div',
    { class: 'callout callout-attn', id: 'p4-rerun', key: 'rerun', role: 'status' },
    ui.rerun_heading ? h('strong', { class: 'block' }, ui.rerun_heading) : null,
    h('p', null, data.rerun_text),
    h(
      'div',
      { class: 'row' },
      actionButton(ctx, {
        label: ui.rerun_button,
        id: 'p4-rerun-button',
        busyKey: saveBusyKey(step),
        busyLabel: ui.rerunning,
        kind: 'primary',
        disabled: ctx.readOnly,
        onClick: () => ctx.actions.partSave(step.id, { action: 'rerun' }, []),
      }),
    ),
  );
}

// ---- starting-point -------------------------------------------------------

function renderChoose(ctx, step) {
  const { data, ui } = step;
  const key = 'p4-start';
  const picked = ctx.draft(key, data.chosen || '');
  const editable = !data.fixed;
  const blurbs = { own: ui.own_blurb, practice: ui.practice_blurb };
  const useLabel = picked === 'own' ? ui.use_own : ui.use_practice;
  return [
    practiceNote(data),
    data.little_gap ? h('p', { class: 'callout callout-attn', id: 'p4-little-gap', key: 'little-gap' }, data.little_gap) : null,
    section(
      'choices',
      ui.heading,
      h(
        'fieldset',
        { class: 'field', id: 'p4-start-choices' },
        h('legend', { class: 'field-label' }, ui.heading),
        data.choices.map((choice) =>
          h(
            'label',
            { class: 'radio-card', key: choice.id, id: `p4-start-${choice.id}-card` },
            h('input', {
              type: 'radio',
              name: 'p4-start',
              id: `p4-start-${choice.id}`,
              value: choice.id,
              checked: picked === choice.id,
              disabled: !choice.available || !editable,
              onChange: () => {
                ctx.setDraft(key, choice.id);
                ctx.rerender();
              },
            }),
            h(
              'span',
              null,
              h('strong', { class: 'block' }, choice.label),
              h('span', { class: 'hint block' }, blurbs[choice.id]),
              choice.note ? h('span', { class: 'hint block', id: `p4-start-${choice.id}-note` }, choice.note) : null,
              !choice.available ? h('span', { class: 'bad-text block', id: `p4-start-${choice.id}-reason` }, ui.unavailable, ': ', choice.reason) : null,
              data.chosen === choice.id ? tag('P', ui.chosen, `p4-start-${choice.id}-chosen`) : null,
            ),
          ),
        ),
      ),
      data.fixed_note ? h('p', { class: 'hint', id: 'p4-start-fixed', key: 'fixed' }, data.fixed_note) : null,
      editable && picked && picked !== data.chosen
        ? h(
            'div',
            { class: 'row', key: 'start-row' },
            actionButton(ctx, {
              label: useLabel,
              id: 'p4-start-use',
              busyKey: saveBusyKey(step),
              busyLabel: ui.saving,
              kind: 'primary',
              onClick: () => ctx.actions.partSave(step.id, { action: 'choose', choice: picked }, [[key, picked]]),
            }),
          )
        : null,
    ),
  ];
}

// ---- known-good -----------------------------------------------------------

function renderKnownGood(ctx, step) {
  const { data, ui } = step;
  const result = data.result;
  return [
    practiceNote(data),
    section(
      'rules',
      ui.rules_heading,
      data.rules_name ? h('p', { class: 'hint' }, data.rules_name) : null,
      plainText('p4-rules', data.rules, ui.rules_heading),
    ),
    rerunBlock(ctx, step, data),
    section(
      'answer',
      ui.heading,
      saveRow(ctx, step, {
        id: 'p4-answer',
        field: 'text',
        label: ui.answer_label,
        hint: ui.answer_hint,
        value: data.answer,
        rows: 8,
        disabled: ctx.readOnly,
        canSave: (unsaved, text) => Boolean(text.trim()) && (unsaved || !result || result.stale),
      }),
    ),
    result
      ? section(
          'result',
          ui.result_heading,
          result.stale ? h('p', { class: 'callout callout-attn', id: 'p4-result-stale', role: 'status' }, ui.stale) : null,
          h('p', { class: 'score-line', id: 'p4-result', role: 'status' }, result.text),
          result.next_step ? h('p', { class: 'hint', id: 'p4-result-next' }, result.next_step) : null,
        )
      : null,
  ];
}

// ---- hypothesis -----------------------------------------------------------

function ruleItem(ui, rule) {
  const status = rule.not_checked
    ? tag('NC', ui.not_checked)
    : rule.failing
      ? tag('F', ui.needs_work)
      : tag('P', ui.passes_all);
  return h(
    'li',
    { key: rule.id, id: `p4-start-rule-${rule.id}`, 'data-failing': rule.failing ? 'true' : 'false' },
    h('span', { class: 'crit-id' }, rule.id),
    ' ',
    rule.name,
    ' ',
    rule.not_checked ? null : h('span', { class: 'hint' }, fmt(ui.rule_count, { passes: rule.passes, checked: rule.checked })),
    ' ',
    status,
  );
}

function renderHypothesis(ctx, step) {
  const { data, ui } = step;
  return [
    practiceNote(data),
    section(
      'start',
      ui.rules_heading,
      h('p', { class: 'hint', id: 'p4-start-note' }, data.start === 0 ? ui.start_iteration_0 : fmt(ui.start_kept, { n: data.start })),
      data.start_overall ? h('p', { class: 'score-line', id: 'p4-start-overall' }, fmt(ui.overall, data.start_overall)) : null,
      h('ul', { class: 'plain-list', id: 'p4-start-rules' }, data.start_rules.map((rule) => ruleItem(ui, rule))),
    ),
    section(
      'hypothesis',
      ui.label,
      data.locked && data.locked_note ? h('p', { class: 'callout callout-attn', id: 'p4-locked-note', role: 'status' }, data.locked_note) : null,
      saveRow(ctx, step, {
        id: 'p4-hypothesis',
        field: 'text',
        label: ui.label,
        hint: ui.hint,
        value: data.hypothesis,
        rows: 5,
        disabled: Boolean(data.locked),
        canSave: (unsaved, text) => unsaved && Boolean(text.trim()),
      }),
    ),
  ];
}

// ---- edit -----------------------------------------------------------------

function renderEdit(ctx, step) {
  const { data, ui } = step;
  return [
    practiceNote(data),
    section('hypothesis', ui.hypothesis_heading, plainText('p4-edit-hypothesis', data.hypothesis, ui.hypothesis_heading)),
    section('start-prompt', ui.start_heading, plainText('p4-start-prompt', data.start_prompt, ui.start_heading)),
    section(
      'editor',
      ui.editor_heading,
      data.locked && data.locked_note ? h('p', { class: 'callout callout-attn', id: 'p4-locked-note', role: 'status' }, data.locked_note) : null,
      saveRow(ctx, step, {
        id: 'p4-prompt',
        field: 'prompt',
        label: ui.editor_label,
        value: data.prompt,
        rows: 12,
        mono: true,
        disabled: Boolean(data.locked),
        canSave: (unsaved, text) => unsaved && Boolean(text.trim()),
      }),
      h('p', { class: 'hint', id: 'p4-edit-state', role: 'status' }, data.changed ? ui.changed_note : ui.same_note),
    ),
  ];
}

// ---- measure and decide: the five answers and the per-rule table ---------------

function countText(ui, cell) {
  if (!cell) return NONE;
  if (cell.not_checked) return ui.not_checked;
  return fmt(ui.count, { passes: cell.passes, checked: cell.checked });
}

function ruleRow(ui, rule) {
  const flagged = rule.lost || rule.change === 'down';
  return h(
    'tr',
    { key: rule.id, id: `p4-rule-${rule.id}`, 'data-change': rule.change || 'none' },
    h('td', null, h('span', { class: 'crit-id' }, rule.id), ' ', rule.name),
    h('td', { id: `p4-rule-${rule.id}-before` }, countText(ui, rule.before)),
    h('td', { id: `p4-rule-${rule.id}-after` }, countText(ui, rule.after)),
    h(
      'td',
      { class: flagged ? 'surprise' : null, id: `p4-rule-${rule.id}-change` },
      rule.change ? ui[rule.change] : NONE,
      rule.lost ? [' ', tag('NC', ui.lost)] : null,
    ),
  );
}

function renderResults(step, attempt) {
  const { ui } = step;
  const compare = attempt && attempt.compare;
  if (!compare) return null;
  const five = attempt.five_answers;
  const coverage = attempt.coverage;
  return section(
    'results',
    ui.results_heading,
    attempt.stale && attempt.stale_text
      ? h('p', { class: 'callout callout-attn', id: 'p4-stale', role: 'status' }, fmt(ui.stale, { what: attempt.stale_text }))
      : null,
    h(
      'div',
      { class: 'table-scroll' },
      h(
        'table',
        { class: 'grid', id: 'p4-results' },
        h(
          'thead',
          null,
          h(
            'tr',
            null,
            h('th', { scope: 'col' }, ui.rule_col),
            h('th', { scope: 'col' }, ui.before_col),
            h('th', { scope: 'col' }, ui.after_col),
            h('th', { scope: 'col' }, ui.change_col),
          ),
        ),
        h('tbody', null, compare.rules.map((rule) => ruleRow(ui, rule))),
      ),
    ),
    h(
      'p',
      { class: 'score-line', id: 'p4-overall' },
      h('span', { id: 'p4-overall-before' }, fmt(ui.overall_before, compare.before)),
      ' · ',
      h('span', { id: 'p4-overall-after' }, fmt(ui.overall_after, compare.after)),
    ),
    five ? h('p', { class: 'score-line', id: 'p4-five' }, five.text) : null,
    five && five.next_step ? h('p', { class: 'hint', id: 'p4-five-next' }, five.next_step) : null,
    coverage && coverage.changed && coverage.text ? h('p', { class: 'callout callout-attn', id: 'p4-coverage', role: 'status' }, coverage.text) : null,
  );
}

function renderMeasure(ctx, step) {
  const { data, ui } = step;
  return [
    practiceNote(data),
    rerunBlock(ctx, step, data),
    section(
      'runs',
      ui.runs_heading,
      h(
        'ul',
        { class: 'plain-list', id: 'p4-runs' },
        data.runs.map((run) =>
          h(
            'li',
            { key: run.n, id: `p4-run-${run.n}`, 'data-done': run.done ? 'true' : 'false' },
            `${fmt(ui.run_label, { n: run.n })}: `,
            run.done ? fmt(ui.run_saved, { words: run.words }) : ui.run_empty,
          ),
        ),
      ),
      data.model ? h('p', { class: 'hint', id: 'p4-model' }, fmt(ui.model_label, { model: data.model })) : null,
      data.model_note ? h('p', { class: 'callout callout-attn', id: 'p4-model-note', role: 'status' }, data.model_note) : null,
      h(
        'div',
        { class: 'row', key: 'score-row' },
        actionButton(ctx, {
          label: ui.score,
          id: 'p4-score',
          busyKey: saveBusyKey(step),
          busyLabel: ui.scoring,
          kind: 'primary',
          disabled: ctx.readOnly || !data.can_score,
          onClick: () => ctx.actions.partSave(step.id, { action: 'score' }, []),
        }),
      ),
    ),
    renderResults(step, data.attempt),
  ];
}

function renderDecide(ctx, step) {
  const { data, ui } = step;
  const attempt = data.attempt;
  const decide = (choice) => ctx.actions.partSave(step.id, { action: 'decide', choice }, []);
  const reflection = data.reflection;
  const reflectionKey = draftKey(step, 'reflection');
  return [
    practiceNote(data),
    rerunBlock(ctx, step, data),
    renderResults(step, attempt),
    section(
      'decision',
      ui.decision_heading,
      data.decided
        ? h('p', { class: 'callout callout-good', id: 'p4-decision-note', role: 'status', 'data-decision': data.decision }, data.decision === 'kept' ? ui.kept_note : ui.undone_note)
        : [
            h('p', { class: 'hint', id: 'p4-pending-note', key: 'pending' }, ui.pending_note),
            h(
              'div',
              { class: 'row', key: 'decide-row' },
              actionButton(ctx, {
                label: ui.keep,
                id: 'p4-keep',
                busyKey: saveBusyKey(step),
                busyLabel: ui.deciding,
                kind: 'primary',
                disabled: ctx.readOnly || !data.can_decide,
                onClick: () => decide('keep'),
              }),
              actionButton(ctx, {
                label: ui.undo,
                id: 'p4-undo',
                busyKey: saveBusyKey(step),
                busyLabel: ui.deciding,
                disabled: ctx.readOnly || !data.can_decide,
                onClick: () => decide('undo'),
              }),
            ),
          ],
    ),
    data.decided && attempt && attempt.evidence
      ? section('evidence', ui.evidence_heading, h('p', { class: 'score-line', id: 'p4-evidence' }, attempt.evidence.text))
      : null,
    data.decided
      ? section('log', ui.log_heading, h('p', { class: 'hint', id: 'p4-log-note' }, fmt(ui.log_note, { log_file: data.log_file })))
      : null,
    reflection
      ? section(
          'reflection',
          reflection.heading,
          textField(ctx, {
            id: 'p4-reflection',
            label: reflection.prompt,
            hint: reflection.hint,
            draftKey: reflectionKey,
            value: reflection.text,
            saveStep: step.id,
            multiline: true,
            rows: 3,
          }),
        )
      : null,
  ];
}

function collectDecide(step, drafts) {
  const key = draftKey(step, 'reflection');
  if (!drafts.has(key)) return { data: {}, keys: [] };
  return { data: { action: 'reflect', text: drafts.get(key) }, keys: [key] };
}

export const ATTEMPT_STEP_PANELS = {
  'starting-point': { render: renderChoose },
  'known-good': { render: renderKnownGood },
  ...Object.fromEntries(
    ROUNDS.flatMap((n) => [
      [`hypothesis-${n}`, { render: renderHypothesis }],
      [`edit-${n}`, { render: renderEdit }],
      [`measure-${n}`, { render: renderMeasure }],
      [`decide-${n}`, { render: renderDecide, collect: collectDecide }],
    ]),
  ),
};
