
(function () {
  'use strict';

  var wall = document.getElementById('cctvWall');
  if (!wall) { return; }


  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function clockText(d) {
    return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }

  function fmtTime(sec) {
    if (!isFinite(sec) || sec < 0) { sec = 0; }
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return pad2(m) + ':' + pad2(s);
  }

  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) { el.textContent = value; }
  }

  function cacheBust(url) {
    if (!url) { return url; }
    return url + (url.indexOf('?') === -1 ? '?' : '&') + 't=' + Date.now();
  }

  function buildNoSignal(icon, label) {
    var box = document.createElement('div');
    box.className = 'cctv-nosignal';
    var i = document.createElement('i');
    i.className = icon;
    box.appendChild(i);
    box.appendChild(document.createTextNode(label));
    return box;
  }


  var wallClock = document.getElementById('cctvWallClock');
  var tileClocks = wall.querySelectorAll('[data-cctv-clock]');

  function tickClocks() {
    var t = clockText(new Date());
    if (wallClock) { wallClock.textContent = t; }
    for (var i = 0; i < tileClocks.length; i++) { tileClocks[i].textContent = t; }
  }
  tickClocks();
  window.setInterval(tickClocks, 1000);


  var searchInput = document.getElementById('cctvSearch');
  var cols = Array.prototype.slice.call(wall.querySelectorAll('.cctv-col'));
  var noMatchBox = document.getElementById('cctvNoMatch');

  function applyClientFilter() {
    if (!searchInput) { return; }
    var term = searchInput.value.trim().toLowerCase();
    var visible = 0;
    cols.forEach(function (col) {
      var haystack = col.getAttribute('data-search') || '';
      var show = !term || haystack.indexOf(term) !== -1;
      col.hidden = !show;
      if (show) { visible++; }
    });
    if (noMatchBox) {
      noMatchBox.hidden = !(term && visible === 0 && cols.length > 0);
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', applyClientFilter);
    applyClientFilter();
  }


  Array.prototype.forEach.call(wall.querySelectorAll('[data-cctv-snapshot]'), function (img) {
    var feed = img.closest('.cctv-feed');
    var skeleton = feed ? feed.querySelector('[data-cctv-skeleton]') : null;
    var noSignal = feed ? feed.querySelector('[data-cctv-nosignal]') : null;
    function reveal() { if (skeleton) { skeleton.hidden = true; } }
    function fail() {
      if (skeleton) { skeleton.hidden = true; }
      img.style.display = 'none';
      if (noSignal) { noSignal.hidden = false; }
    }
    img.addEventListener('load', reveal);
    img.addEventListener('error', fail);
    if (img.complete && img.naturalWidth > 0) { reveal(); }
    if (img.complete && img.naturalWidth === 0) { fail(); }
  });

  Array.prototype.forEach.call(wall.querySelectorAll('[data-cctv-video]'), function (video) {
    var feed = video.closest('.cctv-feed');
    var skeleton = feed ? feed.querySelector('[data-cctv-skeleton]') : null;
    function reveal() { if (skeleton) { skeleton.hidden = true; } }
    function fail() {
      reveal();
      video.style.display = 'none';
      if (feed && !feed.querySelector('.cctv-nosignal')) {
        var box = buildNoSignal('bi bi-wifi-off', 'NO SIGNAL');
        feed.appendChild(box);
      }
    }
    video.addEventListener('loadeddata', reveal);
    video.addEventListener('error', fail);
    if (video.readyState >= 2) { reveal(); }
  });


  var overlay = document.createElement('div');
  overlay.id = 'cctvZoomOverlay';
  overlay.className = 'cctv-zoom';
  overlay.innerHTML =
    '<div class="cctv-zoom-panel" role="dialog" aria-modal="true" aria-label="Camera video review console">' +
    '  <div class="cctv-zoom-head">' +
    '    <div class="cctv-zoom-id">' +
    '      <span id="cctvZoomLed" class="cctv-led cctv-led-live"><span class="cctv-led-dot"></span><span id="cctvZoomLedText">LIVE</span></span>' +
    '      <span class="cctv-zoom-title" id="cctvZoomTitle"></span>' +
    '    </div>' +
    '    <div class="cctv-zoom-head-right">' +
    '      <span class="cctv-zoom-meta" id="cctvZoomMeta"></span>' +
    '      <span class="cctv-zoom-clock" id="cctvZoomClock">--:--:--</span>' +
    '      <button type="button" class="cctv-zoom-close" id="cctvZoomClose" aria-label="Close review console">&times;</button>' +
    '    </div>' +
    '  </div>' +
    '  <div class="cctv-zoom-stage" id="cctvZoomStage"></div>' +
    '  <div class="cctv-zoom-note" id="cctvZoomNote" hidden>' +
    '    <i class="bi bi-info-circle" aria-hidden="true"></i>' +
    '    Snapshot source - video seek available for streamed cameras' +
    '  </div>' +
    '  <div class="cctv-zoom-console" id="cctvZoomConsole">' +
    '    <button type="button" class="cz-btn cz-play" id="czPlay" title="Play / pause (Space)" aria-label="Play or pause">' +
    '      <i class="bi bi-pause-fill" id="czPlayIcon"></i>' +
    '    </button>' +
    '    <div class="cz-seek-group">' +
    '      <span class="cz-time" id="czTimeCurrent">00:00</span>' +
    '      <input type="range" class="cz-seek" id="czSeek" min="0" max="100" step="0.1" value="0" aria-label="Seek position">' +
    '      <span class="cz-time" id="czTimeTotal">00:00</span>' +
    '    </div>' +
    '    <div class="cz-jump-group">' +
    '      <button type="button" class="cz-btn" data-cz-seek="-20" title="Back 20 seconds">-20s</button>' +
    '      <button type="button" class="cz-btn" data-cz-seek="-10" title="Back 10 seconds">-10s</button>' +
    '      <button type="button" class="cz-btn" data-cz-seek="10" title="Forward 10 seconds">+10s</button>' +
    '      <button type="button" class="cz-btn" data-cz-seek="20" title="Forward 20 seconds">+20s</button>' +
    '    </div>' +
    '    <div class="cz-speed-group" id="czSpeedGroup">' +
    '      <button type="button" class="cz-btn cz-speed" data-cz-speed="0.5">0.5x</button>' +
    '      <button type="button" class="cz-btn cz-speed is-active" data-cz-speed="1">1x</button>' +
    '      <button type="button" class="cz-btn cz-speed" data-cz-speed="2">2x</button>' +
    '    </div>' +
    '  </div>' +
    '  <div class="cctv-zoom-foot">Double-click backdrop or press Esc to close | Space: play/pause | Left / Right arrows: seek 5s</div>' +
    '</div>';
  document.body.appendChild(overlay);

  var stage = document.getElementById('cctvZoomStage');
  var consoleBar = document.getElementById('cctvZoomConsole');
  var noteBox = document.getElementById('cctvZoomNote');
  var zoomClock = document.getElementById('cctvZoomClock');
  var seekBar = document.getElementById('czSeek');
  var timeCurrent = document.getElementById('czTimeCurrent');
  var timeTotal = document.getElementById('czTimeTotal');
  var playBtn = document.getElementById('czPlay');
  var playIcon = document.getElementById('czPlayIcon');
  var speedGroup = document.getElementById('czSpeedGroup');

  var activeVideo = null;
  var snapshotTimer = null;
  var seekDragging = false;
  var unbindVideo = [];

  function setLed(statusKey) {
    var led = document.getElementById('cctvZoomLed');
    var text = document.getElementById('cctvZoomLedText');
    if (!led || !text) { return; }
    led.className = 'cctv-led';
    if (statusKey === 'live') {
      led.classList.add('cctv-led-live');
      text.textContent = 'LIVE';
    } else if (statusKey === 'nofeed') {
      led.classList.add('cctv-led-nofeed');
      text.textContent = 'NO FEED';
    } else {
      led.classList.add('cctv-led-off');
      text.textContent = 'OFFLINE';
    }
  }

  function resetConsoleUi() {
    seekBar.value = 0;
    timeCurrent.textContent = '00:00';
    timeTotal.textContent = '00:00';
    if (playIcon) { playIcon.className = 'bi bi-play-fill'; }
    Array.prototype.forEach.call(speedGroup.querySelectorAll('.cz-speed'), function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-cz-speed') === '1');
    });
  }

  function setConsoleMode(mode) {
    consoleBar.classList.toggle('is-disabled', mode !== 'video');
  }

  function clearVideoBindings() {
    unbindVideo.forEach(function (fn) { fn(); });
    unbindVideo = [];
  }

  function stopSnapshotRefresh() {
    if (snapshotTimer) {
      window.clearInterval(snapshotTimer);
      snapshotTimer = null;
    }
  }

  function bindVideoControls(video) {
    function onMeta() {
      seekBar.max = isFinite(video.duration) ? video.duration : 100;
      timeTotal.textContent = fmtTime(video.duration);
    }
    function onTimeUpdate() {
      if (!seekDragging) {
        seekBar.value = isFinite(video.duration) ? clamp(video.currentTime, 0, video.duration) : 0;
      }
      timeCurrent.textContent = fmtTime(video.currentTime);
    }
    function onPlay() { if (playIcon) { playIcon.className = 'bi bi-pause-fill'; } }
    function onPause() { if (playIcon) { playIcon.className = 'bi bi-play-fill'; } }
    function onRate() {
      var rate = String(video.playbackRate);
      Array.prototype.forEach.call(speedGroup.querySelectorAll('.cz-speed'), function (btn) {
        var value = btn.getAttribute('data-cz-speed');
        btn.classList.toggle('is-active', value === rate);
      });
    }
    video.addEventListener('loadedmetadata', onMeta);
    video.addEventListener('timeupdate', onTimeUpdate);
    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);
    video.addEventListener('ratechange', onRate);
    unbindVideo.push(function () {
      video.removeEventListener('loadedmetadata', onMeta);
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
      video.removeEventListener('ratechange', onRate);
    });
    onMeta();
    onTimeUpdate();
    onRate();
  }

  function openZoom(tile) {
    var camId = tile.getAttribute('data-camera-id') || 'CAM';
    var location = tile.getAttribute('data-location') || '';
    var meta = tile.getAttribute('data-meta') || '';
    var stream = tile.getAttribute('data-stream') || '';
    var snapshot = tile.getAttribute('data-snapshot') || '';
    var kind = tile.getAttribute('data-kind') || 'none';
    var statusKey = tile.getAttribute('data-status') || 'offline';

    setText('cctvZoomTitle', camId + (location ? ' | ' + location : ''));
    setText('cctvZoomMeta', meta);
    setLed(statusKey);

    stage.innerHTML = '';
    clearVideoBindings();
    stopSnapshotRefresh();
    activeVideo = null;
    resetConsoleUi();

    if (kind === 'video' && stream) {
      var video = document.createElement('video');
      video.controls = true;
      video.autoplay = true;
      video.loop = true;
      video.muted = true;
      video.playsInline = true;
      video.src = stream;
      stage.appendChild(video);
      activeVideo = video;
      bindVideoControls(video);
      noteBox.hidden = true;
      setConsoleMode('video');
    } else if (kind === 'snapshot' && snapshot) {
      var img = document.createElement('img');
      img.src = cacheBust(snapshot);
      img.alt = camId + ' live snapshot';
      stage.appendChild(img);
      var noSignal = buildNoSignal('bi bi-wifi-off', 'NO SIGNAL');
      noSignal.hidden = true;
      stage.appendChild(noSignal);
      img.addEventListener('error', function () {
        img.style.display = 'none';
        noSignal.hidden = false;
      });
      snapshotTimer = window.setInterval(function () {
        img.style.display = '';
        noSignal.hidden = true;
        img.src = cacheBust(snapshot);
      }, 4000);
      noteBox.hidden = false;
      setConsoleMode('snapshot');
    } else if (kind === 'snapshot') {
      stage.appendChild(buildNoSignal('bi bi-slash-circle', 'SNAPSHOT PREVIEW UNAVAILABLE'));
      noteBox.hidden = false;
      setConsoleMode('none');
    } else {
      stage.appendChild(buildNoSignal('bi bi-camera-video-off', 'NO FEED SOURCE'));
      noteBox.hidden = true;
      setConsoleMode('none');
    }

    overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    tickZoomClock();
  }

  function closeZoom() {
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    stopSnapshotRefresh();
    clearVideoBindings();
    if (activeVideo) {
      activeVideo.pause();
      activeVideo.src = '';
      activeVideo.load();
      activeVideo = null;
    }
    stage.innerHTML = '';
    resetConsoleUi();
  }

  function tickZoomClock() {
    if (zoomClock) { zoomClock.textContent = clockText(new Date()); }
  }
  window.setInterval(tickZoomClock, 1000);


  Array.prototype.forEach.call(wall.querySelectorAll('.cctv-tile'), function (tile) {
    tile.addEventListener('dblclick', function () { openZoom(tile); });
    tile.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { openZoom(tile); }
    });
  });

  document.getElementById('cctvZoomClose').addEventListener('click', closeZoom);

  overlay.addEventListener('dblclick', function (e) {
    if (e.target === overlay) { closeZoom(); }
  });


  playBtn.addEventListener('click', function () {
    if (!activeVideo) { return; }
    if (activeVideo.paused) { activeVideo.play(); } else { activeVideo.pause(); }
  });

  Array.prototype.forEach.call(consoleBar.querySelectorAll('[data-cz-seek]'), function (btn) {
    btn.addEventListener('click', function () {
      if (!activeVideo || !isFinite(activeVideo.duration)) { return; }
      var delta = parseFloat(btn.getAttribute('data-cz-seek')) || 0;
      activeVideo.currentTime = clamp(activeVideo.currentTime + delta, 0, activeVideo.duration);
    });
  });

  Array.prototype.forEach.call(speedGroup.querySelectorAll('.cz-speed'), function (btn) {
    btn.addEventListener('click', function () {
      if (!activeVideo) { return; }
      activeVideo.playbackRate = parseFloat(btn.getAttribute('data-cz-speed')) || 1;
    });
  });

  seekBar.addEventListener('pointerdown', function () { seekDragging = true; });
  seekBar.addEventListener('pointerup', function () { seekDragging = false; });
  seekBar.addEventListener('pointercancel', function () { seekDragging = false; });
  seekBar.addEventListener('change', function () { seekDragging = false; });
  seekBar.addEventListener('input', function () {
    if (!activeVideo || !isFinite(activeVideo.duration)) { return; }
    var target = parseFloat(seekBar.value) || 0;
    activeVideo.currentTime = clamp(target, 0, activeVideo.duration);
    timeCurrent.textContent = fmtTime(target);
  });


  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeZoom(); return; }
    if (!overlay.classList.contains('is-open') || !activeVideo) { return; }

    var target = e.target;
    if (target && target.closest && target.closest('button, input, select, a, video')) { return; }
    if (e.code === 'Space') {
      e.preventDefault();
      if (activeVideo.paused) { activeVideo.play(); } else { activeVideo.pause(); }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      activeVideo.currentTime = clamp(activeVideo.currentTime - 5, 0, activeVideo.duration || 0);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      activeVideo.currentTime = clamp(activeVideo.currentTime + 5, 0, activeVideo.duration || 0);
    }
  });


  var feedUrl = wall.getAttribute('data-feed-url');

  function renderTicker(items) {
    var track = document.getElementById('cctvTicker');
    if (!track) { return; }
    track.innerHTML = '';
    items.slice(0, 8).forEach(function (d) {
      var item = document.createElement('span');
      item.className = 'cctv-ticker-item';
      var cam = document.createElement('span');
      cam.className = 'cctv-ticker-cam';
      cam.textContent = d.camera_id || 'CAM';
      var plate = document.createElement('span');
      plate.className = 'cctv-ticker-plate';
      plate.textContent = d.plate || 'UNKNOWN';
      var time = document.createElement('span');
      time.className = 'cctv-ticker-time';
      time.textContent = d.created_at_display || '';
      item.appendChild(cam);
      item.appendChild(plate);
      item.appendChild(time);
      track.appendChild(item);
    });
  }

  function pollFeed() {
    if (!feedUrl || !window.fetch) { return; }
    window.fetch(feedUrl, { credentials: 'same-origin' })
      .then(function (resp) { return resp.ok ? resp.json() : null; })
      .then(function (data) {
        if (!data) { return; }
        setText('cctvOnlineCount', data.online_count != null ? data.online_count : '-');
        setText('cctvOfflineCount', data.offline_count != null ? data.offline_count : '-');
        setText('cctvTotalCount', data.total_cameras != null ? data.total_cameras : '-');
        renderTicker(data.recent_detections || []);
      })
      .catch(function () {  });
  }

  if (feedUrl) {
    window.setInterval(pollFeed, 20000);
  }
})();
