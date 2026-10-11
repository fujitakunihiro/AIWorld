import { createServer } from 'node:http';
import { WebSocketServer, WebSocket } from 'ws';
import { WorldStore } from './database/store';
import { commandSchema } from '../../shared/schema';
import { SAVE_VERSION } from '../../shared/world';
import { Simulation } from './simulation/engine';
const seed = Number(process.env.WORLD_SEED ?? 73129);
if (!Number.isSafeInteger(seed) || seed < 0 || seed > 2147483647) throw new Error('WORLD_SEEDは0〜2147483647の整数で指定してください。');
const store = new WorldStore(process.env.DB_PATH ?? '/data/world.sqlite', seed);
const simulation = new Simulation(store.data, store.village);
store.saveVillage(simulation.state);
const server = createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET' && req.url === '/api/health') res.end(JSON.stringify({ ok: true, version: SAVE_VERSION, revision: store.revision, residents: simulation.state.residents.length }));
  else { res.statusCode = 404; res.end(JSON.stringify({ error: 'Not found' })); }
});
const wss = new WebSocketServer({ noServer: true, maxPayload: 2048 });
server.on('upgrade', (req, socket, head) => {
  let trusted = false;
  try { trusted = !!req.headers.origin && new URL(req.headers.origin).host === req.headers.host; } catch { /* Invalid origin. */ }
  if (req.url !== '/socket' || !trusted || wss.clients.size >= 32) { socket.write('HTTP/1.1 403 Forbidden\r\n\r\n'); socket.destroy(); return; }
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
  let windowStart = Date.now(), count = 0;
  ws.on('error', console.error);
  ws.on('message', raw => {
    if (Date.now() - windowStart > 1000) { count = 0; windowStart = Date.now(); }
    if (++count > 20) { ws.send(JSON.stringify({ type: 'error', message: '操作が速すぎます。少し待ってください。' })); return; }
    try {
      const command = commandSchema.parse(JSON.parse(raw.toString()));
      if (command.type === 'edit') {
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
  clearInterval(tick); clearInterval(sync); clearInterval(save);
  for (const ws of wss.clients) ws.close(1001, 'Server restarting');
  wss.close(); server.close(); store.close();
  setTimeout(() => process.exit(0), 500).unref();
}
process.once('SIGTERM', shutdown); process.once('SIGINT', shutdown);
