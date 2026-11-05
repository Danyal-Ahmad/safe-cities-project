/* ==========================================================================
   Officer - Camera Feed (officer-camera-feed.js)
   Broken-frame fallbacks on the monitoring wall.
   ========================================================================== */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(function () {
    document.querySelectorAll('img[data-img-fallback]').forEach(function (img) {
      img.addEventListener('error', function () {
        var thumb = img.closest('.sc-feed-thumb') || img.parentElement;
        img.remove();
        if (thumb) { thumb.classList.add('is-broken'); }
      });
    });
  });
})();
