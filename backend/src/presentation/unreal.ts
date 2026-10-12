import { Buffer } from 'node:buffer';
import { planModels, buildingVoxels } from '../../../frontend/src/renderer/model-plan';
import { CHUNK, HEIGHT, SEA, SIZE, index } from '../../../shared/world';
import type { VillageState } from '../../../shared/village';

// Read-only adapter: the native renderer uses the same saved blocks and model masks.
// Keeping base + edits separate allows reconnect to restore removals as well as additions.
export function unrealScene(base: Uint8Array, data: Uint8Array, village: VillageState) {
  const plan = planModels(data, village);
  const dynamic = new Set(village.huts.flatMap(h => buildingVoxels(h).map(e => index(e.x, e.y, e.z))));
  for (const bridge of village.bridges) for (const e of bridge.blocks) dynamic.add(index(e.x, e.y, e.z));
  return {
    format: 1, size: SIZE, height: HEIGHT, chunk: CHUNK, sea: SEA,
    base: Buffer.from(base).toString('base64'),
    hidden: plan.hidden.filter(i => !dynamic.has(i)),
    trees: plan.trees.map(t => ({ ...t, expected: t.hidden.map(i => data[i]) })),
    decorations: plan.decorations.filter(d => d.density < .12)
  };
}
