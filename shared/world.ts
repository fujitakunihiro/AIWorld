export const SIZE = 384;
export const HEIGHT = 32;
export const CHUNK = 32;
export const SEA = 5;
import type { VillageState } from './village';
import type { InstructionResult } from './instructions';
import type { ConversationResult } from './conversation';
export const SAVE_VERSION = 8;
export const EIFFEL = { id: 'eiffel', name: 'エッフェル塔', continent: '暁の新大陸', x: 196, y: 9, z: 122, height: 22 } as const;
export const ARC = { id: 'arc', name: '凱旋門', x: 312, y: 9, z: 113 } as const;
export const CAROUSEL = { id: 'carousel', name: '広場の回転木馬', x: 294, y: 9, z: 144 } as const;
export const PARIS_BRIDGES = [113, 163] as const;
export const inLandmark = (x: number, z: number, margin = 8) => Math.abs(x - EIFFEL.x) <= margin && Math.abs(z - EIFFEL.z) <= margin;
export const inArc = (x: number, z: number, margin = 0) => Math.abs(x - ARC.x) <= 5 + margin && Math.abs(z - ARC.z) <= 3 + margin;
export const inCarousel = (x: number, z: number, margin = 0) => Math.hypot(x - CAROUSEL.x, z - CAROUSEL.z) <= 4 + margin;
export const inParisBridge = (x: number, z: number, margin = 0) =>
  x >= 238 - margin && x <= 277 + margin && PARIS_BRIDGES.some(center => Math.abs(z - center) <= 1 + margin);
export interface FrenchBuilding { id: string; x: number; z: number; floors: 2 | 3 | 4; style: number }
const mainlandRadius = (x: number, z: number) => Math.hypot((x - 196) / 52, (z - 139) / 94);
const eastRadius = (x: number, z: number) => Math.hypot((x - 313) / 58, (z - 140) / 102);
// Six-block lots leave four-block streets. The central avenues lead all the way to the tower.
export const FRENCH_BUILDINGS: FrenchBuilding[] = (() => {
  const buildings: FrenchBuilding[] = [];
  for (let z = 75; z <= 195; z += 10) for (let x = 158; x <= 228; x += 10) {
    if ([[x - 2, z - 2], [x + 7, z - 2], [x - 2, z + 7], [x + 7, z + 7]].some(([px, pz]) => mainlandRadius(px, pz) > .76)) continue;
    if (Math.abs(x + 2.5 - EIFFEL.x) <= 24 && Math.abs(z + 2.5 - EIFFEL.z) <= 24) continue;
    const style = ((x * 17 + z * 11) >>> 1) % 4;
    buildings.push({ id: `paris-${x}-${z}`, x, z, floors: style === 3 ? 2 : 3, style });
  }
  for (let z = 75; z <= 195; z += 8) for (let x = 278; x <= 348; x += 8) {
    if ([[x - 2, z - 2], [x + 7, z - 2], [x - 2, z + 7], [x + 7, z + 7]].some(([px, pz]) => eastRadius(px, pz) > .78)) continue;
    if (Math.abs(x + 2.5 - ARC.x) <= 15 && Math.abs(z + 2.5 - ARC.z) <= 15) continue;
    if (Math.hypot(x + 2.5 - CAROUSEL.x, z + 2.5 - CAROUSEL.z) <= 11) continue;
    const style = (Math.floor((x - 278) / 8) * 3 + Math.floor((z - 75) / 8) * 5) % 4;
    buildings.push({ id: `paris-${x}-${z}`, x, z, floors: style === 0 ? 4 : 3, style });
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
  for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
    const legacy = x < 128 && z < 128, original = x < 64 && z < 64, oldRegion = x < 256 && z < 256;
    const centers = [[96, 32, 29, 27], [88, 94, 33, 28], [27, 96, 24, 26]];
    const radius = legacy ? original ? Math.hypot((x - 31.5) / 28, (z - 31.5) / 26) :
      Math.min(...centers.map(([cx, cz, rx, rz]) => Math.hypot((x - cx) / rx, (z - cz) / rz))) :
      oldRegion ? Math.min(mainlandRadius(x, z), Math.hypot((x - 84) / 44, (z - 209) / 32), Math.hypot((x - 224) / 23, (z - 22) / 13)) :
        Math.min(eastRadius(x, z), Math.hypot((x - 218) / 54, (z - 314) / 40), Math.hypot((x - 328) / 41, (z - 313) / 48));
    const mountain = legacy ? original ? 9 * Math.exp(-((x - 43) ** 2 + (z - 23) ** 2) / 80) :
      8 * Math.exp(-((x - 99) ** 2 + (z - 88) ** 2) / 180) : oldRegion ? 12 * Math.exp(-((x - 220) ** 2 + (z - 183) ** 2) / 260) :
        8 * Math.exp(-((x - 326) ** 2 + (z - 309) ** 2) / 400);
    let h = Math.floor(3 + Math.max(0, 1 - radius) * 9 + mountain + noise(x / 8, z / 8, seed) * 3);
    if (radius > 1) h = Math.min(h, 3);
    // A connected, sea-level river crosses the island; a sheltered plateau is buildable.
    const river = 24 + Math.sin(z / 8) * 3;
    if (original && Math.abs(x - river) < 1.6) h = Math.min(h, SEA - 1);
    if (legacy && !original && z > 68 && Math.abs(x - (82 + Math.sin(z / 12) * 4)) < 1.8) h = Math.min(h, SEA - 1);
    if (!legacy && mainlandRadius(x, z) >= 1 && z > 76 && z < 225 && Math.abs(x - (174 + Math.sin(z / 13) * 3)) < 1.5) h = Math.min(h, SEA - 1);
    if (x >= 29 && x <= 39 && z >= 35 && z <= 45) h = 10;
    if (x >= 92 && x <= 106 && z >= 31 && z <= 45) h = 10;
    if (x >= 28 && x <= 40 && z >= 92 && z <= 104) h = 10;
    if (!legacy && oldRegion) {
      const r = mainlandRadius(x, z);
      if (r <= .84) h = 8;
      else if (r < 1) h = Math.round(8 + (h - 8) * (r - .84) / .16);
    }
    if (!oldRegion) {
      const r = eastRadius(x, z);
      if (r <= .84) h = 8;
      else if (r < 1) h = Math.round(8 + (h - 8) * (r - .84) / .16);
    }
    heights[x + SIZE * z] = h;
    for (let y = 0; y <= Math.max(h, SEA); y++) {
      data[index(x, y, z)] = y > h ? Block.Water : y < h - 2 ? Block.Stone :
        h <= SEA + 1 ? Block.Sand : y === h ? (!legacy && oldRegion && mainlandRadius(x, z) <= .76 || !oldRegion && eastRadius(x, z) <= .78) ? Block.Stone : Block.Grass : Block.Dirt;
    }
  }
  for (let z = 6; z < SIZE - 6; z += 3) for (let x = 6; x < SIZE - 6; x += 3) {
    // The original 64×64 region stays byte-for-byte identical for existing saves.
    if (x < 64 && z < 64 && (x >= 58 || z >= 58)) continue;
    // The old tree loop stopped at 121; new canopies must not spill into old saves.
    if (x < 128 && z < 128 && (x >= 122 || z >= 122)) continue;
    if (x < 130 && z < 130 && (x >= 128 || z >= 128)) continue;
    // Extending the tree grid must not alter the old 256×256 boundary.
    if (x < 256 && z < 256 && (x >= 250 || z >= 250)) continue;
    const h = heights[x + SIZE * z];
    if (h <= SEA + 2 || h > 16 || hash(x, z, seed + 19) < 0.64 ||
      (x >= 27 && x <= 41 && z >= 33 && z <= 47) ||
      (x >= 90 && x <= 108 && z >= 29 && z <= 47) || (x >= 26 && x <= 42 && z >= 90 && z <= 106) ||
      (!(x < 128 && z < 128) && mainlandRadius(x, z) <= .8) ||
      (x >= 256 && eastRadius(x, z) <= .82) || inParisBridge(x, z, 4) || inArc(x, z, 5)) continue;
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
  for (let x = 238; x <= 277; x++) for (let z = center - 1; z <= center + 1; z++)
    for (const y of [7, 8]) voxels.push({ x, y, z, block: Block.Stone });
  for (const x of [244, 253, 262, 271]) for (const z of [center - 1, center + 1]) for (let y = SEA; y < 8; y++)
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
