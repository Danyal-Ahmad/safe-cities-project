(function () {
  'use strict';

  function renderResult(box, payload) {
    var ok = !!payload.verified;
    var html = '';
    if (ok) {
      html = '<span class="badge bg-success"><i class="bi bi-patch-check-fill me-1"></i>Chain verified</span>';
    } else {
      html = '<span class="badge bg-danger"><i class="bi bi-shield-exclamation me-1"></i>Verification failed</span>';
    }
    html += '<div class="small text-muted mt-1">Stored: ' + (payload.stored || '-') + '</div>';
    html += '<div class="small text-muted">Recomputed: ' + (payload.recomputed || '-') + '</div>';
    box.innerHTML = html;
  }

  function bindButtons() {
    document.querySelectorAll('[data-verify-btn]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var url = btn.getAttribute('data-verify-url');
        var id = btn.getAttribute('data-detection-id');
        var box = document.querySelector('[data-verify-result="' + id + '"]');
        if (!url || !box) return;
        btn.disabled = true;
        box.innerHTML = '<span class="badge bg-secondary"><i class="bi bi-arrow-repeat me-1"></i>Recomputing hash...</span>';
        fetch(url, {
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        })
          .then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
          })
          .then(function (data) { renderResult(box, data); })
          .catch(function () {
            box.innerHTML = '<span class="badge bg-danger">Verification request failed</span>';
          })
          .finally(function () { btn.disabled = false; });
      });
    });
  }

  bindButtons();
})();
