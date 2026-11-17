// The "Your AI window" mini lesson: an annotated screenshot with numbered markers and a text legend.
// It is shown on the last wizard page and in a dialog opened from Settings and from the AI window.
// Every word and every marker position comes from content/preflight.json (state.preflight.ai_window_lesson).

import { h } from './dom.js';
import { openOverlay } from './overlays.js';
import { actionButton } from './ui.js';

function fmt(template, vars) {
  return String(template || '').replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] !== undefined ? vars[k] : m));
}

// The screenshot entry for the chosen AI, or null when there is none (the stand-in, or no capture yet).
function screenshotFor(pf) {
  const entry = pf.ai_window_lesson.tools[pf.cli.tool];
  return entry && entry.image && entry.markers.length ? entry : null;
}

export function renderAiWindowLesson(ctx, idPrefix = 'ai-lesson') {
  const pf = ctx.state.preflight;
  const lesson = pf.ai_window_lesson;
  const shot = screenshotFor(pf);
  const markers = shot ? shot.markers : lesson.generic.markers;
  const tipId = (n) => `${idPrefix}-tip-${n}`;
  return h(
    'section',
    { class: 'ai-lesson', id: idPrefix, key: idPrefix },
    h('p', { class: 'ai-lesson-intro', key: 'intro' }, lesson.intro),
    shot
      ? h(
          'figure',
          { class: 'ai-shot', key: 'shot' },
          h(
            'div',
            { class: 'ai-shot-frame' },
            h('img', { class: 'ai-shot-img', src: shot.image, alt: shot.alt }),
            // The part of the picture each marker describes, shown while its marker (or legend entry) is hovered or focused.
            markers
              .filter((m) => m.box)
              .map((m) =>
                h('span', {
                  class: 'ai-region',
                  key: `region-${m.n}`,
                  'data-n': String(m.n),
                  'aria-hidden': 'true',
                  style: `left:${m.box.x}%;top:${m.box.y}%;width:${m.box.w}%;height:${m.box.h}%`,
                }),
              ),
            markers.map((m) =>
              h(
                'span',
                {
                  class: m.x > 60 ? 'ai-marker is-right' : m.x < 40 ? 'ai-marker is-left' : 'ai-marker',
                  key: `marker-${m.n}`,
                  id: `${idPrefix}-marker-${m.n}`,
                  'data-n': String(m.n),
                  tabindex: '0',
                  role: 'img',
                  'aria-label': `${m.n}. ${m.label}`,
                  'aria-describedby': tipId(m.n),
                  style: `left:${m.x}%;top:${m.y}%`,
                },
                String(m.n),
                h('span', { class: 'ai-tip', role: 'tooltip', id: tipId(m.n) }, h('strong', null, m.label), ' ', m.text),
              ),
            ),
          ),
          shot.captured ? h('figcaption', { class: 'hint' }, fmt(lesson.captured_label, { date: shot.captured })) : null,
        )
      : h('p', { class: 'hint', id: `${idPrefix}-generic`, key: 'generic' }, lesson.alt_generic),
    h('h3', { key: 'legend-heading' }, lesson.legend_heading),
    h(
      'ol',
      { class: 'ai-legend', id: `${idPrefix}-legend`, key: 'legend' },
      markers.map((m) => h('li', { key: `legend-${m.n}`, 'data-n': String(m.n) }, h('strong', null, m.label), ' ', m.text)),
    ),
  );
}

// "What am I looking at?" opens the lesson in a dialog and closes back to where the participant was.
export function openAiWindowLesson(ctx) {
  const lesson = ctx.state.preflight.ai_window_lesson;
  const panel = openOverlay({ title: lesson.title, className: 'overlay-ai-window', closeLabel: lesson.close });
  panel.render(renderAiWindowLesson(ctx, 'ai-lesson-dialog'));
}

export function aiWindowLink(ctx, id = 'ai-window-open') {
  const pf = ctx.state && ctx.state.preflight;
  if (!pf || !pf.ai_window_lesson) return null;
  return actionButton(ctx, { label: pf.ai_window_lesson.reopen_label, id, kind: 'quiet', onClick: () => openAiWindowLesson(ctx) });
}
