(function () {
  'use strict';

  function scaleThumb(el) {
    var iframe = el.querySelector('iframe');
    if (!iframe) return;
    var scale = Math.min(el.clientWidth / 794, el.clientHeight / 1123);
    iframe.style.transform = 'scale(' + scale + ')';
  }

  function mountThumbs() {
    document.querySelectorAll('[data-dts-thumb]').forEach(function (el) {
      var raw = el.dataset.dtsThumb || '';
      if (!raw) return;
      var frame = document.createElement('iframe');
      frame.setAttribute('sandbox', '');
      frame.srcdoc = raw;
      el.appendChild(frame);
      frame.addEventListener('load', function () { scaleThumb(el); });
      if (window.ResizeObserver) {
        new ResizeObserver(function () { scaleThumb(el); }).observe(el);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountThumbs);
  } else {
    mountThumbs();
  }
})();
