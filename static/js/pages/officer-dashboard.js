
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {

    setInterval(function() {
      const el = document.getElementById('liveClock');
      if (el) {
        const now = new Date();
        el.textContent = now.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }) + ' · ' + now.toLocaleTimeString();
      }
    }, 1000);

    const queueCfg = document.getElementById('queueVal');
    const queueApiUrl = queueCfg ? queueCfg.dataset.queueApiUrl : null;

    function pollQueue() {
      if (!queueApiUrl) return;
      fetch(queueApiUrl)
        .then(res => res.json())
        .then(data => {
          if (data && typeof data.count !== 'undefined') {
            const valEl = document.getElementById('queueVal');
            const pillEl = document.getElementById('kpiQueuePill');
            if (valEl) valEl.textContent = data.count;
            if (pillEl) pillEl.textContent = data.count;
          }
        })
        .catch(() => {});
    }
    setInterval(pollQueue, 5000);

    const actCanvas = document.getElementById('officerActivityChart');
    let daysLabels = [];
    let daysCounts = [];
    if (actCanvas) {
      try { daysLabels = JSON.parse(actCanvas.dataset.daysLabels || '[]'); } catch(e) { daysLabels = []; }
      try { daysCounts = JSON.parse(actCanvas.dataset.daysCounts || '[]'); } catch(e) { daysCounts = []; }
    }

    const ctxActivity = document.getElementById('officerActivityChart');
    if (ctxActivity && window.scCharts) {
      window.scCharts.line(ctxActivity.id,
        daysLabels.length ? daysLabels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        [{ label: 'Reviewed Violations', data: daysCounts.length ? daysCounts : [0, 0, 0, 0, 0, 0, 0] }],
        { emptyMessage: 'No reviews recorded this week' });
    }

    const ctxDoughnut = document.getElementById('officerDoughnutChart');
    if (ctxDoughnut && window.scCharts) {
      const confCount = Number(ctxDoughnut.dataset.confirmed || 0);
      const rejcCount = Number(ctxDoughnut.dataset.rejected || 0);
      window.scCharts.doughnut(ctxDoughnut.id, ['Confirmed', 'Rejected'], [confCount, rejcCount], {
        colors: ['#22A45D', '#E23B4E'],
        emptyMessage: 'No decisions recorded yet'
      });
    }

    document.querySelectorAll('.sc-table img').forEach(function (img) {
      const fade = function () { img.style.opacity = '0.15'; };
      img.addEventListener('error', fade);
      if (img.complete && img.naturalWidth === 0) fade();
    });
  });
})();
