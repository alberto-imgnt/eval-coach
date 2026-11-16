// One panel per step, each built from step.data. A panel's collect() gathers
// the participant's unsaved answers for /api/step/submit.

import { h } from './dom.js';
import { CRITERIA_STEP_PANELS } from './criteria-steps.js';
import { renderMarkdown } from './markdown.js';
import { PART_STEP_PANELS } from './part-steps.js';
import { actionButton, optionalLive, section, textField, verdictTag, resultTables, VERDICTS } from './ui.js';

const FIXTURES = [
  { key: 'bad', label: 'Bad fixture', predict: 'bad_predict', actual: 'bad_actual', surprise: 'bad_surprise' },
  { key: 'polished', label: 'Polished fixture', predict: 'polished_predict', actual: 'polished_actual', surprise: 'polished_surprise' },
];

const CLASSIFICATIONS = [
  { value: 'vague', label: 'My threshold is vague or too loose' },
  { value: 'reads_differently', label: 'The script reads my threshold differently than I meant' },
  { value: 'predicted_wrong', label: 'I predicted wrong' },
];

const PREDICT_QUESTIONS = [
  { key: 'wrong', label: 'What is wrong with the polished fixture? One sentence is enough.' },
  { key: 'catches', label: 'Which of your criteria should catch that?' },
  { key: 'worst_guess', label: 'Across your five runs, which criterion do you guess will fail most often?' },
];

function choice(ctx, step, { draftKey, current, value, label, name, disabled, cls }) {
  return h(
    'label',
    { class: `seg-opt ${cls || ''}` },
    h('input', {
      type: 'radio',
      name,
      value,
      checked: current === value,
      disabled,
      onChange: () => {
        ctx.setDraft(draftKey, value);
        ctx.queueSave(step.id);
        ctx.rerender();
      },
    }),
    h('span', null, label),
  );
}

// ---- generate -----------------------------------------------------------

function renderGenerate(ctx, step) {
  const { runs = [], current_run: currentRun, model_name: modelName } = step.data;
  const allDone = runs.length > 0 && runs.every((r) => r.done);
  return [
    section(
      'runs',
      'Your five runs',
      h(
        'p',
        { class: 'callout' },
        'You do not need to press anything to move on. When your CLI saves its answer, the app files it as the next run and stops the CLI by itself. Then press ',
        h('strong', null, 'Start my CLI'),
        ' for the next run.',
      ),
      h(
        'ol',
        { class: 'run-list' },
        runs.map((r) => {
          const isCurrent = !r.done && r.n === currentRun && !ctx.readOnly;
          const words = r.words === 1 ? '1 word' : `${r.words} words`;
          const status = r.done ? `Saved, ${words}` : isCurrent ? 'Current run' : 'Waiting';
          return h(
            'li',
            { key: `run-${r.n}`, class: `run${r.done ? ' run-done' : ''}${isCurrent ? ' run-current' : ''}` },
            h('span', { class: 'run-name' }, `Run ${r.n}`),
            h('span', { class: 'run-status' }, status),
          );
        }),
      ),
      allDone ? h('p', { class: 'hint' }, 'All five runs are saved.') : null,
    ),
    section(
      'model',
      null,
      textField(ctx, {
        id: 'model-name',
        label: 'The name of the model you chose in your CLI',
        hint: 'Pick a mid-tier model, not the most powerful one offered.',
        draftKey: 'generate.model_name',
        value: modelName,
        saveStep: step.id,
        disabled: ctx.readOnly,
      }),
    ),
  ];
}

function collectGenerate(step, drafts) {
  const keys = [];
  const data = {};
  if (drafts.has('generate.model_name')) {
    data.model_name = drafts.get('generate.model_name');
    keys.push('generate.model_name');
  }
  return { data, keys };
}

// ---- build --------------------------------------------------------------

function renderBuild(ctx, step) {
  const { checker_exists: exists, first_look: firstLook, scan = [] } = step.data;
  const ui = step.ui || {};
  return [
    section(
      'first-look',
      'First look',
      h('p', null, ui.first_look_blurb),
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, {
          label: firstLook ? 'Run the first look again' : 'Run the first look',
          busyKey: 'first_look',
          busyLabel: 'Running…',
          kind: firstLook ? null : 'primary',
          disabled: !exists || ctx.readOnly,
          onClick: () => ctx.actions.runChecker('first_look'),
        }),
        !exists ? h('span', { class: 'hint' }, ui.first_look_missing) : null,
      ),
      resultTables(firstLook),
    ),
    section(
      'scan',
      'Network and AI scan',
      h('p', { class: 'hint' }, ui.scan_blurb),
      !exists
        ? h('p', null, ui.scan_absent)
        : scan.length === 0
          ? h('p', { class: 'ok-text' }, ui.scan_clear)
          : h('ul', { class: 'plain-list' }, scan.map((s, i) => h('li', { key: `scan-${i}`, class: 'bad-text' }, s.message))),
    ),
  ];
}

// ---- fixtures: add them to the config (promptfoo track) --------------------

function renderFixturesConfig(ctx, step) {
  const { config_exists: exists, tests = [], scan = [], fixtures_ready: ready } = step.data;
  const ui = step.ui || {};
  return [
    section(
      'config',
      ui.config_heading,
      h(
        'ul',
        { class: 'file-list' },
        h(
          'li',
          { key: 'config-file', class: exists ? 'is-present' : '' },
          h('span', { class: 'mono' }, 'promptfooconfig.yaml'),
          h('span', { class: exists ? 'ok-text' : 'hint' }, exists ? 'Present' : 'Not there yet'),
        ),
      ),
      !exists ? h('p', { class: 'hint' }, ui.config_missing) : null,
      ready ? null : h('p', { class: 'callout callout-attn', id: 'fixtures-not-ready' }, 'Your two fixtures are not saved in your project yet.'),
    ),
    section(
      'tests',
      ui.tests_heading,
      h('p', { class: 'hint' }, ui.tests_hint),
      h(
        'ul',
        { class: 'file-list', id: 'fixture-tests' },
        tests.map((t) =>
          h(
            'li',
            { key: `test-${t.name}`, class: t.present ? 'is-present' : '' },
            h('span', { class: 'mono' }, t.name),
            h('span', { class: t.present ? 'ok-text' : 'hint' }, t.present ? 'In the config' : 'Not in the config yet'),
          ),
        ),
      ),
      exists && scan.length === 0
        ? h('p', { class: 'ok-text' }, ui.scan_clear)
        : exists
          ? h('ul', { class: 'plain-list' }, scan.map((s, i) => h('li', { key: `fscan-${i}`, class: 'bad-text' }, s.message)))
          : null,
    ),
  ];
}

// ---- fixtures -----------------------------------------------------------

function fileStatus(files) {
  return section(
    'files',
    'Files',
    h(
      'ul',
      { class: 'file-list' },
      files.map((f) =>
        h(
          'li',
          { key: `file-${f.name}`, class: f.present ? 'is-present' : '' },
          h('span', { class: 'mono' }, f.name),
          h('span', { class: f.present ? 'ok-text' : 'hint' }, f.present ? 'Present' : 'Not there yet'),
        ),
      ),
    ),
  );
}

function renderFixtures(ctx, step) {
  const { files = [], example } = step.data;
  const ui = step.ui || {};
  const sections = [fileStatus(files)];
  if (example && example.offered) {
    sections.push(
      section(
        'example-fixtures',
        ui.example_heading,
        h('p', { class: 'callout', id: 'example-fixtures-note' }, ui.example_blurb),
        h(
          'div',
          { class: 'row' },
          actionButton(ctx, {
            label: ui.example_button,
            id: 'use-example-fixtures',
            busyKey: 'example-fixtures',
            busyLabel: 'Saving…',
            disabled: ctx.readOnly || ctx.state.terminal.running,
            onClick: () => ctx.actions.useExampleFixtures(),
          }),
          ctx.state.terminal.running && !ctx.readOnly
            ? h('span', { class: 'hint', id: 'example-fixtures-stop' }, 'Press Stop first. Your CLI is still running.')
            : null,
        ),
      ),
    );
  }
  return sections;
}

// ---- answer key ---------------------------------------------------------

function renderKey(ctx, step) {
  const { files = [], key_held: keyHeld } = step.data;
  return [
    fileStatus(files),
    section(
      'key',
      'Answer key held back',
      h(
        'p',
        { class: 'callout' },
        keyHeld
          ? 'The answer key is sealed away from your project folder. You will read it in the next step, after your checker has run on both fixtures.'
          : 'When this step passes, the app seals the answer key away from your project folder. You will read it in the next step, after your checker has run on both fixtures.',
      ),
    ),
  ];
}

// ---- readback -----------------------------------------------------------

function renderReadback(ctx, step) {
  const { criteria = [], note } = step.data;
  return [
    section(
      'answers',
      'Does the code mean what you meant?',
      h('p', { class: 'hint' }, 'For each criterion, read the explanation in your CLI and answer honestly. A "No" is useful: it shows you what to fix.'),
      h(
        'div',
        { class: 'readback' },
        criteria.map((c) => {
          const draftKey = `readback.answer.${c.id}`;
          const current = ctx.draft(draftKey, c.answer);
          return h(
            'div',
            { key: `rb-${c.id}`, class: 'readback-row', role: 'radiogroup', 'aria-label': `${c.id} ${c.name}` },
            h('span', { class: 'readback-name' }, h('span', { class: 'crit-id' }, c.id), ' ', c.name),
            h(
              'div',
              { class: 'seg' },
              choice(ctx, step, { draftKey, current, value: 'yes', label: 'Yes', name: `rb-${c.id}`, disabled: ctx.readOnly }),
              choice(ctx, step, { draftKey, current, value: 'no', label: 'No', name: `rb-${c.id}`, disabled: ctx.readOnly }),
            ),
          );
        }),
      ),
    ),
    section(
      'note',
      null,
      textField(ctx, {
        id: 'readback-note',
        label: 'Note (optional)',
        hint: 'Anything you want to remember, for example a criterion you plan to reword.',
        draftKey: 'readback.note',
        value: note,
        saveStep: step.id,
        multiline: true,
        disabled: ctx.readOnly,
      }),
    ),
  ];
}

function collectReadback(step, drafts) {
  const answers = {};
  const keys = [];
  for (const c of step.data.criteria || []) {
    const k = `readback.answer.${c.id}`;
    if (drafts.has(k)) {
      answers[c.id] = drafts.get(k);
      keys.push(k);
    } else if (c.answer) {
      answers[c.id] = c.answer;
    }
  }
  const data = { answers };
  if (drafts.has('readback.note')) {
    data.note = drafts.get('readback.note');
    keys.push('readback.note');
  }
  return { data, keys };
}

// ---- predict ------------------------------------------------------------

function predictCriteria(ctx, data) {
  return data.manual_rows ? ctx.draft('predict.criteria', data.criteria || []) : data.criteria || [];
}

function predictFormState(ctx, step) {
  const { data } = step;
  const criteria = predictCriteria(ctx, data);
  const bad = {};
  const polished = {};
  let filled = 0;
  for (const c of criteria) {
    bad[c.id] = ctx.draft(`predict.bad.${c.id}`, (data.bad || {})[c.id] || null);
    polished[c.id] = ctx.draft(`predict.polished.${c.id}`, (data.polished || {})[c.id] || null);
    if (bad[c.id]) filled += 1;
    if (polished[c.id]) filled += 1;
  }
  const answers = {};
  let answered = 0;
  for (const q of PREDICT_QUESTIONS) {
    answers[q.key] = ctx.draft(`predict.answers.${q.key}`, (data.answers || {})[q.key] || '');
    if (answers[q.key].trim()) answered += 1;
  }
  const missingCells = criteria.length * 2 - filled;
  const missingAnswers = PREDICT_QUESTIONS.length - answered;
  return { criteria, bad, polished, answers, missingCells, missingAnswers };
}

function collectPredict(step, drafts) {
  const { data } = step;
  const keys = [];
  const criteria = data.manual_rows && drafts.has('predict.criteria') ? drafts.get('predict.criteria') : data.criteria || [];
  const bad = { ...(data.bad || {}) };
  const polished = { ...(data.polished || {}) };
  const answers = { ...(data.answers || {}) };
  for (const c of criteria) {
    const b = `predict.bad.${c.id}`;
    const p = `predict.polished.${c.id}`;
    if (drafts.has(b)) {
      bad[c.id] = drafts.get(b);
      keys.push(b);
    }
    if (drafts.has(p)) {
      polished[c.id] = drafts.get(p);
      keys.push(p);
    }
  }
  for (const q of PREDICT_QUESTIONS) {
    const a = `predict.answers.${q.key}`;
    if (drafts.has(a)) {
      answers[q.key] = drafts.get(a);
      keys.push(a);
    }
  }
  const payload = { bad, polished, answers, lock: false };
  if (data.manual_rows) {
    payload.criteria = criteria;
    if (drafts.has('predict.criteria')) keys.push('predict.criteria');
  }
  return { data: payload, keys };
}

function addManualRow(ctx, step) {
  const name = ctx.draft('predict.new_row', '').trim();
  if (!name) return;
  const criteria = [...predictCriteria(ctx, step.data)];
  let n = criteria.length + 1;
  const taken = new Set(criteria.map((c) => c.id));
  while (taken.has(`C${n}`)) n += 1;
  criteria.push({ id: `C${n}`, name });
  ctx.setDraft('predict.criteria', criteria);
  ctx.clearDraft('predict.new_row');
  ctx.queueSave(step.id);
  ctx.rerender();
}

function removeManualRow(ctx, step, id) {
  const criteria = predictCriteria(ctx, step.data).filter((c) => c.id !== id);
  ctx.setDraft('predict.criteria', criteria);
  ctx.clearDraft(`predict.bad.${id}`);
  ctx.clearDraft(`predict.polished.${id}`);
  ctx.queueSave(step.id);
  ctx.rerender();
}

function verdictRadios(ctx, step, { fixture, c, value, disabled }) {
  const draftKey = `predict.${fixture.key}.${c.id}`;
  const name = `predict-${fixture.key}-${c.id}`;
  return h(
    'div',
    { class: 'seg', role: 'radiogroup', 'aria-label': `${c.id} ${c.name}: ${fixture.label}` },
    ['P', 'F', 'NC'].map((v) =>
      choice(ctx, step, { draftKey, current: value, value: v, label: VERDICTS[v], name, disabled, cls: `seg-${v}` }),
    ),
  );
}

function renderPredict(ctx, step) {
  const { data } = step;
  const locked = Boolean(data.locked);
  const disabled = locked || ctx.readOnly;
  const form = predictFormState(ctx, step);
  const { criteria, bad, polished, answers, missingCells, missingAnswers } = form;
  const canLock = criteria.length > 0 && missingCells === 0 && missingAnswers === 0;
  const lockHint = [];
  if (missingCells) lockHint.push(`${missingCells} grid ${missingCells === 1 ? 'choice' : 'choices'}`);
  if (missingAnswers) lockHint.push(`${missingAnswers} ${missingAnswers === 1 ? 'question' : 'questions'}`);

  return [
    locked
      ? h('p', { class: 'callout callout-good', key: 'locked' }, h('strong', null, 'Your predictions are locked. '), 'They can no longer be changed.')
      : null,
    section(
      'polished',
      'The polished fixture',
      h('p', { class: 'hint' }, 'Read it first. It looks good on purpose.'),
      h('pre', { class: 'mono-block polished-text' }, data.polished_text || ''),
    ),
    section(
      'grid',
      'Your predictions',
      h('p', { class: 'hint' }, 'For each criterion, predict what your checker will say about each fixture. Choose before anything runs.'),
      h(
        'div',
        { class: 'table-scroll' },
        h(
          'table',
          { class: 'grid predict-grid' },
          h(
            'thead',
            null,
            h(
              'tr',
              null,
              h('th', { scope: 'col' }, 'Criterion'),
              FIXTURES.map((f) => h('th', { scope: 'col', key: f.key }, f.label)),
              data.manual_rows && !disabled ? h('th', { scope: 'col' }, h('span', { class: 'visually-hidden' }, 'Remove row')) : null,
            ),
          ),
          h(
            'tbody',
            null,
            criteria.map((c) =>
              h(
                'tr',
                { key: `row-${c.id}` },
                h('td', { class: 'crit-cell' }, h('span', { class: 'crit-id' }, c.id), ' ', c.name),
                h('td', null, verdictRadios(ctx, step, { fixture: FIXTURES[0], c, value: bad[c.id], disabled })),
                h('td', null, verdictRadios(ctx, step, { fixture: FIXTURES[1], c, value: polished[c.id], disabled })),
                data.manual_rows && !disabled
                  ? h(
                      'td',
                      null,
                      h(
                        'button',
                        { type: 'button', class: 'btn btn-quiet', 'aria-label': `Remove ${c.id} ${c.name}`, onClick: () => removeManualRow(ctx, step, c.id) },
                        'Remove',
                      ),
                    )
                  : null,
              ),
            ),
          ),
        ),
      ),
      criteria.length === 0 ? h('p', { class: 'hint' }, 'No criteria yet. Add one for each criterion in your test cases.') : null,
      data.manual_rows && !disabled
        ? h(
            'div',
            { class: 'row add-row', key: 'add-row' },
            textField(ctx, { id: 'predict-new-row', label: 'Add a criterion', draftKey: 'predict.new_row', value: '' }),
            actionButton(ctx, { label: 'Add row', onClick: () => addManualRow(ctx, step) }),
          )
        : null,
    ),
    section(
      'questions',
      'Three questions',
      PREDICT_QUESTIONS.map((q) =>
        textField(ctx, {
          id: `predict-${q.key}`,
          label: q.label,
          draftKey: `predict.answers.${q.key}`,
          value: (data.answers || {})[q.key],
          saveStep: step.id,
          multiline: true,
          rows: 2,
          disabled,
        }),
      ),
      !locked
        ? h(
            'div',
            { class: 'lock-area', key: 'lock-area' },
            h('p', { class: 'hint' }, 'Locking is permanent. Once locked, you cannot change your predictions. This is what makes the next step honest. Lock first, then press Check my work.'),
            h(
              'div',
              { class: 'row' },
              actionButton(ctx, {
                label: 'Lock my predictions',
                id: 'lock-predictions',
                busyKey: 'lock',
                busyLabel: 'Locking…',
                kind: 'primary',
                disabled: !canLock || ctx.readOnly,
                onClick: () => ctx.actions.lockPredictions(),
              }),
              !canLock && !ctx.readOnly ? h('span', { class: 'hint' }, `Still to fill: ${lockHint.join(' and ') || 'at least one criterion'}.`) : null,
            ),
          )
        : null,
    ),
  ];
}

// ---- run ----------------------------------------------------------------

function verdictCell(value, isSurprise) {
  return h(
    'td',
    { class: isSurprise ? 'surprise' : null },
    verdictTag(value),
    isSurprise ? h('span', { class: 'surprise-tag' }, 'Surprise') : null,
  );
}

function runGrid(grid) {
  return h(
    'div',
    { class: 'table-scroll', key: 'run-grid' },
    h(
      'table',
      { class: 'grid run-grid' },
      h(
        'thead',
        null,
        h('tr', null, h('th', { rowspan: 2, scope: 'col' }, 'Criterion'), FIXTURES.map((f) => h('th', { colspan: 2, scope: 'colgroup', key: f.key, class: 'group-head' }, f.label))),
        h('tr', null, FIXTURES.flatMap((f) => [h('th', { scope: 'col', key: `${f.key}-p` }, 'You predicted'), h('th', { scope: 'col', key: `${f.key}-a` }, 'Checker said')])),
      ),
      h(
        'tbody',
        null,
        grid.map((row) =>
          h(
            'tr',
            { key: row.id },
            h('td', { class: 'crit-cell' }, h('span', { class: 'crit-id' }, row.id), ' ', row.name),
            h('td', { class: 'group-start' }, verdictTag(row.bad_predict)),
            verdictCell(row.bad_actual, row.bad_surprise),
            h('td', { class: 'group-start' }, verdictTag(row.polished_predict)),
            verdictCell(row.polished_actual, row.polished_surprise),
          ),
        ),
      ),
    ),
  );
}

function surpriseList(ctx, step, grid) {
  const items = [];
  for (const row of grid) {
    for (const f of FIXTURES) {
      if (row[f.surprise]) items.push({ row, fixture: f, key: `${row.id}:${f.key}` });
    }
  }
  if (items.length === 0) return h('p', { class: 'callout callout-good', key: 'no-surprises' }, 'No surprises. Every prediction matched the checker.');
  const classifications = step.data.classifications || {};
  return h(
    'div',
    { class: 'surprises', key: 'surprises' },
    h('h3', null, 'Classify each surprise'),
    h('p', { class: 'hint' }, 'A surprise is a place where your prediction and the checker disagree. Say which kind it is.'),
    items.map(({ row, fixture, key }) => {
      const draftKey = `run.class.${key}`;
      const current = ctx.draft(draftKey, classifications[key] || '');
      const selectId = `class-${key.replace(/\W/g, '-')}`;
      return h(
        'div',
        { class: 'surprise-row', key: `surprise-${key}` },
        h(
          'label',
          { for: selectId, class: 'field-label' },
          h('span', { class: 'crit-id' }, row.id),
          ` ${row.name}, ${fixture.label}: you predicted `,
          verdictTag(row[fixture.predict]),
          ', the checker said ',
          verdictTag(row[fixture.actual]),
          '.',
        ),
        h(
          'select',
          {
            id: selectId,
            class: 'input',
            value: current,
            disabled: ctx.readOnly,
            onChange: (e) => {
              ctx.setDraft(draftKey, e.target.value);
              ctx.queueSave(step.id);
              ctx.rerender();
            },
          },
          h('option', { value: '' }, 'Choose one'),
          CLASSIFICATIONS.map((c) => h('option', { value: c.value, key: c.value }, c.label)),
        ),
      );
    }),
  );
}

function renderRun(ctx, step) {
  const { result, grid = [], answer_key_markdown: answerKey, polished_passed_all: polishedPassedAll } = step.data;
  return [
    section(
      'run',
      'Run your checker',
      h('p', null, (step.ui || {}).run_blurb),
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, {
          label: result ? 'Run again' : 'Run my checker on both fixtures',
          id: 'run-fixtures',
          busyKey: 'fixtures',
          busyLabel: 'Running…',
          kind: result ? null : 'primary',
          disabled: ctx.readOnly,
          onClick: () => ctx.actions.runChecker('fixtures'),
        }),
      ),
      resultTables(result && !result.ok ? result : null),
    ),
    grid.length
      ? section(
          'compare',
          'Your predictions and the checker, side by side',
          polishedPassedAll
            ? h(
                'p',
                { class: 'callout callout-attn', key: 'polished-all' },
                h('strong', null, 'The polished fixture passed every criterion. '),
                'Ask yourself: which requirement does it break that none of your thresholds checks?',
              )
            : null,
          runGrid(grid),
          surpriseList(ctx, step, grid),
        )
      : null,
    answerKey !== null && answerKey !== undefined
      ? section('answer-key', 'Answer key', h('div', { class: 'markdown', id: 'answer-key-body' }, ...renderMarkdown(answerKey)))
      : section('answer-key', 'Answer key', h('p', { class: 'hint' }, 'The answer key stays hidden until your predictions are locked and this run has succeeded.')),
    result && result.ok ? section('run-detail', null, h('details', { class: 'raw' }, h('summary', null, 'Show the checker’s full results'), resultTables(result))) : null,
  ];
}

function collectRun(step, drafts) {
  const classifications = { ...(step.data.classifications || {}) };
  const keys = [];
  for (const [k, v] of drafts.entries()) {
    if (k.startsWith('run.class.')) {
      if (v) classifications[k.slice('run.class.'.length)] = v;
      keys.push(k);
    }
  }
  return { data: { classifications }, keys };
}

// ---- fix ----------------------------------------------------------------

function flagRow(label, value, trueWord, falseWord) {
  return h(
    'li',
    { key: label },
    h('span', null, label),
    h('span', { class: value ? 'ok-text' : 'hint' }, value ? trueWord : falseWord),
  );
}

function renderFix(ctx, step) {
  const { data } = step;
  const unsaved = ctx.hasDraft('fix.test_cases_text');
  return [
    section(
      'edit',
      'Edit your test cases',
      h('p', { class: 'hint' }, (step.ui || {}).edit_blurb),
      textField(ctx, {
        id: 'fix-test-cases',
        label: 'test-cases.md',
        draftKey: 'fix.test_cases_text',
        value: data.test_cases_text,
        multiline: true,
        rows: 14,
        mono: true,
        disabled: ctx.readOnly,
      }),
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, {
          label: 'Save test cases',
          id: 'fix-save',
          busyKey: 'fix-save',
          busyLabel: 'Saving…',
          kind: 'primary',
          disabled: !unsaved || ctx.readOnly,
          onClick: () => ctx.actions.saveFixTests(),
        }),
        unsaved ? h('span', { class: 'hint', role: 'status' }, 'You have unsaved changes.') : h('span', { class: 'hint', role: 'status' }, 'Saved.'),
      ),
    ),
    section(
      'flags',
      'Status',
      h(
        'ul',
        { class: 'file-list' },
        flagRow('test-cases.md changed', data.test_cases_changed, 'Yes', 'Not yet'),
        flagRow((step.ui || {}).flag_checker, data.checker_changed_after, 'Yes', 'Not yet'),
        flagRow('Polished fixture fails at least one criterion', data.polished_fails, 'Yes', 'No'),
      ),
    ),
    section(
      'rerun',
      'Run both fixtures again',
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, {
          label: 'Run both fixtures again',
          id: 'fix-rerun',
          busyKey: 'fixtures',
          busyLabel: 'Running…',
          disabled: ctx.readOnly,
          onClick: () => ctx.actions.runChecker('fixtures'),
        }),
      ),
      resultTables(data.rerun),
    ),
    section(
      'explain',
      null,
      textField(ctx, {
        id: 'fix-explanation',
        label: 'If the polished fixture should pass, say why',
        hint: 'Only needed if the polished fixture still passes every criterion after your fix.',
        draftKey: 'fix.explanation',
        value: data.explanation,
        saveStep: step.id,
        multiline: true,
        rows: 3,
        disabled: ctx.readOnly,
      }),
    ),
    data.can_skip && !ctx.readOnly
      ? section(
          'skip',
          null,
          h('p', { class: 'hint' }, 'You had no surprises and the polished fixture already fails at least one criterion, so you may skip this step.'),
          actionButton(ctx, { label: 'Skip this step', id: 'fix-skip', busyKey: 'skip', onClick: () => ctx.actions.skip() }),
        )
      : null,
  ];
}

function collectFix(step, drafts) {
  const keys = [];
  const data = {};
  if (drafts.has('fix.explanation')) {
    data.explanation = drafts.get('fix.explanation');
    keys.push('fix.explanation');
  }
  return { data, keys };
}

// ---- baseline -----------------------------------------------------------

function rateCell(c) {
  if (c.not_checked) return h('td', { class: 'rate-cell' }, h('span', { class: 'verdict v-NC' }, 'NOT CHECKED'), h('span', { class: 'hint block' }, 'Not covered'));
  return h(
    'td',
    { class: 'rate-cell' },
    h('meter', { class: 'rate-meter', min: 0, max: 100, value: c.rate, 'aria-label': `${c.id} pass rate` }),
    `${c.rate}%`,
  );
}

function baselineTable(summary) {
  return h(
    'div',
    { class: 'table-scroll', key: 'baseline-table' },
    h(
      'table',
      { class: 'grid baseline-grid' },
      h(
        'thead',
        null,
        h('tr', null, ['Criterion', 'Runs passed', 'Pass rate', 'Failed in'].map((t) => h('th', { scope: 'col', key: t }, t))),
      ),
      h(
        'tbody',
        null,
        summary.criteria.map((c) =>
          h(
            'tr',
            { key: c.id, class: c.not_checked ? 'is-not-covered' : null },
            h('td', { class: 'crit-cell' }, h('span', { class: 'crit-id' }, c.id), ' ', c.name),
            h('td', null, c.not_checked ? 'Not checked' : `${c.passes} of ${c.checked_runs}`),
            rateCell(c),
            h('td', null, c.not_checked ? 'Not covered' : c.failing_runs.length ? c.failing_runs.map((n) => `run-${n}`).join(', ') : 'None'),
          ),
        ),
      ),
    ),
  );
}

function renderBaseline(ctx, step) {
  const { data } = step;
  const ui = step.ui || {};
  const { summary, result, fresh } = data;
  const canRun = data.runs_ready && data.checker_exists && !ctx.readOnly;
  const overall = summary ? summary.overall : null;
  const overallRate = overall && overall.total ? Math.round((overall.passes * 100) / overall.total) : null;
  return [
    section(
      'model',
      null,
      textField(ctx, {
        id: 'baseline-model',
        label: 'The model you used for your five runs',
        hint: 'The app types this name into the line for your CLI. It is the name you wrote in the first step.',
        draftKey: 'baseline.model_name',
        value: data.model_name,
        saveStep: step.id,
        disabled: ctx.readOnly,
      }),
    ),
    section(
      'count',
      'The app’s own count',
      h('p', { class: 'hint' }, ui.count_blurb),
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, {
          label: summary ? 'Run my checker on the five runs again' : 'Run my checker on the five runs',
          id: 'baseline-run',
          busyKey: 'baseline',
          busyLabel: 'Running…',
          kind: summary ? null : 'primary',
          disabled: !canRun,
          onClick: () => ctx.actions.runChecker('baseline'),
        }),
        !data.checker_exists ? h('span', { class: 'hint' }, ui.no_checker) : !data.runs_ready ? h('span', { class: 'hint' }, 'All five runs must be saved first.') : null,
      ),
      summary && !fresh
        ? h('p', { class: 'callout callout-attn', id: 'baseline-stale', role: 'status' }, ui.stale)
        : null,
      summary
        ? [
            h(
              'p',
              { class: 'baseline-total', id: 'baseline-overall', key: 'baseline-total' },
              `Overall: ${overall.passes} of ${overall.total} checks passed${overallRate === null ? '' : ` (${overallRate}%)`}.`,
            ),
            baselineTable(summary),
            summary.not_checked.length
              ? h(
                  'p',
                  { class: 'callout callout-attn', id: 'baseline-not-covered', key: 'baseline-nc' },
                  `Not covered: ${summary.not_checked.join(', ')}. ${summary.not_checked.length === 1 ? 'This criterion is' : 'These criteria are'} NOT CHECKED. ${summary.not_checked.length === 1 ? 'It is' : 'They are'} left out of the overall total, and your log must list ${summary.not_checked.length === 1 ? 'it' : 'them'} under Not checked.`,
                )
              : null,
          ]
        : null,
      result && !result.ok ? resultTables(result) : null,
      result && result.ok ? h('details', { class: 'raw', key: 'baseline-raw' }, h('summary', null, 'Show the checker’s full results'), resultTables(result)) : null,
    ),
    section(
      'log',
      'Your log',
      h(
        'ul',
        { class: 'file-list' },
        h(
          'li',
          { class: data.log_exists ? 'is-present' : '' },
          h('span', { class: 'mono' }, 'iteration-log.md'),
          h('span', { class: data.log_exists ? 'ok-text' : 'hint' }, data.log_exists ? 'Present' : 'Not there yet'),
        ),
      ),
      h('p', { class: 'hint' }, 'Your CLI writes this file. The app only reads it, and never changes it.'),
    ),
    optionalLiveSection(ctx),
  ];
}

function optionalLiveSection(ctx) {
  if (!optionalLive(ctx.state) || !ctx.text.optional_live_note) return null;
  return section(
    'optional-live',
    null,
    h('p', { class: 'callout', id: 'optional-live-note' }, ctx.text.optional_live_note),
    h(
      'div',
      { class: 'row' },
      actionButton(ctx, { label: ctx.text.optional_live_button, id: 'open-live', onClick: () => ctx.actions.openCourseItem('step', 'live') }),
    ),
  );
}

function collectBaseline(step, drafts) {
  const keys = [];
  const data = {};
  if (drafts.has('baseline.model_name')) {
    data.model_name = drafts.get('baseline.model_name');
    keys.push('baseline.model_name');
  }
  return { data, keys };
}

// ---- live mode (optional, promptfoo track) ----------------------------------------

function renderLive(ctx, step) {
  const { clis = [], cli, acknowledged, model_name: modelName, config_exists: configExists, provider_exists: providerExists, provider_ok: providerOk, scan = [], started } = step.data;
  const ui = step.ui || {};
  const ack = ctx.draft('live.acknowledged', acknowledged);
  const chosen = ctx.draft('live.cli', cli);
  const chosenCli = clis.find((c) => c.id === chosen);
  const disabled = ctx.readOnly;
  const saveNow = () => {
    ctx.queueSave(step.id);
    ctx.flushSave(step.id);
    ctx.rerender();
  };
  return [
    section(
      'live-warning',
      ui.warning_title,
      h(
        'div',
        { class: 'callout callout-attn', id: 'live-warning' },
        h('p', null, h('strong', null, ui.warning_intro)),
        h('ul', { class: 'prose-list' }, (ui.warning_points || []).map((t, i) => h('li', { key: `lw-${i}` }, t))),
      ),
      h(
        'label',
        { class: 'check-row', id: 'live-ack-row' },
        h('input', {
          type: 'checkbox',
          id: 'live-ack',
          checked: ack,
          disabled,
          onChange: (e) => {
            ctx.setDraft('live.acknowledged', e.target.checked);
            saveNow();
          },
        }),
        h('span', null, ui.ack_label),
      ),
    ),
    section(
      'live-cli',
      ui.cli_heading,
      h('p', { class: 'hint' }, ui.cli_hint),
      h(
        'ul',
        { class: 'checklist', role: 'radiogroup', 'aria-label': ui.cli_heading, id: 'live-cli-choice' },
        clis.map((c) =>
          h(
            'li',
            { key: `cli-${c.id}` },
            h(
              'label',
              { class: 'check-row' },
              h('input', {
                type: 'radio',
                name: 'live-cli',
                value: c.id,
                checked: chosen === c.id,
                disabled,
                onChange: () => {
                  ctx.setDraft('live.cli', c.id);
                  saveNow();
                },
              }),
              h('span', null, c.label),
            ),
          ),
        ),
      ),
      chosenCli ? h('p', { class: 'callout', id: 'live-cli-note' }, chosenCli.note) : null,
      textField(ctx, {
        id: 'live-model',
        label: ui.model_label,
        hint: ui.model_hint,
        draftKey: 'live.model_name',
        value: modelName,
        saveStep: step.id,
        disabled,
      }),
    ),
    section(
      'live-files',
      ui.files_heading,
      h('p', { class: 'hint' }, ui.files_blurb),
      h(
        'ul',
        { class: 'file-list', id: 'live-files' },
        h(
          'li',
          { key: 'live-config', class: configExists ? 'is-present' : '' },
          h('span', { class: 'mono' }, 'promptfooconfig.live.yaml'),
          h('span', { class: configExists ? 'ok-text' : 'hint' }, configExists ? 'Present' : 'Not there yet'),
        ),
        h(
          'li',
          { key: 'live-provider', class: providerExists ? 'is-present' : '' },
          h('span', { class: 'mono' }, 'agent-provider.js'),
          h('span', { class: providerExists ? 'ok-text' : 'hint' }, providerExists ? 'Present' : 'Not there yet'),
        ),
      ),
      !configExists ? h('p', { class: 'hint' }, ui.config_missing) : null,
      !providerExists ? h('p', { class: 'hint' }, ui.provider_missing) : providerOk ? null : h('p', { class: 'bad-text', id: 'live-provider-changed' }, ui.provider_changed),
      configExists && scan.length === 0
        ? h('p', { class: 'ok-text' }, ui.scan_clear)
        : configExists
          ? h('ul', { class: 'plain-list', id: 'live-scan' }, scan.map((s, i) => h('li', { key: `lscan-${i}`, class: 'bad-text' }, s.message)))
          : null,
      started ? h('p', { class: 'hint', id: 'live-started' }, ui.started_note) : null,
    ),
  ];
}

function collectLive(step, drafts) {
  const keys = [];
  const data = {};
  for (const [field, key] of [['acknowledged', 'live.acknowledged'], ['cli', 'live.cli'], ['model_name', 'live.model_name']]) {
    if (drafts.has(key)) {
      data[field] = drafts.get(key);
      keys.push(key);
    }
  }
  return { data, keys };
}

export const PANELS = {
  ...PART_STEP_PANELS,
  ...CRITERIA_STEP_PANELS,
  generate: { render: renderGenerate, collect: collectGenerate },
  build: { render: renderBuild },
  fixtures: { render: renderFixtures },
  'fixtures-config': { render: renderFixturesConfig },
  readback: { render: renderReadback, collect: collectReadback },
  predict: { render: renderPredict, collect: collectPredict },
  key: { render: renderKey },
  run: { render: renderRun, collect: collectRun },
  fix: { render: renderFix, collect: collectFix },
  baseline: { render: renderBaseline, collect: collectBaseline },
  live: { render: renderLive, collect: collectLive },
};
