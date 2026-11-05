/* ==========================================================================
   Officer - Vehicle Tracking (officer-vehicle-tracking.js)
   Timeline thumb fallbacks + clickable timeline items.
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
    // Broken frame thumbnails -> N/A placeholder.
    document.querySelectorAll('img[data-img-fallback]').forEach(function (img) {
      img.addEventListener('error', function () {
        var thumb = img.closest('.sc-vt-thumb') || img.parentElement;
        img.remove();
        if (thumb) { thumb.classList.add('is-broken'); }
      });
    });

    // Clickable timeline rows -> detection detail.
    document.querySelectorAll('.sc-row-link[data-href]').forEach(function (row) {
      row.addEventListener('click', function (e) {
        if (e.target.closest('a, button, input, select, textarea')) {
          return;
        }
        var href = row.getAttribute('data-href');
        if (href) {
          window.location.href = href;
        }
      });
    });
  });
})();
