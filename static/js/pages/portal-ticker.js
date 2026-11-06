/*!
 * SAFE CITIES PROJECT - portal-ticker.js
 * Behavior for the portal announcement ticker bar rendered by
 * templates/_partials/portal_ticker.html. Loaded by base.html for
 * authenticated staff only.
 *
 * Responsibilities:
 *   1. Continuous marquee: the item set is duplicated until the track is at
 *      least twice the viewport width, then a CSS translateX(-50%) marquee
 *      scrolls it right-to-left in a seamless infinite loop. When a single
 *      copy already exceeds the viewport one duplicate is enough; when the
 *      items are short the set is repeated as many times as needed so the
 *      animation always loops seamlessly.
 *   2. Pause on hover is handled in CSS (animation-play-state: paused).
 *   3. Listen for the DOM CustomEvent 'safecity:notification' (dispatched
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

  var MAX_ITEMS = 8;        // hard cap, live items included
  var PX_PER_SECOND = 55;   // marquee scrolling speed
  var MIN_DURATION_S = 18;  // never scroll faster than this
  var CLONE_FLAG = 'data-ticker-clone';
  var RESIZE_DELAY_MS = 200;
  var MAX_COPIES = 12;      // safety cap when repeating very short sets

  var resizeTimer = null;
  var lastEvent = null;

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

  /* --------------------------- marquee control --------------------------- */

  // Measures the track and activates the seamless right-to-left marquee.
  // Spacing between items is a margin on every item (see tailwind-bridge.css).
  // The item set is duplicated until the ORIGINAL half of the track is at
  // least as wide as the viewport, which guarantees the translateX(-50%)
  // loop is seamless no matter how few items there are - the ticker always
  // scrolls, infinitely, right to left.
  function ensureMarquee() {
    removeClones();

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
    // sets and translateX(-50%) lands exactly on a set boundary - that is
    // what makes the infinite loop seamless.
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
    var seconds = Math.max(MIN_DURATION_S, Math.round(halfWidth / PX_PER_SECOND));
    bar.style.setProperty('--sc-ticker-duration', seconds + 's');
    bar.classList.add('is-scrolling');
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
      if (title) {
        var d1 = document.createElement('span');
        d1.className = 'sc-ticker-dash';
        d1.setAttribute('aria-hidden', 'true');
        d1.textContent = '\u2014';
        item.appendChild(d1);
      }
      var m = document.createElement('span');
      m.className = 'sc-ticker-item-message';
      m.textContent = message;
      item.appendChild(m);
    }

    var fresh = document.createElement('span');
    fresh.className = 'sc-ticker-item-new';
    fresh.textContent = 'NEW';
    if (title || message) {
      var d2 = document.createElement('span');
      d2.className = 'sc-ticker-dash';
      d2.setAttribute('aria-hidden', 'true');
      d2.textContent = '\u2014';
      item.appendChild(d2);
    }
    item.appendChild(fresh);

    track.insertBefore(item, track.firstChild);
    trimToMax();
    ensureMarquee();
    flash();
  }

  // realtime-socket.js may dispatch on document, body or window; listening
  // on document plus window covers every dispatch target that bubbles.
  document.addEventListener('safecity:notification', onNotification);
  window.addEventListener('safecity:notification', onNotification);

  /* ------------------------------- wiring -------------------------------- */

  window.addEventListener('resize', function () {
    if (resizeTimer) { clearTimeout(resizeTimer); }
    resizeTimer = setTimeout(ensureMarquee, RESIZE_DELAY_MS);
  });

  // Re-measure once webfonts have settled.
  window.addEventListener('load', ensureMarquee);

  function init() { ensureMarquee(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
