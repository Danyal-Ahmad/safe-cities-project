
(function () {
  'use strict';

  function formatCNICValue(value) {
    var v = String(value || '').replace(/\D/g, '').substring(0, 13);
    if (v.length > 12) return v.substring(0, 5) + '-' + v.substring(5, 12) + '-' + v.substring(12);
    if (v.length > 5) return v.substring(0, 5) + '-' + v.substring(5);
    return v;
  }

  function formatPlateValue(value) {
    var v = String(value || '').toUpperCase();
    v = v.replace(/[^A-Z0-9\- ]/g, '');
    
    v = v.replace(/[\- ]{2,}/g, function (m) { return m.charAt(0); });
    v = v.replace(/[\- ]$/, '');
    return v.substring(0, 12);
  }

  function bindPublicHome(root) {
    root.querySelectorAll('input[name="cnic"]').forEach(function (el) {
      el.addEventListener('input', function () {
        el.value = formatCNICValue(el.value);
      });
    });
    root.querySelectorAll('input[name="plate"]').forEach(function (el) {
      el.addEventListener('input', function () {
        el.value = formatPlateValue(el.value);
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
