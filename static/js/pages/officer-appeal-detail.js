/* ==========================================================================
   Officer | Appeal Detail (officer-appeal-detail.js)
   Read-only page: broken image / evidence link guards are handled globally.
   Here we only smooth-scroll to the decision trail from the hero badge.
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
    var jump = document.querySelector('[data-scroll-to]');
    if (jump) {
      jump.addEventListener('click', function () {
        var target = document.querySelector(jump.getAttribute('data-scroll-to'));
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }
  });
})();
