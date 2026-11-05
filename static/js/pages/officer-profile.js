/* ==========================================================================
   Officer | Profile (officer-profile.js)
   Avatar fallback + light phone-format validation on the profile form.
   ========================================================================== */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(function () {

    /* Avatar fallback to the default icon if the upload is missing. */
    document.querySelectorAll('img[data-img-fallback]').forEach(function (img) {
      img.addEventListener('error', function () {
        var wrap = img.closest('.sc-profile-avatar-wrap') || img.parentElement;
        img.remove();
        if (wrap) { wrap.classList.add('is-broken'); }
      });
    });

    /* Phone sanity check - warn (not block) on obviously invalid input. */
    var form = document.querySelector('form[data-profile-form]');
    if (form) {
      form.addEventListener('submit', function (e) {
        var phoneInput = form.querySelector('[data-phone-input]');
        if (!phoneInput) { return; }
        var value = (phoneInput.value || '').trim();
        if (value && !/^\+?[0-9\s\-()]{7,20}$/.test(value)) {
          var proceed = true;
          if (window.Swal) {
            e.preventDefault();
            window.Swal.fire({
              icon: 'question',
              title: 'Unusual phone number',
              text: '"' + value + '" does not look like a phone number. Save anyway?',
              showCancelButton: true,
              confirmButtonText: 'Save anyway',
              cancelButtonText: 'Fix it',
              confirmButtonColor: '#16294E',
              cancelButtonColor: '#94A3B8'
            }).then(function (result) {
              if (result.isConfirmed) {
                form.removeAttribute('data-profile-form');
                form.submit();
              }
            });
            proceed = false;
          }
          if (proceed && !window.confirm('"' + value + '" does not look like a phone number. Save anyway?')) {
            e.preventDefault();
            phoneInput.focus();
          }
        }
      });
    }
  });
})();
