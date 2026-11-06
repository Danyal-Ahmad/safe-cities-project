(function () {
  'use strict';

  function series(el, attr) {
    return (el.getAttribute(attr) || '')
      .split(',')
      .filter(function (v) { return v !== ''; });
  }

  function initTrend() {
    var canvas = document.getElementById('trendsChart');
    if (!canvas || !window.scCharts) return;
    var labels = series(canvas, 'data-trend-labels');
    var data = series(canvas, 'data-trend-data').map(Number);
    window.scCharts.line(canvas.id, labels, [
      { label: 'Challans', data: data }
    ], { emptyMessage: 'No challan trend data yet' });
  }

  function initTypes() {
    var canvas = document.getElementById('typesChart');
    if (!canvas || !window.scCharts) return;
    var labels = series(canvas, 'data-type-labels');
    var data = series(canvas, 'data-type-counts').map(Number);
    window.scCharts.bar(canvas.id, labels, [
      { label: 'Challans', data: data }
    ], { emptyMessage: 'No violation type data yet' });
  }

  initTrend();
  initTypes();
})();
