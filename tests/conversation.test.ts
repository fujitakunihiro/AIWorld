import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { generateWorld } from '../shared/world';
import { commandSchema } from '../shared/schema';
import { rememberResident } from '../shared/memory';
import { Simulation } from '../backend/src/simulation/engine';
import { ConversationService } from '../backend/src/llm/conversation';
import { villageSchema } from '../backend/src/database/village-schema';
const fresh = () => new Simulation(generateWorld(73129));
test('local conversation uses current work, previous conversation and personal goals without changing orders', async () => {
  const s = fresh(), resident = s.state.residents[0], service = new ConversationService();
  const reply = await service.reply('何をしているの？', resident, s.state);
  assert.equal(reply.source, 'rules'); assert.ok(reply.answer.includes(resident.reason));
  const id = randomUUID();
  s.acceptConversation(resident.id, { id, time: 0, question: '好きな花は青い花です。覚えて', answer: '覚えておきます。', source: 'rules' });
  assert.match((await service.reply('前に何を話した？', resident, s.state)).answer, /青い花/);
  assert.match((await service.reply('好きな花を覚えている？', resident, s.state)).answer, /青い花/);
  assert.match((await service.reply('目標は？', resident, s.state)).answer, new RegExp(resident.goal));
  assert.equal(resident.order, null); assert.equal(resident.task, null);
  s.acceptConversation(resident.id, { id, time: 1, question: '重複', answer: '重複', source: 'rules' });
  assert.equal(resident.conversations.length, 1);
});
test('conversation schema refuses long text and extra executable fields, and accepts extended coordinates', () => {
  const request = { type: 'conversation', id: randomUUID(), residentId: 'haru', text: 'こんにちは' };
  assert.ok(commandSchema.safeParse(request).success);
  for (const patch of [{ text: '' }, { text: 'a'.repeat(301) }, { code: 'process.exit()' }, { residentId: '../secrets' }]) assert.equal(commandSchema.safeParse({ ...request, ...patch }).success, false);
  assert.ok(commandSchema.safeParse({ type: 'edit', x: 127, y: 31, z: 127, block: 5, expected: 0 }).success);
});
test('memories deduplicate repeated work and summarize several older experiences within storage bounds', () => {
  const r = fresh().state.residents[0];
  for (let i = 0; i < 30; i++) rememberResident(r, `思い出${i}：仲間と新しい場所を訪れた。`);
  assert.equal(r.memories.length, 8); assert.ok(r.memorySummary.includes('思い出21')); assert.ok(r.memorySummary.includes('思い出20')); assert.ok(r.memorySummary.length <= 500);
  for (let i = 0; i < 50; i++) rememberResident(r, '木材を4集めた。');
  assert.equal(r.memories.filter(m => m === '木材を4集めた。').length, 1);
});
test('LLM receives limited context with no remote storage and falls back on failures and timeout', async () => {
  const s = fresh(), r = s.state.residents[0]; let body: any;
  r.memories = Array.from({ length: 8 }, (_, i) => `${i}:${'記憶'.repeat(249)}`);
  r.memorySummary = '要約'.repeat(250);
  r.conversations = Array.from({ length: 12 }, (_, i) => ({ id: `past-${i}`, time: i, question: 'あ'.repeat(300), answer: 'い'.repeat(500), source: 'rules' as const }));
  const service = new ConversationService({ apiKey: 'test-key', fetch: (async (_, init) => {
    body = JSON.parse(String(init?.body));
    return new Response(JSON.stringify({ status: 'completed', output: [{ type: 'message', content: [{ type: 'output_text', text: '村の住宅を建てています。' }] }] }));
  }) as typeof fetch });
  assert.equal((await service.reply('何してる？', r, s.state)).source, 'llm');
  assert.equal(body.store, false); assert.equal(body.max_output_tokens, 350); assert.equal(body.previous_response_id, undefined); assert.ok(body.input.length < 3500);
  const context = JSON.parse(body.input).resident; assert.equal(context.conversations.length, 3); assert.equal(context.memories.length, 4); assert.equal(context.olderMemories.length, 240);
  for (const fake of [async () => new Response('', { status: 500 }), async () => new Response('{}'), async () => new Response(JSON.stringify({ status: 'completed', output: [{ type: 'message', content: [{ type: 'output_text', text: 'a'.repeat(501) }] }] }))]) {
    assert.equal((await new ConversationService({ apiKey: 'test', fetch: fake as typeof fetch }).reply('こんにちは', r, s.state)).source, 'rules');
  }
  const timeout = new ConversationService({ apiKey: 'test', timeoutMs: 5, fetch: (async (_, init) => new Promise((_, reject) => init!.signal!.addEventListener('abort', () => reject(new Error('timeout'))))) as typeof fetch });
  assert.equal((await timeout.reply('こんにちは', r, s.state)).source, 'rules');
});
test('nearby residents speak, remember each other and respect their conversation cooldown', () => {
  const s = fresh(); s.state.nextPlan = 1e9;
  for (const r of s.state.residents) { r.position = { ...s.state.camp }; r.nextSocialAt = 0; r.action = 'resting'; }
  s.state.residents[0].action = 'idle'; s.state.residents[1].action = 'idle';
  s.step(.25, 480); assert.ok(s.state.events.some(e => e.kind === 'conversation')); assert.ok(s.state.residents[0].speech);
  const count = s.state.events.filter(e => e.kind === 'conversation' && e.text.startsWith('ハルとミオ')).length;
  for (let i = 0; i < 40; i++) s.step(.25, 480 + s.state.elapsed);
  assert.equal(s.state.events.filter(e => e.kind === 'conversation' && e.text.startsWith('ハルとミオ')).length, count);
  assert.ok(s.state.residents[0].relationships.mio > 50);
});
test('history archives older milestones while preserving bounded chronological entries', () => {
  const s = fresh();
  for (let i = 0; i < 330; i++) s.acceptInstruction(`auto-${i}`, 'みんな自律行動に戻って', { source: 'rules', notice: '', commands: [{ action: 'auto', target: 'all' }] });
  assert.equal(s.state.chronicle.length, 300); assert.ok(s.state.archive.count > 0); assert.equal(s.state.events.length, 30);
  assert.ok(villageSchema.safeParse(s.state).success);
});
test('Phase 4 resident migration adds conversation and history without losing homes, inventory or memories', () => {
  const s = fresh(), old: any = structuredClone(s.state); old.version = 2; delete old.chronicle; delete old.archive;
  for (const r of old.residents) { delete r.conversations; delete r.speech; delete r.nextSocialAt; }
  const migrated = villageSchema.parse(old);
  assert.equal(migrated.version, 3); assert.deepEqual(migrated.chronicle, s.state.events);
  assert.deepEqual(migrated.residents.map(r => [r.position, r.inventory, r.home, r.memories]), s.state.residents.map(r => [r.position, r.inventory, r.home, r.memories]));
  assert.ok(migrated.residents.every(r => !r.conversations.length && r.speech === null));
});
