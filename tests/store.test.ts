import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { WorldStore } from '../backend/src/database/store';
import { Block, getBlock } from '../shared/world';
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
