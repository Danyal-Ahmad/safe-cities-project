/*!
 * SAFE CITIES PROJECT - public-messages.js
 * Temporary inline notifications on public pages: exactly the same behavior
 * as the portal sc-messages strips - inline below the header (never toast
 * style, never floating), auto-faded after a few seconds, dismissible by
 * the close button. Loaded by templates/public_base.html.
 */
(function () {
  'use strict';

  var DISMISS_AFTER_MS = 7000;

  function fadeOut(node) {
    if (node.__psFading) { return; }
    node.__psFading = true;
    node.style.transition = 'opacity .4s ease, transform .4s ease';
    node.style.opacity = '0';
    node.style.transform = 'translateY(-6px)';
    setTimeout(function () {
      var box = node.parentElement;
      node.remove();
      if (box && !box.children.length) { box.remove(); }
    }, 420);
  }

  function init() {
    document.querySelectorAll('.ps-messages .ps-msg').forEach(function (msg) {
      var btn = msg.querySelector('.ps-msg-close');
      if (btn) {
        btn.addEventListener('click', function () { fadeOut(msg); });
      }
      setTimeout(function () { fadeOut(msg); }, DISMISS_AFTER_MS);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
