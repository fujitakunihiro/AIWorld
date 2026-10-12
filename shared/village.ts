import type { InstructionRecord, ResidentOrder } from './instructions';
import type { Conversation } from './conversation';
import type { Traits, ResidentAI, VillageTask, Bridge } from './autonomy';
export interface Position { x: number; y: number; z: number }
export type Resource = 'food' | 'wood' | 'stone';
export type Resources = Record<Resource, number>;
export type Action = 'idle' | 'moving' | 'gathering' | 'delivering' | 'building' | 'farming' | 'eating' | 'resting' | 'socializing' | 'exploring';
export const ACTION_LABELS: Record<Action, string> = {
  idle: '周囲を見ています', moving: '移動中', gathering: '採集中', delivering: '資源を運んでいます',
  building: '建築中', farming: '畑仕事をしています', eating: '食事中', resting: '休息中', socializing: '交流中', exploring: '探索中'
};
export const RESOURCE_LABELS: Record<Resource, string> = { food: '食料', wood: '木材', stone: '石材' };
export interface Resident {
  id: string; name: string; age: number; personality: string; job: string; color: string;
  health: number; energy: number; hunger: number; inventory: Resources; position: Position;
  action: Action; reason: string; goal: string; relationships: Record<string, number>;
  memories: string[]; memorySummary: string;
  conversations: Conversation[]; speech: { text: string; until: number } | null; nextSocialAt: number;
  traits: Traits; ai: ResidentAI;
  task: { kind: 'gather' | 'deliver' | 'build' | 'bridge' | 'farm' | 'wander' | 'explore' | 'rest'; targetId: string | null; destination: Position } | null;
  path: Position[]; work: number; decisionIn: number; home: string | null; order: ResidentOrder | null;
}
export interface ResourceNode {
  id: string; kind: Resource; position: Position; remaining: number; capacity: number; regeneration: number;
}
export interface Hut {
  id: string; name: string; kind: BuildingKind; x: number; y: number; z: number;
  status: 'planned' | 'building' | 'complete'; progress: number; total: number;
  cost: Resources; builder: string | null; materialsReserved: boolean;
  entranceStep: boolean;
  upgrading: boolean;
  crop: { stage: 'fallow' | 'growing' | 'ripe'; growth: number; harvests: number; remaining: number } | null;
}
export type BuildingKind = 'hut' | 'house' | 'farm' | 'warehouse';
export const BUILDING_LABELS: Record<BuildingKind, string> = { hut: '小屋', house: '住宅', farm: '畑', warehouse: '倉庫' };
export const MAX_POPULATION = 20;
export const MAX_BUILDINGS = 20;
export interface Civilization {
  level: 1 | 2; nextArrival: number; nextEventAt: number; eventSequence: number; arrivals: number; harvests: number;
}
export interface VillageEvent { id: number; time: number; text: string; kind: 'life' | 'harvest' | 'arrival' | 'growth' | 'weather' | 'festival' | 'trade' | 'construction' | 'conversation' | 'task'; residentIds?: string[]; buildingId?: string; taskId?: string; position?: Position }
export const EVENT_LABELS: Record<VillageEvent['kind'], string> = { life: '暮らし', harvest: '農業', arrival: '移住', growth: '発展', weather: '天候', festival: '祭り', trade: '交易', construction: '建築', conversation: '会話', task: '村の課題と仕事' };
export interface VillageState {
  version: 4; residents: Resident[]; resources: Resources; nodes: ResourceNode[]; huts: Hut[]; civilization: Civilization;
  tasks: VillageTask[]; bridges: Bridge[]; issues: string[]; nextTaskEvaluation: number; nextBridgePlan: number;
  chronicle: VillageEvent[]; archive: { count: number; through: number; kinds: Record<string, number> };
  camp: Position; events: VillageEvent[]; nextEvent: number; elapsed: number; nextPlan: number; instructions: InstructionRecord[];
}
export function beds(state: VillageState) {
  return state.huts.filter(h => h.status === 'complete').reduce((sum, h) => sum + (h.kind === 'hut' ? 2 : h.kind === 'house' ? 4 : 0), 0);
}
export function growthRequirements(state: VillageState) {
  const complete = (kind: BuildingKind) => state.huts.some(h => h.kind === kind && h.status === 'complete');
  return [
    { label: '人口 5人', met: state.residents.length >= 5 },
    { label: '畑と初めての収穫', met: complete('farm') && state.civilization.harvests > 0 },
    { label: '住宅 1軒', met: complete('house') },
    { label: '倉庫 1棟', met: complete('warehouse') },
    { label: '食料 20', met: state.resources.food >= 20 },
    { label: '農家がいる', met: state.residents.some(r => r.job === '農家') }
  ];
}
