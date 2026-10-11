import { Block, HEIGHT, SIZE, getBlock, index, type Edit } from '../../../shared/world';
import type { Hut, Position, Resident, Resource, Resources, VillageState } from '../../../shared/village';
import { RESOURCE_LABELS } from '../../../shared/village';
import { Navigation } from '../agents/navigation';
import { HUT_COST, hutBlocks, siteClear } from '../buildings/hut';
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
    this.state = { version: 1, residents: profiles.map((p, i) => ({
      id: p[0], name: p[1], age: p[2], personality: p[3], job: p[4], color: p[5],
      health: 100, energy: 90 - i * 3, hunger: 12 + i * 3, inventory: empty(), position: spawn[i],
      action: 'idle', reason: 'この島に、みんなで暮らせる村をつくりたい。', goal: '5人全員が安心して眠れる小屋をつくる',
      relationships: Object.fromEntries(profiles.filter(other => other[0] !== p[0]).map(other => [other[0], 50])),
      memories: ['仲間5人と、はじまりの島で暮らし始めた。'], memorySummary: '',
      task: null, path: [], work: 0, decisionIn: i * 0.5, home: null
    })), resources: { food: 12, wood: 0, stone: 0 }, nodes: [], huts: [], camp,
      events: [{ id: 1, time: 0, text: '5人の住民が島に到着しました。まずは小屋の材料を集めます。' }], nextEvent: 2, elapsed: 0, nextPlan: 0 };
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
  private event(text: string) {
    this.state.events.push({ id: this.state.nextEvent++, time: this.state.elapsed, text });
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
    if (this.state.huts.length >= 3 || this.state.huts.some(h => h.status !== 'complete')) return;
    const search = this.nav.search(this.state.camp);
    const preferred = [{ x: 29, z: 35 }, { x: 35, z: 35 }, { x: 29, z: 41 }];
    const score = (p: { x: number; z: number }) => {
      const priority = preferred.findIndex(site => site.x === p.x && site.z === p.z);
      return priority >= 0 ? priority : 10 + Math.hypot(p.x - 33, p.z - 39);
    };
    const sites = search.queue.map(id => ({ x: id % SIZE, z: Math.floor(id / SIZE) })).sort((a, b) => score(a) - score(b));
    for (const { x, z } of sites) {
      const y = this.nav.height(x, z);
      if (y < 1 || !siteClear(this.data, x, y, z)) continue;
      if (this.state.huts.some(h => x < h.x + 5 && x + 5 > h.x && z < h.z + 5 && z + 5 > h.z)) continue;
      if (this.state.camp.x >= x - 1 && this.state.camp.x < x + 5 && this.state.camp.z >= z - 1 && this.state.camp.z < z + 5) continue;
      if (this.state.nodes.some(n => n.position.x >= x && n.position.x < x + 4 && n.position.z >= z && n.position.z < z + 4)) continue;
      const stand = this.nav.position(x + 1, z + 4);
      if (!stand || stand.y !== y || this.nav.pathFrom(search, stand) === null) continue;
      const hut: Hut = { id: `hut-${this.state.huts.length + 1}`, name: `小屋 ${this.state.huts.length + 1}`, x, y, z,
        status: 'planned', progress: 0, total: 0, cost: { ...HUT_COST }, builder: null, materialsReserved: false };
      hut.total = hutBlocks(hut).length; this.state.huts.push(hut);
      this.event(`${hut.name}の敷地を確保しました。木材24・石材8を集めます。`); return;
    }
  }
  private finish(r: Resident) { r.task = null; r.path = []; r.work = 0; r.action = 'idle'; r.decisionIn = 0.5; }
  private go(r: Resident, kind: NonNullable<Resident['task']>['kind'], destination: Position, targetId: string | null, reason: string, path?: Position[]) {
    const route = path ?? this.nav.path(r.position, destination); if (!route) return false;
    r.task = { kind, destination, targetId }; r.path = route; r.work = 0;
    r.action = route.length ? 'moving' : kind === 'gather' ? 'gathering' : kind === 'build' ? 'building' : kind === 'deliver' ? 'delivering' : 'socializing';
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
    if (r.energy < 22 || (night && r.energy < 75)) {
      const home = this.state.huts.find(h => h.id === r.home && h.status === 'complete');
      const bed = home ? this.nav.position(home.x + 1, home.z + 2) : null;
      if (bed && distance(r.position, bed) > 0.5 && this.go(r, 'rest', bed, home!.id, '疲れたので、自分の小屋に戻って休む。')) return;
      r.action = 'resting'; r.reason = r.home ? '完成した小屋があるので、安心して休息する。' : '疲れがたまったので、ここでひと休みする。'; r.work = 0; return;
    }
    const hut = this.state.huts.find(h => h.status !== 'complete');
    if (hut && (!hut.builder || hut.builder === r.id) && (r.job === '建築家' || !this.state.residents.some(other => other.job === '建築家' && other.energy > 20))) {
      if (!hut.materialsReserved && this.state.resources.wood >= hut.cost.wood && this.state.resources.stone >= hut.cost.stone) {
        this.state.resources.wood -= hut.cost.wood; this.state.resources.stone -= hut.cost.stone;
        hut.materialsReserved = true; hut.status = 'building'; hut.builder = r.id;
        this.event(`${r.name}が${hut.name}の建築を始めました。材料を取り置きしました。`);
      }
      if (hut.materialsReserved) {
        const stand = this.nav.position(hut.x + 1, hut.z + 4);
        if (stand && this.go(r, 'build', stand, hut.id, 'みんなの寝床が足りない。材料が揃ったので小屋を建てる。')) return;
      }
    }
    const search = this.nav.search(r.position);
    const needWood = !!hut && !hut.materialsReserved && this.state.resources.wood < hut.cost.wood;
    const needStone = !!hut && !hut.materialsReserved && this.state.resources.stone < hut.cost.stone;
    const priorities: Record<Resource, number> = {
      food: (this.state.resources.food < 8 ? 95 : this.state.resources.food < 20 ? 50 : 0) + (r.hunger > 60 ? 50 : 0),
      wood: needWood ? 70 : this.state.resources.wood < 24 ? 20 : 0,
      stone: needStone ? 70 : this.state.resources.stone < 8 ? 20 : 0
    };
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
      const reason = choice.node.kind === 'food' ? '食料の備蓄を増やして、仲間が空腹にならないようにする。' :
        choice.node.kind === 'wood' ? (needWood ? '小屋を建てる木材が足りないので、森で集める。' : '次の暮らしに備えて、木材を補充する。') :
          (needStone ? '小屋の土台に使う石材が足りないので、採掘する。' : '修繕に備えて、石材を補充する。');
      this.go(r, 'gather', choice.stand, choice.node.id, reason, choice.path); return;
    }
    if (r.hunger >= 75) { r.action = 'resting'; r.reason = '食料に届く道がない。体力を温存しながら待つ。'; r.work = 0; return; }
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
      if (y >= 0 && Math.abs(y - r.position.y) <= 1) r.position.y = y;
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
    if (this.state.nextPlan <= 0) { this.planHut(); this.state.nextPlan = 20; }
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
            const blocks = hutBlocks(hut), edit = blocks[hut.progress];
            // Never place a block through a resident. Clearing the site is part of construction.
            const occupant = this.state.residents.find(other => Math.floor(other.position.x) === edit.x && Math.floor(other.position.z) === edit.z && edit.y >= other.position.y - 1 && edit.y < other.position.y + 2);
            if (occupant) { this.finish(occupant); this.go(occupant, 'wander', this.state.camp, null, '建築の邪魔にならないよう、敷地から離れる。'); continue; }
            if (getBlock(this.data, edit.x, edit.y, edit.z) !== Block.Air) { r.reason = '建築予定の場所に障害物があるので、作業を待つ。'; continue; }
            this.data[index(edit.x, edit.y, edit.z)] = edit.block; edits.push(edit); hut.progress++; r.work = 0; this.terrainDirty = true; this.economicChange = true;
            if (hut.progress === hut.total) {
              hut.status = 'complete';
              for (const resident of this.state.residents.filter(other => !other.home).slice(0, 2)) { resident.home = hut.id; this.remember(resident, `${hut.name}に自分の寝床ができた。`); }
              this.remember(r, `${hut.name}を完成させた。`); this.event(`${hut.name}が完成！ 2人分の寝床ができました。`); this.finish(r); this.state.nextPlan = 0;
            }
          }
        } else if (r.task.kind === 'rest') {
          r.task = null; r.action = 'resting'; r.work = 0; r.reason = '自分の小屋に戻ったので、安心して休息する。';
        } else { r.action = 'socializing'; if (r.work >= 4) {
          const other = this.state.residents.find(other => other.id !== r.id && distance(other.position, r.position) < 4);
          if (other) { r.relationships[other.id] = Math.min(100, r.relationships[other.id] + 2); this.remember(r, `${other.name}と島での暮らしについて話した。`); }
          this.finish(r);
        } }
      } else if (r.action === 'eating') {
        r.work += dt;
        if (r.work >= 2) { if (this.state.resources.food > 0) { this.state.resources.food--; r.hunger = Math.max(0, r.hunger - 45); this.economicChange = true; } this.finish(r); }
      } else if (r.action === 'resting') {
        r.work += dt; r.energy = Math.min(100, r.energy + dt * (r.home ? 1.6 : 0.8));
        if ((r.energy >= 85 && r.work >= 4) || r.work >= 100 || (r.hunger >= 60 && this.state.resources.food > 0)) this.finish(r);
      } else {
        r.decisionIn -= dt;
        if (r.decisionIn <= 0) this.choose(r, time);
      }
    }
  }
}
