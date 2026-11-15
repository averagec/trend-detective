const BASE_W = 1440, BASE_H = 900, BEZEL = 48;
let uiScale = 1;
function update() {
  const raw = Math.min(innerWidth / BASE_W, innerHeight / BASE_H);
  uiScale = raw >= 1 ? Math.floor(raw * 3) / 3 : Math.max(0.6, raw);
  const root = document.documentElement.style;
  root.setProperty("--ui", uiScale);
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
