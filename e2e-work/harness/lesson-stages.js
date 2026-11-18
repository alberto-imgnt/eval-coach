// Stand-in end-to-end stages for the lessons. The harness acts as an API client of the
// real running app. It never reads answers from a page; it reads content/lessons.json for expected
// answers and asserts that no response carries them before they are answered.
// CLI activities run ONLY against the stand-in e2e-work/harness/fake_cli.py.
const L = require('./lib');
const fs = require('fs');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const http = require('http');

const { state } = L;
const HOME = L.HOME;
const PROJECT = L.PROJECT;
const APP = path.join(L.ROOT, 'app', 'eval_coach');
const KIT = path.join(APP, 'kit');
const CONTENT = JSON.parse(fs.readFileSync(path.join(APP, 'content', 'lessons.json'), 'utf8'));
const P1_CONTENT = JSON.parse(fs.readFileSync(path.join(APP, 'content', 'part-1-lessons.json'), 'utf8'));
const P1_STEPS = JSON.parse(fs.readFileSync(path.join(APP, 'content', 'part-1-steps.json'), 'utf8')).steps;
const P2_CONTENT = JSON.parse(fs.readFileSync(path.join(APP, 'content', 'part-2-lessons.json'), 'utf8'));
const EVENTS = path.join(L.WORK, 'fake-cli-events.jsonl');
const MODE_FILE = path.join(L.WORK, 'fake-cli-mode.txt');
const PROGRESS = path.join(PROJECT, '.learning', 'progress.json');
const PENDING = path.join(HOME, 'pending-lessons.json');

const MISSION_TEXT = 'Understand how to turn the test cases, criteria and thresholds from Part 2 into reusable parts, and how those parts fit into an evaluated AI process.';
const HOOK_LINE = 'Read update.txt and requirements.md. Score the update from 1 to 10 against the requirements, say pass or fail, and give one sentence of reasoning. Save only that to output.txt. Do nothing else.';
const DAY = 86400;
const FORBIDDEN_KEYS = ['correct', 'expected', 'bucket', 'feedback_right', 'feedback_wrong'];

const lessonDef = (id) => CONTENT.lessons.find((l) => l.id === id) || P1_CONTENT.lessons.find((l) => l.id === id) || P2_CONTENT.lessons.find((l) => l.id === id);
const sleep = L.sleep;
const exists = (p) => fs.existsSync(p);
const readText = (p) => fs.readFileSync(p, 'utf8');
const readJson = (p) => JSON.parse(readText(p).replace(/^\uFEFF/, ''));
const hasText = (p) => exists(p) && readText(p).trim().length > 0;
const nowSec = () => Date.now() / 1000;

// ---- checks -------------------------------------------------------------------
// Soft checks keep going so one run reports every problem; endStage fails the stage if any failed.
let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures += 1;
  L.softAssertion(name, ok, detail);
}
function must(name, ok, detail) { L.assertion(name, ok, detail); }
function endStage(name) {
  if (failures) throw new Error(`${name}: ${failures} check(s) failed`);
}
function requireStandIn() {
  if (!L.STANDIN || !L.CLI_COMMAND.includes('fake_cli.py') || !/standin-home(-pf)?$/.test(HOME)) {
    throw new Error('lesson stages run only with E2E_PROFILE=standin and the stand-in CLI (never a real CLI)');
  }
}

// ---- HTTP client --------------------------------------------------------------
let target = null; // another server (the migration stage) instead of the main one
const tgt = () => target || { port: state.port, token: state.token };

const kitKeyLines = (() => {
  const p = path.join(KIT, 'northwind', 'answer-key.md');
  return exists(p) ? readText(p).split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length >= 40) : [];
})();

function scanForKey(route, text) {
  if (route.startsWith('/api/state') || route.startsWith('/api/step') || route.startsWith('/api/terminal')) return;
  const hit = kitKeyLines.find((line) => text.includes(line) || text.includes(JSON.stringify(line).slice(1, -1)));
  if (hit) L.violation(`answer key text leaked via ${route}: ${hit.slice(0, 80)}`);
}

function httpCall(t, method, route, headers, payload) {
  // Plain http with no keep-alive agent: nothing is left open when the process exits.
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: t.port, path: route, method, headers: { ...headers, Connection: 'close', ...(payload !== undefined ? { 'Content-Length': Buffer.byteLength(payload) } : {}) }, agent: false }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({ status: res.statusCode, text: Buffer.concat(chunks).toString('utf8') }));
    });
    req.on('error', reject);
    req.setTimeout(60000, () => req.destroy(new Error(`timeout calling ${route}`)));
    if (payload !== undefined) req.write(payload);
    req.end();
  });
}

async function api(method, route, body, opts = {}) {
  const t = tgt();
  const headers = {};
  if (opts.token !== null) headers['X-Eval-Token'] = opts.token === undefined ? t.token : opts.token;
  let payload;
  if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  const { status, text } = await httpCall(t, method, route, headers, payload);
  let json = null;
  try { json = JSON.parse(text); } catch { /* not JSON */ }
  scanForKey(route, text);
  return { status, text, json, ok: status === 200 && Boolean(json) && json.ok === true, code: json && json.error ? json.error.code : null, message: json && json.error ? json.error.message : '' };
}
const get = (route, opts) => api('GET', route, undefined, opts);
const post = (route, body, opts) => api('POST', route, body === undefined ? {} : body, opts);
let activePart = null; // the Part whose state getState reads; null is Part 3, the server's default
const getState = async () => { const r = await get(activePart ? `/api/state?part=${activePart}` : '/api/state'); return r.json; };
const viewLesson = (id) => get(`/api/lesson?id=${encodeURIComponent(id)}`);
const lessonOf = (r) => r.json.lesson;
const actView = (lesson, id) => lesson.activities.find((a) => a.id === id);

function courseMap(s) { return Object.fromEntries(s.course.map((c) => [c.id, c.status])); }

// ---- files the app wrote ---------------------------------------------------------
function lessonsBlock() {
  if (exists(PROGRESS)) return readJson(PROGRESS).lessons;
  return readJson(PENDING);
}
const entryOf = (lessonId, actId) => (((lessonsBlock().per_lesson[lessonId] || {}).activities || {})[actId]);

// ---- answers: expected values come from the content file -----------------------
function correctAnswer(act) {
  switch (act.type) {
    case 'choice': return { option: act.options.find((o) => o.correct).id };
    case 'order': return { order: act.items.map((i) => i.id) };
    case 'sort': return { placements: Object.fromEntries(act.items.map((i) => [i.id, i.bucket])) };
    case 'rule_lab': return { cases: Object.fromEntries(act.cases.map((c, n) => [`${c.sample}|${c.rule}`, n % 2 ? c.expected.toUpperCase() : c.expected])) };
    case 'reflection': return { text: 'I would quote the threshold above each rule so the checker and the spec say the same thing. '.repeat(Math.ceil(act.min_words / 10) + 1).trim() };
    case 'cli_compare':
    case 'cli_practice': return { option: act.question.options.find((o) => o.correct).id };
    default: throw new Error(`no answer for ${act.type}`);
  }
}
function wrongAnswer(act) {
  switch (act.type) {
    case 'choice': return { option: act.options.find((o) => !o.correct).id };
    case 'order': return { order: act.items.map((i) => i.id).reverse() };
    case 'sort': return { placements: Object.fromEntries(act.items.map((i) => [i.id, act.buckets.find((b) => b.id !== i.bucket).id])) };
    case 'rule_lab': {
      const answer = correctAnswer(act);
      const first = act.cases[0];
      answer.cases[`${first.sample}|${first.rule}`] = first.expected === 'pass' ? 'fail' : 'pass';
      return answer;
    }
    case 'reflection': return { text: 'too short' };
    case 'cli_compare':
    case 'cli_practice': return { option: act.question.options.find((o) => !o.correct).id };
    default: throw new Error(`no answer for ${act.type}`);
  }
}

// ---- hidden-answer checks ----------------------------------------------------------
function keysOf(value, acc = new Set()) {
  if (Array.isArray(value)) value.forEach((v) => keysOf(v, acc));
  else if (value && typeof value === 'object') for (const [k, v] of Object.entries(value)) { acc.add(k); keysOf(v, acc); }
  return acc;
}

// Feedback strings of this activity that a response may not carry yet.
function hiddenTexts(act, chosen) {
  const out = [];
  const options = act.question ? act.question.options : act.options;
  if (options) for (const o of options) if (o.id !== chosen) out.push(o.feedback);
  if (act.type === 'sort') for (const i of act.items) out.push(i.feedback);
  if (act.type === 'order') out.push(act.feedback_right);
  return out.filter(Boolean);
}

// An activity view that has not been passed holds no answer, expected verdict or other option's feedback.
function assertHidden(label, view, act, chosen) {
  const keys = keysOf(view);
  const bad = FORBIDDEN_KEYS.filter((k) => keys.has(k));
  check(`${label}: view has no answer fields`, bad.length === 0, bad.join(','));
  if (!view.passed) check(`${label}: view has no per-option explanations`, !keys.has('explanations'));
  const text = JSON.stringify(view);
  const leaked = hiddenTexts(act, chosen).filter((t) => text.includes(t) || text.includes(JSON.stringify(t).slice(1, -1)));
  check(`${label}: view carries no other option's feedback`, leaked.length === 0, leaked[0] ? leaked[0].slice(0, 60) : '');
  if (act.type === 'order') {
    const listed = view.items.map((i) => i.id).join(',');
    check(`${label}: listed order is not already the answer`, listed !== act.items.map((i) => i.id).join(','));
  }
  if (act.type === 'rule_lab') {
    check(`${label}: cases carry no verdicts`, view.cases.every((c) => Object.keys(c).every((k) => ['id', 'key', 'sample', 'rule'].includes(k))));
  }
  const choiceViews = view.options ? [view.options] : view.question ? [view.question.options] : [];
  for (const options of choiceViews) check(`${label}: options carry only id and text`, options.every((o) => Object.keys(o).sort().join() === 'id,text'));
  if (view.items && act.type === 'sort') check(`${label}: sort items carry only id and text`, view.items.every((o) => Object.keys(o).sort().join() === 'id,text'));
}

function optionOrder(view) {
  const options = view.options || (view.question && view.question.options) || view.items || view.cases || [];
  return options.map((o) => o.id).join(',');
}

// ---- rule-lab checks --------------------------------------------------------------
function evalRule(rule, text) {
  const p = rule.params || {};
  const low = text.toLowerCase();
  switch (rule.kind) {
    case 'word_count_under': return text.trim().split(/\s+/).filter(Boolean).length < p.limit;
    case 'all_present': return p.terms.every((t) => low.includes(t.toLowerCase()));
    case 'none_present': return !p.terms.some((t) => low.includes(t.toLowerCase()));
    case 'all_labels': return p.labels.every((t) => text.includes(t));
    default: throw new Error(`unknown rule kind ${rule.kind}`);
  }
}

async function ruleRun(lessonId, actId, rule, text) {
  return post('/api/lesson/rule-run', { lesson: lessonId, activity: actId, rule, text });
}

async function labBefore(lessonId, act) {
  const rule = act.rules[0];
  const sample = act.samples[0];
  for (const variant of [sample.text, `  ${sample.text.toUpperCase()}  `]) {
    const r = await ruleRun(lessonId, act.id, rule.id, variant);
    check(`${lessonId}/${act.id}: a sample's own text is refused before the answer`, r.status === 400 && r.code === 'sample_before_answer', `${r.status} ${r.code}`);
    check(`${lessonId}/${act.id}: refusal does not show a verdict`, !/"verdict"/.test(r.text));
  }
  const own = 'Something I typed myself with no labels at all.';
  for (const r0 of act.rules) {
    const a = await ruleRun(lessonId, act.id, r0.id, own);
    const b = await ruleRun(lessonId, act.id, r0.id, own);
    const want = evalRule(r0, own) ? 'pass' : 'fail';
    check(`${lessonId}/${act.id}: own text on rule ${r0.id} gives ${want}`, a.ok && a.json.result.verdict === want, a.text.slice(0, 160));
    check(`${lessonId}/${act.id}: Run again gives the same verdict and reason (${r0.id})`, b.ok && b.json.result.verdict === a.json.result.verdict && b.json.result.reason === a.json.result.reason && a.json.result.reason.length > 0);
  }
  const unknown = await ruleRun(lessonId, act.id, 'no-such-rule', own);
  check(`${lessonId}/${act.id}: unknown rule refused`, unknown.status === 400 && unknown.code === 'unknown_rule', unknown.code);
  const empty = await ruleRun(lessonId, act.id, rule.id, '   ');
  check(`${lessonId}/${act.id}: empty text refused`, empty.status === 400 && empty.code === 'bad_answer' && /text/i.test(empty.message), `${empty.code} ${empty.message}`);
  const notText = await ruleRun(lessonId, act.id, rule.id, 42);
  check(`${lessonId}/${act.id}: non-text refused`, notText.status === 400, String(notText.status));
}

async function labAfter(lessonId, act) {
  for (const c of act.cases) {
    const sample = act.samples.find((s) => s.id === c.sample);
    const rule = act.rules.find((r) => r.id === c.rule);
    const r = await ruleRun(lessonId, act.id, rule.id, sample.text);
    check(`${lessonId}/${act.id}: after the answer, ${c.sample} on ${c.rule} shows ${c.expected}`, r.ok && r.json.result.verdict === c.expected && r.json.result.verdict === (evalRule(rule, sample.text) ? 'pass' : 'fail'), r.text.slice(0, 160));
  }
}

// ---- solving activities ------------------------------------------------------------
async function answer(lessonId, actId, ans) {
  return post('/api/lesson/answer', { lesson: lessonId, activity: actId, answer: ans });
}

async function malformed(lessonId, act) {
  const cases = [
    ['a plain string', 'a'],
    ['null', null],
    ['an empty object', {}],
  ];
  if (act.type === 'choice') cases.push(['an unknown option', { option: 'zzz' }]);
  if (act.type === 'order') cases.push(['a missing item', { order: act.items.slice(1).map((i) => i.id) }], ['a repeated item', { order: [act.items[0].id, ...act.items.map((i) => i.id).slice(0, -1)] }]);
  if (act.type === 'sort') cases.push(['a missing item', { placements: Object.fromEntries(act.items.slice(1).map((i) => [i.id, act.buckets[0].id])) }], ['an unknown bucket', { placements: Object.fromEntries(act.items.map((i) => [i.id, 'nope'])) }]);
  if (act.type === 'rule_lab') cases.push(['a missing case', { cases: {} }], ['a non-verdict', { cases: Object.fromEntries(act.cases.map((c) => [`${c.sample}|${c.rule}`, 'maybe'])) }]);
  if (act.type === 'reflection') cases.push(['non-text', { text: 7 }]);
  for (const [what, value] of cases) {
    const r = await answer(lessonId, act.id, value);
    check(`${lessonId}/${act.id}: malformed answer (${what}) is refused`, r.status === 400 && r.code === 'bad_answer', `${r.status} ${r.code}`);
  }
  const e = entryOf(lessonId, act.id);
  check(`${lessonId}/${act.id}: refused answers are not counted`, !e || (e.attempts === 0 && !e.passed), JSON.stringify(e));
}

// Wrong first, then right. Checks the hidden-answer rules at each point, the server's grading and the record.
async function solveActivity(lessonId, act, opts = {}) {
  const label = `${lessonId}/${act.id} (${act.type})`;
  let lesson = lessonOf(await viewLesson(lessonId));
  let view = actView(lesson, act.id);
  must(`${label}: not passed before answering`, view.passed === false);
  assertHidden(`${label} before answering`, view, act);
  if (opts.malformed) await malformed(lessonId, act);
  if (act.type === 'rule_lab') await labBefore(lessonId, act);
  const before = (lessonsBlock().records || []).length;
  let attempts = 0;
  if (!opts.firstTry) {
    const wrong = wrongAnswer(act);
    const r = await answer(lessonId, act.id, wrong);
    attempts += 1;
    check(`${label}: wrong answer is graded not passed by the server`, r.ok && r.json.result.passed === false, r.text.slice(0, 200));
    if (r.ok) {
      lesson = r.json.result.lesson;
      view = actView(lesson, act.id);
      const chosen = act.type === 'choice' || act.question ? wrong.option : undefined;
      assertHidden(`${label} after a wrong answer`, view, act, chosen);
      const res = view.result || (view.question && view.question.result);
      if (act.type === 'choice' || act.question) {
        const feedback = (act.options || act.question.options).find((o) => o.id === wrong.option).feedback;
        check(`${label}: wrong choice shows only that option's feedback`, res && res.feedback === feedback && res.passed === false);
      }
      if (act.type === 'order') check(`${label}: wrong order shows the wrong-order message`, view.result && view.result.feedback === act.feedback_wrong);
      if (act.type === 'sort') check(`${label}: wrong sort reports how many are right, not which`, view.result && view.result.total === act.items.length && view.result.right < act.items.length && !('feedback' in view.result));
      if (act.type === 'reflection') check(`${label}: short reflection is not passed`, view.result && view.result.passed === false && view.result.words < act.min_words);
    }
    const e = entryOf(lessonId, act.id);
    check(`${label}: no learning record for a failed attempt`, (lessonsBlock().records || []).length === before && e && e.passed === false && e.attempts === 1, JSON.stringify(e));
  }
  const good = correctAnswer(act);
  const r2 = await answer(lessonId, act.id, good);
  attempts += 1;
  check(`${label}: correct answer is graded passed by the server`, r2.ok && r2.json.result.passed === true, r2.text.slice(0, 200));
  if (r2.ok) {
    view = actView(r2.json.result.lesson, act.id);
    const res = view.result || (view.question && view.question.result);
    check(`${label}: view shows passed`, view.passed === true && res && res.passed === true);
    if (act.type === 'choice' || act.question) check(`${label}: after passing, every option's explanation is shown`, Array.isArray(res.explanations) && res.explanations.length === (act.options || act.question.options).length && res.explanations.filter((x) => x.correct).length === 1);
    if (act.type === 'sort') check(`${label}: after passing, each item's feedback is shown`, Array.isArray(view.result.feedback) && view.result.feedback.length === act.items.length);
    if (act.type === 'order') check(`${label}: after passing, the right-order message is shown`, view.result.feedback === act.feedback_right);
    if (act.type === 'rule_lab') check(`${label}: after passing, every case shows verdict and reason`, view.result.details && view.result.details.length === act.cases.length && view.result.details.every((d, i) => d.verdict === act.cases.find((c) => `${c.sample}|${c.rule}` === d.key).expected && d.reason.length > 0));
    if (act.type === 'reflection') check(`${label}: reflection text is returned as saved`, view.result.text === good.text && view.result.words >= act.min_words);
  }
  const e2 = entryOf(lessonId, act.id);
  check(`${label}: first_try recorded as ${Boolean(opts.firstTry)}`, e2 && e2.passed === true && e2.first_try === Boolean(opts.firstTry) && e2.attempts === attempts, JSON.stringify(e2));
  const after = lessonsBlock().records || [];
  const mine = after.filter((x) => x.type === 'activity' && x.lesson === lessonId && x.item === act.id);
  check(`${label}: exactly one learning record, source lesson`, after.length === before + 1 && mine.length === 1 && mine[0].source === 'lesson' && mine[0].first_try === Boolean(opts.firstTry), JSON.stringify(mine));
  if (act.type === 'rule_lab') await labAfter(lessonId, act);
  if (act.type !== 'reflection') {
    const again = await answer(lessonId, act.id, wrongAnswer(act));
    const e3 = entryOf(lessonId, act.id);
    check(`${label}: a passed activity stays passed and uncounted`, again.ok && again.json.result.passed === true && e3.passed === true && e3.attempts === attempts, JSON.stringify(e3));
  }
}

// No wrong-answer script: try the options in the order the server lists them until one passes.
async function solveByTrial(lessonId, act) {
  const label = `${lessonId}/${act.id} (trial)`;
  const lesson = lessonOf(await viewLesson(lessonId));
  const view = actView(lesson, act.id);
  assertHidden(`${label} before answering`, view, act);
  let tries = 0;
  let passed = false;
  for (const option of view.options) {
    tries += 1;
    const r = await answer(lessonId, act.id, { option: option.id });
    must(`${label}: answer accepted`, r.ok, r.text.slice(0, 160));
    passed = r.json.result.passed;
    const v = actView(r.json.result.lesson, act.id);
    if (passed) break;
    assertHidden(`${label} after try ${tries}`, v, act, option.id);
  }
  check(`${label}: trying options finds the one right option`, passed === true, `${tries} tries`);
  const e = entryOf(lessonId, act.id);
  check(`${label}: attempts counted`, e && e.passed === true && e.attempts === tries && e.first_try === (tries === 1), JSON.stringify(e));
}

async function solveAll(lessonId, opts = {}) {
  const lesson = lessonDef(lessonId);
  for (const act of lesson.activities) {
    if (act.type === 'cli_compare') continue;
    if (act.type === 'cli_practice') await runPractice(lessonId, act);
    if (opts.skip && opts.skip.has(act.id)) continue;
    if (opts.trial && opts.trial.has(act.id)) await solveByTrial(lessonId, act);
    else await solveActivity(lessonId, act, { firstTry: opts.firstTry && opts.firstTry.has(act.id), malformed: opts.malformed && opts.malformed.has(act.id) });
  }
}

// ---- completing a lesson ---------------------------------------------------------------
async function completeLesson(lessonId, opts = {}) {
  const lesson = lessonDef(lessonId);
  const before = await getState();
  must(`${lessonId}: is the active item before completing`, before.current_item && before.current_item.id === lessonId, JSON.stringify(before.current_item));
  const view = lessonOf(await viewLesson(lessonId));
  check(`${lessonId}: can_complete is true once every activity passed`, view.can_complete === true);
  const t0 = nowSec();
  const r = await post('/api/lesson/complete', { lesson: lessonId });
  const t1 = nowSec();
  must(`${lessonId}: complete accepted`, r.ok, r.text.slice(0, 200));
  state.lessonTimes = state.lessonTimes || {};
  state.lessonTimes[lessonId] = [t0, t1];
  L.saveState(state);
  const s = await getState();
  check(`${lessonId}: status is done`, courseMap(s)[lessonId] === 'done');
  const block = lessonsBlock();
  for (const item of lesson.retrieval) {
    const entry = block.review.items[`${lessonId}:${item.id}`];
    check(`${lessonId}: retrieval ${item.id} is scheduled for 1 day later`, entry && entry.stage === 0 && entry.retired === false && entry.due >= t0 + DAY - 1 && entry.due <= t1 + DAY + 1, JSON.stringify(entry));
  }
  check(`${lessonId}: nothing is due right after completing`, s.review.due === 0 && (await get('/api/review')).json.review.items.length === 0);
  const again = await post('/api/lesson/complete', { lesson: lessonId });
  check(`${lessonId}: completing twice is refused`, again.status === 400 && again.code === 'lesson_done', again.code);
  const act = lesson.activities.find((a) => !['cli_compare', 'cli_practice', 'reflection'].includes(a.type)) || lesson.activities[0];
  if (act) {
    const late = await answer(lessonId, act.id, correctAnswer(act));
    check(`${lessonId}: answers are closed after the lesson is done`, late.status === 400 && ['lesson_done', 'bad_answer'].includes(late.code), late.code);
  }
  return s;
}

async function expectIncomplete(lessonId) {
  // Since 3.33 only CLI exercises hold Continue back. A lesson without one is always completable.
  const blocking = lessonDef(lessonId).activities.some((a) => ['cli_compare', 'cli_practice'].includes(a.type));
  if (!blocking) {
    const view = lessonOf(await viewLesson(lessonId));
    check(`${lessonId}: no question holds Continue back, so it is completable before any answer`, view.can_complete === true);
    return;
  }
  const r = await post('/api/lesson/complete', { lesson: lessonId });
  check(`${lessonId}: Continue is refused until the CLI exercise has run`, r.status === 400 && r.code === 'activities_incomplete', `${r.status} ${r.code}`);
  const view = lessonOf(await viewLesson(lessonId));
  check(`${lessonId}: can_complete is false until the CLI exercise has run`, view.can_complete === false);
}

async function expectStepLocked(stepId, lessonId, note) {
  const s = await getState();
  const stepStatus = s.course.find((c) => c.kind === 'step' && c.id === stepId).status;
  check(`${note || stepId}: step is locked in the course`, stepStatus === 'locked', stepStatus);
  check(`${note || stepId}: steps list shows it locked and current_step is not it`, s.steps.find((x) => x.id === stepId).status === 'locked' && s.current_step !== stepId, String(s.current_step));
  const r = await post('/api/step/start', { step: stepId });
  const title = lessonDef(lessonId).title;
  check(`${note || stepId}: starting it is refused and names the lesson`, r.status === 400 && r.code === 'step_locked' && r.message.includes(title), `${r.status} ${r.code} ${r.message}`);
  const sub = await post('/api/step/check', { step: stepId });
  check(`${note || stepId}: checking it is refused`, sub.status === 400, String(sub.status));
}

async function expectStepActive(stepId) {
  const s = await getState();
  check(`${stepId}: step is now active`, courseMap(s)[stepId] === 'active' && s.current_step === stepId && s.current_item.kind === 'step' && s.current_item.id === stepId, JSON.stringify(s.current_item));
}

async function enterStage(lessonId) {
  requireStandIn();
  const s = await getState();
  must(`stage starts with ${lessonId} as the current item`, s.current_item && s.current_item.id === lessonId, JSON.stringify(s.current_item));
  must('preflight has passed', s.preflight.passed === true);
  return s;
}

function noKeyInLesson(label, text) {
  const hit = kitKeyLines.find((line) => text.includes(line));
  check(`${label}: lesson does not reveal the Northwind answer key`, !hit, hit ? hit.slice(0, 60) : '');
}

function scanLessonText(lessonId, r) {
  noKeyInLesson(lessonId, r.text);
}

// ---- CLI helpers (stand-in only) ----------------------------------------------------------
function readEvents() {
  if (!exists(EVENTS)) return [];
  return readText(EVENTS).split(/\r?\n/).filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
}

// The operating system reuses process ids within a run, so a CLI process is told apart by its id and launch time.
const runId = (run) => `${run.pid}@${run.launch.ts}`;
const eventsOf = (run) => readEvents().filter((e) => e.pid === run.pid && e.ts >= run.launch.ts);
const enterCount = new Map();
async function sendEnter(run) {
  const r = await post('/api/terminal/input', { data: Buffer.from('\r').toString('base64') });
  must('participant keystroke accepted', r.ok, r.text.slice(0, 100));
  enterCount.set(runId(run), (enterCount.get(runId(run)) || 0) + 1);
}

function approvalAllowed(name) {
  const norm = String(name).replace(/\\/g, '/');
  if (norm.split('/').includes('..')) return false;
  if (/^[a-zA-Z]:/.test(norm) || norm.startsWith('/')) return norm.toLowerCase().startsWith(L.WORK.toLowerCase().replace(/\\/g, '/') + '/');
  return true;
}

async function startLessonCli(lessonId, actId, label) {
  L.countSession(label);
  const since = nowSec() - 0.5;
  const r = await post('/api/lesson/cli/start', { lesson: lessonId, activity: actId });
  must(`${label}: start accepted`, r.ok, r.text.slice(0, 200));
  const launch = await L.waitFor(async () => readEvents().find((e) => e.event === 'launch' && e.ts >= since), 20000, `${label} launch`);
  await sleep(1800); // the stand-in prints its input line
  return { pid: launch.pid, launch, since };
}

// The participant (this harness) presses Enter on each approval the stand-in shows.
// Only Enter keystrokes are sent, and only for a file inside the CLI's own folder or e2e-work.
async function driveApprovals(run, done, timeoutMs = 90000) {
  const started = Date.now();
  for (;;) {
    if (Date.now() - started > timeoutMs) throw new Error('stand-in CLI did not finish in time');
    const ev = eventsOf(run);
    const asked = ev.filter((e) => e.event === 'approve');
    const answered = ev.filter((e) => e.event === 'approved');
    if (asked.length > answered.length && (enterCount.get(runId(run)) || 0) === answered.length) {
      const next = asked[answered.length];
      if (!approvalAllowed(next.name)) throw new Error(`prompt for a file outside e2e-work: ${next.name}`);
      await sendEnter(run);
    }
    if (await done(ev)) return;
    await sleep(300);
  }
}

// What the app did to the CLI process: no flags, no extra typing, no answered prompts.
function auditProcess(label, run, expectedLine) {
  const ev = eventsOf(run);
  const launch = ev.find((e) => e.event === 'launch');
  const approved = ev.filter((e) => e.event === 'approved');
  const asked = ev.filter((e) => e.event === 'approve');
  const lines = ev.filter((e) => e.event === 'line');
  const enters = enterCount.get(runId(run)) || 0;
  if (launch.argv.length) L.violation(`${label}: the app added arguments or flags to the CLI command: ${JSON.stringify(launch.argv)}`);
  if (approved.length !== enters || approved.some((a) => a.typed !== '')) L.violation(`${label}: a CLI prompt was answered by something other than the participant (${approved.length} answered, ${enters} Enter presses by the participant)`);
  if (lines.some((l) => l.text !== expectedLine)) L.violation(`${label}: the app typed something other than the activity's line: ${JSON.stringify(lines.map((l) => l.text))}`);
  check(`${label}: the CLI got no flags from the app`, launch.argv.length === 0);
  check(`${label}: every prompt was answered by the participant only`, approved.length === enters && approved.length === asked.length && approved.every((a) => a.typed === ''), `${approved.length}/${asked.length} answered, ${enters} Enter presses`);
  check(`${label}: the app typed only the activity's line, once`, lines.length === 1 && lines[0].text === expectedLine, JSON.stringify(lines.map((l) => l.text)));
}

function cliStopped() {
  return getState().then((s) => !s.terminal.running);
}

// A practice exercise: the participant starts the CLI and sends the line; the app decides from the saved file only.
async function runPractice(lessonId, act) {
  const label = `${lessonId}/${act.id} practice run`;
  const out = path.join(PROJECT, '.learning', 'practice', `${act.id}.txt`);
  check(`${label}: nothing is saved before the run`, !hasText(out));
  const run = await startLessonCli(lessonId, act.id, label);
  const cwd = path.resolve(run.launch.cwd).toLowerCase();
  check(`${label}: the CLI ran in the practice folder for this activity`, cwd.endsWith(path.join('practice', act.id).toLowerCase()), run.launch.cwd);
  const sent = await post('/api/lesson/cli/send', { lesson: lessonId, activity: act.id });
  must(`${label}: Send accepted`, sent.ok, sent.text.slice(0, 160));
  await driveApprovals(run, async () => hasText(out) && (await cliStopped()));
  const saved = readText(out);
  check(`${label}: the answer was saved from the CLI's file`, saved.trim().length > 0 && !saved.includes('DECOY-TERMINAL-ONLY'));
  check(`${label}: the CLI was stopped after saving`, await L.waitFor(async () => !L.pidAlive(run.pid), 15000, `process ${run.pid} gone`).then(() => true).catch(() => false));
  const view = actView(lessonOf(await viewLesson(lessonId)), act.id);
  check(`${label}: shown to the participant exactly as saved`, view.all_saved === true && view.outputs[0].done === true && view.outputs[0].text === saved);
  check(`${label}: the lesson can now be completed even though the question is open`, lessonOf(await viewLesson(lessonId)).can_complete === true);
  auditProcess(label, run, act.line);
}

// ---- restart ----------------------------------------------------------------------
async function quitApp() {
  try { await post('/api/quit', {}); } catch { /* the server closed the connection */ }
  await L.waitFor(async () => !L.pidAlive(state.serverPid), 20000, 'server exit');
}
async function restartApp() {
  await quitApp();
  await L.startServer();
}

// ---- stages -------------------------------------------------------------------------

async function stageMission() {
  requireStandIn();
  must('fresh home: no app.json and no project yet', !exists(path.join(HOME, 'app.json')) && !exists(PROGRESS));
  await L.startServer();

  // Course gating before anything else is done.
  let s = await getState();
  check('before setup: not configured, current item is the mission lesson', s.configured === false && s.current_item && s.current_item.kind === 'lesson' && s.current_item.id === 'mission' && s.current_step === null, JSON.stringify(s.current_item));
  const map = courseMap(s);
  check('course lists the lessons and steps in course order', s.course.map((c) => c.id).join(',') === `mission,hook,several-runs,generate,rules,build,trust,fixtures,readback,predict,key,surprise,run,fix,baseline-why,baseline`, s.course.map((c) => c.id).join(','));
  check('only the mission is open; everything after it is locked', map.mission === 'active' && s.course.filter((c) => c.id !== 'mission').every((c) => c.status === 'locked'), JSON.stringify(map));
  check('steps list is all locked', s.steps.every((x) => x.status === 'locked'));
  check('state has course text and a review summary', s.course_text && s.review && s.review.due === 0);
  // Before setup a locked lesson opens to read, as a preview that records nothing. Everything that acts on it is refused.
  const previewBefore = fs.existsSync(PENDING) ? fs.readFileSync(PENDING, 'utf8') : null;
  const preview = await viewLesson('hook');
  check('viewing a lesson after the mission before setup is a read-only preview', preview.ok && lessonOf(preview).status === 'preview' && lessonOf(preview).can_complete === false && lessonOf(preview).can_skip === false && lessonOf(preview).body.length > 0, `${preview.status} ${preview.code}`);
  scanLessonText('hook (preview)', preview);
  check('reading ahead recorded nothing', (fs.existsSync(PENDING) ? fs.readFileSync(PENDING, 'utf8') : null) === previewBefore);
  for (const [name, r] of [
    ['answering a lesson after the mission', await answer('hook', 'hook-compare', { option: 'a' })],
    ['completing a lesson after the mission', await post('/api/lesson/complete', { lesson: 'hook' })],
    ['starting the hook CLI', await post('/api/lesson/cli/start', { lesson: 'hook', activity: 'hook-compare' })],
    ['running a step', await post('/api/step/start', { step: 'generate' })],
  ]) check(`${name} before preflight is refused`, r.status === 400 && !r.ok && Boolean(r.code), `${r.status} ${r.code}`);
  const unknownLesson = await viewLesson('no-such-lesson');
  check('an unknown lesson is refused', unknownLesson.status === 400 && unknownLesson.code === 'unknown_lesson', unknownLesson.code);
  for (const route of ['/api/lesson?id=mission', '/api/kit?ref=kit:skills/build-eval-script/SKILL.md', '/api/review']) {
    const r = await get(route, { token: null });
    check(`GET ${route.split('?')[0]} without the token is refused`, r.status === 401, String(r.status));
  }
  for (const route of ['/api/lesson/answer', '/api/placement/answer', '/api/review/answer', '/api/lesson/rule-run']) {
    const r = await post(route, {}, { token: 'wrong' });
    check(`POST ${route} with a wrong token is refused`, r.status === 401, String(r.status));
  }

  // The mission lesson: mission text, win, sources, no answers.
  const first = await viewLesson('mission');
  must('mission lesson opens', first.ok, first.text.slice(0, 200));
  scanLessonText('mission', first);
  let lesson = lessonOf(first);
  check('mission text is the required wording', lesson.mission === MISSION_TEXT && CONTENT.mission === MISSION_TEXT, lesson.mission);
  check('lesson has a win, minutes, body and status active', lesson.win.length > 0 && lesson.minutes > 0 && lesson.body.length > 0 && lesson.status === 'active' && lesson.skippable === false);
  check('lesson names a primary source and at least one source', lesson.sources.length > 0 && lesson.primary_source && lesson.primary_source.ref && lesson.primary_source.why);
  check('mission can be completed at once, because no question holds Continue back', lesson.can_complete === true && lesson.can_skip === false);
  check('the lesson view holds no retrieval answers', !('retrieval' in lesson));
  check('the mission is a plain page: no activities, no retrieval, no placement questions', lesson.activities.length === 0 && lessonDef('mission').retrieval.length === 0 && CONTENT.placement.length === 0 && Array.isArray(lesson.placement) && lesson.placement.length === 0, JSON.stringify(lesson.activities));
  check('the mission body has the four passages and no map of the Parts', ['**The goal.**', '**Why it matters to you.**', '**What you will do.**', '**What you leave with.**'].every((p) => lesson.body.includes(p)) && !lesson.body.includes('you-are-here'));
  const again = lessonOf(await viewLesson('mission'));
  check('viewing again gives the same page', again.body === lesson.body && again.activities.length === 0 && again.placement.length === 0);
  check('viewing created no learning record', (lessonsBlock().records || []).length === 0);

  // Kit viewer: reads bundled files only; traversal and the answer key are refused.
  for (const ref of [...lesson.sources.map((x) => x.ref), lesson.primary_source.ref, 'kit:northwind/fixture-bad.txt', 'kit:lessons/hook/requirements.md'].filter((x) => x.startsWith('kit:'))) {
    const r = await get(`/api/kit?ref=${encodeURIComponent(ref)}`);
    const file = path.join(KIT, ref.slice(4).split('/').join(path.sep));
    check(`kit viewer opens ${ref}`, r.ok && r.json.kit.ref === ref && r.json.kit.text === readText(file) && r.json.kit.name === path.basename(file), `${r.status} ${r.code}`);
  }
  const lessonsJsonHead = CONTENT.mission;
  for (const ref of [
    'kit:../content/lessons.json', 'kit:..\\content\\lessons.json', 'kit:northwind/../../content/lessons.json', 'kit:northwind/%2e%2e/%2e%2e/content/lessons.json',
    'kit:%2e%2e/%2e%2e/__main__.py', 'kit:/content/lessons.json', 'kit:C:/Windows/win.ini', 'kit:C:\\Windows\\win.ini', 'kit:\\\\localhost\\c$\\Windows\\win.ini',
    'kit:northwind/answer-key.md', 'kit:NORTHWIND/ANSWER-KEY.MD', 'kit:northwind/./answer-key.md', 'kit:northwind/answer-key.md%00.txt', 'kit:northwind/fixture-bad.txt\u0000',
    'kit:northwind/answer-key.md.', 'kit:northwind/answer-key.md ', 'kit:northwind/answer-key.md::$DATA', 'kit:northwind/ANSWER~1.MD', 'kit:northwind//answer-key.md',
    'kit:', 'kit:northwind', 'kit:no-such-file.txt', '../content/lessons.json', 'content/lessons.json', 'file:///C:/Windows/win.ini', 'https://example.com/', '', 'kit:northwind/fixture-bad.txt/../../../content/lessons.json',
  ]) {
    const r = await get(`/api/kit?ref=${encodeURIComponent(ref)}`);
    check(`kit viewer refuses ${JSON.stringify(ref)}`, r.status === 400 && r.code === 'bad_ref' && !r.text.includes(lessonsJsonHead) && !kitKeyLines.some((k) => r.text.includes(k)), `${r.status} ${r.code}`);
  }
  const noRef = await get('/api/kit');
  check('kit viewer refuses a missing ref', noRef.status === 400 && noRef.code === 'bad_ref', noRef.code);

  // The mission has no questions: finishing it needs nothing, and nothing is scheduled for review.
  await expectIncomplete('mission');
  check('the mission progress is held in the app folder before a project exists', !exists(PROGRESS));

  // Restart: the seed and the mission page persist before any project exists.
  await restartApp();
  lesson = lessonOf(await viewLesson('mission'));
  check('after restart: the mission is still a plain active page', lesson.status === 'active' && lesson.activities.length === 0 && lesson.placement.length === 0 && lesson.can_complete === true);
  s = await getState();
  check('after restart: everything after the mission is still locked', s.course.filter((c) => c.id !== 'mission').every((c) => c.status === 'locked'), JSON.stringify(courseMap(s)));

  await completeLesson('mission');
  check('finishing the mission scheduled no review and made no learning record', Object.keys(lessonsBlock().review.items).length === 0 && (lessonsBlock().records || []).length === 0);
  check('the mission progress is held in the app folder before a project exists', exists(PENDING) && !exists(PROGRESS));
  s = await getState();
  check('hook stays locked until preflight passes', courseMap(s).hook === 'locked' && courseMap(s).mission === 'done' && s.current_item === null, JSON.stringify(s.current_item));
  check('no violations so far', state.violations.length === 0, state.violations.join(' | '));
  await quitApp();
  endStage('mission');
}

async function stageHook() {
  let s = await enterStage('hook');
  check('mission progress was carried into the project', (() => { const b = readJson(PROGRESS).lessons; return b.per_lesson.mission.status === 'done' && Object.keys(b.review.items).length === 0 && b.records.length === 0; })());
  const map = courseMap(s);
  check('hook is active; several-runs is locked; the rest locked', map.hook === 'active' && map['several-runs'] === 'locked' && map.generate === 'locked', JSON.stringify(map));
  await expectStepLocked('generate', 'hook', 'generate while hook is open');
  const progressBefore = fs.readFileSync(PROGRESS, 'utf8');
  const locked = await viewLesson('several-runs');
  check('a later lesson opens as a read-only preview that names the lesson still to do', locked.ok && lessonOf(locked).status === 'preview' && lessonOf(locked).can_complete === false && lessonOf(locked).held_by && lessonOf(locked).held_by.id === 'hook', `${locked.status} ${locked.code}`);
  check('reading a later lesson recorded nothing', fs.readFileSync(PROGRESS, 'utf8') === progressBefore);
  const lockedAnswer = await answer('several-runs', 'generate-spot', { option: 'a' });
  check('a later lesson cannot be answered early', lockedAnswer.status === 400 && lockedAnswer.code === 'lesson_locked', lockedAnswer.code);
  const lockedCli = await post('/api/lesson/cli/start', { lesson: 'rules', activity: 'build-try' });
  check('a later CLI lesson cannot be started early', lockedCli.status === 400 && lockedCli.code === 'lesson_locked', lockedCli.code);
  const noSkip = await post('/api/lesson/skip', { lesson: 'hook' });
  check('a CLI lesson cannot be skipped', noSkip.status === 400 && noSkip.code === 'cannot_skip', `${noSkip.code} ${noSkip.message}`);
  const badActivity = await post('/api/lesson/cli/start', { lesson: 'hook', activity: 'nope' });
  check('an unknown CLI activity is refused', badActivity.status === 400 && badActivity.code === 'unknown_activity', badActivity.code);

  const hook = lessonDef('hook');
  const act = hook.activities[0];
  must('content: hook line is the exact required line', act.line === HOOK_LINE && act.runs === 3);
  const first = await viewLesson('hook');
  scanLessonText('hook', first);
  let view = actView(lessonOf(first), act.id);
  check('hook view: three runs, none saved, the exact line, hook folder label', view.runs === 3 && view.outputs.length === 3 && view.outputs.every((o) => o.done === false && o.text === '') && view.cli.line === HOOK_LINE && view.cli.started === false && view.all_saved === false);
  assertHidden('hook question before runs', view, act);
  const early = await answer('hook', act.id, { option: act.question.options.find((o) => o.correct).id });
  check('the question cannot be answered before the three runs are saved', early.status === 400 && early.code === 'runs_missing', early.code);
  const noCli = await post('/api/lesson/cli/send', { lesson: 'hook', activity: act.id });
  check('Send before Start is refused', noCli.status === 400 && noCli.code === 'cli_not_running', noCli.code);

  const hookDir = path.join(HOME, 'hook');
  const update = readText(path.join(KIT, 'northwind', 'fixture-polished-but-wrong.txt'));
  const requirements = readText(path.join(KIT, 'lessons', 'hook', 'requirements.md'));
  const folderCheck = (label) => {
    const tree = L.listTree(hookDir);
    check(`${label}: hook folder holds only update.txt and requirements.md`, JSON.stringify(tree) === JSON.stringify(['requirements.md', 'update.txt']), tree.join(','));
    check(`${label}: update.txt and requirements.md are the bundled files`, hasText(path.join(hookDir, 'update.txt')) && readText(path.join(hookDir, 'update.txt')) === update && readText(path.join(hookDir, 'requirements.md')) === requirements);
  };

  // A run where the screen shows a result but no file is written: the app must not decide from the screen.
  fs.writeFileSync(MODE_FILE, 'silent');
  process.on('exit', () => { try { fs.unlinkSync(MODE_FILE); } catch { /* already removed */ } });
  const silent = await startLessonCli('hook', act.id, 'hook silent run (screen only, no file)');
  folderCheck('silent run');
  const sendSilent = await post('/api/lesson/cli/send', { lesson: 'hook', activity: act.id });
  must('silent run: Send accepted', sendSilent.ok, sendSilent.text.slice(0, 160));
  await L.waitFor(async () => readEvents().some((e) => e.pid === silent.pid && e.event === 'line'), 15000, 'silent run: line received');
  await sleep(7000); // longer than the app's two-poll file watcher
  check('silent run: no result was saved because no file was written', !exists(path.join(PROJECT, '.learning', 'hook', 'run-1.txt')));
  view = actView(lessonOf(await viewLesson('hook')), act.id);
  check('silent run: the app still shows run 1 as not saved', view.outputs[0].done === false && view.all_saved === false);
  check('silent run: the CLI was left running (the app did not act on screen text)', (await getState()).terminal.running === true);
  const stopSilent = await post('/api/lesson/cli/stop', { lesson: 'hook', activity: act.id });
  check('Stop works', stopSilent.ok && (await L.waitFor(cliStopped, 15000, 'CLI stopped').then(() => true)));
  auditProcess('silent run', silent, HOOK_LINE);
  fs.unlinkSync(MODE_FILE);
  const gone = async (pid) => L.waitFor(async () => !L.pidAlive(pid), 15000, `process ${pid} gone`).then(() => true).catch(() => false);

  // Three real runs: three separate processes, one at a time, decided from output.txt only.
  const runs = [];
  for (let n = 1; n <= 3; n += 1) {
    const run = await startLessonCli('hook', act.id, `hook run ${n}`);
    folderCheck(`run ${n}`);
    for (const earlier of [silent, ...runs]) check(`run ${n}: an earlier CLI process is gone before this one runs`, await gone(earlier.pid), String(earlier.pid));
    check(`run ${n}: this is a new process`, ![silent, ...runs].some((r) => r.pid === run.pid));
    check(`run ${n}: the CLI ran in the hook folder`, path.resolve(run.launch.cwd).toLowerCase() === path.resolve(hookDir).toLowerCase(), run.launch.cwd);
    const sendNow = await post('/api/lesson/cli/send', { lesson: 'hook', activity: act.id });
    must(`run ${n}: Send accepted`, sendNow.ok, sendNow.text.slice(0, 160));
    const runFile = path.join(PROJECT, '.learning', 'hook', `run-${n}.txt`);
    await driveApprovals(run, async () => hasText(runFile) && (await cliStopped()));
    runs.push(run);
    const saved = readText(runFile);
    check(`run ${n}: result saved in .learning/hook/run-${n}.txt from the file`, /^Score: \d\/10\. (pass|fail)\. /.test(saved) && saved.trim().length > 0, saved.slice(0, 100));
    check(`run ${n}: the saved text is the file's text, not the screen's`, !saved.includes('DECOY-TERMINAL-ONLY'));
    check(`run ${n}: the CLI was stopped after saving`, await gone(run.pid));
    view = actView(lessonOf(await viewLesson('hook')), act.id);
    check(`run ${n}: shown to the participant exactly as saved, as plain text`, view.outputs[n - 1].done === true && view.outputs[n - 1].text === saved && !/&lt;|&amp;/.test(view.outputs[n - 1].text) && saved.includes('<b>bold</b> & <script>x()</script>'));
    check(`run ${n}: earlier results are kept`, view.outputs.slice(0, n - 1).every((o, i) => o.done && o.text === readText(path.join(PROJECT, '.learning', 'hook', `run-${i + 1}.txt`))));
    auditProcess(`run ${n}`, run, HOOK_LINE);
  }
  check('three different CLI processes ran, one at a time', new Set(runs.map((r) => r.pid)).size === 3);
  const stale = await post('/api/lesson/cli/start', { lesson: 'hook', activity: act.id });
  check('a fourth run is refused: all runs are saved', stale.status === 400 && stale.code === 'runs_complete', stale.code);
  // Since 3.33 the question never holds Continue back: once all runs are saved the lesson can be completed.
  view = actView(lessonOf(await viewLesson('hook')), act.id);
  check('Continue is open once the runs are saved, even with the question unanswered', lessonOf(await viewLesson('hook')).can_complete === true);
  view = actView(lessonOf(await viewLesson('hook')), act.id);
  check('hook view: all saved, question open', view.all_saved === true && view.passed === false);
  await solveActivity('hook', act, { malformed: false });
  await solveActivity('hook', hook.activities.find((a) => a.id === 'hook-explain'), {});
  check('no result file is HTML-escaped or wrapped', [1, 2, 3].every((n) => readText(path.join(PROJECT, '.learning', 'hook', `run-${n}.txt`)).includes('<b>bold</b>')));
  s = await completeLesson('hook');
  check('after hook: several-runs is active, generate still locked', courseMap(s).hook === 'done' && courseMap(s)['several-runs'] === 'active' && courseMap(s).generate === 'locked', JSON.stringify(courseMap(s)));
  check('the hook results are not in progress.json', !readText(PROGRESS).includes('Score:'));
  check('the app never reached the answer key (hook)', state.violations.length === 0, state.violations.join(' | '));
  endStage('hook');
}

async function stageSeveralRuns() {
  await enterStage('several-runs');
  const lessonJson = await viewLesson('several-runs');
  scanLessonText('several-runs', lessonJson);
  const view = lessonOf(lessonJson);
  check('several-runs is skippable by content but nothing offers a skip', view.skippable === true && view.can_skip === false);
  const skip = await post('/api/lesson/skip', { lesson: 'several-runs' });
  check('several-runs cannot be skipped', skip.status === 400 && skip.code === 'cannot_skip', `${skip.code} ${skip.message}`);
  check('the refused skip changed nothing', courseMap(await getState())['several-runs'] === 'active');
  await expectStepLocked('generate', 'several-runs');
  await expectIncomplete('several-runs');
  await solveAll('several-runs', { trial: new Set(['generate-spot']) });
  const s = await completeLesson('several-runs');
  await expectStepActive('generate');
  check('after several-runs: generate step is the current step', s.current_step === 'generate' || (await getState()).current_step === 'generate');
  endStage('several-runs');
}

async function stageRules() {
  await enterStage('rules');
  const rules = lessonDef('rules');
  const act = (id) => rules.activities.find((a) => a.id === id);
  await expectStepLocked('build', 'rules', 'build while rules is open');
  scanLessonText('rules', await viewLesson('rules'));
  const skip = await post('/api/lesson/skip', { lesson: 'rules' });
  check('rules cannot be skipped', skip.status === 400 && skip.code === 'cannot_skip', `${skip.code} ${skip.message}`);
  await expectIncomplete('rules');
  const wrongType = await post('/api/lesson/cli/start', { lesson: 'rules', activity: 'rules-lab' });
  check('a non-CLI activity cannot start the CLI', wrongType.status === 400 && wrongType.code === 'not_cli', wrongType.code);

  await solveActivity('rules', act('rules-lab'), { malformed: true });
  await solveActivity('rules', act('build-sort'), { malformed: true });
  await solveActivity('rules', act('build-explain'), {});
  await runPractice('rules', act('build-try'));
  await solveActivity('rules', act('build-try'), {});
  await solveActivity('rules', act('choices-lab'), { malformed: true });
  const own = act('choices-own');
  const find = act('choices-find');
  await solveActivity('rules', own, { malformed: true });

  // The reflection and the earlier answers survive an app restart in the middle of the lesson.
  const saved = correctAnswer(own).text;
  let view = lessonOf(await viewLesson('rules'));
  const orderBefore = optionOrder(actView(view, find.id));
  check('before restart: reflection is saved and passed in progress.json', entryOf('rules', own.id).passed === true && entryOf('rules', own.id).last.text === saved);
  await restartApp();
  view = lessonOf(await viewLesson('rules'));
  const ov = actView(view, own.id);
  check('after restart: the reflection text persisted exactly', ov.passed === true && ov.result.text === saved && ov.result.words >= own.min_words, ov.result && ov.result.text);
  check('after restart: both rule labs are still passed', actView(view, 'rules-lab').passed === true && actView(view, 'choices-lab').passed === true);
  check('after restart: the saved practice answer is still shown as saved', actView(view, 'build-try').outputs[0].done === true);
  check('after restart: option order is unchanged', optionOrder(actView(view, find.id)) === orderBefore);
  check('after restart: course position is unchanged', (await getState()).current_item.id === 'rules');
  await solveActivity('rules', find, {});
  await solveActivity('rules', act('choices-explain-tech'), {});
  const s = await completeLesson('rules');
  await expectStepActive('build');
  check('after rules: the build step is active', s.course.find((c) => c.id === 'build').status === 'active');
  check('no CLI violation in the rules lesson', state.violations.length === 0, state.violations.join(' | '));
  endStage('rules');
}

async function stageTrust() {
  await enterStage('trust');
  const lessonJson = await viewLesson('trust');
  scanLessonText('trust', lessonJson);
  const view = lessonOf(lessonJson);
  check('trust is skippable by content but no skip is offered', view.skippable === true && view.can_skip === false);
  const skip = await post('/api/lesson/skip', { lesson: 'trust' });
  check('trust cannot be skipped', skip.status === 400 && skip.code === 'cannot_skip', `${skip.code} ${skip.message}`);
  check('the refused skip changed nothing', courseMap(await getState()).trust === 'active');
  await expectStepLocked('fixtures', 'trust');
  const kitKey = await get(`/api/kit?ref=${encodeURIComponent('kit:northwind/answer-key.md')}`);
  check('the Northwind key cannot be opened in the kit viewer', kitKey.status === 400 && kitKey.code === 'bad_ref');
  await solveAll('trust', { malformed: new Set(['verify-polished']) });
  const s = await completeLesson('trust');
  await expectStepActive('fixtures');
  check('after trust: fixtures is active', s.course.find((c) => c.id === 'fixtures').status === 'active');
  endStage('trust');
}

async function stageSurprise() {
  await enterStage('surprise');
  await expectStepLocked('run', 'surprise');
  const r = await viewLesson('surprise');
  scanLessonText('surprise', r);
  check('surprise lesson does not reveal the answer key before the run', !kitKeyLines.some((k) => r.text.includes(k)));
  await expectIncomplete('surprise');
  await solveAll('surprise', { malformed: new Set(['fix-sort']) });
  const s = await completeLesson('surprise');
  await expectStepActive('run');
  check('after surprise: run is active and fix waits for it', courseMap(s).run === 'active' && courseMap(s).fix === 'locked');
  endStage('surprise');
}

// ---- review queue ---------------------------------------------------------------------
function retrievalDef(key) {
  const [lessonId, itemId] = key.split(':');
  return lessonDef(lessonId).retrieval.find((r) => r.id === itemId);
}

async function ageItems(onlyKeys) {
  await quitApp();
  const data = readJson(PROGRESS);
  const base = nowSec() - 7200;
  Object.keys(data.lessons.review.items).forEach((key, i) => {
    const it = data.lessons.review.items[key];
    if (it.retired) return;
    if (!onlyKeys) it.due = base - i * 10;
    else if (onlyKeys.includes(key)) it.due = base;
    else it.due = nowSec() + 30 * DAY;
  });
  fs.writeFileSync(PROGRESS, JSON.stringify(data, null, 2));
  await L.startServer();
}

async function reviewChecks() {
  // No clock can be injected into the running app. Scheduling is checked as it is; due-time behavior is checked
  // by moving the saved due times into the past while the app is stopped.
  let s = await getState();
  const block = lessonsBlock();
  const expected = [];
  for (const l of CONTENT.lessons) {
    if (block.per_lesson[l.id] && block.per_lesson[l.id].status === 'done') l.retrieval.forEach((r) => expected.push(`${l.id}:${r.id}`));
  }
  const keys = Object.keys(block.review.items);
  check('review: every retrieval item of every completed lesson is scheduled', JSON.stringify([...keys].sort()) === JSON.stringify([...expected].sort()) && expected.length >= 20, `${keys.length} scheduled, ${expected.length} expected`);
  check('review: nothing is scheduled for the mission, which has no questions', !keys.some((k) => k.startsWith('mission:')));
  check('review: every first due time is one day after its lesson was completed', keys.every((k) => { const t = state.lessonTimes && state.lessonTimes[k.split(':')[0]]; const e = block.review.items[k]; return t && e.due >= t[0] + DAY - 1 && e.due <= t[1] + DAY + 1 && e.stage === 0 && e.retired === false; }));
  check('review: none due right after the course is finished', s.review.due === 0 && (await get('/api/review')).json.review.items.length === 0);

  await ageItems(null);
  s = await getState();
  check('review: after a day passes, the reopened app reports at most 5 due', s.review.due === 5 && s.review.postponed === false, JSON.stringify(s.review));
  const r = await get('/api/review');
  must('review: sitting opens', r.ok, r.text.slice(0, 200));
  const items = r.json.review.items;
  check('review: at most 5 items in a sitting', items.length === 5 && keysOf(r.json).size > 0);
  check('review: consecutive items come from different lessons', items.every((it, i) => i === 0 || it.lesson !== items[i - 1].lesson), items.map((i) => i.lesson).join(','));
  check('review: items show no answers or feedback', FORBIDDEN_KEYS.every((k) => !keysOf(r.json).has(k)) && !keysOf(r.json).has('feedback') && items.every((it) => it.options.every((o) => Object.keys(o).sort().join() === 'id,text')) && items.every((it) => retrievalDef(it.item).options.every((o) => !r.text.includes(o.feedback))));
  const second = await get('/api/review');
  check('review: the same sitting is returned until answered', second.json.review.items.map((i) => i.item).join() === items.map((i) => i.item).join());
  const k0 = items[0].item;
  const k1 = items[1].item;
  const right = await post('/api/review/answer', { item: k0, option: retrievalDef(k0).options.find((o) => o.correct).id });
  const t0 = nowSec();
  check('review: a correct answer passes and shows feedback', right.ok && right.json.result.passed === true && right.json.result.feedback.length > 0);
  let it = lessonsBlock().review.items[k0];
  check('review: correct moves the item to 3 days', it.stage === 1 && it.retired === false && Math.abs(it.due - (t0 + 3 * DAY)) < 30, JSON.stringify(it));
  const wrong = await post('/api/review/answer', { item: k1, option: retrievalDef(k1).options.find((o) => !o.correct).id });
  const t1 = nowSec();
  check('review: a wrong answer is not passed', wrong.ok && wrong.json.result.passed === false);
  it = lessonsBlock().review.items[k1];
  check('review: wrong sends the item back to 1 day', it.stage === 0 && it.retired === false && Math.abs(it.due - (t1 + DAY)) < 30, JSON.stringify(it));
  const repeat = await post('/api/review/answer', { item: k0, option: 'a' });
  check('review: an answered item cannot be answered again in the sitting', repeat.status === 400 && repeat.code === 'review_unknown', repeat.code);
  const notDue = await post('/api/review/answer', { item: 'nope:nope', option: 'a' });
  check('review: an item that is not due is refused', notDue.status === 400 && notDue.code === 'review_unknown', notDue.code);
  const badOption = await post('/api/review/answer', { item: items[2].item, option: 'zzz' });
  check('review: an unknown option is refused', badOption.status === 400 && badOption.code === 'bad_answer', badOption.code);
  const records = lessonsBlock().records.filter((x) => x.type === 'review');
  check('review: a learning record exists for the correct answer only', records.length === 1 && records[0].item === k0.split(':')[1] && records[0].source === 'review', JSON.stringify(records));
  const afterAnswers = await get('/api/review');
  check('review: answered items leave the sitting', afterAnswers.json.review.items.length === 3 && !afterAnswers.json.review.items.some((x) => [k0, k1].includes(x.item)));
  const course = JSON.stringify((await getState()).course);
  const postpone = await post('/api/review/postpone', {});
  check('review: Postpone is accepted', postpone.ok);
  const after = await get('/api/review');
  s = await getState();
  check('review: postponed means nothing is shown and nothing blocks the course', after.json.review.postponed === true && after.json.review.items.length === 0 && s.review.due === 0 && s.review.postponed === true && JSON.stringify(s.course) === course);
  check('review: works after the course is finished', s.course.every((c) => c.status === 'done' || c.status === 'skipped') && s.current_item === null);

  // Retire: correct at 1 day, 3 days and 7 days.
  await ageItems([k0]);
  const sitting = (await get('/api/review')).json.review.items;
  check('review: a reopened app lists the aged item', sitting.length === 1 && sitting[0].item === k0, sitting.map((x) => x.item).join());
  const second2 = await post('/api/review/answer', { item: k0, option: retrievalDef(k0).options.find((o) => o.correct).id });
  const t2 = nowSec();
  it = lessonsBlock().review.items[k0];
  check('review: second correct answer moves the item to 7 days', second2.ok && it.stage === 2 && it.retired === false && Math.abs(it.due - (t2 + 7 * DAY)) < 30, JSON.stringify(it));
  await ageItems([k0]);
  await get('/api/review');
  const third = await post('/api/review/answer', { item: k0, option: retrievalDef(k0).options.find((o) => o.correct).id });
  it = lessonsBlock().review.items[k0];
  check('review: the third correct answer retires the item', third.ok && it.retired === true && it.due === null, JSON.stringify(it));
  s = await getState();
  check('review: a retired item is not due again', s.review.due === 0 && (await get('/api/review')).json.review.items.length === 0);
}

async function stageBaselineWhy() {
  await enterStage('baseline-why');
  await expectStepLocked('baseline', 'baseline-why');
  scanLessonText('baseline-why', await viewLesson('baseline-why'));
  await solveAll('baseline-why', { malformed: new Set(['baseline-reflect']) });
  const s = await completeLesson('baseline-why');
  await expectStepActive('baseline');
  check('after baseline-why: the baseline step is next and only it is active', courseMap(s).baseline === 'active' && s.course.filter((c) => c.status === 'active').length === 1);
  const block = lessonsBlock();
  const passedActs = Object.values(block.per_lesson).reduce((n, l) => n + Object.values(l.activities || {}).filter((a) => a.passed).length, 0);
  check('learning records: one per passed activity, nothing else', block.records.filter((r) => r.type === 'activity').length === passedActs && block.records.every((r) => ['activity', 'review'].includes(r.type) && typeof r.at === 'number'), `${block.records.length} records, ${passedActs} passed activities`);
  check('learning records hold no answer text', !JSON.stringify(block.records).includes('word0') && block.records.every((r) => Object.keys(r).every((k) => ['type', 'lesson', 'item', 'source', 'at', 'first_try'].includes(k))), JSON.stringify(Object.keys(block.records[0])));
  check('progress.json holds no key or fixture text', (() => { const r = L.assertProgressClean(); return !r.keyHit && !r.fixtureHit; })());
  check('no violations during the lessons', state.violations.length === 0, state.violations.join(' | '));
  endStage('baseline-why');
}

// ---- the promptfoo track's extra step: add the fixtures to the config (stand-in CLI) ------------------------
const CONFIG_FILE = path.join(PROJECT, 'promptfooconfig.yaml');
const FIXTURES_CONFIG_LINE = 'Read skills/build-promptfoo-config/SKILL.md. Add fixtures/fixture-bad.txt and fixtures/fixture-polished-but-wrong.txt to promptfooconfig.yaml as tests named fixture-bad and fixture-polished-but-wrong. Change nothing else.';
const stepDetailOf = async (id) => (await get(`/api/state?step=${id}`)).json.step;

async function stageFixturesConfig() {
  await enterStage('fixtures-config');
  const s0 = await getState();
  check('fixtures-config: the course and the step list show the extra step after fixtures', s0.steps.map((x) => x.id).join(',') === 'generate,build,fixtures,fixtures-config,readback,predict,key,run,fix,baseline' && courseMap(s0)['fixtures-config'] === 'active' && courseMap(s0).readback === 'locked', s0.steps.map((x) => x.id).join(','));
  const detail = await stepDetailOf('fixtures-config');
  check('fixtures-config: the typed line is exact and the CLI starts in the project folder', detail.cli.line === FIXTURES_CONFIG_LINE && detail.cli.folder_label === 'Your project folder', detail.cli.line);
  check('fixtures-config: neither fixture is a test yet and the config has only the five runs', detail.data.config_exists === true && detail.data.tests.every((t) => t.present === false) && detail.data.fixtures_ready === true && detail.data.scan.length === 0, JSON.stringify(detail.data));
  check('fixtures-config: no answer key exists anywhere before the key step', L.answerKeyLocations().length === 0);
  const locked = await post('/api/step/start', { step: 'readback' });
  check('fixtures-config: readback stays locked until this step is done', locked.status === 400 && locked.code === 'step_locked', `${locked.status} ${locked.code}`);
  const early = await post('/api/step/check', { step: 'fixtures-config' });
  const earlyItems = (await stepDetailOf('fixtures-config')).last_check.items.filter((i) => !i.ok);
  check('fixtures-config: the gate fails before the CLI adds the tests and names them', early.ok && earlyItems.some((i) => i.detail.includes('fixture-bad') && i.detail.includes('fixture-polished-but-wrong')), JSON.stringify(earlyItems.map((i) => i.detail)));
  const before = sha256(CONFIG_FILE);

  const run = await startStepCli('fixtures-config', 'fixtures-config');
  check('fixtures-config: the CLI started in the project folder', path.resolve(run.launch.cwd).toLowerCase() === path.resolve(PROJECT).toLowerCase(), run.launch.cwd);
  const send = await post('/api/step/send', { step: 'fixtures-config' });
  must('fixtures-config: Send accepted', send.ok, send.text.slice(0, 160));
  await driveApprovals(run, async (ev) => ev.filter((e) => e.event === 'approved').length >= 1 && sha256(CONFIG_FILE) !== before, 120000);
  await sleep(1500);
  auditProcess('fixtures-config', run, FIXTURES_CONFIG_LINE);
  const after = await stepDetailOf('fixtures-config');
  check('fixtures-config: the page sees both tests in the config', after.data.tests.every((t) => t.present === true) && after.data.scan.length === 0, JSON.stringify(after.data.tests));
  const text = readText(CONFIG_FILE);
  const template = readText(path.join(L.WORK, 'harness', 'standin-promptfooconfig.yaml')).replace(/\r\n/g, '\n').trimEnd();
  const fixtureTests = ['fixture-bad', 'fixture-polished-but-wrong'].map((n) => `  - description: ${n}\n    vars:\n      output: file://fixtures/${n}.txt\n`).join('');
  check('fixtures-config: the CLI added exactly the two tests, and the runs and the checks were not touched', text.replace(/\r\n/g, '\n') === `${template}\n${fixtureTests}`);
  check('fixtures-config: no answer key anywhere while this step runs', L.answerKeyLocations().length === 0 && !exists(L.projectKeyPath()));
  const pass = await post('/api/step/check', { step: 'fixtures-config' });
  const done = await stepDetailOf('fixtures-config');
  check('fixtures-config: the gate passes and the step is done', pass.ok && done.status === 'done' && done.last_check.ok === true, JSON.stringify(done.last_check));
  const s1 = await getState();
  check('fixtures-config: the CLI was stopped and readback is next', s1.terminal.running === false && courseMap(s1).readback === 'active', JSON.stringify(courseMap(s1)));
  check('fixtures-config: no answer key exists after it either', L.answerKeyLocations().length === 0);
  check('fixtures-config: progress.json is clean and records the promptfoo track', (() => { const r = L.assertProgressClean(); return !r.keyHit && !r.fixtureHit; })() && readJson(PROGRESS).track === 'promptfoo' && readJson(PROGRESS).done.join(',').startsWith('generate,build,fixtures,fixtures-config'));
  check('fixtures-config: no violations (no flags, only the expected typed line, no answered prompts)', state.violations.length === 0, state.violations.join(' | '));
  endStage('fixtures-config');
}

// ---- the baseline step (Script track, stand-in CLI) ---------------------------------------
const BASELINE_LINE = (model) => (L.PF
  ? `Read skills/build-promptfoo-config/SKILL.md and follow it in run + log mode. The runs are the tests named run-1 to run-5. The prompt file is prompt-v0.md. The model was ${model}.`
  : `Read skills/build-eval-script/SKILL.md and follow it in run + log mode. The runs are runs/run-1.txt to runs/run-5.txt. The prompt file is prompt-v0.md. The model was ${model}.`);
const CHECKER_FILE = path.join(PROJECT, L.PF ? 'promptfooconfig.yaml' : 'check.py');
const RUN_FILES = [1, 2, 3, 4, 5].map((n) => `runs/run-${n}.txt`);
const sha256 = (p) => require('crypto').createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const LOG_FILE = path.join(PROJECT, 'iteration-log.md');
const stepDetail = async () => (await get('/api/state?step=baseline')).json.step;

async function startStepCli(stepId, label) {
  L.countSession(label);
  const since = nowSec() - 0.5;
  const r = await post('/api/step/start', { step: stepId });
  must(`${label}: start accepted`, r.ok, r.text.slice(0, 200));
  const launch = await L.waitFor(async () => readEvents().find((e) => e.event === 'launch' && e.ts >= since), 20000, `${label} launch`);
  await sleep(1800);
  return { pid: launch.pid, launch, since };
}

// One stand-in session: Send, press Enter on each approval, wait for the log to be (re)written, stop the CLI.
async function logSession(label, model, wrongCount) {
  if (wrongCount) fs.writeFileSync(MODE_FILE, 'wrong-count'); else fs.rmSync(MODE_FILE, { force: true });
  const before = exists(LOG_FILE) ? sha256(LOG_FILE) : null;
  const run = await startStepCli('baseline', label);
  check(`${label}: the CLI started in the project folder`, path.resolve(run.launch.cwd).toLowerCase() === path.resolve(PROJECT).toLowerCase(), run.launch.cwd);
  const send = await post('/api/step/send', { step: 'baseline' });
  must(`${label}: Send accepted`, send.ok, send.text.slice(0, 160));
  await driveApprovals(run, async (ev) => ev.filter((e) => e.event === 'approved').length >= 1 && exists(LOG_FILE) && sha256(LOG_FILE) !== before, 120000);
  await sleep(1500);
  auditProcess(label, run, BASELINE_LINE(model));
  const stop = await post('/api/step/stop', { step: 'baseline' });
  check(`${label}: Stop works`, stop.ok && (await L.waitFor(cliStopped, 15000, 'CLI stopped').then(() => true)));
  fs.rmSync(MODE_FILE, { force: true });
}

function countsOf(independent) {
  const first = independent['run-1.txt'];
  return Object.keys(first).map((id) => {
    const verdicts = [1, 2, 3, 4, 5].map((n) => independent[`run-${n}.txt`][id]);
    return { id, passes: verdicts.filter((v) => v === 'P').length, checked: verdicts.filter((v) => v !== 'NC').length };
  });
}

async function stageBaseline() {
  await enterStage('baseline');
  const detail = await stepDetail();
  check('baseline: the typed line is exact and names the model the app recorded in the generate step', detail.cli.line === BASELINE_LINE(L.MODEL) && detail.cli.blocked === null && detail.cli.folder_label === 'Your project folder', detail.cli.line);
  check('baseline: no run, no count, no log yet', detail.data.summary === null && detail.data.result === null && detail.data.fresh === false && detail.data.log_exists === false && detail.data.runs_ready === true && detail.data.checker_exists === true);
  check('baseline: there is no model box and no model name in the data', !('model_name' in detail.data));
  check('baseline: no answer key in the project', !exists(L.projectKeyPath()));

  // The model is never typed: an AI start records it, so Send is never held back for a missing model.
  const typed = await post('/api/step/submit', { step: 'baseline', data: { model_name: '  son\n\tnet \u0007 ' } });
  must('baseline: the test-only typed route still saves', typed.ok, typed.text.slice(0, 160));
  check('baseline: a typed name is still forced to one line', (await stepDetail()).cli.line === BASELINE_LINE('son net'), (await stepDetail()).cli.line);
  await post('/api/step/submit', { step: 'baseline', data: { model_name: L.MODEL } });
  check('baseline: the recorded model is back', (await stepDetail()).cli.line === BASELINE_LINE(L.MODEL));

  // Refusals before any work.
  const early = await post('/api/step/check', { step: 'baseline' });
  const earlyItems = (await stepDetail()).last_check.items;
  check('baseline: the gate fails with no log and says what to do', early.ok && earlyItems.some((i) => !i.ok && i.detail.includes('iteration-log.md was not found') && i.detail.includes('Send to AI')), JSON.stringify(earlyItems.filter((i) => !i.ok).map((i) => i.detail)));
  const wrongWhich = await post('/api/step/run-checker', { step: 'baseline', which: 'fixtures' });
  check('baseline: the app run accepts only which=baseline', wrongWhich.status === 400 && wrongWhich.code === 'bad_input', wrongWhich.code);

  // A session whose log has one count too low.
  const checkerBefore = sha256(CHECKER_FILE);
  const runsBefore = RUN_FILES.map((f) => sha256(path.join(PROJECT, f)));
  await logSession('baseline log (one count too low)', L.MODEL, true);
  const wrongLog = readText(LOG_FILE);
  check('baseline: the stand-in wrote an Iteration 0 entry in the skill format', new RegExp(`^## Iteration 0: baseline\\r?\\n- Date: \\d{4}-\\d{2}-\\d{2}\\r?\\n- Prompt: prompt-v0\\.md\\r?\\n- Model: ${L.MODEL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\r?\\n- Runs: 5\\r?\\n- Overall: \\d+ \\/ \\d+\\r?\\n- Not checked: `).test(wrongLog) && wrongLog.includes('| Criterion | Passed | Rate | Notes |'));

  // The app's own run on all five runs.
  const early2 = await post('/api/step/check', { step: 'baseline' });
  check('baseline: before the app counts, the gate says to press Run my checker', early2.ok && (await stepDetail()).last_check.items.some((i) => !i.ok && i.detail.includes('Press Run my checker on the five runs')));
  const ran = await post('/api/step/run-checker', { step: 'baseline', which: 'baseline' });
  must('baseline: the app run is accepted', ran.ok, ran.text.slice(0, 300));
  const data = (await stepDetail()).data;
  check('baseline: the run is usable and fresh', data.result && data.result.ok === true && [0, 1, 100].includes(data.result.exit_code) && data.fresh === true && data.summary && data.summary.runs === 5);
  check('baseline: one checker call covered all five runs', data.result.files.map((f) => f.file.replace(/\\/g, '/')).join(',') === RUN_FILES.join(','), data.result.files.map((f) => f.file).join(','));
  const indep = L.independentRunIn(PROJECT, RUN_FILES);
  const expected = countsOf(indep);
  const mine = data.summary.criteria.map((c) => ({ id: c.id, passes: c.passes, checked: c.checked_runs }));
  check('baseline: the app\'s per-criterion counts equal an independent run of check.py', JSON.stringify(mine) === JSON.stringify(expected), `${JSON.stringify(mine)} vs ${JSON.stringify(expected)}`);
  const total = expected.reduce((n, c) => n + c.passes, 0);
  const possible = expected.reduce((n, c) => n + c.checked, 0);
  check('baseline: the overall total is passes over checked results', data.summary.overall.passes === total && data.summary.overall.total === possible, JSON.stringify(data.summary.overall));
  const saved = readJson(path.join(PROJECT, '.learning', 'results', 'baseline.json'));
  check('baseline: results are stored per criterion in baseline.json', saved.summary && JSON.stringify(saved.summary.criteria.map((c) => [c.id, c.passes, c.checked_runs, c.not_checked, c.failing_runs])) === JSON.stringify(data.summary.criteria.map((c) => [c.id, c.passes, c.checked_runs, c.not_checked, c.failing_runs])));

  // The browser shows what the app counted.
  const { browser, page } = await L.openBrowser({ tall: true });
  try {
    await page.goto(state.url);
    await L.enterPart(page);
    await page.locator('#baseline-overall').waitFor({ timeout: 15000 });
    const text = (await page.locator('#baseline-overall').innerText()).trim();
    const rows = await page.locator('.baseline-grid tbody tr').count();
    check('baseline view: overall and one row per criterion match the app\'s count', text.startsWith(`Overall: ${total} of ${possible} checks passed`) && rows === expected.length, `${text} / ${rows} rows`);
    const firstRow = (await page.locator('.baseline-grid tbody tr').first().innerText()).replace(/\s+/g, ' ');
    check('baseline view: the first row shows its pass count', firstRow.includes(`${expected[0].passes} of ${expected[0].checked}`), firstRow);
    await L.shot(page, 'baseline.png');
  } finally { await browser.close(); }

  // The gate names the criterion and both numbers, and nothing was edited by the app.
  const target0 = expected.find((c) => c.passes > 0);
  const gate = await post('/api/step/check', { step: 'baseline' });
  const gateItems = (await stepDetail()).last_check.items;
  const countItem = gateItems.find((i) => i.label.startsWith('Pass counts'));
  const message = `The log says ${target0.id} passed ${target0.passes - 1} of ${target0.checked} runs. The app counted ${target0.passes} of ${target0.checked}.`;
  check('baseline: a count that is too low fails the gate and names the criterion and both numbers', gate.ok && countItem && !countItem.ok && countItem.detail === message, countItem ? countItem.detail : JSON.stringify(gateItems));
  check('baseline: the step stays active after a failed check', courseMap(await getState()).baseline === 'active');
  check('baseline: the app never edited the log, the checks or a run', sha256(LOG_FILE) === require('crypto').createHash('sha256').update(wrongLog).digest('hex') && sha256(CHECKER_FILE) === checkerBefore && RUN_FILES.every((f, i) => sha256(path.join(PROJECT, f)) === runsBefore[i]));

  // The participant asks the CLI to log again, and the numbers now agree.
  await logSession('baseline log (correct)', L.MODEL, false);
  const fixedLog = readText(LOG_FILE);
  check('baseline: the second entry replaced the first and is Iteration 0 only', fixedLog !== wrongLog && (fixedLog.match(/^## Iteration 0/gm) || []).length === 1);
  const fixedHash = sha256(LOG_FILE);
  const pass = await post('/api/step/check', { step: 'baseline' });
  const passDetail = (await stepDetail());
  check('baseline: the gate passes when the log matches the app\'s own run', pass.ok && passDetail.status === 'done' && passDetail.last_check.ok === true, JSON.stringify(passDetail.last_check));
  check('baseline: the app left the log as the CLI wrote it', sha256(LOG_FILE) === fixedHash);
  const s = await getState();
  check('baseline: the course is finished and the CLI is stopped', s.current_item === null && s.current_step === null && s.course.every((c) => c.status === 'done' || c.status === 'skipped') && s.terminal.running === false);
  check('baseline: progress records the step as done', readJson(PROGRESS).done.slice(-1)[0] === 'baseline');
  check('baseline: no answer key in the project and progress.json is clean', !exists(L.projectKeyPath()) && (() => { const r = L.assertProgressClean(); return !r.keyHit && !r.fixtureHit; })());
  check('baseline: no violations (no flags, only the expected typed lines, no answered prompts)', state.violations.length === 0, state.violations.join(' | '));
  await reviewChecks();
  check('no violations during the review checks', state.violations.length === 0, state.violations.join(' | '));
  endStage('baseline');
}

// ---- optional live mode (promptfoo track, stand-in CLI) -----------------------------------
const LIVE_LINE = (cli, model) => `Read skills/build-promptfoo-config/SKILL.md and follow it in live mode. I use ${cli} with the model ${model}.`;
const LIVE_CONFIG = path.join(PROJECT, 'promptfooconfig.live.yaml');
const PROVIDER_FILE = path.join(PROJECT, 'agent-provider.js');
const KIT_PROVIDER = path.join(KIT, 'skills', 'build-promptfoo-config', 'agent-provider.js');
const PF_STEP_LIST = 'generate,build,fixtures,fixtures-config,readback,predict,key,run,fix,baseline';

async function stageLive() {
  requireStandIn();
  if (!L.PF) throw new Error('the live stage runs on the promptfoo track only');
  const s0 = await getState();
  must('live: the whole course is finished before this stage', s0.current_item === null && s0.current_step === null && s0.course.every((c) => c.status === 'done' || c.status === 'skipped'), JSON.stringify(s0.current_item));
  check('live: it is offered as optional, outside the step list and the course', s0.optional_steps.length === 1 && s0.optional_steps[0].id === 'live' && s0.optional_steps[0].status === 'optional' && s0.steps.map((x) => x.id).join(',') === PF_STEP_LIST && !('live' in courseMap(s0)), JSON.stringify(s0.optional_steps));
  const detail = await stepDetailOf('live');
  check('live: the step is optional, active and on the promptfoo track', detail.optional === true && detail.status === 'active' && detail.track === 'promptfoo' && detail.cli.folder_label === 'Your project folder');
  const points = detail.ui.warning_points.join(' ');
  check('live: the warning says which CLI the helper puts into auto mode, and that the app does not run live mode', points.includes('For Devin CLI the helper adds --permission-mode auto') && points.includes('For GitHub Copilot CLI and Claude Code the helper adds no permission flag') && points.includes('The app does not run live mode') && points.includes('never changes your baseline') && detail.ui.warning_intro.includes('you can skip this step'));
  check('live: before anything is chosen the line shows every option and Start is blocked by the warning', detail.cli.line === LIVE_LINE('<copilot | claude | devin>', L.MODEL) && detail.cli.start_blocked && detail.cli.start_blocked.includes('tick the box'), JSON.stringify(detail.cli));
  check('live: the options come from the content, not the code', detail.data.clis.map((c) => c.id).join(',') === 'copilot,claude,devin');

  // The browser: the course is finished without it, it is offered, and the warning comes before anything can start.
  const { browser, page } = await L.openBrowser({ tall: true });
  try {
    await page.goto(state.url);
    await L.enterPart(page);
    await page.locator('#step-heading').waitFor({ timeout: 15000 });
    check('live view: the page says the course is finished', /finished/i.test(await page.locator('#step-heading').innerText()));
    check('live view: the optional extra is offered and says the course is complete without it', (await page.locator('#optional-live-note').innerText()).includes('complete without it'));
    await page.locator('#open-live').click();
    await page.locator('#live-warning').waitFor({ timeout: 15000 });
    check('live view: the warning, the unticked acknowledgement and the CLI choice are on the page', (await page.locator('#live-warning').innerText()).includes('--permission-mode auto') && (await page.locator('#live-ack').isChecked()) === false && (await page.locator('#live-cli-choice input[type=radio]').count()) === 3);
    check('live view: Start and Send are off until the box is ticked and a CLI is chosen', (await page.locator('#cli-start').getAttribute('aria-disabled')) === 'true' && (await page.locator('#cli-send').getAttribute('aria-disabled')) === 'true' && (await page.locator('#cli-start-blocked').count()) === 1);
    await L.shot(page, 'live.png');
  } finally { await browser.close(); }

  // Nothing starts before the warning is acknowledged and a CLI is chosen.
  const launches = () => readEvents().filter((e) => e.event === 'launch').length;
  const launchesBefore = launches();
  const noAck = await post('/api/step/start', { step: 'live' });
  const noAckSend = await post('/api/step/send', { step: 'live' });
  check('live: Start and Send are refused until the warning is acknowledged', noAck.status === 400 && noAck.code === 'warning_not_acknowledged' && noAckSend.code === 'warning_not_acknowledged', `${noAck.code} ${noAckSend.code}`);
  await post('/api/step/submit', { step: 'live', data: { acknowledged: true } });
  const noCli = await post('/api/step/start', { step: 'live' });
  check('live: and until a CLI is chosen', noCli.status === 400 && noCli.code === 'cli_not_chosen', noCli.code);
  const badCli = await post('/api/step/submit', { step: 'live', data: { cli: 'copilot --yolo' } });
  check('live: only the options in the list can be chosen', badCli.status === 400 && badCli.code === 'bad_input', badCli.code);
  check('live: no CLI process was started by any refused call', launches() === launchesBefore && (await getState()).terminal.running === false);
  const runLive = await post('/api/step/run-checker', { step: 'live', which: 'baseline' });
  check('live: the app has no way to run the live config', runLive.status === 400 && runLive.code === 'bad_input', runLive.code);

  // The CLI that gets its auto mode from the helper is chosen on purpose: the app still adds nothing.
  await post('/api/step/submit', { step: 'live', data: { cli: 'devin' } });
  const ready = await stepDetailOf('live');
  check('live: the typed line is exact, with the chosen CLI and the recorded model', ready.cli.line === LIVE_LINE('devin', L.MODEL) && ready.cli.start_blocked === null && ready.cli.blocked === null, ready.cli.line);
  const early = await post('/api/step/check', { step: 'live' });
  const failing = (await stepDetailOf('live')).last_check.items.filter((i) => !i.ok).map((i) => i.label);
  check('live: the gate fails before anything exists and names what is missing', early.ok && failing.includes('promptfooconfig.live.yaml exists') && failing.includes('Live mode was started here'), failing.join(' / '));
  const mainBefore = sha256(CONFIG_FILE);
  const logBefore = sha256(LOG_FILE);
  const runsBefore = RUN_FILES.map((f) => sha256(path.join(PROJECT, f)));

  const run = await startStepCli('live', 'live mode');
  check('live: the CLI started in the project folder', path.resolve(run.launch.cwd).toLowerCase() === path.resolve(PROJECT).toLowerCase(), run.launch.cwd);
  const send = await post('/api/step/send', { step: 'live' });
  must('live: Send accepted', send.ok, send.text.slice(0, 160));
  await driveApprovals(run, async (ev) => ev.filter((e) => e.event === 'approved').length >= 2 && exists(LIVE_CONFIG) && exists(PROVIDER_FILE), 120000);
  await sleep(1500);
  auditProcess('live', run, LIVE_LINE('devin', L.MODEL));
  const afterSend = await stepDetailOf('live');
  check('live: the page sees both files, the helper unchanged and a clean scan', afterSend.data.config_exists === true && afterSend.data.provider_ok === true && afterSend.data.scan.length === 0 && afterSend.data.started === true, JSON.stringify(afterSend.data));
  check('live: the helper in the project is byte for byte the bundled one', sha256(PROVIDER_FILE) === sha256(KIT_PROVIDER));
  const liveText = readText(LIVE_CONFIG).replace(/\r\n/g, '\n');
  const mainText = readText(CONFIG_FILE).replace(/\r\n/g, '\n');
  const checks = (text) => text.slice(text.indexOf('defaultTest:'), text.indexOf('tests:'));
  check('live: the live config uses only the helper, names the chosen CLI and copies the checks unchanged', liveText.includes("id: 'exec: node ./agent-provider.js'") && liveText.includes('cli: devin') && !liveText.includes('echo') && checks(liveText) === checks(mainText) && !/llm-rubric|apiKey/.test(liveText));
  check('live: the app never edited the main config, the log or a run', sha256(CONFIG_FILE) === mainBefore && sha256(LOG_FILE) === logBefore && RUN_FILES.every((f, i) => sha256(path.join(PROJECT, f)) === runsBefore[i]));
  check('live: the app ran nothing itself: no live results file exists', !exists(path.join(PROJECT, 'results-live.json')));
  check('live: exactly one CLI process was started for this step', launches() === launchesBefore + 1);
  check('live: no answer key in the project or in either working folder', !exists(L.projectKeyPath()) && !exists(L.workKeyPath()) && !exists(L.keyWorkKeyPath()));

  const pass = await post('/api/step/check', { step: 'live' });
  const done = await stepDetailOf('live');
  check('live: the gate passes and the optional step is done', pass.ok && done.status === 'done' && done.last_check.ok === true, JSON.stringify(done.last_check));
  const s1 = await getState();
  check('live: the CLI was stopped and nothing else changed: the steps, the course and the track', s1.terminal.running === false && s1.optional_steps[0].status === 'done' && s1.steps.map((x) => x.id).join(',') === PF_STEP_LIST && s1.steps.every((x) => x.status === 'done') && s1.current_item === null && readJson(PROGRESS).done.join(',') === PF_STEP_LIST && readJson(PROGRESS).track === 'promptfoo');
  check('live: the saved record holds the choice and the noted hashes, never file text', (() => { const live = readJson(PROGRESS).steps.live; return live.cli === 'devin' && live.acknowledged === true && live.done === true && live.start_hashes.config === mainBefore && live.start_hashes.log === logBefore && !JSON.stringify(live).includes('exec:'); })());
  check('live: no violations (no flags, only the expected typed line, no answered prompts)', state.violations.length === 0, state.violations.join(' | '));
  endStage('live');
}

// ---- old progress ------------------------------------------------------------------------
async function spawnApp(home) {
  const log = path.join(L.WORK, 'server-migrate.out');
  fs.writeFileSync(log, '');
  const out = fs.openSync(log, 'a');
  const child = spawn(L.PYTHON, [L.PYZ, '--no-browser', '--custom-ai', '--home', home], { detached: true, stdio: ['ignore', out, out], env: L.filteredEnv(), windowsHide: true, cwd: L.WORK });
  child.unref();
  fs.closeSync(out);
  for (let i = 0; i < 100; i += 1) {
    const m = readText(log).match(/http:\/\/127\.0\.0\.1:(\d+)\/\?t=(\S+)/);
    if (m) return { pid: child.pid, port: m[1], token: m[2] };
    await sleep(100);
  }
  throw new Error('migration server did not print its URL');
}

function copyDir(from, to, skip) {
  fs.mkdirSync(to, { recursive: true });
  for (const e of fs.readdirSync(from, { withFileTypes: true })) {
    if (skip && skip(e.name)) continue;
    if (e.isDirectory()) copyDir(path.join(from, e.name), path.join(to, e.name), skip);
    else fs.copyFileSync(path.join(from, e.name), path.join(to, e.name));
  }
}

async function stageMigrate() {
  requireStandIn();
  const base = path.join(L.WORK, 'migrate-tmp');
  const home = path.join(base, 'home');
  fs.rmSync(base, { recursive: true, force: true });
  fs.mkdirSync(home, { recursive: true });
  fs.copyFileSync(path.join(HOME, 'preflight.json'), path.join(home, 'preflight.json'));
  const projects = [];
  for (const [name, done] of [['p1', ['generate', 'build']], ['p2', ['generate', 'build', 'fixtures', 'readback', 'predict', 'key', 'run', 'fix']]]) {
    const dir = path.join(base, name);
    copyDir(PROJECT, dir, (n) => n === '.learning');
    fs.mkdirSync(path.join(dir, '.learning'), { recursive: true });
    // The shape written before lessons existed: no `lessons` object.
    const old = { version: 1, project_path: dir, cli_command: L.CLI_COMMAND, starter: 'northwind', done, skipped: false, steps: { generate: { model_name: 'sonnet', last_check: null }, build: { checklist: { c1: true }, last_check: null } } };
    if (done.length > 2) for (const k of ['fixtures', 'readback', 'predict', 'key', 'run', 'fix']) old.steps[k] = {};
    fs.writeFileSync(path.join(dir, '.learning', 'progress.json'), JSON.stringify(old, null, 2));
    projects.push({ name, dir, done });
  }
  const app = await spawnApp(home);
  target = { port: app.port, token: app.token };
  try {
    for (const p of projects) {
      const r = await post('/api/setup', { project_path: p.dir, cli_command: L.CLI_COMMAND, starter: 'northwind' });
      check(`${p.name}: older progress.json (no lessons) loads without error`, r.ok, r.text.slice(0, 200));
      const s = await getState();
      const map = courseMap(s);
      const progress = readJson(path.join(p.dir, '.learning', 'progress.json'));
      check(`${p.name}: completed steps are kept`, JSON.stringify(progress.done) === JSON.stringify(p.done) && p.done.every((d) => map[d] === 'done'), JSON.stringify(map));
      check(`${p.name}: step data is kept`, progress.steps.generate.model_name === 'sonnet' && progress.steps.build.checklist.c1 === true);
      check(`${p.name}: a lessons block was added`, progress.lessons && progress.lessons.seed === null && typeof progress.lessons.per_lesson === 'object' && progress.lessons.review && Object.keys(progress.lessons.review.items).length === 0);
      const furthest = ['mission', 'hook', 'several-runs', 'generate', 'rules', 'build', 'trust', 'fixtures', 'readback', 'predict', 'key', 'surprise', 'run', 'fix', 'baseline-why', 'baseline'];
      const lastDone = furthest.indexOf(p.done[p.done.length - 1]);
      const earlier = furthest.slice(0, lastDone).filter((id) => lessonDef(id));
      const later = furthest.slice(lastDone + 1).filter((id) => lessonDef(id));
      check(`${p.name}: lessons before the furthest completed step are skipped and do not block`, earlier.every((id) => map[id] === 'skipped' && progress.lessons.per_lesson[id].migrated === true), earlier.map((id) => `${id}=${map[id]}`).join(' '));
      check(`${p.name}: no reviews are scheduled for them`, Object.keys(progress.lessons.review.items).length === 0 && progress.lessons.records.length === 0);
      check(`${p.name}: the next lesson is active and nothing is blocked wrongly`, s.current_item && s.current_item.kind === 'lesson' && s.current_item.id === later[0] && map[later[0]] === 'active', JSON.stringify(s.current_item));
      const nextStep = furthest.slice(lastDone + 1).find((id) => !lessonDef(id));
      if (nextStep) {
        const locked = await post('/api/step/start', { step: nextStep });
        check(`${p.name}: the next step still waits for the lesson in front of it`, locked.status === 400 && locked.code === 'step_locked', locked.code);
      }
      const hook = await viewLesson('hook');
      check(`${p.name}: a migrated lesson can be read and is closed to answers`, hook.ok && lessonOf(hook).status === 'skipped' && (await answer('hook', 'hook-compare', { option: 'a' })).code === 'lesson_skipped');
      check(`${p.name}: the review queue is empty`, s.review.due === 0 && (await get('/api/review')).json.review.items.length === 0);
    }
  } finally {
    target = null;
    try { execFileSync('taskkill', ['/PID', String(app.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    await sleep(500);
    fs.rmSync(base, { recursive: true, force: true });
    try { fs.unlinkSync(path.join(L.WORK, 'server-migrate.out')); } catch { /* absent */ }
  }
  check('migration temp folder removed', !exists(base));
  endStage('migrate');
}

// ---- Part 1 --------------------------------------------------------------------------
// The whole of Part 1 on the stand-in CLI: the cold run, the three label sets in the rewrite step (each one a run of the
// stand-in, which answers a prompt with label lines better than one without), both scores, every lesson and the own step.
const PART1_ORDER = ['p1-mission', 'cold', 'score', 'p1-gaps', 'p1-frameworks', 'rewrite', 'rescore', 'p1-benefits', 'own'];
const PART1_LINE = 'Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.';
const P1_DIR = path.join(PROJECT, 'part-1');
const p1Scratch = (step) => path.join(HOME, 'part1', step);
const roughNotes = () => readText(path.join(KIT, 'part1', 'rough-notes.txt')).replace(/\r\n/g, '\n').replace(/^\n+|\n+$/g, '');
const p1Marks = (yes) => Object.fromEntries([1, 2, 3, 4, 5].map((i) => [`r${i}`, i <= yes ? 'yes' : 'no']));

async function startStepCli(step, label) {
  L.countSession(label);
  const since = nowSec() - 0.5;
  const r = await post('/api/step/start', { step });
  must(`${label}: start accepted`, r.ok, r.text.slice(0, 200));
  const launch = await L.waitFor(async () => readEvents().find((e) => e.event === 'launch' && e.ts >= since), 20000, `${label} launch`);
  await sleep(1800); // the stand-in prints its input line
  return { pid: launch.pid, launch, since };
}

// One run of a Part 1 step: Start, Send, the participant's Enter on each approval, the file saved by the app.
async function runPart1Cli(step, label, outName) {
  const out = path.join(P1_DIR, outName);
  const run = await startStepCli(step, label);
  check(`${label}: the CLI ran in this step's scratch folder`, path.resolve(run.launch.cwd).toLowerCase() === p1Scratch(step).toLowerCase(), run.launch.cwd);
  check(`${label}: the folder held only prompt.md when the CLI started`, JSON.stringify(fs.readdirSync(p1Scratch(step)).sort()) === JSON.stringify(['prompt.md']), fs.readdirSync(p1Scratch(step)).join(','));
  const sent = await post('/api/step/send', { step });
  must(`${label}: Send accepted`, sent.ok, sent.text.slice(0, 160));
  await driveApprovals(run, async () => hasText(out) && (await cliStopped()));
  const saved = readText(out);
  check(`${label}: the answer was saved from the CLI's file and not from the screen`, saved.trim().length > 0 && !saved.includes('DECOY-TERMINAL-ONLY'));
  check(`${label}: the CLI process ended`, await L.waitFor(async () => !L.pidAlive(run.pid), 15000, `process ${run.pid} gone`).then(() => true).catch(() => false));
  auditProcess(label, run, PART1_LINE);
  return saved;
}

async function answerStepQuestion(step) {
  const item = P1_CONTENT.step_checks.find((c) => c.step === step);
  const right = item.options.find((o) => o.correct).id;
  const r = await post('/api/step/question', { step, option: right });
  check(`part 1 ${step}: the quick check is answered and never gates`, r.ok && r.json.result.passed === true, r.text.slice(0, 160));
}

async function part1Step(step, data) {
  const r = await post('/api/step/submit', { step, data });
  must(`part 1 ${step}: save accepted`, r.ok, `${r.status} ${r.code} ${r.message}`);
}

async function part1Check(step) {
  const r = await post('/api/step/check', { step });
  must(`part 1 ${step}: check accepted`, r.ok, `${r.status} ${r.code} ${r.message}`);
  const s = await getState();
  const detail = (await get(`/api/state?step=${step}`)).json.step;
  check(`part 1 ${step}: the gate passed and the step is done`, detail.last_check && detail.last_check.ok === true && courseMap(s)[step] === 'done', JSON.stringify(detail.last_check));
}

async function stagePart1() {
  requireStandIn();
  activePart = 'part-1';
  try {
    await part1Flow();
  } finally {
    activePart = null;
  }
  endStage('part1');
}

async function part1Flow() {
  let s = await getState();
  check('part 1: the course lists its nine items in order', JSON.stringify(s.course.map((c) => c.id)) === JSON.stringify(PART1_ORDER), JSON.stringify(s.course.map((c) => c.id)));
  check('part 1: the page words are Part 1\'s', s.course_text.brand_sub === 'Part 1 \u00b7 Structured prompting', s.course_text.brand_sub);
  check('part 1: Part 3 keeps its own words', (await get('/api/state')).json.course_text.brand_sub.startsWith('Part 3'));
  const row = (await get('/api/state')).json.series.parts.find((p) => p.id === 'part-1');
  check('part 1: the Series map row is a course, not coming soon', row.kind === 'course' && row.total === 9 && row.state === 'not_started', JSON.stringify(row));
  await enterStage('p1-mission');

  // Order and locking.
  await expectStepLocked('cold', 'p1-mission', 'part 1 cold before the mission');
  const early = await get('/api/kit?ref=kit:part1/sample-rtcc.md');
  check('part 1: the sample prompts stay closed before the rescore step', early.status === 400 && early.code === 'bad_ref', `${early.status} ${early.code}`);
  const mission = lessonOf(await viewLesson('p1-mission'));
  check('part 1: the mission is one page with no questions and names no framework', mission.activities.length === 0 && !/framework|RTCC|RISE/i.test(mission.body));
  await completeLesson('p1-mission');

  // The cold run.
  await expectStepActive('cold');
  let r = await post('/api/step/start', { step: 'cold' });
  check('cold: Start is refused until a prompt is saved', r.status === 400 && r.code === 'prompt_missing', `${r.status} ${r.code}`);
  const coldPrompt = 'Please write my Friday update from the notes below.';
  await part1Step('cold', { prompt: coldPrompt });
  check('cold: Save wrote only the participant\'s words', JSON.stringify(fs.readdirSync(P1_DIR)) === JSON.stringify(['prompt-cold.md']) && readText(path.join(P1_DIR, 'prompt-cold.md')) === coldPrompt);
  const coldOut = await runPart1Cli('cold', 'part 1 cold run', 'output-cold.txt');
  const divider = P1_STEPS.cold.divider;
  check('cold: the CLI read the words, a divider and the rough notes', readText(path.join(p1Scratch('cold'), 'prompt.md')) === `${coldPrompt}\n\n${divider}\n\n${roughNotes()}\n`);
  check('cold: the stand-in gave the weaker answer to a prompt with no labels', /Dear lead/.test(coldOut) && !/Blocker:/.test(coldOut));
  await part1Check('cold');
  await answerStepQuestion('cold');
  r = await post('/api/step/start', { step: 'cold' });
  check('cold: a finished step offers no second run', r.status === 400 && r.code === 'step_done', `${r.status} ${r.code}`);

  // Scoring by hand.
  await expectStepActive('score');
  await part1Step('score', { answers: p1Marks(2), gap: 'It never said what I need from my lead.', in_prompt: 'no' });
  const scoreData = (await get('/api/state?step=score')).json.step.data;
  check('score: the count comes from the participant\'s own answers', scoreData.score && scoreData.score.text === '2 of 5' && scoreData.output === coldOut, JSON.stringify(scoreData.score));
  await part1Check('score');
  await answerStepQuestion('score');

  // The two lessons before the reveal-based rewrite.
  await enterStage('p1-gaps');
  await solveAll('p1-gaps');
  await completeLesson('p1-gaps');
  await expectStepLocked('rewrite', 'p1-frameworks', 'part 1 rewrite before the frameworks lesson');
  await enterStage('p1-frameworks');
  await solveAll('p1-frameworks');
  await completeLesson('p1-frameworks');

  // The rewrite, once with each label set: every Start is a new CLI process and the last run is the one checked.
  await expectStepActive('rewrite');
  let rewriteOut = '';
  for (const fw of ['rtcc', 'rise', 'own']) {
    const skeleton = P1_STEPS.rewrite.labels.find((l) => l.id === fw).skeleton;
    await part1Step('rewrite', { prompt: skeleton, framework: fw });
    rewriteOut = await runPart1Cli('rewrite', `part 1 rewrite run (${fw})`, 'output-framework.txt');
    check(`rewrite (${fw}): the stand-in gave the better answer to a prompt with labels`, /Blocker:/.test(rewriteOut) && !/Dear lead/.test(rewriteOut));
    check(`rewrite (${fw}): the CLI read the same rough notes as the cold run`, readText(path.join(p1Scratch('rewrite'), 'prompt.md')).endsWith(`${divider}\n\n${roughNotes()}\n`));
  }
  await part1Check('rewrite');
  await answerStepQuestion('rewrite');

  // Scoring again and the compare.
  await part1Step('rescore', { answers: p1Marks(4), reflections: { added: 'The reader and the length.', better: 'It told the AI what it needed.' } });
  const compare = (await get('/api/state?step=rescore')).json.step.data.compare;
  check('rescore: both runs are side by side with the change between the scores', compare.first.output === coldOut && compare.second.output === rewriteOut && compare.change === 2 && /went up by 2/.test(compare.change_text), JSON.stringify([compare.change, compare.change_text]));
  check('rescore: the run-to-run variation note is shown', compare.notes.some((n) => /vary/.test(n)));
  await part1Check('rescore');
  await answerStepQuestion('rescore');

  // The benefits lesson, with the sample prompts now open.
  const sample = await get('/api/kit?ref=kit:part1/sample-rise.md');
  check('part 1: the sample prompts open once the rescore step is done', sample.status === 200 && /Role:/.test(sample.json.kit.text), `${sample.status}`);
  await enterStage('p1-benefits');
  await solveAll('p1-benefits');
  await completeLesson('p1-benefits');

  // The own step.
  await expectStepActive('own');
  const noCli = await post('/api/step/start', { step: 'own' });
  check('own: the step has no CLI to start', noCli.status === 400 && noCli.code === 'not_supported', `${noCli.status} ${noCli.code}`);
  await part1Step('own', { before: 'Write my weekly report.', after: 'Role: analyst\nTask: write my weekly report', labels: 'RTCC' });
  await part1Check('own');
  await answerStepQuestion('own');

  // The whole Part, and what it left behind.
  s = await getState();
  check('part 1: every item is done and nothing is left to do', s.course.every((c) => c.status === 'done') && s.current_item === null, JSON.stringify(s.current_item));
  check('part 1: the finished words name Part 2', /Part 2/.test(s.course_text.finished_body));
  const series = (await get('/api/state')).json.series.parts;
  check('part 1: the Series map shows it done, 9 of 9', series.find((p) => p.id === 'part-1').state === 'done' && series.find((p) => p.id === 'part-1').done === 9);
  check('part 1: Part 3 is not changed by it', series.find((p) => p.id === 'part-3').state === 'done');
  check('part 1: the project folder holds exactly the six files', JSON.stringify(fs.readdirSync(P1_DIR).sort()) === JSON.stringify(['output-cold.txt', 'output-framework.txt', 'own-after.md', 'own-before.md', 'prompt-cold.md', 'prompt-framework.md']), fs.readdirSync(P1_DIR).join(','));
  const progress = readJson(PROGRESS);
  const saved = JSON.stringify(progress.parts['part-1']);
  check('part 1: progress lists the five steps in order', JSON.stringify(progress.parts['part-1'].done) === JSON.stringify(['cold', 'score', 'rewrite', 'rescore', 'own']), saved);
  check('part 1: progress holds only the participant\'s own marks and no key, output or notes', !saved.includes('Dear lead') && !saved.includes('Mon: standup') && !kitKeyLines.some((line) => saved.includes(line)));
  check('part 1: the Part 3 progress keys are unchanged in place', Array.isArray(progress.done) && progress.steps && progress.steps.baseline !== undefined);
}

// ---- Part 2 --------------------------------------------------------------------------
// The whole of Part 2. It runs nothing, so no CLI starts: the stage works the lessons, saves the worksheet, adds the thresholds,
// builds and saves the test case file, checks it, compares with the reference and finishes, all over the routes.
const P2_STEPS = JSON.parse(readText(path.join(APP, 'content', 'part-2-steps.json'))).steps;
const PART2_ORDER = ['p2-mission', 'p2-criteria', 'draft', 'p2-thresholds', 'thresholds', 'p2-testfile', 'test-file', 'reference'];
const P2_DIR = path.join(PROJECT, 'part-2');
const P2_ROWS = [
  { requirement: 'It is under 150 words', criterion: 'The update is short', type: 'format', threshold: 'Word count under 100 passes' },
  { requirement: 'The work is grouped by client (Northwind, Contoso, Internal), not by day', criterion: 'Work is grouped by client', type: 'format', threshold: 'Passes if the labels Alpha and Beta both appear' },
  { requirement: 'It calls out the blocker and what you need to resolve it', criterion: 'The blocker is named', type: 'content', threshold: 'Passes if the word "stuck" appears' },
];
const P2_CHOICES = { C1: 'had', C2: 'missed', C3: 'different', C4: 'vague', C5: 'had', C6: 'had' };
// Reference thresholds other than the two worked examples' own: none may be shown before the file is done.
const p2ReferenceParts = () => {
  const text = readText(path.join(KIT, 'northwind', 'northwind-test-cases-reference.md'));
  const thresholds = [...text.matchAll(/^- Threshold: (.+)$/gm)].map((m) => m[1].trim()).slice(1);
  return thresholds.concat(['Teams, not email', 'Factual tone', 'Uses the rough notes', 'happy to report', 'Sincerely']);
};

async function part2Step(step, data) {
  const r = await post('/api/step/submit', { step, data });
  must(`part 2 ${step}: save accepted`, r.ok, `${r.status} ${r.code} ${r.message}`);
  return r;
}

async function part2Check(step) {
  const r = await post('/api/step/check', { step });
  must(`part 2 ${step}: check accepted`, r.ok, `${r.status} ${r.code} ${r.message}`);
  const s = await getState();
  const detail = (await get(`/api/state?step=${step}`)).json.step;
  check(`part 2 ${step}: the gate passed and the step is done`, detail.last_check && detail.last_check.ok === true && courseMap(s)[step] === 'done', JSON.stringify(detail.last_check));
  const q = P2_CONTENT.step_checks.find((c) => c.step === step);
  const answered = await post('/api/step/question', { step, option: q.options.find((o) => o.correct).id });
  check(`part 2 ${step}: the quick check is answered and never gates`, answered.ok && answered.json.result.passed === true, answered.text.slice(0, 160));
}

async function expectP2Locked(step, lessonId, note) {
  const s = await getState();
  check(`${note}: the step is locked in the course`, courseMap(s)[step] === 'locked', courseMap(s)[step]);
  const r = await post('/api/step/submit', { step, data: { checks: {} } });
  check(`${note}: saving is refused and names the lesson`, r.status === 400 && r.code === 'step_locked' && r.message.includes(lessonDef(lessonId).title), `${r.status} ${r.code} ${r.message}`);
  const c = await post('/api/step/check', { step });
  check(`${note}: checking it is refused`, c.status === 400 && c.code === 'step_locked', `${c.status} ${c.code}`);
}

async function stagePart2() {
  requireStandIn();
  activePart = 'part-2';
  try {
    await part2Flow();
  } finally {
    activePart = null;
  }
  endStage('part2');
}

async function part2Flow() {
  const launchesBefore = readEvents().filter((e) => e.event === 'launch').length;
  const ownTestCases = readText(path.join(PROJECT, 'test-cases.md'));
  let s = await getState();
  check('part 2: the course lists its eight items in order', JSON.stringify(s.course.map((c) => c.id)) === JSON.stringify(PART2_ORDER), JSON.stringify(s.course.map((c) => c.id)));
  check('part 2: the page words are Part 2\'s', s.course_text.brand_sub === 'Part 2 \u00b7 Defining evaluation criteria', s.course_text.brand_sub);
  const row = (await get('/api/state')).json.series.parts.find((p) => p.id === 'part-2');
  check('part 2: the Series map row is a course, not coming soon', row.kind === 'course' && row.total === 8 && row.state === 'not_started', JSON.stringify(row));
  await enterStage('p2-mission');

  // Order and locking, and what a preview shows.
  await expectP2Locked('draft', 'p2-mission', 'part 2 draft before the lessons');
  const preview = await get('/api/state?step=reference');
  check('part 2: the reference step opens as a preview with no reference in it', preview.status === 200 && preview.json.step.preview === true && preview.json.step.data && Object.keys(preview.json.step.data).length === 0, preview.text.slice(0, 120));
  const previewText = JSON.stringify(preview.json.step).toLowerCase();
  check('part 2: the preview holds no reference threshold or list word', !p2ReferenceParts().some((x) => previewText.includes(x.toLowerCase())));
  const mission = lessonOf(await viewLesson('p2-mission'));
  check('part 2: the mission is one page with no questions', mission.activities.length === 0);
  await completeLesson('p2-mission');
  await enterStage('p2-criteria');
  await solveAll('p2-criteria');
  await completeLesson('p2-criteria');

  // The worksheet.
  await expectStepActive('draft');
  const draft = (await get('/api/state?step=draft')).json.step;
  check('draft: no CLI is offered', draft.cli === null && draft.kind === 'criteria_table');
  check('draft: the five requirements are on the card and no worksheet is saved yet', draft.data.requirements.length === 5 && draft.data.rows.length === 0 && draft.data.saved === false);
  let r = await post('/api/step/start', { step: 'draft' });
  check('draft: the step has no CLI to start', r.status === 400 && r.code === 'not_supported', `${r.status} ${r.code}`);
  await part2Step('draft', { rows: P2_ROWS.slice(0, 2) });
  r = await post('/api/step/check', { step: 'draft' });
  const failed = (await get('/api/state?step=draft')).json.step.last_check;
  check('draft: two rows and no ticks do not pass, and the gate says what is missing', r.ok && failed.ok === false && failed.items.filter((i) => !i.ok).every((i) => i.detail.length > 0), JSON.stringify(failed));
  await part2Step('draft', { rows: P2_ROWS.map((x) => ({ ...x, threshold: '' })), checks: { traces: true, distinct: true } });
  check('draft: the saved worksheet is shown again when the step is reopened', (await get('/api/state?step=draft')).json.step.data.rows.length === 3);
  await part2Check('draft');
  r = await post('/api/step/submit', { step: 'draft', data: { rows: P2_ROWS } });
  check('draft: a finished step refuses another save', r.status === 400 && r.code === 'step_done', `${r.status} ${r.code}`);

  await enterStage('p2-thresholds');
  await solveAll('p2-thresholds');
  await completeLesson('p2-thresholds');

  // The thresholds.
  await expectStepActive('thresholds');
  const rows = (await get('/api/state?step=thresholds')).json.step.data.rows;
  check('thresholds: the rows from the first step are shown with an empty threshold each', rows.length === 3 && rows.every((x) => x.threshold === ''), JSON.stringify(rows));
  const vague = P2_ROWS.map((x, i) => (i === 0 ? { ...x, threshold: 'The update is clear' } : x));
  await part2Step('thresholds', { rows: vague, checks: { script_test: true } });
  const notes = (await get('/api/state?step=thresholds')).json.step.data.notes;
  check('thresholds: a vague word gets a note that names it', notes.length === 1 && /clear/.test(notes[0].text), JSON.stringify(notes));
  await part2Step('thresholds', { rows: P2_ROWS.map((x, i) => ({ ...x, criterion: 'Changed', threshold: i === 1 ? P2_ROWS[1].threshold : x.threshold })) });
  check('thresholds: only the threshold column changes in this step', (await get('/api/state?step=thresholds')).json.step.data.rows.every((x, i) => x.criterion === P2_ROWS[i].criterion));
  await part2Check('thresholds');

  await enterStage('p2-testfile');
  await solveAll('p2-testfile');
  await completeLesson('p2-testfile');

  // The test case file.
  await expectStepActive('test-file');
  const early = (await get('/api/state?step=test-file')).json.step.data;
  check('test-file: the file is empty at first and a worksheet is there to build from', early.saved === false && early.has_worksheet === true);
  await part2Step('test-file', { text: 'My own words so far.' });
  r = await post('/api/step/submit', { step: 'test-file', data: { build: true } });
  check('test-file: building asks before replacing saved text', r.status === 400 && r.code === 'confirm_replace', `${r.status} ${r.code}`);
  check('test-file: the saved text is kept when the build is declined', readText(path.join(P2_DIR, 'test-cases.md')) === 'My own words so far.');
  await part2Step('test-file', { build: true, replace: true });
  const built = readText(path.join(P2_DIR, 'test-cases.md'));
  check('test-file: the built file holds the participant\'s own criteria in order', P2_ROWS.every((x, i) => built.includes(`### C${i + 1}: ${x.criterion}`) && built.includes(`- Threshold: ${x.threshold}`)));
  check('test-file: the supporting list section holds no Northwind list', !/excited|thrilled|happy to report/i.test(built.split('## Supporting lists')[1] || ''));
  await part2Step('test-file', { text: `${built}- Banned words: aaa, bbb\n` });
  await part2Check('test-file');
  check('test-file: Part 3\'s own test-cases.md is untouched', readText(path.join(PROJECT, 'test-cases.md')) === ownTestCases);

  // The reference, shown only now.
  await expectStepActive('reference');
  const reveal = (await get('/api/state?step=reference')).json.step.data;
  check('reference: the six reference criteria and the example\'s own list are shown now', reveal.revealed === true && reveal.reference.length === 6 && reveal.lists.some((l) => /Banned words/.test(l)), JSON.stringify(reveal.reference.map((x) => x.id)));
  check('reference: four choices of equal label length are offered', reveal.options.length === 4 && new Set(reveal.options.map((o) => o.label.split(/\s+/).length)).size === 1);
  await part2Step('reference', { choices: { C1: 'had' } });
  r = await post('/api/step/check', { step: 'reference' });
  check('reference: a missing choice fails the gate and names it', r.ok && (await get('/api/state?step=reference')).json.step.last_check.ok === false);
  await part2Step('reference', { text: `${readText(path.join(P2_DIR, 'test-cases.md'))}\n` });
  await part2Step('reference', { choices: P2_CHOICES });
  await part2Check('reference');

  // The whole Part, and what it left behind.
  s = await getState();
  check('part 2: every item is done and nothing is left to do', s.course.every((c) => c.status === 'done') && s.current_item === null, JSON.stringify(s.current_item));
  check('part 2: the finished words name the file and Part 3', /part-2/.test(s.course_text.finished_body) && /Part 3/.test(s.course_text.finished_body), s.course_text.finished_body);
  const series = (await get('/api/state')).json.series.parts;
  check('part 2: the Series map shows it done, 8 of 8', series.find((p) => p.id === 'part-2').state === 'done' && series.find((p) => p.id === 'part-2').done === 8);
  check('part 2: Parts 1 and 3 are not changed by it', series.find((p) => p.id === 'part-3').state === 'done' && series.find((p) => p.id === 'part-1').state === 'done');
  check('part 2: the project folder holds exactly the two files', JSON.stringify(fs.readdirSync(P2_DIR).sort()) === JSON.stringify(['test-cases.md', 'worksheet.json']), fs.readdirSync(P2_DIR).join(','));
  const progress = readJson(PROGRESS);
  const saved = JSON.stringify(progress.parts['part-2']);
  check('part 2: progress lists the four steps in order', JSON.stringify(progress.parts['part-2'].done) === JSON.stringify(['draft', 'thresholds', 'test-file', 'reference']), saved);
  check('part 2: progress holds no worksheet text, file text or reference text', !P2_ROWS.some((x) => saved.includes(x.criterion) || saved.includes(x.threshold)) && !p2ReferenceParts().some((x) => saved.includes(x)));
  check('part 2: no CLI was started', readEvents().filter((e) => e.event === 'launch').length === launchesBefore);
}

// ---- Model choice -------------------------------------------------------------------------
// A second app over a throwaway home whose recipe override gives the stand-in model options (the main stand-in has
// none, so it passes no option). Each AI start passes the chosen model, the app records it, a change while the AI
// runs touches nothing, and the app still types nothing and answers no prompt.
async function stageModel() {
  requireStandIn();
  const base = path.join(L.WORK, 'model-tmp');
  const home = path.join(base, 'home');
  const dir = path.join(base, 'project');
  fs.rmSync(base, { recursive: true, force: true });
  fs.mkdirSync(home, { recursive: true });
  fs.copyFileSync(path.join(HOME, 'preflight.json'), path.join(home, 'preflight.json'));
  const recipe = {
    id: 'stand-in', name: 'Stand-in', cli_command: path.parse(L.PYTHON).name.toLowerCase(), shell: 'none', command: '',
    models: { sonnet: { label: 'Sonnet', launch: ['--model', 'sonnet'] }, haiku: { label: 'Haiku', launch: ['--model', 'haiku'] } },
  };
  fs.writeFileSync(path.join(home, 'cli-recipes.json'), JSON.stringify({ recipes: [recipe] }));
  const progressFile = path.join(dir, '.learning', 'progress.json');
  const recordedModel = () => readJson(progressFile).parts['part-1'].steps.cold.model_name;
  const app = await spawnApp(home);
  target = { port: app.port, token: app.token };
  activePart = 'part-1';
  try {
    const setup = await post('/api/setup', { project_path: dir, cli_command: L.CLI_COMMAND, starter: 'northwind' });
    must('model: the second app set up its project', setup.ok, setup.text.slice(0, 200));
    let block = (await getState()).ai_model;
    check('model: the choice is Sonnet, with both options offered', block.preference === 'sonnet' && block.available === true && block.options.map((o) => o.id).join(',') === 'sonnet,haiku', JSON.stringify(block));
    const bad = await post('/api/model', { preference: 'opus' });
    check('model: a model that is not offered is refused', bad.status === 400 && bad.code === 'bad_model', `${bad.status} ${bad.code}`);

    const mission = await post('/api/lesson/complete', { lesson: 'p1-mission' });
    must('model: the Part 1 mission was completed', mission.ok, mission.text.slice(0, 160));
    const saved = await post('/api/step/submit', { step: 'cold', data: { prompt: 'Please write my Friday update from the notes below.' } });
    must('model: the prompt was saved', saved.ok, saved.text.slice(0, 160));

    const sonnet = await startStepCli('cold', 'model: AI start on Sonnet');
    check('model: Sonnet starts the AI with its launch option and nothing else', JSON.stringify(sonnet.launch.argv) === JSON.stringify(['--model', 'sonnet']), JSON.stringify(sonnet.launch.argv));
    check('model: the app recorded Sonnet, with nothing typed by the participant', recordedModel() === 'sonnet', recordedModel());

    const whileRunning = await post('/api/model', { preference: 'haiku' });
    must('model: the choice was changed while the AI runs', whileRunning.ok, whileRunning.text.slice(0, 160));
    block = (await getState()).ai_model;
    check('model: the change applies at the next start and the running AI is untouched', block.preference === 'haiku' && block.applies_next_start === true && L.pidAlive(sonnet.pid) && (await getState()).terminal.running === true);
    const stop = await post('/api/step/stop', { step: 'cold' });
    check('model: Stop works', stop.ok && (await L.waitFor(cliStopped, 15000, 'CLI stopped').then(() => true)));

    const haiku = await startStepCli('cold', 'model: AI start on Haiku');
    check('model: Haiku starts the AI with its launch option', JSON.stringify(haiku.launch.argv) === JSON.stringify(['--model', 'haiku']), JSON.stringify(haiku.launch.argv));
    check('model: the app recorded Haiku', recordedModel() === 'haiku', recordedModel());
    const events = readEvents().filter((e) => e.pid === sonnet.pid || e.pid === haiku.pid);
    check('model: the app typed nothing and answered no prompt in either start', !events.some((e) => e.event === 'line' || e.event === 'approved'), JSON.stringify(events.map((e) => e.event)));
    const stop2 = await post('/api/step/stop', { step: 'cold' });
    check('model: Stop works again', stop2.ok && (await L.waitFor(cliStopped, 15000, 'CLI stopped').then(() => true)));
    check('model: the choice is kept in the app folder', readJson(path.join(home, 'preflight.json')).model_preference === 'haiku');
    check('model: the answer key and every answer stay out of the record', !JSON.stringify(readJson(progressFile)).includes('answer-key'));
  } finally {
    activePart = null;
    target = null;
    try { execFileSync('taskkill', ['/PID', String(app.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
    await sleep(500);
    fs.rmSync(base, { recursive: true, force: true });
    try { fs.unlinkSync(path.join(L.WORK, 'server-migrate.out')); } catch { /* absent */ }
  }
  check('model temp folder removed', !exists(base));
  endStage('model');
}

module.exports = {
  mission: stageMission, hook: stageHook, 'several-runs': stageSeveralRuns, rules: stageRules, trust: stageTrust, surprise: stageSurprise,
  'baseline-why': stageBaselineWhy, baseline: stageBaseline, 'fixtures-config': stageFixturesConfig, live: stageLive, part1: stagePart1, part2: stagePart2, migrate: stageMigrate, model: stageModel,
};
