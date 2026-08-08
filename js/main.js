// Aminullah portfolio — interactivity

document.addEventListener('DOMContentLoaded', function () {

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
});
