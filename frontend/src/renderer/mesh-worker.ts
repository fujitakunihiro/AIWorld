import { meshChunk } from '../../../shared/mesher';
import { index, type Edit } from '../../../shared/world';
let data: Uint8Array;
self.onmessage = (event: MessageEvent<{ data?: Uint8Array; edits?: Edit[]; requests: { cx: number; cz: number; id: number }[] }>) => {
  if (event.data.data) data = event.data.data;
  if (!data) return;
  for (const edit of event.data.edits ?? []) data[index(edit.x, edit.y, edit.z)] = edit.block;
  for (const request of event.data.requests) {
    const result = meshChunk(data, request.cx, request.cz);
    const pack = (mesh: typeof result.solid) => ({ positions: new Float32Array(mesh.positions), normals: new Float32Array(mesh.normals), blocks: new Uint8Array(mesh.blocks), indices: new Uint32Array(mesh.indices) });
    const solid = pack(result.solid), water = pack(result.water);
    self.postMessage({ ...request, solid, water }, { transfer: [solid.positions.buffer, solid.normals.buffer, solid.blocks.buffer, solid.indices.buffer, water.positions.buffer, water.normals.buffer, water.blocks.buffer, water.indices.buffer] });
  }
};
