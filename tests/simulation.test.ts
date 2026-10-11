import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Block, HEIGHT, SIZE, generateWorld, getBlock, index } from '../shared/world';
import { Simulation } from '../backend/src/simulation/engine';
import { Navigation } from '../backend/src/agents/navigation';
import { hutBlocks } from '../backend/src/buildings/hut';
import { villageSchema } from '../backend/src/database/village-schema';
const advance = (sim: Simulation, minutes: number, time = 480) => {
  const edits = [];
  for (let i = 0; i < minutes * 4; i++) edits.push(...sim.step(0.25, time + i / 4));
  return edits;
};
function diagnostic(sim: Simulation) {
  return JSON.stringify({ resources: sim.state.resources, huts: sim.state.huts, residents: sim.state.residents.map(r => ({ name: r.name, position: r.position, action: r.action, task: r.task, inventory: r.inventory, reason: r.reason })) });
}
test('five unique residents have reachable gathering sites, personal state and reasons without an API', () => {
  const data = generateWorld(73129), original = data.slice(), sim = new Simulation(data);
  assert.equal(sim.state.residents.length, 5); assert.equal(new Set(sim.state.residents.map(r => r.id)).size, 5);
  assert.ok(villageSchema.safeParse(sim.state).success);
  assert.deepEqual(data, original);
  for (const kind of ['wood', 'stone', 'food']) assert.ok(sim.state.nodes.some(n => n.kind === kind));
  advance(sim, 2);
  for (const r of sim.state.residents) { assert.ok(r.reason.length > 5); assert.ok(r.task); assert.ok(r.path.every(p => sim.nav.valid(p))); }
});
test('an unassisted village gathers, transports resources and completes three habitable huts', () => {
  const sim = new Simulation(generateWorld(73129));
  const start = sim.state.residents.map(r => ({ ...r.position }));
  const edits = advance(sim, 380);
  assert.equal(sim.state.huts.filter(h => h.status === 'complete').length, 3, diagnostic(sim));
  assert.equal(sim.state.residents.filter(r => r.home).length, 5);
  assert.ok(edits.length > 100);
  assert.ok(sim.state.events.some(e => e.text.includes('届けました')));
  assert.ok(sim.state.events.some(e => e.text.includes('完成')));
  assert.ok(sim.state.residents.some((r, i) => r.position.x !== start[i].x || r.position.z !== start[i].z));
  for (const hut of sim.state.huts) {
    assert.equal(hut.progress, hut.total); assert.ok(hut.materialsReserved);
    for (const block of hutBlocks(hut)) assert.equal(getBlock(sim.data, block.x, block.y, block.z), block.block);
    assert.ok(sim.nav.path(sim.state.camp, { x: hut.x + 1.5, y: hut.y + 1, z: hut.z + 2.5 }), JSON.stringify({hut, camp: sim.state.camp, bedHeight: sim.nav.height(hut.x + 1, hut.z + 2), doorHeight: sim.nav.height(hut.x + 1, hut.z + 3), outsideHeight: sim.nav.height(hut.x + 1, hut.z + 4)}));
  }
  for (const amount of Object.values(sim.state.resources)) assert.ok(amount >= 0);
  assert.ok(villageSchema.safeParse(sim.state).success, diagnostic(sim));
});
test('construction never starts with insufficient resources', () => {
  const sim = new Simulation(generateWorld(73129)); sim.state.nodes = []; sim.state.resources = { food: 20, wood: 23, stone: 8 };
  const edits = advance(sim, 50);
  assert.equal(edits.length, 0); assert.equal(sim.state.huts[0].status, 'planned'); assert.equal(sim.state.huts[0].progress, 0);
  assert.equal(sim.state.resources.wood, 23); assert.equal(sim.state.resources.stone, 8);
});
test('hungry residents actually consume shared food rather than receiving free hunger reduction', () => {
  const sim = new Simulation(generateWorld(73129)); sim.state.nodes = []; sim.state.resources.food = 5;
  for (const r of sim.state.residents) { r.position = { ...sim.state.camp }; r.hunger = 70; r.decisionIn = 0; }
  advance(sim, 8);
  assert.equal(sim.state.resources.food, 0);
  assert.ok(sim.state.residents.every(r => r.hunger < 30));
});
test('depleted resources stay finite, regenerate, and residents keep bounded memories and work', () => {
  const sim = new Simulation(generateWorld(73129));
  for (const node of sim.state.nodes) node.remaining = 0;
  assert.equal(advance(sim, 40).length, 0);
  assert.equal(sim.state.huts[0].progress, 0);
  advance(sim, 800, 520);
  for (const node of sim.state.nodes) assert.ok(node.remaining >= 0 && node.remaining <= node.capacity);
  for (const r of sim.state.residents) {
    assert.ok(r.memories.length <= 8); assert.ok(r.path.length <= SIZE * SIZE);
    assert.ok(Object.values(r.inventory).reduce((a, b) => a + b) <= 8);
  }
  assert.ok(sim.state.events.length <= 30); assert.ok(villageSchema.safeParse(sim.state).success);
});
test('fixed substeps produce the same simulation at 1× and 20×; pause makes no changes', () => {
  const normal = new Simulation(generateWorld(73129)), fast = new Simulation(generateWorld(73129));
  advance(normal, 100);
  for (let i = 0; i < 20; i++) fast.step(5, 480 + i * 5);
  assert.deepEqual(normal.state, fast.state); assert.deepEqual(normal.data, fast.data);
  const snapshot = JSON.stringify(fast.state); fast.step(0, 580); assert.equal(JSON.stringify(fast.state), snapshot);
});
test('navigation avoids water, blocked headroom, cliffs and diagonal corner cutting', () => {
  const data = new Uint8Array(SIZE * SIZE * HEIGHT);
  for (let x = 8; x < 18; x++) for (let z = 8; z < 18; z++) data[index(x, 0, z)] = Block.Grass;
  for (let z = 8; z < 18; z++) data[index(12, 1, z)] = Block.Water;
  data[index(10, 1, 10)] = Block.Stone; data[index(10, 2, 10)] = Block.Stone; data[index(10, 3, 10)] = Block.Stone;
  const nav = new Navigation(data);
  assert.equal(nav.height(12, 10), -1);
  assert.equal(nav.path({ x: 9.5, y: 1, z: 9.5 }, { x: 14.5, y: 1, z: 9.5 }), null);
  const route = nav.path({ x: 9.5, y: 1, z: 9.5 }, { x: 11.5, y: 1, z: 11.5 })!;
  assert.ok(route); assert.ok(route.every(p => !(Math.floor(p.x) === 10 && Math.floor(p.z) === 10)));
  for (let i = 1; i < route.length; i++) assert.equal(Math.abs(route[i].x - route[i - 1].x) + Math.abs(route[i].z - route[i - 1].z), 1);
});
test('terrain changes invalidate blocked paths and gathering sites instead of walking through them', () => {
  const sim = new Simulation(generateWorld(73129)); advance(sim, 3);
  const r = sim.state.residents.find(r => r.path.length)!; assert.ok(r);
  const p = r.path.at(-1)!;
  for (let y = p.y; y < p.y + 3; y++) sim.terrainChanged({ x: Math.floor(p.x), y, z: Math.floor(p.z), block: Block.Stone });
  advance(sim, 2, 483);
  for (const resident of sim.state.residents) assert.ok(resident.path.every(p => sim.nav.valid(p)));
});
