/* SSP District Command dashboard — extracted from templates/dashboard/ssp/dashboard.html */
(function () {
  'use strict';

  // Live clock
  function updateClock(){
    const el = document.getElementById('live-clock');
    if(el) {
      const now = new Date();
      const pad = n => String(n).padStart(2,'0');
      el.textContent = now.toLocaleDateString('en-GB',{weekday:'short',day:'2-digit',month:'short',year:'numeric'}) +
        ' · ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
    }
  }
  updateClock();
  setInterval(updateClock, 1000);

  // Generic Chart.js from API
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
