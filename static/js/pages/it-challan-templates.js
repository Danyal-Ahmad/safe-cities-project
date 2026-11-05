(function () {
  'use strict';

  var A4_WIDTH = 794;
  var A4_HEIGHT = 1123;

  function buildPreview(frame) {
    var html = frame.getAttribute('data-it-preview') || '';
    if (!html.trim()) { return; }
    var iframe = document.createElement('iframe');
    iframe.setAttribute('sandbox', 'allow-same-origin');
    iframe.setAttribute('title', 'Template preview');
    iframe.setAttribute('loading', 'lazy');
    iframe.srcdoc = html;
    iframe.style.width = A4_WIDTH + 'px';
    iframe.style.height = A4_HEIGHT + 'px';
    iframe.style.border = '0';
    iframe.style.position = 'absolute';
    iframe.style.top = '0';
    iframe.style.left = '0';
    iframe.style.transformOrigin = 'top left';
    frame.appendChild(iframe);
    var scale = frame.clientWidth / A4_WIDTH;
    iframe.style.transform = 'scale(' + scale + ')';
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
