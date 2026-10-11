import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { WebSocket } from 'ws';
import { randomUUID } from 'node:crypto';
import { WorldStore } from '../../backend/src/database/store';
import { Simulation } from '../../backend/src/simulation/engine';
import { type ServerMessage, type WorldSnapshot } from '../../shared/world';
async function start(path: string) {
  const child = spawn(process.execPath, ['--import', 'tsx', 'backend/src/server.ts'], { env: { ...process.env, OPENAI_API_KEY: '', DB_PATH: path, PORT: '0' }, stdio: ['ignore', 'pipe', 'pipe'] });
  const port = await new Promise<number>((resolve, reject) => {
    let output = ''; const timer = setTimeout(() => { child.kill(); reject(new Error(`Server startup timeout: ${output}`)); }, 10000);
    child.stdout!.on('data', chunk => { output += String(chunk); const match = output.match(/backend :(\d+)/); if (match) { clearTimeout(timer); resolve(Number(match[1])); } });
    child.stderr!.on('data', chunk => output += String(chunk));
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`Server exited ${code}: ${output}`)); });
  });
  return { child, port };
}
async function stop(child: ChildProcess) { const done = once(child, 'exit'); child.kill('SIGTERM'); await done; }
class Client {
  ws: WebSocket;
  messages: ServerMessage[] = [];
  constructor(port: number) {
    this.ws = new WebSocket(`ws://localhost:${port}/socket`, { origin: `http://localhost:${port}` });
    this.ws.on('message', data => this.messages.push(JSON.parse(data.toString())));
  }
  send(data: unknown) { this.ws.send(JSON.stringify(data)); }
  async wait(type: ServerMessage['type']) {
    const start = Date.now();
    while (Date.now() - start < 5000) {
      const i = this.messages.findIndex(m => m.type === type); if (i >= 0) return this.messages.splice(i, 1)[0];
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    throw new Error(`No ${type} message received`);
  }
}
test('HTTP + WebSocket: snapshots, two-client edits, rejection, clock and real process restart', { timeout: 30000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-integration-')), path = join(dir, 'world.sqlite');
  let running: Awaited<ReturnType<typeof start>> | undefined;
  const clients: Client[] = [];
  try {
    running = await start(path);
    assert.equal((await fetch(`http://localhost:${running.port}/api/health`)).status, 200);
    const a = new Client(running.port), b = new Client(running.port); clients.push(a, b);
    const initial = await a.wait('snapshot') as WorldSnapshot;
    assert.equal(initial.seed, 73129); assert.equal(initial.village!.residents.length, 5); await b.wait('snapshot');
    a.send({ type: 'edit', x: 32, y: 11, z: 40, block: 5, expected: 0 });
    for (const client of [a, b]) { const message = await client.wait('edit'); assert.equal(message.type, 'edit'); if (message.type === 'edit') assert.equal(message.revision, 1); }
    b.send({ type: 'edit', x: 32, y: 11, z: 40, block: 3, expected: 0 }); assert.equal((await b.wait('error')).type, 'error');
    a.send({ type: 'edit', x: 64, y: 40, z: 0, block: 1, expected: 0 }); await a.wait('error');
    a.send({ type: 'speed', speed: 0 });
    let clock = await a.wait('clock'); while (clock.type !== 'clock' || clock.speed !== 0) clock = await a.wait('clock');
    const bad = new WebSocket(`ws://localhost:${running.port}/socket`, { origin: 'http://malicious.example' });
    await new Promise<void>((resolve, reject) => { bad.on('unexpected-response', (_, response) => { assert.equal(response.statusCode, 403); response.resume(); bad.terminate(); resolve(); }); bad.on('open', () => reject(new Error('Invalid origin accepted'))); bad.on('error', () => {}); });
    for (const client of clients) client.ws.close();
    await stop(running.child); running = await start(path);
    const restored = new Client(running.port); clients.push(restored);
    const snapshot = await restored.wait('snapshot') as WorldSnapshot;
    assert.equal(snapshot.revision, 1); assert.equal(snapshot.speed, 0);
    assert.deepEqual(snapshot.edits, [{ x: 32, y: 11, z: 40, block: 5 }]);
  } finally {
    for (const client of clients) client.ws.close();
    if (running && running.child.exitCode === null) await stop(running.child);
    rmSync(dir, { recursive: true, force: true });
  }
});
test('live residents gather and build; paused village and in-progress hut survive a process restart', { timeout: 25000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-village-ws-')), path = join(dir, 'world.sqlite');
  let running: Awaited<ReturnType<typeof start>> | undefined;
  const clients: Client[] = [];
  try {
    running = await start(path); const a = new Client(running.port); clients.push(a);
    const initial = await a.wait('snapshot') as WorldSnapshot; assert.equal(initial.village!.residents.length, 5);
    a.send({ type: 'speed', speed: 20 });
    let building: Extract<ServerMessage, {type: 'village'}> | undefined;
    for (let i = 0; i < 60; i++) {
      const message = await a.wait('village');
      if (message.type === 'village' && message.village.huts.some(h => h.status === 'building' && h.progress >= 8)) { building = message; break; }
    }
    assert.ok(building, 'A hut did not start construction at 20×');
    assert.ok(building.village.events.some(e => e.text.includes('届けました')));
    a.send({ type: 'speed', speed: 0 });
    let message = await a.wait('clock'); while (message.type !== 'clock' || message.speed !== 0) message = await a.wait('clock');
    const beforeClient = new Client(running.port); clients.push(beforeClient);
    const before = await beforeClient.wait('snapshot') as WorldSnapshot;
    await new Promise(resolve => setTimeout(resolve, 350));
    const frozenClient = new Client(running.port); clients.push(frozenClient);
    const frozen = await frozenClient.wait('snapshot') as WorldSnapshot;
    assert.deepEqual(frozen.village, before.village); assert.equal(frozen.time, before.time);
    for (const client of clients) client.ws.close(); await stop(running.child); running = await start(path);
    const restored = new Client(running.port); clients.push(restored);
    const after = await restored.wait('snapshot') as WorldSnapshot;
    assert.equal(after.speed, 0); assert.equal(after.time, before.time); assert.deepEqual(after.edits, before.edits);
    assert.deepEqual(after.village!.huts, before.village!.huts); assert.deepEqual(after.village!.resources, before.village!.resources);
    assert.deepEqual(after.village!.residents.map(r => ({ id: r.id, inventory: r.inventory, memories: r.memories })), before.village!.residents.map(r => ({ id: r.id, inventory: r.inventory, memories: r.memories })));
    restored.send({ type: 'speed', speed: 20 });
    const continuing = await restored.wait('village'); assert.equal(continuing.type, 'village');
    if (continuing.type === 'village') assert.ok(continuing.village.elapsed > before.village!.elapsed);
  } finally {
    for (const client of clients) client.ws.close(); if (running && running.child.exitCode === null) await stop(running.child);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('natural-language instructions synchronize, reject safely, deduplicate and survive a process restart', { timeout: 25000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-instructions-')), path = join(dir, 'world.sqlite');
  let running: Awaited<ReturnType<typeof start>> | undefined; const clients: Client[] = [];
  try {
    running = await start(path); const a = new Client(running.port), b = new Client(running.port); clients.push(a, b);
    await a.wait('snapshot'); await b.wait('snapshot');
    assert.deepEqual(await a.wait('instruction-config'), { type: 'instruction-config', mode: 'rules' });
    a.send({ type: 'speed', speed: 0 });
    let clock = await a.wait('clock'); while (clock.type !== 'clock' || clock.speed !== 0) clock = await a.wait('clock');
    const id = randomUUID(), request = { type: 'instruction', id, text: '小屋を1軒建てて。ミオに木材を集めてほしい' };
    a.send(request); a.send(request);
    for (let i = 0; i < 2; i++) { const result = await a.wait('instruction-result'); assert.equal(result.type, 'instruction-result'); if (result.type === 'instruction-result') { assert.ok(result.ok); assert.equal(result.record?.source, 'rules'); assert.equal(result.record?.jobs.length, 2); } }
    let synced = await b.wait('village'); while (synced.type !== 'village' || !synced.village.instructions.length) synced = await b.wait('village');
    assert.equal(synced.village.instructions.length, 1); assert.equal(synced.village.huts.length, 2); assert.equal(synced.village.residents[1].order?.kind, 'wood');
    a.send({ type: 'instruction', id: randomUUID(), text: '小屋を99軒建てて' });
    const rejected = await a.wait('instruction-result'); assert.equal(rejected.type, 'instruction-result'); if (rejected.type === 'instruction-result') assert.equal(rejected.ok, false);
    for (const client of clients) client.ws.close(); await stop(running.child); running = await start(path);
    const c = new Client(running.port); clients.push(c); const snapshot = await c.wait('snapshot') as WorldSnapshot;
    assert.equal(snapshot.village!.instructions.length, 1); assert.equal(snapshot.village!.huts.length, 2); assert.equal(snapshot.speed, 0); assert.equal(snapshot.village!.residents[1].order?.kind, 'wood');
    c.send(request); const duplicate = await c.wait('instruction-result'); if (duplicate.type === 'instruction-result') assert.ok(duplicate.ok);
    c.send({ type: 'speed', speed: 20 }); const resumed = await c.wait('village'); if (resumed.type === 'village') assert.ok(resumed.village.elapsed > snapshot.village!.elapsed);
  } finally { for (const client of clients) client.ws.close(); if (running && running.child.exitCode === null) await stop(running.child); rmSync(dir, { recursive: true, force: true }); }
});

test('developed village, crops, immigration timers and newcomer instructions synchronize and survive real server restart', { timeout: 25000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ai-world-civilization-ws-')), path = join(dir, 'world.sqlite');
  let running: Awaited<ReturnType<typeof start>> | undefined; const clients: Client[] = [];
  try {
    const store = new WorldStore(path, 73129), simulation = new Simulation(store.data); const edits = [];
    for (let i = 0; i < 6400; i++) edits.push(...simulation.step(.25, 480 + i / 4));
    store.time = 2080; store.speed = 0; store.saveVillage(simulation.state, edits); store.close();
    running = await start(path); const a = new Client(running.port); clients.push(a);
    const initial = await a.wait('snapshot') as WorldSnapshot;
    assert.equal(initial.village!.civilization.level, 2); assert.ok(initial.village!.residents.length > 5);
    const newcomer = initial.village!.residents.find(r => r.id === 'new-1')!;
    a.send({ type: 'instruction', id: randomUUID(), text: `${newcomer.name}に農業を優先させて` });
    const accepted = await a.wait('instruction-result'); if (accepted.type === 'instruction-result') assert.ok(accepted.ok);
    a.send({ type: 'edit', x: simulation.state.huts.find(h => h.kind === 'farm')!.x, y: simulation.state.huts.find(h => h.kind === 'farm')!.y, z: simulation.state.huts.find(h => h.kind === 'farm')!.z, block: 0, expected: 5 });
    await a.wait('error');
    const b = new Client(running.port); clients.push(b); const before = await b.wait('snapshot') as WorldSnapshot;
    assert.equal(before.village!.residents.find(r => r.id === newcomer.id)!.order?.kind, 'farm');
    for (const client of clients) client.ws.close(); await stop(running.child); running = await start(path);
    const c = new Client(running.port); clients.push(c); const after = await c.wait('snapshot') as WorldSnapshot;
    assert.deepEqual(after.village, before.village); assert.deepEqual(after.edits, before.edits);
    c.send({ type: 'speed', speed: 20 }); const resumed = await c.wait('village');
    if (resumed.type === 'village') assert.ok(resumed.village.elapsed > after.village!.elapsed);
  } finally { for (const client of clients) client.ws.close(); if (running && running.child.exitCode === null) await stop(running.child); rmSync(dir, { recursive: true, force: true }); }
});
