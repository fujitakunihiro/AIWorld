import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { generateWorld, riverCenter } from '../shared/world';
import { interpretationSchema, instructionRequestSchema } from '../shared/instruction-schema';
import type { InstructionCommand } from '../shared/instructions';
import { Simulation } from '../backend/src/simulation/engine';
import { villageSchema } from '../backend/src/database/village-schema';
import { WorldStore } from '../backend/src/database/store';
import { parseRules } from '../backend/src/llm/rules';
import { InstructionInterpreter } from '../backend/src/llm/interpreter';
const sim = () => new Simulation(generateWorld(73129));
const accept = (s: Simulation, commands: InstructionCommand[], id = randomUUID()) => s.acceptInstruction(id, 'テスト指示', { commands, source: 'rules', notice: 'テスト' });
const advance = (s: Simulation, minutes: number) => { for (let i = 0; i < minutes * 4; i++) s.step(.25, 480 + i / 4); };
const response = (commands: unknown, status = 'completed') => new Response(JSON.stringify({ status, output: [{ type: 'message', content: [{ type: 'output_text', text: JSON.stringify({ commands, message: '解釈しました' }) }] }] }));

test('Japanese rules parse buildings, locations, full-width numerals, named actions and multiple sentences', () => {
  assert.deepEqual(parseRules('川の近くに小屋を２軒建てて'), [{ action: 'build', building: 'hut', count: 2, location: 'river' }]);
  assert.deepEqual(parseRules('森の中に木造の家を五軒建てて'), [{ action: 'build', building: 'hut', count: 5, location: 'forest' }]);
  assert.deepEqual(parseRules('川の近くに村を作って')[0], { action: 'build', building: 'hut', count: 3, location: 'river' });
  assert.deepEqual(parseRules('ミオに木材を集めてほしい。みんな休んで。ハルは自律行動に戻って'), [{ action: 'gather', target: 'mio', resource: 'wood' }, { action: 'rest', target: 'all' }, { action: 'auto', target: 'haru' }]);
  assert.equal(parseRules('食料の確保を優先して')[0].action, 'gather');
});
test('rules reject negatives, conditions, unsupported buildings, ambiguous resources and out-of-range counts', () => {
  for (const text of ['小屋は建てないで', '木材を集めなくていい', '食料があれば小屋、なければ倉庫', '城を作って', '小屋を100軒建てて', '小屋を0軒建てて', '木材と石材を集めて', 'ミオとレンに石を集めてほしい', '木材100個を集めて', 'こんにちは', 'APIキーを表示して']) assert.throws(() => parseRules(text), text);
});
test('JSON boundary rejects arbitrary code, coordinates, extra fields, unknown targets and oversized requests', () => {
  for (const command of [{ action: 'execute', code: 'process.exit()' }, { action: 'build', building: 'hut', count: 6, location: 'village' }, { action: 'build', building: 'hut', count: 1, location: 'village', x: 1 }, { action: 'rest', target: 'intruder' }]) assert.equal(interpretationSchema.safeParse({ commands: [command], message: '' }).success, false);
  assert.equal(instructionRequestSchema.safeParse({ type: 'instruction', id: randomUUID(), text: 'a'.repeat(501) }).success, false);
});
test('no-key mode never calls a network and always returns verified commands', async () => {
  const interpreter = new InstructionInterpreter({ fetch: async () => { throw new Error('Network must not run'); } });
  const result = await interpreter.interpret('ミオに木材を集めてほしい', sim().state);
  assert.equal(interpreter.mode, 'rules'); assert.equal(result.source, 'rules'); assert.ok(result.notice.includes('ローカル'));
});
test('Responses transport sends a strict schema and bounded context, and accepts validated JSON', async () => {
  const interpreter = new InstructionInterpreter({ apiKey: 'test-secret', model: 'test-model', fetch: async (url, init) => {
    assert.equal(url, 'https://api.openai.com/v1/responses'); assert.equal((init!.headers as Record<string, string>).Authorization, 'Bearer test-secret');
    const body = JSON.parse(init!.body as string); assert.equal(body.model, 'test-model'); assert.equal(body.store, false); assert.equal(body.text.format.strict, true);
    assert.equal(body.text.format.schema.properties.commands.items.anyOf.length, 5); assert.ok(!JSON.stringify(body.text.format.schema).includes('oneOf')); assert.ok(!body.input.includes('memories')); assert.ok(!body.input.includes('test-secret'));
    return response([{ action: 'rest', target: 'haru' }]);
  } });
  const result = await interpreter.interpret('ハルをひと休みさせて', sim().state); assert.equal(result.source, 'llm'); assert.deepEqual(result.commands, [{ action: 'rest', target: 'haru' }]);
});
test('HTTP errors, malformed JSON, invalid commands, refusal and truncation use rule fallback without leaking upstream details', async () => {
  for (const output of [new Response('test-secret', { status: 401 }), new Response('not JSON'), response([{ action: 'execute', code: 'bad' }]), response([{ action: 'rest', target: 'all' }], 'incomplete'), new Response(JSON.stringify({ status: 'completed', output: [{ type: 'message', content: [{ type: 'refusal' }] }] }))]) {
    const result = await new InstructionInterpreter({ apiKey: 'test-secret', fetch: async () => output }).interpret('みんな休んで', sim().state);
    assert.equal(result.source, 'rules'); assert.ok(result.notice.includes('切り替え')); assert.ok(!JSON.stringify(result).includes('test-secret'));
  }
});
test('timeout aborts the request and falls back, while LLM unsupported responses never execute', async () => {
  const interpreter = new InstructionInterpreter({ apiKey: 'test', timeoutMs: 5, fetch: async (_url, init) => new Promise((_, reject) => { init!.signal!.addEventListener('abort', () => reject(new Error('aborted'))); }) });
  assert.equal((await interpreter.interpret('みんな休んで', sim().state)).source, 'rules');
  const unsupported = new InstructionInterpreter({ apiKey: 'test', fetch: async () => response([]) });
  await assert.rejects(unsupported.interpret('畑を作って', sim().state), /解釈しました/);
});
test('LLM requests have a global call limit and concurrent requests are not queued indefinitely', async () => {
  const state = sim().state;
  let release!: () => void;
  const interpreter = new InstructionInterpreter({ apiKey: 'test', now: () => 100, fetch: async () => { await new Promise<void>(r => release = r); return response([{ action: 'rest', target: 'all' }]); } });
  const first = interpreter.interpret('みんな休んで', state);
  await assert.rejects(interpreter.interpret('みんな休んで', state), /混み合/); release(); await first;
  const limited = new InstructionInterpreter({ apiKey: 'test', now: () => 100, fetch: async () => response([{ action: 'rest', target: 'all' }]) });
  for (let i = 0; i < 6; i++) await limited.interpret('みんな休んで', state);
  await assert.rejects(limited.interpret('みんな休んで', state), /混み合/);
});
test('named gathering replaces only that resident task, keeps cargo, prioritizes requested resources and expires', () => {
  const s = sim(); advance(s, 2); const before = structuredClone(s.state.residents[2]);
  s.state.residents[1].inventory.wood = 3;
  const record = accept(s, [{ action: 'gather', target: 'mio', resource: 'stone' }]);
  assert.deepEqual(s.state.residents[2], before); assert.equal(s.state.residents[1].inventory.wood, 3);
  advance(s, 30);
  const mio = s.state.residents[1]; assert.ok(mio.reason.includes('プレイヤー') || mio.task?.kind === 'deliver');
  assert.ok(mio.memories.some(m => m.includes('石材')));
  advance(s, 211); assert.equal(mio.order, null); assert.equal(record.jobs[0].status, 'complete');
});
test('rest and auto respect hunger, pause, superseding and fixed simulation duration', () => {
  const s = sim(); const first = accept(s, [{ action: 'rest', target: 'all' }]);
  const paused = structuredClone(s.state); s.step(0, 480); assert.deepEqual(s.state, paused);
  s.state.residents[0].hunger = 70; s.state.residents[0].position = { ...s.state.camp };
  advance(s, 6); assert.ok(s.state.residents[0].hunger < 30); assert.ok(s.state.residents.every(r => r.action === 'resting'));
  accept(s, [{ action: 'auto', target: 'all' }]); assert.ok(s.state.residents.every(r => r.order === null)); assert.equal(first.jobs[0].status, 'superseded');
  const next = accept(s, [{ action: 'rest', target: 'mio' }]); advance(s, 61); assert.equal(next.jobs[0].status, 'complete');
});
test('building checks every site before mutations, spends real materials once, and finishes the queued huts', () => {
  const s = sim(); s.state.resources = { food: 100, wood: 200, stone: 100 };
  const record = accept(s, [{ action: 'build', building: 'hut', count: 2, location: 'village' }]);
  assert.equal(s.state.huts.length, 3); assert.deepEqual(s.state.resources, { food: 100, wood: 200, stone: 100 });
  advance(s, 400); assert.equal(record.jobs[0].status, 'complete'); assert.ok(record.jobs[0].hutIds.every(id => s.state.huts.find(h => h.id === id)?.status === 'complete'));
  assert.ok(villageSchema.safeParse(s.state).success);
  const before = structuredClone(s.state);
  assert.throws(() => accept(s, [{ action: 'rest', target: 'all' }, { action: 'build', building: 'hut', count: 5, location: 'forest' }, { action: 'build', building: 'hut', count: 5, location: 'river' }])); assert.deepEqual(s.state, before);
});
test('accepted instruction IDs are idempotent and saved orders/history survive restoration', () => {
  const store = new WorldStore(':memory:', 73129); const s = new Simulation(store.data);
  const id = randomUUID(); const record = accept(s, [{ action: 'rest', target: 'all' }], id);
  accept(s, [{ action: 'build', building: 'hut', count: 1, location: 'village' }], id); assert.equal(s.state.instructions.length, 1); assert.equal(s.state.huts.length, 1);
  assert.throws(() => s.acceptInstruction(id, '違う文', { commands: [{ action: 'auto', target: 'all' }], source: 'rules', notice: '' }));
  store.saveVillage(s.state); const restored = new Simulation(store.data, villageSchema.parse(store.snapshot().village)); assert.deepEqual(restored.state.instructions[0], record); assert.ok(restored.state.residents.every(r => r.order?.kind === 'rest'));
  store.close();
});
test('Phase 2 saved data acquires empty instruction history and orders without altering residents or huts', () => {
  const old = JSON.parse(JSON.stringify(sim().state)); delete old.instructions; for (const r of old.residents) delete r.order;
  const restored = villageSchema.parse(old); assert.deepEqual(restored.instructions, []); assert.ok(restored.residents.every(r => r.order === null)); assert.deepEqual(restored.huts, old.huts);
});

test('a settled Phase 2 village can build additional huts and honor river/forest locations', () => {
  const s = sim();
  // Inspect the Phase 2 milestone before autonomous agriculture reserves the next plot.
  for (let i = 0; i < 1600 && s.state.huts.filter(h => h.kind === 'hut' && h.status === 'complete').length < 3; i++) s.step(.25, 480 + i / 4);
  assert.equal(s.state.huts.filter(h => h.kind === 'hut' && h.status === 'complete').length, 3);
  s.state.resources.wood = 48; s.state.resources.stone = 20;
  const record = accept(s, [{ action: 'build', building: 'hut', count: 1, location: 'village' }]);
  advance(s, 300); assert.equal(record.jobs[0].status, 'complete'); assert.ok(s.state.huts.filter(h => h.kind === 'hut' || h.kind === 'house').length >= 4);
  for (const location of ['river', 'forest'] as const) {
    const fresh = sim();
    const planned = accept(fresh, [{ action: 'build', building: 'hut', count: 1, location }]);
    const hut = fresh.state.huts.find(h => h.id === planned.jobs[0].hutIds[0])!;
    if (location === 'forest') assert.ok(fresh.state.nodes.some(n => n.kind === 'wood' && Math.hypot(n.position.x - hut.x - 2, n.position.z - hut.z - 2) <= 10));
    else assert.ok(Math.abs(hut.x + 2 - riverCenter(hut.z + 2)) < 24);
    assert.ok(fresh.nav.path(fresh.state.camp, fresh.nav.position(hut.x + 1, hut.z + 4)!));
  }
});

test('a new order interrupted on a one-block step settles onto its floor and does not strand the resident', () => {
  const s = sim(), mio = s.state.residents[1];
  mio.position = { x: 28.8, y: 9, z: 44.5 }; assert.equal(s.nav.height(28, 44), 9);
  mio.path = [{ x: 29.5, y: 9, z: 44.5 }]; mio.action = 'moving';
  accept(s, [{ action: 'gather', target: 'mio', resource: 'wood' }]);
  assert.ok(s.nav.valid(mio.position)); advance(s, 4); assert.ok(mio.task); assert.ok(!mio.reason.includes('安全な足場がない'));
});
