import { Block, HEIGHT, SIZE, getBlock, index, type Edit } from '../../../shared/world';
import type { Hut, VillageState } from '../../../shared/village';

export interface TreeModel { x: number; y: number; z: number; height: number; variant: number; hidden: number[] }
export interface Decoration { x: number; y: number; z: number; kind: 'grass' | 'flower' | 'rock'; scale: number; rotation: number; density: number }
export interface ModelPlan { trees: TreeModel[]; decorations: Decoration[]; hidden: number[] }
export function variation(x: number, z: number, salt = 0) {
  let n = Math.imul(x + salt, 374761393) ^ Math.imul(z - salt, 668265263);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}

// Presentation-only recipe. No server module or gameplay mutation is imported here.
export function buildingVoxels(hut: Hut): Edit[] {
  const result: Edit[] = [];
  const add = (x: number, y: number, z: number, block: Edit['block']) => result.push({ x: hut.x + x, y: hut.y + y, z: hut.z + z, block });
  if (hut.kind === 'farm') { for (const x of [0, 3]) for (const z of [0, 3]) add(x, 0, z, Block.Wood); return result; }
  for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) add(x, 0, z, Block.Wood);
  for (let y = 1; y <= 2; y++) for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) {
    if (x !== 0 && x !== 3 && z !== 0 && z !== 3) continue;
    if (z === 3 && x === 1 || y === 2 && (x === 0 && z === 1 || x === 3 && z === 2)) continue;
    add(x, y, z, hut.kind === 'house' ? Block.Brick : Block.Wood);
  }
  for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) add(x, 3, z, hut.kind === 'warehouse' ? Block.Wood : Block.Brick);
  for (let z = 0; z < 4; z++) for (let x = 1; x <= 2; x++) add(x, 4, z, hut.kind === 'warehouse' ? Block.Wood : Block.Brick);
  if (hut.entranceStep) add(1, -1, 4, Block.Wood);
  return result;
}

export function planModels(data: Uint8Array, state?: VillageState): ModelPlan {
  const trees: TreeModel[] = [], decorations: Decoration[] = [], hidden = new Set<number>();
  const occupied = new Set<number>();
  const reserve = (x: number, z: number) => { if (x >= 0 && z >= 0 && x < SIZE && z < SIZE) occupied.add(x + z * SIZE); };
  for (const hut of state?.huts ?? []) {
    for (let z = -1; z <= 4; z++) for (let x = -1; x <= 4; x++) reserve(hut.x + x, hut.z + z);
    const voxels = buildingVoxels(hut), built = hut.status === 'complete' || hut.upgrading ? voxels : voxels.slice(0, hut.progress);
    for (const e of built) {
      const block = getBlock(data, e.x, e.y, e.z);
      if (block === e.block || hut.upgrading && block === Block.Wood) hidden.add(index(e.x, e.y, e.z));
    }
  }
  for (const bridge of state?.bridges ?? []) for (const e of bridge.blocks.slice(0, bridge.progress)) {
    reserve(e.x, e.z);
    if (getBlock(data, e.x, e.y, e.z) === e.block) hidden.add(index(e.x, e.y, e.z));
  }
  for (const node of state?.nodes ?? []) for (let z = -1; z <= 1; z++) for (let x = -1; x <= 1; x++) reserve(Math.floor(node.position.x) + x, Math.floor(node.position.z) + z);
  if (state) for (let z = -2; z <= 2; z++) for (let x = -2; x <= 2; x++) reserve(Math.floor(state.camp.x) + x, Math.floor(state.camp.z) + z);
  // Only grounded vertical trunks with the existing canopy pattern qualify as trees.
  // Arbitrary player wood/leaves and all registered structures remain untouched.
  for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) for (let y = 1; y < HEIGHT - 3; y++) {
    if (getBlock(data, x, y, z) !== Block.Wood || hidden.has(index(x, y, z))) continue;
    const ground = getBlock(data, x, y - 1, z);
    if (ground !== Block.Grass && ground !== Block.Dirt) continue;
    let top = y;
    while (top < HEIGHT && getBlock(data, x, top, z) === Block.Wood) top++;
    if (top - y < 3 || top - y > 6) continue;
    const leaves: number[] = [];
    for (let dz = -2; dz <= 2; dz++) for (let dx = -2; dx <= 2; dx++) for (let dy = 0; dy <= 2; dy++) {
      if (Math.abs(dx) + Math.abs(dz) + dy > 4) continue;
      if (getBlock(data, x + dx, top - 1 + dy, z + dz) === Block.Leaves) leaves.push(index(x + dx, top - 1 + dy, z + dz));
    }
    if (leaves.length < 8) continue;
    const cells = [...leaves]; for (let yy = y; yy < top; yy++) cells.push(index(x, yy, z));
    trees.push({ x: x + .5, y, z: z + .5, height: top - y, variant: variation(x, z, 9) > .75 ? 1 : 0, hidden: cells });
    cells.forEach(i => hidden.add(i));
    for (let dz = -1; dz <= 1; dz++) for (let dx = -1; dx <= 1; dx++) reserve(x + dx, z + dz);
  }
  for (let z = 1; z < SIZE - 1; z++) for (let x = 1; x < SIZE - 1; x++) {
    if (occupied.has(x + z * SIZE)) continue;
    let y = HEIGHT - 1; while (y > 0 && getBlock(data, x, y, z) === Block.Air) y--;
    const block = getBlock(data, x, y, z), n = variation(x, z);
    const kind = block === Block.Grass && n < .32 ? (n < .035 ? 'flower' : 'grass') : (block === Block.Stone || block === Block.Sand) && n < .045 ? 'rock' : null;
    if (!kind) continue;
    decorations.push({ x: x + .25 + variation(x, z, 4) * .5, y: y + 1, z: z + .25 + variation(x, z, 7) * .5,
      kind, scale: .65 + variation(x, z, 11) * .6, rotation: variation(x, z, 13) * Math.PI * 2, density: variation(x, z, 17) });
  }
  return { trees, decorations, hidden: [...hidden].sort((a, b) => a - b) };
}

export function presentationWorld(data: Uint8Array, hidden: Iterable<number>) {
  const result = data.slice(); for (const i of hidden) result[i] = Block.Air; return result;
}

export interface BridgeEdge { x: number; y: number; z: number; dx: number; dz: number }
export function bridgeEdges(blocks: Edit[]): BridgeEdge[] {
  const cells = new Set(blocks.map(e => `${e.x}:${e.y}:${e.z}`)), result: BridgeEdge[] = [];
  const span = (e: Edit, dx: number, dz: number) => {
    let count = 1;
    for (const sign of [-1, 1]) for (let i = 1; i <= 4; i++) {
      if (!cells.has(`${e.x + dx * i * sign}:${e.y}:${e.z + dz * i * sign}`)) break; count++;
    }
    return count;
  };
  for (const e of blocks) for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    // Leave deck ends and unfinished frontiers open for the existing walking route.
    if (!cells.has(`${e.x + dx}:${e.y}:${e.z + dz}`) && span(e, dx, dz) <= 3 && span(e, dz, dx) > 3) result.push({ ...e, dx, dz });
  }
  return result;
}
