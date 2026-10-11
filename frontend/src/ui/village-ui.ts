import { ACTION_LABELS, RESOURCE_LABELS, type Resident, type VillageState } from '../../../shared/village';
const $ = (id: string) => document.getElementById(id)!;
const add = (tag: string, parent: HTMLElement, className = '', text = '') => {
  const element = document.createElement(tag); element.className = className; element.textContent = text; parent.append(element); return element;
};
export class VillageUI {
  private selected = 'haru';
  private state?: VillageState;
  private rows = new Map<string, { action: HTMLElement; button: HTMLButtonElement }>();
  private roster = new Map<string, HTMLButtonElement>();
  private dialog = $('residents-dialog') as HTMLDialogElement;
  onFocus: (state: VillageState, id?: string) => void = () => {};
  onSelect: (id: string) => void = () => {};
  constructor() {
    $('residents').onclick = () => { if (!this.state) return; this.open(this.selected); };
    $('close-residents').onclick = () => this.dialog.close();
    $('focus-resident').onclick = () => { if (this.state) this.onFocus(this.state, this.selected); this.dialog.close(); };
    $('start-building').onclick = () => { if (this.state) this.onFocus(this.state); };
    this.dialog.addEventListener('click', e => { if (e.target === this.dialog) {
      const r = this.dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) this.dialog.close();
    } });
  }
  open(id: string) { this.selected = id; this.onSelect(id); this.details(); if (!this.dialog.open) this.dialog.showModal(); }
  update(state: VillageState) {
    this.state = state;
    $('population').textContent = `住民 ${state.residents.length}`;
    for (const kind of ['food', 'wood', 'stone'] as const) $(`resource-${kind}`).textContent = `${RESOURCE_LABELS[kind]} ${state.resources[kind]}`;
    $('homes').textContent = `小屋 ${state.huts.filter(h => h.status === 'complete').length} / 3`;
    for (const r of state.residents) {
      let row = this.rows.get(r.id);
      if (!row) {
        const button = add('button', $('resident-list'), 'resident-row') as HTMLButtonElement;
        button.setAttribute('aria-label', `${r.name}の詳細`); button.onclick = () => this.open(r.id);
        const dot = add('span', button, 'resident-avatar', r.name.slice(0, 1)); dot.style.background = r.color;
        const text = add('span', button, 'resident-row-copy'); add('strong', text, '', `${r.name} · ${r.job}`);
        row = { button, action: add('small', text) }; this.rows.set(r.id, row);
        const roster = add('button', $('resident-roster'), 'roster-person', r.name) as HTMLButtonElement;
        roster.style.setProperty('--resident-color', r.color); roster.onclick = () => this.open(r.id); this.roster.set(r.id, roster);
      }
      row.action.textContent = ACTION_LABELS[r.action]; row.button.title = r.reason;
    }
    const active = state.huts.find(h => h.status !== 'complete');
    $('hut-status').textContent = active ? `${active.name} · ${active.status === 'planned' ? '材料を集めています' : `建築中 ${Math.floor(active.progress / active.total * 100)}%`}` : '全員の寝床ができました';
    ($('hut-progress') as HTMLProgressElement).value = active ? active.progress / active.total : 1;
    $('hut-materials').textContent = active && !active.materialsReserved ? `木材 ${Math.min(state.resources.wood, active.cost.wood)}/${active.cost.wood} · 石材 ${Math.min(state.resources.stone, active.cost.stone)}/${active.cost.stone}` : active ? '資源を確保して建築中' : '住民は採集・食事・休息を続けます';
    const last = state.events.at(-1); if (last) $('village-event').textContent = last.text;
    this.details();
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
