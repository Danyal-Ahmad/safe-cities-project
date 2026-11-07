

(function () {
  'use strict';

  var input = document.getElementById('id-q');

  if (input) {
    input.addEventListener('input', function () {
      input.value = input.value.toUpperCase().replace(/[^A-Z0-9\-\s]/g, '');
    });
  }

  Array.prototype.slice.call(document.querySelectorAll('[data-example]')).forEach(function (chip) {
    chip.addEventListener('click', function () {
      if (!input) return;
      input.value = chip.getAttribute('data-example') || '';
      var form = input.closest('form');
      if (form) form.submit();
    });
  });

  Array.prototype.slice.call(document.querySelectorAll('.md-conf-fill[data-conf]')).forEach(function (bar) {
    var value = parseFloat(bar.getAttribute('data-conf'));
    if (isNaN(value)) value = 0;
    var pct = Math.max(0, Math.min(100, value * 100));
    bar.style.width = pct.toFixed(1) + '%';

    if (pct >= 80) {
      bar.style.background = '#14B8A6';
    } else if (pct >= 50) {
      bar.style.background = '#2563EB';
    } else {
      bar.style.background = '#F5A623';
    }
  });
})();
