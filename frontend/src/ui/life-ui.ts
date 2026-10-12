import { ARC, Block, EIFFEL, HEIGHT, SIZE, getBlock, type Edit } from '../../../shared/world';
import { EVENT_LABELS, type VillageState } from '../../../shared/village';
import { UTILITY_LABELS } from '../../../shared/autonomy';
import type { ConversationResult } from '../../../shared/conversation';
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const add = (tag: string, parent: HTMLElement, className: string, text: string) => { const element = document.createElement(tag); element.className = className; element.textContent = text; parent.append(element); return element; };
export class LifeUI {
  onSend: (id: string, residentId: string, text: string) => void = () => {};
  onMapFocus: (x: number, z: number) => void = () => {};
  onHistoryResident: (id: string) => void = () => {};
  onSettings: (settings: { sound: boolean; effects: boolean; bubbles: boolean }) => void = () => {};
  private selected = 'haru';
  private state?: VillageState;
  private connected = false;
  private pending?: { id: string; residentId: string; text: string; timer: ReturnType<typeof setTimeout> };
  private chatKey = '';
  private historyKey = '';
  private tasksKey = '';
  private baseMap = document.createElement('canvas');
  private data?: Uint8Array;
  private target = { x: 64, z: 64, radius: 80 };
  constructor() {
    const history = $('history-dialog') as HTMLDialogElement, settings = $('settings-dialog') as HTMLDialogElement;
    $('open-history').onclick = () => { this.history(true); history.showModal(); };
    $('close-history').onclick = () => history.close(); $('history-filter').onchange = () => this.history(true);
    const tasks = $('tasks-dialog') as HTMLDialogElement;
    $('open-tasks').onclick = () => { this.tasks(); tasks.showModal(); };
    $('close-tasks').onclick = () => tasks.close();
    $('settings').onclick = () => settings.showModal(); $('close-settings').onclick = () => settings.close();
    for (const dialog of [history, settings, tasks]) dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
    $('conversation-form').onsubmit = event => { event.preventDefault(); this.send(); };
    document.querySelectorAll<HTMLButtonElement>('[data-question]').forEach(button => button.onclick = () => { $('conversation-text').focus(); ($('conversation-text') as HTMLInputElement).value = button.dataset.question!; this.send(); });
    $('toggle-map').onclick = () => { $('map-card').hidden = !$('map-card').hidden; $('toggle-map').setAttribute('aria-pressed', String(!$('map-card').hidden)); this.map(); };
    $('close-map').onclick = () => { $('map-card').hidden = true; $('toggle-map').setAttribute('aria-pressed', 'false'); $('toggle-map').focus(); };
    $('minimap').onclick = event => { const rect = $('minimap').getBoundingClientRect(); this.onMapFocus(Math.max(0, Math.min(SIZE - 1, (event.clientX - rect.left) / rect.width * SIZE)), Math.max(0, Math.min(SIZE - 1, (event.clientY - rect.top) / rect.height * SIZE))); };
    this.baseMap.width = this.baseMap.height = SIZE;
    $('sound-enabled').toggleAttribute('checked', localStorage.getItem('ai-world-sound') === 'on');
    for (const id of ['effects-enabled', 'bubbles-enabled']) ($<HTMLInputElement>(id)).checked = localStorage.getItem(`ai-world-${id}`) !== 'off';
    for (const id of ['sound-enabled', 'effects-enabled', 'bubbles-enabled']) $(id).onchange = () => this.applySettings();
  }
  applySettings() {
    const sound = $<HTMLInputElement>('sound-enabled').checked, effects = $<HTMLInputElement>('effects-enabled').checked, bubbles = $<HTMLInputElement>('bubbles-enabled').checked;
    localStorage.setItem('ai-world-effects-enabled', effects ? 'on' : 'off'); localStorage.setItem('ai-world-bubbles-enabled', bubbles ? 'on' : 'off');
    this.onSettings({ sound, effects, bubbles });
  }
  select(id: string) {
    if (this.selected !== id) { $<HTMLInputElement>('conversation-text').value = ''; $('conversation-feedback').textContent = this.pending ? '返事を待っています。' : '行動と記憶から、住民が答えます。'; }
    this.selected = id; this.chatKey = ''; this.chat();
  }
  setConnected(connected: boolean) {
    this.connected = connected; this.buttons();
    if (!connected && this.pending) { clearTimeout(this.pending.timer); this.pending = undefined; $('conversation-feedback').textContent = '再接続後、保存済みの会話を読み込みます。'; this.buttons(); }
  }
  private buttons() { $('conversation-send').toggleAttribute('disabled', !this.connected || !!this.pending); document.querySelectorAll<HTMLButtonElement>('[data-question]').forEach(b => b.disabled = !this.connected || !!this.pending); }
  private send() {
    const text = $<HTMLInputElement>('conversation-text').value.trim(); if (!text || !this.connected || this.pending) return;
    const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
    const id = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    this.pending = { id, residentId: this.selected, text, timer: setTimeout(() => { this.pending = undefined; this.buttons(); $('conversation-feedback').textContent = '応答を確認できません。再接続後に会話履歴をご確認ください。'; }, 21_000) };
    this.buttons(); $('conversation-feedback').textContent = '住民が言葉を考えています…'; this.onSend(id, this.selected, text);
  }
  result(result: ConversationResult) {
    if (this.pending?.id !== result.id) return;
    const pending = this.pending; clearTimeout(pending.timer); this.pending = undefined; this.buttons();
    if (this.selected === pending.residentId) {
      $('conversation-feedback').textContent = result.message;
      if (result.ok && $<HTMLInputElement>('conversation-text').value.trim() === pending.text) $<HTMLInputElement>('conversation-text').value = '';
    }
  }
  update(state: VillageState) { this.state = state; if (($('residents-dialog') as HTMLDialogElement).open) this.chat(); if (($('history-dialog') as HTMLDialogElement).open) this.history(); if (($('tasks-dialog') as HTMLDialogElement).open) this.tasks(); this.map(); }
  private chat() {
    const resident = this.state?.residents.find(r => r.id === this.selected); if (!resident) return;
    const key = `${resident.id}:${resident.conversations.map(c => c.id).join(',')}`; if (key === this.chatKey) return; this.chatKey = key;
    const log = $('conversation-log'), follow = log.scrollHeight - log.scrollTop - log.clientHeight < 35;
    log.replaceChildren();
    if (!resident.conversations.length) add('p', log, 'chat-empty', `${resident.name}の仕事や目標、思い出を聞いてみましょう。`);
    for (const conversation of resident.conversations) {
      const question = add('div', log, 'chat-line player', ''); add('small', question, '', 'あなた'); add('p', question, '', conversation.question);
      const answer = add('div', log, 'chat-line resident', ''); add('small', answer, '', `${resident.name} · ${conversation.source === 'llm' ? 'AI' : '行動と記憶'}`); add('p', answer, '', conversation.answer);
    }
    if (follow) log.scrollTop = log.scrollHeight;
  }
  private history(force = false) {
    const state = this.state; if (!state) return;
    const filter = $<HTMLSelectElement>('history-filter').value, key = `${filter}:${state.nextEvent}:${state.archive.count}`;
    if (!force && this.historyKey === key) return; this.historyKey = key;
    const log = $('world-history'), expanded = new Set([...log.querySelectorAll<HTMLDetailsElement>('details[open]')].map(row => row.dataset.event)); log.replaceChildren();
    $('history-archive').textContent = state.archive.count ? `古い${state.archive.count}件を記録にまとめました：${Object.entries(state.archive.kinds).map(([kind, count]) => `${EVENT_LABELS[kind as keyof typeof EVENT_LABELS] ?? '暮らし'} ${count}件`).join(' · ')}。最近の重要な出来事を最大300件表示します。` : '建築・農業・移住などの重要な出来事を、時間とともに保存します。';
    for (const event of state.chronicle.filter(e => filter === 'all' || e.kind === filter).slice().reverse()) {
      const row = add('li', log, 'history-entry', ''), minute = Math.floor((event.time + 480) % 1440);
      add('small', row, '', `${Math.floor((event.time + 480) / 1440) + 1}日目 · ${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')} · ${EVENT_LABELS[event.kind]}`);
      const linked = event.position || event.residentIds?.length || event.buildingId;
      if (!linked) { add('p', row, '', event.text); continue; }
      const details = add('details', row, 'event-details', ''); add('summary', details, '', event.text);
      details.dataset.event = String(event.id); (details as HTMLDetailsElement).open = expanded.has(String(event.id));
      for (const id of event.residentIds ?? []) {
        const resident = state.residents.find(r => r.id === id); if (!resident) continue;
        const button = add('button', details, 'event-link', `${resident.name} · ${resident.job}を見る`) as HTMLButtonElement;
        button.onclick = () => { ($('history-dialog') as HTMLDialogElement).close(); this.onHistoryResident(id); };
      }
      const building = state.huts.find(h => h.id === event.buildingId), bridge = state.bridges.find(b => b.id === event.buildingId), task = state.tasks.find(t => t.id === event.taskId);
      if (building || bridge) add('p', details, '', building ? `${building.name} · ${building.status === 'complete' ? '完成' : `建築 ${building.progress}/${building.total}`}` : `${bridge!.name} · ${bridge!.progress}/${bridge!.blocks.length}`);
      if (task) add('p', details, '', `仕事：${task.title} · ${task.failure || { queued: '担当待ち', running: '作業中', blocked: '再評価待ち', complete: '完成' }[task.status]}`);
      if (event.position) {
        const button = add('button', details, 'event-link', 'この場所を近くで見る ↗') as HTMLButtonElement;
        button.onclick = () => { ($('history-dialog') as HTMLDialogElement).close(); this.onMapFocus(event.position!.x, event.position!.z); };
      }
    }
    if (!log.children.length) add('li', log, 'chat-empty', 'この種類の出来事は、これから刻まれます。');
  }
  private tasks() {
    const state = this.state; if (!state) return;
    const key = JSON.stringify([state.issues, state.bridges.map(b => [b.status, b.progress]), state.tasks.map(t => [t.id, t.status, t.progress, t.assignees, t.failure]), state.resources]);
    if (key === this.tasksKey) return; this.tasksKey = key;
    $('task-issues').textContent = state.issues.length ? `いまの課題：${state.issues.join(' · ')}` : '備蓄と住まいが整いました。住民は維持・交流・探索を続けます。';
    $('bridge-list').replaceChildren();
    for (const bridge of state.bridges) {
      const row = add('article', $('bridge-list'), 'growth-site', ''); add('strong', row, '', bridge.name);
      add('p', row, '', `${bridge.status === 'complete' ? '完成 · 川を渡れます' : bridge.materialsReserved ? '建設中 · 木材を確保済み' : `材料待ち · 木材 ${state.resources.wood}/${bridge.cost.wood}`} · ${bridge.progress}/${bridge.blocks.length}`);
      const progress = add('progress', row, '', '') as HTMLProgressElement; progress.max = 1; progress.value = bridge.progress / bridge.blocks.length;
      const focus = add('button', row, 'event-link', '橋を近くで見る ↗') as HTMLButtonElement;
      const block = bridge.blocks[Math.floor(bridge.blocks.length / 2)]; focus.onclick = () => { ($('tasks-dialog') as HTMLDialogElement).close(); this.onMapFocus(block.x, block.z); };
    }
    if (!state.bridges.length) add('p', $('bridge-list'), '', 'セーヌ川の石橋で両岸を行き来できます。');
    $('task-list').replaceChildren();
    const tasks = state.tasks.filter(t => t.status === 'running' || t.kind !== 'gather' && t.status !== 'complete').sort((a, b) => Number(b.status === 'running') - Number(a.status === 'running') || b.priority - a.priority);
    for (const task of tasks) {
      const row = add('article', $('task-list'), 'growth-site', ''); add('strong', row, '', `${UTILITY_LABELS[task.action]} · ${task.title}`);
      add('p', row, '', `優先度 ${task.priority} · ${{ queued: '担当待ち', running: '作業中', blocked: '再評価待ち', complete: '完成' }[task.status]} · ${Math.floor(task.progress)}/${task.total}`);
      add('p', row, '', `必要人数 ${task.requiredPeople} · 担当 ${task.assignees.map(id => state.residents.find(r => r.id === id)?.name ?? id).join('・') || '未決定'} · 場所 (${Math.floor(task.location.x)}, ${Math.floor(task.location.z)})`);
      if (task.requiredResources.wood || task.requiredResources.stone) add('p', row, '', `必要木材 ${task.requiredResources.wood} / 取り置き ${task.reservedResources.wood} · 必要石材 ${task.requiredResources.stone} / 取り置き ${task.reservedResources.stone}`);
      if (task.failure) add('p', row, 'instruction-error', `${task.failure} · 再評価まで${Math.max(0, Math.ceil(task.retryAt - state.elapsed))}分`);
    }
    if (!tasks.length) add('p', $('task-list'), '', '住民は体調と備蓄を見て、次の仕事を選びます。');
  }
  setWorld(data: Uint8Array) { this.data = data; for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) this.mapPixel(x, z); this.map(); }
  terrain(edits: Edit[]) { for (const edit of edits) this.mapPixel(edit.x, edit.z); this.map(); }
  view(x: number, z: number, radius: number) { this.target = { x, z, radius }; this.map(); }
  private mapPixel(x: number, z: number) {
    if (!this.data) return; const context = this.baseMap.getContext('2d')!;
    const colors: Record<number, string> = { 1: '#8cac68', 2: '#ae8f6e', 3: '#9aa4a1', 4: '#e5d49c', 5: '#aa8057', 6: '#4e8051', 7: '#7fbdc7', 8: '#c6886b' };
    let y = HEIGHT - 1; while (y > 0 && getBlock(this.data, x, y, z) === Block.Air) y--;
    context.fillStyle = colors[getBlock(this.data, x, y, z)] ?? '#7fbdc7'; context.fillRect(x, z, 1, 1);
  }
  private map() {
    if ($('map-card').hidden) return;
    const context = $<HTMLCanvasElement>('minimap').getContext('2d')!; context.imageSmoothingEnabled = false; context.drawImage(this.baseMap, 0, 0, 256, 256);
    const scale = 256 / SIZE;
    context.strokeStyle = '#fff9'; const span = Math.min(SIZE, this.target.radius * .6); context.strokeRect((this.target.x - span / 2) * scale, (this.target.z - span / 2) * scale, span * scale, span * scale);
    context.fillStyle = '#fff3cc'; context.font = 'bold 13px sans-serif'; context.textAlign = 'center'; context.fillText('♜', EIFFEL.x * scale, EIFFEL.z * scale + 4);
    context.fillStyle = '#fbe6cb'; context.fillText('✧', ARC.x * scale, ARC.z * scale + 4);
    if (!this.state) return;
    context.fillStyle = '#ffe4a1'; context.fillRect(this.state.camp.x * scale - 4, this.state.camp.z * scale - 4, 8, 8);
    context.fillStyle = '#fff'; for (const resident of this.state.residents) context.fillRect(resident.position.x * scale - 1, resident.position.z * scale - 1, 3, 3);
  }
}
