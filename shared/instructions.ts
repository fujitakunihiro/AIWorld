import type { z } from 'zod';
import type { instructionCommandSchema } from './instruction-schema';
export const MAX_HUTS = 10;
export type InstructionCommand = z.infer<typeof instructionCommandSchema>;
export type InstructionSource = 'rules' | 'llm';
export interface Interpretation { commands: InstructionCommand[]; source: InstructionSource; notice: string }
export interface InstructionJob {
  command: InstructionCommand; status: 'running' | 'complete' | 'superseded';
  hutIds: string[]; until: number; detail: string;
}
export interface InstructionRecord {
  id: string; text: string; source: InstructionSource; notice: string; time: number; jobs: InstructionJob[];
}
export interface ResidentOrder { requestId: string; kind: 'food' | 'wood' | 'stone' | 'rest'; until: number }
export type InstructionResult = { type: 'instruction-result'; id: string; ok: boolean; message: string; record?: InstructionRecord };
export function describeCommand(command: InstructionCommand): string {
  const names = { all: 'みんな', haru: 'ハル', mio: 'ミオ', ren: 'レン', sora: 'ソラ', yui: 'ユイ' };
  const resources = { food: '食料', wood: '木材', stone: '石材' };
  if (command.action === 'build') return `${{ village: '村の近く', river: '川の近く', forest: '森の近く' }[command.location]}に小屋を${command.count}軒建築`;
  if (command.action === 'gather') return `${names[command.target]}が${resources[command.resource]}の採集を優先（4時間）`;
  if (command.action === 'rest') return `${names[command.target]}が休息（1時間）`;
  return `${names[command.target]}が自律行動に戻る`;
}
