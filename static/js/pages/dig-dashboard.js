/* DIG Command Center dashboard — extracted from templates/dashboard/dig/dashboard.html */
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

  // Fetch helper (CSRF-safe)
  async function scFetch(url, options={}){
    const resp = await fetch(url, {
      ...options,
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json', ...(options.headers||{}) },
    });
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  // KPI real-time loading
  async function loadKPIs(){
    // The KPI card exposes the dashboard KPI API endpoint via data-api-url
    // (previously injected inline with {% url 'dig:api_dashboard_kpis' %}).
    const card = document.querySelector('.md-kpi-value[data-api-url]');
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

  // Generic Chart.js from API
  async function initChartFromAPI(canvas){
    if(typeof Chart === 'undefined') return;
    try {
      const apiUrl   = canvas.dataset.apiUrl;
      const chartType = canvas.dataset.chartType || 'bar';
      const indexAxis = canvas.dataset.indexAxis || 'x';
      const json = await scFetch(apiUrl);

      const opts = {
        type: chartType,
        data: json,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 600, easing: 'easeOutQuart' },
          plugins: { legend: { display: chartType === 'line' } },
          scales: {
            x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
            y: { grid: { color: 'rgba(0,0,0,0.05)' } }
          }
        }
      };
      if(indexAxis === 'y') {
        opts.options.indexAxis = 'y';
        opts.options.scales.x.grid = { color: 'rgba(0,0,0,0.05)' };
      }
      if(chartType === 'line') {
        opts.options.scales.y.beginAtZero = true;
      }

      new Chart(canvas, opts);
    } catch(e) {
      console.warn('Chart init failed:', e);
    }
  }

  // Recent detections table renderer
  async function initRecentDetections(){
    const tbl = document.getElementById('recent-detections-table');
    if(!tbl) return;

    // Rows are supplied by the server via data-recent-detections (JSON)
    // (previously inlined by the Django template loop).
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
