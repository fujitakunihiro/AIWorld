export const SIZE = 64;
export const HEIGHT = 32;
export const CHUNK = 16;
export const SEA = 5;
import type { VillageState } from './village';
export const SAVE_VERSION = 2;
export const Block = { Air: 0, Grass: 1, Dirt: 2, Stone: 3, Sand: 4, Wood: 5, Leaves: 6, Water: 7, Brick: 8 } as const;
export type BlockId = typeof Block[keyof typeof Block];
export interface Edit { x: number; y: number; z: number; block: BlockId }
export interface WorldSnapshot {
  type: 'snapshot'; id: string; name: string; version: number; seed: number;
  revision: number; edits: Edit[]; time: number; speed: number; village: VillageState | null;
}
export type ServerMessage = WorldSnapshot | { type: 'edit'; edit: Edit; revision: number } |
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
    const radius = Math.hypot((x - 31.5) / 28, (z - 31.5) / 26);
    const mountain = 9 * Math.exp(-((x - 43) ** 2 + (z - 23) ** 2) / 80);
    let h = Math.floor(3 + Math.max(0, 1 - radius) * 9 + mountain + noise(x / 8, z / 8, seed) * 3);
    if (radius > 1) h = Math.min(h, 3);
    // A connected, sea-level river crosses the island; a sheltered plateau is buildable.
    const river = 24 + Math.sin(z / 8) * 3;
    if (Math.abs(x - river) < 1.6) h = Math.min(h, SEA - 1);
    if (x >= 29 && x <= 39 && z >= 35 && z <= 45) h = 10;
    heights[x + SIZE * z] = h;
    for (let y = 0; y <= Math.max(h, SEA); y++) {
      data[index(x, y, z)] = y > h ? Block.Water : y < h - 2 ? Block.Stone :
        h <= SEA + 1 ? Block.Sand : y === h ? Block.Grass : Block.Dirt;
    }
  }
  for (let z = 6; z < 58; z += 3) for (let x = 6; x < 58; x += 3) {
    const h = heights[x + SIZE * z];
    if (h <= SEA + 2 || h > 16 || hash(x, z, seed + 19) < 0.64 ||
      (x >= 27 && x <= 41 && z >= 33 && z <= 47)) continue;
    for (let y = h + 1; y <= h + 4; y++) data[index(x, y, z)] = Block.Wood;
    for (let dz = -2; dz <= 2; dz++) for (let dx = -2; dx <= 2; dx++) for (let dy = 0; dy <= 2; dy++) {
      if (Math.abs(dx) + Math.abs(dz) + dy > 4) continue;
      const y = h + 4 + dy;
      if (getBlock(data, x + dx, y, z + dz) === Block.Air) data[index(x + dx, y, z + dz)] = Block.Leaves;
    }
  }
  return data;
}
