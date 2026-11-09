
(function () {
  'use strict';

  var bar = document.getElementById('scPortalTicker');
  var viewport = document.getElementById('scTickerViewport');
  var track = document.getElementById('scTickerTrack');
  if (!bar || !viewport || !track) { return; }

  var MAX_ITEMS = 10;
  var PX_PER_SECOND = 55;
  var MIN_DURATION_S = 18;
  var CLONE_FLAG = 'data-ticker-clone';
  var RESIZE_DELAY_MS = 200;
  var MAX_COPIES = 12;
  var STORE_KEY = 'scTickerPhase';
  var SAVE_TICK_MS = 1500;

  var resizeTimer = null;
  var lastEvent = null;
  var saveTimer = null;
  var currentDuration = 0;
  var currentHash = '';


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
    } catch (e) {  }
  }


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


  function ensureMarquee() {
    removeClones();
    track.style.removeProperty('animation-delay');
    currentDuration = 0;

    var items = originalItems();
    if (!items.length) { return; }


    var setWidth = 0;
    for (var w = 0; w < items.length; w++) {
      setWidth += items[w].offsetWidth;
      var ml = getComputedStyle(items[w]).marginLeft;
      var mr = getComputedStyle(items[w]).marginRight;
      setWidth += parseFloat(ml) || 0;
      setWidth += parseFloat(mr) || 0;
    }
    if (setWidth < 1) { return; }


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


    applyPhase();
  }


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
    void bar.offsetWidth;
    bar.classList.add('is-flashing');
  }

  function onNotification(event) {


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


  window.addEventListener('resize', function () {
    if (resizeTimer) { clearTimeout(resizeTimer); }
    resizeTimer = setTimeout(ensureMarquee, RESIZE_DELAY_MS);
  });


  window.addEventListener('load', ensureMarquee);


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
