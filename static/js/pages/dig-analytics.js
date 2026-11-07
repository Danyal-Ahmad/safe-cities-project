
(function () {
  'use strict';
  if (typeof window.Chart === 'undefined') { return; }


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