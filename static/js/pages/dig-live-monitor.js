/* Live CCTV Monitor - extracted from templates/dashboard/dig/live_monitor.html */
(function () {
  'use strict';

  /* ===== Double-click large view (camera grid) ===== */
  const overlay = document.createElement('div');
  overlay.id = 'cctvZoomOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(10,14,20,0.92);z-index:9999;display:none;align-items:center;justify-content:center;padding:32px;backdrop-filter:blur(4px);';
  overlay.innerHTML = `
    <div style="position:relative;max-width:min(1200px,96vw);width:100%;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <span class="badge bg-danger" id="cctvZoomBadge">&#9679; LIVE</span>
          <span id="cctvZoomTitle" style="color:#E4EDF9;font-weight:700;font-size:1rem;"></span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span id="cctvZoomClock" style="color:#8BE9C8;font-family:ui-monospace,monospace;font-size:0.8rem;"></span>
          <button type="button" id="cctvZoomClose" aria-label="Close"
            style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.25);color:#fff;width:34px;height:34px;border-radius:10px;font-size:1rem;cursor:pointer;">&times;</button>
        </div>
      </div>
      <div id="cctvZoomFeed" style="width:100%;aspect-ratio:16/9;background:#05070B;border-radius:14px;overflow:hidden;display:flex;align-items:center;justify-content:center;border:1px solid rgba(139,233,200,0.25);box-shadow:0 24px 80px rgba(0,0,0,0.6);"></div>
      <div style="margin-top:10px;color:#5B6B85;font-size:0.75rem;text-align:center;">Double-click or press Esc to close · Feed auto-refreshes</div>
    </div>`;
  document.body.appendChild(overlay);

  let refreshTimer = null;

  function openZoom(tile){
    const stream = tile.getAttribute('data-stream');
    const snapshot = tile.getAttribute('data-snapshot');
    const camId = tile.getAttribute('data-camera-id');
    const location = tile.getAttribute('data-location');
    document.getElementById('cctvZoomTitle').textContent = camId + (location ? ' · ' + location : '');
    const feed = document.getElementById('cctvZoomFeed');
    feed.innerHTML = '';
    if (stream && (/\.(mp4|webm|mov)(\?|$)/i.test(stream) || stream.includes('/media/'))) {
      const v = document.createElement('video');
      v.src = stream; v.muted = true; v.autoplay = true; v.loop = true; v.playsInline = true;
      v.style.cssText = 'width:100%;height:100%;object-fit:contain;';
      feed.appendChild(v);
    } else if (snapshot) {
      const img = document.createElement('img');
      img.src = snapshot + '?t=' + Date.now();
      img.alt = camId;
      img.style.cssText = 'width:100%;height:100%;object-fit:contain;';
      feed.appendChild(img);
      const noSignal = document.createElement('div');
      noSignal.style.cssText = 'position:absolute;color:#64748B;display:none;align-items:center;gap:8px;font-size:0.9rem;';
      noSignal.innerHTML = '<i class="bi bi-camera-video-off"></i> No Signal';
      feed.style.position = 'relative';
      feed.appendChild(noSignal);
      img.onerror = () => { img.style.display = 'none'; noSignal.style.display = 'flex'; };
      clearInterval(refreshTimer);
      refreshTimer = setInterval(() => { img.src = snapshot + '?t=' + Date.now(); }, 4000);
    } else {
      feed.innerHTML = '<div style="color:#64748B;display:flex;align-items:center;gap:8px;font-size:0.9rem;"><i class="bi bi-camera-video-off"></i> No Signal</div>';
    }
    const badge = document.getElementById('cctvZoomBadge');
    if (badge) { if (stream) { badge.className = 'badge bg-danger'; badge.innerHTML = '&#9679; LIVE'; } else { badge.className = 'badge bg-secondary'; badge.innerHTML = '&#9632; NO FEED'; } }
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    tickClock();
  }

  function closeZoom(){
    overlay.style.display = 'none';
    document.body.style.overflow = '';
    clearInterval(refreshTimer); refreshTimer = null;
    const v = document.querySelector('#cctvZoomFeed video'); if (v) v.pause();
    document.getElementById('cctvZoomFeed').innerHTML = '';
  }

  function tickClock(){
    const el = document.getElementById('cctvZoomClock');
    if (!el) return;
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    el.textContent = now.toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'}) + ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }

  document.querySelectorAll('.cctv-tile').forEach(tile => {
    tile.addEventListener('dblclick', () => openZoom(tile));
    tile.addEventListener('keydown', e => { if (e.key === 'Enter') openZoom(tile); });
  });
  document.getElementById('cctvZoomClose').addEventListener('click', closeZoom);
  overlay.addEventListener('dblclick', e => { if (e.target === overlay) closeZoom(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeZoom(); });

  /* ===== Camera filter ===== */
  document.getElementById('cctvSearch')?.addEventListener('input', function(e) {
    const q = e.target.value.toLowerCase().trim();
    document.querySelectorAll('.cctv-col').forEach(col => {
      const text = col.getAttribute('data-search') || '';
      col.style.display = text.includes(q) ? '' : 'none';
    });
  });

  /* ===== Snapshot fallback: hide broken feed image, show adjacent no-signal
   * state (previously inline onerror handler). ===== */
  document.querySelectorAll('.cctv-feed img').forEach(function (img) {
    const fallback = img.nextElementSibling;
    if (!fallback || !fallback.classList.contains('no-signal')) return;
    const apply = function () {
      img.style.display = 'none';
      fallback.style.display = 'flex';
    };
    img.addEventListener('error', apply);
    if (img.complete && img.naturalWidth === 0) apply();
  });
})();
