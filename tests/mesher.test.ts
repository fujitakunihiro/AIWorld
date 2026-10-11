import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Block, SIZE, HEIGHT, getBlock, index, generateWorld } from '../shared/world';
import { meshChunk, type MeshData } from '../shared/mesher';
function area(mesh: MeshData) {
  let result = 0;
  for (let i = 0; i < mesh.positions.length; i += 12) {
    const a = [0, 1, 2].map(d => mesh.positions[i + 3 + d] - mesh.positions[i + d]);
    const b = [0, 1, 2].map(d => mesh.positions[i + 9 + d] - mesh.positions[i + d]);
    result += Math.hypot(a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]);
  }
  return result;
}
test('greedy meshing collapses a solid cube to six correctly wound quads', () => {
  const data = new Uint8Array(SIZE * SIZE * HEIGHT);
  for (let x = 3; x < 7; x++) for (let y = 3; y < 7; y++) for (let z = 3; z < 7; z++) data[index(x, y, z)] = Block.Stone;
  const { solid } = meshChunk(data, 0, 0);
  assert.equal(solid.indices.length, 36); assert.equal(area(solid), 96);
  for (let i = 0; i < solid.indices.length; i += 3) {
    const [a, b, c] = solid.indices.slice(i, i + 3).map(v => solid.positions.slice(v * 3, v * 3 + 3));
    const u = b.map((v, d) => v - a[d]), v = c.map((value, d) => value - a[d]);
    const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const normal = solid.normals.slice(solid.indices[i] * 3, solid.indices[i] * 3 + 3);
    assert.ok(n.reduce((sum, value, d) => sum + value * normal[d], 0) > 0);
  }
});
test('adjacent chunks hide shared solid faces', () => {
  const data = new Uint8Array(SIZE * SIZE * HEIGHT);
  data[index(15, 8, 8)] = Block.Stone; data[index(16, 8, 8)] = Block.Stone;
  assert.equal(area(meshChunk(data, 0, 0).solid) + area(meshChunk(data, 1, 0).solid), 10);
});
test('water internal faces are culled while adjoining solid faces remain visible', () => {
  const data = new Uint8Array(SIZE * SIZE * HEIGHT);
  data[index(8, 8, 8)] = Block.Water; data[index(9, 8, 8)] = Block.Water; data[index(10, 8, 8)] = Block.Stone;
  const mesh = meshChunk(data, 0, 0);
  assert.equal(area(mesh.water), 9); assert.equal(area(mesh.solid), 6);
});
test('greedy terrain surface area equals independently counted exposed voxel faces', () => {
  const data = generateWorld(73129);
  const expected = { solid: 0, water: 0 };
  const directions = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
  for (let y = 0; y < HEIGHT; y++) for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
    const a = getBlock(data, x, y, z); if (!a) continue;
    for (const [dx, dy, dz] of directions) {
      const b = getBlock(data, x + dx, y + dy, z + dz);
      if (b === Block.Air || (a !== Block.Water && b === Block.Water)) expected[a === Block.Water ? 'water' : 'solid']++;
    }
  }
  const actual = { solid: 0, water: 0 };
  for (let cz = 0; cz < 4; cz++) for (let cx = 0; cx < 4; cx++) {
    const mesh = meshChunk(data, cx, cz); actual.solid += area(mesh.solid); actual.water += area(mesh.water);
  }
  assert.deepEqual(actual, expected);
});
