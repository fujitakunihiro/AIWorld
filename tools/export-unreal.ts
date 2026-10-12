import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import * as THREE from 'three';
import { ModelKit } from '../frontend/src/renderer/model-kit';
import { eiffelModel } from '../frontend/src/renderer/eiffel-model';
import { frenchCityModels } from '../frontend/src/renderer/french-city-model';
import { parisLandmarks } from '../frontend/src/renderer/paris-landmarks-model';
import { ResidentModelLibrary } from '../frontend/src/renderer/resident-model';
import { residentPose } from '../frontend/src/renderer/resident-pose';
import type { Hut, Resident } from '../shared/village';

// The authored meshes are exported, not reimplemented: geometry/colors stay identical.
// Float32 LE buffers avoid large decimal JSON and work in packaged UE builds.
function floats(array: ArrayLike<number>) { return Buffer.from(new Float32Array(Array.from(array)).buffer).toString('base64'); }
function mesh(geometry: THREE.BufferGeometry, color = '#ffffff', matrix?: THREE.Matrix4) {
  const g = geometry.clone(); if (matrix) g.applyMatrix4(matrix);
  const p = g.getAttribute('position'), n = g.getAttribute('normal'), c = g.getAttribute('color');
  const indices = g.index ? Array.from(g.index.array) : Array.from({ length: p.count }, (_, i) => i);
  const result = { positions: floats(p.array), normals: n ? floats(n.array) : '', colors: c ? floats(c.array) : '',
    indices: Buffer.from(new Uint32Array(indices).buffer).toString('base64'), color };
  g.dispose(); return result;
}
const kit = new ModelKit();
const statics: unknown[] = [];
for (const root of [eiffelModel(kit), ...frenchCityModels(kit), parisLandmarks(kit)]) {
  root.updateMatrixWorld(true);
  root.traverse(o => { if (o instanceof THREE.Mesh) {
    const color = (o.material as THREE.MeshStandardMaterial).color.getHexString();
    statics.push(mesh(o.geometry, `#${color}`, o.matrixWorld));
  } });
}
const buildings: Record<string, unknown[]> = {};
for (const kind of ['hut', 'house', 'farm', 'warehouse'] as const) {
  const parts = kit.building({ kind, entranceStep: true } as Hut);
  buildings[kind] = parts.map(p => ({ ...mesh(p.geometry, p.color, p.matrix), stage: p.stage }));
}
const library = new ResidentModelLibrary();
const residents: Record<string, unknown> = {};
const people = [
  ['haru', '建築家', '#cb896c'], ['mio', '木こり', '#86a975'], ['ren', '採掘師', '#7f9bae'],
  ['sora', '採集家', '#d2b16c'], ['sora', '農家', '#d2b16c'], ['yui', '木こり', '#b18cba']
];
for (const [id, job, color] of people) {
  const rig = library.create({ id, job, color } as Resident);
  const from = (g: THREE.Object3D) => mesh((g.children[0] as THREE.Mesh).geometry);
  const face = (rig.head.children[0] as THREE.Mesh).geometry, source = face.getAttribute('position');
  const targets = face.morphAttributes.position ?? [];
  if(targets.length !== 3)throw new Error('Expected blink, smile and worry morph targets');
  const morphs: number[][] = [];
  for(let i=0;i<source.count;i++) { const deltas=targets.map(a=>a.getY(i)-source.getY(i)); if(deltas.some(v=>Math.abs(v)>1e-7))morphs.push([i,...deltas]); }
  const cargos: Record<string, unknown> = {};
  for(const kind of ['food','wood','stone'] as const) {
    const r = { id, job, color, health: 100, energy: 100, hunger: 0, speech: null, action: 'delivering', inventory: { food:0,wood:0,stone:0,[kind]:4 } } as Resident;
    library.pose(rig,residentPose(r,0,true));cargos[kind]=mesh(rig.cargo.geometry);
  }
  const model = { shirt: color, body: from(rig.upper), head: from(rig.head), arm: from(rig.arms[0]), leg: from(rig.legs[0]), morphs,
    tools: Object.fromEntries(Object.entries(rig.tools).map(([k, m]) => [k, mesh(m.geometry)])), cargos };
  residents[`${id}:${job}`] = model; residents[job] ??= model;
  library.release(rig);
}
const output = resolve('unreal/AIWorld/Content/Data/models.json'); mkdirSync(resolve(output, '..'), { recursive: true });
const primitives = Object.fromEntries(['cube', 'round', 'cone', 'grass', 'rock'].map(k => [k, mesh(kit[k as 'cube'], '#ffffff')]));
writeFileSync(output, JSON.stringify({ format: 1, statics, buildings, residents, primitives }));
console.log(`Exported ${statics.length} native mesh batches to ${output}`);
library.dispose(); kit.dispose();
