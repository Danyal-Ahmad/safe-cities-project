

(function () {
  'use strict';

  function init() {

    document.querySelectorAll('.pd-evidence-fig img').forEach(function (img) {
      img.addEventListener('error', function () {
        img.classList.add('is-broken');
      });
      if (img.complete && img.naturalWidth === 0) {
        img.classList.add('is-broken');
      }
    });

    try {
      var tab = new URLSearchParams(window.location.search).get('tab');
      if (tab === 'appeal' || tab === 'review') {
        var target = document.getElementById('appeal');
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch (e) {  }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
