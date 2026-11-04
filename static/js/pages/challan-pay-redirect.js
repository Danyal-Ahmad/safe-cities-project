/* Guest payment gateway auto-submit — extracted from templates/challan/pay_redirect.html */
(function () {
  'use strict';

  function submitGatewayForm(){
    setTimeout(function(){
      var f = document.getElementById('gw');
      if (f) f.submit();
    }, 500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', submitGatewayForm);
  } else {
    submitGatewayForm();
  }
})();
