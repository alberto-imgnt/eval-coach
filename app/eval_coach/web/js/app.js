// Entry point: state, drafts, saving, rendering and step actions.

import { ApiError, apiGet, apiGetState, apiPost, readTokenOnce } from './api.js';
import { openAiWindowLesson } from './ai-window.js';
import { celebrate, initChrome, resetDisplayChoices, syncCourseNav, updateReadProgress } from './chrome.js';
import { confirmDialog } from './dialog.js';
import { morph } from './dom.js';
import { hasLessons, lessonCliActivity, renderLesson, renderLessonTermHead, renderReviewBanner } from './lessons.js';
import { openFileViewer, openGlossary, openReview } from './overlays.js';
import { PANELS } from './panels.js';
import { unsavedCriteria } from './criteria-steps.js';
import { unsavedTexts } from './part-steps.js';
import { setMapText } from './markdown.js';
import { aiTesting, firstWizardItem, nextWizardPage, renderPreflightTermFoot, renderPreflightTermHead, renderWizard, wizardIndex, wizardPageId, wizardPages, wizardUsesTerminal } from './preflight.js';
import { renderSeries } from './series.js';
import { renderSettings, renderSetupBanner, resetDialogBody, restartDialogBody } from './settings.js';
import { createTerminal } from './terminal.js';
import { renderFinished, renderNotices, renderStep, renderTermFoot, renderTermHead, renderTopbar } from './views.js';

const $ = (id) => document.getElementById(id);
const SAVE_DELAY_MS = 600;
const TEST_POLL_MS = 3000; // how often the working test page quietly re-reads the test folder after Send
const DEFAULT_PART = 'part-3'; // the Part the server describes when a request names none
const DEFAULT_OPEN_PARTS = ['part-1', 'part-2', 'part-3']; // the Parts with content start expanded on the Series map

const app = {
  state: null,
  part: 'part-3', // the Part the page is in; the server describes it, and its words and course list replace Part 3's
  viewStep: null, // null means "follow the current step"
  viewLesson: null, // a lesson the participant opened by hand; null follows the current item
  screen: 'series', // 'series' (the Series map, the home screen), 'settings' or 'setup' while one of those is open; null shows the course
  seriesOpen: new Set(DEFAULT_OPEN_PARTS), // Part rows expanded on the Series map; in memory only
  settingsFrom: null, // the screen Settings was opened from ('series' or null for the course), to return to on close
  setupFrom: null, // the screen the setup wizard was opened from ('settings', 'series' or null for the course), to return to on close
  wizardItem: null, // the setup wizard's current page (a preflight item id); in memory only
  setupDismissed: false, // the participant has moved on from the first-run setup wizard without skipping it
  wizardFinishing: false, // first-run setup has passed, but the wizard stays open on its last page (Your AI window)
  summaryStarted: false, // the Checking your computer page started its checks on this visit
  aiTestWatch: false, // after "Use this AI": the wizard moves on by itself when the quiet test ends
  summaryStarting: false,
  testPoll: null, // the timer that quietly re-reads the working test folder after Send
  testPolling: false,
  lessons: new Map(), // latest view of each lesson, with its answers removed by the server
  lessonGen: 0,
  local: new Map(), // short-lived results that are not saved (rule lab runs)
  reviewNote: false,
  referenceData: null,
  lastRenderedLesson: null,
  drafts: new Map(),
  busy: new Set(),
  notices: [],
  focusHeading: false,
  quitting: false,
  terminal: null,
  stepCache: new Map(), // latest detail per step, used to build save payloads
  lastRenderedStep: null,
  autoStartAsked: null, // the step the page already asked the server to open an AI window for, in this visit
};

let noticeId = 0;

function reportError(err) {
  if (app.quitting) return;
  let message;
  if (err instanceof ApiError) message = err.message;
  else if (typeof err === 'string') message = err;
  else message = 'Something went wrong on this page. Try again.';
  if (app.notices.some((n) => n.message === message)) return;
  noticeId += 1;
  app.notices.push({ id: noticeId, message });
  scheduleRender();
}

// ---- saving -------------------------------------------------------------

const saver = {
  timers: new Map(),
  status: new Map(),
  inflight: new Set(),

  schedule(stepId) {
    clearTimeout(this.timers.get(stepId));
    this.timers.set(stepId, setTimeout(() => this.fire(stepId), SAVE_DELAY_MS));
    this.status.set(stepId, 'pending');
  },

  flushStep(stepId) {
    if (this.timers.has(stepId)) {
      clearTimeout(this.timers.get(stepId));
      this.fire(stepId);
    }
  },

  fire(stepId) {
    this.timers.delete(stepId);
    const promise = this.send(stepId).finally(() => this.inflight.delete(promise));
    this.inflight.add(promise);
    return promise;
  },

  async send(stepId) {
    const step = app.stepCache.get(stepId);
    if (!step) return;
    const { data, keys } = collectStep(step);
    if (keys.length === 0) {
      this.status.delete(stepId);
      scheduleRender();
      return;
    }
    const sent = keys.map((k) => [k, app.drafts.get(k)]);
    this.status.set(stepId, 'saving');
    scheduleRender();
    try {
      await mutate('/api/step/submit', { step: stepId, data });
      for (const [k, v] of sent) if (app.drafts.get(k) === v) app.drafts.delete(k);
      if (!this.timers.has(stepId)) this.status.set(stepId, 'saved');
    } catch (err) {
      this.status.set(stepId, 'error');
      reportError(err);
    }
    scheduleRender();
  },

  async flush() {
    for (const stepId of Array.from(this.timers.keys())) this.flushStep(stepId);
    while (this.inflight.size) {
      // eslint-disable-next-line no-await-in-loop
      await Promise.allSettled(Array.from(this.inflight));
    }
  },
};

function collectStep(step) {
  const panel = PANELS[step.id];
  const collected = panel && panel.collect ? panel.collect(step, app.drafts) : { data: {}, keys: [] };
  const data = { ...collected.data };
  const keys = [...collected.keys];
  if (step.checklist && step.checklist.some((item) => app.drafts.has(`checklist.${step.id}.${item.id}`))) {
    data.checklist = {};
    for (const item of step.checklist) {
      const k = `checklist.${step.id}.${item.id}`;
      data.checklist[item.id] = app.drafts.has(k) ? app.drafts.get(k) : item.checked;
      if (app.drafts.has(k)) keys.push(k);
    }
  }
  return { data, keys };
}

// ---- server state -------------------------------------------------------

let mutationChain = Promise.resolve();
let postGeneration = 0;
let fetching = false;
let fetchAgain = false;

// Which screen the main area shows: 'settings', 'wizard' (setup), 'series' (the Series map), or the course
// ('lesson' or 'course' for a step).
function currentView(state) {
  if (!state) return null;
  if (app.screen === 'settings') return 'settings';
  if (app.screen === 'setup') return 'wizard';
  const pf = state.preflight;
  // First run: setup comes first, until it passes, is skipped, or the participant moves on by choice.
  if (!pf.passed && !pf.skipped && !app.setupDismissed) return 'wizard';
  if (app.wizardFinishing) return 'wizard';
  if (app.screen === 'series' && state.series) return 'series';
  return viewedLessonIdInCourse(state) ? 'lesson' : 'course';
}

function viewedLessonIdInCourse(state) {
  if (!hasLessons(state)) return null;
  if (app.viewLesson) return app.viewLesson;
  if (app.viewStep) return null;
  const item = state.current_item;
  if (item && item.kind === 'lesson') return item.id;
  if (!item && !state.preflight.passed) {
    // Setup is not done and the open lessons are finished: show the next lesson to read ahead.
    const next = state.course.find((entry) => entry.kind === 'lesson' && entry.status === 'locked');
    return next ? next.id : null;
  }
  return null;
}

function viewedLessonId(state) {
  const view = currentView(state);
  return view === 'lesson' ? viewedLessonIdInCourse(state) : null;
}

async function loadLesson(id) {
  const generation = app.lessonGen;
  try {
    const res = await apiGet(`/api/lesson?id=${encodeURIComponent(id)}`);
    if (generation !== app.lessonGen) return; // a newer answer arrived; its own refetch follows
    app.lessons.set(id, res.lesson);
    scheduleRender();
  } catch (err) {
    if (['lesson_locked', 'preflight_incomplete', 'unknown_lesson'].includes(err.code) && app.viewLesson === id) {
      app.viewLesson = null;
      scheduleRender();
    }
    reportError(err);
  }
}

function syncLesson() {
  const id = viewedLessonId(app.state);
  if (id) loadLesson(id);
}

function adoptLesson(res) {
  if (res && res.result && res.result.lesson) {
    app.lessons.set(res.result.lesson.id, res.result.lesson);
    scheduleRender();
  }
}

function applyState(state) {
  const previousStepId = app.state && app.state.step ? app.state.step.id : null;
  const installWas = Boolean(app.state && app.state.preflight && app.state.preflight.session.kind === 'recipe');
  // First-run setup is open now. If this state finishes it (whichever check was last), it stays open on its
  // last page instead of closing before the participant has seen Your AI window.
  const firstRunWizardWas = Boolean(app.state && currentView(app.state) === 'wizard' && app.screen !== 'setup');
  app.state = state;
  if (firstRunWizardWas && state.preflight.passed && !state.preflight.skipped && !app.setupDismissed) {
    app.wizardFinishing = true;
  }
  setMapText(state.course_text);
  if (state.step) app.stepCache.set(state.step.id, state.step);
  if (app.terminal && state.terminal) app.terminal.setRunning(state.terminal.running);
  render();
  syncLesson();
  // An install in the AI window ended: look again, so the new tool is found without a button press.
  if (installWas && state.preflight.session.kind !== 'recipe' && !(state.preflight.job && state.preflight.job.running)) {
    mutate('/api/preflight/check', {}).catch(() => {});
  }
  const newStepId = state.step ? state.step.id : null;
  if (newStepId !== previousStepId && !viewedLessonId(state)) $('col-left').scrollTop = 0;
  if (app.focusHeading) {
    app.focusHeading = false;
    const heading = $('step-heading');
    if (heading) heading.focus({ preventScroll: true });
  }
}

function handleServerState(state) {
  postGeneration += 1;
  app.lessonGen += 1;
  if (state && state.configured && app.viewStep && (!state.step || state.step.id !== app.viewStep)) {
    refresh();
    return;
  }
  if (state) applyState(state);
}

// A step where the AI saves its answer finishes by itself in the background. Without this the page would move on to the
// next step on its own, and the participant would not see the answer they just got or press Continue.
function pinPasteStep() {
  const step = app.state && app.state.step;
  if (!app.viewStep && !app.viewLesson && step && step.status === 'active' && step.cli && step.cli.mode === 'paste' && currentView(app.state) === 'course') {
    app.viewStep = step.id;
  }
}

async function refresh() {
  if (fetching) {
    fetchAgain = true;
    return;
  }
  fetching = true;
  pinPasteStep();
  const wantedStep = app.viewStep;
  const generation = postGeneration;
  try {
    const state = await apiGetState(wantedStep, app.part === DEFAULT_PART ? null : app.part);
    if (generation === postGeneration && wantedStep === app.viewStep) applyState(state);
    else fetchAgain = true;
  } catch (err) {
    reportError(err);
  } finally {
    fetching = false;
    if (fetchAgain) {
      fetchAgain = false;
      refresh();
    }
  }
}

function mutate(path, body) {
  const run = async () => {
    try {
      // The server describes the Part named here in the state it returns, so the page stays in its own Part.
      const res = await apiPost(path, app.part === DEFAULT_PART ? body : { ...body, part: app.part });
      handleServerState(res.state);
      return res;
    } catch (err) {
      if (err.state) handleServerState(err.state);
      throw err;
    }
  };
  const result = mutationChain.then(run);
  mutationChain = result.then(
    () => undefined,
    () => undefined,
  );
  return result;
}

// ---- actions ------------------------------------------------------------

async function act(key, fn) {
  if (app.busy.has(key)) return;
  app.busy.add(key);
  scheduleRender();
  try {
    await fn();
  } catch (err) {
    reportError(err);
  } finally {
    app.busy.delete(key);
    scheduleRender();
  }
}

function activityPassed(lessonId, activityId) {
  const lesson = app.lessons.get(lessonId);
  const activity = lesson && lesson.activities ? lesson.activities.find((a) => a.id === activityId) : null;
  return Boolean(activity && activity.passed);
}

const currentStepId = () => (app.state && app.state.step ? app.state.step.id : null);

const actions = {
  navigate(id) {
    if (!app.state || id === currentStepId()) return;
    saver.flush();
    app.screen = null;
    app.setupDismissed = true;
    app.viewStep = id === app.state.current_step ? null : id;
    app.focusHeading = true;
    refresh();
  },

  openCourseItem(kind, id) {
    const { state } = app;
    if (!state) return;
    saver.flush();
    const current = state.current_item;
    const isCurrent = Boolean(current && current.kind === kind && current.id === id);
    app.screen = null;
    app.setupDismissed = true;
    app.local.delete('reset-result');
    app.viewLesson = kind === 'lesson' && !isCurrent ? id : null;
    app.viewStep = kind === 'step' && !isCurrent ? id : null;
    app.focusHeading = true;
    refresh();
  },

  openPart(id) {
    const part = app.state && app.state.series ? app.state.series.parts.find((p) => p.id === id) : null;
    if (!part || part.kind !== 'course') return;
    saver.flush();
    app.part = id;
    app.screen = null;
    app.viewLesson = null;
    app.viewStep = null;
    app.focusHeading = true;
    refresh();
  },

  backToSeries() {
    if (!app.state || !app.state.series) return;
    saver.flush();
    app.screen = 'series';
    app.local.delete('reset-result');
    app.focusHeading = true;
    refresh();
  },

  toggleSeriesPart(id) {
    if (app.seriesOpen.has(id)) app.seriesOpen.delete(id);
    else app.seriesOpen.add(id);
    scheduleRender();
  },

  openSettings() {
    if (!app.state) return;
    saver.flush();
    if (app.screen !== 'settings') app.settingsFrom = app.screen;
    app.screen = 'settings';
    app.focusHeading = true;
    scheduleRender();
  },

  closeSettings() {
    app.screen = app.settingsFrom;
    app.settingsFrom = null;
    app.local.delete('reset-result');
    app.focusHeading = true;
    refresh();
  },

  openSetup() {
    if (!app.state) return;
    saver.flush();
    if (app.screen !== 'setup') app.setupFrom = app.screen;
    app.screen = 'setup';
    app.wizardItem = firstWizardItem(app.state.preflight);
    app.summaryStarted = false;
    app.focusHeading = true;
    scheduleRender();
    focusWizardTop();
  },

  // Leaving the wizard by choice goes back to where it was opened from. Checks and a running CLI are untouched.
  closeSetup() {
    app.screen = app.setupFrom;
    app.setupFrom = null;
    app.wizardItem = null;
    app.wizardFinishing = false;
    app.summaryStarted = false;
    app.focusHeading = true;
    refresh();
  },

  wizardGo(id) {
    app.wizardItem = id;
    app.summaryStarted = false;
    scheduleRender();
    focusWizardTop();
  },

  // The last page, Your AI window, is done. First-run setup closes on the Series map; setup opened by choice closes back.
  wizardFinish() {
    if (app.screen === 'setup') {
      actions.closeSetup();
      return;
    }
    app.wizardFinishing = false;
    app.wizardItem = null;
    app.summaryStarted = false;
    app.screen = 'series';
    app.settingsFrom = null;
    app.setupFrom = null;
    app.viewLesson = null;
    app.viewStep = null;
    app.focusHeading = true;
    refresh();
  },

  openAiWindowLesson() {
    if (app.state) openAiWindowLesson(buildContext());
  },

  pfSkip() {
    return act('pf-skip', async () => {
      await mutate('/api/preflight/skip', {});
      app.screen = 'series';
      app.settingsFrom = null;
      app.setupFrom = null;
      app.wizardItem = null;
      app.setupDismissed = true;
      app.wizardFinishing = false;
      app.summaryStarted = false;
      app.local.delete('reset-result');
      app.focusHeading = true;
      await refresh();
    });
  },

  reset(kind) {
    return act(`reset-${kind}`, async () => {
      const { settings } = app.state;
      const text = settings.text;
      const words = text.reset[kind];
      const ok = await confirmDialog({
        title: words.title,
        body: resetDialogBody(text, kind, settings.backup_folder, settings.has_project),
        confirmLabel: words.confirm_button,
        cancelLabel: words.keep_button,
        danger: kind === 'configuration',
      });
      if (!ok) return;
      await saver.flush();
      const res = await mutate(`/api/reset/${kind}`, { confirm: true });
      app.lessons.clear();
      app.stepCache.clear();
      app.drafts.clear();
      app.local.clear();
      app.viewLesson = null;
      app.viewStep = null;
      app.local.set('reset-result', { message: res.result.message });
      app.focusHeading = true;
      if (kind === 'configuration') {
        // Back to first run: the setup screen comes first and this browser forgets its display choices.
        resetDisplayChoices();
        app.screen = 'series';
        app.part = DEFAULT_PART;
        app.seriesOpen = new Set(DEFAULT_OPEN_PARTS);
        app.settingsFrom = null;
        app.setupFrom = null;
        app.wizardItem = null;
        app.setupDismissed = false;
        app.wizardFinishing = false;
        app.summaryStarted = false;
      }
      await refresh();
    });
  },

  continueToNext() {
    const next = nextStepOf(app.state, app.state.step);
    if (!next) return;
    if (next.kind === 'lesson') actions.openCourseItem('lesson', next.id);
    else actions.navigate(next.id);
  },

  lessonAnswer(lessonId, activityId, answer) {
    return act(`ans-${activityId}`, async () => {
      const passedBefore = activityPassed(lessonId, activityId);
      adoptLesson(await mutate('/api/lesson/answer', { lesson: lessonId, activity: activityId, answer }));
      if (!passedBefore && activityPassed(lessonId, activityId)) celebrate(`#act-title-${activityId}`);
    });
  },

  stepQuestionAnswer(stepId, option) {
    const before = app.state && app.state.step ? app.state.step.question : null;
    return act(`ans-${before ? before.id : 'step-question'}`, async () => {
      await mutate('/api/step/question', { step: stepId, option });
      const after = app.state && app.state.step ? app.state.step.question : null;
      if (after && after.passed && !(before && before.passed)) celebrate(`#act-title-${after.id}`);
    });
  },

  saveReflection(lessonId, activityId, draftKey, text) {
    return act(`ans-${activityId}`, async () => {
      adoptLesson(await mutate('/api/lesson/answer', { lesson: lessonId, activity: activityId, answer: { text } }));
      if (app.drafts.get(draftKey) === text) app.drafts.delete(draftKey);
    });
  },

  ruleRun(lessonId, activityId, rule, text, again) {
    const key = `rule-${activityId}`;
    return act(key, async () => {
      const before = app.local.get(key) || { runs: [] };
      try {
        const res = await mutate('/api/lesson/rule-run', { lesson: lessonId, activity: activityId, rule, text });
        app.local.set(key, { runs: again ? [...before.runs, res.result] : [res.result], error: null, rule, text });
      } catch (err) {
        app.local.set(key, { ...before, error: err.message });
      }
    });
  },

  completeLesson(lessonId) {
    return act('lesson-continue', async () => {
      await saver.flush();
      const cliActivity = lessonCliActivity(app.lessons.get(lessonId));
      if (cliActivity && cliActivity.cli.started && app.state.terminal.running) {
        await mutate('/api/lesson/cli/stop', { lesson: lessonId, activity: cliActivity.id });
      }
      await mutate('/api/lesson/complete', { lesson: lessonId });
      app.viewLesson = null;
      app.viewStep = null;
      app.focusHeading = true;
      await refresh();
    });
  },

  skipLesson(lessonId) {
    return act('lesson-skip', async () => {
      const t = app.state.course_text;
      const ok = await confirmDialog({ title: t.skip_title, body: t.skip_body, confirmLabel: t.skip_confirm, cancelLabel: t.skip_cancel });
      if (!ok) return;
      await mutate('/api/lesson/skip', { lesson: lessonId });
      app.viewLesson = null;
      app.viewStep = null;
      app.focusHeading = true;
      await refresh();
    });
  },

  placementAnswer(id, option) {
    return act(`place-${id}`, async () => {
      adoptLesson(await mutate('/api/placement/answer', { id, option }));
    });
  },

  placementSkip(id, accept) {
    return act(`place-${id}`, async () => {
      adoptLesson(await mutate('/api/placement/answer', { id, accept_skip: accept }));
    });
  },

  lessonCliStart(lessonId, activityId) {
    return act('lcli-start', () => beginLessonCli(lessonId, activityId));
  },

  lessonCliRetry(lessonId, activityId) {
    return act('lcli-retry', async () => {
      if (app.state.terminal.running) {
        const t = app.state.course_text;
        const ok = await confirmDialog({ title: t.cli_restart_title, body: t.cli_restart_body, confirmLabel: t.cli_retry });
        if (!ok) return;
      }
      await beginLessonCli(lessonId, activityId);
    });
  },

  lessonCliSend(lessonId, activityId) {
    return act('lcli-send', async () => {
      await mutate('/api/lesson/cli/send', { lesson: lessonId, activity: activityId });
      app.terminal.focus();
    });
  },

  lessonCliStop(lessonId, activityId) {
    return act('lcli-stop', () => mutate('/api/lesson/cli/stop', { lesson: lessonId, activity: activityId }));
  },

  openKit(ref, label) {
    return openFileViewer({
      text: app.state.course_text,
      ref,
      label,
      load: async (r) => (await apiGet(`/api/kit?ref=${encodeURIComponent(r)}`)).kit,
    });
  },

  openGlossary(term) {
    const lessonLink = (lessonId) => {
      const entry = (app.state.course || []).find((i) => i.kind === 'lesson' && i.id === lessonId);
      return entry ? { id: entry.id, title: entry.title } : null;
    };
    return openGlossary({
      text: app.state.course_text,
      load: loadReference,
      lessonLink,
      onOpenLesson: (id) => actions.openCourseItem('lesson', id),
      focusTerm: term,
    });
  },

  openReview() {
    return openReview({
      text: app.state.course_text,
      load: async () => (await apiGet('/api/review')).review,
      answer: async (item, option) => (await mutate('/api/review/answer', { item, option })).result,
      onClose: () => refresh(),
    });
  },

  postponeReview() {
    return act('review-postpone', async () => {
      await mutate('/api/review/postpone', {});
      app.reviewNote = true;
    });
  },

  dismissReviewNote() {
    app.reviewNote = false;
    scheduleRender();
  },

  dismissNotice(id) {
    app.notices = app.notices.filter((n) => n.id !== id);
    scheduleRender();
  },

  start() {
    const step = currentStepId();
    return act('start', async () => {
      await beginCli(step);
    });
  },

  // "Open a new AI chat" in a step where the participant pastes: it replaces a running window or clears a result in
  // the step's folder, so it asks first.
  newChat() {
    const step = currentStepId();
    return act('start', async () => {
      const shown = app.state.step;
      const ui = shown.ui;
      const clears = Boolean(shown.cli && shown.cli.has_result && ui.new_chat_confirm_body_result);
      if (app.state.terminal.running || clears) {
        const ok = await confirmDialog({
          title: ui.new_chat_confirm_title,
          body: clears ? ui.new_chat_confirm_body_result : ui.new_chat_confirm_body,
          confirmLabel: ui.new_chat_confirm,
        });
        if (!ok) return;
      }
      await beginCli(step);
    });
  },

  // The participant's own Continue on a score form: the answers autosave, so only this finishes the step.
  finishStep() {
    const step = currentStepId();
    return act('check', async () => {
      await saver.flush();
      app.viewStep = step;
      const res = await mutate('/api/step/check', { step });
      const checked = res && res.state && res.state.step;
      if (checked && checked.id === step && checked.status === 'done') {
        celebrate('#continue');
        actions.continueToNext();
      }
    });
  },

  // "Start this step again": clears this step and the later steps of its Part, after a confirm.
  restart(stepId) {
    return act(`restart-${stepId}`, async () => {
      const shown = app.state.step;
      const words = app.state.settings.text.restart;
      const ok = await confirmDialog({
        title: words.title,
        body: restartDialogBody(words, shown.restart),
        confirmLabel: words.confirm_button,
        cancelLabel: words.keep_button,
        danger: true,
      });
      if (!ok) return;
      await saver.flush();
      app.viewStep = null;
      const res = await mutate('/api/step/restart', { step: stepId, confirm: true });
      for (const id of res.result.steps) {
        for (const key of Array.from(app.drafts.keys())) {
          if (key.startsWith(`${id}.`) || key.startsWith(`checklist.${id}.`)) app.drafts.delete(key);
        }
        for (const key of Array.from(app.local.keys())) if (key === `copy-${id}`) app.local.delete(key);
        app.stepCache.delete(id);
      }
      app.local.set('restart-result', { step: stepId, message: res.result.message });
      app.focusHeading = true;
      await refresh();
    });
  },

  retry() {
    const step = currentStepId();
    return act('retry', async () => {
      if (app.state.terminal.running) {
        const ok = await confirmDialog({
          title: 'Start again?',
          body: 'This stops your AI and starts a new chat. Anything it has not saved will be lost.',
          confirmLabel: 'Start again',
        });
        if (!ok) return;
      }
      await beginCli(step);
    });
  },

  send() {
    const step = currentStepId();
    return act('send', async () => {
      await mutate('/api/step/send', { step });
      app.terminal.focus();
    });
  },

  stop() {
    const step = currentStepId();
    return act('stop', () => mutate('/api/step/stop', { step }));
  },

  check() {
    const step = currentStepId();
    return act('check', async () => {
      if (step === 'fix' && app.drafts.has('fix.test_cases_text')) {
        reportError('You have unsaved changes to your test cases. Save them first, then check your work.');
        return;
      }
      const shown = app.stepCache.get(step);
      if (shown && (unsavedTexts(shown, app.drafts) || unsavedCriteria(shown, app.drafts))) {
        reportError(shown.ui.unsaved_check);
        return;
      }
      await saver.flush();
      app.viewStep = step; // stay on this step so the results stay visible
      const res = await mutate('/api/step/check', { step });
      const checked = res && res.state && res.state.step;
      if (checked && checked.id === step && checked.last_check && checked.last_check.ok) celebrate('#check-work');
    });
  },

  runChecker(which) {
    const step = currentStepId();
    return act(which, async () => {
      await saver.flush();
      await mutate('/api/step/run-checker', { step, which });
    });
  },

  lockPredictions() {
    const step = app.state.step;
    return act('lock', async () => {
      const ok = await confirmDialog({
        title: 'Lock your predictions?',
        body: 'Locking is permanent. You will not be able to change your predictions after this.',
        confirmLabel: 'Lock my predictions',
        danger: true,
      });
      if (!ok) return;
      await saver.flush();
      const { data } = PANELS.predict.collect(app.stepCache.get(step.id), app.drafts);
      await mutate('/api/step/submit', { step: step.id, data: { ...data, lock: true } });
      for (const key of Array.from(app.drafts.keys())) {
        if (key.startsWith('predict.')) app.drafts.delete(key);
      }
    });
  },

  saveFixTests() {
    return act('fix-save', async () => {
      const key = 'fix.test_cases_text';
      if (!app.drafts.has(key)) return;
      const text = app.drafts.get(key);
      await mutate('/api/step/submit', { step: 'fix', data: { test_cases_text: text } });
      if (app.drafts.get(key) === text) app.drafts.delete(key);
    });
  },

  useExampleFixtures() {
    const step = app.state.step;
    return act('example-fixtures', async () => {
      const ui = step.ui || {};
      const body = { step: 'fixtures' };
      if (step.data.example && step.data.example.would_replace) {
        const ok = await confirmDialog({
          title: ui.example_confirm_title,
          body: ui.example_confirm_body,
          confirmLabel: ui.example_confirm_label,
        });
        if (!ok) return;
        body.replace = true;
      }
      await mutate('/api/step/use-example-fixtures', body);
    });
  },

  // Saves the texts a Part 1 step keeps by an explicit Save (a prompt, or the own-work pair). `sent` holds the
  // [draft key, value] pairs that were sent, so a text typed while saving stays as a draft.
  partSave(stepId, data, sent) {
    return act(`part-save-${stepId}`, async () => {
      // The first save of a prompt can open the AI window by itself; the pane starts clear and fits the new window.
      const shown = app.stepCache.get(stepId);
      const mayStart = Boolean(shown && shown.cli && shown.cli.mode === 'paste' && 'prompt' in data && !app.state.terminal.running);
      if (mayStart && app.terminal) app.terminal.clearForNewSession();
      await mutate('/api/step/submit', { step: stepId, data });
      if (mayStart && app.terminal) app.terminal.syncSize();
      for (const [key, value] of sent) if (app.drafts.get(key) === value) app.drafts.delete(key);
    });
  },

  // Builds the test case file from the worksheet. `ask` confirms before replacing text; the server's own
  // confirm_replace refusal asks the same question. `clear` lists the drafts the new file replaces.
  buildFile(stepId, { hasText, ask, clear }) {
    return act(`part-build-${stepId}`, async () => {
      const send = (replace) => mutate('/api/step/submit', { step: stepId, data: replace ? { build: true, replace: true } : { build: true } });
      if (hasText && !(await ask())) return;
      try {
        await send(hasText);
      } catch (err) {
        if (!(err instanceof ApiError) || err.code !== 'confirm_replace') throw err;
        if (!(await ask())) return;
        await send(true);
      }
      for (const key of clear) app.drafts.delete(key);
    });
  },

  skip() {
    return act('skip', async () => {
      const ok = await confirmDialog({
        title: 'Skip this step?',
        body: 'You had no surprises, so you can skip fixing your test cases.',
        confirmLabel: 'Skip this step',
      });
      if (!ok) return;
      app.viewStep = null; // a skipped step has nothing to read back, so the page moves on to the next one
      await mutate('/api/step/skip', { step: 'fix' });
    });
  },

  pfTrack(track) {
    return act('pf-track', async () => {
      try {
        await mutate('/api/preflight/track', { track });
      } finally {
        app.drafts.delete('pf.track');
      }
    });
  },

  pfCheckAll() {
    return act('pf-check', () => mutate('/api/preflight/check', {}));
  },

  pfInstall(item) {
    return act(`pf-install-${item.id}`, async () => {
      const ok = await confirmDialog({
        title: item.install.consent.title,
        body: item.install.consent.body,
        confirmLabel: item.install.consent.confirm_label,
        cancelLabel: item.install.consent.cancel_label,
      });
      if (!ok) return;
      await mutate('/api/preflight/install', { item: item.id, consent: true });
    });
  },

  pfCliCheck() {
    return act('pf-cli-check', async () => {
      const pf = app.state.preflight;
      const command = (app.drafts.has('pf.cli_command') ? app.drafts.get('pf.cli_command') : pf.cli.command || '').trim();
      await mutate('/api/preflight/cli', { cli_command: command });
      app.drafts.delete('pf.cli_command');
      watchAiTest();
    });
  },

  pfUseAi(command) {
    return act('pf-use-ai', async () => {
      await mutate('/api/preflight/cli', { cli_command: command });
      app.drafts.delete('pf.ai');
      watchAiTest();
    });
  },

  pfRecipe(recipeId) {
    const key = `pf-recipe-${recipeId}`;
    return act(key, async () => {
      const recipe = app.state.preflight.cli.recipes.find((r) => r.id === recipeId);
      const ok = await confirmDialog({
        title: recipe.consent.title,
        body: recipe.consent.body,
        confirmLabel: recipe.consent.confirm_label,
        cancelLabel: recipe.consent.cancel_label,
      });
      if (!ok) return;
      await beginPreflightCli('/api/preflight/cli/recipe', { recipe: recipeId, consent: true });
    });
  },

  pfTestStart() {
    return act('pf-test-start', () => beginPreflightCli('/api/preflight/test/start', {}));
  },

  pfTestSend() {
    return act('pf-test-send', async () => {
      await mutate('/api/preflight/test/send', {});
      app.terminal.focus();
    });
  },

  pfTestCheck() {
    return act('pf-test-check', () => mutate('/api/preflight/test/check', {}));
  },

  pfStop() {
    return act('pf-stop', () => mutate('/api/preflight/stop', {}));
  },

  setModel(preference) {
    return act('set-model', async () => {
      // Shown at once, so the choice does not flicker back while the request is on its way.
      app.local.set('model-choice', preference);
      try {
        await mutate('/api/model', { preference });
      } finally {
        app.local.delete('model-choice');
      }
    });
  },

  pfImportCheck() {
    return act('pf-import-check', async () => {
      const setup = app.state.setup || {};
      const defaults = setup.defaults || {};
      const value = (key, fallback) => (app.drafts.has(key) ? app.drafts.get(key) : fallback || '').trim();
      const body = {
        prompt_path: value('setup.prompt_path', ''),
        test_cases_path: value('setup.test_cases_path', ''),
        project_path: value('setup.project_path', setup.project_path || defaults.project_path),
      };
      const res = await mutate('/api/setup/import-check', body);
      app.local.set('import-check', { key: [body.prompt_path, body.test_cases_path, body.project_path].join('\n'), result: res.result });
    });
  },

  pfProject() {
    return act('setup', async () => {
      const setup = app.state.setup || {};
      const defaults = setup.defaults || {};
      const value = (key, fallback) => (app.drafts.has(key) ? app.drafts.get(key) : fallback || '').trim();
      const body = {
        project_path: value('setup.project_path', setup.project_path || defaults.project_path),
        starter: app.drafts.has('setup.starter') ? app.drafts.get('setup.starter') : setup.starter || 'northwind',
      };
      if (!body.project_path) {
        reportError(app.state.preflight.text.project_required);
        return;
      }
      if (body.starter === 'own') {
        body.prompt_path = value('setup.prompt_path', '');
        body.test_cases_path = value('setup.test_cases_path', '');
        if (!body.prompt_path || !body.test_cases_path) {
          reportError(app.state.preflight.text.own_paths_required);
          return;
        }
      }
      await mutate('/api/setup', body);
      app.local.delete('import-check');
      for (const key of Array.from(app.drafts.keys())) if (key.startsWith('setup.')) app.drafts.delete(key);
      // The project page is done, but the wizard has one page left: Your AI window. Finish closes it.
      if (app.screen !== 'setup') app.wizardFinishing = true;
      app.wizardItem = 'ai_window';
      app.viewLesson = null;
      app.viewStep = null;
      app.focusHeading = true;
      await refresh();
      focusWizardTop();
    });
  },

  quit() {
    return act('quit', async () => {
      const ok = await confirmDialog({
        title: 'Quit eval-coach?',
        body: 'This stops your AI and closes the app. Your progress is saved, and you can pick up where you left off next time.',
        confirmLabel: 'Quit',
      });
      if (!ok) return;
      await saver.flush();
      app.quitting = true;
      try {
        await apiPost('/api/quit', {});
      } catch {
        // The server may stop before it can answer.
      }
      if (app.terminal) app.terminal.stop();
      showMessage('eval-coach has stopped', 'You can close this tab. Start eval-coach again whenever you want to continue.');
    });
  },
};

async function beginPreflightCli(path, body) {
  if (app.terminal) app.terminal.clearForNewSession();
  await mutate(path, body);
  if (app.terminal) {
    app.terminal.syncSize();
    app.terminal.focus();
  }
}

async function beginCli(step) {
  await saver.flush();
  if (app.terminal) app.terminal.clearForNewSession();
  await mutate('/api/step/start', { step });
  if (app.terminal) {
    app.terminal.syncSize();
    app.terminal.focus();
  }
}

async function beginLessonCli(lessonId, activityId) {
  await saver.flush();
  if (app.terminal) app.terminal.clearForNewSession();
  await mutate('/api/lesson/cli/start', { lesson: lessonId, activity: activityId });
  if (app.terminal) {
    app.terminal.syncSize();
    app.terminal.focus();
  }
}

async function loadReference() {
  if (app.referenceData) return app.referenceData;
  let resp;
  try {
    resp = await fetch('reference-data.json', { cache: 'no-store' });
  } catch {
    throw new ApiError('not_responding', 'The glossary could not be loaded. Try again.');
  }
  if (!resp.ok) throw new ApiError(`http_${resp.status}`, 'The glossary could not be loaded. Try again.');
  app.referenceData = await resp.json();
  return app.referenceData;
}

// ---- rendering ----------------------------------------------------------

function nextStepOf(state, step) {
  if (!step) return null;
  if (hasLessons(state)) {
    const i = state.course.findIndex((item) => item.kind === 'step' && item.id === step.id);
    const next = i >= 0 ? state.course[i + 1] : null;
    return next && next.status !== 'locked' ? next : null;
  }
  if (!state.steps) return null;
  const i = state.steps.findIndex((s) => s.id === step.id);
  const next = i >= 0 ? state.steps[i + 1] : null;
  return next && next.status !== 'locked' ? next : null;
}

const BLANK_TERMINAL = { running: false, label: '', exit_code: null, owner: null };

// Who the terminal pane on screen belongs to: 'preflight' for the setup pages that use it, a step id, a lesson
// activity key, or null when the screen shows no terminal.
function viewedTerminalOwner(state, view, step, lessonId, lesson) {
  if (!state) return null;
  if (view === 'settings' || view === 'series') return null;
  if (view === 'wizard') {
    const probe = { state, wizard: { item: app.wizardItem, byChoice: app.screen === 'setup' } };
    return wizardUsesTerminal(probe) ? 'preflight' : null;
  }
  if (lessonId) {
    const cliActivity = lesson ? lessonCliActivity(lesson) : null;
    return cliActivity ? `lesson:${lessonId}:${cliActivity.id}` : null;
  }
  return step && step.cli ? step.id : null;
}

// Output, label and exit code left over from another section's CLI do not belong on this page.
function isForeignTerminal(terminal, owner) {
  if (!terminal || !owner || terminal.owner === null || terminal.owner === undefined) return false;
  if (owner === 'preflight') return !terminal.owner.startsWith('preflight:');
  return terminal.owner !== owner;
}

// Leaves the section that owned the terminal: the CLI is stopped if it still runs, and the pane starts clear.
// A setup CLI that is still running stays, because setup keeps it open until it passes.
function releaseStaleTerminal() {
  const terminal = app.state && app.state.terminal;
  if (!terminal || app.releasing || app.releaseFailedFor === terminal.owner) return;
  if (terminal.running && terminal.owner.startsWith('preflight:')) return;
  app.releasing = true;
  if (app.terminal) app.terminal.clearForNewSession();
  mutate('/api/terminal/release', {})
    .catch((err) => {
      app.releaseFailedFor = terminal.owner;
      reportError(err);
    })
    .finally(() => {
      app.releasing = false;
    });
}

function buildContext() {
  const { state: rawState } = app;
  const step = rawState ? rawState.step : null;
  const view = currentView(rawState);
  const lessonId = viewedLessonId(rawState);
  let viewed = null;
  if (lessonId) viewed = { kind: 'lesson', id: lessonId };
  else if (view === 'course' && step) viewed = { kind: 'step', id: step.id };
  const lesson = lessonId ? app.lessons.get(lessonId) || null : null;
  // The terminal pane belongs to the section whose CLI filled it. Another section shows it empty.
  const owner = viewedTerminalOwner(rawState, view, step, lessonId, lesson);
  const stale = isForeignTerminal(rawState && rawState.terminal, owner);
  const state = stale ? { ...rawState, terminal: BLANK_TERMINAL } : rawState;
  return {
    state,
    step,
    view,
    wizard: {
      item: app.wizardItem,
      byChoice: app.screen === 'setup',
      summaryDone: Boolean(app.summaryStarted && rawState && rawState.preflight.ran_once && !(rawState.preflight.job && rawState.preflight.job.running)),
    },
    text: (state && state.course_text) || {},
    seriesOpen: app.seriesOpen,
    // The sidebar shows the Series map's form on the map and on Settings opened from it.
    mapNav: Boolean(rawState && rawState.series && (view === 'series' || (view === 'settings' && app.settingsFrom === 'series'))),
    lessonId,
    lesson,
    viewed,
    staleTerminal: stale,
    reviewNote: app.reviewNote,
    readOnly: !step || step.status !== 'active',
    nextStep: nextStepOf(state, step),
    notices: app.notices,
    actions,
    busy: (key) => app.busy.has(key),
    local: (key) => app.local.get(key),
    setLocal: (key, value) => app.local.set(key, value),
    draft: (key, fallback) => (app.drafts.has(key) ? app.drafts.get(key) : fallback),
    hasDraft: (key) => app.drafts.has(key),
    setDraft: (key, value) => app.drafts.set(key, value),
    clearDraft: (key) => app.drafts.delete(key),
    queueSave: (stepId) => saver.schedule(stepId),
    flushSave: (stepId) => saver.flushStep(stepId),
    saveStatus: (stepId) => saver.status.get(stepId) || null,
    rerender: scheduleRender,
  };
}

let renderQueued = false;

function scheduleRender() {
  if (renderQueued) return;
  renderQueued = true;
  queueMicrotask(() => {
    renderQueued = false;
    render();
  });
}

function showScreen(name) {
  $('screen-setup').hidden = name !== 'setup';
  $('screen-main').hidden = name !== 'main';
  $('screen-message').hidden = name !== 'message';
}

// After a page change in the wizard: back to the top of the page, with the heading read first.
function focusWizardTop() {
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      $('col-left').scrollTop = 0;
      const heading = $('step-heading');
      if (heading) heading.focus({ preventScroll: true });
    });
  });
}

function stopTestPoll() {
  if (app.testPoll) {
    clearInterval(app.testPoll);
    app.testPoll = null;
  }
}

// After "Use this AI", the server tests the AI quietly in the background. Watch for it on this visit only when
// a test ran or has a result for this AI; an AI with no quiet test leaves the page as it was.
function watchAiTest() {
  const background = app.state && app.state.preflight.working_test.background;
  app.aiTestWatch = Boolean(background && background.state !== 'idle');
  scheduleRender();
}

// When the quiet test ends the wizard moves on by itself: to the next page that still needs the participant after
// a pass, and to the AI working test page, where the AI window is, when the test could not finish.
function followAiTest(ctx, page) {
  if (!app.aiTestWatch) return;
  const pf = ctx.state.preflight;
  const state = pf.working_test.background.state;
  if (page !== 'cli' || state === 'idle') {
    app.aiTestWatch = false;
    return;
  }
  if (aiTesting(pf)) return;
  app.aiTestWatch = false;
  const pages = wizardPages(pf);
  const target = state === 'passed' ? nextWizardPage(pages, wizardIndex(ctx)) : pages.find((p) => p.id === 'working_test');
  actions.wizardGo(target.id);
}

// Two things the wizard does by itself. The Checking your computer page starts the checks when it is shown (not
// while another job runs). After Send on the working test page, the test folder is re-read every few seconds;
// that read only ever records a pass, so a failure is shown only when the participant presses the Check button.
function syncWizardAutomation(ctx) {
  const pf = ctx.state.preflight;
  const page = wizardPageId(ctx);
  const jobRunning = Boolean(pf.job && pf.job.running);
  followAiTest(ctx, page);
  if (page === 'summary' && !app.summaryStarted && !app.summaryStarting && !jobRunning) {
    app.summaryStarting = true;
    act('pf-summary', async () => {
      try {
        await mutate('/api/preflight/check', {});
      } finally {
        app.summaryStarted = true;
        app.summaryStarting = false;
      }
    });
  }
  const waiting = page === 'working_test' && pf.session.kind === 'test' && pf.session.sent;
  if (!waiting) {
    stopTestPoll();
    return;
  }
  if (app.testPoll) return;
  app.testPoll = setInterval(() => {
    if (app.testPolling) return;
    app.testPolling = true;
    mutate('/api/preflight/test/poll', {})
      .catch(() => {})
      .finally(() => {
        app.testPolling = false;
      });
  }, TEST_POLL_MS);
}

function render() {
  if (app.quitting) return;
  try {
    const ctx = buildContext();
    if (ctx.staleTerminal) releaseStaleTerminal();
    if (ctx.view === 'wizard' && !app.wizardItem) {
      app.wizardItem = firstWizardItem(ctx.state.preflight);
      ctx.wizard.item = app.wizardItem;
    }
    if (ctx.view === 'wizard') syncWizardAutomation(ctx);
    else stopTestPoll();
    // The wizard fills the window: no sidebar, course list or tools beside it.
    if (ctx.view === 'wizard') $('topbar').replaceChildren();
    else morph($('topbar'), ...renderTopbar(ctx));
    syncCourseNav();
    window.requestAnimationFrame(updateReadProgress);
    morph($('notices'), ...renderNotices(ctx));
    morph($('setup-banner'), ...renderSetupBanner(ctx));
    morph($('review-banner'), ...(ctx.view === 'wizard' ? [] : renderReviewBanner(ctx)));
    if (!ctx.state) return;
    showScreen('main');
    $('screen-setup').replaceChildren();
    const main = $('screen-main');
    if (ctx.view === 'settings') {
      main.classList.add('no-terminal');
      morph($('col-left'), renderSettings(ctx));
      app.lastRenderedLesson = null;
      startTerminal();
      return;
    }
    if (ctx.view === 'series') {
      main.classList.add('no-terminal');
      morph($('col-left'), renderSeries(ctx));
      app.lastRenderedLesson = null;
      startTerminal();
      return;
    }
    if (ctx.view === 'wizard') {
      // The terminal shows only on the pages that use the CLI. It is hidden, not recreated, so a running CLI survives page changes.
      const withTerminal = wizardUsesTerminal(ctx);
      main.classList.toggle('no-terminal', !withTerminal);
      morph($('col-left'), renderWizard(ctx));
      if (withTerminal) {
        morph($('term-head'), ...renderPreflightTermHead(ctx));
        morph($('term-foot'), ...renderPreflightTermFoot(ctx));
      }
      app.lastRenderedLesson = null;
      startTerminal();
      if (withTerminal && app.terminal) app.terminal.open($('term-host'));
      return;
    }
    if (ctx.lessonId) {
      const cliActivity = lessonCliActivity(ctx.lesson);
      main.classList.toggle('no-terminal', !cliActivity);
      morph($('col-left'), renderLesson(ctx));
      if (cliActivity) {
        morph($('term-head'), ...renderLessonTermHead(ctx, ctx.lesson, cliActivity));
        morph($('term-foot'), ...renderTermFoot(ctx));
      }
      if (app.lastRenderedLesson !== ctx.lessonId) {
        $('col-left').scrollTop = 0;
        app.lastRenderedLesson = ctx.lessonId;
      }
      startTerminal();
      if (cliActivity && app.terminal) app.terminal.open($('term-host'));
      return;
    }
    app.lastRenderedLesson = null;
    const withTerminal = Boolean(ctx.step && ctx.step.cli);
    main.classList.toggle('no-terminal', !withTerminal);
    if (ctx.step) {
      morph($('col-left'), renderStep(ctx));
    } else {
      morph($('col-left'), renderFinished(ctx));
    }
    if (withTerminal) {
      morph($('term-head'), ...renderTermHead(ctx));
      morph($('term-foot'), ...renderTermFoot(ctx));
      if (app.terminal) app.terminal.open($('term-host'));
    }
    startTerminal();
    maybeAutoStart(ctx);
  } catch (err) {
    console.error(err);
    reportError('Something went wrong drawing this page.');
  }
}

// A Part 3 step opens its AI window by itself the first time it is shown. Ask once per visit, and only when the
// step's own view says the server will start it; the server applies the full rule and ignores the rest.
function maybeAutoStart(ctx) {
  const { step } = ctx;
  if (!step || step.id !== app.autoStartAsked) app.autoStartAsked = null;
  if (!step || !step.cli || !step.cli.can_auto_start || app.autoStartAsked === step.id) return;
  const id = step.id;
  app.autoStartAsked = id;
  act(`auto-start-${id}`, async () => {
    if (app.terminal) app.terminal.clearForNewSession();
    await mutate('/api/step/auto-start', { step: id });
    if (app.terminal) app.terminal.syncSize();
  });
}

function startTerminal() {
  if (app.terminal || !app.state) return;
  app.terminal = createTerminal({
    onState: () => refresh(),
    onExit: (code) => {
      if (app.state) {
        app.state.terminal.running = false;
        app.state.terminal.exit_code = code;
        app.terminal.setRunning(false);
        scheduleRender();
      }
      refresh();
    },
    onConnection: (connected) => {
      if (!connected) app.connectionDrops = (app.connectionDrops || 0) + 1;
      else app.connectionDrops = 0;
      if (app.connectionDrops === 3) reportError('The terminal connection dropped. Trying to reconnect…');
    },
    onError: reportError,
    onLeave: () => {
      const first = document.querySelector('#term-head button:not([aria-disabled="true"])');
      if (first) first.focus();
      else $('col-left').focus();
    },
  });
  app.terminal.setRunning(app.state.terminal && app.state.terminal.running);
  app.terminal.observe($('term-host'));
  app.terminal.connect();
  if (app.state.step && app.state.step.cli) app.terminal.open($('term-host'));
}


function showMessage(title, body) {
  $('topbar').replaceChildren();
  $('notices').replaceChildren();
  const message = $('screen-message');
  const h1 = document.createElement('h1');
  h1.textContent = title;
  const p = document.createElement('p');
  p.textContent = body;
  message.replaceChildren(h1, p);
  showScreen('message');
}

function warnBeforeLeaving(event) {
  if (app.quitting || !app.state || !app.state.configured) return;
  const running = app.state.terminal && app.state.terminal.running;
  const unsaved = Array.from(app.drafts.keys()).some((key) => !key.startsWith('lesson.'));
  if (running || unsaved) {
    event.preventDefault();
    event.returnValue = '';
  }
}

function boot() {
  if (!readTokenOnce()) {
    showMessage(
      'Open eval-coach from its own link',
      'This page needs the private link eval-coach gives you when it starts. If you lost the link, close this tab and start eval-coach again.',
    );
    return;
  }
  window.addEventListener('beforeunload', warnBeforeLeaving);
  initChrome(scheduleRender);
  window.addEventListener('unhandledrejection', (event) => reportError(event.reason));
  refresh();
}

boot();
