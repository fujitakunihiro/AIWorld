export const SIZE = 128;
export const HEIGHT = 32;
export const CHUNK = 16;
export const SEA = 5;
import type { VillageState } from './village';
import type { InstructionResult } from './instructions';
import type { ConversationResult } from './conversation';
export const SAVE_VERSION = 4;
export const Block = { Air: 0, Grass: 1, Dirt: 2, Stone: 3, Sand: 4, Wood: 5, Leaves: 6, Water: 7, Brick: 8 } as const;
export type BlockId = typeof Block[keyof typeof Block];
export interface Edit { x: number; y: number; z: number; block: BlockId }
export interface WorldSnapshot {
  type: 'snapshot'; id: string; name: string; version: number; seed: number;
  revision: number; edits: Edit[]; time: number; speed: number; village: VillageState | null;
}
export type ServerMessage = WorldSnapshot | InstructionResult | ConversationResult | { type: 'instruction-config'; mode: 'llm' | 'rules' } | { type: 'edit'; edit: Edit; revision: number } |
  { type: 'terrain'; edits: Edit[]; revision: number } |
  { type: 'village'; village: VillageState; time: number; speed: number } |
  { type: 'clock'; time: number; speed: number } | { type: 'error'; message: string };
export const index = (x: number, y: number, z: number) => x + SIZE * (z + SIZE * y);
export const inside = (x: number, y: number, z: number) =>
  Number.isInteger(x) && Number.isInteger(y) && Number.isInteger(z) && x >= 0 && x < SIZE && y >= 0 && y < HEIGHT && z >= 0 && z < SIZE;
export const getBlock = (data: Uint8Array, x: number, y: number, z: number): BlockId =>
  inside(x, y, z) ? data[index(x, y, z)] as BlockId : Block.Air;
function hash(x: number, z: number, seed: number) {
  let n = Math.imul(x, 374761393) ^ Math.imul(z, 668265263) ^ seed;
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967295;
}
function noise(x: number, z: number, seed: number) {
  const a = Math.floor(x), b = Math.floor(z);
  const smooth = (t: number) => t * t * (3 - 2 * t);
  const u = smooth(x - a), v = smooth(z - b);
  return (hash(a, b, seed) * (1 - u) + hash(a + 1, b, seed) * u) * (1 - v) +
    (hash(a, b + 1, seed) * (1 - u) + hash(a + 1, b + 1, seed) * u) * v;
}
export function generateWorld(seed: number): Uint8Array {
  const data = new Uint8Array(SIZE * SIZE * HEIGHT);
  const heights = new Int8Array(SIZE * SIZE);
  for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
    const original = x < 64 && z < 64;
    const centers = [[96, 32, 29, 27], [88, 94, 33, 28], [27, 96, 24, 26]];
    const radius = original ? Math.hypot((x - 31.5) / 28, (z - 31.5) / 26) :
      Math.min(...centers.map(([cx, cz, rx, rz]) => Math.hypot((x - cx) / rx, (z - cz) / rz)));
    const mountain = original ? 9 * Math.exp(-((x - 43) ** 2 + (z - 23) ** 2) / 80) :
      8 * Math.exp(-((x - 99) ** 2 + (z - 88) ** 2) / 180);
    let h = Math.floor(3 + Math.max(0, 1 - radius) * 9 + mountain + noise(x / 8, z / 8, seed) * 3);
    if (radius > 1) h = Math.min(h, 3);
    // A connected, sea-level river crosses the island; a sheltered plateau is buildable.
    const river = 24 + Math.sin(z / 8) * 3;
    if (original && Math.abs(x - river) < 1.6) h = Math.min(h, SEA - 1);
    if (!original && z > 68 && Math.abs(x - (82 + Math.sin(z / 12) * 4)) < 1.8) h = Math.min(h, SEA - 1);
    if (x >= 29 && x <= 39 && z >= 35 && z <= 45) h = 10;
    if (x >= 92 && x <= 106 && z >= 31 && z <= 45) h = 10;
    if (x >= 28 && x <= 40 && z >= 92 && z <= 104) h = 10;
    heights[x + SIZE * z] = h;
    for (let y = 0; y <= Math.max(h, SEA); y++) {
      data[index(x, y, z)] = y > h ? Block.Water : y < h - 2 ? Block.Stone :
        h <= SEA + 1 ? Block.Sand : y === h ? Block.Grass : Block.Dirt;
    }
  }
  for (let z = 6; z < SIZE - 6; z += 3) for (let x = 6; x < SIZE - 6; x += 3) {
    // The original 64×64 region stays byte-for-byte identical for existing saves.
    if (x < 64 && z < 64 && (x >= 58 || z >= 58)) continue;
    const h = heights[x + SIZE * z];
    if (h <= SEA + 2 || h > 16 || hash(x, z, seed + 19) < 0.64 ||
      (x >= 27 && x <= 41 && z >= 33 && z <= 47) ||
      (x >= 90 && x <= 108 && z >= 29 && z <= 47) || (x >= 26 && x <= 42 && z >= 90 && z <= 106)) continue;
    for (let y = h + 1; y <= h + 4; y++) data[index(x, y, z)] = Block.Wood;
    for (let dz = -2; dz <= 2; dz++) for (let dx = -2; dx <= 2; dx++) for (let dy = 0; dy <= 2; dy++) {
      if (Math.abs(dx) + Math.abs(dz) + dy > 4) continue;
      const y = h + 4 + dy;
      if (getBlock(data, x + dx, y, z + dz) === Block.Air) data[index(x + dx, y, z + dz)] = Block.Leaves;
    }
  }
  return data;
}
