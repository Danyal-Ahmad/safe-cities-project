/*!
 * SAFE CITIES PROJECT - portal-ticker.js
 * Behavior for the unified announcement ticker bar rendered by
 * templates/_partials/portal_ticker.html. Loaded on EVERY page
 * (base.html and public_base.html).
 *
 * Responsibilities:
 *   1. Continuous marquee: the item set is duplicated until the track is
 *      at least twice the viewport width, then a CSS translateX(-50%)
 *      marquee scrolls it right-to-left in a seamless infinite loop.
 *   2. Phase persistence: the marquee position is anchored to wall-clock
 *      time in sessionStorage, so a page refresh or an in-app redirect
 *      resumes the scroll exactly where it left off instead of restarting.
 *      The state is keyed by a content hash - if the announcement set
 *      changed between pages the marquee simply starts fresh.
 *   3. Pause on hover is handled in CSS (animation-play-state: paused).
 *   4. Listen for the DOM CustomEvent 'safecity:notification' (dispatched
 *      by static/js/realtime-socket.js) and prepend the new item live.
 *
 * The event payload is read defensively because it comes from another
 * module: {title|heading, message|body|text, severity|level|type} or a
 * plain string. All inserted text uses textContent, never innerHTML, so a
 * hostile payload cannot inject markup.
 */
(function () {
  'use strict';

  var bar = document.getElementById('scPortalTicker');
  var viewport = document.getElementById('scTickerViewport');
  var track = document.getElementById('scTickerTrack');
  if (!bar || !viewport || !track) { return; }

  var MAX_ITEMS = 10;       // hard cap, live items included
  var PX_PER_SECOND = 55;   // marquee scrolling speed
  var MIN_DURATION_S = 18;  // never scroll faster than this
  var CLONE_FLAG = 'data-ticker-clone';
  var RESIZE_DELAY_MS = 200;
  var MAX_COPIES = 12;      // safety cap when repeating very short sets
  var STORE_KEY = 'scTickerPhase';
  var SAVE_TICK_MS = 1500;  // periodic phase save interval

  var resizeTimer = null;
  var lastEvent = null;
  var saveTimer = null;
  var currentDuration = 0;
  var currentHash = '';

  /* ------------------------------ helpers -------------------------------- */

  function originalItems() {
    var nodes = track.children;
    var out = [];
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].nodeType === 1 && !nodes[i].hasAttribute(CLONE_FLAG)) {
        out.push(nodes[i]);
      }
    }
    return out;
  }

  function removeClones() {
    var clones = track.querySelectorAll('[' + CLONE_FLAG + ']');
    for (var i = 0; i < clones.length; i++) {
      if (clones[i].parentNode) { clones[i].parentNode.removeChild(clones[i]); }
    }
    bar.classList.remove('is-scrolling');
  }

  function contentHash() {
    var items = originalItems();
    var parts = [String(items.length)];
    for (var i = 0; i < items.length; i++) {
      parts.push((items[i].textContent || '').trim());
    }
    return parts.join('|');
  }

  /* ------------------------- phase persistence --------------------------- */

  // Current marquee progress in seconds, read from the LIVE animated
  // transform (browsers return the in-flight animated matrix from
  // getComputedStyle). 0..duration over one seamless loop.
  function currentPhaseSeconds() {
    if (!currentDuration) { return null; }
    try {
      var m = getComputedStyle(track).transform;
      if (!m || m === 'none') { return 0; }
      var mm = String(m).match(/matrix\(([^)]+)\)/);
      if (!mm) { return 0; }
      var parts = mm[1].split(',');
      var tx = parseFloat(parts[4] || '0');
      var half = track.scrollWidth / 2;
      if (!isFinite(half) || half <= 0) { return 0; }
      var frac = (-tx) / half;
      if (!isFinite(frac) || frac < 0) { frac = 0; }
      return (frac % 1) * currentDuration;
    } catch (e) { return 0; }
  }

  function loadPhase() {
    try {
      var raw = window.sessionStorage.getItem(STORE_KEY);
      if (!raw) { return null; }
      var state = JSON.parse(raw);
      if (!state || typeof state.savedAt !== 'number' ||
          typeof state.duration !== 'number' || !state.hash) { return null; }
      return state;
    } catch (e) { return null; }
  }

  function savePhase() {
    var phase = currentPhaseSeconds();
    if (phase === null || !currentDuration) { return; }
    try {
      window.sessionStorage.setItem(STORE_KEY, JSON.stringify({
        savedAt: Date.now(),
        phase: phase,
        duration: currentDuration,
        hash: currentHash
      }));
    } catch (e) { /* storage unavailable - persistence is best-effort */ }
  }

  // Resume the marquee exactly where the previous page left it: the saved
  // phase plus the time the browser spent loading this page, applied as a
  // negative animation-delay so the loop starts mid-scroll.
  function applyPhase() {
    var state = loadPhase();
    if (!state || state.hash !== currentHash || !currentDuration) {
      track.style.removeProperty('animation-delay');
      return;
    }
    var elapsed = (Date.now() - state.savedAt) / 1000;
    if (!isFinite(elapsed) || elapsed < 0) { elapsed = 0; }
    var base = (typeof state.phase === 'number' && state.phase >= 0) ? state.phase : 0;
    var offset = (base + elapsed) % currentDuration;
    track.style.setProperty('animation-delay', '-' + offset.toFixed(2) + 's');
  }

  /* --------------------------- marquee control --------------------------- */

  // Measures the track and activates the seamless right-to-left marquee.
  // The item set is duplicated until the ORIGINAL half of the track is at
  // least as wide as the viewport, which guarantees the translateX(-50%)
  // loop is seamless no matter how few items there are.
  function ensureMarquee() {
    removeClones();
    track.style.removeProperty('animation-delay');
    currentDuration = 0;

    var items = originalItems();
    if (!items.length) { return; }

    // Width of one original item set.
    var setWidth = 0;
    for (var w = 0; w < items.length; w++) {
      setWidth += items[w].offsetWidth;
      var ml = getComputedStyle(items[w]).marginLeft;
      var mr = getComputedStyle(items[w]).marginRight;
      setWidth += parseFloat(ml) || 0;
      setWidth += parseFloat(mr) || 0;
    }
    if (setWidth < 1) { return; }

    // Repeat the set enough times that the original half covers the
    // viewport (plus a buffer), then mirror it for the -50% loop. The copy
    // count must be ODD so the track holds an even number of identical
    // sets and translateX(-50%) lands exactly on a set boundary.
    var needed = Math.max(1, Math.ceil((viewport.clientWidth + 80) / setWidth));
    if (needed % 2 === 0) { needed += 1; }
    var copies = Math.min(needed, MAX_COPIES);
    if (copies % 2 === 0) { copies -= 1; }
    if (copies < 1) { copies = 1; }

    for (var c = 0; c < copies; c++) {
      for (var i = 0; i < items.length; i++) {
        var clone = items[i].cloneNode(true);
        clone.setAttribute(CLONE_FLAG, 'true');
        clone.setAttribute('aria-hidden', 'true');
        track.appendChild(clone);
      }
    }

    var halfWidth = track.scrollWidth / 2;
    currentDuration = Math.max(MIN_DURATION_S, Math.round(halfWidth / PX_PER_SECOND));
    currentHash = contentHash();

    bar.style.setProperty('--sc-ticker-duration', currentDuration + 's');
    bar.classList.add('is-scrolling');

    // Resume where the previous page left off (refresh / redirect safe).
    applyPhase();
  }

  /* --------------------------- live notifications ------------------------ */

  function severityClass(raw) {
    switch (String(raw || '').toLowerCase()) {
      case 'success': return 'success';
      case 'warning': return 'warning';
      case 'danger':
      case 'error':
      case 'critical': return 'danger';
      default: return 'info';
    }
  }

  function payloadFrom(event) {
    var d = event && event.detail;
    if (d && typeof d === 'object') { return d; }
    if (typeof d === 'string' && d.trim()) { return { message: d }; }
    return {};
  }

  function trimToMax() {
    var items = originalItems();
    while (items.length > MAX_ITEMS) {
      var last = items.pop();
      if (last && last.parentNode) { last.parentNode.removeChild(last); }
    }
  }

  function flash() {
    bar.classList.remove('is-flashing');
    void bar.offsetWidth; // force restyle so the animation restarts
    bar.classList.add('is-flashing');
  }

  function onNotification(event) {
    // The same event object can arrive via both the document and window
    // listeners (it bubbles through both); process it exactly once.
    if (event === lastEvent) { return; }
    lastEvent = event;

    var p = payloadFrom(event);
    var title = p.title || p.heading || p.label || '';
    var message = p.message || p.body || p.text || p.description || '';
    if (!title && !message) { return; }

    var sev = severityClass(p.severity || p.level || p.type || p.priority);

    var item = document.createElement('div');
    item.className = 'sc-ticker-item sc-ticker-item-' + sev + ' sc-ticker-item-live';
    item.setAttribute('data-severity', sev);

    if (title) {
      var t = document.createElement('span');
      t.className = 'sc-ticker-item-title';
      t.textContent = title;
      item.appendChild(t);
    }
    if (message) {
      var m = document.createElement('span');
      m.className = 'sc-ticker-item-message';
      m.textContent = message;
      item.appendChild(m);
    }

    var fresh = document.createElement('span');
    fresh.className = 'sc-ticker-item-new';
    fresh.textContent = 'NEW';
    item.appendChild(fresh);

    track.insertBefore(item, track.firstChild);
    trimToMax();
    ensureMarquee();
    flash();
  }

  document.addEventListener('safecity:notification', onNotification);
  window.addEventListener('safecity:notification', onNotification);

  /* ------------------------------- wiring -------------------------------- */

  window.addEventListener('resize', function () {
    if (resizeTimer) { clearTimeout(resizeTimer); }
    resizeTimer = setTimeout(ensureMarquee, RESIZE_DELAY_MS);
  });

  // Re-measure once webfonts have settled.
  window.addEventListener('load', ensureMarquee);

  // Persist the marquee phase continuously and on page unload so the next
  // page (refresh or redirect) resumes the scroll instead of restarting.
  if (saveTimer) { clearInterval(saveTimer); }
  saveTimer = setInterval(savePhase, SAVE_TICK_MS);
  window.addEventListener('pagehide', savePhase);
  window.addEventListener('beforeunload', savePhase);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') { savePhase(); }
  });

  function init() { ensureMarquee(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
