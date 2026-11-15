import { SFX } from "../audio/sfx.js";
import { play } from "../scene/office.js";
import { enterFullscreen, toggleFullscreen } from "./scale.js";
const $ = (s) => document.querySelector(s);
$("#play").onclick = () => {
  SFX.click();
  enterFullscreen();
  play();
};
const tog = (id) => {
  SFX.click();
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === id && !p.classList.contains("on")));
};
$("#b-how").onclick = () => tog("p-how");
const snd = () => {
  const on = SFX.toggle();
  $("#b-snd").innerHTML = '<span class="arrow">▸</span>SOUND: ' + (on ? "ON" : "OFF");
  $("#h-snd").textContent = "SOUND: " + (on ? "ON" : "OFF");
};
$("#b-snd").onclick = snd;
$("#h-snd").onclick = snd;
$("#h-fs").onclick = () => {
  SFX.click();
  toggleFullscreen();
};
document.addEventListener("fullscreenchange", () => {
  $("#h-fs").textContent = document.fullscreenElement ? "EXIT FULLSCREEN" : "FULLSCREEN";
});
document.querySelectorAll(".mbtn").forEach((b) => b.addEventListener("mouseenter", () => SFX.click()));
