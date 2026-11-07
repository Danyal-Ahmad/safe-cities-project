

(function () {
    'use strict';

    const scLive = {};

    scLive._streams = scLive._streams || {};
    scLive._polling = scLive._polling || {};
    scLive._timelineFrames = scLive._timelineFrames || {};
    scLive._annotationLayers = scLive._annotationLayers || {};

    scLive.init = function (canvasId, streamUrl) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) { console.error('[scLive] Canvas not found:', canvasId); return null; }
        const ctx = canvas.getContext('2d');
        const placeholder = canvas.parentElement.querySelector('.sc-ws-placeholder');
        const badge = canvas.parentElement.querySelector('.sc-ws-badge');

        const state = {
            canvasId: canvasId,
            ctx: ctx,
            stream: null,
            video: null,
            running: false,
            animationId: null,
            overlayCtx: null,
        };

        scLive._streams[canvasId] = state;

        function resize() {
            const parent = canvas.parentElement;
            canvas.width = parent.clientWidth;
            canvas.height = parent.clientHeight;
        }
        resize();
        window.addEventListener('resize', resize);

        if (placeholder) placeholder.style.display = 'flex';

        return state;
    };

    scLive.start = function (canvasId, streamUrl) {
        streamUrl = streamUrl || '/api/live/stream/';
        let state = scLive._streams[canvasId];
        if (!state) state = scLive.init(canvasId, streamUrl);
        if (state.running) return;

        const video = document.createElement('video');
        video.autoplay = true;
        video.playsInline = true;
        video.muted = true;
        state.video = video;

        fetch(streamUrl, { credentials: 'same-origin' })
            .then(function (resp) { return resp.blob(); })
            .then(function (blob) {
                video.src = URL.createObjectURL(blob);
                return video.play();
            })
            .then(function () {
                state.running = true;
                const placeholder = state.canvas.parentElement?.querySelector('.sc-ws-placeholder');
                const badge = state.canvas.parentElement?.querySelector('.sc-ws-badge');
                if (placeholder) placeholder.style.display = 'none';
                if (badge) badge.style.display = 'flex';
                scLive._drawLoop(canvasId);
            })
            .catch(function (err) {
                console.error('[scLive] Stream error:', err);

                if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                    navigator.mediaDevices.getUserMedia({ video: true })
                        .then(function (stream) {
                            video.srcObject = stream;
                            state.stream = stream;
                            state.running = true;
                            const placeholder = state.canvas.parentElement?.querySelector('.sc-ws-placeholder');
                            if (placeholder) placeholder.style.display = 'none';
                            scLive._drawLoop(canvasId);
                        })
                        .catch(function (e) { console.error('[scLive] Camera error:', e); });
                }
            });
    };

    scLive.stop = function (canvasId) {
        const state = scLive._streams[canvasId];
        if (!state) return;
        state.running = false;
        if (state.animationId) cancelAnimationFrame(state.animationId);
        if (state.stream) {
            state.stream.getTracks().forEach(function (t) { t.stop(); });
        }
        if (state.video) {
            state.video.srcObject = null;
            URL.revokeObjectURL(state.video.src);
        }
        const placeholder = state.canvas.parentElement?.querySelector('.sc-ws-placeholder');
        const badge = state.canvas.parentElement?.querySelector('.sc-ws-badge');
        if (placeholder) placeholder.style.display = '';
        if (badge) badge.style.display = 'none';
    };

    scLive._drawLoop = function (canvasId) {
        const state = scLive._streams[canvasId];
        if (!state || !state.running) return;
        const video = state.video;
        const ctx = state.ctx;
        const canvas = state.canvas;

        if (video.readyState >= 2) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const vw = video.videoWidth, vh = video.videoHeight;
            const cw = canvas.width, ch = canvas.height;
            const scale = Math.max(cw / vw, ch / vh);
            const w = vw * scale, h = vh * scale;
            const x = (cw - w) / 2, y = (ch - h) / 2;
            ctx.drawImage(video, x, y, w, h);
        }

        state.animationId = requestAnimationFrame(function () { scLive._drawLoop(canvasId); });
    };

    scLive.drawOverlay = function (canvasId, detections) {
        const state = scLive._streams[canvasId];
        if (!state) return;
        const ctx = state.ctx;
        const canvas = state.canvas;
        detections = detections || [];

        detections.forEach(function (det) {
            const x = det.x * canvas.width;
            const y = det.y * canvas.height;
            const w = det.w * canvas.width;
            const h = det.h * canvas.height;
            const color = det.color || '#22c55e';
            const label = det.label || '';

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, w, h);

            const cs = 8;
            ctx.beginPath();
            ctx.moveTo(x, y + cs); ctx.lineTo(x, y); ctx.lineTo(x + cs, y);
            ctx.moveTo(x + w - cs, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + cs);
            ctx.moveTo(x + w, y + h - cs); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w - cs, y + h);
            ctx.moveTo(x + cs, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h - cs);
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.stroke();

            if (label) {
                ctx.fillStyle = color;
                const textW = ctx.measureText(label).width + 8;
                ctx.fillRect(x, y - 22, textW, 20);
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 12px Inter, sans-serif';
                ctx.fillText(label, x + 4, y - 6);
            }
        });
    };

    scLive.annotate = function (canvasId, x, y, label, type) {
        const state = scLive._streams[canvasId];
        if (!state) return;
        const ctx = state.ctx;
        const color = type === 'plate' ? '#facc15'
            : type === 'helmet' ? '#22c55e'
            : type === 'vehicle' ? '#60a5fa'
            : '#ffffff';
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 1;
        ctx.stroke();
        if (label) {
            ctx.font = 'bold 11px Inter, sans-serif';
            ctx.fillStyle = color;
            ctx.fillText(label, x + 8, y + 4);
        }
    };

    scLive.snapshot = function (canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        const data = canvas.toDataURL('image/jpeg', 0.85);
        return data;
    };

    scLive.uploadFrame = function (file) {
        var formData = new FormData();
        formData.append('frame', file);
        return fetch('/api/live/upload-frame/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': scLive._csrf() }
        }).then(function (r) { return r.json(); });
    };

    scLive._csrf = function () {
        if (window.scApp && typeof window.scApp.csrfToken === 'function') return window.scApp.csrfToken();
        var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    };

    scLive.pollDetections = function (cameraId, intervalMs) {
        intervalMs = intervalMs || 2000;
        if (scLive._polling[cameraId]) clearInterval(scLive._polling[cameraId]);
        scLive._polling[cameraId] = setInterval(function () {
            fetch('/api/live/recent-detections/?camera=' + cameraId, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (Array.isArray(data.detections)) {
                        data.detections.forEach(function (det) {
                            scLive.showDetection(det);
                        });
                    }
                })
                .catch(function () {  });
        }, intervalMs);
    };

    scLive.stopPolling = function (cameraId) {
        if (scLive._polling[cameraId]) {
            clearInterval(scLive._polling[cameraId]);
            delete scLive._polling[cameraId];
        }
    };

    scLive.showDetection = function (det) {
        const container = document.querySelector('.sc-ws-detections');
        if (!container) return;
        const el = document.createElement('div');
        el.className = 'sc-ws-detection';
        el.innerHTML =
            '<div class="sc-ws-detection-time">' + (det.timestamp || new Date().toLocaleTimeString()) + '</div>' +
            '<div class="sc-ws-detection-plate">' + (det.plate || '---') + '</div>' +
            '<div class="sc-ws-detection-type">' + (det.violation_type || 'Unknown') + '</div>';
        container.insertBefore(el, container.firstChild);

        while (container.children.length > 20) container.removeChild(container.lastChild);
    };

    scLive.initTimeline = function (containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        scLive._timelineFrames[containerId] = [];
        container.innerHTML = '';
        container.classList.add('sc-ws-timeline');
    };

    scLive.addFrame = function (containerId, frameData) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!scLive._timelineFrames[containerId]) scLive._timelineFrames[containerId] = [];
        const frames = scLive._timelineFrames[containerId];
        const frame = document.createElement('div');
        frame.className = 'sc-frame';
        frame.setAttribute('title', frameData.timestamp || new Date().toLocaleTimeString());

        const img = document.createElement('img');
        img.src = frameData.data || frameData.url || '';
        img.alt = 'Frame';
        frame.appendChild(img);

        if (frameData.detections) {
            const badge = document.createElement('span');
            badge.className = 'sc-badge sc-badge-red sc-badge-pill';
            badge.style.cssText = 'position:absolute;top:2px;right:2px;font-size:9px;';
            badge.textContent = frameData.detections.length;
            frame.style.position = 'relative';
            frame.appendChild(badge);
        }

        frame.addEventListener('click', function () {
            container.querySelectorAll('.sc-frame').forEach(function (f) { f.classList.remove('active'); });
            frame.classList.add('active');
            if (frameData.onClick) frameData.onClick(frameData);
        });

        frames.unshift(frameData);
        container.insertBefore(frame, container.firstChild);

        while (container.children.length > 30) {
            container.removeChild(container.lastChild);
            frames.pop();
        }
    };

    function autoInit() {
        document.querySelectorAll('[data-live-camera]').forEach(function (el) {
            const id = el.id;
            const url = el.getAttribute('data-live-url') || '/api/live/stream/';
            const autostart = el.getAttribute('data-live-autostart') !== 'false';
            scLive.init(id, url);
            if (autostart) scLive.start(id, url);
        });
        document.querySelectorAll('[data-live-poll]').forEach(function (el) {
            const cameraId = el.getAttribute('data-live-poll');
            const interval = parseInt(el.getAttribute('data-live-poll-interval') || '2000', 10);
            scLive.pollDetections(cameraId, interval);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.scLive = scLive;
})();
