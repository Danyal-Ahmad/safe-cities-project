
(function () {
    'use strict';

    window.scApp = window.scApp || {};

    
    
    

    function getCookie(name) {
        if (!document.cookie) return null;
        const parts = document.cookie.split(';');
        for (let i = 0; i < parts.length; i++) {
            const c = parts[i].trim();
            if (c.substring(0, name.length + 1) === (name + '=')) {
                return decodeURIComponent(c.substring(name.length + 1));
            }
        }
        return null;
    }

    function csrfToken() {
        return getCookie('csrftoken') || document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    }

    function scFetch(url, options) {
        options = options || {};
        options.headers = options.headers || {};
        options.headers['X-CSRFToken'] = csrfToken();
        options.headers['X-Requested-With'] = 'XMLHttpRequest';
        if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.body);
        }
        options.credentials = 'same-origin';
        return fetch(url, options).then(function (resp) {
            if (!resp.ok) throw new Error('Network error: ' + resp.status);
            const ct = resp.headers.get('content-type') || '';
            if (ct.indexOf('application/json') !== -1) return resp.json();
            return resp.text();
        });
    }

    function scPostJSON(url, data) {
        return scFetch(url, { method: 'POST', body: data });
    }

    
    
    

    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function fmtTime(d) {
        return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    }

    function fmtDate(d) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return months[d.getMonth()] + ' ' + pad(d.getDate()) + ', ' + d.getFullYear();
    }

    function startClock() {
        const el = document.getElementById('scClock');
        if (!el) return;
        function tick() {
            const d = new Date();
            el.textContent = fmtTime(d) + '  ' + fmtDate(d);
        }
        tick();
        setInterval(tick, 1000);
    }

    
    
    

    function closeUserMenu() {
        const dd = document.querySelector('.sc-user-dropdown');
        if (dd) dd.classList.remove('show');
    }

    function scToggleUserMenu(e) {
        if (e) e.stopPropagation();
        const dd = document.querySelector('.sc-user-dropdown');
        if (dd) dd.classList.toggle('show');
    }

    function initUserMenu() {
        const btn = document.querySelector('.sc-user-btn');
        if (btn) {
            btn.addEventListener('click', scToggleUserMenu);
        }
        document.addEventListener('click', function (e) {
            if (e.target.closest('.sc-user-menu')) return;
            closeUserMenu();
        });
    }

    
    
    

    function hasSwal() { return typeof window.Swal !== 'undefined'; }

    function scAlert(title, message, icon) {
        if (!hasSwal()) {
            alert((title ? title + '\n\n' : '') + (message || ''));
            return;
        }
        return Swal.fire({
            title: title || '',
            text: message || '',
            icon: icon || 'info',
            confirmButtonColor: '#1f3b73',
        });
    }

    function scConfirm(title, message, callback) {
        if (!hasSwal()) {
            if (window.confirm((title ? title + '\n\n' : '') + (message || ''))) {
                if (typeof callback === 'function') callback();
            }
            return;
        }
        Swal.fire({
            title: title || 'Are you sure?',
            text: message || '',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#1f3b73',
            cancelButtonColor: '#64748b',
            confirmButtonText: 'Yes',
        }).then(function (result) {
            if (result.isConfirmed && typeof callback === 'function') callback();
        });
    }

    function scToast(message, type) {
        if (!hasSwal()) {
            console.log('[toast]', type || 'info', message);
            return;
        }
        const Toast = Swal.mixin({
            toast: true,
            position: 'bottom-end',
            showConfirmButton: false,
            timer: 3500,
            timerProgressBar: true,
            customClass: { popup: 'sc-toast' },
        });
        Toast.fire({
            icon: type || 'info',
            title: message || '',
        });
    }

    function scShowMessages() {
        const nodes = document.querySelectorAll('.sc-messages .sc-msg, .sc-msg[data-msg-type]');
        if (!nodes.length) return;
        let toasted = 0;
        nodes.forEach(function (n) {
            const type = (n.getAttribute('data-msg-type') || n.className.match(/sc-msg-(\w+)/) || [, 'info'])[1];
            const text = n.textContent.trim();
            if (text && hasSwal()) {
                scToast(text, type === 'error' ? 'error' : type === 'success' ? 'success' : type === 'warning' ? 'warning' : 'info');
                toasted++;
            }
        });
        if (toasted === nodes.length) {
            const box = document.querySelector('.sc-messages');
            if (box) box.hidden = true;
        }
    }

    
    
    

    function scInitTables() {
        document.querySelectorAll('.sc-data-table').forEach(function (table) {
            if (table.__scInit) return;
            table.__scInit = true;
            const headers = table.querySelectorAll('thead th.sortable');
            headers.forEach(function (th, idx) {
                th.addEventListener('click', function () {
                    const dir = th.getAttribute('data-sort-dir') === 'asc' ? 'desc' : 'asc';
                    headers.forEach(function (h) { h.removeAttribute('data-sort-dir'); });
                    th.setAttribute('data-sort-dir', dir);
                    const tbody = table.querySelector('tbody');
                    const rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
                    rows.sort(function (a, b) {
                        const av = a.children[idx]?.textContent.trim() || '';
                        const bv = b.children[idx]?.textContent.trim() || '';
                        const an = parseFloat(av), bn = parseFloat(bv);
                        if (!isNaN(an) && !isNaN(bn)) {
                            return dir === 'asc' ? an - bn : bn - an;
                        }
                        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
                    });
                    rows.forEach(function (r) { tbody.appendChild(r); });
                });
            });
            const searchInput = document.querySelector('[data-table-search="' + (table.id || '') + '"]');
            if (searchInput) {
                searchInput.addEventListener('input', function () {
                    const q = searchInput.value.toLowerCase();
                    table.querySelectorAll('tbody tr').forEach(function (row) {
                        row.style.display = row.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
                    });
                });
            }
        });
    }

    
    
    

    function scInitTooltips() {
        if (typeof window.bootstrap === 'undefined' || !window.bootstrap.Tooltip) return;
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            try { new bootstrap.Tooltip(el); } catch (e) {  }
        });
    }

    
    
    

    function initMsgDismiss() {
        document.querySelectorAll('.sc-msg .sc-msg-close, .sc-banner-dismiss').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const target = btn.closest('.sc-msg, .sc-banner');
                if (target) target.style.display = 'none';
            });
        });
    }

    
    
    

    function initConfirmLinks() {
        document.querySelectorAll('[data-confirm]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                const msg = el.getAttribute('data-confirm') || 'Are you sure?';
                if (!hasSwal()) {
                    if (!window.confirm(msg)) e.preventDefault();
                    return;
                }
                e.preventDefault();
                scConfirm('Please confirm', msg, function () {
                    if (el.tagName === 'A' && el.href) {
                        window.location.href = el.href;
                    } else if (el.tagName === 'BUTTON' && (el.type || '').toLowerCase() === 'submit') {
                        el.closest('form')?.submit();
                    } else if (typeof el.click === 'function') {
                        
                    }
                });
            });
        });
    }

    
    
    

    function init() {
        startClock();
        initUserMenu();
        scInitTables();
        scInitTooltips();
        initMsgDismiss();
        initConfirmLinks();
        scShowMessages();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    
    
    

    window.scApp = {
        getCookie: getCookie,
        csrfToken: csrfToken,
        fetch: scFetch,
        postJSON: scPostJSON,
        startClock: startClock,
        toggleUserMenu: scToggleUserMenu,
        closeUserMenu: closeUserMenu,
        alert: scAlert,
        confirm: scConfirm,
        toast: scToast,
        showMessages: scShowMessages,
        initTables: scInitTables,
        initTooltips: scInitTooltips,
    };
})();
