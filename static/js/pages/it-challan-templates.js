
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
