import type { InstructionRecord, ResidentOrder } from './instructions';
export interface Position { x: number; y: number; z: number }
export type Resource = 'food' | 'wood' | 'stone';
export type Resources = Record<Resource, number>;
export type Action = 'idle' | 'moving' | 'gathering' | 'delivering' | 'building' | 'eating' | 'resting' | 'socializing';
export const ACTION_LABELS: Record<Action, string> = {
  idle: '周囲を見ています', moving: '移動中', gathering: '採集中', delivering: '資源を運んでいます',
  building: '小屋を建てています', eating: '食事中', resting: '休息中', socializing: '交流中'
};
export const RESOURCE_LABELS: Record<Resource, string> = { food: '食料', wood: '木材', stone: '石材' };
export interface Resident {
  id: string; name: string; age: number; personality: string; job: string; color: string;
  health: number; energy: number; hunger: number; inventory: Resources; position: Position;
  action: Action; reason: string; goal: string; relationships: Record<string, number>;
  memories: string[]; memorySummary: string;
  task: { kind: 'gather' | 'deliver' | 'build' | 'wander' | 'rest'; targetId: string | null; destination: Position } | null;
  path: Position[]; work: number; decisionIn: number; home: string | null; order: ResidentOrder | null;
}
export interface ResourceNode {
  id: string; kind: Resource; position: Position; remaining: number; capacity: number; regeneration: number;
}
export interface Hut {
  id: string; name: string; x: number; y: number; z: number;
  status: 'planned' | 'building' | 'complete'; progress: number; total: number;
  cost: Resources; builder: string | null; materialsReserved: boolean;
}
export interface VillageEvent { id: number; time: number; text: string }
export interface VillageState {
  version: 1; residents: Resident[]; resources: Resources; nodes: ResourceNode[]; huts: Hut[];
  camp: Position; events: VillageEvent[]; nextEvent: number; elapsed: number; nextPlan: number; instructions: InstructionRecord[];
}
