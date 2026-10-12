import { z } from 'zod';
import type { VillageState } from '../../../shared/village';
import { MAX_BUILDINGS, MAX_POPULATION } from '../../../shared/village';
import { instructionCommandSchema } from '../../../shared/instruction-schema';
import { HEIGHT, SIZE } from '../../../shared/world';
import { defaultTraits, emptyAI } from '../../../shared/autonomy';
const position = z.object({ x: z.number().min(0).max(SIZE), y: z.number().min(0).max(HEIGHT - 1), z: z.number().min(0).max(SIZE) });
const resources = z.object({ food: z.number().int().nonnegative(), wood: z.number().int().nonnegative(), stone: z.number().int().nonnegative() });
const text = z.string().max(500), id = z.string().max(64);
const action = z.enum(['food', 'wood', 'stone', 'build', 'farm', 'rest', 'social', 'explore']);
const event = z.object({ id: z.number().int(), time: z.number().nonnegative(), text, kind: z.enum(['life', 'harvest', 'arrival', 'growth', 'weather', 'festival', 'trade', 'construction', 'conversation', 'task']).default('life'), residentIds: z.array(id).max(MAX_POPULATION).optional(), buildingId: id.optional(), taskId: id.optional(), position: position.optional() });
const score = z.object({ action, taskId: id.nullable(), score: z.number().finite(), available: z.boolean(), reason: text, factors: z.array(z.object({ label: text, value: z.number().finite() })).max(16) });
const task = z.object({ id, kind: z.enum(['gather', 'build', 'bridge', 'farm']), action, title: text, priority: z.number().finite(), requiredResources: resources, reservedResources: resources, requiredPeople: z.number().int().min(1).max(MAX_POPULATION), location: position, targetId: id,
  assignees: z.array(id).max(MAX_POPULATION), status: z.enum(['queued', 'running', 'blocked', 'complete']), progress: z.number().nonnegative(), total: z.number().positive(), createdAt: z.number().nonnegative(), updatedAt: z.number().nonnegative(), lastProgressAt: z.number().nonnegative(), retryAt: z.number().nonnegative(), failure: text });
const currentSchema = z.object({
  version: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4)]).transform(() => 4 as const), camp: position, resources, elapsed: z.number().nonnegative(), nextPlan: z.number(), nextEvent: z.number().int().positive(),
  tasks: z.array(task).max(160).default([]), issues: z.array(text).max(16).default([]), nextTaskEvaluation: z.number().nonnegative().default(0), nextBridgePlan: z.number().nonnegative().default(0),
  bridges: z.array(z.object({ id, name: text, destination: position, blocks: z.array(z.object({ x: z.number().int().min(0).max(SIZE - 1), y: z.number().int().min(1).max(HEIGHT - 3), z: z.number().int().min(0).max(SIZE - 1), block: z.literal(5) })).min(1).max(600), progress: z.number().int().nonnegative(), cost: resources, status: z.enum(['planned', 'building', 'complete']), materialsReserved: z.boolean(), builder: id.nullable() }).refine(b => b.progress <= b.blocks.length && (b.status !== 'complete' || b.progress === b.blocks.length) && b.cost.wood === b.blocks.length)).max(8).default([]),
  chronicle: z.array(event).max(300).default([]),
  archive: z.object({ count: z.number().int().nonnegative(), through: z.number().nonnegative(), kinds: z.record(z.string().max(32), z.number().int().nonnegative()) }).default({ count: 0, through: 0, kinds: {} }),
  civilization: z.object({ level: z.union([z.literal(1), z.literal(2)]), nextArrival: z.number().nonnegative(), nextEventAt: z.number().nonnegative(), eventSequence: z.number().int().nonnegative(), arrivals: z.number().int().min(0).max(15), harvests: z.number().int().nonnegative() }),
  residents: z.array(z.object({
    id, name: text, age: z.number().int(), personality: text, job: text, color: text,
    traits: z.object({ diligence: z.number().min(0).max(1), curiosity: z.number().min(0).max(1), sociability: z.number().min(0).max(1), caution: z.number().min(0).max(1), specialty: action }),
    ai: z.object({ taskId: id.nullable(), cooldownUntil: z.number().nonnegative(), chosen: action.nullable(), decidedAt: z.number().nonnegative(), scores: z.array(score).max(8),
      history: z.array(z.object({ time: z.number().nonnegative(), action, taskId: id.nullable(), text, outcome: z.enum(['selected', 'complete', 'failed', 'interrupted']) })).max(20), failures: z.array(z.object({ taskId: id, until: z.number().nonnegative(), reason: text })).max(16) }),
    health: z.number().min(0).max(100), energy: z.number().min(0).max(100), hunger: z.number().min(0).max(100),
    inventory: resources, position, action: z.enum(['idle', 'moving', 'gathering', 'delivering', 'building', 'farming', 'eating', 'resting', 'socializing', 'exploring']),
    reason: text, goal: text, relationships: z.record(id, z.number().min(0).max(100)), memories: z.array(text).max(8), memorySummary: text,
    conversations: z.array(z.object({ id, time: z.number().nonnegative(), question: z.string().max(300), answer: text, source: z.enum(['rules', 'llm']) })).max(12).default([]),
    speech: z.object({ text: z.string().max(160), until: z.number().nonnegative() }).nullable().default(null), nextSocialAt: z.number().nonnegative().default(0),
    task: z.object({ kind: z.enum(['gather', 'deliver', 'build', 'bridge', 'farm', 'wander', 'explore', 'rest']), targetId: id.nullable(), destination: position }).nullable(),
    path: z.array(position).max(4096), work: z.number().nonnegative(), decisionIn: z.number(), home: id.nullable(),
    order: z.object({ requestId: id, kind: z.enum(['food', 'wood', 'stone', 'farm', 'rest']), until: z.number().nonnegative() }).nullable().default(null)
  })).min(5).max(MAX_POPULATION),
  nodes: z.array(z.object({ id, kind: z.enum(['food', 'wood', 'stone']), position, remaining: z.number().int().nonnegative(), capacity: z.number().int().positive(), regeneration: z.number().nonnegative() })).max(64),
  huts: z.array(z.object({ id, name: text, kind: z.enum(['hut', 'house', 'farm', 'warehouse']).default('hut'), x: z.number().int().min(0).max(SIZE - 4), y: z.number().int().min(1).max(27), z: z.number().int().min(0).max(SIZE - 4), status: z.enum(['planned', 'building', 'complete']),
    progress: z.number().int().nonnegative(), total: z.number().int().positive(), cost: resources, builder: id.nullable(), materialsReserved: z.boolean(), entranceStep: z.boolean().default(false), upgrading: z.boolean().default(false),
    crop: z.object({ stage: z.enum(['fallow', 'growing', 'ripe']), growth: z.number().min(0).max(1), harvests: z.number().int().nonnegative(), remaining: z.number().int().min(0).max(32) }).nullable().default(null)
  }).refine(h => h.progress <= h.total && (h.kind === 'farm' ? h.crop !== null : h.crop === null), '不正な建築・作物データです。')).max(MAX_BUILDINGS),
  events: z.array(event).max(30),
  instructions: z.array(z.object({ id, text, source: z.enum(['rules', 'llm']), notice: text, time: z.number().nonnegative(),
    jobs: z.array(z.object({ command: instructionCommandSchema, status: z.enum(['running', 'complete', 'superseded']), hutIds: z.array(id).max(5), until: z.number().nonnegative(), detail: text })).min(1).max(5)
  })).max(20).default([])
}).refine(s => new Set(s.residents.map(r => r.id)).size === s.residents.length && new Set(s.huts.map(h => h.id)).size === s.huts.length && s.civilization.arrivals === s.residents.length - 5, '住民・建物のIDまたは移住人数が不正です。');
export const villageSchema: z.ZodType<VillageState> = z.preprocess(value => {
  if (value && typeof value === 'object') {
    const old = value as { residents?: { id: string; job: string; traits?: unknown; ai?: unknown }[] };
    if (Array.isArray(old.residents)) value = { ...old, residents: old.residents.map(r => ({ ...r, traits: r.traits ?? defaultTraits(r.id, r.job), ai: r.ai ?? emptyAI() })) };
  }
  if (value && typeof value === 'object' && [1, 2].includes((value as { version: number }).version)) {
    const old = value as { elapsed?: number; civilization?: unknown; events?: unknown[] };
    return { ...old, chronicle: old.events ?? [], civilization: old.civilization ?? { level: 1, nextArrival: (old.elapsed ?? 0) + 720, nextEventAt: (old.elapsed ?? 0) + 720, eventSequence: 0, arrivals: 0, harvests: 0 } };
  }
  return value;
}, currentSchema);
