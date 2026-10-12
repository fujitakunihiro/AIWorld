import type { Position, Resources } from './village';
import type { Edit } from './world';
export type UtilityAction = 'food' | 'wood' | 'stone' | 'build' | 'farm' | 'rest' | 'social' | 'explore';
export const UTILITY_LABELS: Record<UtilityAction, string> = { food: '食料採集', wood: '木材採集', stone: '石材採集', build: '建築・橋', farm: '農業', rest: '休息', social: '交流', explore: '探索' };
export interface Traits { diligence: number; curiosity: number; sociability: number; caution: number; specialty: UtilityAction }
export function defaultTraits(id: string, job: string): Traits {
  let seed = 0; for (const letter of id) seed = (Math.imul(seed, 31) + letter.charCodeAt(0)) >>> 0;
  const value = (shift: number) => 0.35 + ((seed >>> shift) % 60) / 100;
  return { diligence: value(0), curiosity: value(5), sociability: value(10), caution: value(15), specialty: job === '建築家' ? 'build' : job === '木こり' ? 'wood' : job === '採掘師' ? 'stone' : job === '農家' ? 'farm' : 'food' };
}
export interface UtilityScore { action: UtilityAction; taskId: string | null; score: number; available: boolean; reason: string; factors: { label: string; value: number }[] }
export interface ResidentAI {
  taskId: string | null; cooldownUntil: number; chosen: UtilityAction | null; decidedAt: number; scores: UtilityScore[];
  history: { time: number; action: UtilityAction; taskId: string | null; text: string; outcome: 'selected' | 'complete' | 'failed' | 'interrupted' }[];
  failures: { taskId: string; until: number; reason: string }[];
}
export const emptyAI = (): ResidentAI => ({ taskId: null, cooldownUntil: 0, chosen: null, decidedAt: 0, scores: [], history: [], failures: [] });
export interface VillageTask {
  id: string; kind: 'gather' | 'build' | 'bridge' | 'farm'; action: UtilityAction; title: string; priority: number;
  requiredResources: Resources; reservedResources: Resources; requiredPeople: number; location: Position; targetId: string;
  assignees: string[]; status: 'queued' | 'running' | 'blocked' | 'complete'; progress: number; total: number;
  createdAt: number; updatedAt: number; lastProgressAt: number; retryAt: number; failure: string;
}
export interface Bridge {
  id: string; name: string; destination: Position; blocks: Edit[]; progress: number; cost: Resources;
  status: 'planned' | 'building' | 'complete'; materialsReserved: boolean; builder: string | null;
}
