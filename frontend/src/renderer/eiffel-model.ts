import * as THREE from 'three';
import { EIFFEL } from '../../../shared/world';
import { ModelKit, type ModelPart } from './model-kit';

// An original miniature interpretation, built from shared primitives and baked by material.
export function eiffelModel(kit: ModelKit) {
  const parts: ModelPart[] = [], bronze = '#876b53', edge = '#af8a62', dark = '#655848';
  const column = new THREE.CylinderGeometry(1, 1, 1, 6);
  const axis = new THREE.Vector3(0, 1, 0), a = new THREE.Vector3(), b = new THREE.Vector3();
  const beam = (from: number[], to: number[], thickness = .08, color = bronze) => {
    a.fromArray(from); b.fromArray(to); const direction = b.clone().sub(a), length = direction.length();
    const matrix = new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(.5), new THREE.Quaternion().setFromUnitVectors(axis, direction.normalize()), new THREE.Vector3(thickness, length, thickness));
    parts.push({ geometry: column, color, matrix, stage: 0 });
  };
  const levels = [[0, 6], [3.5, 4.5], [7, 3.35], [10, 2.25], [13, 1.3], [16, .83], [19, .45]];
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    kit.box(parts, '#b9ad92', [sx * 6, -.15, sz * 6], [2.4, .3, 2.4]);
    for (let i = 0; i < levels.length - 1; i++) {
      const [y, w] = levels[i], [nextY, nextW] = levels[i + 1];
      beam([sx * w, y, sz * w], [sx * nextW, nextY, sz * nextW], y < 7 ? .22 : .14);
    }
  }
  for (let i = 0; i < levels.length - 1; i++) {
    const [y, w] = levels[i], [ny, nw] = levels[i + 1];
    if (y < 7) continue;
    for (const s of [-1, 1]) {
      beam([-w, y, s * w], [nw, ny, s * nw]); beam([w, y, s * w], [-nw, ny, s * nw]);
      beam([s * w, y, -w], [s * nw, ny, nw]); beam([s * w, y, w], [s * nw, ny, -nw]);
      beam([-w, y, s * w], [w, y, s * w], .065, edge); beam([s * w, y, -w], [s * w, y, w], .065, edge);
    }
  }
  // Four curved entrance arches leave the centre open at ground level.
  for (const s of [-1, 1]) for (const turn of [false, true]) for (let i = 0; i < 12; i++) {
    const point = (t: number) => { const x = Math.cos(t) * 5.3, y = 1.1 + Math.sin(t) * 4.6; return turn ? [s * (6 - y * .38), y, x] : [x, y, s * (6 - y * .38)]; };
    beam(point(i / 12 * Math.PI), point((i + 1) / 12 * Math.PI), .14, edge);
  }
  for (const [y, width] of [[7, 4.05], [13, 1.95], [19, .95]]) {
    kit.box(parts, dark, [0, y, 0], [width * 2, .28, width * 2]);
    kit.box(parts, edge, [0, y + .2, 0], [width * 2 + .16, .12, width * 2 + .16]);
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) kit.part(parts, kit.round, '#f1d195', [sx * width, y + .84, sz * width], [.09, .09, .09]);
    for (const s of [-1, 1]) {
      beam([-width, y + .8, s * width], [width, y + .8, s * width], .045, edge);
      beam([s * width, y + .8, -width], [s * width, y + .8, width], .045, edge);
      const count = Math.ceil(width * 4);
      for (let j = 0; j <= count; j++) {
        const p = -width + width * 2 * j / count;
        beam([p, y + .2, s * width], [p, y + .8, s * width], .027);
        beam([s * width, y + .2, p], [s * width, y + .8, p], .027);
      }
    }
  }
  kit.box(parts, bronze, [0, 19.6, 0], [1.15, 1, 1.15]);
  beam([0, 20, 0], [0, EIFFEL.height, 0], .065, edge);
  kit.part(parts, kit.round, '#f1d195', [0, 22, 0], [.12, .12, .12]);
  // Paved paths and clipped gardens sit just above the existing flat ground.
  for (const turn of [false, true]) kit.box(parts, '#d9c9a6', [0, .02, 0], turn ? [32, .035, 3.8] : [3.8, .035, 32]);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    kit.box(parts, '#b9ad92', [sx * 11, .08, sz * 11], [6.8, .14, 6.8]);
    kit.box(parts, '#738857', [sx * 11, .2, sz * 11], [6.2, .28, 6.2]);
    for (const dz of [-2.5, 2.5]) kit.part(parts, kit.round, '#8f9e67', [sx * 11, .4, sz * 11 + dz], [2.8, .36, .42]);
    kit.box(parts, '#94724e', [sx * 8.5, .45, sz * 13.5], [2.1, .17, .65]);
    for (const dx of [-.7, .7]) kit.box(parts, dark, [sx * 8.5 + dx, .23, sz * 13.5], [.12, .45, .4]);
  }
  const group = kit.assemble(parts); column.dispose(); group.position.set(EIFFEL.x, EIFFEL.y, EIFFEL.z);
  // Visual-only miniature exaggeration makes the landmark readable above the Paris rooftops.
  group.scale.y = 1.85;
  group.userData.modelId = EIFFEL.id; return group;
}
