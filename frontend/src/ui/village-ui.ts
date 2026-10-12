import { ACTION_LABELS, beds, EVENT_LABELS, growthRequirements, MAX_POPULATION, RESOURCE_LABELS, type VillageState } from '../../../shared/village';
const $ = (id: string) => document.getElementById(id)!;
const add = (tag: string, parent: HTMLElement, className = '', text = '') => {
  const element = document.createElement(tag); element.className = className; element.textContent = text; parent.append(element); return element;
};
export class VillageUI {
  private selected = 'haru';
  private state?: VillageState;
  private rows = new Map<string, { action: HTMLElement; title: HTMLElement; button: HTMLButtonElement }>();
  private roster = new Map<string, HTMLButtonElement>();
  private dialog = $('residents-dialog') as HTMLDialogElement;
  private growthDialog = $('civilization-dialog') as HTMLDialogElement;
  onFocus: (state: VillageState, id?: string) => void = () => {};
  onSelect: (id: string) => void = () => {};
  constructor() {
    $('residents').onclick = () => { if (!this.state) return; this.open(this.selected); };
    $('close-residents').onclick = () => this.dialog.close();
    $('focus-resident').onclick = () => { if (this.state) this.onFocus(this.state, this.selected); this.dialog.close(); };
    $('start-building').onclick = () => { if (this.state) this.onFocus(this.state); };
    $('civilization').onclick = () => { this.growth(); this.growthDialog.showModal(); };
    $('close-civilization').onclick = () => this.growthDialog.close();
    $('focus-development').onclick = () => { if (this.state) this.onFocus(this.state); this.growthDialog.close(); };
    this.growthDialog.addEventListener('click', e => { if (e.target === this.growthDialog) {
      const r = this.growthDialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) this.growthDialog.close();
    } });
    this.dialog.addEventListener('click', e => { if (e.target === this.dialog) {
      const r = this.dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) this.dialog.close();
    } });
  }
  open(id: string) { this.selected = id; this.onSelect(id); this.details(); if (!this.dialog.open) this.dialog.showModal(); }
  update(state: VillageState) {
    this.state = state;
    $('population').textContent = `住民 ${state.residents.length}`;
    for (const kind of ['food', 'wood', 'stone'] as const) $(`resource-${kind}`).textContent = `${RESOURCE_LABELS[kind]} ${state.resources[kind]}`;
    $('homes').textContent = `寝床 ${state.residents.filter(r => r.home).length}人 / ${beds(state)}人分`;
    $('village-title').textContent = `${state.residents.length}人の、育つ暮らし。`;
    $('civilization-label').textContent = state.civilization.level === 2 ? 'Lv.2 村' : 'Lv.1 集落';
    for (const r of state.residents) {
      let row = this.rows.get(r.id);
      if (!row) {
        const button = add('button', $('resident-list'), 'resident-row') as HTMLButtonElement;
        button.setAttribute('aria-label', `${r.name}の詳細`); button.onclick = () => this.open(r.id);
        const dot = add('span', button, 'resident-avatar', r.name.slice(0, 1)); dot.style.background = r.color;
        const text = add('span', button, 'resident-row-copy'); const title = add('strong', text);
        row = { button, title, action: add('small', text) }; this.rows.set(r.id, row);
        const roster = add('button', $('resident-roster'), 'roster-person', r.name) as HTMLButtonElement;
        roster.style.setProperty('--resident-color', r.color); roster.onclick = () => this.open(r.id); this.roster.set(r.id, roster);
      }
      row.title.textContent = `${r.name} · ${r.job}`; row.action.textContent = ACTION_LABELS[r.action]; row.button.title = r.reason;
    }
    const active = state.huts.find(h => h.status !== 'complete');
    $('hut-status').textContent = active ? `${active.name} · ${active.status === 'planned' ? '材料を集めています' : `${active.upgrading ? '改築' : '建築'}中 ${Math.floor(active.progress / active.total * 100)}%`}` : '村の暮らしを整えています';
    ($('hut-progress') as HTMLProgressElement).value = active ? active.progress / active.total : 1;
    $('hut-materials').textContent = active && !active.materialsReserved ? `木材 ${Math.min(state.resources.wood, active.cost.wood)}/${active.cost.wood} · 石材 ${Math.min(state.resources.stone, active.cost.stone)}/${active.cost.stone}` : active ? '資源を確保して建築中' : '農業・採集・食事・休息を続けます';
    const last = state.events.at(-1); if (last) $('village-event').textContent = last.text;
    if (this.dialog.open) this.details();
    if (this.growthDialog.open) this.growth();
  }
  private growth() {
    const s = this.state; if (!s) return;
    const c = s.civilization, population = s.residents.length, capacity = beds(s);
    $('growth-title').textContent = c.level === 2 ? '農業が根づいた、私たちの村。' : '集落から、村へ。';
    $('growth-description').textContent = c.level === 2 ? 'Level 2 · 農業と住まいが整い、新しい仲間を迎えられる村になりました。' : 'Level 1 · 住民が仕事を分担して、採集の集落から農業の村へ育てます。';
    $('growth-population').textContent = `${population} / ${capacity}人`;
    $('growth-harvests').textContent = `${c.harvests}回`;
    $('growth-buildings').textContent = `${s.huts.filter(h => h.status === 'complete').length}棟`;
    $('growth-requirements-title').textContent = c.level === 2 ? 'Level 2「村」に発展済み' : 'Level 2「村」への条件';
    $('growth-requirements').replaceChildren();
    for (const requirement of growthRequirements(s)) { const met = c.level === 2 || requirement.met; add('span', $('growth-requirements'), met ? 'met' : '', `${met ? '✓' : '○'} ${requirement.label}`); }
    const food = population * 3 + 4, waiting: string[] = [];
    if (c.level < 2) waiting.push('Level 2への発展');
    if (capacity <= population) waiting.push('完成した家の空き寝床');
    if (s.resources.food < food) waiting.push(`食料 ${s.resources.food}/${food}`);
    $('growth-arrival').textContent = population >= MAX_POPULATION ? '人口20人に到達しました。これからも村の暮らしは続きます。' : waiting.length ? `移住を待っています：${waiting.join(' · ')}。移住時は歓迎の食料4を使います。` : `受け入れ準備が整いました。次の移住判定まで約${Math.max(0, Math.ceil(c.nextArrival - s.elapsed))}分（ゲーム内）。道が通じていれば1人が移住します。`;
    $('growth-jobs').replaceChildren();
    for (const job of [...new Set(s.residents.map(r => r.job))]) add('span', $('growth-jobs'), '', `${job} ${s.residents.filter(r => r.job === job).length}人`);
    $('growth-sites').replaceChildren();
    for (const building of s.huts) {
      const card = add('article', $('growth-sites'), 'growth-site');
      add('strong', card, '', `${building.name}${building.upgrading ? ' · 小屋から改築' : ''}`);
      const crop = building.crop;
      const status = building.status !== 'complete' ? building.status === 'planned' ? `材料待ち · 木材${building.cost.wood} / 石材${building.cost.stone}` : `${building.upgrading ? '改築' : '建築'}中 ${Math.floor(building.progress / building.total * 100)}%` :
        crop ? crop.stage === 'growing' ? `生育中 ${Math.floor(crop.growth * 100)}% · 約${Math.ceil((1 - crop.growth) * 180)}分で収穫` : crop.stage === 'ripe' ? `収穫待ち · 食料${crop.remaining}が実っています` : '種まき待ち' :
          building.kind === 'warehouse' ? '完成 · 収穫量32、木材80・石材40が備蓄の目安' : `完成 · ${building.kind === 'house' ? 4 : 2}人分の寝床`;
      add('p', card, '', status);
      const progress = add('progress', card) as HTMLProgressElement; progress.max = 1;
      progress.value = building.status !== 'complete' ? building.progress / building.total : crop ? crop.growth : 1;
      progress.setAttribute('aria-label', `${building.name}の${crop && building.status === 'complete' ? '作物の成長' : '建築進捗'}`);
    }
    $('growth-events').replaceChildren();
    for (const event of s.events.filter(e => e.kind !== 'life').slice(-12).reverse()) {
      const row = add('li', $('growth-events'));
      add('small', row, '', `開始から${Math.floor(event.time / 60)}時間 · ${EVENT_LABELS[event.kind]}`);
      add('span', row, '', event.text);
    }
    if (!$('growth-events').children.length) add('li', $('growth-events'), '', 'これから村の歴史が生まれます。');
  }
  private details() {
    const r = this.state?.residents.find(r => r.id === this.selected); if (!r || !this.state) return;
    for (const [id, button] of this.roster) { button.classList.toggle('active', id === r.id); button.setAttribute('aria-pressed', String(id === r.id)); }
    $('resident-name').textContent = r.name; $('resident-meta').textContent = `${r.age}歳 · ${r.job} · ${r.personality}`;
    $('resident-action').textContent = ACTION_LABELS[r.action]; $('resident-reason').textContent = r.reason;
    for (const key of ['health', 'energy', 'hunger'] as const) {
      ($(`resident-${key}`) as HTMLMeterElement).value = r[key]; $(`resident-${key}-value`).textContent = `${Math.round(r[key])} / 100`;
    }
    $('resident-inventory').textContent = `食料 ${r.inventory.food} · 木材 ${r.inventory.wood} · 石材 ${r.inventory.stone} ／ 持てる量 8`;
    $('resident-goal').textContent = r.goal; $('resident-home').textContent = r.home ? `${this.state.huts.find(h => h.id === r.home)?.name}に寝床あり` : '小屋の完成を待っています';
    $('resident-memories').replaceChildren(); for (const memory of [...r.memories].reverse()) add('li', $('resident-memories'), '', memory);
    $('resident-summary').textContent = r.memorySummary;
    $('resident-relations').textContent = Object.entries(r.relationships).map(([id, value]) => `${this.state!.residents.find(other => other.id === id)?.name} ${value}`).join(' · ');
    $('village-history').replaceChildren(); for (const event of [...this.state.events].reverse().slice(0, 10)) add('li', $('village-history'), '', event.text);
  }
}
