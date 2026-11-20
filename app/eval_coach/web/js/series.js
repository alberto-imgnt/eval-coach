// The Series map: the app's home screen, one row per Part of the series.
// Every word comes from content/series.json (state.series.ui) and content/lesson-ui.json (the status words).

import { h } from './dom.js';
import { fmt } from './lessons.js';
import { actionButton, lockIcon, lockTip, lockTipId, lockedProps } from './ui.js';

const STATE_WORD = {
  not_started: 'state_not_started',
  in_progress: 'state_in_progress',
  done: 'state_done',
  skipped: 'state_skipped',
  locked: 'state_locked',
};
const ACTION_WORD = { not_started: 'start', in_progress: 'continue', done: 'review' };

function partName(words, part) {
  return [h('span', { class: 'visually-hidden' }, `${fmt(words.part_label, { n: part.n })}: `), part.title];
}

function rowHead(words, part, ...tail) {
  return [
    h('span', { class: 'series-mark', 'aria-hidden': 'true' }, String(part.n)),
    h(
      'span',
      { class: 'series-body' },
      h('span', { class: 'series-title' }, ...partName(words, part)),
      h('span', { class: 'series-outcome' }, part.outcome),
    ),
    ...tail,
  ];
}

// What the open control shows on the right: the state, then a count and an action only for an open Part.
function rowMeta(ctx, words, part) {
  const counted = part.done !== null && part.done !== undefined && part.state !== 'not_started';
  return h(
    'span',
    { class: 'series-meta' },
    part.state === 'locked' ? lockIcon(ctx) : null,
    part.state === 'skipped' ? h('span', { class: 'skip-icon', 'aria-hidden': 'true' }) : null,
    h('span', { class: 'series-state' }, words[STATE_WORD[part.state]]),
    counted ? h('span', { class: 'series-count' }, fmt(words.count, { done: part.done, total: part.total })) : null,
    ACTION_WORD[part.state] ? h('span', { class: 'series-action' }, words[ACTION_WORD[part.state]]) : null,
  );
}

// A Part with content: an expand control and an open control, side by side.
function renderCourseRow(ctx, words, part) {
  const open = ctx.seriesOpen.has(part.id);
  const locked = part.state === 'locked';
  const toggleLabel = fmt(open ? words.collapse : words.expand, { n: part.n });
  const tipId = lockTipId('part', part.id);
  const openProps = locked
    ? { type: 'button', class: 'series-open is-locked', id: `series-open-${part.id}`, ...lockedProps(ctx, tipId) }
    : { type: 'button', class: 'series-open', id: `series-open-${part.id}`, onClick: () => ctx.actions.openPart(part.id) };
  return h(
    'li',
    { class: `series-row k-course st-${part.state}${open ? ' is-open' : ''}`, id: `series-${part.id}`, key: part.id },
    h(
      'div',
      { class: 'series-head' },
      h(
        'button',
        {
          type: 'button',
          class: 'series-toggle',
          id: `series-toggle-${part.id}`,
          'aria-expanded': open ? 'true' : 'false',
          'aria-controls': `series-lessons-${part.id}`,
          'aria-label': toggleLabel,
          title: toggleLabel,
          onClick: () => ctx.actions.toggleSeriesPart(part.id),
        },
        h('span', { class: 'series-chevron', 'aria-hidden': 'true' }),
      ),
      h('button', openProps, ...rowHead(words, part, rowMeta(ctx, words, part))),
      locked ? lockTip(ctx, tipId) : null,
    ),
    part.can_skip
      ? h(
          'div',
          { class: 'series-extras', key: `extras-${part.id}` },
          actionButton(ctx, { label: words.skip_button, id: `series-skip-${part.id}`, kind: 'quiet', onClick: () => ctx.actions.skipPart(part) }),
        )
      : null,
    h(
      'ol',
      { class: 'series-lessons', id: `series-lessons-${part.id}`, hidden: !open, 'aria-label': fmt(words.lessons_label, { n: part.n }) },
      part.lessons.map((lesson) =>
        h(
          'li',
          { class: `series-lesson s-${lesson.status}`, key: lesson.id },
          h('span', { class: 'series-lesson-title' }, lesson.title),
          h('span', { class: 'series-lesson-status' }, ctx.text[`status_${lesson.status}`] || ''),
        ),
      ),
    ),
  );
}

// A Part without content (coming soon) or a live one: text only, nothing to select.
function renderTextRow(words, part) {
  const label = part.kind === 'live' ? words.live : words.soon;
  return h(
    'li',
    { class: `series-row k-${part.kind}`, id: `series-${part.id}`, key: part.id },
    h('div', { class: 'series-head' }, ...rowHead(words, part, h('span', { class: 'series-meta' }, h('span', { class: 'series-tag' }, label)))),
  );
}

export function renderSeries(ctx) {
  const { series } = ctx.state;
  const words = series.ui;
  return h(
    'article',
    { class: 'series-page', key: 'series' },
    h('h1', { id: 'step-heading', tabindex: -1 }, series.title),
    h('p', { class: 'lede' }, words.intro),
    h(
      'ol',
      { class: 'series-list', id: 'series-list', 'aria-label': words.list_label },
      series.parts.map((part) => (part.kind === 'course' ? renderCourseRow(ctx, words, part) : renderTextRow(words, part))),
    ),
  );
}

// The confirm for "Skip this Part": what it teaches, why it matters and what is given up. Words come from series.json.
export function skipDialogBody(words, part) {
  return [
    h(
      'div',
      { class: 'skip-dialog', id: `skip-dialog-${part.id}` },
      h('h3', null, words.skip_teaches_label),
      h('p', { id: 'skip-teaches' }, part.skip.teaches),
      h('h3', null, words.skip_matters_label),
      h('p', { id: 'skip-matters' }, part.skip.matters),
      h('p', { id: 'skip-cost' }, words.skip_cost),
    ),
  ];
}

// The sidebar's middle section on the map: no progress count and no course list.
export function renderSeriesNav() {
  return h('div', { class: 'steps-spacer', key: 'steps-spacer' });
}
