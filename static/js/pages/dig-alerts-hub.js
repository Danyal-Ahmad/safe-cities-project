/* Alert Hub - extracted from templates/dashboard/dig/alerts_hub.html */
(function () {
  'use strict';

  // Card/List view toggles
  document.querySelectorAll('.ah-view-toggle').forEach(function(toggle){
    var kind = toggle.getAttribute('data-view-toggle');
    var grid = document.getElementById(kind + 'Grid');
    var wrap = document.getElementById(kind + 'TableWrap');
    toggle.querySelectorAll('.ah-view-btn').forEach(function(btn){
      btn.addEventListener('click', function(){
        toggle.querySelectorAll('.ah-view-btn').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        var isTable = btn.getAttribute('data-view') === 'table';
        if (grid) grid.style.display = isTable ? 'none' : '';
        if (wrap) wrap.style.display = isTable ? '' : 'none';
      });
    });
  });

  // Live filters
  function bindFilter(inputId, sevId, statusId, containerIds){
    function apply(){
      var q = (document.getElementById(inputId)?.value || '').toLowerCase().trim();
      var sev = sevId ? (document.getElementById(sevId)?.value || '') : '';
      var st = statusId ? (document.getElementById(statusId)?.value || '') : '';
      containerIds.forEach(function(cid){
        document.querySelectorAll('#' + cid + ' [data-title]').forEach(function(el){
          var ok = (!q || (el.getAttribute('data-title')||'').includes(q))
                 && (!sev || el.getAttribute('data-sev') === sev)
                 && (!st || el.getAttribute('data-status') === st);
          el.style.display = ok ? '' : 'none';
        });
      });
    }
    [inputId, sevId, statusId].forEach(function(id){
      if (id) document.getElementById(id)?.addEventListener('input', apply);
      if (id) document.getElementById(id)?.addEventListener('change', apply);
    });
  }
  bindFilter('alertSearch', 'alertSevFilter', 'alertStatusFilter', ['alertGrid', 'alertTableWrap']);
  bindFilter('bannerSearch', null, 'bannerStatusFilter', ['bannerGrid', 'bannerTableWrap']);
  bindFilter('broadcastSearch', null, null, ['broadcastGrid', 'broadcastTableWrap']);

  // Edit alert modal - prefill
  var editAlertModal = document.getElementById('editAlertModal');
  if (editAlertModal) editAlertModal.addEventListener('show.bs.modal', function(e){
    var btn = e.relatedTarget;
    document.getElementById('editAlertForm').action = btn.getAttribute('data-edit-url');
    document.getElementById('editAlertTitle').value = btn.getAttribute('data-title') || '';
    document.getElementById('editAlertMessage').value = btn.getAttribute('data-message') || '';
    document.getElementById('editAlertSeverity').value = btn.getAttribute('data-severity') || 'info';
    document.getElementById('editAlertAudience').value = btn.getAttribute('data-audience') || 'all';
    document.getElementById('editAlertActive').checked = btn.getAttribute('data-active') === '1';
  });

  // Edit banner modal - prefill
  var editBannerModal = document.getElementById('editBannerModal');
  if (editBannerModal) editBannerModal.addEventListener('show.bs.modal', function(e){
    var btn = e.relatedTarget;
    document.getElementById('editBannerForm').action = btn.getAttribute('data-edit-url');
    document.getElementById('editBannerTitle').value = btn.getAttribute('data-title') || '';
    document.getElementById('editBannerHtml').value = btn.getAttribute('data-html') || '';
    document.getElementById('editBannerPlacement').value = btn.getAttribute('data-placement') || 'popup';
    document.getElementById('editBannerAudience').value = btn.getAttribute('data-audience') || 'all';
    document.getElementById('editBannerType').value = btn.getAttribute('data-type') || 'html';
    document.getElementById('editBannerHomeOnly').checked = btn.getAttribute('data-home-only') === '1';
    document.getElementById('editBannerActive').checked = btn.getAttribute('data-active') === '1';
  });

  // Delete confirmation modal
  var delModal = document.getElementById('confirmDeleteModal');
  if (delModal) delModal.addEventListener('show.bs.modal', function(e){
    var btn = e.relatedTarget;
    document.getElementById('confirmDeleteForm').action = btn.getAttribute('data-delete-url');
    document.getElementById('confirmDeleteObjectName').textContent = btn.getAttribute('data-object-name') || 'this item';
  });
})();
