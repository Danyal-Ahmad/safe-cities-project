
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

  async function scFetch(url, options={}){
    const resp = await fetch(url, {
      ...options,
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json', ...(options.headers||{}) },
    });
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  async function loadKPIs(){
    const grid = document.querySelector('.scr-stats[data-kpi-api-url]');
    if (!grid) return;
    const apiBase = grid.dataset.kpiApiUrl;
    try {
      const data = (await scFetch(apiBase)).kpis || {};
      document.querySelectorAll('[data-key]').forEach(el => {
        const key = el.dataset.key;
        const fmt = el.dataset.format;
        if(!(key in data)) return;
        const val = data[key];
        if(fmt === 'pkr') {
          el.textContent = 'PKR ' + Number(val).toLocaleString('en-PK');
        } else {
          el.textContent = Number(val).toLocaleString('en-PK');
        }
      });
    } catch(e) { console.warn('KPI load failed:', e); }
  }

  function initStaticCharts(){
    if (typeof Chart === 'undefined' || !window.scCharts) return;

    const trend = document.getElementById('chart-citizen-trend');
    if(trend && !trend.dataset.apiUrl) {
      let labels = [];
      let counts = [];
      try { labels = JSON.parse(trend.dataset.monthLabels || '[]'); } catch(e) { labels = []; }
      try { counts = JSON.parse(trend.dataset.monthCounts || '[]'); } catch(e) { counts = []; }
      if(labels.length > 0) {
        window.scCharts.bar(trend.id, labels, [{ label: 'Challans', data: counts }], {
          emptyMessage: 'No challans in recent months'
        });
      }
    }

    const types = document.getElementById('chart-citizen-types');
    if(types && !types.dataset.apiUrl) {
      let labels = [];
      let counts = [];
      try { labels = JSON.parse(types.dataset.violationLabels || '[]'); } catch(e) { labels = []; }
      try { counts = JSON.parse(types.dataset.violationCounts || '[]'); } catch(e) { counts = []; }
      if(labels.length > 0) {
        window.scCharts.doughnut(types.id, labels, counts, {
          emptyMessage: 'No violations recorded'
        });
      }
    }
  }

  async function initChartFromAPI(canvas){
    if (typeof Chart === 'undefined' || !window.scCharts) return;
    try {
      const apiUrl = canvas.dataset.apiUrl;
      const chartType = canvas.dataset.chartType || 'bar';
      const json = await scFetch(apiUrl);

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
        window.scCharts.bar(canvas.id, json.labels || [], json.datasets || []);
      }
    } catch(e) {
      console.warn('API chart init failed:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    loadKPIs();
    initStaticCharts();
    document.querySelectorAll('canvas[data-api-url]').forEach(canvas => initChartFromAPI(canvas));
  });
})();
