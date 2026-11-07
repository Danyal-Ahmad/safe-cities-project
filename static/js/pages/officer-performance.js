/* Officer performance page - extracted from templates/dashboard/officer/performance.html
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
  if (actCanvas && window.scCharts) {
    window.scCharts.bar(actCanvas.id, actLabels, [{ label: 'Reviews', data: actData }], {
      emptyMessage: 'No review activity recorded yet'
    });
  }

  if (decCanvas && window.scCharts && (confirmed || rejected || flagged)) {
    window.scCharts.doughnut(decCanvas.id, ['Confirmed', 'Rejected', 'Flagged'],
      [confirmed, rejected, flagged], {
        colors: ['#22A45D', '#E23B4E', '#F5A623'],
        emptyMessage: 'No decisions recorded yet'
      });
  }
})();