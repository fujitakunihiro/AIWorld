import * as THREE from 'three';
import type { Resident, VillageState } from '../../../shared/village';
import type { EffectKind } from './effects';
interface Figure { group: THREE.Group; legs: THREE.Mesh[]; arms: THREE.Mesh[]; cargo: THREE.Mesh; target: THREE.Vector3; resident: Resident; label: HTMLElement; speech: HTMLElement }
export class VillageRenderer {
  showBubbles = true;
  onEffect: (kind: EffectKind, position: Resident['position']) => void = () => {};
  private previous?: VillageState;
  private direction = new THREE.Vector3();
  private projected = new THREE.Vector3();
  private reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  private labels = document.getElementById('resident-labels')!;
  private root = new THREE.Group();
  private figures = new Map<string, Figure>();
  private sites = new Map<string, THREE.Group>();
  private nodes = new Map<string, THREE.Group>();
  private fields = new Map<string, { group: THREE.Group; crops: THREE.Group[] }>();
  private cube = new THREE.BoxGeometry(1, 1, 1);
  private materials = new Map<string, THREE.MeshLambertMaterial>();
  private selection = new THREE.Mesh(new THREE.RingGeometry(0.6, 0.72, 24), new THREE.MeshBasicMaterial({ color: '#ffe4a1', side: THREE.DoubleSide, depthWrite: false }));
  private selected: string | null = null;
  constructor(scene: THREE.Scene) { scene.add(this.root); this.root.add(this.selection); this.selection.rotation.x = -Math.PI / 2; this.selection.visible = false; }
  private material(color: string) {
    let material = this.materials.get(color);
    if (!material) { material = new THREE.MeshLambertMaterial({ color }); this.materials.set(color, material); } return material;
  }
  private box(parent: THREE.Object3D, color: string, size: number[], p: number[]) {
    const mesh = new THREE.Mesh(this.cube, this.material(color)); mesh.scale.set(size[0], size[1], size[2]); mesh.position.set(p[0], p[1], p[2]); parent.add(mesh); return mesh;
  }
  private figure(r: Resident): Figure {
    const group = new THREE.Group(); group.userData.residentId = r.id;
    const legs = [-1, 1].map(side => this.box(group, '#334b50', [0.18, 0.52, 0.23], [side * 0.13, 0.27, 0]));
    this.box(group, r.color, [0.48, 0.59, 0.3], [0, 0.82, 0]);
    const arms = [-1, 1].map(side => this.box(group, r.color, [0.17, 0.55, 0.22], [side * 0.34, 0.84, 0]));
    this.box(group, '#efcc9f', [0.44, 0.43, 0.42], [0, 1.34, 0]);
    this.box(group, r.id === 'ren' ? '#5a5148' : '#5b4233', [0.46, 0.14, 0.44], [0, 1.57, 0]);
    for (const side of [-1, 1]) this.box(group, '#324443', [0.055, 0.07, 0.015], [side * 0.095, 1.36, 0.217]);
    const cargo = this.box(group, '#c5a36e', [0.5, 0.45, 0.42], [0, 0.9, 0.43]);
    cargo.visible = false;
    const handle = this.box(arms[1], '#826244', [0.12, 0.7, 0.12], [0, -0.65, 0.5]);
    // Child coordinates use the arm's scaled frame, keeping the tool compact.
    this.box(handle, '#9aa6a5', [2.5, 0.3, 1.3], [0, -0.4, 0]);
    group.position.set(r.position.x, r.position.y, r.position.z); this.root.add(group);
    const label = document.createElement('div'); label.className = 'resident-label';
    const name = document.createElement('strong'); name.textContent = r.name; label.append(name);
    const speech = document.createElement('span'); label.append(speech); this.labels.append(label);
    return { group, legs, arms, cargo, resident: r, target: group.position.clone(), label, speech };
  }
  update(state: VillageState, snap = false) {
    if (!snap && this.previous) {
      for (const bridge of state.bridges) {
        const previous = this.previous.bridges.find(b => b.id === bridge.id), edit = bridge.blocks[Math.max(0, bridge.progress - 1)];
        if (previous && bridge.progress > previous.progress) this.onEffect(bridge.status === 'complete' ? 'complete' : 'build', { x: edit.x + .5, y: edit.y + 1, z: edit.z + .5 });
      }
      for (const hut of state.huts) {
        const previous = this.previous.huts.find(h => h.id === hut.id);
        if (hut.status === 'complete' && previous && previous.status !== 'complete') this.onEffect('complete', { x: hut.x + 2, y: hut.y + 4, z: hut.z + 2 });
        else if (previous && hut.progress > previous.progress) this.onEffect('build', { x: hut.x + 2, y: hut.y + 1, z: hut.z + 4 });
        if (hut.crop?.stage === 'ripe' && previous?.crop?.stage === 'growing') this.onEffect('harvest', { x: hut.x + 2, y: hut.y + 1, z: hut.z + 2 });
      }
      for (const r of state.residents) {
        const previous = this.previous.residents.find(old => old.id === r.id);
        if (!previous) this.onEffect('arrival', r.position);
        else if (r.inventory.food + r.inventory.wood + r.inventory.stone > previous.inventory.food + previous.inventory.wood + previous.inventory.stone) this.onEffect('gather', r.position);
      }
    }
    this.previous = state;
    for (const r of state.residents) {
      let figure = this.figures.get(r.id);
      if (!figure) { figure = this.figure(r); this.figures.set(r.id, figure); }
      figure.resident = r; figure.target.set(r.position.x, r.position.y, r.position.z);
      figure.speech.textContent = r.speech?.text ?? '';
      if (snap || figure.group.position.distanceTo(figure.target) > 6) figure.group.position.copy(figure.target);
      figure.cargo.visible = r.inventory.food + r.inventory.wood + r.inventory.stone > 0;
      figure.cargo.material = this.material(r.inventory.food ? '#cba56c' : r.inventory.stone ? '#8b9a9d' : '#ab7955');
    }
    for (const hut of state.huts) {
      if (this.sites.has(hut.id)) continue;
      const group = new THREE.Group(); group.userData.hutId = hut.id;
      const height = hut.kind === 'farm' ? 0.8 : 4.8;
      const geometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(4.1, height, 4.1));
      const edges = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: '#a8ae77', transparent: true, opacity: 0.4 }));
      edges.position.set(2, height / 2, 2); group.add(edges); group.position.set(hut.x, hut.y, hut.z); this.root.add(group); this.sites.set(hut.id, group);
    }
    for (const hut of state.huts) this.sites.get(hut.id)!.visible = hut.status !== 'complete';
    for (const farm of state.huts.filter(h => h.kind === 'farm')) {
      let field = this.fields.get(farm.id);
      if (!field) {
        const group = new THREE.Group(); group.position.set(farm.x, farm.y, farm.z);
        this.box(group, '#76583d', [3.8, 0.07, 3.8], [2, 0.015, 2]);
        for (let z = 0; z < 3; z++) this.box(group, '#503c2d', [3.4, 0.04, 0.12], [2, 0.07, 0.8 + z * 1.15]);
        const crops: THREE.Group[] = [];
        for (let z = 0; z < 3; z++) for (let x = 0; x < 3; x++) {
          const crop = new THREE.Group(); crop.position.set(1 + x, 0.07, 1 + z);
          this.box(crop, '#83a24d', [0.12, 0.7, 0.12], [0, 0.35, 0]);
          this.box(crop, '#c7bc62', [0.33, 0.24, 0.25], [0, 0.7, 0]);
          this.box(crop, '#8caa52', [0.5, 0.09, 0.14], [0, 0.27, 0]); group.add(crop); crops.push(crop);
        }
        this.root.add(group); field = { group, crops }; this.fields.set(farm.id, field);
      }
      field.group.visible = farm.status === 'complete';
      const crop = farm.crop;
      field.crops.forEach((plant, i) => {
        plant.visible = !!crop && crop.stage !== 'fallow' && (crop.stage !== 'ripe' || i < Math.ceil(crop.remaining / 32 * 9));
        plant.scale.y = 0.2 + (crop?.growth ?? 0) * 0.8;
        (plant.children[1] as THREE.Mesh).material = this.material(crop?.stage === 'ripe' ? '#dec075' : '#8aa45b');
      });
    }
    for (const node of state.nodes) {
      if (node.kind === 'wood') continue; // Existing voxel trees are the wood gathering sites.
      let group = this.nodes.get(node.id);
      if (!group) {
        group = new THREE.Group(); group.position.set(node.position.x, node.position.y, node.position.z);
        if (node.kind === 'stone') {
          this.box(group, '#93a0a0', [0.8, 0.5, 0.65], [0, 0.25, 0]); this.box(group, '#a6b0ac', [0.5, 0.4, 0.6], [0.2, 0.6, 0.05]);
        } else {
          this.box(group, '#609251', [0.8, 0.65, 0.7], [0, 0.33, 0]);
          for (let i = 0; i < 3; i++) this.box(group, '#dca47c', [0.17, 0.17, 0.17], [(i - 1) * 0.22, 0.5, 0.36]);
        }
        this.nodes.set(node.id, group); this.root.add(group);
      }
      group.visible = node.remaining > 0; group.scale.setScalar(node.remaining > 0 ? 0.65 + 0.35 * node.remaining / node.capacity : 1);
    }
  }
  select(id: string | null) { this.selected = id; }
  pick(raycaster: THREE.Raycaster, terrainDistance: number) {
    const hit = raycaster.intersectObjects([...this.figures.values()].map(f => f.group), true)[0];
    if (!hit || hit.distance > terrainDistance + 0.1) return null;
    let object: THREE.Object3D | null = hit.object;
    while (object && !object.userData.residentId) object = object.parent;
    return object?.userData.residentId as string | null;
  }
  frame(now: number, delta: number, paused: boolean, camera: THREE.PerspectiveCamera, radius: number) {
    let bubbles = 0;
    for (const figure of this.figures.values()) {
      const d = this.direction.copy(figure.target).sub(figure.group.position);
      if (Math.hypot(d.x, d.z) > 0.015) figure.group.rotation.y = Math.atan2(d.x, d.z);
      figure.group.position.lerp(figure.target, 1 - Math.exp(-delta * 16));
      const moving = !paused && !this.reduced && figure.resident.action === 'moving';
      const working = !paused && !this.reduced && (figure.resident.action === 'gathering' || figure.resident.action === 'building' || figure.resident.action === 'farming');
      if (working && figure.resident.task) {
        const hut = this.previous?.huts.find(h => h.id === figure.resident.task?.targetId);
        const node = this.previous?.nodes.find(n => n.id === figure.resident.task?.targetId);
        const p = hut ? { x: hut.x + 2, z: hut.z + 2 } : node?.position;
        if (p) figure.group.rotation.y = Math.atan2(p.x - figure.group.position.x, p.z - figure.group.position.z);
      }
      for (let i = 0; i < 2; i++) {
        figure.legs[i].rotation.x = moving ? Math.sin(now / 120 + i * Math.PI) * 0.5 : 0;
        figure.arms[i].rotation.x = working ? -0.7 + Math.sin(now / 180) * 0.55 : moving ? Math.sin(now / 120 + (1 - i) * Math.PI) * 0.35 : 0;
      }
      if (figure.resident.action === 'resting') figure.group.scale.y = 0.75; else figure.group.scale.y = 1;
      const speaking = this.showBubbles && !!figure.resident.speech && radius < 120 && bubbles < 4;
      this.projected.copy(figure.group.position); this.projected.y += 2.15; this.projected.project(camera);
      const visible = (speaking || this.selected === figure.resident.id) && radius < 120 && this.projected.z > -1 && this.projected.z < 1 && Math.abs(this.projected.x) < .93 && Math.abs(this.projected.y) < .9;
      figure.label.hidden = !visible; figure.speech.hidden = !speaking;
      if (visible) { if (speaking) bubbles++; figure.label.style.transform = `translate(-50%, -100%) translate(${(this.projected.x + 1) / 2 * innerWidth}px, ${(1 - this.projected.y) / 2 * innerHeight}px)`; }
    }
    const selected = this.selected ? this.figures.get(this.selected) : null;
    this.selection.visible = !!selected;
    if (selected) { this.selection.position.copy(selected.group.position); this.selection.position.y += .03; }
  }
}
