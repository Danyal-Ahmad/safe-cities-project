/* ==========================================================================
   DIG — Add to Blacklist  (dashboard/dig/blacklist_add.html)
   Uppercase transform · placeholder switching · reason char counter
   ========================================================================== */
(function () {
  'use strict';

  var form = document.getElementById('blacklistAddForm');
  if (!form) return;

  /* ---------- Uppercase + charset guard on the value input ---------- */
  var valueInput = form.querySelector('[data-uppercase-input]');
  var typeSelect = form.querySelector('[data-type-select]');

  if (valueInput) {
    valueInput.addEventListener('input', function () {
      valueInput.value = valueInput.value.toUpperCase().replace(/[^A-Z0-9\-\s]/g, '');
    });
  }

  /* ---------- Placeholder + label follow the selected type ---------- */
  function syncPlaceholder() {
    if (!valueInput || !typeSelect) return;
    var isCnic = typeSelect.value === 'cnic';
    valueInput.placeholder = isCnic
      ? (form.getAttribute('data-cnic-placeholder') || '35202-1234567-8')
      : (form.getAttribute('data-plate-placeholder') || 'LEA-1100');
  }

  if (typeSelect) {
    typeSelect.addEventListener('change', syncPlaceholder);
    syncPlaceholder();
  }

  /* ---------- Reason character counter ---------- */
  var counter = form.querySelector('[data-char-counter-for]');
  var reason = document.getElementById('id-reason');

  if (counter && reason) {
    var max = parseInt(counter.getAttribute('data-max-chars') || '255', 10);

    var updateCounter = function () {
      var len = reason.value.length;
      counter.textContent = len + ' / ' + max;
      counter.classList.toggle('bl-counter-warn', len >= max * 0.85 && len < max);
      counter.classList.toggle('bl-counter-limit', len >= max);
    };

    reason.addEventListener('input', updateCounter);
    updateCounter();
  }

  /* ---------- Guard: trim before submit ---------- */
  form.addEventListener('submit', function (ev) {
    var incomplete = [];

    if (valueInput && !valueInput.value.trim()) incomplete.push(valueInput);
    if (reason && !reason.value.trim()) incomplete.push(reason);

    if (incomplete.length) {
      ev.preventDefault();
      incomplete.forEach(function (el) {
        el.classList.add('bl-invalid');
        setTimeout(function () { el.classList.remove('bl-invalid'); }, 1800);
      });
      if (typeof window.Swal !== 'undefined' && typeof window.Swal.fire === 'function') {
        window.Swal.fire({
          icon: 'warning',
          title: 'Missing details',
          text: 'A value and a reason are required to blacklist an entry.',
          confirmButtonColor: '#16294E'
        });
      } else {
        (incomplete[0] || form).focus();
      }
      return;
    }

    var btn = form.querySelector('[data-submit-btn]');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Adding…';
    }
  });
})();
