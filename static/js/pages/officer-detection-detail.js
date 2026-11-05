
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(function () {

    
    document.querySelectorAll('img[data-img-fallback]').forEach(function (img) {
      img.addEventListener('error', function () {
        var box = img.closest('.sc-evidence-imgbox') || img.parentElement;
        img.remove();
        if (box) { box.classList.add('is-broken'); }
      });
    });

    
    document.querySelectorAll('.sc-conf-fill[data-conf-width]').forEach(function (el) {
      var w = parseInt(el.getAttribute('data-conf-width'), 10);
      if (!isNaN(w)) {
        el.style.width = Math.max(0, Math.min(100, w)) + '%';
      }
    });

    
    document.querySelectorAll('[data-notes-input]').forEach(function (input) {
      var min = parseInt(input.getAttribute('data-notes-min') || '0', 10);
      var form = input.closest('form');
      var counter = form ? form.querySelector('[data-notes-counter]') : null;
      function update() {
        var len = input.value.trim().length;
        if (counter) {
          counter.textContent = String(len);
          if (counter.parentElement) {
            counter.parentElement.classList.toggle('is-valid-note', len >= min);
          }
        }
      }
      input.addEventListener('input', update);
      update();
    });

    
    document.querySelectorAll('form[data-notes-form]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        var min = parseInt(form.getAttribute('data-notes-min') || '0', 10);
        var input = form.querySelector('[data-notes-input]');
        var len = input ? input.value.trim().length : min;

        if (len < min) {
          e.preventDefault();
          if (window.Swal) {
            window.Swal.fire({
              icon: 'error',
              title: 'Notes are too short',
              text: 'Please write at least ' + min + ' characters (' + len + ' so far).',
              confirmButtonColor: '#16294E'
            });
          } else {
            window.alert('Please write at least ' + min + ' characters (' + len + ' so far).');
          }
          if (input) { input.focus(); }
          return;
        }

        var confirmTitle = form.getAttribute('data-confirm-title');
        if (confirmTitle) {
          e.preventDefault();
          if (window.Swal) {
            window.Swal.fire({
              icon: 'warning',
              title: confirmTitle,
              text: form.getAttribute('data-confirm-text') || '',
              showCancelButton: true,
              confirmButtonText: form.getAttribute('data-confirm-button') || 'Confirm',
              confirmButtonColor: '#E23B4E',
              cancelButtonColor: '#94A3B8'
            }).then(function (result) {
              if (result.isConfirmed) {
                form.removeAttribute('data-notes-form');
                form.submit();
              }
            });
          } else if (window.confirm(confirmTitle)) {
            form.removeAttribute('data-notes-form');
            form.submit();
          }
        }
      });
    });

    
    document.querySelectorAll('[data-copy-value]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var value = btn.getAttribute('data-copy-value') || '';
        var original = btn.innerHTML;
        function restore() { btn.innerHTML = original; }
        function done(ok) {
          btn.innerHTML = ok
            ? '<i class="bi bi-clipboard-check"></i> Copied'
            : '<i class="bi bi-clipboard-x"></i> Failed';
          window.setTimeout(restore, 1600);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(value).then(function () { done(true); }, function () { done(false); });
        } else {
          done(false);
        }
      });
    });

  });
})();

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
        tag.textContent = chosen.dataset.frameLabel + ' / 0' + Math.max(srcs.length, 1) + '3'.slice(-2);
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

  document.addEventListener('keydown', function (e) {
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    var srcs = sources();
    if (!srcs.length) return;
    var current = srcs.findIndex(function (s) { return s.src === main.src; });
    if (e.key === 'ArrowRight' || e.key === '2') {
      selectSlot(Math.min(current + 2, srcs.length));
    } else if (e.key === 'ArrowLeft' || e.key === '1') {
      selectSlot(Math.max(current, 1));
    } else if (e.key === '3') {
      selectSlot(3);
    }
  });
})();
