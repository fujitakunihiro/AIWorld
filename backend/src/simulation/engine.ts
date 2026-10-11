import { Block, HEIGHT, SIZE, getBlock, index, type Edit } from '../../../shared/world';
import type { BuildingKind, Hut, Position, Resident, Resource, Resources, VillageState, VillageEvent } from '../../../shared/village';
import { beds, BUILDING_LABELS, growthRequirements, MAX_BUILDINGS, MAX_POPULATION, RESOURCE_LABELS } from '../../../shared/village';
import { interpretationSchema } from '../../../shared/instruction-schema';
import { Navigation } from '../agents/navigation';
import { siteClear } from '../buildings/hut';
import { BUILDING_COSTS, buildingBlocks } from '../buildings/development';
import { describeCommand, MAX_HUTS, type Interpretation, type InstructionRecord } from '../../../shared/instructions';
const empty = (): Resources => ({ food: 0, wood: 0, stone: 0 });
const distance = (a: Position, b: Position) => Math.hypot(a.x - b.x, a.z - b.z);
const carried = (r: Resident) => r.inventory.food + r.inventory.wood + r.inventory.stone;
const capacity = 8;
const profiles = [
  ['haru', 'ハル', 24, '慎重で世話好き', '建築家', '#cb896c'],
  ['mio', 'ミオ', 21, '好奇心旺盛', '木こり', '#86a975'],
  ['ren', 'レン', 28, '粘り強い', '採掘師', '#7f9bae'],
  ['sora', 'ソラ', 22, '穏やかで食いしん坊', '採集家', '#d2b16c'],
  ['yui', 'ユイ', 26, '仲間思いで行動的', '木こり', '#b18cba']
] as const;
export class Simulation {
  readonly data: Uint8Array;
  readonly nav: Navigation;
  readonly state: VillageState;
  private terrainDirty = false;
  economicChange = false;
  constructor(data: Uint8Array, saved: VillageState | null = null) {
    this.data = data.slice(); this.nav = new Navigation(this.data);
    if (saved) { this.state = saved; this.revalidate(); return; }
    const camp = this.nav.nearest({ x: 34.5, y: 11, z: 45.5 });
    if (!camp) throw new Error('住民が暮らせる陸地がありません。');
    const reachable = this.nav.search(camp);
    const spawn = reachable.queue.slice(0, 5).map(id => this.nav.position(id % SIZE, Math.floor(id / SIZE))!);
    if (spawn.length < 5) throw new Error('5人の住民が暮らせる連続した陸地が必要です。');
    this.state = { version: 2, civilization: { level: 1, nextArrival: 720, nextEventAt: 720, eventSequence: 0, arrivals: 0, harvests: 0 }, residents: profiles.map((p, i) => ({
      id: p[0], name: p[1], age: p[2], personality: p[3], job: p[4], color: p[5],
      health: 100, energy: 90 - i * 3, hunger: 12 + i * 3, inventory: empty(), position: spawn[i],
      action: 'idle', reason: 'この島に、みんなで暮らせる村をつくりたい。', goal: '5人全員が安心して眠れる小屋をつくる',
      relationships: Object.fromEntries(profiles.filter(other => other[0] !== p[0]).map(other => [other[0], 50])),
      memories: ['仲間5人と、はじまりの島で暮らし始めた。'], memorySummary: '',
      task: null, path: [], work: 0, decisionIn: i * 0.5, home: null, order: null
    })), resources: { food: 12, wood: 0, stone: 0 }, nodes: [], huts: [], camp,
      events: [{ id: 1, time: 0, kind: 'arrival', text: '5人の住民が島に到着しました。まずは小屋の材料を集めます。' }], nextEvent: 2, elapsed: 0, nextPlan: 0, instructions: [] };
    // Natural trees remain standing: these are renewable gathering sites, not infinite inventory.
    for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
      if (this.state.nodes.filter(n => n.kind === 'wood').length >= 36) break;
      for (let y = 2; y < HEIGHT - 3; y++) if (getBlock(this.data, x, y, z) === Block.Wood && getBlock(this.data, x, y - 1, z) === Block.Grass) {
        const p = { x: x + 0.5, y, z: z + 0.5 };
        if (this.adjacent(p).some(adj => this.nav.pathFrom(reachable, adj) !== null)) this.node('wood', p, 24);
        break;
      }
    }
    const candidates = reachable.queue.map(id => this.nav.position(id % SIZE, Math.floor(id / SIZE))!).filter(p => distance(p, camp) > 7 && distance(p, camp) < 20);
    for (const kind of ['food', 'stone'] as const) for (let i = 0; i < 5; i++) {
      const p = candidates.find(p => this.state.nodes.every(n => distance(n.position, p) > 4));
      if (p) this.node(kind, p, kind === 'food' ? 20 : 30);
    }
    this.planHut();
  }
  private node(kind: Resource, position: Position, amount: number) {
    this.state.nodes.push({ id: `${kind}-${this.state.nodes.length}`, kind, position, remaining: amount, capacity: amount, regeneration: 0 });
  }
  private event(text: string, kind: VillageEvent['kind'] = 'life') {
    this.state.events.push({ id: this.state.nextEvent++, time: this.state.elapsed, text, kind });
    if (this.state.events.length > 30) this.state.events.shift(); this.economicChange = true;
  }
  private remember(r: Resident, text: string) {
    r.memories.push(text);
    if (r.memories.length > 8) { r.memorySummary = `以前の記憶：${r.memories.shift()}`; }
  }
  adjacent(p: Position) {
    return [[1, 0], [0, 1], [-1, 0], [0, -1]].map(([dx, dz]) => this.nav.position(Math.floor(p.x) + dx, Math.floor(p.z) + dz))
      .filter((point): point is Position => !!point && Math.abs(point.y - p.y) <= 1);
  }
  terrainChanged(edit: Edit) { this.data[index(edit.x, edit.y, edit.z)] = edit.block; this.terrainDirty = true; }
  private isReserved(x: number, z: number) {
    return this.state.huts.some(h => x >= h.x - 1 && x <= h.x + 4 && z >= h.z - 1 && z <= h.z + 4);
  }
  private planHut() {
    if (this.state.huts.filter(h => h.kind === 'hut' || h.kind === 'house').length >= 3 || this.state.huts.some(h => h.status !== 'complete')) return;
    const hut = this.findHut('village', [], 'hut');
    if (hut) { this.state.huts.push(hut); this.event(`${hut.name}の敷地を確保しました。木材24・石材8を集めます。`); }
  }
  private findHut(location: 'village' | 'river' | 'forest', extra: Hut[], kind: BuildingKind): Hut | null {
    const search = this.nav.search(this.state.camp);
    const river: Position[] = [];
    if (location === 'river') for (let z = 8; z < SIZE - 8; z++) for (let x = 18; x <= 29; x++) if (getBlock(this.data, x, 5, z) === Block.Water) river.push({ x, y: 5, z });
    const trees = this.state.nodes.filter(n => n.kind === 'wood' && this.nodeValid(n)).map(n => n.position);
    const landmarks = location === 'river' ? river : location === 'forest' ? trees : [this.state.camp];
    const proximity = (p: { x: number; z: number }) => Math.min(...landmarks.map(n => Math.hypot(n.x - p.x - 2, n.z - p.z - 2)));
    const preferred = [{ x: 29, z: 35 }, { x: 35, z: 35 }, { x: 29, z: 41 }];
    const score = (p: { x: number; z: number }) => {
      if (location !== 'village') return proximity(p);
      const priority = preferred.findIndex(site => site.x === p.x && site.z === p.z);
      return priority >= 0 ? priority : 10 + Math.hypot(p.x - 33, p.z - 39);
    };
    const sites = search.queue.map(id => ({ x: id % SIZE, z: Math.floor(id / SIZE) })).sort((a, b) => score(a) - score(b));
    for (const { x, z } of sites) {
      if (proximity({ x, z }) > (location === 'village' ? 24 : 10)) continue;
      const y = this.nav.height(x, z);
      if (y < 1 || !siteClear(this.data, x, y, z)) continue;
      if ([...this.state.huts, ...extra].some(h => x < h.x + 5 && x + 5 > h.x && z < h.z + 5 && z + 5 > h.z)) continue;
      if (this.state.camp.x >= x - 1 && this.state.camp.x < x + 5 && this.state.camp.z >= z - 1 && this.state.camp.z < z + 5) continue;
      if (this.state.nodes.some(n => n.position.x >= x && n.position.x < x + 4 && n.position.z >= z && n.position.z < z + 4)) continue;
      const stand = this.nav.position(x + 1, z + 4);
      // A one-block lower approach needs an entrance step once the floor is built.
      if (!stand || Math.abs(stand.y - y) > 1 || this.nav.pathFrom(search, stand) === null) continue;
      const workStand = this.nav.position(x + 2, z + 4);
      if (!workStand || this.nav.pathFrom(search, workStand) === null) continue;
      const number = this.state.huts.length + extra.length + 1;
      const hut: Hut = { id: `hut-${number}`, kind, name: `${BUILDING_LABELS[kind]} ${this.state.huts.filter(h => h.kind === kind).length + extra.filter(h => h.kind === kind).length + 1}`, x, y, z,
        status: 'planned', progress: 0, total: 0, cost: { ...BUILDING_COSTS[kind] }, builder: null, materialsReserved: false, entranceStep: kind !== 'farm' && stand.y < y, upgrading: false,
        crop: kind === 'farm' ? { stage: 'fallow', growth: 0, harvests: 0, remaining: 0 } : null };
      hut.total = buildingBlocks(hut).length; return hut;
    }
    return null;
  }
  private planDevelopment() {
    if (this.state.huts.some(h => h.status !== 'complete') || this.state.huts.length >= MAX_BUILDINGS) return;
    if (this.state.huts.filter(h => h.kind === 'hut' || h.kind === 'house').length < 3) { this.planHut(); return; }
    const count = (kind: BuildingKind) => this.state.huts.filter(h => h.kind === kind).length;
    const candidates: BuildingKind[] = [];
    if (count('farm') < Math.ceil(this.state.residents.length / 6)) candidates.push('farm');
    if (!count('warehouse')) candidates.push('warehouse');
    if (!count('house') || (beds(this.state) - this.state.residents.length < 2 && this.state.residents.length < MAX_POPULATION)) candidates.push('house');
    for (const kind of candidates) {
      const building = this.findHut('village', [], kind);
      if (!building) {
        if (kind === 'house') {
          const old = this.state.huts.find(h => h.kind === 'hut' && this.nav.path(this.state.camp, this.nav.position(h.x + 2, h.z + 4) ?? { x: -1, y: -1, z: -1 }) !== null);
          if (old) {
            const oldName = old.name; old.kind = 'house'; old.name = `住宅 ${count('house')}`; old.upgrading = true;
            old.status = 'planned'; old.progress = 0; old.cost = { food: 0, wood: 24, stone: 12 }; old.materialsReserved = false; old.builder = null; old.total = buildingBlocks(old).length;
            this.event(`${oldName}を住宅へ改築します。木材24・石材12で、寝床が2人分から4人分に増えます。`, 'growth'); break;
          }
        }
        continue;
      }
      this.state.huts.push(building); this.event(`${building.name}の敷地を確保しました。${kind === 'farm' ? '採集に加えて、作物を育てます。' : kind === 'house' ? '家族や新しい住民のために4人分の住宅を建てます。' : '倉庫で収穫量と資源の備蓄を増やします。'}`); break;
    }
  }
  private assignHomes() {
    for (const building of this.state.huts.filter(h => h.status === 'complete' && (h.kind === 'hut' || h.kind === 'house'))) {
      const free = (building.kind === 'house' ? 4 : 2) - this.state.residents.filter(r => r.home === building.id).length;
      for (const r of this.state.residents.filter(r => !r.home).slice(0, Math.max(0, free))) {
        r.home = building.id; this.remember(r, `${building.name}に自分の寝床ができた。`);
      }
    }
  }
  private develop() {
    const c = this.state.civilization;
    if (this.state.residents.every(r => r.home)) for (const r of this.state.residents) {
      if (r.job !== '農家') r.goal = r.job === '建築家' ? '農業と住宅を整えて、新しい仲間を迎える' : r.job === '木こり' ? '村の建築と備蓄に使う木材を届ける' : r.job === '採掘師' ? '住宅と倉庫の土台に使う石材を届ける' : '村の食料を安定して確保する';
    }
    if (this.state.huts.some(h => h.kind === 'farm' && h.status === 'complete') && !this.state.residents.some(r => r.job === '農家')) {
      const farmer = this.state.residents.find(r => r.job === '採集家') ?? this.state.residents.find(r => r.job === '木こり');
      if (farmer) { farmer.job = '農家'; farmer.goal = '畑を育てて、村に安定した食料を届ける'; this.remember(farmer, '畑ができたので、農家の仕事を選んだ。'); this.event(`${farmer.name}が農家になりました。種まきと収穫を担当します。`, 'growth'); }
    }
    if (c.level === 1 && growthRequirements(this.state).every(r => r.met)) {
      c.level = 2; this.event('文明が Level 2「村」に発展！ 農業・住宅・倉庫と役割分担が揃いました。', 'growth');
      for (const r of this.state.residents) this.remember(r, 'みんなの集落が、農業を営む村になった。');
    }
    if (c.nextArrival <= this.state.elapsed) {
      c.nextArrival = this.state.elapsed + 60; this.economicChange = true;
      const population = this.state.residents.length;
      const home = this.state.huts.find(h => h.status === 'complete' && (h.kind === 'house' || h.kind === 'hut') && this.state.residents.filter(r => r.home === h.id).length < (h.kind === 'house' ? 4 : 2));
      const door = home ? this.nav.position(home.x + 1, home.z + 4) : null;
      if (c.level === 2 && population < MAX_POPULATION && this.state.resources.food >= population * 3 + 4 && door && this.nav.path(this.state.camp, door) !== null) {
        const names = ['アオ', 'ナギ', 'ヒナ', 'カイ', 'ツキ', 'リク', 'メイ', 'トワ', 'フウ', 'サキ', 'イツキ', 'コハク', 'セナ', 'ルイ', 'アサ'];
        const jobs = ['農家', '木こり', '採掘師'];
        const job = jobs.slice().sort((a, b) => this.state.residents.filter(r => r.job === a).length - this.state.residents.filter(r => r.job === b).length)[0];
        const n = c.arrivals++, id = `new-${n + 1}`;
        const newcomer: Resident = { id, name: names[n], age: 20 + n % 13, personality: '新しい暮らしを楽しみにしている', job, color: ['#77a69b', '#c5a575', '#a589b9'][n % 3],
          health: 100, hunger: 15, energy: 85, inventory: empty(), position: { ...this.state.camp }, action: 'idle', reason: '食料と住宅が整った村へ移住した。仲間と仕事を始めたい。', goal: job === '農家' ? '村の食料を育てる' : '村の発展に必要な資源を届ける',
          relationships: Object.fromEntries(this.state.residents.map(r => [r.id, 50])), memories: ['安心して暮らせる村の噂を聞いて、島へ移住した。'], memorySummary: '', task: null, path: [], work: 0, decisionIn: 0, home: null, order: null };
        for (const r of this.state.residents) r.relationships[id] = 50;
        this.state.resources.food -= 4; this.state.residents.push(newcomer); this.assignHomes(); c.nextArrival = this.state.elapsed + 720;
        this.event(`${newcomer.name}が移住しました！ ${job}として暮らします。歓迎の食料4を使い、人口${population + 1}人になりました。`, 'arrival');
      }
    }
    if (c.nextEventAt <= this.state.elapsed) {
      c.nextEventAt = this.state.elapsed + 720;
      const type = c.eventSequence++ % 3, population = this.state.residents.length;
      if (type === 0) {
        for (const h of this.state.huts) if (h.crop?.stage === 'growing') { h.crop.growth = Math.min(1, h.crop.growth + 0.2); if (h.crop.growth === 1) { h.crop.stage = 'ripe'; h.crop.remaining = this.harvestYield(); } }
        this.event('恵みの雨が降りました。育ち途中の作物が20%成長しました。', 'weather');
      } else if (type === 1 && this.state.resources.food >= population * 4) {
        this.state.resources.food -= population;
        for (const r of this.state.residents) { r.energy = Math.min(100, r.energy + 15); this.remember(r, '村の収穫祭で仲間と食卓を囲んだ。'); }
        this.event(`収穫祭を開きました。食料${population}を分け合い、全員の元気が15回復しました。`, 'festival');
      } else if (type === 2 && this.state.huts.some(h => h.kind === 'warehouse' && h.status === 'complete') && this.state.resources.food >= population * 3 + 6) {
        this.state.resources.food -= 6; this.state.resources.wood += 8; this.state.resources.stone += 4;
        this.event('旅の商人が倉庫を訪れました。食料6を木材8・石材4と交換しました。', 'trade');
      } else this.event(this.state.resources.food < population * 3 ? '食料の備蓄が少なくなりました。住民は採集と収穫を優先します。' : '穏やかな一日。住民たちは仕事を分担して、村の暮らしを続けています。');
    }
  }
  private harvestYield() { return this.state.huts.some(h => h.kind === 'warehouse' && h.status === 'complete') ? 32 : 24; }
  acceptInstruction(id: string, text: string, interpretation: Interpretation): InstructionRecord {
    const existing = this.state.instructions.find(r => r.id === id);
    if (existing) { if (existing.text !== text) throw new Error('この指示IDは使用済みです。'); return existing; }
    const commands = interpretationSchema.parse({ commands: interpretation.commands, message: '' }).commands;
    if (!commands.length) throw new Error('実行するコマンドがありません。');
    if (this.state.instructions.length >= 20 && this.state.instructions.every(r => r.jobs.some(j => j.status === 'running'))) throw new Error('指示の上限に達しました。実行中の仕事が完了するのを待ってください。');
    if (this.terrainDirty) this.revalidate();
    const additions: Hut[] = [];
    const jobs = commands.map(command => {
      const hutIds: string[] = [];
      if (command.action === 'build') {
        if (this.state.huts.length + additions.length + command.count > MAX_BUILDINGS) throw new Error(`建物は世界全体で${MAX_BUILDINGS}棟までです。`);
        if (command.building === 'hut' && this.state.huts.filter(h => h.kind === 'hut').length + additions.filter(h => h.kind === 'hut').length + command.count > MAX_HUTS) throw new Error(`小屋は世界全体で${MAX_HUTS}軒までです。`);
        for (let i = 0; i < command.count; i++) {
          const hut = this.findHut(command.location, additions, command.building);
          if (!hut) throw new Error('指定場所に、届く道と平らな4×4の敷地が足りません。建築数を減らすか、別の場所を指定してください。');
          additions.push(hut); hutIds.push(hut.id);
        }
      } else {
        if (command.target !== 'all' && !this.state.residents.some(r => r.id === command.target)) throw new Error('指定した住民はこの村にいません。');
        if (command.action === 'farm' && ![...this.state.huts, ...additions].some(h => h.kind === 'farm')) throw new Error('農業には畑が必要です。先に「畑を1面作って」と指示してください。');
      }
      return { command, hutIds, until: this.state.elapsed + (command.action === 'rest' ? 60 : command.action === 'gather' || command.action === 'farm' ? 240 : 0), status: command.action === 'auto' ? 'complete' as const : 'running' as const, detail: describeCommand(command) };
    });
    // All feasibility checks precede mutations: a batch either registers in full or changes nothing.
    const record: InstructionRecord = { id, text, source: interpretation.source, notice: interpretation.notice, time: this.state.elapsed, jobs };
    this.state.huts.push(...additions);
    if (this.state.instructions.length >= 20) this.state.instructions.splice(this.state.instructions.findIndex(r => r.jobs.every(j => j.status !== 'running')), 1);
    this.state.instructions.push(record);
    jobs.forEach((job, i) => {
      if (job.command.action === 'build') return;
      const command = job.command;
      for (const r of this.state.residents.filter(r => command.target === 'all' || r.id === command.target)) {
        r.order = command.action === 'auto' ? null : { requestId: `${id}:${i}`, kind: command.action === 'rest' ? 'rest' : command.action === 'farm' ? 'farm' : command.resource, until: job.until };
        this.finish(r); r.decisionIn = 0; r.reason = `プレイヤーからの指示：${describeCommand(command)}。`; this.remember(r, r.reason);
      }
    });
    this.event(`指示を受け付けました：${jobs.map(j => describeCommand(j.command)).join(' ／ ')}。`);
    this.refreshInstructions();
    return record;
  }
  private refreshInstructions() {
    for (const r of this.state.residents) if (r.order && r.order.until <= this.state.elapsed) { r.order = null; this.finish(r); this.economicChange = true; }
    for (const record of this.state.instructions) record.jobs.forEach((job, i) => {
      if (job.status !== 'running') return;
      const before = `${job.status}:${job.detail}`;
      if (job.command.action === 'build') {
        const huts = this.state.huts.filter(h => job.hutIds.includes(h.id));
        const done = huts.filter(h => h.status === 'complete').length;
        const active = huts.find(h => h.status !== 'complete');
        if (done === job.hutIds.length) { job.status = 'complete'; job.detail = `${done}棟の${BUILDING_LABELS[job.command.building]}が完成しました。`; }
        else if (active?.materialsReserved) job.detail = `${done}/${huts.length}軒完成 · ${active.name}を建築中 ${active.progress}/${active.total}`;
        else {
          const wood = Math.max(0, (active?.cost.wood ?? 0) - this.state.resources.wood), stone = Math.max(0, (active?.cost.stone ?? 0) - this.state.resources.stone);
          job.detail = `${done}/${huts.length}軒完成 · ${wood || stone ? `材料を準備中（木材${wood}・石材${stone}不足）` : '材料が揃い、着工待ち'}。住民の食事・休息後、既存の建築から順に着工します。`;
        }
      } else {
        const remaining = this.state.residents.filter(r => r.order?.requestId === `${record.id}:${i}`);
        if (!remaining.length) { job.status = this.state.elapsed >= job.until ? 'complete' : 'superseded'; job.detail = job.status === 'complete' ? '指示の時間が終了し、自律行動に戻りました。' : '新しい行動指示に切り替えました。'; }
        else job.detail = `${describeCommand(job.command)} · 残り${Math.ceil(job.until - this.state.elapsed)}分（ゲーム内）`;
      }
      if (before !== `${job.status}:${job.detail}`) this.economicChange = true;
    });
  }
  private finish(r: Resident) {
    // A new order can interrupt a step between two floor heights. Settle onto the
    // current cell before removing its route, otherwise it appears permanently unsafe.
    const floor = this.nav.height(Math.floor(r.position.x), Math.floor(r.position.z));
    if (floor >= 0 && Math.abs(floor - r.position.y) <= 1) r.position.y = floor;
    r.task = null; r.path = []; r.work = 0; r.action = 'idle'; r.decisionIn = 0.5;
  }
  private go(r: Resident, kind: NonNullable<Resident['task']>['kind'], destination: Position, targetId: string | null, reason: string, path?: Position[]) {
    const route = path ?? this.nav.path(r.position, destination); if (!route) return false;
    r.task = { kind, destination, targetId }; r.path = route; r.work = 0;
    r.action = route.length ? 'moving' : kind === 'gather' ? 'gathering' : kind === 'build' ? 'building' : kind === 'farm' ? 'farming' : kind === 'deliver' ? 'delivering' : 'socializing';
    r.reason = reason; return true;
  }
  private choose(r: Resident, time: number) {
    if (carried(r) > 0) {
      if (this.go(r, 'deliver', this.state.camp, null, '集めた資源を拠点に運び、みんなの材料にする。')) return;
      r.action = 'resting'; r.reason = '拠点への道が塞がっているので、運んだ資源を持って安全に待つ。'; r.work = 0; return;
    }
    if (r.hunger >= 55 && this.state.resources.food > 0) {
      if (distance(r.position, this.state.camp) > 1) { this.go(r, 'deliver', this.state.camp, null, 'お腹が空いたので、拠点で食事をする。'); return; }
      r.action = 'eating'; r.reason = 'お腹が空いたので、共有の食料を食べて元気を取り戻す。'; r.work = 0; return;
    }
    const night = time % 1440 >= 1200 || time % 1440 < 360;
    if (r.order?.kind === 'rest') { r.action = 'resting'; r.reason = 'プレイヤーの休息指示で、1時間ゆっくり体を休める。空腹時は食事を先に済ませる。'; r.work = 0; return; }
    if (r.energy < 22 || (night && r.energy < 75)) {
      const home = this.state.huts.find(h => h.id === r.home && h.status === 'complete');
      const bed = home ? this.nav.position(home.x + 1, home.z + 2) : null;
      if (bed && distance(r.position, bed) > 0.5 && this.go(r, 'rest', bed, home!.id, '疲れたので、自分の小屋に戻って休む。')) return;
      r.action = 'resting'; r.reason = r.home ? '自分の寝床があるので、安心して休息する。' : '疲れがたまったので、ここでひと休みする。'; r.work = 0; return;
    }
    const hut = this.state.huts.find(h => h.status !== 'complete');
    if (!r.order && hut && (!hut.builder || hut.builder === r.id) && (r.job === '建築家' || !this.state.residents.some(other => other.job === '建築家' && other.energy > 20))) {
      if (!hut.materialsReserved && this.state.resources.wood >= hut.cost.wood && this.state.resources.stone >= hut.cost.stone) {
        this.state.resources.wood -= hut.cost.wood; this.state.resources.stone -= hut.cost.stone;
        hut.materialsReserved = true; hut.status = 'building'; hut.builder = r.id;
        this.event(`${r.name}が${hut.name}の建築を始めました。材料を取り置きしました。`);
      }
      if (hut.materialsReserved) {
        const stand = this.nav.position(hut.x + 2, hut.z + 4);
        const requested = this.state.instructions.some(record => record.jobs.some(job => job.hutIds.includes(hut.id)));
        if (stand && this.go(r, 'build', stand, hut.id, requested ? `プレイヤーからの建築指示。材料が揃ったので${hut.name}を建てる。` : `${hut.kind === 'farm' ? '安定した食料を育てたい。' : hut.kind === 'warehouse' ? '収穫と備蓄を増やしたい。' : 'みんなと新しい住民の寝床が必要。'}材料が揃ったので${hut.name}を建てる。`)) return;
      }
    }
    const search = this.nav.search(r.position);
    const population = this.state.residents.length;
    if (r.order?.kind === 'farm' || (!r.order && (r.job === '農家' || this.state.resources.food < population * 3))) {
      const farms = this.state.huts.filter(h => h.kind === 'farm' && h.status === 'complete' && h.crop?.stage !== 'growing')
        .sort((a, b) => Number(b.crop?.stage === 'ripe') - Number(a.crop?.stage === 'ripe') || distance(a, r.position) - distance(b, r.position));
      for (const farm of farms) {
        if (farm.crop?.stage === 'fallow' && this.state.civilization.harvests > 0 && this.state.resources.food >= population * 12 && r.order?.kind !== 'farm') continue;
        if (this.state.residents.some(other => other.id !== r.id && other.task?.kind === 'farm' && other.task.targetId === farm.id)) continue;
        const stand = this.nav.position(farm.x + 1, farm.z + 4);
        if (stand && this.go(r, 'farm', stand, farm.id, farm.crop?.stage === 'ripe' ? '作物が実ったので収穫して拠点へ運ぶ。' : '畑に種をまき、村の食料を育てる。')) return;
      }
    }
    const needWood = !!hut && !hut.materialsReserved && this.state.resources.wood < hut.cost.wood;
    const needStone = !!hut && !hut.materialsReserved && this.state.resources.stone < hut.cost.stone;
    const priorities: Record<Resource, number> = {
      food: (this.state.resources.food < population * 2 ? 95 : this.state.resources.food < population * 5 ? 50 : 0) + (r.hunger > 60 ? 50 : 0),
      wood: needWood ? 70 : this.state.resources.wood < (this.state.huts.some(h => h.kind === 'warehouse' && h.status === 'complete') ? 80 : 24) ? 20 : 0,
      stone: needStone ? 70 : this.state.resources.stone < (this.state.huts.some(h => h.kind === 'warehouse' && h.status === 'complete') ? 40 : 8) ? 20 : 0
    };
    if (r.order) { priorities.food = r.hunger > 70 ? 160 : r.order.kind === 'farm' && this.state.resources.food < population * 2 ? 95 : 0; priorities.wood = 0; priorities.stone = 0; if (r.order.kind !== 'farm') priorities[r.order.kind] += 140; }
    if (r.job === '木こり' && priorities.wood > 0) priorities.wood += 30;
    if (r.job === '採掘師' && priorities.stone > 0) priorities.stone += 30;
    if (r.job === '採集家' && priorities.food > 0) priorities.food += 30;
    const choices: { score: number; node: VillageState['nodes'][number]; stand: Position; path: Position[] }[] = [];
    for (const node of this.state.nodes) {
      if (node.remaining <= 0 || priorities[node.kind] <= 0 || !this.nodeValid(node)) continue;
      const workers = this.state.residents.filter(other => other.id !== r.id && other.task?.targetId === node.id).length;
      for (const stand of this.adjacent(node.position)) {
        const path = this.nav.pathFrom(search, stand); if (!path) continue;
        choices.push({ node, stand, path, score: priorities[node.kind] - path.length * 0.55 - workers * 15 });
      }
    }
    choices.sort((a, b) => b.score - a.score);
    const choice = choices[0];
    if (choice) {
      const reason = r.order?.kind === choice.node.kind ? `プレイヤーの指示で、${RESOURCE_LABELS[choice.node.kind]}の採集を優先する。集めた資源は拠点へ運ぶ。` : choice.node.kind === 'food' ? '食料の備蓄を増やして、仲間が空腹にならないようにする。' :
        choice.node.kind === 'wood' ? (needWood ? `${hut!.name}を建てる木材が足りないので、森で集める。` : '次の暮らしに備えて、木材を補充する。') :
          (needStone ? `${hut!.name}の土台に使う石材が足りないので、採掘する。` : '修繕に備えて、石材を補充する。');
      this.go(r, 'gather', choice.stand, choice.node.id, reason, choice.path); return;
    }
    if (r.hunger >= 75) { r.action = 'resting'; r.reason = '食料に届く道がない。体力を温存しながら待つ。'; r.work = 0; return; }
    if (r.order) { r.action = 'resting'; r.reason = r.order.kind === 'farm' ? '畑の完成や作物の成長を待つ。食料不足なら採集も手伝う。' : '指示された資源が枯渇しているか、道が塞がっている。再生や地形の変化を待つ。'; r.work = 0; return; }
    const id = search.queue[(Math.floor(this.state.elapsed / 8) + this.state.residents.indexOf(r) * 13) % Math.max(1, search.queue.length)];
    const p = id === undefined ? null : this.nav.position(id % SIZE, Math.floor(id / SIZE));
    if (p && distance(p, r.position) < 20 && !this.isReserved(Math.floor(p.x), Math.floor(p.z))) {
      this.go(r, 'wander', p, null, hut ? '届く資源や安全な建築場所を探して、周囲を見回る。' : '小屋も備蓄も揃ったので、島を歩いて仲間と交流する。');
    } else { r.action = 'resting'; r.reason = 'いま届く仕事がないので、休みながら周囲の変化を待つ。'; r.work = 0; }
  }
  private nodeValid(node: VillageState['nodes'][number]) {
    const { x, y, z } = node.position;
    return node.kind === 'wood' ? getBlock(this.data, Math.floor(x), y, Math.floor(z)) === Block.Wood : this.nav.height(Math.floor(x), Math.floor(z)) === y;
  }
  private revalidate() {
    this.nav.rebuild();
    const camp = this.nav.nearest(this.state.camp); if (camp) this.state.camp = camp;
    for (const r of this.state.residents) {
      const y = this.nav.height(Math.floor(r.position.x), Math.floor(r.position.z));
      if (y >= 0 && Math.abs(y - r.position.y) <= 1) { if (!r.path.length) r.position.y = y; }
      else if (y < 0 || !this.nav.valid({ ...r.position, y: Math.round(r.position.y) })) {
        const safe = this.nav.nearest(r.position);
        if (safe) r.position = safe;
        this.finish(r); r.reason = safe ? '地形が変わったので、近くの安全な足場へ避難した。' : '安全な足場がないため、行動を停止している。';
      }
      if (r.task && (!this.nav.valid(r.task.destination) || r.path.some(p => !this.nav.valid(p)))) this.finish(r);
    }
    this.terrainDirty = false;
  }
  step(minutes: number, time: number): Edit[] {
    this.economicChange = false;
    const edits: Edit[] = [];
    const steps = Math.round(minutes / 0.25);
    for (let i = 0; i < steps; i++) this.fixedStep(0.25, time + i * 0.25, edits);
    if (this.terrainDirty) this.revalidate();
    return edits;
  }
  private fixedStep(dt: number, time: number, edits: Edit[]) {
    if (this.terrainDirty) this.revalidate();
    this.state.elapsed += dt; this.state.nextPlan -= dt;
    this.refreshInstructions();
    if (this.state.nextPlan <= 0) { this.develop(); this.planDevelopment(); this.state.nextPlan = 20; }
    for (const farm of this.state.huts) if (farm.status === 'complete' && farm.crop?.stage === 'growing') {
      farm.crop.growth = Math.min(1, farm.crop.growth + dt / 180);
      if (farm.crop.growth === 1) { farm.crop.stage = 'ripe'; farm.crop.remaining = this.harvestYield(); this.event(`${farm.name}の作物が実りました。収穫を待っています。`, 'harvest'); }
    }
    for (const node of this.state.nodes) {
      node.regeneration += dt;
      if (node.regeneration >= 480) { node.remaining = Math.min(node.capacity, node.remaining + Math.ceil(node.capacity / 2)); node.regeneration = 0; this.economicChange = true; }
    }
    for (const r of this.state.residents) {
      if (!this.nav.valid({ ...r.position, y: Math.round(r.position.y) }) && !r.path.length) {
        r.action = 'idle'; r.reason = '安全な足場がないため、地形が戻るのを待っている。'; continue;
      }
      r.hunger = Math.min(100, r.hunger + dt * 0.05);
      r.energy = Math.max(0, r.energy - dt * (r.action === 'resting' ? 0 : 0.08));
      if (r.hunger > 95) r.health = Math.max(10, r.health - dt * 0.05);
      else if (r.hunger < 40) r.health = Math.min(100, r.health + dt * 0.08);
      if (r.path.length) {
        const next = r.path[0];
        if (!this.nav.valid(next)) { this.finish(r); continue; }
        const remaining = distance(r.position, next), movement = dt * 1.4;
        if (remaining <= movement) { r.position = { ...next }; r.path.shift(); }
        else { const ratio = movement / remaining; r.position.y = Math.max(this.nav.height(Math.floor(r.position.x), Math.floor(r.position.z)), next.y); r.position.x += (next.x - r.position.x) * ratio; r.position.z += (next.z - r.position.z) * ratio; }
        r.action = 'moving'; continue;
      }
      if (r.task) {
        r.work += dt;
        if (r.task.kind === 'gather') {
          const node = this.state.nodes.find(n => n.id === r.task!.targetId);
          if (!node || !this.nodeValid(node) || node.remaining <= 0 || distance(r.position, node.position) > 1.1) { this.finish(r); continue; }
          r.action = 'gathering';
          if (r.work >= (node.kind === 'stone' ? 5 : 4)) {
            const amount = Math.min(node.remaining, node.kind === 'stone' ? 3 : 4, capacity - carried(r));
            node.remaining -= amount; r.inventory[node.kind] += amount; r.work = 0; this.economicChange = true;
            this.remember(r, `${RESOURCE_LABELS[node.kind]}を${amount}集めた。`);
            if (carried(r) >= capacity || node.remaining <= 0 || r.hunger >= 70 || r.energy < 18) this.finish(r);
          }
        } else if (r.task.kind === 'deliver') {
          r.action = 'delivering';
          if (r.work >= 1) {
            const count = carried(r);
            for (const kind of ['food', 'wood', 'stone'] as const) { this.state.resources[kind] += r.inventory[kind]; r.inventory[kind] = 0; }
            if (count) { this.remember(r, `集めた資源${count}個を拠点へ運んだ。`); this.event(`${r.name}が資源${count}個を拠点に届けました。`); }
            this.finish(r);
          }
        } else if (r.task.kind === 'build') {
          const hut = this.state.huts.find(h => h.id === r.task!.targetId);
          if (!hut || !hut.materialsReserved || hut.status === 'complete') { this.finish(r); continue; }
          r.action = 'building';
          if (r.work >= 0.65) {
            const blocks = buildingBlocks(hut), edit = blocks[hut.progress];
            const current = getBlock(this.data, edit.x, edit.y, edit.z);
            const oldBlock = hut.upgrading ? buildingBlocks({ ...hut, kind: 'hut' })[hut.progress].block : Block.Air;
            if (!hut.upgrading || current !== edit.block) {
              // Never change a resident's floor/body; only the original hut blocks may be replaced during an upgrade.
              const occupant = this.state.residents.find(other => Math.floor(other.position.x) === edit.x && Math.floor(other.position.z) === edit.z && edit.y >= other.position.y - 1 && edit.y < other.position.y + 2);
              if (occupant) { this.finish(occupant); this.go(occupant, 'wander', this.state.camp, null, '建築の邪魔にならないよう、敷地から離れる。'); continue; }
              if (current !== oldBlock) { r.reason = '建築予定の場所に障害物があるので、作業を待つ。'; continue; }
              this.data[index(edit.x, edit.y, edit.z)] = edit.block; edits.push(edit); this.terrainDirty = true;
            }
            hut.progress++; r.work = 0; this.economicChange = true;
            if (hut.progress === hut.total) {
              hut.status = 'complete';
              this.assignHomes();
              const effect = hut.kind === 'farm' ? '種まきから農業を始めます。' : hut.kind === 'warehouse' ? '収穫量が24から32に増え、木材80・石材40を目安に備蓄します。' : `${hut.kind === 'house' ? 4 : 2}人分の寝床ができました。`;
              this.remember(r, `${hut.name}を完成させた。`); this.event(`${hut.name}が完成！ ${effect}`, 'growth'); this.finish(r); this.state.nextPlan = 0;
            }
          }
        } else if (r.task.kind === 'farm') {
          const farm = this.state.huts.find(h => h.id === r.task!.targetId && h.status === 'complete');
          if (!farm?.crop || farm.crop.stage === 'growing') { this.finish(r); continue; }
          r.action = 'farming';
          if (r.work >= (r.job === '農家' ? 6 : 10)) {
            const crop = farm.crop;
            if (crop.stage === 'fallow') {
              crop.stage = 'growing'; crop.growth = 0; this.remember(r, `${farm.name}に種をまいた。約3時間で実る。`); this.event(`${r.name}が${farm.name}に種をまきました。`, 'harvest'); this.finish(r);
            } else {
              const amount = Math.min(crop.remaining, capacity - carried(r));
              crop.remaining -= amount; r.inventory.food += amount; this.remember(r, `${farm.name}から食料${amount}を収穫した。`);
              if (crop.remaining === 0) { crop.stage = 'fallow'; crop.growth = 0; crop.harvests++; this.state.civilization.harvests++; this.event(`${farm.name}の収穫が完了！ 次の種まきを始められます。`, 'harvest'); this.state.nextPlan = 0; }
              this.finish(r);
            }
            this.economicChange = true;
          }
        } else if (r.task.kind === 'rest') {
          r.task = null; r.action = 'resting'; r.work = 0; r.reason = '自分の小屋に戻ったので、安心して休息する。';
        } else { r.action = 'socializing'; if (r.work >= 4) {
          const other = this.state.residents.find(other => other.id !== r.id && distance(other.position, r.position) < 4);
          if (other) { r.relationships[other.id] = Math.min(100, (r.relationships[other.id] ?? 50) + 2); this.remember(r, `${other.name}と島での暮らしについて話した。`); }
          this.finish(r);
        } }
      } else if (r.action === 'eating') {
        r.work += dt;
        if (r.work >= 2) { if (this.state.resources.food > 0) { this.state.resources.food--; r.hunger = Math.max(0, r.hunger - 45); this.economicChange = true; } this.finish(r); }
      } else if (r.action === 'resting') {
        r.work += dt; r.energy = Math.min(100, r.energy + dt * (r.home ? 1.6 : 0.8));
        if ((r.order?.kind !== 'rest' && r.energy >= 85 && r.work >= 4) || r.work >= 100 || (r.hunger >= 60 && this.state.resources.food > 0)) this.finish(r);
      } else {
        r.decisionIn -= dt;
        if (r.decisionIn <= 0) this.choose(r, time);
      }
    }
  }
}
