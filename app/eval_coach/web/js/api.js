// HTTP layer. The token is kept in sessionStorage so that a reload of this tab
// keeps working; it never stays in the address bar.

let token = null;
const STORAGE_KEY = 'eval-coach-token';

function storeToken(value) {
  try {
    sessionStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Storage can be blocked; the token then lives only in this module's memory.
  }
}

function loadStoredToken() {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function forgetToken() {
  token = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing was stored.
  }
}

const NOT_RESPONDING =
  'eval-coach is not responding. If you closed its window, start it again and then reopen this page from the link it gives you.';

export class ApiError extends Error {
  constructor(code, message, state) {
    super(message);
    this.code = code;
    this.state = state || null;
  }
}

export function readTokenOnce() {
  const url = new URL(window.location.href);
  if (url.searchParams.has('t')) {
    token = url.searchParams.get('t') || null;
    if (token) storeToken(token);
    url.searchParams.delete('t');
    const query = url.searchParams.toString();
    window.history.replaceState(window.history.state, '', url.pathname + (query ? `?${query}` : '') + url.hash);
  } else if (!token) {
    token = loadStoredToken();
  }
  return Boolean(token);
}

export function streamUrl(after) {
  let url = `/api/terminal/stream?t=${encodeURIComponent(token)}`;
  if (after !== null && after !== undefined) url += `&after=${encodeURIComponent(after)}`;
  return url;
}

function statusMessage(status) {
  if (status === 401 || status === 403) {
    return 'This page no longer has permission to talk to eval-coach. Close this tab and start eval-coach again.';
  }
  if (status === 413) return 'That text is too large to send. Try a shorter version.';
  if (status >= 500) return 'Something went wrong inside eval-coach. Try again; if it keeps happening, restart it.';
  return `eval-coach could not handle that request (error ${status}).`;
}

async function parse(resp) {
  let body = null;
  try {
    body = await resp.json();
  } catch {
    body = null;
  }
  return body;
}

export async function apiGetState(stepId, partId) {
  const query = [];
  if (stepId) query.push(`step=${encodeURIComponent(stepId)}`);
  if (partId) query.push(`part=${encodeURIComponent(partId)}`);
  const path = query.length ? `/api/state?${query.join('&')}` : '/api/state';
  let resp;
  try {
    resp = await fetch(path, { headers: { 'X-Eval-Token': token }, cache: 'no-store' });
  } catch {
    throw new ApiError('not_responding', NOT_RESPONDING);
  }
  const body = await parse(resp);
  if (resp.ok && body && typeof body.configured === 'boolean') return body;
  if (resp.status === 401) forgetToken();
  if (body && body.error) throw new ApiError(body.error.code, body.error.message, body.state);
  throw new ApiError(`http_${resp.status}`, statusMessage(resp.status));
}

// Any other GET route (lesson, kit file, review). Returns the whole JSON body.
export async function apiGet(path) {
  let resp;
  try {
    resp = await fetch(path, { headers: { 'X-Eval-Token': token }, cache: 'no-store' });
  } catch {
    throw new ApiError('not_responding', NOT_RESPONDING);
  }
  const body = await parse(resp);
  if (resp.ok && body && body.ok === true) return body;
  if (resp.status === 401) forgetToken();
  if (body && body.error) throw new ApiError(body.error.code, body.error.message, body.state);
  throw new ApiError(`http_${resp.status}`, statusMessage(resp.status));
}

export async function apiPost(path, data) {
  let resp;
  try {
    resp = await fetch(path, {
      method: 'POST',
      headers: { 'X-Eval-Token': token, 'Content-Type': 'application/json' },
      body: JSON.stringify(data || {}),
      cache: 'no-store',
    });
  } catch {
    throw new ApiError('not_responding', NOT_RESPONDING);
  }
  const body = await parse(resp);
  if (body && body.ok === true) return body;
  if (resp.status === 401) forgetToken();
  if (body && body.error) throw new ApiError(body.error.code, body.error.message, body.state);
  throw new ApiError(`http_${resp.status}`, statusMessage(resp.status));
}
