import { h } from './dom.js';

// A modal confirmation built on <dialog>, which traps focus and handles Escape.
export function confirmDialog({ title, body, confirmLabel, cancelLabel = 'Cancel', danger = false }) {
  return new Promise((resolve) => {
    let result = false;
    // A plain sentence, or a list of ready-made elements for a longer dialog.
    const bodyNode = typeof body === 'string' ? h('p', { class: 'confirm-body' }, body) : h('div', { class: 'confirm-body' }, body);
    const dialog = h(
      'dialog',
      { class: 'confirm', 'aria-labelledby': 'confirm-title', onClose: () => {
        dialog.remove();
        resolve(result);
      } },
      h('h2', { id: 'confirm-title' }, title),
      bodyNode,
      h(
        'div',
        { class: 'confirm-actions' },
        h('button', { type: 'button', class: 'btn', autofocus: true, onClick: () => dialog.close() }, cancelLabel),
        h(
          'button',
          {
            type: 'button',
            class: danger ? 'btn btn-danger' : 'btn btn-primary',
            onClick: () => {
              result = true;
              dialog.close();
            },
          },
          confirmLabel,
        ),
      ),
    );
    document.body.appendChild(dialog);
    dialog.showModal();
  });
}
