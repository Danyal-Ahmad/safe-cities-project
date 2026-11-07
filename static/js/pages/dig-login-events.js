(function () {
  'use strict';

  function series(el, attr) {
    return (el.getAttribute(attr) || '')
      .split(',')
      .filter(function (v) { return v !== ''; });
  }

  function initTrend() {
    var canvas = document.getElementById('loginTrendChart');
    if (!canvas || !window.scCharts) return;
    var labels = series(canvas, 'data-trend-labels');
    var success = series(canvas, 'data-trend-success').map(Number);
    var failed = series(canvas, 'data-trend-failed').map(Number);
    window.scCharts.line(canvas.id, labels, [
      { label: 'Successful', data: success },
      { label: 'Failed', data: failed }
    ], { emptyMessage: 'No login events in the last 7 days' });
  }

  initTrend();
})();
