/* Officer performance page — extracted from templates/dashboard/officer/performance.html
 * NOTE: loaded WITHOUT `defer` on purpose. The original inline <script> executed
 * during HTML parsing, BEFORE the deferred Chart.js CDN script loaded, so its
 * chart initialization threw (Chart undefined) and the canvases stayed untouched.
 * Loading this file synchronously preserves that exact original behavior. */
(function () {
  'use strict';
  if (typeof window.Chart === 'undefined') { return; }

  // Chart series are supplied on the canvases via data-* attributes
  // (previously inlined with {{ activity_labels|safe }} etc.).
  const actCanvas = document.getElementById('activityChart');
  let actLabels = [];
  let actData = [];
  if (actCanvas) {
    try { actLabels = JSON.parse(actCanvas.dataset.activityLabels || '[]'); } catch(e) { actLabels = []; }
    try { actData = JSON.parse(actCanvas.dataset.activityData || '[]'); } catch(e) { actData = []; }
  }

  const decCanvas = document.getElementById('decisionChart');
  const confirmed = decCanvas ? Number(decCanvas.dataset.confirmed || 0) : 0;
  const rejected  = decCanvas ? Number(decCanvas.dataset.rejected || 0) : 0;
  const flagged   = decCanvas ? Number(decCanvas.dataset.flagged || 0) : 0;

  if (actCanvas) {
    new Chart(actCanvas, {
      type: 'bar',
      data: {
        labels: actLabels.length ? actLabels : ['No data'],
        datasets: [{
          label: 'Reviews',
          data: actData.length ? actData : [0],
          backgroundColor: 'rgba(30,64,175,0.7)',
          borderRadius: 4,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
      }
    });
  }

  if (decCanvas && (confirmed || rejected || flagged)) {
    new Chart(decCanvas, {
      type: 'doughnut',
      data: {
        labels: ['Confirmed', 'Rejected', 'Flagged'],
        datasets: [{
          data: [confirmed, rejected, flagged],
          backgroundColor: ['#22c55e', '#ef4444', '#f59e0b'],
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  } else if (decCanvas) {
    decCanvas.closest('.sc-card-body').innerHTML =
      '<p class="sc-empty">No review data yet.</p>';
  }
})();
