import { Block, HEIGHT, SIZE, getBlock, type Edit } from '../../../shared/world';
import { EVENT_LABELS, type VillageState } from '../../../shared/village';
import type { ConversationResult } from '../../../shared/conversation';
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const add = (tag: string, parent: HTMLElement, className: string, text: string) => { const element = document.createElement(tag); element.className = className; element.textContent = text; parent.append(element); return element; };
export class LifeUI {
  onSend: (id: string, residentId: string, text: string) => void = () => {};
  onMapFocus: (x: number, z: number) => void = () => {};
  onSettings: (settings: { sound: boolean; effects: boolean; bubbles: boolean; quality: 'auto' | 'low' | 'high' }) => void = () => {};
  private selected = 'haru';
  private state?: VillageState;
  private connected = false;
  private pending?: { id: string; residentId: string; text: string; timer: ReturnType<typeof setTimeout> };
  private chatKey = '';
  private historyKey = '';
  private baseMap = document.createElement('canvas');
  private data?: Uint8Array;
  private target = { x: 64, z: 64, radius: 80 };
  constructor() {
    const history = $('history-dialog') as HTMLDialogElement, settings = $('settings-dialog') as HTMLDialogElement;
    $('open-history').onclick = () => { this.history(true); history.showModal(); };
    $('close-history').onclick = () => history.close(); $('history-filter').onchange = () => this.history(true);
    $('settings').onclick = () => settings.showModal(); $('close-settings').onclick = () => settings.close();
    for (const dialog of [history, settings]) dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
    $('conversation-form').onsubmit = event => { event.preventDefault(); this.send(); };
    document.querySelectorAll<HTMLButtonElement>('[data-question]').forEach(button => button.onclick = () => { $('conversation-text').focus(); ($('conversation-text') as HTMLInputElement).value = button.dataset.question!; this.send(); });
    $('toggle-map').onclick = () => { $('map-card').hidden = !$('map-card').hidden; $('toggle-map').setAttribute('aria-pressed', String(!$('map-card').hidden)); this.map(); };
    $('minimap').onclick = event => { const rect = $('minimap').getBoundingClientRect(); this.onMapFocus(Math.max(0, Math.min(SIZE - 1, (event.clientX - rect.left) / rect.width * SIZE)), Math.max(0, Math.min(SIZE - 1, (event.clientY - rect.top) / rect.height * SIZE))); };
    this.baseMap.width = this.baseMap.height = SIZE;
    $('sound-enabled').toggleAttribute('checked', localStorage.getItem('ai-world-sound') === 'on');
    for (const id of ['effects-enabled', 'bubbles-enabled']) ($<HTMLInputElement>(id)).checked = localStorage.getItem(`ai-world-${id}`) !== 'off';
    const quality = localStorage.getItem('ai-world-quality'); $<HTMLSelectElement>('render-quality').value = quality === 'low' || quality === 'high' ? quality : 'auto';
    for (const id of ['sound-enabled', 'effects-enabled', 'bubbles-enabled', 'render-quality']) $(id).onchange = () => this.applySettings();
  }
  applySettings() {
    const sound = $<HTMLInputElement>('sound-enabled').checked, effects = $<HTMLInputElement>('effects-enabled').checked, bubbles = $<HTMLInputElement>('bubbles-enabled').checked;
    const quality = $<HTMLSelectElement>('render-quality').value as 'auto' | 'low' | 'high';
    localStorage.setItem('ai-world-effects-enabled', effects ? 'on' : 'off'); localStorage.setItem('ai-world-bubbles-enabled', bubbles ? 'on' : 'off'); localStorage.setItem('ai-world-quality', quality);
    this.onSettings({ sound, effects, bubbles, quality });
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
  update(state: VillageState) { this.state = state; if (($('residents-dialog') as HTMLDialogElement).open) this.chat(); if (($('history-dialog') as HTMLDialogElement).open) this.history(); this.map(); }
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
    const log = $('world-history'); log.replaceChildren();
    $('history-archive').textContent = state.archive.count ? `古い${state.archive.count}件を記録にまとめました：${Object.entries(state.archive.kinds).map(([kind, count]) => `${EVENT_LABELS[kind as keyof typeof EVENT_LABELS] ?? '暮らし'} ${count}件`).join(' · ')}。最近の重要な出来事を最大300件表示します。` : '建築・農業・移住などの重要な出来事を、時間とともに保存します。';
    for (const event of state.chronicle.filter(e => filter === 'all' || e.kind === filter).slice().reverse()) {
      const row = add('li', log, 'history-entry', ''), minute = Math.floor((event.time + 480) % 1440);
      add('small', row, '', `${Math.floor((event.time + 480) / 1440) + 1}日目 · ${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')} · ${EVENT_LABELS[event.kind]}`);
      add('p', row, '', event.text);
    }
    if (!log.children.length) add('li', log, 'chat-empty', 'この種類の出来事は、これから刻まれます。');
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
    context.strokeStyle = '#fff9'; const span = Math.min(128, this.target.radius * .6); context.strokeRect((this.target.x - span / 2) * 2, (this.target.z - span / 2) * 2, span * 2, span * 2);
    if (!this.state) return;
    context.fillStyle = '#ffe4a1'; context.fillRect(this.state.camp.x * 2 - 4, this.state.camp.z * 2 - 4, 8, 8);
    context.fillStyle = '#fff'; for (const resident of this.state.residents) context.fillRect(resident.position.x * 2 - 1, resident.position.z * 2 - 1, 3, 3);
  }
}
