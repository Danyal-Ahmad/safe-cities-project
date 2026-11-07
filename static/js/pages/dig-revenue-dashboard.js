(function () {
  'use strict';

  function series(el, attr) {
    return (el.getAttribute(attr) || '')
      .split(',')
      .filter(function (v) { return v !== ''; });
  }

  function initDaily() {
    var canvas = document.getElementById('dailyChart');
    if (!canvas || !window.scCharts) return;
    var labels = series(canvas, 'data-daily-labels');
    var collected = series(canvas, 'data-daily-collected').map(Number);
    var pending = series(canvas, 'data-daily-pending').map(Number);
    window.scCharts.bar(canvas.id, labels, [
      { label: 'Collected', data: collected },
      { label: 'Pending', data: pending }
    ], { emptyMessage: 'No daily collection data yet' });
  }

  function initStatus() {
    var canvas = document.getElementById('statusChart');
    if (!canvas || !window.scCharts) return;
    var labels = series(canvas, 'data-status-labels');
    var counts = series(canvas, 'data-status-counts').map(Number);
    window.scCharts.doughnut(canvas.id, labels, counts, {
      emptyMessage: 'No payment status data yet'
    });
  }

  initDaily();
  initStatus();
})();
