/* ==========================================================================
   DIG | System Settings  (dashboard/dig/settings_edit.html)
   Secret visibility toggles · integration-mode warning · change tracking
   ========================================================================== */
(function () {
  'use strict';

  var form = document.getElementById('settingsForm');
  if (!form) return;

  /* ---------- Show / hide secret fields ---------- */
  Array.prototype.slice.call(document.querySelectorAll('[data-secret-toggle]')).forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = document.getElementById(btn.getAttribute('data-secret-toggle'));
      if (!input) return;
      var hidden = input.type === 'password';
      input.type = hidden ? 'text' : 'password';
      btn.innerHTML = hidden ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
      btn.setAttribute('aria-label', hidden ? 'Hide value' : 'Show value');
    });
  });

  /* ---------- Integration mode warning ---------- */
  var modeSelect = document.getElementById('id-integration-mode');
  var modeBanner = document.querySelector('[data-mode-banner]');

  function syncModeBanner() {
    if (!modeSelect || !modeBanner) return;
    var isReal = modeSelect.value === 'real';
    modeBanner.hidden = !isReal;
    modeBanner.classList.toggle('sc-banner-danger', isReal);
    modeBanner.classList.toggle('sc-banner', true);
  }

  if (modeSelect) {
    modeSelect.addEventListener('change', syncModeBanner);
    syncModeBanner();
  }

  /* ---------- Track unsaved changes ---------- */
  var initialState = new FormData(form).toString();
  var saveBtn = form.querySelector('[data-save-btn]');
  var savebar = document.querySelector('[data-savebar]');
  var dirty = false;

  function markDirty() {
    if (dirty) return;
    dirty = true;
    if (saveBtn && savebar) {
      saveBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Save changes';
      savebar.classList.add('set-savebar-dirty');
    }
  }

  form.addEventListener('input', markDirty);
  form.addEventListener('change', markDirty);

  window.addEventListener('beforeunload', function (ev) {
    var changed = new FormData(form).toString() !== initialState;
    if (changed) {
      ev.preventDefault();
      ev.returnValue = '';
    }
  });

  /* ---------- Required-field guard ---------- */
  form.addEventListener('submit', function (ev) {
    var missing = [];

    Array.prototype.slice.call(form.querySelectorAll('[data-label]')).forEach(function (el) {
      var tag = (el.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'select' && tag !== 'textarea') return;
      if (el.type === 'checkbox' || el.type === 'hidden' || el.type === 'password') return;
      if (el.required && !String(el.value || '').trim()) missing.push(el);
    });

    if (missing.length) {
      ev.preventDefault();
      missing.forEach(function (el) {
        el.classList.add('set-invalid');
        setTimeout(function () { el.classList.remove('set-invalid'); }, 1800);
      });
      if (typeof window.Swal !== 'undefined' && typeof window.Swal.fire === 'function') {
        window.Swal.fire({
          icon: 'warning',
          title: 'Missing required fields',
          text: 'Please complete: ' + missing.map(function (el) { return el.getAttribute('data-label'); }).join(', '),
          confirmButtonColor: '#16294E'
        });
      } else {
        missing[0].focus();
      }
      return;
    }

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Saving…';
    }
  });
})();
