// Lessons: the course list, the lesson page, every activity type, placement and the review banner.
// Correct answers never reach this file. Everything shown as right or wrong comes from a server response.

import { isWide } from './chrome.js';
import { h } from './dom.js';
import { renderMarkdown } from './markdown.js';
import { actionButton, resultTables, section } from './ui.js';

const COURSE_LABEL = 'Course';
const SAMPLE_LABEL = 'Start from a sample';

export function fmt(template, vars) {
  return String(template || '').replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] !== undefined ? vars[k] : m));
}

export const tx = (ctx, key, vars) => fmt(ctx.text[key], vars);

const dk = (lessonId, activityId, part) => `lesson.${lessonId}.${activityId}.${part}`;

export function wordCount(text) {
  const trimmed = String(text || '').trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

export function hasLessons(state) {
  return Boolean(state && Array.isArray(state.course) && state.course.some((item) => item.kind === 'lesson'));
}

export function lessonCliActivity(lesson) {
  return lesson && lesson.activities ? lesson.activities.find((a) => a.cli) || null : null;
}

// ---- course list --------------------------------------------------------

function statusWord(ctx, status) {
  return ctx.text[`status_${status}`] || '';
}

// The group an item belongs to, from ui.course_groups in the interface text.
function groupOf(ctx, id) {
  return (ctx.text.course_groups || []).find((g) => g.items.includes(id)) || null;
}

function courseEntries(ctx) {
  const { state } = ctx;
  const entries = state.course.map((item) => ({
    kind: item.kind,
    id: item.id,
    title: item.title,
    status: item.status,
    viewed: ctx.viewed && ctx.viewed.kind === item.kind && ctx.viewed.id === item.id,
  }));
  for (const extra of state.optional_steps || []) {
    entries.push({
      kind: 'step',
      id: extra.id,
      title: extra.title,
      status: extra.status,
      viewed: Boolean(ctx.viewed && ctx.viewed.kind === 'step' && ctx.viewed.id === extra.id),
    });
  }
  // Setup is not a course item: the list holds only lessons and steps.
  return entries;
}

export function renderCourseNav(ctx) {
  const entries = courseEntries(ctx);
  const viewed = entries.find((e) => e.viewed) || entries.find((e) => e.status === 'active');
  const lessons = entries.filter((e) => e.kind === 'lesson');
  // On wide screens this list is the sidebar and stays open. On narrow ones it is a drop-down.
  return h(
    'details',
    {
      class: 'course-nav',
      key: 'course-nav',
      onKeydown: (event) => {
        if (event.key !== 'Escape' || isWide()) return;
        const details = event.currentTarget;
        if (details.open) {
          details.open = false;
          const summary = details.querySelector('summary');
          if (summary) summary.focus();
        }
      },
    },
    h(
      'summary',
      {
        class: 'course-summary',
        onClick: (event) => {
          if (isWide()) event.preventDefault();
        },
      },
      h('span', { class: 'tb-icon tb-icon-list', 'aria-hidden': 'true' }),
      h('span', { class: 'course-label' }, COURSE_LABEL),
      viewed ? h('span', { class: 'course-current' }, viewed.title) : null,
      viewed && viewed.kind === 'lesson'
        ? h('span', { class: 'course-count' }, `${lessons.findIndex((e) => e.id === viewed.id) + 1}/${lessons.length}`)
        : null,
    ),
    h(
      'nav',
      { class: 'course-panel', 'aria-label': COURSE_LABEL },
      h(
        'ol',
        { class: 'course-list' },
        entries.flatMap((e, index) => {
          const inner = [
            h('span', { class: 'course-item-mark', 'aria-hidden': 'true' }, String(index + 1)),
            h('span', { class: 'course-item-title' }, e.title),
            h('span', { class: 'course-item-status' }, statusWord(ctx, e.status)),
          ];
          const group = groupOf(ctx, e.id);
          const heading =
            group && (index === 0 || groupOf(ctx, entries[index - 1].id) !== group)
              ? h(
                  'li',
                  { key: `group-${group.id}`, role: 'presentation' },
                  h('span', { class: 'course-group', role: 'heading', 'aria-level': '2' }, group.label),
                )
              : null;
          const item = h(
            'li',
            { key: `${e.kind}-${e.id}`, class: `course-item k-${e.kind} s-${e.status}${e.viewed ? ' is-viewed' : ''}` },
            h(
              'button',
              {
                type: 'button',
                class: 'course-btn',
                title: e.title,
                'aria-current': e.viewed ? 'step' : null,
                onClick: (event) => {
                  const details = event.currentTarget.closest('details');
                  if (details && !isWide()) details.open = false;
                  ctx.actions.openCourseItem(e.kind, e.id);
                },
              },
              inner,
            ),
          );
          return heading ? [heading, item] : [item];
        }),
      ),
    ),
  );
}

// ---- review banner ------------------------------------------------------

export function renderReviewBanner(ctx) {
  const review = ctx.state && ctx.state.review;
  if (!review || !ctx.text.review_banner) return [];
  if (review.due > 0 && !review.postponed) {
    const word = review.due === 1 ? ctx.text.review_word_one : ctx.text.review_word_many;
    return [
      h(
        'section',
        { class: 'review-banner', key: 'review-banner', 'aria-label': ctx.text.review_heading },
        h('p', null, fmt(ctx.text.review_banner, { n: review.due, word })),
        actionButton(ctx, { label: ctx.text.review_start, id: 'review-start', kind: 'primary', onClick: () => ctx.actions.openReview() }),
        actionButton(ctx, { label: ctx.text.review_postpone, id: 'review-postpone', busyKey: 'review-postpone', onClick: () => ctx.actions.postponeReview() }),
      ),
    ];
  }
  if (review.postponed && ctx.reviewNote) {
    return [
      h(
        'section',
        { class: 'review-banner is-note', key: 'review-note', role: 'status' },
        h('p', null, ctx.text.review_postponed),
        h('button', { type: 'button', class: 'btn btn-quiet', onClick: () => ctx.actions.dismissReviewNote() }, ctx.text.dialog_close),
      ),
    ];
  }
  return [];
}

// ---- shared activity pieces ---------------------------------------------

function passedTag(ctx, passed) {
  return passed ? h('span', { class: 'pass-tag' }, tx(ctx, 'passed_tag')) : null;
}

function feedbackRegion(ctx, key, content) {
  return h('div', { class: 'feedback', key, role: 'status', 'aria-live': 'polite' }, content);
}

function sameSet(a, b) {
  return Array.isArray(a) && a.length === b.length && [...a].sort().join('\u0000') === [...b].sort().join('\u0000');
}

function submitButton(ctx, activity, { disabled, onClick }) {
  return actionButton(ctx, {
    label: tx(ctx, 'submit'),
    busyLabel: tx(ctx, 'submitting'),
    busyKey: `ans-${activity.id}`,
    id: `submit-${activity.id}`,
    kind: 'primary',
    disabled,
    onClick,
  });
}

function activityShell(ctx, activity, title, ...children) {
  const titleId = `act-title-${activity.id}`;
  return h(
    'article',
    { class: `activity a-${activity.type}${activity.passed ? ' is-passed' : ''}`, key: `act-${activity.id}`, 'aria-labelledby': titleId },
    h('h3', { class: 'activity-title', id: titleId }, title, passedTag(ctx, activity.passed)),
    ...children,
  );
}

// ---- choice -------------------------------------------------------------

function renderChoiceBody(ctx, lesson, activity, view, enabled, labelId, onSubmit) {
  const key = dk(lesson.id, activity.id, 'option');
  const result = view.result;
  const selected = ctx.draft(key, result ? result.chosen : null);
  const explain = new Map(((result && result.explanations) || []).map((e) => [e.id, e]));
  const chosen = result ? view.options.find((o) => o.id === result.chosen) : null;
  const passed = Boolean(activity.passed);
  return [
    h(
      'ul',
      { class: 'choice-list', key: 'options', role: 'radiogroup', 'aria-labelledby': labelId },
      view.options.map((o) => {
        const note = explain.get(o.id);
        return h(
          'li',
          { key: `opt-${o.id}`, class: `choice-opt${selected === o.id ? ' is-selected' : ''}` },
          h(
            'label',
            { class: 'radio-card' },
            h('input', {
              type: 'radio',
              name: `choice-${activity.id}`,
              value: o.id,
              checked: selected === o.id,
              disabled: !enabled,
              onChange: () => {
                ctx.setDraft(key, o.id);
                ctx.rerender();
              },
            }),
            h('span', null, o.text),
          ),
          note
            ? h('p', { class: 'choice-note', key: 'note' }, note.correct ? h('strong', null, `${tx(ctx, 'feedback_correct')} `) : null, note.feedback)
            : null,
        );
      }),
    ),
    feedbackRegion(
      ctx,
      'feedback',
      result
        ? h(
            'div',
            { class: `callout ${passed || result.passed ? 'callout-good' : 'callout-attn'}` },
            h('strong', { class: 'block' }, result.passed ? tx(ctx, 'feedback_correct') : tx(ctx, 'feedback_try_again')),
            chosen ? h('span', { class: 'block choice-chosen' }, chosen.text) : null,
            result.passed ? null : result.feedback,
            result.passed ? null : h('span', { class: 'hint block' }, tx(ctx, 'retry_hint')),
          )
        : null,
    ),
    passed || !enabled
      ? null
      : h(
          'div',
          { class: 'row', key: 'row' },
          submitButton(ctx, activity, {
            disabled: !selected,
            onClick: () => (onSubmit ? onSubmit(selected) : ctx.actions.lessonAnswer(lesson.id, activity.id, { option: selected })),
          }),
        ),
  ];
}

function renderChoice(ctx, lesson, activity, enabled) {
  return activityShell(ctx, activity, activity.prompt, ...renderChoiceBody(ctx, lesson, activity, activity, enabled && !activity.passed, `act-title-${activity.id}`));
}

// The question that follows a finished step. It reuses the lesson choice card and never gates anything.
export function renderStepQuestion(ctx, step) {
  const question = step.question;
  if (!question || !ctx.text.step_check_heading) return null;
  const activity = { id: question.id, type: 'choice', passed: question.passed };
  const holder = { id: `step-${step.id}` };
  return section(
    'step-question',
    tx(ctx, 'step_check_heading'),
    h('p', { class: 'hint', key: 'note' }, tx(ctx, 'step_check_note')),
    activityShell(
      ctx,
      activity,
      question.prompt,
      ...renderChoiceBody(ctx, holder, activity, question, !question.passed, `act-title-${question.id}`, (option) => ctx.actions.stepQuestionAnswer(step.id, option)),
    ),
  );
}

// ---- order --------------------------------------------------------------

function renderOrder(ctx, lesson, activity, enabled) {
  const key = dk(lesson.id, activity.id, 'order');
  const ids = activity.items.map((i) => i.id);
  const submitted = activity.result && activity.result.submitted;
  let order = ctx.draft(key, sameSet(submitted, ids) ? submitted : ids);
  if (activity.passed && sameSet(submitted, ids)) order = submitted;
  if (!sameSet(order, ids)) order = ids;
  const byId = new Map(activity.items.map((i) => [i.id, i]));
  const active = enabled && !activity.passed;

  const move = (index, delta, direction) => {
    const target = index + delta;
    if (!active || target < 0 || target >= order.length) return;
    const next = [...order];
    [next[index], next[target]] = [next[target], next[index]];
    ctx.setDraft(key, next);
    ctx.rerender();
    const buttonId = `ord-${activity.id}-${next[target]}-${direction}`;
    setTimeout(() => {
      const button = document.getElementById(buttonId);
      if (button) button.focus();
    }, 0);
  };

  const result = activity.result;
  return activityShell(
    ctx,
    activity,
    activity.prompt,
    h('p', { class: 'hint', key: 'hint' }, tx(ctx, 'order_hint')),
    h(
      'ol',
      { class: 'order-list', key: 'items' },
      order.map((id, index) => {
        const item = byId.get(id);
        return h(
          'li',
          { key: `ord-${id}`, class: 'order-item' },
          h('span', { class: 'order-text' }, item.text),
          h(
            'span',
            { class: 'order-buttons' },
            h(
              'button',
              {
                type: 'button',
                class: 'btn btn-small',
                id: `ord-${activity.id}-${id}-up`,
                'aria-label': tx(ctx, 'order_up_aria', { text: item.text }),
                'aria-disabled': !active || index === 0 ? 'true' : null,
                onClick: () => move(index, -1, 'up'),
              },
              tx(ctx, 'order_up'),
            ),
            h(
              'button',
              {
                type: 'button',
                class: 'btn btn-small',
                id: `ord-${activity.id}-${id}-down`,
                'aria-label': tx(ctx, 'order_down_aria', { text: item.text }),
                'aria-disabled': !active || index === order.length - 1 ? 'true' : null,
                onClick: () => move(index, 1, 'down'),
              },
              tx(ctx, 'order_down'),
            ),
          ),
        );
      }),
    ),
    feedbackRegion(
      ctx,
      'feedback',
      result
        ? h(
            'div',
            { class: `callout ${result.passed ? 'callout-good' : 'callout-attn'}` },
            h('strong', { class: 'block' }, result.passed ? tx(ctx, 'feedback_correct') : tx(ctx, 'feedback_try_again')),
            result.feedback,
            result.passed ? null : h('span', { class: 'hint block' }, tx(ctx, 'retry_hint')),
          )
        : null,
    ),
    active
      ? h('div', { class: 'row', key: 'row' }, submitButton(ctx, activity, { onClick: () => ctx.actions.lessonAnswer(lesson.id, activity.id, { order }) }))
      : null,
  );
}

// ---- sort ---------------------------------------------------------------

function renderSort(ctx, lesson, activity, enabled) {
  const key = dk(lesson.id, activity.id, 'sort');
  const result = activity.result;
  const stored = (result && result.placements) || {};
  const placements = activity.passed ? stored : ctx.draft(key, stored);
  const active = enabled && !activity.passed;
  const complete = activity.items.every((i) => placements[i.id]);
  const notes = new Map(((result && result.feedback) || []).map((f) => [f.item, f.feedback]));
  return activityShell(
    ctx,
    activity,
    activity.prompt,
    h('p', { class: 'hint', key: 'hint' }, tx(ctx, 'sort_hint')),
    h(
      'ul',
      { class: 'sort-list', key: 'items' },
      activity.items.map((item) => {
        const selectId = `sort-${activity.id}-${item.id}`;
        return h(
          'li',
          { key: `sort-${item.id}`, class: 'sort-row' },
          h('label', { for: selectId, class: 'sort-text' }, item.text),
          h(
            'select',
            {
              id: selectId,
              class: 'input sort-select',
              value: placements[item.id] || '',
              disabled: !active,
              onChange: (event) => {
                ctx.setDraft(key, { ...placements, [item.id]: event.target.value });
                ctx.rerender();
              },
            },
            h('option', { value: '' }, tx(ctx, 'sort_choose')),
            activity.buckets.map((b) => h('option', { value: b.id, key: `b-${b.id}` }, b.label)),
          ),
          notes.has(item.id) ? h('p', { class: 'choice-note', key: 'note' }, notes.get(item.id)) : null,
        );
      }),
    ),
    feedbackRegion(
      ctx,
      'feedback',
      result
        ? h(
            'div',
            { class: `callout ${result.passed ? 'callout-good' : 'callout-attn'}` },
            h('strong', { class: 'block' }, result.passed ? tx(ctx, 'feedback_correct') : tx(ctx, 'feedback_try_again_count')),
            result.passed ? null : tx(ctx, 'sort_count', { right: result.right, total: result.total }),
            result.passed ? null : h('span', { class: 'hint block' }, tx(ctx, 'retry_hint')),
          )
        : null,
    ),
    active
      ? h('div', { class: 'row', key: 'row' }, submitButton(ctx, activity, { disabled: !complete, onClick: () => ctx.actions.lessonAnswer(lesson.id, activity.id, { placements }) }))
      : null,
  );
}

// ---- rule lab -----------------------------------------------------------

function verdictWord(ctx, verdict) {
  return verdict === 'pass' ? tx(ctx, 'rule_pass') : tx(ctx, 'rule_fail');
}

function verdictChip(ctx, verdict) {
  return h('span', { class: `verdict ${verdict === 'pass' ? 'v-P' : 'v-F'}` }, verdictWord(ctx, verdict));
}

function renderRuleOwn(ctx, lesson, activity, enabled) {
  const base = dk(lesson.id, activity.id, 'own');
  const ruleKey = `${base}.rule`;
  const textKey = `${base}.text`;
  const rule = ctx.draft(ruleKey, activity.rules[0].id);
  const text = ctx.draft(textKey, '');
  const local = ctx.local(`rule-${activity.id}`) || { runs: [], error: null };
  const busyKey = `rule-${activity.id}`;
  const same = local.runs.length > 1 && local.runs.every((r) => r.verdict === local.runs[0].verdict && r.reason === local.runs[0].reason);
  return h(
    'div',
    { class: 'rule-own', key: 'own' },
    h('h4', { class: 'rule-own-heading' }, tx(ctx, 'rule_own_heading')),
    h('p', { class: 'hint', key: 'own-intro' }, tx(ctx, 'rule_own_intro')),
    activity.passed
      ? h(
          'div',
          { class: 'field', key: 'sample-pick' },
          h('label', { for: `rule-sample-${activity.id}`, class: 'field-label' }, SAMPLE_LABEL),
          h(
            'select',
            {
              id: `rule-sample-${activity.id}`,
              class: 'input',
              value: '',
              onChange: (event) => {
                const sample = activity.samples.find((s) => s.id === event.target.value);
                if (sample) {
                  ctx.setDraft(textKey, sample.text);
                  ctx.rerender();
                }
              },
            },
            h('option', { value: '' }, tx(ctx, 'sort_choose')),
            activity.samples.map((s) => h('option', { value: s.id, key: `s-${s.id}` }, s.label)),
          ),
        )
      : null,
    h(
      'div',
      { class: 'field', key: 'rule-pick' },
      h('label', { for: `rule-pick-${activity.id}`, class: 'field-label' }, tx(ctx, 'rule_own_rule')),
      h(
        'select',
        {
          id: `rule-pick-${activity.id}`,
          class: 'input',
          value: rule,
          onChange: (event) => {
            ctx.setDraft(ruleKey, event.target.value);
            ctx.rerender();
          },
        },
        activity.rules.map((r) => h('option', { value: r.id, key: `r-${r.id}` }, r.label)),
      ),
    ),
    h(
      'div',
      { class: 'field', key: 'text-field' },
      h('label', { for: `rule-text-${activity.id}`, class: 'field-label' }, tx(ctx, 'rule_own_text')),
      h('textarea', {
        id: `rule-text-${activity.id}`,
        class: 'input',
        rows: 3,
        value: text,
        autocomplete: 'off',
        onInput: (event) => {
          ctx.setDraft(textKey, event.target.value);
          ctx.rerender();
        },
      }),
    ),
    h(
      'div',
      { class: 'row', key: 'buttons' },
      actionButton(ctx, {
        label: tx(ctx, 'rule_own_run'),
        id: `rule-run-${activity.id}`,
        busyKey,
        kind: 'primary',
        disabled: !enabled || !text.trim(),
        onClick: () => ctx.actions.ruleRun(lesson.id, activity.id, rule, text, false),
      }),
      local.runs.length
        ? actionButton(ctx, {
            label: tx(ctx, 'rule_rerun'),
            id: `rule-again-${activity.id}`,
            busyKey,
            disabled: !enabled,
            onClick: () => ctx.actions.ruleRun(lesson.id, activity.id, local.rule, local.text, true),
          })
        : null,
    ),
    h(
      'div',
      { class: 'feedback', key: 'runs', role: 'status', 'aria-live': 'polite' },
      local.error ? h('p', { class: 'bad-text' }, local.error) : null,
      local.runs.length
        ? h(
            'ol',
            { class: 'rule-runs' },
            local.runs.map((r, i) =>
              h('li', { key: `run-${i}` }, h('span', { class: 'rule-run-n' }, fmt(tx(ctx, 'cli_run_label'), { n: i + 1 })), ' ', verdictChip(ctx, r.verdict), ' ', h('span', { class: 'rule-reason' }, r.reason)),
            ),
          )
        : null,
      same ? h('p', { class: 'hint' }, tx(ctx, 'rule_rerun_note')) : null,
    ),
  );
}

function renderRuleLab(ctx, lesson, activity, enabled) {
  const key = dk(lesson.id, activity.id, 'pred');
  const result = activity.result;
  const stored = (result && result.predictions) || {};
  const predictions = activity.passed ? stored : ctx.draft(key, stored);
  const active = enabled && !activity.passed;
  const sampleOf = new Map(activity.samples.map((s) => [s.id, s]));
  const ruleOf = new Map(activity.rules.map((r) => [r.id, r]));
  const details = new Map(((result && result.details) || []).map((d) => [d.key, d]));
  const complete = activity.cases.every((c) => predictions[c.key]);
  return activityShell(
    ctx,
    activity,
    activity.prompt,
    h(
      'ul',
      { class: 'samples', key: 'samples' },
      activity.samples.map((s) => h('li', { key: `sample-${s.id}` }, h('strong', null, s.label), h('pre', { class: 'mono-block sample-text' }, s.text))),
    ),
    h('h4', { class: 'rule-defs-heading', key: 'rules-heading' }, tx(ctx, 'rule_rules_heading')),
    h(
      'ul',
      { class: 'samples', key: 'rules' },
      activity.rules.map((r) => h('li', { key: `rule-def-${r.id}` }, h('strong', null, r.label), r.explain ? h('p', { class: 'hint' }, r.explain) : null)),
    ),
    h('p', { class: 'hint', key: 'hint' }, tx(ctx, 'rule_predict')),
    h(
      'div',
      { class: 'cases', key: 'cases' },
      activity.cases.map((c, index) => {
        const detail = details.get(c.key);
        const name = `case-${activity.id}-${index}`;
        const pick = (verdict, cls) =>
          h(
            'label',
            { class: `seg-opt ${cls}`, key: `v-${verdict}` },
            h('input', {
              type: 'radio',
              name,
              value: verdict,
              checked: predictions[c.key] === verdict,
              disabled: !active,
              onChange: () => {
                ctx.setDraft(key, { ...predictions, [c.key]: verdict });
                ctx.rerender();
              },
            }),
            h('span', null, verdictWord(ctx, verdict)),
          );
        return h(
          'fieldset',
          { class: 'field case-row', key: `case-${c.key}` },
          h('legend', { class: 'field-label' }, `${sampleOf.get(c.sample).label} · ${ruleOf.get(c.rule).label}`),
          h('div', { class: 'seg' }, pick('pass', 'seg-P'), pick('fail', 'seg-F')),
          detail
            ? h('p', { class: 'case-result', key: 'detail' }, h('span', { class: 'hint' }, `${tx(ctx, 'rule_verdict')}: `), verdictChip(ctx, detail.verdict), ' ', detail.reason)
            : null,
        );
      }),
    ),
    feedbackRegion(
      ctx,
      'feedback',
      result
        ? h(
            'div',
            { class: `callout ${result.passed ? 'callout-good' : 'callout-attn'}` },
            h('strong', { class: 'block' }, result.passed ? tx(ctx, 'feedback_correct') : tx(ctx, 'feedback_try_again_count')),
            result.passed ? null : tx(ctx, 'rule_count', { right: result.right, total: result.total }),
            result.passed ? null : h('span', { class: 'hint block' }, tx(ctx, 'retry_hint')),
          )
        : null,
    ),
    active ? h('div', { class: 'row', key: 'row' }, submitButton(ctx, activity, { disabled: !complete, onClick: () => ctx.actions.lessonAnswer(lesson.id, activity.id, { cases: predictions }) })) : null,
    renderRuleOwn(ctx, lesson, activity, lesson.status !== 'locked' && lesson.status !== 'preview'),
  );
}

// ---- reflection ---------------------------------------------------------

function renderReflection(ctx, lesson, activity, enabled) {
  const key = `reflection.${lesson.id}.${activity.id}`;
  const saved = activity.result ? activity.result.text : '';
  const text = ctx.draft(key, saved);
  const words = wordCount(text);
  const id = `reflection-${activity.id}`;
  const unsaved = ctx.hasDraft(key) && text !== saved;
  return activityShell(
    ctx,
    activity,
    h('label', { for: id }, activity.prompt),
    h('textarea', {
      id,
      class: 'input',
      rows: 6,
      value: text,
      disabled: !enabled,
      autocomplete: 'off',
      'aria-describedby': `${id}-count`,
      onInput: (event) => {
        ctx.setDraft(key, event.target.value);
        ctx.rerender();
      },
    }),
    h('p', { class: `hint reflection-count${words >= activity.min_words ? ' is-enough' : ''}`, id: `${id}-count`, key: 'count' }, tx(ctx, 'reflection_words', { words, min: activity.min_words })),
    h(
      'div',
      { class: 'row', key: 'row' },
      enabled
        ? actionButton(ctx, {
            label: tx(ctx, 'reflection_save'),
            busyLabel: tx(ctx, 'reflection_saving'),
            busyKey: `ans-${activity.id}`,
            id: `submit-${activity.id}`,
            kind: 'primary',
            disabled: !text.trim() || !unsaved,
            onClick: () => ctx.actions.saveReflection(lesson.id, activity.id, key, text),
          })
        : null,
      h('span', { class: 'hint', role: 'status', 'aria-live': 'polite', key: 'saved' }, !unsaved && activity.result ? tx(ctx, 'reflection_saved') : ''),
    ),
  );
}

// ---- CLI activities -----------------------------------------------------

function cliFiles(ctx, activity) {
  return h(
    'div',
    { class: 'cli-files', key: 'files' },
    h('h4', null, tx(ctx, 'cli_files_heading')),
    h('ul', { class: 'file-names' }, (activity.files || []).map((name) => h('li', { key: `file-${name}` }, h('code', null, name)))),
  );
}

function renderCompare(ctx, lesson, activity, enabled) {
  const practice = activity.type === 'cli_practice';
  const active = enabled && !activity.passed;
  return activityShell(
    ctx,
    activity,
    tx(ctx, practice ? 'practice_heading' : 'cli_runs_heading'),
    h('p', { class: 'hint', key: 'note' }, tx(ctx, practice ? 'practice_note' : 'cli_runs_note')),
    cliFiles(ctx, activity),
    h(
      'div',
      { class: 'compare', key: 'outputs' },
      activity.outputs.map((o) =>
        h(
          'section',
          { class: `compare-col${o.done ? ' is-done' : ''}`, key: `out-${o.n}`, 'aria-label': tx(ctx, 'cli_run_label', { n: o.n }) },
          practice ? null : h('h4', null, tx(ctx, 'cli_run_label', { n: o.n })),
          o.done ? h('pre', { class: 'mono-block compare-text' }, o.text) : h('p', { class: 'hint' }, tx(ctx, practice ? 'practice_empty' : 'cli_run_empty')),
        ),
      ),
    ),
    activity.all_saved ? h('p', { class: 'callout callout-good', key: 'saved', role: 'status' }, tx(ctx, practice ? 'practice_done' : 'cli_runs_done')) : null,
    h(
      'div',
      { class: 'compare-question', key: 'question' },
      h('h4', { id: `q-title-${activity.id}` }, activity.question.prompt),
      h('div', null, ...renderChoiceBody(ctx, lesson, activity, activity.question, active && activity.all_saved, `q-title-${activity.id}`)),
    ),
  );
}

function renderDemo(ctx, lesson, activity, enabled) {
  const active = enabled && !activity.passed;
  const runs = activity.runs || [];
  const scan = activity.scan || [];
  return activityShell(
    ctx,
    activity,
    tx(ctx, 'demo_run'),
    cliFiles(ctx, activity),
    h(
      'div',
      { class: 'row', key: 'row' },
      actionButton(ctx, {
        label: runs.length ? tx(ctx, 'demo_rerun') : tx(ctx, 'demo_run'),
        busyLabel: tx(ctx, 'demo_running'),
        busyKey: `ans-${activity.id}`,
        id: `submit-${activity.id}`,
        kind: 'primary',
        disabled: !active || !activity.checker_exists,
        onClick: () => ctx.actions.lessonAnswer(lesson.id, activity.id, {}),
      }),
      !activity.checker_exists ? h('span', { class: 'hint' }, tx(ctx, 'demo_waiting')) : null,
    ),
    activity.checker_exists
      ? h(
          'div',
          { class: 'demo-scan', key: 'scan' },
          h('h4', null, tx(ctx, 'demo_scan_heading')),
          scan.length
            ? h('ul', { class: 'plain-list' }, scan.map((s, i) => h('li', { key: `scan-${i}` }, s.message)))
            : h('p', { class: 'hint' }, tx(ctx, 'demo_scan_ok')),
        )
      : null,
    runs.length
      ? h(
          'div',
          { class: 'demo-runs', key: 'runs' },
          runs.map((run, i) => h('section', { key: `run-${i}`, class: 'demo-run' }, h('h4', null, tx(ctx, i === 0 ? 'demo_list_first' : 'demo_list_second')), resultTables(run))),
        )
      : null,
    feedbackRegion(
      ctx,
      'feedback',
      activity.identical === true
        ? h('p', { class: 'callout callout-good' }, tx(ctx, 'demo_identical'))
        : activity.identical === false
          ? h('p', { class: 'callout callout-attn' }, tx(ctx, 'demo_different'))
          : null,
    ),
  );
}

// ---- placement ----------------------------------------------------------

function renderPlacementItem(ctx, lesson, item, open) {
  const key = `lesson.${lesson.id}.place.${item.id}`;
  const result = item.result;
  const selected = ctx.draft(key, result ? result.chosen : null);
  const chosen = result ? item.options.find((o) => o.id === result.chosen) : null;
  const decided = result && result.decision;
  return h(
    'fieldset',
    { class: 'field choice placement-item', key: `place-${item.id}` },
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
              name: `place-${item.id}`,
              value: o.id,
              checked: selected === o.id,
              disabled: !open || Boolean(result),
              onChange: () => {
                ctx.setDraft(key, o.id);
                ctx.rerender();
              },
            }),
            h('span', null, o.text),
          ),
        ),
      ),
    ),
    h(
      'div',
      { class: 'feedback', key: 'feedback', role: 'status', 'aria-live': 'polite' },
      result
        ? h(
            'div',
            { class: `callout ${result.passed ? 'callout-good' : 'callout-attn'}` },
            chosen ? h('span', { class: 'block choice-chosen' }, chosen.text) : null,
            result.feedback,
            !result.passed ? h('span', { class: 'block hint' }, tx(ctx, 'placement_wrong')) : null,
            result.passed && result.offer_skip && !decided
              ? h(
                  'div',
                  { class: 'placement-offer', key: 'offer' },
                  h('p', null, tx(ctx, 'placement_offer', { title: item.lesson_title })),
                  h(
                    'div',
                    { class: 'row' },
                    actionButton(ctx, { label: tx(ctx, 'placement_accept'), id: `accept-${item.id}`, busyKey: `place-${item.id}`, kind: 'primary', disabled: !open, onClick: () => ctx.actions.placementSkip(item.id, true) }),
                    actionButton(ctx, { label: tx(ctx, 'placement_decline'), id: `decline-${item.id}`, busyKey: `place-${item.id}`, disabled: !open, onClick: () => ctx.actions.placementSkip(item.id, false) }),
                  ),
                )
              : null,
            decided === 'accepted' ? h('strong', { class: 'block' }, tx(ctx, 'placement_skip_done')) : null,
            decided === 'declined' ? h('strong', { class: 'block' }, tx(ctx, 'placement_declined')) : null,
          )
        : null,
    ),
    !result && open
      ? h(
          'div',
          { class: 'row', key: 'row' },
          actionButton(ctx, {
            label: tx(ctx, 'submit'),
            busyLabel: tx(ctx, 'submitting'),
            busyKey: `place-${item.id}`,
            id: `place-submit-${item.id}`,
            kind: 'primary',
            disabled: !selected,
            onClick: () => ctx.actions.placementAnswer(item.id, selected),
          }),
        )
      : null,
  );
}

function renderPlacement(ctx, lesson) {
  if (!lesson.placement || !lesson.placement.length) return null;
  const open = lesson.status === 'active';
  return section(
    'placement',
    tx(ctx, 'placement_heading'),
    h('p', { class: 'hint', key: 'hint' }, tx(ctx, 'placement_hint')),
    lesson.placement.map((item) => renderPlacementItem(ctx, lesson, item, open)),
  );
}

// ---- sources and related ------------------------------------------------

function sourceLink(ctx, source, prefix) {
  if (source.ref.startsWith('kit:')) {
    return h(
      'button',
      { type: 'button', class: 'btn btn-small', 'aria-label': `${tx(ctx, 'kit_open')}: ${source.label}`, onClick: () => ctx.actions.openKit(source.ref, source.label) },
      tx(ctx, 'kit_open'),
    );
  }
  return h(
    'a',
    { href: source.ref, target: '_blank', rel: 'noopener noreferrer', class: 'source-link', 'aria-label': `${tx(ctx, 'kit_open')}: ${source.label}` },
    prefix || source.label,
  );
}

function renderSources(ctx, lesson) {
  const primary = lesson.primary_source;
  return [
    primary
      ? section(
          'primary',
          tx(ctx, 'primary_heading'),
          h(
            'div',
            { class: 'primary-source' },
            h('p', null, h('strong', null, primary.label), ' ', sourceLink(ctx, primary, tx(ctx, 'kit_open'))),
            h('p', { class: 'hint' }, primary.why),
          ),
        )
      : null,
    lesson.sources && lesson.sources.length
      ? section(
          'sources',
          tx(ctx, 'sources_heading'),
          h('ul', { class: 'source-list' }, lesson.sources.map((s, i) => h('li', { key: `src-${i}` }, h('span', { class: 'source-label' }, s.label), ' ', sourceLink(ctx, s, tx(ctx, 'kit_open'))))),
        )
      : null,
  ];
}

function renderRelated(ctx, lesson) {
  const related = lesson.related || { lessons: [], glossary: [] };
  if (!related.lessons.length && !related.glossary.length) return null;
  return section(
    'related',
    tx(ctx, 'related_heading'),
    related.lessons.length
      ? h(
          'ul',
          { class: 'related-list', key: 'lessons' },
          related.lessons.map((l) =>
            h(
              'li',
              { key: `rl-${l.id}` },
              h('button', { type: 'button', class: 'btn btn-quiet', onClick: () => ctx.actions.openCourseItem('lesson', l.id) }, tx(ctx, 'open_lesson', { title: l.title })),
            ),
          ),
        )
      : null,
    related.glossary.length
      ? h(
          'ul',
          { class: 'related-terms', key: 'terms' },
          related.glossary.map((term) => h('li', { key: `rt-${term}` }, h('button', { type: 'button', class: 'btn btn-small', onClick: () => ctx.actions.openGlossary(term) }, term))),
        )
      : null,
  );
}

// ---- the lesson page ----------------------------------------------------

function renderActivity(ctx, lesson, activity) {
  const enabled = lesson.status === 'active';
  switch (activity.type) {
    case 'choice':
      return renderChoice(ctx, lesson, activity, enabled);
    case 'order':
      return renderOrder(ctx, lesson, activity, enabled);
    case 'sort':
      return renderSort(ctx, lesson, activity, enabled);
    case 'rule_lab':
      return renderRuleLab(ctx, lesson, activity, enabled);
    case 'reflection':
      return renderReflection(ctx, lesson, activity, enabled);
    case 'cli_compare':
    case 'cli_practice':
      return renderCompare(ctx, lesson, activity, enabled);
    case 'cli_demo':
      return renderDemo(ctx, lesson, activity, enabled);
    default:
      return null;
  }
}

function renderLessonActions(ctx, lesson) {
  if (lesson.status === 'preview') return null; // reading ahead: nothing to complete or skip
  if (lesson.status === 'active') {
    return h(
      'div',
      { class: 'lesson-actions', key: 'actions' },
      h(
        'div',
        { class: 'row' },
        actionButton(ctx, {
          label: tx(ctx, 'continue'),
          busyLabel: tx(ctx, 'continuing'),
          busyKey: 'lesson-continue',
          id: 'lesson-continue',
          kind: 'primary',
          disabled: !lesson.can_complete,
          onClick: () => ctx.actions.completeLesson(lesson.id),
        }),
        lesson.skippable && lesson.can_skip
          ? actionButton(ctx, { label: tx(ctx, 'skip_lesson'), id: 'lesson-skip', busyKey: 'lesson-skip', onClick: () => ctx.actions.skipLesson(lesson.id) })
          : null,
      ),
      lesson.can_complete ? null : h('p', { class: 'hint', id: 'continue-hint' }, tx(ctx, 'continue_disabled_hint')),
    );
  }
  const current = ctx.state.current_item;
  return h(
    'div',
    { class: 'lesson-actions', key: 'actions' },
    h('p', { class: 'hint' }, lesson.status === 'skipped' ? tx(ctx, 'skipped_note') : tx(ctx, 'done_note')),
    current ? h('div', { class: 'row' }, actionButton(ctx, { label: tx(ctx, 'continue'), id: 'lesson-back', kind: 'primary', onClick: () => ctx.actions.openCourseItem(current.kind, current.id) })) : null,
  );
}

// A row of pips under the title: one per activity, filled as each is passed.
function renderLessonProgress(ctx, lesson) {
  const total = lesson.activities.length;
  if (!total) return null;
  const done = lesson.activities.filter((a) => a.passed).length;
  return h(
    'div',
    { class: `lesson-progress${done === total ? ' is-complete' : ''}`, key: 'progress' },
    h('span', { class: 'pips', 'aria-hidden': 'true' }, lesson.activities.map((a) => h('span', { key: `pip-${a.id}`, class: `pip${a.passed ? ' is-on' : ''}` }))),
    h('span', { class: 'lesson-progress-text' }, tx(ctx, 'progress_label', { done, total })),
  );
}

// Shown on a lesson that is open to read ahead: the exercises are off and nothing is saved. Before setup it points
// to setup; after setup it names the item still to do and leads back to it.
function renderPreviewNote(ctx, lesson) {
  const gate = ctx.state.settings ? ctx.state.settings.text.setup_gate : null;
  if (!gate) return null;
  if (!ctx.state.preflight.passed) {
    return h(
      'div',
      { class: 'callout callout-attn', id: 'preview-note', key: 'preview-note', role: 'status' },
      h('p', null, gate.preview_lesson),
      h('div', { class: 'row' }, actionButton(ctx, { label: gate.button, id: 'preview-setup', onClick: () => ctx.actions.openSetup() })),
    );
  }
  const held = lesson.held_by;
  if (!held) return null;
  return h(
    'div',
    { class: 'callout callout-attn', id: 'preview-note', key: 'preview-note', role: 'status' },
    h('p', null, gate.preview_lesson_after.replace('{title}', held.title)),
    h('div', { class: 'row' }, actionButton(ctx, { label: gate.preview_back, id: 'preview-back', onClick: () => ctx.actions.openCourseItem(held.kind, held.id) })),
  );
}

export function renderLesson(ctx) {
  const { lesson, lessonId } = ctx;
  const lessons = ctx.state.course.filter((i) => i.kind === 'lesson');
  const entry = lessons.find((i) => i.id === lessonId);
  if (!lesson) {
    return h(
      'article',
      { class: 'step-page lesson-page', key: `lesson-${lessonId}` },
      h('h1', { id: 'step-heading', tabindex: -1 }, entry ? entry.title : ''),
      h('p', { class: 'hint', role: 'status' }, tx(ctx, 'lesson_loading')),
    );
  }
  const number = lessons.findIndex((i) => i.id === lessonId) + 1;
  return h(
    'article',
    { class: 'step-page lesson-page', key: `lesson-${lessonId}` },
    h('p', { class: 'kicker' }, `${tx(ctx, 'kicker', { n: number, total: lessons.length })} · ${tx(ctx, 'minutes', { minutes: lesson.minutes })}`),
    h('h1', { id: 'step-heading', tabindex: -1 }, lesson.title),
    renderLessonProgress(ctx, lesson),
    lesson.status === 'preview' ? renderPreviewNote(ctx, lesson) : null,
    lesson.id === 'mission'
      ? h('div', { class: 'callout mission-box', key: 'mission' }, h('strong', { class: 'block' }, tx(ctx, 'mission_label')), lesson.mission)
      : null,
    h('div', { class: 'callout callout-good win-box', key: 'win' }, h('strong', { class: 'block' }, tx(ctx, 'win_label')), lesson.win),
    h('div', { class: 'markdown lesson-body', key: 'body' }, ...renderMarkdown(lesson.body)),
    lesson.activities.length
      ? section('activities', tx(ctx, 'activities_heading'), lesson.activities.map((a) => renderActivity(ctx, lesson, a)))
      : null,
    renderPlacement(ctx, lesson),
    renderLessonActions(ctx, lesson),
    ...renderSources(ctx, lesson),
    renderRelated(ctx, lesson),
  );
}

// ---- lesson CLI header and footer ---------------------------------------

export function renderLessonTermHead(ctx, lesson, activity) {
  const { terminal } = ctx.state;
  const cli = activity.cli;
  const mine = Boolean(cli.started) && terminal.running;
  const gate = ctx.state.settings ? ctx.state.settings.text.setup_gate : null;
  if (!ctx.state.preflight.passed && gate) {
    // Hands-on work needs setup: no CLI controls here, only the reason and a way to setup.
    return [
      h(
        'div',
        { class: 'term-title-row', key: 'title' },
        h('h2', { class: 'term-label' }, terminal.label || 'Your CLI'),
        h('span', { class: `term-status${mine ? ' is-on' : ''}`, role: 'status' }, terminalStatus(ctx, mine)),
      ),
      h(
        'div',
        { key: 'needs-setup' },
        h('p', { class: 'callout callout-attn', id: 'cli-needs-setup', role: 'status' }, gate.cli_exercise),
        h('div', { class: 'row term-actions' }, actionButton(ctx, { label: gate.button, id: 'cli-setup-go', onClick: () => ctx.actions.openSetup() })),
      ),
    ];
  }
  const readOnly = lesson.status !== 'active' || activity.passed;
  const finished = Boolean(activity.all_saved);
  const busyKey = (name) => `lcli-${name}`;
  return [
    h(
      'div',
      { class: 'term-title-row', key: 'title' },
      h('h2', { class: 'term-label' }, terminal.label || 'Your CLI'),
      h('span', { class: `term-status${mine ? ' is-on' : ''}`, role: 'status' }, terminalStatus(ctx, mine)),
    ),
    h(
      'div',
      { class: 'term-line-block', key: 'line' },
      h('span', { class: 'hint block' }, tx(ctx, 'cli_line_prefix')),
      h('code', { class: 'term-line' }, cli.line),
      h('span', { class: 'hint block' }, tx(ctx, 'cli_folder_prefix'), cli.folder_label),
    ),
    readOnly
      ? h(
          'div',
          { key: 'readonly' },
          h('p', { class: 'hint' }, tx(ctx, 'cli_readonly')),
          mine
            ? h(
                'div',
                { class: 'row term-actions' },
                actionButton(ctx, {
                  label: tx(ctx, 'cli_stop'),
                  busyLabel: tx(ctx, 'cli_stopping'),
                  busyKey: busyKey('stop'),
                  id: 'cli-stop',
                  onClick: () => ctx.actions.lessonCliStop(lesson.id, activity.id),
                }),
              )
            : null,
        )
      : h(
          'div',
          { class: 'row term-actions', key: 'actions' },
          actionButton(ctx, {
            label: tx(ctx, 'cli_start'),
            busyLabel: tx(ctx, 'cli_starting'),
            busyKey: busyKey('start'),
            id: 'cli-start',
            kind: mine ? null : 'primary',
            disabled: mine || finished,
            onClick: () => ctx.actions.lessonCliStart(lesson.id, activity.id),
          }),
          actionButton(ctx, {
            label: tx(ctx, 'cli_send'),
            busyLabel: tx(ctx, 'cli_sending'),
            busyKey: busyKey('send'),
            id: 'cli-send',
            kind: mine ? 'primary' : null,
            disabled: !mine,
            onClick: () => ctx.actions.lessonCliSend(lesson.id, activity.id),
          }),
          actionButton(ctx, {
            label: tx(ctx, 'cli_stop'),
            busyLabel: tx(ctx, 'cli_stopping'),
            busyKey: busyKey('stop'),
            id: 'cli-stop',
            disabled: !mine,
            onClick: () => ctx.actions.lessonCliStop(lesson.id, activity.id),
          }),
          actionButton(ctx, {
            label: tx(ctx, 'cli_retry'),
            busyLabel: tx(ctx, 'cli_starting'),
            busyKey: busyKey('retry'),
            id: 'cli-retry',
            disabled: finished || (!mine && !cli.started),
            onClick: () => ctx.actions.lessonCliRetry(lesson.id, activity.id),
          }),
        ),
    !readOnly && cli.sent && mine
      ? h('p', { class: 'hint', key: 'sent' }, tx(ctx, 'cli_sent'))
      : !readOnly && mine
        ? h('p', { class: 'hint', key: 'ready' }, tx(ctx, 'cli_ready'))
        : null,
  ];
}

function terminalStatus(ctx, mine) {
  const { terminal } = ctx.state;
  if (mine) return 'Your CLI is running.';
  if (terminal.exit_code !== null && terminal.exit_code !== undefined) return `Your CLI has stopped (exit code ${terminal.exit_code}).`;
  return 'Your CLI is not running.';
}
