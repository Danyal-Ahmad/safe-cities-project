(function () {
  'use strict';

  function formatCNICValue(value) {
    var v = String(value || '').replace(/\D/g, '').substring(0, 13);
    if (v.length > 12) return v.substring(0, 5) + '-' + v.substring(5, 12) + '-' + v.substring(12);
    if (v.length > 5) return v.substring(0, 5) + '-' + v.substring(5);
    return v;
  }

  function bindPublicHome(root) {
    root.querySelectorAll('input[name="cnic"]').forEach(function (el) {
      el.addEventListener('input', function () {
        el.value = formatCNICValue(el.value);
      });
    });
    root.querySelectorAll('input[name="plate"]').forEach(function (el) {
      el.addEventListener('input', function () {
        el.value = el.value.toUpperCase().replace(/[^A-Z0-9-]/g, '');
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { bindPublicHome(document); });
  } else {
    bindPublicHome(document);
  }

  window.formatCNIC = formatCNICValue;
})();
