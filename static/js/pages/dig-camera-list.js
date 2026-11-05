/* ==========================================================================
   DIG - Camera Network  (dashboard/dig/camera_list.html)
   Client-side registry filtering (search + health + active state)
   ========================================================================== */
(function () {
  'use strict';

  var searchInput = document.querySelector('[data-camera-search]');
  var healthSelect = document.querySelector('[data-camera-health-filter]');
  var activeSelect = document.querySelector('[data-camera-active-filter]');
  var resetBtn = document.querySelector('[data-camera-filter-reset]');
  var rows = Array.prototype.slice.call(document.querySelectorAll('[data-camera-row]'));
  var emptyBox = document.querySelector('[data-camera-empty]');
  var countBadge = document.querySelector('[data-count-badge]');

  if (!rows.length) return;

  var totalLabel = countBadge ? countBadge.textContent : '';

  function applyFilters() {
    var term = (searchInput && searchInput.value ? searchInput.value : '').trim().toLowerCase();
    var health = healthSelect ? healthSelect.value : '';
    var active = activeSelect ? activeSelect.value : '';
    var visible = 0;

    rows.forEach(function (row) {
      var haystack = (row.getAttribute('data-camera-id') || '') + ' ' +
                     (row.getAttribute('data-location') || '');
      var matchesTerm = !term || haystack.indexOf(term) !== -1;
      var matchesHealth = !health || row.getAttribute('data-health') === health;
      var matchesActive = !active || row.getAttribute('data-active') === active;
      var show = matchesTerm && matchesHealth && matchesActive;

      row.hidden = !show;
      if (show) visible++;
    });

    if (emptyBox) emptyBox.hidden = visible !== 0;

    if (countBadge) {
      countBadge.textContent = visible === rows.length
        ? totalLabel
        : visible + ' of ' + rows.length + ' cameras';
    }
  }

  if (searchInput) searchInput.addEventListener('input', applyFilters);
  if (healthSelect) healthSelect.addEventListener('change', applyFilters);
  if (activeSelect) activeSelect.addEventListener('change', applyFilters);

  if (resetBtn) {
    resetBtn.addEventListener('click', function () {
      if (searchInput) searchInput.value = '';
      if (healthSelect) healthSelect.value = '';
      if (activeSelect) activeSelect.value = '';
      applyFilters();
    });
  }
})();
