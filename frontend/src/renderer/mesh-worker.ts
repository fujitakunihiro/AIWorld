import { meshChunk } from '../../../shared/mesher';
import { index, type Edit } from '../../../shared/world';
import { presentationWorld } from './model-plan';
let data: Uint8Array;
let hidden: number[] = [];
self.onmessage = (event: MessageEvent<{ data?: Uint8Array; hidden?: number[]; edits?: Edit[]; requests: { cx: number; cz: number; id: number }[] }>) => {
  if (event.data.data) data = event.data.data;
  if (!data) return;
  for (const edit of event.data.edits ?? []) data[index(edit.x, edit.y, edit.z)] = edit.block;
  if (event.data.hidden) hidden = event.data.hidden;
  const display = presentationWorld(data, hidden);
  for (const request of event.data.requests) {
    const result = meshChunk(data, request.cx, request.cz);
    const remake = meshChunk(display, request.cx, request.cz);
    const pack = (mesh: typeof result.solid) => ({ positions: new Float32Array(mesh.positions), normals: new Float32Array(mesh.normals), blocks: new Uint8Array(mesh.blocks), indices: new Uint32Array(mesh.indices) });
    const solid = pack(result.solid), water = pack(result.water), diorama = pack(remake.solid);
    self.postMessage({ ...request, solid, water, diorama }, { transfer: [solid.positions.buffer, solid.normals.buffer, solid.blocks.buffer, solid.indices.buffer, water.positions.buffer, water.normals.buffer, water.blocks.buffer, water.indices.buffer, diorama.positions.buffer, diorama.normals.buffer, diorama.blocks.buffer, diorama.indices.buffer] });
  }
};
