import { z } from 'zod';
import type { VillageState } from '../../../shared/village';
import { MAX_BUILDINGS, MAX_POPULATION } from '../../../shared/village';
import { instructionCommandSchema } from '../../../shared/instruction-schema';
const position = z.object({ x: z.number().min(0).max(64), y: z.number().min(0).max(31), z: z.number().min(0).max(64) });
const resources = z.object({ food: z.number().int().nonnegative(), wood: z.number().int().nonnegative(), stone: z.number().int().nonnegative() });
const text = z.string().max(500), id = z.string().max(64);
const currentSchema = z.object({
  version: z.union([z.literal(1), z.literal(2)]).transform(() => 2 as const), camp: position, resources, elapsed: z.number().nonnegative(), nextPlan: z.number(), nextEvent: z.number().int().positive(),
  civilization: z.object({ level: z.union([z.literal(1), z.literal(2)]), nextArrival: z.number().nonnegative(), nextEventAt: z.number().nonnegative(), eventSequence: z.number().int().nonnegative(), arrivals: z.number().int().min(0).max(15), harvests: z.number().int().nonnegative() }),
  residents: z.array(z.object({
    id, name: text, age: z.number().int(), personality: text, job: text, color: text,
    health: z.number().min(0).max(100), energy: z.number().min(0).max(100), hunger: z.number().min(0).max(100),
    inventory: resources, position, action: z.enum(['idle', 'moving', 'gathering', 'delivering', 'building', 'farming', 'eating', 'resting', 'socializing']),
    reason: text, goal: text, relationships: z.record(id, z.number().min(0).max(100)), memories: z.array(text).max(8), memorySummary: text,
    task: z.object({ kind: z.enum(['gather', 'deliver', 'build', 'farm', 'wander', 'rest']), targetId: id.nullable(), destination: position }).nullable(),
    path: z.array(position).max(4096), work: z.number().nonnegative(), decisionIn: z.number(), home: id.nullable(),
    order: z.object({ requestId: id, kind: z.enum(['food', 'wood', 'stone', 'farm', 'rest']), until: z.number().nonnegative() }).nullable().default(null)
  })).min(5).max(MAX_POPULATION),
  nodes: z.array(z.object({ id, kind: z.enum(['food', 'wood', 'stone']), position, remaining: z.number().int().nonnegative(), capacity: z.number().int().positive(), regeneration: z.number().nonnegative() })).max(64),
  huts: z.array(z.object({ id, name: text, kind: z.enum(['hut', 'house', 'farm', 'warehouse']).default('hut'), x: z.number().int().min(0).max(60), y: z.number().int().min(1).max(27), z: z.number().int().min(0).max(60), status: z.enum(['planned', 'building', 'complete']),
    progress: z.number().int().nonnegative(), total: z.number().int().positive(), cost: resources, builder: id.nullable(), materialsReserved: z.boolean(), entranceStep: z.boolean().default(false), upgrading: z.boolean().default(false),
    crop: z.object({ stage: z.enum(['fallow', 'growing', 'ripe']), growth: z.number().min(0).max(1), harvests: z.number().int().nonnegative(), remaining: z.number().int().min(0).max(32) }).nullable().default(null)
  }).refine(h => h.progress <= h.total && (h.kind === 'farm' ? h.crop !== null : h.crop === null), '不正な建築・作物データです。')).max(MAX_BUILDINGS),
  events: z.array(z.object({ id: z.number().int(), time: z.number().nonnegative(), text, kind: z.enum(['life', 'harvest', 'arrival', 'growth', 'weather', 'festival', 'trade']).default('life') })).max(30),
  instructions: z.array(z.object({ id, text, source: z.enum(['rules', 'llm']), notice: text, time: z.number().nonnegative(),
    jobs: z.array(z.object({ command: instructionCommandSchema, status: z.enum(['running', 'complete', 'superseded']), hutIds: z.array(id).max(5), until: z.number().nonnegative(), detail: text })).min(1).max(5)
  })).max(20).default([])
}).refine(s => new Set(s.residents.map(r => r.id)).size === s.residents.length && new Set(s.huts.map(h => h.id)).size === s.huts.length && s.civilization.arrivals === s.residents.length - 5, '住民・建物のIDまたは移住人数が不正です。');
export const villageSchema: z.ZodType<VillageState> = z.preprocess(value => {
  if (value && typeof value === 'object' && (value as { version?: unknown }).version === 1) {
    const old = value as { elapsed?: number; civilization?: unknown };
    return { ...old, civilization: old.civilization ?? { level: 1, nextArrival: (old.elapsed ?? 0) + 720, nextEventAt: (old.elapsed ?? 0) + 720, eventSequence: 0, arrivals: 0, harvests: 0 } };
  }
  return value;
}, currentSchema);
