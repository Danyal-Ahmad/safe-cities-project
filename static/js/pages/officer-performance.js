
(function () {
  'use strict';
  if (typeof window.Chart === 'undefined') { return; }


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