import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Block, SIZE, HEIGHT, generateWorld, getBlock, index, inside } from '../shared/world';
import { commandSchema } from '../shared/schema';
test('64×64×32 terrain is deterministic and changes with seed', () => {
  const world = generateWorld(73129);
  assert.equal(world.length, SIZE * SIZE * HEIGHT);
  assert.deepEqual(world, generateWorld(73129));
  assert.notDeepEqual(world, generateWorld(100));
  assert.ok([...world].every(block => block >= 0 && block <= 8));
});
test('terrain contains forest, river, mountain, beach, ocean, and a flat building site', () => {
  const world = generateWorld(73129);
  for (const block of [Block.Grass, Block.Dirt, Block.Stone, Block.Sand, Block.Wood, Block.Leaves, Block.Water]) assert.ok(world.includes(block));
  for (let z = 0; z < 64; z++) {
    const x = Math.round(24 + Math.sin(z / 8) * 3);
    assert.equal(getBlock(world, x, 5, z), Block.Water);
  }
  for (let x = 29; x <= 39; x++) for (let z = 35; z <= 45; z++) {
    assert.equal(getBlock(world, x, 10, z), Block.Grass);
    assert.equal(getBlock(world, x, 11, z), Block.Air);
  }
  assert.equal(getBlock(world, 0, 5, 0), Block.Water);
  assert.notEqual(getBlock(world, 43, 16, 23), Block.Air);
});
test('bounds and indexing cannot alias invalid positions', () => {
  const world = generateWorld(4);
  for (const p of [[-1, 0, 0], [64, 0, 0], [0, 32, 0], [0, 0, 64], [1.5, 2, 3]]) {
    assert.equal(inside(p[0], p[1], p[2]), false); assert.equal(getBlock(world, p[0], p[1], p[2]), Block.Air);
  }
  assert.equal(index(63, 31, 63), world.length - 1);
});
test('schema rejects out-of-range coordinates, arbitrary code, invalid block types and speed', () => {
  const valid = { type: 'edit', x: 20, y: 10, z: 30, block: 5, expected: 0 };
  assert.ok(commandSchema.safeParse(valid).success);
  for (const patch of [{ x: 64 }, { y: 32 }, { z: -1 }, { x: 1.2 }, { block: 99 }, { block: 'wood' }, { expected: -1 }, { code: 'alert(1)' }]) assert.equal(commandSchema.safeParse({ ...valid, ...patch }).success, false);
  for (const speed of [0, 1, 5, 20]) assert.ok(commandSchema.safeParse({ type: 'speed', speed }).success);
  assert.equal(commandSchema.safeParse({ type: 'speed', speed: 100 }).success, false);
});
