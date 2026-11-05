
(function () {
  'use strict';
  if (typeof window.Chart === 'undefined') { return; }

  
  
  const trendsCanvas = document.getElementById('trendsChart');
  let trendsLabels = [];
  let trendsData = [];
  if (trendsCanvas) {
    try { trendsLabels = JSON.parse(trendsCanvas.dataset.trendLabels || '[]'); } catch(e) { trendsLabels = []; }
    try { trendsData = JSON.parse(trendsCanvas.dataset.trendData || '[]'); } catch(e) { trendsData = []; }
  }

  const typesCanvas = document.getElementById('typesChart');
  let typeLabels = [];
  let typeCounts = [];
  if (typesCanvas) {
    try { typeLabels = JSON.parse(typesCanvas.dataset.typeLabels || '[]'); } catch(e) { typeLabels = []; }
    try { typeCounts = JSON.parse(typesCanvas.dataset.typeCounts || '[]'); } catch(e) { typeCounts = []; }
  }

  if (trendsCanvas) {
    new Chart(trendsCanvas, {
      type: 'line',
      data: {
        labels: trendsLabels.length ? trendsLabels : ['No data'],
        datasets: [{
          label: 'Violations',
          data: trendsData.length ? trendsData : [0],
          borderColor: '#6D28D9',
          backgroundColor: 'rgba(109,40,217,0.08)',
          tension: 0.4,
          fill: true,
          pointRadius: 3,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
      }
    });
  }

  if (typesCanvas && typeLabels.length) {
    new Chart(typesCanvas, {
      type: 'doughnut',
      data: {
        labels: typeLabels,
        datasets: [{
          data: typeCounts,
          backgroundColor: ['#6D28D9','#BE123C','#B45309','#1E40AF','#0F766E','#475569'],
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  } else if (typesCanvas) {
    typesCanvas.closest('.sc-card-body').innerHTML =
      '<p class="sc-empty">No violation type data yet.</p>';
  }
})();
