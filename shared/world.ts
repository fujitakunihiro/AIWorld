export const SIZE = 384;
export const HEIGHT = 32;
export const CHUNK = 32;
export const SEA = 5;
import type { VillageState } from './village';
import type { InstructionResult } from './instructions';
import type { ConversationResult } from './conversation';
export const SAVE_VERSION = 9;
// The map is oriented with north at the top. The Seine crosses the city north–south
// in map space; landmark coordinates follow their real west/central/east order.
export const EIFFEL = { id: 'eiffel', name: 'エッフェル塔', continent: 'パリ', x: 104, y: 9, z: 258, height: 22 } as const;
export const ARC = { id: 'arc', name: '凱旋門', x: 148, y: 9, z: 98 } as const;
export const LOUVRE = { id: 'louvre', name: 'ルーヴル美術館', x: 266, y: 9, z: 156 } as const;
export const NOTRE_DAME = { id: 'notre-dame', name: 'ノートルダム大聖堂', x: 194, y: 9, z: 194 } as const;
export const CAROUSEL = { id: 'carousel', name: '広場の回転木馬', x: 117, y: 9, z: 289 } as const;
export const PARIS_BRIDGES = [52, 112, 172, 216, 276, 336] as const;
export const riverCenter = (z: number) => 192 + Math.sin((z - 30) / 64) * 18 + Math.sin(z / 23) * 6;
export const inCite = (x: number, z: number, margin = 0) => {
  const dz = (z - NOTRE_DAME.z) / (17 + margin), dx = (x - riverCenter(z)) / (7 + margin);
  return dx * dx + dz * dz <= 1;
};
export const bridgeCenter = (z: number) => riverCenter(z);
export const inLandmark = (x: number, z: number, margin = 8) => Math.abs(x - EIFFEL.x) <= margin && Math.abs(z - EIFFEL.z) <= margin;
export const inArc = (x: number, z: number, margin = 0) => Math.abs(x - ARC.x) <= 5 + margin && Math.abs(z - ARC.z) <= 3 + margin;
export const inCarousel = (x: number, z: number, margin = 0) => Math.hypot(x - CAROUSEL.x, z - CAROUSEL.z) <= 4 + margin;
export const inCulturalLandmark = (x: number, z: number, margin = 0) =>
  (Math.abs(x - LOUVRE.x) <= 31 + margin && Math.abs(z - LOUVRE.z) <= 27 + margin) ||
  (Math.abs(x - NOTRE_DAME.x) <= 15 + margin && Math.abs(z - NOTRE_DAME.z) <= 22 + margin);
export const inParisBridge = (x: number, z: number, margin = 0) =>
  PARIS_BRIDGES.some(center => Math.abs(z - center) <= 1 + margin && Math.abs(x - bridgeCenter(center)) <= 25 + margin);
export interface FrenchBuilding { id: string; x: number; z: number; floors: 2 | 3 | 4; style: number }
const onPark = (x: number, z: number) =>
  (x >= EIFFEL.x - 24 && x <= EIFFEL.x + 27 && z >= EIFFEL.z - 34 && z <= EIFFEL.z + 56) ||
  (x >= ARC.x - 20 && x <= ARC.x + 20 && z >= ARC.z - 20 && z <= ARC.z + 20) ||
  (x > LOUVRE.x - 27 && x < LOUVRE.x + 31 && z > LOUVRE.z - 24 && z < LOUVRE.z + 23) || inCite(x, z, 2);
const onGrandAvenue = (x: number, z: number) => {
  if ([48, 96, 144, 240, 288, 336].some(n => Math.abs(x - n) < 3.5 || Math.abs(z - n) < 3.5)) return true;
  // Eight broad avenues radiate from Place Charles de Gaulle.
  const dx = x - ARC.x, dz = z - ARC.z, length = Math.hypot(dx, dz);
  if (length < 3) return true;
  const angle = Math.atan2(dz, dx), spoke = Math.round(angle / (Math.PI / 4)) * Math.PI / 4;
  return Math.abs(Math.sin(angle - spoke) * length) < 2.7 && length < 140;
};
// Repeating six-by-six urban lots leave generous walkable streets between blocks.
export const FRENCH_BUILDINGS: FrenchBuilding[] = (() => {
  const buildings: FrenchBuilding[] = [];
  for (let z = 12; z <= SIZE - 20; z += 10) for (let x = 12; x <= SIZE - 20; x += 10) {
    // Keep the original village's starter clearing available for residents and saved homes.
    if (x < 76 && z < 78) continue;
    const samples = [[x, z], [x + 6, z], [x, z + 6], [x + 6, z + 6], [x + 3, z + 3]];
    if (samples.some(([px, pz]) => Math.abs(px - riverCenter(pz)) < 23 && !inCite(px, pz))) continue;
    if (samples.some(([px, pz]) => onPark(px, pz) || onGrandAvenue(px, pz) || inParisBridge(px, pz, 8))) continue;
    if (Math.hypot(x + 3 - EIFFEL.x, z + 3 - EIFFEL.z) < 31 ||
        Math.hypot(x + 3 - NOTRE_DAME.x, z + 3 - NOTRE_DAME.z) < 12 ||
        Math.hypot(x + 3 - CAROUSEL.x, z + 3 - CAROUSEL.z) < 10) continue;
    const style = ((x * 17 + z * 11) >>> 1) % 4;
    buildings.push({ id: `paris-${x}-${z}`, x, z, floors: style === 3 ? 2 : style === 0 ? 4 : 3, style });
  }
  return buildings;
})();
export const inFrenchBuilding = (x: number, z: number, margin = 0) =>
  FRENCH_BUILDINGS.some(b => x >= b.x - margin && x < b.x + 6 + margin && z >= b.z - margin && z < b.z + 6 + margin);
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
  const parks: [number, number, number, number][] = [
    [EIFFEL.x - 24, EIFFEL.z - 34, EIFFEL.x + 27, EIFFEL.z + 56],
    [ARC.x - 20, ARC.z - 20, ARC.x + 20, ARC.z + 20],
    [LOUVRE.x - 28, LOUVRE.z - 24, LOUVRE.x + 32, LOUVRE.z + 24],
    [24, 28, 75, 77], // Bois de Boulogne edge and the preserved starting village clearing.
  ];
  for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
    const cx = riverCenter(z), inWater = Math.abs(x - cx) < 12 && !inCite(x, z);
    const onIsland = inCite(x, z);
    const h = inWater ? SEA : 8;
    heights[x + SIZE * z] = h;
    const park = parks.some(([x0, z0, x1, z1]) => x >= x0 && x <= x1 && z >= z0 && z <= z1) || onIsland;
    for (let y = 0; y <= Math.max(h, SEA + 1); y++) {
      const block = y > h ? Block.Water : y < h - 2 ? Block.Stone :
        inWater ? y === h ? Block.Sand : Block.Stone :
          y === h ? park ? Block.Grass : Block.Stone : y >= h - 2 ? park ? Block.Dirt : Block.Stone : Block.Stone;
      data[index(x, y, z)] = block;
    }
    // Pale stone quays mark both banks and make the Seine read as a planned city river.
    if (!inWater && Math.abs(x - cx) >= 12 && Math.abs(x - cx) <= 16 && !onIsland)
      data[index(x, h, z)] = Block.Stone;
  }
  for (let z = 6; z < SIZE - 6; z += 3) for (let x = 6; x < SIZE - 6; x += 3) {
    const h = heights[x + SIZE * z], inWater = h <= SEA;
    if (inWater || inFrenchBuilding(x, z) || onPark(x, z) || onGrandAvenue(x, z) ||
      Math.abs(x - riverCenter(z)) < 19 || inParisBridge(x, z, 5) || inLandmark(x, z, 34) || inArc(x, z, 6) || inCulturalLandmark(x, z) ||
      (x >= 20 && x <= 60 && z >= 25 && z <= 65) ||
      hash(x, z, seed + 19) < 0.7) continue;
    for (let y = h + 1; y <= h + 4; y++) data[index(x, y, z)] = Block.Wood;
    for (let dz = -2; dz <= 2; dz++) for (let dx = -2; dx <= 2; dx++) for (let dy = 0; dy <= 2; dy++) {
      if (Math.abs(dx) + Math.abs(dz) + dy > 4) continue;
      const y = h + 4 + dy;
      if (getBlock(data, x + dx, y, z + dz) === Block.Air) data[index(x + dx, y, z + dz)] = Block.Leaves;
    }
  }
  for (const e of eiffelVoxels()) data[index(e.x, e.y, e.z)] = e.block;
  for (const e of FRENCH_VOXELS) data[index(e.x, e.y, e.z)] = e.block;
  for (const e of ARC_VOXELS) data[index(e.x, e.y, e.z)] = e.block;
  for (const e of PARIS_BRIDGE_VOXELS) data[index(e.x, e.y, e.z)] = e.block;
  for (const e of CAROUSEL_VOXELS) data[index(e.x, e.y, e.z)] = e.block;
  return data;
}

// Permanent city blocks keep paths and collision consistent in both graphic styles.
export const FRENCH_VOXELS: Edit[] = FRENCH_BUILDINGS.flatMap(b => {
  const voxels: Edit[] = [], top = 8 + b.floors * 3;
  for (let y = 9; y <= top; y++) for (let dz = 0; dz < 6; dz++) for (let dx = 0; dx < 6; dx++) {
    if (y > 9 && dx !== 0 && dx !== 5 && dz !== 0 && dz !== 5) continue;
    voxels.push({ x: b.x + dx, y, z: b.z + dz, block: Block.Brick });
  }
  for (let y = top + 1; y <= top + 3; y++) for (let dz = y === top + 3 ? 1 : 0; dz < (y === top + 3 ? 5 : 6); dz++)
    for (let dx = y === top + 3 ? 1 : 0; dx < (y === top + 3 ? 5 : 6); dx++)
      voxels.push({ x: b.x + dx, y, z: b.z + dz, block: Block.Stone });
  return voxels;
});

export const ARC_VOXELS: Edit[] = (() => {
  const voxels: Edit[] = [];
  for (let y = 9; y <= 20; y++) for (let z = ARC.z - 2; z <= ARC.z + 2; z++) for (let x = ARC.x - 4; x <= ARC.x + 4; x++) {
    if (Math.abs(x - ARC.x) < 3 && y < 17) continue;
    voxels.push({ x, y, z, block: Block.Stone });
  }
  return voxels;
})();
export const PARIS_BRIDGE_VOXELS: Edit[] = PARIS_BRIDGES.flatMap(center => {
  const voxels: Edit[] = [];
  const mid = bridgeCenter(center), start = Math.round(mid - 24), end = Math.round(mid + 24);
  for (let x = start; x <= end; x++) for (let z = center - 1; z <= center + 1; z++)
    for (const y of [7, 8]) voxels.push({ x, y, z, block: Block.Stone });
  for (const x of [start + 6, start + 18, start + 30, start + 42]) for (const z of [center - 1, center + 1]) for (let y = SEA; y < 8; y++)
    voxels.push({ x, y, z, block: Block.Stone });
  return voxels;
});
export const CAROUSEL_VOXELS: Edit[] = (() => {
  const voxels: Edit[] = [];
  for (let y = CAROUSEL.y; y <= CAROUSEL.y + 4; y++)
    voxels.push({ x: CAROUSEL.x, y, z: CAROUSEL.z, block: Block.Wood });
  for (let dz = -4; dz <= 4; dz++) for (let dx = -4; dx <= 4; dx++) {
    if (Math.hypot(dx, dz) > 4.2) continue;
    voxels.push({ x: CAROUSEL.x + dx, y: CAROUSEL.y + 4, z: CAROUSEL.z + dz, block: (dx + dz) % 2 ? Block.Brick : Block.Sand });
  }
  return voxels;
})();

// Persistent voxel silhouette supplies classic rendering, collision and edit protection.
export function eiffelVoxels(): Edit[] {
  const cells = new Map<string, Edit>();
  const add = (x: number, y: number, z: number, block: BlockId = Block.Brick) => {
    x = EIFFEL.x + Math.round(x); y = EIFFEL.y + Math.round(y); z = EIFFEL.z + Math.round(z);
    if (inside(x, y, z)) cells.set(`${x}:${y}:${z}`, { x, y, z, block });
  };
  for (let y = 0; y <= 19; y++) {
    const half = y < 7 ? 6 - y * .38 : y < 13 ? 3.34 - (y - 7) * .34 : 1.3 - (y - 13) * .14;
    const previousY = Math.max(0, y - 1), previous = previousY < 7 ? 6 - previousY * .38 : previousY < 13 ? 3.34 - (previousY - 7) * .34 : 1.3 - (previousY - 13) * .14;
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      add(sx * half, y, sz * half);
      // Stepped legs share full voxel faces instead of floating diagonally apart.
      if (Math.round(previous) !== Math.round(half)) { add(sx * previous, y, sz * previous); add(sx * half, y, sz * previous); add(sx * previous, y, sz * half); }
    }
    if ([7, 13, 19].includes(y)) for (let a = -Math.round(half) - 1; a <= Math.round(half) + 1; a++) for (const s of [-1, 1]) { add(a, y, s * (Math.round(half) + 1)); add(s * (Math.round(half) + 1), y, a); }
  }
  for (let y = 20; y <= 22; y++) add(0, y, 0);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) add(sx * 6 + x, -1, sz * 6 + z, Block.Stone);
  return [...cells.values()];
}
