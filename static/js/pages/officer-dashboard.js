/* Officer Command Center dashboard - extracted from templates/dashboard/officer/dashboard.html */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {
    // 1. Live Clock
    setInterval(function() {
      const el = document.getElementById('liveClock');
      if (el) {
        const now = new Date();
        el.textContent = now.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }) + ' · ' + now.toLocaleTimeString();
      }
    }, 1000);

    // 2. Real-time Queue Polling
    // The queue-count endpoint is exposed on #queueVal via data-queue-api-url
    // (previously injected inline with {% url 'realtime:queue_count' %}).
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

    // 3. Activity Line Chart
    // Series data is supplied on the canvas via data-days-labels / data-days-counts
    // (previously inlined by the Django template loop).
    const actCanvas = document.getElementById('officerActivityChart');
    let daysLabels = [];
    let daysCounts = [];
    if (actCanvas) {
      try { daysLabels = JSON.parse(actCanvas.dataset.daysLabels || '[]'); } catch(e) { daysLabels = []; }
      try { daysCounts = JSON.parse(actCanvas.dataset.daysCounts || '[]'); } catch(e) { daysCounts = []; }
    }

    const ctxActivity = document.getElementById('officerActivityChart');
    if (ctxActivity && window.Chart) {
      new Chart(ctxActivity, {
        type: 'line',
        data: {
          labels: daysLabels.length ? daysLabels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
          datasets: [{
            label: 'Reviewed Violations',
            data: daysCounts.length ? daysCounts : [0, 0, 0, 0, 0, 0, 0],
            borderColor: '#1d4ed8',
            backgroundColor: 'rgba(29, 78, 216, 0.08)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointBackgroundColor: '#1d4ed8',
            pointRadius: 4,
            pointHoverRadius: 6,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#0f172a',
              padding: 10,
              cornerRadius: 8,
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
              grid: { color: 'rgba(226, 232, 240, 0.6)' }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    }

    // 4. Decision Distribution Doughnut
    // Counts are supplied on the canvas via data-confirmed / data-rejected
    // (previously inlined with {{ confirmed_total }} / {{ rejected_total }}).
    const ctxDoughnut = document.getElementById('officerDoughnutChart');
    if (ctxDoughnut && window.Chart) {
      const confCount = Number(ctxDoughnut.dataset.confirmed || 0);
      const rejcCount = Number(ctxDoughnut.dataset.rejected || 0);
      new Chart(ctxDoughnut, {
        type: 'doughnut',
        data: {
          labels: ['Confirmed', 'Rejected'],
          datasets: [{
            data: [confCount || (rejcCount ? 0 : 1), rejcCount],
            backgroundColor: ['#10b981', '#ef4444'],
            borderWidth: 2,
            borderColor: '#ffffff',
            hoverOffset: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#0f172a',
              padding: 10,
              cornerRadius: 8,
            }
          }
        }
      });
    }

    // Snapshot thumbnails: fade out when the frame image fails to load
    // (previously inline onerror="this.style.opacity='0.15';").
    document.querySelectorAll('.sc-table img').forEach(function (img) {
      const fade = function () { img.style.opacity = '0.15'; };
      img.addEventListener('error', fade);
      if (img.complete && img.naturalWidth === 0) fade();
    });
  });
})();
