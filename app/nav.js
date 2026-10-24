/* Shared top navigation for every Commonwatt page. Include with
     <script src="nav.js"></script>                      (pages in app/)
     <script src="../nav.js" data-root="../"></script>  (pages in app/presentation/)
   It injects a <nav> at the top of <body> and highlights the current page. No dependencies, works from file://. */
(function () {
  'use strict';
  var me = document.currentScript;
  var root = (me && me.getAttribute('data-root')) || '';
  var PAGES = [
    ['index.html', 'Commonwatt', 'home'],
    ['presentation/commonwatt-story.html', 'Scenes'],
    ['story.html', 'Network'],
    ['history.html', 'Trading history'],
    ['member.html', 'Member app'],
    ['about.html', 'About'],
  ];
  var here = location.pathname.replace(/\\/g, '/');
  function isCurrent(href) {
    var file = href.split('/').pop();
    if (href.indexOf('/') > -1) return here.indexOf(href) > -1;
    return here.split('/').pop() === file || (file === 'index.html' && /\/app\/?$|\/$/.test(here));
  }
  var css = '' +
    '.cw-nav{position:sticky;top:0;z-index:50;display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;' +
    'padding:10px max(16px,calc((100vw - 1280px)/2 + 20px));background:rgba(232,235,231,.92);backdrop-filter:blur(8px);' +
    'border-bottom:1px solid #dde1dc;font:600 14px/1.2 "Archivo","Helvetica Neue",Arial,sans-serif}' +
    '.cw-nav a{color:#565d65;text-decoration:none;padding:7px 11px;border-radius:999px}' +
    '.cw-nav a:hover{color:#15181c;background:#fff}' +
    '.cw-nav a[aria-current=page]{color:#fff;background:#15181c}' +
    '.cw-nav a.home{color:#15181c;font-size:17px;font-stretch:115%;margin-right:8px;padding-left:0;background:none}' +
    '.cw-nav a.home[aria-current=page]{color:#15181c;background:none}' +
    '.cw-nav a:focus-visible{outline:2px solid #5960f0;outline-offset:2px}' +
    '@media (max-width:640px){.cw-nav{gap:2px;padding:8px 10px;font-size:12.5px}.cw-nav a{padding:6px 8px}' +
    '.cw-nav a.home{width:100%;font-size:16px}}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  function mount() {
    var nav = document.createElement('nav');
    nav.className = 'cw-nav'; nav.setAttribute('aria-label', 'Commonwatt pages');
    PAGES.forEach(function (p) {
      var a = document.createElement('a');
      a.href = root + p[0]; a.textContent = p[1];
      if (p[2]) a.className = p[2];
      if (isCurrent(p[0])) a.setAttribute('aria-current', 'page');
      nav.appendChild(a);
    });
    document.body.insertBefore(nav, document.body.firstChild);
  }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
})();
