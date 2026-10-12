import * as THREE from 'three';
import { WorldCamera } from '../camera/controls';
import { Block, CHUNK, EIFFEL, SIZE, getBlock, inside, type Edit } from '../../../shared/world';
import type { Resident, VillageState } from '../../../shared/village';
import { VillageRenderer } from './village-renderer';
import { WorldEffects } from './effects';
import { DioramaEnvironment } from './environment';
import { DioramaPostProcessing } from './post-processing';
import { WorldModels } from './world-models';
import { QUALITY_PROFILES, effectiveQuality, lightingAt, previewMinute, summarizeFrames, type GraphicsSettings, type QualityProfile, type RenderMetrics, type Benchmark } from './graphics';
interface WorkerMesh { positions: Float32Array; normals: Float32Array; blocks: Uint8Array; indices: Uint32Array }
const palette: Record<number, string> = { 1: '#85ae62', 2: '#a47a50', 3: '#909a9e', 4: '#e9d39c', 5: '#aa8057', 6: '#548b54', 7: '#77bec7', 8: '#c6886b' };
const dioramaPalette: Record<number, string> = { 1: '#8caa6a', 2: '#a28a69', 3: '#969c95', 4: '#e4d1a0', 5: '#a88560', 6: '#628657', 7: '#ffffff', 8: '#bd927b' };
export class WorldRenderer {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(42, 1, 0.1, 2200);
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: WorldCamera;
  readonly village: VillageRenderer;
  readonly effects: WorldEffects;
  settings: GraphicsSettings = { style: 'diorama', quality: 'auto', shadows: true, ao: true, distance: 'standard', preview: 'world', grass: 'lush' };
  private models: WorldModels;
  private following: string | null = null;
  private followTarget = new THREE.Vector3();
  onFollow: (resident: Resident | null) => void = () => {};
  private editing = false;
  private hidden: number[] = [];
  private environment: DioramaEnvironment;
  private post?: DioramaPostProcessing;
  private profile: QualityProfile = QUALITY_PROFILES.high;
  private downgrade = 0;
  private profileKey = '';
  private postUnavailable = false;
  private gpu = '';
  private durations: number[] = [];
  private cpuTimes: number[] = [];
  private benchmark?: { durations: number[]; cpu: number[]; warmupUntil: number; elapsed: number };
  private shadowAt = 0;
  private lastShadowKey = '';
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
  onMetrics: (metrics: RenderMetrics) => void = () => {};
  onBenchmark: (result: Benchmark | null) => void = () => {};
  onGraphicNotice: (text: string) => void = () => {};
  constructor(container: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.ratio = Math.min(devicePixelRatio, window.innerWidth < 700 ? 1.5 : 2); this.renderer.setPixelRatio(this.ratio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.info.autoReset = false;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap; this.renderer.shadowMap.autoUpdate = false;
    const gl = this.renderer.getContext(), debug = gl.getExtension('WEBGL_debug_renderer_info');
    this.gpu = debug ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : 'WebGL 2（GPU名は非公開）';
    this.postUnavailable = !this.renderer.extensions.has('EXT_color_buffer_float');
    container.appendChild(this.renderer.domElement);
    this.controls = new WorldCamera(this.camera, this.renderer.domElement); this.controls.home();
    this.controls.onPan = () => this.stopFollowing();
    this.village = new VillageRenderer(this.scene);
    this.models = new WorldModels(this.scene);
    this.effects = new WorldEffects(this.scene); this.village.onEffect = (kind, position) => this.effects.emit(kind, position);
    this.scene.background = new THREE.Color('#dfeef0'); this.scene.fog = new THREE.Fog('#dfeef0', 380, 700);
    this.scene.add(this.sun, this.ambient); this.sun.position.set(45, 75, 20);
    this.environment = new DioramaEnvironment(this.scene, this.sun, this.ambient);
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
    this.clouds.userData.skipAO = true; this.outline.userData.skipAO = true;
    window.addEventListener('resize', () => { if (this.benchmark) { this.benchmark = undefined; this.onBenchmark(null); } this.configureGraphics(); }); this.resize();
    document.addEventListener('visibilitychange', () => { this.lastFrame = performance.now(); this.durations = []; this.cpuTimes = []; if (this.benchmark) { this.benchmark = undefined; this.onBenchmark(null); } this.renderer.setAnimationLoop(document.hidden ? null : () => this.frame()); });
    this.configureGraphics();
    this.renderer.setAnimationLoop(() => this.frame());
  }
  private geometry(mesh: WorkerMesh) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(mesh.normals, 3));
    const colors = new Float32Array(mesh.blocks.length * 3), warmColors = new Float32Array(colors.length), color = new THREE.Color();
    for (let i = 0; i < mesh.blocks.length; i++) {
      const block = mesh.blocks[i], normalY = mesh.normals[i * 3 + 1];
      color.set(block === Block.Grass && normalY !== 1 ? '#96734d' : palette[block]);
      if (normalY < 0) color.multiplyScalar(0.76);
      colors.set([color.r, color.g, color.b], i * 3);
      color.set(block === Block.Grass && normalY !== 1 ? '#a28a69' : dioramaPalette[block]);
      if (normalY < 0) color.multiplyScalar(.8);
      warmColors.set([color.r, color.g, color.b], i * 3);
    }
    // Keep both palettes as owned attributes so disposing an edited chunk releases both GPU buffers.
    geometry.setAttribute('classicColor', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setAttribute('dioramaColor', new THREE.Float32BufferAttribute(warmColors, 3));
    geometry.setAttribute('color', geometry.getAttribute(`${this.settings.style}Color`)); geometry.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
    geometry.computeBoundingSphere(); return geometry;
  }
  setWorld(data: Uint8Array, center = { x: 34, z: 40 }, state?: VillageState): Promise<void> {
    this.data = data;
    this.models.world(data); if (state) this.models.update(state);
    this.hidden = this.models.refresh()?.hidden ?? [];
    this.environment.world(data);
    this.worker?.terminate(); this.jobs.clear(); this.dirty.clear(); this.pendingEdits = [];
    for (const group of this.chunks.values()) { group.traverse(o => { if (o instanceof THREE.Mesh) o.geometry.dispose(); }); this.scene.remove(group); } this.chunks.clear();
    this.worker = new Worker(new URL('./mesh-worker.ts', import.meta.url), { type: 'module' });
    const requests: { cx: number; cz: number; id: number }[] = [];
    for (let cz = 0; cz < SIZE / CHUNK; cz++) for (let cx = 0; cx < SIZE / CHUNK; cx++) { const id = ++this.jobId; requests.push({ cx, cz, id }); this.jobs.set(`${cx},${cz}`, id); }
    requests.sort((a, b) => Math.hypot(a.cx * CHUNK + CHUNK / 2 - center.x, a.cz * CHUNK + CHUNK / 2 - center.z) - Math.hypot(b.cx * CHUNK + CHUNK / 2 - center.x, b.cz * CHUNK + CHUNK / 2 - center.z));
    // Let the nearby streets appear first; distant sectors continue streaming in.
    const initialIds = new Set(requests.slice(0, Math.min(80, requests.length)).map(r => r.id));
    let initial = initialIds.size;
    const ready = new Promise<void>((resolve, reject) => {
      this.worker!.onerror = () => reject(new Error('地形を描画できませんでした。ページを再読み込みしてください。'));
      this.worker!.onmessage = (event: MessageEvent<{ cx: number; cz: number; id: number; solid: WorkerMesh; water: WorkerMesh; diorama: WorkerMesh }>) => {
        const { cx, cz, id, solid, water, diorama } = event.data;
        if (this.jobs.get(`${cx},${cz}`) === id) this.applyChunk(cx, cz, { solid, water, diorama });
        if (initialIds.delete(id) && --initial === 0) resolve();
      };
    });
    const copy = data.slice(); this.worker.postMessage({ data: copy, requests, hidden: this.hidden }, [copy.buffer]); return ready;
  }
  updateVillage(state: VillageState, snap = false) {
    this.village.update(state, snap); this.models.update(state);
    if (this.following) {
      const r = state.residents.find(r => r.id === this.following);
      if (r) this.onFollow(r); else this.stopFollowing();
    }
  }
  stopFollowing() { if (this.following) { this.following = null; this.renderer.shadowMap.needsUpdate = true; this.onFollow(null); } }
  rebuild(cx: number, cz: number) {
    if (!this.data || cx < 0 || cz < 0 || cx >= SIZE / CHUNK || cz >= SIZE / CHUNK) return;
    this.dirty.add(`${cx},${cz}`);
  }
  private applyChunk(cx: number, cz: number, result: { solid: WorkerMesh; water: WorkerMesh; diorama: WorkerMesh }) {
    const key = `${cx},${cz}`, old = this.chunks.get(key);
    if (old) { old.traverse(o => { if (o instanceof THREE.Mesh) o.geometry.dispose(); }); this.scene.remove(old); }
    const group = new THREE.Group(); group.userData.cx = cx; group.userData.cz = cz;
    for (const [kind, mesh] of Object.entries(result)) {
      if (!mesh.indices.length) continue;
      const object = new THREE.Mesh(this.geometry(mesh), this.material(kind !== 'water'));
      object.castShadow = object.receiveShadow = kind !== 'water'; object.userData.skipAO = kind === 'water';
      object.userData.solid = kind === 'solid'; object.userData.kind = kind; group.add(object);
    }
    this.chunks.set(key, group); this.scene.add(group);
    this.syncChunkStyle(group);
    this.renderer.shadowMap.needsUpdate = true;
  }
  changed(edit: Edit) {
    this.models.terrain();
    if (this.data) this.environment.edits(this.data, [edit]);
    this.pendingEdits.push(edit);
    const cx = Math.floor(edit.x / CHUNK), cz = Math.floor(edit.z / CHUNK);
    this.rebuild(cx, cz);
    if (edit.x % CHUNK === 0) this.rebuild(cx - 1, cz);
    if (edit.x % CHUNK === CHUNK - 1) this.rebuild(cx + 1, cz);
    if (edit.z % CHUNK === 0) this.rebuild(cx, cz - 1);
    if (edit.z % CHUNK === CHUNK - 1) this.rebuild(cx, cz + 1);
  }
  changedBatch(edits: Edit[]) {
    this.models.terrain();
    if (this.data) this.environment.edits(this.data, edits);
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
  private material(solid: boolean) { return this.settings.style === 'classic' ? (solid ? this.solid : this.water) : (solid ? this.environment.solid : this.environment.water); }
  private syncChunkStyle(group: THREE.Group) {
    const classic = this.settings.style === 'classic' || this.editing;
    for (const object of group.children) if (object instanceof THREE.Mesh) {
      const kind = object.userData.kind;
      object.visible = kind === 'water' || (classic ? kind === 'solid' : kind === 'diorama');
      object.material = this.material(kind !== 'water');
      object.geometry.setAttribute('color', object.geometry.getAttribute(`${this.settings.style}Color`));
    }
  }
  setEditing(editing: boolean) {
    if (editing) this.stopFollowing();
    if (editing === this.editing) return;
    this.editing = editing; this.models.setEditing(editing);
    this.village.setGraphicStyle(editing ? 'classic' : this.settings.style);
    for (const group of this.chunks.values()) this.syncChunkStyle(group);
    this.renderer.shadowMap.needsUpdate = true;
  }
  setGraphics(settings: GraphicsSettings) {
    const styleChanged = settings.style !== this.settings.style;
    const changed = JSON.stringify(settings) !== JSON.stringify(this.settings);
    if (changed && this.benchmark) { this.benchmark = undefined; this.onBenchmark(null); }
    this.settings = settings; this.slowFrames = 0; this.downgrade = 0;
    if (styleChanged) {
      for (const group of this.chunks.values()) this.syncChunkStyle(group);
      this.village.setGraphicStyle(this.editing ? 'classic' : settings.style);
    }
    this.configureGraphics();
  }
  private configureGraphics() {
    const effective = effectiveQuality(this.settings.quality, innerWidth < 700, this.downgrade);
    this.profile = QUALITY_PROFILES[effective];
    this.models.configure(this.settings, this.profile);
    const remake = this.settings.style === 'diorama';
    this.ratio = Math.min(devicePixelRatio, this.profile.pixelRatio); this.renderer.setPixelRatio(this.ratio);
    this.renderer.toneMapping = remake ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
    this.renderer.toneMappingExposure = remake ? 1.04 : 1;
    this.renderer.shadowMap.enabled = remake && this.settings.shadows && this.profile.shadowSize > 0;
    this.environment.shadow(this.profile, this.renderer.shadowMap.enabled); this.renderer.shadowMap.needsUpdate = true;
    const usePost = remake && this.settings.ao && this.profile.aoScale > 0 && !this.postUnavailable;
    if (remake && this.settings.ao && this.profile.aoScale > 0 && this.postUnavailable) this.onGraphicNotice('この端末では AO を利用できないため、光と影だけで描画します。');
    const key = `${effective}:${usePost}`;
    if (key !== this.profileKey) {
      this.post?.dispose(); this.post = undefined; this.profileKey = key;
      if (usePost) {
        try { this.post = new DioramaPostProcessing(this.renderer, this.scene, this.camera, this.profile); }
        catch (error) { this.postUnavailable = true; this.onGraphicNotice('この端末では AO を無効にして描画します。'); console.warn('AO unavailable', error); }
      }
    }
    this.durations = []; this.cpuTimes = []; this.resize();
  }
  measure() { this.benchmark = { durations: [], cpu: [], warmupUntil: performance.now() + 1000, elapsed: 0 }; }
  focusVillage(state: VillageState, residentId?: string) {
    this.stopFollowing();
    const resident = state.residents.find(r => r.id === residentId);
    if (resident) { this.following = resident.id; this.village.select(resident.id); this.onFollow(resident); }
    const p = state.residents.find(r => r.id === residentId)?.position ?? state.camp;
    this.controls.target.set(p.x, p.y + (residentId ? .75 : 0), p.z);
    if (!residentId && state.huts.length) {
      const points = [state.camp, ...state.huts.map(h => ({ x: h.x + 2, y: h.y + 1, z: h.z + 2 }))];
      this.controls.target.set((Math.min(...points.map(p => p.x)) + Math.max(...points.map(p => p.x))) / 2,
        Math.max(...points.map(p => p.y)), (Math.min(...points.map(p => p.z)) + Math.max(...points.map(p => p.z))) / 2);
    }
    this.controls.orbit.radius = residentId ? (window.innerWidth < 700 ? 24 : 16) : (window.innerWidth < 700 ? 68 : 48);
    this.controls.update();
  }
  focusContinent() {
    this.stopFollowing(); this.controls.target.set(EIFFEL.x, EIFFEL.y + EIFFEL.height * .42, EIFFEL.z);
    this.controls.orbit.set(innerWidth < 700 ? 78 : 55, .98, .68); this.controls.update();
  }
  focusParis() {
    this.stopFollowing(); this.controls.target.set(250, 12, 132);
    this.controls.orbit.set(innerWidth < 700 ? 285 : 180, .92, .52); this.controls.update();
  }
  pickResident(clientX: number, clientY: number) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.raycaster.setFromCamera(new THREE.Vector2((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1), this.camera);
    const diorama = this.settings.style === 'diorama' && !this.editing;
    const meshes = [...this.chunks.values()].filter(group => group.visible).flatMap(group => group.children.filter(mesh => diorama ? mesh.userData.kind === 'diorama' : mesh.userData.solid));
    if (diorama) meshes.push(...this.models.occluders());
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
    this.camera.clearViewOffset(); this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.post?.resize(this.profile);
    this.renderer.shadowMap.needsUpdate = true;
  }
  private frame() {
    const now = performance.now(), frameMs = now - this.lastFrame;
    const visualTime = previewMinute(this.settings.preview, this.time), hour = (visualTime % 1440) / 60;
    const delta = Math.min(0.1, frameMs / 1000);
    this.village.frame(now, delta, this.paused, this.camera, this.controls.orbit.radius); this.effects.frame(delta, this.paused); this.lastFrame = now;
    const follow = this.following ? this.village.position(this.following) : undefined;
    if (follow) {
      this.followTarget.copy(follow); this.followTarget.y += .9;
      this.controls.target.lerp(this.followTarget, 1 - Math.exp(-delta * 8)); this.controls.update();
    }
    const presentation = this.models.refresh();
    if (presentation) {
      this.hidden = presentation.hidden;
      for (const key of presentation.chunks) { const [cx, cz] = key.split(',').map(Number); this.rebuild(cx, cz); }
    }
    if (this.dirty.size && this.worker) {
      const requests = [...this.dirty].map(key => { const [cx, cz] = key.split(',').map(Number), id = ++this.jobId; this.jobs.set(key, id); return { cx, cz, id }; });
      this.worker.postMessage({ edits: this.pendingEdits, requests, hidden: this.hidden }); this.dirty.clear(); this.pendingEdits = [];
    }
    if (this.settings.style === 'classic') {
      const light = Math.max(0.12, Math.sin((hour - 6) / 24 * Math.PI * 2));
      this.sun.position.set(45, 75, 20); this.sun.target.position.set(0, 0, 0); this.sun.color.set('#fff1d8');
      this.ambient.color.set('#effbff'); this.ambient.groundColor.set('#7b875a');
      this.sun.intensity = light * 2.1; this.ambient.intensity = 0.6 + light * 1.4;
      this.sky.copy(this.nightColor).lerp(this.dayColor, light);
    } else {
      this.renderer.toneMappingExposure = lightingAt(visualTime).exposure;
    }
    this.environment.frame(visualTime, now, this.camera, this.controls.target, this.controls.orbit.radius, this.settings);
    if (this.settings.style === 'diorama') this.sky.copy(this.environment.horizon);
    (this.scene.background as THREE.Color).copy(this.sky); (this.scene.fog as THREE.Fog).color.copy(this.sky);
    this.clouds.position.x = Math.sin(now / 90000) * 10;
    this.water.opacity = 0.68 + Math.sin(now / 1800) * 0.035;
    // Frustum culling is enabled on each mesh; mobile limits distant chunks as well.
    const distance = this.settings.distance === 'far' ? SIZE * 2 : this.settings.distance === 'near' ? 44 : this.profile.distance;
    const fog = this.scene.fog as THREE.Fog; fog.near = Math.max(180, this.controls.orbit.radius * .9 + 100); fog.far = Math.max(700, this.controls.orbit.radius + SIZE * 2);
    this.models.frame(this.controls.target, this.controls.orbit.radius, distance, visualTime, delta, this.paused, follow);
    for (const group of this.chunks.values()) {
      const { cx, cz } = group.userData;
      // Match the 32×32 nature sectors so a visible tree always has its terrain below it.
      const sectorSize = CHUNK, x = cx * sectorSize + sectorSize / 2, z = cz * sectorSize + sectorSize / 2;
      group.visible = Math.hypot(x - this.controls.target.x, z - this.controls.target.z) < Math.max(distance, this.controls.orbit.radius * .8) + sectorSize;
    }
    this.renderer.info.reset();
    // Paused scenes keep their shadow map until the camera or lighting changes.
    const shadowKey = `${Math.round(this.camera.position.x * 10)}:${Math.round(this.camera.position.y * 10)}:${Math.round(this.camera.position.z * 10)}:${Math.floor(visualTime)}`;
    if (this.renderer.shadowMap.enabled && now - this.shadowAt > (this.profile.shadowSize < 2048 ? 100 : 66) && (!this.paused || shadowKey !== this.lastShadowKey)) { this.renderer.shadowMap.needsUpdate = true; this.shadowAt = now; this.lastShadowKey = shadowKey; }
    if (this.post) this.post.render(delta); else this.renderer.render(this.scene, this.camera);
    this.frames++;
    const cpuMs = performance.now() - now;
    this.durations.push(frameMs); this.cpuTimes.push(cpuMs);
    if (this.durations.length > 300) { this.durations.shift(); this.cpuTimes.shift(); }
    if (this.benchmark && now >= this.benchmark.warmupUntil) {
      this.benchmark.durations.push(frameMs); this.benchmark.cpu.push(cpuMs);
      this.benchmark.elapsed += frameMs;
      if (this.benchmark.elapsed >= 10_000) {
        const result = summarizeFrames(this.benchmark.durations, this.benchmark.cpu); this.benchmark = undefined;
        this.onBenchmark({ ...result, metrics: this.metrics() });
      }
    }
    if (now - this.fpsAt > 1000) {
      const fps = Math.round(this.frames * 1000 / (now - this.fpsAt)); this.onFps(fps);
      this.onMetrics(this.metrics());
      this.slowFrames = fps < (innerWidth < 700 ? 28 : 50) ? this.slowFrames + 1 : 0;
      if (!this.benchmark && this.settings.quality === 'auto' && this.slowFrames >= 4 && this.downgrade < 2) {
        this.downgrade++; this.configureGraphics(); this.slowFrames = 0;
        this.onGraphicNotice('描画負荷に合わせて、品質を軽くしました。');
      }
      this.frames = 0; this.fpsAt = now;
    }
  }
  private metrics(): RenderMetrics {
    const sample = summarizeFrames(this.durations, this.cpuTimes), info = this.renderer.info;
    return { fps: sample.fps, frameP95: sample.frameP95, cpuMs: sample.cpuMs, calls: info.render.calls, triangles: info.render.triangles,
      geometries: info.memory.geometries, textures: info.memory.textures, width: this.renderer.domElement.width, height: this.renderer.domElement.height,
      ratio: this.ratio, gpu: this.gpu, effectiveQuality: effectiveQuality(this.settings.quality, innerWidth < 700, this.downgrade),
      post: !!this.post, shadowSize: this.renderer.shadowMap.enabled ? this.profile.shadowSize : 0, style: this.settings.style };
  }
}
