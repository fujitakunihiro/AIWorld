import { Block, SEA, getBlock } from '../../../shared/world';

// Read only the seabed; bridges and roofs above the water must not alter its tint.
export function waterDepthByte(data: Uint8Array, x: number, z: number) {
  let y = SEA;
  while (y > 0 && (getBlock(data, x, y, z) === Block.Air || getBlock(data, x, y, z) === Block.Water)) y--;
  return Math.round(Math.min(8, SEA - y) / 8 * 255);
}
