/*!
 * SAFE CITIES PROJECT — it-challan-templates.js
 * Shared behavior for the DIG/IT challan template pages.
 * The preview cards now render the REAL PDF output server-side
 * (rasterised first page / uploaded PDF), so no iframe srcdoc
 * mounting is needed here — only the confirmation dialogs.
 */
(function () {
  'use strict';

  function init() {
    var forms = document.querySelectorAll('form[data-it-confirm]');
    for (var j = 0; j < forms.length; j++) {
      (function (form) {
        form.addEventListener('submit', function (evt) {
          var msg = form.getAttribute('data-it-confirm') || 'Are you sure?';
          if (!window.confirm(msg)) { evt.preventDefault(); }
        });
      })(forms[j]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
