/* Officer triage detail partial (_detection_detail.html) — extracted JS.
 * Idempotent: guards against double-binding if the partial is included more
 * than once or this file is loaded multiple times. */
(function () {
  'use strict';

  if (document.body.dataset.officerTriageDetailBound === '1') return;
  document.body.dataset.officerTriageDetailBound = '1';

  function applyQuickNote(text) {
    const noteField = document.getElementById('reviewNotesInput');
    if (noteField) {
      noteField.value = text;
      noteField.focus();
    }
  }

  function validateRejectNotes() {
    const noteField = document.getElementById('reviewNotesInput');
    if (!noteField || noteField.value.trim().length < 5) {
      applyQuickNote('False positive: Vehicle was executing a legal maneuver');
    }
    return true;
  }

  function validateFlagNotes() {
    const noteField = document.getElementById('reviewNotesInput');
    if (!noteField || noteField.value.trim().length < 5) {
      applyQuickNote('Escalated for senior review due to ambiguous plate lighting');
    }
    return true;
  }

  // Quick-reason preset buttons (previously inline onclick="applyQuickNote(...)").
  document.querySelectorAll('[data-quick-note]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      applyQuickNote(btn.getAttribute('data-quick-note'));
    });
  });

  // Triage submit buttons: auto-fill a default note when empty
  // (previously inline onclick="return validateRejectNotes()" / validateFlagNotes()).
  const rejectBtn = document.getElementById('btnRejectTriage');
  if (rejectBtn) rejectBtn.addEventListener('click', function () { validateRejectNotes(); });
  const flagBtn = document.getElementById('btnFlagTriage');
  if (flagBtn) flagBtn.addEventListener('click', function () { validateFlagNotes(); });

  // Target image: fade out when the frame fails to load
  // (previously inline onerror="this.style.opacity='0.15';").
  const targetImg = document.getElementById('detailTargetImage');
  if (targetImg) {
    const fade = function () { targetImg.style.opacity = '0.15'; };
    targetImg.addEventListener('error', fade);
    if (targetImg.complete && targetImg.naturalWidth === 0) fade();
  }
})();
