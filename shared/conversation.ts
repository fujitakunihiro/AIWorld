import { z } from 'zod';
export interface Conversation { id: string; time: number; question: string; answer: string; source: 'rules' | 'llm' }
export interface ConversationResult { type: 'conversation-result'; id: string; residentId: string; ok: boolean; message: string; conversation?: Conversation }
export const conversationRequestSchema = z.object({ type: z.literal('conversation'), id: z.string().regex(/^[a-zA-Z0-9-]{1,64}$/), residentId: z.string().regex(/^[a-zA-Z0-9-]{1,64}$/), text: z.string().trim().min(1).max(300) }).strict();
