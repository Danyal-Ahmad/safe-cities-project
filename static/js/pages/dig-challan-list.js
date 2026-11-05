
(function () {
  'use strict';

  
  var plateInput = document.querySelector('[data-uppercase-input]');
  if (plateInput) {
    plateInput.addEventListener('input', function () {
      plateInput.value = plateInput.value.toUpperCase().replace(/[^A-Z0-9\-\s]/g, '');
    });
  }

  
  var summary = document.querySelector('[data-challan-summary]');
  var rows = Array.prototype.slice.call(document.querySelectorAll('[data-challan-row]'));
  if (!summary || !rows.length) return;

  var counters = { paid: 0, unpaid: 0, overdue: 0, voided: 0 };

  rows.forEach(function (row) {
    var status = row.getAttribute('data-status');
    var overdue = row.getAttribute('data-overdue') === '1';

    if (status === 'PAID') counters.paid++;
    else if (status === 'VOIDED') counters.voided++;
    else if (overdue) counters.overdue++;
    else counters.unpaid++;
  });

  Object.keys(counters).forEach(function (key) {
    var el = summary.querySelector('[data-stat="' + key + '"]');
    if (el) el.textContent = counters[key];
  });
})();
