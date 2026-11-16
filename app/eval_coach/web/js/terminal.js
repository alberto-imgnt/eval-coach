// The embedded terminal: xterm.js, the SSE stream and keystroke forwarding.

import { apiPost, streamUrl } from './api.js';

const INPUT_BATCH_MS = 12;
const MAX_INPUT_BYTES = 256 * 1024;
const RECONNECT_MIN_MS = 500;
const RECONNECT_MAX_MS = 5000;
const BASE_FONT_PX = 14;

// The terminal text follows the app's text size, so it is rounded to whole pixels.
function terminalFontSize() {
  const display = window.EvalCoachDisplay;
  return Math.round(BASE_FONT_PX * (display ? display.size() / 100 : 1));
}

export function base64ToBytes(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function bytesToBase64(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export function createTerminal({ onState, onExit, onConnection, onError, onLeave }) {
  const term = new window.Terminal({
    convertEol: false,
    cursorBlink: true,
    fontFamily: '"Cascadia Mono", Consolas, "SF Mono", Menlo, monospace',
    fontSize: terminalFontSize(),
    lineHeight: 1.2,
    scrollback: 5000,
    disableStdin: true,
    theme: {
      background: '#101018',
      foreground: '#e9e9f2',
      cursor: '#d6ff3e',
      cursorAccent: '#101018',
      selectionBackground: '#3a2f8a',
    },
  });
  const fitAddon = new window.FitAddon.FitAddon();
  term.loadAddon(fitAddon);

  let host = null;
  let opened = false;
  let running = false;
  let lastSent = null;

  // ---- keystrokes -----------------------------------------------------
  const encoder = new TextEncoder();
  let inputQueue = [];
  let inputTimer = null;
  let inputFlushing = false;

  function enqueueInput(bytes) {
    inputQueue.push(bytes);
    if (inputTimer === null && !inputFlushing) inputTimer = setTimeout(flushInput, INPUT_BATCH_MS);
  }

  function takeBatch() {
    let total = 0;
    let count = 0;
    while (count < inputQueue.length && total + inputQueue[count].length <= MAX_INPUT_BYTES) {
      total += inputQueue[count].length;
      count += 1;
    }
    if (count === 0) {
      // A single enormous paste: send it in slices.
      count = 1;
      const big = inputQueue[0];
      inputQueue.unshift(big.slice(0, MAX_INPUT_BYTES));
      inputQueue[1] = big.slice(MAX_INPUT_BYTES);
      total = MAX_INPUT_BYTES;
    }
    const batch = new Uint8Array(total);
    let offset = 0;
    for (const chunk of inputQueue.slice(0, count)) {
      batch.set(chunk, offset);
      offset += chunk.length;
    }
    inputQueue = inputQueue.slice(count);
    return batch;
  }

  async function flushInput() {
    inputTimer = null;
    if (inputFlushing) return;
    inputFlushing = true;
    try {
      while (inputQueue.length) {
        const batch = takeBatch();
        // eslint-disable-next-line no-await-in-loop
        await apiPost('/api/terminal/input', { data: bytesToBase64(batch) });
      }
    } catch (err) {
      inputQueue = [];
      onError(err);
    } finally {
      inputFlushing = false;
      if (inputQueue.length && inputTimer === null) inputTimer = setTimeout(flushInput, 0);
    }
  }

  term.onData((data) => {
    if (running) enqueueInput(encoder.encode(data));
  });
  term.onBinary((data) => {
    if (!running) return;
    const bytes = new Uint8Array(data.length);
    for (let i = 0; i < data.length; i += 1) bytes[i] = data.charCodeAt(i) & 0xff;
    enqueueInput(bytes);
  });

  term.attachCustomKeyEventHandler((event) => {
    if (event.type !== 'keydown') return true;
    if (event.key === 'F6') {
      event.preventDefault();
      onLeave();
      return false;
    }
    if (event.ctrlKey && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'c' && term.hasSelection()) {
      return false;
    }
    return true;
  });

  // ---- sizing ---------------------------------------------------------
  let resizeTimer = null;

  function hostVisible() {
    return Boolean(host && host.offsetParent !== null && host.clientWidth > 0 && host.clientHeight > 0);
  }

  function open(hostEl) {
    host = hostEl;
    if (!opened && hostVisible()) {
      term.open(host);
      opened = true;
      fitNow();
    }
  }

  function fitNow() {
    if (!opened || !hostVisible()) return;
    try {
      fitAddon.fit();
    } catch {
      return;
    }
    sendSize();
  }

  function sendSize() {
    const size = `${term.cols}x${term.rows}`;
    if (size === lastSent) return;
    lastSent = size;
    apiPost('/api/terminal/resize', { cols: term.cols, rows: term.rows }).catch((err) => {
      if (running) onError(err);
    });
  }

  function debouncedFit() {
    if (resizeTimer !== null) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      resizeTimer = null;
      fitNow();
    }, 150);
  }

  window.addEventListener('resize', debouncedFit);
  // A new text size changes how many columns and rows fit, so the terminal refits. The CLI keeps running.
  window.addEventListener('eval-coach:text-size', () => {
    term.options.fontSize = terminalFontSize();
    debouncedFit();
  });

  function observe(el) {
    if (typeof ResizeObserver === 'function') new ResizeObserver(debouncedFit).observe(el);
  }

  // ---- stream ---------------------------------------------------------
  let source = null;
  let lastSeq = null;
  let expectNewSession = false;
  let stopped = false;
  let reconnectDelay = RECONNECT_MIN_MS;
  let hadError = false;

  function connect() {
    if (stopped) return;
    source = new EventSource(streamUrl(lastSeq));
    source.addEventListener('output', (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (typeof msg.seq !== 'number') return;
      if (!expectNewSession && lastSeq !== null && msg.seq <= lastSeq) return;
      expectNewSession = false;
      lastSeq = msg.seq;
      // xterm keeps its own UTF-8 decoder state, so multi-byte characters
      // that are split across chunks come out whole.
      term.write(base64ToBytes(msg.data));
    });
    source.addEventListener('exit', (event) => {
      let msg = {};
      try {
        msg = JSON.parse(event.data);
      } catch {
        msg = {};
      }
      onExit(typeof msg.code === 'number' ? msg.code : null);
    });
    source.addEventListener('state', () => onState());
    source.onopen = () => {
      reconnectDelay = RECONNECT_MIN_MS;
      onConnection(true);
      if (hadError) {
        hadError = false;
        onState();
      }
    };
    source.onerror = () => {
      if (stopped) return;
      source.close();
      hadError = true;
      onConnection(false);
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_MS);
    };
  }

  return {
    connect,
    open,
    observe,
    fit: fitNow,
    focus: () => term.focus(),
    setRunning(value) {
      running = Boolean(value);
      term.options.disableStdin = !running;
    },
    clearForNewSession() {
      term.reset();
      expectNewSession = true;
      lastSent = null;
    },
    syncSize() {
      lastSent = null;
      fitNow();
    },
    stop() {
      stopped = true;
      if (source) source.close();
    },
  };
}
