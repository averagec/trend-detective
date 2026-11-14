let ac = null, on = true;
const ctx = () => {
  try {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === "suspended") ac.resume();
  } catch (e) {
  }
  return ac;
};
function tone(f, d, type, vol, slide, delay) {
  const a = ctx();
  if (!a || !on) return;
  const t0 = a.currentTime + (delay || 0);
  const o = a.createOscillator(), g = a.createGain();
  o.type = type || "square";
  o.frequency.setValueAtTime(f, t0);
  if (slide) o.frequency.exponentialRampToValueAtTime(slide, t0 + d);
  g.gain.setValueAtTime(vol || 0.03, t0);
  g.gain.exponentialRampToValueAtTime(1e-4, t0 + d);
  o.connect(g);
  g.connect(a.destination);
  o.start(t0);
  o.stop(t0 + d);
}
function noise(d, vol, lp) {
  const a = ctx();
  if (!a || !on) return;
  const b = a.createBuffer(1, a.sampleRate * d, a.sampleRate), c = b.getChannelData(0);
  for (let i = 0; i < c.length; i++) c[i] = Math.random() * 2 - 1;
  const s = a.createBufferSource(), g = a.createGain(), f = a.createBiquadFilter();
  f.type = "lowpass";
  f.frequency.value = lp || 6e3;
  s.buffer = b;
  g.gain.setValueAtTime(vol || 0.05, a.currentTime);
  g.gain.exponentialRampToValueAtTime(1e-4, a.currentTime + d);
  s.connect(f);
  f.connect(g);
  g.connect(a.destination);
  s.start();
}
const SFX = {
  blip: () => tone(520 + Math.random() * 80, 0.035, "square", 0.016),
  click: () => tone(1800, 0.012, "square", 0.02),
  key: () => {
    noise(0.03, 0.06, 3500);
    tone(160 + Math.random() * 60, 0.02, "square", 0.012);
  },
  mouse: () => {
    tone(2400, 0.01, "square", 0.03);
    tone(1200, 0.012, "square", 0.02, null, 0.06);
  },
  open: () => {
    tone(440, 0.06, "square", 0.025);
    tone(660, 0.06, "square", 0.025, null, 0.06);
    tone(880, 0.08, "square", 0.025, null, 0.12);
  },
  close: () => {
    tone(660, 0.05, "square", 0.022);
    tone(440, 0.07, "square", 0.022, null, 0.05);
  },
  select: () => tone(1200, 0.02, "square", 0.02),
  err: () => {
    tone(140, 0.18, "sawtooth", 0.04);
    tone(110, 0.18, "sawtooth", 0.04, null, 0.08);
  },
  chime: () => {
    [523, 659, 784, 1046].forEach((f, i) => tone(f, 0.18, "triangle", 0.05, null, i * 0.09));
  },
  thunk: () => {
    tone(120, 0.35, "sine", 0.18, 40);
    noise(0.25, 0.05, 900);
  },
  static: (d) => noise(d || 0.6, 0.07, 7e3),
  beep: () => tone(880, 0.12, "square", 0.03),
  stamp: () => {
    tone(70, 0.25, "sine", 0.25, 35);
    noise(0.12, 0.08, 1500);
  },
  whoosh: () => noise(1.2, 0.035, 500),
  toggle: () => {
    on = !on;
    return on;
  }
};
export {
  SFX
};
