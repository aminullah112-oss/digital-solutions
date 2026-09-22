(function () {
  var toggle = document.getElementById('navToggle');
  var nav = document.getElementById('main-nav');

  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    nav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  var yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  var waNumber = '919444569023';
  document.querySelectorAll('.s-link[data-service]').forEach(function (link) {
    var service = link.getAttribute('data-service');
    var text = encodeURIComponent(
      'Hi, I\'d like to enquire about: ' + service + '.'
    );
    link.href = 'https://wa.me/' + waNumber + '?text=' + text;
    link.target = '_blank';
    link.rel = 'noopener';
  });
})();
