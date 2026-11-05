
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
        const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return days[d.getDay()] + ', ' + pad(d.getDate()) + ' ' + months[d.getMonth()] + ' ' + d.getFullYear();
    }

    function startClock() {
        const wrap = document.getElementById('scClock');
        const timeEl = document.getElementById('scClockTime');
        const dateEl = document.getElementById('scClockDate');
        if (!wrap || !timeEl) return;
        function tick() {
            const d = new Date();
            timeEl.textContent = fmtTime(d);
            if (dateEl) dateEl.textContent = fmtDate(d);
        }
        tick();
        setInterval(tick, 1000);
    }

    function isMobile() {
        return window.matchMedia('(max-width: 1024px)').matches;
    }

    function initSidebar() {
        const app = document.getElementById('scApp');
        const sidebar = document.getElementById('scSidebar');
        const toggle = document.getElementById('scSidebarToggle');
        const collapseBtn = document.getElementById('scSidebarCollapse');
        const backdrop = document.getElementById('scSidebarBackdrop');
        if (!app || !sidebar || !toggle) return;

        let collapsed = 'true' === (localStorage.getItem('scSidebarCollapsed') || 'false');
        function apply() {
            if (isMobile()) {
                app.classList.remove('sc-collapsed');
                app.classList.remove('sc-mobile-open');
                if (backdrop) backdrop.hidden = true;
            } else if (collapsed) {
                app.classList.add('sc-collapsed');
            } else {
                app.classList.remove('sc-collapsed');
            }
            const open = !isMobile() && !collapsed;
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        function setCollapsed(state) {
            collapsed = state;
            localStorage.setItem('scSidebarCollapsed', collapsed ? 'true' : 'false');
            apply();
        }

        toggle.addEventListener('click', function () {
            if (isMobile()) {
                const opening = !app.classList.contains('sc-mobile-open');
                app.classList.toggle('sc-mobile-open', opening);
                if (backdrop) backdrop.hidden = !opening;
            } else {
                setCollapsed(!collapsed);
            }
        });

        if (collapseBtn) {
            collapseBtn.addEventListener('click', function () {
                if (isMobile()) {
                    app.classList.remove('sc-mobile-open');
                    if (backdrop) backdrop.hidden = true;
                } else {
                    setCollapsed(!collapsed);
                }
            });
        }

        if (backdrop) {
            backdrop.addEventListener('click', function () {
                app.classList.remove('sc-mobile-open');
                backdrop.hidden = true;
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && app.classList.contains('sc-mobile-open')) {
                app.classList.remove('sc-mobile-open');
                if (backdrop) backdrop.hidden = true;
            }
        });

        let resizeTimer = null;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(apply, 120);
        });

        apply();
    }

    
    
    

    function closeUserMenu() {
        const dd = document.querySelector('.sc-user-dropdown');
        if (dd) { dd.classList.remove('show'); dd.classList.remove('open'); }
    }

    function scToggleUserMenu(e) {
        if (e) e.stopPropagation();
        const dd = document.querySelector('.sc-user-dropdown');
        const btn = document.querySelector('.sc-user-btn');
        if (!dd) return;
        const willOpen = !(dd.classList.contains('show') || dd.classList.contains('open'));
        dd.classList.toggle('show', willOpen);
        dd.classList.toggle('open', willOpen);
        if (btn) btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
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
        const box = document.querySelector('.sc-flash-zone .sc-messages');
        if (!box) return;
        box.querySelectorAll('.sc-msg').forEach(function (n) {
            n.classList.add('is-visible');
        });
        clearTimeout(scShowMessages._t);
        scShowMessages._t = setTimeout(function () {
            box.querySelectorAll('.sc-msg').forEach(function (n) {
                n.classList.remove('is-visible');
            });
        }, 9000);
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
        initSidebar();
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
        initSidebar: initSidebar,
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
