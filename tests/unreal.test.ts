import { test } from 'node:test';
import assert from 'node:assert/strict';
import { unrealScene } from '../backend/src/presentation/unreal';
import { WorldStore } from '../backend/src/database/store';
import { Simulation } from '../backend/src/simulation/engine';
import { SIZE, HEIGHT, index } from '../shared/world';
test('Unreal presentation preserves base, saved edits and village without mutating simulation', () => {
  const store = new WorldStore(':memory:',73129);const simulation = new Simulation(store.data,store.village);
  const before = structuredClone(simulation.state), bytes = store.data.slice();
  const scene = unrealScene(store.base,store.data,simulation.state);
  assert.equal(scene.format,1);assert.equal(scene.size,SIZE);assert.equal(scene.height,HEIGHT);
  assert.deepEqual(Buffer.from(scene.base,'base64'),Buffer.from(store.base));
  assert.deepEqual(store.data,bytes);assert.deepEqual(simulation.state,before);
  assert.ok(scene.trees.length>0);assert.ok(scene.hidden.length>0);
  for(const tree of scene.trees)assert.deepEqual(tree.expected,tree.hidden.map(i=>bytes[i]));
  for(const hut of simulation.state.huts)assert.ok(!scene.hidden.includes(index(hut.x,hut.y,hut.z)));
  store.close();
});
