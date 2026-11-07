/* DIG Analytics page - extracted from templates/dashboard/dig/analytics.html
 * NOTE: loaded WITHOUT `defer` on purpose. The original inline <script> executed
 * during HTML parsing, BEFORE the deferred Chart.js CDN script loaded, so its
 * chart initialization threw (Chart undefined) and the canvases stayed untouched.
 * Loading this file synchronously preserves that exact original behavior. */
(function () {
  'use strict';
  if (typeof window.Chart === 'undefined') { return; }

  // Chart series are supplied on the canvases via data-* attributes
  // (previously inlined with {{ trend_labels|safe }} etc.).
  const trendsCanvas = document.getElementById('trendsChart');
  let trendsLabels = [];
  let trendsData = [];
  if (trendsCanvas && window.scCharts) {
    window.scCharts.line(trendsCanvas.id,
      trendsLabels.length ? trendsLabels : [],
      [{ label: 'Violations', data: trendsData.length ? trendsData : [] }],
      { emptyMessage: 'No violation trend data yet' });
  }

  if (typesCanvas && typeLabels.length && window.scCharts) {
    window.scCharts.doughnut(typesCanvas.id, typeLabels, typeCounts, {
      colors: ['#6D28D9', '#BE123C', '#B45309', '#1E40AF', '#0F766E', '#475569'],
      emptyMessage: 'No violation type data yet'
    });
  } else if (typesCanvas) {
    typesCanvas.closest('.sc-card-body').innerHTML =
      '<p class="sc-empty">No violation type data yet.</p>';
  }
})();