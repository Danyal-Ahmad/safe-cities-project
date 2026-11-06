/* Public challan detail page
   - Marks broken evidence images (instead of inline onerror attributes)
   - Scrolls to the appeal section when the URL carries ?tab=appeal|review
     (matches the redirect targets used by the appeal POST handler) */
(function () {
  'use strict';

  function init() {
    // Evidence images: fade out if the file is missing
    document.querySelectorAll('.pd-evidence-fig img').forEach(function (img) {
      img.addEventListener('error', function () {
        img.classList.add('is-broken');
      });
      if (img.complete && img.naturalWidth === 0) {
        img.classList.add('is-broken');
      }
    });

    // Deep link to the appeal section
    try {
      var tab = new URLSearchParams(window.location.search).get('tab');
      if (tab === 'appeal' || tab === 'review') {
        var target = document.getElementById('appeal');
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch (e) { /* older browsers: ignore */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
