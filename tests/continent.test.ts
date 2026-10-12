import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import * as THREE from 'three';
import { ARC, ARC_VOXELS, Block, CAROUSEL, CAROUSEL_VOXELS, EIFFEL, FRENCH_BUILDINGS, FRENCH_VOXELS, HEIGHT, PARIS_BRIDGES, PARIS_BRIDGE_VOXELS, SAVE_VERSION, SIZE, eiffelVoxels, generateWorld, getBlock, index, inFrenchBuilding, inside } from '../shared/world';
import { WorldStore } from '../backend/src/database/store';
import { Simulation } from '../backend/src/simulation/engine';
import { Navigation } from '../backend/src/agents/navigation';
import { NEW_CONTINENT, planBridge } from '../backend/src/buildings/bridge';
import { siteClear } from '../backend/src/buildings/hut';
import { eiffelModel } from '../frontend/src/renderer/eiffel-model';
import { ModelKit } from '../frontend/src/renderer/model-kit';
import { frenchCityModels } from '../frontend/src/renderer/french-city-model';
import { parisLandmarks } from '../frontend/src/renderer/paris-landmarks-model';
import { planModels } from '../frontend/src/renderer/model-plan';

test('all 128×128 legacy terrain bytes are preserved for different saved seeds', () => {
  for (const [seed, expected] of [[73129, '7bf31cf4e940e485830564e6301c59ef506b9f2ae6ac1f439149abecfcf82eab'], [100, '8d875a39ae7547db6f2d3d614a7ce4c9a29a3136ff857be0690c2282f04f7591']] as const) {
    const data = generateWorld(seed), legacy = new Uint8Array(128 * 128 * HEIGHT);
    for (let y = 0; y < HEIGHT; y++) for (let z = 0; z < 128; z++) for (let x = 0; x < 128; x++) legacy[x + 128 * (z + 128 * y)] = getBlock(data, x, y, z);
    assert.equal(createHash('sha256').update(legacy).digest('hex'), expected);
  }
});

test('the mainland has a walkable tower plaza, bounded persistent legs, and a feasible bridge from the old islands', () => {
  const data = generateWorld(73129), nav = new Navigation(data);
  assert.equal(SIZE, 384); assert.ok(nav.position(220, 145));
  const goal = nav.position(NEW_CONTINENT.x, NEW_CONTINENT.z)!; assert.ok(goal);
  const centre = nav.position(EIFFEL.x, EIFFEL.z)!; assert.equal(centre.y, EIFFEL.y); assert.ok(nav.path(goal, centre));
  const bridge = planBridge(data, nav, nav.nearest({ x: 99, y: 11, z: 38 })!, NEW_CONTINENT)!;
  assert.ok(bridge && bridge.blocks.length > 0 && bridge.blocks.length <= 600);
  for (const e of bridge.blocks) data[index(e.x, e.y, e.z)] = e.block;
  nav.rebuild(); assert.ok(nav.path(nav.nearest({ x: 99, y: 11, z: 38 })!, goal));
  assert.ok(eiffelVoxels().every(e => inside(e.x, e.y, e.z) && e.x >= 128));
  const cells = new Set(eiffelVoxels().map(e => `${e.x}:${e.y}:${e.z}`)), queue = [eiffelVoxels()[0]], reached = new Set([`${queue[0].x}:${queue[0].y}:${queue[0].z}`]);
  for (let i = 0; i < queue.length; i++) for (const [dx, dy, dz] of [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]) {
    const { x, y, z } = queue[i], key = `${x + dx}:${y + dy}:${z + dz}`;
    if (cells.has(key) && !reached.has(key)) { reached.add(key); queue.push({ x: x + dx, y: y + dy, z: z + dz, block: Block.Brick }); }
  }
  assert.equal(reached.size, cells.size, 'classic tower legs, platforms and feet form one connected structure');
  assert.equal(siteClear(data, EIFFEL.x - 10, EIFFEL.y, EIFFEL.z), false);
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
  assert.ok(FRENCH_BUILDINGS.length >= 160, 'both banks have a substantial city');
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
  assert.ok(FRENCH_VOXELS.every(e => inside(e.x, e.y, e.z) && e.x >= 128));
  for (const [x, z] of [[196, 90], [196, 160], [176, 122], [220, 122], [220, 183]]) {
    assert.equal(nav.position(x, z)?.y, 9);
    assert.ok(nav.path(nav.position(x, z)!, nav.position(EIFFEL.x, EIFFEL.z)!));
  }
  for (const center of PARIS_BRIDGES) {
    for (let x = 238; x <= 277; x++) assert.equal(nav.position(x, center)?.y, 9);
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
  assert.ok(sectors.every(s => s.children.length <= 30));
  assert.ok(sectors.reduce((count, s) => count + s.children.length, 0) <= 120);
  const bounds = new THREE.Box3(); sectors.forEach(s => bounds.expandByObject(s));
  assert.ok(bounds.min.x >= 128 && bounds.max.y < HEIGHT);
  assert.deepEqual(data, before);
  sectors.forEach(s => kit.release(s)); kit.dispose();
});

test('Paris monuments and bridges keep classic collision and replace only their own generated voxels', () => {
  const data = generateWorld(73129), hidden = new Set(planModels(data).hidden);
  for (const voxel of [...ARC_VOXELS, ...CAROUSEL_VOXELS, ...PARIS_BRIDGE_VOXELS])
    assert.ok(hidden.has(index(voxel.x, voxel.y, voxel.z)));
  const kit = new ModelKit(), models = parisLandmarks(kit);
  assert.equal(models.children.length, 4);
  const bounds = new THREE.Box3().setFromObject(models);
  assert.ok(bounds.min.x >= 230 && bounds.max.x < SIZE && bounds.max.y < HEIGHT);
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
