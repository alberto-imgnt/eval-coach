// The printable reference card. It reads the same glossary and wording the app uses.
// Static page: it holds no answers and no participant data, so it needs no token.

import { h } from './dom.js';

const MESSAGE_LOAD = 'The reference could not be loaded. Close this tab and open it again from eval-coach.';

function build(data) {
  const text = data.reference;
  document.title = text.page_title;
  const termGroups = [
    { kind: 'idea', label: text.glossary_ideas },
    { kind: 'course', label: text.glossary_course },
  ];
  return [
    h(
      'header',
      { class: 'ref-head' },
      h('h1', null, text.heading),
      h('button', { type: 'button', class: 'ref-print', id: 'ref-print', onClick: () => window.print() }, text.print),
    ),
    h(
      'section',
      { class: 'ref-method', 'aria-labelledby': 'ref-method-h' },
      h('h2', { id: 'ref-method-h' }, text.method_heading),
      h('p', { class: 'ref-loop-line' }, text.method_line),
    ),
    h(
      'section',
      { class: 'ref-loop', 'aria-labelledby': 'ref-loop-h' },
      h('h2', { id: 'ref-loop-h' }, text.loop_heading),
      text.loop_lines.map((line) => h('p', { class: 'ref-course-line' }, line)),
    ),
    h(
      'section',
      { class: 'ref-verdicts', 'aria-labelledby': 'ref-verdicts-h' },
      h('h2', { id: 'ref-verdicts-h' }, text.verdicts_heading),
      h(
        'ul',
        { class: 'ref-verdict-list' },
        text.verdicts.map((v) =>
          h('li', { class: `ref-verdict v-${v.name.replace(/\s+/g, '-').toLowerCase()}` }, h('strong', null, v.name), h('span', null, v.meaning)),
        ),
      ),
    ),
    h(
      'section',
      { class: 'ref-glossary', 'aria-labelledby': 'ref-glossary-h' },
      h('h2', { id: 'ref-glossary-h' }, text.glossary_heading),
      termGroups.flatMap(({ kind, label }) => {
        // A term with card: false (Part 1's) is in the in-app glossary only, which keeps this one-page card to Part 3's terms.
        const entries = data.glossary.filter((entry) => entry.kind === kind && entry.card !== false);
        if (!entries.length) return [];
        return [
          h('h3', { class: 'ref-group' }, label),
          h(
            'dl',
            { class: 'ref-terms' },
            entries.map((entry) => h('div', { class: 'ref-term' }, h('dt', null, entry.term), h('dd', null, entry.meaning))),
          ),
        ];
      }),
    ),
    h(
      'section',
      { class: 'ref-principles', 'aria-labelledby': 'ref-principles-h' },
      h('h2', { id: 'ref-principles-h' }, text.principles_heading),
      h('ul', { class: 'ref-principle-list' }, text.principles.map((p) => h('li', null, p))),
    ),
  ];
}

async function main() {
  const root = document.getElementById('reference');
  try {
    const resp = await fetch('reference-data.json', { cache: 'no-store' });
    if (!resp.ok) throw new Error(`http ${resp.status}`);
    root.replaceChildren(...build(await resp.json()));
  } catch {
    root.replaceChildren(h('p', { class: 'ref-error', role: 'alert' }, MESSAGE_LOAD));
  }
}

main();
