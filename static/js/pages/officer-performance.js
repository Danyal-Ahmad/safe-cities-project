/* Officer performance page - review activity bar + decision doughnut.
 * Chart series are supplied on the canvases via data-* attributes. */
(function () {
  'use strict';

  function readJSON(value) {
    try { return JSON.parse(value || '[]'); } catch (e) { return []; }
  }

  function render() {
    if (typeof window.Chart === 'undefined' || !window.scCharts) return;

    const actCanvas = document.getElementById('activityChart');
    if (actCanvas) {
      const actLabels = readJSON(actCanvas.dataset.activityLabels);
      const actData = readJSON(actCanvas.dataset.activityData);
      window.scCharts.bar(actCanvas.id, actLabels,
        [{ label: 'Reviews', data: actData }], {
          emptyMessage: 'No review activity recorded yet'
        });
    }

    const decCanvas = document.getElementById('decisionChart');
    if (decCanvas) {
      const confirmed = parseInt(decCanvas.dataset.confirmed || '0', 10) || 0;
      const rejected = parseInt(decCanvas.dataset.rejected || '0', 10) || 0;
      const flagged = parseInt(decCanvas.dataset.flagged || '0', 10) || 0;
      if (confirmed || rejected || flagged) {
        window.scCharts.doughnut(decCanvas.id, ['Confirmed', 'Rejected', 'Flagged'],
          [confirmed, rejected, flagged], {
            colors: ['#22A45D', '#E23B4E', '#F5A623'],
            emptyMessage: 'No decisions recorded yet'
          });
      } else {
        const body = decCanvas.closest('.sc-card-body');
        if (body) body.innerHTML = '<p class="sc-empty">No decisions recorded yet.</p>';
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
