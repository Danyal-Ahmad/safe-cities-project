(function () {
    'use strict';

    var SPEED_PX_PER_SEC = 56;
    var reduced = false;
    try { reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { reduced = false; }

    function trackNeedsClone(track) {
        var viewport = track.parentElement;
        var vw = viewport ? viewport.clientWidth : window.innerWidth;
        return track.scrollWidth < vw * 2;
    }

    function setupTrack(track) {
        if (!track || track.dataset.scMarqueeReady === '1') return;
        var items = Array.prototype.slice.call(track.children);
        if (!items.length) return;
        track.dataset.scMarqueeReady = '1';

        var original = items.length;
        if (original === 1) { track.appendChild(items[0].cloneNode(true)); }

        var guard = 0;
        while (trackNeedsClone(track) && guard < 12) {
            items.forEach(function (node) { track.appendChild(node.cloneNode(true)); });
            guard += 1;
        }

        if (reduced || !track.scrollWidth) return;

        var duration = Math.max(12, Math.round(track.scrollWidth / 2 / SPEED_PX_PER_SEC));
        track.style.animationDuration = duration + 's';
        track.classList.add('sc-marquee-run');

        var host = track.closest('.sc-ticker, .ps-ticker');
        if (host) {
            host.addEventListener('mouseenter', function () { track.style.animationPlayState = 'paused'; });
            host.addEventListener('mouseleave', function () { track.style.animationPlayState = 'running'; });
        }
    }

    function init() {
        document.querySelectorAll('.sc-ticker-track, .ps-ticker-track, [data-sc-marquee]').forEach(setupTrack);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    window.addEventListener('resize', function () {
        document.querySelectorAll('.sc-ticker-track, .ps-ticker-track').forEach(function (track) {
            if (trackNeedsClone(track) && track.dataset.scMarqueeReady === '1') {
                var items = Array.prototype.slice.call(track.children, 0, Math.ceil(track.children.length / 2));
                var guard = 0;
                while (trackNeedsClone(track) && guard < 8) {
                    items.forEach(function (node) { track.appendChild(node.cloneNode(true)); });
                    guard += 1;
                }
            }
        });
    });
})();
