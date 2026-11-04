/* ==========================================================================
   Officer — Detection Detail (officer-detection-detail.js)
   Image fallbacks, notes counters + validation, confirm dialogs, copy hash.
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

    /* ---- Broken image fallbacks ---------------------------------------- */
    document.querySelectorAll('img[data-img-fallback]').forEach(function (img) {
      img.addEventListener('error', function () {
        var box = img.closest('.sc-evidence-imgbox') || img.parentElement;
        img.remove();
        if (box) { box.classList.add('is-broken'); }
      });
    });

    /* ---- Confidence meter widths (data-driven, no inline CSS) ---------- */
    document.querySelectorAll('.sc-conf-fill[data-conf-width]').forEach(function (el) {
      var w = parseInt(el.getAttribute('data-conf-width'), 10);
      if (!isNaN(w)) {
        el.style.width = Math.max(0, Math.min(100, w)) + '%';
      }
    });

    /* ---- Notes character counters -------------------------------------- */
    document.querySelectorAll('[data-notes-input]').forEach(function (input) {
      var min = parseInt(input.getAttribute('data-notes-min') || '0', 10);
      var form = input.closest('form');
      var counter = form ? form.querySelector('[data-notes-counter]') : null;
      function update() {
        var len = input.value.trim().length;
        if (counter) {
          counter.textContent = String(len);
          if (counter.parentElement) {
            counter.parentElement.classList.toggle('is-valid-note', len >= min);
          }
        }
      }
      input.addEventListener('input', update);
      update();
    });

    /* ---- Submit validation + destructive-action confirmation ----------- */
    document.querySelectorAll('form[data-notes-form]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        var min = parseInt(form.getAttribute('data-notes-min') || '0', 10);
        var input = form.querySelector('[data-notes-input]');
        var len = input ? input.value.trim().length : min;

        if (len < min) {
          e.preventDefault();
          if (window.Swal) {
            window.Swal.fire({
              icon: 'error',
              title: 'Notes are too short',
              text: 'Please write at least ' + min + ' characters (' + len + ' so far).',
              confirmButtonColor: '#16294E'
            });
          } else {
            window.alert('Please write at least ' + min + ' characters (' + len + ' so far).');
          }
          if (input) { input.focus(); }
          return;
        }

        var confirmTitle = form.getAttribute('data-confirm-title');
        if (confirmTitle) {
          e.preventDefault();
          if (window.Swal) {
            window.Swal.fire({
              icon: 'warning',
              title: confirmTitle,
              text: form.getAttribute('data-confirm-text') || '',
              showCancelButton: true,
              confirmButtonText: form.getAttribute('data-confirm-button') || 'Confirm',
              confirmButtonColor: '#E23B4E',
              cancelButtonColor: '#94A3B8'
            }).then(function (result) {
              if (result.isConfirmed) {
                form.removeAttribute('data-notes-form');
                form.submit();
              }
            });
          } else if (window.confirm(confirmTitle)) {
            form.removeAttribute('data-notes-form');
            form.submit();
          }
        }
      });
    });

    /* ---- Copy evidence hash --------------------------------------------- */
    document.querySelectorAll('[data-copy-value]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var value = btn.getAttribute('data-copy-value') || '';
        var original = btn.innerHTML;
        function restore() { btn.innerHTML = original; }
        function done(ok) {
          btn.innerHTML = ok
            ? '<i class="bi bi-clipboard-check"></i> Copied'
            : '<i class="bi bi-clipboard-x"></i> Failed';
          window.setTimeout(restore, 1600);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(value).then(function () { done(true); }, function () { done(false); });
        } else {
          done(false);
        }
      });
    });

  });
})();
