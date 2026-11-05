/* Public popup ad dismiss - extracted from templates/challan/_public_ads.html */
(function () {
  'use strict';

  var SEEN_KEY = 'scAdPopupSeen';

  function seenIds() {
    try { return JSON.parse(sessionStorage.getItem(SEEN_KEY) || '[]'); } catch (e) { return []; }
  }

  function markSeen(id) {
    try {
      var seen = seenIds();
      if (seen.indexOf(id) === -1) { seen.push(id); sessionStorage.setItem(SEEN_KEY, JSON.stringify(seen)); }
    } catch (e) { /* storage unavailable: fall back to once per page view */ }
  }

  /* ---- popup channel ---- */
  function initPopup() {
    var popup = document.getElementById('psPopup');
    if (!popup) return;
    var adId = parseInt(popup.getAttribute('data-ad-id'), 10);
    var seen = seenIds();
    if (seen.indexOf(adId) !== -1) return;

    function close() {
      markSeen(adId);
      popup.classList.remove('is-open');
    }
    popup.addEventListener('click', function (ev) {
      if (ev.target.hasAttribute('data-ps-popup-close')) { close(); }
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && popup.classList.contains('is-open')) { close(); }
    });
    window.setTimeout(function () {
      popup.classList.add('is-open');
    }, 900);
  }

  /* ---- ticker channel ---- */
  function initTicker() {
    var track = document.getElementById('psTickerTrack');
    if (!track) return;
    var items = track.children.length;
    if (items < 1) return;
    if (items < 2) return;

    var viewport = track.parentElement;
    function contentWidth() {
      return Math.max(1, track.scrollWidth - viewport.clientWidth);
    }
    var pos = 0;
    var speed = 0.4;
    var last = performance.now();
    var paused = false;
    viewport.addEventListener('mouseenter', function () { paused = true; });
    viewport.addEventListener('mouseleave', function () { paused = false; });

    function step(now) {
      var dt = Math.min(64, now - last);
      last = now;
      if (!paused) {
        pos += speed * dt / 16.6667;
        var max = contentWidth();
        if (pos >= max) { pos = 0; }
        track.style.transform = 'translateX(' + (-pos) + 'px)';
      }
      requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* ---- hidden static post staging (index -100) ---- */
  function initStaging() {
    var staging = document.getElementById('psAdStaging');
    if (!staging) return;
    if (staging.getAttribute('data-index') !== '-100') return;
    if (!staging.hasAttribute('hidden')) { staging.setAttribute('hidden', ''); }
  }

  function ready(fn) {
    if (document.readyState !== 'loading') { fn(); }
    else { document.addEventListener('DOMContentLoaded', fn); }
  }
  ready(function () {
    initStaging();
    initPopup();
    initTicker();
  });
})();
