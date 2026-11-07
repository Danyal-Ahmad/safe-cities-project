(function () {
  'use strict';

  function readCookie(name) {
    if (!document.cookie) return null;
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var c = parts[i].trim();
      if (c.substring(0, name.length + 1) === (name + '=')) {
        return decodeURIComponent(c.substring(name.length + 1));
      }
    }
    return null;
  }

  function csrfToken() {
    return readCookie('safecity_csrftoken') ||
      (document.querySelector('input[name="csrfmiddlewaretoken"]') || {}).value ||
      '';
  }

  function statusBadge(status) {
    if (status === 'ok') return '<span class="sc-badge sc-badge-ok"><i class="bi bi-check-circle"></i> OK</span>';
    if (status === 'warn') return '<span class="sc-badge sc-badge-amber"><i class="bi bi-exclamation-triangle"></i> Warn</span>';
    return '<span class="sc-badge sc-badge-red"><i class="bi bi-x-circle"></i> Fail</span>';
  }

  function resultRow(item) {
    var latency = item.latency_ms > 0 ? item.latency_ms + ' ms' : '-';
    return '' +
      '<div class="it-env-result">' +
        '<div class="it-env-result-head">' +
          '<span class="fw-semibold"><i class="bi bi-hdd-network me-1"></i>' + item.label + '</span>' +
          statusBadge(item.status) +
        '</div>' +
        '<div class="it-env-result-detail sc-text-sm sc-text-muted">' + item.detail + '</div>' +
        '<div class="it-env-result-latency sc-mono sc-text-xs">' + latency + '</div>' +
      '</div>';
  }

  function render(data) {
    var container = document.querySelector('[data-env-results]');
    var summary = document.querySelector('[data-env-summary]');
    var last = document.querySelector('[data-env-last]');
    if (!container) return;
    var html = data.results.map(resultRow).join('');
    container.innerHTML = html;
    if (summary) {
      summary.hidden = false;
      summary.className = 'ms-auto sc-badge ' +
        (data.fail > 0 ? 'sc-badge-red' : (data.warn > 0 ? 'sc-badge-amber' : 'sc-badge-ok'));
      summary.textContent = data.ok + ' ok / ' + data.warn + ' warn / ' + data.fail + ' fail';
    }
    if (last) {
      last.textContent = new Date().toLocaleTimeString();
    }
  }

  function setBusy(busy) {
    var btn = document.querySelector('[data-env-run]');
    if (!btn) return;
    btn.disabled = busy;
    btn.innerHTML = busy
      ? '<span class="spinner-border spinner-border-sm me-1"></span> Testing connections...'
      : '<i class="bi bi-broadcast-pin me-1"></i>Run Live Connectivity Test';
  }

  function init() {
    var btn = document.querySelector('[data-env-run]');
    if (!btn) return;
    btn.addEventListener('click', function () {
      setBusy(true);
      window.fetch(btn.dataset.url || window.location.href + 'test/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken(),
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin'
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(render)
        .catch(function (err) {
          var container = document.querySelector('[data-env-results]');
          if (container) {
            container.innerHTML = '<div class="it-env-error"><i class="bi bi-x-circle me-1"></i>Live test failed to run: ' + err.message + '</div>';
          }
        })
        .then(function () { setBusy(false); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
