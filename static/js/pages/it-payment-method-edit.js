(function () {
  'use strict';

  function apply(typeSelect, groups) {
    var value = (typeSelect.value || '').trim();
    for (var i = 0; i < groups.length; i++) {
      var group = groups[i];
      var supported = (group.getAttribute('data-pm-types') || '').split(/[\s,]+/);
      var show = supported.indexOf(value) !== -1;
      group.classList[show ? 'remove' : 'add']('d-none');
    }
  }

  function init() {
    var typeSelect = document.querySelector('[data-pm-type-select]');
    var groups = document.querySelectorAll('.it-pm-group[data-pm-types]');
    if (!typeSelect || !groups.length) { return; }
    apply(typeSelect, groups);
    typeSelect.addEventListener('change', function () { apply(typeSelect, groups); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
