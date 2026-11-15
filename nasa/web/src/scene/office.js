import { SFX } from "../audio/sfx.js";
import { say, closeSay } from "../ui/dialogue.js";
import { desktop } from "../os/desktop.js";
import { skip, beginSkip, endSkip } from "../ui/skip.js";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
const $ = (s) => document.querySelector(s);
const canvas = $("#scene");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
const scene = new THREE.Scene();
scene.background = new THREE.Color(329224);
const camera = new THREE.PerspectiveCamera(58, innerWidth / innerHeight, 0.02, 100);
scene.add(new THREE.HemisphereLight(9414344, 1708556, 0.55));
const windowLight = new THREE.DirectionalLight(8364248, 1.1);
windowLight.position.set(3, 4, -6);
scene.add(windowLight);
scene.add(windowLight.target);
const lamp = new THREE.PointLight(16761466, 2.2, 0, 2);
lamp.position.set(1.25, 1.95, -1.15);
scene.add(lamp);
const screenGlow = new THREE.PointLight(7314687, 0.7, 2.5, 2);
screenGlow.position.set(0.545, 1.59, -0.72);
scene.add(screenGlow);
const sweep = new THREE.SpotLight(16773324, 0, 0, 0.42, 0.85, 2);
sweep.position.set(-2, 2.5, -3.6);
sweep.target.position.set(0, 1.4, 1.2);
scene.add(sweep);
scene.add(sweep.target);
let nextSweep = 9, sweepT = -1;
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.28, 0.35, 0.92);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.enabled = false;
controls.enablePan = false;
const SCREEN = new THREE.Vector3(0.545, 1.59, -0.935);
const V = (a) => new THREE.Vector3(...a);
const views = {
  intro: { pos: V([1.72, 2.65, 1.78]), target: V([-0.5, 1.15, -0.9]) },
  room: { pos: V([1.6, 2.25, 0.9]), target: V([0.5, 1.45, -0.95]) },
  screen: { pos: V([0.545, 1.59, -0.4]), target: SCREEN.clone() }
};
const state = { mode: "loading", hoverPC: false, firstRoom: true };
let screenMats = [], roomRoot = null;
function closeRoom(wallMat) {
  const mk = (w, h, mat) => new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  const wm = wallMat.clone();
  if (wm.map) {
    wm.map = wm.map.clone();
    wm.map.wrapS = wm.map.wrapT = THREE.RepeatWrapping;
    wm.map.repeat.set(3, 3);
    wm.map.needsUpdate = true;
  }
  wm.side = THREE.FrontSide;
  const right = mk(3.7, 3.5, wm);
  right.position.set(1.79, 1.75, 0.03);
  right.rotation.y = -Math.PI / 2;
  scene.add(right);
  const front = mk(3.6, 3.5, wm);
  front.position.set(0, 1.75, 1.864);
  front.rotation.y = Math.PI;
  scene.add(front);
  const ceil = mk(3.6, 3.7, new THREE.MeshStandardMaterial({ color: 2303274, roughness: 0.95 }));
  ceil.position.set(0, 3.48, 0.03);
  ceil.rotation.x = Math.PI / 2;
  scene.add(ceil);
  const base = new THREE.MeshStandardMaterial({ color: 2764602, roughness: 0.6 });
  const b1 = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.14, 3.6), base);
  b1.position.set(1.77, 0.07, 0.03);
  scene.add(b1);
  const b2 = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.14, 0.03), base);
  b2.position.set(0, 0.07, 1.845);
  scene.add(b2);
  const doorMat = new THREE.MeshStandardMaterial({ color: 3811870, roughness: 0.55 });
  const door = new THREE.Mesh(new THREE.BoxGeometry(0.05, 2.1, 0.95), doorMat);
  door.position.set(1.765, 1.05, 0.9);
  scene.add(door);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.55), new THREE.MeshStandardMaterial({ color: 13220234, emissive: 7035440, emissiveIntensity: 0.25, roughness: 0.2 }));
  glass.position.set(1.738, 1.6, 0.9);
  glass.rotation.y = -Math.PI / 2;
  scene.add(glass);
  const knob = new THREE.Mesh(new THREE.SphereGeometry(0.03, 12, 8), new THREE.MeshStandardMaterial({ color: 11569738, metalness: 0.8, roughness: 0.3 }));
  knob.position.set(1.73, 1, 0.5);
  scene.add(knob);
}
let dust;
function addDust() {
  const N = 420, g = new THREE.BufferGeometry(), p = new Float32Array(N * 3), seed = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    p[i * 3] = -1.6 + Math.random() * 3.3;
    p[i * 3 + 1] = 0.3 + Math.random() * 3;
    p[i * 3 + 2] = -1.6 + Math.random() * 3.3;
    seed[i] = Math.random() * 100;
  }
  g.setAttribute("position", new THREE.BufferAttribute(p, 3));
  g.setAttribute("seed", new THREE.BufferAttribute(seed, 1));
  const dc = document.createElement("canvas");
  dc.width = dc.height = 32;
  const dx = dc.getContext("2d");
  const gr = dx.createRadialGradient(16, 16, 0, 16, 16, 16);
  gr.addColorStop(0, "rgba(255,255,255,1)");
  gr.addColorStop(1, "rgba(255,255,255,0)");
  dx.fillStyle = gr;
  dx.fillRect(0, 0, 32, 32);
  const m = new THREE.PointsMaterial({ map: new THREE.CanvasTexture(dc), color: 16769712, size: 8e-3, transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending });
  dust = new THREE.Points(g, m);
  scene.add(dust);
}
const bar = $("#load-fill"), pct = $("#load-pct");
const loader = new GLTFLoader();
function onModel(gltf) {
  const root = gltf.scene;
  roomRoot = root;
  root.scale.setScalar(40);
  scene.add(root);
  let wallMat = null;
  root.traverse((o) => {
    if (!o.isMesh) return;
    const n = o.material && o.material.name;
    if (n === "Monitor_Screen" && !screenMats.includes(o.material)) screenMats.push(o.material);
    if (n === "Whitewall" && !wallMat) wallMat = o.material;
  });
  closeRoom(wallMat || new THREE.MeshStandardMaterial({ color: 9344675 }));
  addDust();
  camera.position.copy(views.intro.pos);
  controls.target.copy(views.intro.target);
  camera.lookAt(views.intro.target);
  document.querySelector(".load").style.display = "none";
  document.body.classList.add("ready");
  $("#play").disabled = false;
  state.mode = "intro";
}
loader.load("models/office.glb", onModel, (e) => {
  if (!e.total) return;
  const p = Math.round(e.loaded / e.total * 100);
  bar.style.width = p + "%";
  pct.textContent = "LOADING " + p + "%";
}, () => {
  pct.textContent = "COULD NOT LOAD THE ROOM";
});
let tween = null;
const ease = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
function flyTo(v, ms, done, fov) {
  controls.enabled = false;
  tween = { p0: camera.position.clone(), t0: controls.target.clone(), p1: v.pos.clone(), t1: v.target.clone(), f0: camera.fov, f1: fov || camera.fov, start: performance.now(), ms, done };
}
function enableRoomControls() {
  controls.target.copy(views.room.target);
  const off = new THREE.Vector3().subVectors(views.room.pos, views.room.target);
  const sph = new THREE.Spherical().setFromVector3(off);
  controls.minAzimuthAngle = sph.theta - 1.05;
  controls.maxAzimuthAngle = sph.theta + 0.55;
  controls.minPolarAngle = Math.max(0.45, sph.phi - 0.45);
  controls.maxPolarAngle = Math.min(1.85, sph.phi + 0.4);
  controls.minDistance = off.length() * 0.55;
  controls.maxDistance = off.length() * 1.15;
  controls.rotateSpeed = 0.45;
  controls.enabled = true;
}
function play() {
  if (state.mode !== "intro") return;
  SFX.whoosh();
  document.body.classList.add("playing");
  state.mode = "flying";
  beginSkip();
  flyTo(views.room, 3200, () => {
    endSkip();
    state.mode = "room";
    enableRoomControls();
    $("#hud").classList.add("on");
    if (state.firstRoom) {
      state.firstRoom = false;
      say([
        "Jakarta again. High tide came over the sea wall last night.",
        "Everyone says the sea is rising. Could be true. Could also be a scary line drawn through noise.",
        "Only one way to settle it. NASA’s records. Computer first."
      ]);
    }
  }, 58);
}
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
function pcUnderPointer(e) {
  mouse.set(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObject(roomRoot, true)[0];
  return !!hit && (/^(Monitor|Computer|Keyboard)_/.test(hit.object.name) || hit.point.distanceTo(SCREEN) < 0.45);
}
let lastMove = 0;
canvas.addEventListener("pointermove", (e) => {
  if (state.mode !== "room" || !roomRoot) return;
  const now = performance.now();
  if (now - lastMove < 40) return;
  lastMove = now;
  state.hoverPC = pcUnderPointer(e);
  canvas.style.cursor = state.hoverPC ? "pointer" : "grab";
  const tip = $("#tip");
  if (state.hoverPC) {
    tip.style.left = e.clientX + 18 + "px";
    tip.style.top = e.clientY + 18 + "px";
    tip.classList.add("on");
  } else tip.classList.remove("on");
});
let downAt = null;
canvas.addEventListener("pointerdown", (e) => {
  downAt = [e.clientX, e.clientY];
});
canvas.addEventListener("pointerup", (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 6) return;
  if (state.mode !== "room" || !roomRoot) return;
  if (pcUnderPointer(e)) bootOS();
});
function bootOS() {
  if (state.mode === "os") return;
  state.mode = "os";
  state.hoverPC = false;
  $("#tip").classList.remove("on");
  $("#hud").classList.remove("on");
  closeSay();
  SFX.whoosh();
  beginSkip();
  flyTo(views.screen, 1700, () => desktop.open(), 52);
}
function leaveDesk() {
  state.mode = "flying";
  flyTo(views.room, 1500, () => {
    state.mode = "room";
    enableRoomControls();
    $("#hud").classList.add("on");
  }, 58);
}
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
});
const clock = new THREE.Clock();
(function loop() {
  requestAnimationFrame(loop);
  const t = clock.getElapsedTime();
  if (tween) {
    const k = skip.req ? 1 : Math.min(1, (performance.now() - tween.start) / tween.ms), e = ease(k);
    camera.position.lerpVectors(tween.p0, tween.p1, e);
    controls.target.lerpVectors(tween.t0, tween.t1, e);
    camera.fov = tween.f0 + (tween.f1 - tween.f0) * e;
    camera.updateProjectionMatrix();
    camera.lookAt(controls.target);
    if (k >= 1) {
      const d = tween.done;
      tween = null;
      d && d();
    }
  } else if (state.mode === "intro") {
    const v = views.intro, s = Math.sin(t * 0.18) * 0.12;
    camera.position.set(v.pos.x + s * 0.4, v.pos.y + Math.sin(t * 0.23) * 0.04, v.pos.z - s * 0.3);
    camera.lookAt(v.target);
  }
  if (controls.enabled) controls.update();
  if (t > nextSweep && sweepT < 0) {
    sweepT = 0;
    nextSweep = t + 18 + Math.random() * 10;
  }
  if (sweepT >= 0) {
    sweepT += 1 / 60;
    const k = sweepT / 2.6;
    sweep.position.x = -2.2 + 4.6 * k;
    sweep.target.position.x = 1.6 - 2.8 * k;
    sweep.intensity = Math.sin(Math.min(1, k) * Math.PI) * 26;
    if (k >= 1) {
      sweepT = -1;
      sweep.intensity = 0;
    }
  }
  lamp.intensity = 2.2 + Math.sin(t * 7.3) * 0.04 + (Math.random() < 4e-3 ? -0.8 : 0);
  const hov = state.hoverPC && state.mode === "room";
  const flick = 1 + Math.sin(t * 40) * 0.015 + (Math.random() < 0.01 ? -0.12 : 0);
  screenMats.forEach((m) => {
    m.emissiveIntensity = (hov ? 1.7 : 1.25) * flick;
  });
  screenGlow.intensity = (hov ? 1 : 0.6) * flick;
  if (dust) {
    const pos = dust.geometry.attributes.position, sd = dust.geometry.attributes.seed;
    for (let i = 0; i < pos.count; i++) {
      const s = sd.getX(i);
      pos.setY(i, pos.getY(i) + Math.sin(t * 0.3 + s) * 25e-5 - 8e-5);
      pos.setX(i, pos.getX(i) + Math.cos(t * 0.2 + s) * 18e-5);
      if (pos.getY(i) < 0.2) pos.setY(i, 3.2);
    }
    pos.needsUpdate = true;
    dust.material.opacity = 0.45 + Math.sin(t * 0.7) * 0.1;
  }
  if (state.mode === "os" && !tween && document.body.classList.contains("in-os")) return;
  composer.render();
})();
export {
  leaveDesk,
  play
};
