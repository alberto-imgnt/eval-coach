// The panels of Part 1's three step kinds: a prompt editor with one CLI run (write_and_run), a score form with an
// optional side-by-side compare (score_form) and a pair of texts with no CLI (write_pair).
// Every word comes from the step's content (step.ui and step.data), and everything the participant or the CLI
// wrote is placed in text nodes, never as markup.

import { confirmDialog } from './dialog.js';
import { h } from './dom.js';
import { fmt } from './lessons.js';
import { actionButton, section, textField } from './ui.js';

const YES_NO = ['yes', 'no'];

const draftKey = (step, name) => `${step.id}.${name}`;

// ---- shared pieces ------------------------------------------------------

export function plainText(id, text, label) {
  return h('pre', { class: 'mono-block part-text', id, tabindex: '0', role: 'region', 'aria-label': label }, text);
}

export function savedLine(ui, unsaved, saved) {
  return h('span', { class: 'hint', role: 'status', id: 'part-save-status' }, unsaved ? ui.unsaved : saved ? ui.saved : '');
}

export function saveButton(ctx, step, ui, entries, unsaved) {
  // entries: [[field, draft key, current value]] for the texts this Save writes.
  const sent = entries.filter(([, key]) => ctx.hasDraft(key));
  return actionButton(ctx, {
    label: ui.save,
    id: 'part-save',
    busyKey: `part-save-${step.id}`,
    busyLabel: ui.saving,
    kind: 'primary',
    disabled: !unsaved || ctx.readOnly,
    onClick: () => {
      const data = {};
      for (const [field, key] of sent) data[field] = ctx.draft(key, '');
      ctx.actions.partSave(step.id, data, sent.map(([, key]) => [key, ctx.draft(key, '')]));
    },
  });
}

// Which of a step's texts have changes that are not saved. The Check button asks before it runs.
export function unsavedTexts(step, drafts) {
  const names = step.kind === 'write_pair' ? ['before', 'after', 'labels'] : step.kind === 'write_and_run' ? ['prompt'] : [];
  return names.some((name) => drafts.has(draftKey(step, name)));
}

// ---- write_and_run: cold and rewrite ----------------------------------------

export function renderScenario(data, ui) {
  const card = data.scenario;
  if (!card) return null;
  return section(
    'scenario',
    ui.scenario_heading,
    h(
      'div',
      { class: 'callout scenario-card', id: 'scenario-card' },
      h('p', null, card.intro),
      data.notes
        ? [
            h('strong', { class: 'block', key: 'notes-heading' }, ui.notes_heading),
            h('p', { class: 'hint', key: 'notes-hint' }, ui.notes_hint),
            h('div', { key: 'notes-text' }, plainText('scenario-notes', data.notes, ui.notes_heading)),
          ]
        : null,
      h('strong', { class: 'block' }, ui.requirements_heading),
      h('ul', { class: 'plain-list' }, card.requirements.map((r) => h('li', { key: r.id }, r.label))),
      h('p', null, card.task),
    ),
  );
}

function renderLabelChoice(ctx, step) {
  const { data, ui } = step;
  const current = ctx.draft(draftKey(step, 'framework'), data.framework);
  return h(
    'fieldset',
    { class: 'field', id: 'label-sets', key: 'label-sets' },
    h('legend', { class: 'field-label' }, ui.labels_heading),
    h('p', { class: 'hint' }, ui.labels_hint),
    data.labels.map((label) =>
      h(
        'label',
        { class: 'radio-card', key: label.id },
        h('input', {
          type: 'radio',
          name: 'label-set',
          value: label.id,
          checked: current === label.id,
          disabled: ctx.readOnly,
          onChange: () => {
            ctx.setDraft(draftKey(step, 'framework'), label.id);
            ctx.queueSave(step.id);
            ctx.flushSave(step.id);
            ctx.rerender();
          },
        }),
        h('span', null, h('strong', { class: 'block' }, label.label), h('span', { class: 'hint block' }, label.description)),
      ),
    ),
  );
}

async function insertLabels(ctx, step) {
  const { data, ui } = step;
  const chosen = ctx.draft(draftKey(step, 'framework'), data.framework);
  const label = data.labels.find((l) => l.id === chosen);
  if (!label) return;
  const key = draftKey(step, 'prompt');
  const text = ctx.draft(key, data.prompt);
  if (text.trim() && text.trim() !== label.skeleton.trim()) {
    const ok = await confirmDialog({ title: ui.insert_confirm_title, body: ui.insert_confirm_body, confirmLabel: ui.insert_confirm, cancelLabel: ui.insert_cancel });
    if (!ok) return;
  }
  ctx.setDraft(key, label.skeleton);
  ctx.rerender();
  window.requestAnimationFrame(() => {
    const editor = document.getElementById('prompt-editor');
    if (editor) editor.focus();
  });
}

function renderEditor(ctx, step) {
  const { data, ui } = step;
  const key = draftKey(step, 'prompt');
  const unsaved = ctx.hasDraft(key);
  const hasLabels = Boolean(data.labels);
  const chosen = hasLabels ? ctx.draft(draftKey(step, 'framework'), data.framework) : null;
  return section(
    'editor',
    ui.editor_heading,
    hasLabels ? renderLabelChoice(ctx, step) : null,
    textField(ctx, {
      id: 'prompt-editor',
      label: ui.editor_label,
      hint: ui.editor_hint,
      draftKey: key,
      value: data.prompt,
      multiline: true,
      rows: 10,
      disabled: ctx.readOnly,
    }),
    h(
      'div',
      { class: 'row' },
      hasLabels
        ? actionButton(ctx, {
            label: ui.insert_labels,
            id: 'insert-labels',
            disabled: !chosen || ctx.readOnly,
            onClick: () => insertLabels(ctx, step),
          })
        : null,
      saveButton(ctx, step, ui, [['prompt', key, data.prompt]], unsaved),
      savedLine(ui, unsaved, data.prompt_saved),
    ),
    hasLabels && !chosen && !ctx.readOnly ? h('p', { class: 'hint', id: 'insert-hint' }, ui.insert_need_choice) : null,
  );
}

function renderRunPanel(ctx, step) {
  const { data, ui } = step;
  return [
    renderScenario(data, ui),
    data.cold_prompt
      ? h('details', { class: 'raw', key: 'cold-prompt', id: 'cold-prompt' }, h('summary', null, ui.cold_heading), plainText('cold-prompt-text', data.cold_prompt, ui.cold_heading))
      : null,
    renderEditor(ctx, step),
    section(
      'preview',
      ui.preview_heading,
      h('p', { class: 'hint' }, ui.preview_note),
      data.prompt_saved ? plainText('run-preview', data.preview, ui.preview_heading) : h('p', { class: 'hint', id: 'run-preview-empty' }, ui.preview_empty),
    ),
    section(
      'model',
      null,
      textField(ctx, {
        id: 'model-name',
        label: ui.model_label,
        hint: ui.model_hint,
        draftKey: draftKey(step, 'model_name'),
        value: data.model_name,
        saveStep: step.id,
        disabled: ctx.readOnly,
      }),
      data.model_note
        ? h('div', { class: 'callout callout-attn', id: 'model-note', role: 'status' }, h('strong', { class: 'block' }, ui.model_note_heading), data.model_note)
        : null,
    ),
    section(
      'output',
      ui.output_heading,
      data.output
        ? [h('p', { class: 'hint' }, ui.output_note), plainText('run-output', data.output, ui.output_heading)]
        : h('p', { class: 'hint', id: 'run-output-empty' }, ui.output_empty),
    ),
  ];
}

function collectRunPanel(step, drafts) {
  const data = {};
  const keys = [];
  for (const field of ['model_name', 'framework']) {
    const key = draftKey(step, field);
    if (drafts.has(key)) {
      data[field] = drafts.get(key);
      keys.push(key);
    }
  }
  return { data, keys };
}

// ---- score_form: score and rescore ------------------------------------------

const answerKey = (step, id) => draftKey(step, `answer.${id}`);

function currentAnswers(ctx, step) {
  const answers = {};
  for (const row of step.data.rows) answers[row.id] = ctx.draft(answerKey(step, row.id), row.answer);
  return answers;
}

function renderRow(ctx, step, row, answers) {
  const { ui } = step;
  const name = `${step.id}-${row.id}`;
  return h(
    'fieldset',
    { class: 'case-row score-row', key: `row-${row.id}`, id: `score-row-${row.id}` },
    h('legend', null, row.label),
    h(
      'div',
      { class: 'seg' },
      YES_NO.map((value) =>
        h(
          'label',
          { class: `seg-opt ${value === 'yes' ? 'seg-P' : 'seg-F'}`, key: value },
          h('input', {
            type: 'radio',
            name,
            value,
            checked: answers[row.id] === value,
            disabled: ctx.readOnly,
            onChange: () => {
              ctx.setDraft(answerKey(step, row.id), value);
              ctx.queueSave(step.id);
              ctx.flushSave(step.id);
              ctx.rerender();
            },
          }),
          h('span', null, ui[value]),
        ),
      ),
    ),
  );
}

function scoreLine(ui, answers, rows) {
  const marked = rows.map((r) => answers[r.id]);
  const done = marked.every((m) => YES_NO.includes(m));
  const yes = marked.filter((m) => m === 'yes').length;
  return h(
    'p',
    { class: 'score-line', id: 'score-line', role: 'status' },
    done ? [`${ui.score_label} `, h('strong', null, fmt(ui.score_text, { yes, total: rows.length }))] : ui.score_pending,
  );
}

function renderInPrompt(ctx, step) {
  const { data, ui } = step;
  const key = draftKey(step, 'in_prompt');
  const current = ctx.draft(key, data.in_prompt);
  return h(
    'fieldset',
    { class: 'field', id: 'in-prompt', key: 'in-prompt' },
    h('legend', { class: 'field-label' }, ui.in_prompt_label),
    h(
      'div',
      { class: 'seg' },
      ui.in_prompt_options.map((option) =>
        h(
          'label',
          { class: 'seg-opt', key: option.id },
          h('input', {
            type: 'radio',
            name: `${step.id}-in-prompt`,
            value: option.id,
            checked: current === option.id,
            disabled: ctx.readOnly,
            onChange: () => {
              ctx.setDraft(key, option.id);
              ctx.queueSave(step.id);
              ctx.flushSave(step.id);
              ctx.rerender();
            },
          }),
          h('span', null, option.label),
        ),
      ),
    ),
  );
}

function compareSide(words, side, heading, id) {
  return h(
    'div',
    { class: 'compare-col', id, key: id },
    h('h4', null, heading),
    h('p', { class: 'hint' }, words.prompt_label),
    plainText(`${id}-prompt`, side.prompt, `${heading}: ${words.prompt_label}`),
    h('p', { class: 'hint' }, words.output_label),
    plainText(`${id}-output`, side.output, `${heading}: ${words.output_label}`),
    h('p', { class: 'compare-score' }, `${words.score_label}: `, h('strong', null, side.score ? side.score.text : words.score_empty)),
  );
}

function renderCompare(data) {
  const { compare } = data;
  if (!compare) return null;
  const { words } = compare;
  return section(
    'compare',
    words.heading,
    h('div', { class: 'compare compare-two', id: 'compare' }, compareSide(words, compare.first, words.first_heading, 'compare-first'), compareSide(words, compare.second, words.second_heading, 'compare-second')),
    compare.change_text ? h('p', { class: 'score-line', id: 'compare-change', role: 'status' }, compare.change_text) : null,
    h(
      'div',
      { class: 'callout', id: 'compare-notes' },
      compare.notes.map((note, i) => h('p', { key: `note-${i}` }, note)),
    ),
  );
}

function renderScoreForm(ctx, step) {
  const { data, ui } = step;
  const answers = currentAnswers(ctx, step);
  const allYes = data.rows.every((r) => answers[r.id] === 'yes');
  const gapKey = draftKey(step, 'gap');
  return [
    section(
      'answer',
      ui.output_heading,
      data.output ? plainText('score-output', data.output, ui.output_heading) : h('p', { class: 'hint' }, ui.output_empty),
    ),
    section('rows', ui.rows_heading, data.rows.map((row) => renderRow(ctx, step, row, answers)), scoreLine(ui, answers, data.rows)),
    renderCompare(data),
    data.fields.includes('gap')
      ? textField(ctx, {
          id: 'score-gap',
          label: allYes ? ui.gap_label_all_yes : ui.gap_label,
          draftKey: gapKey,
          value: data.gap,
          saveStep: step.id,
          multiline: true,
          rows: 3,
          disabled: ctx.readOnly,
        })
      : null,
    data.fields.includes('in_prompt') ? renderInPrompt(ctx, step) : null,
    data.reflections.length
      ? section(
          'reflections',
          ui.reflections_heading,
          data.reflections.map((r) =>
            textField(ctx, {
              id: `reflection-${r.id}`,
              label: r.label,
              draftKey: draftKey(step, `reflection.${r.id}`),
              value: r.value,
              saveStep: step.id,
              multiline: true,
              rows: 3,
              disabled: ctx.readOnly,
            }),
          ),
        )
      : null,
  ];
}

function collectScoreForm(step, drafts) {
  const data = {};
  const keys = [];
  const answers = {};
  for (const row of step.data.rows) {
    const key = answerKey(step, row.id);
    if (drafts.has(key)) {
      answers[row.id] = drafts.get(key);
      keys.push(key);
    }
  }
  if (keys.length) data.answers = answers;
  for (const field of ['gap', 'in_prompt']) {
    const key = draftKey(step, field);
    if (drafts.has(key)) {
      data[field] = drafts.get(key);
      keys.push(key);
    }
  }
  const reflections = {};
  for (const r of step.data.reflections) {
    const key = draftKey(step, `reflection.${r.id}`);
    if (drafts.has(key)) {
      reflections[r.id] = drafts.get(key);
      keys.push(key);
    }
  }
  if (Object.keys(reflections).length) data.reflections = reflections;
  return { data, keys };
}

// ---- write_pair: own --------------------------------------------------------

function renderPair(ctx, step) {
  const { data, ui } = step;
  const entries = [
    ['before', draftKey(step, 'before'), data.before],
    ['after', draftKey(step, 'after'), data.after],
    ['labels', draftKey(step, 'labels'), data.labels],
  ];
  const unsaved = entries.some(([, key]) => ctx.hasDraft(key));
  const saved = Boolean(data.before.trim() || data.after.trim() || data.labels.trim());
  return [
    h('p', { class: 'callout callout-attn', id: 'own-privacy', key: 'privacy' }, ui.privacy_note),
    textField(ctx, { id: 'own-before', label: ui.before_label, hint: ui.before_hint, draftKey: entries[0][1], value: data.before, multiline: true, rows: 8, disabled: ctx.readOnly }),
    textField(ctx, { id: 'own-after', label: ui.after_label, hint: ui.after_hint, draftKey: entries[1][1], value: data.after, multiline: true, rows: 8, disabled: ctx.readOnly }),
    textField(ctx, { id: 'own-labels', label: ui.labels_label, hint: ui.labels_hint, draftKey: entries[2][1], value: data.labels, disabled: ctx.readOnly }),
    h('div', { class: 'row', key: 'save-row' }, saveButton(ctx, step, ui, entries, unsaved), savedLine(ui, unsaved, saved)),
  ];
}

export const PART_STEP_PANELS = {
  cold: { render: renderRunPanel, collect: collectRunPanel },
  rewrite: { render: renderRunPanel, collect: collectRunPanel },
  score: { render: renderScoreForm, collect: collectScoreForm },
  rescore: { render: renderScoreForm, collect: collectScoreForm },
  own: { render: renderPair },
};
