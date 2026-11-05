
(function () {
  'use strict';

  

  
  async function initChartFromAPI(canvas){
    if(typeof Chart === 'undefined') return;
    try {
      const apiUrl   = canvas.dataset.apiUrl;
      const chartType = canvas.dataset.chartType || 'bar';
      const json = await (await fetch(apiUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })).json();

      new Chart(canvas, {
        type: chartType,
        data: json,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: chartType === 'doughnut' } },
          scales: chartType === 'doughnut' ? {} : {
            x: { grid: { display: false } },
            y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } }
          }
        }
      });
    } catch(e) {
      console.warn('Chart init failed:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('canvas[data-api-url]').forEach(canvas => initChartFromAPI(canvas));
  });
})();
