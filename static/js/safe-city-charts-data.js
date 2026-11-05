/**
 * SafeCities Project - Chart Data & Helper Module
 * Reusable data shapes, color palettes, and formatters for charts
 * and KPI displays.
 */
(function () {
    'use strict';

    const scChartsData = {};

    // ============================================================
    // Palettes (5 predefined)
    // ============================================================

    scChartsData.palettes = {
        navy: ['#1f3b73', '#2d5aa0', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe', '#eff6ff'],
        green: ['#15803d', '#22c55e', '#4ade80', '#86efac', '#bbf7d0', '#16a34a', '#166534', '#14532d'],
        warm: ['#b91c1c', '#dc2626', '#f97316', '#fb923c', '#fbbf24', '#facc15', '#eab308', '#ca8a04'],
        cool: ['#0e7490', '#0891b2', '#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc', '#cffafe', '#ecfeff'],
        all:  ['#1f3b73', '#15803d', '#b91c1c', '#b45309', '#0e7490', '#7c3aed', '#db2777', '#475569']
    };

    // ============================================================
    // Common chart defaults
    // ============================================================

    scChartsData.chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: {
                    font: { family: 'Inter, sans-serif', size: 12 },
                    color: '#64748b',
                    boxWidth: 12,
                    padding: 12,
                    usePointStyle: true
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
                titleFont: { family: 'Inter, sans-serif', weight: '600' },
                bodyFont: { family: 'Inter, sans-serif' }
            }
        }
    };

    // ============================================================
    // Violation labels & colors
    // ============================================================

    scChartsData.violationLabels = [
        'Red Light',
        'Speed',
        'Helmet',
        'Seat Belt',
        'Illegal Turn',
        'Wrong Lane',
        'Phone',
        'Signal'
    ];

    scChartsData.violationColors = [
        '#b91c1c', // Red Light - red
        '#f59e0b', // Speed - amber
        '#0e7490', // Helmet - cyan
        '#15803d', // Seat Belt - green
        '#7c3aed', // Illegal Turn - purple
        '#1f3b73', // Wrong Lane - navy
        '#db2777', // Phone - pink
        '#475569'  // Signal - gray
    ];

    // ============================================================
    // Status colors
    // ============================================================

    scChartsData.statusColors = {
        PAID: '#15803d',
        UNPAID: '#b91c1c',
        OVERDUE: '#b45309',
        CANCELLED: '#94a3b8',
        PENDING: '#0e7490',
        ACTIVE: '#15803d',
        INACTIVE: '#94a3b8',
        APPROVED: '#15803d',
        REJECTED: '#b91c1c',
        DRAFT: '#64748b',
        FLAGGED: '#b91c1c',
        RESOLVED: '#15803d',
        OPEN: '#b45309',
        CLOSED: '#15803d'
    };

    scChartsData.getStatusColor = function (status) {
        return scChartsData.statusColors[(status || '').toUpperCase()] || '#64748b';
    };

    scChartsData.getViolationColor = function (idx) {
        return scChartsData.violationColors[idx % scChartsData.violationColors.length];
    };

    // ============================================================
    // Number / KPI formatting
    // ============================================================

    scChartsData.formatKPI = function (value, suffix) {
        if (value === null || value === undefined || isNaN(value)) return '-';
        suffix = suffix != null ? suffix : '';
        const num = Number(value);
        const abs = Math.abs(num);
        let formatted;
        if (abs >= 1e9) formatted = (num / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
        else if (abs >= 1e6) formatted = (num / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
        else if (abs >= 1e3) formatted = (num / 1e3).toFixed(1).replace(/\.0$/, '') + 'k';
        else formatted = num.toLocaleString();
        return formatted + suffix;
    };

    scChartsData.formatNumber = function (value) {
        if (value === null || value === undefined || isNaN(value)) return '-';
        return Number(value).toLocaleString();
    };

    scChartsData.formatPercent = function (value, decimals) {
        if (value === null || value === undefined || isNaN(value)) return '-';
        decimals = decimals != null ? decimals : 1;
        return Number(value).toFixed(decimals) + '%';
    };

    scChartsData.formatCurrency = function (amount) {
        if (amount === null || amount === undefined || isNaN(amount)) return 'PKR 0';
        const n = Number(amount);
        return 'PKR ' + n.toLocaleString('en-PK', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    };

    scChartsData.formatDate = function (d) {
        if (!d) return '';
        const dt = (d instanceof Date) ? d : new Date(d);
        if (isNaN(dt.getTime())) return String(d);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return months[dt.getMonth()] + ' ' + dt.getDate() + ', ' + dt.getFullYear();
    };

    scChartsData.formatDateTime = function (d) {
        if (!d) return '';
        const dt = (d instanceof Date) ? d : new Date(d);
        if (isNaN(dt.getTime())) return String(d);
        function pad(n) { return n < 10 ? '0' + n : '' + n; }
        return scChartsData.formatDate(dt) + ' ' + pad(dt.getHours()) + ':' + pad(dt.getMinutes());
    };

    // ============================================================
    // Helpers
    // ============================================================

    scChartsData.trend = function (current, previous) {
        if (current == null || previous == null || previous === 0) return null;
        return ((current - previous) / previous) * 100;
    };

    scChartsData.trendArrow = function (delta) {
        if (delta == null) return '';
        if (delta > 0) return '\u2191';
        if (delta < 0) return '\u2193';
        return '\u2192';
    };

    scChartsData.trendClass = function (delta, invert) {
        if (delta == null) return '';
        if (delta > 0) return invert ? 'down' : 'up';
        if (delta < 0) return invert ? 'up' : 'down';
        return '';
    };

    // ============================================================
    // Color interpolation for gradients
    // ============================================================

    scChartsData.makeGradient = function (ctx, area, fromColor, toColor) {
        if (!ctx || !area) return fromColor;
        const gradient = ctx.createLinearGradient(0, area.top, 0, area.bottom);
        gradient.addColorStop(0, fromColor);
        gradient.addColorStop(1, toColor);
        return gradient;
    };

    window.scChartsData = scChartsData;
})();
