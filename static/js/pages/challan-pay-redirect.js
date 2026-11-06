
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
