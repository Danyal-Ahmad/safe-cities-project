

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
