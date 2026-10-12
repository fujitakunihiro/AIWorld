import * as THREE from 'three';
import { CHUNK, SIZE, getBlock } from '../../../shared/world';
import type { VillageState } from '../../../shared/village';
import type { GraphicStyle, QualityProfile, GraphicsSettings } from './graphics';
import { ModelKit, type ModelPart } from './model-kit';
import { planModels, bridgeEdges, type ModelPlan } from './model-plan';

export class WorldModels {
  readonly root = new THREE.Group();
  private kit = new ModelKit();
  private sectors = new Map<string, THREE.Group>();
  private structures = new Map<string, { key: string; group: THREE.Group }>();
  private data?: Uint8Array;
  private state?: VillageState;
  private plan?: ModelPlan;
  private topology = '';
  private dirty = false;
  private hidden = new Set<number>();
  private density = 1;
  private editing = false;
  private style: GraphicStyle = 'diorama';
  private profile?: QualityProfile;
  constructor(scene: THREE.Scene) { scene.add(this.root); }
  world(data: Uint8Array) {
    this.data = data; this.state = undefined; this.topology = ''; this.dirty = true;
    for (const item of this.structures.values()) { this.kit.release(item.group); this.root.remove(item.group); }
    this.structures.clear(); this.hidden.clear();
  }
  terrain() { this.dirty = true; }
  update(state: VillageState) {
    this.state = state;
    const topology = JSON.stringify([state.huts.map(h => [h.id, h.kind, h.x, h.y, h.z, h.status, h.progress, h.entranceStep, h.upgrading]), state.bridges.map(b => [b.id, b.progress, b.status]), state.nodes.map(n => [n.id, n.position])]);
    if (topology !== this.topology) { this.topology = topology; this.dirty = true; }
    this.updateStructures();
  }
  refresh(): { hidden: number[]; chunks: string[] } | null {
    if (!this.dirty || !this.data) return null;
    this.dirty = false; this.plan = planModels(this.data, this.state);
    const next = new Set(this.plan.hidden), chunks = new Set<string>();
    const changed = (i: number) => {
      const x = i % SIZE, z = Math.floor(i / SIZE) % SIZE, cx = Math.floor(x / CHUNK), cz = Math.floor(z / CHUNK);
      chunks.add(`${cx},${cz}`);
      if (x % CHUNK === 0) chunks.add(`${cx - 1},${cz}`); if (x % CHUNK === CHUNK - 1) chunks.add(`${cx + 1},${cz}`);
      if (z % CHUNK === 0) chunks.add(`${cx},${cz - 1}`); if (z % CHUNK === CHUNK - 1) chunks.add(`${cx},${cz + 1}`);
    };
    for (const i of this.hidden) if (!next.has(i)) changed(i);
    for (const i of next) if (!this.hidden.has(i)) changed(i);
    this.hidden = next; this.rebuildNature(); this.updateStructures();
    return { hidden: this.plan.hidden, chunks: [...chunks] };
  }
  configure(settings: GraphicsSettings, profile: QualityProfile) {
    this.style = settings.style; this.profile = profile;
    const density = Math.min(profile.grassDensity, settings.grass === 'off' ? 0 : settings.grass === 'sparse' ? .28 : 1);
    if (density !== this.density) { this.density = density; this.rebuildNature(); }
    this.root.visible = this.style === 'diorama' && !this.editing;
  }
  setEditing(editing: boolean) { this.editing = editing; this.root.visible = this.style === 'diorama' && !editing; }
  private clearNature() {
    for (const sector of this.sectors.values()) {
      sector.traverse(o => { if (o instanceof THREE.InstancedMesh) o.dispose(); }); this.root.remove(sector);
    }
    this.sectors.clear();
  }
  private rebuildNature() {
    if (!this.plan) return;
    this.clearNature();
    const batches = new Map<string, { geometry: THREE.BufferGeometry; color: string; matrices: THREE.Matrix4[]; shadow: boolean; cx: number; cz: number }>();
    const add = (x: number, z: number, geometry: THREE.BufferGeometry, color: string, p: number[], s: number[], rotation = [0, 0, 0], shadow = true) => {
      const cx = Math.floor(x / 32), cz = Math.floor(z / 32), key = `${cx},${cz}:${geometry.id}:${color}:${shadow}`;
      const batch = batches.get(key) ?? { geometry, color, matrices: [], shadow, cx, cz };
      batch.matrices.push(this.kit.transform(p, s, rotation)); batches.set(key, batch);
    };
    for (const t of this.plan.trees) {
      const turn = (t.x + t.z) * .7;
      add(t.x, t.z, this.kit.trunk, '#987452', [t.x, t.y + t.height * .43, t.z], [1.15, t.height * .86, 1.15]);
      if (t.variant === 0) {
        add(t.x, t.z, this.kit.round, '#76965b', [t.x, t.y + t.height + .3, t.z], [1.9, 1.65, 1.85], [0, turn, 0]);
        add(t.x, t.z, this.kit.round, '#8aaa68', [t.x - .65, t.y + t.height + 1.25, t.z + .25], [1.25, 1, 1.15], [0, turn, .1]);
      } else for (let i = 0; i < 3; i++) add(t.x, t.z, this.kit.cone, '#648673', [t.x, t.y + 2.5 + i * 1.25, t.z], [1.75 - i * .4, 2.9 - i * .25, 1.75 - i * .4], [0, turn, 0]);
    }
    for (const d of this.plan.decorations) {
      if (d.kind !== 'rock' && d.density > this.density) continue;
      if (d.kind === 'rock') add(d.x, d.z, this.kit.rock, '#a5aba0', [d.x, d.y + .12, d.z], [d.scale * .33, d.scale * .25, d.scale * .3], [0, d.rotation, .2]);
      else {
        add(d.x, d.z, this.kit.grass, '#7d9754', [d.x, d.y, d.z], [d.scale, d.scale, d.scale], [0, d.rotation, 0], false);
        if (d.kind === 'flower') add(d.x, d.z, this.kit.flower, '#e6bda2', [d.x, d.y, d.z], [d.scale, d.scale, d.scale], [0, d.rotation, 0], false);
      }
    }
    for (const batch of batches.values()) {
      const key = `${batch.cx},${batch.cz}`; let group = this.sectors.get(key);
      if (!group) { group = new THREE.Group(); group.userData.center = new THREE.Vector3(batch.cx * 32 + 16, 10, batch.cz * 32 + 16); this.root.add(group); this.sectors.set(key, group); }
      const mesh = new THREE.InstancedMesh(batch.geometry, this.kit.material(batch.color), batch.matrices.length);
      batch.matrices.forEach((matrix, i) => mesh.setMatrixAt(i, matrix)); mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere(); mesh.castShadow = batch.shadow; mesh.receiveShadow = true;
      if (!batch.shadow) mesh.userData.decoration = true;
      group.add(mesh);
    }
  }
  private put(id: string, key: string, parts: ModelPart[], position: number[], progress = 1) {
    const old = this.structures.get(id); if (old?.key === key) return;
    if (old) { this.kit.release(old.group); this.root.remove(old.group); }
    const group = this.kit.assemble(parts, progress); group.position.set(position[0], position[1], position[2]);
    group.userData.modelId = id; this.root.add(group); this.structures.set(id, { key, group });
  }
  private updateStructures() {
    if (!this.state || !this.data) return;
    const active = new Set<string>();
    for (const h of this.state.huts) {
      active.add(h.id);
      const progress = h.status === 'complete' ? 1 : h.progress / Math.max(1, h.total);
      const key = `${h.kind}:${h.x}:${h.y}:${h.z}:${progress}:${h.entranceStep}:${h.upgrading}`;
      const visual = h.upgrading && progress < .35 ? { ...h, kind: 'hut' as const } : h;
      if (this.structures.get(h.id)?.key !== key) this.put(h.id, key, this.kit.building(visual), [h.x, h.y, h.z], h.upgrading ? 1 : progress);
      if (h.kind === 'farm') {
        const id = `${h.id}-crops`; active.add(id);
        const crop = h.crop, growth = Math.round((crop?.growth ?? 0) * 10) / 10, count = crop?.stage === 'ripe' ? Math.ceil(crop.remaining / 32 * 9) : 9;
        const cropKey = `${key}:${crop?.stage}:${growth}:${count}`;
        if (this.structures.get(id)?.key === cropKey) continue;
        const parts: ModelPart[] = [];
        if (h.status === 'complete' && crop && crop.stage !== 'fallow') for (let i = 0; i < count; i++) {
          const x = 1 + i % 3, z = 1 + Math.floor(i / 3), scale = .25 + growth * .75;
          this.kit.part(parts, this.kit.grass, '#84965b', [x, .12, z], [1.2, scale * 2, 1.2]);
          this.kit.part(parts, this.kit.cone, crop.stage === 'ripe' ? '#d7b569' : '#9db26b', [x, .12 + scale * .8, z], [.18, scale * .35, .18], 0, [0, 0, .15]);
        }
        this.put(id, cropKey, parts, [h.x, h.y, h.z]);
      }
    }
    for (const bridge of this.state.bridges) {
      active.add(bridge.id);
      const blocks = bridge.blocks.slice(0, bridge.progress).filter(e => getBlock(this.data!, e.x, e.y, e.z) === e.block);
      const key = JSON.stringify(blocks); if (this.structures.get(bridge.id)?.key === key) continue;
      const parts: ModelPart[] = [];
      for (const e of blocks) {
        // The top of every saved deck block stays at exactly e.y+1.
        this.kit.box(parts, '#987452', [e.x + .5, e.y + .54, e.z + .5], [1, .92, 1]);
        for (let i = 0; i < 3; i++) this.kit.box(parts, '#bf9c6d', [e.x + .17 + i * .33, e.y + .94, e.z + .5], [.31, .12, .97]);
      }
      for (const e of bridgeEdges(blocks)) {
        const x = e.x + .5 + e.dx * .43, z = e.z + .5 + e.dz * .43;
        this.kit.box(parts, '#987452', [x, e.y + 1.6, z], [e.dx ? .1 : 1, .12, e.dz ? .1 : 1]);
        if ((e.x + e.z) % 3 === 0) {
          this.kit.box(parts, '#765c46', [x, e.y + .8, z], [.15, 2.8, .15]);
          this.kit.part(parts, this.kit.round, '#bf9c6d', [x, e.y + 2.23, z], [.12, .065, .12]);
        }
      }
      this.put(bridge.id, key, parts, [0, 0, 0]);
    }
    for (const node of this.state.nodes) {
      if (node.kind === 'wood') continue;
      active.add(node.id);
      const fraction = Math.round(node.remaining / Math.max(1, node.capacity) * 4) / 4;
      const key = `${node.kind}:${fraction}:${node.remaining > 0}`;
      if (this.structures.get(node.id)?.key === key) continue;
      const parts: ModelPart[] = [], scale = .65 + fraction * .35;
      if (node.remaining > 0) {
        if (node.kind === 'stone') {
          this.kit.part(parts, this.kit.rock, '#a5aba0', [0, .3, 0], [.65 * scale, .5 * scale, .5 * scale]);
          this.kit.part(parts, this.kit.rock, '#89958c', [.35, .19, .23], [.35 * scale, .25 * scale, .34 * scale]);
        } else {
          this.kit.part(parts, this.kit.round, '#71935a', [0, .33, 0], [.55 * scale, .45 * scale, .5 * scale]);
          for (let i = 0; i < 4; i++) this.kit.part(parts, this.kit.rock, '#ce9172', [(i - 1.5) * .2, .48, .36], [.11, .11, .1]);
        }
      }
      this.put(node.id, key, parts, [node.position.x, node.position.y, node.position.z]);
    }
    for (const [id, item] of this.structures) if (!active.has(id)) { this.kit.release(item.group); this.root.remove(item.group); this.structures.delete(id); }
  }
  frame(target: THREE.Vector3, radius: number, distance: number) {
    for (const group of this.sectors.values()) {
      const center = group.userData.center as THREE.Vector3, d = Math.hypot(center.x - target.x, center.z - target.z);
      group.visible = d < Math.max(distance, radius * .8) + 32;
      for (const object of group.children) if (object.userData.decoration) object.visible = d < Math.max(this.profile?.decorationDistance ?? 60, radius * .4) + 24;
    }
    for (const { group } of this.structures.values()) {
      // Bridges already carry world-space geometry, so mesh frustum culling handles them.
      group.visible = group.userData.modelId.startsWith('bridge-') || Math.hypot(group.position.x - target.x, group.position.z - target.z) < Math.max(distance, radius * .8) + 16;
    }
  }
}
