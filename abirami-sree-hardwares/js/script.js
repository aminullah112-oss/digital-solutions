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

  // Header shadow once the page has scrolled past the hero
  var header = document.querySelector('.site-header');
  if (header) {
    var onScroll = function () {
      header.classList.toggle('is-scrolled', window.scrollY > 12);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  // Scroll-reveal: fade/rise elements into view once, skipped for reduced-motion
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion && 'IntersectionObserver' in window) {
    var revealSelectors = [
      '.about-specialties', '.materials-photo', '.chip', '.s-card',
      '.gallery-grid a', '.vasthu-grid', '.process-strip li', '.pay-card',
      '.contact-card', '.section-title', '.eyebrow'
    ];
    revealSelectors.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        el.classList.add('reveal');
      });
    });

    // Stagger siblings within the same parent so grids animate in sequence.
    var parentIndex = new WeakMap();
    document.querySelectorAll('.reveal').forEach(function (el) {
      var parent = el.parentElement;
      var i = parentIndex.get(parent) || 0;
      el.style.transitionDelay = Math.min(i, 8) * 70 + 'ms';
      parentIndex.set(parent, i + 1);
    });

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0, rootMargin: '0px 0px 200px 0px' });

    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });

    // Backstop: a fast fling, a jump-to-anchor, or an observer edge case can
    // leave an element permanently at opacity 0 if it's never reported as
    // intersecting. Sweep on scroll/resize and reveal anything already on
    // or past screen — content must never stay invisible.
    var sweepPending = false;
    function sweep() {
      sweepPending = false;
      var vh = window.innerHeight;
      document.querySelectorAll('.reveal:not(.is-visible)').forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.top < vh + 200 && r.bottom > -200) {
          el.classList.add('is-visible');
          io.unobserve(el);
        }
      });
    }
    function scheduleSweep() {
      if (sweepPending) return;
      sweepPending = true;
      requestAnimationFrame(sweep);
    }
    window.addEventListener('scroll', scheduleSweep, { passive: true });
    window.addEventListener('resize', scheduleSweep, { passive: true });
    sweep();
  }

  // Subtle mouse-tilt on the hero photo, desktop only, skipped for reduced-motion
  var frame = document.querySelector('.hero-photo-frame');
  if (frame && !reduceMotion && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    var heroArt = document.querySelector('.hero-art');
    heroArt.addEventListener('mousemove', function (e) {
      var rect = heroArt.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width - 0.5;
      var py = (e.clientY - rect.top) / rect.height - 0.5;
      frame.style.transform = 'rotateY(' + (px * 8) + 'deg) rotateX(' + (py * -8) + 'deg)';
    });
    heroArt.addEventListener('mouseleave', function () {
      frame.style.transform = 'rotateY(0deg) rotateX(0deg)';
    });
  }
})();
