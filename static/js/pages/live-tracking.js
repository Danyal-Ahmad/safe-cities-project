
(function () {
  'use strict';

  let showBBoxes = true;
  const canvas = document.getElementById('trackingCanvas');
  const ctx = canvas ? canvas.getContext('2d') : null;
  const stageContainer = document.getElementById('stageContainer');
  const videoPlayer = document.getElementById('liveVideoPlayer');
  let simulatedDetections = [];

  const selectedCameraPk = stageContainer ? (stageContainer.dataset.selectedCameraPk || '') : '';
  const selectedCameraId = stageContainer ? (stageContainer.dataset.selectedCameraId || '') : '';

  function resizeCanvas() {
    if (!canvas || !stageContainer) return;
    canvas.width = stageContainer.clientWidth;
    canvas.height = stageContainer.clientHeight;
    drawBoxes();
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  document.getElementById('btnToggleBBox')?.addEventListener('click', function() {
    showBBoxes = !showBBoxes;
    document.getElementById('bboxStateText').textContent = showBBoxes ? 'ON' : 'OFF';
    drawBoxes();
  });

  function drawBoxes() {
    if (!ctx || !canvas) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!showBBoxes) return;

    const w = canvas.width;
    const h = canvas.height;

    simulatedDetections.forEach((det, idx) => {

      let bx = (det.bbox && det.bbox[0]) ? (det.bbox[0] * w) : (w * 0.25 + (idx * 60) % (w * 0.5));
      let by = (det.bbox && det.bbox[1]) ? (det.bbox[1] * h) : (h * 0.35 + (idx * 40) % (h * 0.3));
      let bw = (det.bbox && det.bbox[2]) ? (det.bbox[2] * w) : 180;
      let bh = (det.bbox && det.bbox[3]) ? (det.bbox[3] * h) : 120;

      ctx.strokeStyle = '#00F0FF';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(bx, by, bw, bh);

      const cLen = 14;
      ctx.strokeStyle = '#10B981';
      ctx.lineWidth = 3.5;

      ctx.beginPath(); ctx.moveTo(bx, by + cLen); ctx.lineTo(bx, by); ctx.lineTo(bx + cLen, by); ctx.stroke();

      ctx.beginPath(); ctx.moveTo(bx + bw - cLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cLen); ctx.stroke();

      ctx.beginPath(); ctx.moveTo(bx, by + bh - cLen); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + cLen, by + bh); ctx.stroke();

      ctx.beginPath(); ctx.moveTo(bx + bw - cLen, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - cLen); ctx.stroke();

      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.fillRect(bx, by - 24, Math.max(120, bw * 0.7), 24);
      ctx.fillStyle = '#00F0FF';
      ctx.font = 'bold 12px monospace';
      ctx.fillText(`${det.plate || 'TARGET'} (${Math.round((det.confidence || 0.85) * 100)}%)`, bx + 6, by - 7);
    });
  }

  function selectDetection(id, plate, conf, camera, status, imgUrl) {
    const inspectorId = document.getElementById('inspectorId');
    const inspectorPlate = document.getElementById('inspectorPlate');
    const inspectorConf = document.getElementById('inspectorConfidence');
    const inspectorCamera = document.getElementById('inspectorCamera');
    const inspectorImage = document.getElementById('inspectorImage');
    const targetBadge = document.getElementById('targetStatusBadge');
    const btnStudio = document.getElementById('btnSendToStudio');
    const btnDetail = document.getElementById('btnDetailLink');

    if (inspectorId) inspectorId.textContent = '#' + id;
    if (inspectorPlate) inspectorPlate.textContent = plate || 'UNREADABLE';
    if (inspectorConf) inspectorConf.textContent = conf;
    if (inspectorCamera) inspectorCamera.textContent = camera || 'Camera';
    if (targetBadge) targetBadge.textContent = status || 'PENDING';
    if (inspectorImage && imgUrl) inspectorImage.src = imgUrl;

    const camId = selectedCameraPk;
    if (btnStudio) btnStudio.href = `/portal/officer/manual/?camera_id=${camId}&focus=${id}`;
    if (btnDetail) btnDetail.href = `/portal/officer/detection/${id}/`;

    document.querySelectorAll('.md-feed-item').forEach(el => el.classList.remove('active'));
  }

  document.querySelectorAll('.timeline-thumb-card[data-det-id], .md-feed-item[data-det-id]').forEach(function (el) {
    el.addEventListener('click', function () {
      selectDetection(
        el.dataset.detId,
        el.dataset.plate,
        el.dataset.conf,
        el.dataset.camera,
        el.dataset.status,
        el.dataset.img
      );
    });
  });

  document.querySelectorAll('select[name="camera_id"]').forEach(function (sel) {
    sel.addEventListener('change', function () { sel.form.submit(); });
  });

  function bindImgError(img, apply) {
    if (!img) return;
    img.addEventListener('error', apply);
    if (img.complete && img.naturalWidth === 0) apply();
  }

  document.querySelectorAll('img#liveVideoPlayer:not([data-snapshot-fallback])').forEach(function (img) {
    bindImgError(img, function () { img.src = '/static/img/no_signal.png'; });
  });

  document.querySelectorAll('img#liveVideoPlayer[data-snapshot-fallback]').forEach(function (img) {
    bindImgError(img, function () {
      img.style.display = 'none';
      var ns = document.getElementById('noSignalState');
      if (ns) ns.style.display = 'flex';
    });
  });

  document.querySelectorAll('#timelineGallery img, .md-feed-item img, #inspectorImage').forEach(function (img) {
    bindImgError(img, function () { img.style.visibility = 'hidden'; });
  });

  function pollRealtimeStream() {
    const camId = selectedCameraId;
    fetch(`/realtime/api/live/recent-detections/?camera_id=${encodeURIComponent(camId)}&limit=15`)
      .then(res => res.json())
      .then(data => {
        if (data && data.items && data.items.length) {
          simulatedDetections = data.items;
          document.getElementById('hudDetectionCount').textContent = `AI Targets: ${data.items.length}`;
          drawBoxes();
        }
      })
      .catch(() => {});
  }

  setTimeout(resizeCanvas, 500);
  setInterval(pollRealtimeStream, 2000);
  pollRealtimeStream();
})();
