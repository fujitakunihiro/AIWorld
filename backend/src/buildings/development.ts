import { Block, type Edit } from '../../../shared/world';
import type { BuildingKind, Hut } from '../../../shared/village';
import { HUT_COST, hutBlocks } from './hut';
export const BUILDING_COSTS = {
  hut: HUT_COST, house: { food: 0, wood: 48, stone: 20 },
  farm: { food: 0, wood: 12, stone: 4 }, warehouse: { food: 0, wood: 32, stone: 16 }
} satisfies Record<BuildingKind, Hut['cost']>;
export function buildingBlocks(building: Hut): Edit[] {
  if (building.kind === 'farm') {
    // Crops are visual instances; the corner posts make the field persistent terrain.
    return [0, 3].flatMap(x => [0, 3].map(z => ({ x: building.x + x, y: building.y, z: building.z + z, block: Block.Wood })));
  }
  const blocks = hutBlocks(building).map(edit => {
    const roof = edit.y >= building.y + 3;
    return { ...edit, block: building.kind === 'house' && !roof && edit.y > building.y ? Block.Brick : building.kind === 'warehouse' && roof ? Block.Wood : edit.block };
  });
  if (building.entranceStep) blocks.push({ x: building.x + 1, y: building.y - 1, z: building.z + 4, block: Block.Wood });
  return blocks;
}
