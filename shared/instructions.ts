import type { z } from 'zod';
import type { instructionCommandSchema } from './instruction-schema';
import { BUILDING_LABELS } from './village';
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
export interface ResidentOrder { requestId: string; kind: 'food' | 'wood' | 'stone' | 'farm' | 'rest'; until: number }
export type InstructionResult = { type: 'instruction-result'; id: string; ok: boolean; message: string; record?: InstructionRecord };
export function describeCommand(command: InstructionCommand): string {
  const names: Record<string, string> = { all: 'みんな', haru: 'ハル', mio: 'ミオ', ren: 'レン', sora: 'ソラ', yui: 'ユイ' };
  const target = command.action === 'build' ? '' : names[command.target] ?? `移住者 ${command.target.replace('new-', '')}`;
  const resources = { food: '食料', wood: '木材', stone: '石材' };
  if (command.action === 'build') return `${{ village: '村の近く', river: '川の近く', forest: '森の近く' }[command.location]}に${BUILDING_LABELS[command.building]}を${command.count}棟建築`;
  if (command.action === 'farm') return `${target}が農業を優先（4時間）`;
  if (command.action === 'gather') return `${target}が${resources[command.resource]}の採集を優先（4時間）`;
  if (command.action === 'rest') return `${target}が休息（1時間）`;
  return `${target}が自律行動に戻る`;
}
