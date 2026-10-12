import * as THREE from 'three';
import { WorldCamera } from '../camera/controls';
import { Block, CHUNK, SIZE, getBlock, inside, type Edit } from '../../../shared/world';
import type { VillageState } from '../../../shared/village';
import { VillageRenderer } from './village-renderer';
import { WorldEffects } from './effects';
interface WorkerMesh { positions: Float32Array; normals: Float32Array; blocks: Uint8Array; indices: Uint32Array }
const palette: Record<number, string> = { 1: '#85ae62', 2: '#a47a50', 3: '#909a9e', 4: '#e9d39c', 5: '#aa8057', 6: '#548b54', 7: '#77bec7', 8: '#c6886b' };
export class WorldRenderer {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(42, 1, 0.1, 800);
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: WorldCamera;
  readonly village: VillageRenderer;
  readonly effects: WorldEffects;
  quality: 'auto' | 'low' | 'high' = 'auto';
  private worker?: Worker;
  private jobId = 0;
  private jobs = new Map<string, number>();
  private dirty = new Set<string>();
  private pendingEdits: Edit[] = [];
  private slowFrames = 0;
  private ratio = 1;
  private sky = new THREE.Color();
  private nightColor = new THREE.Color('#152c48');
  private dayColor = new THREE.Color('#dfeef0');
  paused = false;
  private lastFrame = performance.now();
  private chunks = new Map<string, THREE.Group>();
  private solid = new THREE.MeshLambertMaterial({ vertexColors: true });
  private water = new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: 0.72, depthWrite: false });
  private sun = new THREE.DirectionalLight('#fff1d8', 2.1);
  private ambient = new THREE.HemisphereLight('#effbff', '#7b875a', 2);
  private clouds = new THREE.Group();
  private raycaster = new THREE.Raycaster();
  private outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.02, 1.02, 1.02)), new THREE.LineBasicMaterial({ color: '#fff5cf' }));
  private data?: Uint8Array;
  private fpsAt = performance.now();
  private frames = 0;
  time = 480;
  onFps: (fps: number) => void = () => {};
  constructor(container: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.ratio = Math.min(devicePixelRatio, window.innerWidth < 700 ? 1.5 : 2); this.renderer.setPixelRatio(this.ratio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);
    this.controls = new WorldCamera(this.camera, this.renderer.domElement); this.controls.home();
    this.village = new VillageRenderer(this.scene);
    this.effects = new WorldEffects(this.scene); this.village.onEffect = (kind, position) => this.effects.emit(kind, position);
    this.scene.background = new THREE.Color('#dfeef0'); this.scene.fog = new THREE.Fog('#dfeef0', 380, 700);
    this.scene.add(this.sun, this.ambient); this.sun.position.set(45, 75, 20);
    this.scene.add(this.outline); this.outline.visible = false;
    const cloudGeo = new THREE.BoxGeometry(1, 1, 1);
    const cloudMat = new THREE.MeshLambertMaterial({ color: '#ffffff', transparent: true, opacity: 0.75 });
    const instanced = new THREE.InstancedMesh(cloudGeo, cloudMat, 48);
    const dummy = new THREE.Object3D();
    for (let i = 0; i < 48; i++) {
      const cluster = Math.floor(i / 8), k = i % 8;
      dummy.position.set(cluster * 22 - 22 + (k % 4) * 2.5, 29 + (cluster % 3) * 3 + (k > 3 ? 1 : 0), (cluster % 3) * 23 + (k > 3 ? 2 : 0));
      dummy.scale.set(4, 1.4, 3); dummy.updateMatrix(); instanced.setMatrixAt(i, dummy.matrix);
    }
    this.clouds.add(instanced); this.scene.add(this.clouds);
    window.addEventListener('resize', () => this.resize()); this.resize();
    document.addEventListener('visibilitychange', () => { this.lastFrame = performance.now(); this.renderer.setAnimationLoop(document.hidden ? null : () => this.frame()); });
    this.renderer.setAnimationLoop(() => this.frame());
  }
  private geometry(mesh: WorkerMesh) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(mesh.normals, 3));
    const colors = new Float32Array(mesh.blocks.length * 3), color = new THREE.Color();
    for (let i = 0; i < mesh.blocks.length; i++) {
      const block = mesh.blocks[i], normalY = mesh.normals[i * 3 + 1];
      color.set(block === Block.Grass && normalY !== 1 ? '#96734d' : palette[block]);
      if (normalY < 0) color.multiplyScalar(0.76);
      colors.set([color.r, color.g, color.b], i * 3);
    }
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); geometry.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
    geometry.computeBoundingSphere(); return geometry;
  }
  setWorld(data: Uint8Array, center = { x: 34, z: 40 }): Promise<void> {
    this.data = data;
    this.worker?.terminate(); this.jobs.clear(); this.dirty.clear(); this.pendingEdits = [];
    for (const group of this.chunks.values()) { group.traverse(o => { if (o instanceof THREE.Mesh) o.geometry.dispose(); }); this.scene.remove(group); } this.chunks.clear();
    this.worker = new Worker(new URL('./mesh-worker.ts', import.meta.url), { type: 'module' });
    const requests: { cx: number; cz: number; id: number }[] = [];
    for (let cz = 0; cz < SIZE / CHUNK; cz++) for (let cx = 0; cx < SIZE / CHUNK; cx++) { const id = ++this.jobId; requests.push({ cx, cz, id }); this.jobs.set(`${cx},${cz}`, id); }
    requests.sort((a, b) => Math.hypot(a.cx * CHUNK + 8 - center.x, a.cz * CHUNK + 8 - center.z) - Math.hypot(b.cx * CHUNK + 8 - center.x, b.cz * CHUNK + 8 - center.z));
    let initial = requests.length;
    const initialIds = new Set(requests.map(r => r.id));
    const ready = new Promise<void>((resolve, reject) => {
      this.worker!.onerror = () => reject(new Error('地形を描画できませんでした。ページを再読み込みしてください。'));
      this.worker!.onmessage = (event: MessageEvent<{ cx: number; cz: number; id: number; solid: WorkerMesh; water: WorkerMesh }>) => {
        const { cx, cz, id, solid, water } = event.data;
        if (this.jobs.get(`${cx},${cz}`) === id) this.applyChunk(cx, cz, { solid, water });
        if (initialIds.delete(id) && --initial === 0) resolve();
      };
    });
    const copy = data.slice(); this.worker.postMessage({ data: copy, requests }, [copy.buffer]); return ready;
  }
  rebuild(cx: number, cz: number) {
    if (!this.data || cx < 0 || cz < 0 || cx >= SIZE / CHUNK || cz >= SIZE / CHUNK) return;
    this.dirty.add(`${cx},${cz}`);
  }
  private applyChunk(cx: number, cz: number, result: { solid: WorkerMesh; water: WorkerMesh }) {
    const key = `${cx},${cz}`, old = this.chunks.get(key);
    if (old) { old.traverse(o => { if (o instanceof THREE.Mesh) o.geometry.dispose(); }); this.scene.remove(old); }
    const group = new THREE.Group(); group.userData.cx = cx; group.userData.cz = cz;
    for (const [kind, mesh] of Object.entries(result)) {
      if (!mesh.indices.length) continue;
      const object = new THREE.Mesh(this.geometry(mesh), kind === 'solid' ? this.solid : this.water);
      object.userData.solid = kind === 'solid'; group.add(object);
    }
    this.chunks.set(key, group); this.scene.add(group);
  }
  changed(edit: Edit) {
    this.pendingEdits.push(edit);
    const cx = Math.floor(edit.x / CHUNK), cz = Math.floor(edit.z / CHUNK);
    this.rebuild(cx, cz);
    if (edit.x % CHUNK === 0) this.rebuild(cx - 1, cz);
    if (edit.x % CHUNK === CHUNK - 1) this.rebuild(cx + 1, cz);
    if (edit.z % CHUNK === 0) this.rebuild(cx, cz - 1);
    if (edit.z % CHUNK === CHUNK - 1) this.rebuild(cx, cz + 1);
  }
  changedBatch(edits: Edit[]) {
    this.pendingEdits.push(...edits);
    for (const edit of edits.slice(-12)) if (edit.block !== Block.Air) this.effects.block(edit, palette[edit.block]);
    const chunks = new Set<string>();
    for (const edit of edits) {
      const cx = Math.floor(edit.x / CHUNK), cz = Math.floor(edit.z / CHUNK); chunks.add(`${cx},${cz}`);
      if (edit.x % CHUNK === 0) chunks.add(`${cx - 1},${cz}`);
      if (edit.x % CHUNK === CHUNK - 1) chunks.add(`${cx + 1},${cz}`);
      if (edit.z % CHUNK === 0) chunks.add(`${cx},${cz - 1}`);
      if (edit.z % CHUNK === CHUNK - 1) chunks.add(`${cx},${cz + 1}`);
    }
    for (const key of chunks) { const [x, z] = key.split(',').map(Number); this.rebuild(x, z); }
  }
  setQuality(quality: 'auto' | 'low' | 'high') {
    this.quality = quality; this.slowFrames = 0;
    this.ratio = quality === 'low' ? 1 : Math.min(devicePixelRatio, window.innerWidth < 700 ? 1.5 : 2); this.renderer.setPixelRatio(this.ratio); this.resize();
  }
  focusVillage(state: VillageState, residentId?: string) {
    const p = state.residents.find(r => r.id === residentId)?.position ?? state.camp;
    this.controls.target.set(p.x, p.y, p.z);
    if (!residentId && state.huts.length) {
      const points = [state.camp, ...state.huts.map(h => ({ x: h.x + 2, y: h.y + 1, z: h.z + 2 }))];
      this.controls.target.set((Math.min(...points.map(p => p.x)) + Math.max(...points.map(p => p.x))) / 2,
        Math.max(...points.map(p => p.y)), (Math.min(...points.map(p => p.z)) + Math.max(...points.map(p => p.z))) / 2);
    }
    this.controls.orbit.radius = residentId ? (window.innerWidth < 700 ? 43 : 28) : (window.innerWidth < 700 ? 68 : 48);
    this.controls.update();
  }
  pickResident(clientX: number, clientY: number) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.raycaster.setFromCamera(new THREE.Vector2((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1), this.camera);
    const meshes = [...this.chunks.values()].filter(group => group.visible).flatMap(group => group.children.filter(mesh => mesh.userData.solid));
    const terrain = this.raycaster.intersectObjects(meshes, false)[0];
    return this.village.pick(this.raycaster, terrain?.distance ?? Infinity);
  }
  pick(clientX: number, clientY: number, place: boolean) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.raycaster.setFromCamera(new THREE.Vector2((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1), this.camera);
    const meshes: THREE.Object3D[] = [];
    for (const group of this.chunks.values()) if (group.visible) for (const mesh of group.children) if (mesh.userData.solid) meshes.push(mesh);
    const hit = this.raycaster.intersectObjects(meshes, false)[0];
    if (!hit?.face || !this.data) return null;
    const p = hit.point.clone().addScaledVector(hit.face.normal, place ? 0.01 : -0.01);
    const x = Math.floor(p.x), y = Math.floor(p.y), z = Math.floor(p.z);
    if (!inside(x, y, z)) return null;
    return { x, y, z, block: getBlock(this.data, x, y, z) };
  }
  highlight(position: { x: number; y: number; z: number } | null, remove = false) {
    this.outline.visible = !!position;
    if (position) this.outline.position.set(position.x + 0.5, position.y + 0.5, position.z + 0.5);
    (this.outline.material as THREE.LineBasicMaterial).color.set(remove ? '#fa826e' : '#fff5cf');
  }
  private resize() {
    this.camera.fov = window.innerWidth < 700 ? 50 : 42;
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.setViewOffset(window.innerWidth, window.innerHeight, 0, window.innerWidth < 700 ? 0 : window.innerHeight * .08, window.innerWidth, window.innerHeight); this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }
  private frame() {
    const now = performance.now(), hour = (this.time % 1440) / 60;
    const delta = Math.min(0.1, (now - this.lastFrame) / 1000);
    this.village.frame(now, delta, this.paused, this.camera, this.controls.orbit.radius); this.effects.frame(delta, this.paused); this.lastFrame = now;
    if (this.dirty.size && this.worker) {
      const requests = [...this.dirty].map(key => { const [cx, cz] = key.split(',').map(Number), id = ++this.jobId; this.jobs.set(key, id); return { cx, cz, id }; });
      this.worker.postMessage({ edits: this.pendingEdits, requests }); this.dirty.clear(); this.pendingEdits = [];
    }
    const light = Math.max(0.12, Math.sin((hour - 6) / 24 * Math.PI * 2));
    this.sun.intensity = light * 2.1; this.ambient.intensity = 0.6 + light * 1.4;
    this.sky.copy(this.nightColor).lerp(this.dayColor, light);
    (this.scene.background as THREE.Color).copy(this.sky); (this.scene.fog as THREE.Fog).color.copy(this.sky);
    this.clouds.position.x = Math.sin(now / 90000) * 10;
    this.water.opacity = 0.68 + Math.sin(now / 1800) * 0.035;
    // Frustum culling is enabled on each mesh; mobile limits distant chunks as well.
    const mobile = window.innerWidth < 700;
    for (const group of this.chunks.values()) {
      const { cx, cz } = group.userData;
      group.visible = !(mobile || this.quality === 'low') || Math.hypot(cx * CHUNK + 8 - this.controls.target.x, cz * CHUNK + 8 - this.controls.target.z) < Math.max(44, this.controls.orbit.radius * 0.8);
    }
    this.renderer.render(this.scene, this.camera); this.frames++;
    if (now - this.fpsAt > 1000) {
      const fps = Math.round(this.frames * 1000 / (now - this.fpsAt)); this.onFps(fps);
      this.slowFrames = fps < 30 ? this.slowFrames + 1 : 0;
      if (this.quality === 'auto' && this.slowFrames >= 4 && this.ratio > 1) { this.ratio = Math.max(1, this.ratio - .25); this.renderer.setPixelRatio(this.ratio); this.resize(); this.slowFrames = 0; }
      this.frames = 0; this.fpsAt = now;
    }
  }
}
