/**
 * SafeCities Project - Tables engine (framework-free)
 * Sort + filter + paginate any <table> with a modern card presentation:
 * the table lives inside an .sc-table-card surface and the pagination
 * footer ("Showing X to Y of Z" + page controls) is rendered INSIDE that
 * card as a proper footer bar - never as a loose floating fragment.
 */
(function () {
    'use strict';

    const scTables = {};
    scTables._instances = scTables._instances || {};

    // ============================================================
    // Config
    // ============================================================

    scTables.config = {
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100]
    };

    // ============================================================
    // Native sort/filter/paginate implementation
    // ============================================================

    function nativeSort(table, colIndex, direction) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        const rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        rows.sort(function (a, b) {
            const av = a.children[colIndex]?.textContent.trim() || '';
            const bv = b.children[colIndex]?.textContent.trim() || '';
            const an = parseFloat(av.replace(/[^\d.-]/g, ''));
            const bn = parseFloat(bv.replace(/[^\d.-]/g, ''));
            if (!isNaN(an) && !isNaN(bn)) {
                return direction === 'asc' ? an - bn : bn - an;
            }
            return direction === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
    }

    function visibleRows(table) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return [];
        return Array.prototype.slice.call(tbody.querySelectorAll('tr')).filter(function (r) {
            return !r.dataset.filteredOut;
        });
    }

    function nativeFilter(table, query) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        const q = (query || '').toLowerCase();
        tbody.querySelectorAll('tr').forEach(function (row) {
            const match = row.textContent.toLowerCase().indexOf(q) !== -1;
            if (match) { delete row.dataset.filteredOut; }
            else { row.dataset.filteredOut = '1'; }
        });
    }

    function nativePaginate(table, page, perPage) {
        const rows = visibleRows(table);
        const total = rows.length;
        const start = (page - 1) * perPage;
        const end = start + perPage;
        rows.forEach(function (r, i) {
            r.style.display = (i >= start && i < end) ? '' : 'none';
        });
        return { total: total, page: page, perPage: perPage };
    }

    // ============================================================
    // Card presentation + footer bar
    // ============================================================

    /* Attach the pagination footer to the table's existing presentation
       wrapper. Priority:
       1. an .sc-table-card the engine (or the template) already provided;
       2. an .sc-table-wrap (project table style) - footer goes inside it;
       3. a .card-body / .sc-card-body - footer goes inside it;
       4. otherwise wrap the table in a fresh .sc-table-card.
       Never nest a new card inside an existing one. */
    function ensureCard(instance) {
        const table = instance.table;
        let card = table.closest('.sc-table-card');
        let host = null; // where the footer element is appended

        if (!card) {
            const wrap = table.closest('.sc-table-wrap');
            const cardBody = table.closest('.card-body, .sc-card-body');
            if (wrap) {
                host = wrap;
            } else if (cardBody) {
                host = cardBody;
            } else {
                card = document.createElement('div');
                card.className = 'sc-table-card';
                const scroll = document.createElement('div');
                scroll.className = 'sc-table-scroll';
                table.parentNode.insertBefore(card, table);
                scroll.appendChild(table);
                card.appendChild(scroll);
                host = card;
            }
        } else {
            host = card;
        }

        const existing = host.classList.contains('sc-table-wrap')
            ? (host.nextElementSibling && host.nextElementSibling.classList.contains('sc-table-footer') ? host.nextElementSibling : null)
            : host.querySelector('.sc-table-footer');
        if (!existing) {
            const footer = document.createElement('div');
            footer.className = 'sc-table-footer';
            const info = document.createElement('span');
            info.className = 'sc-table-info';
            const controls = document.createElement('div');
            controls.className = 'sc-table-controls';
            footer.appendChild(info);
            footer.appendChild(controls);
            if (host.classList.contains('sc-table-wrap')) {
                // The wrap scrolls horizontally; the footer must stay fixed
                // below it, so insert as its next sibling.
                host.parentNode.insertBefore(footer, host.nextSibling);
            } else {
                host.appendChild(footer);
            }
            instance.footerEl = footer;
        } else {
            instance.footerEl = existing;
        }
        instance.card = host;
        instance.footerInfo = instance.footerEl.querySelector('.sc-table-info');
        instance.footerControls = instance.footerEl.querySelector('.sc-table-controls');
    }

    function pageButton(html, page, title, disabled, active) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'sc-table-page' + (active ? ' active' : '');
        b.innerHTML = html;
        b.title = title;
        b.disabled = !!disabled;
        if (!disabled) {
            b.addEventListener('click', function () {
                const inst = b.__scInstance;
                inst.state.page = page;
                nativePaginate(inst.table, page, inst.state.perPage);
                updateFooter(inst);
            });
        }
        return b;
    }

    function updateFooter(instance) {
        if (!instance.footerInfo) return;
        const total = visibleRows(instance.table).length;
        const perPage = instance.state.perPage;
        const totalPages = Math.max(1, Math.ceil(total / perPage));
        const cur = Math.min(instance.state.page, totalPages);

        instance.state.page = cur;

        const from = total === 0 ? 0 : (cur - 1) * perPage + 1;
        const to = Math.min(cur * perPage, total);
        instance.footerInfo.textContent =
            total === 0 ? 'No records' : 'Showing ' + from + '\u2013' + to + ' of ' + total + ' records';

        const c = instance.footerControls;
        c.innerHTML = '';

        if (totalPages <= 1) return;

        const first = pageButton('<i class="bi bi-chevron-double-left"></i>', 1, 'First page', cur === 1);
        const prev = pageButton('<i class="bi bi-chevron-left"></i>', cur - 1, 'Previous page', cur === 1);
        first.__scInstance = instance;
        prev.__scInstance = instance;
        c.appendChild(first);
        c.appendChild(prev);

        // Compact page window: 1 … (cur-1) cur (cur+1) … last
        const window = [];
        for (let p = 1; p <= totalPages; p++) {
            if (p === 1 || p === totalPages || Math.abs(p - cur) <= 1) window.push(p);
        }
        let lastPrinted = 0;
        window.forEach(function (p) {
            if (p - lastPrinted > 1) {
                const dots = document.createElement('span');
                dots.className = 'sc-table-dots';
                dots.textContent = '\u2026';
                c.appendChild(dots);
            }
            const pb = pageButton(String(p), p, 'Page ' + p, false, p === cur);
            pb.__scInstance = instance;
            c.appendChild(pb);
            lastPrinted = p;
        });

        const next = pageButton('<i class="bi bi-chevron-right"></i>', cur + 1, 'Next page', cur === totalPages);
        const lastB = pageButton('<i class="bi bi-chevron-double-right"></i>', totalPages, 'Last page', cur === totalPages);
        next.__scInstance = instance;
        lastB.__scInstance = instance;
        c.appendChild(next);
        c.appendChild(lastB);
    }

    // ============================================================
    // Init native table
    // ============================================================

    function initNative(table) {
        const id = table.id || 'tbl_' + Math.random().toString(36).substr(2, 9);
        if (scTables._instances[id]) return scTables._instances[id];
        table.id = id;
        const instance = {
            id: id,
            table: table,
            type: 'native',
            state: { page: 1, perPage: scTables.config.pageLength, sortCol: -1, sortDir: 'asc', search: '' }
        };
        scTables._instances[id] = instance;

        // Sorting
        table.querySelectorAll('thead th[data-sortable], thead th.sortable').forEach(function (th) {
            th.style.cursor = 'pointer';
            th.addEventListener('click', function () {
                const idx = Array.prototype.indexOf.call(th.parentElement.children, th);
                const dir = th.getAttribute('data-sort-dir') === 'asc' ? 'desc' : 'asc';
                table.querySelectorAll('thead th').forEach(function (h) { h.removeAttribute('data-sort-dir'); });
                th.setAttribute('data-sort-dir', dir);
                instance.state.sortCol = idx;
                instance.state.sortDir = dir;
                nativeSort(table, idx, dir);
                instance.state.page = 1;
                nativePaginate(table, 1, instance.state.perPage);
                updateFooter(instance);
            });
        });

        // Search
        const searchEl = document.querySelector('[data-table-search="' + id + '"]');
        if (searchEl) {
            searchEl.addEventListener('input', function () {
                instance.state.search = searchEl.value;
                nativeFilter(table, searchEl.value);
                instance.state.page = 1;
                nativePaginate(table, 1, instance.state.perPage);
                updateFooter(instance);
            });
        }

        // Presentation: card + footer, then paginate.
        ensureCard(instance);
        nativePaginate(table, instance.state.page, instance.state.perPage);
        updateFooter(instance);

        return instance;
    }

    // ============================================================
    // Public API
    // ============================================================

    scTables.init = function (tableId, options) {
        const table = typeof tableId === 'string' ? document.getElementById(tableId) : tableId;
        if (!table) { console.error('[scTables] Table not found:', tableId); return null; }
        return initNative(table);
    };

    scTables.reload = function (tableId) {
        const inst = scTables._instances[tableId];
        if (!inst) return;
        const url = inst.table.getAttribute('data-url');
        if (!url) return;
        const headers = {};
        if (window.scApp && window.scApp.csrfToken) headers['X-CSRFToken'] = window.scApp.csrfToken();
        fetch(url, { credentials: 'same-origin', headers: headers })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                const tbody = inst.table.querySelector('tbody');
                if (tbody && data.rows) {
                    tbody.innerHTML = data.rows;
                    updateFooter(inst);
                }
            });
    };

    scTables.exportCsv = function (tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;
        const rows = table.querySelectorAll('tbody tr');
        const header = Array.prototype.slice.call(table.querySelectorAll('thead th')).map(function (th) {
            return '"' + th.textContent.trim().replace(/"/g, '""') + '"';
        }).join(',');
        const body = Array.prototype.slice.call(rows).map(function (row) {
            return Array.prototype.slice.call(row.querySelectorAll('td')).map(function (td) {
                return '"' + td.textContent.trim().replace(/"/g, '""') + '"';
            }).join(',');
        }).join('\n');
        const csv = header + '\n' + body;
        const blob = new Blob([csv], { type: 'text/csv' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = (table.getAttribute('data-export-name') || tableId) + '.csv';
        a.click();
    };

    scTables.columnFilter = function (tableId, colIdx, value) {
        const inst = scTables._instances[tableId];
        if (!inst) return;
        nativeFilter(inst.table, value);
        nativePaginate(inst.table, 1, inst.state.perPage);
        updateFooter(inst);
    };

    scTables.rowActions = function (tableId, actions) {
        actions = actions || {};
        const table = document.getElementById(tableId);
        if (!table) return;
        table.querySelectorAll('tbody').forEach(function (tbody) {
            tbody.addEventListener('click', function (e) {
                const btn = e.target.closest('[data-action]');
                if (!btn) return;
                const action = btn.getAttribute('data-action');
                const row = btn.closest('tr');
                const handler = actions[action];
                if (typeof handler === 'function') {
                    handler(row, btn);
                }
            });
        });
    };

    // ============================================================
    // Auto-init tables with data-table-init attribute
    // ============================================================

    function autoInit() {
        document.querySelectorAll('[data-table-init], table.sc-data-table').forEach(function (el) {
            const id = el.getAttribute('data-table-init') || el.id;
            if (id) scTables.init(id);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.scTables = scTables;
})();
