/* DIG admin password reset — extracted from templates/dashboard/dig/admin_reset_password.html */
(function () {
  'use strict';

  // password visibility toggles
  document.querySelectorAll('input[type=password]').forEach(function(inp) {
    const wrap = inp.parentElement;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw-toggle';
    btn.innerHTML = '<i class="bi bi-eye"></i>';
    btn.style.cssText = 'position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;color:#6B7280;cursor:pointer;';
    wrap.style.position = 'relative';
    wrap.appendChild(btn);
    btn.addEventListener('click', function() {
      if (inp.type === 'password') { inp.type = 'text'; btn.innerHTML = '<i class="bi bi-eye-slash"></i>'; }
      else { inp.type = 'password'; btn.innerHTML = '<i class="bi bi-eye"></i>'; }
    });
  });
})();
