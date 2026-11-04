(function () {
  'use strict';

  function init() {
    var createForm = document.querySelector('[data-it-form="create"]');
    var importForm = document.querySelector('[data-it-form="import"]');
    var fileInput = document.querySelector('[data-it-file-input]');
    var fileLabel = document.querySelector('[data-it-file-label]');

    if (createForm) {
      createForm.addEventListener('submit', function (evt) {
        if (!window.confirm('Create a new database snapshot now?')) {
          evt.preventDefault();
        }
      });
    }

    if (importForm && fileInput) {
      importForm.addEventListener('submit', function (evt) {
        if (!fileInput.files || !fileInput.files.length) {
          evt.preventDefault();
          window.alert('Choose a .json backup file to import first.');
          fileInput.focus();
        }
      });
    }

    if (fileInput && fileLabel) {
      fileInput.addEventListener('change', function () {
        var name = fileInput.files && fileInput.files.length ? fileInput.files[0].name : null;
        fileLabel.textContent = name ? 'Selected: ' + name : 'No file selected.';
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
