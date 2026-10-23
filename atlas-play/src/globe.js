import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { feature } from "topojson-client";
import landData from "world-atlas/land-110m.json";
const landFeatures = feature(landData, landData.objects.land);
const landPolygons = landFeatures.features.flatMap((f) =>
  f.geometry.type === "MultiPolygon"
    ? f.geometry.coordinates
    : [f.geometry.coordinates],
);
const R = 2;
export function vector(lat, lng, r = R) {
  const p = (lat * Math.PI) / 180,
    t = (lng * Math.PI) / 180;
  return new THREE.Vector3(
    r * Math.cos(p) * Math.cos(t),
    r * Math.sin(p),
    -r * Math.cos(p) * Math.sin(t),
  );
}
function texture() {
  const c = document.createElement("canvas");
  c.width = 2048;
  c.height = 1024;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#182b34";
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.strokeStyle = "#27404a";
  ctx.lineWidth = 1;
  for (let x = 0; x <= 2048; x += 2048 / 24) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, 1024);
    ctx.stroke();
  }
  for (let y = 0; y <= 1024; y += 1024 / 12) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(2048, y);
    ctx.stroke();
  }
  ctx.fillStyle = "#a2b9ad";
  ctx.strokeStyle = "#cee1bf";
  ctx.lineWidth = 0.65;
  for (const polygon of landPolygons) {
    ctx.beginPath();
    for (const ring of polygon) {
      ring.forEach(([lng, lat], i) => {
        const x = ((lng + 180) / 360) * 2048,
          y = ((90 - lat) / 180) * 1024;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.closePath();
    }
    ctx.fill("evenodd");
    ctx.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
export class Globe {
  constructor(host, onPick) {
    this.host = host;
    this.onPick = onPick;
    this.enabled = true;
    this.markers = [];
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    this.camera.position.copy(vector(22, 55, 7.4));
    try {
      this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      host.innerHTML =
        '<div class="fallback">此设备无法启动三维地球。请开启浏览器硬件加速，或换用支持 WebGL 的浏览器。</div>';
      return;
    }
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.append(this.renderer.domElement);
    this.renderer.domElement.setAttribute(
      "aria-label",
      "交互地球：拖动旋转，滚轮缩放，点击选择位置。也可在右侧手动输入经纬度。",
    );
    this.renderer.domElement.tabIndex = 0;
    this.earth = new THREE.Mesh(
      new THREE.SphereGeometry(R, 96, 64),
      new THREE.MeshStandardMaterial({
        map: texture(),
        roughness: 0.94,
        metalness: 0.08,
      }),
    ); // Sphere UV maps canvas longitude -180..180 directly to geographic vectors.
    this.scene.add(this.earth);
    this.scene.add(new THREE.AmbientLight(0xe9f4e7, 2.05));
    const light = new THREE.DirectionalLight(0xffffff, 2.3);
    light.position.set(4, 6, 5);
    this.scene.add(light);
    const rim = new THREE.Mesh(
      new THREE.SphereGeometry(R * 1.015, 64, 48),
      new THREE.MeshBasicMaterial({
        color: 0x9cd7be,
        side: THREE.BackSide,
        transparent: true,
        opacity: 0.12,
      }),
    );
    this.scene.add(rim);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;
    this.controls.minDistance = 2.6;
    this.controls.maxDistance = 10;
    this.controls.rotateSpeed = 0.55;
    this.controls.zoomSpeed = 0.65;
    this.controls.autoRotate = !matchMedia("(prefers-reduced-motion: reduce)")
      .matches;
    this.controls.autoRotateSpeed = 0.35;
    const ray = new THREE.Raycaster(),
      mouse = new THREE.Vector2();
    let down = null;
    this.renderer.domElement.addEventListener("pointerdown", (e) => {
      down = { x: e.clientX, y: e.clientY };
      this.controls.autoRotate = false;
    });
    this.renderer.domElement.addEventListener("pointerup", (e) => {
      if (
        !this.enabled ||
        !down ||
        Math.hypot(e.clientX - down.x, e.clientY - down.y) > 7
      )
        return;
      const rect = this.renderer.domElement.getBoundingClientRect();
      mouse.set(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        (-(e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      ray.setFromCamera(mouse, this.camera);
      const hit = ray.intersectObject(this.earth)[0];
      if (hit) {
        const p = hit.point.clone().normalize();
        onPick({
          lat: (Math.asin(p.y) * 180) / Math.PI,
          lng: (Math.atan2(-p.z, p.x) * 180) / Math.PI,
        });
      }
    });
    this.resize = new ResizeObserver(() => {
      const w = host.clientWidth,
        h = host.clientHeight;
      this.renderer.setSize(w, h);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    });
    this.resize.observe(host);
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }
  clear() {
    this.markers.forEach((o) => {
      this.scene.remove(o);
      o.geometry.dispose();
      o.material.dispose();
    });
    this.markers = [];
  }
  dot(p, color, size = 0.025) {
    if (!this.renderer) return;
    const o = new THREE.Mesh(
      new THREE.SphereGeometry(size, 16, 16),
      new THREE.MeshBasicMaterial({ color, depthTest: false }),
    );
    o.position.copy(vector(p.lat, p.lng, 2.025));
    this.scene.add(o);
    this.markers.push(o);
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(size * 1.5, size * 2.2, 32),
      new THREE.MeshBasicMaterial({
        color,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.5,
        depthTest: false,
      }),
    );
    ring.position.copy(vector(p.lat, p.lng, 2.027));
    ring.lookAt(vector(p.lat, p.lng, 4));
    this.scene.add(ring);
    this.markers.push(ring);
  }
  guess(p) {
    if (!this.renderer) return;
    this.clear();
    this.dot(p, 0xe4f5a0, 0.035);
  }
  reveal(a, b) {
    if (!this.renderer) return;
    this.clear();
    this.dot(a, 0xe4f5a0, 0.035);
    this.dot(b, 0xffffff, 0.04);
    const va = vector(a.lat, a.lng).normalize(),
      vb = vector(b.lat, b.lng).normalize(),
      angle = va.angleTo(vb);
    let axis = new THREE.Vector3().crossVectors(va, vb);
    if (axis.length() < 1e-6) axis.crossVectors(va, new THREE.Vector3(0, 1, 0));
    if (axis.length() < 1e-6) axis.set(1, 0, 0);
    axis.normalize();
    const pts = [];
    for (let i = 0; i <= 80; i++) {
      const t = i / 80;
      pts.push(
        va
          .clone()
          .applyAxisAngle(axis, angle * t)
          .multiplyScalar(2.035 + Math.sin(Math.PI * t) * 0.25),
      );
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({
        color: 0xe4f5a0,
        transparent: true,
        opacity: 0.9,
      }),
    );
    this.scene.add(line);
    this.markers.push(line);
    this.camera.position.copy(vector(b.lat, b.lng, 7.4));
    this.controls.update();
  }
  reset() {
    if (!this.renderer) return;
    this.clear();
    this.camera.position.copy(vector(22, 55, 7.4));
    this.controls.update();
  }
  zoom(factor) {
    if (!this.renderer) return;
    const length = THREE.MathUtils.clamp(
      this.camera.position.length() * factor,
      2.6,
      10,
    );
    this.camera.position.setLength(length);
    this.controls.update();
  }
}
