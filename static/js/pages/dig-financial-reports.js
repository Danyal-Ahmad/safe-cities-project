(function () {
  'use strict';

  function series(el, attr) {
    return (el.getAttribute(attr) || '')
      .split(',')
      .filter(function (v) { return v !== ''; });
  }

  function initMonthly() {
    var canvas = document.getElementById('monthlyChart');
    if (!canvas || !window.scCharts) return;
    var labels = series(canvas, 'data-month-labels');
    var collected = series(canvas, 'data-month-collected').map(Number);
    var pending = series(canvas, 'data-month-pending').map(Number);
    window.scCharts.bar(canvas.id, labels, [
      { label: 'Collected', data: collected },
      { label: 'Pending', data: pending }
    ], { emptyMessage: 'No monthly revenue data yet' });
  }

  initMonthly();
})();
