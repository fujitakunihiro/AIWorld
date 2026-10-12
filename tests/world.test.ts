import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ARC, Block, EIFFEL, HEIGHT, NOTRE_DAME, SIZE, generateWorld, getBlock, inCite, index, inside, riverCenter } from '../shared/world';
import { commandSchema } from '../shared/schema';
test('the regenerated world uses a continuous Paris street plan around the Seine', () => {
  const world = generateWorld(73129);
  assert.equal(getBlock(world, 32, 8, 40), Block.Grass, 'the existing starter clearing stays open');
  for (const [x, z] of [[100, 258], [148, 98], [266, 156], [194, 194]])
    assert.notEqual(getBlock(world, x, 8, z), Block.Water, 'landmarks have a walkable site');
  assert.equal(EIFFEL.x, 104); assert.equal(ARC.z, 98); assert.equal(NOTRE_DAME.z, 194);
  const riverX = Math.round(riverCenter(120));
  assert.equal(getBlock(world, riverX, 6, 120), Block.Water);
  assert.equal(getBlock(world, riverX - 30, 8, 120), Block.Stone);
  assert.equal(getBlock(world, riverX + 30, 8, 120), Block.Stone);
});
test('384×384×32 terrain is deterministic and changes with seed', () => {
  const world = generateWorld(73129);
  assert.equal(world.length, SIZE * SIZE * HEIGHT);
  assert.deepEqual(world, generateWorld(73129));
  assert.notDeepEqual(world, generateWorld(100));
  assert.ok([...world].every(block => block >= 0 && block <= 8));
});
test('terrain contains parks, a navigable Seine, quays, and flat building sites', () => {
  const world = generateWorld(73129);
  for (const block of [Block.Grass, Block.Dirt, Block.Stone, Block.Sand, Block.Wood, Block.Leaves, Block.Water, Block.Brick]) assert.ok(world.includes(block));
  for (let z = 30; z < SIZE - 30; z += 30) if (!inCite(riverCenter(z), z)) assert.equal(getBlock(world, Math.round(riverCenter(z)), 6, z), Block.Water);
  for (let x = 29; x <= 39; x++) for (let z = 35; z <= 45; z++) {
    assert.equal(getBlock(world, x, 8, z), Block.Grass);
    assert.equal(getBlock(world, x, 9, z), Block.Air);
  }
  assert.equal(getBlock(world, 0, 8, 0), Block.Stone);
  assert.equal(getBlock(world, 43, 14, 23), Block.Air);
});
test('bounds and indexing cannot alias invalid positions', () => {
  const world = generateWorld(4);
  for (const p of [[-1, 0, 0], [SIZE, 0, 0], [0, HEIGHT, 0], [0, 0, SIZE], [1.5, 2, 3]]) {
    assert.equal(inside(p[0], p[1], p[2]), false); assert.equal(getBlock(world, p[0], p[1], p[2]), Block.Air);
  }
  assert.equal(index(SIZE - 1, HEIGHT - 1, SIZE - 1), world.length - 1);
});
test('schema rejects out-of-range coordinates, arbitrary code, invalid block types and speed', () => {
  const valid = { type: 'edit', x: 20, y: 10, z: 30, block: 5, expected: 0 };
  assert.ok(commandSchema.safeParse(valid).success);
  for (const patch of [{ x: SIZE }, { y: HEIGHT }, { z: -1 }, { x: 1.2 }, { block: 99 }, { block: 'wood' }, { expected: -1 }, { code: 'alert(1)' }]) assert.equal(commandSchema.safeParse({ ...valid, ...patch }).success, false);
  for (const speed of [0, 1, 5, 20]) assert.ok(commandSchema.safeParse({ type: 'speed', speed }).success);
  assert.equal(commandSchema.safeParse({ type: 'speed', speed: 100 }).success, false);
});
