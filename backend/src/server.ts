import { createServer } from 'node:http';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { WebSocketServer, WebSocket } from 'ws';
import { WorldStore } from './database/store';
import { commandSchema } from '../../shared/schema';
import { SAVE_VERSION } from '../../shared/world';
import { Simulation } from './simulation/engine';
import { InstructionInterpreter } from './llm/interpreter';
import type { InstructionResult } from '../../shared/instructions';
import { ConversationService } from './llm/conversation';
import type { ConversationResult } from '../../shared/conversation';
import { unrealScene } from './presentation/unreal';
const seed = Number(process.env.WORLD_SEED ?? 73129);
// Native UE's libwebsockets supplies its own Origin. A non-browser-only header
// authenticates the native route without weakening the browser Origin check.
const nativeSession = randomBytes(32).toString('hex');
if (!Number.isSafeInteger(seed) || seed < 0 || seed > 2147483647) throw new Error('WORLD_SEEDは0〜2147483647の整数で指定してください。');
const store = new WorldStore(process.env.DB_PATH ?? '/data/world.sqlite', seed);
const simulation = new Simulation(store.data, store.village);
store.saveVillage(simulation.state);
// Phase 6 runs entirely locally, including player instructions and conversations.
const interpreter = new InstructionInterpreter();
const conversations = new ConversationService();
const talking = new Map<string, { residentId: string; text: string; result: Promise<ConversationResult> }>();
let closing = false;
let instructionTimes: number[] = [];
const inFlight = new Map<string, { text: string; result: Promise<InstructionResult> }>();
async function handleConversation(id: string, residentId: string, text: string): Promise<ConversationResult> {
  const fail = (message: string): ConversationResult => ({ type: 'conversation-result', id, residentId, ok: false, message });
  const resident = simulation.state.residents.find(r => r.id === residentId);
  if (!resident) return fail('この住民は見つかりません。');
  const previous = simulation.state.residents.flatMap(r => r.conversations.map(c => ({ residentId: r.id, conversation: c }))).find(c => c.conversation.id === id);
  if (previous) return previous.residentId === residentId && previous.conversation.question === text ? { type: 'conversation-result', id, residentId, ok: true, message: '保存済みの会話です。', conversation: previous.conversation } : fail('この会話IDは使用済みです。');
  const pending = talking.get(id);
  if (pending) return pending.text === text && pending.residentId === residentId ? pending.result : fail('この会話IDは使用中です。');
  const now = Date.now(); instructionTimes = instructionTimes.filter(t => now - t < 60_000);
  if (instructionTimes.length >= 12 || talking.size >= 2) return fail('少し待ってから、もう一度話しかけてください。');
  instructionTimes.push(now);
  const result = (async (): Promise<ConversationResult> => {
    try {
      const reply = await conversations.reply(text, structuredClone(resident), structuredClone(simulation.state));
      if (closing) return fail('サーバーを再起動しています。');
      const backup = structuredClone(simulation.state);
      let conversation;
      try {
        conversation = simulation.acceptConversation(residentId, { id, time: simulation.state.elapsed, question: text, answer: reply.answer, source: reply.source });
        store.saveVillage(simulation.state);
      } catch (error) { Object.assign(simulation.state, backup); throw error; }
      broadcast({ type: 'village', village: simulation.state, time: store.time, speed: store.speed });
      return { type: 'conversation-result', id, residentId, ok: true, message: reply.source === 'llm' ? 'AIとの会話を保存しました。' : '住民の行動と記憶から応答しました。', conversation };
    } catch { return fail('会話を保存できませんでした。もう一度お試しください。'); }
    finally { talking.delete(id); }
  })();
  talking.set(id, { residentId, text, result }); return result;
}
async function handleInstruction(id: string, text: string): Promise<InstructionResult> {
  const previous = simulation.state.instructions.find(r => r.id === id);
  if (previous) return previous.text === text ? { type: 'instruction-result', id, ok: true, message: '受け付け済みの指示です。', record: previous } : { type: 'instruction-result', id, ok: false, message: 'この指示IDは使用済みです。' };
  const pending = inFlight.get(id);
  if (pending) return pending.text === text ? pending.result : { type: 'instruction-result', id, ok: false, message: 'この指示IDは使用中です。' };
  const now = Date.now(); instructionTimes = instructionTimes.filter(t => now - t < 60_000);
  if (instructionTimes.length >= 12) return { type: 'instruction-result', id, ok: false, message: '指示が多いため、少し待ってから送信してください。' };
  instructionTimes.push(now);
  const result = (async (): Promise<InstructionResult> => {
    try {
      const interpretation = await interpreter.interpret(text, simulation.state);
      if (closing) throw new Error('サーバーを再起動しています。');
      // Recheck current terrain and village after the asynchronous API response.
      const backup = structuredClone(simulation.state);
      let record;
      try { record = simulation.acceptInstruction(id, text, interpretation); store.saveVillage(simulation.state); }
      catch (error) { Object.assign(simulation.state, backup); throw error; }
      broadcast({ type: 'village', village: simulation.state, time: store.time, speed: store.speed });
      return { type: 'instruction-result', id, ok: true, message: store.speed === 0 ? '指示を保存しました。時間を進めると住民が実行します。' : '指示を保存しました。住民が順に実行します。', record };
    } catch (error) {
      return { type: 'instruction-result', id, ok: false, message: error instanceof Error && error.name !== 'ZodError' ? error.message : '指示のJSONが不正です。' };
    } finally { inFlight.delete(id); }
  })();
  inFlight.set(id, { text, result });
  return result;
}
const server = createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET' && req.url === '/api/health') res.end(JSON.stringify({ ok: true, version: SAVE_VERSION, revision: store.revision, residents: simulation.state.residents.length }));
  else if (req.method === 'GET' && req.url === '/api/unreal/world') {
    res.end(JSON.stringify({ ...unrealScene(store.base, store.data, simulation.state), snapshot: store.snapshot(), nativeSession }));
  }
  else { res.statusCode = 404; res.end(JSON.stringify({ error: 'Not found' })); }
});
const wss = new WebSocketServer({ noServer: true, maxPayload: 2048 });
server.on('upgrade', (req, socket, head) => {
  let trusted = false;
  try { trusted = !!req.headers.origin && new URL(req.headers.origin).host === req.headers.host; } catch { /* Invalid origin. */ }
  const candidate = req.headers['x-ai-world-session'];
  const native = req.url === '/native-socket' && typeof candidate === 'string' && /^[a-f0-9]{64}$/.test(candidate) && timingSafeEqual(Buffer.from(candidate), Buffer.from(nativeSession));
  if (!(req.url === '/socket' && trusted || native) || wss.clients.size >= 32) { socket.write('HTTP/1.1 403 Forbidden\r\n\r\n'); socket.destroy(); return; }
  wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws));
});
function broadcast(message: unknown) {
  const encoded = JSON.stringify(message);
  for (const ws of wss.clients) if (ws.readyState === WebSocket.OPEN) {
    if (ws.bufferedAmount > 1_000_000) ws.terminate(); else ws.send(encoded);
  }
}
wss.on('connection', ws => {
  ws.send(JSON.stringify(store.snapshot()));
  ws.send(JSON.stringify({ type: 'instruction-config', mode: interpreter.mode }));
  let windowStart = Date.now(), count = 0;
  ws.on('error', console.error);
  ws.on('message', raw => {
    if (Date.now() - windowStart > 1000) { count = 0; windowStart = Date.now(); }
    if (++count > 20) { ws.send(JSON.stringify({ type: 'error', message: '操作が速すぎます。少し待ってください。' })); return; }
    try {
      const command = commandSchema.parse(JSON.parse(raw.toString()));
      if (command.type === 'instruction') {
        void handleInstruction(command.id, command.text).then(result => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(result)); });
      } else if (command.type === 'conversation') {
        void handleConversation(command.id, command.residentId, command.text).then(result => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(result)); });
      } else if (command.type === 'edit') {
        const edit = store.edit(command);
        simulation.terrainChanged(edit);
        broadcast({ type: 'edit', edit, revision: store.revision });
      } else { store.speed = command.speed; store.saveVillage(simulation.state); broadcast({ type: 'clock', time: store.time, speed: store.speed }); }
    } catch (error) {
      ws.send(JSON.stringify({ type: 'error', message: error instanceof Error && error.name !== 'ZodError' ? error.message : '操作データが不正です。' }));
    }
  });
});
// Fixed-step world clock: one real second advances one game minute at 1×.
const tick = setInterval(() => {
  if (store.speed === 0) return;
  try {
    const edits = simulation.step(store.speed / 4, store.time);
    store.time += store.speed / 4;
    if (edits.length || simulation.economicChange) store.saveVillage(simulation.state, edits);
    if (edits.length) broadcast({ type: 'terrain', edits, revision: store.revision });
    broadcast({ type: 'village', village: simulation.state, time: store.time, speed: store.speed });
  } catch (error) {
    console.error('Simulation halted to protect save data', error);
    store.speed = 0; broadcast({ type: 'clock', time: store.time, speed: 0 });
    broadcast({ type: 'error', message: 'シミュレーションを停止しました。サーバーログを確認してください。' });
    clearInterval(tick); clearInterval(save);
    // Discard the failed in-memory step; Docker restores the last atomic SQLite snapshot.
    setTimeout(() => process.exit(1), 100);
  }
}, 250);
const sync = setInterval(() => broadcast({ type: 'clock', time: store.time, speed: store.speed }), 1000);
const save = setInterval(() => store.saveVillage(simulation.state), 5000);
server.listen(Number(process.env.PORT ?? 3001), '0.0.0.0', () => {
  const address = server.address();
  console.log(`AI WORLD backend :${address && typeof address === 'object' ? address.port : 3001}`);
});
function shutdown() {
  closing = true;
  clearInterval(tick); clearInterval(sync); clearInterval(save);
  for (const ws of wss.clients) ws.close(1001, 'Server restarting');
  wss.close(); server.close(); store.close();
  setTimeout(() => process.exit(0), 500).unref();
}
process.once('SIGTERM', shutdown); process.once('SIGINT', shutdown);
