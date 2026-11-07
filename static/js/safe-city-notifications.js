

(function () {
  'use strict';

  var SEEN_KEY = 'scPushSeen';
  var POLL_MS = 45000;

  function lsGet(key) {
    try { return JSON.parse(localStorage.getItem(key) || '[]'); } catch (e) { return []; }
  }
  function lsSet(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {  }
  }

  function seenIds() { return lsGet(SEEN_KEY); }

  function ensurePanel() {
    return {
      btn: document.getElementById('scBellBtn'),
      panel: document.getElementById('scBellPanel'),
      list: document.getElementById('scBellList'),
      count: document.getElementById('scBellCount'),
      enable: document.getElementById('scBellEnable'),
    };
  }

  function renderBell(items) {
    var ui = ensurePanel();
    if (!ui.list) return;
    var seen = seenIds();
    var fresh = 0;
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      var isNew = seen.indexOf(it.id) === -1;
      if (isNew) { fresh++; }
      html += '<div class="sc-bell-item' + (isNew ? ' is-new' : '') + '">'
        + '<div class="sc-bell-item-title">' + escapeHtml(it.title) + '</div>'
        + (it.body ? '<div class="sc-bell-item-body">' + escapeHtml(it.body) + '</div>' : '')
        + '</div>';
    }
    ui.list.innerHTML = html || '<div class="sc-bell-empty">No notifications right now.</div>';
    if (ui.count) {
      if (fresh > 0) { ui.count.textContent = fresh > 99 ? '99+' : String(fresh); ui.count.hidden = false; }
      else { ui.count.hidden = true; }
    }
    return fresh;
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function browserNotify(item) {
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;
    try {
      new Notification('Safe Cities Project', { body: item.title, tag: 'sc-push-' + item.id });
    } catch (e) {  }
  }

  function markAllSeen(items) {
    var ids = items.map(function (it) { return it.id; });
    lsSet(SEEN_KEY, ids);
  }

  function poll() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/auth/notifications/feed/', true);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.onload = function () {
      if (xhr.status !== 200) return;
      var data;
      try { data = JSON.parse(xhr.responseText); } catch (e) { return; }
      if (!data || !data.push) return;
      storeItems(data.push);
      renderBell(data.push);
      for (var i = 0; i < data.push.length; i++) {
        var seen = seenIds();
        if (seen.indexOf(data.push[i].id) === -1) { browserNotify(data.push[i]); }
      }
    };
    xhr.send();
  }

  function bindBell() {
    var ui = ensurePanel();
    if (!ui.btn || !ui.panel) return;
    ui.btn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var open = ui.panel.classList.toggle('is-open');
      ui.btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        var items = currentItems();
        markAllSeen(items);
        renderBell(items);
        var c = document.getElementById('scBellCount');
        if (c) { c.hidden = true; }
      }
    });
    document.addEventListener('click', function (ev) {
      if (!ui.panel.classList.contains('is-open')) return;
      if (ui.panel.contains(ev.target) || ui.btn.contains(ev.target)) return;
      ui.panel.classList.remove('is-open');
      ui.btn.setAttribute('aria-expanded', 'false');
    });
    if (ui.enable) {
      ui.enable.addEventListener('click', function () {
        if (!('Notification' in window)) { alert('This browser does not support notifications.'); return; }
        if (Notification.permission === 'granted') { return; }
        Notification.requestPermission().then(function (p) {
          if (p === 'granted') { ui.enable.textContent = 'Push on'; }
        });
      });
      if ('Notification' in window && Notification.permission === 'granted') {
        ui.enable.textContent = 'Push on';
      }
    }
  }

  var lastItems = [];
  function currentItems() { return lastItems; }
  function storeItems(items) { lastItems = items; }

  function initTicker() {
    var track = document.querySelector('#scTicker .sc-ticker-track');
    if (!track) return;
    if (track.children.length < 2) return;
    var viewport = track.parentElement;
    var pos = 0, last = performance.now(), paused = false;
    viewport.addEventListener('mouseenter', function () { paused = true; });
    viewport.addEventListener('mouseleave', function () { paused = false; });
    function step(now) {
      var dt = Math.min(64, now - last);
      last = now;
      if (!paused) {
        pos += 0.4 * dt / 16.6667;
        var max = Math.max(1, track.scrollWidth - viewport.clientWidth);
        if (pos >= max) { pos = 0; }
        track.style.transform = 'translateX(' + (-pos) + 'px)';
      }
      requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function ready(fn) {
    if (document.readyState !== 'loading') { fn(); }
    else { document.addEventListener('DOMContentLoaded', fn); }
  }
  ready(function () {
    bindBell();
    initTicker();
    poll();
    window.setInterval(poll, POLL_MS);
  });
})();
