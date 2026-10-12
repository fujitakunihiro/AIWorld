import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import type { Hut } from '../../../shared/village';
import { lightingAt } from './graphics';

export interface ModelPart { geometry: THREE.BufferGeometry; color: string; matrix: THREE.Matrix4; stage: number }
// Original geometry built from primitives; shared resources belong to this kit.
export class ModelKit {
  private object = new THREE.Object3D();
  readonly cube = new THREE.BoxGeometry(1, 1, 1);
  readonly round = new THREE.IcosahedronGeometry(1, 1);
  readonly rock = new THREE.IcosahedronGeometry(1, 0);
  readonly trunk = new THREE.CylinderGeometry(.19, .3, 1, 7);
  readonly cone = new THREE.ConeGeometry(1, 1, 9);
  readonly gable = new THREE.ShapeGeometry(new THREE.Shape().moveTo(-1.9, 0).lineTo(1.9, 0).lineTo(0, 1.9).lineTo(-1.9, 0));
  readonly grass = this.grassGeometry();
  readonly flower = this.flowerGeometry();
  private materials = new Map<string, THREE.MeshStandardMaterial>();
  material(color: string) {
    let material = this.materials.get(color);
    if (!material) { material = new THREE.MeshStandardMaterial({ color, roughness: .92, metalness: 0, flatShading: true,
      side: color === '#7d9754' || color === '#84965b' ? THREE.DoubleSide : THREE.FrontSide }); this.materials.set(color, material); }
    return material;
  }
  light(time: number) {
    const glow = (1 - Math.sqrt(lightingAt(time).daylight)) ** 3;
    const windows = this.material('#628e94'); windows.emissive.set('#ffc777'); windows.emissiveIntensity = glow * 1.8;
    windows.color.set('#628e94').lerp(new THREE.Color('#f4c777'), glow);
  }
  transform(p: number[], s: number[], rotation: number[] = [0, 0, 0]) {
    this.object.position.set(p[0], p[1], p[2]); this.object.scale.set(s[0], s[1], s[2]);
    this.object.rotation.set(rotation[0], rotation[1], rotation[2]); this.object.updateMatrix(); return this.object.matrix.clone();
  }
  private grassGeometry() {
    // Three bent blades, nine triangles total (rather than three solid cones).
    const parts = [-.65, 0, .65].map((angle, i) => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute([-.045, 0, 0, .045, 0, 0, .032, .24, .035,
        -.045, 0, 0, .032, .24, .035, -.032, .24, .035, -.032, .24, .035, .032, .24, .035, .035, .46, .12], 3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, .5, 0, 0, 1, .5, 0, .5, 0, .5, 1, .5, .5, 1], 2));
      geometry.computeVertexNormals();
      return geometry.applyMatrix4(this.transform([(i - 1) * .1, 0, 0], [1, 1 + i * .1, 1], [0, angle, angle * .3]));
    });
    const result = mergeGeometries(parts)!; parts.forEach(g => g.dispose()); return result;
  }
  private flowerGeometry() {
    const parts: THREE.BufferGeometry[] = [];
    for (let i = 0; i < 5; i++) {
      const angle = i / 5 * Math.PI * 2;
      parts.push(this.rock.clone().applyMatrix4(this.transform([Math.cos(angle) * .11, .4, Math.sin(angle) * .11], [.105, .045, .08], [0, -angle, 0])));
    }
    parts.push(this.round.clone().applyMatrix4(this.transform([0, .42, 0], [.055, .035, .055])));
    const result = mergeGeometries(parts)!; parts.forEach(g => g.dispose()); return result;
  }
  part(parts: ModelPart[], geometry: THREE.BufferGeometry, color: string, p: number[], s: number[], stage = 0, rotation?: number[]) {
    parts.push({ geometry, color, matrix: this.transform(p, s, rotation), stage });
  }
  box(parts: ModelPart[], color: string, p: number[], s: number[], stage = 0, rotation?: number[]) { this.part(parts, this.cube, color, p, s, stage, rotation); }
  // Bake same-material parts together: tile roofs and beams do not add a draw call per part.
  assemble(parts: ModelPart[], progress = 1) {
    const byColor = new Map<string, THREE.BufferGeometry[]>(), group = new THREE.Group();
    for (const part of parts) if (part.stage <= progress) {
      // Roof pieces can be hidden while following a resident indoors.
      const roof = part.stage >= .7 && part.matrix.elements[13] >= 3;
      const key = `${part.color}:${roof}`, list = byColor.get(key) ?? [];
      const geometry = part.geometry.index ? part.geometry.toNonIndexed() : part.geometry.clone();
      list.push(geometry.applyMatrix4(part.matrix)); byColor.set(key, list);
    }
    for (const [key, list] of byColor) {
      const [color, roof] = key.split(':');
      const geometry = mergeGeometries(list)!; list.forEach(g => g.dispose());
      const mesh = new THREE.Mesh(geometry, this.material(color)); mesh.castShadow = mesh.receiveShadow = true; mesh.userData.roof = roof === 'true'; group.add(mesh);
    }
    return group;
  }
  release(group: THREE.Object3D) { group.traverse(o => { if (o instanceof THREE.Mesh) { o.geometry.dispose(); if (o instanceof THREE.InstancedMesh) o.dispose(); } }); }
  dispose() {
    for (const g of [this.cube, this.round, this.rock, this.trunk, this.cone, this.gable, this.grass, this.flower]) g.dispose();
    for (const m of this.materials.values()) m.dispose(); this.materials.clear();
  }
  building(hut: Hut) {
    const parts: ModelPart[] = [], b = this.box.bind(this, parts);
    if (hut.kind === 'farm') {
      b('#795d43', [2, .055, 2], [3.8, .11, 3.8], .01);
      for (let z = 0; z < 3; z++) b('#594b37', [2, .14, .8 + z * 1.15], [3.4, .09, .22], .1);
      for (const x of [.5, 3.5]) for (const z of [.5, 3.5]) { b('#aa8962', [x, .5, z], [.2, 1, .2], .25); this.part(parts, this.round, '#c4a17b', [x, 1.02, z], [.14, .07, .14], .25); }
      for (const x of [.5, 3.5]) b('#aa8962', [x, .55, 2], [.1, .1, 3], .65);
      b('#aa8962', [2, .55, .5], [3, .1, .1], .65);
      // Open front, keeping the farmer's approach clear.
      this.part(parts, this.trunk, '#bc9471', [3.2, .3, 4.1], [1.4, .6, 1.4], .95);
      return parts;
    }
    const wall = hut.kind === 'house' ? '#e3cfac' : hut.kind === 'warehouse' ? '#b9beb0' : '#c4a17b';
    const beam = '#765c46', roof = hut.kind === 'warehouse' ? '#738b91' : '#be795b';
    b('#b3aa92', [2, .35, 2], [3.96, .7, 3.96], .01);
    b('#ad8760', [2, .84, 2], [3.96, .32, 3.96], .12);
    // Front doorway matches the saved x=1,z=3 opening. Side windows match y=2.
    b(wall, [2, 2, .5], [4, 2, 1], .25);
    b(wall, [.5, 1.5, 2], [1, 1, 2], .25); b(wall, [3.5, 1.5, 2], [1, 1, 2], .25);
    b(wall, [.5, 2.5, 2.5], [1, 1, 1], .5); b(wall, [3.5, 2.5, 1.5], [1, 1, 1], .5);
    b(wall, [.5, 2, 3.5], [1, 2, 1], .35); b(wall, [3, 2, 3.5], [2, 2, 1], .35);
    b(beam, [1.5, 2.92, 3.53], [1, .16, .97], .55);
    for (const x of [.14, 3.86]) for (const z of [.14, 3.86]) b(beam, [x, 2, z], [.22, 2, .22], .6);
    for (const y of [1.1, 2.94]) { b(beam, [2, y, 3.94], [3.9, .16, .1], .6); b(beam, [2, y, .06], [3.9, .16, .1], .6); }
    // Recessed windows occupy only the exterior edge of the existing window voxels.
    for (const [x, z] of [[.03, 1.5], [3.97, 2.5]]) {
      b('#628e94', [x, 2.46, z], [.045, .7, .7], .62);
      b(beam, [x, 2.46, z], [.09, .76, .055], .64); b(beam, [x, 2.46, z], [.09, .055, .76], .64);
      b('#ad8760', [x, 2.03, z], [.28, .13, .94], .64);
    }
    // An open dark doorway; the saved walkable cell is not covered by a new door.
    for (const x of [1.03, 1.97]) b(beam, [x, 1.96, 3.95], [.09, 1.9, .1], .6);
    if (hut.entranceStep) b('#ad8760', [1.5, -.5, 4.5], [1, 1, 1], .12);
    // Rounded rows of overlapping tiles form a pitched roof inside the 4×4 footprint.
    this.part(parts, this.gable, wall, [2, 3.02, 3.94], [1, 1, 1], .7);
    this.part(parts, this.gable, wall, [2, 3.02, .06], [1, 1, 1], .7, [0, Math.PI, 0]);
    b(beam, [2, 3.95, 3.98], [.12, 1.8, .08], .84);
    for (const side of [-1, 1]) for (let row = 0; row < 5; row++) for (let col = 0; col < 7; col++) {
      const x = 2 + side * (.22 + row * .38), y = 4.78 - row * .33;
      b(roof, [x, y, .29 + col * .57], [.56, .13, .58], .7 + row * .025, [0, 0, -side * .715]);
    }
    b(roof, [2, 4.94, 2], [.36, .18, 3.95], .84);
    b('#a48c72', [3.15, 4.38, .85], [.53, 1.04, .55], .91); b('#765c46', [3.15, 4.94, .85], [.67, .14, .69], .94);
    b('#393e38', [3.15, 5.02, .85], [.28, .015, .29], .94);
    if (hut.kind === 'warehouse') {
      for (const x of [2.65, 3.3]) { b('#ad8760', [x, 1.32, 4.18], [.57, .65, .6], .98); b(beam, [x, 1.32, 4.5], [.6, .065, .035], .98); }
      b('#d4bd80', [2.9, 2.55, 4.04], [.85, .32, .06], .99);
    } else {
      b('#79935b', [.5, 1.28, 4.05], [.65, .3, .35], .98);
      this.part(parts, this.flower, '#e6bda2', [.5, 1.35, 4.05], [.9, .9, .9], .98);
    }
    return parts;
  }
}
