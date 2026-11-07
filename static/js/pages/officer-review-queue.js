
(function () {
  'use strict';

  const triageGrid = document.querySelector('.md-triage-grid');
  const hasSelected = triageGrid ? triageGrid.dataset.hasSelected === '1' : false;

  document.addEventListener('keydown', function(e) {

    const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') {
      return;
    }

    const key = e.key.toUpperCase();

    if (key === 'C') {
      const btn = document.getElementById('btnConfirmTriage');
      if (btn) {
        e.preventDefault();
        btn.click();
      }
    }

    else if (key === 'R') {
      const btn = document.getElementById('btnRejectTriage');
      if (btn) {
        e.preventDefault();
        btn.click();
      }
    }

    else if (key === 'F') {
      const btn = document.getElementById('btnFlagTriage');
      if (btn) {
        e.preventDefault();
        btn.click();
      }
    }
    else if (key === 'A') {
      if (hasSelected) {
        e.preventDefault();
      }
    }

    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const queueLinks = Array.from(document.querySelectorAll('.md-queue-item'));
      if (queueLinks.length === 0) return;

      let currentIndex = queueLinks.findIndex(l => l.classList.contains('active'));
      if (e.key === 'ArrowDown') {
        const nextIndex = currentIndex < queueLinks.length - 1 ? currentIndex + 1 : 0;
        queueLinks[nextIndex].click();
        e.preventDefault();
      } else if (e.key === 'ArrowUp') {
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : queueLinks.length - 1;
        queueLinks[prevIndex].click();
        e.preventDefault();
      }
    }
  });

  document.querySelectorAll('#queueItemsList img').forEach(function (img) {
    const fade = function () { img.style.opacity = '0.15'; };
    img.addEventListener('error', fade);
    if (img.complete && img.naturalWidth === 0) fade();
  });
})();

(function () {
  var main = document.getElementById('detailTargetImage');
  var strip = document.getElementById('seqFrameStrip');
  var tag = document.getElementById('seqFrameTag');
  if (!main || !strip) return;

  function sources() {
    return Array.prototype.slice.call(document.querySelectorAll('.seq-frame-src'));
  }

  function selectSlot(slot) {
    var srcs = sources();
    var chosen = srcs.filter(function (s) { return s.dataset.frameSlot === String(slot); })[0];
    if (chosen) {
      main.src = chosen.src;
      if (tag) {
        tag.textContent = chosen.dataset.frameLabel + ' / ' + (srcs.length < 10 ? '0' : '') + srcs.length;
      }
    }
    Array.prototype.forEach.call(strip.querySelectorAll('.seq-frame-btn'), function (b) {
      var active = b.dataset.frameSlot === String(slot);
      b.style.borderColor = active ? '#38bdf8' : '#334155';
      var im = b.querySelector('img');
      if (im) im.style.opacity = active ? '1' : '0.65';
    });
  }

  strip.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.seq-frame-btn') : null;
    if (btn) selectSlot(btn.dataset.frameSlot);
  });
})();

// --- live queue telemetry: poll /realtime/queue-count/ + realtime events ---
(function () {
  'use strict';

  var POLL_MS = 20000;
  var lastCount = null;
  var timer = null;

  function paint(count) {
    var pendingEls = document.querySelectorAll('[data-rq-pending]');
    var countEls = document.querySelectorAll('[data-rq-count]');
    var items = document.querySelectorAll('#queueItemsList .rq-item').length;

    if (typeof count === 'number' && !isNaN(count)) {
      if (lastCount !== null && count > lastCount) {
        pendingEls.forEach(function (el) {
          el.classList.remove('flash-increase');
          void el.offsetWidth;
          el.classList.add('flash-increase');
        });
      }
      lastCount = count;
      pendingEls.forEach(function (el) { el.textContent = String(count); });
      countEls.forEach(function (el) {
        el.textContent = (typeof count === 'number' && count > 0 ? count : items) + ' items';
      });
    }
  }

  function refresh() {
    var panel = document.querySelector('[data-rq-panel]');
    var api = panel ? panel.getAttribute('data-queue-api') : null;
    if (!api) { return; }
    fetch(api, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && typeof d.count === 'number') { paint(d.count); } })
      .catch(function () { /* offline: keep last values */ });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.querySelector('[data-rq-panel]');
    if (!panel) { return; }
    try {
      panel.setAttribute('data-queue-api', new URL('/realtime/queue-count/', window.location.href).href);
    } catch (e) {
      panel.setAttribute('data-queue-api', '/realtime/queue-count/');
    }
    var initial = document.querySelector('[data-rq-pending]');
    if (initial) {
      var n = parseInt(initial.textContent || '', 10);
      if (!isNaN(n)) { lastCount = n; }
    }
    timer = setInterval(refresh, POLL_MS);
    window.addEventListener('beforeunload', function () { clearInterval(timer); });
  });

  document.addEventListener('safecity:notification', function () { refresh(); });
  window.addEventListener('safecity:notification', function () { refresh(); });
})();
