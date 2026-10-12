import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { Block, generateWorld, getBlock, index } from '../shared/world';
import { Simulation } from '../backend/src/simulation/engine';
import { buildingBlocks } from '../backend/src/buildings/development';
import type { Hut } from '../shared/village';
import { buildingVoxels, planModels, presentationWorld, bridgeEdges } from '../frontend/src/renderer/model-plan';
import { ModelKit } from '../frontend/src/renderer/model-kit';
import { WorldModels } from '../frontend/src/renderer/world-models';
import { QUALITY_PROFILES } from '../frontend/src/renderer/graphics';

test('model planning is deterministic and preserves every saved terrain byte and village field', () => {
  const data = generateWorld(73129), simulation = new Simulation(data), before = data.slice(), village = JSON.stringify(simulation.state);
  const a = planModels(data, simulation.state), b = planModels(data, simulation.state);
  assert.deepEqual(a, b); assert.deepEqual(data, before); assert.equal(JSON.stringify(simulation.state), village);
  assert.ok(a.trees.length > 50); assert.ok(a.decorations.some(d => d.kind === 'grass'));
  const display = presentationWorld(data, a.hidden), hidden = new Set(a.hidden);
  for (let i = 0; i < data.length; i++) assert.equal(display[i], hidden.has(i) ? Block.Air : data[i]);
  for (const t of a.trees) assert.equal(getBlock(display, Math.floor(t.x), t.y - 1, Math.floor(t.z)), getBlock(data, Math.floor(t.x), t.y - 1, Math.floor(t.z)));
});

test('model building recipe stays aligned with authoritative construction including upgrades and entrance steps', () => {
  const data = generateWorld(73129), simulation = new Simulation(data), base = simulation.state.huts[0];
  for (const kind of ['hut', 'house', 'farm', 'warehouse'] as const) for (const entranceStep of [false, true]) {
    const h: Hut = { ...base, kind, entranceStep };
    assert.deepEqual(buildingVoxels(h), buildingBlocks(h));
    const edits = buildingBlocks(h), world = data.slice(), progress = Math.floor(edits.length / 2);
    for (const e of edits.slice(0, progress)) world[index(e.x, e.y, e.z)] = e.block;
    simulation.state.huts = [{ ...h, status: 'building', progress, total: edits.length }];
    const plan = planModels(world, simulation.state), masked = new Set(plan.hidden);
    for (const [i, e] of edits.entries()) assert.equal(masked.has(index(e.x, e.y, e.z)), i < progress);
    for (const d of plan.decorations) assert.ok(d.x < h.x - 1 || d.x >= h.x + 5 || d.z < h.z - 1 || d.z >= h.z + 5);
  }
});

test('wood and leaves placed by the player are preserved; deleting a tree changes only presentation masking', () => {
  const data = generateWorld(73129);
  data[index(32, 12, 40)] = Block.Wood; data[index(33, 12, 40)] = Block.Leaves;
  const a = planModels(data), before = data.slice();
  assert.ok(!a.hidden.includes(index(32, 12, 40))); assert.ok(!a.hidden.includes(index(33, 12, 40)));
  const tree = a.trees[0], x = Math.floor(tree.x), z = Math.floor(tree.z);
  data[index(x, tree.y, z)] = Block.Air;
  const b = planModels(data);
  assert.ok(!b.trees.some(t => t.x === tree.x && t.z === tree.z));
  before[index(x, tree.y, z)] = Block.Air; assert.deepEqual(data, before);
});

test('remodeling a hut keeps the existing wooden shell covered until replacement bricks arrive', () => {
  const data = generateWorld(73129), simulation = new Simulation(data), h = simulation.state.huts[0];
  for (const e of buildingBlocks(h)) data[index(e.x, e.y, e.z)] = e.block;
  const before = data.slice();
  h.kind = 'house'; h.upgrading = true; h.progress = 0; h.status = 'planned';
  const hidden = new Set(planModels(data, simulation.state).hidden);
  for (const e of buildingBlocks({ ...h, kind: 'hut' })) assert.ok(hidden.has(index(e.x, e.y, e.z)));
  assert.deepEqual(data, before);
});

test('bridge rails follow either deck direction and leave the saved entry and exit open', () => {
  for (const turn of [false, true]) {
    const blocks = [];
    for (let a = 0; a < 8; a++) for (let b = 0; b < 3; b++) blocks.push({ x: turn ? b : a, y: 6, z: turn ? a : b, block: Block.Wood });
    const edges = bridgeEdges(blocks);
    assert.ok(edges.length > 0); assert.ok(edges.every(e => turn ? e.dx !== 0 && e.dz === 0 : e.dz !== 0 && e.dx === 0));
    assert.equal(bridgeEdges(blocks.slice(0, 3)).length, 0);
  }
});

test('baked tile models keep the doorway walkable and construction progress hides unfinished roof pieces', () => {
  const simulation = new Simulation(generateWorld(73129)), h = simulation.state.huts[0], kit = new ModelKit();
  const parts = kit.building({ ...h, kind: 'house' }), planned = kit.assemble(parts, 0), early = kit.assemble(parts, .2), complete = kit.assemble(parts);
  assert.equal(planned.children.length, 0); assert.ok(early.children.length < complete.children.length);
  assert.ok(complete.children.length <= 12, `one draw call per material: ${complete.children.length}`);
  const box = new THREE.Box3().setFromObject(complete); assert.ok(box.max.y < 5.2);
  complete.updateMatrixWorld(true);
  const ray = new THREE.Raycaster(new THREE.Vector3(1.5, 1.7, 6), new THREE.Vector3(0, 0, -1));
  const hit = ray.intersectObject(complete, true)[0]; assert.ok(hit && hit.point.z < 3, 'no new door blocks the original entrance');
  for (const g of [planned, early, complete]) kit.release(g); kit.dispose();
});

test('style/quality changes and repeated state updates reuse instance geometry and restore model visibility', () => {
  const data = generateWorld(73129), simulation = new Simulation(data), scene = new THREE.Scene(), models = new WorldModels(scene);
  models.world(data); models.update(simulation.state); assert.ok(models.refresh());
  const settings = { style: 'diorama' as const, quality: 'high' as const, shadows: true, ao: true, distance: 'standard' as const, preview: 'day' as const, grass: 'lush' as const };
  models.configure(settings, QUALITY_PROFILES.high);
  let highInstances = 0, highMeshes = 0;
  models.root.traverse(o => { if (o instanceof THREE.InstancedMesh) { highInstances += o.count; highMeshes++; assert.ok(o.boundingSphere); } });
  assert.ok(highInstances > highMeshes * 3);
  models.update(structuredClone(simulation.state)); assert.equal(models.refresh(), null);
  models.configure({ ...settings, style: 'classic' }, QUALITY_PROFILES.high); assert.equal(models.root.visible, false);
  models.configure(settings, QUALITY_PROFILES.low); assert.equal(models.root.visible, true);
  let lowInstances = 0; models.root.traverse(o => { if (o instanceof THREE.InstancedMesh) lowInstances += o.count; });
  assert.ok(lowInstances < highInstances);
  models.setEditing(true); assert.equal(models.root.visible, false); models.setEditing(false); assert.equal(models.root.visible, true);
  const saved = JSON.parse(JSON.stringify(simulation.state)); models.world(data.slice()); models.update(saved);
  assert.deepEqual(models.refresh()?.hidden, planModels(data, simulation.state).hidden);
});
