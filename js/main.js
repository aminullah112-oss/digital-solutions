// Aminullah portfolio — interactivity

// Paste your deployed Google Apps Script Web App URL here (see README: "Lead Capture Backend Setup").
// Leave blank and the form will tell visitors to email you directly instead of failing silently.
var LEADS_ENDPOINT = '';

document.addEventListener('DOMContentLoaded', function () {

    /* 3D cursor-tracked tilt — only on devices with a real mouse, and only when the
       visitor hasn't asked for reduced motion. Touch/keyboard users keep the plain
       CSS :hover lift as a fallback (see css/style.css). */
    var canTilt = window.matchMedia('(hover: hover) and (pointer: fine)').matches &&
        !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function init3DTilt(selector, maxTilt, lift) {
        if (!canTilt) return;
        document.querySelectorAll(selector).forEach(function (el) {
            el.addEventListener('mousemove', function (e) {
                var rect = el.getBoundingClientRect();
                var x = (e.clientX - rect.left) / rect.width;
                var y = (e.clientY - rect.top) / rect.height;
                var rotateY = (x - 0.5) * maxTilt * 2;
                var rotateX = (0.5 - y) * maxTilt * 2;
                el.style.transform = 'perspective(900px) rotateX(' + rotateX.toFixed(2) + 'deg) ' +
                    'rotateY(' + rotateY.toFixed(2) + 'deg) translateY(-' + lift + 'px) translateZ(10px)';
            });
            el.addEventListener('mouseleave', function () {
                el.style.transform = '';
            });
        });
    }
    init3DTilt('.project-card', 6, 8);
    init3DTilt('.product-chip', 5, 3);
    init3DTilt('.track-card', 6, 4);
    init3DTilt('.process-card', 6, 4);
    init3DTilt('.identity-card', 4, 2);

    /* Hero panels tilt together toward the cursor, as one rigid group */
    var heroTilt = document.getElementById('heroTilt');
    var heroSection = document.getElementById('home');
    if (canTilt && heroTilt && heroSection) {
        heroSection.addEventListener('mousemove', function (e) {
            var rect = heroSection.getBoundingClientRect();
            var x = (e.clientX - rect.left) / rect.width;
            var y = (e.clientY - rect.top) / rect.height;
            var rotateY = (x - 0.5) * 16;
            var rotateX = (0.5 - y) * 10;
            heroTilt.style.transform = 'rotateX(' + rotateX.toFixed(2) + 'deg) rotateY(' + rotateY.toFixed(2) + 'deg)';
        });
        heroSection.addEventListener('mouseleave', function () {
            heroTilt.style.transform = 'rotateX(0deg) rotateY(0deg)';
        });
    }

    /* Reveal on scroll */
    var reveals = document.querySelectorAll('.reveal');
    function reveal() {
        var windowHeight = window.innerHeight;
        reveals.forEach(function (el) {
            var top = el.getBoundingClientRect().top;
            if (top < windowHeight - 120) {
                el.classList.add('active');
            }
        });
    }
    window.addEventListener('scroll', reveal);
    reveal();

    /* Animated stat counters */
    var counters = document.querySelectorAll('.stat-num');
    var countersStarted = false;
    function animateCounters() {
        if (countersStarted) return;
        var heroStats = document.querySelector('.hero-stats');
        if (!heroStats) return;
        var top = heroStats.getBoundingClientRect().top;
        if (top < window.innerHeight - 80) {
            countersStarted = true;
            counters.forEach(function (counter) {
                var target = parseInt(counter.getAttribute('data-count'), 10);
                var current = 0;
                var step = Math.max(1, Math.ceil(target / 40));
                var timer = setInterval(function () {
                    current += step;
                    if (current >= target) {
                        current = target;
                        clearInterval(timer);
                    }
                    counter.textContent = current;
                }, 30);
            });
        }
    }
    window.addEventListener('scroll', animateCounters);
    animateCounters();

    /* Project filter */
    var filterBtns = document.querySelectorAll('.filter-btn');
    var projectItems = document.querySelectorAll('.project-item');
    filterBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            filterBtns.forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            var filter = btn.getAttribute('data-filter');
            projectItems.forEach(function (item) {
                var match = filter === 'all' || item.getAttribute('data-category') === filter;
                item.style.display = match ? '' : 'none';
                if (match) {
                    item.querySelector('.project-card').classList.add('active');
                    reveal();
                }
            });
        });
    });

    /* Theme toggle (dark mode) */
    var themeToggle = document.getElementById('themeToggle');
    var themeIcon = themeToggle ? themeToggle.querySelector('i') : null;
    var storedTheme = localStorage.getItem('theme');
    if (storedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        if (themeIcon) { themeIcon.classList.remove('fa-moon'); themeIcon.classList.add('fa-sun'); }
    }
    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            document.body.classList.toggle('dark-mode');
            var isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            if (themeIcon) {
                themeIcon.classList.toggle('fa-moon', !isDark);
                themeIcon.classList.toggle('fa-sun', isDark);
            }
        });
    }

    /* Close mobile nav on link click */
    var navLinks = document.querySelectorAll('.nav-link');
    var navbarCollapse = document.getElementById('navbarNav');
    navLinks.forEach(function (link) {
        link.addEventListener('click', function () {
            if (navbarCollapse.classList.contains('show')) {
                new bootstrap.Collapse(navbarCollapse).hide();
            }
        });
    });

    /* Highlight active nav link on scroll */
    var sections = document.querySelectorAll('section[id]');
    function setActiveNav() {
        var scrollPos = window.scrollY + 150;
        sections.forEach(function (section) {
            var top = section.offsetTop;
            var height = section.offsetHeight;
            var id = section.getAttribute('id');
            var link = document.querySelector('.nav-link[href="#' + id + '"]');
            if (link) {
                if (scrollPos >= top && scrollPos < top + height) {
                    document.querySelectorAll('.nav-link').forEach(function (l) { l.classList.remove('active'); });
                    link.classList.add('active');
                }
            }
        });
    }
    window.addEventListener('scroll', setActiveNav);
    setActiveNav();

    /* Lead capture form */
    var leadForm = document.getElementById('leadForm');
    if (leadForm) {
        var leadStatus = document.getElementById('leadFormStatus');
        var leadSubmit = document.getElementById('leadFormSubmit');

        leadForm.addEventListener('submit', function (e) {
            e.preventDefault();

            if (!leadForm.checkValidity()) {
                leadForm.reportValidity();
                return;
            }

            // Honeypot: real visitors never fill this hidden field.
            var honeypot = leadForm.querySelector('[name="website"]');
            if (honeypot && honeypot.value) {
                leadStatus.className = 'lead-form-status success';
                leadStatus.textContent = "Thanks! I'll be in touch soon.";
                leadForm.reset();
                return;
            }

            if (!LEADS_ENDPOINT) {
                leadStatus.className = 'lead-form-status error';
                leadStatus.textContent = "This form isn't connected yet — please email aminullah112@gmail.com directly for now.";
                console.warn('LEADS_ENDPOINT is not set in js/main.js — see README "Lead Capture Backend Setup".');
                return;
            }

            leadStatus.className = 'lead-form-status sending';
            leadStatus.textContent = 'Sending…';
            leadSubmit.disabled = true;

            var formData = new FormData(leadForm);
            fetch(LEADS_ENDPOINT, { method: 'POST', mode: 'no-cors', body: formData })
                .then(function () {
                    leadStatus.className = 'lead-form-status success';
                    leadStatus.textContent = "Thanks! I've got your details and will follow up soon.";
                    leadForm.reset();
                })
                .catch(function () {
                    leadStatus.className = 'lead-form-status error';
                    leadStatus.textContent = 'Something went wrong — please email aminullah112@gmail.com directly.';
                })
                .finally(function () {
                    leadSubmit.disabled = false;
                });
        });
    }
});
