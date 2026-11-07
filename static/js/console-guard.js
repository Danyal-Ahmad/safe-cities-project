/*!
 * SAFE CITIES PROJECT - console-guard.js
 * Client-side inspection deterrent for the shared app shell.
 * Loaded with `defer` from templates/base.html on every page (public and
 * portal).
 *
 * NOTE: client-side blocking is defense-in-depth ONLY. Every technique in
 * this file can be bypassed by disabling JavaScript, using a proxy, or a
 * modified client. True enforcement is always server-side: CSP and other
 * security headers, authentication and authorization, input validation,
 * rate limiting, and audit logging. Treat this file as a speed bump that
 * raises the cost of casual tampering, nothing more.
 *
 * Environment contract with the server-rendered shell:
 *   <body data-env="development|production">   rendered by base.html from
 *                                              the `debug` context variable
 *   <body data-user-role="dig|ssp|supv|...">   empty for anonymous users
 *
 * Behavior summary:
 *   - Right-click context menu is disabled on portal pages (/portal/...).
 *   - F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C and Ctrl+U are blocked.
 *   - console.log/info/warn/error/debug become no-ops after DOMContentLoaded
 *     in production mode. Development keeps the console fully working.
 *   - DevTools-open heuristic: when window.outerWidth - window.innerWidth
 *     exceeds 160px, confirmed twice 500ms apart, on three consecutive
 *     polls, and only on an authenticated portal page, the page body is
 *     replaced with a full-screen block notice. Window resizes and page
 *     zoom changes reset the counter so normal use never trips it.
 *   - window.SAFECITY_CONFIG is frozen when present.
 */
(function () {
  'use strict';

  /* ----------------------------- configuration ---------------------------- */

  var DEVTOOLS_GAP_THRESHOLD = 160; // px, outerWidth minus innerWidth
  var CONFIRM_DELAY_MS = 500;       // second check must still be positive
  var POLL_INTERVAL_MS = 1000;      // heuristic poll frequency
  var REQUIRED_STRIKES = 3;         // confirmed detections before blocking
  var RESIZE_GRACE_MS = 1500;       // ignore heuristic right after a resize

  /* ------------------------------ environment ----------------------------- */

  function bodyEl() { return document.body; }

  function isProduction() {
    var b = bodyEl();
    return !!b && b.getAttribute('data-env') === 'production';
  }

  function userRole() {
    var b = bodyEl();
    return b ? (b.getAttribute('data-user-role') || '') : '';
  }

  // Portals live under /portal/<role>/ (see wrongway_system URL config).
  function isPortalPage() {
    return /^\/portal(\/|$)/.test(window.location.pathname);
  }

  function isAuthedPortal() {
    return isPortalPage() && userRole() !== '';
  }

  /* ------------------------- 1. context menu block ------------------------ */
  /* Disabled on portal pages only; the public site keeps normal behavior.   */

  if (isPortalPage()) {
    document.addEventListener('contextmenu', function (e) {
      e.preventDefault();
    }, true);
  }

  /* ------------------------ 2. keyboard shortcut block -------------------- */
  /* F12, Ctrl+Shift+I / J / C (devtools panes), Ctrl+U (view source).       */

  document.addEventListener('keydown', function (e) {
    if (e.defaultPrevented) { return; }

    var key = (e.key || '').toLowerCase();

    // F12 (keyCode 123 kept for older engines)
    if (e.key === 'F12' || e.keyCode === 123) {
      e.preventDefault();
      return;
    }

    // Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C
    if (e.ctrlKey && e.shiftKey && (key === 'i' || key === 'j' || key === 'c')) {
      e.preventDefault();
      return;
    }

    // Ctrl+U (view source)
    if (e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey && key === 'u') {
      e.preventDefault();
    }
  }, true);

  /* --------------------------- 3. console no-ops -------------------------- */
  /* Production only, and only after DOMContentLoaded so framework boot      */
  /* messages remain visible during development.                             */

  function silenceConsole() {
    if (!isProduction()) { return; }
    var methods = ['log', 'info', 'warn', 'error', 'debug'];
    for (var i = 0; i < methods.length; i++) {
      (function (name) {
        try {
          Object.defineProperty(console, name, {
            value: function () {},
            writable: false,
            configurable: false
          });
        } catch (err) {
          // Some engines refuse to lock host properties; fall back.
          try { console[name] = function () {}; } catch (err2) { /* noop */ }
        }
      })(methods[i]);
    }
  }

  /* ----------------------- 4. DevTools-open heuristic --------------------- */

  var strikes = 0;
  var confirmPending = false;
  var blocked = false;
  var lastResizeAt = 0;
  var baseDpr = window.devicePixelRatio || 1;
  var pollTimer = null;
  var confirmTimer = null;

  function widthGap() {
    return (window.outerWidth || 0) - (window.innerWidth || 0);
  }

  function devtoolsOpen() {
    // A docked devtools panel shrinks innerWidth while outerWidth stays
    // constant; a gap above the threshold means the viewport is compressed
    // by roughly 160px of browser chrome or panel.
    return widthGap() > DEVTOOLS_GAP_THRESHOLD;
  }

  function recentlyResized() {
    return (Date.now() - lastResizeAt) < RESIZE_GRACE_MS;
  }

  // Page zoom and monitor moves change devicePixelRatio and shrink
  // innerWidth, which would false-positive the width heuristic. Fail open
  // (skip detection) whenever the ratio drifted from the initial value.
  function zoomOrDpiChanged() {
    var dpr = window.devicePixelRatio || 1;
    return Math.abs(dpr - baseDpr) > 0.05;
  }

  function stopWatching() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    if (confirmTimer) { clearTimeout(confirmTimer); confirmTimer = null; }
  }

  function triggerBlock() {
    if (blocked) { return; }
    blocked = true;
    stopWatching();

    try { window.stop(); } catch (err) { /* keep going */ }

    var b = bodyEl();
    if (!b) { return; }

    document.title = 'Access Blocked';

    // Full-screen notice. Styling lives in tailwind-bridge.css
    // (.sc-guard-block family) which stays loaded because only the body
    // markup is replaced, not the head.
    var wrap = document.createElement('div');
    wrap.className = 'sc-guard-block';
    wrap.setAttribute('role', 'alert');

    var card = document.createElement('div');
    card.className = 'sc-guard-block-card';

    var brand = document.createElement('p');
    brand.className = 'sc-guard-block-brand';
    brand.textContent = 'SAFE CITIES PROJECT';

    var title = document.createElement('h1');
    title.className = 'sc-guard-block-title';
    title.textContent = 'Unauthorized inspection attempt blocked.';

    var text = document.createElement('p');
    text.className = 'sc-guard-block-text';
    text.textContent = 'This incident has been logged.';

    var sub = document.createElement('p');
    sub.className = 'sc-guard-block-sub';
    sub.textContent = 'Close this tab and sign in again to continue.';

    card.appendChild(brand);
    card.appendChild(title);
    card.appendChild(text);
    card.appendChild(sub);
    wrap.appendChild(card);
    b.innerHTML = '';
    b.appendChild(wrap);

    // Keep a local record of the incident for any surviving handlers.
    try {
      window.__SC_GUARD_BLOCKED_AT = new Date().toISOString();
    } catch (err) { /* noop */ }
  }

  function confirmStrike() {
    confirmTimer = null;
    if (blocked) { return; }

    // The 500ms confirmation check: still open, and no resize or zoom
    // happened in between, otherwise it was a transient layout change.
    if (recentlyResized() || zoomOrDpiChanged() || !devtoolsOpen()) {
      strikes = 0;
      return;
    }

    strikes += 1;

    if (strikes >= REQUIRED_STRIKES && isAuthedPortal()) {
      triggerBlock();
    }
    // On public or unauthenticated pages the counter simply resets on the
    // next negative poll; the destructive action only ever runs on
    // authenticated portal pages.
  }

  function poll() {
    if (blocked || confirmPending) { return; }

    if (recentlyResized() || zoomOrDpiChanged()) {
      strikes = 0;
      return;
    }

    if (devtoolsOpen()) {
      // Debounce: schedule the confirmation check 500ms out so a one-off
      // viewport change (sidebar animation, browser UI reveal) does not
      // count as a strike.
      confirmPending = true;
      confirmTimer = setTimeout(function () {
        confirmPending = false;
        confirmStrike();
      }, CONFIRM_DELAY_MS);
    } else {
      strikes = 0;
    }
  }

  window.addEventListener('resize', function () {
    lastResizeAt = Date.now();
    strikes = 0;
  }, true);

  pollTimer = setInterval(poll, POLL_INTERVAL_MS);

  /* ------------------------- 5. freeze app config ------------------------- */

  function freezeConfig() {
    var cfg = window.SAFECITY_CONFIG;
    if (cfg && typeof cfg === 'object') {
      try { Object.freeze(cfg); } catch (err) { /* noop */ }
    }
  }

  /* ------------------------------ bootstrap ------------------------------- */

  // Runs a callback once the DOM is ready, in every load mode. Deferred
  // scripts execute before DOMContentLoaded, so the listener path is the
  // normal one; the window load fallback covers scripts injected later.
  function afterDomReady(fn) {
    var done = false;
    function run() {
      if (done) { return; }
      done = true;
      fn();
    }
    document.addEventListener('DOMContentLoaded', run);
    window.addEventListener('load', run);
    if (document.readyState === 'complete') { run(); }
  }

  freezeConfig();
  afterDomReady(function () {
    freezeConfig();          // configs defined by page scripts
    silenceConsole();        // production no-ops, after DOMContentLoaded
  });
  window.addEventListener('load', freezeConfig);
})();
