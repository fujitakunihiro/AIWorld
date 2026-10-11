import { Block, HEIGHT, SIZE, getBlock } from '../../../shared/world';
import type { Position } from '../../../shared/village';
const directions = [[1, 0], [0, 1], [-1, 0], [0, -1]];
export class Navigation {
  private heights = new Int8Array(SIZE * SIZE).fill(-1);
  constructor(readonly data: Uint8Array) { this.rebuild(); }
  rebuild() {
    this.heights.fill(-1);
    for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
      // A two-block clearance allows walking under tree canopies, never through logs or water.
      for (let y = 1; y < HEIGHT - 1; y++) {
        const floor = getBlock(this.data, x, y - 1, z);
        if (floor !== Block.Air && floor !== Block.Water && floor !== Block.Leaves &&
          getBlock(this.data, x, y, z) === Block.Air && getBlock(this.data, x, y + 1, z) === Block.Air) {
          this.heights[x + SIZE * z] = y; break;
        }
      }
    }
  }
  height(x: number, z: number) { return x >= 0 && z >= 0 && x < SIZE && z < SIZE ? this.heights[x + SIZE * z] : -1; }
  position(x: number, z: number): Position | null {
    const y = this.height(x, z); return y >= 0 ? { x: x + 0.5, y, z: z + 0.5 } : null;
  }
  valid(position: Position) { return this.height(Math.floor(position.x), Math.floor(position.z)) === position.y; }
  neighbors(x: number, z: number) {
    const y = this.height(x, z); if (y < 0) return [];
    return directions.map(([dx, dz]) => ({ x: x + dx, z: z + dz })).filter(p => {
      const h = this.height(p.x, p.z); return h >= 0 && Math.abs(h - y) <= 1;
    });
  }
  search(start: Position) {
    const sx = Math.floor(start.x), sz = Math.floor(start.z), root = sx + SIZE * sz;
    const parents = new Int32Array(SIZE * SIZE).fill(-1), queue: number[] = [];
    if (this.height(sx, sz) < 0) return { parents, queue, root };
    parents[root] = root; queue.push(root);
    for (let i = 0; i < queue.length; i++) {
      const cell = queue[i];
      for (const next of this.neighbors(cell % SIZE, Math.floor(cell / SIZE))) {
        const id = next.x + SIZE * next.z; if (parents[id] >= 0) continue;
        parents[id] = cell; queue.push(id);
      }
    }
    return { parents, queue, root };
  }
  path(start: Position, goal: Position) {
    const search = this.search(start); return this.pathFrom(search, goal);
  }
  pathFrom(search: ReturnType<Navigation['search']>, goal: Position): Position[] | null {
    let id = Math.floor(goal.x) + SIZE * Math.floor(goal.z);
    if (!this.valid(goal) || search.parents[id] < 0) return null;
    const result: Position[] = [];
    while (id !== search.root) {
      result.push(this.position(id % SIZE, Math.floor(id / SIZE))!); id = search.parents[id];
    }
    return result.reverse();
  }
  nearest(position: Position): Position | null {
    let best: Position | null = null, distance = Infinity;
    for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) {
      const p = this.position(x, z); if (!p) continue;
      const d = Math.hypot(p.x - position.x, p.z - position.z) + Math.abs(p.y - position.y) * 0.25;
      if (d < distance) { best = p; distance = d; }
    }
    return best;
  }
}
