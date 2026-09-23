// Lightweight decorative WebGL layer for the hero: a slowly rotating
// "blueprint" node network (points + connecting lines). Hand-written,
// no dependency — pulling in a full 3D library for one ambient effect
// isn't worth the payload. Fails silently: any error, missing WebGL,
// reduced-motion, a saved-data connection, or a small viewport just
// leaves the hero photo as the complete visual.

(function () {
  var canvas = document.getElementById('heroScene');
  var hero = document.querySelector('.hero');
  if (!canvas || !hero) return;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (window.innerWidth < 640) return;
  if (navigator.connection && navigator.connection.saveData) return;

  var gl = canvas.getContext('webgl', { alpha: true, antialias: true, premultipliedAlpha: false })
    || canvas.getContext('experimental-webgl', { alpha: true, antialias: true });
  if (!gl) return;

  try {
    run();
  } catch (err) {
    // Leave the canvas blank — hero photo already carries the section.
  }

  function run() {
    var vsPoints = compileShader(gl.VERTEX_SHADER,
      'attribute vec3 aPosition;' +
      'attribute float aSize;' +
      'uniform mat4 uMVP;' +
      'varying float vW;' +
      'void main() {' +
      '  vec4 pos = uMVP * vec4(aPosition, 1.0);' +
      '  gl_Position = pos;' +
      '  gl_PointSize = aSize * (14.0 / pos.w);' +
      '  vW = pos.w;' +
      '}'
    );
    var fsPoints = compileShader(gl.FRAGMENT_SHADER,
      'precision mediump float;' +
      'uniform vec3 uColor;' +
      'uniform float uAlpha;' +
      'varying float vW;' +
      'void main() {' +
      '  vec2 c = gl_PointCoord - vec2(0.5);' +
      '  float d = length(c);' +
      '  if (d > 0.5) discard;' +
      '  float edge = smoothstep(0.5, 0.05, d);' +
      '  float fog = clamp(1.4 - (vW - 3.0) / 7.0, 0.3, 1.0);' +
      '  gl_FragColor = vec4(uColor, edge * fog * uAlpha);' +
      '}'
    );
    var vsLines = compileShader(gl.VERTEX_SHADER,
      'attribute vec3 aPosition;' +
      'uniform mat4 uMVP;' +
      'void main() { gl_Position = uMVP * vec4(aPosition, 1.0); }'
    );
    var fsLines = compileShader(gl.FRAGMENT_SHADER,
      'precision mediump float;' +
      'uniform vec4 uColor;' +
      'void main() { gl_FragColor = uColor; }'
    );

    var pointProgram = linkProgram(vsPoints, fsPoints);
    var lineProgram = linkProgram(vsLines, fsLines);
    if (!pointProgram || !lineProgram) return;

    // --- Node network geometry (deterministic-ish, decorative only) ---
    var COUNT = 46;
    var positions = new Float32Array(COUNT * 3);
    var sizes = new Float32Array(COUNT);
    var seed = 42;
    function rand() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }

    for (var i = 0; i < COUNT; i++) {
      positions[i * 3] = (rand() * 2 - 1) * 2.7;
      positions[i * 3 + 1] = (rand() * 2 - 1) * 1.5;
      positions[i * 3 + 2] = (rand() * 2 - 1) * 1.3;
      sizes[i] = 2.5 + rand() * 4;
    }

    var linePositions = [];
    var maxEdges = 70;
    for (var a = 0; a < COUNT && linePositions.length / 6 < maxEdges; a++) {
      for (var b = a + 1; b < COUNT && linePositions.length / 6 < maxEdges; b++) {
        var dx = positions[a * 3] - positions[b * 3];
        var dy = positions[a * 3 + 1] - positions[b * 3 + 1];
        var dz = positions[a * 3 + 2] - positions[b * 3 + 2];
        var dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < 1.05) {
          linePositions.push(
            positions[a * 3], positions[a * 3 + 1], positions[a * 3 + 2],
            positions[b * 3], positions[b * 3 + 1], positions[b * 3 + 2]
          );
        }
      }
    }
    var linePositionsArr = new Float32Array(linePositions);

    var pointBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, pointBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    var sizeBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, sizeBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, sizes, gl.STATIC_DRAW);

    var lineBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, linePositionsArr, gl.STATIC_DRAW);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.disable(gl.DEPTH_TEST);

    var pointLoc = {
      position: gl.getAttribLocation(pointProgram, 'aPosition'),
      size: gl.getAttribLocation(pointProgram, 'aSize'),
      mvp: gl.getUniformLocation(pointProgram, 'uMVP'),
      color: gl.getUniformLocation(pointProgram, 'uColor'),
      alpha: gl.getUniformLocation(pointProgram, 'uAlpha')
    };
    var lineLoc = {
      position: gl.getAttribLocation(lineProgram, 'aPosition'),
      mvp: gl.getUniformLocation(lineProgram, 'uMVP'),
      color: gl.getUniformLocation(lineProgram, 'uColor')
    };

    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    function resize() {
      var w = hero.clientWidth, h = hero.clientHeight;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      gl.viewport(0, 0, canvas.width, canvas.height);
    }
    resize();
    if ('ResizeObserver' in window) {
      new ResizeObserver(resize).observe(hero);
    } else {
      window.addEventListener('resize', resize);
    }

    var mouseX = 0, mouseY = 0;
    var reduceParallax = !window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    if (!reduceParallax) {
      hero.addEventListener('mousemove', function (e) {
        var rect = hero.getBoundingClientRect();
        mouseX = (e.clientX - rect.left) / rect.width - 0.5;
        mouseY = (e.clientY - rect.top) / rect.height - 0.5;
      });
    }

    var running = true;
    var rafId = null;
    var start = performance.now();

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        running = entry.isIntersecting;
        if (running) tick(performance.now());
        else if (rafId) cancelAnimationFrame(rafId);
      });
    }, { threshold: 0.01 });
    io.observe(hero);

    document.addEventListener('visibilitychange', function () {
      running = !document.hidden && isInViewport(hero);
      if (running) tick(performance.now());
      else if (rafId) cancelAnimationFrame(rafId);
    });

    function isInViewport(el) {
      var r = el.getBoundingClientRect();
      return r.bottom > 0 && r.top < window.innerHeight;
    }

    function tick(now) {
      if (!running) return;
      rafId = requestAnimationFrame(tick);
      render(now);
    }

    var readyFired = false;
    function render(now) {
      var t = (now - start) / 1000;
      var aspect = canvas.width / canvas.height;
      var proj = mat4Perspective(0.6, aspect, 0.1, 20);
      var view = mat4Translate(0, 0, -6.4);
      var model = mat4Multiply(
        mat4RotateY(t * 0.06 + mouseX * 0.6),
        mat4RotateX(0.18 + mouseY * 0.35)
      );
      var mvp = mat4Multiply(proj, mat4Multiply(view, model));

      gl.clear(gl.COLOR_BUFFER_BIT);

      // Lines
      gl.useProgram(lineProgram);
      gl.uniformMatrix4fv(lineLoc.mvp, false, mvp);
      gl.uniform4f(lineLoc.color, 0.051, 0.231, 0.180, 0.22);
      gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
      gl.enableVertexAttribArray(lineLoc.position);
      gl.vertexAttribPointer(lineLoc.position, 3, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.LINES, 0, linePositionsArr.length / 3);

      // Points
      gl.useProgram(pointProgram);
      gl.uniformMatrix4fv(pointLoc.mvp, false, mvp);
      gl.uniform3f(pointLoc.color, 0.91, 0.702, 0.353);
      gl.uniform1f(pointLoc.alpha, 0.6);
      gl.bindBuffer(gl.ARRAY_BUFFER, pointBuffer);
      gl.enableVertexAttribArray(pointLoc.position);
      gl.vertexAttribPointer(pointLoc.position, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, sizeBuffer);
      gl.enableVertexAttribArray(pointLoc.size);
      gl.vertexAttribPointer(pointLoc.size, 1, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.POINTS, 0, COUNT);

      if (!readyFired) {
        readyFired = true;
        canvas.classList.add('is-ready');
      }
    }

    tick(performance.now());
  }

  function compileShader(type, src) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function linkProgram(vs, fs) {
    if (!vs || !fs) return null;
    var program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteProgram(program);
      return null;
    }
    return program;
  }

  // --- Minimal column-major mat4 helpers (no library) ---
  function mat4Identity() { return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]); }
  function mat4Multiply(a, b) {
    var out = new Float32Array(16);
    for (var i = 0; i < 4; i++) {
      for (var j = 0; j < 4; j++) {
        var sum = 0;
        for (var k = 0; k < 4; k++) sum += a[k * 4 + j] * b[i * 4 + k];
        out[i * 4 + j] = sum;
      }
    }
    return out;
  }
  function mat4Perspective(fovy, aspect, near, far) {
    var f = 1 / Math.tan(fovy / 2);
    var nf = 1 / (near - far);
    var out = new Float32Array(16);
    out[0] = f / aspect; out[5] = f; out[10] = (far + near) * nf;
    out[11] = -1; out[14] = 2 * far * near * nf;
    return out;
  }
  function mat4RotateY(a) {
    var c = Math.cos(a), s = Math.sin(a);
    return new Float32Array([c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]);
  }
  function mat4RotateX(a) {
    var c = Math.cos(a), s = Math.sin(a);
    return new Float32Array([1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1]);
  }
  function mat4Translate(x, y, z) {
    var m = mat4Identity(); m[12] = x; m[13] = y; m[14] = z; return m;
  }
})();
