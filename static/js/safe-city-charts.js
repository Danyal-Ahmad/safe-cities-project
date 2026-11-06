
(function () {
    'use strict';

    if (typeof window.Chart === 'undefined') {
        console.warn('[scCharts] Chart.js not found. Charts will not render.');
    }

    const scCharts = {};

    scCharts.palettes = {
        navy: ['#2563EB', '#6094FA', '#93B8FD', '#1D4ED8', '#3B76F6', '#7FA8E9', '#AEC5F7', '#4A82EC'],
        green: ['#059669', '#10B981', '#34D399', '#6EE7B7', '#047857', '#059669', '#10B981', '#34D399'],
        warm: ['#D97706', '#F59E0B', '#FBBF24', '#FCD34D', '#B45309', '#D97706', '#F59E0B', '#FBBF24'],
        cool: ['#0D9488', '#14B8A6', '#2DD4BF', '#5EEAD4', '#0F766E', '#0D9488', '#14B8A6', '#2DD4BF'],
        all:  ['#2563EB', '#059669', '#D97706', '#7C3AED', '#0D9488', '#DC2626', '#0284C7', '#94A0B8']
    };

    scCharts.defaults = {
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: '#64748B',
        borderColor: '#EDF1F7',
    };

    function verticalGradient(canvas, color, alphaTop, alphaBottom) {
        if (!canvas || !canvas.getContext) return color;
        const ctx = canvas.getContext('2d');
        const h = canvas.height || canvas.clientHeight || 220;
        const g = ctx.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, hexToRgba(color, alphaTop == null ? 0.32 : alphaTop));
        g.addColorStop(0.6, hexToRgba(color, alphaBottom == null ? 0.10 : alphaBottom));
        g.addColorStop(1, hexToRgba(color, 0));
        return g;
    }

    function barGradient(canvas, color) {
        if (!canvas || !canvas.getContext) return color;
        const ctx = canvas.getContext('2d');
        const h = canvas.height || canvas.clientHeight || 220;
        const g = ctx.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, color);
        g.addColorStop(1, hexToRgba(color, 0.55));
        return g;
    }

    function mergeOpts(opts) {
        opts = opts || {};
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            indexAxis: opts.indexAxis || 'x',
            plugins: {
                legend: {
                    display: opts.hideLegend ? false : undefined,
                    position: 'bottom',
                    labels: {
                        font: { family: scCharts.defaults.fontFamily, size: 11.5, weight: '600' },
                        color: scCharts.defaults.color,
                        boxWidth: 9,
                        boxHeight: 9,
                        padding: 16,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        pointStyleWidth: 9,
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.96)',
                    titleColor: '#ffffff',
                    bodyColor: '#E2E8F0',
                    borderColor: 'rgba(148, 163, 184, 0.22)',
                    borderWidth: 1,
                    padding: 13,
                    cornerRadius: 12,
                    displayColors: true,
                    usePointStyle: true,
                    boxPadding: 5,
                    titleFont: { family: scCharts.defaults.fontFamily, weight: '700', size: 12 },
                    bodyFont: { family: scCharts.defaults.fontFamily, size: 12, weight: '500' },
                }
            },
            scales: opts.scales || undefined
        };
    }

    function datasetsTotal(datasets) {
        var total = 0;
        (datasets || []).forEach(function (ds) {
            var d = (ds && ds.data) || [];
            if (Array.isArray(d)) {
                d.forEach(function (v) {
                    var n = typeof v === 'object' && v ? v.y : v;
                    total += (typeof n === 'number' && isFinite(n)) ? n : 0;
                });
            }
        });
        return total;
    }

    scCharts.emptyState = function (canvas, message) {
        canvas = getCanvas(canvas);
        if (!canvas) return null;
        var box = canvas.parentElement;
        if (!box || box.classList.contains('sc-chart-empty-host')) return null;
        canvas.style.display = 'none';
        var holder = document.createElement('div');
        holder.className = 'sc-chart-empty';
        holder.innerHTML = '<i class="bi bi-graph-up-arrow"></i><span>' + (message || 'No data for this period yet') + '</span>';
        canvas.insertAdjacentElement('afterend', holder);
        box.classList.add('sc-chart-empty-host');
        return holder;
    };

    scCharts.restoreFromEmpty = function (canvas) {
        canvas = getCanvas(canvas);
        if (!canvas) return;
        canvas.style.display = '';
        var next = canvas.nextElementSibling;
        if (next && next.classList && next.classList.contains('sc-chart-empty')) next.remove();
        if (canvas.parentElement) canvas.parentElement.classList.remove('sc-chart-empty-host');
    };

    function applyScales(opts) {
        const axis = {
            grid: {
                color: 'rgba(148, 163, 184, 0.13)',
                drawBorder: false,
                drawTicks: false,
            },
            border: { display: false },
            ticks: {
                color: '#94A3B8',
                font: { family: scCharts.defaults.fontFamily, size: 11, weight: '500' },
                padding: 8,
                precision: 0,
            }
        };
        return {
            x: Object.assign({}, axis, (opts.scales && opts.scales.x) || {}, { grid: Object.assign({}, axis.grid, { display: false, drawOnChartArea: false, drawTicks: false }) }),
            y: Object.assign({}, axis, (opts.scales && opts.scales.y) || {}, {
                beginAtZero: true,
                grid: Object.assign({}, axis.grid, (opts.scales && opts.scales.y && opts.scales.y.grid) || {}),
                border: Object.assign({}, axis.border, { display: false, dash: [4, 6] }),
            })
        };
    }

    function enhanceChartConfig(canvas, config) {
        if (!config || config.__scStyled) return config;
        config.__scStyled = true;
        const data = config.data || {};
        const datasets = data.datasets || [];
        const type = config.type || '';

        datasets.forEach(function (ds, i) {
            const dsType = ds.type || type;
            if (dsType === 'line') {
                ds.tension = ds.tension === undefined ? 0.42 : ds.tension;
                ds.borderWidth = ds.borderWidth === undefined ? 2.6 : ds.borderWidth;
                ds.pointRadius = ds.pointRadius === undefined ? 0 : ds.pointRadius;
                ds.pointHoverRadius = ds.pointHoverRadius === undefined ? 6 : ds.pointHoverRadius;
                ds.pointBackgroundColor = ds.pointBackgroundColor || '#FFFFFF';
                ds.pointBorderWidth = 2.5;
                ds.pointHoverBorderWidth = 3;
                ds.fill = ds.fill === undefined ? 'origin' : ds.fill;
                const c = typeof ds.borderColor === 'string' ? ds.borderColor : (scCharts.palettes.navy[i % 8]);
                if (!ds.backgroundColor || typeof ds.backgroundColor !== 'object') {
                    ds.backgroundColor = verticalGradient(canvas, c, 0.28, 0.06);
                }
            } else if (dsType === 'bar') {
                const c = typeof ds.borderColor === 'string' ? ds.borderColor
                    : (typeof ds.backgroundColor === 'string' && ds.backgroundColor.indexOf('#') === 0 ? ds.backgroundColor
                    : scCharts.palettes.navy[i % 8]);
                if (!ds.backgroundColor || typeof ds.backgroundColor === 'string') {
                    ds.backgroundColor = barGradient(canvas, c);
                }
                ds.borderRadius = ds.borderRadius === undefined ? 7 : ds.borderRadius;
                ds.borderSkipped = false;
                ds.maxBarThickness = ds.maxBarThickness === undefined ? 38 : ds.maxBarThickness;
            } else if (dsType === 'doughnut' || dsType === 'pie') {
                if (!Array.isArray(ds.backgroundColor)) {
                    ds.backgroundColor = scCharts.palettes.all.slice(0, (ds.data || []).length);
                }
                ds.borderColor = ds.borderColor || '#FFFFFF';
                ds.borderWidth = ds.borderWidth === undefined ? 3 : ds.borderWidth;
                if (dsType === 'doughnut') ds.cutout = ds.cutout || '70%';
                ds.hoverOffset = ds.hoverOffset === undefined ? 6 : ds.hoverOffset;
            }
        });

        config.options = config.options || {};
        const o = config.options;
        o.interaction = o.interaction || { mode: 'index', intersect: false };
        o.plugins = o.plugins || {};
        if (!o.plugins.legend) {
            o.plugins.legend = {
                position: 'bottom',
                labels: {
                    font: { family: scCharts.defaults.fontFamily, size: 11.5, weight: '600' },
                    color: scCharts.defaults.color,
                    boxWidth: 9, boxHeight: 9, padding: 16,
                    usePointStyle: true, pointStyle: 'circle', pointStyleWidth: 9,
                }
            };
        }
        if (!o.plugins.tooltip) {
            o.plugins.tooltip = {
                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                titleColor: '#ffffff', bodyColor: '#E2E8F0',
                borderColor: 'rgba(148, 163, 184, 0.22)', borderWidth: 1,
                padding: 13, cornerRadius: 12, usePointStyle: true, boxPadding: 5,
                titleFont: { family: scCharts.defaults.fontFamily, weight: '700', size: 12 },
                bodyFont: { family: scCharts.defaults.fontFamily, size: 12, weight: '500' },
            };
        }
        return config;
    }

    function patchChartConstructor() {
        if (typeof window.Chart === 'undefined' || window.Chart.__scPatched) return;
        const Native = window.Chart;
        function Styled(canvas, config) {
            if (!(this instanceof Styled)) {
                return new Styled(canvas, config);
            }
            config = enhanceChartConfig(getCanvas(canvas), config || {});
            return new Native(canvas, config);
        }
        try {
            Object.getOwnPropertyNames(Native).forEach(function (key) {
                if (key === 'prototype' || key === 'length' || key === 'name') return;
                try {
                    Styled[key] = Native[key];
                } catch (e) {  }
            });
            Styled.prototype = Native.prototype;
            Styled.__scPatched = true;
            window.Chart = Styled;
        } catch (e) {  }
    }

    if (typeof window.Chart !== 'undefined') {
        try {
            Chart.defaults.font.family = scCharts.defaults.fontFamily;
            Chart.defaults.font.size = 11;
            Chart.defaults.color = scCharts.defaults.color;
            Chart.defaults.borderColor = scCharts.defaults.borderColor;
            if (Chart.defaults.datasets && Chart.defaults.datasets.bar) {
                Chart.defaults.datasets.bar.borderRadius = 7;
                Chart.defaults.datasets.bar.borderSkipped = false;
                Chart.defaults.datasets.bar.maxBarThickness = 38;
                Chart.defaults.datasets.bar.categoryPercentage = 0.68;
                Chart.defaults.datasets.bar.barPercentage = 0.82;
            }
            if (Chart.defaults.datasets && Chart.defaults.datasets.line) {
                Chart.defaults.datasets.line.tension = 0.42;
                Chart.defaults.datasets.line.borderWidth = 2.6;
                Chart.defaults.datasets.line.pointRadius = 0;
                Chart.defaults.datasets.line.pointHoverRadius = 6;
                Chart.defaults.datasets.line.pointBackgroundColor = '#FFFFFF';
                Chart.defaults.datasets.line.pointBorderColor = '#2563EB';
                Chart.defaults.datasets.line.pointBorderWidth = 2.5;
                Chart.defaults.datasets.line.pointHoverBorderWidth = 3;
            }
            if (Chart.defaults.datasets && Chart.defaults.datasets.doughnut) {
                Chart.defaults.datasets.doughnut.cutout = '70%';
                Chart.defaults.datasets.doughnut.borderWidth = 3;
                Chart.defaults.datasets.doughnut.borderColor = '#FFFFFF';
                Chart.defaults.datasets.doughnut.hoverOffset = 6;
            }
            patchChartConstructor();
        } catch (e) {  }
    }

    function getCanvas(canvasId) {
        if (typeof canvasId === 'string') {
            return document.getElementById(canvasId);
        }
        return canvasId;
    }

    function getCtx(canvas) {
        return canvas.getContext('2d');
    }

    function colorize(datasets, paletteName) {
        const palette = scCharts.palettes[paletteName || 'navy'] || scCharts.palettes.navy;
        return (datasets || []).map(function (ds, i) {
            const c = palette[i % palette.length];
            if (ds.backgroundColor === undefined) {
                ds.backgroundColor = ds.type === 'line'
                    ? hexToRgba(c, 0.15)
                    : (ds.type === 'doughnut' || ds.type === 'pie' ? palette : c);
            }
            if (ds.borderColor === undefined) ds.borderColor = c;
            if (ds.borderWidth === undefined && ds.type !== 'doughnut' && ds.type !== 'pie') {
                ds.borderWidth = 2;
            }
            if ((ds.type === 'doughnut' || ds.type === 'pie') && Array.isArray(ds.data)) {
                ds.backgroundColor = palette.slice(0, ds.data.length);
            }
            return ds;
        });
    }

    function hexToRgba(hex, alpha) {
        const h = (hex || '#1f3b73').replace('#', '');
        const r = parseInt(h.substring(0, 2), 16);
        const g = parseInt(h.substring(2, 4), 16);
        const b = parseInt(h.substring(4, 6), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + (alpha == null ? 0.2 : alpha) + ')';
    }

    function buildDatasets(canvas, datasets, paletteName) {
        const palette = scCharts.palettes[paletteName || 'navy'] || scCharts.palettes.navy;
        return (datasets || []).map(function (ds, i) {
            const c = ds.borderColor || palette[i % palette.length];
            ds.borderColor = c;
            ds.tension = ds.tension || 0.42;
            ds.fill = ds.fill === undefined ? 'origin' : ds.fill;
            ds.pointRadius = ds.pointRadius === undefined ? 0 : ds.pointRadius;
            ds.pointHoverRadius = ds.pointHoverRadius === undefined ? 6 : ds.pointHoverRadius;
            ds.pointBackgroundColor = ds.pointBackgroundColor || '#FFFFFF';
            ds.pointBorderColor = ds.pointBorderColor || c;
            ds.pointBorderWidth = 2.5;
            ds.pointHoverBorderWidth = 3;
            ds.pointHoverBackgroundColor = '#FFFFFF';
            ds.backgroundColor = verticalGradient(canvas, c, 0.28, 0.06);
            return ds;
        });
    }

    function buildBarDatasets(canvas, datasets, paletteName) {
        const palette = scCharts.palettes[paletteName || 'navy'] || scCharts.palettes.navy;
        return (datasets || []).map(function (ds, i) {
            const c = ds.borderColor || palette[i % palette.length];
            ds.backgroundColor = ds.backgroundColor && typeof ds.backgroundColor === 'string' && ds.backgroundColor.indexOf('rgba') === 0
                ? ds.backgroundColor
                : barGradient(canvas, c);
            ds.borderColor = c;
            ds.borderRadius = ds.borderRadius === undefined ? 7 : ds.borderRadius;
            ds.borderSkipped = false;
            ds.maxBarThickness = ds.maxBarThickness === undefined ? 38 : ds.maxBarThickness;
            ds.categoryPercentage = 0.68;
            ds.barPercentage = 0.82;
            return ds;
        });
    }

    scCharts.line = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const opts = options || {};
        if (datasetsTotal(datasets) <= 0) { scCharts.emptyState(canvas, opts.emptyMessage); return null; }
        scCharts.restoreFromEmpty(canvas);
        const ds = buildDatasets(canvas, datasets, opts.palette);
        const config = {
            type: 'line',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(opts)
        };
        config.options.scales = applyScales(opts);
        config.options.scales.y.grace = '8%';
        return new Chart(getCtx(canvas), config);
    };

    scCharts.bar = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const opts = options || {};
        if (datasetsTotal(datasets) <= 0) { scCharts.emptyState(canvas, opts.emptyMessage); return null; }
        scCharts.restoreFromEmpty(canvas);
        const ds = buildBarDatasets(canvas, datasets, opts.palette);
        const config = {
            type: 'bar',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(opts)
        };
        config.options.scales = applyScales(opts);
        config.options.scales.y.grace = '8%';
        return new Chart(getCtx(canvas), config);
    };

    scCharts.horizontalBar = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        options = options || {};
        if (!options.indexAxis) options.indexAxis = 'y';
        if (datasetsTotal(datasets) <= 0) { scCharts.emptyState(canvas, options.emptyMessage); return null; }
        scCharts.restoreFromEmpty(canvas);
        const ds = buildBarDatasets(canvas, datasets, options.palette);
        ds.forEach(function (d) {
            d.maxBarThickness = Math.min(d.maxBarThickness || 34, 34);
            d.categoryPercentage = 0.62;
            d.barPercentage = 0.7;
        });
        const config = {
            type: 'bar',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(options)
        };
        const scales = applyScales(options);
        scales.x.grid.display = true;
        scales.x.grid.drawOnChartArea = true;
        scales.y.grid.display = false;
        scales.y.grid.drawOnChartArea = false;
        scales.x.beginAtZero = true;
        scales.x.grace = '8%';
        config.options.scales = scales;
        return new Chart(getCtx(canvas), config);
    };

    scCharts.doughnut = function (canvasId, labels, data, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        options = options || {};
        const flat = (data || []).reduce(function (a, v) { return a + (typeof v === 'number' ? v : 0); }, 0);
        if (flat <= 0 || (data || []).length < 2) { scCharts.emptyState(canvas, options.emptyMessage || 'Not enough data yet'); return null; }
        scCharts.restoreFromEmpty(canvas);
        const palette = scCharts.palettes[options.palette || 'navy'];
        const ds = [{
            data: data || [],
            backgroundColor: palette.slice(0, (data || []).length),
            borderColor: '#ffffff',
            borderWidth: 3,
            hoverOffset: 6,
        }];
        const config = {
            type: options.type === 'pie' ? 'pie' : 'doughnut',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(options)
        };
        config.options.scales = { x: { display: false }, y: { display: false } };
        return new Chart(getCtx(canvas), config);
    };

    scCharts._registry = scCharts._registry || {};

    scCharts.destroy = function (canvasId) {
        const canvas = getCanvas(canvasId);
        if (!canvas) return;
        const existing = scCharts._registry[canvas.id] || (typeof Chart !== 'undefined' && Chart.getChart && Chart.getChart(canvas));
        if (existing && typeof existing.destroy === 'function') {
            existing.destroy();
        }
        if (canvas.id) delete scCharts._registry[canvas.id];
    };

    scCharts.getData = function (canvasId) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        const chart = Chart.getChart(canvas);
        return chart ? chart.data : null;
    };

    scCharts.getChart = function (canvasId) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        return Chart.getChart(canvas) || null;
    };

    scCharts.fetchRender = function (canvasId, url, type) {
        type = type || 'line';
        const headers = {};
        if (window.scApp && typeof window.scApp.csrfToken === 'function') {
            headers['X-CSRFToken'] = window.scApp.csrfToken();
        }
        return fetch(url, { credentials: 'same-origin', headers: headers })
            .then(function (resp) { return resp.json(); })
            .then(function (payload) {
                const opts = payload.options || {};
                if (type === 'line') return scCharts.line(canvasId, payload.labels, payload.datasets, opts);
                if (type === 'bar') return scCharts.bar(canvasId, payload.labels, payload.datasets, opts);
                if (type === 'horizontalBar') return scCharts.horizontalBar(canvasId, payload.labels, payload.datasets, opts);
                if (type === 'doughnut' || type === 'pie') return scCharts.doughnut(canvasId, payload.labels, payload.data || payload.datasets, opts);
                throw new Error('Unknown chart type: ' + type);
            });
    };

    function autoInit() {
        document.querySelectorAll('canvas[data-chart]').forEach(function (canvas) {
            const url = canvas.getAttribute('data-chart-url');
            const type = canvas.getAttribute('data-chart-type') || 'line';
            if (url) {
                scCharts.fetchRender(canvas.id, url, type).catch(function (err) {
                    console.error('[scCharts] auto-init failed for', canvas.id, err);
                });
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.scCharts = scCharts;
})();
