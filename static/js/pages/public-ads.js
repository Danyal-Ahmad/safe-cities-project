
(function () {
  'use strict';

  var MAX_COPIES = 12;

  function initTicker() {
    var track = document.getElementById('psTickerTrack');
    var viewport = track ? track.parentElement : null;
    var bar = viewport ? viewport.parentElement : null;
    if (!track || !viewport || !bar) return;
    if (!track.children.length) return;

    var CLONE_FLAG = 'data-ticker-clone';

    function originals() {
      var out = [];
      for (var i = 0; i < track.children.length; i++) {
        var n = track.children[i];
        if (n.nodeType === 1 && !n.hasAttribute(CLONE_FLAG)) out.push(n);
      }
      return out;
    }

    var items = originals();


    var setWidth = 0;
    for (var i = 0; i < items.length; i++) {
      setWidth += items[i].offsetWidth;
    }
    var gap = parseFloat(getComputedStyle(track).columnGap || getComputedStyle(track).gap) || 48;
    setWidth += gap * items.length;
    if (setWidth < 1) return;


    var needed = Math.max(1, Math.ceil((viewport.clientWidth + 60) / setWidth));
    if (needed % 2 === 0) needed += 1;
    var copies = Math.min(needed, MAX_COPIES);
    if (copies % 2 === 0) copies -= 1;
    if (copies < 1) copies = 1;

    for (var c = 0; c < copies; c++) {
      for (var j = 0; j < items.length; j++) {
        var clone = items[j].cloneNode(true);
        clone.setAttribute(CLONE_FLAG, 'true');
        clone.setAttribute('aria-hidden', 'true');
        track.appendChild(clone);
      }
    }

    var halfWidth = track.scrollWidth / 2;
    var seconds = Math.max(18, Math.round(halfWidth / 55));
    bar.style.setProperty('--ps-ticker-duration', seconds + 's');
    bar.classList.add('is-scrolling');
  }

  function ready(fn) {
    if (document.readyState !== 'loading') { fn(); }
    else { document.addEventListener('DOMContentLoaded', fn); }
  }
  ready(initTicker);
  window.addEventListener('load', initTicker);
})();
