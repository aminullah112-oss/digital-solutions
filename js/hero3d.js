// Hero 3D background — a small animated wireframe rendered with Three.js.
// Fails silently at every step: no THREE global (CDN blocked/offline), no WebGL,
// or reduced-motion preference, and the hero just keeps its flat gradient background.
(function () {
    if (typeof THREE === 'undefined') return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var canvas = document.getElementById('hero3d');
    var heroSection = canvas ? canvas.closest('.hero') : null;
    if (!canvas || !heroSection) return;

    var renderer;
    try {
        renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
    } catch (e) {
        return; // WebGL unsupported/blocked — leave the plain hero background as-is
    }

    var isMobile = window.innerWidth < 768;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2));

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.z = 9;

    var group = new THREE.Group();
    scene.add(group);

    // Two nested wireframe icosahedra — a low-poly "circuit core" centerpiece
    var core = new THREE.Mesh(
        new THREE.IcosahedronGeometry(2.6, 1),
        new THREE.MeshBasicMaterial({ color: 0x0ea5a4, wireframe: true, transparent: true, opacity: 0.55 })
    );
    group.add(core);

    var shell = new THREE.Mesh(
        new THREE.IcosahedronGeometry(3.4, 0),
        new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.18 })
    );
    group.add(shell);

    // Scattered points around it — a sparse "node field"
    var pointCount = isMobile ? 60 : 140;
    var positions = new Float32Array(pointCount * 3);
    for (var i = 0; i < pointCount; i++) {
        var radius = 4.5 + Math.random() * 3.5;
        var theta = Math.random() * Math.PI * 2;
        var phi = Math.acos((Math.random() * 2) - 1);
        positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = radius * Math.cos(phi);
    }
    var pointsGeo = new THREE.BufferGeometry();
    pointsGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    var points = new THREE.Points(pointsGeo, new THREE.PointsMaterial({
        color: 0x38bdf8, size: 0.045, transparent: true, opacity: 0.6
    }));
    group.add(points);

    function resize() {
        var w = heroSection.clientWidth;
        var h = heroSection.clientHeight;
        if (!w || !h) return;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }
    resize();
    window.addEventListener('resize', resize);

    var running = false;
    var lastTime = 0;

    function animate(time) {
        if (!running) return;
        requestAnimationFrame(animate);
        var delta = Math.min((time - lastTime) / 1000, 0.1);
        lastTime = time;
        group.rotation.y += delta * 0.12;
        group.rotation.x += delta * 0.04;
        points.rotation.y -= delta * 0.05;
        renderer.render(scene, camera);
    }

    function start() {
        if (running) return;
        running = true;
        lastTime = performance.now();
        requestAnimationFrame(animate);
    }
    function stop() {
        running = false;
    }

    // Only spend GPU/battery on this while the hero is actually on screen and the tab is active.
    if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting && document.visibilityState === 'visible') start();
                else stop();
            });
        }, { threshold: 0.05 });
        observer.observe(heroSection);
    } else {
        start();
    }
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') stop();
        else if (heroSection.getBoundingClientRect().top < window.innerHeight) start();
    });
})();
