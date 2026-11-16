// Small DOM helpers. All strings become text nodes, never markup; this file
// (and the whole UI) does not touch innerHTML.
//
// morph() updates existing DOM to match a freshly built tree. It reuses
// elements, so a state refetch keeps focus, selection and scroll position.

const SKIP_ATTR_FOR = { DETAILS: new Set(['open']) };

function dispatch(event) {
  const fn = this.__on && this.__on[event.type];
  if (fn) return fn.call(this, event);
  return undefined;
}

function bindEvents(el, handlers) {
  el.__on = handlers || null;
  if (!handlers) return;
  el.__bound = el.__bound || new Set();
  for (const type of Object.keys(handlers)) {
    if (!el.__bound.has(type)) {
      el.addEventListener(type, dispatch);
      el.__bound.add(type);
    }
  }
}

function appendChildren(el, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false || child === true) continue;
    if (Array.isArray(child)) appendChildren(el, child);
    else if (child instanceof Node) el.appendChild(child);
    else el.appendChild(document.createTextNode(String(child)));
  }
}

// h('div', {class: 'x', onClick: fn, key: 'k'}, 'text', childNode)
export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  const on = {};
  let hasOn = false;
  let value;
  let hasValue = false;
  let checked;
  let hasChecked = false;
  for (const [name, val] of Object.entries(props || {})) {
    if (val === null || val === undefined || val === false) {
      if (name === 'checked') {
        hasChecked = true;
        checked = false;
      }
      continue;
    }
    if (name === 'key') el.setAttribute('data-key', String(val));
    else if (name === 'value') {
      hasValue = true;
      value = val;
    } else if (name === 'checked') {
      hasChecked = true;
      checked = !!val;
    } else if (name.length > 2 && name.startsWith('on') && typeof val === 'function') {
      on[name.slice(2).toLowerCase()] = val;
      hasOn = true;
    } else {
      el.setAttribute(name, val === true ? '' : String(val));
    }
  }
  appendChildren(el, children);
  if (hasValue) {
    el.value = value;
    el.__hasValue = true;
  }
  if (hasChecked) {
    el.checked = checked;
    el.__hasChecked = true;
  }
  if (hasOn) bindEvents(el, on);
  return el;
}

function keyOf(node) {
  if (node.nodeType !== 1) return null;
  return node.getAttribute('data-key') || node.id || null;
}

function sameType(a, b) {
  return a.nodeType === b.nodeType && a.nodeName === b.nodeName;
}

function morphAttributes(a, b) {
  const skip = SKIP_ATTR_FOR[a.tagName];
  for (const attr of Array.from(a.attributes)) {
    if (!b.hasAttribute(attr.name) && !(skip && skip.has(attr.name))) a.removeAttribute(attr.name);
  }
  for (const attr of Array.from(b.attributes)) {
    if (a.getAttribute(attr.name) !== attr.value && !(skip && skip.has(attr.name))) {
      a.setAttribute(attr.name, attr.value);
    }
  }
}

function morphNode(a, b) {
  if (a.nodeType === 3) {
    if (a.nodeValue !== b.nodeValue) a.nodeValue = b.nodeValue;
    return;
  }
  if (a.nodeType !== 1) return;
  morphAttributes(a, b);
  morphChildren(a, b);
  bindEvents(a, b.__on || null);
  a.__hasValue = b.__hasValue;
  a.__hasChecked = b.__hasChecked;
  if (b.__hasValue && document.activeElement !== a && a.value !== b.value) a.value = b.value;
  if (b.__hasChecked && a.checked !== b.checked) a.checked = b.checked;
}

function morphChildren(a, b) {
  const oldKids = Array.from(a.childNodes);
  const newKids = Array.from(b.childNodes);
  const oldByKey = new Map();
  const oldPlain = [];
  for (const n of oldKids) {
    const k = keyOf(n);
    if (k) oldByKey.set(k, n);
    else oldPlain.push(n);
  }
  const matches = new Map();
  const used = new Set();
  let plainIndex = 0;
  for (const nk of newKids) {
    const k = keyOf(nk);
    if (k) {
      const m = oldByKey.get(k);
      if (m && sameType(m, nk)) {
        matches.set(nk, m);
        used.add(m);
      }
    } else {
      while (plainIndex < oldPlain.length && !sameType(oldPlain[plainIndex], nk)) plainIndex += 1;
      if (plainIndex < oldPlain.length) {
        matches.set(nk, oldPlain[plainIndex]);
        used.add(oldPlain[plainIndex]);
        plainIndex += 1;
      }
    }
  }
  for (const n of oldKids) if (!used.has(n)) a.removeChild(n);
  let cursor = a.firstChild;
  for (const nk of newKids) {
    const m = matches.get(nk);
    if (m) {
      if (m === cursor) cursor = cursor.nextSibling;
      else a.insertBefore(m, cursor);
      morphNode(m, nk);
    } else {
      a.insertBefore(nk, cursor);
    }
  }
}

// Replace root's content with nodes, reusing what already exists.
export function morph(root, ...nodes) {
  const scratch = document.createElement(root.tagName);
  appendChildren(scratch, nodes);
  morphChildren(root, scratch);
}
