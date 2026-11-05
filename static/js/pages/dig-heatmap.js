/* Violation Heatmap - extracted from templates/dashboard/dig/heatmap.html */
(function () {
  'use strict';

  // Heat points are supplied by the server on #heatmap-map via data-heat-points
  // (previously inlined with {{ heat_points|safe }}).
  const mapEl = document.getElementById('heatmap-map');
  let heatPoints = [];
  try { heatPoints = JSON.parse((mapEl && mapEl.dataset.heatPoints) || '[]'); } catch(e) { heatPoints = []; }

  const map = L.map('heatmap-map').setView([31.5497, 74.3436], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  if (heatPoints.length && window.L.heatLayer) {
    L.heatLayer(heatPoints, {
      radius: 28, blur: 18, maxZoom: 16,
      gradient: { 0.2: '#4ade80', 0.5: '#fbbf24', 0.8: '#f87171', 1.0: '#dc2626' }
    }).addTo(map);
  } else if (!heatPoints.length) {
    const noData = document.createElement('div');
    noData.className = 'sc-empty p-4 text-center';
    noData.innerHTML = '<i class="bi bi-map" style="font-size:2rem;"></i><br>No GPS data yet. Add lat/lng to cameras.';
    document.getElementById('heatmap-map').replaceWith(noData);
  }
})();
