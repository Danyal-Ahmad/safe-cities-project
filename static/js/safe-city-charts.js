/**
 * SafeCity FYP - Chart.js Wrapper Module
 * Provides a consistent API for line/bar/doughnut charts with
 * prebuilt color palettes and an auto-fetch helper.
 * Requires Chart.js v4 to be loaded globally.
 */
(function () {
    'use strict';

    if (typeof window.Chart === 'undefined') {
        console.warn('[scCharts] Chart.js not found. Charts will not render.');
    }

    const scCharts = {};

    // ============================================================
    // Prebuilt color palettes
    // ============================================================

    scCharts.palettes = {
        navy: ['#1f3b73', '#2d5aa0', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe', '#eff6ff'],
        green: ['#15803d', '#22c55e', '#4ade80', '#86efac', '#bbf7d0', '#16a34a', '#166534', '#14532d'],
        warm: ['#b91c1c', '#dc2626', '#f97316', '#fb923c', '#fbbf24', '#facc15', '#eab308', '#ca8a04'],
        cool: ['#0e7490', '#0891b2', '#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc', '#cffafe', '#ecfeff'],
        all:  ['#1f3b73', '#15803d', '#b91c1c', '#b45309', '#0e7490', '#7c3aed', '#db2777', '#475569']
    };

    // ============================================================
    // Default options
    // ============================================================

    scCharts.defaults = {
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: '#64748b',
        borderColor: '#e2e8f0',
    };

    function mergeOpts(opts) {
        opts = opts || {};
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: scCharts.defaults.fontFamily, size: 12 },
                        color: scCharts.defaults.color,
                        boxWidth: 12,
                        padding: 12,
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#e2e8f0',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 6,
                    titleFont: { family: scCharts.defaults.fontFamily, weight: '600' },
                    bodyFont: { family: scCharts.defaults.fontFamily },
                }
            },
            scales: opts.scales || undefined
        };
    }

    // Apply Chart.js global defaults if available
    if (typeof window.Chart !== 'undefined') {
        try {
            Chart.defaults.font.family = scCharts.defaults.fontFamily;
            Chart.defaults.color = scCharts.defaults.color;
            Chart.defaults.borderColor = scCharts.defaults.borderColor;
        } catch (e) { /* noop */ }
    }

    // ============================================================
    // Internal helpers
    // ============================================================

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

    // ============================================================
    // Chart factory helpers
    // ============================================================

    function buildDatasets(datasets, paletteName) {
        return colorize(datasets, paletteName).map(function (ds) {
            // Set sensible line defaults
            if (!ds.tension) ds.tension = 0.35;
            if (ds.fill === undefined) ds.fill = true;
            if (ds.pointRadius === undefined) ds.pointRadius = 3;
            if (ds.pointHoverRadius === undefined) ds.pointHoverRadius = 5;
            return ds;
        });
    }

    scCharts.line = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const palette = (options && options.palette) || 'navy';
        const ds = buildDatasets(datasets, palette);
        return new Chart(getCtx(canvas), {
            type: 'line',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(options)
        });
    };

    scCharts.bar = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const palette = (options && options.palette) || 'navy';
        const ds = colorize(datasets, palette);
        ds.forEach(function (d) {
            if (d.borderRadius === undefined) d.borderRadius = 4;
            if (d.borderSkipped === undefined) d.borderSkipped = false;
            if (d.maxBarThickness === undefined) d.maxBarThickness = 48;
        });
        return new Chart(getCtx(canvas), {
            type: 'bar',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(options)
        });
    };

    scCharts.horizontalBar = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        options = options || {};
        if (!options.indexAxis) options.indexAxis = 'y';
        const palette = options.palette || 'navy';
        const ds = colorize(datasets, palette);
        return new Chart(getCtx(canvas), {
            type: 'bar',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(options)
        });
    };

    scCharts.doughnut = function (canvasId, labels, data, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        options = options || {};
        const palette = scCharts.palettes[options.palette || 'navy'];
        const ds = [{
            data: data || [],
            backgroundColor: palette.slice(0, (data || []).length),
            borderColor: '#ffffff',
            borderWidth: 2,
        }];
        return new Chart(getCtx(canvas), {
            type: options.type === 'pie' ? 'pie' : 'doughnut',
            data: { labels: labels || [], datasets: ds },
            options: mergeOpts(options)
        });
    };

    // ============================================================
    // Lifecycle helpers
    // ============================================================

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

    // ============================================================
    // Fetch-and-render helper
    // Expects: { labels: [...], datasets: [...], type: 'line'|'bar'|'doughnut', options: {} }
    // ============================================================

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

    // ============================================================
    // Auto-init: any <canvas data-chart> will be rendered
    // ============================================================

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
