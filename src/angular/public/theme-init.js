// Apply saved theme or system preference before first paint to avoid flash.
// Must run synchronously before Angular bootstraps.
(function() {
    var t = localStorage.getItem('theme');
    if (t === 'dark' || t === 'light') {
        document.documentElement.setAttribute('data-bs-theme', t);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
})();
