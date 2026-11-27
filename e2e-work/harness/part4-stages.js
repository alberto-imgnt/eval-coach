// Stand-in end-to-end stages for Part 4 (iterating with evaluation-driven development), on the stand-in CLI only.
//
// `part4` works the participant's own Part 3 baseline in the main stand-in home (after `part2`). `part4-practice` works the
// catch-up path on a second app whose Part 3 was never done. Both drive the routes the page uses. The stand-in answers each
// measure line from a fixed set picked by a marker line the harness puts in its own edit of the prompt (see fake_cli.py), so
// every round's five answers are known. Expected counts always come from an independent run of a checker (the attempt's own
// check.py, or the Northwind reference checker on the promptfoo track), never from the app. The harness types only the
// participant's paste, and decides nothing from what is on the screen.
const L = require('./lib');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

module.exports = function part4Stages(h) {
  const { state, PROJECT, HOME, APP, KIT, PROGRESS, LOG_FILE, RUN_FILES, MODE_FILE, PASTE_AUDIT, LOCK_MESSAGE, check, must, endStage, requireStandIn,
    get, post, getState, viewLesson, lessonOf, actView, courseMap, answer, correctAnswer, wrongAnswer, solveAll, solveActivity, completeLesson,
    enterStage, expectStepActive, expectStepLocked, lessonDef, openPart3Ai, expectPart3SendRefused, pastePart3Line, driveApprovals, auditProcess,
    cliStopped, countsOf, spawnApp, sha256, readText, readJson, exists, hasText, sleep } = h;

  const P4_STEPS = JSON.parse(readText(path.join(APP, 'content', 'part-4-steps.json'))).steps;
  const P4_WORDS = JSON.parse(readText(path.join(APP, 'content', 'part-4-attempts.json')));
  const PART4_ORDER = ['p4-mission', 'starting-point', 'p4-checker-first', 'known-good', 'p4-one-change', 'p4-worked-example', 'hypothesis-1', 'edit-1', 'measure-1', 'decide-1', 'p4-read-results', 'hypothesis-2', 'edit-2', 'measure-2', 'decide-2', 'p4-keep-and-log'];
  const GOLDEN = path.join(L.ROOT, 'tests', 'golden');
  const WORKED = path.join(GOLDEN, 'part4-worked');
  const NORTHWIND_SAMPLES = path.join(GOLDEN, 'northwind');
  const P4_MEASURE_LINE = 'Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else.';
  const P4_CHECKER = L.PF ? 'promptfooconfig.yaml' : 'check.py';
  const P4_TIGHTEN_FIND = "return True, 'found \"Blocker:\" and \"Need:\"'";
  const P4_RUNS = [1, 2, 3, 4, 5];
  const P4_PART3_FILES = ['prompt-v0.md', 'test-cases.md', P4_CHECKER, ...RUN_FILES, path.join('.learning', 'results', 'baseline.json')];
  const PART4_TMP = path.join(L.WORK, 'part4-tmp');

  const p4Answers = (kind) => P4_RUNS.map((k) => {
    if (kind === 'gain' || kind === 'flat') return readText(path.join(WORKED, kind === 'gain' ? 'round-1' : 'round-2', `run-${k}.txt`));
    if (kind === 'worse') return readText(path.join(NORTHWIND_SAMPLES, ['sample-run-3.txt', 'sample-run-5.txt', 'fixture-bad.txt', 'fixture-polished-but-wrong.txt', 'sample-run-3.txt'][k - 1]));
    return readText(path.join(NORTHWIND_SAMPLES, `sample-run-${k}.txt`));
  });
  const lf = (text) => text.replace(/\r\n/g, '\n');
  const fmt = (template, values) => template.replace(/\{(\w+)\}/g, (_, key) => values[key]);
  const digest = (data) => crypto.createHash('sha256').update(data).digest('hex');
  const escapeRe = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  // Where a Part 4 working folder keeps its files: the participant's own, or the Practice one.
  function p4Ctx(project, home, practice) {
    const base = practice ? path.join(project, 'part-4', 'practice') : path.join(project, 'part-4');
    return {
      project, home, practice, base,
      attempt: (n) => path.join(base, 'attempts', String(n)),
      startPrompt: path.join(practice ? base : project, 'prompt-v0.md'),
      log: path.join(practice ? base : project, 'iteration-log.md'),
      logRel: practice ? 'part-4/practice/iteration-log.md' : 'iteration-log.md',
      rel: practice ? 'part-4/practice' : 'part-4',
      blind: path.join(home, 'part4', 'blind'),
      progress: path.join(project, '.learning', 'progress.json'),
    };
  }

  // An independent run of a folder's checker: the folder's own check.py on the Script track, the Northwind reference checker
  // (tightened the way the config says it is) on the promptfoo track. Results are keyed by file name, like parseCheckerText.
  function p4Independent(dir, files) {
    let checker = path.join(dir, 'check.py');
    if (L.PF) {
      const reference = readText(path.join(GOLDEN, 'reference-check.py'));
      const tight = readText(path.join(dir, 'promptfooconfig.yaml')).includes('test data');
      checker = path.join(L.WORK, 'pf-independent-p4.py');
      fs.writeFileSync(checker, tight ? reference.replace(P4_TIGHTEN_FIND, `if 'test data' not in text.split('Blocker:', 1)[1].splitlines()[0]:\n        return False, 'blocker does not mention test data'\n    ${P4_TIGHTEN_FIND}`) : reference);
    }
    let out;
    try {
      out = execFileSync(L.PYTHON, [checker, ...files], { cwd: dir, encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1' }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      if (e.status === 0 || e.status === 1) out = e.stdout.toString();
      else throw new Error(`the independent checker failed: ${e.status} ${e.stderr}`);
    }
    return L.parseCheckerText(out);
  }

  // Per-rule counts of the five answers in a folder, optionally limited to some rule ids.
  function p4Counts(dir, ids) {
    const found = p4Independent(dir, P4_RUNS.map((k) => `runs/run-${k}.txt`));
    return countsOf(found).filter((c) => !ids || ids.includes(c.id));
  }
  const p4Total = (counts) => ({ passes: counts.reduce((n, c) => n + c.passes, 0), checked: counts.reduce((n, c) => n + c.checked, 0) });
  const p4Fraction = (t) => `${t.passes} of ${t.checked}`;
  const p4Evidence = (n, gain, before, after) => fmt(P4_WORDS.evidence.line, { n, verdict: gain ? P4_WORDS.evidence.gain : P4_WORDS.evidence.no_gain, before: p4Fraction(before), after: p4Fraction(after) });

  const p4Step = async (id) => (await get(`/api/state?step=${id}`)).json.step;
  const p4Submit = (step, data) => post('/api/step/submit', { step, data });
  async function p4Ok(label, step, data) {
    const r = await p4Submit(step, data);
    must(`${label}: accepted`, r.ok, `${r.status} ${r.code} ${r.message}`);
    return r;
  }
  function p4Refused(label, r, code, words) {
    check(`${label}: refused as ${code}${words ? ' with its plain message' : ''}`, r.status === 400 && r.code === code && (!words || r.message.includes(words)), `${r.status} ${r.code} ${r.message}`);
  }
  const p4Hashes = (dir, names) => Object.fromEntries(names.map((n) => [n, exists(path.join(dir, n)) ? sha256(path.join(dir, n)) : null]));
  const p4Part3Snapshot = (project) => p4Hashes(project, P4_PART3_FILES);

  // The part of the log that belongs to Iteration n, so an edit never touches another entry.
  function p4Section(text, n) {
    const start = text.search(new RegExp(`^## Iteration ${n}\\b`, 'm'));
    const next = start < 0 ? -1 : text.slice(start + 1).search(/^## Iteration \d+/m);
    return { start, end: next < 0 ? text.length : start + 1 + next };
  }
  function p4EditEntry(logFile, n, edit) {
    const text = readText(logFile);
    const { start, end } = p4Section(text, n);
    fs.writeFileSync(logFile, text.slice(0, start) + edit(text.slice(start, end)) + text.slice(end));
  }
  // The participant writes their own words and the Decision line into the entry the AI added to the log. The app never does.
  const p4ParticipantWrites = (logFile, n, decision, words) => p4EditEntry(logFile, n, (section) => section
    .replace(/^- Hypothesis:/m, `- Decision: ${decision}\n- Hypothesis:`)
    .replace(/^- Change:.*$/m, `- Change: ${words.change}`).replace(/^- Result:.*$/m, `- Result: ${words.result}`).replace(/^- Reasoning:.*$/m, `- Reasoning: ${words.reasoning}`));

  // One AI window for a Part 4 step (the page opens the first one by itself, "Open a new AI chat" opens the others), the
  // participant's paste of the step's line, the approvals the participant answers, and the file the stand-in wrote.
  async function p4Session(step, label, done, expectedLine, cwd, opts) {
    const run = await openPart3Ai(step, label);
    check(`${label}: the AI started in ${opts.folderName}`, path.resolve(run.launch.cwd).toLowerCase() === path.resolve(cwd).toLowerCase(), run.launch.cwd);
    if (opts.beforePaste) await opts.beforePaste(run);
    await expectPart3SendRefused(step, label);
    await pastePart3Line(step, label);
    await driveApprovals(run, done, 120000);
    if (opts.ends) check(`${label}: the AI process ended by itself`, await L.waitFor(async () => !L.pidAlive(run.pid), 20000, `process ${run.pid} gone`).then(() => true).catch(() => false));
    auditProcess(label, run, expectedLine, PASTE_AUDIT);
    return run;
  }

  // The five answers of a round through five AI windows, each holding only that round's prompt.md.
  async function p4Collect(ctx, step, n, kind) {
    const dir = ctx.attempt(n);
    const prompt = readText(path.join(dir, 'prompt.md'));
    const expected = p4Answers(kind);
    fs.appendFileSync(path.join(L.WORK, 'fake-cli-events.jsonl'), `${JSON.stringify({ event: 'part4-round', step, ts: Date.now() / 1000 })}\n`);
    for (const k of P4_RUNS) {
      const label = `${step} answer ${k}`;
      const out = path.join(dir, 'runs', `run-${k}.txt`);
      check(`${label}: not saved yet`, !hasText(out));
      await p4Session(step, label, async () => hasText(out) && (await cliStopped()), P4_MEASURE_LINE, ctx.blind, {
        folderName: 'the round\'s own folder', ends: true,
        beforePaste: async () => {
          check(`${label}: the folder held only this round's prompt.md, byte for byte`, JSON.stringify(fs.readdirSync(ctx.blind).sort()) === '["prompt.md"]' && lf(readText(path.join(ctx.blind, 'prompt.md'))) === lf(prompt), fs.readdirSync(ctx.blind).join(','));
        },
      });
      check(`${label}: the answer was filed from the AI's file as the next run`, lf(readText(out)) === lf(expected[k - 1]), out);
      const view = await p4Step(step);
      check(`${label}: the page lists ${k} of 5 saved`, view.data.runs.filter((r) => r.done).length === k && view.status === 'active', JSON.stringify(view.data.runs.map((r) => r.done)));
      if (k === 1) {
        p4Refused(`${step}: the hypothesis cannot change once an answer is saved`, await p4Submit(`hypothesis-${n}`, { action: 'save', text: 'Changed after the first answer.' }), 'hypothesis_locked');
        p4Refused(`${step}: the prompt cannot change once an answer is saved`, await p4Submit(`edit-${n}`, { action: 'save', prompt: `${prompt}\nChanged after the first answer.\n` }), 'edit_locked');
      }
    }
    const done = await p4Step(step);
    check(`${step}: all five answers are saved, the AI window is closed and nothing is scored yet`, (await getState()).terminal.running === false && done.data.all_saved === true && done.data.attempt.scored === false);
  }

  // The per-rule table the page shows after scoring: every rule before and after, with its NOT CHECKED state in each cell.
  function p4CheckTable(label, view, before, after) {
    const rules = view.data.attempt.compare.rules;
    const mine = rules.map((r) => [r.id, r.before && r.before.passes, r.after && r.after.passes]);
    const want = after.map((c) => [c.id, before.find((b) => b.id === c.id).passes, c.passes]);
    check(`${label}: every rule is listed with its count before and after, equal to an independent run`, JSON.stringify(mine) === JSON.stringify(want), `${JSON.stringify(mine)} vs ${JSON.stringify(want)}`);
    check(`${label}: every cell says whether it is NOT CHECKED, and whether coverage was lost`, rules.every((r) => r.before && r.after && typeof r.before.not_checked === 'boolean' && typeof r.after.not_checked === 'boolean' && typeof r.lost === 'boolean'), JSON.stringify(rules[0]));
    const tb = p4Total(before);
    const ta = p4Total(after);
    const cmp = view.data.attempt.compare;
    check(`${label}: the two overall scores equal the independent totals`, cmp.before.passes === tb.passes && cmp.before.total === tb.checked && cmp.after.passes === ta.passes && cmp.after.total === ta.checked, JSON.stringify([cmp.before, cmp.after]));
    const five = view.data.attempt.five_answers;
    const meets = ta.passes * 100 >= 95 * ta.checked;
    check(`${label}: the five-answer score is shown apart, and under 95% it comes with a next step`, five.passes === ta.passes && five.total === ta.checked && five.meets_target === meets && (meets ? five.next_step === null : typeof five.next_step === 'string' && five.next_step.length > 0), JSON.stringify(five));
  }

  // A round: hypothesis, one changed prompt, five fresh answers through the AI window, the score, keep or undo, and the log.
  // `o`: start (the kept version), startCounts (independent counts of it), kind (the answer set), makePrompt, hypothesis, choice,
  // and optionally stale (a run edited after scoring) and wrongCount (a log with one count too low first).
  async function p4Round(ctx, n, o) {
    const label = `part 4 round ${n}`;
    const dir = ctx.attempt(n);
    const parentPrompt = o.start === 0 ? ctx.startPrompt : path.join(ctx.attempt(o.start), 'prompt.md');
    const parentBytes = fs.readFileSync(parentPrompt);

    // The hypothesis is written first.
    const hyp = await p4Step(`hypothesis-${n}`);
    const ruleCounts = hyp.data.start_rules.map((r) => ({ id: r.id, passes: r.passes, checked: r.checked }));
    check(`${label}: the hypothesis step shows every rule of the starting version (kept ${o.start}) with its count`, hyp.data.start === o.start && JSON.stringify(ruleCounts) === JSON.stringify(o.startCounts), JSON.stringify(ruleCounts));
    p4Refused(`${label}: the edit step is locked until a hypothesis is saved`, await p4Submit(`edit-${n}`, { action: 'save', prompt: 'x' }), 'step_locked');
    p4Refused(`${label}: a blank hypothesis`, await p4Submit(`hypothesis-${n}`, { action: 'save', text: '   ' }), 'hypothesis_blank');
    await p4Ok(`${label}: hypothesis`, `hypothesis-${n}`, { action: 'save', text: `${o.hypothesis} (first draft)` });
    await p4Ok(`${label}: hypothesis again`, `hypothesis-${n}`, { action: 'save', text: o.hypothesis });
    check(`${label}: the hypothesis file holds the participant's words and the step is done`, readText(path.join(dir, 'hypothesis.md')).trim() === o.hypothesis && courseMap(await getState())[`hypothesis-${n}`] === 'done');
    check(`${label}: the round's own folder started from the kept version, byte for byte`, sha256(path.join(dir, 'prompt.md')) === digest(parentBytes));

    // One changed prompt.
    await p4Ok(`${label}: an unchanged prompt`, `edit-${n}`, { action: 'save', prompt: parentBytes.toString('utf8') });
    check(`${label}: an unchanged prompt does not finish the edit step`, courseMap(await getState())[`edit-${n}`] === 'active');
    const prompt = o.makePrompt(parentBytes.toString('utf8'));
    await p4Ok(`${label}: the changed prompt`, `edit-${n}`, { action: 'save', prompt });
    check(`${label}: the round's prompt is the participant's text and the edit step is done`, lf(readText(path.join(dir, 'prompt.md'))) === lf(prompt) && courseMap(await getState())[`edit-${n}`] === 'done');
    check(`${label}: the version it started from is untouched`, Buffer.compare(fs.readFileSync(parentPrompt), parentBytes) === 0);

    // Five fresh answers.
    const step = `measure-${n}`;
    const m0 = await p4Step(step);
    check(`${label}: the measure step shows the line to paste, with no answer saved`, m0.cli.line === P4_MEASURE_LINE && m0.data.runs.every((r) => !r.done) && m0.data.can_score === false, JSON.stringify(m0.cli));
    p4Refused(`${label}: scoring without five answers`, await p4Submit(step, { action: 'score' }), 'answers_missing');
    await p4Collect(ctx, step, n, o.kind);
    await p4Ok(`${label}: score`, step, { action: 'score' });
    const after = p4Counts(dir);
    const scored = await p4Step(step);
    check(`${label}: the measure step is done once scored, and no window is open`, scored.status === 'done' && (await getState()).terminal.running === false);
    p4CheckTable(label, scored, o.startCounts, after);
    check(`${label}: the model the AI windows used is recorded`, scored.data.attempt.model === L.MODEL, scored.data.attempt.model);

    // Deciding.
    const decideStep = `decide-${n}`;
    const d0 = await p4Step(decideStep);
    check(`${label}: no line to paste before the decision, and the decision is the participant's`, d0.cli === null && d0.data.decided === false && d0.data.can_decide === true, d0.data.decision);
    p4Refused(`${label}: opening the log window before a decision`, await post('/api/step/start', { step: decideStep }), 'not_decided');
    if (o.stale) {
      const run3 = path.join(dir, 'runs', 'run-3.txt');
      fs.writeFileSync(run3, Buffer.concat([fs.readFileSync(run3), Buffer.from('\n')]));
      check(`${label}: a run edited after scoring cannot be decided`, (await p4Step(decideStep)).data.can_decide === false);
      p4Refused(`${label}: deciding on stale results`, await p4Submit(decideStep, { action: 'decide', choice: 'keep' }), 'stale', 'answers');
      check(`${label}: nothing was decided`, (await p4Step(decideStep)).data.decision === 'pending');
      await p4Ok(`${label}: score again`, step, { action: 'score' });
      check(`${label}: scored again, the round can be decided and the counts are the same`, (await p4Step(decideStep)).data.can_decide === true && JSON.stringify(p4Counts(dir)) === JSON.stringify(after));
    }
    p4Refused(`${label}: a decision that is not keep or undo`, await p4Submit(decideStep, { action: 'decide', choice: 'maybe' }), 'bad_input');
    await p4Ok(`${label}: decide`, decideStep, { action: 'decide', choice: o.choice });
    const decided = await p4Step(decideStep);
    const before = p4Total(o.startCounts);
    const now = p4Total(after);
    const gain = o.choice === 'keep' && now.passes * before.checked > before.passes * now.checked;
    const evidence = decided.data.attempt.evidence;
    check(`${label}: the evidence line says ${gain ? 'a measured gain' : 'no measured gain'} and gives both scores`, evidence && evidence.gain === gain && evidence.text === p4Evidence(n, gain, before, now), JSON.stringify(evidence));
    check(`${label}: ${o.choice === 'keep' ? 'kept' : 'undone'} is recorded`, decided.data.decision === (o.choice === 'keep' ? 'kept' : 'undone'));
    const template = (L.PF ? P4_STEPS[decideStep].tracks.promptfoo : P4_STEPS[decideStep]).line_template;
    const line = fmt(template, { n, base: ctx.rel, log: ctx.logRel, model: L.MODEL });
    check(`${label}: the line to paste names this round's files, the model and the log`, decided.cli.line === line && decided.cli.can_auto_start === true, decided.cli.line);

    // The AI adds the numbers and the saved hypothesis to the log; the participant writes the rest.
    const logBefore = exists(ctx.log) ? readText(ctx.log) : '';
    const logHash = () => (exists(ctx.log) ? sha256(ctx.log) : null);
    if (o.wrongCount) fs.writeFileSync(MODE_FILE, 'wrong-count'); else fs.rmSync(MODE_FILE, { force: true });
    const was = logHash();
    await p4Session(decideStep, `${label} log${o.wrongCount ? ' (one count too low)' : ''}`, async (ev) => ev.filter((e) => e.event === 'approved').length >= 1 && logHash() !== was, line, ctx.project, { folderName: 'the project folder', ends: false });
    fs.rmSync(MODE_FILE, { force: true });
    const entry = readText(ctx.log);
    const mine = entry.slice(p4Section(entry, n).start);
    check(`${label}: the AI appended an Iteration ${n} entry after what the log already held`, entry.startsWith(logBefore.replace(/\s+$/, '')) && new RegExp(`^## Iteration ${n}: `, 'm').test(entry), entry.slice(-300));
    check(`${label}: the entry copies the saved hypothesis and leaves Change, Result and Reasoning empty`, new RegExp(`^- Hypothesis: ${escapeRe(o.hypothesis)}[ \\t]*\\r?$`, 'm').test(mine) && /^- Change:[ \t]*\r?$/m.test(mine) && /^- Result:[ \t]*\r?$/m.test(mine) && /^- Reasoning:[ \t]*\r?$/m.test(mine));
    const words = { change: `Round ${n}: the prompt was changed (harness).`, result: `Round ${n}: the counts are in the table (harness).`, reasoning: `Round ${n}: my reading of the counts (harness).` };
    p4ParticipantWrites(ctx.log, n, o.choice === 'keep' ? 'kept' : 'undone', words);

    if (o.wrongCount) {
      const target0 = after.find((c) => c.passes > 0);
      const hashBefore = logHash();
      const bad = await post('/api/step/check', { step: decideStep });
      const items = (await p4Step(decideStep)).last_check.items;
      const countItem = items.find((i) => i.label.includes('pass counts'));
      const message = `The log says ${target0.id} passed ${target0.passes - 1} of ${target0.checked} runs. The app counted ${target0.passes} of ${target0.checked}.`;
      check(`${label}: a log with one count too low fails the gate and names the rule and both numbers`, bad.ok && countItem && !countItem.ok && countItem.detail.includes(message), countItem ? countItem.detail : JSON.stringify(items));
      check(`${label}: the step stays active and the app did not edit the log`, courseMap(await getState())[decideStep] === 'active' && logHash() === hashBefore);
      // The participant corrects the number in their own log.
      p4EditEntry(ctx.log, n, (section) => section.split('\n').map((row) => {
        if (!row.startsWith(`| ${target0.id} `)) return row;
        const cells = row.split('|');
        cells[2] = ` ${target0.passes}/${target0.checked} `;
        cells[3] = ` ${Math.floor(target0.passes * 100 / target0.checked + 0.5)}% `;
        return cells.join('|');
      }).join('\n'));
    }
    const hashBeforeCheck = logHash();
    const good = await post('/api/step/check', { step: decideStep });
    const final = await p4Step(decideStep);
    check(`${label}: a log that matches the app's own count passes and the step is done`, good.ok && final.status === 'done' && final.last_check.ok === true, JSON.stringify(final.last_check));
    check(`${label}: the app left the log exactly as the AI and the participant wrote it`, logHash() === hashBeforeCheck);
    check(`${label}: the pass closed the AI window`, (await getState()).terminal.running === false);
    const recorded = readJson(ctx.progress).parts['part-4'].attempts.find((a) => a.n === n);
    check(`${label}: the manifest holds the decision, hashes and counts only`, recorded.decision === (o.choice === 'keep' ? 'kept' : 'undone') && Object.values(recorded.hashes).every((x) => /^[0-9a-f]{64}$/.test(x)) && after.every((c) => recorded.results[c.id].passes === c.passes && recorded.results[c.id].checked_runs === c.checked), JSON.stringify(recorded).slice(0, 300));
    return { after, hypothesis: o.hypothesis, words, prompt };
  }

  // The known-good step: the answer is chosen and saved before any score; a score under 95% gives a next step and no way to
  // loosen a rule; a passing answer finishes the step.
  async function p4KnownGood(ctx, label, answers) {
    const view = await p4Step('known-good');
    check(`${label}: the step shows the written requirements and no answer, score or result yet`, view.data.saved === false && view.data.result === null && view.data.answer === '' && view.data.rules.length > 0, JSON.stringify(view.data.result));
    const early = await p4Submit('known-good', { action: 'score' });
    check(`${label}: asking for a score before an answer is saved is refused`, early.status === 400 && ['known_good_needed', 'unknown_attempt'].includes(early.code), `${early.status} ${early.code}`);
    const afterEarly = await p4Step('known-good');
    check(`${label}: still no score, and the step is not done`, afterEarly.data.result === null && afterEarly.status === 'active');
    const dir = ctx.attempt(1);
    const independent = () => {
      const rows = Object.values(p4Independent(dir, ['known-good.txt'])['known-good.txt']);
      return { passes: rows.filter((v) => v === 'P').length, checked: rows.filter((v) => v !== 'NC').length };
    };
    if (answers.bad) {
      await p4Ok(`${label}: an answer under 95%`, 'known-good', { action: 'save', text: answers.bad });
      const low = await p4Step('known-good');
      const want = independent();
      check(`${label}: the score appears once the answer is saved, equal to an independent run`, low.data.saved === true && low.data.result && low.data.result.passes === want.passes && low.data.result.checked === want.checked, JSON.stringify(low.data.result));
      check(`${label}: an answer under 95% does not meet the mark, gives a next step and does not finish the step`, low.data.result.meets === false && /Do not loosen a rule/.test(low.data.result.next_step) && low.status === 'active', JSON.stringify(low.data.result));
      const loosen = await p4Submit('known-good', { action: 'loosen' });
      check(`${label}: there is no way to loosen a rule here`, loosen.status === 400 && loosen.code === 'bad_input', `${loosen.status} ${loosen.code}`);
      check(`${label}: the step offers no field to change a rule or a threshold`, !/"(threshold|loosen|edit_rules)"/.test((await get('/api/state?step=known-good')).text));
    }
    await p4Ok(`${label}: the known-good answer`, 'known-good', { action: 'save', text: answers.good });
    const good = await p4Step('known-good');
    const want = independent();
    check(`${label}: an answer that meets the mark is scored to the same counts as an independent run and finishes the step`, good.data.result.meets === true && good.data.result.passes === want.passes && good.data.result.checked === want.checked && good.status === 'done', JSON.stringify(good.data.result));
    check(`${label}: its score is kept apart from the five-answer score`, good.data.result.text.includes('known-good') && !('five_answers' in good.data.result), good.data.result.text);
    p4Refused(`${label}: a finished known-good step cannot be overwritten`, await p4Submit('known-good', { action: 'save', text: 'Another answer.' }), 'step_done');
    if (L.PF) check(`${label}: the attempt's own config holds the generated known-good test`, readText(path.join(dir, 'promptfooconfig.yaml')).includes('eval-coach: known-good test (generated)'));
  }

  // progress.json holds ids, hashes and counts, and none of the participant's words, the answers or the log's text.
  function p4ScanProgress(label, ctx, secrets) {
    const text = readText(ctx.progress);
    const lines = (value) => value.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length >= 25);
    const needles = secrets.flatMap((s) => (s.length >= 25 && !s.includes('\n') ? [s] : lines(s)));
    const found = needles.find((s) => text.includes(s) || text.includes(JSON.stringify(s).slice(1, -1)));
    check(`${label}: progress.json holds no prompt, answer, hypothesis or log text`, !found, found ? found.slice(0, 80) : '');
    const block = readJson(ctx.progress).parts['part-4'];
    check(`${label}: each saved attempt holds ids, hashes, counts and a decision only`, block.attempts.every((a) => Object.keys(a).sort().join() === 'decision,hashes,hypothesis_hash,known_good,log_entry,model,n,parent,results'), JSON.stringify(block.attempts.map((a) => Object.keys(a))));
    const clean = L.assertProgressClean();
    check(`${label}: no answer key or fixture text in progress.json`, !clean.keyHit && !clean.fixtureHit);
  }

  // The worked example: the exact edits and results stay out of every response until the prediction is placed right.
  async function p4WorkedExample() {
    const lessonId = 'p4-worked-example';
    const act = lessonDef(lessonId).activities.find((a) => a.id === 'wx-predict');
    const fragments = act.reveal.split('\n').map((l) => l.trim()).filter((l) => l.length >= 40);
    const leaked = (text) => fragments.filter((f) => text.includes(f) || text.includes(JSON.stringify(f).slice(1, -1)));
    check('worked example: the reveal has enough long lines to scan for', fragments.length >= 6, String(fragments.length));
    check('worked example: the leak scan finds the reveal when it is shown (plain or as JSON), and nothing otherwise', leaked(`before ${act.reveal} after`).length === fragments.length && leaked(JSON.stringify({ body: act.reveal })).length === fragments.length && leaked('nothing of it').length === 0);
    const wholePart = async () => (await get('/api/state?part=part-4')).text;
    let r = await viewLesson(lessonId);
    check('worked example: nothing of the edits or results is in the lesson before the prediction', leaked(r.text).length === 0 && leaked(await wholePart()).length === 0, leaked(r.text)[0]);
    // One placement wrong: the feedback is for that one item only.
    const almost = correctAnswer(act);
    const last = act.items[act.items.length - 1];
    almost.placements[last.id] = act.buckets.find((b) => b.id !== last.bucket).id;
    r = await answer(lessonId, 'wx-predict', almost);
    const view = actView(r.json.result.lesson, 'wx-predict');
    check('worked example: one wrong placement is not passed and shows feedback for that one item only', r.ok && r.json.result.passed === false && view.result.right === act.items.length - 1 && view.result.feedback.length === 1 && view.result.feedback[0].item === last.id, JSON.stringify(view.result));
    check('worked example: still no edits or results anywhere', leaked(r.text).length === 0 && leaked((await viewLesson(lessonId)).text).length === 0 && leaked(await wholePart()).length === 0);
    const wrong = await answer(lessonId, 'wx-predict', wrongAnswer(act));
    check('worked example: an all-wrong prediction still reveals nothing', wrong.ok && wrong.json.result.passed === false && leaked(wrong.text).length === 0);
    r = await answer(lessonId, 'wx-predict', correctAnswer(act));
    const passed = r.json.result.lesson;
    check('worked example: the passing response returns the edits and results, on the activity and in the lesson text', r.ok && r.json.result.passed === true && leaked(passed.body).length === fragments.length && actView(passed, 'wx-predict').reveal === act.reveal, String(leaked(passed.body).length));
    check('worked example: the reveal is not saved in progress.json', leaked(readText(PROGRESS)).length === 0);
    await solveActivity(lessonId, lessonDef(lessonId).activities.find((a) => a.id === 'wx-reflect'));
  }

  // A lesson with no AI exercise can be finished at once.
  async function completeSimply(lessonId) {
    const r = await post('/api/lesson/complete', { lesson: lessonId });
    must(`${lessonId}: completed`, r.ok, `${r.status} ${r.code} ${r.message}`);
  }

  // ---- the participant's own baseline ------------------------------------------------------------------------------
  async function stagePart4() {
    requireStandIn();
    const progress = exists(PROGRESS) ? readJson(PROGRESS) : null;
    const part2 = progress && progress.parts && progress.parts['part-2'];
    if (!state.port || !L.pidAlive(state.serverPid) || !progress || !progress.done.includes('baseline') || !part2 || part2.done.length < 4) {
      const error = new Error('part4 needs the earlier stages first, with the app running: mission, setup, hook, several-runs, inputs, generate, rules, restart, build, trust, fixtures, readback, predict, key, surprise, run, fix, baseline-why, baseline, part1 and part2 (node e2e-work\\harness\\run-all.js --fresh runs them all, and part4 follows part2)');
      error.stack = undefined;
      throw error;
    }
    h.setActivePart('part-4');
    try {
      await part4Flow();
    } finally {
      h.setActivePart(null);
    }
    endStage('part4');
  }

  async function part4Flow() {
    const ctx = p4Ctx(PROJECT, HOME, false);
    const part3Before = p4Part3Snapshot(PROJECT);
    const logZero = lf(readText(LOG_FILE)).replace(/\s+$/, '');
    const secrets = [];
    let s = await getState();
    check('part 4: the course lists its sixteen items in order', JSON.stringify(s.course.map((c) => c.id)) === JSON.stringify(PART4_ORDER), JSON.stringify(s.course.map((c) => c.id)));
    check('part 4: round 3 is listed apart from the course, optional and shut', JSON.stringify(s.optional_steps.map((x) => [x.id, x.status])) === JSON.stringify([['hypothesis-3', 'locked'], ['edit-3', 'locked'], ['measure-3', 'locked'], ['decide-3', 'locked']]), JSON.stringify(s.optional_steps));
    const row = (await get('/api/state')).json.series.parts.find((p) => p.id === 'part-4');
    check('part 4: the Series map row is a course that has not started', row.kind === 'course' && row.state === 'not_started' && row.total === 16 && row.done === 0, JSON.stringify(row));
    check('part 4: nothing of Part 4 is in progress.json or in the project folder before the first choice', readJson(PROGRESS).parts['part-4'] === undefined && !exists(path.join(PROJECT, 'part-4')));
    // Parts 1 to 3 are done, so Part 4 is open even with demo access off.
    must('part 4: demo access turned off', (await post('/api/demo/lock', {})).ok);
    const open = await viewLesson('p4-mission');
    check('part 4: with Parts 1 to 3 done, Part 4 opens without demo access', open.ok, `${open.status} ${open.code}`);
    await L.unlockDemo(state.port, state.token);
    await enterStage('p4-mission');
    await expectStepLocked('starting-point', 'p4-mission', 'part 4 starting point before the mission');
    const early = await get('/api/state?step=hypothesis-1');
    check('part 4: a step further on is refused with the lock message and returns nothing of it', early.status === 400 && early.code === 'step_locked' && early.message === LOCK_MESSAGE, `${early.status} ${early.code}`);
    check('part 4: the mission is one page with no questions', lessonOf(await viewLesson('p4-mission')).activities.length === 0);
    await completeLesson('p4-mission');

    // The starting point: nothing preselected, and the participant's own Part 3 baseline chosen.
    await expectStepActive('starting-point');
    const start = await p4Step('starting-point');
    check('part 4: nothing is preselected or fixed, and there is no little-to-improve note at 25 of 30', start.data.chosen === null && start.data.fixed === false && start.data.little_gap === null, JSON.stringify(start.data));
    const own = start.data.choices.find((c) => c.id === 'own');
    const practice = start.data.choices.find((c) => c.id === 'practice');
    check('part 4: the participant\'s own baseline is available, and the Practice baseline is labelled practice only', own.available === true && own.reason === null && practice.available === true && /practice only/i.test(practice.note), JSON.stringify(start.data.choices));
    check('part 4: looking at the choices created nothing in the project', !exists(path.join(PROJECT, 'part-4')));
    p4Refused('part 4: a choice that is not offered', await p4Submit('starting-point', { action: 'choose', choice: 'maybe' }), 'bad_input');
    await p4Ok('part 4: own baseline', 'starting-point', { action: 'choose', choice: 'own' });
    check('part 4: the step is done and the choice is saved as "own"', courseMap(await getState())['starting-point'] === 'done' && readJson(PROGRESS).parts['part-4'].start === 'own');
    check('part 4: choosing the own baseline created and changed no file of Part 3', JSON.stringify(p4Part3Snapshot(PROJECT)) === JSON.stringify(part3Before) && !exists(path.join(PROJECT, 'part-4', 'attempts')) && !exists(path.join(PROJECT, 'part-4', 'practice')));

    // The checker, checked on a known-good answer chosen before its score is seen.
    await solveAll('p4-checker-first');
    await completeLesson('p4-checker-first');
    await expectStepActive('known-good');
    const badAnswer = readText(path.join(NORTHWIND_SAMPLES, 'fixture-bad.txt'));
    const goodAnswer = readText(path.join(NORTHWIND_SAMPLES, 'sample-run-1.txt'));
    secrets.push(badAnswer, goodAnswer);
    await p4KnownGood(ctx, 'part 4 known-good', { bad: badAnswer, good: goodAnswer });
    check('part 4: the known-good check changed no file of Part 3 (on the promptfoo track the original config has no known-good test)', JSON.stringify(p4Part3Snapshot(PROJECT)) === JSON.stringify(part3Before) && !readText(path.join(PROJECT, P4_CHECKER)).includes('known-good'));
    p4Refused('part 4: the starting point is fixed once round 1 exists', await p4Submit('starting-point', { action: 'choose', choice: 'practice' }), 'start_fixed', 'fixed');
    check('part 4: attempt 1 started from Part 3\'s own prompt, byte for byte', sha256(path.join(ctx.attempt(1), 'prompt.md')) === part3Before['prompt-v0.md']);

    // The lessons before round 1, and the worked example's early reveal.
    await solveAll('p4-one-change');
    await completeLesson('p4-one-change');
    await p4WorkedExample();
    await completeLesson('p4-worked-example');

    // Round 1: a measured gain, kept. It also covers an edited run, and a log with one count too low.
    const startCounts = countsOf(L.independentRunIn(PROJECT, RUN_FILES));
    const baseTotal = p4Total(startCounts);
    const hypothesis1 = 'Factual tone (C5) should rise, because a concrete tone line names what to avoid. The other rules should stay the same.';
    const round1 = await p4Round(ctx, 1, {
      start: 0, startCounts, kind: 'gain', choice: 'keep', hypothesis: hypothesis1, stale: true, wrongCount: true,
      makePrompt: (text) => `${text.replace(/\s+$/, '')}\n\n- Tone: factual. Do not use praise or enthusiasm words, and do not use exclamation marks.\n<!-- stand-in answers: gain -->\n`,
    });
    secrets.push(hypothesis1, round1.prompt, ...Object.values(round1.words), ...p4Answers('gain'));
    const afterOne = round1.after;
    check('part 4 round 1: the starting score was 25 of 30 and the five answers scored 26', baseTotal.passes === 25 && baseTotal.checked === 30 && p4Total(afterOne).passes === 26, JSON.stringify([baseTotal, p4Total(afterOne)]));
    check('part 4 round 1: Part 3\'s own files are as they were, and the log still starts with Iteration 0 as it was', JSON.stringify(p4Part3Snapshot(PROJECT)) === JSON.stringify(part3Before) && lf(readText(LOG_FILE)).startsWith(logZero));

    await solveAll('p4-read-results');
    await completeLesson('p4-read-results');

    // Round 2: from the kept version. The edit changes nothing the rules measure, so it is undone.
    const hypothesis2 = 'Nothing should change, because the new line says what the old one says.';
    const round2 = await p4Round(ctx, 2, {
      start: 1, startCounts: afterOne, kind: 'flat', choice: 'undo', hypothesis: hypothesis2,
      makePrompt: (text) => text.replace('stand-in answers: gain', 'stand-in answers: flat').replace('- Tone: factual.', '- Tone: factual, plainly.'),
    });
    secrets.push(hypothesis2, round2.prompt, ...Object.values(round2.words), ...p4Answers('flat'));
    const flat = (await p4Step('decide-2')).data.attempt;
    check('part 4 round 2: a flat attempt is never called a gain, and its rule set is unchanged', flat.evidence.gain === false && flat.evidence.verdict === P4_WORDS.evidence.no_gain && flat.coverage.changed === false && flat.decision === 'undone', JSON.stringify(flat.evidence));
    check('part 4 round 2: the flat answers scored the same as round 1', JSON.stringify(round2.after) === JSON.stringify(afterOne));

    await solveAll('p4-keep-and-log');
    await completeLesson('p4-keep-and-log');

    // The whole Part, finished below the 95% coaching target.
    s = await getState();
    const seriesRow = (await get('/api/state')).json.series.parts.find((p) => p.id === 'part-4');
    check('part 4: every item is done after two documented rounds and nothing is left to do', s.course.every((c) => c.status === 'done') && s.current_item === null, JSON.stringify(s.current_item));
    check('part 4: the Series map shows it done, 16 of 16', seriesRow.state === 'done' && seriesRow.done === 16, JSON.stringify(seriesRow));
    const last = (await p4Step('measure-2')).data.attempt;
    const known = (await p4Step('known-good')).data.result;
    check('part 4: it finished below the 95% target, with a suggested next step and no gate', last.five_answers.meets_target === false && last.five_answers.next_step && /target is 95%/.test(last.five_answers.text), JSON.stringify(last.five_answers));
    check('part 4: the known-good result is shown apart from the five-answer score', known.meets === true && known.text !== last.five_answers.text && known.text.includes('known-good') && !last.five_answers.text.includes('known-good'), known.text);

    // Round 3 (optional): from the kept version, with a changed rule set that is never counted as a gain.
    await part4OptionalRound(ctx, afterOne, round1.prompt, round2.prompt);

    // What the whole run left behind.
    check('part 4: Part 3\'s files are byte for byte what they were at the start, and the log still starts with Iteration 0 as it was', JSON.stringify(p4Part3Snapshot(PROJECT)) === JSON.stringify(part3Before) && lf(readText(LOG_FILE)).startsWith(logZero));
    const finalLog = lf(readText(LOG_FILE));
    check('part 4: the log holds both rounds, kept and undone, as the participant finished them', /^## Iteration 1: /m.test(finalLog) && /^## Iteration 2: /m.test(finalLog) && /^- Decision: kept$/m.test(finalLog) && /^- Decision: undone$/m.test(finalLog));
    p4ScanProgress('part 4', ctx, secrets);
    check('part 4: no violations (no flags, only the participant\'s paste, no answered prompts)', state.violations.length === 0, state.violations.join(' | '));
  }

  // Round 3, the optional one: it starts from the kept version (round 1, not the undone round 2), the participant narrows the
  // rule set in the round's own checker, and the app flags the changed coverage and never counts it as a gain.
  async function part4OptionalRound(ctx, startCounts, round1Prompt, round2Prompt) {
    const label = 'part 4 round 3';
    const dir = ctx.attempt(3);
    const s = await getState();
    check(`${label}: it is offered after the course, as optional`, s.optional_steps[0].id === 'hypothesis-3' && s.optional_steps[0].status === 'optional' && (await p4Step('hypothesis-3')).optional === true, JSON.stringify(s.optional_steps));
    check(`${label}: the undone second edit differs from the kept first one`, lf(round1Prompt) !== lf(round2Prompt));
    await p4Ok(`${label}: hypothesis`, 'hypothesis-3', { action: 'save', text: 'Dropping the notes rule should leave the rest the same.' });
    check(`${label}: it starts from the kept version, round 1, and not from the undone round 2`, lf(readText(path.join(dir, 'prompt.md'))) === lf(round1Prompt) && lf(readText(path.join(dir, 'prompt.md'))) !== lf(round2Prompt) && (await p4Step('hypothesis-3')).data.start === 1);
    if (!L.PF) check(`${label}: its own copy of the checker is the kept version's`, sha256(path.join(dir, P4_CHECKER)) === sha256(path.join(ctx.attempt(1), P4_CHECKER)));
    await p4Ok(`${label}: edit`, 'edit-3', { action: 'save', prompt: `${round1Prompt.replace(/\s+$/, '')}\n- Keep it short.\n` });
    // The participant drops the "Uses the rough notes" rule from the round's own checker and brings five answers.
    const checkerFile = path.join(dir, P4_CHECKER);
    const text = readText(checkerFile);
    const narrowed = L.PF ? text.replace(/ {4}# C6:[\s\S]*?(?= {4}# Empty outputs)/, '') : text.replace(/^[ \t]*\("C6", .*\),\r?\n/m, '');
    check(`${label}: the participant's edit really removed the rule`, narrowed !== text);
    fs.writeFileSync(checkerFile, narrowed);
    p4Answers('gain').forEach((answerText, i) => fs.writeFileSync(path.join(dir, 'runs', `run-${i + 1}.txt`), answerText));
    await p4Ok(`${label}: score`, 'measure-3', { action: 'score' });
    const after = p4Counts(dir, ['C1', 'C2', 'C3', 'C4', 'C5']);
    const attempt = (await p4Step('measure-3')).data.attempt;
    check(`${label}: the counts equal an independent run on the rules that remain`, JSON.stringify(attempt.compare.rules.filter((r) => r.after).map((r) => [r.id, r.after.passes])) === JSON.stringify(after.map((c) => [c.id, c.passes])), JSON.stringify(attempt.compare.rules));
    check(`${label}: the rule that is gone is flagged as changed coverage, in words`, attempt.coverage.changed === true && JSON.stringify(attempt.coverage.removed) === '["C6"]' && /no longer reports C6/.test(attempt.coverage.text), JSON.stringify(attempt.coverage));
    const kept = p4Total(startCounts);
    const now = p4Total(after);
    check(`${label}: the rate rose, so a gain would have been counted if the coverage had not changed`, now.passes * kept.checked > kept.passes * now.checked, `${now.passes}/${now.checked} vs ${kept.passes}/${kept.checked}`);
    const d = await p4Step('decide-3');
    check(`${label}: the original five answers must be run again with the corrected checker before any decision`, d.data.rerun_needed === true && d.data.can_decide === false, JSON.stringify([d.data.rerun_needed, d.data.can_decide]));
    p4Refused(`${label}: deciding before that rerun`, await p4Submit('decide-3', { action: 'decide', choice: 'keep' }), 'rerun_needed');
    await p4Ok(`${label}: rerun`, 'decide-3', { action: 'rerun' });
    check(`${label}: the rerun recorded a corrected Iteration 0`, (await p4Step('decide-3')).data.rerun_needed === false && readJson(ctx.progress).parts['part-4'].iteration_0 !== null);
    await p4Ok(`${label}: keep`, 'decide-3', { action: 'decide', choice: 'keep' });
    const decided = (await p4Step('decide-3')).data.attempt;
    check(`${label}: kept, but never counted as a gain, and the page says the set of rules changed`, decided.decision === 'kept' && decided.evidence.gain === false && decided.evidence.text.includes(P4_WORDS.evidence.coverage_not_gain) && decided.evidence.text.includes(P4_WORDS.evidence.no_gain), JSON.stringify(decided.evidence));
    const row = (await get('/api/state')).json.series.parts.find((p) => p.id === 'part-4');
    check(`${label}: it never counts toward Done, so the Part still shows 16 of 16`, row.state === 'done' && row.done === 16 && (await getState()).course.length === 16, JSON.stringify(row));
  }

  // ---- the catch-up path -------------------------------------------------------------------------------------------
  // A second app whose Part 3 was never done: the participant's own baseline is refused with a reason, the Practice baseline is
  // copied in without touching anything of theirs, and a Practice round is documented in the Practice log only.
  function linkPf(home) {
    const spike = path.join(L.ROOT, 'spikes', 'phase0-preflight');
    fs.mkdirSync(path.join(home, 'runtime'), { recursive: true });
    for (const [link, target] of [[path.join(home, 'runtime', 'node'), path.join(spike, 'runtime', 'node-v26.13.0-win-x64')], [path.join(home, 'npm-cache'), path.join(spike, 'npm-cache')]]) {
      if (!exists(target)) throw new Error(`the spike's private runtime is missing: ${target}`);
      if (!exists(link)) fs.symlinkSync(target, link, 'junction');
    }
  }
  // A junction is removed on its own, never recursively, so the spike's files are never touched.
  function unlinkPf(home) {
    for (const link of [path.join(home, 'runtime', 'node'), path.join(home, 'npm-cache')]) {
      let st = null;
      try { st = fs.lstatSync(link); } catch { continue; }
      if (st.isSymbolicLink()) fs.rmdirSync(link);
    }
  }

  async function stagePart4Practice() {
    requireStandIn();
    const home = path.join(PART4_TMP, 'home');
    const project = path.join(PART4_TMP, 'project');
    unlinkPf(home);
    fs.rmSync(PART4_TMP, { recursive: true, force: true });
    fs.mkdirSync(home, { recursive: true });
    fs.copyFileSync(path.join(HOME, 'preflight.json'), path.join(home, 'preflight.json'));
    if (L.PF) linkPf(home);
    const app = await spawnApp(home, { keepLocked: true, log: 'server-part4.out' });
    h.setTarget({ port: app.port, token: app.token });
    h.setActivePart('part-4');
    try {
      await part4PracticeFlow(app, home, project);
    } finally {
      h.setActivePart(null);
      h.setTarget(null);
      try { execFileSync('taskkill', ['/PID', String(app.pid), '/T', '/F'], { stdio: 'ignore' }); } catch { /* gone */ }
      await sleep(500);
      unlinkPf(home);
      fs.rmSync(PART4_TMP, { recursive: true, force: true });
      try { fs.unlinkSync(path.join(L.WORK, 'server-part4.out')); } catch { /* absent */ }
    }
    check('part 4 practice: the temp folder is removed', !exists(PART4_TMP));
    endStage('part4-practice');
  }

  async function part4PracticeFlow(app, home, project) {
    const ctx = p4Ctx(project, home, true);
    const locked = await viewLesson('p4-mission');
    check('part 4 practice: before demo access, with Parts 1 to 3 untouched, Part 4 is refused with the lock message', locked.status === 400 && locked.code === 'lesson_locked' && locked.message === LOCK_MESSAGE, `${locked.status} ${locked.code}`);
    await L.unlockDemo(app.port, app.token);
    const setup = await post('/api/setup', { project_path: project, cli_command: L.CLI_COMMAND, starter: 'northwind' });
    must('part 4 practice: the second app set up its project', setup.ok, setup.text.slice(0, 200));
    // The participant's own files, one of them a log that nothing could read as a log: Practice must never read or change them.
    fs.writeFileSync(path.join(project, 'iteration-log.md'), 'My own notes, not a log. Nothing here starts with an iteration heading.\n');
    const ownFiles = {};
    const walk = (dir, rel) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        if (rel === '' && ['.learning', 'part-4'].includes(e.name)) continue;
        const r = rel ? `${rel}/${e.name}` : e.name;
        if (e.isDirectory()) walk(path.join(dir, e.name), r); else ownFiles[r] = sha256(path.join(dir, e.name));
      }
    };
    walk(project, '');
    check('part 4 practice: the participant\'s own project holds files to protect', Object.keys(ownFiles).length >= 3 && 'iteration-log.md' in ownFiles, Object.keys(ownFiles).join(','));
    const snapshotOwn = () => Object.fromEntries(Object.keys(ownFiles).map((rel) => [rel, exists(path.join(project, rel)) ? sha256(path.join(project, rel)) : null]));

    await completeSimply('p4-mission');
    await expectStepActive('starting-point');
    const words = P4_STEPS['starting-point'].messages;
    const own = (await p4Step('starting-point')).data;
    check('part 4 practice: Part 3 unfinished makes the own baseline unavailable, with its reason, and nothing is chosen', own.choices.find((c) => c.id === 'own').available === false && own.choices.find((c) => c.id === 'own').reason === words.own_unfinished && own.chosen === null, JSON.stringify(own.choices));
    p4Refused('part 4 practice: choosing the own baseline', await p4Submit('starting-point', { action: 'choose', choice: 'own' }), 'start_unavailable', words.own_unfinished);
    const skip = await post('/api/part/skip', { part: 'part-3', confirm: true });
    must('part 4 practice: Part 3 was skipped on purpose', skip.ok, skip.text.slice(0, 200));
    const skipped = (await p4Step('starting-point')).data.choices.find((c) => c.id === 'own');
    check('part 4 practice: Part 3 skipped gives its own reason', skipped.available === false && skipped.reason === words.own_skipped, JSON.stringify(skipped));
    p4Refused('part 4 practice: the own baseline after skipping Part 3', await p4Submit('starting-point', { action: 'choose', choice: 'own' }), 'start_unavailable', words.own_skipped);
    check('part 4 practice: those refusals created and chose nothing', !exists(path.join(project, 'part-4')) && !(readJson(ctx.progress).parts['part-4'] || {}).start);

    // A Practice file the participant already has is never overwritten.
    fs.mkdirSync(ctx.base, { recursive: true });
    const earlier = '# My Practice notes\n\nSomething I wrote before choosing Practice.\n';
    fs.writeFileSync(ctx.log, earlier);
    await p4Ok('part 4 practice: Practice baseline', 'starting-point', { action: 'choose', choice: 'practice' });
    const kitChecker = path.join(KIT, 'part4', 'practice', P4_CHECKER);
    check('part 4 practice: the choice is saved as practice and the step is done', readJson(ctx.progress).parts['part-4'].start === 'practice' && courseMap(await getState())['starting-point'] === 'done');
    check('part 4 practice: the bundled files were copied into part-4\\practice, the five answers and the checker byte for byte', P4_RUNS.every((k) => sha256(path.join(ctx.base, 'runs', `run-${k}.txt`)) === sha256(path.join(KIT, 'northwind', `sample-run-${k}.txt`))) && hasText(path.join(ctx.base, 'prompt-v0.md')) && hasText(path.join(ctx.base, 'test-cases.md')) && sha256(path.join(ctx.base, P4_CHECKER)) === sha256(kitChecker));
    check('part 4 practice: a Practice file that already existed was not overwritten', readText(ctx.log) === earlier);
    const results = readJson(path.join(ctx.base, 'results.json'));
    check('part 4 practice: Iteration 0 was scored once, 25 of 30', results.overall.passes === 25 && results.overall.total === 30, JSON.stringify(results.overall));
    check('part 4 practice: none of the participant\'s own files was changed', JSON.stringify(snapshotOwn()) === JSON.stringify(ownFiles));

    await completeSimply('p4-checker-first');
    await p4KnownGood(ctx, 'part 4 practice known-good', { good: readText(path.join(NORTHWIND_SAMPLES, 'sample-run-1.txt')) });
    check('part 4 practice: attempts are kept under part-4\\practice\\attempts and nowhere else', exists(ctx.attempt(1)) && !exists(path.join(project, 'part-4', 'attempts')));
    p4Refused('part 4 practice: the choice is fixed once round 1 exists', await p4Submit('starting-point', { action: 'choose', choice: 'own' }), 'start_fixed');
    await completeSimply('p4-one-change');
    await completeSimply('p4-worked-example');

    // A Practice round that gets worse, is undone and is documented in the Practice log only.
    const practiceCounts = p4Counts(ctx.base);
    check('part 4 practice: the starting score is the Practice 25 of 30', p4Total(practiceCounts).passes === 25 && p4Total(practiceCounts).checked === 30, JSON.stringify(p4Total(practiceCounts)));
    const hypothesis = 'A friendlier tone should make the update warmer and change nothing else.';
    const round = await p4Round(ctx, 1, {
      start: 0, startCounts: practiceCounts, kind: 'worse', choice: 'undo', hypothesis,
      makePrompt: (text) => `${text.replace(/\s+$/, '')}\n\n- Tone: friendly and upbeat.\n<!-- stand-in answers: worse -->\n`,
    });
    const logText = readText(ctx.log);
    check('part 4 practice: the Practice log keeps what was there and now holds the round, undone, in the participant\'s words', lf(logText).startsWith(lf(earlier).replace(/\s+$/, '')) && /^## Iteration 1: /m.test(logText) && /^- Decision: undone$/m.test(lf(logText)) && logText.includes(round.words.change));
    check('part 4 practice: the participant\'s own files and log were never read or changed (the gate passed beside a log that cannot be parsed)', JSON.stringify(snapshotOwn()) === JSON.stringify(ownFiles) && readText(path.join(project, 'iteration-log.md')).startsWith('My own notes'));
    const worse = p4Total(round.after);
    check('part 4 practice: the worse round scored under the start and is shown without gain wording', worse.passes < 25 && (await p4Step('decide-1')).data.attempt.evidence.gain === false, JSON.stringify(worse));
    await completeSimply('p4-read-results');
    check('part 4 practice: the undone round left the starting version as it was', (await p4Step('hypothesis-2')).data.start === 0);
    p4ScanProgress('part 4 practice', ctx, [hypothesis, round.prompt, ...Object.values(round.words), ...p4Answers('worse'), earlier.trim()]);
    check('part 4 practice: no violations', state.violations.length === 0, state.violations.join(' | '));
  }

  return { part4: stagePart4, 'part4-practice': stagePart4Practice };
};
