/* Public popup ad dismiss — extracted from templates/challan/_public_ads.html */
(function () {
  'use strict';

  function dismissPopup(){
    var o = document.getElementById('scfPopupOverlay'); o && o.remove();
    try { sessionStorage.setItem('scf_popup_dismissed', '1'); } catch(e) {}
  }

  function init(){
    try {
      if (sessionStorage.getItem('scf_popup_dismissed')) {
        var o = document.getElementById('scfPopupOverlay'); o && o.remove();
      }
    } catch(e) {}
    // Close button (previously inline onclick="dismissPopup()").
    document.querySelectorAll('.scf-popup-close').forEach(function (btn) {
      btn.addEventListener('click', dismissPopup);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
