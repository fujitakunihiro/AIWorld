import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { Simulation } from '../backend/src/simulation/engine';
import { WorldStore } from '../backend/src/database/store';
import { villageSchema } from '../backend/src/database/village-schema';
import { Block, generateWorld, getBlock, SAVE_VERSION } from '../shared/world';
import { ISLANDS } from '../backend/src/buildings/bridge';
import { evaluateUtility, type UtilityContext } from '../backend/src/agents/utility';
const fresh = () => new Simulation(generateWorld(73129));
function advance(s: Simulation, minutes: number) { const edits = []; for (let i = 0; i < minutes * 4; i++) edits.push(...s.step(.25, 480 + s.state.elapsed)); return edits; }
const diagnostic = (s: Simulation) => JSON.stringify({ resources: s.state.resources, huts: s.state.huts, bridges: s.state.bridges.map(b => ({ name: b.name, status: b.status, progress: b.progress, total: b.blocks.length })), tasks: s.state.tasks.filter(t => t.kind !== 'gather'), people: s.state.residents.map(r => ({ name: r.name, action: r.action, task: r.task, reason: r.reason, energy: r.energy, hunger: r.hunger })) });

test('A: food shortage makes the food specialist choose food over material gathering', () => {
  const s = fresh(); s.state.resources.food = 0;
  for (const r of s.state.residents) { r.energy = 90; r.hunger = 10; r.decisionIn = 0; }
  s.step(.25, 480);
  const farmer = s.state.residents.find(r => r.id === 'sora')!;
  assert.equal(farmer.ai.chosen, 'food', diagnostic(s));
  assert.ok(s.state.issues.includes('食料不足'));
  assert.ok(s.state.residents.filter(r => r.ai.chosen === 'food').length >= 2);
  assert.ok(farmer.ai.scores.find(c => c.action === 'food')!.factors.some(f => f.label === '食料備蓄の不足' && f.value > 0));
});
test('B: housing shortage creates a reachable residential construction task', () => {
  const s = fresh(); s.step(.25, 480);
  assert.ok(s.state.issues.includes('住宅不足'));
  const task = s.state.tasks.find(t => t.kind === 'build')!;
  assert.ok(task); assert.ok(task.priority > 0); assert.equal(task.requiredPeople, 1);
  assert.ok(s.state.huts.some(h => h.id === task.targetId && ['hut', 'house'].includes(h.kind)));
  assert.ok(s.nav.path(s.state.camp, task.location));
  assert.ok(s.state.chronicle.some(e => e.text.includes('住宅不足')));
});
test('C: insufficient wood postpones construction and assigns a wood collector', () => {
  const s = fresh(); s.state.resources = { food: 100, wood: 0, stone: 8 }; s.state.nodes = s.state.nodes.filter(n => n.kind === 'wood');
  for (const r of s.state.residents) { r.hunger = 0; r.decisionIn = 0; }
  s.step(.25, 480);
  assert.equal(s.state.huts[0].materialsReserved, false);
  assert.ok(s.state.residents.some(r => r.ai.chosen === 'wood'));
  assert.ok(s.state.residents[0].ai.scores.find(c => c.action === 'build')!.reason.includes('必要資源'));
});
test('D: an exhausted resident selects rest and recovers energy', () => {
  const s = fresh(), r = s.state.residents[0]; r.energy = 5; r.hunger = 0; r.decisionIn = 0; s.state.resources.food = 100;
  s.step(.25, 480); assert.equal(r.ai.chosen, 'rest'); assert.equal(r.action, 'resting');
  assert.ok(r.ai.scores.find(c => c.action === 'rest')!.score > 200);
  advance(s, 5); assert.ok(r.energy > 8);
});
test('E: construction materials and work sites are claimed only once by multiple builders', () => {
  const s = fresh(); s.state.resources = { food: 100, wood: 24, stone: 8 }; s.state.nodes = []; s.state.nextPlan = 1e9;
  for (const r of s.state.residents) { r.traits.specialty = 'build'; r.job = '建築家'; r.hunger = 0; r.decisionIn = 0; }
  advance(s, 5);
  assert.equal(s.state.resources.wood, 0); assert.equal(s.state.resources.stone, 0); assert.equal(s.state.huts[0].materialsReserved, true);
  const task = s.state.tasks.find(t => t.targetId === s.state.huts[0].id)!;
  assert.equal(task.assignees.length, 1); assert.equal(task.reservedResources.wood, 24);
  advance(s, 50); assert.equal(s.state.resources.wood, 0); assert.equal(s.state.resources.stone, 0);
  assert.equal(s.state.chronicle.filter(e => e.buildingId === s.state.huts[0].id && e.text.includes('一度だけ')).length, 1);
});
test('F: unreachable resources are excluded, remembered with a retry cooldown, and never repeatedly assigned', () => {
  const s = fresh(); s.state.resources = { food: 100, wood: 0, stone: 0 };
  for (let z = 122; z <= 125; z++) for (let x = 122; x <= 125; x++) s.terrainChanged({ x, y: 10, z, block: Block.Grass });
  s.terrainChanged({ x: 124, y: 11, z: 124, block: Block.Wood }); s.step(0, 480);
  s.state.nodes = [{ id: 'isolated', kind: 'wood', position: { x: 124.5, y: 11, z: 124.5 }, remaining: 24, capacity: 24, regeneration: 0 }];
  advance(s, 250);
  assert.ok(s.state.residents.some(r => r.ai.failures.some(f => f.taskId === 'gather:isolated' && f.reason.includes('到達'))));
  assert.equal(s.state.tasks.find(t => t.id === 'gather:isolated')!.assignees.length, 0);
  assert.equal(s.state.nodes[0].remaining, 24);
  assert.ok(s.state.residents.every(r => !r.ai.history.some(e => e.outcome === 'selected' && e.taskId === 'gather:isolated')));
});
test('G: 1000 simulation steps run autonomously, develop the village, and keep state bounded', () => {
  const s = fresh(); let edits = 0;
  for (let i = 0; i < 1000; i++) { edits += s.step(1, 480 + s.state.elapsed).length; assert.ok(Object.values(s.state.resources).every(n => Number.isFinite(n) && n >= 0)); }
  assert.ok(edits > 200); assert.ok(s.state.huts.some(h => h.kind === 'farm' && h.status === 'complete'), diagnostic(s));
  assert.ok(s.state.civilization.harvests > 0); assert.ok(s.state.tasks.length <= 160); assert.ok(s.state.chronicle.length <= 300);
  for (const r of s.state.residents) { assert.ok(r.ai.history.length <= 20); assert.ok(r.ai.failures.length <= 16); assert.ok(r.ai.scores.every(c => Number.isFinite(c.score))); }
  assert.ok(villageSchema.safeParse(s.state).success, diagnostic(s));
});
test('H: reservations, task ownership, paths and bridges survive SQLite restore and continue identically', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-ai-')), path = join(dir, 'world.sqlite');
  try {
    const store = new WorldStore(path, 73129), s = new Simulation(store.data); const edits = advance(s, 100);
    store.time = 480 + s.state.elapsed; store.saveVillage(s.state, edits); store.close();
    const reopened = new WorldStore(path, 2), restored = new Simulation(reopened.data, reopened.village);
    assert.deepEqual(restored.state, s.state); assert.deepEqual(restored.data, s.data);
    advance(restored, 80); advance(s, 80); assert.deepEqual(restored.state, s.state); assert.deepEqual(restored.data, s.data);
    for (const task of restored.state.tasks) { assert.ok(task.assignees.length <= task.requiredPeople); for (const id of task.assignees) assert.equal(restored.state.residents.find(r => r.id === id)!.ai.taskId, task.id); }
    assert.ok(villageSchema.safeParse(restored.state).success); reopened.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('traits create explainable choices; the displayed score equals the sum of its factors', () => {
  const s = fresh(), r = s.state.residents[0];
  const c: UtilityContext = { resident: r, population: 5, food: 100, wood: 100, stone: 100, woodNeeded: 0, stoneNeeded: 0, housingShortage: 0, distance: 0, priority: 0, night: false, continuing: false, ripe: false };
  r.traits.sociability = 1; r.traits.curiosity = 0;
  assert.ok(evaluateUtility('social', c, null).score > evaluateUtility('explore', c, null).score);
  r.traits.sociability = 0; r.traits.curiosity = 1;
  assert.ok(evaluateUtility('social', c, null).score < evaluateUtility('explore', c, null).score);
  for (const action of ['food', 'wood', 'stone', 'build', 'farm', 'rest', 'social', 'explore'] as const) {
    const result = evaluateUtility(action, c, null);
    assert.equal(result.score, Math.round(result.factors.reduce((n, f) => n + f.value, 0) * 10) / 10);
  }
});
test('blocked construction is detected as stagnant and retains the one-time material reservation', () => {
  const s = fresh(), hut = s.state.huts[0]; s.state.nodes = []; s.state.resources = { food: 100, wood: 24, stone: 8 }; s.state.nextPlan = 1e9;
  s.terrainChanged({ x: hut.x, y: hut.y, z: hut.z, block: Block.Brick });
  advance(s, 160);
  const task = s.state.tasks.find(t => t.id === `build:${hut.id}`)!;
  assert.equal(hut.progress, 0); assert.equal(hut.materialsReserved, true); assert.equal(s.state.resources.wood, 0);
  assert.ok(s.state.residents.some(r => r.ai.history.some(e => e.outcome === 'failed' && e.text.includes('停滞'))));
  assert.ok(task.failure.includes('停滞')); assert.ok(task.retryAt > s.state.elapsed); assert.equal(task.assignees.length, 0);
});
test('bridges are built from the shore, connect every island and preserve the original terrain', () => {
  const s = fresh(); s.state.resources = { food: 2000, wood: 2000, stone: 2000 };
  const original = s.data.slice(), edits = advance(s, 2000);
  assert.ok(s.state.bridges.filter(b => b.status === 'complete').length >= 3, diagnostic(s));
  for (const island of ISLANDS) {
    const target = s.nav.nearest({ x: island.x + .5, y: 7, z: island.z + .5 })!;
    assert.ok(s.nav.path(s.state.camp, target), `${island.name}: ${diagnostic(s)}`);
  }
  for (const bridge of s.state.bridges) { assert.equal(bridge.progress, bridge.blocks.length); for (const e of bridge.blocks) { assert.equal(getBlock(s.data, e.x, e.y, e.z), Block.Wood); assert.equal(getBlock(original, e.x, e.y, e.z), Block.Air); } }
  assert.ok(edits.some(e => s.state.bridges.some(b => b.blocks.some(p => p.x === e.x && p.z === e.z))));
});
test('a Phase 5 save migrates personal traits and the job board without losing the existing world', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-ai-migrate-')), path = join(dir, 'world.sqlite');
  try {
    const store = new WorldStore(path, 73129), s = fresh(); advance(s, 40);
    const old: any = structuredClone(s.state); old.version = 3; delete old.tasks; delete old.bridges; delete old.issues; delete old.nextTaskEvaluation; delete old.nextBridgePlan;
    for (const r of old.residents) { delete r.traits; delete r.ai; }
    store.close(); const db = new DatabaseSync(path); db.exec('UPDATE world SET version=4'); db.prepare('INSERT INTO simulation VALUES(1,?)').run(JSON.stringify(old)); db.close();
    const restored = new WorldStore(path, 9);
    assert.equal(restored.snapshot().version, SAVE_VERSION); assert.equal(restored.village!.version, 4); assert.deepEqual(restored.village!.camp, old.camp);
    assert.deepEqual(restored.village!.residents.map(r => r.position), old.residents.map((r: any) => r.position));
    assert.ok(restored.village!.residents.every(r => r.traits && r.ai)); assert.deepEqual(restored.village!.tasks, []); restored.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('exploration of a new island discovers finite resource sites and records actual findings', () => {
  const s = fresh(), r = s.state.residents[0], p = s.nav.position(100, 42)!; assert.ok(p);
  r.position = { ...p }; r.path = []; r.task = { kind: 'explore', targetId: null, destination: p }; r.ai.chosen = 'explore'; r.hunger = 0; r.energy = 90;
  advance(s, 4.25);
  for (const kind of ['food', 'stone']) assert.ok(s.state.nodes.some(n => n.kind === kind && n.position.x > 64));
  assert.ok(s.state.chronicle.some(e => e.residentIds?.includes(r.id) && e.text.includes('採集地')));
  assert.ok(r.memories.some(m => m.includes('周辺を探索'))); assert.ok(s.state.nodes.length <= 64);
});
test('at the population limit, enough beds do not create an impossible spare-housing goal', () => {
  const s = fresh(), hut = s.state.huts[0];
  s.state.huts = Array.from({ length: 5 }, (_, i) => ({ ...structuredClone(hut), id: `home-${i}`, kind: 'house' as const, status: 'complete' as const, progress: hut.total, x: 12 + i * 6, materialsReserved: true }));
  while (s.state.residents.length < 20) { const n = s.state.residents.length; s.state.residents.push({ ...structuredClone(s.state.residents[0]), id: `test-${n}`, home: s.state.huts[Math.floor(n / 4)].id }); }
  s.state.civilization.arrivals = 15; s.state.resources.food = 100; s.state.nextPlan = 1e9; s.step(.25, 480);
  assert.equal(s.state.issues.includes('住宅不足'), false);
});
