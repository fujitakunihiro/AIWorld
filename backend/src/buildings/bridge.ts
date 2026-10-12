import { Block, SEA, SIZE, getBlock, type Edit } from '../../../shared/world';
import type { Position } from '../../../shared/village';
import type { Bridge } from '../../../shared/autonomy';
import type { Navigation } from '../agents/navigation';
export const ISLANDS = [{ id: 'east', name: '東の島', x: 96, z: 38 }, { id: 'south', name: '南東の島', x: 96, z: 96 }, { id: 'west', name: '南西の島', x: 34, z: 98 }, { id: 'river', name: '川の向こう岸', x: 14, z: 32 }];
// Find a shortest walkable connection, adding wood only above open water.
// Multisource Dijkstra starts at every cell connected to the village.
export function planBridge(data: Uint8Array, nav: Navigation, camp: Position, island: typeof ISLANDS[number]): Bridge | null {
  const destination = nav.nearest({ x: island.x + .5, y: 7, z: island.z + .5 }); if (!destination) return null;
  const reachable = nav.search(camp), goal = Math.floor(destination.x) + SIZE * Math.floor(destination.z);
  if (reachable.parents[goal] >= 0) return null;
  const water = (x: number, z: number) => getBlock(data, x, SEA, z) === Block.Water && getBlock(data, x, SEA + 1, z) === Block.Air && getBlock(data, x, SEA + 2, z) === Block.Air;
  const height = (x: number, z: number) => nav.height(x, z) >= 0 ? nav.height(x, z) : water(x, z) ? SEA + 2 : -1;
  const costs = new Float64Array(SIZE * SIZE).fill(Infinity), parents = new Int32Array(SIZE * SIZE).fill(-1);
  const heap: { id: number; cost: number }[] = [];
  const push = (id: number, cost: number) => { let i = heap.length; heap.push({ id, cost }); while (i > 0) { const p = (i - 1) >> 1; if (heap[p].cost <= cost) break; heap[i] = heap[p]; i = p; } heap[i] = { id, cost }; };
  const pop = () => { const first = heap[0], tail = heap.pop()!; if (heap.length) { let i = 0; while (i * 2 + 1 < heap.length) { let child = i * 2 + 1; if (child + 1 < heap.length && heap[child + 1].cost < heap[child].cost) child++; if (heap[child].cost >= tail.cost) break; heap[i] = heap[child]; i = child; } heap[i] = tail; } return first; };
  for (const id of reachable.queue) { costs[id] = 0; parents[id] = id; push(id, 0); }
  while (heap.length) {
    const cell = pop(); if (cell.cost !== costs[cell.id]) continue; if (cell.id === goal) break;
    const x = cell.id % SIZE, z = Math.floor(cell.id / SIZE), y = height(x, z);
    for (const [dx, dz] of [[1, 0], [0, 1], [-1, 0], [0, -1]]) {
      const nx = x + dx, nz = z + dz; if (nx < 0 || nz < 0 || nx >= SIZE || nz >= SIZE) continue;
      const nextY = height(nx, nz); if (nextY < 0 || Math.abs(nextY - y) > 1) continue;
      const id = nx + SIZE * nz, cost = cell.cost + (water(nx, nz) ? 3 : 1);
      if (cost >= costs[id]) continue; costs[id] = cost; parents[id] = cell.id; push(id, cost);
    }
  }
  if (parents[goal] < 0) return null;
  const route: number[] = []; let id = goal;
  while (parents[id] !== id) { route.push(id); id = parents[id]; } route.push(id); route.reverse();
  const blocks: Edit[] = [], keys = new Set<string>();
  const add = (x: number, z: number, y = SEA + 1) => { const key = `${x}:${y}:${z}`; if (keys.has(key)) return; keys.add(key); blocks.push({ x, y, z, block: Block.Wood }); };
  // The center deck always precedes its side planks, so builders can advance from shore.
  route.forEach((cell, i) => {
    const x = cell % SIZE, z = Math.floor(cell / SIZE); if (!water(x, z)) return; add(x, z);
    const previous = route[Math.max(0, i - 1)], dx = x - previous % SIZE, dz = z - Math.floor(previous / SIZE);
    for (const side of [-1, 1]) { const nx = x + dz * side, nz = z - dx * side; if (nx >= 0 && nz >= 0 && nx < SIZE && nz < SIZE && water(nx, nz)) add(nx, nz); }
  });
  if (!blocks.length || blocks.length > 600) return null;
  return { id: `bridge-${island.id}`, name: `${island.name}への橋`, destination, blocks, progress: 0, cost: { food: 0, wood: blocks.length, stone: 0 }, status: 'planned', materialsReserved: false, builder: null };
}
