/* ==========================================================================
   Officer | Flagged List (officer-flagged-list.js)
   Clickable rows: navigate to the detection detail page.
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
