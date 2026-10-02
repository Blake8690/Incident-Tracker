// Hero: Sverige som lutad 3D-punktkarta i natten. Fjällen reser sig i väster,
// städerna lyser och guldpulser visar där det bor folk. Dekorativt — inga
// riktiga händelser visas här.
(() => {
  const canvas = document.getElementById("sweden");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const hero = canvas.closest(".hero");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Förenklad konturlinje [lon, lat], medurs från Smygehuk
  const FASTLAND = [
    [13.36,55.34],[12.98,55.40],[12.85,55.58],[12.92,55.75],[12.70,56.05],[12.50,56.30],[12.85,56.45],
    [12.85,56.65],[12.60,56.85],[12.25,57.10],[11.95,57.40],[11.80,57.70],[11.70,58.00],[11.45,58.25],
    [11.25,58.55],[11.15,58.95],[11.45,59.10],[11.80,59.40],[11.85,59.85],[12.40,60.00],[12.55,60.40],
    [12.30,60.90],[12.65,61.10],[12.85,61.35],[12.30,61.65],[12.15,61.95],[12.30,62.30],[12.05,62.60],
    [12.20,63.00],[12.00,63.30],[12.65,63.90],[13.70,64.10],[14.10,64.45],[13.70,64.60],[14.35,65.10],
    [14.50,65.70],[15.10,66.10],[15.45,66.30],[16.05,66.90],[16.40,67.20],[16.75,67.90],[17.35,68.05],
    [18.10,68.45],[18.60,68.40],[19.95,68.35],[20.20,68.55],[20.35,68.85],[20.55,69.06],[21.40,68.45],
    [22.35,68.45],[23.05,68.30],[23.65,67.95],[23.50,67.45],[23.75,67.15],[23.65,66.80],[23.90,66.45],
    [23.95,66.15],[24.15,65.82],[23.10,65.75],[22.60,65.70],[22.15,65.55],[21.70,65.35],[21.45,65.10],
    [21.30,64.80],[21.10,64.60],[20.90,64.40],[20.60,64.10],[20.20,63.80],[19.70,63.55],[19.30,63.40],
    [18.80,63.20],[18.50,63.00],[18.15,62.75],[17.95,62.55],[17.50,62.35],[17.40,62.05],[17.25,61.80],
    [17.15,61.55],[17.20,61.20],[17.20,60.90],[17.30,60.65],[17.70,60.55],[18.25,60.40],[18.60,60.25],
    [18.85,59.95],[19.05,59.75],[18.95,59.50],[18.70,59.30],[18.40,59.10],[18.05,58.90],[17.70,58.80],
    [17.20,58.70],[16.85,58.55],[16.75,58.25],[16.70,57.90],[16.60,57.60],[16.55,57.30],[16.45,57.00],
    [16.40,56.70],[16.20,56.40],[15.90,56.15],[15.50,56.15],[15.00,56.17],[14.70,56.05],[14.35,55.95],
    [14.20,55.70],[14.35,55.55],[14.10,55.40],[13.80,55.42],
  ];
  const GOTLAND = [[18.10,56.92],[18.30,57.10],[18.75,57.25],[18.85,57.45],[18.95,57.70],[19.10,57.85],
    [19.30,57.97],[19.00,57.98],[18.75,57.85],[18.45,57.75],[18.20,57.55],[18.15,57.30]];
  const OLAND = [[16.40,56.20],[16.60,56.35],[16.85,56.75],[17.05,57.10],[17.10,57.35],[16.95,57.30],
    [16.70,56.95],[16.45,56.55],[16.38,56.30]];
  // Fjällkedjan följer norska gränsen
  const FJALL = FASTLAND.slice(16, 48);

  const STADER = [
    [18.07,59.33,10],[11.97,57.71,6],[13.00,55.60,5],[17.64,59.86,3],[16.55,59.61,2],[15.21,59.27,2],
    [15.62,58.41,2],[12.69,56.05,2],[14.16,57.78,2],[16.18,58.59,2],[13.19,55.70,2],[20.26,63.83,2],
    [17.14,60.67,1.5],[12.94,57.72,1.5],[16.51,59.37,1.2],[17.63,59.20,1.2],[13.50,59.38,1.2],
    [14.81,56.88,1.2],[12.86,56.67,1.2],[17.31,62.39,1.2],[22.15,65.58,1.2],[14.64,63.18,1],
    [20.22,67.86,.6],[16.36,56.66,1],[18.29,57.64,.6],[15.63,60.61,1],[20.95,64.75,.8],[12.29,58.28,.8],
    [14.16,56.03,.8],[15.59,56.16,.8],
  ];

  const LON0 = 16.6, LAT0 = 62.2;
  const proj = ([lon, lat]) => [(lon - LON0) * Math.cos(lat * Math.PI / 180), lat - LAT0];
  const polys = [FASTLAND, GOTLAND, OLAND].map(p => p.map(proj));
  const fjall = FJALL.map(proj);
  // Vänern och Vättern som ellipser [cx, cy, rx, ry]
  const SJOAR = [[13.25, 58.95, 0.42, 0.33], [14.55, 58.35, 0.09, 0.52]].map(([lon, lat, rx, ry]) => {
    const [x, y] = proj([lon, lat]);
    return [x, y, rx, ry];
  });

  const inside = (x, y, poly) => {
    let hit = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
    }
    return hit;
  };
  const distToLine = (x, y, line) => {
    let best = Infinity;
    for (let i = 0; i < line.length - 1; i++) {
      const [ax, ay] = line[i], [bx, by] = line[i + 1];
      const dx = bx - ax, dy = by - ay;
      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)));
      best = Math.min(best, Math.hypot(x - ax - t * dx, y - ay - t * dy));
    }
    return best;
  };
  const smooth = (a, b, v) => { const t = Math.max(0, Math.min(1, (v - a) / (b - a))); return t * t * (3 - 2 * t); };

  // Punkter på ett jämnt rutnät inom konturen
  const STEP = 0.12;
  const points = [];
  for (let y = -7.0; y <= 7.0; y += STEP) {
    for (let x = -3.4; x <= 3.6; x += STEP) {
      if (!polys.some(p => inside(x, y, p))) continue;
      if (SJOAR.some(([cx, cy, rx, ry]) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1)) continue;
      const lat = y + LAT0;
      const d = distToLine(x, y, fjall);
      const z = 0.75 * Math.exp(-((d / 0.55) ** 2)) * smooth(60.3, 63.5, lat)
        + 0.04 * Math.sin(x * 7.1 + y * 3.3) * Math.cos(y * 5.7);
      points.push([x, y, Math.max(0, z)]);
    }
  }
  const stader = STADER.map(([lon, lat, w]) => [...proj([lon, lat]), w]);
  const totalW = stader.reduce((s, c) => s + c[2], 0);
  const stars = Array.from({ length: 140 }, () => [Math.random(), Math.random() * 0.55, Math.random() * 1.2 + 0.2, Math.random() * 6]);

  let W, H, dpr, mx = 0, my = 0, tx = 0, ty = 0, running = false;
  const pulses = [];
  let nextPulse = 0;

  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = hero.clientWidth; H = hero.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!running) draw(performance.now());
  }

  function pickCity() {
    let r = Math.random() * totalW;
    for (const c of stader) { if ((r -= c[2]) <= 0) return c; }
    return stader[0];
  }

  function draw(now) {
    tx += (mx - tx) * 0.04; ty += (my - ty) * 0.04;
    const hp = Math.min(scrollY / H, 1);
    const mobile = W < 820;

    const yaw = -0.2 + tx * 0.3 + (reduced ? 0 : Math.sin(now * 0.00012) * 0.05);
    const pitch = 0.82 + ty * 0.1 + hp * 0.3;
    const ca = Math.cos(yaw), sa = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const F = 22;
    const scale = mobile ? Math.min(W * 0.13, H * 0.06) : Math.min(H * 0.07, W * 0.05);
    const cx = mobile ? W * 0.6 : W * 0.77;
    const cy = mobile ? H * 0.6 : H * 0.53 + hp * H * 0.1;
    const fade = 1 - hp * 0.7;

    const project = (x, y, z) => {
      const x1 = x * ca - y * sa, y1 = x * sa + y * ca;
      const vert = y1 * cp + z * sp, depth = y1 * sp - z * cp;
      const k = F / (F + depth);
      return [cx + x1 * scale * k, cy - vert * scale * k, depth, k];
    };

    ctx.clearRect(0, 0, W, H);

    // Stjärnor
    for (const [sx, sy, r, ph] of stars) {
      ctx.globalAlpha = (0.25 + 0.35 * Math.sin(now * 0.001 + ph) ** 2) * fade;
      ctx.fillStyle = "#e8e8e8";
      ctx.fillRect(sx * W, sy * H, r, r);
    }

    // Kartan
    for (const [x, y, z] of points) {
      const [px, py, depth, k] = project(x, y, z);
      const near = Math.max(0, Math.min(1, (6 - depth) / 12));
      ctx.globalAlpha = (0.3 + near * 0.5 + z * 0.4) * fade;
      ctx.fillStyle = z > 0.25 ? "#f1efe8" : "#7a7a7a";
      const s = (1.3 + z * 1.4) * k * (mobile ? 1 : 1.25);
      ctx.fillRect(px - s / 2, py - s / 2, s, s);
    }

    // Stadsljus
    for (const [x, y, w] of stader) {
      const [px, py, , k] = project(x, y, 0.02);
      const r = (3 + w * 1.2) * k;
      const g = ctx.createRadialGradient(px, py, 0, px, py, r);
      g.addColorStop(0, "rgba(255, 255, 255, 0.7)");
      g.addColorStop(1, "rgba(255, 255, 255, 0)");
      ctx.globalAlpha = 0.55 * fade;
      ctx.fillStyle = g;
      ctx.fillRect(px - r, py - r, r * 2, r * 2);
    }

    // Blåljus
    if (!reduced && now > nextPulse) {
      const [x, y] = pickCity();
      pulses.push({ x: x + (Math.random() - 0.5) * 0.15, y: y + (Math.random() - 0.5) * 0.15, t0: now });
      nextPulse = now + 500 + Math.random() * 900;
    }
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      const t = (now - p.t0) / 2600;
      if (t > 1) { pulses.splice(i, 1); continue; }
      const a = (1 - t) * fade;
      // Ring på marken
      ctx.globalAlpha = a * 0.9;
      ctx.strokeStyle = "#e3b23c";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      const R = 0.08 + t * 0.55;
      for (let s = 0; s <= 28; s++) {
        const ang = (s / 28) * Math.PI * 2;
        const [qx, qy] = project(p.x + Math.cos(ang) * R, p.y + Math.sin(ang) * R, 0.02);
        s ? ctx.lineTo(qx, qy) : ctx.moveTo(qx, qy);
      }
      ctx.stroke();
      // Ljuspelare
      const [bx, by] = project(p.x, p.y, 0);
      const [, ty2] = project(p.x, p.y, 0.9 * (1 - t * 0.4));
      const beam = ctx.createLinearGradient(bx, by, bx, ty2);
      beam.addColorStop(0, "rgba(242, 205, 107, 0.95)");
      beam.addColorStop(1, "rgba(242, 205, 107, 0)");
      ctx.globalAlpha = a;
      ctx.strokeStyle = beam;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx, ty2); ctx.stroke();
      // Kärna
      const glow = ctx.createRadialGradient(bx, by, 0, bx, by, 14);
      glow.addColorStop(0, "rgba(255, 236, 180, 1)");
      glow.addColorStop(1, "rgba(227, 178, 60, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(bx - 14, by - 14, 28, 28);
    }
    ctx.globalAlpha = 1;
  }

  function loop(now) {
    if (!running) return;
    draw(now);
    requestAnimationFrame(loop);
  }

  addEventListener("mousemove", e => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; });
  addEventListener("resize", resize);
  resize();

  if (reduced) {
    addEventListener("scroll", () => draw(0), { passive: true });
  } else {
    // Rita bara när hero syns, sparar batteri
    new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !running) { running = true; requestAnimationFrame(loop); }
      else if (!e.isIntersecting) running = false;
    }).observe(hero);
  }
})();
