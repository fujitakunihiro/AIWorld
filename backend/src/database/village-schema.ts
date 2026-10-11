import { z } from 'zod';
import type { VillageState } from '../../../shared/village';
const position = z.object({ x: z.number().min(0).max(64), y: z.number().min(0).max(31), z: z.number().min(0).max(64) });
const resources = z.object({ food: z.number().int().nonnegative(), wood: z.number().int().nonnegative(), stone: z.number().int().nonnegative() });
const text = z.string().max(500), id = z.string().max(64);
export const villageSchema: z.ZodType<VillageState> = z.object({
  version: z.literal(1), camp: position, resources, elapsed: z.number().nonnegative(), nextPlan: z.number(), nextEvent: z.number().int().positive(),
  residents: z.array(z.object({
    id, name: text, age: z.number().int(), personality: text, job: text, color: text,
    health: z.number().min(0).max(100), energy: z.number().min(0).max(100), hunger: z.number().min(0).max(100),
    inventory: resources, position, action: z.enum(['idle', 'moving', 'gathering', 'delivering', 'building', 'eating', 'resting', 'socializing']),
    reason: text, goal: text, relationships: z.record(id, z.number().min(0).max(100)), memories: z.array(text).max(8), memorySummary: text,
    task: z.object({ kind: z.enum(['gather', 'deliver', 'build', 'wander', 'rest']), targetId: id.nullable(), destination: position }).nullable(),
    path: z.array(position).max(4096), work: z.number().nonnegative(), decisionIn: z.number(), home: id.nullable()
  })).length(5),
  nodes: z.array(z.object({ id, kind: z.enum(['food', 'wood', 'stone']), position, remaining: z.number().int().nonnegative(), capacity: z.number().int().positive(), regeneration: z.number().nonnegative() })).max(64),
  huts: z.array(z.object({ id, name: text, x: z.number().int(), y: z.number().int(), z: z.number().int(), status: z.enum(['planned', 'building', 'complete']),
    progress: z.number().int().nonnegative(), total: z.number().int().positive(), cost: resources, builder: id.nullable(), materialsReserved: z.boolean()
  })).max(3),
  events: z.array(z.object({ id: z.number().int(), time: z.number().nonnegative(), text })).max(30)
});
