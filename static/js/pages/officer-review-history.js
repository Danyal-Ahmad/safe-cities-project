

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

    document.querySelectorAll('[data-range-days]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var fromInput = document.getElementById('dateFromInput');
        var toInput = document.getElementById('dateToInput');
        var form = btn.closest('form');
        if (!fromInput || !toInput) { return; }
        var days = parseInt(btn.getAttribute('data-range-days'), 10);
        var to = new Date();
        var from = new Date();
        from.setDate(from.getDate() - (isNaN(days) ? 0 : days));
        function iso(d) {
          return d.toISOString().split('T')[0];
        }
        fromInput.value = iso(from);
        toInput.value = iso(to);
        if (form) { form.submit(); }
      });
    });
  });
})();
