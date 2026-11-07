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
  var MAX_COPIES = 24;      // safety cap when repeating very short sets (keeps the loop gapless)

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
  //
  // True-infinite rule: the track must hold an EVEN number of identical
  // sets and the FIRST HALF of the track must be at least as wide as the
  // viewport (plus buffer). translateX(-50%) then lands exactly on a set
  // boundary, so the loop is seamless and never runs out of content -
  // no blank gap can open at the leading edge, no matter how few items.
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

    // Number of sets needed so that HALF the track covers the viewport.
    var halfSets = Math.max(1, Math.ceil((viewport.clientWidth + 120) / setWidth));
    // Total sets must be even for the -50% loop to land on a set boundary.
    var totalSets = halfSets * 2;
    if (totalSets > MAX_COPIES + 1) { totalSets = MAX_COPIES + 1; }
    if (totalSets % 2 !== 0) { totalSets += 1; }
    // copies = extra sets beyond the originals.
    var copies = Math.max(0, totalSets - 1);
    if (copies < 1) { copies = 1; totalSets = 2; }

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
