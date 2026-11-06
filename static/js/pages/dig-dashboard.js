
(function () {
  'use strict';

  function prettyLabel(s) {
    return String(s === undefined || s === null ? '' : s)
      .replace(/[_-]+/g, ' ')
      .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

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

    const card = document.querySelector('.scr-stat-value[data-api-url]');
    if(!card) return;
    try {
      const apiBase = card.dataset.apiUrl;
      const data = (await scFetch(apiBase)).kpis;
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

  async function initChartFromAPI(canvas){
    if (typeof Chart === 'undefined' || !window.scCharts) return;
    try {
      const apiUrl   = canvas.dataset.apiUrl;
      const chartType = canvas.dataset.chartType || 'bar';
      const indexAxis = canvas.dataset.indexAxis || 'x';
      const json = await scFetch(apiUrl);

      if (chartType === 'doughnut' || chartType === 'pie') {
        let data = json.data;
        if (!data && Array.isArray(json.datasets) && json.datasets[0] && Array.isArray(json.datasets[0].data)) {
          data = json.datasets[0].data;
        }
        window.scCharts.doughnut(canvas.id, (json.labels || []).map(prettyLabel), data || [], {});
      } else if (chartType === 'line') {
        (json.datasets || []).forEach(function (d) { if (!d.type) d.type = 'line'; });
        window.scCharts.line(canvas.id, (json.labels || []).map(prettyLabel), json.datasets || []);
      } else if (indexAxis === 'y') {
        window.scCharts.horizontalBar(canvas.id, (json.labels || []).map(prettyLabel), json.datasets || []);
      } else {

        const lineish = Array.isArray(json.datasets) && json.datasets.some(function (d) {
          return d && (d.tension !== undefined || d.fill !== undefined);
        });
        if (lineish) {
          window.scCharts.line(canvas.id, (json.labels || []).map(prettyLabel), json.datasets || []);
        } else {
          window.scCharts.bar(canvas.id, (json.labels || []).map(prettyLabel), json.datasets || []);
        }
      }
    } catch(e) { console.warn('Chart init failed:', e); }
  }

  async function initRecentDetections(){
    const tbl = document.getElementById('recent-detections-table');
    if(!tbl) return;

    let recent = [];
    try { recent = JSON.parse(tbl.dataset.recentDetections || '[]'); } catch(e) { recent = []; }

    const tbody = tbl.querySelector('tbody');
    tbody.innerHTML = recent.map(d => `
      <tr>
        <td style="font-family:monospace;font-weight:700;">#${d.id}</td>
        <td>${d.camera}</td>
        <td><span class="md-badge md-badge-dark" style="font-family:monospace;">${d.plate}</span></td>
        <td><span class="md-badge ${d.confidence>0.85?'md-badge-success':d.confidence>0.6?'md-badge-warning':'md-badge-danger'}">${(d.confidence*100).toFixed(0)}%</span></td>
        <td><span class="md-badge ${d.status==='Pending'?'md-badge-warning':d.status==='Flagged'?'md-badge-danger':'md-badge-success'}">${d.status}</span></td>
        <td style="font-size:0.8rem;color:var(--md-text-muted);">${d.created_at}</td>
      </tr>`).join('');
  }

  document.addEventListener('DOMContentLoaded', function(){
    loadKPIs();
    document.querySelectorAll('canvas[data-api-url]').forEach(canvas => initChartFromAPI(canvas));
    initRecentDetections();
  });
})();
