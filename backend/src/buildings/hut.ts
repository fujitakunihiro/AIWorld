import { Block, getBlock, inside, type Edit } from '../../../shared/world';
import type { Hut } from '../../../shared/village';
export const HUT_COST = { food: 0, wood: 24, stone: 8 };
export function hutBlocks(hut: Pick<Hut, 'x' | 'y' | 'z'>): Edit[] {
  const blocks: Edit[] = [];
  const add = (x: number, y: number, z: number, block: Edit['block']) => blocks.push({ x: hut.x + x, y: hut.y + y, z: hut.z + z, block });
  for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) add(x, 0, z, Block.Wood);
  for (let y = 1; y <= 2; y++) for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) {
    if (x !== 0 && x !== 3 && z !== 0 && z !== 3) continue;
    if (z === 3 && x === 1) continue; // A two-block-high door faces the outside path.
    if (y === 2 && ((x === 0 && z === 1) || (x === 3 && z === 2))) continue;
    add(x, y, z, Block.Wood);
  }
  for (let z = 0; z < 4; z++) for (let x = 0; x < 4; x++) add(x, 3, z, Block.Brick);
  for (let z = 0; z < 4; z++) for (let x = 1; x <= 2; x++) add(x, 4, z, Block.Brick);
  return blocks;
}
export function inHut(edit: Pick<Edit, 'x' | 'y' | 'z'>, hut: Hut) {
  return (edit.x >= hut.x && edit.x < hut.x + 4 && edit.z >= hut.z && edit.z < hut.z + 4 && edit.y >= hut.y - 1 && edit.y <= hut.y + 4) ||
    (hut.entranceStep && edit.x === hut.x + 1 && edit.z === hut.z + 4 && edit.y >= hut.y - 2 && edit.y <= hut.y + 1);
}
export function siteClear(data: Uint8Array, x: number, y: number, z: number) {
  for (let dz = 0; dz < 4; dz++) for (let dx = 0; dx < 4; dx++) {
    if (!inside(x + dx, y + 4, z + dz)) return false;
    const floor = getBlock(data, x + dx, y - 1, z + dz);
    if (floor !== Block.Grass && floor !== Block.Dirt && floor !== Block.Stone && floor !== Block.Sand) return false;
    for (let dy = 0; dy <= 4; dy++) if (getBlock(data, x + dx, y + dy, z + dz) !== Block.Air) return false;
  }
  return true;
}
