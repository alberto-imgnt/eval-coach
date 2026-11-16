// A small Markdown renderer that builds DOM nodes directly. Text is only ever
// placed in text nodes, so raw HTML in the source shows up as literal text.
// Links render as their text followed by the address; nothing here navigates.

import { h } from './dom.js';

const INLINE = new RegExp(
  [
    '\\\\([\\\\`*_{}\\[\\]()#+\\-.!|~>])', // 1 backslash escape
    '(`+)([\\s\\S]+?)\\2', // 2,3 code span
    '\\*\\*([\\s\\S]+?)\\*\\*', // 4 bold
    '__([\\s\\S]+?)__', // 5 bold
    '\\*([^*\\s](?:[^*]*?[^*\\s])?)\\*', // 6 emphasis
    '(?<![\\w])_([^_\\s](?:[^_]*?[^_\\s])?)_(?![\\w])', // 7 emphasis
    '\\[([^\\]]+)\\]\\(([^)\\s]+)\\)', // 8,9 link
  ].join('|'),
  'g',
);

export function renderInline(text) {
  const out = [];
  let last = 0;
  INLINE.lastIndex = 0;
  let m = INLINE.exec(text);
  while (m !== null) {
    const { index } = m;
    if (index > last) out.push(text.slice(last, index));
    last = index + m[0].length;
    if (m[1] !== undefined) out.push(m[1]);
    else if (m[3] !== undefined) out.push(h('code', null, m[3]));
    else if (m[4] !== undefined) out.push(h('strong', null, ...renderNested(m[4])));
    else if (m[5] !== undefined) out.push(h('strong', null, ...renderNested(m[5])));
    else if (m[6] !== undefined) out.push(h('em', null, ...renderNested(m[6])));
    else if (m[7] !== undefined) out.push(h('em', null, ...renderNested(m[7])));
    else if (m[8] !== undefined) {
      out.push(...renderNested(m[8]));
      out.push(` (${m[9]})`);
    }
    m = INLINE.exec(text);
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function renderNested(text) {
  // Nested spans reuse the same regex, so they cannot overlap with the outer
  // exec() loop state: renderInline() always resets lastIndex first.
  const saved = INLINE.lastIndex;
  const nested = renderInline(text);
  INLINE.lastIndex = saved;
  return nested;
}

const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const FENCE = /^(`{3,}|~{3,})\s*([\w-]*)/;
const RULE = /^(?:-{3,}|\*{3,}|_{3,})\s*$/;
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_DIVIDER = /^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$/;

function splitRow(line) {
  let row = line.trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1);
  const cells = [];
  let cell = '';
  for (let i = 0; i < row.length; i += 1) {
    if (row[i] === '\\' && row[i + 1] === '|') {
      cell += '|';
      i += 1;
    } else if (row[i] === '|') {
      cells.push(cell);
      cell = '';
    } else {
      cell += row[i];
    }
  }
  cells.push(cell);
  return cells.map((c) => c.trim());
}

function isTableStart(lines, i) {
  return lines[i].includes('|') && i + 1 < lines.length && TABLE_DIVIDER.test(lines[i + 1]) && lines[i + 1].includes('-');
}

function renderTable(lines, start) {
  const head = splitRow(lines[start]);
  let i = start + 2;
  const rows = [];
  while (i < lines.length && lines[i].trim() !== '' && lines[i].includes('|')) {
    rows.push(splitRow(lines[i]));
    i += 1;
  }
  const table = h(
    'table',
    { class: 'md-table' },
    h('thead', null, h('tr', null, head.map((c) => h('th', { scope: 'col' }, ...renderInline(c))))),
    h(
      'tbody',
      null,
      rows.map((row) => h('tr', null, head.map((_, col) => h('td', null, ...renderInline(row[col] || ''))))),
    ),
  );
  return { node: h('div', { class: 'table-scroll' }, table), next: i };
}

function renderList(lines, start) {
  // Builds nested lists from indentation. Returns the top-level node.
  const first = LIST_ITEM.exec(lines[start]);
  const rootOrdered = /\d/.test(first[2]);
  const root = h(rootOrdered ? 'ol' : 'ul', { class: 'md-list' });
  const stack = [{ indent: first[1].length, list: root, last: null }];
  let i = start;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === '') {
      const next = lines[i + 1];
      if (next !== undefined && LIST_ITEM.test(next)) {
        i += 1;
        continue;
      }
      break;
    }
    const m = LIST_ITEM.exec(line);
    if (!m) {
      const top = stack[stack.length - 1];
      if (/^\s+\S/.test(line) && top.last) {
        top.last.append(` ${line.trim()}`);
        i += 1;
        continue;
      }
      break;
    }
    const indent = m[1].length;
    while (stack.length > 1 && indent < stack[stack.length - 1].indent) stack.pop();
    let top = stack[stack.length - 1];
    if (indent > top.indent && top.last) {
      const list = h(/\d/.test(m[2]) ? 'ol' : 'ul', { class: 'md-list' });
      top.last.appendChild(list);
      top = { indent, list, last: null };
      stack.push(top);
    }
    const item = h('li', null, ...renderInline(m[3]));
    top.list.appendChild(item);
    top.last = item;
    i += 1;
  }
  return { node: root, next: i };
}

// The route map's row title and screen-reader label come from the interface text (ui.map_title, ui.map_aria).
// renderMarkdown has no context, so the text is set once when the interface text loads.
let mapText = { title: '', aria: '', label: '' };

export function setMapText(ui) {
  mapText = { title: (ui && ui.map_title) || '', aria: (ui && ui.map_aria) || '', label: (ui && ui.map_label) || '' };
}

function fillMapText(template, vars) {
  return template.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
}

const MAP_STOPS = {
  done: { tag: 'Done', cls: 'is-done' },
  here: { tag: 'You are here', cls: 'is-here' },
  next: { tag: 'Ahead', cls: 'is-next' },
};

// A fenced block tagged "you-are-here" holds one stop per line:
// "done|here|next | number | title | one line". It renders as a route map.
function renderRouteMap(body) {
  const stops = body
    .map((line) => splitRow(line))
    .filter((cells) => cells.length >= 4 && MAP_STOPS[cells[0]]);
  if (!stops.length) return h('pre', { class: 'md-code' }, h('code', null, body.join('\n')));
  const current = stops.find((s) => s[0] === 'here');
  return h(
    'figure',
    { class: 'route-map' },
    h(
      'ol',
      { class: 'route-stops', 'aria-label': current ? fillMapText(mapText.aria, { n: current[1], total: stops.length }) : mapText.label },
      stops.map(([status, num, title, line]) => {
        const { tag, cls } = MAP_STOPS[status];
        return h(
          'li',
          { class: `route-stop ${cls}`, 'aria-current': status === 'here' ? 'step' : null },
          h('span', { class: 'route-node', 'aria-hidden': 'true' }, num),
          h(
            'div',
            { class: 'route-card' },
            h('span', { class: 'route-pin' }, status === 'here' ? h('span', { class: 'route-pin-icon', 'aria-hidden': 'true' }) : null, tag),
            h('strong', { class: 'route-title' }, fillMapText(mapText.title, { n: num }), ...renderInline(title)),
            h('span', { class: 'route-line' }, ...renderInline(line)),
          ),
        );
      }),
    ),
  );
}

// Headings start at h4 because the answer key sits under an h2/h3 in the app.
const HEADING_LEVEL = ['h4', 'h4', 'h5', 'h5', 'h6', 'h6'];

export function renderMarkdown(source) {
  const nodes = [];
  const lines = String(source).replace(/\r\n?/g, '\n').split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === '') {
      i += 1;
      continue;
    }

    const fence = FENCE.exec(line);
    if (fence) {
      const body = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith(fence[1])) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1;
      nodes.push(fence[2] === 'you-are-here' ? renderRouteMap(body) : h('pre', { class: 'md-code' }, h('code', null, body.join('\n'))));
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      nodes.push(h(HEADING_LEVEL[heading[1].length - 1], { class: 'md-heading' }, ...renderInline(heading[2])));
      i += 1;
      continue;
    }

    if (RULE.test(line.trim())) {
      nodes.push(h('hr', { class: 'md-rule' }));
      i += 1;
      continue;
    }

    if (isTableStart(lines, i)) {
      const { node, next } = renderTable(lines, i);
      nodes.push(node);
      i = next;
      continue;
    }

    if (LIST_ITEM.test(line)) {
      const { node, next } = renderList(lines, i);
      nodes.push(node);
      i = next;
      continue;
    }

    if (line.trimStart().startsWith('>')) {
      const body = [];
      while (i < lines.length && lines[i].trimStart().startsWith('>')) {
        body.push(lines[i].trimStart().replace(/^>\s?/, ''));
        i += 1;
      }
      nodes.push(h('blockquote', { class: 'md-quote' }, ...renderMarkdown(body.join('\n'))));
      continue;
    }

    const para = [line.trim()];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !HEADING.test(lines[i]) &&
      !FENCE.test(lines[i]) &&
      !RULE.test(lines[i].trim()) &&
      !LIST_ITEM.test(lines[i]) &&
      !lines[i].trimStart().startsWith('>') &&
      !isTableStart(lines, i)
    ) {
      para.push(lines[i].trim());
      i += 1;
    }
    nodes.push(h('p', { class: 'md-p' }, ...renderInline(para.join(' '))));
  }
  return nodes;
}
