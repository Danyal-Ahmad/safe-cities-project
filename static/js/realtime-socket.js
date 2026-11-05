
(function () {
    'use strict';

    if (window.SafeCityRealtime) {
        return; 
    }

    var SOCKET_IO_CDN = 'https://cdn.jsdelivr.net/npm/socket.io@4.7.5/dist/socket.io.min.js';
    var SOCKET_PATH = '/ws/socket.io';

    
    
    

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
        } catch (e) {  }
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

    
    function swalIcon(severity) {
        var map = {
            info: 'info', success: 'success', ok: 'success',
            warning: 'warning', warn: 'warning',
            error: 'error', critical: 'error', danger: 'error', alert: 'error'
        };
        return map[String(severity || 'info').toLowerCase()] || 'info';
    }

    function flashZone() {
        var zone = document.querySelector('.sc-flash-zone');
        if (!zone) {
            var main = document.querySelector('.sc-main');
            if (!main) { return null; }
            zone = document.createElement('div');
            zone.className = 'sc-flash-zone';
            main.insertBefore(zone, main.firstChild);
        }
        return zone;
    }

    function showToast(title, message, severity) {
        var zone = flashZone();
        if (!zone) { return; }
        var icon = {
            info: 'bi-info-circle-fill', success: 'bi-check-circle-fill',
            warning: 'bi-exclamation-triangle-fill', error: 'bi-x-circle-fill'
        }[swalIcon(severity)] || 'bi-info-circle-fill';
        var box = document.createElement('div');
        box.className = 'sc-messages';
        box.setAttribute('role', 'status');
        var item = document.createElement('div');
        item.className = 'sc-msg sc-msg-' + swalIcon(severity) + ' is-visible';
        item.innerHTML = '<i class="bi ' + icon + '"></i>';
        var body = document.createElement('div');
        body.className = 'sc-msg-body';
        var strong = document.createElement('strong');
        strong.textContent = title || 'Notification';
        strong.style.display = 'block';
        var span = document.createElement('span');
        span.textContent = message || '';
        body.appendChild(strong);
        body.appendChild(span);
        item.appendChild(body);
        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'sc-msg-close';
        close.setAttribute('aria-label', 'Dismiss');
        close.innerHTML = '<i class="bi bi-x-lg"></i>';
        close.addEventListener('click', function () { box.remove(); });
        item.appendChild(close);
        box.appendChild(item);
        zone.appendChild(box);
        window.setTimeout(function () {
            item.classList.remove('is-visible');
            window.setTimeout(function () { box.remove(); }, 400);
        }, 6500);
    }

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
        dispatch('safecity:challan', payload);
    }

    
    
    

    function connect() {
        var socket = io(window.location.origin, {
            path: SOCKET_PATH,
            auth: { role: getRole() },
            
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000
        });

        socket.on('connect', function () {
            setState('connected');
        });

        socket.on('disconnect', function (reason) {
            
            
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
