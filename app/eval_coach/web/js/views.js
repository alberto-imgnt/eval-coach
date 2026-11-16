// Sidebar (a top bar on narrow screens), step layout and terminal header.

import { getTheme, navCollapsed, toggleNav, toggleTheme } from './chrome.js';
import { h } from './dom.js';
import { hasLessons, renderCourseNav, renderStepQuestion, tx } from './lessons.js';
import { PANELS } from './panels.js';
import { renderSeriesNav } from './series.js';
import { actionButton, optionalLive, section } from './ui.js';

const STATUS_WORD = { locked: 'Not started', active: 'Now', done: 'Done', optional: 'Optional' };

// Steps are grouped into phases in the top bar. Any step not listed here (an optional extra) is "extra".
const PHASE_OF = {
  generate: 'build',
  build: 'build',
  fixtures: 'build',
  'fixtures-config': 'build',
  readback: 'build',
  predict: 'test',
  key: 'test',
  run: 'test',
  fix: 'test',
  baseline: 'measure',
};

function icon(name) {
  return h('span', { class: `tb-icon tb-icon-${name}`, 'aria-hidden': 'true' });
}

// One control in the sidebar's tool list: an icon and a label. The label stays in the page when the
// sidebar is collapsed to icons, so its name is still read out.
function tool(props, iconName, label) {
  return h(props.href ? 'a' : 'button', { class: 'tool', type: props.href ? null : 'button', title: label, ...props }, icon(iconName), h('span', { class: 'tool-label' }, label));
}

function renderTopbarTools(ctx) {
  const { state } = ctx;
  if (!state) return null;
  const hasText = Boolean(ctx.text && ctx.text.glossary_button);
  const dark = getTheme() === 'dark';
  const quitting = ctx.busy('quit');
  return h(
    'div',
    { class: 'topbar-tools', key: 'tools' },
    hasText ? tool({ id: 'glossary-open', onClick: () => ctx.actions.openGlossary() }, 'glossary', tx(ctx, 'glossary_button')) : null,
    hasText ? tool({ id: 'reference-link', href: 'reference.html', target: '_blank', rel: 'noopener noreferrer' }, 'reference', tx(ctx, 'reference_link')) : null,
    tool(
      {
        id: 'theme-toggle',
        'aria-pressed': dark ? 'true' : 'false',
        onClick: () => {
          toggleTheme();
          ctx.rerender();
        },
      },
      dark ? 'sun' : 'moon',
      dark ? 'Light theme' : 'Dark theme',
    ),
    tool(
      {
        id: 'settings-open',
        'aria-current': ctx.view === 'settings' ? 'page' : null,
        onClick: () => ctx.actions.openSettings(),
      },
      'settings',
      (state.settings && state.settings.text.settings.tool) || 'Settings',
    ),
    tool(
      {
        id: 'quit',
        class: 'tool tool-quit',
        'aria-disabled': quitting ? 'true' : null,
        'aria-busy': quitting ? 'true' : null,
        onClick: () => {
          if (!quitting) ctx.actions.quit();
        },
      },
      'power',
      quitting ? 'Quitting…' : 'Quit',
    ),
  );
}

// The progress label comes from content ("{done} of {total} ..."); its leading count stays bold.
function journeyText(ctx, course, done, total) {
  const label = tx(ctx, course ? 'journey_done' : 'journey_done_steps', { done, total });
  const count = `${done} of ${total}`;
  if (!label.startsWith(count)) return [h('span', null, label)];
  return [h('strong', null, count), ' ', h('span', null, label.slice(count.length).trim())];
}

// The sidebar: brand, overall progress, the course list (or the steps), and the tools.
// On narrow screens the same pieces lay out as a bar across the top.
export function renderTopbar(ctx) {
  const { state } = ctx;
  const onMap = Boolean(ctx.mapNav);
  const steps = state && state.configured ? [...(state.steps || []), ...(state.optional_steps || [])] : [];
  const required = state && state.configured ? state.steps || [] : [];
  const course = hasLessons(state);
  const journeyItems = onMap ? [] : course ? state.course : required;
  const journeyDone = journeyItems.filter((i) => i.status === 'done' || i.status === 'skipped').length;
  const percent = journeyItems.length ? Math.round((journeyDone * 100) / journeyItems.length) : 0;
  const collapsed = navCollapsed();
  const toggleLabel = collapsed ? 'Expand the sidebar' : 'Collapse the sidebar';
  const backLabel = state && state.series && !onMap ? tx(ctx, 'back_to_series') : '';
  return [
    h(
      'div',
      { class: 'side-head', key: 'head' },
      h(
        'div',
        { class: 'brand' },
        h('span', { class: 'wordmark' }, h('span', { class: 'wm-a' }, 'eval'), h('span', { class: 'wm-sep' }, '-'), h('span', { class: 'wm-b' }, 'coach')),
        h('span', { class: 'brand-sub' }, onMap ? state.series.ui.brand_sub : tx(ctx, 'brand_sub')),
      ),
      state
        ? h(
            'button',
            {
              type: 'button',
              class: 'nav-toggle',
              id: 'nav-toggle',
              'aria-expanded': collapsed ? 'false' : 'true',
              'aria-label': toggleLabel,
              title: toggleLabel,
              onClick: () => {
                toggleNav();
                ctx.rerender();
              },
            },
            icon('sidebar'),
          )
        : null,
    ),
    backLabel ? h('div', { class: 'back-series', key: 'back' }, tool({ id: 'back-to-series', onClick: () => ctx.actions.backToSeries() }, 'back', backLabel)) : null,
    journeyItems.length
      ? h(
          'div',
          { class: 'journey', key: 'journey' },
          h('span', { class: 'ring', style: `--p: ${percent}`, role: 'img', 'aria-label': `${percent}% complete` }, h('span', { class: 'ring-num' }, `${percent}%`)),
          h('span', { class: 'journey-text' }, ...journeyText(ctx, course, journeyDone, journeyItems.length)),
        )
      : null,
    onMap
      ? renderSeriesNav()
      : course
      ? renderCourseNav(ctx)
      : steps.length
      ? h(
          'nav',
          { class: 'steps', 'aria-label': 'Steps', key: 'steps' },
          h(
            'ol',
            null,
            steps.map((s, i, all) => {
              const viewed = ctx.step && ctx.step.id === s.id;
              // The row that reads as "you are here" is the step on screen, or the active step when none is.
              const anyViewed = Boolean(ctx.step && all.some((x) => x.id === ctx.step.id));
              const open = viewed || (!anyViewed && s.status === 'active');
              const phase = PHASE_OF[s.id] || 'extra';
              const prevPhase = i > 0 ? PHASE_OF[steps[i - 1].id] || 'extra' : null;
              const inner = [
                h('span', { class: 'step-num', 'aria-hidden': 'true' }, String(i + 1)),
                h('span', { class: 'step-title' }, s.title),
                h('span', { class: 'step-status' }, STATUS_WORD[s.status] || ''),
              ];
              return h(
                'li',
                {
                  key: s.id,
                  class: `step-item s-${s.status} ph-${phase}${phase !== prevPhase ? ' ph-start' : ''}${viewed ? ' is-viewed' : ''}${open ? ' is-open' : ''}`,
                },
                h(
                  'button',
                  { type: 'button', class: 'step-btn', title: s.title, 'aria-current': viewed ? 'step' : null, onClick: () => ctx.actions.navigate(s.id) },
                  inner,
                ),
              );
            }),
          ),
        )
      : h('div', { class: 'steps-spacer', key: 'steps-spacer' }),
    renderTopbarTools(ctx),
  ];
}

export function renderNotices(ctx) {
  return ctx.notices.map((n) =>
    h(
      'div',
      { class: 'notice', role: 'alert', key: `notice-${n.id}` },
      h('p', null, n.message),
      h('button', { type: 'button', class: 'btn btn-quiet', onClick: () => ctx.actions.dismissNotice(n.id) }, 'Dismiss'),
    ),
  );
}

function renderChecklist(ctx, step) {
  if (!step.checklist || step.checklist.length === 0) return null;
  return section(
    'checklist',
    'Before you check',
    h(
      'ul',
      { class: 'checklist' },
      step.checklist.map((item) => {
        const key = `checklist.${step.id}.${item.id}`;
        const checked = ctx.draft(key, item.checked);
        return h(
          'li',
          { key: `cl-${item.id}` },
          h(
            'label',
            { class: 'check-row' },
            h('input', {
              type: 'checkbox',
              checked,
              disabled: ctx.readOnly,
              onChange: (e) => {
                ctx.setDraft(key, e.target.checked);
                ctx.queueSave(step.id);
                ctx.rerender();
              },
            }),
            h('span', null, item.label),
          ),
        );
      }),
    ),
  );
}

function renderCheckResult(check) {
  if (!check) return null;
  return h(
    'div',
    { class: 'check-result', key: 'check-result', role: 'status', 'aria-live': 'polite' },
    h('p', { class: check.ok ? 'ok-text check-head' : 'bad-text check-head' }, check.ok ? 'Passed. This step is done.' : 'Not done yet. Here is what is missing:'),
    h(
      'ul',
      { class: 'check-items' },
      (check.items || []).map((item, i) =>
        h(
          'li',
          { key: `item-${i}`, class: item.ok ? 'is-ok' : 'is-missing' },
          h('span', { class: `check-mark ${item.ok ? 'ok-text' : 'bad-text'}` }, item.ok ? 'OK' : 'Not yet'),
          h('span', null, item.label, item.detail ? h('span', { class: 'hint block' }, item.detail) : null),
        ),
      ),
    ),
    check.nudges && check.nudges.length
      ? h(
          'div',
          { class: 'callout callout-attn', key: 'nudges' },
          h('strong', { class: 'block' }, 'A nudge'),
          h('ul', { class: 'plain-list' }, check.nudges.map((n, i) => h('li', { key: `n-${i}` }, n))),
        )
      : null,
  );
}

function renderCheckSection(ctx, step) {
  const status = ctx.saveStatus(step.id);
  return section(
    'check',
    null,
    ctx.readOnly
      ? null
      : h(
          'div',
          { class: 'row' },
          actionButton(ctx, {
            label: 'Check my work',
            id: 'check-work',
            busyKey: 'check',
            busyLabel: 'Checking…',
            kind: 'primary',
            onClick: () => ctx.actions.check(),
          }),
          status === 'saving' || status === 'pending'
            ? h('span', { class: 'hint' }, 'Saving your answers…')
            : status === 'saved'
              ? h('span', { class: 'hint' }, 'Your answers are saved.')
              : status === 'error'
                ? h('span', { class: 'bad-text' }, 'Could not save. Your answers are still here.')
                : null,
        ),
    renderCheckResult(step.last_check),
    renderStepQuestion(ctx, step),
    step.status === 'done' && ctx.nextStep
      ? h(
          'div',
          { class: 'row', key: 'continue' },
          actionButton(ctx, { label: `Continue to: ${ctx.nextStep.title}`, id: 'continue', kind: 'primary', onClick: () => ctx.actions.continueToNext() }),
        )
      : null,
  );
}

function renderTroubleshooting(step) {
  if (!step.troubleshooting || step.troubleshooting.length === 0) return null;
  return h(
    'details',
    { class: 'troubleshoot', key: 'troubleshoot' },
    h('summary', null, 'Something not working?'),
    h(
      'dl',
      null,
      step.troubleshooting.flatMap((t, i) => [h('dt', { key: `p-${i}` }, t.problem), h('dd', { key: `f-${i}` }, t.fix)]),
    ),
  );
}

// A step read ahead: its words only. Nothing in it can be started, and nothing is saved.
function renderStepPreviewNote(ctx, step) {
  const gate = ctx.state.settings ? ctx.state.settings.text.setup_gate : null;
  if (!gate) return null;
  if (!ctx.state.preflight.passed) {
    return h(
      'div',
      { class: 'callout callout-attn', id: 'preview-note', key: 'preview-note', role: 'status' },
      h('p', null, gate.preview_step),
      h('div', { class: 'row' }, actionButton(ctx, { label: gate.button, id: 'preview-setup', onClick: () => ctx.actions.openSetup() })),
    );
  }
  const held = step.held_by;
  if (!held) return null;
  return h(
    'div',
    { class: 'callout callout-attn', id: 'preview-note', key: 'preview-note', role: 'status' },
    h('p', null, gate.preview_step_after.replace('{title}', held.title)),
    h('div', { class: 'row' }, actionButton(ctx, { label: gate.preview_back, id: 'preview-back', onClick: () => ctx.actions.openCourseItem(held.kind, held.id) })),
  );
}

function renderStepPreview(ctx, step) {
  const stepNumber = (ctx.state.steps || []).findIndex((s) => s.id === step.id) + 1;
  return h(
    'article',
    { class: 'step-page', key: `step-${step.id}` },
    h('p', { class: 'kicker' }, step.optional ? 'Optional step' : `Step ${stepNumber} of ${(ctx.state.steps || []).length}`),
    h('h1', { id: 'step-heading', tabindex: -1 }, step.title),
    renderStepPreviewNote(ctx, step),
    h('p', { class: 'lede', key: 'goal' }, step.goal),
    step.why && step.why.length ? section('why', 'Why this matters', h('ul', { class: 'prose-list' }, step.why.map((w, i) => h('li', { key: `why-${i}` }, w)))) : null,
    step.instructions && step.instructions.length
      ? section('instructions', 'What to do', h('ol', { class: 'prose-list' }, step.instructions.map((t, i) => h('li', { key: `inst-${i}` }, t))))
      : null,
    renderTroubleshooting(step),
  );
}

export function renderStep(ctx) {
  const { step } = ctx;
  if (step.preview) return renderStepPreview(ctx, step);
  const panel = PANELS[step.id];
  const stepNumber = (ctx.state.steps || []).findIndex((s) => s.id === step.id) + 1;
  return h(
    'article',
    { class: 'step-page', key: `step-${step.id}` },
    h('p', { class: 'kicker' }, step.optional ? 'Optional step' : `Step ${stepNumber} of ${(ctx.state.steps || []).length}`),
    h('h1', { id: 'step-heading', tabindex: -1 }, step.title),
    step.status === 'done' && ctx.readOnly ? h('p', { class: 'hint', key: 'done-note' }, 'You finished this step. It is shown here as a record.') : null,
    h('p', { class: 'lede', key: 'goal' }, step.goal),
    step.why && step.why.length ? section('why', 'Why this matters', h('ul', { class: 'prose-list' }, step.why.map((w, i) => h('li', { key: `why-${i}` }, w)))) : null,
    step.instructions && step.instructions.length
      ? section('instructions', 'What to do', h('ol', { class: 'prose-list' }, step.instructions.map((t, i) => h('li', { key: `inst-${i}` }, t))))
      : null,
    h('div', { class: 'panel', key: 'panel' }, panel ? panel.render(ctx, step) : null),
    renderChecklist(ctx, step),
    renderCheckSection(ctx, step),
    renderTroubleshooting(step),
  );
}

export function renderFinished(ctx) {
  const live = optionalLive(ctx.state);
  const liveOffer = live && ctx.text.optional_live_note
    ? h(
        'div',
        { key: 'optional-live' },
        h('p', { class: 'callout', id: 'optional-live-note' }, ctx.text.optional_live_note),
        h('div', { class: 'row' }, actionButton(ctx, { label: ctx.text.optional_live_button, id: 'open-live', onClick: () => ctx.actions.openCourseItem('step', 'live') })),
      )
    : null;
  if (hasLessons(ctx.state) && ctx.text.finished_title) {
    return h(
      'article',
      { class: 'step-page finished-page', key: 'finished' },
      h('div', { class: 'finished-badge', 'aria-hidden': 'true' }, '✓'),
      h('h1', { id: 'step-heading', tabindex: -1 }, tx(ctx, 'finished_title')),
      h('p', { class: 'lede' }, tx(ctx, 'finished_body')),
      liveOffer,
      h('p', null, 'When you are done, press Quit to stop the app.'),
    );
  }
  return h(
    'article',
    { class: 'step-page finished-page', key: 'finished' },
      h('div', { class: 'finished-badge', 'aria-hidden': 'true' }, '✓'),
    h('h1', { id: 'step-heading', tabindex: -1 }, 'You have finished every step'),
    h('p', { class: 'lede' }, 'Your work is saved in your project folder. You can open any finished step from the list to look back at it.'),
    liveOffer,
    h('p', null, 'When you are done, press Quit to stop the app.'),
  );
}

function terminalStatusText(terminal) {
  if (terminal.running) return 'Your CLI is running.';
  if (terminal.exit_code !== null && terminal.exit_code !== undefined) {
    return `Your CLI has stopped (exit code ${terminal.exit_code}).`;
  }
  return 'Your CLI is not running.';
}

export function renderTermHead(ctx) {
  const { state, step } = ctx;
  const { terminal } = state;
  const { cli } = step;
  const running = terminal.running;
  return [
    h(
      'div',
      { class: 'term-title-row', key: 'title' },
      h('h2', { class: 'term-label' }, terminal.label || 'Your CLI'),
      h('span', { class: `term-status${running ? ' is-on' : ''}`, role: 'status' }, terminalStatusText(terminal)),
    ),
    h(
      'div',
      { class: 'term-line-block', key: 'line' },
      h('span', { class: 'hint block' }, 'This exact line will be typed into your CLI:'),
      h('code', { class: 'term-line' }, cli.line),
      h('span', { class: 'hint block' }, 'Your CLI starts in: ', cli.folder_label),
      cli.blocked ? h('p', { class: 'callout callout-attn', id: 'cli-blocked', role: 'status' }, cli.blocked) : null,
      cli.start_blocked && !ctx.readOnly ? h('p', { class: 'callout callout-attn', id: 'cli-start-blocked', role: 'status' }, cli.start_blocked) : null,
    ),
    ctx.readOnly
      ? h('p', { class: 'hint', key: 'readonly' }, 'This step is finished, so the controls are off here.')
      : h(
          'div',
          { class: 'row term-actions', key: 'actions' },
          actionButton(ctx, {
            label: 'Start my CLI',
            id: 'cli-start',
            busyKey: 'start',
            busyLabel: 'Starting…',
            kind: running || cli.start_blocked ? null : 'primary',
            disabled: running || Boolean(cli.start_blocked),
            onClick: () => ctx.actions.start(),
          }),
          actionButton(ctx, {
            label: 'Send to CLI',
            id: 'cli-send',
            busyKey: 'send',
            busyLabel: 'Sending…',
            kind: running && !cli.blocked && !cli.start_blocked ? 'primary' : null,
            disabled: !running || Boolean(cli.blocked) || Boolean(cli.start_blocked),
            onClick: () => ctx.actions.send(),
          }),
          actionButton(ctx, { label: 'Stop', id: 'cli-stop', busyKey: 'stop', busyLabel: 'Stopping…', disabled: !running, onClick: () => ctx.actions.stop() }),
          actionButton(ctx, { label: 'Start again', id: 'cli-retry', busyKey: 'retry', busyLabel: 'Starting…', disabled: Boolean(cli.start_blocked) || (!running && !cli.started && (terminal.exit_code === null || terminal.exit_code === undefined)), onClick: () => ctx.actions.retry() }),
        ),
    !ctx.readOnly && cli.sent
      ? h('p', { class: 'hint', key: 'sent' }, 'Sent. If your CLI reports a temporary error, press Send to CLI again.')
      : !ctx.readOnly && running
        ? h('p', { class: 'hint', key: 'ready' }, 'Wait until your CLI is ready for a message, then press Send to CLI.')
        : null,
  ];
}

export function renderTermFoot() {
  return [
    h(
      'p',
      { class: 'term-note', key: 'approvals' },
      'Depending on its settings, your CLI may ask for your approval before it reads, writes or runs something, or it may act on its own. Any approval requests appear here in the terminal. Click in the terminal and answer them with your keyboard. The app never answers for you. To move out of the terminal, press F6.',
    ),
  ];
}
