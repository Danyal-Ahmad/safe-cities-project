/* AI Review Queue hotkeys - extracted from templates/dashboard/officer/review_queue.html */
(function () {
  'use strict';

  // Whether a detection is currently selected is flagged by the server on the
  // triage grid via data-has-selected (previously an inline {% if selected %}).
  const triageGrid = document.querySelector('.md-triage-grid');
  const hasSelected = triageGrid ? triageGrid.dataset.hasSelected === '1' : false;

  document.addEventListener('keydown', function(e) {
    // If user is focused on an input or textarea, do not trigger single-key hotkeys
    const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') {
      return;
    }

    const key = e.key.toUpperCase();

    // 'C' -> Confirm & Issue Challan
    if (key === 'C') {
      const btn = document.getElementById('btnConfirmTriage');
      if (btn) {
        e.preventDefault();
        btn.click();
      }
    }
    // 'R' -> Reject False Positive
    else if (key === 'R') {
      const btn = document.getElementById('btnRejectTriage');
      if (btn) {
        e.preventDefault();
        btn.click();
      }
    }
    // 'F' -> Flag for DIG Escalation
    else if (key === 'F') {
      const btn = document.getElementById('btnFlagTriage');
      if (btn) {
        e.preventDefault();
        btn.click();
      }
    }
    else if (key === 'A') {
      if (hasSelected) {
        e.preventDefault();
      }
    }
    // Arrow Down / Arrow Up to navigate items in the queue
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const queueLinks = Array.from(document.querySelectorAll('.md-queue-item'));
      if (queueLinks.length === 0) return;

      let currentIndex = queueLinks.findIndex(l => l.classList.contains('active'));
      if (e.key === 'ArrowDown') {
        const nextIndex = currentIndex < queueLinks.length - 1 ? currentIndex + 1 : 0;
        queueLinks[nextIndex].click();
        e.preventDefault();
      } else if (e.key === 'ArrowUp') {
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : queueLinks.length - 1;
        queueLinks[prevIndex].click();
        e.preventDefault();
      }
    }
  });

  // Queue thumbnails: fade out when the frame image fails to load
  // (previously inline onerror="this.style.opacity='0.15';").
  document.querySelectorAll('#queueItemsList img').forEach(function (img) {
    const fade = function () { img.style.opacity = '0.15'; };
    img.addEventListener('error', fade);
    if (img.complete && img.naturalWidth === 0) fade();
  });
})();

// --- 3-frame sequential evidence viewer (shared triage partial) ---
(function () {
  var main = document.getElementById('detailTargetImage');
  var strip = document.getElementById('seqFrameStrip');
  var tag = document.getElementById('seqFrameTag');
  if (!main || !strip) return;

  function sources() {
    return Array.prototype.slice.call(document.querySelectorAll('.seq-frame-src'));
  }

  function selectSlot(slot) {
    var srcs = sources();
    var chosen = srcs.filter(function (s) { return s.dataset.frameSlot === String(slot); })[0];
    if (chosen) {
      main.src = chosen.src;
      if (tag) {
        tag.textContent = chosen.dataset.frameLabel + ' / ' + (srcs.length < 10 ? '0' : '') + srcs.length;
      }
    }
    Array.prototype.forEach.call(strip.querySelectorAll('.seq-frame-btn'), function (b) {
      var active = b.dataset.frameSlot === String(slot);
      b.style.borderColor = active ? '#38bdf8' : '#334155';
      var im = b.querySelector('img');
      if (im) im.style.opacity = active ? '1' : '0.65';
    });
  }

  strip.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.seq-frame-btn') : null;
    if (btn) selectSlot(btn.dataset.frameSlot);
  });
})();
