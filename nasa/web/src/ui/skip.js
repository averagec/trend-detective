// One SKIP button for the cut-scenes (camera flights and the computer boot).
// begin() shows it; while it is requested, wait() resolves at once and camera tweens finish.
const btn = document.createElement("button");
btn.id = "skip";
btn.className = "skip";
btn.type = "button";
btn.textContent = "SKIP ▸▸";
btn.setAttribute("aria-label", "Skip intro");
document.body.appendChild(btn);
const skip = { req: false, waiters: new Set() };
function fire() {
  skip.req = true;
  skip.waiters.forEach((f) => f());
  skip.waiters.clear();
}
btn.addEventListener("click", (e) => {
  e.stopPropagation();
  fire();
});
addEventListener("keydown", (e) => {
  if (!btn.classList.contains("on")) return;
  if (e.key === "Escape" || e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    e.stopImmediatePropagation();
    fire();
  }
}, true);
function begin() {
  if (!btn.classList.contains("on")) skip.req = false;
  btn.classList.add("on");
}
function end() {
  skip.req = false;
  btn.classList.remove("on");
}
function wait(ms) {
  if (skip.req) return Promise.resolve();
  return new Promise((r) => {
    const t = setTimeout(done, ms);
    function done() {
      clearTimeout(t);
      skip.waiters.delete(done);
      r();
    }
    skip.waiters.add(done);
  });
}
export { skip, begin as beginSkip, end as endSkip, wait as skipWait };
