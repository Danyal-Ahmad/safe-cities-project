(function () {
  'use strict';

  function init() {
    var forms = document.querySelectorAll('form[data-it-confirm]');
    for (var i = 0; i < forms.length; i++) {
      (function (form) {
        form.addEventListener('submit', function (evt) {
          var msg = form.getAttribute('data-it-confirm') || 'Are you sure?';
          if (!window.confirm(msg)) { evt.preventDefault(); }
        });
      })(forms[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
