// Aplica tema, transparencia e idioma antes de arrancar Angular para evitar parpadeo.
(function () {
  var root = document.documentElement;
  function read(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }
  var theme = read('cp.theme') || 'system';
  var dark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  root.classList.toggle('dark', dark);
  if (read('cp.reduceTransparency') === 'true') root.classList.add('reduce-transparency');
  var lang = read('cp.lang');
  if (lang) root.lang = lang;
})();
