import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import { Simulation } from '../backend/src/simulation/engine';
import { WorldStore } from '../backend/src/database/store';
import { villageSchema } from '../backend/src/database/village-schema';
import { buildingBlocks } from '../backend/src/buildings/development';
import { parseRules } from '../backend/src/llm/rules';
import { beds, growthRequirements, MAX_POPULATION } from '../shared/village';
import { generateWorld, SAVE_VERSION } from '../shared/world';
const advance = (s: Simulation, minutes: number) => { const edits = []; for (let i = 0; i < minutes * 4; i++) edits.push(...s.step(.25, 480 + s.state.elapsed)); return edits; };
const fresh = () => new Simulation(generateWorld(73129));

test('without instructions a settlement farms, builds homes and a warehouse, develops and welcomes residents', () => {
  const s = fresh(); advance(s, 1600);
  assert.equal(s.state.civilization.level, 2, JSON.stringify(s.state.huts));
  for (const kind of ['hut', 'farm', 'house', 'warehouse']) assert.ok(s.state.huts.some(h => h.kind === kind && h.status === 'complete'), kind);
  assert.ok(s.state.civilization.harvests > 0); assert.ok(s.state.residents.some(r => r.job === '農家'));
  assert.ok(s.state.residents.length > 5 && s.state.residents.length <= MAX_POPULATION);
  assert.ok(s.state.residents.every(r => r.home)); assert.ok(beds(s.state) >= s.state.residents.length);
  assert.ok(growthRequirements(s.state).every(r => r.met)); assert.ok(villageSchema.safeParse(s.state).success);
  for (const r of s.state.residents) assert.equal(Object.keys(r.relationships).length, s.state.residents.length - 1);
  for (const h of s.state.huts.filter(h => h.kind === 'house' && h.status === 'complete')) {
    const bed = s.nav.position(h.x + 1, h.z + 2)!; assert.ok(s.nav.path(s.state.camp, bed), JSON.stringify(h));
  }
});

test('farming harvests finite crops into inventory and requires delivery before food reaches the village', () => {
  const s = fresh(); s.state.huts = [];
  const record = s.acceptInstruction(randomUUID(), '畑', { source: 'rules', notice: '', commands: [{ action: 'build', building: 'farm', count: 1, location: 'village' }] });
  const farm = s.state.huts.find(h => h.id === record.jobs[0].hutIds[0])!;
  farm.status = 'complete'; farm.progress = farm.total; farm.materialsReserved = true;
  for (const edit of buildingBlocks(farm)) s.terrainChanged(edit);
  s.step(0, 480); s.state.nextPlan = 1e9; s.state.resources.food = 0;
  farm.crop = { stage: 'ripe', growth: 1, remaining: 32, harvests: 0 };
  for (const r of s.state.residents) { r.task = null; r.path = []; r.hunger = 0; r.energy = 90; r.action = 'resting'; r.order = { requestId: 'test', kind: 'rest', until: 1e9 }; }
  const farmer = s.state.residents[0]; farmer.job = '農家'; farmer.order = { requestId: 'farm', kind: 'farm', until: 1e9 };
  farmer.position = s.nav.position(farm.x + 1, farm.z + 4)!; farmer.action = 'idle'; farmer.decisionIn = 0;
  advance(s, 6.25);
  assert.equal(farmer.inventory.food, 8); assert.equal(s.state.resources.food, 0); assert.equal(farm.crop.remaining, 24);
  advance(s, 90);
  assert.ok(s.state.resources.food >= 24); assert.equal(farm.crop.harvests, 1); assert.equal(s.state.civilization.harvests, 1);
  assert.ok(farm.crop.remaining >= 0); assert.ok(farmer.inventory.food <= 8);
});

test('a farm reserves its cost once and cannot start without every required material', () => {
  const s = fresh(); s.state.huts = []; s.state.nodes = []; s.state.resources = { food: 100, wood: 11, stone: 4 };
  s.acceptInstruction(randomUUID(), '畑', { source: 'rules', notice: '', commands: [{ action: 'build', building: 'farm', count: 1, location: 'village' }] });
  advance(s, 30); assert.equal(s.state.huts[0].status, 'planned'); assert.equal(s.state.resources.wood, 11);
  s.state.resources.wood++; advance(s, 35);
  assert.equal(s.state.huts[0].status, 'complete'); assert.equal(s.state.resources.wood, 0); assert.equal(s.state.resources.stone, 0);
  advance(s, 35); assert.equal(s.state.resources.wood, 0); assert.equal(s.state.resources.stone, 0);
});

test('immigration requires spare completed housing and surplus food, and is bounded by its cooldown', () => {
  const s = fresh(); advance(s, 1600);
  const count = s.state.residents.length;
  s.state.resources.food = 0; s.state.nodes = []; for (const h of s.state.huts) if (h.crop) h.crop.stage = 'fallow';
  s.state.civilization.nextArrival = s.state.elapsed; s.state.nextPlan = 0;
  s.step(.25, 480 + s.state.elapsed); assert.equal(s.state.residents.length, count);
  s.state.resources.food = 500; s.state.civilization.nextArrival = s.state.elapsed; s.state.nextPlan = 0;
  s.step(.25, 480 + s.state.elapsed); assert.equal(s.state.residents.length, count + 1);
  const after = s.state.residents.length; advance(s, 300); assert.equal(s.state.residents.length, after);
  const blocked = fresh(); blocked.state.civilization.level = 2; blocked.state.resources.food = 500;
  blocked.state.civilization.nextArrival = 0; blocked.step(.25, 480); assert.equal(blocked.state.residents.length, 5);
});

test('rain accelerates planted crops, festivals consume food, and trade exchanges food for resources', () => {
  const s = fresh(); advance(s, 1600);
  const c = s.state.civilization, farm = s.state.huts.find(h => h.kind === 'farm')!;
  c.nextArrival = 1e9; c.eventSequence = 0; c.nextEventAt = s.state.elapsed; s.state.nextPlan = 0;
  farm.crop!.stage = 'growing'; farm.crop!.growth = .1; s.step(.25, 480 + s.state.elapsed);
  assert.ok(farm.crop!.growth >= .3); assert.equal(c.eventSequence, 1); assert.ok(s.state.events.some(e => e.kind === 'weather'));
  for (const r of s.state.residents) { r.task = null; r.path = []; r.decisionIn = 10; r.action = 'idle'; r.hunger = 0; r.energy = 50; }
  s.state.resources.food = 100; c.nextEventAt = s.state.elapsed; s.state.nextPlan = 0;
  s.step(.25, 480 + s.state.elapsed); assert.equal(s.state.resources.food, 100 - s.state.residents.length); assert.ok(s.state.residents.every(r => r.energy > 64));
  const before = { ...s.state.resources }; c.nextEventAt = s.state.elapsed; s.state.nextPlan = 0;
  s.step(.25, 480 + s.state.elapsed); assert.equal(s.state.resources.food, before.food - 6); assert.equal(s.state.resources.wood, before.wood + 8); assert.equal(s.state.resources.stone, before.stone + 4);
});

test('development, arrivals, crops and events are identical at normal and accelerated speed; pause freezes everything', () => {
  const a = fresh(), b = fresh(); advance(a, 1600);
  for (let i = 0; i < 320; i++) b.step(5, 480 + i * 5);
  assert.deepEqual(b.state, a.state); assert.deepEqual(b.data, a.data);
  const paused = structuredClone(b.state); b.step(0, 2080); assert.deepEqual(b.state, paused);
});

test('legacy Phase 3 saves migrate and agricultural worlds resume crops, timers, arrivals and events exactly', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-development-')), path = join(dir, 'world.sqlite');
  try {
    const store = new WorldStore(path, 73129), s = new Simulation(store.data);
    const legacy = structuredClone(s.state) as any; legacy.version = 1; delete legacy.civilization;
    for (const h of legacy.huts) { delete h.kind; delete h.crop; }
    for (const e of legacy.events) delete e.kind;
    store.close();
    const db = new DatabaseSync(path); db.prepare('INSERT INTO simulation VALUES(1,?)').run(JSON.stringify(legacy)); db.exec('UPDATE world SET version=2'); db.close();
    const migrated = new WorldStore(path, 1);
    assert.equal(migrated.snapshot().version, SAVE_VERSION); assert.equal(migrated.village!.version, 3);
    assert.deepEqual(migrated.village!.residents, legacy.residents); assert.equal(migrated.village!.huts[0].kind, 'hut');
    const active = new Simulation(migrated.data, migrated.village), edits = advance(active, 1600); migrated.saveVillage(active.state, edits); migrated.close();
    const reopened = new WorldStore(path, 1), resumed = new Simulation(reopened.data, reopened.village);
    assert.deepEqual(resumed.state, active.state); advance(resumed, 100); advance(active, 100);
    assert.deepEqual(resumed.state, active.state); assert.deepEqual(resumed.data, active.data); reopened.close();
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

test('rules support development commands and newcomer names, but absent residents and ambiguous buildings are rejected', () => {
  assert.deepEqual(parseRules('畑を２面作って。住宅を1軒建てて。倉庫を1棟建てて。農業を優先して').map(c => c.action === 'build' ? c.building : c.action), ['farm', 'house', 'warehouse', 'farm']);
  assert.deepEqual(parseRules('アオに農業を優先させて', [{ id: 'new-1', name: 'アオ' }]), [{ action: 'farm', target: 'new-1' }]);
  assert.throws(() => parseRules('住宅と畑を作って'));
  assert.equal((parseRules('build a farm')[0] as { building: string }).building, 'farm');
  assert.throws(() => parseRules('build a catapult'));
  const s = fresh(); assert.throws(() => s.acceptInstruction(randomUUID(), '不在', { source: 'rules', notice: '', commands: [{ action: 'rest', target: 'new-1' }] }), /いません/);
});

test('a crowded Phase 3 village upgrades an existing hut into housing and retains its residents', () => {
  const s = fresh();
  for (let i = 0; i < 1600 && s.state.huts.filter(h => h.status === 'complete').length < 3; i++) s.step(.25, 480 + i / 4);
  s.acceptInstruction(randomUUID(), '小屋を追加', { source: 'rules', notice: '', commands: [{ action: 'build', building: 'hut', count: 1, location: 'village' }] });
  const homes = s.state.residents.map(r => r.home);
  s.state.resources.food = 200; // Existing saves with abundant food must still complete their first harvest.
  advance(s, 1600);
  assert.equal(s.state.civilization.level, 2); assert.ok(s.state.residents.length > 5);
  const house = s.state.huts.find(h => h.kind === 'house' && h.upgrading && h.status === 'complete'); assert.ok(house);
  assert.deepEqual(s.state.residents.slice(0, 5).map(r => r.home), homes);
  assert.deepEqual(house.cost, { food: 0, wood: 24, stone: 12 });
  assert.ok(villageSchema.safeParse(s.state).success);
});

test('population stays at its limit even when food, open homes and the arrival timer permit immigration', () => {
  const s = fresh(); advance(s, 1600);
  while (s.state.residents.length < MAX_POPULATION) {
    const n = s.state.residents.length - 4;
    s.state.residents.push({ ...structuredClone(s.state.residents[0]), id: `new-${n}`, name: `移住者${n}`, task: null, path: [], inventory: { food: 0, wood: 0, stone: 0 }, home: null });
  }
  s.state.civilization.arrivals = 15; s.state.resources.food = 1000; s.state.nextPlan = 0; s.state.civilization.nextArrival = s.state.elapsed;
  assert.ok(villageSchema.safeParse(s.state).success); advance(s, 80); assert.equal(s.state.residents.length, MAX_POPULATION);
});
