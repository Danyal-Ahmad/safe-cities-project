
(function () {
  'use strict';

  function submitRedirectForm(){
    setTimeout(function(){
      var f = document.getElementById('redirectForm');
      if (f) f.submit();
    }, 500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', submitRedirectForm);
  } else {
    submitRedirectForm();
  }
})();
