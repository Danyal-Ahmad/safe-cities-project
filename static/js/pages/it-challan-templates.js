(function () {
  'use strict';

  function buildPreview(frame) {
    var html = frame.getAttribute('data-it-preview') || '';
    if (!html.trim()) { return; }
    var iframe = document.createElement('iframe');
    iframe.setAttribute('sandbox', '');
    iframe.setAttribute('title', 'Template preview');
    iframe.setAttribute('loading', 'lazy');
    iframe.srcdoc = html;
    frame.appendChild(iframe);
  }

  function init() {
    var frames = document.querySelectorAll('.it-tpl-frame[data-it-preview]');
    for (var i = 0; i < frames.length; i++) { buildPreview(frames[i]); }

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
