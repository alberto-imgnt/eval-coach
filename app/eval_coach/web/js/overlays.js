// Read-only panels that open over the page: the file viewer, the glossary and the review queue.
// They are native <dialog> elements, so focus stays inside and Escape closes them.

import { h, morph } from './dom.js';

let overlayCount = 0;

function fmt(template, vars) {
  return String(template || '').replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] !== undefined ? vars[k] : m));
}

export function openOverlay({ title, className, closeLabel, onClose }) {
  const opener = document.activeElement;
  overlayCount += 1;
  const titleId = `overlay-title-${overlayCount}`;
  const body = h('div', { class: 'overlay-body' });
  const dialog = h(
    'dialog',
    {
      class: `overlay ${className || ''}`.trim(),
      'aria-labelledby': titleId,
      onClose: () => {
        dialog.remove();
        if (opener && opener.isConnected && typeof opener.focus === 'function') opener.focus();
        if (onClose) onClose();
      },
      onClick: (event) => {
        if (event.target === dialog) dialog.close();
      },
    },
    h(
      'div',
      { class: 'overlay-inner' },
      h(
        'div',
        { class: 'overlay-head' },
        h('h2', { id: titleId }, title),
        h('button', { type: 'button', class: 'btn', id: `overlay-close-${overlayCount}`, onClick: () => dialog.close() }, closeLabel || 'Close'),
      ),
      body,
    ),
  );
  document.body.appendChild(dialog);
  dialog.showModal();
  return {
    dialog,
    close: () => dialog.close(),
    render: (...nodes) => morph(body, ...nodes),
  };
}

// ---- file viewer --------------------------------------------------------

export async function openFileViewer({ text, ref, label, load }) {
  const panel = openOverlay({
    title: fmt(text.viewer_title, { name: label || ref }),
    className: 'overlay-viewer',
    closeLabel: text.dialog_close,
  });
  panel.render(h('p', { class: 'hint', role: 'status' }, text.viewer_loading));
  try {
    const kit = await load(ref);
    panel.render(h('pre', { class: 'mono-block viewer-text', tabindex: '0', 'aria-label': kit.name }, kit.text));
  } catch (err) {
    panel.render(h('p', { class: 'bad-text', role: 'alert' }, err && err.message ? err.message : String(err)));
  }
}

// ---- glossary -----------------------------------------------------------

function termId(term) {
  return `term-${String(term).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
}

export async function openGlossary({ text, load, lessonLink, onOpenLesson, focusTerm }) {
  const panel = openOverlay({ title: text.glossary_title, className: 'overlay-glossary', closeLabel: text.dialog_close });
  panel.render(h('p', { class: 'hint', role: 'status' }, text.viewer_loading));
  let data;
  try {
    data = await load();
  } catch (err) {
    panel.render(h('p', { class: 'bad-text', role: 'alert' }, err && err.message ? err.message : String(err)));
    return;
  }
  const wanted = focusTerm ? String(focusTerm).toLowerCase() : null;
  const labels = (data.reference || {});
  const groups = [
    { kind: 'idea', label: labels.glossary_ideas },
    { kind: 'course', label: labels.glossary_course },
  ];
  const termRows = (entries) =>
    entries.flatMap((entry) => {
      const link = entry.lesson ? lessonLink(entry.lesson) : null;
      const isWanted = wanted && entry.term.toLowerCase() === wanted;
      return [
        h('dt', { key: termId(entry.term), id: termId(entry.term), tabindex: '-1', class: isWanted ? 'is-wanted' : '' }, entry.term),
        h(
          'dd',
          { key: `${termId(entry.term)}-meaning` },
          entry.meaning,
          link
            ? h(
                'button',
                {
                  type: 'button',
                  class: 'btn btn-quiet',
                  onClick: () => {
                    panel.close();
                    onOpenLesson(link.id);
                  },
                },
                fmt(text.open_lesson, { title: link.title }),
              )
            : null,
        ),
      ];
    });
  panel.render(
    h(
      'p',
      { class: 'hint', key: 'ref-link' },
      h('a', { href: 'reference.html', target: '_blank', rel: 'noopener noreferrer' }, text.glossary_reference_link),
    ),
    ...groups.flatMap(({ kind, label }) => {
      const entries = data.glossary.filter((entry) => entry.kind === kind);
      if (!entries.length) return [];
      return [
        h('h3', { key: `group-${kind}`, class: 'glossary-group' }, label),
        h('dl', { class: 'glossary-list', key: `terms-${kind}` }, termRows(entries)),
      ];
    }),
  );
  if (wanted) {
    const target = panel.dialog.querySelector('.is-wanted');
    if (target) {
      target.scrollIntoView({ block: 'center' });
      target.focus({ preventScroll: true });
    }
  }
}

// ---- review queue -------------------------------------------------------

export async function openReview({ text, load, answer, onClose }) {
  const panel = openOverlay({ title: text.review_heading, className: 'overlay-review', closeLabel: text.review_close, onClose });
  const local = { items: null, index: 0, option: null, outcome: null, busy: false, error: null };

  function view() {
    if (local.error) return [h('p', { class: 'bad-text', role: 'alert', key: 'error' }, local.error)];
    if (local.items === null) return [h('p', { class: 'hint', role: 'status', key: 'loading' }, text.viewer_loading)];
    const item = local.items[local.index];
    if (!item) {
      return [
        h('p', { class: 'lede', key: 'done', role: 'status' }, fmt(text.review_progress, { n: 0 })),
        h('div', { class: 'row', key: 'done-row' }, h('button', { type: 'button', class: 'btn btn-primary', id: 'review-finish', onClick: () => panel.close() }, text.review_close)),
      ];
    }
    const left = local.items.length - local.index;
    const answered = Boolean(local.outcome);
    return [
      h('p', { class: 'hint', key: 'progress' }, fmt(text.review_progress, { n: left })),
      h('p', { class: 'hint', key: 'from' }, item.lesson_title),
      h(
        'fieldset',
        { class: 'field choice', key: `item-${item.item}` },
        h('legend', { class: 'field-label' }, item.prompt),
        h(
          'ul',
          { class: 'choice-list' },
          item.options.map((o) =>
            h(
              'li',
              { key: `opt-${o.id}`, class: 'choice-opt' },
              h(
                'label',
                { class: 'radio-card' },
                h('input', {
                  type: 'radio',
                  name: 'review-option',
                  value: o.id,
                  checked: local.option === o.id,
                  disabled: answered || local.busy,
                  onChange: () => {
                    local.option = o.id;
                    update();
                  },
                }),
                h('span', null, o.text),
              ),
            ),
          ),
        ),
      ),
      h(
        'div',
        { class: 'feedback', role: 'status', 'aria-live': 'polite', key: 'feedback' },
        answered
          ? h(
              'div',
              { class: `callout ${local.outcome.passed ? 'callout-good' : 'callout-attn'}` },
              h('strong', { class: 'block' }, local.outcome.passed ? text.review_correct : text.review_wrong),
              local.outcome.feedback,
            )
          : null,
      ),
      h(
        'div',
        { class: 'row', key: 'row' },
        answered
          ? h(
              'button',
              {
                type: 'button',
                class: 'btn btn-primary',
                id: 'review-next',
                onClick: () => {
                  local.index += 1;
                  local.option = null;
                  local.outcome = null;
                  update();
                },
              },
              text.review_next,
            )
          : h(
              'button',
              {
                type: 'button',
                class: 'btn btn-primary',
                id: 'review-submit',
                'aria-disabled': local.option && !local.busy ? null : 'true',
                onClick: async () => {
                  if (!local.option || local.busy) return;
                  local.busy = true;
                  update();
                  try {
                    local.outcome = await answer(item.item, local.option);
                  } catch (err) {
                    local.error = err && err.message ? err.message : String(err);
                  }
                  local.busy = false;
                  update();
                },
              },
              local.busy ? text.submitting : text.submit,
            ),
      ),
    ];
  }

  function update() {
    panel.render(...view());
  }

  update();
  try {
    const review = await load();
    local.items = review.items || [];
  } catch (err) {
    local.error = err && err.message ? err.message : String(err);
  }
  update();
}
