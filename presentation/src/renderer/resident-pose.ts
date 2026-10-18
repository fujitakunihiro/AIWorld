import type { Resident, Resource } from '../../../shared/village';

export type ResidentRole = 'builder' | 'lumberjack' | 'miner' | 'farmer' | 'forager';
export type ResidentTool = 'hammer' | 'axe' | 'pick' | 'hoe' | 'basket';
export const residentRole = (job: string): ResidentRole => ({ '建築家': 'builder', '木こり': 'lumberjack', '採掘師': 'miner', '農家': 'farmer' } as Record<string, ResidentRole>)[job] ?? 'forager';
export const roleTool: Record<ResidentRole, ResidentTool> = { builder: 'hammer', lumberjack: 'axe', miner: 'pick', farmer: 'hoe', forager: 'basket' };
export function residentSeed(id: string) { let n = 0; for (const c of id) n = (Math.imul(n, 31) + c.charCodeAt(0)) >>> 0; return n; }
export function workTool(resident: Resident, resource?: Resource): ResidentTool {
  if (resident.action === 'building') return 'hammer';
  if (resident.action === 'farming') return 'hoe';
  if (resident.action === 'gathering' && resource) return resource === 'wood' ? 'axe' : resource === 'stone' ? 'pick' : 'basket';
  return roleTool[residentRole(resident.job)];
}
export interface ResidentPose {
  legs: [number, number]; arms: [number, number]; upperY: number; lean: number; headTurn: number; headNod: number;
  legY: number; legScale: number; tool: ResidentTool; showTool: boolean; cargo: Resource | null; cargoScale: number;
  blink: number; smile: number; worry: number;
}
export function residentMood(r: Resident): 'calm' | 'happy' | 'tired' | 'worried' {
  if (r.health < 40 || r.hunger > 75) return 'worried';
  if (r.action === 'resting' || r.energy < 25) return 'tired';
  if (r.action === 'socializing' || r.speech) return 'happy';
  return 'calm';
}
// Only presentation state is derived here. The action, inventory, and task are read-only.
// time is a per-resident animation clock; the renderer freezes it while paused.
export function residentPose(r: Resident, time: number, reduced: boolean, resource?: Resource): ResidentPose {
  const seed = residentSeed(r.id), phase = seed % 628 / 100, t = reduced ? 0 : time;
  const breath = reduced ? 0 : Math.sin(t * 2 + phase) * .009;
  const total = r.inventory.food + r.inventory.wood + r.inventory.stone;
  const cargo = total > 0 ? r.inventory.food > 0 ? 'food' : r.inventory.stone > 0 ? 'stone' : 'wood' : null;
  const tool = workTool(r, resource), working = ['building', 'gathering', 'farming'].includes(r.action);
  const mood = residentMood(r), cycle = 3.2 + seed % 23 / 10, blinkTime = (t + phase) % cycle;
  const blink = reduced ? 0 : Math.max(0, 1 - Math.abs(blinkTime - .12) / .12);
  const pose: ResidentPose = { legs: [0, 0], arms: [0, 0], upperY: .64 + breath, lean: 0,
    headTurn: reduced ? 0 : Math.sin(t * .65 + phase) * .07, headNod: 0, legY: .6, legScale: 1,
    tool, showTool: !cargo && (working || ['idle', 'exploring'].includes(r.action)), cargo, cargoScale: Math.min(1, .8 + total / 40),
    blink: Math.max(blink, mood === 'tired' ? r.action === 'resting' ? .85 : .35 : 0), smile: mood === 'happy' ? 1 : 0, worry: mood === 'worried' ? 1 : 0 };
  if (r.action === 'resting') {
    pose.upperY = .48 + breath; pose.legY = .45; pose.legScale = .75; pose.legs = [-.25, -.25];
    pose.lean = .08; pose.arms = [-.3, -.3]; pose.headNod = .12; pose.showTool = false;
  } else if (r.action === 'moving' && !reduced) {
    const stride = Math.sin(t * 10 + phase);
    pose.legs = [stride * .52, -stride * .52]; pose.upperY += Math.abs(stride) * .018;
    pose.arms = cargo ? [-.82, -.82] : [-stride * .36, stride * .36]; pose.lean = .04; pose.headTurn *= .25;
  } else if (working) {
    const swing = reduced ? 0 : Math.sin(t * (tool === 'hammer' ? 8 : 5.6) + phase);
    pose.headTurn = 0;
    if (tool === 'basket') { pose.arms = [-.95 - swing * .15, -.9 + swing * .25]; pose.lean = .17; pose.headNod = .1; }
    else if (tool === 'hoe') { pose.arms = [-.7 + swing * .16, -.85 + swing * .42]; pose.lean = .14 + swing * .025; pose.headNod = .09; }
    else if (tool === 'hammer') { pose.arms = [-.4, -.95 + swing * .55]; pose.lean = .07; pose.headNod = .05; }
    else { pose.arms = [-.4 - swing * .12, -1.05 + swing * .65]; pose.lean = .1 + swing * .03; pose.headNod = .07; }
    pose.showTool = true;
  } else if (r.action === 'eating') { pose.arms = [-1.7, -.7]; pose.showTool = false; pose.headNod = .06; }
  else if (r.action === 'socializing') { pose.arms = [0, -.75 + (reduced ? 0 : Math.sin(t * 3 + phase) * .15)]; pose.showTool = false; }
  else if (r.action === 'exploring') pose.headTurn = reduced ? 0 : Math.sin(t * .8 + phase) * .35;
  if (cargo && !working && r.action !== 'eating') { pose.arms = [-.82, -.82]; pose.showTool = false; }
  return pose;
}
