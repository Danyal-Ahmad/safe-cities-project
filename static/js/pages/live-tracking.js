
(function () {
  'use strict';

  let showBBoxes = true;
  const canvas = document.getElementById('trackingCanvas');
  const ctx = canvas ? canvas.getContext('2d') : null;
  const stageContainer = document.getElementById('stageContainer');
  const videoPlayer = document.getElementById('liveVideoPlayer');


  let trackedDetections = [];


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

    trackedDetections.forEach(function (det) {


      let box = det.vehicle_bbox && det.vehicle_bbox[2] > det.vehicle_bbox[0]
        ? det.vehicle_bbox : det.bbox;
      if (!box || box.length !== 4) { return; }

      const bx = box[0] * w;
      const by = box[1] * h;
      const bw = Math.max(24, (box[2] - box[0]) * w);
      const bh = Math.max(18, (box[3] - box[1]) * h);


      ctx.strokeStyle = '#00F0FF';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(bx, by, bw, bh);


      if (det.bbox && det.bbox.length === 4) {
        ctx.strokeStyle = '#F5A623';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(det.bbox[0] * w, det.bbox[1] * h,
                       Math.max(14, (det.bbox[2] - det.bbox[0]) * w),
                       Math.max(10, (det.bbox[3] - det.bbox[1]) * h));
      }


      const cLen = Math.min(16, bw * 0.22);
      ctx.strokeStyle = '#10B981';
      ctx.lineWidth = 3.5;

      ctx.beginPath(); ctx.moveTo(bx, by + cLen); ctx.lineTo(bx, by); ctx.lineTo(bx + cLen, by); ctx.stroke();

      ctx.beginPath(); ctx.moveTo(bx + bw - cLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cLen); ctx.stroke();

      ctx.beginPath(); ctx.moveTo(bx, by + bh - cLen); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + cLen, by + bh); ctx.stroke();

      ctx.beginPath(); ctx.moveTo(bx + bw - cLen, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - cLen); ctx.stroke();


      const label = (det.plate || 'UNREADABLE') + ' (' + Math.round((det.confidence || 0) * 100) + '%)';
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      const labelW = Math.max(130, Math.min(bw, w - bx) * 0.9);
      ctx.fillRect(bx, Math.max(0, by - 24), labelW, 24);
      ctx.fillStyle = det.plate ? '#00F0FF' : '#F5A623';
      ctx.font = 'bold 12px monospace';
      ctx.fillText(label, bx + 6, Math.max(16, by - 7));
    });
  }


  function selectDetection(id, plate, conf, camera, status, imgUrl) {
    const inspectorId = document.getElementById('inspectorId');
    const inspectorPlate = document.getElementById('inspectorPlate');
    const inspectorConfidence = document.getElementById('inspectorConfidence');
    const inspectorCamera = document.getElementById('inspectorCamera');
    const inspectorImage = document.getElementById('inspectorImage');
    const targetBadge = document.getElementById('targetStatusBadge');
    const btnDetail = document.getElementById('btnDetailLink');

    if (inspectorId) inspectorId.textContent = '#' + id;
    if (inspectorPlate) inspectorPlate.textContent = plate || 'UNREADABLE';
    if (inspectorConfidence) inspectorConfidence.textContent = conf;
    if (inspectorCamera) inspectorCamera.textContent = camera || 'Camera';
    if (targetBadge) targetBadge.textContent = status || 'PENDING';
    if (inspectorImage && imgUrl) inspectorImage.src = imgUrl;

    const camId = selectedCameraPk;
    if (btnDetail) btnDetail.href = '/portal/officer/detection/' + id + '/';


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
    fetch('/realtime/api/live/recent-detections/?camera_id=' + encodeURIComponent(camId) + '&limit=15')
      .then(res => res.json())
      .then(data => {
        if (!data || !Array.isArray(data.items)) { return; }
        trackedDetections = data.items;
        const withBox = data.items.filter(it => it.bbox || it.vehicle_bbox).length;
        const counter = document.getElementById('hudDetectionCount');
        if (counter) {
          counter.textContent = 'AI Targets: ' + withBox + (data.items.length ? ' / ' + data.items.length + ' frames' : '');
        }
        drawBoxes();
      })
      .catch(() => {});
  }


  setTimeout(resizeCanvas, 500);
  setInterval(pollRealtimeStream, 2000);
  pollRealtimeStream();
})();
