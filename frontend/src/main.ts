import './style.css';
import { WorldRenderer } from './renderer/world-renderer';
import { Block, SAVE_VERSION, generateWorld, getBlock, index, type BlockId, type Edit, type ServerMessage } from '../../shared/world';
import { VillageUI } from './ui/village-ui';
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
type Mode = 'observe' | 'place' | 'remove';
let mode: Mode = 'observe', material: BlockId = Block.Grass;
let world: Uint8Array | undefined, socket: WebSocket | undefined, ready = false;
let reconnectDelay = 1000, toastTimer: ReturnType<typeof setTimeout>;
let history: { before: Edit; after: Edit }[] = [];
let pending: { before: Edit; after: Edit; undo: boolean; timer: ReturnType<typeof setTimeout> } | undefined;
let renderer: WorldRenderer;
const villageUI = new VillageUI();
const materials: { id: BlockId; name: string; color: string }[] = [
  { id: Block.Grass, name: '草', color: '#85ae62' }, { id: Block.Dirt, name: '土', color: '#a47a50' },
  { id: Block.Stone, name: '石', color: '#909a9e' }, { id: Block.Sand, name: '砂', color: '#e9d39c' },
  { id: Block.Wood, name: '木材', color: '#aa8057' }, { id: Block.Leaves, name: '葉', color: '#548b54' },
  { id: Block.Brick, name: 'レンガ', color: '#c6886b' }
];
function toast(message: string) {
  $('toast').textContent = message; $('toast').classList.add('visible'); clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 3600);
}
function updateHint() {
  const touch = matchMedia('(pointer: coarse)').matches;
  $('hint').textContent = mode === 'observe' ? (touch ? '住民をタップで詳細 · 1本指で移動 · 2本指でズーム' : '住民をクリックで詳細 · ドラッグで回転 · 右ドラッグで移動') :
    mode === 'place' ? `${materials.find(m => m.id === material)!.name}を置く場所をタップ · ドラッグでカメラ操作` : '消したいブロックをタップ · 高さ0の基盤は保護されています';
}
function setMode(next: Mode) {
  mode = next; document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(button => button.classList.toggle('active', button.dataset.mode === mode));
  $('palette').classList.toggle('editing', mode === 'place');
  renderer?.highlight(null); updateHint();
}
function setConnection(connected: boolean) {
  $('connection').textContent = connected ? '世界に接続中' : '再接続中';
  $('status-dot').classList.toggle('online', connected);
  document.querySelectorAll<HTMLButtonElement>('[data-speed]').forEach(button => button.disabled = !connected);
  $('undo').toggleAttribute('disabled', !connected || !!pending || history.length === 0);
}
function clearPending() { if (pending) clearTimeout(pending.timer); pending = undefined; $('undo').toggleAttribute('disabled', !ready || history.length === 0); }
function sendEdit(edit: Edit, undo = false) {
  if (!ready || !socket || !world) { toast('サーバーへの再接続を待ってください。'); return; }
  if (pending) return;
  const before: Edit = { ...edit, block: getBlock(world, edit.x, edit.y, edit.z) };
  pending = { before, after: edit, undo, timer: setTimeout(() => {
    clearPending(); ready = false; setConnection(false); socket?.close(); toast('保存の応答を確認できません。世界を再読み込みしています。');
  }, 5000) };
  $('save-state').textContent = '保存中…'; $('undo').setAttribute('disabled', '');
  socket.send(JSON.stringify({ type: 'edit', ...edit, expected: before.block }));
}
function clock(time: number, speed: number) {
  renderer.time = time;
  renderer.paused = speed === 0;
  const minute = Math.floor(time % 1440), hour = Math.floor(minute / 60);
  $('day').textContent = `${Math.floor(time / 1440) + 1}日目`;
  $('clock').textContent = `${hour >= 6 && hour < 18 ? '☀' : '☾'} ${String(hour).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
  document.querySelectorAll<HTMLButtonElement>('[data-speed]').forEach(button => button.classList.toggle('active', Number(button.dataset.speed) === speed));
}
function connect() {
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/socket`); socket = ws;
  ws.onmessage = event => {
    try {
      const message = JSON.parse(event.data) as ServerMessage;
      if (message.type === 'snapshot') {
        if (message.version !== SAVE_VERSION) throw new Error('保存バージョンが一致しません。ページを再読み込みしてください。');
        world = generateWorld(message.seed);
        for (const edit of message.edits) world[index(edit.x, edit.y, edit.z)] = edit.block;
        renderer.setWorld(world); ready = true; history = []; clearPending(); setConnection(true); reconnectDelay = 1000;
        clock(message.time, message.speed); $('loading').classList.add('hidden');
        if (message.village) { villageUI.update(message.village); renderer.village.update(message.village, true); }
        $('save-state').textContent = `✓ 保存済み · #${message.revision}`;
      } else if (message.type === 'edit' && world) {
        const { edit } = message;
        world[index(edit.x, edit.y, edit.z)] = edit.block; renderer.changed(edit);
        if (pending && ['x', 'y', 'z', 'block'].every(key => edit[key as keyof Edit] === pending!.after[key as keyof Edit])) {
          if (pending.undo) history.pop(); else { history.push({ before: pending.before, after: pending.after }); if (history.length > 50) history.shift(); }
          clearPending();
        }
        $('save-state').textContent = `✓ 保存済み · #${message.revision}`;
      } else if (message.type === 'terrain' && world) {
        for (const edit of message.edits) world[index(edit.x, edit.y, edit.z)] = edit.block;
        renderer.changedBatch(message.edits); $('save-state').textContent = `✓ 保存済み · #${message.revision}`;
      } else if (message.type === 'village') {
        villageUI.update(message.village); renderer.village.update(message.village); clock(message.time, message.speed);
      } else if (message.type === 'clock') clock(message.time, message.speed);
      else if (message.type === 'error') { clearPending(); $('save-state').textContent = '操作は適用されませんでした'; toast(message.message); }
    } catch (error) { toast(error instanceof Error ? error.message : 'データを読み込めませんでした。'); }
  };
  ws.onclose = () => {
    ready = false; clearPending(); setConnection(false); $('save-state').textContent = 'オフライン · 編集待機';
    $('loading-message').textContent = 'サーバーに接続できません。起動状態を確認しています…';
    setTimeout(connect, reconnectDelay); reconnectDelay = Math.min(10000, reconnectDelay * 1.5);
  };
  ws.onerror = () => ws.close();
}
for (const m of materials) {
  const button = document.createElement('button'); button.className = 'swatch'; button.title = m.name;
  button.setAttribute('aria-label', `${m.name}ブロック`); button.dataset.block = String(m.id);
  const cube = document.createElement('span'); cube.style.setProperty('--swatch', m.color); button.append(cube);
  const name = document.createElement('small'); name.textContent = m.name; button.append(name);
  button.classList.toggle('selected', m.id === material);
  button.onclick = () => { material = m.id; setMode('place'); document.querySelectorAll<HTMLButtonElement>('.swatch').forEach(b => b.classList.toggle('selected', Number(b.dataset.block) === material)); };
  $('palette').append(button);
}
document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(button => button.onclick = () => setMode(button.dataset.mode as Mode));
document.querySelectorAll<HTMLButtonElement>('[data-speed]').forEach(button => button.onclick = () => { if (ready) socket?.send(JSON.stringify({ type: 'speed', speed: Number(button.dataset.speed) })); });
const guide = $('guide') as HTMLDialogElement;
$('help').onclick = () => guide.showModal(); $('close-guide').onclick = () => guide.close();
guide.addEventListener('click', e => { if (e.target === guide) { const r = guide.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) guide.close(); } });
$('undo').onclick = () => {
  const item = history.at(-1); if (!item || !world) return;
  if (getBlock(world, item.after.x, item.after.y, item.after.z) !== item.after.block) { history.pop(); clearPending(); toast('この場所は別の操作で変更されているため、元に戻せません。'); return; }
  sendEdit(item.before, true);
};
try {
  renderer = new WorldRenderer($('world'));
  villageUI.onFocus = (state, id) => { setMode('observe'); renderer.focusVillage(state, id); };
  villageUI.onSelect = id => renderer.village.select(id);
  renderer.onFps = fps => $('fps').textContent = `${fps} FPS`;
  renderer.controls.onTap = (x, y) => {
    if (mode === 'observe') { const id = renderer.pickResident(x, y); if (id) villageUI.open(id); return; }
    const picked = renderer.pick(x, y, mode === 'place');
    if (!picked) { toast('編集できる地形を選んでください。'); return; }
    sendEdit({ ...picked, block: mode === 'place' ? material : Block.Air });
  };
  renderer.controls.onHover = (x, y) => renderer.highlight(mode === 'observe' ? null : renderer.pick(x, y, mode === 'place'), mode === 'remove');
  renderer.controls.onLongPress = () => { setMode('place'); toast('配置ツールを開きました。素材を選んでタップしてください。'); };
  $('zoom-in').onclick = () => renderer.controls.zoom(0.82); $('zoom-out').onclick = () => renderer.controls.zoom(1.22);
  $('rotate').onclick = () => { renderer.controls.orbit.theta += Math.PI / 4; renderer.controls.update(); };
  $('home').onclick = () => renderer.controls.home();
  updateHint(); setConnection(false); connect();
} catch (error) {
  $('loading-message').textContent = '3D描画を開始できません。WebGLが利用できるブラウザで開いてください。';
  console.error(error);
}
