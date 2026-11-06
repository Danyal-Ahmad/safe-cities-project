/**
 * SAFE CITIES PROJECT - Realtime Socket.IO client
 *
 * Connects the portal page to the Socket.IO server mounted at /ws/socket.io
 * (wrongway_system/asgi.py + realtime/realtime_events.py) and reacts to
 * pushed events without polling:
 *
 *   'detection:new'        -> toast + DOM CustomEvent 'safecity:detection'
 *   'portal:notification'  -> severity-colored toast + CustomEvent
 *                             'safecity:notification'
 *   'challan:updated'      -> DOM CustomEvent 'safecity:challan' (no toast)
 *
 * Connection state changes are announced via the DOM CustomEvent
 * 'safecity:realtime-state' with detail.state in:
 *   'connecting' | 'connected' | 'reconnecting' | 'disconnected' |
 *   'unavailable'   (CDN client could not be loaded)
 * so pages can update a status badge without touching the console.
 *
 * Page integration (added to templates by a separate stream):
 *   <script src="{% static 'js/realtime-socket.js' %}" defer></script>
 *   <body data-user-role="officer">        (or window.SAFECITY_USER.role)
 *
 * Listeners on portal pages:
 *   document.addEventListener('safecity:detection', function (e) {
 *       // e.detail = {id, plate, status, action, camera, confidence, ...}
 *   });
 */
(function () {
    'use strict';

    if (window.SafeCityRealtime) {
        return; // already initialised; never connect twice
    }

    var SOCKET_IO_CDN = 'https://cdn.jsdelivr.net/npm/socket.io@4.7.5/dist/socket.io.min.js';
    var SOCKET_PATH = '/ws/socket.io';

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    function getRole() {
        var fromGlobal = window.SAFECITY_USER && window.SAFECITY_USER.role;
        var fromBody = document.body && document.body.dataset
            ? document.body.dataset.userRole : '';
        return String(fromGlobal || fromBody || 'guest').trim().toLowerCase() || 'guest';
    }

    function dispatch(name, payload) {
        try {
            document.dispatchEvent(new CustomEvent(name, {
                bubbles: true,
                detail: payload
            }));
        } catch (e) { /* older browsers without CustomEvent detail */ }
    }

    function setState(state, extra) {
        dispatch('safecity:realtime-state', {
            state: state,
            role: getRole(),
            extra: extra || null,
            at: new Date().toISOString()
        });
    }

    function hasSwal() {
        return typeof window.Swal !== 'undefined' && window.Swal &&
            typeof window.Swal.mixin === 'function';
    }

    // SweetAlert2 toast icons only accept these four values.
    function swalIcon(severity) {
        var map = {
            info: 'info', success: 'success', ok: 'success',
            warning: 'warning', warn: 'warning',
            error: 'error', critical: 'error', danger: 'error', alert: 'error'
        };
        return map[String(severity || 'info').toLowerCase()] || 'info';
    }

    function showToast(title, message, severity) {
        if (hasSwal()) {
            var Toast = window.Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 4200,
                timerProgressBar: true,
                customClass: { popup: 'sc-toast' }
            });
            Toast.fire({ icon: swalIcon(severity), title: title, text: message || '' });
            return;
        }
        fallbackToast(title, message, severity);
    }

    // Minimal dependency-free toast (used when SweetAlert2 is absent).
    function fallbackToast(title, message, severity) {
        if (!document.body) { return; }
        var colors = {
            info: '#0369a1', success: '#15803d',
            warning: '#b45309', error: '#b91c1c'
        };
        var bar = colors[swalIcon(severity)] || colors.info;

        var stack = document.getElementById('sc-realtime-toasts');
        if (!stack) {
            stack = document.createElement('div');
            stack.id = 'sc-realtime-toasts';
            stack.style.cssText = 'position:fixed;top:16px;right:16px;z-index:10800;' +
                'display:flex;flex-direction:column;gap:8px;max-width:340px;';
            document.body.appendChild(stack);
        }

        var el = document.createElement('div');
        el.setAttribute('role', 'status');
        el.style.cssText = 'background:#0f172a;color:#f8fafc;border-left:4px solid ' + bar +
            ';border-radius:8px;padding:10px 14px;box-shadow:0 8px 24px rgba(2,6,23,.35);' +
            'font:13px/1.45 system-ui,Segoe UI,Arial,sans-serif;opacity:0;' +
            'transition:opacity .2s ease;';

        var strong = document.createElement('strong');
        strong.textContent = title || 'Notification';
        strong.style.display = 'block';
        strong.style.marginBottom = '2px';

        var span = document.createElement('span');
        span.textContent = message || '';

        // textContent only: pushed payloads (plates, titles) are never HTML.
        el.appendChild(strong);
        el.appendChild(span);
        stack.appendChild(el);
        window.requestAnimationFrame(function () { el.style.opacity = '1'; });
        window.setTimeout(function () {
            el.style.opacity = '0';
            window.setTimeout(function () {
                if (el.parentNode) { el.parentNode.removeChild(el); }
            }, 250);
        }, 4200);
    }

    // ------------------------------------------------------------------
    // Event handlers
    // ------------------------------------------------------------------

    function onDetection(payload) {
        dispatch('safecity:detection', payload);
        var p = payload || {};
        var plate = p.plate || 'unknown plate';
        var loc = (p.camera && p.camera.location) ? ' @ ' + p.camera.location : '';
        var ev = (p.evidence_passed !== null && p.evidence_passed !== undefined)
            ? ' (' + p.evidence_passed + '/5 checks)' : '';
        if (p.action === 'challan_issued') {
            showToast('Challan issued', plate + loc + ev, 'success');
        } else if (p.action === 'queued_review') {
            showToast('Detection queued for review', plate + loc + ev, 'warning');
        }
    }

    function onNotification(payload) {
        dispatch('safecity:notification', payload);
        var p = payload || {};
        showToast(p.title || 'Notification', p.message || '', p.severity);
    }

    function onChallan(payload) {
        // No toast (staff lists refresh silently); pages listen for the event.
        dispatch('safecity:challan', payload);
    }

    // ------------------------------------------------------------------
    // Bootstrap
    // ------------------------------------------------------------------

    function connect() {
        var socket = io(window.location.origin, {
            path: SOCKET_PATH,
            auth: { role: getRole() },
            // socket.io auto-reconnect defaults, made explicit:
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000
        });

        socket.on('connect', function () {
            setState('connected');
        });

        socket.on('disconnect', function (reason) {
            // 'io client disconnect' = we closed it; anything else means
            // socket.io will retry automatically.
            setState(reason === 'io client disconnect' ? 'disconnected' : 'reconnecting', reason);
        });

        socket.on('connect_error', function (err) {
            setState('reconnecting', err && err.message ? err.message : String(err));
        });

        socket.on('detection:new', onDetection);
        socket.on('portal:notification', onNotification);
        socket.on('challan:updated', onChallan);

        return socket;
    }

    function loadClient(ready) {
        if (typeof window.io === 'function') {
            ready();
            return;
        }
        // Another stream may already add the CDN <script> tag; if we got
        // here without it, inject it ourselves before connecting.
        var script = document.createElement('script');
        script.src = SOCKET_IO_CDN;
        script.async = true;
        script.onload = ready;
        script.onerror = function () {
            setState('unavailable', 'could not load ' + SOCKET_IO_CDN);
        };
        (document.head || document.documentElement).appendChild(script);
    }

    function init() {
        setState('connecting');
        loadClient(function () {
            var socket = connect();
            var api = { socket: socket };
            Object.defineProperty(api, 'connected', {
                get: function () { return socket.connected; }
            });
            window.SafeCityRealtime = api;
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
