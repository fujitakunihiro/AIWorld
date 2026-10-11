import { z } from 'zod';

export const targetSchema = z.enum(['all', 'haru', 'mio', 'ren', 'sora', 'yui', ...Array.from({ length: 15 }, (_, i) => `new-${i + 1}`)]);
export const instructionCommandSchema = z.discriminatedUnion('action', [
  z.object({ action: z.literal('build'), building: z.enum(['hut', 'house', 'farm', 'warehouse']), count: z.number().int().min(1).max(5), location: z.enum(['village', 'river', 'forest']) }).strict(),
  z.object({ action: z.literal('farm'), target: targetSchema }).strict(),
  z.object({ action: z.literal('gather'), target: targetSchema, resource: z.enum(['food', 'wood', 'stone']) }).strict(),
  z.object({ action: z.literal('rest'), target: targetSchema }).strict(),
  z.object({ action: z.literal('auto'), target: targetSchema }).strict()
]);
export const interpretationSchema = z.object({ commands: z.array(instructionCommandSchema).max(5), message: z.string().max(300) }).strict();
export const instructionRequestSchema = z.object({ type: z.literal('instruction'), id: z.string().uuid(), text: z.string().trim().min(1).max(500) }).strict();
