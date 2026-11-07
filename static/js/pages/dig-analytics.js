/* DIG Analytics page - chart initializers for trends + violation types.
 * Chart series are supplied on the canvases via data-* attributes. */
(function () {
  'use strict';

  function readJSON(value) {
    try { return JSON.parse(value || '[]'); } catch (e) { return []; }
  }

  function render() {
    if (typeof window.Chart === 'undefined' || !window.scCharts) return;

    const trendsCanvas = document.getElementById('trendsChart');
    if (trendsCanvas) {
      const trendsLabels = readJSON(trendsCanvas.dataset.trendLabels);
      const trendsData = readJSON(trendsCanvas.dataset.trendData);
      window.scCharts.line(trendsCanvas.id,
        trendsLabels,
        [{ label: 'Violations', data: trendsData }],
        { emptyMessage: 'No violation trend data yet' });
    }

    const typesCanvas = document.getElementById('typesChart');
    if (typesCanvas) {
      const typeLabels = readJSON(typesCanvas.dataset.typeLabels);
      const typeCounts = readJSON(typesCanvas.dataset.typeCounts);
      if (typeLabels.length) {
        window.scCharts.doughnut(typesCanvas.id, typeLabels, typeCounts, {
          colors: ['#6D28D9', '#BE123C', '#B45309', '#1E40AF', '#0F766E', '#475569'],
          emptyMessage: 'No violation type data yet'
        });
      } else {
        const body = typesCanvas.closest('.sc-card-body');
        if (body) body.innerHTML = '<p class="sc-empty">No violation type data yet.</p>';
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
