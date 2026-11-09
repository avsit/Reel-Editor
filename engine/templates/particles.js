/* Reel Studio particle scenes. One cloud of dots per scene, drawn as a pure function of reel time t, so every frame is
   deterministic and seek-safe. Morphs sweep left to right (particles matched by x order), never a random scramble.
   Colours come from window.BRAND (the brand file). Each scene takes its cue times from the edit:
       driver("answer_bubble", a, b, {"light": wt("ad", 1.2), "label": "AD"})
   and draws into <canvas id="cv-<scene>">. Add a scene by writing a function (t, cue) and registering it in PART. */
(function () {
  const B = window.BRAND || {};
  const BONE = B.text || '#EFEADF', LIME = B.accent || '#E5FF1F', NIGHT = B.ground || '#0E1110', MUTED = B.muted || '#8A8F86';
  const DIM = MUTED;
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647; const reseed = s => { seed = s; };
  const P = (x, y, l = 0) => ({ x, y, l });
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = m => m < .5 ? 4 * m * m * m : 1 - Math.pow(-2 * m + 2, 3) / 2;
  const disc = (cx, cy, r, n, l = 0) => Array.from({ length: n }, () => { const a = rnd() * 6.283, d = Math.sqrt(rnd()) * r; return P(cx + Math.cos(a) * d, cy + Math.sin(a) * d, l); });
  const ring = (cx, cy, r, n, w = 6, l = 0) => Array.from({ length: n }, () => { const a = rnd() * 6.283, d = r + (rnd() - .5) * w; return P(cx + Math.cos(a) * d, cy + Math.sin(a) * d, l); });
  const seg = (x0, y0, x1, y1, n, w = 5, l = 0) => Array.from({ length: n }, () => { const t = rnd(); return P(x0 + (x1 - x0) * t + (rnd() - .5) * w, y0 + (y1 - y0) * t + (rnd() - .5) * w, l); });
  const fill = (x, y, w, h, n, l = 0) => Array.from({ length: n }, () => P(x + rnd() * w, y + rnd() * h, l));
  function rrect(x, y, w, h, r, n, l = 0, jit = 5) {
    const out = [], e = [w - 2 * r, Math.PI * r / 2, h - 2 * r, Math.PI * r / 2, w - 2 * r, Math.PI * r / 2, h - 2 * r, Math.PI * r / 2];
    const per = e.reduce((a, b) => a + b, 0), c = [[x + w - r, y + r], [x + w - r, y + h - r], [x + r, y + h - r], [x + r, y + r]];
    for (let i = 0; i < n; i++) { let s = rnd() * per, k = 0, px, py; while (s > e[k]) { s -= e[k]; k++; }
      if (k === 0) { px = x + r + s; py = y; } else if (k === 2) { px = x + w; py = y + r + s; } else if (k === 4) { px = x + w - r - s; py = y + h; } else if (k === 6) { px = x; py = y + h - r - s; }
      else { const q = (k - 1) / 2, a = -Math.PI / 2 + q * Math.PI / 2 + s / r; px = c[q][0] + Math.cos(a) * r; py = c[q][1] + Math.sin(a) * r; }
      out.push(P(px + (rnd() - .5) * jit, py + (rnd() - .5) * jit, l)); }
    return out;
  }
  const lines = (x, y, ws, gap, nper, l = 0) => ws.flatMap((w, i) => seg(x, y + i * gap, x + w, y + i * gap, Math.round(nper * w / 700), 7, l));
  const bubble = (x, y, w, h, n, l = 0) => [...rrect(x, y, w, h, 64, Math.round(n * .86), l), ...seg(x + 110, y + h, x + 60, y + h + 100, Math.round(n * .07), 6, l), ...seg(x + 60, y + h + 100, x + 210, y + h, n - Math.round(n * .86) - Math.round(n * .07), 6, l)];
  const byX = a => [...a].sort((p, q) => p.x - q.x);
  const PH = n => { reseed(99); return Array.from({ length: n }, () => ({ ph: rnd() * 6.283, r: 2.9 + rnd() * 1.1 })); };
  function dot(c, x, y, r, col, a) { c.globalAlpha = a; c.fillStyle = col; c.beginPath(); c.arc(x, y, r, 0, 6.283); c.fill(); }
  const ctx = id => { const el = document.getElementById(id); return el ? el.getContext('2d') : null; };
  const wob = (t, ph, amp = 1.3) => [Math.sin(t * 1.3 + ph) * amp, Math.cos(t * 1.1 + ph) * amp];

  // ── answer_bubble: an answer bubble assembles from dust (start..start+1.1 s); its slot lights in the accent at cue.light ──
  reseed(11);
  const AB = [...bubble(150, 860, 780, 380, 760), ...lines(230, 950, [560, 620, 470], 58, 110), ...fill(230, 1135, 430, 76, 380, 1)];
  const ABph = PH(AB.length);
  const ABslot = byX(AB.filter(p => p.l === 1)); ABslot.forEach((p, i) => { p.k = i / ABslot.length; });
  const ABd = byX(fill(110, 820, 860, 560, AB.length)), ABs = byX(AB.map((p, i) => ({ ...p, i })));
  function answer_bubble(t, cue = {}) {
    const c = ctx('cv-answer_bubble'); if (!c) return; c.clearRect(0, 0, 1080, 1920);
    const t0 = cue.start || 0, g = (t - (cue.light ?? t0 + 1.2)) / 0.45, ga = (t - t0) / 1.1;
    ABs.forEach((p, j) => { const d = ABd[j], m = ease(clamp((ga - 0.5 * (j / ABs.length)) / 0.5));
      const ph = ABph[p.i], [dx, dy] = wob(t, ph.ph, m > .9 ? 1.1 : 2.4);
      const x = d.x + (p.x - d.x) * m + dx, y = d.y + (p.y - d.y) * m + dy;
      if (p.l === 1) { const on = clamp((g - p.k) / 0.25); dot(c, x, y, ph.r * (1 + .25 * on), on > .5 ? LIME : DIM, on > .5 ? .95 : .25 + .35 * m); }
      else dot(c, x, y, ph.r, BONE, .4 + .42 * m); });
    if (cue.label) { c.globalAlpha = clamp((t - t0 - 1.0) / 0.3); c.font = `500 24px "${(B.labelFont || 'monospace')}"`; c.fillStyle = MUTED; c.fillText(cue.label, 690, 1183); c.globalAlpha = 1; }
  }

  // ── two_into_one: dust -> icon A (cue.a) + icon B (cue.b) -> dimmed (cue.dim) -> sweep into one bubble (cue.morph)
  //    -> accent core (cue.core). Icons: a search loupe and a 3x3 feed grid by default ──
  reseed(21);
  const IA = [...ring(300, 700, 140, 520, 9), ...seg(400, 800, 520, 920, 200, 10)].map(p => ({ ...p, grp: 0 }));
  const IB = [0, 1, 2].flatMap(r => [0, 1, 2].flatMap(q => rrect(610 + q * 96, 580 + r * 96, 76, 76, 10, 40, 0, 3))).map(p => ({ ...p, grp: 1 }));
  const A1 = byX([...IA, ...IB]); const N1 = A1.length;
  const B1 = byX([...bubble(150, 470, 780, 470, N1 - 230), ...disc(540, 705, 76, 230, 1)]);
  const D1 = byX(fill(110, 430, 860, 620, N1));
  [0, 1].forEach(g => { const m = A1.filter(p => p.grp === g); m.forEach((p, i) => { p.k = i / m.length; }); });
  const PH1 = PH(N1);
  function two_into_one(t, cue = {}) {
    const c = ctx('cv-two_into_one'); if (!c) return; c.clearRect(0, 0, 1080, 1920);
    const gm = (t - cue.morph) / 0.9, dim = clamp((t - cue.dim) / 0.3);
    for (let i = 0; i < N1; i++) {
      const a = A1[i], b = B1[i], d = D1[i], start = a.grp === 0 ? cue.a : cue.b;
      const fm = ease(clamp(((t - start) / (a.grp === 0 ? 0.3 : 0.6) - 0.5 * a.k) / 0.5));
      let x = d.x + (a.x - d.x) * fm, y = d.y + (a.y - d.y) * fm;
      const mm = ease(clamp((gm - 0.5 * (i / N1)) / 0.5));
      x += (b.x - x) * mm; y += (b.y - y) * mm;
      const [dx, dy] = wob(t, PH1[i].ph, fm > .9 ? 1.1 : 2.4);
      let col = BONE, al = .18 + .64 * fm;
      if (fm > .5 && mm < .5) { al = .82 - .4 * dim; }
      if (mm >= .5) { col = BONE; al = .82; if (b.l === 1 && t >= cue.core) { col = LIME; al = .95; } }
      dot(c, x + dx, y + dy, PH1[i].r * (col === LIME ? 1.25 : 1), col, al);
    }
    c.globalAlpha = 1;
  }

  // ── field_to_stream (light ground): a scattered field gathers into one stream (from cue.start); its head lights at cue.head ──
  reseed(51);
  const S2 = byX(Array.from({ length: 1200 }, (_, i) => { const u = i / 1200, x = 90 + u * 900, sp = Math.pow(1 - u, 1.6) * 300 + 10;
    return P(x + (rnd() - .5) * 20, 640 + (rnd() - .5) * 2 * sp + Math.sin(u * 5) * 28 * (1 - u), u > .9 ? 1 : 0); }));
  const D2 = byX(fill(90, 260, 900, 760, S2.length)); const PH2 = PH(S2.length);
  function field_to_stream(t, cue = {}) {
    const c = ctx('cv-field_to_stream'); if (!c) return; c.clearRect(0, 0, 1080, 1920);
    const g = (t - cue.start) / 0.7;
    for (let i = 0; i < S2.length; i++) {
      const s = S2[i], d = D2[i], m = ease(clamp((g - 0.5 * (i / S2.length)) / 0.5));
      const [dx, dy] = wob(t, PH2[i].ph, m > .9 ? 1.0 : 2.2);
      const x = d.x + (s.x - d.x) * m, y = d.y + (s.y - d.y) * m, lit = s.l === 1 && t >= cue.head && m > .8;
      if (lit) { dot(c, x + dx, y + dy, PH2[i].r * 1.35 + 1, NIGHT, .9); dot(c, x + dx, y + dy, PH2[i].r * 1.35, LIME, 1); }
      else dot(c, x + dx, y + dy, PH2[i].r, cue.onDark ? BONE : NIGHT, .18 + .57 * m);   // onDark: draw on the ground colour
    }
    c.globalAlpha = 1;
  }
  window.PART = { answer_bubble, two_into_one, field_to_stream };
})();
