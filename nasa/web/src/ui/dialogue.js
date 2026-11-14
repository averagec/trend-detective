import { SFX } from "../audio/sfx.js";
const box = document.getElementById("say"), txt = document.getElementById("say-text");
let q = [], typing = null, full = "", done = null;
const face = document.querySelector(".say-face");
function show(line) {
  full = line;
  let i = 0;
  clearInterval(typing);
  txt.textContent = "";
  face.classList.add("talk");
  typing = setInterval(() => {
    i++;
    txt.textContent = full.slice(0, i);
    if (i % 2 === 0 && full[i - 1] !== " ") SFX.blip();
    if (i >= full.length) {
      clearInterval(typing);
      typing = null;
      face.classList.remove("talk");
    }
  }, 30);
}
function next() {
  if (typing) {
    clearInterval(typing);
    typing = null;
    txt.textContent = full;
    face.classList.remove("talk");
    return;
  }
  if (!q.length) {
    closeSay();
    const d = done;
    done = null;
    d && d();
    return;
  }
  show(q.shift());
}
function say(lines, cb) {
  q = lines.slice();
  done = cb || null;
  box.classList.add("on");
  next();
}
;
function closeSay() {
  box.classList.remove("on");
  q = [];
  clearInterval(typing);
  typing = null;
}
;
document.getElementById("say-box").addEventListener("click", next);
addEventListener("keydown", (e) => {
  if (box.classList.contains("on") && (e.key === " " || e.key === "Enter")) {
    e.preventDefault();
    next();
  }
});
export {
  closeSay,
  say
};
