
(function () {
  'use strict';

  

  
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
    if(typeof Chart === 'undefined') return;

    const trend = document.getElementById('chart-citizen-trend');
    if(trend && !trend.dataset.apiUrl) {
      let labels = [];
      let counts = [];
      try { labels = JSON.parse(trend.dataset.monthLabels || '[]'); } catch(e) { labels = []; }
      try { counts = JSON.parse(trend.dataset.monthCounts || '[]'); } catch(e) { counts = []; }
      if(labels.length > 0) {
        new Chart(trend, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Challans',
              data: counts,
              backgroundColor: 'rgba(2, 132, 199, 0.75)',
              borderColor: '#0284c7',
              borderWidth: 1,
              borderRadius: 6,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: 'rgba(0,0,0,0.05)' } },
              x: { grid: { display: false } }
            }
          }
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
        new Chart(types, {
          type: 'doughnut',
          data: {
            labels: labels,
            datasets: [{
              data: counts,
              backgroundColor: ['#ef4444', '#f59e0b', '#8b5cf6', '#10b981', '#0284c7'],
              borderColor: '#fff',
              borderWidth: 2,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } }
          }
        });
      }
    }
  }

  
  async function initChartFromAPI(canvas){
    if(typeof Chart === 'undefined') return;
    try {
      const apiUrl = canvas.dataset.apiUrl;
      const chartType = canvas.dataset.chartType || 'bar';
      const json = await scFetch(apiUrl);
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
      console.warn('API chart init failed:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    loadKPIs();
    initStaticCharts();
    document.querySelectorAll('canvas[data-api-url]').forEach(canvas => initChartFromAPI(canvas));
  });
})();
