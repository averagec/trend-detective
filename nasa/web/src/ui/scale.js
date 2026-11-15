const BASE_W = 1440, BASE_H = 900, BEZEL = 48;
let uiScale = 1;
function update() {
  const raw = Math.min(innerWidth / BASE_W, innerHeight / BASE_H);
  uiScale = raw >= 1 ? Math.floor(raw * 3) / 3 : Math.max(0.6, raw);
  const root = document.documentElement.style;
  root.setProperty("--ui", uiScale);
  const menu = Math.max(0.75, Math.min(2.4, Math.min(innerWidth / 1180, innerHeight / 740)));
  root.setProperty("--ui-menu", menu.toFixed(3));
  root.setProperty("--ui-say", Math.max(uiScale, Math.min(1.35, menu * 0.9)).toFixed(3));
  root.setProperty("--crt-w", Math.round(innerWidth / uiScale - BEZEL) + "px");
  root.setProperty("--crt-h", Math.round(innerHeight / uiScale - BEZEL) + "px");
}
update();
addEventListener("resize", update);
const toLocal = (v) => v / uiScale;
async function enterFullscreen() {
  const el = document.documentElement;
  if (document.fullscreenElement || !el.requestFullscreen) return;
  try {
    await el.requestFullscreen({ navigationUI: "hide" });
  } catch (e) {
  }
}
function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else enterFullscreen();
}
export {
  uiScale,
  toLocal,
  enterFullscreen,
  toggleFullscreen
};
