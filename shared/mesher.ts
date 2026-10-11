import { Block, CHUNK, HEIGHT, getBlock } from './world';
export interface MeshData { positions: number[]; normals: number[]; blocks: number[]; indices: number[] }
export function meshChunk(data: Uint8Array, cx: number, cz: number) {
  const solid: MeshData = { positions: [], normals: [], blocks: [], indices: [] };
  const water: MeshData = { positions: [], normals: [], blocks: [], indices: [] };
  const dims = [CHUNK, HEIGHT, CHUNK], origin = [cx * CHUNK, 0, cz * CHUNK];
  for (let d = 0; d < 3; d++) for (const sign of [-1, 1]) {
    const u = (d + 1) % 3, v = (d + 2) % 3;
    for (let slice = 0; slice < dims[d]; slice++) {
      const mask = new Int16Array(dims[u] * dims[v]);
      for (let j = 0; j < dims[v]; j++) for (let i = 0; i < dims[u]; i++) {
        const p = [...origin]; p[d] += slice; p[u] += i; p[v] += j;
        const a = getBlock(data, p[0], p[1], p[2]); p[d] += sign;
        const b = getBlock(data, p[0], p[1], p[2]);
        if (a !== Block.Air && (b === Block.Air || (a !== Block.Water && b === Block.Water))) mask[i + j * dims[u]] = a;
      }
      for (let j = 0; j < dims[v]; j++) for (let i = 0; i < dims[u];) {
        const block = mask[i + j * dims[u]];
        if (!block) { i++; continue; }
        let w = 1, h = 1;
        while (i + w < dims[u] && mask[i + w + j * dims[u]] === block) w++;
        outer: while (j + h < dims[v]) {
          for (let k = 0; k < w; k++) if (mask[i + k + (j + h) * dims[u]] !== block) break outer;
          h++;
        }
        const target = block === Block.Water ? water : solid;
        const start = target.positions.length / 3;
        for (const [du, dv] of [[0, 0], [w, 0], [w, h], [0, h]]) {
          const p = [...origin]; p[d] += slice + (sign > 0 ? 1 : 0); p[u] += i + du; p[v] += j + dv;
          const n = [0, 0, 0]; n[d] = sign;
          target.positions.push(...p); target.normals.push(...n); target.blocks.push(block);
        }
        target.indices.push(...(sign > 0 ? [0, 1, 2, 0, 2, 3] : [0, 2, 1, 0, 3, 2]).map(k => k + start));
        for (let row = 0; row < h; row++) for (let col = 0; col < w; col++) mask[i + col + (j + row) * dims[u]] = 0;
        i += w;
      }
    }
  }
  return { solid, water };
}
