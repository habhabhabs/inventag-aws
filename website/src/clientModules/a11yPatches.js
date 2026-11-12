/**
 * Accessibility patches for markup this site does not own (the Docusaurus
 * classic theme and the local search plugin). Each patch fixes a failure
 * found by `npm run check:a11y`; remove a patch when upstream fixes it.
 *
 * 1. Mobile navigation menu: the theme opens the menu as a full-screen panel
 *    but leaves keyboard focus on the page behind it. While the menu is open
 *    this module makes the rest of the page inert, moves focus into the menu,
 *    closes it on Escape, and gives focus back to the menu button.
 * 2. Search suggestions: the combobox has no `aria-controls`; the "See all
 *    results" link and the "No results" message sit in the listbox without
 *    the `option` role.
 * 3. Search page: the clear button has no text name, and the page has no
 *    `main` landmark.
 * 4. Search box: the plugin loads its index when the box first gets focus and
 *    then calls `input.focus()`, even if the visitor has already moved on.
 *    Focus that the visitor did not ask for is given back.
 */
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

const MENU_OPEN = 'navbar-sidebar--show';
const INERT_MARK = 'data-menu-inert';

let menuIsOpen = false;
let followedLink = false;

function everythingOutside(panel) {
  const outside = [];
  for (let node = panel; node && node !== document.body; node = node.parentElement) {
    for (const sibling of node.parentElement.children) {
      if (sibling === node || sibling.matches('script, style, link, .navbar-sidebar__backdrop')) continue;
      outside.push(sibling);
    }
  }
  return outside;
}

// The panel fades in from `visibility: hidden`, and a hidden element cannot
// take focus. Try on each frame until it works (at most about half a second).
function focusWhenVisible(el, tries = 30) {
  if (!el || !menuIsOpen) return;
  el.focus();
  if (document.activeElement !== el && tries > 0) {
    requestAnimationFrame(() => focusWhenVisible(el, tries - 1));
  }
}

function syncMenu() {
  const nav = document.querySelector('nav.navbar');
  const panel = nav && nav.querySelector('.navbar-sidebar');
  const open = !!(nav && panel && nav.classList.contains(MENU_OPEN));
  if (open === menuIsOpen) return;
  menuIsOpen = open;
  if (open) {
    followedLink = false;
    for (const el of everythingOutside(panel)) {
      if (el.inert) continue;
      el.inert = true;
      el.setAttribute(INERT_MARK, '');
    }
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', 'Navigation menu');
    focusWhenVisible(panel.querySelector('.navbar-sidebar__close'));
  } else {
    for (const el of document.querySelectorAll(`[${INERT_MARK}]`)) {
      el.inert = false;
      el.removeAttribute(INERT_MARK);
    }
    if (panel) {
      panel.removeAttribute('role');
      panel.removeAttribute('aria-modal');
      panel.removeAttribute('aria-label');
    }
    // Closed with Escape, the close button or the backdrop: back to the menu
    // button. After following a link the new page keeps the focus.
    const toggle = nav && nav.querySelector('.navbar__toggle');
    if (toggle && !followedLink) toggle.focus();
  }
}

function patchSearch() {
  for (const input of document.querySelectorAll('.navbar__search-input[role="combobox"][aria-owns]:not([aria-controls])')) {
    input.setAttribute('aria-controls', input.getAttribute('aria-owns'));
  }
  for (const link of document.querySelectorAll('.navbar__search [role="listbox"] a[href]:not([role])')) {
    link.setAttribute('role', 'option');
    link.setAttribute('aria-selected', 'false');
  }
  // "No results" is the only thing in the listbox then: a disabled option.
  for (const empty of document.querySelectorAll('.navbar__search [role="listbox"] [class*="noResults_"]:not([role])')) {
    empty.setAttribute('role', 'option');
    empty.setAttribute('aria-disabled', 'true');
    empty.setAttribute('aria-selected', 'false');
  }
  for (const button of document.querySelectorAll('button[class*="searchClearButton"]:not([aria-label])')) {
    button.setAttribute('aria-label', 'Clear search');
  }
}

function patchMainLandmark() {
  const wrapper = document.getElementById('__docusaurus_skipToContent_fallback');
  if (!wrapper) return;
  if (wrapper.querySelector('main, [role="main"]')) wrapper.removeAttribute('role');
  else wrapper.setAttribute('role', 'main');
}

// True only while the browser handles a key press or a pointer press, which
// is when a focus change is the visitor's own doing.
let userGesture = false;
function markGesture() {
  userGesture = true;
  setTimeout(() => {
    userGesture = false;
  }, 0);
}

function returnStolenFocus(event) {
  const input = event.target;
  const previous = event.relatedTarget;
  if (userGesture || !previous || previous === input) return;
  if (!(input instanceof Element) || !input.matches('.navbar__search-input')) return;
  if (previous.isConnected && typeof previous.focus === 'function') previous.focus();
}

if (ExecutionEnvironment.canUseDOM) {
  for (const type of ['keydown', 'mousedown', 'pointerdown', 'touchend', 'click']) {
    document.addEventListener(type, markGesture, true);
  }
  document.addEventListener('focusin', returnStolenFocus, true);

  let queued = false;
  const run = () => {
    queued = false;
    syncMenu();
    patchSearch();
    patchMainLandmark();
  };
  const schedule = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(run);
  };
  const start = () => {
    new MutationObserver(schedule).observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['class'],
    });
    schedule();
  };
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !menuIsOpen) return;
    const close = document.querySelector('.navbar-sidebar__close');
    if (close) close.click();
  });
  document.addEventListener(
    'click',
    (event) => {
      if (menuIsOpen && event.target.closest && event.target.closest('.navbar-sidebar a[href]')) followedLink = true;
    },
    true,
  );
}
