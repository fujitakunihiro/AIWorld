import { z } from 'zod';
import { SIZE, HEIGHT } from './world';
import { instructionRequestSchema } from './instruction-schema';
export const editSchema = z.object({
  type: z.literal('edit'),
  x: z.number().int().min(0).max(SIZE - 1),
  y: z.number().int().min(0).max(HEIGHT - 1),
  z: z.number().int().min(0).max(SIZE - 1),
  block: z.union([z.literal(0), z.literal(1), z.literal(2), z.literal(3), z.literal(4), z.literal(5), z.literal(6), z.literal(7), z.literal(8)]),
  expected: z.number().int().min(0).max(8)
}).strict();
export const commandSchema = z.discriminatedUnion('type', [editSchema, instructionRequestSchema,
  z.object({ type: z.literal('speed'), speed: z.union([z.literal(0), z.literal(1), z.literal(5), z.literal(20)]) }).strict()
]);
