import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { WorldStore } from '../backend/src/database/store';
import { Block, getBlock, SAVE_VERSION } from '../shared/world';
import { Simulation } from '../backend/src/simulation/engine';
import { hutBlocks } from '../backend/src/buildings/hut';
test('edits, original seed, version, revision and clock survive reopening SQLite', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-')), path = join(dir, 'world.sqlite');
  try {
    const store = new WorldStore(path, 73129);
    store.edit({ type: 'edit', x: 32, y: 11, z: 40, block: Block.Wood, expected: 0 });
    store.edit({ type: 'edit', x: 32, y: 10, z: 40, block: 0, expected: Block.Grass });
    store.time = 2000; store.speed = 5; store.close();
    const restored = new WorldStore(path, 123);
    assert.equal(restored.seed, 73129); assert.equal(restored.revision, 2); assert.equal(restored.time, 2000); assert.equal(restored.speed, 5);
    assert.equal(getBlock(restored.data, 32, 11, 40), Block.Wood);
    assert.equal(getBlock(restored.data, 32, 10, 40), Block.Air);
    assert.equal(restored.snapshot().edits.length, 2); restored.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('restoring a generated block removes its stored difference', () => {
  const store = new WorldStore(':memory:', 73129);
  store.edit({ type: 'edit', x: 32, y: 10, z: 40, block: 0, expected: 1 });
  store.edit({ type: 'edit', x: 32, y: 10, z: 40, block: 1, expected: 0 });
  assert.equal(store.edits().length, 0); assert.equal(store.revision, 2); store.close();
});
test('invalid, conflicting, occupied, empty and bedrock edits do not mutate the database', () => {
  const store = new WorldStore(':memory:', 73129), initial = store.data.slice();
  for (const edit of [
    { x: -1, y: 11, z: 40, block: 5, expected: 0 }, { x: 32, y: 32, z: 40, block: 5, expected: 0 },
    { x: 32, y: 0, z: 40, block: 0, expected: 3 }, { x: 32, y: 10, z: 40, block: 5, expected: 1 },
    { x: 32, y: 11, z: 40, block: 0, expected: 0 }, { x: 32, y: 11, z: 40, block: 5, expected: 1 },
    { x: 32, y: 11, z: 40, block: 7, expected: 0 }
  ]) assert.throws(() => store.edit({ type: 'edit', ...edit }));
  assert.deepEqual(store.data, initial); assert.equal(store.revision, 0); assert.deepEqual(store.edits(), []); store.close();
});
test('water replacement can be undone without losing the original water', () => {
  const store = new WorldStore(':memory:', 73129);
  store.edit({ type: 'edit', x: 1, y: 5, z: 1, block: Block.Sand, expected: Block.Water });
  store.edit({ type: 'edit', x: 1, y: 5, z: 1, block: Block.Water, expected: Block.Sand });
  assert.equal(store.edits().length, 0); assert.equal(getBlock(store.data, 1, 5, 1), Block.Water); store.close();
});
test('unknown save versions are refused instead of silently overwritten', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-')), path = join(dir, 'world.sqlite');
  try {
    new WorldStore(path, 1).close();
    const db = new DatabaseSync(path); db.exec('UPDATE world SET version=999'); db.close();
    assert.throws(() => new WorldStore(path, 1), /保存バージョン/);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('Phase 1 save migration preserves seed, edited terrain, time and speed', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-migrate-')), path = join(dir, 'world.sqlite');
  try {
    const db = new DatabaseSync(path);
    db.exec(`CREATE TABLE world (id TEXT PRIMARY KEY, version INTEGER, seed INTEGER, revision INTEGER, time REAL, speed INTEGER);
      INSERT INTO world VALUES('island-1',1,73129,1,2000,5);
      CREATE TABLE edits (x INTEGER,y INTEGER,z INTEGER,block INTEGER,PRIMARY KEY(x,y,z));
      INSERT INTO edits VALUES(32,11,40,5);`); db.close();
    const store = new WorldStore(path, 1);
    assert.equal(store.snapshot().version, SAVE_VERSION); assert.equal(store.seed, 73129); assert.equal(store.time, 2000); assert.equal(store.speed, 5);
    assert.equal(getBlock(store.data, 32, 11, 40), Block.Wood); assert.equal(store.edits().length, 1);
    const sim = new Simulation(store.data); store.saveVillage(sim.state); store.close();
    const restored = new WorldStore(path, 1); assert.equal(restored.village!.residents.length, 5); restored.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('residents, reserved resources and partial construction resume without double spending', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-resume-')), path = join(dir, 'world.sqlite');
  try {
    const store = new WorldStore(path, 73129), sim = new Simulation(store.data);
    for (let i = 0; i < 1000; i++) {
      const edits = sim.step(0.25, store.time); store.time += 0.25;
      store.saveVillage(sim.state, edits);
      if (sim.state.huts.some(h => h.progress >= 12 && h.status === 'building')) break;
    }
    assert.ok(sim.state.huts[0].progress >= 12);
    const saved = JSON.parse(JSON.stringify(sim.state)); store.close();
    const restored = new WorldStore(path, 73129), resumed = new Simulation(restored.data, restored.village);
    assert.deepEqual(resumed.state.resources, saved.resources);
    assert.deepEqual(resumed.state.huts, saved.huts);
    assert.deepEqual(resumed.state.residents.map(r => r.inventory), saved.residents.map((r: { inventory: unknown }) => r.inventory));
    const resources = { ...resumed.state.resources };
    for (let i = 0; i < 100; i++) {
      const edits = resumed.step(0.25, restored.time); restored.time += 0.25; restored.saveVillage(resumed.state, edits);
    }
    assert.ok(resumed.state.huts[0].progress > saved.huts[0].progress);
    assert.ok(resumed.state.resources.wood >= resources.wood); assert.ok(resumed.state.resources.stone >= resources.stone);
    for (const h of resumed.state.huts) for (const block of hutBlocks(h).slice(0, h.progress)) assert.equal(getBlock(restored.data, block.x, block.y, block.z), block.block);
    restored.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('player edits protect resident bodies, their supporting block, and hut reservations', () => {
  const store = new WorldStore(':memory:', 73129), sim = new Simulation(store.data); store.saveVillage(sim.state);
  const hut = sim.state.huts[0], resident = sim.state.residents[0];
  assert.throws(() => store.edit({ type: 'edit', x: hut.x, y: hut.y, z: hut.z, block: 5, expected: 0 }), /建築敷地/);
  assert.throws(() => store.edit({ type: 'edit', x: Math.floor(resident.position.x), y: resident.position.y, z: Math.floor(resident.position.z), block: 5, expected: 0 }), /住民/);
  assert.throws(() => store.edit({ type: 'edit', x: Math.floor(resident.position.x), y: resident.position.y - 1, z: Math.floor(resident.position.z), block: 0, expected: 1 }), /住民/);
  assert.equal(store.revision, 0); assert.equal(store.edits().length, 0); store.close();
});
