// The Series map: the app's home screen, one row per Part of the series.
// Every word comes from content/series.json (state.series.ui) and content/lesson-ui.json (the status words).

import { h } from './dom.js';
import { fmt } from './lessons.js';

const STATE_WORD = { not_started: 'state_not_started', in_progress: 'state_in_progress', done: 'state_done' };
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

// A Part with content: an expand control and an open control, side by side.
function renderCourseRow(ctx, words, part) {
  const open = ctx.seriesOpen.has(part.id);
  const started = part.state !== 'not_started';
  const toggleLabel = fmt(open ? words.collapse : words.expand, { n: part.n });
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
      h(
        'button',
        { type: 'button', class: 'series-open', id: `series-open-${part.id}`, onClick: () => ctx.actions.openPart(part.id) },
        ...rowHead(
          words,
          part,
          h(
            'span',
            { class: 'series-meta' },
            h('span', { class: 'series-state' }, words[STATE_WORD[part.state]]),
            started ? h('span', { class: 'series-count' }, fmt(words.count, { done: part.done, total: part.total })) : null,
            h('span', { class: 'series-action' }, words[ACTION_WORD[part.state]]),
          ),
        ),
      ),
    ),
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

// The sidebar's middle section on the map: no progress count and no course list.
export function renderSeriesNav() {
  return h('div', { class: 'steps-spacer', key: 'steps-spacer' });
}
