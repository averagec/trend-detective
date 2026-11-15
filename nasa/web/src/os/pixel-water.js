const BASE = [74, 130, 196], DEEP = [28, 92, 124], LINE = [168, 210, 232], GLINT = [232, 246, 251];
const CELL = 22;

function hash(x, y) {
  let h = (x * 374761393 + y * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

function seed(cx, cy, t) {
  const a = hash(cx, cy), b = hash(cy + 91, cx - 37), p = hash(cx * 7 + 3, cy * 13 + 5) * 6.283;
  const r = 0.22;
  return [
    (cx + 0.5 + (a - 0.5) * 0.5 + Math.cos(t + p) * r) * CELL,
    (cy + 0.5 + (b - 0.5) * 0.5 + Math.sin(t * 0.8 + p) * r) * CELL
  ];
}

function paintWater(img, W, H, t, ox, oy) {
  const d = img.data;
  const gx0 = Math.floor(ox / CELL) - 1, gy0 = Math.floor(oy / CELL) - 1;
  const gw = Math.ceil(W / CELL) + 3, gh = Math.ceil(H / CELL) + 3;
  const pts = new Float32Array(gw * gh * 2);
  for (let j = 0; j < gh; j++) for (let i = 0; i < gw; i++) {
    const s = seed(gx0 + i, gy0 + j, t), k = (j * gw + i) * 2;
    pts[k] = s[0] - ox;
    pts[k + 1] = s[1] - oy;
  }
  for (let y = 0; y < H; y++) {
    const cy = Math.floor((y + oy) / CELL) - gy0;
    for (let x = 0; x < W; x++) {
      const cx = Math.floor((x + ox) / CELL) - gx0;
      let d1 = 1e9, d2 = 1e9, d3 = 1e9;
      for (let j = cy - 1; j <= cy + 1; j++) for (let i = cx - 1; i <= cx + 1; i++) {
        const k = (j * gw + i) * 2, dx = pts[k] - x, dy = pts[k + 1] - y, q = dx * dx + dy * dy;
        if (q < d1) { d3 = d2; d2 = d1; d1 = q; } else if (q < d2) { d3 = d2; d2 = q; } else if (q < d3) d3 = q;
      }
      const e = Math.sqrt(d2) - Math.sqrt(d1), e3 = Math.sqrt(d3) - Math.sqrt(d1);
      let c = BASE;
      if (e < 1.25) c = e3 < 2.6 ? GLINT : LINE;
      else if (e < 3.4) c = DEEP;
      const p = (y * W + x) * 4;
      d[p] = c[0];
      d[p + 1] = c[1];
      d[p + 2] = c[2];
      d[p + 3] = 255;
    }
  }
}

function startWater(canvas, opts) {
  const ctx = canvas.getContext("2d");
  let img = null, raf = 0, last = 0, t0 = performance.now();
  const frame = (now) => {
    raf = 0;
    if (!canvas.isConnected) return;
    if (now - last >= 140 && document.visibilityState === "visible") {
      last = now;
      const { cell, ox, oy } = opts();
      const W = Math.ceil(canvas.clientWidth / cell), H = Math.ceil(canvas.clientHeight / cell);
      if (W > 0 && H > 0) {
        if (canvas.width !== W || canvas.height !== H || !img) {
          canvas.width = W;
          canvas.height = H;
          img = ctx.createImageData(W, H);
        }
        canvas.style.width = W * cell + "px";
        canvas.style.height = H * cell + "px";
        paintWater(img, W, H, (now - t0) / 1600, Math.round(ox / cell), Math.round(oy / cell));
        ctx.putImageData(img, 0, 0);
      }
    }
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  return () => raf && cancelAnimationFrame(raf);
}

export { startWater, paintWater };
