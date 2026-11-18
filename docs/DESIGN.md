# eval-coach design system: "Graphite and Lime"

Status as of 2026-11-18 (the system itself was set on 2026-11-10; components added since for the Series map, Parts 1 and 2, the setup wizard and the AI window lesson are in section 6). This replaces the earlier "Midnight, linen and brass" restyle, which kept the old layout and a navy, cream and gold palette and was rejected as too close to the original. This version changes the palette, the typography, the page structure and the interaction design, and adds a dark theme. Light is the default.

The HTTP contract, the copy and the element ids are unchanged. The markup changed in the sidebar, the course list and the lesson header, and the interface tests in `tests/frontend/ui.spec.js` cover the new behaviour.

## 1. Constraints

- **Offline, no build step, standard library only.** No web fonts and no CSS framework. The system is one hand-written stylesheet and two small scripts.
- **Fonts must ship with Windows 11.** Segoe UI Variable (Display, Text and Small optical sizes) and Cascadia Mono. Other systems fall back to their own UI and mono fonts.
- **The console stays dark in both themes** so CLI colours stay legible.
- **State is never colour alone.** Verdicts carry a glyph and a word, and status words stay in the page for screen readers when the sidebar is collapsed.
- **Reduced motion is honoured.** Every animation and transition is off, and the confetti does not run.
- **Nothing leaves the machine.** Theme, sidebar and text size choices are kept in this browser's `localStorage` and are never sent to the server.

## 2. Research summary

Sources were reviewed on 2026-11-10. Most are practitioner writing. The two peer-reviewed items are marked.

**What makes product UI read as premium.** The recurring advice across write-ups of Linear, Stripe and Vercel is restraint: tinted neutrals instead of pure grey, hairline borders, at most two accent colours, one typeface used with confidence, and removing anything that does not earn its place. Density is not the same as quality. Sources: [Mantlr](https://mantlr.com/blog/stripe-linear-vercel-premium-ui), [opendesigner.io](https://opendesigner.io/fr/blog/recreating-stripe-linear-vercel-design-systems-with-design-md), [Merge Rocks](https://merge.rocks/blog/7-best-designed-edtech-platforms-weve-seen-so-far).

**Light and dark themes.** Components should read semantic tokens, and a dark theme should be designed, not inverted: lighter and slightly less saturated accents on dark surfaces, elevation shown by lighter surfaces, and AA contrast on every surface. The common pattern is a default plus a manual override. Sources: [muz.li dark mode guide](https://muz.li/blog/dark-mode-design-systems-a-complete-guide-to-patterns-tokens-and-hierarchy/), [saasui.design](https://www.saasui.design/blog/saas-dark-mode-theming-ux-patterns), [UXPin](https://www.uxpin.com/studio/blog/color-consistency-design-systems/).

**Typography.** A muz.li survey of 2,190 admired sites found that 60% set headline and body in one family, and that a mono face is the usual second voice in product UI. Sources: [muz.li font pairings](https://muz.li/blog/font-pairings-2026/), [Gleam Studio](https://www.gleamstudio.design/blog-post/font-trends-2026). Microsoft's guidance is to name Segoe UI Variable's optical sizes explicitly in CSS: [Microsoft typography](https://learn.microsoft.com/windows/apps/design/style/typography), [tigeroakes.com](https://tigeroakes.com/posts/segoe-ui-variable/).

**Engagement.** A 2026 Scientific Reports experiment (240 participants, peer reviewed) found visual progress indicators correlated with better learning performance, and that micro-assessments inside the content raise engagement. A 2026 Springer study (peer reviewed) found prompts that make learners judge their own progress improved the accuracy of that judgement. Case studies of Duolingo describe breaking a goal into visible stages, celebrating each small win, and keeping feedback on mistakes gentle. Sources: [Nature Scientific Reports](https://www.nature.com/articles/s41598-026-41429-y), [Springer](https://link.springer.com/article/10.1007/s10639-026-14082-1), [UX Planet](https://uxplanet.org/ux-and-gamification-in-duolingo-40d55ee09359), [925 Studios](https://www.925studios.co/blog/duolingo-design-breakdown).

**Learning platforms.** Adult learning products favour a clean, professional interface with the learner kept in the loop. Sources: [The Finch](https://thefinch.design/edtech-app-ux-2026/), [Shakuro](https://shakuro.com/blog/e-learning-app-design-and-how-to-make-it-better), [Onix](https://onix-systems.com/blog/education-app-design-trends).

## 3. Decisions

| Area | Before | Now | Why |
|---|---|---|---|
| Palette | Navy, cream and gold | Cool graphite neutrals, one lime accent (`#b8db35` light, `#d6ff3e` dark) with dark ink on it, a lime gradient for progress and wins only | A clear break from the old look; one accent plus one reserved gradient follows the restraint the research points to. Lime is a fill colour, so text and focus on the light theme use a deeper olive |
| Themes | Light only | Light (default) and dark, switched from the sidebar and remembered | Requested; the dark theme has its own surfaces, borders and lighter accents |
| Headings | Serif | Segoe UI Variable Display, bold, tight tracking | One family used with confidence; reads as a product, not a document |
| Labels | Small caps sans | Cascadia Mono, uppercase | A second voice that ties the page to the console |
| Navigation | A bar across the top with a drop-down course list | A sidebar: brand, a progress ring, the whole course as a timeline, and the tools. It collapses to a rail of marks, and becomes a top bar under 821px | The course map is always in view, which is the best-evidenced engagement feature |
| Progress | A count in the top bar | Ring with percent, timeline marks, a reading-progress line over the page, and a pip per activity in each lesson | Progress is visible at course, lesson and page level |
| Feedback | Text changes | Confetti on a newly passed activity or step check, a pass medallion, pips filling, staggered entrances, a beacon on the current item | Small wins are marked; mistakes stay calm |
| Instructions | Plain lists | "What to do" as numbered cards, "Why this matters" as a quiet list | Breaks up the wall of text |
| Activities | Unnumbered cards | Numbered cards that light up while in use and turn to a check when passed | Shows how many there are and where you are |
| Console | A light code box above a dark terminal | A dock: status pill, the typed line shown as a prompt, the terminal as a window | The exact line reads as something that will be typed |

## 4. Tokens

Tokens are defined on `:root` for light and redefined under `:root[data-theme="dark"]`. Components use tokens only.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f5f5f9` | `#0c0c13` | Page |
| `--side` | `#fbfbfe` | `#101018` | Sidebar |
| `--surface` | `#ffffff` | `#16161f` | Cards |
| `--sunken` | `#f0f0f6` | `#111119` | Code blocks, hover fills |
| `--ink` | `#12131f` | `#eeeef6` | Text |
| `--ink-soft` | `#4d5066` | `#a9abc0` | Secondary text |
| `--ink-faint` | `#62657b` | `#8f92a8` | Hints and labels |
| `--rule` | `#e3e3ee` | `#272735` | Hairlines |
| `--accent` | `#4f6a00` | `#d6ff3e` | Links, focus, current position (text on light needs the deeper olive) |
| `--accent-solid` / hover | `#b8db35` / `#c9e75c` | `#d6ff3e` / `#e4ff7a` | Primary buttons, done marks, selected states |
| `--accent-ink` | `#11160a` | `#11160a` | Text on `--accent-solid` |
| `--accent-tint` | `#f2f7dc` | `#1d2308` | Selected and highlighted fills |
| `--pass` / tint | `#0b7350` / `#daf5e8` | `#4ddc9c` / `#0f2a20` | PASS |
| `--fail` / tint | `#c01c44` / `#fde6eb` | `#ff8097` / `#34151f` | FAIL |
| `--nc` / tint | `#555b6e` / `#ebecf2` | `#a9abc0` / `#23232f` | NOT CHECKED |
| `--attn` / tint | `#8f5400` / `#fff0d4` | `#ffc45c` / `#2f2510` | Attention |
| `--term-bg` | `#101018` | `#101018` | Console |

The progress gradient is `--grad`: `#8fae24` to `#b8db35` to `#cfec62` on light, `#8fbf00` to `#b9e41a` to `#d6ff3e` on dark. It is never used behind body text. The mission card, finished badge, baseline total and logo tile use `--grad-deep`, a near-black olive (`#0f1307` to `#2b3510`) with white text and lime labels.

Contrast (WCAG 2 ratios, recomputed for the lime palette). Light: ink on page 17.0, secondary text 7.3, hints 5.3, accent text on white 6.2 and on its tint 5.6, dark ink on the primary button 11.6 (13.2 on hover), verdict colours on their tints 5.1 to 5.7. Dark: ink on page 16.9, secondary text 7.9, hints 5.9, accent on a card 15.6, dark ink on the primary button 16.0, verdict colours on their tints 6.9 to 9.6. White on the mission card 13.0 or better. Console text 15.7. Every text pairing clears the 4.5:1 AA threshold in both themes. The lime fill itself is low contrast against a light page, so buttons and marks always carry a label or glyph.

Shape: radii 10, 14 and 20px. Motion: `--ease` for movement and `--spring` for the small pops.

## 5. Typography

The app fetches nothing at runtime, so there are no web fonts. The stacks are tokens in `styles.css`.

| Role | Token | Stack starts with | Use |
|---|---|---|---|
| Display | `--display` | Segoe UI Variable Display | Headings: bold, tracking -0.02em, and -0.035em on `h1` |
| Body | `--sans` | Segoe UI Variable Text | Instructions, controls and tables at 1rem (16px at 100%); Variable Small for hints |
| Utility | `--mono` | Cascadia Mono, then Cascadia Code and Consolas | Uppercase labels, marks, verdicts, CLI lines and the terminal |

## 6. Components

- **Sidebar.** Brand, an overall progress ring, the course as a timeline of numbered marks, and the tools: glossary, reference, theme, Settings and Quit, with Settings always directly before Quit. Inside a Part the sidebar also carries a "Back to series map" control above the progress (in the top bar on narrow screens). Done marks fill lime with a check. The current item carries a "Now" chip and a beacon pulse. Locked and optional items use dashed marks; a locked item can always be opened to read, in any Part, whether or not setup has passed (it opens as a read-only preview). Setup is not in the list. It collapses to a rail of marks, with status words kept in the page for screen readers, and becomes a top bar in the narrow layout with the course list as a drop-down. The course shown is the course of the Part the page is in (Part 1, Part 2 or Part 3).
- **Series map.** The home screen (`web/js/series.js`): one row per Part of the six-Part series, each with its number, name, a state in words and by icon, and a one-line outcome. A Part with content (1, 2 and 3) has an expand control, which lists its lesson names with their status as plain text, and a separate open control ("Start" or "Continue"). Parts 4 and 5 show "Coming soon" and Part 6 shows "Live meeting"; those rows are text only. The map's sidebar keeps the tools but shows no progress count and no course list. Words come from `content/series.json`.
- **Course-list group headings.** The course list is split into groups of lessons and steps by one heading row above each group (Part 3's: "Why check AI work", "Collect answers", "Turn it into rules", "Test the checker", "Read results and improve", "Keep a record"; Part 1 and Part 2 have their own groups). The labels and membership come from `ui.course_groups` in `content/lesson-ui.json` for Part 3 and from the Part's own `ui.course_groups` in `content/series.json` for another Part. A heading is a non-interactive label (`li` with `role="presentation"` holding a `span` with `role="heading"`, level 2): not a button, not in the tab order, with no mark and no status. It is set in `--mono` at 0.66rem, uppercase, semibold, `--ink-soft`, with `.course-group` as its one style rule and no new token. Item numbering stays global, and the connector line between consecutive items is kept. In the collapsed rail the heading text is kept in the page for screen readers and hidden visually, and in the narrow layout the same headings appear in the drop-down. Contrast is the normal text contrast in both themes, including at the largest text size.
- **Glossary groups.** The glossary panel and the printable reference show two groups, "Ideas" then "In this course" (labels `reference.glossary_ideas` and `reference.glossary_course`), each introduced by a small `h3` and chosen by the term's `kind` in `content/glossary.json`. A group with no terms is not shown. The printable reference opens with the method line, then "How this course works" and the verdict chips, then the glossary in its two groups, then the principles, in the same styles as before, and still fits one page.
- **Settings panel.** One page with three stacked groups and no tabs, in this order: text size (a range slider with a value readout and a "Back to 100%" button), setup (a list of the checks with their status tags and an "Open setup" button that opens the setup wizard full page), and reset (two actions, each in its own box; the configuration one has a danger-tinted border and a danger button). The panel is one centered column with no terminal. "Close Settings" returns to the screen that was open before.
- **Setup wizard.** A full-page flow with no sidebar, tools or banners: a header with the `eval-coach` mark and "Skip for now" (first run) or "Close setup" (opened from Settings or the banner), the "Before you begin" heading, an "n of total" count with a row of pills (a check mark for a passed page, the number otherwise, the current page outlined and named; on narrow screens only the current pill shows its name), one setup card for the current check, and a footer with Back, "Check everything" (only on the pages where something can be fixed outside the app) and Next (lime, disabled until the check passes) plus a plain line saying what is still needed. The pages are Track, Checking your computer (runs the checks by itself), one page per applicable check, and a last "Your AI window" mini lesson with an annotated screenshot (numbered markers, a text legend and hover or focus descriptions; the same lesson opens in a dialog from Settings and the AI window head). The terminal dock ("Your AI window") appears beside the card (below it on narrow screens) only on the AI working test page and while an install runs. On phones every button is at least 44px tall.
- **Part 1 and Part 2 step panels.** Built from the existing tokens and components (`radio-card`, `seg`, `mono-block`), with no new token. Part 1: a prompt editor with Save and a confirm before replacing text, a score form of labelled yes or no groups, a side-by-side compare that stacks in the `mid` and `narrow` layouts, and the own-work form. Part 2: a criteria worksheet (rows with a requirement box, criterion box, type choice and threshold box), the test case file editor with findings (blocking ones first), and the reference comparison with a labelled group of four `radio-card` choices per criterion. Free text is always placed in text nodes. Meaning is in text, never colour alone.
- **Reset dialogs.** The existing confirm dialog with a longer body: a lead sentence, "This clears" and "This keeps" lists, and the backup folder line. The default (focused) button is "Keep everything". The configuration dialog uses the danger button and says progress is cleared too.
- **Setup banner.** A slim strip in the amber attention colors (not the error colors) directly above the content, outside the scrolling column so it stays in view. One or two lines, one button that opens the setup wizard, no close control, no focus movement (`role="status"`). On phones the button is at least 44px tall. It is hidden inside the setup wizard.
- **Instructions.** "What to do" is a run of numbered cards that nudge right on hover. "Why this matters" is a quiet list with diamond bullets. The mission card and the baseline total use `--grad-deep`, so the two things a learner carries away stand out.
- **Activities.** Each activity is a numbered card. A pip per activity fills with `--grad` as each is passed, the number turns to a check, and a pass medallion pops in. A wrong answer gets a calm red banner with a coaching line and no penalty.
- **Verdicts.** Chips carry a glyph (check, cross, circle) as well as a colour. After a run, the learner's locked predictions sit beside the checker's verdicts, and each surprise warms to amber with an attention marker.
- **Console dock.** A status pill says whether the AI window is running, and the pill reflects the process only because the app never parses terminal output. A Sonnet / Haiku toggle sits in the head of every AI window and applies the next time the AI starts. The line to type sits in a dark box with a lime prompt chevron. The terminal is a window with its own title bar and a lime focus ring.
- **Callouts.** Accent for a tip or note, then good, attention and problem, each coloured with its verdict token.

## 7. Motion

Movement uses `--ease` and small pops use `--spring`. Every animation and transition is off under `prefers-reduced-motion`.

| Moment | Treatment |
|---|---|
| Newly passed activity or step check | Confetti, a pass medallion that pops in, the number turning to a check, and the pip filling |
| Current item | A beacon pulse on the mark in the sidebar |
| Page and card entrance | A 12px rise, with a short stagger on checklist items and activity cards |
| Reading progress | A 3px gradient line over the page that scales with scroll |
| Hover and press | Buttons lift 1px on hover and settle on press. Choices and instruction cards nudge right. Hover also shifts the border to the accent |
| Theme change | A 0.3s crossfade of background, border and text colours |
| Running CLI | The status dot pulses green |

## 8. Where things live

- `web/styles.css`: the system, in sections (base, text pieces, sidebar, notices, layout, console dock, controls, callouts and tables, setup and preflight, dialogs, lesson page, meters, celebration, responsive).
- `web/js/theme.js`: a plain script in the page head that applies the saved theme, sidebar width and text size before the first paint, and sets `data-layout` and `data-phone`. It also exposes `window.EvalCoachDisplay` (range, size, `setSize`, `resetChoices`) to the modules.
- `web/js/chrome.js`: theme toggle, sidebar collapse, text size wrappers, the reading-progress line and the confetti.
- `web/js/views.js`: the sidebar (brand, ring, steps, tools) and the step view shared by every Part.
- `web/js/lessons.js`: the course timeline (with the group headings) and the activity pips.
- `web/js/series.js`: the Series map (rows, expand and open controls, the map's sidebar section).
- `web/js/part-steps.js`: Part 1's step panels (prompt editor with one AI run, score form with compare, own-work form). `web/js/criteria-steps.js`: Part 2's panels (criteria worksheet, test case file, reference comparison). `web/js/panels.js`: Part 3's step panels.
- `web/js/preflight.js`: the setup wizard pages. `web/js/ai-window.js`: the "Your AI window" mini lesson.
- `web/js/settings.js`: the Settings panel, the reset dialog body and the setup banner.
- `web/reference.css`: the printable card on the same tokens. Print is always light.
- `web/favicon.svg` and `web/img/`: the mark and the icons.

## 9. Behaviour notes

- `localStorage` keys: `eval-coach-theme` (`light` or `dark`), `eval-coach-nav` (`expanded` or `collapsed`) and `eval-coach-text-size` (a percentage). With no saved sidebar choice, the sidebar is expanded at 1400px and wider and collapsed below that. "Reset app configuration" clears all three.
- **Text size.** The slider offers 80% to 150% in steps of 5 on a desktop and 90% to 130% on a phone, with 100% the default. A phone is a touch device (`(pointer: coarse)`) whose shorter screen side is 600 CSS pixels or less; a narrow desktop window is not a phone. `theme.js` stores and clamps the value (not a number: 100; outside the range: the nearest limit) and sets `data-text-size` on `<html>`; `styles.css` has one rule per step that sets the root font size, so `rem` follows it and no inline style is used. The body is `1rem`, and the terminal font is `round(14 * scale)` and refits.
- **Layouts.** `data-layout` on `<html>` is `wide`, `mid` or `narrow`: the window width divided by the text scale, against 1100px and 820px. The responsive rules in `styles.css` select on it, so a larger size reaches the compact forms sooner. At 100% it matches the former `@media` widths: `mid` is 821 to 1100px and `narrow` is 820px and under. The sidebar's collapsed rail applies in every layout except `narrow`.
- On the `narrow` layout the course list is a drop-down that closes on a choice or on Escape; otherwise it is always open.
- Confetti runs only when an activity or a step check passes for the first time in response to the participant's own action. It never takes clicks.
