/* ==========================================================================
   AUDIT PORTAL | Compliance Reports (audit-compliance.js)
   Builds the doughnut charts from data-* attributes on the canvases
   (labels/values are pipe-separated so no inline JSON is required).
   ========================================================================== */
(function () {
  'use strict';

  var STATUS_COLORS = {
    PAID: '#22A45D',
    UNPAID: '#F5A623',
    VOIDED: '#E23B4E',
    PENDING: '#2563EB',
    OVERDUE: '#7C5CE0'
  };

  var PALETTE = [
    '#2563EB', '#7C5CE0', '#14B8A6', '#F5A623',
    '#E23B4E', '#2E5FB7', '#0D9488', '#B45309'
  ];

  function parseList(value) {
    return (value || '')
      .split('|')
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s.length > 0; });
  }

  function parseValues(value) {
    return parseList(value).map(Number).filter(function (n) { return !isNaN(n); });
  }

  function fallback(el) {
    if (!el) { return; }
    var box = el.closest('.audit-chart-box');
    if (box) {
      box.innerHTML = '<p class="sc-empty">No data available for this chart.</p>';
    }
  }

  function buildDoughnut(id, colorFor) {
    var el = document.getElementById(id);
    if (!el) { return; }
    var labels = parseList(el.getAttribute('data-labels'));
    var values = parseValues(el.getAttribute('data-values'));
    if (!labels.length || !values.length || labels.length !== values.length) {
      fallback(el);
      return;
    }
    if (!window.scCharts) {
      fallback(el);
      return;
    }
    var colors = labels.map(function (label, i) {
      return colorFor(label, i);
    });
    // Themed engine: stat ring for single categories, synced legend,
    // friendly empty state for all-zero data.
    window.scCharts.doughnut(el.id, labels, values, {
      colors: colors,
      emptyMessage: 'No data available for this chart yet'
    });
  }

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(function () {
    /* Payment-status breakdown - colours matched to status semantics. */
    buildDoughnut('auditStatusChart', function (label, i) {
      return STATUS_COLORS[label.toUpperCase()] || PALETTE[i % PALETTE.length];
    });

    /* Violation-type breakdown - palette-cycled colours. */
    buildDoughnut('auditTypeChart', function (label, i) {
      return PALETTE[i % PALETTE.length];
    });
  });
})();
