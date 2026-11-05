
(function () {
  'use strict';

  

  var DEVTOOLS_GAP_THRESHOLD = 160; 
  var CONFIRM_DELAY_MS = 500;       
  var POLL_INTERVAL_MS = 1000;      
  var REQUIRED_STRIKES = 3;         
  var RESIZE_GRACE_MS = 1500;       

  

  function bodyEl() { return document.body; }

  function isProduction() {
    var b = bodyEl();
    return !!b && b.getAttribute('data-env') === 'production';
  }

  function userRole() {
    var b = bodyEl();
    return b ? (b.getAttribute('data-user-role') || '') : '';
  }

  
  function isPortalPage() {
    return /^\/portal(\/|$)/.test(window.location.pathname);
  }

  function isAuthedPortal() {
    return isPortalPage() && userRole() !== '';
  }

  
  

  if (isPortalPage()) {
    document.addEventListener('contextmenu', function (e) {
      e.preventDefault();
    }, true);
  }

  
  

  document.addEventListener('keydown', function (e) {
    if (e.defaultPrevented) { return; }

    var key = (e.key || '').toLowerCase();

    
    if (e.key === 'F12' || e.keyCode === 123) {
      e.preventDefault();
      return;
    }

    
    if (e.ctrlKey && e.shiftKey && (key === 'i' || key === 'j' || key === 'c')) {
      e.preventDefault();
      return;
    }

    
    if (e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey && key === 'u') {
      e.preventDefault();
    }
  }, true);

  
  
  

  function silenceConsole() {
    if (!isProduction()) { return; }
    var methods = ['log', 'info', 'warn', 'error', 'debug'];
    for (var i = 0; i < methods.length; i++) {
      (function (name) {
        try {
          Object.defineProperty(console, name, {
            value: function () {},
            writable: false,
            configurable: false
          });
        } catch (err) {
          
          try { console[name] = function () {}; } catch (err2) {  }
        }
      })(methods[i]);
    }
  }

  

  var strikes = 0;
  var confirmPending = false;
  var blocked = false;
  var lastResizeAt = 0;
  var baseDpr = window.devicePixelRatio || 1;
  var pollTimer = null;
  var confirmTimer = null;

  function widthGap() {
    return (window.outerWidth || 0) - (window.innerWidth || 0);
  }

  function devtoolsOpen() {
    
    
    
    return widthGap() > DEVTOOLS_GAP_THRESHOLD;
  }

  function recentlyResized() {
    return (Date.now() - lastResizeAt) < RESIZE_GRACE_MS;
  }

  
  
  
  function zoomOrDpiChanged() {
    var dpr = window.devicePixelRatio || 1;
    return Math.abs(dpr - baseDpr) > 0.05;
  }

  function stopWatching() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    if (confirmTimer) { clearTimeout(confirmTimer); confirmTimer = null; }
  }

  function triggerBlock() {
    if (blocked) { return; }
    blocked = true;
    stopWatching();

    try { window.stop(); } catch (err) {  }

    var b = bodyEl();
    if (!b) { return; }

    document.title = 'Access Blocked';

    
    
    
    var wrap = document.createElement('div');
    wrap.className = 'sc-guard-block';
    wrap.setAttribute('role', 'alert');

    var card = document.createElement('div');
    card.className = 'sc-guard-block-card';

    var brand = document.createElement('p');
    brand.className = 'sc-guard-block-brand';
    brand.textContent = 'SAFE CITIES PROJECT';

    var title = document.createElement('h1');
    title.className = 'sc-guard-block-title';
    title.textContent = 'Unauthorized inspection attempt blocked.';

    var text = document.createElement('p');
    text.className = 'sc-guard-block-text';
    text.textContent = 'This incident has been logged.';

    var sub = document.createElement('p');
    sub.className = 'sc-guard-block-sub';
    sub.textContent = 'Close this tab and sign in again to continue.';

    card.appendChild(brand);
    card.appendChild(title);
    card.appendChild(text);
    card.appendChild(sub);
    wrap.appendChild(card);
    b.innerHTML = '';
    b.appendChild(wrap);

    
    try {
      window.__SC_GUARD_BLOCKED_AT = new Date().toISOString();
    } catch (err) {  }
  }

  function confirmStrike() {
    confirmTimer = null;
    if (blocked) { return; }

    
    
    if (recentlyResized() || zoomOrDpiChanged() || !devtoolsOpen()) {
      strikes = 0;
      return;
    }

    strikes += 1;

    if (strikes >= REQUIRED_STRIKES && isAuthedPortal()) {
      triggerBlock();
    }
    
    
    
  }

  function poll() {
    if (blocked || confirmPending) { return; }

    if (recentlyResized() || zoomOrDpiChanged()) {
      strikes = 0;
      return;
    }

    if (devtoolsOpen()) {
      
      
      
      confirmPending = true;
      confirmTimer = setTimeout(function () {
        confirmPending = false;
        confirmStrike();
      }, CONFIRM_DELAY_MS);
    } else {
      strikes = 0;
    }
  }

  window.addEventListener('resize', function () {
    lastResizeAt = Date.now();
    strikes = 0;
  }, true);

  pollTimer = setInterval(poll, POLL_INTERVAL_MS);

  

  function freezeConfig() {
    var cfg = window.SAFECITY_CONFIG;
    if (cfg && typeof cfg === 'object') {
      try { Object.freeze(cfg); } catch (err) {  }
    }
  }

  

  
  
  
  function afterDomReady(fn) {
    var done = false;
    function run() {
      if (done) { return; }
      done = true;
      fn();
    }
    document.addEventListener('DOMContentLoaded', run);
    window.addEventListener('load', run);
    if (document.readyState === 'complete') { run(); }
  }

  freezeConfig();
  afterDomReady(function () {
    freezeConfig();          
    silenceConsole();        
  });
  window.addEventListener('load', freezeConfig);
})();
