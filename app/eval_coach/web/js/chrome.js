// The app frame: theme, sidebar width, the reading-progress bar and the small celebration on a pass.
// Nothing here talks to the server. Preferences live in this browser only.

const THEME_KEY = 'eval-coach-theme';
const NAV_KEY = 'eval-coach-nav';
const ROOMY_PX = 1400;
const root = document.documentElement;

function save(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage can be blocked; the choice then lasts until the page reloads.
  }
}

function saved(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

// ---- theme ----------------------------------------------------------------

export function getTheme() {
  return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  root.classList.add('theme-switching');
  root.setAttribute('data-theme', next);
  save(THEME_KEY, next);
  window.setTimeout(() => root.classList.remove('theme-switching'), 350);
  return next;
}

// ---- text size ------------------------------------------------------------

// The slider's range, size and live apply come from js/theme.js, so they are in place before the first paint.
export const textRange = () => window.EvalCoachDisplay.range();
export const getTextSize = () => window.EvalCoachDisplay.size();
export const setTextSize = (value) => window.EvalCoachDisplay.setSize(value);
export const textSizeStep = () => window.EvalCoachDisplay.step;

// After "Reset app configuration": text size, theme and sidebar choices go back to their defaults.
export const resetDisplayChoices = () => window.EvalCoachDisplay.resetChoices();

// ---- sidebar --------------------------------------------------------------

// On wide screens the course list is a sidebar that is always open. On narrow ones it is a drop-down.
// "Narrow" is decided in js/theme.js from the window width at the current text size.
export const isWide = () => document.documentElement.getAttribute('data-layout') !== 'narrow';

export function navCollapsed() {
  return root.getAttribute('data-nav') === 'collapsed';
}

export function toggleNav() {
  const next = navCollapsed() ? 'expanded' : 'collapsed';
  root.setAttribute('data-nav', next);
  save(NAV_KEY, next);
  return next;
}

let wasWide = null;

export function syncCourseNav() {
  const details = document.querySelector('details.course-nav');
  const wide = isWide();
  if (details) {
    if (wide) details.open = true;
    else if (wasWide !== false) details.open = false;
  }
  wasWide = wide;
}

// ---- reading progress -----------------------------------------------------

export function updateReadProgress() {
  const scroller = document.getElementById('col-left');
  const bar = document.querySelector('#read-progress span');
  if (!scroller || !bar) return;
  const travel = scroller.scrollHeight - scroller.clientHeight;
  const share = travel > 8 ? Math.min(1, Math.max(0, scroller.scrollTop / travel)) : 0;
  bar.style.transform = `scaleX(${share})`;
}

// ---- celebration ----------------------------------------------------------

const CONFETTI = ['#8fbf00', '#d6ff3e', '#ffb224', '#18b47b', '#3aa0ff'];

// A short burst of confetti from an element. It is decoration only: it takes no clicks and is skipped
// when the participant asks for reduced motion.
export function celebrate(selector) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  window.requestAnimationFrame(() => {
    const target = selector ? document.querySelector(selector) : null;
    const box = target ? target.getBoundingClientRect() : null;
    if (!box || (box.width === 0 && box.height === 0)) return;
    const originX = box.left + Math.min(box.width / 2, 60);
    const originY = box.top + box.height / 2;
    const layer = document.createElement('div');
    layer.className = 'confetti';
    layer.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 26; i += 1) {
      const piece = document.createElement('i');
      const angle = (Math.PI * 2 * i) / 26 + Math.random() * 0.5;
      const reach = 50 + Math.random() * 90;
      piece.style.left = `${originX}px`;
      piece.style.top = `${originY}px`;
      piece.style.background = CONFETTI[i % CONFETTI.length];
      if (i % 3 === 0) piece.style.borderRadius = '50%';
      layer.appendChild(piece);
      if (piece.animate) {
        piece.animate(
          [
            { transform: 'translate(0, 0) rotate(0deg) scale(1)', opacity: 1 },
            {
              transform: `translate(${Math.cos(angle) * reach}px, ${Math.sin(angle) * reach + 70}px) rotate(${Math.random() * 540 - 270}deg) scale(0.5)`,
              opacity: 0,
            },
          ],
          { duration: 800 + Math.random() * 500, easing: 'cubic-bezier(0.15, 0.7, 0.3, 1)', fill: 'forwards' },
        );
      }
    }
    document.body.appendChild(layer);
    window.setTimeout(() => layer.remove(), 1500);
  });
}

// ---- wiring ---------------------------------------------------------------

export function initChrome(rerender) {
  const scroller = document.getElementById('col-left');
  if (scroller) scroller.addEventListener('scroll', updateReadProgress, { passive: true });
  let roomy = window.innerWidth >= ROOMY_PX;
  window.addEventListener('resize', () => {
    const nowRoomy = window.innerWidth >= ROOMY_PX;
    // Follow the window only until the participant has chosen a sidebar width.
    if (nowRoomy !== roomy && !saved(NAV_KEY)) root.setAttribute('data-nav', nowRoomy ? 'expanded' : 'collapsed');
    roomy = nowRoomy;
    syncCourseNav();
    updateReadProgress();
    rerender();
  });
  // A new text size can change the layout, so the course list and the screen follow it at once.
  window.addEventListener('eval-coach:text-size', () => {
    syncCourseNav();
    updateReadProgress();
    rerender();
  });
}
