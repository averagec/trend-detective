const INK = [6, 9, 15];
const CLOUD = [
  "....####......",
  "...#LLLL#.###.",
  ".##LLLLLL#LLL#",
  "#LLLLLLLLLLLM#",
  "#LLLLLLLLLMMM#",
  "#MLLLLLLLMMMD#",
  ".#MMMMMMMMDD#.",
  "..##########.."
];
const CC = { "#": INK, L: [214, 225, 242], M: [150, 172, 206], D: [94, 116, 156] };
const DROP = [127, 214, 232], DROP2 = [64, 132, 196];
function rain(f) {
  const px = [];
  CLOUD.forEach((row, y) => [...row].forEach((c, x) => {
    if (c !== ".") px.push([x, y, CC[c]]);
  }));
  [[3, 0], [5, 3], [7, 1], [9, 4], [11, 2]].forEach(([x, ph]) => {
    const y = 8 + (f + ph) % 6;
    px.push([x, y, DROP2]);
    if (y + 1 < 14) px.push([x, y + 1, DROP]);
  });
  return { w: 14, h: 14, px };
}
const TL = [222, 218, 206], TM = [168, 163, 152], TD = [112, 108, 100], DIRT = [138, 90, 43], DUST = [201, 164, 106];
const PROF = [4.6, 5.8, 5.8, 5.2, 4.5, 3.9, 3.3, 2.8, 2.3, 1.8, 1.4, 1, 0.6];
function storm(f) {
  const px = [], t = f / 8, W = 15, Hh = 13, m = new Int8Array(W * Hh).fill(0), cxs = [];
  PROF.forEach((hw, y) => {
    const lean = 0.9 * Math.sin(y / 12 * 2 * Math.PI), sway = Math.sin(2 * Math.PI * t + y * 0.6) * (y / 12) * 1.8;
    const cx = 7.5 + lean + sway;
    cxs.push(cx);
    for (let x = Math.round(cx - hw); x < Math.round(cx + hw); x++) if (x >= 0 && x < W) m[y * W + x] = 1;
  });
  const on = (x, y) => x >= 0 && y >= 0 && x < W && y < Hh && m[y * W + x];
  let tip = 7;
  for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) {
    if (!on(x, y)) continue;
    tip = y === Hh - 1 ? x : tip;
    const rowW = [...Array(W).keys()].filter((q) => on(q, y)).length;
    let c;
    if (rowW <= 2) c = TM;
    else if (!on(x - 1, y) || !on(x + 1, y) || !on(x, y - 1) || !on(x, y + 1) && rowW > 3) c = INK;
    else {
      const band = ((y + Math.floor((x - cxs[y] + f) / 3)) % 2 + 2) % 2;
      c = band === 0 ? TM : TL;
      if (x > cxs[y] + PROF[y] * 0.3) c = c === TL ? TM : TD;
    }
    px.push([x, y, c]);
  }
  for (let k = 0; k < 4; k++) {
    const a = 2 * Math.PI * (t + k / 4), x = Math.round(tip + Math.cos(a) * 3.2), y = 12 + (Math.sin(a) > 0 ? 1 : 0);
    px.push([x, y, k % 2 ? DIRT : DUST]);
  }
  return { w: W, h: 14, px };
}
const SEA = [28, 92, 124], SEA2 = [74, 130, 196], LITE = [168, 210, 232], FOAM = [232, 246, 251];
const WALL = [196, 180, 150], WALL2 = [150, 136, 110], ROOF = [217, 74, 54], ROOF2 = [150, 48, 36], WIN = [247, 214, 120];
const FLOOD_COLS = [[2, 0], [4, 3], [7, 1], [11, 4], [13, 2]];
function flood(f) {
  const px = [], w = 16, h = 19, put = (x, y, c) => px.push([x, y, c]);
  const lvl = [0, 0, 1, 1, 2, 2, 3, 3, 3, 3, 2, 2, 1, 1, 0, 0][f % 16], top = 15 - lvl;
  CLOUD.forEach((row, y) => [...row].forEach((c, x) => {
    if (c !== ".") put(x + 1, y, CC[c]);
  }));
  for (let y = 9; y < 12; y++) for (let x = 7 - (y - 9); x <= 9 + (y - 9); x++) {
    const edge = x === 7 - (y - 9) || x === 9 + (y - 9) || y === 9;
    put(x, y, edge ? INK : y % 2 ? ROOF : ROOF2);
  }
  for (let y = 12; y < top; y++) for (let x = 5; x <= 11; x++) {
    const win = y === 13 && (x === 7 || x === 9);
    put(x, y, x === 5 || x === 11 ? INK : win ? WIN : (x + y) % 2 ? WALL : WALL2);
  }
  const splash = [];
  FLOOD_COLS.forEach(([x, ph]) => {
    const fall = top - 9, y = 9 + (f + ph) % (fall + 2);
    if (x >= 5 && x <= 11 && y >= 9) return;
    if (y < top - 1) {
      put(x, y, DROP2);
      put(x, y + 1, DROP);
    } else splash.push(x);
  });
  for (let y = top; y < h; y++) for (let x = 0; x < w; x++) {
    let c;
    if (y === top) c = Math.sin((x + f) * 0.9) > 0.3 ? FOAM : LITE;
    else {
      const e = Math.sin(x * 1.3 + y * 0.7 + f * 0.5) + Math.sin(x * 0.6 - y * 1.1 - f * 0.35);
      c = e > 1.35 ? LITE : e < -1.1 ? SEA : SEA2;
    }
    if (y === h - 1 && (x === 0 || x === w - 1)) continue;
    put(x, y, c);
  }
  splash.forEach((x) => {
    put(x, top - 1, FOAM);
    if (x > 0) put(x - 1, top, FOAM);
    if (x < w - 1) put(x + 1, top, FOAM);
  });
  return { w, h, px };
}
const SUN = [247, 214, 120], SUN2 = [233, 169, 58], HOT = [217, 74, 54], GLASS = [236, 230, 214];
function heat(f) {
  const px = [], put = (x, y, c) => px.push([x, y, c]), cx = 6, cy = 6;
  for (let y = 0; y < 13; y++) for (let x = 0; x < 13; x++) {
    const d = Math.hypot(x - cx, y - cy);
    if (d <= 3.6) put(x, y, d > 2.8 ? INK : d < 1.6 && (x + y) % 2 ? SUN : d < 2.2 ? SUN : SUN2);
  }
  const ray = f % 4 < 2 ? 1 : 0;
  [[0, -1], [1, 0], [0, 1], [-1, 0], [1, -1], [1, 1], [-1, 1], [-1, -1]].forEach(([dx, dy], i) => {
    const r0 = i < 4 ? 5 : 4, len = i < 4 ? 1 + ray : 1 + (1 - ray);
    for (let k = 0; k < len; k++) put(cx + dx * (r0 + k), cy + dy * (r0 + k), i % 2 ? SUN2 : SUN);
  });
  const tx = 14, lvl = [3, 4, 5, 6, 6, 5, 4, 3][f % 8];
  for (let y = 1; y < 12; y++) {
    put(tx - 1, y, INK);
    put(tx + 1, y, INK);
    put(tx, y, 11 - y <= lvl ? HOT : GLASS);
  }
  put(tx, 0, INK);
  for (let y = 11; y < 14; y++) for (let x = tx - 1; x <= tx + 1; x++) put(x, y, Math.abs(x - tx) + (y - 12) > 1 ? INK : HOT);
  for (let x = 1; x < 12; x++) {
    const y = 15 + Math.round(Math.sin((x + f) * 0.9));
    if ((x + f) % 3) put(x, y, x % 2 ? SUN2 : DUST);
  }
  return { w: 16, h: 17, px };
}
function paintSprite(img, W, H, s, ax, ay) {
  const ox = ax - Math.floor(s.w / 2), oy = ay - s.h + 1, d = img.data;
  for (const [x, y, c] of s.px) {
    const X = ox + x, Y = oy + y;
    if (X < 0 || Y < 0 || X >= W || Y >= H) continue;
    const p = (Y * W + X) * 4;
    d[p] = c[0];
    d[p + 1] = c[1];
    d[p + 2] = c[2];
    d[p + 3] = 255;
  }
}
const TAN = [201, 164, 106], TAN2 = [176, 128, 74], CRACK = [90, 58, 30];
function rnd(seed) {
  let s = seed >>> 0;
  return () => (s = s * 1664525 + 1013904223 >>> 0) / 4294967296;
}
function drought(masks, W, H, seed = 7) {
  const own = new Int16Array(W * H).fill(-1);
  masks.forEach((m, k) => {
    for (let i = 0; i < m.length; i++) if (m[i]) own[i] = k;
  });
  const cells = [], edge = new Uint8Array(W * H), crack = new Float32Array(W * H).fill(-1), r = rnd(seed), seeds = [];
  for (let i = 0; i < W * H; i++) {
    if (own[i] < 0) continue;
    cells.push(i);
    const x = i % W, y = i / W | 0;
    edge[i] = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => {
      const X = x + dx, Y = y + dy;
      return X < 0 || Y < 0 || X >= W || Y >= H || own[Y * W + X] !== own[i];
    }) ? 1 : 0;
    if (!edge[i] && r() < 0.018) seeds.push([x, y, own[i]]);
  }
  for (const i of cells) {
    if (edge[i]) continue;
    const x = i % W, y = i / W | 0;
    let d1 = 1e9, d2 = 1e9;
    for (const [sx, sy, k] of seeds) {
      if (k !== own[i]) continue;
      const d = Math.hypot(sx - x, sy - y);
      if (d < d1) {
        d2 = d1;
        d1 = d;
      } else if (d < d2) d2 = d;
    }
    if (d2 - d1 < 0.75) crack[i] = d1;
  }
  return { W, H, cells, edge, crack };
}
const BAYER = [0, 2, 3, 1];
function paintDrought(img, st, f) {
  const T = f % 32, grow = T < 20 ? T * 0.9 : T < 28 ? 99 : -1, d = img.data;
  for (const i of st.cells) {
    const x = i % st.W, y = i / st.W | 0;
    const c = st.edge[i] ? INK : st.crack[i] >= 0 && st.crack[i] <= grow ? CRACK : BAYER[x % 2 + 2 * (y % 2)] < 2 ? TAN : TAN2;
    const p = i * 4;
    d[p] = c[0];
    d[p + 1] = c[1];
    d[p + 2] = c[2];
    d[p + 3] = 255;
  }
}
const pixelWeather = { rain, storm, flood, heat, paintSprite, drought, paintDrought, INK };
export {
  pixelWeather
};
