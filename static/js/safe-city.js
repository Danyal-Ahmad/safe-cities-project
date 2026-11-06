/**
 * SafeCities Project - Master App JS
 * Core application functionality:
 * - CSRF token handling for fetch
 * - Live topbar clock
 * - User dropdown menu
 * - Sidebar toggle with localStorage persistence
 * - SweetAlert2 wrappers (alert, confirm - explicit calls only)
 * - Django flash messages: rendered inline under the navbar, auto-faded
 * - Table sort/search
 * - Custom modal system (data-bs-toggle="modal" compatible, no Bootstrap)
 * - Custom tooltip system (data-bs-toggle="tooltip", no Bootstrap)
 */
(function () {
    'use strict';

    window.scApp = window.scApp || {};

    // ============================================================
    // CSRF / Fetch helpers
    // ============================================================

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

    // ============================================================
    // Live Clock
    // ============================================================

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

    // ============================================================
    // User Menu
    // ============================================================

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
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeUserMenu();
        });
    }

    // ============================================================
    // SweetAlert2 wrappers (used only for explicit confirm dialogs)
    // ============================================================

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

    // ============================================================
    // Flash messages: inline under the navbar, temporary.
    // Messages stay in the document flow directly below the topbar
    // (never floating), fade out automatically after 7s, and can be
    // dismissed manually via the close button.
    // ============================================================

    function fadeOutMsg(node) {
        if (node.__scFading) return;
        node.__scFading = true;
        node.style.transition = 'opacity .45s ease, transform .45s ease';
        node.style.opacity = '0';
        node.style.transform = 'translateY(-4px)';
        setTimeout(function () {
            const box = node.parentElement;
            node.remove();
            if (box && !box.children.length) box.remove();
        }, 480);
    }

    function initMsgDismiss() {
        document.querySelectorAll('.sc-messages .sc-msg').forEach(function (msg) {
            const btn = msg.querySelector('.sc-msg-close');
            if (btn) {
                btn.addEventListener('click', function () { fadeOutMsg(msg); });
            }
            // Temporary display: auto-fade after 7 seconds.
            setTimeout(function () { fadeOutMsg(msg); }, 7000);
        });
    }

    // ============================================================
    // Simple table sort + search
    // ============================================================

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

    // ============================================================
    // Custom modal system (replaces Bootstrap JS modals).
    // API compatibility: [data-bs-toggle="modal"][data-bs-target="#id"]
    // opens, [data-bs-dismiss="modal"] closes, .modal.show displays.
    // ============================================================

    const scModals = {
        open: function (modalEl) {
            if (!modalEl || modalEl.classList.contains('show')) return;
            modalEl.__scBackdrop = document.createElement('div');
            modalEl.__scBackdrop.className = 'modal-backdrop';
            document.body.appendChild(modalEl.__scBackdrop);
            modalEl.__scBackdrop.addEventListener('click', function () { scModals.close(modalEl); });
            modalEl.classList.add('show');
            modalEl.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            const focusable = modalEl.querySelector('input:not([type=hidden]), select, textarea, button:not([data-bs-dismiss])');
            if (focusable) setTimeout(function () { focusable.focus(); }, 60);
            modalEl.dispatchEvent(new CustomEvent('shown.sc.modal'));
        },
        close: function (modalEl) {
            if (!modalEl || !modalEl.classList.contains('show')) return;
            modalEl.classList.remove('show');
            modalEl.style.display = '';
            if (modalEl.__scBackdrop) {
                modalEl.__scBackdrop.remove();
                modalEl.__scBackdrop = null;
            }
            if (!document.querySelector('.modal.show')) document.body.style.overflow = '';
            modalEl.dispatchEvent(new CustomEvent('hidden.sc.modal'));
        },
        toggle: function (modalEl) {
            modalEl.classList.contains('show') ? scModals.close(modalEl) : scModals.open(modalEl);
        }
    };

    function initModals() {
        document.addEventListener('click', function (e) {
            const opener = e.target.closest('[data-bs-toggle="modal"]');
            if (opener) {
                const sel = opener.getAttribute('data-bs-target');
                const modal = sel ? document.querySelector(sel) : null;
                if (modal) { e.preventDefault(); scModals.open(modal); }
                return;
            }
            const closer = e.target.closest('[data-bs-dismiss="modal"]');
            if (closer) {
                const modal = closer.closest('.modal');
                if (modal) { e.preventDefault(); scModals.close(modal); }
            }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                const open = document.querySelector('.modal.show');
                if (open) scModals.close(open);
            }
        });
    }

    // ============================================================
    // Custom tooltips (replaces Bootstrap JS tooltips).
    // [data-bs-toggle="tooltip"][title="..."] -> styled .sc-tooltip.
    // Native title attribute is kept as fallback text source.
    // ============================================================

    let scTooltipEl = null;
    let scTooltipHideTimer = null;

    function showTooltip(host) {
        const text = host.getAttribute('title') || host.getAttribute('data-bs-original-title') || '';
        if (!text) return;
        if (!scTooltipEl) {
            scTooltipEl = document.createElement('div');
            scTooltipEl.className = 'sc-tooltip';
            scTooltipEl.setAttribute('role', 'tooltip');
            document.body.appendChild(scTooltipEl);
        }
        if (host.getAttribute('title')) {
            host.setAttribute('data-bs-original-title', host.getAttribute('title'));
            host.removeAttribute('title'); // avoid double native tooltip
            host.__scRestoreTitle = true;
        }
        scTooltipEl.textContent = text;
        scTooltipEl.style.visibility = 'hidden';
        scTooltipEl.style.left = '0px';
        scTooltipEl.style.top = '0px';
        scTooltipEl.style.display = 'block';

        const r = host.getBoundingClientRect();
        const tw = scTooltipEl.offsetWidth;
        const th = scTooltipEl.offsetHeight;
        let left = r.left + r.width / 2 - tw / 2;
        left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
        let top = r.top - th - 8;
        if (top < 8) top = r.bottom + 8;
        scTooltipEl.style.left = left + 'px';
        scTooltipEl.style.top = top + 'px';
        scTooltipEl.style.visibility = 'visible';
    }

    function hideTooltip() {
        if (scTooltipEl) scTooltipEl.style.display = 'none';
    }

    function initTooltips() {
        document.addEventListener('mouseover', function (e) {
            const host = e.target.closest('[data-bs-toggle="tooltip"]');
            if (!host) return;
            clearTimeout(scTooltipHideTimer);
            scTooltipHideTimer = setTimeout(function () { showTooltip(host); }, 240);
            host.addEventListener('mouseleave', function () {
                clearTimeout(scTooltipHideTimer);
                hideTooltip();
            }, { once: true });
        });
        document.addEventListener('scroll', hideTooltip, true);
    }

    // ============================================================
    // Confirm-on-click for any element with data-confirm attr
    // ============================================================

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
                    }
                });
            });
        });
    }

    // ============================================================
    // DOMContentLoaded init
    // ============================================================

    function init() {
        startClock();
        initUserMenu();
        scInitTables();
        initModals();
        initTooltips();
        initMsgDismiss();
        initConfirmLinks();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ============================================================
    // Public API
    // ============================================================

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
        initTables: scInitTables,
        modals: scModals,
    };
})();
