import type { UtilityAction, UtilityScore } from '../../../shared/autonomy';
import type { Resident } from '../../../shared/village';
export interface UtilityContext {
  resident: Resident; population: number; food: number; wood: number; stone: number; woodNeeded: number; stoneNeeded: number;
  housingShortage: number; distance: number; priority: number; night: boolean; continuing: boolean; ripe: boolean;
}
const rounded = (value: number) => Math.round(value * 10) / 10 || 0;
const factor = (label: string, value: number) => ({ label, value: rounded(value) });
function common(action: UtilityAction, c: UtilityContext) {
  const r = c.resident;
  const job: Record<string, UtilityAction> = { 建築家: 'build', 木こり: 'wood', 採掘師: 'stone', 採集家: 'food', 農家: 'farm' };
  return [factor('職業', job[r.job] === action ? 12 : 0), factor('得意な仕事', r.traits.specialty === action ? 24 : 0), factor('勤勉さ', ['food', 'wood', 'stone', 'build', 'farm'].includes(action) ? r.traits.diligence * 10 : 0),
    factor('道の距離', -Math.min(45, c.distance * (0.35 + r.traits.caution * .3))), factor('疲労と慎重さ', action === 'rest' ? 0 : -Math.max(0, 45 - r.energy) * (1 + r.traits.caution)), factor('継続中の仕事', c.continuing ? 16 : 0)];
}
export function scoreFood(c: UtilityContext) { return [factor('食料備蓄の不足', Math.max(0, 1 - c.food / Math.max(1, c.population * 5)) * 100), factor('空腹', c.resident.hunger * .65), ...common('food', c)]; }
export function scoreWood(c: UtilityContext) { return [factor('建設に必要な木材', c.woodNeeded > c.wood ? 78 : 0), factor('木材の備蓄', Math.max(0, 1 - c.wood / 80) * 22), ...common('wood', c)]; }
export function scoreStone(c: UtilityContext) { return [factor('建設に必要な石材', c.stoneNeeded > c.stone ? 78 : 0), factor('石材の備蓄', Math.max(0, 1 - c.stone / 40) * 22), ...common('stone', c)]; }
export function scoreBuild(c: UtilityContext) { return [factor('村の建設課題', c.priority), factor('住宅の不足', c.housingShortage * 4), factor('食料不足時は調達を優先', c.food < c.population * 2 ? -35 : 0), ...common('build', c)]; }
export function scoreFarm(c: UtilityContext) { return [factor('食料備蓄の不足', Math.max(0, 1 - c.food / Math.max(1, c.population * 6)) * 105), factor('収穫できる作物', c.ripe ? 25 : 5), factor('初めての農業・種まき', c.priority), ...common('farm', c)]; }
export function scoreRest(c: UtilityContext) { return [factor('疲労', c.resident.energy < 22 ? 240 : Math.max(0, 85 - c.resident.energy) * .8), factor('夜間の休息', c.night && c.resident.energy < 75 ? 110 : 0), factor('慎重さ', c.resident.traits.caution * 10), ...common('rest', c)]; }
export function scoreSocial(c: UtilityContext) { return [factor('仲間と交流する時間', 12), factor('社交性', c.resident.traits.sociability * 22), factor('空腹時は仕事を優先', -c.resident.hunger * .35), ...common('social', c)]; }
export function scoreExplore(c: UtilityContext) { return [factor('周辺を調べる', 10), factor('好奇心', c.resident.traits.curiosity * 25), factor('空腹時は仕事を優先', -c.resident.hunger * .4), ...common('explore', c)]; }
const scorers = { food: scoreFood, wood: scoreWood, stone: scoreStone, build: scoreBuild, farm: scoreFarm, rest: scoreRest, social: scoreSocial, explore: scoreExplore };
export function evaluateUtility(action: UtilityAction, c: UtilityContext, taskId: string | null, unavailable = ''): UtilityScore {
  const factors = scorers[action](c);
  if (c.resident.order && action === c.resident.order.kind) factors.push(factor('プレイヤーの行動指示', 160));
  const score = rounded(factors.reduce((sum, f) => sum + f.value, 0));
  return { action, taskId, score, available: !unavailable, factors, reason: unavailable || factors.filter(f => f.value !== 0).map(f => `${f.label} ${f.value > 0 ? '+' : ''}${f.value}`).join(' / ') };
}
