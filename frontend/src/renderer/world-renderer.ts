import * as THREE from 'three';
import { WorldCamera } from '../camera/controls';
import { Block, CHUNK, SIZE, getBlock, inside, type Edit } from '../../../shared/world';
import { meshChunk, type MeshData } from '../../../shared/mesher';
const palette: Record<number, string> = { 1: '#85ae62', 2: '#a47a50', 3: '#909a9e', 4: '#e9d39c', 5: '#aa8057', 6: '#548b54', 7: '#77bec7', 8: '#c6886b' };
export class WorldRenderer {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: WorldCamera;
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
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, window.innerWidth < 700 ? 1.5 : 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);
    this.controls = new WorldCamera(this.camera, this.renderer.domElement); this.controls.home();
    this.scene.background = new THREE.Color('#dfeef0'); this.scene.fog = new THREE.Fog('#dfeef0', 190, 360);
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
    this.renderer.setAnimationLoop(() => this.frame());
  }
  private geometry(mesh: MeshData) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(mesh.normals, 3));
    const colors: number[] = [];
    for (let i = 0; i < mesh.blocks.length; i++) {
      const block = mesh.blocks[i], normalY = mesh.normals[i * 3 + 1];
      const color = new THREE.Color(block === Block.Grass && normalY !== 1 ? '#96734d' : palette[block]);
      if (normalY < 0) color.multiplyScalar(0.76);
      colors.push(color.r, color.g, color.b);
    }
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); geometry.setIndex(mesh.indices);
    geometry.computeBoundingSphere(); return geometry;
  }
  setWorld(data: Uint8Array) {
    this.data = data;
    for (let z = 0; z < SIZE / CHUNK; z++) for (let x = 0; x < SIZE / CHUNK; x++) this.rebuild(x, z);
  }
  rebuild(cx: number, cz: number) {
    if (!this.data || cx < 0 || cz < 0 || cx >= SIZE / CHUNK || cz >= SIZE / CHUNK) return;
    const key = `${cx},${cz}`, old = this.chunks.get(key);
    if (old) { old.traverse(o => { if (o instanceof THREE.Mesh) o.geometry.dispose(); }); this.scene.remove(old); }
    const group = new THREE.Group(), result = meshChunk(this.data, cx, cz);
    for (const [kind, mesh] of Object.entries(result)) {
      if (!mesh.indices.length) continue;
      const object = new THREE.Mesh(this.geometry(mesh), kind === 'solid' ? this.solid : this.water);
      object.userData.solid = kind === 'solid'; group.add(object);
    }
    this.chunks.set(key, group); this.scene.add(group);
  }
  changed(edit: Edit) {
    const cx = Math.floor(edit.x / CHUNK), cz = Math.floor(edit.z / CHUNK);
    this.rebuild(cx, cz);
    if (edit.x % CHUNK === 0) this.rebuild(cx - 1, cz);
    if (edit.x % CHUNK === CHUNK - 1) this.rebuild(cx + 1, cz);
    if (edit.z % CHUNK === 0) this.rebuild(cx, cz - 1);
    if (edit.z % CHUNK === CHUNK - 1) this.rebuild(cx, cz + 1);
  }
  pick(clientX: number, clientY: number, place: boolean) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.raycaster.setFromCamera(new THREE.Vector2((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1), this.camera);
    const meshes: THREE.Object3D[] = [];
    for (const group of this.chunks.values()) for (const mesh of group.children) if (mesh.userData.solid) meshes.push(mesh);
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
    this.camera.aspect = window.innerWidth / window.innerHeight; this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }
  private frame() {
    const now = performance.now(), hour = (this.time % 1440) / 60;
    const light = Math.max(0.12, Math.sin((hour - 6) / 24 * Math.PI * 2));
    this.sun.intensity = light * 2.1; this.ambient.intensity = 0.6 + light * 1.4;
    const sky = new THREE.Color('#152c48').lerp(new THREE.Color('#dfeef0'), light);
    (this.scene.background as THREE.Color).copy(sky); (this.scene.fog as THREE.Fog).color.copy(sky);
    this.clouds.position.x = Math.sin(now / 90000) * 10;
    this.water.opacity = 0.68 + Math.sin(now / 1800) * 0.035;
    // Frustum culling is enabled on each mesh; mobile limits distant chunks as well.
    const mobile = window.innerWidth < 700;
    for (const [key, group] of this.chunks) {
      const [cx, cz] = key.split(',').map(Number);
      group.visible = !mobile || Math.hypot(cx * CHUNK + 8 - this.controls.target.x, cz * CHUNK + 8 - this.controls.target.z) < Math.max(38, this.controls.orbit.radius * 0.8);
    }
    this.renderer.render(this.scene, this.camera); this.frames++;
    if (now - this.fpsAt > 1000) { this.onFps(Math.round(this.frames * 1000 / (now - this.fpsAt))); this.frames = 0; this.fpsAt = now; }
  }
}
