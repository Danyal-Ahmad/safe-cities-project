(function () {
  'use strict';

  function qs(id) { return document.getElementById(id); }

  function fillForm(btn) {
    qs('adFormAction').value = 'edit';
    qs('adFormId').value = btn.dataset.id || '';
    qs('adFormName').value = btn.dataset.title || '';
    qs('adFormType').value = btn.dataset.type || 'html';
    qs('adFormPlacement').value = btn.dataset.placement || 'ticker';
    qs('adFormAudience').value = btn.dataset.audience || 'all';
    qs('adFormHtml').value = btn.dataset.html || '';
    qs('adFormLink').value = btn.dataset.link || '';
    qs('adFormBg').value = btn.dataset.bg || '#1F4E79';
    qs('adFormFg').value = btn.dataset.fg || '#FFFFFF';
    qs('adFormPriority').value = btn.dataset.priority || 0;
    qs('adFormActive').checked = btn.dataset.active === '1';
    qs('adFormStart').value = btn.dataset.start || '';
    qs('adFormExpires').value = btn.dataset.expires || '';
    qs('adFormTitle').innerHTML = '<i class="bi bi-pencil me-2"></i>Edit Ad';
    qs('adFormSave').textContent = 'Save Changes';
  }

  function clearForm() {
    qs('adFormAction').value = 'create';
    qs('adFormId').value = '';
    qs('adFormName').value = '';
    qs('adFormType').value = 'html';
    qs('adFormPlacement').value = 'ticker';
    qs('adFormAudience').value = 'all';
    qs('adFormHtml').value = '';
    qs('adFormLink').value = '';
    qs('adFormBg').value = '#1F4E79';
    qs('adFormFg').value = '#FFFFFF';
    qs('adFormPriority').value = 0;
    qs('adFormActive').checked = true;
    qs('adFormStart').value = '';
    qs('adFormExpires').value = '';
    qs('adFormImage').value = '';
    qs('adFormTitle').innerHTML = '<i class="bi bi-plus-circle me-2"></i>New Ad';
    qs('adFormSave').textContent = 'Save Ad';
  }

  document.addEventListener('show.bs.modal', function (ev) {
    var modal = ev.target;
    if (!modal) return;
    if (modal.id === 'adFormModal') {
      var btn = ev.relatedTarget;
      if (btn && btn.dataset.mode === 'edit') { fillForm(btn); } else { clearForm(); }
    } else if (modal.id === 'adDeleteModal') {
      var d = ev.relatedTarget;
      if (d) {
        qs('adDeleteId').value = d.dataset.id || '';
        qs('adDeleteTitle').textContent = d.dataset.title || 'this ad';
      }
    }
  }, false);
})();
