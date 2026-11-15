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
const SEA = [31, 79, 160], SEA2 = [59, 125, 221], FOAM = [214, 236, 248], WALL = [150, 140, 120], WALL2 = [96, 88, 74];
const ROOF = [217, 74, 54], ROOF2 = [150, 48, 36], WIN = [247, 214, 120];
function flood(f) {
  const px = [], w = 11, h = 11, lvl = [0, 1, 1, 2, 2, 2, 1, 1][f % 8];
  for (let y = 0; y < 4; y++) for (let x = 4 - y; x <= 6 + y; x++) {
    const edge = x === 4 - y || x === 6 + y || y === 0;
    px.push([x, y, edge ? INK : y % 2 ? ROOF : ROOF2]);
  }
  for (let y = 4; y < 10; y++) for (let x = 1; x < w - 1; x++) {
    const edge = x === 1 || x === w - 2;
    const win = y >= 5 && y <= 6 && (x === 3 || x === 4 || x === 6 || x === 7);
    px.push([x, y, edge ? INK : win ? WIN : (x + y) % 2 ? WALL : WALL2]);
  }
  const top = 8 - lvl;
  for (let y = top; y < h; y++) for (let x = -1; x <= w; x++) {
    const c = y === top ? ((x + f) % 4 < 2 ? FOAM : SEA2) : (x + y) % 2 ? SEA : SEA2;
    px.push([x, y, c]);
  }
  px.push([((f * 2) % (w + 2)) - 1, top - 1, FOAM]);
  return { w, h, px };
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
const pixelWeather = { rain, storm, flood, paintSprite, drought, paintDrought, INK };
export {
  pixelWeather
};
