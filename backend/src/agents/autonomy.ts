import { Block, SIZE, getBlock, type Edit } from '../../../shared/world';
import { beds, MAX_POPULATION, RESOURCE_LABELS, type Position, type Resident, type Resources, type VillageEvent, type VillageState } from '../../../shared/village';
import { UTILITY_LABELS, type UtilityAction, type UtilityScore, type VillageTask } from '../../../shared/autonomy';
import { evaluateUtility, type UtilityContext } from './utility';
import type { Navigation } from './navigation';
import { ISLANDS, NEW_CONTINENT, planBridge } from '../buildings/bridge';
const empty = (): Resources => ({ food: 0, wood: 0, stone: 0 });
const distance = (a: Position, b: Position) => Math.hypot(a.x - b.x, a.z - b.z);
interface Hooks {
  state: VillageState; nav: Navigation; data: Uint8Array;
  go(r: Resident, kind: NonNullable<Resident['task']>['kind'], destination: Position, target: string | null, reason: string, path?: Position[]): boolean;
  finish(r: Resident): void; terrain(edit: Edit): void; nodeValid(node: VillageState['nodes'][number]): boolean;
  event(text: string, kind?: VillageEvent['kind'], links?: Partial<Pick<VillageEvent, 'residentIds' | 'buildingId' | 'taskId' | 'position'>>): void;
}
interface Choice { score: UtilityScore; task?: VillageTask; position?: Position; path?: Position[] }
export class Autonomy {
  constructor(private hooks: Hooks) {}
  private get state() { return this.hooks.state; }
  private log(r: Resident, outcome: Resident['ai']['history'][number]['outcome'], text: string) {
    r.ai.history.push({ time: this.state.elapsed, action: r.ai.chosen ?? 'rest', taskId: r.ai.taskId, text: text.slice(0, 500), outcome });
    if (r.ai.history.length > 20) r.ai.history.shift();
  }
  private create(input: Pick<VillageTask, 'id' | 'kind' | 'action' | 'title' | 'priority' | 'requiredResources' | 'location' | 'targetId' | 'total'>) {
    let task = this.state.tasks.find(t => t.id === input.id);
    if (!task) {
      task = { ...input, reservedResources: empty(), requiredPeople: 1, assignees: [], status: 'queued', progress: 0, createdAt: this.state.elapsed, updatedAt: this.state.elapsed, lastProgressAt: this.state.elapsed, retryAt: 0, failure: '' };
      this.state.tasks.push(task);
      if (input.kind !== 'gather') this.hooks.event(`仕事を作成：${input.title}。必要人数1、木材${input.requiredResources.wood}・石材${input.requiredResources.stone}。`, 'task', { taskId: task.id, buildingId: task.targetId, position: task.location });
    }
    else Object.assign(task, input);
    return task;
  }
  evaluateWorld() {
    const s = this.state, population = s.residents.length;
    const issues = [];
    if (s.resources.food < population * 3) issues.push('食料不足');
    if (beds(s) < population + (population < MAX_POPULATION ? 2 : 0)) issues.push('住宅不足');
    const needed = [...s.huts.filter(h => h.status !== 'complete' && !h.materialsReserved), ...s.bridges.filter(b => b.status !== 'complete' && !b.materialsReserved)].reduce((n, b) => ({ wood: n.wood + b.cost.wood, stone: n.stone + b.cost.stone }), { wood: 0, stone: 0 });
    if (s.resources.wood < needed.wood) issues.push('木材不足');
    if (s.resources.stone < needed.stone) issues.push('石材不足');
    const reachable = this.hooks.nav.search(s.camp);
    const disconnected = [...ISLANDS, NEW_CONTINENT].filter(i => { const p = this.hooks.nav.position(i.x, i.z); return p && reachable.parents[Math.floor(p.x) + SIZE * Math.floor(p.z)] < 0; });
    if (disconnected.length) issues.push('島への道がない');
    for (const issue of issues.filter(i => !s.issues.includes(i))) this.hooks.event(`村の課題を検知：${issue}。住民が必要な仕事を選びます。`, 'task', { position: s.camp });
    s.issues = issues;
    if (s.nextBridgePlan <= s.elapsed && !s.bridges.some(b => b.status !== 'complete')) {
      s.nextBridgePlan = s.elapsed + 60;
      for (const island of disconnected) {
        if (s.bridges.some(b => b.id === `bridge-${island.id}`)) continue;
        const bridge = planBridge(this.hooks.data, this.hooks.nav, s.camp, island);
        if (bridge) { s.bridges.push(bridge); this.hooks.event(`${island.name}に移動できないため、岸から歩ける橋を計画しました。木材${bridge.cost.wood}を準備します。`, 'construction', { buildingId: bridge.id, position: bridge.destination }); break; }
      }
    }
    for (const hut of s.huts) {
      const kind = hut.status === 'complete' ? 'farm' : 'build';
      if (kind === 'farm' && hut.kind !== 'farm') continue;
      const location = this.hooks.nav.position(hut.x + (kind === 'farm' ? 1 : 2), hut.z + 4) ?? { x: hut.x + 2.5, y: hut.y, z: hut.z + 4.5 };
      const task = this.create({ id: `${kind}:${hut.id}`, kind, action: kind, title: kind === 'farm' ? `${hut.name}の種まき・収穫` : `${hut.name}の${hut.upgrading ? '改築' : '建築'}`, priority: kind === 'farm' ? s.civilization.harvests === 0 ? 30 : 0 : hut.kind === 'farm' ? 92 : hut.kind === 'warehouse' ? 72 : 88,
        requiredResources: kind === 'farm' ? empty() : { ...hut.cost }, location, targetId: hut.id, total: kind === 'farm' ? this.harvestTotal(hut) : hut.total });
      task.location = location; task.reservedResources = hut.materialsReserved && kind === 'build' ? { ...hut.cost } : empty();
      if (kind === 'build' && task.status === 'complete' && hut.status !== 'complete') task.status = 'queued';
      const progress = kind === 'build' ? hut.progress : hut.crop?.stage === 'growing' ? hut.crop.growth * task.total : hut.crop?.stage === 'ripe' ? task.total - hut.crop.remaining : 0;
      this.progress(task, progress);
      if (kind === 'build' && hut.status === 'complete') task.status = 'complete';
      if (kind === 'farm' && !task.assignees.length && task.retryAt <= s.elapsed) task.status = hut.crop?.stage === 'growing' ? 'blocked' : 'queued';
    }
    for (const bridge of s.bridges) {
      const edit = bridge.blocks[Math.min(bridge.progress, bridge.blocks.length - 1)];
      const task = this.create({ id: `bridge:${bridge.id}`, kind: 'bridge', action: 'build', title: bridge.name, priority: 38, requiredResources: { ...bridge.cost }, location: { x: edit.x + .5, y: edit.y + 1, z: edit.z + .5 }, targetId: bridge.id, total: bridge.blocks.length });
      task.reservedResources = bridge.materialsReserved ? { ...bridge.cost } : empty(); this.progress(task, bridge.progress);
      if (bridge.status === 'complete') task.status = 'complete';
    }
    for (const node of s.nodes) this.create({ id: `gather:${node.id}`, kind: 'gather', action: node.kind, title: `${RESOURCE_LABELS[node.kind]}の採集`, priority: node.kind === 'food' ? s.resources.food < population * 3 ? 90 : 25 : s.resources[node.kind] < needed[node.kind] ? 78 : 20, requiredResources: empty(), location: { ...node.position }, targetId: node.id, total: 8 });
    for (const task of s.tasks) if (!task.assignees.length && task.status !== 'complete' && task.retryAt <= s.elapsed) {
      task.status = task.kind === 'farm' && s.huts.find(h => h.id === task.targetId)?.crop?.stage === 'growing' ? 'blocked' : 'queued'; task.failure = '';
    }
    for (const r of s.residents) if (!r.ai.taskId && r.task && ['gather', 'build', 'bridge', 'farm'].includes(r.task.kind)) {
      const task = s.tasks.find(t => t.kind === r.task!.kind && t.targetId === r.task!.targetId);
      if (task && !task.assignees.length) { r.ai.taskId = task.id; r.ai.chosen = task.action; task.assignees = [r.id]; task.status = 'running'; task.lastProgressAt = s.elapsed; }
    }
    // Completed construction records remain linked from history; gather tasks reuse their IDs.
  }
  private harvestTotal(h: VillageState['huts'][number]) { return this.state.huts.some(b => b.kind === 'warehouse' && b.status === 'complete') ? 32 : 24; }
  progress(task: VillageTask, value: number) { if (value !== task.progress) { task.progress = value; task.lastProgressAt = this.state.elapsed; task.updatedAt = this.state.elapsed; } }
  private stand(r: Resident, p: Position, search: ReturnType<Navigation['search']>) {
    let best: { position: Position; path: Position[] } | undefined;
    for (const [dx, dz] of [[1, 0], [0, 1], [-1, 0], [0, -1]]) {
      const position = this.hooks.nav.position(Math.floor(p.x) + dx, Math.floor(p.z) + dz);
      if (!position || Math.abs(position.y - p.y) > 1) continue;
      const path = this.hooks.nav.pathFrom(search, position); if (path && (!best || path.length < best.path.length)) best = { position, path };
    }
    return best;
  }
  private unavailable(task: VillageTask, r: Resident) {
    if (task.status === 'complete' && task.kind !== 'gather' && task.kind !== 'farm') return '仕事は完成済み';
    if (task.retryAt > this.state.elapsed) return `失敗後の再評価待ち：${task.failure}`;
    if (r.ai.failures.some(f => f.taskId === task.id && f.until > this.state.elapsed)) return '同じ仕事を短時間に選び直さないため待機';
    if (task.assignees.some(id => id !== r.id) && task.assignees.length >= task.requiredPeople) return '他の住民が作業場所を予約済み';
    if (task.kind === 'build' || task.kind === 'bridge') {
      const target = task.kind === 'build' ? this.state.huts.find(h => h.id === task.targetId) : this.state.bridges.find(b => b.id === task.targetId);
      if (!target || target.status === 'complete') return '仕事は完成済み';
      if (!target.materialsReserved && Object.entries(target.cost).some(([kind, amount]) => this.state.resources[kind as keyof Resources] < amount)) return '必要資源が不足。採集を先行';
    } else if (task.kind === 'gather') {
      const node = this.state.nodes.find(n => n.id === task.targetId);
      if (!node || node.remaining <= 0 || !this.hooks.nodeValid(node)) return '資源が枯渇、または採集場所が変化';
    } else if (task.kind === 'farm') {
      const farm = this.state.huts.find(h => h.id === task.targetId);
      if (!farm?.crop || farm.status !== 'complete' || farm.crop.stage === 'growing') return '畑の完成・作物の成長待ち';
    }
    return '';
  }
  private context(r: Resident, time: number): UtilityContext {
    const costs = [...this.state.huts, ...this.state.bridges].filter(b => b.status !== 'complete' && !b.materialsReserved).reduce((n, b) => ({ wood: n.wood + b.cost.wood, stone: n.stone + b.cost.stone }), { wood: 0, stone: 0 });
    const population = this.state.residents.length;
    return { resident: r, population, food: this.state.resources.food, wood: this.state.resources.wood, stone: this.state.resources.stone, woodNeeded: costs.wood, stoneNeeded: costs.stone, housingShortage: Math.max(0, population + (population < MAX_POPULATION ? 2 : 0) - beds(this.state)), distance: 0, priority: 0, night: time % 1440 >= 1200 || time % 1440 < 360, continuing: false, ripe: false };
  }
  choose(r: Resident, time: number, review = false): boolean {
    if (!this.state.tasks.length) this.evaluateWorld();
    const c = this.context(r, time), search = this.hooks.nav.search(r.position), choices: Choice[] = [];
    for (const task of this.state.tasks) {
      if (task.status === 'complete' && task.kind !== 'gather' && task.kind !== 'farm') continue;
      let unavailable = this.unavailable(task, r), position = task.location, path: Position[] | undefined;
      if (task.kind === 'gather' || task.kind === 'bridge') {
        const bridge = this.state.bridges.find(b => b.id === task.targetId), edit = bridge?.blocks[bridge.progress];
        const point = edit ? { x: edit.x + .5, y: edit.y + 1, z: edit.z + .5 } : task.location;
        const stand = this.stand(r, point, search); if (stand) { position = stand.position; path = stand.path; }
      } else path = this.hooks.nav.pathFrom(search, position) ?? undefined;
      if (!path && !unavailable) {
        unavailable = '作業場所に到達できない';
        r.ai.failures = [...r.ai.failures.filter(f => f.taskId !== task.id), { taskId: task.id, until: this.state.elapsed + 60, reason: unavailable }].slice(-16);
        task.failure = unavailable; if (!task.assignees.length) { task.status = 'blocked'; task.retryAt = this.state.elapsed + 60; }
      }
      if (r.order && r.order.kind !== task.action && !(task.action === 'food' && r.hunger >= 70 && c.food < c.population * 2)) unavailable ||= '別のプレイヤー指示を優先中';
      if (task.kind === 'gather' && !r.order) {
        const needed = task.action === 'food' ? c.food < c.population * 5 || r.hunger > 70 : task.action === 'wood' ? c.wood < Math.max(80, c.woodNeeded) : c.stone < Math.max(40, c.stoneNeeded);
        if (!needed) unavailable ||= '備蓄は十分';
      }
      if (task.kind === 'farm' && !r.order && this.state.civilization.harvests > 0 && c.food >= c.population * 12 && this.state.huts.find(h => h.id === task.targetId)?.crop?.stage === 'fallow') unavailable ||= '食料備蓄は十分';
      const score = evaluateUtility(task.action, { ...c, priority: task.priority, distance: path?.length ?? distance(r.position, position), continuing: r.ai.taskId === task.id, ripe: this.state.huts.find(h => h.id === task.targetId)?.crop?.stage === 'ripe' }, task.id, unavailable);
      choices.push({ task, position, path, score });
    }
    const home = this.state.huts.find(h => h.id === r.home && h.status === 'complete'), bed = home ? this.hooks.nav.position(home.x + 1, home.z + 2) : null;
    const restPath = bed ? this.hooks.nav.pathFrom(search, bed) : null;
    choices.push({ score: evaluateUtility('rest', c, null), position: restPath ? bed! : r.position, path: restPath ?? [] });
    for (const action of ['social', 'explore'] as const) {
      const friend = this.state.residents.filter(o => o.id !== r.id && o.action !== 'resting').sort((a, b) => distance(a.position, r.position) - distance(b.position, r.position))[0];
      const candidates = search.queue.filter(id => { const p = this.hooks.nav.position(id % SIZE, Math.floor(id / SIZE))!; return distance(r.position, p) >= 4 && distance(r.position, p) <= (action === 'explore' ? 32 : 10) && !this.state.huts.some(h => p.x >= h.x - 1 && p.x <= h.x + 4 && p.z >= h.z - 1 && p.z <= h.z + 4); });
      const id = candidates[(Math.floor(this.state.elapsed / 30) + this.state.residents.indexOf(r) * 17) % Math.max(1, candidates.length)];
      const position = action === 'social' && friend ? this.hooks.nav.position(Math.floor(friend.position.x), Math.floor(friend.position.z)) : id === undefined ? null : this.hooks.nav.position(id % SIZE, Math.floor(id / SIZE));
      const path = position ? this.hooks.nav.pathFrom(search, position) : null;
      choices.push({ score: evaluateUtility(action, { ...c, distance: path?.length ?? 0 }, null, !path ? '安全な目的地がない' : r.order ? 'プレイヤー指示を優先中' : ''), position: position ?? undefined, path: path ?? undefined });
    }
    // UI shows the best feasible option for each action, or its actual exclusion reason.
    r.ai.scores = (Object.keys(UTILITY_LABELS) as UtilityAction[]).map(action => choices.filter(c => c.score.action === action).sort((a, b) => Number(b.score.available) - Number(a.score.available) || b.score.score - a.score.score)[0]?.score ?? evaluateUtility(action, c, null, '作業候補がない'));
    const choice = choices.filter(c => c.score.available).sort((a, b) => b.score.score - a.score.score)[0];
    if (!choice) return false;
    if (review) {
      const current = choices.find(c => c.task?.id === r.ai.taskId && c.score.available);
      // A small improvement does not interrupt productive work. Continuation is
      // scored explicitly, and a further 20-point margin avoids oscillation.
      if (current && choice.score.score <= current.score.score + 20) {
        r.reason = `${UTILITY_LABELS[current.score.action]} ${current.score.score}点：${current.score.reason}`;
        r.ai.decidedAt = this.state.elapsed; return true;
      }
      this.finish(r, 'interrupted'); this.hooks.finish(r);
    }
    r.ai.decidedAt = this.state.elapsed; r.ai.chosen = choice.score.action; r.ai.cooldownUntil = this.state.elapsed + 4;
    r.goal = choice.task?.title ?? UTILITY_LABELS[choice.score.action];
    const reason = `${UTILITY_LABELS[choice.score.action]} ${choice.score.score}点：${choice.score.reason}`;
    if (choice.task) {
      const task = choice.task;
      if (task.kind === 'build' || task.kind === 'bridge') {
        const target = task.kind === 'build' ? this.state.huts.find(h => h.id === task.targetId)! : this.state.bridges.find(b => b.id === task.targetId)!;
        if (!target.materialsReserved) {
          for (const resource of ['food', 'wood', 'stone'] as const) this.state.resources[resource] -= target.cost[resource];
          target.materialsReserved = true;
          this.hooks.event(`${r.name}が${task.title}を開始。木材${target.cost.wood}・石材${target.cost.stone}を一度だけ取り置きしました。`, 'construction', { residentIds: [r.id], buildingId: task.targetId, taskId: task.id, position: task.location });
        }
        target.builder = r.id; target.status = 'building'; task.reservedResources = { ...target.cost };
      }
      task.status = 'running'; task.failure = ''; task.retryAt = 0; task.assignees = [r.id]; task.updatedAt = task.lastProgressAt = this.state.elapsed; task.progress = task.kind === 'gather' ? 0 : task.progress;
      r.ai.taskId = task.id; this.log(r, 'selected', reason);
      this.hooks.event(`担当を決定：${r.name} → ${task.title}（${choice.score.score}点）。`, 'task', { residentIds: [r.id], taskId: task.id, buildingId: task.kind !== 'gather' ? task.targetId : undefined, position: task.location });
      if (!this.hooks.go(r, task.kind, choice.position!, task.targetId, reason, choice.path)) { this.fail(r, '選択後に道が変化した'); return false; }
    } else {
      r.ai.taskId = null; this.log(r, 'selected', reason); r.reason = reason;
      if (choice.score.action === 'rest') {
        if (choice.path?.length) this.hooks.go(r, 'rest', choice.position!, home?.id ?? null, reason, choice.path);
        else { r.action = 'resting'; r.work = 0; }
      } else this.hooks.go(r, choice.score.action === 'explore' ? 'explore' : 'wander', choice.position!, null, reason, choice.path);
    }
    return true;
  }
  finish(r: Resident, outcome: 'complete' | 'interrupted' = 'complete') {
    const task = this.state.tasks.find(t => t.id === r.ai.taskId);
    if (r.ai.chosen) this.log(r, outcome, `${r.goal}：${outcome === 'complete' ? '一区切り' : '体調・指示に合わせて切り替え'}`);
    if (task) {
      task.assignees = task.assignees.filter(id => id !== r.id); task.updatedAt = this.state.elapsed;
      const target = task.kind === 'build' ? this.state.huts.find(h => h.id === task.targetId) : task.kind === 'bridge' ? this.state.bridges.find(b => b.id === task.targetId) : undefined;
      if (target) { if (target.builder === r.id) target.builder = null; this.progress(task, target.progress); }
      if (task.status !== 'blocked') task.status = target?.status === 'complete' ? 'complete' : 'queued';
      if (outcome === 'complete' && task.kind === 'gather') r.ai.failures = [...r.ai.failures.filter(f => f.taskId !== task.id), { taskId: task.id, until: this.state.elapsed + 8, reason: '採集後の運搬を優先' }].slice(-16);
    }
    r.ai.taskId = null; r.ai.chosen = null;
  }
  fail(r: Resident, reason: string) {
    const task = this.state.tasks.find(t => t.id === r.ai.taskId);
    if (task) { task.failure = reason; task.status = 'blocked'; task.retryAt = this.state.elapsed + 60; r.ai.failures = [...r.ai.failures.filter(f => f.taskId !== task.id), { taskId: task.id, until: task.retryAt, reason }].slice(-16); }
    this.log(r, 'failed', reason); this.hooks.event(`${r.name}の仕事を切り替え：${reason}。60分後に再評価します。`, 'task', { residentIds: [r.id], taskId: task?.id, buildingId: task?.kind === 'build' || task?.kind === 'bridge' ? task.targetId : undefined, position: r.position });
    r.ai.chosen = null; r.reason = `${reason}。別の仕事を選び、60分後に再評価する。`;
    this.hooks.finish(r);
  }
  tick(time: number) {
    if (this.state.nextTaskEvaluation <= this.state.elapsed) {
      this.state.nextTaskEvaluation = this.state.elapsed + 5; this.evaluateWorld();
      for (const task of this.state.tasks) if (task.status === 'running' && this.state.elapsed - task.lastProgressAt > 120) {
        for (const id of [...task.assignees]) { const r = this.state.residents.find(r => r.id === id); if (r) this.fail(r, '120分間、作業が進まず停滞した'); }
      }
      for (const r of this.state.residents) if (r.ai.taskId && r.task && r.inventory.food + r.inventory.wood + r.inventory.stone === 0 && r.ai.cooldownUntil <= this.state.elapsed) this.choose(r, time, true);
    }
  }
  workBridge(r: Resident, edits: Edit[]) {
    const bridge = this.state.bridges.find(b => b.id === r.task?.targetId);
    if (!bridge || !bridge.materialsReserved || bridge.status === 'complete') { this.hooks.finish(r); return; }
    const edit = bridge.blocks[bridge.progress];
    const current = getBlock(this.hooks.data, edit.x, edit.y, edit.z);
    if (current !== Block.Air && current !== Block.Water && current !== edit.block) { this.fail(r, '橋の予定地に障害物がある'); return; }
    if (distance(r.position, { x: edit.x + .5, y: edit.y + 1, z: edit.z + .5 }) > 1.1) {
      const stand = this.stand(r, { x: edit.x + .5, y: edit.y + 1, z: edit.z + .5 }, this.hooks.nav.search(r.position));
      if (!stand || !this.hooks.go(r, 'bridge', stand.position, bridge.id, r.reason, stand.path)) this.fail(r, '橋の建築先に到達できない');
      return;
    }
    r.action = 'building'; if (r.work < .65) return;
    if (current !== edit.block) { this.hooks.terrain(edit); edits.push(edit); }
    bridge.progress++; r.work = 0;
    const task = this.state.tasks.find(t => t.id === r.ai.taskId); if (task) this.progress(task, bridge.progress);
    if (bridge.progress === bridge.blocks.length) {
      bridge.status = 'complete'; this.state.nextBridgePlan = 0;
      this.hooks.event(`${bridge.name}が完成！ 歩いて新しい島へ渡れます。`, 'growth', { residentIds: [r.id], buildingId: bridge.id, taskId: task?.id, position: bridge.destination }); this.hooks.finish(r);
    }
  }
}
