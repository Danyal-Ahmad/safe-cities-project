
(function () {
  'use strict';

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

  async function initChartFromAPI(canvas){
    if (typeof Chart === 'undefined' || !window.scCharts) return;
    try {
      const apiUrl   = canvas.dataset.apiUrl;
      const chartType = canvas.dataset.chartType || 'bar';
      const json = await (await fetch(apiUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })).json();

      if (chartType === 'doughnut' || chartType === 'pie') {
        let data = json.data;
        if (!data && Array.isArray(json.datasets) && json.datasets[0] && Array.isArray(json.datasets[0].data)) {
          data = json.datasets[0].data;
        }
        window.scCharts.doughnut(canvas.id, json.labels || [], data || [], {});
      } else if (chartType === 'line') {
        (json.datasets || []).forEach(function (d) { if (!d.type) d.type = 'line'; });
        window.scCharts.line(canvas.id, json.labels || [], json.datasets || []);
      } else if (chartType === 'horizontalBar') {
        window.scCharts.horizontalBar(canvas.id, json.labels || [], json.datasets || []);
      } else {
        const lineish = Array.isArray(json.datasets) && json.datasets.some(function (d) {
          return d && (d.tension !== undefined || d.fill !== undefined);
        });
        if (lineish) {
          window.scCharts.line(canvas.id, json.labels || [], json.datasets || []);
        } else {
          window.scCharts.bar(canvas.id, json.labels || [], json.datasets || []);
        }
      }
    } catch(e) {
      console.warn('Chart init failed:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('canvas[data-api-url]').forEach(canvas => initChartFromAPI(canvas));
  });
})();
