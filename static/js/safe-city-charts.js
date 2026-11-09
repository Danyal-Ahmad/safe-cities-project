
(function () {
    'use strict';

    if (typeof window.Chart === 'undefined') {
        console.warn('[scCharts] Chart.js not found. Charts will not render.');
    }

    const scCharts = {};


    scCharts.palettes = {
        navy: ['#2563EB', '#1D4ED8', '#3B82F6', '#60A5FA', '#93C5FD', '#BFDBFE', '#1E40AF', '#DBEAFE'],
        green: ['#22A45D', '#16A34A', '#4ADE80', '#86EFAC', '#BBF7D0', '#15803D', '#166534', '#14532D'],
        warm: ['#E23B4E', '#F97316', '#FB923C', '#FBBF24', '#FACC15', '#DC2626', '#B91C1C', '#CA8A04'],
        cool: ['#14B8A6', '#06B6D4', '#22D3EE', '#67E8F9', '#A5F3FC', '#0E7490', '#0891B2', '#ECFEFF'],
        all:  ['#2563EB', '#22A45D', '#F5A623', '#E23B4E', '#14B8A6', '#7C5CE0', '#DB2777', '#5B6B85']
    };


    scCharts.defaults = {
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: '#5B6B85',
        gridColor: 'rgba(180, 192, 214, 0.35)',
        axisColor: '#8A94B0',
        barRadius: 9,
        lineTension: 0.42,
        labelMax: 24
    };

    function hexToRgba(hex, alpha) {
        const h = (hex || '#2563EB').replace('#', '');
        const r = parseInt(h.substring(0, 2), 16);
        const g = parseInt(h.substring(2, 4), 16);
        const b = parseInt(h.substring(4, 6), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + (alpha == null ? 0.2 : alpha) + ')';
    }


    function gradientFill(ctx, canvas, hex) {
        try {
            var h = (canvas.parentElement && canvas.parentElement.clientHeight) ||
                    canvas.clientHeight || canvas.height || 260;
            if (h < 40) h = 260;
            var g = ctx.createLinearGradient(0, 0, 0, h);
            g.addColorStop(0, hexToRgba(hex, 0.28));
            g.addColorStop(0.6, hexToRgba(hex, 0.10));
            g.addColorStop(1, hexToRgba(hex, 0));
            return g;
        } catch (e) {
            return hexToRgba(hex, 0.15);
        }
    }


    function baseLegend() {
        return {
            position: 'bottom',
            align: 'center',
            labels: {
                font: { family: scCharts.defaults.fontFamily, size: 12 },
                color: scCharts.defaults.color,
                boxWidth: 9,
                boxHeight: 9,
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 16
            }
        };
    }

    function baseTooltip() {
        return {
            backgroundColor: 'rgba(15, 37, 87, 0.96)',
            titleColor: '#FFFFFF',
            bodyColor: '#DBE6F8',
            borderColor: 'rgba(96, 165, 250, 0.35)',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 10,
            displayColors: true,
            usePointStyle: true,
            titleFont: { family: scCharts.defaults.fontFamily, weight: '700', size: 12 },
            bodyFont: { family: scCharts.defaults.fontFamily, size: 12 }
        };
    }


    function buildScales(opts, unit) {
        const s = (opts && opts.scales) || {};
        if (unit) {

            if (!s.y) s.y = {};
            if (!s.y.title) s.y.title = { display: true, text: unit, font: { family: scCharts.defaults.fontFamily, size: 11, weight: '600' }, color: scCharts.defaults.axisColor };
        }
        ['x', 'y'].forEach(function (axis) {
            if (s[axis] === null || s[axis] === false) return;
            s[axis] = s[axis] || {};
            if (s[axis].grid === undefined) {
                s[axis].grid = axis === 'y'
                    ? { color: scCharts.defaults.gridColor, drawTicks: false, borderDash: [4, 4] }
                    : { display: false };
            }
            if (s[axis].ticks === undefined) {
                s[axis].ticks = { color: scCharts.defaults.axisColor, font: { family: scCharts.defaults.fontFamily, size: 11 }, padding: 6 };
            }
            if (s[axis].border === undefined) s[axis].border = { display: false };
        });
        return s;
    }


    function paddedMax(datasets) {
        let max = 0;
        (datasets || []).forEach(function (ds) {
            (ds.data || []).forEach(function (v) {
                if (typeof v === 'number' && v > max) max = v;
            });
        });
        return max > 0 ? max * 1.28 : 10;
    }

    function mergeOpts(opts, extra) {
        opts = opts || {};
        const merged = {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 18 } },
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: (opts.legend === false) ? { display: false } : baseLegend(),
                tooltip: baseTooltip(),
                datalabels: { display: false }
            },
            animation: { duration: 650, easing: 'easeOutQuart' },
            scales: opts.scales
        };
        if (extra) Object.assign(merged, extra);
        return merged;
    }


    if (typeof window.Chart !== 'undefined') {
        try {
            Chart.defaults.font.family = scCharts.defaults.fontFamily;
            Chart.defaults.color = scCharts.defaults.color;
            Chart.defaults.borderColor = 'rgba(180, 192, 214, 0.30)';
            if (window.ChartDataLabels) {
                Chart.register(window.ChartDataLabels);


                Chart.defaults.set('plugins.datalabels', { display: false });
            }
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

    function isAllEmpty(values) {
        return !values || values.length === 0 ||
            values.every(function (v) { return !v || (typeof v === 'number' && v === 0); });
    }


    scCharts.emptyState = function (canvasId, message) {
        const canvas = getCanvas(canvasId);
        if (!canvas) return;
        const wrap = canvas.parentElement;
        if (!wrap || wrap.querySelector('.sc-chart-empty')) return;
        if (getComputedStyle(wrap).position === 'static') {
            wrap.style.position = 'relative';
        }
        const box = document.createElement('div');
        box.className = 'sc-chart-empty';
        box.innerHTML = '<i class="bi bi-bar-chart-steps" aria-hidden="true"></i>' +
                        '<span>' + (message || 'No data to display yet') + '</span>';
        canvas.style.display = 'none';
        wrap.appendChild(box);
    };

    scCharts.clearEmptyState = function (canvasId) {
        const canvas = getCanvas(canvasId);
        if (!canvas) return;
        const wrap = canvas.parentElement;
        const box = wrap ? wrap.querySelector('.sc-chart-empty') : null;
        if (box) box.remove();
        canvas.style.display = '';
    };

    function colorize(datasets, paletteName) {
        const palette = scCharts.palettes[paletteName || 'navy'] || scCharts.palettes.navy;
        return (datasets || []).map(function (ds, i) {
            const c = palette[i % palette.length];
            if (ds.backgroundColor === undefined) {
                ds.backgroundColor = ds.type === 'line'
                    ? hexToRgba(c, 0.15)
                    : ((ds.type === 'doughnut' || ds.type === 'pie') ? palette : c);
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


    function buildDatasets(datasets, paletteName, ctx, canvas) {
        const palette = scCharts.palettes[paletteName || 'navy'] || scCharts.palettes.navy;
        return colorize(datasets, paletteName).map(function (ds, i) {
            const c = palette[i % palette.length];

            if (ds.type === 'line' || (!ds.type && !ds.indexAxis)) {
                ds.type = ds.type || 'line';
                ds.tension = ds.tension === undefined ? scCharts.defaults.lineTension : ds.tension;
                ds.cubicInterpolationMode = ds.cubicInterpolationMode || 'monotone';
                ds.fill = ds.fill === undefined ? true : ds.fill;
                ds.borderWidth = ds.borderWidth || 2.5;
                ds.pointRadius = ds.pointRadius === undefined ? 3 : ds.pointRadius;
                ds.pointHoverRadius = ds.pointHoverRadius === undefined ? 6 : ds.pointHoverRadius;
                ds.pointBackgroundColor = ds.pointBackgroundColor || '#FFFFFF';
                ds.pointBorderColor = ds.pointBorderColor || c;
                ds.pointBorderWidth = ds.pointBorderWidth || 2;
                ds.pointHoverBackgroundColor = c;
                if (ds.fill && ctx && canvas && typeof ds.backgroundColor === 'string' && ds.backgroundColor.startsWith('rgba')) {
                    ds.backgroundColor = gradientFill(ctx, canvas, c);
                }
            }
            return ds;
        });
    }


    function barDataLabels(labels, datasets) {
        return {
            display: (datasets || []).length === 1 && (labels || []).length <= scCharts.defaults.labelMax,
            anchor: 'end',
            align: 'end',
            offset: -2,
            color: '#5B6B85',
            font: { family: scCharts.defaults.fontFamily, size: 11, weight: '700' },
            formatter: function (v) {
                if (v === null || v === undefined) return '';
                if (typeof v === 'number' && !Number.isInteger(v)) return v.toFixed(1);
                return v;
            }
        };
    }

    scCharts.line = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const opts = options || {};
        const palette = opts.palette || 'navy';
        if (isAllEmpty((datasets || []).map(function (d) { return d.data; }).flat())) {
            scCharts.emptyState(canvasId, opts.emptyMessage);
            return null;
        }
        scCharts.clearEmptyState(canvasId);


        (datasets || []).forEach(function (d) { if (!d.type) d.type = 'line'; });
        const ds = buildDatasets(datasets, palette, getCtx(canvas), canvas);
        const scales = buildScales(opts, opts.unit);
        scales.y = scales.y || {};
        if (scales.y.suggestedMax === undefined) scales.y.suggestedMax = paddedMax(datasets) * 0.55;
        if (scales.y.beginAtZero === undefined) scales.y.beginAtZero = true;
        const chartOpts = mergeOpts(opts, { scales: scales });
        chartOpts.plugins.datalabels = { display: false };
        return new Chart(getCtx(canvas), {
            type: 'line',
            data: { labels: labels || [], datasets: ds },
            options: chartOpts
        });
    };

    scCharts.bar = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const opts = options || {};
        const palette = opts.palette || 'navy';
        if (isAllEmpty((datasets || []).map(function (d) { return d.data; }).flat())) {
            scCharts.emptyState(canvasId, opts.emptyMessage);
            return null;
        }
        scCharts.clearEmptyState(canvasId);
        const ds = colorize(datasets, palette);
        ds.forEach(function (d) {

            d.borderRadius = d.borderRadius === undefined ? scCharts.defaults.barRadius : d.borderRadius;
            d.borderSkipped = d.borderSkipped === undefined ? false : d.borderSkipped;
            d.maxBarThickness = d.maxBarThickness === undefined ? 42 : d.maxBarThickness;
            d.backgroundColor = typeof d.backgroundColor === 'string'
                ? hexToRgba(d.borderColor || d.backgroundColor, 0.85)
                : d.backgroundColor;
        });
        const scales = buildScales(opts, opts.unit);
        scales.y = scales.y || {};
        if (scales.y.suggestedMax === undefined) scales.y.suggestedMax = paddedMax(datasets);
        if (scales.y.beginAtZero === undefined) scales.y.beginAtZero = true;
        const chartOpts = mergeOpts(opts, { scales: scales });
        chartOpts.plugins.datalabels = barDataLabels(labels, datasets);
        return new Chart(getCtx(canvas), {
            type: 'bar',
            data: { labels: labels || [], datasets: ds },
            options: chartOpts
        });
    };

    scCharts.horizontalBar = function (canvasId, labels, datasets, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const opts = options || {};
        if (!opts.indexAxis) opts.indexAxis = 'y';
        const palette = opts.palette || 'navy';
        if (isAllEmpty((datasets || []).map(function (d) { return d.data; }).flat())) {
            scCharts.emptyState(canvasId, opts.emptyMessage);
            return null;
        }
        scCharts.clearEmptyState(canvasId);
        const ds = colorize(datasets, palette);
        ds.forEach(function (d) {
            d.borderRadius = d.borderRadius === undefined ? scCharts.defaults.barRadius : d.borderRadius;
            d.borderSkipped = d.borderSkipped === undefined ? false : d.borderSkipped;
            d.maxBarThickness = d.maxBarThickness === undefined ? 30 : d.maxBarThickness;
            d.backgroundColor = typeof d.backgroundColor === 'string'
                ? hexToRgba(d.borderColor || d.backgroundColor, 0.85)
                : d.backgroundColor;
        });
        const scales = buildScales(opts, opts.unit);
        scales.x = scales.x || {};
        if (scales.x.suggestedMax === undefined) scales.x.suggestedMax = paddedMax(datasets);
        if (scales.x.beginAtZero === undefined) scales.x.beginAtZero = true;


        const chartOpts = mergeOpts(opts, { scales: scales, indexAxis: 'y' });


        if (scales.x.suggestedMax) scales.x.suggestedMax = scales.x.suggestedMax * 1.12 + 1;
        chartOpts.layout = chartOpts.layout || {};
        chartOpts.layout.padding = chartOpts.layout.padding || {};
        chartOpts.layout.padding.right = 34;
        chartOpts.plugins.datalabels = {
            display: true,
            anchor: 'end',
            align: 'end',
            color: '#5B6B85',
            font: { family: scCharts.defaults.fontFamily, size: 11, weight: '700' },
            formatter: function (v) { return v === null || v === undefined ? '' : v; }
        };
        return new Chart(getCtx(canvas), {
            type: 'bar',
            data: { labels: labels || [], datasets: ds },
            options: chartOpts
        });
    };

    scCharts.doughnut = function (canvasId, labels, data, options) {
        const canvas = getCanvas(canvasId);
        if (!canvas || typeof window.Chart === 'undefined') return null;
        scCharts.destroy(canvasId);
        const opts = options || {};
        const palette = scCharts.palettes[opts.palette || 'navy'];


        if (isAllEmpty(data) || (labels || []).length === 0) {
            scCharts.emptyState(canvasId, opts.emptyMessage || 'No records yet');
            return null;
        }
        scCharts.clearEmptyState(canvasId);


        const positive = (data || []).filter(function (v) { return (v || 0) > 0; }).length;
        const single = (labels || []).length === 1 || positive === 1;

        const colors = (opts.colors && opts.colors.length)
            ? opts.colors
            : palette.slice(0, (data || []).length);
        const ds = [{
            data: data || [],
            backgroundColor: colors,
            borderColor: '#FFFFFF',
            borderWidth: single ? 0 : 3,
            hoverOffset: 6,
            borderRadius: single ? 0 : 6
        }];
        const chartOpts = mergeOpts(opts, {
            cutout: opts.cutout === undefined ? (single ? '70%' : '62%') : opts.cutout,
            scales: null
        });
        if (single) {
            chartOpts.plugins.legend = { display: false };
            const centerValue = (data || []).reduce(function (a, b) { return a + (b || 0); }, 0);
            const centerLabel = (labels || []).slice(0, 2).join(' + ');
            const ctx = getCtx(canvas);
            chartOpts.plugins.centerText = false;
            delete chartOpts.plugins.centerText;
            const centerTextPlugin = {
                id: 'scCenterText',
                afterDraw: function (chart) {
                    if (chart.config.type !== 'doughnut' && chart.config.type !== 'pie') return;
                    const meta = chart.getDatasetMeta(0);
                    if (!meta.data.length) return;
                    const arc = meta.data[0];
                    const x = arc.x, y = arc.y;
                    ctx.save();
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = '#0F2557';
                    ctx.font = '800 ' + Math.round(canvas.clientHeight / 6.2) + 'px ' + scCharts.defaults.fontFamily;
                    ctx.fillText(String(centerValue), x, y - 6);
                    ctx.fillStyle = '#8A94B0';
                    ctx.font = '600 ' + Math.max(9, Math.round(canvas.clientHeight / 15)) + 'px ' + scCharts.defaults.fontFamily;
                    ctx.fillText(String(centerLabel).toUpperCase(), x, y + Math.round(canvas.clientHeight / 12));
                    ctx.restore();
                }
            };
            return new Chart(getCtx(canvas), {
                type: opts.type === 'pie' ? 'pie' : 'doughnut',
                data: { labels: labels || [], datasets: ds },
                options: chartOpts,
                plugins: [centerTextPlugin]
            });
        }
        chartOpts.plugins.legend = opts.legend === false
            ? { display: false }
            : {
                position: 'bottom',
                labels: {
                    font: { family: scCharts.defaults.fontFamily, size: 12 },
                    color: scCharts.defaults.color,
                    boxWidth: 9, boxHeight: 9,
                    usePointStyle: true, pointStyle: 'circle',
                    padding: 14,
                    generateLabels: function (chart) {


                        return chart.data.labels.map(function (label, i) {
                            const v = chart.data.datasets[0].data[i] || 0;
                            const bg = chart.data.datasets[0].backgroundColor[i];
                            return {
                                text: label + '  (' + v + ')',
                                fillStyle: bg,
                                strokeStyle: bg,
                                pointStyle: 'circle',
                                hidden: false,
                                index: i
                            };
                        });
                    }
                }
            };
        chartOpts.plugins.datalabels = { display: false };
        return new Chart(getCtx(canvas), {
            type: opts.type === 'pie' ? 'pie' : 'doughnut',
            data: { labels: labels || [], datasets: ds },
            options: chartOpts
        });
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
