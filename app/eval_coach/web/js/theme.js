// Runs before the first paint so the saved theme, sidebar width and text size apply at once.
// Light is the default theme. A plain script (not a module) so it blocks rendering.
// It also holds the display logic the app shares: the text size range, and which layout fits the window.
(function () {
  var root = document.documentElement;
  var THEME_KEY = 'eval-coach-theme';
  var NAV_KEY = 'eval-coach-nav';
  var TEXT_KEY = 'eval-coach-text-size';
  var DEFAULT_SIZE = 100;
  var STEP = 5;
  var DESKTOP = { min: 80, max: 150 };
  var PHONE = { min: 90, max: 130 };

  function read(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null; // storage can be blocked
    }
  }

  function write(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      // the choice then lasts until the page reloads
    }
  }

  // A phone is a touch device whose shorter screen side is 600 pixels or less. A narrow desktop window is not one.
  function isPhone() {
    try {
      return window.matchMedia('(pointer: coarse)').matches && Math.min(window.screen.width, window.screen.height) <= 600;
    } catch (err) {
      return false;
    }
  }

  function range() {
    return isPhone() ? PHONE : DESKTOP;
  }

  // Anything that is not a number is 100. A number outside the range becomes the nearest limit.
  function clamp(value) {
    if (value === null || value === undefined || String(value).trim() === '') return DEFAULT_SIZE;
    var n = Number(value);
    if (!isFinite(n)) return DEFAULT_SIZE;
    var r = range();
    return Math.min(r.max, Math.max(r.min, Math.round(n / STEP) * STEP));
  }

  var size = DEFAULT_SIZE;

  // The layout is the window width at the current text size: a larger size switches to the compact form sooner.
  function layout() {
    var width = window.innerWidth / (size / 100);
    var name = width <= 820 ? 'narrow' : width <= 1100 ? 'mid' : 'wide';
    if (root.getAttribute('data-layout') !== name) root.setAttribute('data-layout', name);
    return name;
  }

  // The size is an attribute that styles.css turns into a root font size (one rule per step), so no inline style is needed.
  function apply() {
    root.setAttribute('data-text-size', String(size));
    layout();
  }

  function announce() {
    try {
      window.dispatchEvent(new CustomEvent('eval-coach:text-size', { detail: { size: size } }));
    } catch (err) {
      // an older browser without CustomEvent only misses the terminal refit
    }
  }

  function setSize(value) {
    size = clamp(value);
    apply();
    write(TEXT_KEY, String(size));
    announce();
    return size;
  }

  function defaultNav() {
    return window.innerWidth >= 1400 ? 'expanded' : 'collapsed';
  }

  // After "Reset app configuration": forget every display choice kept in this browser.
  function resetChoices() {
    try {
      window.localStorage.removeItem(THEME_KEY);
      window.localStorage.removeItem(NAV_KEY);
      window.localStorage.removeItem(TEXT_KEY);
    } catch (err) {
      // nothing stored can be cleared; the defaults still apply to this page
    }
    root.setAttribute('data-theme', 'light');
    root.setAttribute('data-nav', defaultNav());
    size = DEFAULT_SIZE;
    apply();
    announce();
  }

  var theme = 'light';
  var nav = null;
  var savedTheme = read(THEME_KEY);
  if (savedTheme === 'dark' || savedTheme === 'light') theme = savedTheme;
  var savedNav = read(NAV_KEY);
  if (savedNav === 'collapsed' || savedNav === 'expanded') nav = savedNav;
  root.setAttribute('data-theme', theme);
  root.setAttribute('data-nav', nav || defaultNav());
  if (isPhone()) root.setAttribute('data-phone', '');
  size = clamp(read(TEXT_KEY));
  apply();
  window.addEventListener('resize', layout);

  window.EvalCoachDisplay = {
    isPhone: isPhone,
    range: range,
    size: function () {
      return size;
    },
    setSize: setSize,
    layout: layout,
    resetChoices: resetChoices,
    defaultSize: DEFAULT_SIZE,
    step: STEP,
  };
})();
