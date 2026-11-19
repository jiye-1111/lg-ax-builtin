// 3D 뷰어 (three.js, glb)
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { toast } from "./core.js";

export function makeViewer(el) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  el.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#eceae5");
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb8b2a8, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(-4, 8, 6);
  scene.add(sun);
  const cam = new THREE.PerspectiveCamera(45, 1, 0.05, 200);
  const ctl = new OrbitControls(cam, renderer.domElement);
  ctl.enableDamping = true;
  let model = null, framed = false, alive = true, walls = [], center = new THREE.Vector3();
  const tmp = new THREE.Vector3(), toCam = new THREE.Vector3();
  // 카메라 쪽 벽은 반투명으로 (돌하우스 컷어웨이)
  const cutaway = () => {
    toCam.copy(cam.position).sub(center).setY(0).normalize();
    for (const w of walls) {
      w.getWorldPosition(tmp);
      const front = tmp.sub(center).setY(0).normalize().dot(toCam) > 0.35;
      w.material.opacity = front ? 0.12 : 1;
      w.material.transparent = front;
      w.material.depthWrite = !front;
    }
  };
  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    renderer.setSize(w, h);
    cam.aspect = w / h;
    cam.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(el);
  resize();
  (function loop() {
    if (!alive) return;
    ctl.update();
    cutaway();
    renderer.render(scene, cam);
    requestAnimationFrame(loop);
  })();
  // 방 전체가 보이게 카메라를 잡는다 (화면 비율이 세로로 길면 더 멀리)
  const frame = () => {
    if (!model) return;
    const box = new THREE.Box3().setFromObject(model);
    const c = box.getCenter(new THREE.Vector3());
    const s = box.getSize(new THREE.Vector3()).length() * Math.max(1, 1.2 / cam.aspect);
    cam.position.set(c.x - s * 0.35, c.y + s * 1.05, c.z + s * 0.55);
    ctl.target.copy(c);
  };
  const loader = new GLTFLoader();
  return {
    load(url) {
      loader.load(url + (url.includes("?") ? "&" : "?") + "v=" + Date.now(), (g) => {
        if (model) scene.remove(model);
        model = g.scene;
        walls = [];
        model.traverse((o) => {
          if (o.isMesh) o.material = o.material.clone();
          const kind = o.userData?.kind ?? o.parent?.userData?.kind;
          if (o.isMesh && (kind === "wall" || kind === "door" || kind === "window")) walls.push(o);
        });
        scene.add(model);
        new THREE.Box3().setFromObject(model).getCenter(center);
        if (!framed) { frame(); framed = true; }
      }, undefined, () => toast("3D 파일을 불러오지 못했습니다", true));
    },
    reframe() { setTimeout(() => { resize(); frame(); }, 280); },
    dispose() { alive = false; ro.disconnect(); renderer.dispose(); el.innerHTML = ""; },
  };
}
