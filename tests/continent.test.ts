import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import * as THREE from 'three';
import { ARC, ARC_VOXELS, Block, CAROUSEL, CAROUSEL_VOXELS, EIFFEL, FRENCH_BUILDINGS, FRENCH_VOXELS, HEIGHT, PARIS_BRIDGES, PARIS_BRIDGE_VOXELS, SAVE_VERSION, SIZE, bridgeCenter, eiffelVoxels, generateWorld, getBlock, index, inFrenchBuilding, inside } from '../shared/world';
import { WorldStore } from '../backend/src/database/store';
import { Simulation } from '../backend/src/simulation/engine';
import { Navigation } from '../backend/src/agents/navigation';
import { siteClear } from '../backend/src/buildings/hut';
import { eiffelModel } from '../presentation/src/renderer/eiffel-model';
import { ModelKit } from '../presentation/src/renderer/model-kit';
import { frenchCityModels } from '../presentation/src/renderer/french-city-model';
import { parisLandmarks } from '../presentation/src/renderer/paris-landmarks-model';
import { planModels } from '../presentation/src/renderer/model-plan';

test('the Paris map has walkable landmarks and permanent crossings over the Seine', () => {
  const data = generateWorld(73129), nav = new Navigation(data);
  assert.equal(SIZE, 384); assert.ok(nav.position(80, 110));
  const centre = nav.position(EIFFEL.x, EIFFEL.z)!; assert.equal(centre.y, EIFFEL.y); assert.ok(nav.path(nav.position(40, 40)!, centre));
  const arch = nav.position(ARC.x, ARC.z)!; assert.ok(nav.path(centre, arch));
  assert.ok(eiffelVoxels().every(e => inside(e.x, e.y, e.z)));
  const cells = new Set(eiffelVoxels().map(e => `${e.x}:${e.y}:${e.z}`)), queue = [eiffelVoxels()[0]], reached = new Set([`${queue[0].x}:${queue[0].y}:${queue[0].z}`]);
  for (let i = 0; i < queue.length; i++) for (const [dx, dy, dz] of [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]) {
    const { x, y, z } = queue[i], key = `${x + dx}:${y + dy}:${z + dz}`;
    if (cells.has(key) && !reached.has(key)) { reached.add(key); queue.push({ x: x + dx, y: y + dy, z: z + dz, block: Block.Brick }); }
  }
  assert.equal(reached.size, cells.size, 'classic tower legs, platforms and feet form one connected structure');
  assert.equal(nav.position(EIFFEL.x - 10, EIFFEL.z)?.y, EIFFEL.y);
});

test('tower presentation has open entrances, a tall silhouette and a small fixed material count', () => {
  const data = generateWorld(73129), before = data.slice(), plan = planModels(data), hidden = new Set(plan.hidden);
  for (const e of eiffelVoxels()) assert.ok(hidden.has(index(e.x, e.y, e.z)));
  const kit = new ModelKit(), tower = eiffelModel(kit), bounds = new THREE.Box3().setFromObject(tower);
  assert.ok(bounds.max.y >= EIFFEL.y + EIFFEL.height * 1.8 && bounds.max.y < HEIGHT * 2);
  assert.ok(tower.children.length <= 9); tower.updateMatrixWorld(true);
  const ray = new THREE.Raycaster(new THREE.Vector3(EIFFEL.x, EIFFEL.y + 1.7, EIFFEL.z + 8), new THREE.Vector3(0, 0, -1));
  assert.equal(ray.intersectObject(tower, true).length, 0, 'ground-level arches stay open for residents');
  assert.deepEqual(data, before); kit.release(tower); kit.dispose();
});

test('the French district fills level ground while keeping streets and the tower accessible', () => {
  const data = generateWorld(73129), nav = new Navigation(data);
  assert.ok(FRENCH_BUILDINGS.length >= 500, 'dense blocks cover the Paris districts');
  const footprints = new Set<string>();
  for (const b of FRENCH_BUILDINGS) {
    assert.equal(getBlock(data, b.x + 3, 8, b.z + 3), Block.Stone);
    assert.equal(getBlock(data, b.x + 3, 9, b.z + 3), Block.Brick);
    assert.ok(!inFrenchBuilding(EIFFEL.x, EIFFEL.z));
    assert.equal(siteClear(data, b.x, 9, b.z), false);
    for (let z = b.z; z < b.z + 6; z++) for (let x = b.x; x < b.x + 6; x++) {
      const key = `${x}:${z}`; assert.ok(!footprints.has(key)); footprints.add(key);
    }
  }
  assert.ok(FRENCH_VOXELS.every(e => inside(e.x, e.y, e.z)));
  for (const [x, z] of [[80, 110], [80, 160], [240, 100], [280, 250], [140, 330]]) {
    assert.equal(nav.position(x, z)?.y, 9);
    assert.ok(nav.path(nav.position(x, z)!, nav.position(EIFFEL.x, EIFFEL.z)!));
  }
  for (const center of PARIS_BRIDGES) {
    for (const x of [Math.floor(bridgeCenter(center) - 24), Math.ceil(bridgeCenter(center) + 24)]) assert.ok(nav.position(x, center));
    assert.ok(nav.path(nav.position(EIFFEL.x, EIFFEL.z)!, nav.position(ARC.x, ARC.z)!));
  }
  assert.equal(nav.position(ARC.x, ARC.z)?.y, ARC.y, 'the arch remains passable at street level');
  assert.equal(getBlock(data, ARC.x, ARC.y + 9, ARC.z), Block.Stone);
  assert.equal(getBlock(data, CAROUSEL.x, CAROUSEL.y + 4, CAROUSEL.z), Block.Sand);
});

test('French facades replace only matching city voxels and remain batched by sector', () => {
  const data = generateWorld(73129), before = data.slice(), hidden = new Set(planModels(data).hidden);
  assert.ok(FRENCH_VOXELS.every(e => hidden.has(index(e.x, e.y, e.z))));
  const kit = new ModelKit(), sectors = frenchCityModels(kit);
  assert.ok(sectors.length > 1 && sectors.length <= 4);
  assert.ok(sectors.every(s => s.children.length <= 60));
  assert.ok(sectors.reduce((count, s) => count + s.children.length, 0) <= 120);
  const bounds = new THREE.Box3(); sectors.forEach(s => bounds.expandByObject(s));
  assert.ok(bounds.min.x >= 0 && bounds.max.y < HEIGHT);
  assert.deepEqual(data, before);
  sectors.forEach(s => kit.release(s)); kit.dispose();
});

test('Paris monuments and bridges keep classic collision and replace only their own generated voxels', () => {
  const data = generateWorld(73129), hidden = new Set(planModels(data).hidden);
  for (const voxel of [...ARC_VOXELS, ...CAROUSEL_VOXELS, ...PARIS_BRIDGE_VOXELS])
    assert.ok(hidden.has(index(voxel.x, voxel.y, voxel.z)));
  const kit = new ModelKit(), models = parisLandmarks(kit);
  assert.ok(models.children.length >= 10);
  const bounds = new THREE.Box3().setFromObject(models);
  assert.ok(bounds.min.x >= 0 && bounds.max.x < SIZE && bounds.max.y < HEIGHT);
  for (const child of models.children) kit.release(child);
  kit.dispose();
});

test('version 7 saves gain the expanded Paris world once and keep village state and edits', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-paris-expand-')), path = join(dir, 'world.sqlite');
  let store: WorldStore | undefined;
  try {
    store = new WorldStore(path, 73129); const simulation = new Simulation(store.data);
    simulation.state.events = simulation.state.events.filter(e => !e.text.includes('384×384'));
    simulation.state.chronicle = simulation.state.chronicle.filter(e => !e.text.includes('384×384'));
    store.speed = 0; store.time = 2345;
    store.edit({ type: 'edit', x: 32, y: 11, z: 40, block: Block.Wood, expected: Block.Air });
    store.saveVillage(simulation.state);
    const saved = structuredClone(simulation.state), revision = store.revision;
    store.close();
    const db = new DatabaseSync(path); db.exec('UPDATE world SET version=7'); db.close();
    store = new WorldStore(path, 1);
    assert.equal(store.snapshot().version, SAVE_VERSION);
    assert.equal(store.time, 2345); assert.equal(store.speed, 0); assert.equal(store.revision, revision);
    assert.equal(getBlock(store.data, 32, 11, 40), Block.Wood);
    assert.deepEqual(store.village!.residents, saved.residents);
    assert.deepEqual(store.village!.bridges, saved.bridges);
    assert.deepEqual(store.village!.tasks, saved.tasks);
    assert.deepEqual(store.village!.resources, saved.resources);
    assert.equal(store.village!.chronicle.filter(e => e.text.includes('384×384')).length, 1);
    for (const voxel of [ARC_VOXELS[0], PARIS_BRIDGE_VOXELS[0], CAROUSEL_VOXELS[0]])
      assert.throws(() => store!.edit({ type: 'edit', ...voxel, block: Block.Air, expected: voxel.block }));
    store.close();
    store = new WorldStore(path, 1);
    assert.equal(store.village!.chronicle.filter(e => e.text.includes('384×384')).length, 1);
    store.close();
  } finally { try { store?.close(); } catch { /* May already be closed. */ } rmSync(dir, { recursive: true, force: true }); }
});

test('version 5 migration keeps residents, jobs, resources, old edits and clock, and adds the continent once', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-mainland-')), path = join(dir, 'world.sqlite');
  try {
    let store = new WorldStore(path, 73129), simulation = new Simulation(store.data);
    store.time = 1024; store.speed = 0;
    store.edit({ type: 'edit', x: 127, y: 31, z: 127, block: Block.Wood, expected: Block.Air });
    store.saveVillage(simulation.state); const saved = structuredClone(simulation.state), revision = store.revision; store.close();
    const db = new DatabaseSync(path); db.exec('UPDATE world SET version=5'); db.close();
    store = new WorldStore(path, 1); assert.equal(store.snapshot().version, SAVE_VERSION); assert.equal(store.seed, 73129);
    assert.equal(store.time, 1024); assert.equal(store.speed, 0); assert.equal(store.revision, revision);
    assert.deepEqual(store.village!.residents, saved.residents); assert.deepEqual(store.village!.tasks, saved.tasks); assert.deepEqual(store.village!.resources, saved.resources);
    assert.equal(getBlock(store.data, 127, 31, 127), Block.Wood);
    const e = eiffelVoxels()[0]; assert.throws(() => store.edit({ type: 'edit', ...e, block: Block.Air, expected: e.block }), /エッフェル塔/);
    store.edit({ type: 'edit', x: 230, y: 31, z: 240, block: Block.Wood, expected: Block.Air });
    const history = structuredClone(store.village!.chronicle); store.close();
    store = new WorldStore(path, 1); assert.deepEqual(store.village!.chronicle, history); assert.equal(getBlock(store.data, 230, 31, 240), Block.Wood); store.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

test('version 6 saves gain the city once without changing village jobs or existing bridge', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-paris-')), path = join(dir, 'world.sqlite');
  try {
    let store = new WorldStore(path, 73129);
    const simulation = new Simulation(store.data);
    for (const event of [...simulation.state.events, ...simulation.state.chronicle])
      event.text = event.text.replace('エッフェル塔とフランス風の街並み', 'エッフェル塔の広場');
    const saved = structuredClone(simulation.state);
    store.speed = 0; store.time = 2190; store.saveVillage(simulation.state); store.close();
    const db = new DatabaseSync(path); db.exec('UPDATE world SET version=6'); db.close();
    store = new WorldStore(path, 1);
    assert.deepEqual(store.village!.residents, saved.residents);
    assert.deepEqual(store.village!.tasks, saved.tasks);
    assert.deepEqual(store.village!.bridges, saved.bridges);
    assert.equal(store.time, 2190);
    const cityEvents = store.village!.chronicle.filter(e => e.text.includes('フランス風の街並み'));
    assert.equal(cityEvents.length, 1);
    const first = FRENCH_VOXELS[0];
    assert.throws(() => store.edit({ type: 'edit', ...first, block: Block.Air, expected: first.block }), /フランスの街並み/);
    store.close();
    store = new WorldStore(path, 1);
    assert.equal(store.village!.chronicle.filter(e => e.text.includes('フランス風の街並み')).length, 1);
    store.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
