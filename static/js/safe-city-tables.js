
(function () {
    'use strict';

    const scTables = {};
    scTables._instances = scTables._instances || {};

    
    
    

    scTables.config = {
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100],
        language: {
            search: 'Search:',
            lengthMenu: 'Show _MENU_ entries',
            info: 'Showing _START_ to _END_ of _TOTAL_',
            infoEmpty: 'No entries',
            zeroRecords: 'No matching records found',
            paginate: {
                first: '&laquo;',
                last: '&raquo;',
                next: '&rsaquo;',
                previous: '&lsaquo;'
            }
        }
    };

    
    
    

    function hasDataTables() {
        return typeof window.jQuery !== 'undefined' && typeof window.jQuery.fn.DataTable !== 'undefined';
    }

    
    
    

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

    function nativeFilter(table, query) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        const q = query.toLowerCase();
        tbody.querySelectorAll('tr').forEach(function (row) {
            row.style.display = row.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
        });
    }

    function nativePaginate(table, page, perPage) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        const rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        const visibleRows = rows.filter(function (r) { return r.style.display !== 'none'; });
        const total = visibleRows.length;
        const start = (page - 1) * perPage;
        const end = start + perPage;
        rows.forEach(function (r) { r.style.display = 'none'; });
        visibleRows.slice(start, end).forEach(function (r) { r.style.display = ''; });
        return { total: total, page: page, perPage: perPage };
    }

    
    
    

    function initNative(table) {
        const id = table.id || 'tbl_' + Math.random().toString(36).substr(2, 9);
        if (scTables._instances[id]) return scTables._instances[id];
        const instance = {
            id: id,
            table: table,
            type: 'native',
            state: { page: 1, perPage: scTables.config.pageLength, sortCol: -1, sortDir: 'asc', search: '' }
        };
        scTables._instances[id] = instance;

        
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
            });
        });

        
        const searchEl = document.querySelector('[data-table-search="' + id + '"]');
        if (searchEl) {
            searchEl.addEventListener('input', function () {
                instance.state.search = searchEl.value;
                nativeFilter(table, searchEl.value);
                instance.state.page = 1;
                nativePaginate(table, 1, instance.state.perPage);
                updatePagination(instance);
            });
        }

        
        nativePaginate(table, instance.state.page, instance.state.perPage);
        buildPagination(instance);
        updatePagination(instance);

        return instance;
    }

    function buildPagination(instance) {
        let wrap = instance.table.parentElement.querySelector('.sc-table-pagination');
        if (!wrap) {
            wrap = document.createElement('div');
            wrap.className = 'sc-table-pagination';
            wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:0.75rem 0;font-size:0.875rem;color:#64748b;';
            instance.table.parentElement.appendChild(wrap);
        }
        instance.paginationWrap = wrap;
    }

    function updatePagination(instance) {
        const tbody = instance.table.querySelector('tbody');
        if (!tbody) return;
        const visible = Array.prototype.slice.call(tbody.querySelectorAll('tr')).filter(function (r) { return r.style.display !== 'none'; });
        const total = visible.length;
        const totalPages = Math.max(1, Math.ceil(total / instance.state.perPage));
        const cur = Math.min(instance.state.page, totalPages);

        const info = document.createElement('span');
        info.textContent = 'Showing ' + Math.min((cur - 1) * instance.state.perPage + 1, total) + ' to ' + Math.min(cur * instance.state.perPage, total) + ' of ' + total;

        const controls = document.createElement('div');
        controls.style.display = 'flex';
        controls.style.gap = '0.25rem';

        function btn(text, page) {
            const b = document.createElement('button');
            b.textContent = text;
            b.className = 'sc-btn sc-btn-sm sc-btn-ghost';
            b.style.cssText = 'min-width:32px;height:32px;padding:0 0.5rem;';
            b.disabled = page < 1 || page > totalPages;
            b.addEventListener('click', function () {
                instance.state.page = page;
                nativePaginate(instance.table, page, instance.state.perPage);
                updatePagination(instance);
            });
            return b;
        }

        controls.appendChild(btn('\u00ab', 1));
        controls.appendChild(btn('\u2039', cur - 1));
        controls.appendChild(btn(String(cur), cur));
        controls.appendChild(btn('\u203a', cur + 1));
        controls.appendChild(btn('\u00bb', totalPages));

        instance.paginationWrap.innerHTML = '';
        instance.paginationWrap.appendChild(info);
        instance.paginationWrap.appendChild(controls);
    }

    
    
    

    function initDataTables(table) {
        const id = table.id || 'tbl_' + Math.random().toString(36).substr(2, 9);
        if (scTables._instances[id]) return scTables._instances[id];
        const $table = jQuery(table);
        const dt = $table.DataTable({
            pageLength: scTables.config.pageLength,
            lengthMenu: scTables.config.lengthMenu,
            language: scTables.config.language,
            dom: 'rt<"sc-table-pagination"ip>',
            columnDefs: [{ orderable: false, targets: 'no-sort' }],
            initComplete: function () {
                
                const wrapper = table.closest('.sc-table-wrap') || table.parentElement;
                if (!wrapper.classList.contains('sc-table-wrap')) {
                    wrapper.classList.add('sc-table-wrap');
                }
            }
        });
        const instance = { id: id, table: table, $dt: dt, type: 'datatables' };
        scTables._instances[id] = instance;
        return instance;
    }

    
    
    

    scTables.init = function (tableId, options) {
        options = options || {};
        const table = typeof tableId === 'string' ? document.getElementById(tableId) : tableId;
        if (!table) { console.error('[scTables] Table not found:', tableId); return null; }
        if (hasDataTables()) return initDataTables(table);
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
                }
            });
    };

    scTables.exportCsv = function (tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;
        const rows = table.querySelectorAll('tbody tr:not([style*="display: none"])');
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
        if (inst.type === 'native') {
            nativeFilter(inst.table, value);
        } else if (inst.type === 'datatables') {
            inst.$dt.column(colIdx).search(value).draw();
        }
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
